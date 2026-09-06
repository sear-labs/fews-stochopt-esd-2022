# fews-stochopt

Stochastic programming model for climate risk management in agriculture — the food–energy–water
(FEWS) farm model behind Jones (2022), *Environment Systems and Decisions*,
[10.1007/s10669-021-09838-8](https://doi.org/10.1007/s10669-021-09838-8).

A farm chooses between utility and alternative water and electricity, and between crops, under
uncertain precipitation. The model reports the classic stochastic-programming quantities: the value
of known weather, the **expected value of perfect information**, and the **value of the stochastic
solution**, under two climate regimes.

## Status: the code is here, the reproduction is not finished

**`pytest` fails on a clean clone, deliberately.** The paper's published values are pinned in
`tests/test_reproduces_paper.py`, and nothing in this repository yet regenerates them from source.
That failure is the honest state of the work, written where it will be read — see
*What is not done yet*.

| | |
|---|---|
| `test_reference_file_still_says_what_we_pinned` | **passes** — guards the pinned numbers against edits |
| `test_pipeline_reproduces_published_values` | **fails** — no `scripts/run_all.py` exists |

## The published values

From `reference/solnvalues.csv`:

| Climate regime | Value of known weather | Value of perfect information | Value of stochastic solution |
|---|---|---|---|
| Equally Probable | 10,396.32 | 108,725.14 | 0.4887 |
| Dry Most Likely | 11,740.03 | 76,606.01 | 940.90 |

`reference/simstatstrad.csv` holds the Monte Carlo statistics behind them.

## How the pipeline actually works

It is **two languages in two stages**, which is the main reason it is not yet reproducible by one
command:

```
stage1-python/   gurobipy models, one solve per scenario in Monte Carlo loops
      |          FarmModelStoch_EV_loop.ipynb  -> csvs/{DML,EP}/*_ev.csv
      |          FarmModelStoch_PI_loop.ipynb  -> csvs/{DML,EP}/*_pi.csv
      v
stage2-r/        FM Final Outputs.Rmd aggregates those into the table above
```

`DML` and `EP` are the two case study sites. `_ev` is the expected-value solution, `_pi` the
perfect-information solution; the difference between them is what EVPI measures.

`stage1-python/FEWS_Farm_model.py` is the deterministic core, written in **Pyomo**. The stochastic
notebooks are **raw gurobipy** — the two stages of the project used different modelling layers.

## What is not done yet

1. **The R stage cannot run on any machine as committed.** All seven files in `stage2-r/` carry
   hardcoded absolute paths to a layout that no longer exists — `~/Coding/R/Research/Farm Model/
   Graphs/`, `C:\Users\Jones\Documents\Coding\Python\Farm Model\`. `FM Final Outputs.Rmd`, the file
   that produces the reference table above, has **nine** of them. This is not "needs running by
   hand"; it is broken until the paths are parameterised.
2. **One input has been missing all along.** `FM DML MC.Rmd` reads
   `~/Coding/Data/Farm_Model/trans_matrix.csv` — a Markov transition matrix that **exists nowhere in
   the source archive** and was already absent before this repository was split out. Whatever it
   held has to be reconstructed or the file rewritten.
3. **No single entry point.** Part 1's first invariant is that one command reproduces everything.
   Neither stage runs headless.
4. **The intermediate CSVs are gitignored.** They are 68 MB of generated scenario output, and
   invariant 5 says generated files do not belong in git. But until stage 1 runs from a clean clone,
   removing them means stage 2 has nothing to read. `reference/` is the documented exception.
5. **No seeds.** The Monte Carlo loops (`range(1000)`, `range(4000)`) do not record a seed, so a
   re-run will not reproduce the published statistics exactly even once the pipeline runs. Fixing
   this is a prerequisite for the red test ever going green, not an afterthought.
6. **No environment lock.** Requires `gurobipy` and a Gurobi licence; the R stage requires
   `tidyverse`. Neither is pinned.

## Which notebook is the model

There were **eight notebooks with no canonical version** — `Original`, `-v0`, `v2`, `v3`, `Stoch`,
`_EV_loop`, `_PI_loop`, `Untitled` — the failure Part 7's duplication check exists to catch.

`stage1-python/` holds only the two that produced the paper's scenario outputs. The other six are in
`stage1-python/superseded/`, kept so nobody rediscovers one and mistakes it for the model. **They are
not maintained and should not be run.**

## Licensing note

Requires a Gurobi licence. The one on the author's machine is **academic and node-locked**, which
means it cannot run in CI — relevant if the red test is ever to be enforced automatically. An open
solver (HiGHS via Pyomo) would remove that constraint for the smaller per-scenario solves.

## How to cite

> Jones, Erick C., Jr. "Climate risk management in agriculture using alternative electricity and
> water resources: a stochastic programming framework." *Environment Systems and Decisions*, 2022.
> doi:10.1007/s10669-021-09838-8

BibTeX: `author = {Jones, Jr., Erick C.}` — the suffix is the middle field.

## Licence

MIT — see `LICENSE`.
