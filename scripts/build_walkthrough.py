"""Build `notebooks/00_walkthrough.ipynb`, then execute it.

The notebook is a build output, not a hand-edited file: the standard's Part 4
corollary says a generated artifact needs something checking that regenerating
reproduces it, and the only way to keep a notebook honest about a package that
keeps changing is to generate it from the package's own vocabulary and run it.

    python scripts/build_walkthrough.py            # build and execute
    python scripts/build_walkthrough.py --check    # rebuild and compare sources

`--check` compares the *source* cells, not the outputs: outputs legitimately
differ between machines (timings, licence banners), and comparing them would make
the check fail for reasons that are not drift.
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
TARGET = ROOT / "notebooks" / "00_walkthrough.ipynb"

MD = nbformat.v4.new_markdown_cell
CODE = nbformat.v4.new_code_cell


def cells():
    yield MD("""# FEWS farm model — Jones (2022), *Environment Systems and Decisions*

The stochastic programming model behind
[10.1007/s10669-021-09838-8](https://doi.org/10.1007/s10669-021-09838-8):
a farm choosing alternative water and electricity capacity under uncertain
precipitation, over 25 years and 4,000 Monte Carlo weather draws.

**This notebook is thin on purpose.** It imports the package and calls it; it
holds no model logic of its own. The model lives in `src/fews_stochopt/`, and
duplicating it here would create a second copy with nothing comparing the two —
which is the failure the repository's own tests exist to prevent.

## What runs without a licence

**Section 2 needs no solver at all.** The repository ships the frozen model
instances and their solutions, and verifying them is arithmetic. That is this
repository's central claim and it is the part that runs everywhere.

**Sections 3 and 4 need `gurobipy`, and should need no licence file.** The models
solved there are 37 variables against a documented 2,000-variable cap on the
licence bundled with `pip install gurobipy`. That cap is reported rather than
measured here — this machine holds a full academic licence — so treat it as an
inference until this notebook has been run somewhere without one. Only the full
704,002-variable formulation in section 5 needs a real licence, and section 5 is
optional.""")

    yield MD("""## 1. Install

On Colab, **clone the repository and install from that checkout.**
`pip install git+https://…` is not enough and fails in a way that looks like a
bug in the model: it installs the package but not `data/`, because the
precipitation inputs live at the repository root and are not part of the wheel.
The installed `config.py` then derives the repository root relative to
site-packages and the first cell that loads data dies with a `FileNotFoundError`
naming a directory that has nothing to do with the problem.""")

    yield CODE('''import subprocess
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

print("fews_stochopt", fews_stochopt.__version__)''')

    yield MD("""## 2. Verify the published result — no solver, no licence

Re-solving and checking are different verbs, and checking is the stronger one.

Given a model and a claimed solution, feasibility and the objective can be
confirmed by arithmetic. That verification needs no licence, does not depend on
hardware or solver version, and reproduces bit for bit forever — none of which is
true of re-solving.

`scripts/verify_solution.py` reads the twelve frozen instances in `artifacts/`
and checks each one. It imports nothing from this package: it writes the model
out again from the shipped instance files, because a check written from the same
source as the thing it checks is not a check.""")

    yield CODE('''import pathlib

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
        print("--- stderr ---", proc.stderr.rstrip(), sep="\\n")
    if proc.returncode != 0:
        raise RuntimeError(f"{name} exited {proc.returncode}")
    return proc


run_script("verify_solution.py")''')

    yield MD("""That is the paper's result checked, end to end, with numpy.

Each line reports three things: that the point satisfies every constraint and
bound, that recomputing the objective from the variable values gives the number
the repository reports, and how far an independent search can improve on it.

The last figure is small and **positive by design**. Gurobi returns points a
little *outside* the feasible region while reporting `OPTIMAL`, so every shipped
solution is clipped back inside before it is stored. The reported values are
therefore valid lower bounds, and the true optimum sits just above them.""")

    yield MD("""## 3. What was actually solved

The instances are small enough to read. Each is one weighted block per distinct
precipitation value — the model collapses to that because, given the capacities,
nothing couples one run-year to another and precipitation takes only five values.

That is why 704,002 variables become 37, and why this notebook needs no licence.""")

    yield CODE('''import json

import pandas as pd

instance = json.loads((ROOT / "artifacts" / "EP_stochastic.json").read_text())

blocks = pd.DataFrame(instance["blocks"])
blocks["share_of_run_years"] = blocks["run_years"] / blocks["run_years"].sum()
print(f"Equally Probable, Stochastic scenario — {instance['n_runs']:,} runs "
      f"x {instance['years']} years")
display(blocks)

print("\\ncoefficients:")
for k, v in sorted(instance["coefficients"].items()):
    print(f"  {k:32} {v:>16,.6f}")''')

    yield MD("""## 4. Re-solve the model

Three of the four scenarios collapse and solve in milliseconds. The cell prints
the model size first, because that is the number that decides whether a reader
without a licence can run this at all.

**Perfect Information does not collapse** — every run chooses its own capacities,
so the runs share nothing to aggregate over. It is 4,000 separate solves of 178
variables each, about two minutes, and it is skipped by default. Set
`QUICK = False` to run it.""")

    yield CODE('''import gurobipy as gp

from fews_stochopt import collapsed, load_config
from fews_stochopt.model import EXPECTED_VALUE, KNOWN_CLIMATE, STOCHASTIC

cfg = load_config()

env = gp.Env(params={"OutputFlag": 0})
weights, n_runs = collapsed.rain_weights(cfg, "EP")
probe = collapsed.build(cfg, weights, n_runs, env)
print(f"collapsed model: {probe.NumVars} variables, {probe.NumConstrs} linear "
      f"and {probe.NumQConstrs} quadratic constraints")
# The documented cap on the licence bundled with `pip install gurobipy` is 2,000
# variables. That is a REPORTED cap, not one measured here: this machine holds a
# full academic licence, and forcing the fallback makes Gurobi error rather than
# degrade. Counting variables is also the weaker probe -- the limit is enforced
# when you optimize, so a model that declares small can still be refused. Treat
# the line below as an inference, and the real test as running this notebook on
# Colab, where no licence file exists.
print(f"documented cap on the bundled licence: 2,000 variables -> "
      f"{'well inside' if probe.NumVars <= 2000 else 'OVER'} "
      f"({probe.NumVars} declared; not verified under that licence here)")
del probe, env''')

    yield CODE('''QUICK = True   # skip the 4,000-solve Perfect Information scenario

rows = []
for site in cfg.sites:
    for scenario in (STOCHASTIC, KNOWN_CLIMATE, EXPECTED_VALUE):
        result = collapsed.solve(cfg, site, scenario)
        rows.append({"site": site, "label": cfg.site(site).label,
                     "scenario": scenario, "mean_profit": result["objective"],
                     "alt_water_cap_cm": result["alt_water_cap"],
                     "alt_elc_cap_kW": result["alt_elc_cap"]})

solved = pd.DataFrame(rows)
display(solved.style.format({"mean_profit": "{:,.4f}",
                             "alt_water_cap_cm": "{:.6f}",
                             "alt_elc_cap_kW": "{:.4f}"}))

if QUICK:
    print("\\nQUICK = True: Perfect Information was NOT solved here.")
    print("It is 4,000 solves of 178 variables each, about two minutes, and it")
    print("should fit the bundled licence too. Its published value is read from")
    print("results/ below.")''')

    yield MD("""### Against the published figures

The comparison is to `reference/simstatstrad.csv`, which holds the paper's
Table 5 as the original pipeline produced it.""")

    yield CODE('''published = pd.read_csv(ROOT / "reference" / "simstatstrad.csv")
published = published.set_index(["Climate_Probability", "sim"])["profit_mean"]

check = solved.assign(
    published=[published[(r.label, r.scenario)] for r in solved.itertuples()],
)
check["difference"] = check["mean_profit"] - check["published"]

display(check[["label", "scenario", "published", "mean_profit", "difference"]]
        .style.format({"published": "{:,.4f}", "mean_profit": "{:,.4f}",
                       "difference": "{:+.4f}"}))

worst = check["difference"].abs().max()
print(f"\\nlargest difference: ${worst:,.4f} on profits of order $2,000,000")
print("The Dry Most Likely expected-value row is the known one - its first stage")
print("solves a problem whose objective is flat. See docs/reproduction-notes.md.")''')

    yield MD("""## 5. The full pipeline — optional, and needs a real licence

Everything above used the collapsed model. `scripts/run_all.py` solves the
original 704,002-variable formulation as the published run did, reproduces both
of the paper's tables, and takes about eight minutes.

It needs a full Gurobi licence. On Colab a node-locked licence cannot work — the
virtual machine differs every session — so use WLS credentials held as Colab
secrets, never as literals in the notebook: a key committed to a repository is
exposed the moment the repository is shared, and deleting it later does not
remove it from the history.

```python
import os
from google.colab import userdata          # SecretNotFoundError is EXPECTED
for k in ("WLSACCESSID", "WLSSECRET", "LICENSEID"):
    os.environ["GRB_" + k] = userdata.get("GRB_" + k)
```

Then:

```bash
python scripts/run_all.py
```

`tests/test_collapsed_agrees.py` is what ties the two together: it solves the
collapsed model and the full one and asserts they agree, so the fast path above
is not a different model with a convenient answer.""")


def build() -> nbformat.NotebookNode:
    nb = nbformat.v4.new_notebook(cells=list(cells()))
    nb.metadata.update({
        "kernelspec": {"display_name": "Python 3", "language": "python",
                       "name": "python3"},
        "language_info": {"name": "python",
                          "version": f"{sys.version_info.major}.{sys.version_info.minor}"},
    })
    return nb


def sources(nb) -> list[str]:
    return [c.source for c in nb.cells]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--check", action="store_true")
    args = p.parse_args(argv)

    nb = build()
    if args.check:
        if not TARGET.exists():
            print(f"{TARGET} does not exist; run without --check", file=sys.stderr)
            return 1
        on_disk = nbformat.read(TARGET, as_version=4)
        if sources(on_disk) != sources(nb):
            print("notebooks/00_walkthrough.ipynb is stale against "
                  "scripts/build_walkthrough.py. Rebuild it.", file=sys.stderr)
            return 1
        print(f"walkthrough matches its builder: {len(nb.cells)} cells")
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    # Ship it executed. A reader without a licence should still see every number
    # the prose refers to.
    client = NotebookClient(nb, timeout=1800, kernel_name="python3",
                            resources={"metadata": {"path": str(TARGET.parent)}})
    client.execute()
    nbformat.write(nb, TARGET)
    errors = [o for c in nb.cells for o in c.get("outputs", [])
              if o.get("output_type") == "error"]
    print(f"wrote {TARGET} — {len(nb.cells)} cells, {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
