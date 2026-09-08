"""Recovering the weather transition matrix that was lost before the split.

`archive/stage2-r/markov_chain.Rmd` and both `FM * MC.Rmd` reports open by reading
`~/Coding/Data/Farm_Model/trans_matrix.csv`, a 20x20 matrix over the states
`c1w1 .. c4w5`. **That file exists nowhere.** It was already gone when this
repository was carved out of the original archive, and nothing in the R sources
creates it -- every one of them reads it.

What it is *for* is generating the precipitation draws. Those draws are committed
(`data/raw/precips_c0_{EP,DML}.csv`), so nothing about reproducing the
paper's table needs the matrix. What needs it is re-running the generation step,
which is the only part of the pipeline the committed inputs do not cover.

## What can honestly be recovered, and what cannot

The draws are 4,000 sequences of 25 states each per site, and the states are
recoverable exactly because precipitation takes only five distinct values. So the
per-climate 5x5 blocks can be **estimated** from the transition counts.

Two limits, stated rather than buried, because an estimate presented as the
original is worse than a missing file:

- **It is a maximum-likelihood estimate from 96,000 transitions, not the matrix
  itself.** Standard errors on each row are of order 0.005. Regenerating draws
  from it will produce a statistically similar sample, never the committed one.
- **The 12 off-diagonal 5x5 blocks cannot be recovered at all.** A run never
  changes climate: `FM * MC.Rmd` picks a climate, then draws 25 years from that
  climate's chain alone. So the data contains zero between-climate transitions,
  and zero observations is not evidence of zero probability. They are written as
  zeros and flagged, because that is what the pipeline's own use of the matrix
  assumes -- it only ever slices out the four diagonal blocks.

The reconstruction is therefore useful for one thing: making the generation step
runnable again. It is not the published input, and
`reference/reconstructed/` is named so nobody mistakes it for one.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from fews_stochopt.config import Config
from fews_stochopt.data import load_precipitation

STATE_NAMES = ("w1", "w2", "w3", "w4", "w5")


def state_sequences(cfg: Config, site: str) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """The draws as integer state indices, shaped (runs, years), plus the blocks."""
    df = load_precipitation(cfg, site)
    levels = np.array([cfg.weather_states[s] for s in STATE_NAMES])
    wide = (
        df.pivot(index="run", columns="year", values="precip")
        .sort_index()
        .to_numpy()
    )
    # argmin over |value - level| is exact here: the five levels are far apart
    # relative to the 1e-9 tolerance load_precipitation already enforced.
    states = np.abs(wide[:, :, None] - levels[None, None, :]).argmin(axis=2)
    return states, list(cfg.site(site).climate_blocks)


def transition_counts(states: np.ndarray) -> np.ndarray:
    """5x5 counts of state i followed by state j, over consecutive years."""
    counts = np.zeros((5, 5), dtype=np.int64)
    frm = states[:, :-1].ravel()
    to = states[:, 1:].ravel()
    np.add.at(counts, (frm, to), 1)
    return counts


def estimate_climate_matrix(states: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Row-normalised transition probabilities, and the counts behind them.

    A state the sample never visits leaves its row **unidentified**, and it is
    returned as NaN rather than as zeros. Zeros would assert that those
    transitions are impossible, which is a claim the data does not make and which
    would propagate silently into anything regenerating draws from the result.
    The dry climates never reach the wettest state, so this is not hypothetical.
    """
    counts = transition_counts(states)
    totals = counts.sum(axis=1, keepdims=True)
    probs = np.full(counts.shape, np.nan)
    seen = totals.ravel() > 0
    probs[seen] = counts[seen] / totals[seen]
    return probs, counts


def reconstruct(cfg: Config, site: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The 20x20 matrix and a per-row report of how much data is behind it.

    Returns `(matrix, provenance)`. The matrix is block diagonal by construction;
    `provenance` carries the observation count and a crude standard error for
    each row, so a reader can see which rows are well determined.
    """
    states, blocks = state_sequences(cfg, site)
    labels = [f"c{k}{w}" for k in range(1, len(blocks) + 1) for w in STATE_NAMES]
    n = len(labels)
    matrix = np.zeros((n, n))
    rows = []

    for k, (first, last) in enumerate(blocks):
        block_states = states[first - 1 : last]
        probs, counts = estimate_climate_matrix(block_states)
        matrix[k * 5 : (k + 1) * 5, k * 5 : (k + 1) * 5] = probs
        for i, w in enumerate(STATE_NAMES):
            total = int(counts[i].sum())
            # Largest standard error over the row: sqrt(p(1-p)/n), maximised at p=0.5.
            se = (
                float(np.sqrt(np.max(probs[i] * (1 - probs[i])) / total))
                if total
                else float("nan")
            )
            rows.append(
                {
                    "state": f"c{k + 1}{w}",
                    "climate": k + 1,
                    "transitions_observed": total,
                    "identified": bool(total),
                    "max_row_standard_error": se,
                }
            )

    frame = pd.DataFrame(matrix, index=labels, columns=labels)
    identified = ~np.isnan(frame.to_numpy()).any(axis=1)
    if not identified.any():
        raise AssertionError(
            "no transition row could be identified at all -- the reconstruction "
            "found nothing to estimate, which is a failure and not a result"
        )
    sums = frame.to_numpy()[identified].sum(axis=1)
    if not np.allclose(sums, 1.0, atol=1e-12):
        raise AssertionError(
            f"identified transition rows do not sum to 1: {sums[~np.isclose(sums, 1.0)]}"
        )
    return frame, pd.DataFrame(rows)


def pooled_reconstruct(cfg: Config, site: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The same estimate, pooling each climate's rows into one distribution.

    The row-wise estimate above turns out to show something: within a climate,
    every row is the same to within its own sampling error. Climate 1's rows all
    read about (0.20, 0.50, 0.25, 0.05, 0.00) whatever state they start from.
    **The chain is a sequence of independent draws**, not a chain with memory --
    the climate fixes a weather distribution and each year samples it afresh.

    That is worth knowing on its own, and it also closes the gap the row-wise
    estimate cannot: a state nobody visits has no row of its own to estimate, but
    under row homogeneity it has the same row as every other state in its block.
    This function returns that pooled matrix, complete, together with the evidence
    for the homogeneity it assumes -- `max_row_deviation` against
    `max_row_standard_error`. If the first is not small relative to the second,
    the assumption is wrong and the pooled matrix should not be used.
    """
    states, blocks = state_sequences(cfg, site)
    labels = [f"c{k}{w}" for k in range(1, len(blocks) + 1) for w in STATE_NAMES]
    matrix = np.zeros((len(labels), len(labels)))
    rows = []

    for k, (first, last) in enumerate(blocks):
        block_states = states[first - 1 : last]
        probs, counts = estimate_climate_matrix(block_states)
        pooled = counts.sum(axis=0) / counts.sum()
        matrix[k * 5 : (k + 1) * 5, k * 5 : (k + 1) * 5] = np.tile(pooled, (5, 1))

        identified = ~np.isnan(probs).any(axis=1)
        deviation = (
            float(np.abs(probs[identified] - pooled).max()) if identified.any() else float("nan")
        )
        n = int(counts.sum())
        se = float(np.sqrt(np.max(pooled * (1 - pooled)) / counts[identified].sum(axis=1).min()))
        rows.append(
            {
                "climate": k + 1,
                "transitions_observed": n,
                "rows_identified": int(identified.sum()),
                **{f"p_{w}": float(p) for w, p in zip(STATE_NAMES, pooled)},
                "max_row_deviation": deviation,
                "max_row_standard_error": se,
                "homogeneous_within_3_se": bool(deviation < 3 * se),
            }
        )

    frame = pd.DataFrame(matrix, index=labels, columns=labels)
    if not np.allclose(frame.to_numpy().sum(axis=1), 1.0, atol=1e-12):
        raise AssertionError("pooled transition rows do not sum to 1")
    return frame, pd.DataFrame(rows)


def write_reconstruction(cfg: Config, site: str, out_dir) -> dict[str, str]:
    from pathlib import Path

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    matrix, provenance = reconstruct(cfg, site)
    pooled, pooled_provenance = pooled_reconstruct(cfg, site)
    written = {
        "rowwise": out_dir / f"trans_matrix_reconstructed_{site}.csv",
        "rowwise_provenance": out_dir / f"trans_matrix_reconstructed_{site}_provenance.csv",
        "pooled": out_dir / f"trans_matrix_reconstructed_{site}_pooled.csv",
        "pooled_provenance": out_dir / f"trans_matrix_reconstructed_{site}_pooled_provenance.csv",
    }
    matrix.to_csv(written["rowwise"])
    provenance.to_csv(written["rowwise_provenance"], index=False)
    pooled.to_csv(written["pooled"])
    pooled_provenance.to_csv(written["pooled_provenance"], index=False)
    return {k: str(v) for k, v in written.items()}


# ---------------------------------------------------------------------------
# Generation. Ported from markov_chain.Rmd, which is archived verbatim
# under archive/stage2-r/ and is no longer maintained.
# ---------------------------------------------------------------------------

def simulate(
    cfg: Config,
    site: str,
    seed: int = 12345,
    iters: int = 1000,
    matrix: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Draw a fresh precipitation sample, the way the original R did.

    **This does not reproduce the committed draws and cannot.** The original set
    `set.seed(12345)` but its sample depended on RNG state accumulated through
    earlier chunks, so the exact sequence is unrecoverable. What is checkable is
    that a fresh sample has the same distribution, which
    `analysis.compare_precipitation` does.

    The output goes to `results/regenerated/`, never over
    `data/raw/precips_c0_*.csv`. An input a later stage can overwrite is not an
    input.

    The R used `markovchain::rmarkovchain`; this is the same walk in numpy, which
    drops two dependencies from a step that is now reproducible. It also stays
    correct if the matrix ever stops being row-homogeneous, which the estimate
    says it currently is.
    """
    s = cfg.site(site)
    if matrix is None:
        path = (
            Path(__file__).resolve().parents[2]
            / "reference" / "reconstructed" / f"trans_matrix_{site}.csv"
        )
        if not path.exists():
            raise FileNotFoundError(
                f"{path} is missing. Run `python scripts/reconstruct_markov.py` "
                f"first -- the original transition matrix was lost before this "
                f"repository was split out and is estimated from the committed draws."
            )
        matrix = pd.read_csv(path, index_col=0)

    rng = np.random.default_rng(seed)
    levels = np.array([cfg.weather_states[w] for w in STATE_NAMES])
    n_climates = len(s.climate_blocks)

    blocks = []
    for k in range(n_climates):
        block = matrix.to_numpy()[k * 5 : (k + 1) * 5, k * 5 : (k + 1) * 5]
        if not np.allclose(block.sum(axis=1), 1.0, atol=1e-9):
            raise ValueError(f"{site} climate {k + 1}: transition rows do not sum to 1")
        blocks.append(block)

    # The climate mixture IS the site: FM {EP,DML} MC.Rmd draws
    # `iters * 4 * probability` runs from each climate, concatenates them, then
    # renumbers 1..4000. Reproduced exactly, because the run index encodes the
    # climate and everything downstream depends on that.
    counts = [round(p * iters * n_climates) for p in s.climate_probabilities]
    if sum(counts) != iters * n_climates:
        raise ValueError(
            f"{site}: climate counts {counts} sum to {sum(counts)}, not "
            f"{iters * n_climates}"
        )

    draws = []
    for block, n in zip(blocks, counts):
        # Start from the chain's own stationary distribution rather than a fixed
        # state, which is what a memoryless chain implies and avoids a burn-in.
        start_p = block.sum(axis=0) / block.sum()
        for _ in range(n):
            state = rng.choice(5, p=start_p)
            row = np.empty(cfg.years, dtype=int)
            for y in range(cfg.years):
                state = rng.choice(5, p=block[state])
                row[y] = state
            draws.append(row)

    states = np.array(draws)
    # Rounded to two decimals, reproducing the original's string round-trip:
    # `gsub('w2', as.character(w2p), ...)` prints the shortest form within 15
    # significant digits, so the committed files hold exactly 26.67 while the
    # unrounded product is 26.669999999999998. Without the round-trip a
    # comparison by value finds no matches at all.
    precip = np.round(levels[states], 2)

    runs = np.repeat(np.arange(1, len(states) + 1), cfg.years)
    years = np.tile(np.arange(1, cfg.years + 1), len(states))
    return pd.DataFrame({"run": runs, "year": years, "precip": precip.reshape(-1)})
