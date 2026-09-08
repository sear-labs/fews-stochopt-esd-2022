"""Archetype P: one maintained language, and the original frozen beside it.

> Everything that produced the published result is preserved verbatim. Exactly
> one implementation is maintained, and it is Python.

Two halves, and this file asserts both.

**One language.** The rule applies to *both sides* of the pipeline. This
repository used to port its model to Python and leave 674 lines of analysis in R,
which does not reduce the languages a reader needs -- it moves the barrier from
the model to the figures. `archive/stage2-r/` is now history; the analysis is
`src/fews_stochopt/analysis.py` and the figures are `scripts/make_figures.py`.

**Frozen.** Archived is not deleted -- the original is the only evidence of what
produced the published numbers. Archived is also not maintained -- a correction
goes in the Python and the divergence is recorded.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "archive"

# Where a maintained implementation may live. `archive/` is excluded by
# definition; `figures/` and `results/` hold outputs.
LIVE = ("src", "scripts", "tests", "notebooks")


def test_the_archive_exists_and_holds_the_originals():
    """Guards every check below against passing over an empty directory."""
    assert ARCHIVE.is_dir(), "archive/ is missing; the originals must be kept"
    r_files = sorted(ARCHIVE.rglob("*.Rmd")) + sorted(ARCHIVE.rglob("*.R"))
    notebooks = sorted(ARCHIVE.rglob("*.ipynb"))
    assert len(r_files) >= 23, f"only {len(r_files)} archived R file(s)"
    assert len(notebooks) >= 8, f"only {len(notebooks)} archived notebook(s)"


def test_no_maintained_code_is_in_another_language():
    """The rule, on the side that gets forgotten.

    A `.R` or `.Rmd` anywhere outside `archive/` means the analysis has crept
    back into a second language.
    """
    strays = []
    for directory in LIVE:
        base = ROOT / directory
        if not base.exists():
            continue
        for pattern in ("*.R", "*.Rmd", "*.gms", "*.do", "*.m"):
            strays += [p.relative_to(ROOT).as_posix() for p in base.rglob(pattern)]
    assert not strays, (
        "maintained code outside Python: " + ", ".join(strays)
        + ". Archetype P allows exactly one maintained implementation."
    )


def test_the_repository_root_holds_no_live_r():
    """The old `stage2-r/` and `stage1-python/` must not come back."""
    for gone in ("stage2-r", "stage1-python"):
        assert not (ROOT / gone).exists(), (
            f"{gone}/ is back at the repository root. Its contents belong under "
            f"archive/, and its inputs under data/raw/."
        )


def test_the_archive_is_frozen():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "freeze_archive.py"), "--check"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    assert proc.returncode == 0, (
        f"the archive has changed and must not\n"
        f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
    )


def test_the_freeze_covers_every_archived_file():
    """A manifest that lists nothing would pass --check forever."""
    manifest = ARCHIVE / "MANIFEST.sha256"
    assert manifest.exists(), "archive/MANIFEST.sha256 is missing"
    listed = [
        ln.split("  ", 1)[1]
        for ln in manifest.read_text(encoding="utf-8").splitlines()
        if ln and not ln.startswith("#")
    ]
    on_disk = [
        p.relative_to(ROOT).as_posix()
        for p in ARCHIVE.rglob("*")
        if p.is_file() and p.name != "MANIFEST.sha256"
    ]
    assert sorted(listed) == sorted(on_disk), (
        f"the manifest lists {len(listed)} files but {len(on_disk)} are present"
    )
    assert len(listed) >= 30, f"the manifest lists only {len(listed)} files"


def test_gitattributes_stops_git_rewriting_the_archive():
    """"Verbatim" has to mean bytes, and git will change them if allowed.

    With `core.autocrlf=true` a checkout rewrites LF to CRLF, which changes the
    raw-bytes hash and fails the freeze on every clean clone. Found exactly that
    way, by restoring an archived file and watching the manifest reject it.
    """
    attributes = (ROOT / ".gitattributes")
    assert attributes.exists(), ".gitattributes is missing"
    text = attributes.read_text(encoding="utf-8")
    assert "archive/** -text" in text, (
        ".gitattributes does not exempt archive/ from line-ending conversion"
    )


@pytest.mark.parametrize("stage", ["analysis code", "figures"])
def test_the_last_two_stages_are_python(stage):
    """Archetype P's stage list: analysis is `.py`, figures come from a script."""
    if stage == "analysis code":
        target = ROOT / "src" / "fews_stochopt" / "analysis.py"
    else:
        target = ROOT / "scripts" / "make_figures.py"
    assert target.exists(), f"{target.relative_to(ROOT)} is missing"
    assert target.suffix == ".py"


def test_figures_read_cleaned_output_and_never_raw():
    """A figure that parses the solver dump re-implements the clean-up stage."""
    source = (ROOT / "scripts" / "make_figures.py").read_text(encoding="utf-8")
    for forbidden in ("_detail.csv", "_profit.csv", "_investment.csv", "solve_scenario"):
        assert forbidden not in source, (
            f"make_figures.py reads raw output (`{forbidden}`). Figures must read "
            f"results/clean/ only."
        )
    assert "clean_dir" in source, "make_figures.py does not read cleaned output"
