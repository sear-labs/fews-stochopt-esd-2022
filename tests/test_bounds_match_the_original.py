"""Every variable bound in the port matches the original, extracted not remembered.

**Porting a model equation-by-equation misses bounds by construction.** A bound is
not an equation; it sits among the variable declarations, often far from anything
that looks like a constraint, and a diff of the constraints cannot find it.

That failure is not hypothetical. The session reproducing Jones and Leibowicz
(2019) found its gurobipy port 1.70 units low against GAMS — relative 2.3e-5,
too small to see and far too large to be arithmetic — after confirming all 107
equations had counterparts. The cause was a single `.fx` line fixing one variable
to zero, 130 lines from any constraint. This suite exists so the same class of
defect cannot hide here.

What the original actually sets, extracted from every `addVar`/`addVars` call in
both canonical notebooks and every Python chunk of the superseded R reports:

    every variable        lb = 0
    irrigation_water      ub = max_irrigation_water   <- the ONLY non-default ub
    profit                lb = 0 by Gurobi's default, never written explicitly
    nothing anywhere      no post-hoc .LB / .UB / setAttr assignment

The last line is the one that matters most, and it is asserted rather than
assumed: a bound set after construction is exactly what an eye-check misses.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import gurobipy as gp
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Skip the whole module rather than fail to collect it. These tests build
# and solve models, so they genuinely need a licence -- but a module-level
# import of `model` or `collapsed` raises at COLLECTION time, and without
# --continue-on-collection-errors that aborts the entire suite. A reader
# without a licence then sees no results at all rather than the stages they
# can run. Measured in a real clone with gurobipy blocked.
pytest.importorskip("gurobipy", reason="these tests build and solve models")

from fews_stochopt import collapsed  # noqa: E402
from fews_stochopt.config import load_config  # noqa: E402
from fews_stochopt.data import load_precipitation, rain_dict  # noqa: E402
from fews_stochopt.model import _env, _solve_block  # noqa: E402

# A bound set after a variable is created, in any form Gurobi accepts.
POST_HOC = re.compile(r"\.(LB|UB)\s*=|setAttr\(\s*['\"](LB|UB)['\"]|\.(lb|ub)\s*=")


# The sources that actually built the published scenarios. Named explicitly
# rather than globbed, because `superseded/` also holds ABANDONED VARIANTS of a
# different model -- `Farm Model Original.ipynb` and `FarmModelStoch.ipynb`
# declare integer `pick_c*` variables that the canonical model has none of.
# Globbing swept those in and made this suite report an upper bound the published
# model does not have. That was the scan's error, not a finding.
CANONICAL = (
    "archive/stage1-python/FarmModelStoch_EV_loop.ipynb",     # Expected Value
    "archive/stage1-python/FarmModelStoch_PI_loop.ipynb",     # Perfect Information
    "archive/stage2-r/superseded/FM MI EP All Climates.Rmd",  # Stochastic + Known Climate, EP
    "archive/stage2-r/superseded/FM MI DML All Climates.Rmd", # ... and DML
)


def original_sources() -> list[Path]:
    paths = [ROOT / p for p in CANONICAL]
    missing = [p.name for p in paths if not p.exists()]
    assert not missing, f"canonical source(s) missing: {missing}"
    return paths


def source_text(path: Path) -> str:
    if path.suffix != ".ipynb":
        return path.read_text(encoding="utf-8", errors="replace")
    nb = json.loads(path.read_text(encoding="utf-8"))
    return "\n".join(
        "".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"
    )


def test_the_scan_covers_the_originals():
    """Guards every check below against passing over an empty set."""
    sources = original_sources()
    assert len(sources) == 4, f"expected 4 canonical sources, found {len(sources)}"
    text = "\n".join(source_text(p) for p in sources)
    assert text.count("addVar") > 30, (
        f"found only {text.count('addVar')} variable declarations; the scan is "
        f"not reading the sources it thinks it is"
    )


def test_the_post_hoc_bound_probe_can_fire():
    """A search that must return zero has to be shown capable of returning one."""
    assert POST_HOC.search("x.UB = 5")
    assert POST_HOC.search('m.setAttr("LB", v, 0)')
    assert POST_HOC.search("alt_water_cap.LB = 3")
    assert not POST_HOC.search("m.addVars(year, lb=0, ub=max_irrigation_water)")


def test_the_original_sets_no_bound_after_construction():
    """The defect class that an equation-by-equation port cannot see."""
    offenders = []
    for path in original_sources():
        for i, line in enumerate(source_text(path).splitlines(), start=1):
            if POST_HOC.search(line):
                offenders.append(f"{path.name}:{i}: {line.strip()[:80]}")
    assert not offenders, (
        "the original sets bounds outside the variable declarations, which this "
        "port does not reproduce:\n  " + "\n  ".join(offenders)
    )


def test_irrigation_is_the_only_non_default_upper_bound():
    """Extracted from the sources, not recalled."""
    text = "\n".join(source_text(p) for p in original_sources())
    calls = re.findall(r"m\.addVars?\((.*?)\)", text, re.S)
    assert calls, "no addVar calls parsed"

    with_ub = [c for c in calls if re.search(r"\bub\s*=", c)]
    assert with_ub, "no upper bounds found at all; the parse is wrong"
    for call in with_ub:
        assert "irrigation_water" in call, (
            f"a variable other than irrigation_water carries an upper bound: {call.strip()[:120]}"
        )
        assert "max_irrigation_water" in call, (
            f"irrigation_water's upper bound is not max_irrigation_water: {call.strip()[:120]}"
        )


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def test_the_shipped_lp_files_bound_only_irrigation():
    """The frozen instances are the record; read the bounds out of them.

    An `.lp` written by Gurobi lists a Bounds section naming every variable whose
    bounds are not the default. If anything but irrigation appears there, the
    port and the original disagree about the feasible region -- and the
    objectives can still match while that is true, because an unbinding bound
    changes nothing until the instance moves.
    """
    lps = sorted((ROOT / "artifacts").glob("*.lp"))
    assert len(lps) == 12, f"expected 12 LP files, found {len(lps)}"
    for path in lps:
        text = path.read_text(encoding="utf-8")
        assert "Bounds" in text, f"{path.name} has no Bounds section at all"
        section = text.split("Bounds", 1)[1]
        for keyword in ("Generals", "Binaries", "End"):
            section = section.split(keyword, 1)[0]
        bounded = [ln.strip() for ln in section.splitlines() if ln.strip()]
        # `Constant = 1` is Gurobi's own artificial variable, written whenever the
        # objective carries a constant term -- which the fixed-first-stage models
        # do, because their capacity costs are numbers rather than variables. It
        # is a serialisation artifact, not part of the model.
        bounded = [ln for ln in bounded if not ln.startswith("Constant")]
        assert bounded, f"{path.name} declares no bounds"
        for line in bounded:
            assert "irrigation_water" in line, (
                f"{path.name} bounds something other than irrigation_water: {line}"
            )


def test_no_shipped_model_has_an_integer_variable():
    """The canonical model is a pure QCP.

    Two abandoned notebooks in `archive/stage1-python/superseded/` declare integer
    `pick_c*` variables.
    If one of those formulations ever leaked into the port, the model would stop
    being convex and every claim about certified optimality would weaken.
    """
    for path in sorted((ROOT / "artifacts").glob("*.lp")):
        text = path.read_text(encoding="utf-8")
        for keyword in ("Generals", "Binaries", "Semi-Continuous"):
            assert keyword not in text, (
                f"{path.name} contains a {keyword} section; the model is no "
                f"longer a pure convex QCP"
            )


def test_the_collapsed_model_carries_the_same_bounds(cfg):
    """The second implementation must not have quietly relaxed anything.

    A bound present in one implementation and absent in the other is the same
    defect one level up, and the objectives can still agree while it is there --
    an unbinding bound changes nothing until the instance moves.
    """
    env = _env(cfg)
    try:
        weights, n = collapsed.rain_weights(cfg, "EP")
        m = collapsed.build(cfg, weights, n, env)
        by_name = {v.VarName: v for v in m.getVars()}
        assert by_name, "the collapsed model has no variables"

        # Gurobi returns float('inf') for an unbounded variable, not GRB.INFINITY
        # (1e100). Comparing against the constant makes every variable look
        # bounded, which is how this test first "found" nine of them.
        bounded = {n_: v for n_, v in by_name.items() if v.UB < float("inf")}
        assert bounded, "the collapsed model has no upper bounds at all"
        assert all(n_.startswith("irrigation_water") for n_ in bounded), (
            f"the collapsed model bounds something the original does not: "
            f"{sorted(set(n_.split('[')[0] for n_ in bounded))}"
        )
        for v in bounded.values():
            assert v.UB == pytest.approx(cfg.max_irrigation_water)
        for v in by_name.values():
            assert v.LB == 0.0, f"{v.VarName} has lb {v.LB}, not 0"
        del m
    finally:
        del env


def test_the_discrepancy_has_the_sign_a_conservative_solve_should(cfg):
    """A sign check, in the shape the SAV session named.

    For a MAXIMISATION, reproducing *below* the reference means either an extra
    restriction or a conservative point; reproducing *above* would mean a missing
    one. Every scenario here reproduces at or slightly below, which is what the
    feasibility repair is designed to produce -- it clips to a feasible point, so
    the value is a lower bound.

    An extra binding constraint would show up somewhere else too: the
    published-first-stage diagnostic would also come back low, and it does not
    (within $0.50). So the sign is explained by the repair rather than by a
    missing restriction, and this test records that reasoning where it will be
    re-read rather than in prose that will not.
    """
    import csv

    path = ROOT / "results" / "expected_value_diagnostic.csv"
    if not path.exists():
        pytest.skip("run `python scripts/run_all.py` first")
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    assert rows, "the diagnostic table parsed to zero rows"
    published = {"Equally Probable": 0.488689677613507,
                 "Dry Most Likely": 940.899927688976}
    tol = cfg.tolerances["value_of_information_abs_dollars"]
    for r in rows:
        got = float(r["vss_published_first_stage"])
        want = published[r["label"]]
        assert abs(got - want) <= tol, (
            f"{r['label']}: at the published first stage VSS is {got:.4f} against "
            f"{want:.4f}. If this were also low, the low reproduction would point "
            f"at an extra constraint rather than at the first stage."
        )
