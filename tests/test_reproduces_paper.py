"""Acceptance test for the paper's headline numbers.

**This suite is committed RED on purpose.**

The published values are pinned below from `reference/solnvalues.csv`. Nothing in this
repository yet regenerates them from source: the pipeline is two-stage (gurobipy
notebooks -> per-scenario CSVs -> R aggregation), the intermediate CSVs are gitignored
as generated files, and neither stage has been made runnable from a clean clone.

The standard's Part 6 is explicit about this case: a requirement recorded as prose has
already failed, because prose gets read after the thing it was meant to prevent. So the
requirement is written as a test that fails, and it goes green when — and only when —
`scripts/run_all.py` exists and reproduces these numbers.

Run with `-m pinned` to check only that the reference file still parses.
"""
import csv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "reference" / "solnvalues.csv"

# From reference/solnvalues.csv, produced by stage2-r/FM Final Outputs.Rmd.
PUBLISHED = {
    "Equally Probable": {
        "Value_of_Known_Weather": 10396.3181015145,
        "Value_of_Perfect_Information": 108725.141709509,
        "Value_of_Stochastic_Solution": 0.488689677613507,
    },
    "Dry Most Likely": {
        "Value_of_Known_Weather": 11740.0305519786,
        "Value_of_Perfect_Information": 76606.0080918825,
        "Value_of_Stochastic_Solution": 940.899927688976,
    },
}


def read_reference():
    with open(REFERENCE, newline="", encoding="utf-8") as fh:
        return {r["Climate_Probability"]: r for r in csv.DictReader(fh)}


@pytest.mark.pinned
def test_reference_file_still_says_what_we_pinned():
    """Guards the pin itself. Green today; goes red if reference/ is edited."""
    rows = read_reference()
    assert rows, "reference/solnvalues.csv parsed to zero rows"
    for regime, expected in PUBLISHED.items():
        assert regime in rows, f"climate regime {regime!r} missing from reference"
        for field, value in expected.items():
            assert float(rows[regime][field]) == pytest.approx(value, rel=1e-12), (
                f"{regime}/{field} in reference/ no longer matches the pinned value"
            )


def _regenerate():
    """Run the pipeline and return {regime: {field: value}}. Not implemented yet."""
    runner = ROOT / "scripts" / "run_all.py"
    if not runner.exists():
        pytest.fail(
            "RED BY DESIGN: no scripts/run_all.py, so nothing regenerates the paper's "
            "numbers from source. See README 'What is not done yet'. This test goes "
            "green when the two-stage pipeline runs from a clean clone."
        )
    raise NotImplementedError


@pytest.mark.parametrize("regime", sorted(PUBLISHED))
def test_pipeline_reproduces_published_values(regime):
    got = _regenerate()
    for field, value in PUBLISHED[regime].items():
        assert got[regime][field] == pytest.approx(value, rel=1e-6), f"{regime}/{field}"
