# fews-stochopt

Stochastic programming model for climate risk management in agriculture — the food–energy–water
(FEWS) farm model behind Jones (2022), *Environment Systems and Decisions*,
[10.1007/s10669-021-09838-8](https://doi.org/10.1007/s10669-021-09838-8).

A farm chooses between utility and alternative water and electricity, and between crops, under
uncertain precipitation. The model reports the classic stochastic-programming quantities: the value
of known weather, the **expected value of perfect information**, and the **value of the stochastic
solution**, under two climate regimes.

## Status: reproduced

One command reproduces the paper's Tables 4 and 5 from source, and `pytest` checks the result
against the published values.

```bash
pip install -e .
python scripts/run_all.py
pytest
```

**Seven of the eight published scenario means come back within $0.76**, on figures of $1.9M–$2.4M.
The eighth is $20.35 out, for a reason that is located rather than tolerated — see *The one figure
that does not reproduce*. A cold run takes about seven minutes; solved scenarios are cached with a
digest of everything that could change them, so a second run takes seconds.

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
| | reproduced | 10,396.68 | **108,725.92** | 0.37 | 98,329.24 |
| Dry Most Likely | paper | $11,740.03 | $76,606.01 | $940.90 | $64,865.98 |
| | reproduced | 11,740.34 | 76,606.81 | 961.20 | 64,866.47 |

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
config.yaml                every parameter, both sites, the solver ladder, the tolerances
      |
src/fews_stochopt/         one model, four scenarios, one aggregation
      |
scripts/run_all.py         stage 1 solves, stage 2 aggregates
      |
      +-> results/solnvalues.csv       Table 4, all four columns
      +-> results/simstatstrad.csv     Table 5
      +-> results/<site>/              per-run output, with a provenance stamp
      |
stage2-r/farm_report.Rmd   one parameterised report; figures, and the same table recomputed
```

The four scenarios differ **only in how the runs are grouped** when the investment decision is
made — one group per run under perfect information, one per climate when the climate is known, one
overall for the stochastic solution, and a single deterministic path for the expected-value
solution. That observation is why one model replaced eight notebooks and eleven R reports.

`DML` and `EP` are the two case study sites. Everything the model needs is in
`stage1-python/precips_c0_{DML,EP}.csv`.

## The one figure that does not reproduce

Dry Most Likely / Expected Value comes back $20.35 low. The expected-value farm invests against a
single deterministic precipitation path, and **that problem's objective is flat in the capacities**:
two answers 0.08% apart differ by $0.43 there, and by $20 in the profit they go on to earn across the
4,000 realised weather runs.

Re-solving the second stage at the capacities the published run actually used — which survive as two
literals in `FM Traditional DML.Rmd` — reproduces that mean to **$0.36**, like the other seven. So
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

- **The published run used solutions Gurobi had not certified.** On default settings the barrier
  stalls short of its optimality tolerance on this model and returns status 13, SUBOPTIMAL — 27 of
  40 sampled runs. The original code never reads `m.Status`. `config.yaml` now carries a ladder of
  solver settings and `model.py` refuses anything that is not OPTIMAL; 1.5% of solves need a
  fallback rung.
- **`trans_matrix.csv` was needed only to regenerate the inputs**, which ship. It is now estimated
  from those inputs and committed under `reference/reconstructed/`, with the two limits stated:
  it is an estimate, and two rows per site are unidentified because no run ever visits those states.
  The estimate shows the chain has no memory — within a climate, every transition row is the same.
- **Eleven R reports became one.** `stage2-r/` was a 2 × 5 grid built by copy-paste plus two
  combining files, carrying more than thirty absolute paths to a machine layout that no longer
  exists. `farm_report.Rmd` takes `params: {site, label, root}`; the originals are kept under
  `stage2-r/superseded/` as the record of what the published run did.

`docs/reproduction-notes.md` has the measurements behind every one of these, including the parameter
sweeps that did *not* work.

## Running it

```bash
pip install -e .                      # needs a Gurobi licence
python scripts/run_all.py             # both sites, full sample
python scripts/run_all.py --runs 200  # smoke run; does NOT reproduce the paper
python scripts/run_all.py --force     # ignore cached scenario solutions
python scripts/run_all.py --reports   # also render the R reports
pytest                                # the acceptance suite
pytest -m pinned                      # just the pinned values; solves nothing
```

The R stage needs `rmarkdown`, `ggplot2`, `dplyr`, `tidyr` and `readr`:

```bash
Rscript -e 'install.packages(c("rmarkdown","ggplot2","dplyr","tidyr","readr"))'
Rscript stage2-r/render_reports.R
```

Without R, the `rstage` tests skip with a reason naming what is missing. They never report success
over an environment that could not run them.

## What is committed, and why

Generated files are gitignored, with three documented exceptions:

- **`stage1-python/precips_c0_*.csv`** — generated, but they are *inputs* to the optimisation and
  nothing runs without them. They are the input of record: `stage2-r/markov_chain.Rmd` writes a
  fresh sample to `results/regenerated/` and never over these.
- **`reference/`** — the published values, the transcribed first-stage capacities, and the
  reconstructed transition matrix. Inputs to the checks, never outputs of the pipeline.
- **`results/*.csv` and `figures/`** — the headline tables and the published figures, so a reader
  without a Gurobi licence sees the outputs without running anything. The 68 MB of per-run scenario
  CSVs underneath them are not committed.

## Which notebook is the model

There were **eight notebooks with no canonical version** — `Original`, `-v0`, `v2`, `v3`, `Stoch`,
`_EV_loop`, `_PI_loop`, `Untitled`. `stage1-python/` holds only the two that produced the paper's
scenario outputs; the other six are in `stage1-python/superseded/`, kept so nobody rediscovers one
and mistakes it for the model. **They are not maintained and should not be run** — they use
`DataFrame.append`, removed in pandas 2.0.

The model they encode now lives in `src/fews_stochopt/model.py`, which is what `run_all.py` calls
and what the tests check.

`stage1-python/FEWS_Farm_model.py` is a **different, earlier model** — one period, two crops, binary
investment decisions, a different yield curve. It is not the deterministic core of the paper's
model and is kept as history.

## How to cite

> Jones, Erick C., Jr. "Climate risk management in agriculture using alternative electricity and
> water resources: a stochastic programming framework." *Environment Systems and Decisions*, 2022.
> doi:10.1007/s10669-021-09838-8

BibTeX: `author = {Jones, Jr., Erick C.}` — the suffix is the middle field.

## Licence

MIT for the code — see `LICENSE`. The committed data under `reference/`, `stage1-python/*.csv` and
`figures/` is CC-BY 4.0; see `LICENSE-DATA`.
