"""Every import is declared, and the check reads the declaration rather than a copy.

An undeclared import is invisible on the machine that has the package installed
for some other reason, and fatal on a clean one. This guard exists because that
is precisely the class of defect a passing suite does not catch: the suite runs in
the environment where the import happens to resolve.

Three things about how it is written, each one a way this check could quietly
stop working:

- **It scans; it does not import.** Importing `model.py` would build a Gurobi
  environment. `ast` reads the imports without executing anything.
- **It reads `pyproject.toml`.** Restating the dependency list here would create a
  second copy with nothing comparing the two, so the guard against drift would be
  the first thing to drift.
- **`tomllib` is standard library only from 3.11**, and this project declares
  `>=3.10`. `pytest.importorskip` is the reflex and is wrong: on 3.10 it would
  skip and report green, which is this file's own failure mode wearing a hat. The
  `tomli` backport is declared in `pyproject.toml` so the check always runs.

Proven to fire: adding an undeclared `import requests` to `src/fews_stochopt/data.py`
turns this red, naming the module and the file. See `docs/reproduction-notes.md`.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised only on 3.10
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
SCANNED = (ROOT / "src", ROOT / "scripts", ROOT / "tests")

# A distribution name is not always the module it installs. Recorded as an
# explicit map rather than accommodated by loosening the comparison, which would
# quietly pass the next undeclared import that happened to look similar.
DISTRIBUTION_TO_MODULE = {
    "pyyaml": {"yaml"},
    "tomli": {"tomli"},
    "gurobipy": {"gurobipy"},
    "scikit-learn": {"sklearn"},
}


def declared_modules() -> set[str]:
    with open(ROOT / "pyproject.toml", "rb") as fh:
        data = tomllib.load(fh)
    project = data["project"]
    specs = list(project.get("dependencies", []))
    for extra in project.get("optional-dependencies", {}).values():
        specs.extend(extra)
    assert specs, "pyproject.toml declares no dependencies at all"

    modules: set[str] = set()
    for spec in specs:
        # "pandas>=2.0,<4" / "tomli>=2.0,<3; python_version < '3.11'"
        name = spec.split(";")[0]
        for sep in ("[", ">", "<", "=", "!", "~", " "):
            name = name.split(sep)[0]
        name = name.strip().lower()
        modules |= DISTRIBUTION_TO_MODULE.get(name, {name.replace("-", "_")})
    return modules


def top_level_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                found.add(node.module.split(".")[0])
    return found


def python_files() -> list[Path]:
    files: list[Path] = []
    for base in SCANNED:
        if base.exists():
            files.extend(sorted(base.rglob("*.py")))
    return files


def test_the_scan_finds_files_to_scan():
    """Guards against passing vacuously over an empty set."""
    files = python_files()
    assert len(files) >= 8, f"only {len(files)} python file(s) found under {SCANNED}"


def test_every_import_is_declared_or_standard_library():
    declared = declared_modules()
    local = {"fews_stochopt"}
    stdlib = set(sys.stdlib_module_names)
    # pytest is a test dependency, declared under [project.optional-dependencies].
    undeclared: list[tuple[str, str]] = []

    for path in python_files():
        for module in sorted(top_level_imports(path)):
            if module in stdlib or module in declared or module in local:
                continue
            undeclared.append((module, str(path.relative_to(ROOT))))

    assert not undeclared, (
        "imported but not declared in pyproject.toml: "
        + ", ".join(f"{m} ({f})" for m, f in undeclared)
        + ". Either add it to [project] dependencies or remove the import."
    )
