# Archived — these notebooks are history and are **not expected to run**

Eight `.ipynb` files. None of them executes on a current environment, and that is
**not a defect to be fixed**.

They call `DataFrame.append`, which pandas removed in 2.0. Repairing them is
exactly what Archetype P forbids: the archive's job is to say what the paper did,
not to be right. A correction goes into `src/fews_stochopt/`, and the divergence
is recorded in `docs/reproduction-notes.md`.

This file exists because eight broken notebooks with nothing marking them as
history read to a stranger as eight broken notebooks.

| | |
|---|---|
| `FarmModelStoch_EV_loop.ipynb` | **canonical** — produced the paper's `*_ev.csv` scenario outputs |
| `FarmModelStoch_PI_loop.ipynb` | **canonical** — produced the `*_pi.csv` outputs |
| `FEWS_Farm_model.py` | a *different, earlier* model: one period, two crops, binary decisions. Not this paper's deterministic core, whatever the filename suggests |
| `superseded/` | six abandoned variants. Two of them — `Farm Model Original.ipynb` and `FarmModelStoch.ipynb` — encode a **different model** with integer `pick_c*` variables that the published one has none of |

That last row is why `tests/test_bounds_match_the_original.py` names its four
canonical sources explicitly instead of globbing this directory: a sweep that
included the variants reported a bound the published model does not have.

Three of the superseded notebooks carry `C:\Users\Jones\gurobi.lic` in committed
output. That is Gurobi's startup banner — a path and an expiry, **no key
material**.

What replaced them: `src/fews_stochopt/model.py`, which builds the model once
where the notebooks each built their own copy.
