"""The shipped artifacts and the walkthrough still match what generates them.

Three committed things here are build outputs: `artifacts/`, produced by
`scripts/export_artifacts.py`, and `notebooks/00_walkthrough.ipynb`, produced by
`scripts/build_walkthrough.py`. A build script and its output drift exactly as
fast as two pasted copies, and for the same reason -- nobody compares them.

The verifier gets its own test because it is the repository's central claim: that
the published result can be checked with no solver and no licence. A claim like
that is worth nothing if nobody runs it.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

ARTIFACTS = ROOT / "artifacts"
VERIFICATION = ROOT / "notebooks" / "00_verification.ipynb"
EXAMPLE = ROOT / "notebooks" / "01_example.ipynb"
NOTEBOOKS = (VERIFICATION, EXAMPLE)


def _run(script: str, *args):
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *args],
        cwd=str(ROOT), capture_output=True, text=True,
    )


def test_the_artifacts_exist_and_are_small_enough_to_ship():
    """Guards against every check below passing over an empty directory."""
    jsons = sorted(ARTIFACTS.glob("*.json"))
    sols = sorted(ARTIFACTS.glob("*.sol"))
    lps = sorted(ARTIFACTS.glob("*.lp"))
    assert len(jsons) == 12, f"expected 12 instances, found {len(jsons)}"
    assert len(sols) == len(jsons), "every instance needs its solution"
    assert len(lps) == len(jsons), "every instance needs its LP form"

    total = sum(p.stat().st_size for p in ARTIFACTS.iterdir() if p.is_file())
    # The ship-the-artifact pattern dies at GitHub's 100 MB limit, which an MPS
    # reaches at roughly 2M nonzeros. This model is three orders inside that, and
    # if it ever were not, the collapse has stopped working.
    assert total < 5_000_000, f"artifacts total {total:,} bytes; something grew"


def test_verifying_needs_no_solver_and_no_licence():
    """The central claim, exercised.

    `verify_solution.py` imports numpy and the standard library, and nothing
    else. If it ever grew a gurobipy import the claim would be false while every
    other test stayed green.
    """
    source = (ROOT / "scripts" / "verify_solution.py").read_text(encoding="utf-8")
    for forbidden in ("import gurobipy", "from gurobipy", "import fews_stochopt",
                      "from fews_stochopt"):
        assert forbidden not in source, (
            f"verify_solution.py contains `{forbidden}`. It must depend on "
            f"neither a solver nor this package, or it is not an independent check."
        )

    proc = _run("verify_solution.py")
    assert proc.returncode == 0, (
        f"verify_solution.py exited {proc.returncode}\n"
        f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
    )
    assert "All 12 verified." in proc.stdout, proc.stdout[-2000:]


def test_committed_artifacts_are_not_stale():
    proc = _run("export_artifacts.py", "--check")
    assert proc.returncode == 0, (
        f"export_artifacts.py --check exited {proc.returncode}\n"
        f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
    )


def test_every_shipped_solution_is_feasible_and_priced_correctly():
    """Read the verifier's own numbers rather than trusting its exit code."""
    proc = _run("verify_solution.py")
    lines = proc.stdout.splitlines()
    confirmed = [ln for ln in lines if "FEASIBLE, objective confirmed" in ln]
    assert len(confirmed) == 12, (
        f"{len(confirmed)} of 12 artifacts confirmed:\n{proc.stdout[-2000:]}"
    )


def _code(path):
    nb = json.loads(path.read_text(encoding="utf-8"))
    return "\n".join(
        "".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"
    )


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_the_notebooks_are_thin(path):
    """Part 4: they import the package and hold no model logic.

    A notebook that rebuilds the model is a second copy with nothing comparing
    it to the first. These may call the package and read files; they may not
    define the model.
    """
    code = _code(path)
    assert code.strip(), f"{path.name} has no code cells"
    for forbidden in ("addQConstr", "addConstrs(", "ModelSense", "setObjective"):
        assert forbidden not in code, (
            f"{path.name} builds a model: it contains `{forbidden}`. It must "
            f"call fews_stochopt instead."
        )
    assert "import fews_stochopt" in code or "from fews_stochopt" in code


def test_the_verification_notebook_needs_no_solver():
    """Archetype P: the two notebooks make different claims, and this is the
    stronger one. If it grew a `gurobipy` import, checking the paper would start
    depending on being able to run it -- which is what splitting them prevents.
    """
    code = _code(VERIFICATION)
    for forbidden in ("import gurobipy", "from gurobipy", "collapsed.solve",
                      "solve_scenario", "run_all.py"):
        assert forbidden not in code, (
            f"00_verification.ipynb contains `{forbidden}`. It must claim the "
            f"published result is correct WITHOUT needing a solver."
        )
    assert "verify_solution.py" in code, (
        "00_verification.ipynb does not run the verifier, which is its whole claim"
    )


def test_the_example_notebook_actually_solves_something():
    """And the weaker claim must actually be made, or the split is cosmetic."""
    code = _code(EXAMPLE)
    assert "collapsed.solve" in code, (
        "01_example.ipynb never solves anything; it is not an example"
    )
    assert "import gurobipy" in code


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_the_notebooks_shipped_executed_and_without_errors(path):
    """Rule 5's documented exception: a reader sees the outputs without running.

    Also checks no cell errored, which a committed notebook can easily do while
    still looking complete.
    """
    nb = json.loads(path.read_text(encoding="utf-8"))
    code_cells = [c for c in nb["cells"] if c["cell_type"] == "code"]
    executed = [c for c in code_cells if c.get("outputs")]
    assert len(executed) >= len(code_cells) - 1, (
        f"only {len(executed)} of {len(code_cells)} code cells carry output; "
        f"{path.name} was not shipped executed"
    )
    errors = [
        o for c in code_cells for o in c.get("outputs", [])
        if o.get("output_type") == "error"
    ]
    assert not errors, f"{path.name} contains {len(errors)} error output(s)"


def test_the_notebooks_match_their_builder():
    proc = _run("build_notebooks.py", "--check")
    assert proc.returncode == 0, (
        f"build_notebooks.py --check exited {proc.returncode}\n"
        f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
    )


@pytest.mark.parametrize("badge", ["colab.research.google.com"])
def test_no_badge_points_at_a_private_repository(badge):
    """A badge that cannot work is worse than no badge.

    This repository is private, so an Open-in-Colab badge would render as a 404
    for every reader while looking correct to anyone with access -- exactly the
    failure `lithium-optsc-energies-2024` recorded as "the Colab button could
    never have run". The badge goes in when the repository goes public, and this
    test is what stops it going in before.

    **Delete this test in the same commit that makes the repository public.**
    """
    for path in (ROOT / "README.md", *NOTEBOOKS):
        assert badge not in path.read_text(encoding="utf-8"), (
            f"{path.name} carries a Colab badge while the repository is private. "
            f"Either make the repository public or remove the badge."
        )
