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

| Site | Scenario | Published mean profit | Reproduced | Difference | Relative |
|---|---|---:|---:|---:|---:|
| Equally Probable | Perfect Information | 2,355,663.1032 | 2,355,663.7950 | +0.6918 | 2.9e-07 |
| Equally Probable | Known Climate | 2,345,266.7851 | 2,345,267.1180 | +0.3329 | 1.4e-07 |
| Equally Probable | Stochastic | 2,246,937.9615 | 2,246,937.8797 | −0.0818 | 3.6e-08 |
| Equally Probable | Expected Value | 2,246,937.4728 | 2,246,937.5072 | +0.0344 | 1.5e-08 |
| Dry Most Likely | Perfect Information | 1,975,827.2395 | 1,975,827.9917 | +0.7523 | 3.8e-07 |
| Dry Most Likely | Known Climate | 1,964,087.2089 | 1,964,087.6475 | +0.4386 | 2.2e-07 |
| Dry Most Likely | Stochastic | 1,899,221.2314 | 1,899,221.1807 | −0.0506 | 2.7e-08 |
| **Dry Most Likely** | **Expected Value** | **1,898,280.3314** | **1,898,259.9822** | **−20.3492** | **1.1e-05** |

**Seven of eight within $0.76.** The eighth is section 3.

And the value-of-information table, against `reference/solnvalues.csv`:

| Site | Quantity | Published | Reproduced | Difference |
|---|---|---:|---:|---:|
| Equally Probable | EVKW | 10,396.3181 | 10,396.6769 | +0.3588 |
| Equally Probable | EVPI | 108,725.1417 | 108,725.9153 | +0.7736 |
| Equally Probable | EVKC | 98,328.8236 † | 98,329.2383 | +0.4147 |
| Equally Probable | VSS | 0.4887 | 0.3725 | −0.1162 |
| Dry Most Likely | EVKW | 11,740.0306 | 11,740.3443 | +0.3137 |
| Dry Most Likely | EVPI | 76,606.0081 | 76,606.8110 | +0.8029 |
| Dry Most Likely | EVKC | 64,865.9775 † | 64,866.4667 | +0.4892 |
| Dry Most Likely | VSS | 940.8999 | 961.1985 | +20.2986 |

† EVKC was never in the pipeline output. These are derived from Table 5 as
`KnownClimate − Stochastic`; see section 2.

**So `scenario_mean_abs_dollars` is 2.0** against a worst observed 0.75, and
**`value_of_information_abs_dollars` is 2.0** against a worst observed 0.80. Both
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

| Site | Published EV mean | At published first stage | Difference |
|---|---:|---:|---:|
| Equally Probable | 2,246,937.4728 | 2,246,937.5220 | +0.0492 |
| Dry Most Likely | 1,898,280.3314 | 1,898,280.6947 | +0.3633 |

**Both within half a dollar.** The second stage is correct; the entire discrepancy
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
Measured over 40 sampled runs at Equally Probable: **27 of 40 uncertified.** The
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

Tightening tolerances instead does **not** work and is worth recording so nobody
tries it again: `BarQCPConvTol 1e-9`, `1e-12` and `BarConvTol 1e-12` all certify
*fewer* solves, not more, and the full-run mean moved further from the published
value (2,355,663.26 against 2,355,663.17 at defaults, published 2,355,663.10).
The residual is not convergence tolerance; it is where the interior-point method
stops.

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

Confirmed against `run_c1 = list(range(2400))` and its siblings in
`FM MI DML All Climates.Rmd`, and checked at runtime by
`data.py::_check_blocks`, which refuses to load a file whose block sizes and
declared probabilities disagree.

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
| `model.py` optimality check | ran the ladder with Gurobi defaults | red on 27 of 40 runs — which is how section 4 was found |
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
  run in CI as it stands. Each per-scenario solve is small — under 200 variables
  and 25 quadratic constraints — so HiGHS via Pyomo would lift that, at the cost
  of re-verifying every number in section 1 against a second solver.
- **R with `rmarkdown`, `ggplot2`, `dplyr`, `tidyr`, `readr`** for stage 2's
  reports. The `markovchain` and `diagram` dependencies are gone. Without R the
  `rstage` tests skip with a reason; they never report success.
- The committed precipitation inputs. Everything else is regenerated.
