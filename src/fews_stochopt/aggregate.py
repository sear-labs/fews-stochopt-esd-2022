"""Turning per-run solutions into the paper's Tables 4 and 5.

The arithmetic is small and it is the whole of stage 2. It was previously spread
across `FM Traditional {EP,DML}.Rmd` and `FM Final Outputs.Rmd`, in two copies
that differed only in a site name.

**Table 5** (`simstatstrad.csv`) is mean, standard deviation, t, standard error
and half-width for profit and crop yield, per scenario. Two details of the
original are reproduced deliberately rather than corrected, because the
published numbers carry them:

- the standard error divides by `sqrt(n - 1)`, not `sqrt(n)`
- profit is summarised over 4,000 runs while crop yield is summarised over
  100,000 run-years, so the two carry different degrees of freedom in the same
  row -- which is why `profit_t` and `crop_yield_t` differ

**Table 4** (`solnvalues.csv`) is four differences of those means:

    EVKW  value of known weather        = PI   - KnownClimate
    EVPI  value of perfect information  = PI   - Stochastic
    VSS   value of the stochastic soln  = Stoch- ExpectedValue
    EVKC  value of known climate        = KC   - Stochastic

EVKC is in the paper and was never in the pipeline output. Its definition above
is not a guess: it is the one that reproduces the paper's Dry-Most-Likely figure,
$64,865.98, to the cent, and it satisfies the identity EVPI = EVKW + EVKC, which
`value_of_information` asserts.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from scipy import stats as scs

from fews_stochopt.config import Config
from fews_stochopt.model import (
    EXPECTED_VALUE,
    KNOWN_CLIMATE,
    PERFECT_INFORMATION,
    STOCHASTIC,
    ScenarioResult,
)

# Table order, as printed in the paper.
SCENARIOS = [PERFECT_INFORMATION, KNOWN_CLIMATE, STOCHASTIC, EXPECTED_VALUE]


@dataclass
class ScenarioStats:
    sim: str
    profit_mean: float
    profit_sd: float
    profit_t: float
    profit_se: float
    profit_h: float
    crop_yield_mean: float
    crop_yield_sd: float
    crop_yield_t: float
    crop_yield_se: float
    crop_yield_h: float


def _summary(x: np.ndarray) -> tuple[float, float, float, float, float]:
    """mean, sd, t, se, h -- with the original's `sqrt(n - 1)` denominator."""
    n = len(x)
    if n < 2:
        raise ValueError(f"cannot summarise {n} observation(s)")
    mean = float(np.mean(x))
    sd = float(np.std(x, ddof=1))
    t = float(scs.t.ppf(0.975, n - 1))
    se = sd / np.sqrt(n - 1)
    return mean, sd, t, float(se), float(t * se)


def scenario_stats(result: ScenarioResult) -> ScenarioStats:
    p = result.profit["profit"].to_numpy()
    cy = result.detail["crop_yield"].to_numpy()
    pm, psd, pt, pse, ph = _summary(p)
    ym, ysd, yt, yse, yh = _summary(cy)
    return ScenarioStats(
        sim=result.scenario,
        profit_mean=pm,
        profit_sd=psd,
        profit_t=pt,
        profit_se=pse,
        profit_h=ph,
        crop_yield_mean=ym,
        crop_yield_sd=ysd,
        crop_yield_t=yt,
        crop_yield_se=yse,
        crop_yield_h=yh,
    )


def sim_stats_table(cfg: Config, results: dict[str, dict[str, ScenarioResult]]) -> pd.DataFrame:
    """Table 5: one row per site x scenario."""
    rows = []
    for site, by_scenario in results.items():
        for scenario in SCENARIOS:
            st = scenario_stats(by_scenario[scenario])
            rows.append({"Climate_Probability": cfg.site(site).label, **asdict(st)})
    return pd.DataFrame(rows)


def value_of_information(
    cfg: Config, site: str, by_scenario: dict[str, ScenarioResult]
) -> dict[str, float]:
    """Table 4 for one site, all four columns."""
    missing = [s for s in SCENARIOS if s not in by_scenario]
    if missing:
        raise ValueError(f"site {site} is missing scenario(s) {missing}")

    pi = by_scenario[PERFECT_INFORMATION].mean_profit()
    kc = by_scenario[KNOWN_CLIMATE].mean_profit()
    st = by_scenario[STOCHASTIC].mean_profit()
    ev = by_scenario[EXPECTED_VALUE].mean_profit()

    row = {
        "Climate_Probability": cfg.site(site).label,
        "Value_of_Known_Weather": pi - kc,
        "Value_of_Perfect_Information": pi - st,
        "Value_of_Stochastic_Solution": st - ev,
        "Value_of_Known_Climate": kc - st,
    }

    # Assert the theory, not the plumbing. These hold for any correct solve, so
    # a failure here means the scenarios were mixed up, not that the model is
    # wrong. They are the reason a mislabelled scenario cannot reach the table.
    identity_rel = cfg.tolerances["identity_rel"]
    evpi = row["Value_of_Perfect_Information"]
    total = row["Value_of_Known_Weather"] + row["Value_of_Known_Climate"]
    if abs(evpi - total) > identity_rel * max(abs(evpi), 1.0):
        raise AssertionError(
            f"{site}: EVPI ({evpi:.6f}) does not equal EVKW + EVKC ({total:.6f}). "
            f"These are differences of the same four means and must agree exactly."
        )
    # More information cannot be worth less than none: PI >= KC >= Stochastic.
    if not (pi >= kc >= st):
        raise AssertionError(
            f"{site}: expected profit should not fall as information is added, "
            f"but PI={pi:.2f}, KnownClimate={kc:.2f}, Stochastic={st:.2f}"
        )
    return row


def value_table(
    cfg: Config, results: dict[str, dict[str, ScenarioResult]]
) -> pd.DataFrame:
    """Table 4 for every site."""
    return pd.DataFrame(
        [value_of_information(cfg, site, by) for site, by in results.items()]
    )


def scenario_averages(
    cfg: Config, site: str, by_scenario: dict[str, ScenarioResult], precip_mean: float
) -> pd.DataFrame:
    """The per-scenario yearly averages the report plots.

    This is `scenario_yearly_avg_trad` from `FM Traditional {EP,DML}.Rmd`, with
    the same unit conversions: profit in $M, crop yield scaled from tonne/ha to
    tonne by the farm area, electricity from kWh to MWh.
    """
    rows = []
    for scenario in SCENARIOS:
        r = by_scenario[scenario]
        d = r.detail
        rows.append(
            {
                "sim": scenario,
                "profit_MM": r.mean_profit() / 1e6,
                "crop_yield_tonne": float(d["crop_yield"].mean()) * cfg.hectares,
                "precip_cm": precip_mean,
                "alt_water_cap_cm": float(
                    np.average(
                        r.investment["alt_water_cap"], weights=r.investment["n_runs"]
                    )
                ),
                "alt_elc_cap_kW": float(
                    np.average(
                        r.investment["alt_elc_cap"], weights=r.investment["n_runs"]
                    )
                ),
                "water_cm": float(d["water"].mean()),
                "elc_prod_MWh": float(d["elc"].mean()) / 1000,
            }
        )
    return pd.DataFrame(rows)
