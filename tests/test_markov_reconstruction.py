"""The Markov layer: the reconstructed matrix, and the generator ported from it.

Two halves. The first checks that `reference/reconstructed/` still matches what
`scripts/reconstruct_markov.py` produces. The second is the acceptance test for
`markov.simulate`, the port of `markov_chain.Rmd` -- which is a *generator*
producing model inputs, not a report, whatever directory it was filed under.

A ported analysis layer has no objective to reconcile on, so its acceptance test
has to be invented, and the original's RNG state was never recorded. That leaves
a distributional comparison as the strongest check available.

The committed reconstruction still matches what the script produces.

`reference/reconstructed/` holds an estimate of `trans_matrix.csv`, the input that
was lost before this repository was split out. A generated artifact and the script
that generates it drift exactly as fast as two pasted copies, and for the same
reason -- nobody compares them. This is that comparison.

Proven to fire: perturbing one cell of the committed matrix by 1e-6 turns
`--check` red and names the file. See `docs/reproduction-notes.md`.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fews_stochopt import markov  # noqa: E402
from fews_stochopt.config import load_config  # noqa: E402
from fews_stochopt.data import load_precipitation  # noqa: E402
from fews_stochopt.markov import pooled_reconstruct, reconstruct  # noqa: E402

RECONSTRUCTED = ROOT / "reference" / "reconstructed"


def test_committed_reconstruction_is_not_stale():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "reconstruct_markov.py"), "--check"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"reconstruct_markov.py --check exited {proc.returncode}\n"
        f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
    )
    assert "matches" in proc.stdout, f"unexpected output: {proc.stdout!r}"


def test_the_committed_files_exist():
    """Guards against the check above passing over nothing."""
    files = sorted(RECONSTRUCTED.glob("*.csv"))
    assert len(files) == 3, f"expected 3 CSVs in {RECONSTRUCTED}, found {len(files)}"


def test_rows_within_a_climate_are_homogeneous():
    """The estimate's central finding, asserted rather than described.

    Within a climate every transition row is the same to within sampling error:
    the chain has no memory, and each year is an independent draw from that
    climate's weather distribution. The pooled matrix -- which is what fills the
    two rows no run ever visits -- is only defensible because of this.
    """
    cfg = load_config()
    for site in cfg.sites:
        _, provenance = pooled_reconstruct(cfg, site)
        assert len(provenance) == 4, f"{site}: expected 4 climates"
        assert provenance["homogeneous_within_3_se"].all(), (
            f"{site}: at least one climate's rows are not homogeneous, so the "
            f"pooled matrix rests on an assumption the data contradicts:\n"
            f"{provenance.to_string(index=False)}"
        )


def test_the_two_sites_agree_on_the_underlying_matrix():
    """EP and DML are independent samples; their estimates should coincide.

    This is the strongest available evidence that the reconstruction recovers the
    original rather than the sample. The two sets of draws were generated in
    different R sessions from the same matrix, so an estimate that depended on the
    sample would not agree across them.
    """
    cfg = load_config()
    ep, _ = pooled_reconstruct(cfg, "EP")
    dml, _ = pooled_reconstruct(cfg, "DML")
    difference = np.abs(ep.to_numpy() - dml.to_numpy())
    assert difference.max() < 0.02, (
        f"the two sites' reconstructions differ by up to {difference.max():.4f}, "
        f"more than sampling error explains"
    )


def test_unidentified_rows_are_recorded_not_invented():
    """A state nobody visits gets NaN in the row-wise estimate, never zeros.

    Zeros would assert those transitions impossible, which the data does not say.
    Both sites have exactly two such rows: the driest climate never reaches the
    wettest state, and the wettest never reaches the driest.
    """
    cfg = load_config()
    for site in cfg.sites:
        matrix, provenance = reconstruct(cfg, site)
        unidentified = provenance.loc[~provenance["identified"], "state"].tolist()
        assert unidentified == [f"c1{'w5'}", f"c4{'w1'}"], (
            f"{site}: unidentified rows are {unidentified}, expected c1w5 and c4w1"
        )
        for state in unidentified:
            # NaN within the state's own climate block. The off-diagonal blocks
            # are zero for every row -- a run never changes climate -- so the
            # unidentified part is the 5 columns of its own climate.
            climate = state[:2]
            block = [c for c in matrix.columns if c.startswith(climate)]
            assert len(block) == 5
            assert matrix.loc[state, block].isna().all(), (
                f"{site}: row {state} has no observations but is not NaN"
            )
            others = [c for c in matrix.columns if not c.startswith(climate)]
            assert (matrix.loc[state, others] == 0).all(), (
                f"{site}: row {state} has non-zero mass outside its own climate"
            )
        identified = provenance.loc[provenance["identified"], "state"]
        assert len(identified) == 18
        for state in identified:
            assert matrix.loc[state].sum() == pytest.approx(1.0, rel=1e-12)


# ---------------------------------------------------------------------------
# The generator's own acceptance test.
#
# `markov.simulate` is a port of `markov_chain.Rmd`, and porting an analysis
# layer offers no objective to reconcile on -- so the acceptance test has to be
# invented. The individual draws are unrecoverable (the original's RNG state was
# never recorded), which leaves a distributional comparison as the strongest
# check available. `analysis.precipitation_table` computes exactly that
# comparison and writes it to `results/clean/precipitation_states.csv`, where
# until now **nothing asserted it**: the column could have gone to zeros and the
# CSV would still have looked complete.
# ---------------------------------------------------------------------------

RAW_LEVELS = {"w1": 5, "w2": 15, "w3": 30, "w4": 45, "w5": 60}


def test_a_fresh_sample_has_the_committed_distribution():
    """The invented acceptance test: same distribution, never the same draws.

    Tolerance is set by sampling error, not by taste. At 800 runs per site a
    share near 0.25 carries a standard error of about 0.0022, so 0.02 is roughly
    nine of them -- loose enough never to flake, tight enough that a generator
    drawing from the wrong distribution cannot pass.
    """
    pytest.importorskip("gurobipy", reason="`analysis` reaches `model`; see CLAUDE.md")
    # Imported here, not at module scope. `analysis` reaches `aggregate`, which
    # imports `model`, which imports gurobipy -- so a module-level import makes
    # this whole file uncollectable without a licence, and every test in it is
    # otherwise pure numpy and pandas over committed CSVs. Measured: it was a
    # module-level import until running the suite on a simulated licence-free
    # machine showed three modules failing to collect, this one needlessly.
    from fews_stochopt import analysis

    cfg = load_config()
    fresh = {s: markov.simulate(cfg, s, iters=200) for s in cfg.sites}
    table = analysis.precipitation_table(cfg, fresh)

    assert len(table) == 10, f"expected 5 states x 2 sites, got {len(table)}"
    assert table["regenerated_share"].notna().all(), (
        "the regenerated column is empty, so the comparison never happened"
    )
    worst = (table["committed_share"] - table["regenerated_share"]).abs().max()
    assert worst < 0.02, (
        f"a regenerated share differs from the committed one by {worst:.4f}, "
        f"more than sampling error explains:\n{table.to_string(index=False)}"
    )


def test_the_state_values_survive_the_formatting_round_trip():
    """The round-trip is load-bearing, and it fails as an empty join.

    The original turned states into numbers with `as.character`, which prints
    the shortest form within 15 significant digits -- so the committed files
    hold exactly `26.67` where `15 * 2.54 * 0.7` is `26.669999999999998`. **All
    five states are affected, not only that one.** A port computing the exact
    product matches nothing, and the symptom is a join returning no rows, which
    reads as a missing file rather than as a precision difference.

    Verified by injecting it: with both round-trips removed, the regenerated
    share is 0.0 for five of five states at both sites.
    """
    cfg = load_config()
    committed = {
        site: set(load_precipitation(cfg, site)["precip"].unique()) for site in cfg.sites
    }

    for name, inches in RAW_LEVELS.items():
        state = cfg.weather_states[name]
        exact = inches * 2.54 * 0.7
        assert exact != state, (
            f"{name}: the unrounded product equals the committed value, so this "
            f"test no longer demonstrates anything. Check the conversion."
        )
        for site, values in committed.items():
            assert state in values, (
                f"{site}: weather state {name} = {state!r} appears nowhere in the "
                f"committed precipitation file. The round-trip at config.py has "
                f"been removed or changed; comparisons by value will now find "
                f"no matches and report an empty join."
            )


def test_the_generator_emits_only_committed_state_values():
    """The second round-trip, which absorbs a defect in the first.

    `simulate` rounds again after indexing the levels. That looked redundant
    until the config-level round was removed as an experiment and this one
    silently absorbed it -- so a check aimed at only one of the two would have
    reported that the defect had no effect. Both are asserted.
    """
    cfg = load_config()
    expected = set(cfg.weather_states.values())
    for site in cfg.sites:
        produced = set(markov.simulate(cfg, site, iters=40)["precip"].unique())
        assert produced <= expected, (
            f"{site}: generated precipitation values {sorted(produced - expected)!r} "
            f"are not among the five weather states {sorted(expected)!r}"
        )
