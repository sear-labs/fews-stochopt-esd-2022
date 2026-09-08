"""Build the two notebooks, then execute them.

    python scripts/build_notebooks.py            # build and execute both
    python scripts/build_notebooks.py --check    # rebuild and compare sources

Archetype P asks for two notebooks with **deliberately different claims**, and
keeping them apart is the point:

    00_verification.ipynb   needs NOTHING but numpy   the published result is correct
    01_example.ipynb        needs a free solver       the implementation runs and behaves

Merging them would let the stronger claim borrow the weaker one's dependencies. A
reader who only wants to check the paper should never be asked to install a
solver, and the file they open should not contain one.

The notebooks are build outputs, not hand-edited files: the standard's Part 4
corollary says a generated artifact needs something checking that regenerating
reproduces it. `--check` compares the *source* cells, not the outputs, which
legitimately differ between machines.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import nbformat  # noqa: E402
from nbclient import NotebookClient  # noqa: E402

from fews_stochopt.config import repo_root  # noqa: E402

ROOT = repo_root()
NOTEBOOKS = ROOT / "notebooks"
VERIFICATION = NOTEBOOKS / "00_verification.ipynb"
EXAMPLE = NOTEBOOKS / "01_example.ipynb"

MD = nbformat.v4.new_markdown_cell
CODE = nbformat.v4.new_code_cell

INSTALL_MD = """## 1. Install

On Colab, **clone the repository and install from that checkout.**
`pip install git+https://...` is not enough and fails in a way that looks like a
bug in the model: it installs the package but not `data/`, because the
precipitation inputs live in `data/raw/` and are not part of the wheel. The
installed `config.py` then derives the repository root relative to site-packages,
and the first cell that loads data dies with a `FileNotFoundError` naming a
directory that has nothing to do with the problem."""

INSTALL_CODE = '''import subprocess
import sys

try:
    import google.colab  # noqa: F401
    IN_COLAB = True
except ImportError:
    IN_COLAB = False

if IN_COLAB:
    REPO = "https://github.com/sear-labs/fews-stochopt-esd-2022.git"
    subprocess.run(["git", "clone", "--depth", "1", REPO], check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-e",
                    "fews-stochopt-esd-2022"], check=True)
    print("cloned and installed from the checkout")
else:
    print("running from a local checkout; `pip install -e .` once if you have not")

import fews_stochopt

print("fews_stochopt", fews_stochopt.__version__)'''

ROOT_CODE = '''import pathlib

import fews_stochopt

# Derived from the INSTALLED package, never from the working directory. A
# relative "../scripts/..." breaks the moment the notebook runs from anywhere but
# its own folder, which is exactly what happens on Colab after the clone.
ROOT = pathlib.Path(fews_stochopt.__file__).resolve().parents[2]


def run_script(name, *args):
    """Run a repository script and show BOTH streams and the return code.

    Printing only stdout is how a failing script comes to look like one that did
    nothing.
    """
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / name), *args],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.stderr:
        print("--- stderr ---")
        print(proc.stderr.rstrip())
    if proc.returncode != 0:
        raise RuntimeError(f"{name} exited {proc.returncode}")
    return proc'''


def verification_cells():
    """Claims the published result is correct. Needs nothing but numpy."""
    yield MD("""# Is the published result correct? --- FEWS farm model

Jones (2022), *Environment Systems and Decisions*,
[10.1007/s10669-021-09838-8](https://doi.org/10.1007/s10669-021-09838-8).

**This notebook needs no solver and no licence.** It is this repository's central
claim, and it is deliberately kept apart from the notebook that demonstrates the
code: merging them would make checking the paper depend on being able to run it.

Re-solving and checking are different verbs, and checking is the stronger one.
Re-solving needs Gurobi, a licence, and the same version and hardware to land in
the same place. Checking needs arithmetic, and it reproduces bit for bit forever.

`01_example.ipynb` is the other one: it runs the model.""")

    yield MD(INSTALL_MD)
    yield CODE(INSTALL_CODE)

    yield MD("""## 2. Check twelve frozen models against their solutions

`artifacts/` ships each collapsed instance and its solution. For every one,
`scripts/verify_solution.py` confirms that the point satisfies every constraint
and bound, that recomputing the objective from the variable values gives the
number this repository reports, and how far an independent search can improve on
it.

It imports neither `gurobipy` nor `fews_stochopt`: it writes the model out again
from the shipped instance files, because a check written from the same source as
the thing it checks is not a check.""")
    yield CODE(ROOT_CODE + '\n\n\nrun_script("verify_solution.py")')

    yield MD("""The last figure on each line is small and **positive by design**.
Gurobi returns points a little *outside* the feasible region while reporting
`OPTIMAL`, so every shipped solution is clipped back inside before it is stored.
The reported values are therefore valid lower bounds, and the true optimum sits
just above them.""")

    yield MD("""## 3. The reproduced table against the paper

`results/clean/value_of_information.csv` is committed, so this needs no run.""")
    yield CODE('''import pandas as pd

values = pd.read_csv(ROOT / "results" / "clean" / "value_of_information.csv")
short = {"Value_of_Known_Weather": "EVKW", "Value_of_Known_Climate": "EVKC",
         "Value_of_Perfect_Information": "EVPI",
         "Value_of_Stochastic_Solution": "VSS"}
table = values.assign(quantity=values["variable"].map(short))[
    ["label", "quantity", "published", "value", "difference"]]
display(table.style.format({"published": "{:,.4f}", "value": "{:,.4f}",
                            "difference": "{:+.4f}"}))

worst = table["difference"].abs().max()
print(f"largest difference: ${worst:,.4f}")
print("The Dry Most Likely VSS is the known one: its first stage solves a")
print("problem whose objective is flat. See docs/reproduction-notes.md, section 3.")''')

    yield MD("""## 4. What the figures show

Regenerated by `scripts/make_figures.py` from cleaned output, never from the raw
solver dump. Each carries a text alternative in `figures/generated/README.md`.""")
    yield CODE('''from IPython.display import Image, display as show

for name in ("value_of_information.png", "profit_against_rainfall.png"):
    print(name)
    show(Image(filename=str(ROOT / "figures" / "generated" / name)))''')


def example_cells():
    """Claims the implementation runs and behaves. Needs a free solver."""
    yield MD("""# Running the model --- FEWS farm model

Jones (2022), *Environment Systems and Decisions*,
[10.1007/s10669-021-09838-8](https://doi.org/10.1007/s10669-021-09838-8).

**This notebook runs the model.** It needs `gurobipy`, and should need no licence
file: the models it solves are 37 variables against a documented 2,000-variable
cap on the licence bundled with `pip install gurobipy`. That cap is reported
rather than measured here, so treat it as an inference until this has been run
somewhere without a licence.

**It is not the reproduction claim.** `00_verification.ipynb` makes that one and
needs nothing but numpy. This one shows that the code runs and behaves.

**Nothing here is a reduced instance.** The collapsed model solves the *whole*
problem: given the capacities nothing couples one run-year to another, and
precipitation takes five values, so 704,002 variables become 37 carrying integer
weights. Same mathematics --- `tests/test_collapsed_agrees.py` asserts the two
agree. So there is no reduction to stamp onto a figure, and a warning here would
be a false one.

**This notebook is thin.** It imports the package and calls it; the model lives
in `src/fews_stochopt/`.""")

    yield MD(INSTALL_MD)
    yield CODE(INSTALL_CODE)

    yield MD("""## 2. How big is the model, really""")
    yield CODE(ROOT_CODE + '''


import gurobipy as gp

from fews_stochopt import collapsed, load_config
from fews_stochopt.model import EXPECTED_VALUE, KNOWN_CLIMATE, STOCHASTIC

cfg = load_config()
env = gp.Env(params={"OutputFlag": 0})
weights, n_runs = collapsed.rain_weights(cfg, "EP")
probe = collapsed.build(cfg, weights, n_runs, env)
print(f"collapsed model: {probe.NumVars} variables, {probe.NumConstrs} linear "
      f"and {probe.NumQConstrs} quadratic constraints")
inside = "well inside" if probe.NumVars <= 2000 else "OVER"
print(f"documented cap on the bundled licence: 2,000 variables -> {inside} "
      f"({probe.NumVars} declared; not verified under that licence here)")
del probe, env''')

    yield MD("""## 3. Solve it, and compare against the full pipeline

Three of the four scenarios collapse and solve in milliseconds. **Perfect
Information does not collapse** --- every run picks its own capacities, so the
runs share nothing to aggregate over. It is 4,000 separate solves of 178
variables, about two minutes, and it is skipped here.""")
    yield CODE('''import pandas as pd

QUICK = True   # skip the 4,000-solve Perfect Information scenario

rows = []
for site in cfg.sites:
    for scenario in (STOCHASTIC, KNOWN_CLIMATE, EXPECTED_VALUE):
        result = collapsed.solve(cfg, site, scenario)
        rows.append({"site": site, "label": cfg.site(site).label,
                     "scenario": scenario, "mean_profit": result["objective"],
                     "alt_water_cap_cm": result["alt_water_cap"],
                     "alt_elc_cap_kW": result["alt_elc_cap"]})
solved = pd.DataFrame(rows)

stats = pd.read_csv(ROOT / "results" / "clean" / "scenario_stats.csv")
full = stats[stats["variable"] == "profit_mean"].set_index(["label", "scenario"])["value"]
solved["full_pipeline"] = [full[(r.label, r.scenario)] for r in solved.itertuples()]
solved["difference"] = solved["mean_profit"] - solved["full_pipeline"]

display(solved[["label", "scenario", "full_pipeline", "mean_profit", "difference"]]
        .style.format({"full_pipeline": "{:,.4f}", "mean_profit": "{:,.4f}",
                       "difference": "{:+.4f}"}))

if QUICK:
    print("QUICK = True: Perfect Information was not solved here.")''')

    yield MD("""## 4. Change something, and see what it does

This is what an example notebook is for. The capacity cost is a knob; halving it
should buy more alternative water.""")
    yield CODE('''import copy

base = collapsed.solve(cfg, "DML", STOCHASTIC)

cheaper = copy.deepcopy(cfg)
cheaper.cost_alt_water = cfg.cost_alt_water / 2
changed = collapsed.solve(cheaper, "DML", STOCHASTIC)

header = f"{'':22}{'water cap (cm)':>16}{'elc cap (kW)':>15}{'mean profit':>16}"
print(header)
print(f"{'as published':22}{base['alt_water_cap']:>16.4f}"
      f"{base['alt_elc_cap']:>15.4f}{base['objective']:>16,.2f}")
print(f"{'half the water cost':22}{changed['alt_water_cap']:>16.4f}"
      f"{changed['alt_elc_cap']:>15.4f}{changed['objective']:>16,.2f}")

assert changed["alt_water_cap"] > base["alt_water_cap"], (
    "halving the cost of alternative water should buy more of it")
print("More alternative water, as it should be.")''')

    yield MD("""## 5. The full 704,002-variable formulation --- needs a real licence

`scripts/run_all.py` solves the model as the published run wrote it, reproduces
both of the paper's tables, and takes about eight minutes.

On Colab a node-locked licence cannot work --- the virtual machine differs every
session --- so use WLS credentials held as Colab secrets, never as literals: a
key committed to a repository is exposed the moment the repository is shared, and
deleting it later does not remove it from the history.

```python
import os
from google.colab import userdata          # SecretNotFoundError is EXPECTED
for k in ("WLSACCESSID", "WLSSECRET", "LICENSEID"):
    os.environ["GRB_" + k] = userdata.get("GRB_" + k)
```

`tests/test_collapsed_agrees.py` ties the two together: it solves the collapsed
model and the full one and asserts they agree, so the fast path above is not a
different model with a convenient answer.""")


NOTEBOOKS_TO_BUILD = {
    VERIFICATION: verification_cells,
    EXAMPLE: example_cells,
}


def build(cells_fn) -> nbformat.NotebookNode:
    nb = nbformat.v4.new_notebook(cells=list(cells_fn()))
    nb.metadata.update({
        "kernelspec": {"display_name": "Python 3", "language": "python",
                       "name": "python3"},
        "language_info": {
            "name": "python",
            "version": f"{sys.version_info.major}.{sys.version_info.minor}",
        },
    })
    return nb


def sources(nb) -> list[str]:
    return [c.source for c in nb.cells]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--check", action="store_true")
    args = p.parse_args(argv)

    if args.check:
        stale = []
        for target, cells_fn in NOTEBOOKS_TO_BUILD.items():
            if not target.exists():
                stale.append(f"{target.name} missing")
                continue
            if sources(nbformat.read(target, as_version=4)) != sources(build(cells_fn)):
                stale.append(f"{target.name} differs from its builder")
        if stale:
            print("notebooks are stale: " + "; ".join(stale), file=sys.stderr)
            return 1
        print(f"notebooks match their builder: {len(NOTEBOOKS_TO_BUILD)}")
        return 0

    NOTEBOOKS.mkdir(parents=True, exist_ok=True)
    failed = 0
    for target, cells_fn in NOTEBOOKS_TO_BUILD.items():
        nb = build(cells_fn)
        # Ship them executed. A reader without a licence should still see every
        # number the prose refers to.
        client = NotebookClient(
            nb, timeout=1800, kernel_name="python3",
            resources={"metadata": {"path": str(NOTEBOOKS)}},
        )
        client.execute()
        nbformat.write(nb, target)
        errors = [
            o for c in nb.cells for o in c.get("outputs", [])
            if o.get("output_type") == "error"
        ]
        failed += len(errors)
        print(f"wrote {target.relative_to(ROOT)} - {len(nb.cells)} cells, "
              f"{len(errors)} error(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
