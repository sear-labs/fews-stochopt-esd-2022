"""Domain invariants: the things that must be true of any correct output.

These do not compare against the paper. They assert the theory, so that when one
fails the plumbing is wrong rather than the science -- and so that a table of four
plausible numbers cannot pass unnoticed.

None of them solves a model except the last, which solves one small one.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fews_stochopt.config import load_config  # noqa: E402
from fews_stochopt.data import (  # noqa: E402
    climate_of_run,
    expected_value_rain,
    load_precipitation,
)


@pytest.fixture(scope="module")
def cfg():
    return load_config()


# --------------------------------------------------------------------------
# The yield function
# --------------------------------------------------------------------------

def test_folded_yield_matches_the_expression_as_written(cfg):
    """`config.py` collapses the salinity terms; check the collapse, not the result.

    `config.yaml` carries the yield function with every term spelled out, as it
    appears in Dinar et al. (1991) and in the notebooks. The model needs it as a
    quadratic in water depth alone. Those are two forms of one thing, and nothing
    else compares them.
    """
    y = cfg.raw["yield_function"]
    s = y["soil_salinity_ds_per_m"]
    sw = y["water_salinity_ds_per_m"]

    def as_written(w: float) -> float:
        return (
            y["intercept"]
            + y["water"] * w
            + y["water_squared"] * w * w
            + y["water_salinity"] * sw
            + y["water_salinity_squared"] * sw * sw
            + y["soil_salinity"] * s
            + y["soil_salinity_squared"] * s * s
            + y["water_x_water_salinity"] * w * sw
            + y["water_x_soil_salinity"] * w * s
            + y["water_salinity_x_soil_salinity"] * sw * s
        )

    for w in (0.0, 8.89, 26.67, 53.34, 73.0, 80.01, 106.68, 120.0):
        assert cfg.yield_coeffs(w) == pytest.approx(as_written(w), rel=1e-12), (
            f"folded and written-out yield disagree at water depth {w}"
        )


def test_yield_function_is_concave_and_peaks_in_range(cfg):
    """The curve must be concave, or the QCP feasible region is not convex.

    It must also peak inside the range of water depths the farm can reach --
    otherwise the capacity decision has no interior optimum and every scenario
    would invest at a bound.
    """
    a = cfg.yield_coeffs
    assert a.a2 < 0, "the water-squared coefficient is not negative; yield is not concave"
    peak = -a.a1 / (2 * a.a2)
    assert 0 < peak < 200, f"yield peaks at {peak} cm, outside any reachable depth"
    assert a(peak) > 0, "peak yield is not positive"


# --------------------------------------------------------------------------
# The inputs
# --------------------------------------------------------------------------

@pytest.mark.parametrize("site", ["EP", "DML"])
def test_precipitation_file_validates(cfg, site):
    """`load_precipitation` refuses a file of the wrong shape; check it accepts a right one."""
    df = load_precipitation(cfg, site)
    assert len(df) == cfg.runs * cfg.years
    assert df["precip"].min() > 0


@pytest.mark.parametrize("site", ["EP", "DML"])
def test_climate_blocks_encode_the_climate_probabilities(cfg, site):
    """Block sizes ARE the probabilities; nothing else records them.

    `FM {EP,DML} MC.Rmd` builds the c0 sample as
    `c(precips_c1, precips_c2, precips_c3, precips_c4)` with each climate drawn
    `iters * 4 * probability` times, then renumbers the runs 1..4000. So the DML
    regime differs from EP not in its transition matrix but in how many runs each
    climate contributes.
    """
    s = cfg.site(site)
    mapping = climate_of_run(s)
    assert len(mapping) == cfg.runs
    for k, p in enumerate(s.climate_probabilities, start=1):
        share = sum(1 for c in mapping.values() if c == k) / cfg.runs
        assert share == pytest.approx(p, abs=1e-9)


def test_the_two_sites_draw_from_the_same_climates(cfg):
    """EP and DML differ in composition, not in what a climate is.

    Each climate's mean precipitation should agree between the sites -- they are
    two independent samples of the same four chains. This is what makes the DML
    regime "dry most likely" rather than "drier climates".
    """
    means = {}
    for site in ("EP", "DML"):
        df = load_precipitation(cfg, site)
        mapping = climate_of_run(cfg.site(site))
        df = df.assign(climate=df["run"].map(mapping))
        means[site] = df.groupby("climate")["precip"].mean()

    for k in means["EP"].index:
        ep, dml = means["EP"][k], means["DML"][k]
        assert ep == pytest.approx(dml, rel=0.02), (
            f"climate {k} averages {ep:.2f} cm at EP and {dml:.2f} cm at DML; "
            f"the two sites should be sampling the same chain"
        )

    # And the composition genuinely differs, or the sites are the same instance.
    overall = {s: load_precipitation(cfg, s)["precip"].mean() for s in ("EP", "DML")}
    assert overall["DML"] < overall["EP"] - 5, (
        f"DML should be materially drier overall: {overall}"
    )


@pytest.mark.parametrize("site", ["EP", "DML"])
def test_expected_value_rain_path_is_drawn_from_the_weather_states(cfg, site):
    """Every entry of the deterministic path is a weather state -- bar one, knowingly.

    `rain_dict1` and `rain_dict2` end in 107, where the wettest state is 106.68.
    That rounding is in the published run and is reproduced rather than corrected,
    so it is asserted here as a known deviation: if it is ever silently changed,
    this test says so.
    """
    path = expected_value_rain(cfg, site)
    states = set(cfg.weather_states.values())
    off = sorted({v for v in path.values() if v not in states})
    assert off == [107.0], (
        f"expected_value_rain for {site} departs from the weather states at {off}; "
        f"the only known departure is 107 for 106.68"
    )
    assert len(path) == cfg.years


# --------------------------------------------------------------------------
# The solved output
# --------------------------------------------------------------------------

def _meta_files() -> list[Path]:
    return sorted((ROOT / "results").glob("*/*.meta.json"))


@pytest.mark.pipeline
def test_profit_non_negativity_never_binds():
    """`profit` carries Gurobi's default lower bound of zero, as in the original.

    If it ever bound, it would truncate the loss tail and bias every mean above --
    silently, because a truncated mean is still a plausible number. The published
    run had no such check.
    """
    metas = _meta_files()
    assert metas, "no solved scenarios found; run `python scripts/run_all.py` first"
    for path in metas:
        meta = json.loads(path.read_text(encoding="utf-8"))
        floor = meta["slack"]["min_profit"]
        assert floor > 1000.0, (
            f"{meta['site']}/{meta['scenario']}: the smallest run profit is "
            f"{floor}, close enough to the zero lower bound that it may be binding"
        )


@pytest.mark.pipeline
def test_every_solve_was_certified_optimal():
    """The ladder records which rung certified; none may have run out of rungs.

    `model.py` raises rather than returning an uncertified solution, so reaching
    this test at all means every solve was OPTIMAL. What is checked here is that
    the fallback rungs are used rarely -- if the first rung stopped working the
    run would still succeed, much more slowly, and nothing else would notice.
    """
    metas = _meta_files()
    assert metas, "no solved scenarios found; run `python scripts/run_all.py` first"
    total = fallback = 0
    for path in metas:
        meta = json.loads(path.read_text(encoding="utf-8"))
        total += int(meta["slack"]["solves"])
        fallback += int(meta["slack"]["fallback_solves"])
    assert total > 0, "no solves recorded at all"
    share = fallback / total
    assert share < 0.10, (
        f"{fallback} of {total} solves ({share:.1%}) needed a fallback rung of "
        f"solver.parameter_ladder; the first rung has stopped being the normal path"
    )


@pytest.mark.pipeline
def test_information_is_never_worth_less_than_none():
    """Expected profit must not fall as the farm is told more.

    Perfect Information >= Known Climate >= Stochastic. This is the ordering the
    whole paper is about, and it is the check that fails first if two scenarios
    are swapped.
    """
    import csv

    path = ROOT / "results" / "simstatstrad.csv"
    assert path.exists(), "run `python scripts/run_all.py` first"
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    assert rows, "results/simstatstrad.csv parsed to zero rows"

    by_site: dict[str, dict[str, float]] = {}
    for r in rows:
        by_site.setdefault(r["Climate_Probability"], {})[r["sim"]] = float(r["profit_mean"])

    assert len(by_site) >= 2, f"only {len(by_site)} regime(s) in the results"
    for regime, means in by_site.items():
        pi = means["Perfect Information"]
        kc = means["Known Climate, Unknown Weather"]
        st = means["Stochastic"]
        ev = means["Expected Value"]
        assert pi >= kc >= st, f"{regime}: information ordering violated ({pi}, {kc}, {st})"
        assert st >= ev - 1e-6, (
            f"{regime}: the stochastic solution is worse than the expected-value "
            f"one ({st} < {ev}), which cannot happen -- the stochastic first stage "
            f"is feasible for the expected-value problem"
        )


def _per_climate_pi_profit(cfg, site):
    import pandas as pd

    path = ROOT / "results" / site / "perfect_information_profit.csv"
    if not path.exists():
        pytest.skip(f"{path} not present; run `python scripts/run_all.py` first")
    profit = pd.read_csv(path)
    mapping = climate_of_run(cfg.site(site))
    return profit.assign(climate=profit["run"].map(mapping)).groupby("climate")[
        "profit"
    ].mean()


@pytest.mark.pipeline
def test_the_same_climate_earns_the_same_at_both_sites(cfg):
    """A climate is a climate, whichever site's sample it appears in.

    The two sites draw from the same four chains and differ only in how many runs
    each contributes. So mean profit under perfect information, taken within a
    climate, must agree between them -- these are two independent samples of one
    quantity. Measured: within 0.6%, on sample sizes from 200 to 2,400.

    This is the check that catches a mis-sliced climate block, which would
    otherwise change the headline table by a plausible-looking amount and nothing
    would say so.
    """
    means = {site: _per_climate_pi_profit(cfg, site) for site in cfg.sites}
    assert set(means) == {"EP", "DML"}
    for k in means["EP"].index:
        ep, dml = means["EP"][k], means["DML"][k]
        assert ep == pytest.approx(dml, rel=0.02), (
            f"climate {k} earns {ep:,.0f} at EP and {dml:,.0f} at DML under "
            f"perfect information; the same climate should earn the same"
        )


@pytest.mark.pipeline
def test_profit_is_not_monotone_in_rainfall(cfg):
    """More rain is not always better, and the model must show that.

    The yield curve peaks near 72 cm and declines beyond it, and the farm can add
    water but cannot shed it. So a climate with more rain on average can earn
    less if that rain is spread wider: climate 3 averages 55 cm against climate
    2's 50 cm and earns about 16% less, because a uniform climate puts a fifth of
    its years at 107 cm, past the peak, and another fifth at 9 cm.

    This is asserted rather than described because it is counter-intuitive enough
    that someone will one day "fix" it, and because it holds at both sites --
    which is itself evidence the climate blocks are sliced correctly.
    """
    for site in cfg.sites:
        means = _per_climate_pi_profit(cfg, site)
        assert len(means) == 4, f"{site}: expected 4 climates, found {len(means)}"
        assert means[3] < means[2], (
            f"{site}: climate 3 ({means[3]:,.0f}) is expected to earn less than "
            f"climate 2 ({means[2]:,.0f}) despite more rain, because the yield "
            f"curve declines past its peak. If this has changed, the yield "
            f"function or the climate slicing changed with it."
        )
        assert means[4] > means[2] > means[1], (
            f"{site}: the rest of the ordering is monotone and is not: {means.to_dict()}"
        )


@pytest.mark.pipeline
def test_the_yield_peak_lies_inside_the_observed_rainfall_range(cfg):
    """The non-monotonicity above has a cause; check the cause, not only the effect."""
    a = cfg.yield_coeffs
    peak = -a.a1 / (2 * a.a2)
    wettest = max(cfg.weather_states.values())
    driest = min(cfg.weather_states.values())
    assert driest < peak < wettest, (
        f"the yield curve peaks at {peak:.2f} cm, outside the observed range "
        f"{driest}-{wettest} cm. If it did not, more rain would always be better "
        f"and test_profit_is_not_monotone_in_rainfall would be asserting nothing."
    )
