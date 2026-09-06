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

# These are the paper's Table 4, cross-checked against reference/solnvalues.csv
# (produced by stage2-r/FM Final Outputs.Rmd). Five of six agree to the paper's
# printed precision. One does NOT:
#
#     EVPI, equally probable:   paper $108,725.10   solnvalues.csv 108,725.1417
#
# A 0.04 discrepancy. Too small to be a different solution and too large to be
# rounding of the CSV value, which would give .14. Either the article carries a
# typo or its table was produced by a slightly earlier run. The CSV value is
# pinned below because it is the one this pipeline actually produces; the paper's
# figure is recorded here so the difference is not silently lost.
#
# The paper also reports EVKC (Expected Value of Known Climate) - $98,328.78 and
# $64,865.98 - which solnvalues.csv does not contain at all. Any future run_all.py
# should emit it so all four columns can be checked.
PAPER_TABLE_4 = {
    "Equally Probable": {"EVPI": 108_725.10, "VSS": 0.49, "EVKW": 10_396.32, "EVKC": 98_328.78},
    "Dry Most Likely": {"EVPI": 76_606.01, "VSS": 940.90, "EVKW": 11_740.03, "EVKC": 64_865.98},
}

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


@pytest.mark.pinned
def test_pinned_values_agree_with_the_published_table():
    """Five of the six shared figures match the article to its printed precision.

    The sixth is asserted as a KNOWN discrepancy rather than skipped, so that if a
    future edit changes it the difference is noticed rather than absorbed.
    """
    field = {"EVPI": "Value_of_Perfect_Information",
             "VSS": "Value_of_Stochastic_Solution",
             "EVKW": "Value_of_Known_Weather"}
    mismatches = []
    for regime, paper in PAPER_TABLE_4.items():
        for short, key in field.items():
            ours = PUBLISHED[regime][key]
            if round(ours, 2) != pytest.approx(paper[short], abs=1e-9):
                mismatches.append((regime, short, paper[short], round(ours, 2)))
    assert mismatches == [("Equally Probable", "EVPI", 108725.10, 108725.14)], (
        f"the set of paper-vs-pipeline discrepancies changed: {mismatches}"
    )
