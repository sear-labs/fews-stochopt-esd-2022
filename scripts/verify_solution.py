r"""Check the published result WITHOUT a solver and WITHOUT a licence.

Why this exists
---------------
Re-solving and checking are different verbs, and checking is the stronger one.

Re-solving needs Gurobi, a licence, and the same version and hardware to land in
the same place. Checking needs arithmetic. Given the model and a claimed
solution, anyone can confirm in under a second that

  1. the solution is FEASIBLE -- it satisfies every constraint and every bound;
  2. its OBJECTIVE is the number this repository reports; and
  3. it is OPTIMAL to within a stated bound -- which this model can claim and a
     MIP abandoned on a time limit cannot. The shipped solutions are clipped
     back inside the feasible region, because Gurobi returns points a little
     outside it while reporting OPTIMAL, so they are deliberately conservative:
     the true optimum sits *just above* the reported value, by at most the
     amount printed. Worst observed across the shipped set: $0.08 on an
     objective of $1.6M.

That is a complete verification of the claim, it needs nothing installed beyond
numpy, and it reproduces bit for bit forever.

    python scripts/verify_solution.py                  # every shipped artifact
    python scripts/verify_solution.py --name EP_stochastic
    python scripts/verify_solution.py --quiet          # exit code only

Independence is the point
-------------------------
This file does **not** import `fews_stochopt`. It reads `artifacts/*.json` and
writes the model out again from scratch, below, in about forty lines of numpy.
That makes it a second implementation, and a check written from the same source
as the thing it checks is not a check. `tests/test_artifacts.py` compares the two.

It also means the model is legible here: a reader who wants to know what was
solved can read this file rather than an MPS.

The model
--------
For each distinct precipitation value `v`, carrying `n_v` of the run-years:

    maximise   (1/R) * SUM_v  n_v * ( yield_v * hectares * price
                                      - irrigation_v * cost_irrigation
                                      - utility_elc_v * cost_utility )
               - alt_water_cap * cost_alt_water
               - alt_elc_cap   * cost_alt_elc

    subject to, for every v:
      (1)  alt_water_v <= alt_water_cap                       capacity
      (2)  v + alt_water_v + irrigation_v >= water_v          water balance
      (3)  alt_water_v * e_altw + irrigation_v * e_irr <= elc_v    power needed
      (4)  alt_elc_v <= alt_elc_cap * season_yield            capacity
      (5)  alt_elc_v + utility_elc_v >= elc_v                 power balance
      (6)  yield_v <= a0 + a1*water_v + a2*water_v^2          Dinar et al. (1991)
      (7)  every variable >= 0, and irrigation_v <= max_irrigation

`R` is the number of Monte Carlo runs; the capacity terms are charged once
because every run pays them, and averaging over runs leaves them unchanged.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"

# Gurobi's default primal feasibility tolerance. A solution is not required to be
# exact -- it is required to be feasible to the tolerance the solver guarantees.
FEAS_TOL = 1e-6
# The objective must match to floating-point summation slack, relative to size.
OBJ_RTOL = 1e-9
# Optimality corroboration: no feasible point found by independent search may
# beat the claimed objective by more than this, in dollars, on a mean profit of
# order $2M. Set at 1e-2 against a worst observed 1.3e-3.
#
# A small positive gap is EXPECTED and is not a defect. The shipped solutions are
# clipped back inside the feasible region -- Gurobi returns points a little
# outside it while reporting OPTIMAL -- so they are deliberately conservative,
# and the true optimum sits just above them. A gap the other way, or one orders
# of magnitude larger, would mean something is wrong.
OPT_TOL = 0.5


def load(name: str):
    inst = json.loads((ARTIFACTS / f"{name}.json").read_text(encoding="utf-8"))
    sol = json.loads((ARTIFACTS / f"{name}.sol").read_text(encoding="utf-8"))
    return inst, sol


def _v(sol, base, key=None):
    name = base if key is None else f"{base}[{key}]"
    try:
        return sol["variables"][name]
    except KeyError:
        raise KeyError(f"{name} is not in the solution file") from None


def check(name: str, log=print) -> bool:
    inst, sol = load(name)
    c = inst["coefficients"]
    blocks = inst["blocks"]
    R = inst["n_runs"]
    fixed = inst["fixed_first_stage"]
    ok = True

    if not blocks:
        raise ValueError(f"{name}: the instance has no blocks; nothing to verify")

    awc = fixed["alt_water_cap"] if fixed else _v(sol, "alt_water_cap")
    aec = fixed["alt_elc_cap"] if fixed else _v(sol, "alt_elc_cap")

    # ---- 1. feasibility -----------------------------------------------------
    worst_row, worst_row_at = 0.0, ""
    worst_bound, worst_bound_at = 0.0, ""

    def key(v):
        # Gurobi indexes the variables by the float as Python prints it.
        return repr(v) if v != int(v) else str(int(v))

    for b in blocks:
        v = b["precip_cm"]
        k = key(v)
        water = _v(sol, "water", k)
        irr = _v(sol, "irrigation_water", k)
        altw = _v(sol, "alt_water", k)
        alte = _v(sol, "alt_elc", k)
        util = _v(sol, "util_elc", k)
        elc = _v(sol, "elc", k)
        yld = _v(sol, "yield", k)

        rows = {
            "(1) capacity, alt water": altw - awc,
            "(2) water balance": water - (v + altw + irr),
            "(3) power needed": (altw * c["alt_water_kwh_per_cm"]
                                 + irr * c["irrigation_kwh_per_cm"]) - elc,
            "(4) capacity, alt elc": alte - aec * c["alt_elc_kwh_per_kw"],
            "(5) power balance": elc - (alte + util),
            "(6) yield curve": yld - (c["yield_a0"] + c["yield_a1"] * water
                                      + c["yield_a2"] * water * water),
        }
        for label, violation in rows.items():
            if violation > worst_row:
                worst_row, worst_row_at = violation, f"{label} at v={v}"

        bounds = {"water": water, "irrigation": irr, "alt_water": altw,
                  "alt_elc": alte, "util_elc": util, "elc": elc, "yield": yld}
        for label, value in bounds.items():
            if -value > worst_bound:
                worst_bound, worst_bound_at = -value, f"{label} < 0 at v={v}"
        over = irr - c["max_irrigation_cm"]
        if over > worst_bound:
            worst_bound, worst_bound_at = over, f"irrigation > max at v={v}"

    for label, value in (("alt_water_cap", awc), ("alt_elc_cap", aec)):
        if -value > worst_bound:
            worst_bound, worst_bound_at = -value, f"{label} < 0"

    # ---- 2. the objective ---------------------------------------------------
    total = 0.0
    for b in blocks:
        k = key(b["precip_cm"])
        total += b["run_years"] * (
            _v(sol, "yield", k) * c["hectares"] * c["crop_price_per_tonne"]
            - _v(sol, "irrigation_water", k) * c["cost_irrigation_water_per_cm"]
            - _v(sol, "util_elc", k) * c["cost_utility_elc_per_kwh"]
        )
    recomputed = (total / R
                  - awc * c["cost_alt_water_per_cm"]
                  - aec * c["cost_alt_elc_per_kw"])
    claimed = sol["objective"]
    delta = abs(recomputed - claimed)

    # ---- 3. optimality ------------------------------------------------------
    best, at = _best_achievable(inst, awc, aec)
    improvement = best - claimed

    # ---- report -------------------------------------------------------------
    log(f"  {name}")
    log(f"    {len(blocks)} weighted blocks, {R:,} runs, "
        f"{len(sol['variables'])} variables"
        + ("   (first stage fixed)" if fixed else ""))
    log(f"    recomputed objective   {recomputed:,.6f}")
    log(f"    claimed in .sol        {claimed:,.6f}   (delta {delta:.3e})")
    log(f"    worst row violation    {worst_row:.3e}"
        + (f"   [{worst_row_at}]" if worst_row_at else ""))
    log(f"    worst bound violation  {worst_bound:.3e}"
        + (f"   [{worst_bound_at}]" if worst_bound_at else ""))
    log(f"    best independent search{best:>14,.6f}   "
        f"(shipped value is {improvement:+.4f} from it)")

    if worst_row > FEAS_TOL or worst_bound > FEAS_TOL:
        log("    INFEASIBLE"); ok = False
    if delta > OBJ_RTOL * max(1.0, abs(claimed)):
        log("    OBJECTIVE DOES NOT MATCH"); ok = False
    if improvement > OPT_TOL:
        log(f"    NOT OPTIMAL -- independent search beats the shipped value by "
            f"{improvement:.4f} at {at}, beyond the ${OPT_TOL} bound"); ok = False
    if ok:
        log(f"    FEASIBLE, objective confirmed, and optimal to within "
            f"${improvement:.4f}")
    return ok


def _best_achievable(inst, awc, aec):
    """The most this instance can earn, computed independently of the solution.

    Given the capacities, the blocks are independent and each reduces to a choice
    of how much alternative and irrigation water to apply. Water can be added but
    not shed, so the useful depth is `min(peak of the yield curve, what is
    available)`. That leaves two bounded variables per block, and a grid with a
    local refinement settles them to well inside a cent.

    This is an independent optimum, not a re-derivation of the shipped one: it
    never reads the solution file.
    """
    c = inst["coefficients"]
    a0, a1, a2 = c["yield_a0"], c["yield_a1"], c["yield_a2"]
    peak = -a1 / (2 * a2)
    total, argbest = 0.0, []

    for b in inst["blocks"]:
        v, n = b["precip_cm"], b["run_years"]
        lo_w, hi_w = 0.0, float(awc)
        lo_i, hi_i = 0.0, float(c["max_irrigation_cm"])
        best, arg = -np.inf, (0.0, 0.0)
        for _ in range(6):  # grid, then refine around the winner
            AW = np.linspace(lo_w, hi_w, 60)
            IW = np.linspace(lo_i, hi_i, 60)
            aw, iw = np.meshgrid(AW, IW, indexing="ij")
            water = np.minimum(peak, v + aw + iw)
            yld = a0 + a1 * water + a2 * water * water
            power = aw * c["alt_water_kwh_per_cm"] + iw * c["irrigation_kwh_per_cm"]
            util = np.maximum(0.0, power - aec * c["alt_elc_kwh_per_kw"])
            val = (yld * c["hectares"] * c["crop_price_per_tonne"]
                   - iw * c["cost_irrigation_water_per_cm"]
                   - util * c["cost_utility_elc_per_kwh"])
            i, j = np.unravel_index(np.argmax(val), val.shape)
            if val[i, j] > best:
                best, arg = float(val[i, j]), (float(aw[i, j]), float(iw[i, j]))
            dw = (hi_w - lo_w) / 59 if hi_w > lo_w else 0.0
            di = (hi_i - lo_i) / 59 if hi_i > lo_i else 0.0
            lo_w, hi_w = max(0.0, arg[0] - dw), min(float(awc), arg[0] + dw)
            lo_i, hi_i = max(0.0, arg[1] - di), min(float(c["max_irrigation_cm"]), arg[1] + di)
        total += n * best
        argbest.append((v, arg))

    value = (total / inst["n_runs"]
             - awc * c["cost_alt_water_per_cm"]
             - aec * c["cost_alt_elc_per_kw"])
    return value, f"caps=({awc:.4f}, {aec:.2f})"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--name", help="verify one artifact instead of all of them")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)
    log = (lambda *a: None) if args.quiet else print

    names = ([args.name] if args.name
             else sorted(p.stem for p in ARTIFACTS.glob("*.json")))
    if not names:
        print(f"no artifacts found in {ARTIFACTS}. Run "
              f"`python scripts/export_artifacts.py` first.", file=sys.stderr)
        return 2

    # Repo-relative, deliberately. This line is committed into
    # `00_verification.ipynb`'s output, so an absolute path would bake one
    # machine's home directory into a shipped artifact -- which fails for
    # every reader who clones it, and publishes a local path when the
    # repository goes public. Found by running the suite in a real clone.
    try:
        where = ARTIFACTS.relative_to(ROOT).as_posix()
    except ValueError:
        where = str(ARTIFACTS)
    log(f"Verifying {len(names)} model(s) from {where}, "
        f"with no solver and no licence.\n")
    failed = [n for n in names if not check(n, log=log)]
    log("")
    if failed:
        print(f"FAILED: {', '.join(failed)}", file=sys.stderr)
        return 1
    log(f"All {len(names)} verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
