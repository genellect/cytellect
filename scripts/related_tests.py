"""Pick the Python test modules a change can affect, for `dev.py check --related`.

A test module is related to a changed file when it

- is the changed file,
- imports it directly, or
- names it: the file's path or name appears in the test's source, as in tests that read
  workflows, fixtures, lockfiles or documents.

Tests that reach a change only through another module (most API tests reach the analysis
package through the application) are left to pull-request CI, which runs the whole suite:
following every import would select most of the suite for most changes. Changes to the test
configuration itself select every module. Standard library only.
"""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path, PurePosixPath

# A change here can affect any test.
EVERYTHING = ("pyproject.toml", "uv.lock", "tests/conftest.py")
# File names too common to identify one file.
GENERIC_NAMES = frozenset({"__init__.py", "README.md", "manifest.json", "package.json"})


def tracked_python(root: Path) -> list[str]:
    """Python files git tracks or would add, as repository-relative POSIX paths that exist."""
    listed = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", "*.py"],
                            cwd=root, capture_output=True, text=True, check=True)
    return sorted(path for path in set(listed.stdout.splitlines()) if (root / path).is_file())


def module_name(path: str, files: frozenset[str]) -> str:
    """The dotted name a file is imported by: its packages up to the first directory without __init__.py."""
    parts = list(PurePosixPath(path).with_suffix("").parts)
    start = len(parts) - 1
    while start > 0 and "/".join([*parts[:start], "__init__.py"]) in files:
        start -= 1
    names = parts[start:]
    return ".".join(names[:-1] if names[-1] == "__init__" and len(names) > 1 else names)


def imported_names(path: str, source: str, files: frozenset[str]) -> set[str]:
    """Dotted names a module imports; `from a import b` yields both `a` and `a.b`."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    package = module_name(path, files).split(".")
    if PurePosixPath(path).name != "__init__.py":
        package = package[:-1]
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = package[:len(package) - node.level + 1] if node.level else []
            module = ".".join([*base, *(node.module.split(".") if node.module else [])])
            if module:
                names.add(module)
            names.update(f"{module}.{alias.name}" if module else alias.name for alias in node.names)
    return names


def importers(sources: dict[str, str], changed: set[str]) -> set[str]:
    """The files in `sources` that import a changed file directly."""
    files = frozenset(sources)
    names = {module_name(path, files) for path in changed if path in sources}
    return {path for path, source in sources.items() if names & imported_names(path, source, files)}


def is_test(path: str) -> bool:
    return path.startswith("tests/") and PurePosixPath(path).name.startswith("test_") and path.endswith(".py")


def select(sources: dict[str, str], changed: list[str]) -> list[str] | None:
    """Related test modules for the changed paths; None when the change can affect every test."""
    if any(path in EVERYTHING for path in changed):
        return None
    tests = {path for path in sources if is_test(path)}
    related = {path for path in changed if path in tests} | (importers(sources, set(changed)) & tests)
    needles = {needle for path in changed
               for needle in (path, PurePosixPath(path).name) if needle not in GENERIC_NAMES}
    related |= {test for test in tests if any(needle in sources[test] for needle in needles)}
    return sorted(related)


def related_tests(root: Path, changed: list[str]) -> list[str] | None:
    sources = {path: (root / path).read_text(encoding="utf-8", errors="replace") for path in tracked_python(root)}
    return select(sources, changed)
