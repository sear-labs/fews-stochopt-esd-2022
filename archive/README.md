# `archive/` — the code that produced the published result

**Everything here is preserved verbatim, never edited, and never maintained.**
It is not deleted, because it is the only evidence of what actually produced the
paper's numbers. It is not maintained, because its job is to say what the paper
did, not to be right.

A correction goes into `src/fews_stochopt/`, and the divergence is recorded in
`docs/reproduction-notes.md`. If you find a bug in here, **do not fix it here.**

| | |
|---|---|
| `stage1-python/` | the gurobipy notebooks. `FarmModelStoch_{EV,PI}_loop.ipynb` produced the paper's scenario outputs; `superseded/` holds six abandoned variants, two of which encode a *different* model with integer `pick_c*` variables |
| `stage1-python/FEWS_Farm_model.py` | an earlier, different model — one period, two crops, binary decisions. **Not** this paper's deterministic core, whatever the filename suggests |
| `stage2-r/` | the R analysis. `farm_report.Rmd`, `markov_chain.Rmd` and `render_reports.R` were this repository's own parameterised versions; `superseded/` holds the twenty originals, including the eleven site-specific reports they replaced |

## Why it is frozen, and how

Archetype P of the [code standard](https://github.com/sear-labs/code-standard)
requires one maintained implementation, in Python, on **both** sides of the
pipeline. Porting the model to Python while leaving the analysis in R does not
reduce the number of languages a reader needs — it moves the barrier from the
model to the figures. So the R went too:

    farm_report.Rmd    -> src/fews_stochopt/analysis.py + scripts/make_figures.py
    markov_chain.Rmd   -> fews_stochopt.markov.simulate
    render_reports.R   -> no longer needed; figures come from a script

`archive/MANIFEST.sha256` records a sha256 over the **raw bytes** of every file
here, and `scripts/freeze_archive.py --check` verifies it. A hash quoted without
its normalisation is not evidence, so the manifest says which it is.

`.gitattributes` marks `archive/** -text` so git never converts line endings.
Without it, `core.autocrlf=true` rewrites LF to CRLF on checkout, the raw-bytes
hash changes, and the freeze fails on every clean clone. That was found by
restoring one archived file and watching the manifest reject it.

## What still runs

Nothing here, reliably. The notebooks call `DataFrame.append`, removed in pandas
2.0. The superseded R carries absolute paths to a machine layout that no longer
exists. `stage2-r/farm_report.Rmd` and `markov_chain.Rmd` did run, on R 4.6.1 with
`rmarkdown`, `ggplot2`, `dplyr`, `tidyr` and `readr`, before being ported — that
is recorded in `requirements-lock-R.txt`, which is kept for the same reason this
directory is.
