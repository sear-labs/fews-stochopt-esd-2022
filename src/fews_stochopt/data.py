"""Reading the committed precipitation scenarios, and slicing them by climate.

The two files `data/raw/precips_c0_{EP,DML}.csv` hold 4,000 Monte Carlo
draws of 25 years each. They are *inputs* to the optimisation, generated once by
`archive/stage2-r/superseded/FM {EP,DML} MC.Rmd`, and they are committed -- the documented exception
to the rule that generated files stay out of git.

The layout is the load-bearing fact in this module. Both R reports build their
c0 sample by concatenating the four per-climate draws and then renumbering the
runs 1..4000:

    precips_c0 <- c(precips_c1, precips_c2, precips_c3, precips_c4)
    precips_c0_tbl %>% mutate(run = rep(seq(1,4000), each=25))

so a run's climate is decided by *where it sits in the file*, and the sizes of
those four blocks are how each site's climate probabilities are encoded. For EP
the climates are equally likely and the blocks are 1000 runs each. For DML they
are 0.60/0.25/0.10/0.05 and the blocks are 2400/1000/400/200 -- which is exactly
the `run_c1 = list(range(2400))` in `archive/stage2-r/superseded/FM MI DML All Climates.Rmd`.

The consequence is worth stating plainly, because the repository's own README
records the opposite: **the per-climate inputs are not missing.** They are the
four slices of a file that ships. Nothing else has to be reconstructed to
reproduce the published table.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from fews_stochopt.config import Config, Site

REQUIRED_COLUMNS = ("run", "year", "precip")


def load_precipitation(cfg: Config, site: str) -> pd.DataFrame:
    """Return the site's draws as tidy `run, year, precip`, validated.

    Every check here guards a way the file could be wrong while still parsing --
    the shape of failure Part 6 of the standard is about. A silently short file
    would give a plausible mean and a wrong table.
    """
    path = cfg.precipitation_path(site)
    if not path.exists():
        raise FileNotFoundError(
            f"precipitation input {path} is missing. It is committed to this "
            f"repository as a documented exception; if it has been removed, "
            f"restore it with `git checkout -- {path.name}`."
        )
    df = pd.read_csv(path, index_col=0)
    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"{path} lacks column(s) {sorted(missing)}")
    df = df.astype({"run": int, "year": int, "precip": float})

    s = cfg.site(site)
    expected_rows = cfg.runs * cfg.years
    if len(df) != expected_rows:
        raise ValueError(
            f"{path} has {len(df)} rows, expected {expected_rows} "
            f"({cfg.runs} runs x {cfg.years} years)"
        )
    if sorted(df["run"].unique()) != list(range(1, cfg.runs + 1)):
        raise ValueError(f"{path} runs are not exactly 1..{cfg.runs}")
    if sorted(df["year"].unique()) != list(range(1, cfg.years + 1)):
        raise ValueError(f"{path} years are not exactly 1..{cfg.years}")

    # The draws come from a five-state Markov chain, so every value must be one
    # of the five states. A value outside them means the file was regenerated
    # with different state definitions and the published table no longer applies.
    states = np.array(sorted(cfg.weather_states.values()))
    seen = np.array(sorted(df["precip"].unique()))
    off = [v for v in seen if not np.any(np.isclose(states, v, atol=1e-9))]
    if off:
        raise ValueError(
            f"{path} contains precipitation values {off} that are not among the "
            f"five weather states {states.tolist()} in config.yaml"
        )

    _check_blocks(s, df, path)
    return df.sort_values(["run", "year"]).reset_index(drop=True)


def _check_blocks(site: Site, df: pd.DataFrame, path: Path) -> None:
    """The climate blocks must tile the run range exactly, with no gap or overlap."""
    covered: list[int] = []
    for first, last in site.climate_blocks:
        if last < first:
            raise ValueError(f"climate block [{first}, {last}] for {site.key} is empty")
        covered.extend(range(first, last + 1))
    runs = sorted(df["run"].unique())
    if covered != runs:
        raise ValueError(
            f"climate_blocks for site {site.key} do not tile runs 1..{runs[-1]} "
            f"of {path}: they cover {len(covered)} runs, "
            f"{len(set(covered))} of them distinct"
        )
    if len(site.climate_probabilities) != len(site.climate_blocks):
        raise ValueError(
            f"site {site.key} has {len(site.climate_blocks)} climate blocks but "
            f"{len(site.climate_probabilities)} probabilities"
        )
    total = sum(site.climate_probabilities)
    if not np.isclose(total, 1.0, atol=1e-12):
        raise ValueError(
            f"climate probabilities for site {site.key} sum to {total}, not 1"
        )
    # The block sizes ARE the probabilities. If they disagree, one of the two was
    # edited without the other, and every weighted mean below is quietly wrong.
    n = len(runs)
    for (first, last), p in zip(site.climate_blocks, site.climate_probabilities):
        share = (last - first + 1) / n
        if not np.isclose(share, p, atol=1e-9):
            raise ValueError(
                f"site {site.key}: climate block [{first}, {last}] is "
                f"{share:.4f} of the sample but config.yaml gives it "
                f"probability {p}. The block sizes encode the probabilities; "
                f"they cannot disagree."
            )


def rain_dict(df: pd.DataFrame) -> dict[tuple[int, int], float]:
    """`{(run, year): precip}`, the form the model indexes by."""
    return {(r, y): p for r, y, p in df.itertuples(index=False)}


def climate_of_run(site: Site) -> dict[int, int]:
    """`{run: climate index 1..4}` from the block layout."""
    out: dict[int, int] = {}
    for k, (first, last) in enumerate(site.climate_blocks, start=1):
        for r in range(first, last + 1):
            out[r] = k
    return out


def expected_value_rain(cfg: Config, site: str) -> dict[int, float]:
    """The deterministic precipitation path the expected-value farm plans against.

    Taken verbatim from `rain_dict1` / `rain_dict2` in
    `FarmModelStoch_EV_loop.ipynb`. Note that its final entries are 107 rather
    than the 106.68 the wettest Markov state actually carries; that rounding is
    in the published run and is reproduced rather than corrected. See
    `docs/reproduction-notes.md`.
    """
    s = cfg.site(site)
    path = s.expected_value_rain
    if len(path) != cfg.years:
        raise ValueError(
            f"expected_value_rain for site {site} has {len(path)} entries, "
            f"expected {cfg.years}"
        )
    return {y: path[y - 1] for y in range(1, cfg.years + 1)}


def subset_runs(
    rain: dict[tuple[int, int], float], runs: list[int]
) -> dict[tuple[int, int], float]:
    wanted = set(runs)
    return {(r, y): v for (r, y), v in rain.items() if r in wanted}
