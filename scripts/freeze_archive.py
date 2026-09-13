"""Record, and check, that nothing which must not change has changed.

    python scripts/freeze_archive.py            # write both MANIFEST.sha256
    python scripts/freeze_archive.py --check    # verify them

Two trees, two reasons:

    archive/    Archetype P -- the original is preserved verbatim
    data/raw/   invariant 4 -- inputs are immutable; no stage writes back

`data/raw/` was added on 2026-09-13. The rule had been stated in prose and
in `markov.simulate`, which says an input a later stage can overwrite is not
an input -- and asserted nowhere. The two committed precipitation files are
what every number in Tables 4 and 5 follows from, and they could have
changed without a test noticing. The script keeps its name because the
archive freeze is what most references point at.

Archetype P: the original is preserved verbatim, never edited, never maintained,
and **a test fails if an archived file changes**. This is that test's instrument.

Archived is not deleted -- the original is the only evidence of what produced the
published numbers. Archived is also not maintained -- a correction goes into the
Python implementation and the divergence is recorded, because the original's job
is to say what the paper did, not to be right.

Hashes are over raw bytes, and the manifest says so: a hash quoted without its
normalisation is not evidence, and on Windows a CRLF-normalised hash of the same
file differs by one byte per line.

**When a file first enters `archive/`, renormalise before freezing.** Git applies
`.gitattributes` at the moment a blob is written, so a file committed *before* it
was covered by `archive/** -text` carries line endings that a fresh clone will not
reproduce -- and the manifest, built from the working tree, then rejects every
clone. The sequence is:

    git add --renormalize -- archive
    rm -rf archive && git checkout -- archive     # what a clone will actually get
    python scripts/freeze_archive.py

Learned by moving one file in and watching a clean clone fail. `--check` compares
against the working tree, so it cannot see this on the machine that froze it; the
clean-clone run is what catches it, and that is why there is one.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Two trees must not change, for two different reasons, and both are invariants
# rather than preferences.
#
#   archive/   invariant: the original is preserved verbatim (Archetype P)
#   data/raw/  invariant 4: inputs are immutable -- no stage writes back to them
#
# `data/raw/` was unfrozen until 2026-09-13. The rule was stated in prose and in
# `markov.simulate`'s docstring ("an input a later stage can overwrite is not an
# input") and asserted nowhere, so the two committed precipitation files -- from
# which every number in the paper's Tables 4 and 5 follows -- could have changed
# without a single test noticing.
FROZEN = (
    ("archive", ROOT / "archive"),
    ("data/raw", ROOT / "data" / "raw"),
)

_WHY = {
    "archive": [
        "# archive/ is the code that produced the published result. It is preserved",
        "# verbatim and never maintained: corrections go into src/fews_stochopt/,",
        "# and the divergence is recorded in docs/reproduction-notes.md.",
    ],
    "data/raw": [
        "# data/raw/ is the input of record. Every number in the paper's Tables 4",
        "# and 5 follows from these draws, and no stage may write back to them --",
        "# markov.simulate writes regenerated draws to results/regenerated/ instead.",
    ],
}


def files(root: Path) -> list[Path]:
    # Sorted by POSIX string, NOT by Path. `PurePath.__lt__` compares a
    # case-folded string on Windows and raw characters on POSIX, so sorting
    # Path objects puts `FEWS_Farm_model.py` after `FarmModelStoch_*` on one
    # platform and before it on the other. The manifest is compared as text, so
    # that reordering fails the freeze with every hash identical -- which is
    # what a clean Linux runner reported the first time one ever ran this.
    #
    # It means the archive freeze could not have passed on any non-Windows
    # clone since it was written: a reader on Linux or macOS could not verify
    # the archive at all, and nothing here could have told them why.
    return sorted(
        (p for p in root.rglob("*")
         if p.is_file() and p.name != "MANIFEST.sha256"),
        key=lambda p: p.as_posix(),
    )


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build(label: str, root: Path) -> str:
    entries = files(root)
    if not entries:
        raise SystemExit(f"{label}/ is empty; there is nothing to freeze")
    lines = [
        f"# sha256 over RAW BYTES of every file in {label}/.",
        "# A CRLF-normalised hash of the same file differs; this is the raw one.",
        "#",
        *_WHY[label],
        "#",
        f"# {len(entries)} files",
        "",
    ]
    for path in entries:
        lines.append(f"{digest(path)}  {path.relative_to(ROOT).as_posix()}")
    return chr(10).join(lines) + chr(10)


def _parse(text: str) -> dict[str, str]:
    return {
        ln.split("  ", 1)[1]: ln.split("  ", 1)[0]
        for ln in text.splitlines()
        if ln and not ln.startswith("#")
    }


def _report(label: str, recorded: str, current: str) -> None:
    was, now = _parse(recorded), _parse(current)
    changed = sorted(k for k in was.keys() & now.keys() if was[k] != now[k])
    removed = sorted(was.keys() - now.keys())
    added = sorted(now.keys() - was.keys())
    print(f"{label}/ has changed, and it must not:", file=sys.stderr)
    for k in changed:
        print(f"  MODIFIED {k}", file=sys.stderr)
    for k in removed:
        print(f"  REMOVED  {k}", file=sys.stderr)
    for k in added:
        print(f"  ADDED    {k}", file=sys.stderr)

    if not (changed or removed or added):
        # The manifest differs but no file does, so the difference is in the
        # header -- and naming nothing while saying "has changed" is a useless
        # message. Met exactly once, from a CI runner, where there was no way to
        # find out what differed. Show the lines.
        import difflib

        print("  no file differs; the manifest header does:", file=sys.stderr)
        diff = difflib.unified_diff(
            recorded.splitlines(), current.splitlines(),
            fromfile="committed", tofile="rebuilt", lineterm="", n=1,
        )
        for line in list(diff)[:20]:
            print(f"    {line}", file=sys.stderr)
    if label == "archive":
        why = (
            "The archive is the evidence of what produced the published numbers. "
            "If a change is genuinely intended -- adding a newly found original, "
            "say -- re-run without --check and say why in the commit."
        )
    else:
        why = (
            "data/raw/ is the input of record: every number in Tables 4 and 5 "
            "follows from it. If a stage wrote back to it, that is the defect -- "
            "fix the stage. If the input genuinely changed, the published "
            "comparison no longer means what it says, so say why in the commit."
        )
    print("", file=sys.stderr)
    print(why, file=sys.stderr)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    failed = 0
    for label, root in FROZEN:
        if not root.is_dir():
            print(f"{label}/ does not exist", file=sys.stderr)
            return 1
        manifest = root / "MANIFEST.sha256"
        current = build(label, root)

        if not args.check:
            manifest.write_text(current, encoding="utf-8")
            print(f"froze {len(files(root))} files into "
                  f"{manifest.relative_to(ROOT).as_posix()}")
            continue

        if not manifest.exists():
            print(f"{manifest} is missing; run without --check", file=sys.stderr)
            failed = 1
            continue
        recorded = manifest.read_text(encoding="utf-8")
        if recorded == current:
            print(f"{label} unchanged: {len(files(root))} files")
            continue
        _report(label, recorded, current)
        failed = 1

    return failed


if __name__ == "__main__":
    raise SystemExit(main())
