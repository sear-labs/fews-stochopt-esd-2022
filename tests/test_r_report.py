"""The parameterised R report renders, and agrees with the Python package.

`stage2-r/farm_report.Rmd` replaces eleven copy-pasted reports. It recomputes the
value-of-information table from the same per-run output the package reads, and
`farm_report.Rmd` itself asserts the two agree to 1e-6 before writing
`report_table.csv`. This file re-checks that from outside, so the agreement is not
only asserted by the thing being checked.

**Skipping is not passing.** If R or `rmarkdown` is absent these tests skip with a
reason naming what is missing; they never report success over an environment that
could not run them. A skip is visible in pytest's summary, a vacuous pass is not.
"""
from __future__ import annotations

import csv
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fews_stochopt.config import load_config  # noqa: E402

FIELDS = (
    "Value_of_Known_Weather",
    "Value_of_Perfect_Information",
    "Value_of_Stochastic_Solution",
    "Value_of_Known_Climate",
)


def _rscript() -> str | None:
    for name in ("Rscript", "Rscript.exe"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _has_rmarkdown(rscript: str) -> bool:
    proc = subprocess.run(
        [rscript, "-e", 'quit(status = if (requireNamespace("rmarkdown", quietly=TRUE)) 0 else 1)'],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


requires_r = pytest.mark.skipif(
    _rscript() is None, reason="Rscript is not on PATH; the R stage cannot be checked here"
)


@pytest.fixture(scope="module")
def rendered():
    rscript = _rscript()
    if rscript is None:
        pytest.skip("Rscript is not on PATH")
    if not _has_rmarkdown(rscript):
        pytest.skip("the rmarkdown package is not installed for this R")
    if not (ROOT / "results" / "solnvalues.csv").exists():
        pytest.skip("stage 1 has not run; `python scripts/run_all.py` first")

    proc = subprocess.run(
        [rscript, str(ROOT / "stage2-r" / "render_reports.R")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    # Both streams and the return code, always.
    if proc.returncode != 0:
        pytest.fail(
            f"render_reports.R exited {proc.returncode}\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
        )
    return proc


@pytest.mark.rstage
def test_one_report_replaced_the_eleven():
    """The parameterised report exists and the copy-pasted grid is gone.

    This is the check the briefing's first task asks for, written so it fails if
    the duplication comes back rather than being recorded as done in prose.
    """
    stage2 = ROOT / "stage2-r"
    assert (stage2 / "farm_report.Rmd").exists(), "stage2-r/farm_report.Rmd is missing"

    superseded = stage2 / "superseded"
    live = sorted(p.name for p in stage2.glob("*.Rmd"))
    # Two live documents: the parameterised report, and the scenario generation
    # that feeds stage 1. Neither is site-specific; both take `params$site`.
    assert live == ["farm_report.Rmd", "markov_chain.Rmd"], (
        f"stage2-r/ should hold exactly the two parameterised documents; it holds "
        f"{live}. The eleven site-specific reports belong under {superseded.name}/."
    )
    # And they must actually still exist somewhere, not have been deleted.
    kept = sorted(p.name for p in superseded.glob("*.Rmd"))
    assert len(kept) >= 11, (
        f"only {len(kept)} superseded report(s) kept; the originals are the record "
        f"of what the published run did and must not be discarded"
    )


def _r_code(path: Path) -> str:
    """The executable R in a file: chunk bodies for an .Rmd, everything for an .R.

    Prose is excluded on purpose. `markov_chain.Rmd` *names* the path it replaced,
    in a sentence explaining why it no longer reads it, and a check that cannot
    tell a path in a code chunk from a path in a paragraph would force that
    explanation to be deleted -- which is the opposite of what it is for.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix != ".Rmd":
        return text
    code, inside = [], False
    for line in text.splitlines():
        if line.startswith("```{"):
            inside = True
            continue
        if inside and line.startswith("```"):
            inside = False
            continue
        if inside:
            code.append(line)
    return "\n".join(code)


@pytest.mark.rstage
def test_no_hardcoded_absolute_paths_remain():
    """The live stage-2 code carries no path to a machine that no longer exists.

    `~/Coding/R/Research/Farm Model/` and `C:\\Users\\Jones\\...` appeared more
    than thirty times across the eleven reports, nine in `FM Final Outputs.Rmd`
    alone. Parameterising the site is what removed them -- a path cannot stay
    hardcoded once the site is an argument -- and this is what keeps them removed.
    """
    needles = ("~/Coding", "C:\\Users\\Jones", "C:/Users/Jones", "Documents\\Coding")
    sources = sorted((ROOT / "stage2-r").glob("*.Rmd")) + sorted(
        (ROOT / "stage2-r").glob("*.R")
    )
    assert len(sources) >= 3, f"only {len(sources)} live stage-2 source(s) found"

    offenders = []
    for path in sources:
        code = _r_code(path)
        for needle in needles:
            if needle in code:
                offenders.append(f"{path.name}: {needle}")
    assert not offenders, "hardcoded absolute paths are back: " + "; ".join(offenders)


@pytest.mark.rstage
def test_the_path_check_can_actually_see_code():
    """The check above searches chunk bodies; prove it finds something in them.

    A stripper with an off-by-one in its fence handling would return the empty
    string for every file, and the check would pass over nothing forever.
    """
    code = _r_code(ROOT / "stage2-r" / "farm_report.Rmd")
    assert len(code) > 1000, f"chunk extraction returned {len(code)} characters"
    assert "read_csv" in code, "chunk extraction did not find code it should have"
    assert "# What this report covers" not in code, "prose leaked into the code slice"

    # And prove it would fire: the superseded originals are full of these paths.
    superseded = ROOT / "stage2-r" / "superseded" / "FM Final Outputs.Rmd"
    assert superseded.exists()
    assert "~/Coding" in _r_code(superseded), (
        "the check found no hardcoded path in a file known to carry nine of them, "
        "so a clean result on the live sources would mean nothing"
    )


@pytest.mark.rstage
@requires_r
def test_report_renders_for_every_site(rendered):
    cfg = load_config()
    out = ROOT / "results" / "reports"
    for site in cfg.sites:
        html = out / f"farm_report_{site}.html"
        assert html.exists(), f"{html} was not produced"
        assert html.stat().st_size > 10_000, f"{html} is suspiciously small"


@pytest.mark.rstage
@requires_r
def test_r_table_agrees_with_the_python_table(rendered):
    """Two implementations of the same arithmetic, compared rather than assumed.

    Both read the same per-run CSVs and both do the differencing in double
    precision, so the only permissible difference is summation order. The
    tolerance is tight on purpose: anything larger means the two disagree about
    what they are computing, which is the failure deliberate duplication invites.
    """
    cfg = load_config()
    python_rows = {
        r["Climate_Probability"]: r
        for r in csv.DictReader(
            open(ROOT / "results" / "solnvalues.csv", encoding="utf-8")
        )
    }
    assert python_rows, "results/solnvalues.csv parsed to zero rows"

    checked = 0
    for site in cfg.sites:
        path = ROOT / "results" / site / "report_table.csv"
        assert path.exists(), f"{path} was not written by farm_report.Rmd"
        r_rows = list(csv.DictReader(open(path, encoding="utf-8")))
        assert len(r_rows) == 1, f"{path} has {len(r_rows)} rows, expected 1"
        r_row = r_rows[0]
        label = cfg.site(site).label
        assert r_row["Climate_Probability"] == label
        for field in FIELDS:
            a = float(r_row[field])
            b = float(python_rows[label][field])
            assert a == pytest.approx(b, abs=1e-6), (
                f"{label}/{field}: R says {a!r}, Python says {b!r}"
            )
            checked += 1

    assert checked == len(FIELDS) * len(cfg.sites), (
        f"only {checked} comparison(s) made; the loop found less than it should"
    )
