"""The FEWS farm model behind Jones (2022), Environment Systems and Decisions.

A farm chooses alternative water and electricity capacity under uncertain
precipitation, then operates for 25 years. Four scenarios differ only in *what
the farm knows when it invests*, and the differences between their expected
profits are the value-of-information quantities the paper reports.

**Importing this package does not import a solver.** That is load-bearing, not
tidiness: `notebooks/00_verification.ipynb` claims the published result can be
checked with no solver and no licence, and it derives its paths from this
package. If `import fews_stochopt` pulled in `gurobipy`, that notebook would fail
at import on exactly the machine it exists to serve, and the claim would be false
while every other check stayed green.

It was false. `__init__` used to import `model` eagerly, and the test guarding the
claim only searched the notebook for the literal string `import gurobipy`, which
a transitive import does not contain. Names are resolved lazily below instead,
and `tests/test_artifacts.py` now blocks `gurobipy` and imports for real.

So: `fews_stochopt.solve_scenario` still works and still needs Gurobi at the
moment it is *used*. `import fews_stochopt`, `load_config` and
`fews_stochopt.__file__` need nothing.
"""
from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

__version__ = "1.0.0"

# name -> module it lives in. Resolved on first attribute access, so a name that
# needs a solver costs nothing until somebody asks for it.
_EXPORTS = {
    "Config": "fews_stochopt.config",
    "load_config": "fews_stochopt.config",
    "load_precipitation": "fews_stochopt.data",
    "expected_value_rain": "fews_stochopt.data",
    "ScenarioResult": "fews_stochopt.model",
    "solve_scenario": "fews_stochopt.model",
    "ScenarioStats": "fews_stochopt.aggregate",
    "scenario_stats": "fews_stochopt.aggregate",
    "value_of_information": "fews_stochopt.aggregate",
    "SCENARIOS": "fews_stochopt.aggregate",
}

# Submodules reachable as `fews_stochopt.collapsed` and so on, also lazily.
_SUBMODULES = ("config", "data", "model", "aggregate", "analysis", "collapsed", "markov")

__all__ = [*_EXPORTS, *_SUBMODULES, "__version__"]

if TYPE_CHECKING:  # for type checkers and editors only; never executed
    from fews_stochopt.aggregate import (  # noqa: F401
        SCENARIOS,
        ScenarioStats,
        scenario_stats,
        value_of_information,
    )
    from fews_stochopt.config import Config, load_config  # noqa: F401
    from fews_stochopt.data import expected_value_rain, load_precipitation  # noqa: F401
    from fews_stochopt.model import ScenarioResult, solve_scenario  # noqa: F401


def __getattr__(name: str):
    """PEP 562 lazy attribute access."""
    if name in _SUBMODULES:
        return importlib.import_module(f"fews_stochopt.{name}")
    if name in _EXPORTS:
        return getattr(importlib.import_module(_EXPORTS[name]), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(__all__)
