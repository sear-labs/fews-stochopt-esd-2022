"""The scenario names, and nothing else.

**This module exists so that reading results does not require a solver.**

The four names below are the paper's scenarios, and they are keys: they appear in
every cleaned-output table, every figure title and every cache path. They lived
in `model.py`, which imports `gurobipy` at module scope -- so `aggregate.py`
imported them from there, `analysis.py` imported `aggregate`, and
`scripts/make_figures.py` imported `analysis`. The result was that regenerating a
figure from 90 KB of committed CSVs required a commercial licence, and
`fews_stochopt.SCENARIOS` -- a tuple of four strings -- could not be resolved
without one.

Four lines of import, three separate consequences, none of them visible by
reading the import graph. See `docs/reproduction-notes.md` sections 20 and 23.

`model.py` re-exports these, so existing imports from `fews_stochopt.model`
continue to work; new code should import from here. Nothing in this module may
import anything that needs a solver -- `tests/test_artifacts.py` asserts it.
"""
from __future__ import annotations

# The scenario names, and the order the paper's tables use.
PERFECT_INFORMATION = "Perfect Information"
KNOWN_CLIMATE = "Known Climate, Unknown Weather"
STOCHASTIC = "Stochastic"
EXPECTED_VALUE = "Expected Value"

# A diagnostic, not one of the paper's four. It is the Expected Value scenario
# with the first stage pinned to what the published run invested, which isolates
# the second stage from the flat first-stage optimum. See reference/README.md.
EXPECTED_VALUE_PUBLISHED_FIRST_STAGE = "Expected Value (published first stage)"

# Table order, as printed in the paper. A list, not a tuple, because that is
# what `aggregate.SCENARIOS` has always been and this move must not change any
# behaviour alongside it.
SCENARIOS = [PERFECT_INFORMATION, KNOWN_CLIMATE, STOCHASTIC, EXPECTED_VALUE]
