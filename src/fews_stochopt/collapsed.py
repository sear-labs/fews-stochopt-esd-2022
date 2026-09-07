"""The same model, written at the size it actually is.

`model.py` writes out every run and every year, as the original notebooks did:
704,002 variables for the stochastic scenario. That size is an accident of how
the model was expressed, not a property of the problem.

**Given the first-stage capacities, nothing couples one `(run, year)` to
another.** Every constraint is either a capacity bound on `(r, y)` or a balance
within it. And precipitation takes exactly five values. So the 100,000
second-stage blocks are 100,000 copies of five distinct problems, and the model
is the same one with those five carrying integer weights:

    maximise   (1/R) * sum_v  n_v * (yield revenue - water cost - power cost)_v
                 - alt_water_cap * cost - alt_elc_cap * cost

with `n_v` the number of run-years at precipitation `v` and `R` the run count.
Thirty-seven variables. Milliseconds instead of forty seconds.

**The one thing that could break the equivalence** is `profit[r] >= 0`, which is
the only constraint spanning the years of a run. It is nowhere near binding --
the smallest run profit is $769,058 -- and `test_profit_non_negativity_never_binds`
asserts that independently. If it ever bound, this module would be wrong and
`model.py` would still be right.

This is deliberate duplication of the kind Part 4 of the code standard describes,
so it carries the obligation that comes with it:
`tests/test_collapsed_agrees.py` solves both and compares them. Two
implementations of one model with nothing checking they agree is how a fix
reaches three places out of four.

Why it is worth having a second implementation at all:

- **It fits the free licence.** `pip install gurobipy` ships a licence capped at
  2,000 variables. 37 fits; 704,002 does not. That is the difference between a
  reader running this and a reader watching it fail.
- **It is better conditioned.** Measured against the published figures, the
  collapsed solve lands closer than the full one at both sites.
- **It makes the instance shippable.** A 37-variable model serialises to an
  `.mps` a reader can check by hand; a 704,002-variable one does not.
"""
from __future__ import annotations

from collections import Counter

import gurobipy as gp
import numpy as np

from fews_stochopt.config import Config
from fews_stochopt.data import expected_value_rain, load_precipitation
from fews_stochopt.model import (
    EXPECTED_VALUE,
    KNOWN_CLIMATE,
    STOCHASTIC,
    _env,
    _optimize,
)

# The scenarios this module can express. Perfect Information cannot be collapsed:
# every run chooses its own capacities, so the runs share nothing to aggregate
# over. It does not need to be -- a single run is 178 variables and already fits
# any licence.
COLLAPSIBLE = (STOCHASTIC, KNOWN_CLIMATE, EXPECTED_VALUE)


def rain_weights(cfg: Config, site: str, runs: list[int] | None = None):
    """`({precipitation: run-years at it}, number of runs)` for a set of runs."""
    df = load_precipitation(cfg, site)
    if runs is not None:
        df = df[df["run"].isin(set(runs))]
    n_runs = df["run"].nunique()
    if n_runs == 0:
        raise ValueError(f"no runs selected for site {site}")
    counts = Counter(df["precip"].tolist())
    if sum(counts.values()) != n_runs * cfg.years:
        raise ValueError(
            f"{site}: {sum(counts.values())} run-years over {n_runs} runs is not "
            f"{n_runs * cfg.years}; the sample is ragged and cannot be collapsed"
        )
    return dict(counts), n_runs


def build(
    cfg: Config,
    weights: dict[float, int],
    n_runs: int,
    env: gp.Env,
    fixed_first_stage: tuple[float, float] | None = None,
) -> gp.Model:
    """One weighted block per distinct precipitation value."""
    if not weights:
        raise ValueError("no precipitation weights: nothing to build")
    a = cfg.yield_coeffs
    values = sorted(weights)

    m = gp.Model(env=env)
    m.ModelSense = -1

    if fixed_first_stage is None:
        awc: gp.Var | float = m.addVar(lb=0, name="alt_water_cap")
        aec: gp.Var | float = m.addVar(lb=0, name="alt_elc_cap")
    else:
        awc, aec = fixed_first_stage

    water = m.addVars(values, lb=0, name="water")
    irrigation = m.addVars(
        values, lb=0, ub=cfg.max_irrigation_water, name="irrigation_water"
    )
    alt_water = m.addVars(values, lb=0, name="alt_water")
    alt_elc = m.addVars(values, lb=0, name="alt_elc")
    utility_elc = m.addVars(values, lb=0, name="util_elc")
    elc = m.addVars(values, lb=0, name="elc")
    crop_yield = m.addVars(values, lb=0, name="yield")

    m.setObjective(
        gp.quicksum(
            weights[v]
            * (
                crop_yield[v] * cfg.hectares * cfg.crop_price
                - irrigation[v] * cfg.cost_irrigation_water
                - utility_elc[v] * cfg.cost_utility_elc
            )
            for v in values
        )
        / n_runs
        - awc * cfg.cost_alt_water
        - aec * cfg.cost_alt_elc
    )

    m.addConstrs((alt_water[v] <= awc for v in values), name="water_cap")
    m.addConstrs(
        (v + alt_water[v] + irrigation[v] >= water[v] for v in values), name="water"
    )
    m.addConstrs(
        (
            alt_water[v] * cfg.alt_water_elc
            + irrigation[v] * cfg.irrigation_water_elc
            <= elc[v]
            for v in values
        ),
        name="elc_water",
    )
    m.addConstrs(
        (alt_elc[v] <= aec * cfg.alt_elc_yield for v in values), name="elc_cap"
    )
    m.addConstrs(
        (alt_elc[v] + utility_elc[v] >= elc[v] for v in values), name="elc_balance"
    )
    for v in values:
        m.addQConstr(
            crop_yield[v] <= a.a0 + a.a1 * water[v] + a.a2 * water[v] * water[v],
            name=f"crop_yield[{v}]",
        )
    m.update()
    return m


def solve(
    cfg: Config,
    site: str,
    scenario: str,
    env: gp.Env | None = None,
) -> dict:
    """Solve a collapsible scenario and return its value and first stage.

    `Known Climate` returns the run-weighted mean over its four climate blocks,
    which is what the aggregation takes; the per-climate values come back too.
    """
    if scenario not in COLLAPSIBLE:
        raise ValueError(
            f"{scenario!r} cannot be collapsed; the runs share no structure to "
            f"aggregate over. Collapsible scenarios are {list(COLLAPSIBLE)}."
        )
    own_env = env is None
    env = env if env is not None else _env(cfg)
    try:
        if scenario == STOCHASTIC:
            weights, n = rain_weights(cfg, site)
            m = build(cfg, weights, n, env)
            _optimize(m, cfg)
            return _result(m, n)

        if scenario == KNOWN_CLIMATE:
            blocks, total = [], 0
            for first, last in cfg.site(site).climate_blocks:
                runs = list(range(first, last + 1))
                weights, n = rain_weights(cfg, site, runs)
                m = build(cfg, weights, n, env)
                _optimize(m, cfg)
                blocks.append({**_result(m, n), "n_runs": n})
                total += n
            value = sum(b["objective"] * b["n_runs"] for b in blocks) / total
            return {
                "objective": value,
                "alt_water_cap": float(
                    np.average([b["alt_water_cap"] for b in blocks],
                               weights=[b["n_runs"] for b in blocks])
                ),
                "alt_elc_cap": float(
                    np.average([b["alt_elc_cap"] for b in blocks],
                               weights=[b["n_runs"] for b in blocks])
                ),
                "blocks": blocks,
            }

        # EXPECTED_VALUE: the deterministic path collapses too -- 25 years over
        # five distinct values -- and then the realised runs are evaluated at the
        # capacities it chose.
        path = expected_value_rain(cfg, site)
        det_weights = dict(Counter(path.values()))
        m = build(cfg, det_weights, 1, env)
        _optimize(m, cfg)
        caps = (m.getVarByName("alt_water_cap").X, m.getVarByName("alt_elc_cap").X)

        weights, n = rain_weights(cfg, site)
        m2 = build(cfg, weights, n, env, fixed_first_stage=caps)
        _optimize(m2, cfg)
        return {
            "objective": m2.ObjVal,
            "alt_water_cap": caps[0],
            "alt_elc_cap": caps[1],
            "deterministic_objective": m.ObjVal,
        }
    finally:
        if own_env:
            del env


def _result(m: gp.Model, n_runs: int) -> dict:
    return {
        "objective": float(m.ObjVal),
        "alt_water_cap": float(m.getVarByName("alt_water_cap").X),
        "alt_elc_cap": float(m.getVarByName("alt_elc_cap").X),
        "n_runs": n_runs,
    }


def repair_solution(coefficients: dict, blocks: list[dict], n_runs: int,
                    variables: dict[str, float], caps: tuple[float, float]):
    """The same clip `model._repair` applies, for a collapsed solution.

    Gurobi returns points a little outside its own tolerances, one-sidedly, so a
    solution written straight out of the solver is not quite feasible. Clip
    `water` to what is available and `crop_yield` to the curve, then re-price.
    Both clips only relax the constraints they are not about, so the result is
    feasible by construction -- which is what `scripts/verify_solution.py`
    checks, from outside, with no solver.

    Returns `(variables, objective)`.
    """
    c = coefficients
    awc, aec = caps
    out = dict(variables)
    total = 0.0
    for b in blocks:
        v = b["precip_cm"]
        k = repr(v) if v != int(v) else str(int(v))
        aw = out[f"alt_water[{k}]"]
        iw = out[f"irrigation_water[{k}]"]
        water = min(out[f"water[{k}]"], v + aw + iw)
        curve = (c["yield_a0"] + c["yield_a1"] * water
                 + c["yield_a2"] * water * water)
        yld = min(out[f"yield[{k}]"], curve)
        out[f"water[{k}]"] = water
        out[f"yield[{k}]"] = yld
        total += b["run_years"] * (
            yld * c["hectares"] * c["crop_price_per_tonne"]
            - iw * c["cost_irrigation_water_per_cm"]
            - out[f"util_elc[{k}]"] * c["cost_utility_elc_per_kwh"]
        )
    objective = (total / n_runs
                 - awc * c["cost_alt_water_per_cm"]
                 - aec * c["cost_alt_elc_per_kw"])
    return out, objective
