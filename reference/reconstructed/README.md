# `reference/reconstructed/` — an estimate of an input that was lost

**These files are not the paper's input.** They are an estimate of it, built from
the committed precipitation draws by `scripts/reconstruct_markov.py`, and named
`reconstructed` so nobody can quote one as the original.

## What was missing

`stage2-r/markov_chain.Rmd`, `FM EP MC.Rmd` and `FM DML MC.Rmd` all open with

    tmA <- read.csv('~/Coding/Data/Farm_Model/trans_matrix.csv', header = TRUE)

a 20x20 transition matrix over the states `c1w1 .. c4w5`. Every R file *reads* it;
none creates it. It was already gone when this repository was carved out of the
original archive, and the path names a machine layout that no longer exists.

## Why its absence does not block the reproduction

The matrix generates the precipitation draws, and **the draws are committed** --
`stage1-python/precips_c0_{EP,DML}.csv`, 4,000 sequences of 25 years each. Every
number in the paper's Tables 4 and 5 follows from those. The matrix is needed only
to re-run the generation step, which is the one part of the pipeline the committed
inputs do not already cover.

## What the estimate recovers, and how well

Precipitation takes exactly five values, so the state sequence behind each draw is
recoverable without ambiguity, and the transition probabilities follow from the
counts -- 24,000 to 57,600 transitions per climate.

The estimate says something the original code does not: **within a climate, every
row is the same.** Whatever state a year starts in, the next year's distribution
is identical to within sampling error. The chain has no memory; the climate fixes
a weather distribution and each year is an independent draw from it.

| Climate | Estimated distribution over (w1 … w5) |
|---|---|
| 1 | 0.20, 0.50, 0.25, 0.05, 0.00 |
| 2 | 0.05, 0.25, 0.55, 0.10, 0.05 |
| 3 | 0.20, 0.20, 0.20, 0.20, 0.20 |
| 4 | 0.00, 0.05, 0.20, 0.45, 0.30 |

Two things support reading these as the original values. They are round numbers of
the kind a modeller writes down. And the two sites are **independent samples** --
different draws, generated in different R sessions -- yet agree to about 0.01,
which is the sampling error.

`provenance.csv` carries the evidence for each row: how many transitions it rests
on, the largest deviation of any single row from the pooled one, and the standard
error to compare that against.

## The two limits, stated rather than buried

- **This is a maximum-likelihood estimate, not the file.** Regenerating draws from
  it produces a statistically similar sample, never the committed one. The
  committed draws remain the input of record.
- **Two rows in each site are unidentified.** Climate 1 never reaches the wettest
  state and climate 4 never reaches the driest, so those rows have no observations
  and no row of their own to estimate. `provenance.csv` names them in
  `unidentified_rows`. They are filled from the pooled distribution of their own
  climate, which is defensible *only* because of the row homogeneity above, and
  `scripts/reconstruct_markov.py` refuses to write these files at all if that
  homogeneity does not hold.
- **The 12 off-diagonal 5x5 blocks are zero by construction, not by measurement.**
  A run never changes climate, so the data contains no between-climate
  transitions. Zero here means *never observed*. The pipeline only ever slices out
  the four diagonal blocks -- `tma[1:5,1:5]` and so on -- so nothing downstream
  depends on the off-diagonal values.

## Keeping it honest

A generated artifact and the script that generates it drift as fast as two pasted
copies. `scripts/reconstruct_markov.py --check` compares the committed files
against a fresh estimate, and `tests/test_markov_reconstruction.py` runs it, so
the drift fails a test rather than going unnoticed.
