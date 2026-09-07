# Published figures

Result figures from the paper, moved here from `yamierick/gradschool-research-code`. They were the
last part of the published output living outside a named repository.

Named by climate scenario and quantity: `MI-{DML,EP}_{profit,invest,water,elc,cy}.pdf` and the
aggregate `objectives.pdf`, `profit.pdf`, `waterop.pdf`, `waterinvest.pdf`, `elcop.pdf`.

`DML` and `EP` are the two case-study sites; `MI` is multi-iteration.

**Committed deliberately**, as invariant 5 permits: a reader sees the published outputs without
running anything, and without a Gurobi licence.

## These are the published figures, not the current ones

They were drawn by `FM {DML,EP} Graphs.Rmd`, which are now under `stage2-r/superseded/` — they
carry hardcoded absolute paths to a machine layout that no longer exists and do not run.

The replacement is `stage2-r/farm_report.Rmd`, one parameterised report rendered once per site by
`python scripts/run_all.py --reports`. Its figures are drawn from a fresh run and land in
`results/reports/`, which is not committed because the tables that carry every number in them are.

So the two sets are not the same artifact and should not be compared pixel for pixel: these are the
paper's, and `results/reports/` holds this repository's. The numbers behind both are checked against
each other in `tests/test_reproduces_paper.py`.

## Accessibility

The figures here are as published and carry no text alternatives. That is a real gap and it is
recorded rather than left implicit: 55 PDFs, none with alt text.

It is not remediated here because these are a frozen record of the article. The obligation attaches
to what this repository generates going forward, and `farm_report.Rmd` and `markov_chain.Rmd` write
an alt-text description in the same cell as every plot they draw — at authoring time, which is the
only point where it costs one sentence rather than a project. Both also put the numbers behind each
figure in a table beside it, so a reader who cannot see a plot is not asked to take it on trust.
