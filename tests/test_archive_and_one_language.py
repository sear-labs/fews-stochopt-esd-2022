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


def test_the_raw_inputs_are_frozen():
    """Invariant 4: inputs are immutable, and no stage writes back to them.

    That rule was stated in prose and in `markov.simulate`'s docstring -- *an
    input a later stage can overwrite is not an input* -- and asserted nowhere
    until 2026-09-13. `data/raw/precips_c0_{EP,DML}.csv` are 4,000 sequences of
    25 years each, and **every number in the paper's Tables 4 and 5 follows from
    them**. They could have been overwritten by a regeneration, edited by hand,
    or silently line-ending-converted, and the only symptom would have been that
    the reproduction quietly started comparing against something else.

    The solve cache would have noticed something -- `.meta.json` carries
    `input_sha256`, so a change invalidates it and forces a re-solve -- but a
    re-solve is what the cache does when anything changes. It would have produced
    new numbers, not a complaint.

    `scripts/freeze_archive.py --check` now covers both trees. Shown to fail by
    appending one byte to a committed input.
    """
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "freeze_archive.py"), "--check"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    assert proc.returncode == 0, (
        f"a frozen tree has changed\n"
        f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
    )
    assert "data/raw unchanged" in proc.stdout, (
        f"the freeze did not report on data/raw, so it may not be covering it:\n"
        f"{proc.stdout}"
    )


def test_the_freeze_covers_every_committed_input():
    """Guards against the check above passing over an empty or partial manifest.

    The same failure the archive freeze guards against: a manifest that lists
    nothing passes its own check forever.
    """
    raw = ROOT / "data" / "raw"
    manifest = raw / "MANIFEST.sha256"
    assert manifest.exists(), "data/raw/MANIFEST.sha256 is missing"

    listed = {
        line.split("  ", 1)[1]
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    }
    on_disk = {
        p.relative_to(ROOT).as_posix()
        for p in raw.rglob("*")
        if p.is_file() and p.name != "MANIFEST.sha256"
    }
    assert listed == on_disk, (
        f"the input manifest does not match what is in data/raw/.\n"
        f"  listed but absent: {sorted(listed - on_disk)}\n"
        f"  present but unlisted: {sorted(on_disk - listed)}"
    )
    assert len(on_disk) >= 2, f"expected at least the two precipitation files, found {on_disk}"


def test_no_stage_writes_into_the_raw_inputs():
    """The other half of invariant 4, checked in the source rather than by running.

    A freeze catches a write after it happens. This catches the code that would
    do it: nothing outside the archive may open a path under `data/raw/` for
    writing, and `markov.simulate` in particular must write regenerated draws to
    `results/regenerated/`.
    """
    suspicious = []
    for path in sorted((ROOT / "src").rglob("*.py")) + sorted((ROOT / "scripts").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), 1):
            if "data/raw" not in line and "data\\raw" not in line:
                continue
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if any(verb in line for verb in ("to_csv", "write_text", "write_bytes",
                                             'open(', "unlink", "rmtree", "rename")):
                suspicious.append(f"{path.relative_to(ROOT).as_posix()}:{number}: {stripped}")
    assert not suspicious, (
        "a stage appears to write into data/raw/, which is the input of record:\n"
        + "\n".join(suspicious)
    )


def test_the_manifests_are_ordered_the_same_way_on_every_platform():
    """The freeze compares text, so its ordering has to be platform-independent.

    It was not. `files()` sorted `Path` objects, and `PurePath.__lt__` compares a
    **case-folded** string on Windows and raw characters on POSIX -- so
    `FEWS_Farm_model.py` sorts after `FarmModelStoch_*` on one and before it on
    the other. Eight lines move, every hash is identical, and the freeze fails
    naming no changed file.

    **The archive freeze therefore could not have passed on any non-Windows
    clone since it was written.** A reader on Linux or macOS could not verify the
    archive, which is one of this repository's stated guarantees, and the failure
    message would not have told them why. It was found the first time CI ran on a
    clean Ubuntu runner -- the invariant this repository had exempted itself from.

    This asserts the recorded order is the POSIX-string order, which is the same
    everywhere, rather than whatever the local `Path` comparison yields.
    """
    for manifest in (ROOT / "archive" / "MANIFEST.sha256",
                     ROOT / "data" / "raw" / "MANIFEST.sha256"):
        assert manifest.exists(), f"{manifest} is missing"
        listed = [
            line.split("  ", 1)[1]
            for line in manifest.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")
        ]
        assert listed, f"{manifest} lists no files"
        assert listed == sorted(listed), (
            f"{manifest.relative_to(ROOT).as_posix()} is not in POSIX-string "
            f"order, so it was written by a platform-dependent sort and will "
            f"fail the freeze somewhere else.\n"
            f"  first out of order: "
            f"{next(b for a, b in zip(sorted(listed), listed) if a != b)}"
        )
