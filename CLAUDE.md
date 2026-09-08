# fews-stochopt conventions

The portable standard governs this repo. **Read it first and last** — first because it
decides how the work is done, last because a change you are about to make may be
something it already settles.

    https://github.com/sear-labs/code-standard    canonical; the same from any machine,
                                                  no clone and no auth needed
    a local clone, if you have one                faster; check the branch, then pull

**The URL is the address; a path is a convenience.** An absolute path is true of one
machine and silently wrong on every other.

Nothing below restates the standard. A subordinate document may point at it and may never
summarise it: a partial restatement reads as complete and stops the search.

---

# Part 11 — This project specifically

## Archetype and the four axes

**Archetype P** — a published result whose code is being replaced. Archetype A plus a
preserved original and the machinery that keeps the two honest. Adopted 2026-09-08
(code-standard amendment 6).

**The rule, applied here:** everything that produced the published result is in `archive/`,
verbatim and frozen; exactly one implementation is maintained and it is Python. That
applies on **both sides** — porting the model to Python while leaving the analysis in R
would only move the barrier from the model to the figures, so the 674 lines of R went too.

The nine stages, and which are empty here:

| stage | here |
|---|---|
| input raw | `data/raw/precips_c0_*.csv`, committed |
| clean-up code | **empty** — the raw input is already open plain-text |
| cleaned data | **empty** — same files; nothing to clean |
| model files | `archive/` (original) and `src/fews_stochopt/` (maintained) |
| raw output | `results/<site>/*.csv`, 135 MB, gitignored |
| clean-up output code | `src/fews_stochopt/analysis.py` |
| cleaned output | `results/clean/`, 90 KB, tidy and long, **committed** |
| analysis code | `analysis.py` and `aggregate.py`, `.py` |
| figures | `scripts/make_figures.py` |

**A stage being empty is a finding, not an omission.** Two of the nine do not exist here
because the original's input needed no conversion.

**And one stage sat in the wrong directory.** `markov_chain.Rmd` was filed in
`stage2-r/` beside the report files, but it is a *generator*: it produces
`data/raw/precips_c0_*.csv`, which is the model's input. That is stages 1-3, not
stage 8, and it changes the acceptance test -- a report is checked by comparing
tables, a generator whose RNG state was never recorded can only be checked
distributionally. Ported to `fews_stochopt.markov.simulate`, asserted by
`tests/test_markov_reconstruction.py`. Check what a "reporting" directory
actually contains before accepting its label.

| Axis | Answer |
|---|---|
| How sensitive? | Not. Public paper, public data, no restricted inputs. It stays private only until the reproduction is finished. |
| Actively developed? | Yes — so it has git. |
| In a syncing folder? | No. `C:\Users\jonesec\dev\repo\projects\` is outside OneDrive, so `.git` lives in place and the pointer treatment does not apply. |
| How many devices edit it? | One. |

Restricted Pecan Street data is **not** used. Checked rather than assumed: the model's
only inputs are the two committed precipitation files and `config.yaml`.

## The one command

```bash
python scripts/run_all.py     # about 7 minutes cold, seconds warm
pytest                        # the acceptance suite
```

Solved scenarios are cached under `results/<site>/` with a `.meta.json` carrying a digest
of the configuration, the input file, the source of every module that builds the model,
the run count and the solver version. A mtime would not be able to tell it was stale;
these can. `--force` bypasses it.

`config.solve_digest()` deliberately excludes `tolerances` — a tolerance says how closely
a result must match a published figure and enters no model, so folding it in would discard
seven minutes of solves every time a check was adjusted.

## Known defects and deliberate deviations

Each of these is asserted somewhere rather than only written here, because a requirement
that lives only in prose has already failed. `docs/reproduction-notes.md` has the
measurements.

| | Where it is asserted |
|---|---|
| EVPI at Equally Probable is $0.04 off the article — the paper's figure or an earlier run | `test_pinned_values_agree_with_the_published_table` |
| Dry Most Likely / Expected Value is $20.35 off, entirely from a flat first stage | `test_stochastic_solution_value_is_reproduced_at_the_published_first_stage` |
| The expected-value rain path ends at 107 cm where the weather state is 106.68 | `test_expected_value_rain_path_is_drawn_from_the_weather_states` |
| Standard errors divide by `sqrt(n-1)`, reproducing the original | the R report and `aggregate._summary`, both commented |
| `profit` carries a lower bound of zero, as in the original | `test_profit_non_negativity_never_binds` |
| `reference/reconstructed/` is an estimate; two rows per site are unidentified | `test_unidentified_rows_are_recorded_not_invented` |
| The five weather states are rounded to 2 dp, reproducing R's `as.character`; the exact product matches nothing | `test_the_state_values_survive_the_formatting_round_trip` |
| A regenerated sample matches the committed distribution, never the committed draws | `test_a_fresh_sample_has_the_committed_distribution` |
| The archive must never change | `test_the_archive_is_frozen` |
| No maintained code in a second language | `test_no_maintained_code_is_in_another_language` |
| The verification notebook must not need a solver | `test_the_verification_notebook_needs_no_solver` |

## Exemptions from the invariants

- **Invariant 5, generated files.** Five documented exceptions, listed in the README: the
  precipitation inputs, `reference/`, the headline `results/*.csv`, `results/clean/` and
  `figures/generated/`. The 135 MB of per-run raw output is gitignored.
- **Archetype P's ~10 MB comfort boundary on committed cleaned output.** The tidy per-run
  detail would be 135 MB. The boundary is met by committing the right *layer* — the
  per-(site, scenario, year) aggregate at 90 KB — rather than by compressing the wrong one.
  Worth saying because "compress or subset" is not the only escape.
- **Invariant 6, CI on a clean machine.** Not possible as things stand: Gurobi's licence
  here is academic and node-locked, expiring 2026-12-04. The per-run solves are 178
  variables and fit the size-limited licence that ships with `pip install gurobipy`; the
  two joint models are 176k and 704k variables and do not. **Do not repeat the inherited
  claim that HiGHS lifts this** -- HiGHS does convex quadratic objectives, this model has a
  quadratic constraint, and nobody has checked. See section 10 of
  `docs/reproduction-notes.md` for two routes that do work on the mathematics.
- **Part 6, the published path.** This repository is run from a checkout, not a wheel — it
  needs the committed inputs and a licence. `config.repo_root()` says so loudly rather
  than returning a path that is only right on the machine that built it.

## Where the numbers come from

`archive/` is **history, not code**. It is what the published run did, and it no longer runs
— `DataFrame.append` was removed in pandas 2.0, and the superseded R carries paths to a
machine layout that is gone. **Do not repair anything in there**: a correction goes into
`src/fews_stochopt/` and the divergence is recorded in `docs/reproduction-notes.md`. The
freeze test will stop you anyway.

`archive/stage1-python/FEWS_Farm_model.py` is an earlier, different model — one period, two
crops, binary decisions. It is not this paper's deterministic core, whatever its name
suggests.

**One deviation from the adopted text, recorded rather than silently taken.** Archetype P
says to read the primal residual and *scale it by the largest constraint-matrix
coefficient*. This repository records that scaled residual per solve
(`scaled_violation_before_repair`) but does not gate on it: `model._repair` clips the point
back inside the feasible region instead, which removes the violation rather than accepting a
small one. Gating on a scaled threshold was tried and rejected — see
`docs/reproduction-notes.md` §12. That was raised in review before the amendment merged and
is worth re-petitioning if it recurs elsewhere.

## Working here alongside other sessions

One writer at a time in this folder; it is a git repo, so two sessions share one index and
one HEAD even when editing different files. Commit with explicit paths.
