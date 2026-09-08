"""Shared fixtures. The important one runs the pipeline exactly once.

**This file exists because of a defect a clean clone found and a warm tree could
not.** Several tests read what stage 1 wrote -- the per-run CSVs, the solver
provenance stamps, the rendered reports. On the machine the work was done on,
those were already there, so every test passed no matter what order it ran in. On
a fresh clone they are not, and pytest collects `test_invariants.py` and
`test_r_report.py` before `test_reproduces_paper.py`, so four tests failed on the
first run and passed on the second.

A suite that passes only the second time is broken for the stranger it is written
for, and it fails in a way that reads as a real defect rather than as an ordering
problem. So the dependency is declared rather than left to alphabetical order:
anything needing solved output asks for `pipeline_run`, and it runs once per
session for whichever test reaches it first.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture(scope="session")
def pipeline_run():
    """Run `scripts/run_all.py` once, and return its root.

    Cold this takes about seven minutes; warm, seconds -- `run_all.py` reuses
    solved scenarios whose configuration, inputs, source and solver version all
    match. See `src/fews_stochopt/pipeline.py`.
    """
    # A reader without a licence gets a skip, not nineteen errors. Measured in a
    # real clone with gurobipy blocked: the pipeline tests failed at fixture
    # setup, and pytest reports that as an ERROR per test -- which reads as a
    # broken repository rather than as the documented CI exemption behaving
    # correctly. The cache is gitignored, so a clone has neither solver nor
    # cached solves and cannot run this stage at all.
    if not HAS_SOLVER:
        pytest.skip("needs a Gurobi licence to solve; see the CI exemption")

    runner = ROOT / "scripts" / "run_all.py"
    assert runner.exists(), (
        "scripts/run_all.py is missing -- nothing regenerates the paper's numbers"
    )
    proc = subprocess.run(
        [sys.executable, str(runner), "--quiet"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    # Both streams and the return code. Printing only stdout is how a failing
    # script comes to look like one that did nothing.
    if proc.returncode != 0:
        pytest.fail(
            f"scripts/run_all.py exited {proc.returncode}\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
        )

    # A clean exit is not evidence that anything was written. Check the outputs.
    for name in (
        "solnvalues.csv",
        "simstatstrad.csv",
        "first_stage.csv",
        "expected_value_diagnostic.csv",
    ):
        path = ROOT / "results" / name
        assert path.exists(), f"run_all.py exited 0 but did not write {name}"
    stamps = sorted((ROOT / "results").glob("*/*.meta.json"))
    assert len(stamps) >= 8, (
        f"run_all.py exited 0 but left only {len(stamps)} solver provenance "
        f"stamp(s); the scenarios were not solved"
    )
    return ROOT


def _has_solver() -> bool:
    """Whether gurobipy can be imported at all."""
    import importlib.util

    try:
        return importlib.util.find_spec("gurobipy") is not None
    except (ImportError, ValueError):
        return False


HAS_SOLVER = _has_solver()

needs_solver = pytest.mark.skipif(
    not HAS_SOLVER,
    reason="needs a Gurobi licence; see the CI exemption in CLAUDE.md",
)
