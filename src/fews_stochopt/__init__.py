"""The FEWS farm model behind Jones (2022), Environment Systems and Decisions.

A farm chooses alternative water and electricity capacity under uncertain
precipitation, then operates for 25 years. Four scenarios differ only in *what
the farm knows when it invests*, and the differences between their expected
profits are the value-of-information quantities the paper reports.

The public entry point is `scripts/run_all.py`; everything it needs is
importable from here.
"""
from fews_stochopt.aggregate import (
    SCENARIOS,
    ScenarioStats,
    scenario_stats,
    value_of_information,
)
from fews_stochopt.config import Config, load_config
from fews_stochopt.data import expected_value_rain, load_precipitation
from fews_stochopt.model import ScenarioResult, solve_scenario

__all__ = [
    "Config",
    "load_config",
    "load_precipitation",
    "expected_value_rain",
    "ScenarioResult",
    "solve_scenario",
    "ScenarioStats",
    "scenario_stats",
    "value_of_information",
    "SCENARIOS",
]

__version__ = "1.0.0"
