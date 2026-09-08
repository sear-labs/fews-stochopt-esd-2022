# fews-stochopt

Stochastic programming model for climate risk management in agriculture — the food–energy–water
(FEWS) farm model behind Jones (2022), *Environment Systems and Decisions*,
[10.1007/s10669-021-09838-8](https://doi.org/10.1007/s10669-021-09838-8).

A farm chooses between utility and alternative water and electricity, and between crops, under
uncertain precipitation. The model reports the classic stochastic-programming quantities: the value
of known weather, the **expected value of perfect information**, and the **value of the stochastic
solution**, under two climate regimes.

**Archetype P** — a published result whose code is being replaced. One maintained implementation,
in Python, on both sides of the pipeline; the original preserved verbatim in `archive/` and frozen
by a test.

## Status: reproduced

One command reproduces the paper's Tables 4 and 5 from source, and `pytest` checks the result
against the published values.

```bash
pip install -e .
python scripts/run_all.py
pytest
```

**Seven of the eight published scenario means come back within $0.73**, on figures of $1.9M–$2.4M,
and they are **lower bounds rather than estimates** — every solver point is clipped back inside the
feasible region before it is read, so each figure is achievable in the model. The eighth is $24 out,
for a reason that is located rather than tolerated — see *The one figure that does not reproduce*.
A cold run takes about eight minutes; solved scenarios are cached with a digest of everything that
could change them, so a second run takes seconds.

**You can check the result without a solver and without a licence.** `artifacts/` ships twelve
frozen instances with their solutions, and `python scripts/verify_solution.py` confirms feasibility,
the objective and near-optimality from arithmetic alone, in half a second, with only numpy.

This required a Gurobi licence. The academic one this was verified on is node-locked and expires
2026-12-04, so the suite cannot run in CI as it stands. The *per-run* solves are 178 variables and
fit the free licence that ships with `pip install gurobipy`; only the two joint models -- 176k and
704k variables -- need a real one. See `docs/reproduction-notes.md` section 10.

## The published values

`reference/solnvalues.csv` holds **the paper's Table 4** — confirmed by reading the article, not
assumed. Against what `scripts/run_all.py` now produces:

| Climate regime | | EVKW | EVPI | VSS | EVKC |
|---|---|---|---|---|---|
| Equally Probable | paper | $10,396.32 | **$108,725.10** | $0.49 | $98,328.78 |
| | reproduced | 10,395.27 | **108,724.48** | 0.34 | 98,329.22 |
| Dry Most Likely | paper | $11,740.03 | $76,606.01 | $940.90 | $64,865.98 |
| | reproduced | 11,739.31 | 76,605.57 | 964.89 | 64,866.26 |

**EVKC is now produced.** It was in the paper and never in the pipeline output. It is
`KnownClimate − Stochastic`, which is not a guess: applied to the published Table 5 it gives
$64,865.9775 for Dry Most Likely, matching the paper to the cent, and it satisfies
EVPI = EVKW + EVKC identically.

**The known $0.04 discrepancy is unchanged and still asserted as known.** EVPI for the
equally-probable regime is $108,725.10 in the paper against 108,725.1417 in the pipeline output —
too small to be a different solution and too large to be rounding, which would give `.14`. Either
the article carries a typo or its table came from a slightly earlier run. It is asserted in
`tests/test_reproduces_paper.py` rather than smoothed over. It also turns out to appear in the EVKC
column, necessarily: EVKW agrees, so if EVPI is $0.04 high then EVKC must be too.

`reference/simstatstrad.csv` holds the Monte Carlo statistics behind Table 5.

## How the pipeline works

```
data/raw/                        the input of record: 4,000 weather draws per site
config.yaml                      every parameter, both sites, the solver ladder, the tolerances
      |
src/fews_stochopt/               one model, four scenarios, one aggregation
      |   model.py               the model as the original wrote it: 704,002 variables
      |   collapsed.py           the same model at the size it is: 37 variables
      |   analysis.py            stage 7: the cleaned output everything reads
      |
scripts/run_all.py               solve, aggregate, clean
      |
      +-> results/<site>/              RAW output, per run and year. 135 MB, gitignored
      +-> results/clean/               CLEANED output, tidy and long. 90 KB, COMMITTED
      +-> results/solnvalues.csv       Table 4, all four columns
      +-> results/simstatstrad.csv     Table 5
      |
scripts/make_figures.py          stage 9: figures, from cleaned output only
artifacts/                       12 frozen instances + solutions, 164 KB
scripts/verify_solution.py       checks them with numpy alone — no solver, no licence
notebooks/00_verification.ipynb  needs nothing   — the published result is correct
notebooks/01_example.ipynb       needs a solver  — the implementation runs and behaves
archive/                         the original gurobipy notebooks and R analysis, frozen
```

The four scenarios differ **only in how the runs are grouped** when the investment decision is
made — one group per run under perfect information, one per climate when the climate is known, one
overall for the stochastic solution, and a single deterministic path for the expected-value
solution. That observation is why one model replaced eight notebooks and eleven R reports.

`DML` and `EP` are the two case study sites. Everything the model needs is in
`data/raw/precips_c0_{DML,EP}.csv`.

### Two implementations of the model, and why there are two

`model.py` writes out every run and every year, as the notebooks did. `collapsed.py` observes that
given the capacities nothing couples one run-year to another, and that precipitation takes only five
values — so 100,000 second-stage blocks are 100,000 copies of five distinct problems.
**704,002 variables become 37, and 40 seconds become 0.01.** It is exact, not a reduction, and
`tests/test_collapsed_agrees.py` solves both and asserts they agree.

It is worth having because 37 variables fit the licence that ships with `pip install gurobipy`, and
704,002 do not.

### Two notebooks, two claims, deliberately apart

The verification notebook makes the reproduction claim and needs no solver. The example notebook
demonstrates the code. Merging them would let the stronger claim borrow the weaker one's
dependencies — a reader who only wants to check the paper should not be asked to install a solver.

### The archive is frozen, and that is enforced

`archive/` holds everything that produced the published result, verbatim. Archived is not deleted:
it is the only evidence of what made the numbers. Archived is also not maintained: a correction goes
into the Python and the divergence is recorded. `scripts/freeze_archive.py --check` fails if any
archived byte changes, and `tests/test_archive_and_one_language.py` runs it.

## The one figure that does not reproduce

Dry Most Likely / Expected Value comes back $24.05 low. The expected-value farm invests against a
single deterministic precipitation path, and **that problem's objective is flat in the capacities**:
two answers 0.08% apart differ by $0.43 there, and by $20 in the profit they go on to earn across the
4,000 realised weather runs.

Re-solving the second stage at the capacities the published run actually used — which survive as two
literals in the archived `FM Traditional DML.Rmd` — reproduces VSS to **$0.50**, against $24 for the freely re-solved figure. So
the discrepancy is entirely the first stage, and the tests assert the pinned version tightly. That
narrow check is what stops the wide tolerance on the free solve from hiding a real defect.

The same effect makes VSS unmeasurable at Equally Probable, where it is $0.49 — smaller than the
solver noise in the two means it differences.

## Two things the previous README recorded that turned out to be wrong

Both were reasonable readings of the code, and both are worth naming because they had made the
reproduction look harder than it was.

**The per-climate inputs are not missing.** `FM {EP,DML} MC.Rmd` builds its scenario set as
`c(precips_c1, precips_c2, precips_c3, precips_c4)` and then renumbers the runs 1..4000 — so the
four per-climate samples *are* the four slices of the committed file, and the block sizes are how
each site's climate probabilities are encoded (1000 each for EP; 2400/1000/400/200 for DML).

**The Monte Carlo loops are not sampling.** Both notebooks call `random.seed(a=100)` and then never
use `random`. `range(4000)` iterates over rows of the committed precipitation file. Stage 1 is
deterministic given that file, which is why the means reproduce to a dollar despite no seed being
recorded anywhere.

## What was found along the way

- **The published run used solutions Gurobi had not certified** — on default settings the barrier
  stalls and returns status 13 on 25 of 40 sampled runs, and the original code never reads
  `m.Status`. **But `OPTIMAL` is not feasibility either**: Gurobi returns points violating its own
  tolerance by 2,000× while reporting status 2. The artifact verifier caught that within minutes of
  existing, and it reversed a conclusion this README previously stated — the residual on the
  Perfect Information rows was largely *our own* solver rung overshooting the yield curve by ~$1 per
  run, not the published run's. Every point is now clipped back inside the feasible region.
  See `docs/reproduction-notes.md` §12.
- **`trans_matrix.csv` was needed only to regenerate the inputs**, which ship. It is now estimated
  from those inputs and committed under `reference/reconstructed/`, with the two limits stated:
  it is an estimate, and two rows per site are unidentified because no run ever visits those states.
  The estimate shows the chain has no memory — within a climate, every transition row is the same.
- **Eleven R reports became one, then became Python.** `stage2-r/` was a 2 × 5 grid built by copy-paste plus two
  combining files, carrying more than thirty absolute paths to a machine layout that no longer
  exists. `farm_report.Rmd` takes `params: {site, label, root}`; the originals are kept under
  `archive/stage2-r/superseded/` as the record of what the published run did. Under Archetype P the
  parameterised R went to `archive/` too: the analysis is now `analysis.py` and `make_figures.py`.

`docs/reproduction-notes.md` has the measurements behind every one of these, including the parameter
sweeps that did *not* work.

## Running it

```bash
pip install -e ".[dev]"
python scripts/verify_solution.py     # check the published result: no solver, no licence
python scripts/run_all.py             # solve both sites, full sample — needs Gurobi
python scripts/run_all.py --figures   # and regenerate figures/generated/
python scripts/run_all.py --runs 200  # smoke run; does NOT reproduce the paper
python scripts/run_all.py --force     # ignore cached scenario solutions
pytest                                # the acceptance suite
pytest -m pinned                      # just the pinned values; solves nothing
```

**R is no longer needed for anything.** The analysis and figures are Python; the original R lives
in `archive/` and is not maintained.

## What is committed, and why

Generated files are gitignored, with three documented exceptions:

- **`data/raw/precips_c0_*.csv`** — generated, but they are *inputs* to the optimisation and
  nothing runs without them. They are the input of record: `fews_stochopt.markov.simulate` writes a
  fresh sample to `results/regenerated/` and never over these.
- **`results/clean/`** — the cleaned output, tidy and long, 90 KB. Committed because without it
  nothing works from a clean clone. The 135 MB of per-run *raw* output beneath it is not: the
  archetype's ~10 MB boundary is met by committing the right layer, not by compressing the wrong one.
- **`figures/generated/`** — regenerated by `scripts/make_figures.py`, each with a text alternative.
- **`reference/`** — the published values, the transcribed first-stage capacities, and the
  reconstructed transition matrix. Inputs to the checks, never outputs of the pipeline.
- **`results/*.csv` and `figures/`** — the headline tables and the published figures, so a reader
  without a Gurobi licence sees the outputs without running anything. The 68 MB of per-run scenario
  CSVs underneath them are not committed.

## Which notebook is the model

There were **eight notebooks with no canonical version** — `Original`, `-v0`, `v2`, `v3`, `Stoch`,
`_EV_loop`, `_PI_loop`, `Untitled`. `archive/stage1-python/` holds them all — the two that produced
the paper's scenario outputs, and six variants under `superseded/`, kept so nobody rediscovers one
and mistakes it for the model. **They are not maintained and should not be run** — they use
`DataFrame.append`, removed in pandas 2.0.

The model they encode now lives in `src/fews_stochopt/model.py`, which is what `run_all.py` calls
and what the tests check.

`archive/stage1-python/FEWS_Farm_model.py` is a **different, earlier model** — one period, two crops, binary
investment decisions, a different yield curve. It is not the deterministic core of the paper's
model and is kept as history.

## How to cite

> Jones, Erick C., Jr. "Climate risk management in agriculture using alternative electricity and
> water resources: a stochastic programming framework." *Environment Systems and Decisions*, 2022.
> doi:10.1007/s10669-021-09838-8

BibTeX: `author = {Jones, Jr., Erick C.}` — the suffix is the middle field.

## Licence

MIT for the code — see `LICENSE`. The committed data under `reference/`, `data/raw/`,
`results/clean/`, `artifacts/` and `figures/` is CC-BY 4.0; see `LICENSE-DATA`.
