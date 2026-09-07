"""The collapsed model and the full one must agree. This is that assertion.

`src/fews_stochopt/collapsed.py` is a second implementation of the same model,
written at 37 variables instead of 704,002. Deliberate duplication is a design;
deliberate duplication with nothing comparing the copies is how a fix gets
applied in three places out of four. So this file solves both and compares them.

The tolerances are the ones already measured in `config.yaml`, not new ones:

- **Stochastic and Known Climate** get `scenario_mean_abs_dollars`. Their optima
  are well determined and the two implementations land within $0.09.
- **Expected Value** gets `expected_value_first_stage_sensitivity_dollars`,
  because its first stage is the flat one documented in
  `docs/reproduction-notes.md` §3. Two implementations of a flat optimum land in
  different places on the ridge for the same reason two solvers do, and the
  amplification into realised profit is the same effect measured there.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fews_stochopt import collapsed  # noqa: E402
from fews_stochopt.config import load_config  # noqa: E402
from fews_stochopt.model import (  # noqa: E402
    EXPECTED_VALUE,
    KNOWN_CLIMATE,
    PERFECT_INFORMATION,
    STOCHASTIC,
)

SLUG = {
    STOCHASTIC: "stochastic",
    KNOWN_CLIMATE: "known_climate_unknown_weather",
    EXPECTED_VALUE: "expected_value",
}


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def _full_mean(site: str, scenario: str) -> float:
    path = ROOT / "results" / site / f"{SLUG[scenario]}_profit.csv"
    return float(pd.read_csv(path)["profit"].mean())


@pytest.mark.pipeline
@pytest.mark.parametrize("site", ["EP", "DML"])
@pytest.mark.parametrize("scenario", list(SLUG))
def test_collapsed_reproduces_the_full_model(cfg, site, scenario, pipeline_run):
    tol = cfg.tolerances[
        "expected_value_first_stage_sensitivity_dollars"
        if scenario == EXPECTED_VALUE
        else "scenario_mean_abs_dollars"
    ]
    got = collapsed.solve(cfg, site, scenario)["objective"]
    want = _full_mean(site, scenario)
    assert got == pytest.approx(want, abs=tol), (
        f"{site}/{scenario}: collapsed {got:,.4f} against full {want:,.4f}, "
        f"difference {got - want:+.4f} beyond ${tol}"
    )


@pytest.mark.pipeline
@pytest.mark.parametrize("site", ["EP", "DML"])
def test_collapsed_first_stage_matches(cfg, site, pipeline_run):
    """The capacities, not only the objective.

    A model can reach the right objective from the wrong decision when the
    objective is flat -- which this one is. Comparing the decision as well is
    what makes the agreement mean something.
    """
    inv = pd.read_csv(ROOT / "results" / site / "stochastic_investment.csv").iloc[0]
    got = collapsed.solve(cfg, site, STOCHASTIC)
    assert got["alt_water_cap"] == pytest.approx(inv["alt_water_cap"], abs=1e-2)
    assert got["alt_elc_cap"] == pytest.approx(inv["alt_elc_cap"], abs=1e-1)


def test_collapsed_model_is_small_enough_for_the_free_licence(cfg):
    """37 variables, which is the whole point.

    `pip install gurobipy` ships a licence capped at 2,000 variables and 2,000
    linear constraints. If the collapsed model ever grew past that, the notebook
    and the Colab badge would stop working for every reader without a licence,
    and nothing else would say so.
    """
    import gurobipy as gp

    from fews_stochopt.model import _env

    env = _env(cfg)
    weights, n = collapsed.rain_weights(cfg, "EP")
    m = collapsed.build(cfg, weights, n, env)
    assert m.NumVars <= 2000, f"collapsed model has {m.NumVars} variables"
    assert m.NumConstrs <= 2000, f"collapsed model has {m.NumConstrs} constraints"
    # And it must not have collapsed to nothing, which would also be "small".
    assert m.NumQConstrs == len(weights) >= 2, (
        f"expected one yield constraint per distinct precipitation value, "
        f"got {m.NumQConstrs} for {len(weights)} value(s)"
    )
    del env


def test_perfect_information_is_refused(cfg):
    """Collapsing is not always valid, and the module must say so rather than try.

    Under perfect information every run chooses its own capacities, so the runs
    share nothing to aggregate over. A silent wrong answer here would be a
    plausible number.
    """
    with pytest.raises(ValueError, match="cannot be collapsed"):
        collapsed.solve(cfg, "EP", PERFECT_INFORMATION)
