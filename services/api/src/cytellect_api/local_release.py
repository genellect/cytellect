"""Verify the installed Windows release without importing the API runtime."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


def installed_source_revision(root: Path | None = None, *, execution_file: Path | None = None) -> str | None:
    """A release label only when installed source matches its complete manifest.

    The manifest is not a code signature. Exported per-file/aggregate source
    hashes remain the identity of executed scientific code.
    """
    # Preserve the lexical wheel location so resolving a redirected package
    # cannot turn wheel verification into source-only manifest inspection.
    execution_file = (execution_file or Path(__file__)).absolute()
    root = root or execution_file.parents[4]
    site_packages = next(
        (root / runtime / "Lib/site-packages" for runtime in (".venv", "python")
         if execution_file.parent == (root / runtime / "Lib/site-packages/cytellect_api").absolute()),
        None,
    )
    manifest = root / "local-release.json"
    if not manifest.is_file():
        return None
    try:
        release = json.loads(manifest.read_text(encoding="utf-8"))
        revision = release["source_commit"]
        if release["schema"] != "cytellect-local-release/1" or not re.fullmatch("[a-f0-9]{40}", revision):
            return None
        entries = {}
        for item in release["files"]:
            name = item["path"]
            if (not isinstance(name, str) or name in entries or "\\" in name or ":" in name
                    or name.startswith("/") or any(part in {"", ".", ".."} for part in name.split("/"))):
                return None
            file = root / name
            if (not file.resolve().is_relative_to(root.resolve()) or not file.is_file()
                    or file.stat().st_size != item["size"]
                    or hashlib.sha256(file.read_bytes()).hexdigest() != item["sha256"]):
                return None
            entries[name] = item
        for relative in ("packages/analysis/src/cytellect_analysis", "services/api/src/cytellect_api",
                         "services/worker/src/cytellect_worker"):
            directory = root / relative
            if not (directory / "__init__.py").is_file():
                return None
            for file in directory.rglob("*.py"):
                if file.relative_to(root).as_posix() not in entries:
                    return None
            if site_packages is not None:
                # A normal wheel executes its site-packages copies. Identical
                # source files elsewhere in the release are not sufficient.
                installed = site_packages / directory.name
                if installed.resolve() != installed.absolute():
                    return None
                expected = {name[len(relative) + 1:]: entry for name, entry in entries.items()
                            if name.startswith(relative + "/") and name.endswith(".py")}
                paths = list(installed.rglob("*"))
                # Check directories too: rglob need not descend into a linked
                # directory that could still supply an unrecorded Python module.
                if any(file.resolve() != file.absolute() for file in paths):
                    return None
                actual = {file.relative_to(installed).as_posix(): file for file in paths
                          if file.suffix.lower() == ".py"}
                if actual.keys() != expected.keys():
                    return None
                for name, file in actual.items():
                    if file.resolve() != file.absolute() or not file.is_file():
                        return None
                    content = file.read_bytes()
                    if (len(content) != expected[name]["size"]
                            or hashlib.sha256(content).hexdigest() != expected[name]["sha256"]):
                        return None
        return revision
    except (OSError, ValueError, KeyError, TypeError):
        return None
