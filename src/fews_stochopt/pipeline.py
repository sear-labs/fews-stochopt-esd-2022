"""Running the scenarios, caching their output, and stamping it with provenance.

A full reproduction is eight solves and takes a few minutes, most of it in the
two scenarios that solve one model per run. Re-solving that on every `pytest`
invocation would train people not to run `pytest`, so results are cached.

**A cache is only safe if it can tell it is stale**, and a mtime cannot. Each
scenario's output therefore carries a sidecar `.meta.json` holding a digest of
everything that could change the answer: the configuration, the precipitation
input, the source of every module that builds or solves the model, the run
count, and the solver version. Any difference and the scenario is re-solved.
`--force` bypasses it entirely.

This is the same reasoning as the standard's rule that a generated artifact needs
something checking that regenerating reproduces it -- here the check runs before
the reuse rather than after it.
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import dataclass
from pathlib import Path

import gurobipy as gp
import pandas as pd

from fews_stochopt import __version__
from fews_stochopt.aggregate import SCENARIOS
from fews_stochopt.config import Config, repo_root
from fews_stochopt.model import ScenarioResult, solve_scenario

# Every module whose source can change a number. Listed rather than globbed, so
# adding a module is a deliberate decision about whether it affects results.
_SOURCE_MODULES = ("config.py", "data.py", "model.py", "aggregate.py",
                   "names.py")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _source_digest() -> str:
    here = Path(__file__).resolve().parent
    h = hashlib.sha256()
    for name in _SOURCE_MODULES:
        p = here / name
        if not p.exists():
            raise RuntimeError(f"expected source module {p} is missing")
        h.update(name.encode())
        h.update(_sha256(p).encode())
    return h.hexdigest()[:16]


def provenance(cfg: Config, site: str, scenario: str, n_runs: int | None) -> dict:
    return {
        "package_version": __version__,
        "config_digest": cfg.solve_digest(),
        "source_digest": _source_digest(),
        "input_sha256": _sha256(cfg.precipitation_path(site))[:16],
        "site": site,
        "scenario": scenario,
        "n_runs": n_runs if n_runs is not None else cfg.runs,
        "gurobi": ".".join(str(v) for v in gp.gurobi.version()),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }


def _matches(stamp: dict, want: dict) -> bool:
    """Compare only the fields that can change a number.

    `platform` and `python` are recorded but deliberately not compared: they are
    provenance, not inputs, and treating them as inputs would discard a valid
    cache on every interpreter patch release.
    """
    keys = (
        "package_version",
        "config_digest",
        "source_digest",
        "input_sha256",
        "site",
        "scenario",
        "n_runs",
        "gurobi",
    )
    return all(stamp.get(k) == want.get(k) for k in keys)


@dataclass
class Paths:
    root: Path

    def scenario_dir(self, site: str) -> Path:
        return self.root / "results" / site

    def profit(self, site: str, scenario: str) -> Path:
        return self.scenario_dir(site) / f"{_slug(scenario)}_profit.csv"

    def detail(self, site: str, scenario: str) -> Path:
        return self.scenario_dir(site) / f"{_slug(scenario)}_detail.csv"

    def investment(self, site: str, scenario: str) -> Path:
        return self.scenario_dir(site) / f"{_slug(scenario)}_investment.csv"

    def meta(self, site: str, scenario: str) -> Path:
        return self.scenario_dir(site) / f"{_slug(scenario)}.meta.json"


def _slug(scenario: str) -> str:
    return scenario.lower().replace(",", "").replace(" ", "_")


def run_scenario(
    cfg: Config,
    site: str,
    scenario: str,
    paths: Paths,
    n_runs: int | None = None,
    force: bool = False,
    log=print,
) -> ScenarioResult:
    want = provenance(cfg, site, scenario, n_runs)
    meta_path = paths.meta(site, scenario)

    if not force and meta_path.exists():
        try:
            stamp = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            stamp = {}
        needed = [
            paths.profit(site, scenario),
            paths.detail(site, scenario),
            paths.investment(site, scenario),
        ]
        if _matches(stamp, want) and all(p.exists() for p in needed):
            log(f"  {site:>4} {scenario:<32} cached")
            return ScenarioResult(
                site=site,
                scenario=scenario,
                profit=pd.read_csv(needed[0]),
                detail=pd.read_csv(needed[1]),
                investment=pd.read_csv(needed[2]),
                solve_seconds=float(stamp.get("solve_seconds", 0.0)),
                slack=stamp.get("slack", {}),
            )

    result = solve_scenario(cfg, site, scenario, n_runs=n_runs)
    log(f"  {site:>4} {scenario:<32} solved in {result.solve_seconds:6.1f}s")

    paths.scenario_dir(site).mkdir(parents=True, exist_ok=True)
    result.profit.to_csv(paths.profit(site, scenario), index=False)
    result.detail.to_csv(paths.detail(site, scenario), index=False)
    result.investment.to_csv(paths.investment(site, scenario), index=False)
    meta_path.write_text(
        json.dumps(
            {**want, "solve_seconds": result.solve_seconds, "slack": result.slack},
            indent=2,
        ),
        encoding="utf-8",
    )
    return result


def run_all_scenarios(
    cfg: Config,
    sites: list[str] | None = None,
    n_runs: int | None = None,
    force: bool = False,
    log=print,
) -> dict[str, dict[str, ScenarioResult]]:
    paths = Paths(repo_root())
    sites = sites if sites is not None else list(cfg.sites)
    out: dict[str, dict[str, ScenarioResult]] = {}
    for site in sites:
        out[site] = {
            scenario: run_scenario(
                cfg, site, scenario, paths, n_runs=n_runs, force=force, log=log
            )
            for scenario in SCENARIOS
        }
    return out
