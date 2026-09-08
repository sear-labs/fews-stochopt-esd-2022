"""Record, and check, that nothing in `archive/` has changed.

    python scripts/freeze_archive.py            # write archive/MANIFEST.sha256
    python scripts/freeze_archive.py --check    # verify it

Archetype P: the original is preserved verbatim, never edited, never maintained,
and **a test fails if an archived file changes**. This is that test's instrument.

Archived is not deleted -- the original is the only evidence of what produced the
published numbers. Archived is also not maintained -- a correction goes into the
Python implementation and the divergence is recorded, because the original's job
is to say what the paper did, not to be right.

Hashes are over raw bytes, and the manifest says so: a hash quoted without its
normalisation is not evidence, and on Windows a CRLF-normalised hash of the same
file differs by one byte per line.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "archive"
MANIFEST = ARCHIVE / "MANIFEST.sha256"


def files() -> list[Path]:
    return sorted(
        p for p in ARCHIVE.rglob("*")
        if p.is_file() and p.name != MANIFEST.name
    )


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build() -> str:
    entries = files()
    if not entries:
        raise SystemExit("archive/ is empty; there is nothing to freeze")
    lines = [
        "# sha256 over RAW BYTES of every file in archive/.",
        "# A CRLF-normalised hash of the same file differs; this is the raw one.",
        "#",
        "# archive/ is the code that produced the published result. It is preserved",
        "# verbatim and never maintained: corrections go into src/fews_stochopt/,",
        "# and the divergence is recorded in docs/reproduction-notes.md.",
        "#",
        f"# {len(entries)} files",
        "",
    ]
    for p in entries:
        lines.append(f"{digest(p)}  {p.relative_to(ROOT).as_posix()}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    current = build()
    if not args.check:
        MANIFEST.write_text(current, encoding="utf-8")
        print(f"froze {len(files())} archived files into {MANIFEST.relative_to(ROOT)}")
        return 0

    if not MANIFEST.exists():
        print(f"{MANIFEST} is missing; run without --check", file=sys.stderr)
        return 1
    recorded = MANIFEST.read_text(encoding="utf-8")
    if recorded == current:
        print(f"archive unchanged: {len(files())} files")
        return 0

    def parse(text):
        return {
            ln.split("  ", 1)[1]: ln.split("  ", 1)[0]
            for ln in text.splitlines()
            if ln and not ln.startswith("#")
        }

    was, now = parse(recorded), parse(current)
    changed = sorted(k for k in was.keys() & now.keys() if was[k] != now[k])
    removed = sorted(was.keys() - now.keys())
    added = sorted(now.keys() - was.keys())
    print("archive/ has changed, and it must not:", file=sys.stderr)
    for k in changed:
        print(f"  MODIFIED {k}", file=sys.stderr)
    for k in removed:
        print(f"  REMOVED  {k}", file=sys.stderr)
    for k in added:
        print(f"  ADDED    {k}", file=sys.stderr)
    print(
        "\nThe archive is the evidence of what produced the published numbers. "
        "If a change is genuinely intended -- adding a newly found original, say "
        "-- re-run without --check and say why in the commit.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
