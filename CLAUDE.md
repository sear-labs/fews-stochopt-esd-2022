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

**Archetype A**, batch analysis pipeline. `config.yaml`, `src/fews_stochopt/`,
`scripts/run_all.py`, `results/`, `tests/`.

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

## Exemptions from the invariants

- **Invariant 5, generated files.** Three documented exceptions, listed in the README:
  the precipitation inputs, `reference/`, and the headline `results/*.csv`. The 68 MB of
  per-run scenario CSVs are gitignored.
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

`stage1-python/` and `stage2-r/superseded/` are **history, not code**. They are what the
published run did and they no longer run — `DataFrame.append` was removed in pandas 2.0,
and the R reports carry paths to a machine layout that is gone. Do not repair them; the
model lives in `src/fews_stochopt/`.

`stage1-python/FEWS_Farm_model.py` is an earlier, different model — one period, two crops,
binary decisions. It is not this paper's deterministic core, whatever its name suggests.

## Working here alongside other sessions

One writer at a time in this folder; it is a git repo, so two sessions share one index and
one HEAD even when editing different files. Commit with explicit paths.
