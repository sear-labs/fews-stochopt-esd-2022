"""Freeze the collapsed instances and their solutions into `artifacts/`.

    python scripts/export_artifacts.py            # write them
    python scripts/export_artifacts.py --check    # verify the committed copies

Three files per site x scenario:

    <name>.json   the instance: five weighted precipitation blocks and the
                  coefficients, in a form `verify_solution.py` reads with nothing
                  but the standard library and numpy
    <name>.sol    the solution: every variable value, plus the objective
    <name>.lp     the same model as Gurobi writes it, for a reader who has a
                  solver and wants to re-solve rather than check

The point of shipping these is that **checking a solution needs no solver and no
licence, while re-solving needs both.** `scripts/verify_solution.py` reads the
first two and confirms feasibility and the objective from arithmetic alone.

`--check` exists because a build script and its committed output drift exactly as
fast as two pasted copies. `tests/test_artifacts.py` runs it.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import gurobipy as gp  # noqa: E402

from fews_stochopt import collapsed  # noqa: E402
from fews_stochopt.config import load_config, repo_root  # noqa: E402
from fews_stochopt.model import (  # noqa: E402
    EXPECTED_VALUE,
    KNOWN_CLIMATE,
    STOCHASTIC,
    _env,
    _optimize,
)

ROOT = repo_root()
ARTIFACTS = ROOT / "artifacts"

# Known Climate solves one model per climate, so it has four instances rather
# than one and is exported per block.
EXPORTED = [STOCHASTIC, EXPECTED_VALUE]


def slug(site: str, scenario: str) -> str:
    return f"{site}_{scenario.lower().replace(',', '').replace(' ', '_')}"


def instance(cfg, weights: dict[float, int], n_runs: int, caps=None) -> dict:
    """Everything needed to reconstruct the model, and nothing else.

    Written out rather than referenced so the verifier depends on this file
    alone -- not on `config.yaml`, not on the package. That independence is what
    makes the verification worth anything.
    """
    return {
        "description": (
            "FEWS farm model, collapsed. One weighted block per distinct "
            "precipitation value. See scripts/verify_solution.py for the "
            "constraints, written out in full."
        ),
        "n_runs": n_runs,
        "years": cfg.years,
        "blocks": [
            {"precip_cm": float(v), "run_years": int(weights[v])}
            for v in sorted(weights)
        ],
        "coefficients": {
            "hectares": cfg.hectares,
            "crop_price_per_tonne": cfg.crop_price,
            "cost_alt_water_per_cm": cfg.cost_alt_water,
            "cost_alt_elc_per_kw": cfg.cost_alt_elc,
            "cost_irrigation_water_per_cm": cfg.cost_irrigation_water,
            "cost_utility_elc_per_kwh": cfg.cost_utility_elc,
            "alt_water_kwh_per_cm": cfg.alt_water_elc,
            "irrigation_kwh_per_cm": cfg.irrigation_water_elc,
            "alt_elc_kwh_per_kw": cfg.alt_elc_yield,
            "max_irrigation_cm": cfg.max_irrigation_water,
            "yield_a0": cfg.yield_coeffs.a0,
            "yield_a1": cfg.yield_coeffs.a1,
            "yield_a2": cfg.yield_coeffs.a2,
        },
        "fixed_first_stage": (
            None if caps is None
            else {"alt_water_cap": caps[0], "alt_elc_cap": caps[1]}
        ),
    }


def solution(m: gp.Model, inst: dict, caps) -> dict:
    """The solver's point, clipped back inside the feasible region and re-priced.

    Writing the raw point would ship an artifact that `verify_solution.py`
    correctly rejects -- which is how this was found.
    """
    raw = {v.VarName: float(v.X) for v in m.getVars()}
    if caps is None:
        caps = (raw["alt_water_cap"], raw["alt_elc_cap"])
    fixed, objective = collapsed.repair_solution(
        inst["coefficients"], inst["blocks"], inst["n_runs"], raw, caps)
    return {
        "objective": objective,
        "objective_before_repair": float(m.ObjVal),
        "variables": fixed,
    }


def build_all(cfg) -> dict[str, tuple[dict, dict, str]]:
    """`{name: (instance, solution, lp_text)}` for every exported model."""
    env = _env(cfg)
    out: dict[str, tuple[dict, dict, str]] = {}
    try:
        for site in cfg.sites:
            for scenario in EXPORTED:
                caps = None
                if scenario == EXPECTED_VALUE:
                    # Its capacities come from the deterministic path; the
                    # instance being frozen is the evaluation at those capacities.
                    caps = tuple(
                        collapsed.solve(cfg, site, EXPECTED_VALUE, env=env)[k]
                        for k in ("alt_water_cap", "alt_elc_cap")
                    )
                weights, n = collapsed.rain_weights(cfg, site)
                m = collapsed.build(cfg, weights, n, env, fixed_first_stage=caps)
                _optimize(m, cfg)
                name = slug(site, scenario)
                m.write(str(_tmp_lp(name)))
                inst = instance(cfg, weights, n, caps)
                out[name] = (
                    inst,
                    solution(m, inst, caps),
                    _tmp_lp(name).read_text(encoding="utf-8"),
                )
                _tmp_lp(name).unlink()

            for k, (first, last) in enumerate(cfg.site(site).climate_blocks, start=1):
                runs = list(range(first, last + 1))
                weights, n = collapsed.rain_weights(cfg, site, runs)
                m = collapsed.build(cfg, weights, n, env)
                _optimize(m, cfg)
                name = f"{slug(site, KNOWN_CLIMATE)}_climate{k}"
                m.write(str(_tmp_lp(name)))
                inst = instance(cfg, weights, n)
                out[name] = (
                    inst,
                    solution(m, inst, None),
                    _tmp_lp(name).read_text(encoding="utf-8"),
                )
                _tmp_lp(name).unlink()
    finally:
        del env
    return out


# Gurobi can only write an LP to a path, so it goes to a real temporary
# directory. It used to go to `artifacts/` and be unlinked after reading, which
# meant `--check` DELETED the committed .lp files as a side effect -- a check
# that destroys what it is checking. tests/test_artifacts.py caught it.
_TMPDIR = Path(tempfile.mkdtemp(prefix="fews-lp-"))


def _tmp_lp(name: str) -> Path:
    return _TMPDIR / f"{name}.lp"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--check", action="store_true",
                   help="compare against the committed copies instead of writing")
    args = p.parse_args(argv)

    cfg = load_config()
    built = build_all(cfg)
    assert built, "nothing was built; there is no artifact to write or check"

    if args.check:
        stale = []
        for name, (inst, sol, lp) in built.items():
            for suffix, want in ((".json", inst), (".sol", sol)):
                path = ARTIFACTS / f"{name}{suffix}"
                if not path.exists():
                    stale.append(f"{path.name} missing")
                    continue
                got = json.loads(path.read_text(encoding="utf-8"))
                if not _same(got, want):
                    stale.append(f"{path.name} differs")
            lp_path = ARTIFACTS / f"{name}.lp"
            if not lp_path.exists():
                stale.append(f"{lp_path.name} missing")
        if stale:
            print("committed artifacts are stale: " + "; ".join(stale), file=sys.stderr)
            return 1
        print(f"committed artifacts match: {len(built)} model(s)")
        return 0

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    for name, (inst, sol, lp) in built.items():
        (ARTIFACTS / f"{name}.json").write_text(
            json.dumps(inst, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (ARTIFACTS / f"{name}.sol").write_text(
            json.dumps(sol, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (ARTIFACTS / f"{name}.lp").write_text(lp, encoding="utf-8")
        print(f"wrote artifacts/{name}.{{json,sol,lp}}   objective {sol['objective']:,.4f}")
    return 0


def _same(got, want, tol: float = 1e-9) -> bool:
    """Compare parsed JSON, allowing float round-trip slack."""
    if isinstance(want, dict):
        return isinstance(got, dict) and set(got) == set(want) and all(
            _same(got[k], want[k], tol) for k in want)
    if isinstance(want, list):
        return (isinstance(got, list) and len(got) == len(want)
                and all(_same(a, b, tol) for a, b in zip(got, want)))
    if isinstance(want, float):
        return isinstance(got, (int, float)) and abs(got - want) <= tol * max(1.0, abs(want))
    return got == want


if __name__ == "__main__":
    raise SystemExit(main())
