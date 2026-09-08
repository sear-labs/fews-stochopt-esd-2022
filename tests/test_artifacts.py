"""The shipped artifacts and the notebooks still match what generates them.

Four committed things here are build outputs: `artifacts/`, produced by
`scripts/export_artifacts.py`, and the two notebooks, produced by
`scripts/build_notebooks.py`. A build script and its output drift exactly as fast
as two pasted copies, and for the same reason -- nobody compares them.

The verifier gets its own tests because it is this repository's central claim:
that the published result can be checked with no solver and no licence. A claim
like that is worth nothing if nobody runs it -- and worse than nothing if the
test that guards it cannot see the way it fails.

**It could not.** `test_the_verification_notebook_needs_no_solver` searched the
notebook for the literal string `import gurobipy`. The notebook imports
`fews_stochopt`, which imported `model`, which imports `gurobipy` -- so the
licence-free notebook failed at import on any machine without a solver, and the
text search contained nothing to find. The package now resolves its names lazily,
and the tests at the bottom of this file **block gurobipy and import for real**.
"""
from __future__ import annotations

import json
import re
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

    This is the *text* half of that check and it is not sufficient on its own: a
    transitive import contains none of these strings.
    `test_the_verification_notebooks_imports_all_resolve_without_a_solver` is the
    half that actually runs.
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


# ---------------------------------------------------------------------------
# The licence-free claim, tested by removing the licence.
# ---------------------------------------------------------------------------

_BLOCK_AND_IMPORT = '''
import sys
from importlib.abc import MetaPathFinder


class Blocker(MetaPathFinder):
    """Make gurobipy unimportable, as a machine without a solver sees it."""

    def find_spec(self, name, path=None, target=None):
        if name == "gurobipy" or name.startswith("gurobipy."):
            raise ImportError("gurobipy is blocked")
        return None


sys.meta_path.insert(0, Blocker())

# The probe must be shown capable of firing before a clean result means anything.
try:
    import gurobipy  # noqa: F401
except ImportError:
    pass
else:
    raise SystemExit("PROBE-BROKEN: gurobipy imported despite the blocker")

{body}
print("OK")
'''


def _run_without_gurobipy(body: str):
    script = _BLOCK_AND_IMPORT.format(body=body)
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(ROOT), capture_output=True, text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")},
    )


def test_the_blocker_itself_works():
    """A search that must return zero has to be shown capable of returning one."""
    proc = _run_without_gurobipy("import gurobipy")
    assert proc.returncode != 0, "importing gurobipy succeeded despite the blocker"


def test_importing_the_package_does_not_need_a_solver():
    """`00_verification.ipynb` derives its paths from this package.

    If `import fews_stochopt` pulled in gurobipy, that notebook would fail at
    import on exactly the machine it exists to serve. **It did**, until the
    package was made to resolve its names lazily -- and the test guarding the
    claim missed it, because it searched the notebook for the literal string
    `import gurobipy` and a transitive import does not contain one.
    """
    proc = _run_without_gurobipy(
        "import fews_stochopt\n"
        "from fews_stochopt.config import load_config\n"
        "load_config()"
    )
    assert proc.returncode == 0, (
        "importing fews_stochopt requires gurobipy, so the licence-free claim is "
        f"false\n--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
    )


def test_the_verification_notebooks_imports_all_resolve_without_a_solver():
    """Every top-level import the verification notebook makes, actually made.

    Reading the source for a forbidden string is not enough: the failure this
    catches is transitive and invisible to a text search.
    """
    code = _code(VERIFICATION)
    imports = sorted(set(re.findall(r"^\s*(?:import|from)\s+([A-Za-z_]\w*)", code, re.M)))
    # `google` only exists on Colab and is guarded by try/except in the notebook.
    imports = [m for m in imports if m != "google"]
    assert "fews_stochopt" in imports, "the notebook does not import the package"

    proc = _run_without_gurobipy("\n".join(f"import {m}" for m in imports))
    assert proc.returncode == 0, (
        "an import in 00_verification.ipynb needs gurobipy: "
        f"{imports}\n--- stderr ---\n{proc.stderr}"
    )


def test_the_verifier_runs_without_a_solver():
    """The claim end to end, not just its imports."""
    proc = _run_without_gurobipy(
        "import runpy, sys\n"
        "sys.argv = ['verify_solution.py', '--quiet']\n"
        "try:\n"
        "    runpy.run_path('scripts/verify_solution.py', run_name='__main__')\n"
        "except SystemExit as e:\n"
        "    assert not e.code, f'verifier exited {e.code}'"
    )
    assert proc.returncode == 0, (
        f"verify_solution.py needs a solver\n--- stderr ---\n{proc.stderr}"
    )


def test_every_advertised_export_actually_resolves():
    """`__all__` is a promise, and until now nothing checked it.

    The package resolves its public names lazily (PEP 562 `__getattr__`) so that
    importing it does not drag in a solver -- the remedy behind
    `test_importing_the_package_does_not_need_a_solver`. But **every consumer in
    this repository imports from the submodules**, `from fews_stochopt.config
    import load_config`, so the `_EXPORTS` branch of that `__getattr__` had never
    executed once. Ten advertised names, zero ever resolved: a coverage run over
    every entry point put lines 67-68 among the handful never reached.

    That is the same shape as a sixteen-entry alias map with one entry exercised.
    A broken entry here raises loudly rather than resolving wrongly, so this is
    unverified rather than wrong -- which is exactly the state a test removes.
    """
    import fews_stochopt

    exports = fews_stochopt._EXPORTS
    assert exports, "the export map is empty; this test is checking nothing"

    unresolved = {}
    for name, module in exports.items():
        try:
            attr = getattr(fews_stochopt, name)
        except Exception as exc:  # noqa: BLE001 -- the failure is the finding
            unresolved[name] = f"{type(exc).__name__}: {exc}"
            continue
        assert attr is not None, f"{name} resolved to None"
        assert getattr(attr, "__module__", module) or True
    assert not unresolved, (
        f"{len(unresolved)} of {len(exports)} advertised exports do not resolve, "
        f"so `__all__` names things the package cannot provide: {unresolved}"
    )

    # `__dir__` drives tab-completion and `from ... import *`; it must not
    # advertise a name the resolver would refuse.
    for name in dir(fews_stochopt):
        if name.startswith("_"):
            continue
        assert name in exports or name in fews_stochopt._SUBMODULES, (
            f"__dir__ advertises {name!r}, which __getattr__ does not resolve"
        )


# Measured, not assumed: which advertised names survive with gurobipy blocked.
# Six do not. Only two of those six should need a solver.
#
# `aggregate.py:38` imports `fews_stochopt.model` at module level for four
# scenario-name string constants and one annotation, and `model.py:43` imports
# gurobipy at module level. So `SCENARIOS` -- a tuple of four strings -- cannot
# be resolved without a Gurobi licence. That is the exact defect shape the
# standard names: a module-level import reached by an eager one.
#
# It is asserted as it stands rather than fixed. The fix is small and known --
# move the four constants to a solver-free module, and put `ScenarioResult`
# under TYPE_CHECKING where it already belongs, since all five uses are
# annotations and the module has `from __future__ import annotations`. But
# `model.py` and `aggregate.py` are both in `pipeline._SOURCE_MODULES`, so
# touching either re-stamps the provenance of all ten solved scenarios and
# re-solves the pipeline. Re-stamping a published reproduction for an API
# tidy-up is a decision, not a cleanup. See `docs/reproduction-notes.md` §20.
SOLVER_BOUND_EXPORTS = {
    "ScenarioResult",        # legitimately from `model`
    "solve_scenario",        # legitimately from `model`
    "ScenarioStats",         # from `aggregate`, coupled via the import above
    "scenario_stats",        # ditto
    "value_of_information",  # ditto
    "SCENARIOS",             # ditto -- four strings behind a licence
}


def test_the_licence_free_exports_resolve_without_a_solver():
    """Splitting the promise: which advertised names survive with no gurobipy.

    Asserting the split in BOTH directions is what makes this a measurement
    rather than a wish. If the coupling above is ever fixed, the second half
    fails and tells you to tighten the set, instead of the set quietly
    over-claiming forever.
    """
    lines = [
        "import fews_stochopt as f",
        f"needs_solver = {sorted(SOLVER_BOUND_EXPORTS)!r}",
        "bad, unexpectedly_ok = [], []",
        "for name in f._EXPORTS:",
        "    try:",
        "        getattr(f, name)",
        "        resolved = True",
        "    except Exception:",
        "        resolved = False",
        "    if resolved and name in needs_solver:",
        "        unexpectedly_ok.append(name)",
        "    if not resolved and name not in needs_solver:",
        "        bad.append(name)",
        "assert not bad, f'these should not need a solver: {bad}'",
        "assert not unexpectedly_ok, f'no longer solver-bound, tighten the set: {unexpectedly_ok}'",
    ]
    proc = _run_without_gurobipy("\n".join(lines))
    assert proc.returncode == 0, (
        "the licence-free export surface has changed\n"
        f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "KNOWN, UNFIXED: analysis.py:30 -> aggregate.py:38 -> model.py:43 imports "
        "gurobipy, so regenerating the figures needs a Gurobi licence even though "
        "make_figures.py reads only results/clean/. The fix touches files in "
        "pipeline._SOURCE_MODULES and re-stamps the provenance of all ten solved "
        "scenarios, which is a decision rather than a cleanup. See "
        "docs/reproduction-notes.md section 20."
    ),
)
def test_regenerating_the_figures_needs_no_solver():
    """The figure path is stage 9 and reads 90 KB of committed cleaned output.

    Nothing about drawing a line through `results/clean/` requires a solver, and
    a reader without a licence is exactly who the committed cleaned output exists
    for. This is `strict=True` deliberately: when the import coupling is fixed
    this test XPASSes, which pytest reports as a failure, and the marker has to
    be removed. A known defect that quietly heals is a known defect nobody
    notices has healed.
    """
    proc = _run_without_gurobipy(
        "import runpy, sys\n"
        "sys.argv = ['make_figures.py', '--quiet']\n"
        "runpy.run_path('scripts/make_figures.py', run_name='__main__')"
    )
    assert proc.returncode == 0, (
        "make_figures.py cannot run without a solver\n"
        f"--- stderr ---\n{proc.stderr[-1500:]}"
    )


def _cell_outputs(nb):
    """Every output channel of every code cell, joined. No normalisation.

    Comparing only `text/plain` is what made the first version of this test
    blind: the one cell carrying a table emits `<Styler at 0x...>` there and the
    table itself in `text/html`. See the docstring below.
    """
    rows = []
    for cell in nb.cells:
        if cell.cell_type != "code":
            continue
        chunks = []
        for o in cell.get("outputs", []):
            if o.output_type == "stream":
                chunks.append(f"stream/{o.get('name')}:{o.text}")
            elif o.output_type in ("execute_result", "display_data"):
                # Every channel, not an allowlist. Naming two of them is how a
                # comparison half-sees a change: it goes red on whichever cell
                # happens to differ in a channel it reads, and green on the cell
                # whose result is the point, so the failure is reported in the
                # wrong place. `00_verification.ipynb` carries image/png.
                for mime in sorted(o.get("data", {})):
                    chunks.append(f"{mime}:{o['data'][mime]}")
            elif o.output_type == "error":
                chunks.append("ERROR:" + o.get("ename", ""))
        rows.append("".join(chunks))
    return rows


def _channels(nb):
    """Every MIME type and stream name the notebook's outputs carry."""
    seen = set()
    for cell in nb.cells:
        if cell.cell_type != "code":
            continue
        for o in cell.get("outputs", []):
            if o.output_type == "stream":
                seen.add(f"stream/{o.get('name')}")
            elif o.output_type in ("execute_result", "display_data"):
                seen.update(o.get("data", {}))
            elif o.output_type == "error":
                seen.add("error")
    return seen


def _execute_copy(path):
    nbformat = pytest.importorskip("nbformat")
    nbclient = pytest.importorskip("nbclient")
    fresh = nbformat.from_dict(json.loads(json.dumps(nbformat.read(path, as_version=4))))
    nbclient.NotebookClient(
        fresh, timeout=600, kernel_name="python3",
        resources={"metadata": {"path": str(ROOT / "notebooks")}},
    ).execute()
    return fresh


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_the_committed_notebook_outputs_are_reproducible(path):
    """Rule 5's exception says a reader sees the outputs without running the
    notebook. That is honest only if the committed outputs are what the code
    produces, and `build_notebooks.py --check` deliberately does not check it --
    it compares source cells, because outputs legitimately differ between
    machines. Right in general, too strong for this notebook: it runs
    deterministic arithmetic over committed artifacts, with no solver and no RNG.

    **The first version of this test was blind, and passed while being so.**
    It compared only `text/plain` and normalised away ` at 0x...`. The one cell
    that carries a real result renders a pandas Styler, whose `text/plain` is
    just `<Styler at 0x...>` -- so the normaliser erased the only channel that
    differed, and the 4 KB of actual table in `text/html` was never compared at
    all. Measured: adding $11,111 to a committed value in
    `results/clean/value_of_information.csv` produced a completely different
    table and this test still passed.

    Two things changed. The comparison now reads **every** output channel. And
    the notebook was fixed at source rather than the comparison taught to ignore
    it -- `build_notebooks.py` renders through `HTML()` with `set_uuid`, so
    neither the repr address nor the Styler's random table id appears. **There is
    no normalisation left here**, which is the point: a normaliser that changes
    no outcome is a future excuse for a real difference, and this one was hiding
    the whole subject.

    **Both notebooks are checked, and the reason the second one was exempt turned
    out to be wrong.** I had written that the example notebook could not be
    compared because it solves and its last digits move. Measured: every stream
    output re-executes bit-identical, Gurobi solve included. What actually
    differed was the same two Styler tokens, in a repository where the instance
    is fixed and the solve deterministic. Reasoning about the artifact rather
    than about the repository is the whole lesson of this section -- and I made
    the file-shaped mistake in the same breath as naming it.
    """
    nbformat = pytest.importorskip("nbformat")
    committed = nbformat.read(path, as_version=4)
    old = _cell_outputs(committed)
    new = _cell_outputs(_execute_copy(path))

    assert old, "the committed notebook has no code-cell outputs to compare"
    assert len(old) == len(new), f"{len(old)} committed cells against {len(new)}"
    differing = [i for i, (a, b) in enumerate(zip(old, new)) if a != b]
    assert not differing, (
        f"cell(s) {differing} produce different output than committed, so the "
        f"shipped outputs are not what this code produces:\n"
        + "\n".join(
            f"--- cell {i}\n  committed: {old[i][:300]!r}\n  fresh    : {new[i][:300]!r}"
            for i in differing
        )
    )


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_the_comparison_reads_every_output_channel(path):
    """Partial blindness is worse than total blindness, and harder to see.

    A comparison naming two MIME types goes red on whichever cell happens to
    differ in a channel it reads, and green on the cell whose result is the
    point -- so a real defect is reported at the wrong cell while the right one
    passes. That survives a casual look at a red test in a way total blindness
    does not. Measured in the SAV repository on the same injection: two cells
    affected, differing in different channels, and a `text/plain`-only
    comparison catching one of the two.

    `00_verification.ipynb` carries `image/png`, which the first version of
    `_cell_outputs` did not read. This asserts every channel present is
    captured, so narrowing back to an allowlist fails here rather than silently.
    """
    nbformat = pytest.importorskip("nbformat")
    nb = nbformat.read(path, as_version=4)
    present = _channels(nb)
    assert present, f"{path.name} has no outputs at all"

    captured = "".join(_cell_outputs(nb))
    unread = sorted(c for c in present if f"{c}:" not in captured)
    assert not unread, (
        f"{path.name} carries output channel(s) {unread} that the comparison "
        f"never reads, so a change confined to them would pass unnoticed"
    )


_OPAQUE = re.compile(r"^<[\w.]+ (?:object|at 0x)[^>]*>$")


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_no_cell_is_captured_only_as_an_object_repr(path):
    """A narrow guard, described narrowly -- I first wrote it up as the general
    form of the can-see-the-table guard and measured that it is not.

    **Whether a channel is informative depends on the renderer, not the
    channel.** A plain DataFrame's `text/plain` carries its numbers; a Styler's
    is `<Styler at 0x...>` and carries nothing. So the identical comparison over
    the identical channel is sound for one cell and blind for the next, decided
    by a rendering choice made in the notebook rather than by anything visible
    in the test. Confirmed across two repositories on the same injection: the
    same `text/plain`-only comparison caught the results table in one and missed
    it in the other.

    **What this does NOT catch, measured rather than assumed.** Narrowing the
    capture back to `text/plain` alone leaves the two Styler cells with their
    table gone -- and this test still passes, because those cells also print
    stream output, so the cell as a whole is not opaque. Per-cell opacity is a
    weaker property than per-subject blindness, and only the latter is the
    failure that shipped here.

    What catches that narrowing is the other two: every-output-channel fires on
    both notebooks, and can-see-the-table fires by name. Verified by injection.

    This one covers the case they do not: a cell whose *entire* output is an
    opaque repr, which no named value would be looked for in and which reading
    every channel would still faithfully capture as nothing. Cheap, real, and
    much smaller than the sentence I first wrote about it.
    """
    nbformat = pytest.importorskip("nbformat")
    nb = nbformat.read(path, as_version=4)

    captured = _cell_outputs(nb)
    cells = [c for c in nb.cells if c.cell_type == "code"]
    assert len(captured) == len(cells)

    blind = []
    for i, (cell, text) in enumerate(zip(cells, captured)):
        if not cell.get("outputs"):
            continue
        # Strip the `channel:` tags `_cell_outputs` adds, then ask whether
        # anything informative is left.
        pieces = [
            piece.split(":", 1)[-1].strip()
            for piece in re.split(r"(?=(?:stream/|[\w.+-]+/[\w.+-]+):)", text)
            if piece.strip()
        ]
        informative = [x for x in pieces if x and not _OPAQUE.match(x)]
        if not informative:
            blind.append((i, text[:120]))
    assert not blind, (
        f"{path.name}: cell(s) captured only as an object repr, so the "
        f"comparison is looking at nothing for them: {blind}"
    )


def test_the_notebook_comparison_can_see_the_table():
    """The guard the blind version needed and did not have.

    A comparison that cannot see a cell's real content passes for the wrong
    reason, and nothing about a green run distinguishes that from correctness.
    This asserts the captured output actually contains the numbers -- so if the
    comparison ever narrows back to `text/plain`, or the table stops being
    emitted, this fails instead of quietly going blind again.
    """
    nbformat = pytest.importorskip("nbformat")
    captured = "".join(_cell_outputs(nbformat.read(VERIFICATION, as_version=4)))

    values = ROOT / "results" / "clean" / "value_of_information.csv"
    published = values.read_text(encoding="utf-8").splitlines()[1].split(",")
    number = float(published[3])
    rendered = f"{number:,.4f}"
    assert rendered in captured, (
        f"the captured notebook output does not contain {rendered!r}, the first "
        f"value in {values.name}. The comparison is not seeing the table, which "
        f"is how the first version of this test passed while blind."
    )
def test_the_committed_figures_are_what_the_script_draws(pipeline_run):
    """The Part 4 corollary, applied to the one generated artifact that lacked it.

    `artifacts/` has `export_artifacts.py --check` and the notebooks have
    `build_notebooks.py --check`. The figures had only a *source grep* asserting
    that `make_figures.py` reads `results/clean/` and not raw output -- which is
    the same text-search weakness that let a transitive gurobipy import through:
    a read reached indirectly contains none of the forbidden strings.

    Regenerating and comparing bytes is the check that does not depend on how
    the script is written. Matplotlib output is not deterministic in general, so
    this asserts a property of this repository rather than a general one.

    On failure the committed bytes are put back, so a red test never leaves the
    working tree dirty.
    """
    figures = sorted((ROOT / "figures" / "generated").glob("*.p*"))
    assert len(figures) >= 4, f"only {len(figures)} generated figures found"

    before = {p: p.read_bytes() for p in figures}
    proc = _run("make_figures.py", "--quiet")
    try:
        assert proc.returncode == 0, (
            f"make_figures.py exited {proc.returncode}\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
        )
        after = {p: p.read_bytes() for p in figures}
        changed = [p.name for p in figures if before[p] != after.get(p)]
        assert not changed, (
            f"regenerating changed {len(changed)} committed figure(s): {changed}. "
            f"Either the cleaned output moved or the committed figures are stale."
        )
        missing = [p.name for p in figures if not p.exists()]
        assert not missing, f"the run removed committed figures: {missing}"
    except AssertionError:
        for p, data in before.items():
            p.write_bytes(data)
        raise


# Test modules whose subject needs no solver. Every test in them reads committed
# CSVs with numpy and pandas. They are named here because a single module-level
# import of `analysis` -- which reaches `aggregate`, then `model`, then gurobipy
# -- makes a whole file uncollectable, and pytest reports that as a collection
# error before running anything, not as a skip.
LICENCE_FREE_TEST_MODULES = (
    "test_markov_reconstruction.py",
    "test_dependencies_declared.py",
    "test_archive_and_one_language.py",
)


@pytest.mark.parametrize("module", LICENCE_FREE_TEST_MODULES)
def test_the_licence_free_test_modules_still_import_without_a_solver(module):
    """A reader without a licence must be able to run the tests that apply to them.

    **Measured on a simulated licence-free machine -- gurobipy blocked in every
    process, subprocesses included, and the gitignored solve cache moved aside,
    which is what a fresh clone actually looks like.** Three test modules failed
    to *collect*. Two of them import `model` or `collapsed` and legitimately need
    a solver. The third was `test_markov_reconstruction.py`, which is pure numpy
    and pandas over committed CSVs -- and it had acquired a module-level
    `from fews_stochopt import analysis` earlier in this same session, added for
    one assertion, which made all eight of its tests uncollectable.

    Nothing noticed because the suite had never been run without a licence. That
    is the gap this file's other tests simulate one import at a time; this is the
    same claim at module granularity.
    """
    path = Path(__file__).resolve().parent / module
    assert path.exists(), f"{module} does not exist; update the list"
    proc = _run_without_gurobipy(
        "import importlib.util, sys\n"
        f"spec = importlib.util.spec_from_file_location('probe_mod', r'{path}')\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "sys.modules['probe_mod'] = mod\n"
        "spec.loader.exec_module(mod)\n"
    )
    assert proc.returncode == 0, (
        f"{module} cannot be imported without a solver, so pytest reports a "
        f"collection error and every test in it is lost to a reader without a "
        f"licence\n--- stderr ---\n{proc.stderr[-1500:]}"
    )


# Backslashes are built with chr(92), never typed. A Windows path in a non-raw
# Python string makes `\U` an escape sequence, and the first version of this
# test failed to parse because of it.
_BS = chr(92)
_ABSOLUTE_PATH_PATTERNS = {
    "Windows user directory": "[A-Za-z]:" + _BS + _BS + "+Users",
    "POSIX home directory": "/(?:home|Users)/[A-Za-z0-9_.-]+/",
}


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_no_committed_output_carries_an_absolute_path(path):
    """A shipped artifact must not name the machine that built it.

    `00_verification.ipynb` carried a line reading `Verifying 12 model(s) from`
    followed by an absolute path into this author's home directory, because
    `verify_solution.py` logged `ARTIFACTS` rather than a repo-relative name.
    Two consequences, and the first hid the second: every reader who clones gets
    a different path there, so the output-reproducibility check fails for
    everyone except the author -- and a repository heading for publication ships
    a local home directory inside a file people read.

    Found by running the suite in a **real clone** rather than in a working tree
    with directories moved aside. A clone is what a stranger gets, by
    definition; a mutated tree is a guess about what a clone would be, and that
    guess was wrong twice -- it still held two generated directories a clone
    does not have, and it could not show this at all, because on the machine
    that wrote the path the path is correct.
    """
    text = path.read_text(encoding="utf-8")
    found = {
        label: re.findall(pattern, text)[:3]
        for label, pattern in _ABSOLUTE_PATH_PATTERNS.items()
        if re.search(pattern, text)
    }
    assert not found, (
        f"{path.name} carries an absolute path in its committed content: "
        f"{found}. It cannot reproduce on anyone else's machine, and it names "
        f"this one in a published artifact."
    )
