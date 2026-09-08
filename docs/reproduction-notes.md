# Reproduction notes

Every tolerance in `config.yaml` is a measurement. This is where the measurements
are, with the run that produced them, so a reader can tell a number that was
measured from one that was chosen to make a check pass.

Measured on 2026-09-06: Gurobi 13.0.2, Python 3.13, Windows 11, academic licence
2750151. A full cold run is about seven minutes.

---

## 1. What reproduces, and how closely

`scripts/run_all.py` solves all four scenarios at both sites from the committed
precipitation inputs and aggregates them. Against `reference/simstatstrad.csv`:

| Site | Scenario | Published mean profit | Reproduced | Difference |
|---|---|---:|---:|---:|
| Equally Probable | Perfect Information | 2,355,663.1032 | 2,355,662.3753 | −0.7279 |
| Equally Probable | Known Climate | 2,345,266.7851 | 2,345,267.1068 | +0.3217 |
| Equally Probable | Stochastic | 2,246,937.9615 | 2,246,937.8910 | −0.0705 |
| Equally Probable | Expected Value | 2,246,937.4728 | 2,246,937.5497 | +0.0769 |
| Dry Most Likely | Perfect Information | 1,975,827.2395 | 1,975,826.7392 | −0.5002 |
| Dry Most Likely | Known Climate | 1,964,087.2089 | 1,964,087.4288 | +0.2199 |
| Dry Most Likely | Stochastic | 1,899,221.2314 | 1,899,221.1646 | −0.0668 |
| **Dry Most Likely** | **Expected Value** | **1,898,280.3314** | **1,898,256.2783** | **−24.0531** |

**Seven of eight within $0.73.** The eighth is section 3.

These are **lower bounds, not estimates.** `model._repair` clips each solver
point back inside the feasible region before anything reads it, so every figure
above is achievable and the model's true optimum sits at or above it. That is why
most residuals are now negative where an earlier version of this table had them
positive: the sign changed because the claim changed, not because the model did.
See section 12.

And the value-of-information table, against `reference/solnvalues.csv`:

| Site | Quantity | Published | Reproduced | Difference |
|---|---|---:|---:|---:|
| Equally Probable | EVKW | 10,396.3181 | 10,395.2685 | −1.0496 |
| Equally Probable | EVPI | 108,725.1417 | 108,724.4843 | −0.6574 |
| Equally Probable | EVKC | 98,328.8236 † | 98,329.2158 | +0.3922 |
| Equally Probable | VSS | 0.4887 | 0.3413 | −0.1474 |
| Dry Most Likely | EVKW | 11,740.0306 | 11,739.3104 | −0.7201 |
| Dry Most Likely | EVPI | 76,606.0081 | 76,605.5746 | −0.4335 |
| Dry Most Likely | EVKC | 64,865.9775 † | 64,866.2642 | +0.2867 |
| Dry Most Likely | VSS | 940.8999 | 964.8863 | +23.9864 |

† EVKC was never in the pipeline output. These are derived from Table 5 as
`KnownClimate − Stochastic`; see section 2.

**So `scenario_mean_abs_dollars` is 2.0** against a worst observed 0.73, and
**`value_of_information_abs_dollars` is 2.0** against a worst observed 1.05. Both
sit two to three orders of magnitude below anything a real defect would produce: a
mis-sliced climate block moves EVPI by thousands, as the `--runs 200` smoke run
shows (EVPI 107,055 against 108,725).

---

## 2. EVKC: recovering a column that was never computed

The paper reports four quantities and `reference/solnvalues.csv` carries three.
The missing one is EVKC, the expected value of known climate — $98,328.78 and
$64,865.98.

It is `KnownClimate − Stochastic`. That is not a guess. Applying it to the
published Table 5 gives **64,865.9775 for Dry Most Likely**, which rounds to the
paper's $64,865.98 exactly. It also satisfies EVPI = EVKW + EVKC identically,
which is what makes the decomposition meaningful: the value of perfect information
splits into knowing your climate and, given that, knowing your weather.

Applying it to Equally Probable gives 98,328.8236 against the paper's $98,328.78 —
**off by the same $0.04 the EVPI column is off by.** That is necessary rather than
coincidental: EVKW agrees, so if EVPI is 0.04 high then EVKC must be too. The
known discrepancy simply shows up in a second column.

`tests/test_reproduces_paper.py::test_evkc_definition_matches_the_paper` asserts
all three of those facts.

---

## 3. The one figure that does not reproduce, and why

Dry Most Likely / Expected Value is $20.35 out. The cause is located, not
tolerated.

The expected-value scenario invests against a single deterministic precipitation
path, then lives with that investment through all 4,000 realised runs. The first
stage is therefore the solution of a small deterministic problem — and that
problem's objective is **flat in the capacities.**

Solving it several ways:

| Solver settings | alt water cap (cm) | alt elc cap (kW) | Deterministic objective |
|---|---:|---:|---:|
| BarHomogeneous + NumericFocus 3 | 11.854334 | 222.0711 | 1,856,879.0753 |
| … + ScaleFlag 2 | 11.853924 | 222.0643 | 1,856,878.6495 |
| Published run (from `FM Traditional DML.Rmd`) | 11.844907 | 221.9111 | — |

The first two differ by 0.003% in capacity and **$0.43** in the objective that
chooses them. The published run's capacities are 0.08% away from ours. That is
indistinguishable in the deterministic problem — and worth **$20** in profit
earned across the realised weather.

The decisive check: re-solve the *second* stage at the published capacities.

| Site | Published VSS | VSS at the published first stage | Difference |
|---|---:|---:|---:|
| Equally Probable | 0.4887 | 0.2167 | −0.2720 |
| Dry Most Likely | 940.8999 | 940.3978 | −0.5021 |

**Both within about half a dollar**, against a freely re-solved figure that is
$24 out at Dry Most Likely. The second stage is correct; the entire discrepancy
is which point on a flat ridge the first-stage solve happened to land on.

That is why `config.yaml` carries two tolerances rather than one wide one.
`expected_value_first_stage_sensitivity_dollars: 25.0` bounds how far a freely
re-solved first stage may wander, and it is only honest because
`test_stochastic_solution_value_is_reproduced_at_the_published_first_stage`
asserts the pinned version at $2. A wide bound with nothing narrow beside it would
be a check reporting its own edge.

### The same effect explains VSS at Equally Probable

There, VSS is $0.49 — a difference between two means each carrying about $0.1 of
solver noise. It is not a reproducible quantity at any tolerance, and the honest
statement is that the expected-value and stochastic first stages are the same
decision to within measurement. The paper's own text says as much: the value of
the stochastic solution is negligible when climates are equally likely.

---

## 4. The published run used solutions the solver had not certified

This one was found by adding a status check the original does not have.

On Gurobi's default settings, the barrier stalls short of its optimality tolerance
on most single-run solves of this model and returns **status 13, SUBOPTIMAL**.
Measured over 40 sampled runs at Equally Probable: **25 of 40 uncertified.** The
original notebooks read `profit.X` immediately after `m.optimize()` and never look
at `m.Status`, so those solutions went into the published means.

`solver.parameter_ladder` in `config.yaml` fixes it, and `model.py` raises rather
than returning anything not OPTIMAL:

| Rung | Settings | Certified |
|---|---|---|
| 1 | `BarHomogeneous 1, NumericFocus 3` | 197 of 200 sampled runs |
| 2 | + `ScaleFlag 2` | the remaining 3 |
| 3 | `NumericFocus 3` alone | (unused in practice) |

Where two rungs both certify they agree to about 1e-3 on a $2.6M objective. Over
the full run, **240 of 16,010 solves (1.5%) needed a fallback rung**, and
`tests/test_invariants.py::test_every_solve_was_certified_optimal` fails if that
share ever exceeds 10% — which would mean the first rung had quietly stopped being
the normal path.

### Why not just widen the tolerance until it certifies?

The obvious move, and it **works** — which is exactly the problem. Measured over
the same 40 runs, building each model directly so no ladder can intervene:

| Setting | Certified | Worst gap vs the anchor |
|---|---:|---:|
| Gurobi defaults | 15 / 40 | $2.01 |
| **loosen** `BarQCPConvTol 1e-4` | 27 / 40 | $154.63 |
| **loosen** `BarQCPConvTol 1e-3` | **40 / 40** | **$264.77** |
| **loosen** `BarQCPConvTol 1e-2` | 40 / 40 | $264.77 |
| tighten `BarQCPConvTol 1e-9` | 0 / 40 | $4.76 |
| **`BarHomogeneous 1, NumericFocus 3`** (shipped) | **40 / 40** | anchor |

Loosening buys the **status**, not the convergence. At `1e-3` every solve reports
OPTIMAL and the answers are up to $265 out — against an EVPI of $108,725 and a VSS
of $941, that would swamp the quantities the paper is about. It is the mirror of
the failure the standard records as *a loose MIP gap manufactures agreement*.

`BarHomogeneous` and `NumericFocus` are a different kind of change: they select
the homogeneous self-dual barrier and make Gurobi more careful numerically. They
move the **algorithm**, not the acceptance threshold, so the certification is
earned rather than relabelled.

### Is the anchor right, or only self-consistent?

A setting that certifies everything and agrees with itself proves nothing. Two
independent cross-checks, on the same 40 runs:

| Comparison | Where both certify | Worst | Median |
|---|---|---:|---:|
| anchor vs rung 2 (different scaling) | 40 / 40 | $0.34 | $0.20 |
| anchor vs **Gurobi defaults**, on the runs defaults *did* certify | 15 / 40 | $1.14 | $0.49 |

Where the default solve reaches certified optimality it agrees with the anchor.
Where it does not, the disagreement is **signed**: mean +$0.69, sd $0.34, never
negative. That is a bias, not scatter, so it does not average away over 4,000
runs — and it is the same sign and size as the residual in section 1, where
Perfect Information reproduces +$0.69 at Equally Probable and +$0.75 at Dry Most
Likely. **The reproduction gap on those rows is largely the uncertified-solve
bias in the published numbers.**

Tightening is also worth recording so nobody tries it: `BarQCPConvTol 1e-9` and
`1e-12` certify *fewer* solves, not more. The residual is not convergence
tolerance; it is where the interior-point method stops.

---

## 5. Seeds: the randomness is in the input file

The briefing's third item was that no seeds are recorded, so results would not
reproduce. **That turns out not to apply to the optimisation.**

Both canonical notebooks call `random.seed(a=100)` and then never use `random`.
The Monte Carlo loops `range(1000)` and `range(4000)` are not sampling — they are
**iterating over rows of `precips_c0_*.csv`**, which is committed. Every draw the
published run used is in that file. Stage 1 is deterministic given it, and Gurobi
is deterministic given identical parameters and version.

So the seed is recorded in `config.yaml` and in `farm_report.Rmd` for honesty
rather than for effect, and both say so where they set it. The reproduction above
is the evidence: seven of eight means to within a dollar, which would be
impossible if anything were resampling.

Where seeds *do* matter is scenario generation — `markov_chain.Rmd`. The original
set `set.seed(12345)` but the draws depended on RNG state accumulated through
earlier chunks, so its exact sample cannot be recovered. That document therefore
writes to `results/regenerated/` and never over the committed inputs, and checks
its fresh sample against them distributionally instead.

---

## 6. The missing input was never needed for the table

`trans_matrix.csv` is read by three R files and created by none. It was already
gone before the split.

It generates the precipitation draws — and **the draws are committed**, so nothing
about Tables 4 and 5 depends on it. What it blocked was re-running the generation
step.

It is now estimated from the committed draws, because precipitation takes only
five values so the state sequence behind every run is recoverable exactly. The two
sites are independent samples of the same underlying matrix and their estimates
agree to about 0.01, which is the sampling error — the strongest available
evidence that the estimate recovers the original rather than the sample. See
`reference/reconstructed/README.md`.

The estimate also shows something the original code does not state: within a
climate, **every transition row is the same.** The chain has no memory.

---

## 7. The climate blocks, and why nothing else was missing

The README used to record that `FM DML MC.Rmd` needed inputs that do not ship. It
does not.

`FM {EP,DML} MC.Rmd` builds its scenario set as

```r
precips_c0 <- c(precips_c1, precips_c2, precips_c3, precips_c4)
precips_c0_tbl <- precips_c0_tbl %>% mutate(run = rep(seq(1,4000), each=25))
```

so **the per-climate draws are the four slices of the committed c0 file**, and a
run's climate is decided by its position. The block sizes are how each site's
climate probabilities are encoded — `iters * 4 * prob` runs per climate:

| Site | Climate 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| Equally Probable (0.25 each) | runs 1–1000 | 1001–2000 | 2001–3000 | 3001–4000 |
| Dry Most Likely (.60/.25/.10/.05) | 1–2400 | 2401–3400 | 3401–3800 | 3801–4000 |

Confirmed three ways. Against `run_c1 = list(range(2400))` and its siblings in
`FM MI DML All Climates.Rmd`. At runtime by `data.py::_check_blocks`, which
refuses to load a file whose block sizes and declared probabilities disagree.
And -- found later, on a prompt from the session reproducing the SAV paper --
**by the line that wrote the file, which survives commented out** at
`FM Traditional EP.Rmd:38`:

```r
#write.csv(precips_c0_tbl, '~/Coding/Python/Farm Model/precips_c0_EP.csv')
```

`precips_c0_tbl` is the `rbind` of the four per-climate tables with the runs
renumbered 1..4000. So this is not an inference about how the shipped file was
built; it is the statement that built it.

> **Check what is commented out, not only what is absent.** A dead line is a
> saved configuration nobody labelled. That corollary came from the SAV session,
> which recovered its entire ten-scenario grid from commented-out lines in a data
> file, and applying it here turned up both this provenance and a second,
> disabled irrigation-cost parameterisation now recorded in `config.yaml`.

The two regimes therefore use the **same four climates**; only the mixture
differs. `test_the_two_sites_draw_from_the_same_climates` asserts that each
climate's mean precipitation agrees between the sites to 2%.

---

## 8. Faithful reproductions of things that look like mistakes

Three, all reproduced deliberately because the published numbers carry them:

- **`sqrt(n − 1)` in the standard error**, not `sqrt(n)`. `FM Traditional *.Rmd`
  divides by `sqrt(nrow(x) - 1)`.
- **Profit over 4,000 runs, crop yield over 100,000 run-years**, so `profit_t` and
  `crop_yield_t` differ within one row of Table 5. Confirmed: 1.96056 is
  `qt(0.975, 3999)` and 1.95999 is `qt(0.975, 99999)`.
- **The expected-value rain path ends at 107 cm**, where the wettest weather state
  is 106.68. `rain_dict1` and `rain_dict2` both round it.
  `test_expected_value_rain_path_is_drawn_from_the_weather_states` asserts that
  107 is the *only* such departure, so a future silent change is caught.

`profit` also carries Gurobi's default lower bound of zero, as in the original. It
is nowhere near binding — the smallest run profit is $769,058 — and
`test_profit_non_negativity_never_binds` asserts it stays that way, because a
binding non-negativity would truncate the loss tail and bias every mean above
without erroring.

---

## 9. Every guard has been watched to fail

A guard that has only ever passed is indistinguishable from one that cannot fail.

| Guard | Defect injected | Result |
|---|---|---|
| `reconstruct_markov.py --check` | one cell of the committed matrix moved by 1e-6 | red, naming `trans_matrix_EP.csv`; green again after restoring |
| `model.py` optimality check | ran the ladder with Gurobi defaults | red on 25 of 40 runs — which is how section 4 was found |
| `markov_chain.Rmd` distribution check | unrounded state values, so the join found no matches | red; fixed by reproducing the original's rounding, then green |
| `data.py::_check_blocks` | — | fires at load; see below |

The third is worth keeping in view. The check fired on the very first render, for
a real defect in the comparison rather than a distributional difference. Had it
been written as `worst < 0.01` without the `is.finite` guard it would have failed
with a message about the tolerance while the actual fault was an `NA` from a
float-equality join.

---

## 10. What a clean clone needs

- **Gurobi.** Academic node-locked licence, expiring 2026-12-04, so this cannot
  run in CI as it stands.

  **How big the models actually are**, measured, because it decides what a free
  licence can run. `pip install gurobipy` ships a size-limited licence capped at
  2,000 variables and 2,000 linear constraints:

  | Model | Variables | Linear | Quadratic | Fits the free licence |
  |---|---:|---:|---:|---|
  | one run — Perfect Information, Expected Value evaluation | 178 | 126 | 25 | **yes** |
  | 11 runs | 1,938 | 1,386 | 275 | **yes**, just |
  | 1,000 runs — one Known Climate block | 176,002 | 126,000 | 25,000 | no |
  | 4,000 runs — Stochastic | 704,002 | 504,000 | 100,000 | no |

  So the per-run scenarios run anywhere, with no licence at all. Only the two
  *joint* models need one, and they need it because they are genuinely large.

  > **The "HiGHS via Pyomo would lift this" line, inherited from the original
  > README, is NOT established and should not be repeated until it is.** HiGHS
  > solves LPs, MIPs and convex quadratic *objectives*. This model's
  > nonlinearity is a quadratic *constraint* —
  > `crop_yield <= a0 + a1*w + a2*w^2` — which is a different capability, and
  > nobody here has checked that HiGHS has it.

  Two routes that do work on the mathematics, neither tried yet:

  - **A conic solver** (Clarabel, ECOS or SCS through cvxpy — all pip-installable,
    no licence). The curve is concave, `a2 < 0`, so the constraint is a rotated
    second-order cone.
  - **A piecewise-linear outer approximation**, which is the boring option and
    probably the right one. Because the curve is concave and enters a
    maximisation as an upper bound, a set of tangent lines is a valid relaxation
    that tightens monotonically with the number of pieces — and the result is a
    plain LP that any solver handles. The cost is a documented approximation
    error to add to the tolerances in section 1.
- **R with `rmarkdown`, `ggplot2`, `dplyr`, `tidyr`, `readr`** for stage 2's
  reports. The `markovchain` and `diagram` dependencies are gone. Without R the
  `rstage` tests skip with a reason; they never report success.
- The committed precipitation inputs. Everything else is regenerated.

---

## 11. The joint models are large by accident, not by necessity

**Not yet implemented. Measured on 2026-09-07 and recorded so it is not lost.**

The 704,002-variable stochastic model exists because the original wrote out every
run and every year explicitly. It does not need to.

Given the first-stage capacities, nothing couples one `(run, year)` to another:
every constraint is either a capacity bound on `(r, y)` or a balance within it.
And precipitation takes **five distinct values**. So the 100,000 second-stage
blocks are 100,000 copies of five distinct problems, and the model collapses to
those five carrying integer weights.

The only thing that could break the equivalence is the `profit[r] >= 0` bound,
which couples the years within a run. It is nowhere near binding — the smallest
run profit is $769,058 — and `test_profit_non_negativity_never_binds` already
asserts that.

Measured against the full solve:

| Site | | Collapsed (37 vars) | Full (704,002 vars) | Published |
|---|---|---:|---:|---:|
| EP | objective | 2,246,937.9654 | 2,246,937.8797 | 2,246,937.9615 |
| EP | water cap | 5.445671 | 5.445671 | — |
| EP | elc cap | 94.4104 | 94.4165 | — |
| DML | objective | 1,899,221.2705 | 1,899,221.1807 | 1,899,221.2314 |
| DML | water cap | 10.958137 | 10.957609 | — |
| DML | elc cap | 206.8482 | 206.8392 | — |

**0.01 seconds against 40, agreeing to $0.09** — inside the noise established in
section 1. The collapsed value is the *higher* of the two and lands closer to the
published figure at both sites, which is what a well-conditioned 37-variable
problem should do against a 704,002-variable barrier solve.

Two consequences:

- **The whole pipeline would fit the free `pip install gurobipy` licence.** The
  per-run scenarios already do (178 variables). Collapsing the two joint models
  brings them to 37. Nothing would need a licence file, which is what a Colab
  badge requires and what invariant 6 has been exempted from.
- **Table 5 still needs the per-run solves**, because its standard deviations are
  taken over runs. Those are 178 variables each and run anywhere; they are just
  4,000 of them.

If this is built, it is a second implementation of the same model and Part 4
applies: one assertion comparing the collapsed and full solves, at a tolerance
this table already measures.

---

## 12. Gurobi reports OPTIMAL on points outside its own tolerance

**Found by the artifact verifier, minutes after it first existed**, and it
reversed a conclusion this document previously stated.

`scripts/verify_solution.py` checks a shipped solution against the constraints
with no solver. The first artifact exported, `EP_expected_value`, came back
**INFEASIBLE**: the water balance was violated by 2.06e-03. Gurobi had returned
that point with **status 2, OPTIMAL** — and its own `MaxVio` agreed with the
verifier at 2.063e-03, two thousand times the `FeasibilityTol` of 1e-06 it
promises.

Three defects came out of chasing it, all in this repository rather than in the
published run.

### 12.1 Status is not feasibility

`model._optimize` checked `m.Status == OPTIMAL` and nothing else. That is the
original code's mistake — not reading the status at all — moved one level in.

### 12.2 The ladder's parameters accumulated

`m.reset()` clears the solution, not the settings. So rung 3 ran with rung 1's
`BarHomogeneous` still set, and two rungs reported identical results because they
were the same solve. `m.resetParams()` now runs before each rung, and the ladder
tests what it names.

### 12.3 The residual was ours, not theirs

Section 4 attributed the +$0.69 residual on the Perfect Information rows to the
published run's uncertified solutions. **That was wrong.** Measured over 120 runs
at Equally Probable, the yield-curve overshoot converted to dollars:

| Solver rung | Certified | Overshoot, $ per run |
|---|---:|---:|
| Gurobi defaults | 39 / 120 | **+0.009** (max +0.42) |
| `BarHomogeneous 1, NumericFocus 3` | 120 / 120 | **+1.030** (max +1.39, never below 0) |

The rung this repository had chosen inflated every run by about a dollar, always
upward, which is the size and sign of the residual it was being used to explain.
The published run, on defaults, carries almost none of it.

### The fix, and what it does not fix

**Gating on `MaxVio` was tried and is wrong.** An absolute tolerance is the wrong
instrument for a model whose quantities run from 0.08 to 2,000,000: at 1e-06 it
rejected 87 of 91 solves whose *relative* violation was around 4e-10.

`model._repair` clips instead — `water` to what is available, then `crop_yield`
to the curve. Both clips only relax the constraints they are not about, so the
result is feasible by construction and the reported value is a valid lower bound.
Across the full run the clip removes **$11,846 over 8,016 solves, about $1.48
each**, or 7e-7 of a $2M profit.

What it fixes is the *kind* of claim: every number in section 1 is now achievable
in the model rather than a point just outside it. What it does not fix is the
*magnitude* of the residual, which is about the same and has changed sign. Saying
otherwise would be claiming an accuracy improvement that was not measured.

### The ladder is reordered as a result

Gurobi's defaults now come first, because where they converge they are the most
accurate rung. They converge on about a third of single-run solves, so **68% of
solves fall through to a fallback** — designed behaviour, not a symptom, and the
test that used to police a 10% fallback rate was rewritten rather than retuned.
The last rung stays unused, which is the headroom
`test_the_solver_ladder_never_runs_out_of_rungs` protects.

---

## 13. What came from the SAV session, and what went the other way

Compared notes with the session reproducing Jones and Leibowicz (2019), which hit
the same shape of problem — a published configuration that was never saved.

**Taken from them:**

- **"Check what is commented out, not only what is absent."** They recovered
  their entire ten-scenario grid from commented-out lines in a data file.
  Applying it here found the `write.csv` line that produced the shipped
  precipitation input (section 7) and a second, disabled irrigation-cost
  parameterisation now recorded in `config.yaml`.
- **The ship-the-artifact pattern breaks at about 2M nonzeros**, where an MPS
  passes GitHub's 100 MB limit at roughly 50 bytes per nonzero. Their model is
  43.6M nonzeros and 34× over; the artifacts here are 164 KB across twelve
  models. Worth knowing before starting rather than after.
- **The free `pip install gurobipy` licence caps at 2,000 variables** — their
  measurement (1,500 accepted, 2,500 refused), not ours. It could not be measured
  on this machine: a full academic licence is installed and forcing the fallback
  makes Gurobi error rather than degrade. Recorded as their finding.

**Sent to them:** that widening a tolerance until the solver reports OPTIMAL buys
the status rather than the convergence, and that a stalling barrier's error is
signed rather than scattered.

**Not adopted from `lithium-optsc-energies-2024`:** its "this repository is
frozen" line, which Part 0 of the standard argues against for paper repos — the
version DOI is already the frozen artifact, and freezing the branch costs errata
and the contributor credit a pull request carries.


---

## 14. The walkthrough notebook, and the badge that is deliberately absent

`notebooks/00_walkthrough.ipynb` is thin, in the Part 4 sense: it imports the
package and calls it, and `tests/test_artifacts.py::test_the_walkthrough_is_thin`
fails if it ever grows an `addQConstr` or a `setObjective`. It is generated by
`scripts/build_walkthrough.py` and shipped executed, and `--check` compares the
source cells -- not the outputs, which legitimately differ between machines.

**It needs no licence for the part that matters.** Section 2 runs the verifier,
which is numpy and arithmetic. Sections 3 and 4 solve the collapsed models, 37
variables against the 2,000 the free `pip install gurobipy` licence allows. Only
the full 704,002-variable formulation needs a real licence, and it is optional.

Perfect Information is behind `QUICK = True`, on by default, and the notebook
prints what that skipped and why: it is 4,000 separate 178-variable solves,
about two minutes, and it fits the free licence too.

**There is no Open-in-Colab badge, on purpose.** This repository is private, so a
badge would render as a 404 for every reader while looking correct to anyone with
access -- the failure `lithium-optsc-energies-2024` recorded in its own history as
"the Colab button could never have run".
`test_no_badge_points_at_a_private_repository` is what stops one going in early,
and it carries an instruction to delete itself in the same commit that makes the
repository public.

### Two defects the artifact tests caught immediately

- **`export_artifacts.py --check` deleted the files it was checking.** Gurobi can
  only write an LP to a path, so the export wrote into `artifacts/`, read the
  text back and unlinked it -- which was harmless while writing and destructive
  while checking. It now writes to a real temporary directory.
- **The dependency guard fired on `nbformat` and `nbclient`**, imported by the
  new builder and declared nowhere. That is exactly the defect it exists to
  catch, and it caught it on the first run after the file appeared.


---

## 15. Bounds are not equations, and a port checks them separately

From the SAV session, which hit this directly. Their gurobipy port came out
**1.6977 low against GAMS** — relative 2.3e-5, too small to see and far too large
to be arithmetic — *after* they had diffed all 107 GAMS equations against the
port and confirmed every one had a counterpart.

That check could not have found it. The cause was one line among the variable
declarations, 130 lines from anything resembling a constraint:

```gams
ProductionByTechnology.fx(y, LowV2G, "EV_CHARGE", f, r) = 0;
```

**A bound is not an equation.** An equation-by-equation port misses bounds by
construction, and the resulting error is small enough to be mistaken for
tolerance.

### Applied here

Every `addVar`/`addVars` call in the four sources that built the published
scenarios was extracted rather than recalled:

    every variable        lb = 0
    irrigation_water      ub = max_irrigation_water   <- the ONLY non-default ub
    profit                lb = 0, by Gurobi's default, never written explicitly
    nowhere               any post-hoc .LB / .UB / setAttr assignment

The port carries all of them, and `tests/test_bounds_match_the_original.py` now
asserts it — including by reading the Bounds section out of the twelve shipped
`.lp` files, which is the frozen record rather than the source. The post-hoc
probe is shown capable of firing before its clean result is believed.

### Two things the check found about itself

- **Globbing `superseded/` swept in abandoned variants of a different model.**
  `Farm Model Original.ipynb` and `FarmModelStoch.ipynb` declare integer
  `pick_c*` variables the canonical model has none of, and the suite reported
  them as an upper bound the published model does not have. That was the scan's
  scope, not a finding, and the canonical sources are now named explicitly.
  A second test asserts no shipped model has a `Generals` or `Binaries` section,
  since an integer variable would end the convexity every optimality claim rests on.
- **`v.UB != GRB.INFINITY` is the wrong comparison.** Gurobi returns
  `float('inf')`; `GRB.INFINITY` is `1e100`. The two are unequal, so every
  variable looked bounded and the test "found" nine violations that did not exist.

### The sign of a discrepancy narrows the search

Also from them, and worth keeping: on a **minimisation**, reproducing *below* the
reference means under-constrained — a missing restriction, which is what a
missing bound is. A wrong coefficient could go either way.

This model is a **maximisation**, and every scenario reproduces at or slightly
below. That would point at an extra restriction, except that the
published-first-stage diagnostic reproduces VSS to within $0.50: an extra binding
constraint would drag that down too, and it does not. The sign is explained by
the feasibility repair, which clips to a feasible point and therefore reports a
lower bound by design. `test_the_discrepancy_has_the_sign_a_conservative_solve_should`
records that reasoning where it will be re-read.

### One more, for anyone reading solver output

**Read objectives from the solver, never from a rounded results file.** Their
results writer printed two decimals, and several apparent mismatches turned out
to be exactly 0.005 — half of the last printed digit. `reference/solnvalues.csv`
here carries fifteen significant figures, so this repository is not exposed, but
the failure mode is worth naming: a rounded file can both hide a real
disagreement and manufacture a fake one.


---

## 16. Adopting Archetype P

The code standard's amendment 6 merged on 2026-09-08 and this repository was
restructured onto it. The rule:

> Everything that produced the published result is preserved verbatim. Exactly
> one implementation is maintained, and it is Python.

**It applies on both sides of the pipeline**, and that is the half this
repository had missed. The model was already Python; the analysis was 674 lines
of R. Porting one and not the other does not reduce the languages a reader needs
-- it moves the barrier from the model to the figures.

    farm_report.Rmd   312 lines  ->  src/fews_stochopt/analysis.py + scripts/make_figures.py
    markov_chain.Rmd  276 lines  ->  fews_stochopt.markov.simulate
    render_reports.R   86 lines  ->  no longer needed

The R is in `archive/`, verbatim, frozen by `scripts/freeze_archive.py --check`
over a sha256 manifest of raw bytes.

### What the port had to reproduce, and how it was checked

`markov_chain.Rmd` generates the precipitation scenarios, so it is stages 1-3
rather than stage 8, and its acceptance test is distributional rather than visual.
The original's exact draws cannot be recovered -- `set.seed(12345)` was set but
the sample depended on RNG state accumulated through earlier chunks. So the port
is checked against the committed input by state share: **largest difference
0.0014**, against the 0.01 the R version itself asserted.

Two details had to be reproduced rather than improved:

- **The two-decimal round-trip.** The R converted states to numbers through
  `gsub('w2', as.character(w2p), ...)`, and `as.character` prints the shortest
  form within 15 significant digits -- so the committed files hold exactly 26.67
  while the unrounded product is 26.669999999999998. Without the round-trip a
  comparison by value finds no matches at all.
- **The concatenate-then-renumber layout**, which is what makes a run's index
  encode its climate.

### Two defects the move surfaced

- **`core.autocrlf=true` breaks a raw-bytes freeze.** Restoring one archived file
  with `git checkout` rewrote its line endings, the manifest rejected it, and the
  same would have happened on every clean clone. `.gitattributes` now marks
  `archive/** -text`, because "verbatim" has to mean bytes.
- **`resetParams()` restores Gurobi's defaults, not the environment's**, so the
  `OutputFlag=0` from `config.yaml` was lost and every solve printed its barrier
  log. Cosmetic -- `Seed` and `Threads` were already at their defaults -- but it
  had flooded a full run's output.

### The 10 MB boundary, met by committing a different layer

Archetype P commits cleaned output and notes that this "assumes it stays small...
around 10 MB". The tidy per-run detail here is **135 MB**. The resolution is not
to compress or subset: the per-run detail is *raw* output, and what everything
actually reads is the per-(site, scenario, year) aggregate, which is **90 KB**.
Committing the right layer keeps the repository working from a clean clone
without straining the boundary. Reported back to the standard as a case its
"compress or subset" escape does not cover.

### One deviation, recorded

Archetype P says to read the primal residual and **scale it by the largest
constraint-matrix coefficient**. This repository records that figure per solve --
`scaled_violation_before_repair` in each scenario's `.meta.json` -- but does not
gate on it. `model._repair` clips the point back inside the feasible region
instead, which removes the violation rather than accepting a small one, and the
reported values are then valid lower bounds.

Gating on a threshold was tried and rejected: at 1e-8 scaled by the objective it
would have permitted about $1,300 of error on quantities asserted to $2. That was
raised in review before the amendment merged; the evidence cited for the scaling
(87 of 91 solves wrongly rejected by an absolute gate) supports "an absolute gate
is wrong" and does not extend to the remedy. Worth re-petitioning if it recurs.
