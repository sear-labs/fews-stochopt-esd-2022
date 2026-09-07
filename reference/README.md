# `reference/` — what the paper published, kept so a rerun can be compared to it

These files are **inputs to the checks, not outputs of the pipeline.** They are the
documented exception to the rule that generated files stay out of git: without
them a clean clone can run the model but cannot tell whether the answer is right.

`results/` holds what a run produces. Nothing here is ever written by
`scripts/run_all.py`.

| File | What it is |
|---|---|
| `solnvalues.csv` | **Table 4.** The value-of-information figures, as produced by `stage2-r/FM Final Outputs.Rmd` for the paper. Three columns; the paper's fourth, EVKC, was never in the pipeline output and is reconstructed by `src/fews_stochopt/aggregate.py`. |
| `simstatstrad.csv` | **Table 5.** Mean, standard deviation, t, standard error and half-width of profit and crop yield, for each of the four scenarios at each of the two sites. |
| `published_first_stage.csv` | The expected-value investment decision the published run used, transcribed from the two `FM Traditional *.Rmd` files where it survives as a pair of literals. |

## Why `published_first_stage.csv` exists

Everything else the published run computed lives in `.RData` files that were never
committed. These two numbers per site survived only because the R report pasted
them in as constants rather than loading them.

That accident is useful. Seven of the eight scenario means reproduce from source
to within $0.76. The eighth — Dry Most Likely, Expected Value — is $20.35 out,
and the reason is that its first-stage investment is the solution of a
*deterministic* problem whose objective is flat: capacities 0.08% apart differ by
$0.43 in that objective, and by $20 in the profit they go on to earn across the
4,000 realised weather runs.

Re-solving the second stage at the capacities above reproduces that eighth mean
to $0.36, like the other seven. So the discrepancy is located, not merely
tolerated, and `tests/test_reproduces_paper.py` asserts the located version
tightly — which is what stops the wider tolerance on the free solve from hiding a
real defect. See `docs/reproduction-notes.md`.

**These capacities are never used to produce `results/solnvalues.csv`.** That
table is solved from source end to end. They are used only by the diagnostic that
explains the one figure that does not match.
