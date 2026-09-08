"""Reproduce the paper's Tables 4 and 5 from source. The one entry point.

    python scripts/run_all.py                # full reproduction, both sites
    python scripts/run_all.py --force        # ignore cached scenario output
    python scripts/run_all.py --runs 200     # fast smoke run; NOT the paper
    python scripts/run_all.py --figures      # also regenerate figures/generated/

Stage 1 solves the four scenarios at each of the two sites with Gurobi and writes
per-run output to `results/<site>/`. Stage 2 aggregates that into
`results/solnvalues.csv` (Table 4, including the EVKC column the original
pipeline never produced) and `results/simstatstrad.csv` (Table 5).

This script holds no thresholds of its own. Everything it compares against comes
from `config.yaml`, which `tests/` reads too -- the standard's Part 4 corollary
is that a tolerance written in two places is where a correction fails to reach.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# A checkout is the supported layout: the package is installed with
# `pip install -e .`, but working without that installed should not be a puzzle.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from fews_stochopt import analysis  # noqa: E402
from fews_stochopt.aggregate import (  # noqa: E402
    SCENARIOS,
    scenario_averages,
    sim_stats_table,
    value_table,
)
from fews_stochopt.config import load_config, repo_root  # noqa: E402
from fews_stochopt.data import load_precipitation  # noqa: E402
from fews_stochopt.model import EXPECTED_VALUE, STOCHASTIC  # noqa: E402
from fews_stochopt.pipeline import run_all_scenarios  # noqa: E402

ROOT = repo_root()
RESULTS = ROOT / "results"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--force", action="store_true", help="re-solve, ignoring the cache")
    p.add_argument(
        "--runs",
        type=int,
        default=None,
        metavar="N",
        help="truncate the Monte Carlo sample to about N runs (smoke test only)",
    )
    p.add_argument(
        "--sites", nargs="*", default=None, help="sites to run (default: all)"
    )
    p.add_argument(
        "--no-regenerate",
        action="store_true",
        help="skip redrawing the precipitation sample (a few seconds)",
    )
    p.add_argument(
        "--figures",
        action="store_true",
        help="also regenerate figures/generated/ from the cleaned output",
    )
    p.add_argument("--quiet", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    log = (lambda *a, **k: None) if args.quiet else print
    cfg = load_config()

    if args.runs is not None:
        log(
            f"\n*** --runs {args.runs}: this is a smoke run over a truncated sample.\n"
            f"*** It does NOT reproduce the published table and must not be quoted.\n"
        )

    log(f"config      {cfg.source}  (digest {cfg.digest()})")
    log(f"stage 1     solving {len(SCENARIOS)} scenarios at "
        f"{len(args.sites or cfg.sites)} site(s)")
    results = run_all_scenarios(
        cfg, sites=args.sites, n_runs=args.runs, force=args.force, log=log
    )

    log("stage 2     aggregating")
    RESULTS.mkdir(parents=True, exist_ok=True)

    values = value_table(cfg, results)
    stats = sim_stats_table(cfg, results)
    values.to_csv(RESULTS / "solnvalues.csv", index=False)
    stats.to_csv(RESULTS / "simstatstrad.csv", index=False)

    for site, by_scenario in results.items():
        precip = load_precipitation(cfg, site)["precip"].mean()
        averages = scenario_averages(cfg, site, by_scenario, precip)
        averages.to_csv(RESULTS / site / "scenario_averages.csv", index=False)

    # Stage 7: the cleaned output every figure and analysis reads. The per-run
    # detail written above is RAW output -- 135 MB, gitignored. This is the
    # aggregate of it, tidy and long, and small enough to commit.
    log("stage 7     cleaned output")
    regenerated = None
    if not args.no_regenerate:
        from fews_stochopt import markov
        regenerated = {s_: markov.simulate(cfg, s_) for s_ in results}
        out = RESULTS / "regenerated"
        out.mkdir(parents=True, exist_ok=True)
        for s_, frame in regenerated.items():
            frame.to_csv(out / f"precips_c0_{s_}_regenerated.csv", index=False)
    analysis.write_all(cfg, results, regenerated=regenerated, log=log)

    first_stage_table(cfg, results).to_csv(RESULTS / "first_stage.csv", index=False)
    diagnostic = expected_value_diagnostic(
        cfg, results, n_runs=args.runs, force=args.force, log=log
    )
    diagnostic.to_csv(RESULTS / "expected_value_diagnostic.csv", index=False)

    log("")
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        log(values.to_string(index=False))
    log("")
    log(f"wrote {RESULTS / 'solnvalues.csv'}")
    log(f"      {RESULTS / 'simstatstrad.csv'}")
    log(f"      {RESULTS / 'first_stage.csv'}")
    log(f"      {RESULTS / 'expected_value_diagnostic.csv'}")

    if args.figures:
        rc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "make_figures.py")],
            cwd=str(ROOT), capture_output=True, text=True,
        )
        if rc.stdout:
            log(rc.stdout.rstrip())
        if rc.stderr:
            print(rc.stderr.rstrip(), file=sys.stderr)
        if rc.returncode != 0:
            return rc.returncode

    return 0


def first_stage_table(cfg, results) -> pd.DataFrame:
    """What each scenario invested, run-weighted, beside what the paper invested."""
    published = pd.read_csv(ROOT / "reference" / "published_first_stage.csv")
    rows = []
    for site, by_scenario in results.items():
        pub = published[published["site"] == site].iloc[0]
        for scenario in SCENARIOS:
            inv = results[site][scenario].investment
            w = inv["n_runs"]
            row = {
                "site": site,
                "label": cfg.site(site).label,
                "scenario": scenario,
                "alt_water_cap_cm": float((inv["alt_water_cap"] * w).sum() / w.sum()),
                "alt_elc_cap_kW": float((inv["alt_elc_cap"] * w).sum() / w.sum()),
                "published_alt_water_cap_cm": "",
                "published_alt_elc_cap_kW": "",
            }
            # Only the expected-value first stage survives in the original source,
            # as a pair of literals in FM Traditional *.Rmd. The others lived in
            # .RData files that were never committed.
            if scenario == EXPECTED_VALUE:
                row["published_alt_water_cap_cm"] = float(pub["alt_water_cap_cm"])
                row["published_alt_elc_cap_kW"] = float(pub["alt_elc_cap_kW"])
            rows.append(row)
    return pd.DataFrame(rows)


def expected_value_diagnostic(cfg, results, n_runs=None, force=False, log=print):
    """Separate the flat first stage from the second stage that follows it.

    Seven of the eight scenario means reproduce from source to within a dollar.
    The eighth, Dry Most Likely / Expected Value, does not -- because its
    first-stage investment solves a deterministic problem whose objective is flat,
    so two capacities 0.08% apart are equally good there and earn $20 apart over
    the realised runs.

    Re-solving that second stage at the capacities the published run actually used
    separates the two. If the result lands within a dollar of the published mean,
    the difference is entirely the first stage and the second stage is sound. That
    is what lets `tests/` assert a wide tolerance on one figure without the wide
    tolerance hiding anything: the narrow check sits right beside it.
    """
    from fews_stochopt.model import EXPECTED_VALUE_PUBLISHED_FIRST_STAGE
    from fews_stochopt.pipeline import Paths, run_scenario

    published = pd.read_csv(ROOT / "reference" / "published_first_stage.csv")
    paths = Paths(ROOT)
    rows = []
    log("diagnostic  expected value at the published first stage")
    for site, by_scenario in results.items():
        pub = published[published["site"] == site].iloc[0]
        pinned = run_scenario(
            cfg,
            site,
            EXPECTED_VALUE_PUBLISHED_FIRST_STAGE,
            paths,
            n_runs=n_runs,
            force=force,
            log=log,
        )
        rows.append(
            {
                "site": site,
                "label": cfg.site(site).label,
                "mean_profit_own_first_stage": by_scenario[EXPECTED_VALUE].mean_profit(),
                "mean_profit_published_first_stage": pinned.mean_profit(),
                "published_alt_water_cap_cm": float(pub["alt_water_cap_cm"]),
                "published_alt_elc_cap_kW": float(pub["alt_elc_cap_kW"]),
                "stochastic_mean_profit": by_scenario[STOCHASTIC].mean_profit(),
                "vss_own_first_stage": by_scenario[STOCHASTIC].mean_profit()
                - by_scenario[EXPECTED_VALUE].mean_profit(),
                "vss_published_first_stage": by_scenario[STOCHASTIC].mean_profit()
                - pinned.mean_profit(),
            }
        )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    raise SystemExit(main())
