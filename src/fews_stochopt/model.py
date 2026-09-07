"""The farm model, and the four scenarios that differ only in what it knows.

There is **one** optimisation model here. The eleven R reports and eight
notebooks it replaces each carried their own copy of it, which is why a
correction to one of them never reached the others.

The model, for a set of runs sharing one investment decision:

    maximise   mean over runs of  profit[r]
    subject to profit[r] = crop revenue - water cost - electricity cost
               alt_water[r,y]  <= alt_water_cap                (capacity)
               rain[r,y] + alt_water[r,y] + irrigation[r,y] >= water[r,y]
               alt_water[r,y]*e_alt + irrigation[r,y]*e_irr <= elc[r,y]
               alt_elc[r,y]    <= alt_elc_cap * season_yield   (capacity)
               alt_elc[r,y] + utility_elc[r,y] >= elc[r,y]
               crop_yield[r,y] <= a0 + a1*water[r,y] + a2*water[r,y]^2

`alt_water_cap` and `alt_elc_cap` are the first stage; everything else is the
second. The only nonlinearity is the yield curve, which is concave, so the
feasible region is convex and Gurobi solves this as a QCP.

**The four scenarios are four groupings of the runs, nothing more.** That is the
observation the original code does not make anywhere, and it is why eleven files
were needed to express four ideas:

    perfect information   every run invests knowing its own weather
    known climate         one investment per climate, over that climate's runs
    stochastic            one investment over all 4,000 runs
    expected value        one investment against a single deterministic
                          precipitation path, then evaluated on all runs

`profit` carries Gurobi's default lower bound of zero, as it does in the
original. It is not binding on either site -- the smallest run profit observed is
about $0.77M -- and `tests/test_invariants.py` asserts that it stays slack, since
a binding non-negativity would silently truncate the loss tail and bias every
mean above.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import gurobipy as gp
import numpy as np
import pandas as pd

from fews_stochopt.config import Config
from fews_stochopt.data import (
    climate_of_run,
    expected_value_rain,
    load_precipitation,
    rain_dict,
)

# The scenario names, and the order the paper's tables use.
PERFECT_INFORMATION = "Perfect Information"
KNOWN_CLIMATE = "Known Climate, Unknown Weather"
STOCHASTIC = "Stochastic"
EXPECTED_VALUE = "Expected Value"

# A diagnostic, not one of the paper's four. It is the Expected Value scenario
# with the first stage pinned to what the published run invested, which isolates
# the second stage from the flat first-stage optimum. See reference/README.md.
EXPECTED_VALUE_PUBLISHED_FIRST_STAGE = "Expected Value (published first stage)"


@dataclass
class ScenarioResult:
    """Per-run and per-year outcomes of one scenario at one site."""

    site: str
    scenario: str
    profit: pd.DataFrame       # run, profit
    detail: pd.DataFrame       # run, year, crop_yield, water, elc, irrigation, alt_water
    investment: pd.DataFrame   # group, alt_water_cap, alt_elc_cap, n_runs
    solve_seconds: float = 0.0
    slack: dict[str, float] = field(default_factory=dict)

    def mean_profit(self) -> float:
        return float(self.profit["profit"].mean())


def _env(cfg: Config) -> gp.Env:
    params = {
        "OutputFlag": cfg.solver.get("output_flag", 0),
        "Seed": cfg.solver.get("seed", 0),
    }
    threads = cfg.solver.get("threads", 0)
    if threads:
        params["Threads"] = threads
    return gp.Env(params=params)


def _optimize(m: gp.Model, cfg: Config) -> int:
    """Optimise, working down the ladder until a rung reaches certified optimality.

    Returns that rung's index. Raises if none does -- the original code never
    read the status at all, and most single-run solves stall short of it on
    Gurobi's defaults.

    **Status OPTIMAL is not evidence that the solution is feasible**, which is a
    second trap one level in: Gurobi has been observed here returning status 2
    with a maximum violation of 2.1e-03, two thousand times its own
    `FeasibilityTol`. Gating this function on `MaxVio` was tried and is wrong --
    an absolute tolerance is the wrong instrument for a model whose quantities
    run from 0.08 to 2,000,000, and it rejected 87 of 91 solves that were
    numerically excellent in relative terms. Feasibility is enforced instead by
    `_repair`, which clips the returned point back inside the region and
    re-prices it, so what leaves this module is feasible by construction.
    """
    ladder = cfg.solver.get("parameter_ladder") or [{}]
    attempts = []
    for rung, params in enumerate(ladder):
        # Parameters must NOT accumulate. `m.reset()` clears the solution, not
        # the settings, so without this a later rung inherits every earlier
        # rung's parameters and the ladder stops testing what it names -- rung 3
        # was running with rung 1's BarHomogeneous still set, and two rungs
        # reported identical results because they were the same solve.
        m.resetParams()
        for name, value in params.items():
            m.setParam(name, value)
        m.optimize()
        if m.Status == gp.GRB.OPTIMAL:
            return rung
        attempts.append(f"rung {rung}: status {m.Status}")
    raise RuntimeError(
        "no rung of solver.parameter_ladder reached certified optimality on a "
        f"model with {m.NumVars} variables. " + "; ".join(attempts)
        + ". Nothing downstream may use this result."
    )


def _repair(
    cfg: Config,
    rain: dict[tuple[int, int], float],
    runs: list[int],
    years: list[int],
    profit: np.ndarray,
    detail: dict[str, np.ndarray],
) -> tuple[np.ndarray, dict[str, np.ndarray], float]:
    """Pull the returned point back inside the feasible region, and re-price it.

    **Gurobi returns points that violate its own tolerances while reporting
    OPTIMAL**, and the violations here are one-sided: the barrier stops just
    outside the yield curve and just outside the water balance, never inside. So
    they do not average away. Measured over 120 runs, the shipped solver rung
    overshoots the yield curve by a mean of **$1.03 per run and never less than
    zero** -- which is the same size and sign as the residual against the
    published figures, and was very nearly reported as a property of the
    published run rather than of this one.

    The repair is two clips, in order, each of which only ever *relaxes* the
    constraints it is not about:

        water     <- min(water, rain + alt_water + irrigation)   (2)
        crop_yield<- min(crop_yield, a0 + a1*water + a2*water^2) (6)

    `water` appears only in those two rows and `crop_yield` only in (6) and in
    the profit definition, so lowering either leaves every other constraint
    satisfied. Profit is then recomputed from the clipped yield.

    The result is a point that is **feasible by construction**, so the value
    reported is a valid lower bound on the model's optimum rather than a number
    just outside it. `scripts/verify_solution.py` re-checks that from outside.
    """
    a = cfg.yield_coeffs
    water = detail["water"]
    available = np.array(
        [[rain[r, y] + detail["alt_water"][i, j] + detail["irrigation"][i, j]
          for j, y in enumerate(years)]
         for i, r in enumerate(runs)]
    )
    water = np.minimum(water, available)
    curve = a.a0 + a.a1 * water + a.a2 * water * water
    clipped = np.minimum(detail["crop_yield"], curve)

    removed = detail["crop_yield"] - clipped
    profit = profit - removed.sum(axis=1) * cfg.hectares * cfg.crop_price

    detail = {**detail, "water": water, "crop_yield": clipped}
    return profit, detail, float(removed.sum() * cfg.hectares * cfg.crop_price)


def _solve_block(
    cfg: Config,
    rain: dict[tuple[int, int], float],
    runs: list[int],
    env: gp.Env,
    fixed_first_stage: tuple[float, float] | None = None,
) -> tuple[np.ndarray, dict[str, np.ndarray], tuple[float, float], int]:
    """Solve one model in which `runs` share a single investment decision.

    Returns per-run profits, per-(run, year) operational quantities, and the
    first-stage capacities. When `fixed_first_stage` is given the capacities are
    constants and the runs decouple; the model is still built as one, which is
    algebraically identical to solving them one at a time.
    """
    years = list(range(1, cfg.years + 1))
    a = cfg.yield_coeffs

    m = gp.Model(env=env)
    m.ModelSense = -1  # maximise

    if fixed_first_stage is None:
        awc: gp.Var | float = m.addVar(lb=0, name="alt_water_cap")
        aec: gp.Var | float = m.addVar(lb=0, name="alt_elc_cap")
    else:
        awc, aec = fixed_first_stage

    water = m.addVars(runs, years, lb=0, name="water")
    irrigation = m.addVars(
        runs, years, lb=0, ub=cfg.max_irrigation_water, name="irrigation_water"
    )
    alt_water = m.addVars(runs, years, lb=0, name="alt_water")
    alt_elc = m.addVars(runs, years, lb=0, name="alt_elc")
    utility_elc = m.addVars(runs, years, lb=0, name="util_elc")
    elc = m.addVars(runs, years, lb=0, name="elc")
    crop_yield = m.addVars(runs, years, lb=0, name="yield")
    # lb defaults to 0, as in the original. See the module docstring.
    profit = m.addVars(runs, obj=1.0 / len(runs), name="profit")

    m.addConstrs(
        (
            profit[r]
            == crop_yield.sum(r, "*") * cfg.hectares * cfg.crop_price
            - awc * cfg.cost_alt_water
            - irrigation.sum(r, "*") * cfg.cost_irrigation_water
            - aec * cfg.cost_alt_elc
            - utility_elc.sum(r, "*") * cfg.cost_utility_elc
            for r in runs
        ),
        name="profit_constr",
    )
    m.addConstrs(
        (alt_water[r, y] <= awc for r in runs for y in years), name="water_cap"
    )
    m.addConstrs(
        (
            rain[r, y] + alt_water[r, y] + irrigation[r, y] >= water[r, y]
            for r in runs
            for y in years
        ),
        name="water",
    )
    m.addConstrs(
        (
            alt_water[r, y] * cfg.alt_water_elc
            + irrigation[r, y] * cfg.irrigation_water_elc
            <= elc[r, y]
            for r in runs
            for y in years
        ),
        name="elc_water",
    )
    m.addConstrs(
        (alt_elc[r, y] <= aec * cfg.alt_elc_yield for r in runs for y in years),
        name="elc_cap",
    )
    m.addConstrs(
        (
            alt_elc[r, y] + utility_elc[r, y] >= elc[r, y]
            for r in runs
            for y in years
        ),
        name="elc_balance",
    )
    for r in runs:
        for y in years:
            m.addQConstr(
                crop_yield[r, y]
                <= a.a0 + a.a1 * water[r, y] + a.a2 * water[r, y] * water[r, y],
                name=f"crop_yield[{r},{y}]",
            )

    rung = _optimize(m, cfg)
    # A model that presolved to nothing would report OPTIMAL over an empty set.
    if m.NumVars == 0 or m.NumQConstrs == 0:
        raise RuntimeError(
            f"model built with {m.NumVars} variables and {m.NumQConstrs} quadratic "
            f"constraints -- the yield curve is missing, so this is not the farm model"
        )

    def grid(v: gp.tupledict) -> np.ndarray:
        return np.array([[v[r, y].X for y in years] for r in runs])

    profits = np.array([profit[r].X for r in runs])
    detail = {
        "crop_yield": grid(crop_yield),
        "water": grid(water),
        "elc": grid(elc),
        "irrigation": grid(irrigation),
        "alt_water": grid(alt_water),
        "alt_elc": grid(alt_elc),
        "utility_elc": grid(utility_elc),
    }
    # Gurobi reports OPTIMAL on points that sit just outside its own tolerances,
    # one-sidedly. Pull them back in before anything downstream sees them.
    profits, detail, repaired = _repair(cfg, rain, runs, years, profits, detail)
    caps = (
        (float(awc.X), float(aec.X))
        if fixed_first_stage is None
        else (float(awc), float(aec))
    )
    return profits, detail, caps, rung, repaired


def _assemble(
    site: str,
    scenario: str,
    years: list[int],
    blocks: list[tuple[list[int], np.ndarray, dict[str, np.ndarray], tuple[float, float]]],
    seconds: float,
) -> ScenarioResult:
    profit_rows, detail_frames, invest_rows = [], [], []
    for gi, (runs, profits, detail, caps) in enumerate(blocks):
        profit_rows.append(pd.DataFrame({"run": runs, "profit": profits}))
        n = len(runs) * len(years)
        frame = pd.DataFrame(
            {
                "run": np.repeat(runs, len(years)),
                "year": np.tile(years, len(runs)),
                **{k: v.reshape(n) for k, v in detail.items()},
            }
        )
        detail_frames.append(frame)
        invest_rows.append(
            {
                "group": gi,
                "alt_water_cap": caps[0],
                "alt_elc_cap": caps[1],
                "n_runs": len(runs),
            }
        )
    return ScenarioResult(
        site=site,
        scenario=scenario,
        profit=pd.concat(profit_rows, ignore_index=True).sort_values("run").reset_index(drop=True),
        detail=pd.concat(detail_frames, ignore_index=True)
        .sort_values(["run", "year"])
        .reset_index(drop=True),
        investment=pd.DataFrame(invest_rows),
        solve_seconds=seconds,
    )


def solve_scenario(
    cfg: Config, site: str, scenario: str, n_runs: int | None = None
) -> ScenarioResult:
    """Solve one scenario at one site.

    `n_runs` truncates the Monte Carlo sample. It exists for the smoke test and
    for a quick look; it does NOT reproduce the paper, and `run_all.py` says so
    on the way past. The truncation keeps whole climate blocks proportional so a
    short run is still a valid instance rather than one climate's worth of runs.
    """
    s = cfg.site(site)
    years = list(range(1, cfg.years + 1))
    df = load_precipitation(cfg, site)
    rain = rain_dict(df)

    blocks_runs = _run_blocks(cfg, site, n_runs)
    all_runs = [r for b in blocks_runs for r in b]

    env = _env(cfg)
    t0 = time.perf_counter()
    rungs: list[int] = []
    repaired = 0.0

    if scenario == PERFECT_INFORMATION:
        # Every run invests knowing its own weather: one group per run.
        blocks = []
        for r in all_runs:
            p, d, c, rung, fixed = _solve_block(cfg, rain, [r], env)
            repaired += fixed
            blocks.append(([r], p, d, c))
            rungs.append(rung)

    elif scenario == KNOWN_CLIMATE:
        # One investment per climate, taken over that climate's runs.
        blocks = []
        for runs in blocks_runs:
            p, d, c, rung, fixed = _solve_block(cfg, rain, runs, env)
            repaired += fixed
            blocks.append((runs, p, d, c))
            rungs.append(rung)

    elif scenario == STOCHASTIC:
        p, d, c, rung, repaired = _solve_block(cfg, rain, all_runs, env)
        blocks = [(all_runs, p, d, c)]
        rungs.append(rung)

    elif scenario == EXPECTED_VALUE:
        # Stage one: invest against the single deterministic precipitation path.
        ev_rain = expected_value_rain(cfg, site)
        _, _, caps, rung, repaired = _solve_block(
            cfg, {(0, y): v for y, v in ev_rain.items()}, [0], env
        )
        rungs.append(rung)
        # Stage two: live with that investment through every realised run.
        p, d, _, rung, fixed = _solve_block(cfg, rain, all_runs, env, fixed_first_stage=caps)
        repaired += fixed
        blocks = [(all_runs, p, d, caps)]
        rungs.append(rung)

    elif scenario == EXPECTED_VALUE_PUBLISHED_FIRST_STAGE:
        caps = published_first_stage(site)
        p, d, _, rung, fixed = _solve_block(cfg, rain, all_runs, env, fixed_first_stage=caps)
        repaired += fixed
        blocks = [(all_runs, p, d, caps)]
        rungs.append(rung)

    else:
        raise ValueError(
            f"unknown scenario {scenario!r}; expected one of "
            f"{[PERFECT_INFORMATION, KNOWN_CLIMATE, STOCHASTIC, EXPECTED_VALUE, EXPECTED_VALUE_PUBLISHED_FIRST_STAGE]}"
        )

    result = _assemble(site, scenario, years, blocks, time.perf_counter() - t0)
    result.slack = {
        # The non-negativity on profit must not bind: it would truncate the loss
        # tail and bias every mean above. tests/test_invariants.py asserts this.
        "min_profit": float(result.profit["profit"].min()),
        "solves": float(len(rungs)),
        "fallback_solves": float(sum(1 for r in rungs if r > 0)),
        "worst_rung": float(max(rungs)),
        # Total dollars clipped off by _repair. One-sided, so it is a bias.
        "repaired_dollars": float(repaired),
    }
    del env
    return result


def _run_blocks(cfg: Config, site: str, n_runs: int | None) -> list[list[int]]:
    """The run indices of each climate, truncated proportionally if asked."""
    s = cfg.site(site)
    blocks = [list(range(a, b + 1)) for a, b in s.climate_blocks]
    if n_runs is None or n_runs >= cfg.runs:
        return blocks
    if n_runs < len(blocks):
        raise ValueError(
            f"n_runs={n_runs} cannot cover {len(blocks)} climates; use at least "
            f"{len(blocks)}"
        )
    keep = [max(1, round(len(b) * n_runs / cfg.runs)) for b in blocks]
    return [b[:k] for b, k in zip(blocks, keep)]


def published_first_stage(site: str) -> tuple[float, float]:
    """The investment the published run made, from `reference/published_first_stage.csv`.

    Used only by the diagnostic scenario. Nothing that produces
    `results/solnvalues.csv` reads it -- that table is solved from source.
    """
    from fews_stochopt.config import repo_root

    path = repo_root() / "reference" / "published_first_stage.csv"
    table = pd.read_csv(path)
    row = table[table["site"] == site]
    if len(row) != 1:
        raise ValueError(
            f"{path} has {len(row)} row(s) for site {site!r}, expected exactly 1"
        )
    return (
        float(row["alt_water_cap_cm"].iloc[0]),
        float(row["alt_elc_cap_kW"].iloc[0]),
    )


def climate_labels(cfg: Config, site: str) -> pd.DataFrame:
    """`run -> climate` as a frame, for the report."""
    mapping = climate_of_run(cfg.site(site))
    return pd.DataFrame(
        {"run": list(mapping), "climate": [mapping[r] for r in mapping]}
    )
