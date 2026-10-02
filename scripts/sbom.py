"""Installed dependency/license evidence, not a legal compatibility decision.

Python CycloneDX is produced by the existing pip-audit CI invocation. This
inventory combines Python, actual Web notices and the fixed Fiji manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
from pathlib import Path, PurePosixPath

from web_licenses import collect_notices, notice_name

PLACEHOLDERS = {"", "unknown", "none", "n/a", "not declared", "review_required"}
PRIVATE_PATH = re.compile(r"(?:(?<![A-Za-z0-9])[A-Za-z]:[/\\](?!/)|/(?:home|Users)/)[^\s]+")


def declared(value: str | None) -> str | None:
    if value is None or value.strip().lower() in PLACEHOLDERS:
        return None
    value = value.strip()
    if "\x00" in value or PRIVATE_PATH.search(value):
        raise ValueError("dependency_metadata_contains_private_path")
    return value


def python_component(dist) -> dict:
    metadata = dist.metadata
    name, version = metadata.get("Name"), dist.version
    if (not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name)
            or not isinstance(version, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.!+_-]*", version)):
        raise ValueError("dependency_identity_invalid")
    expression = declared(metadata.get("License-Expression"))
    text = declared(metadata.get("License"))
    classifiers = sorted({c for c in metadata.get_all("Classifier", [])
                          if c.startswith("License :: ") and declared(c)})
    files = []
    base = Path(dist.locate_file("")).resolve()
    for entry in dist.files or []:
        relative = PurePosixPath(str(entry).replace("\\", "/"))
        if not (notice_name(relative.name) or "licenses" in [p.lower() for p in relative.parts]):
            continue
        if (relative.is_absolute() or ".." in relative.parts or "\\" in str(entry)
                or ":" in str(entry) or any(part in {"", "."} for part in relative.parts)):
            raise ValueError("dependency_notice_path_invalid")
        source = Path(dist.locate_file(entry))
        if not source.is_file() or not source.resolve().is_relative_to(base):
            raise ValueError("dependency_notice_unavailable")
        for ancestor in [source, *source.parents]:
            if ancestor.resolve() == base:
                break
            if ancestor.is_symlink() or ancestor.is_junction():
                raise ValueError("dependency_notice_redirected")
        raw = source.read_bytes()
        if len(raw) > 25 * 1024**2:
            raise ValueError("dependency_notice_invalid")
        files.append({"path": relative.as_posix(), "sha256": hashlib.sha256(raw).hexdigest(),
                      "size_bytes": len(raw)})
    # Some wheels ship empty placeholders for disabled optional codecs. Record
    # their hashes/sizes honestly, but never count an empty file as evidence.
    if not (expression or text or classifiers or any(f["size_bytes"] for f in files)):
        raise ValueError(f"dependency_license_evidence_missing: {name}@{version}")
    return {"type": "library", "name": name, "version": version,
            "license_evidence": {"expression": expression, "text": text,
                                 "classifiers": classifiers,
                                 "files": sorted(files, key=lambda f: f["path"])}}


def inventory(root: Path, distributions=None) -> tuple[dict, str]:
    distributions = importlib.metadata.distributions() if distributions is None else distributions
    python = sorted((python_component(dist) for dist in distributions),
                    key=lambda item: (item["name"].lower(), item["version"]))
    if not python:
        raise ValueError("dependency_python_inventory_empty")
    # Same installed pnpm collector used by the release builder; actual direct
    # dependency notice texts are required, not merely package metadata.
    notices, web = collect_notices(root)
    payload = {
        "schema": "cytellect-dependency-inventory/2",
        "scope": "installed development and runtime dependencies; not production-only",
        "python": python,
        "web": web,
        "fiji": json.loads((root / "engines/fiji/runtime.lock.json").read_text(encoding="utf-8")),
        "lockfiles": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                      for name in ("uv.lock", "pnpm-lock.yaml")},
        "notice": "Declared evidence and included notice hashes only. No inferred SPDX mapping, "
                  "legal compatibility decision, complete redistribution review or vulnerability guarantee.",
    }
    if PRIVATE_PATH.search(json.dumps(payload)) or PRIVATE_PATH.search(notices):
        raise ValueError("dependency_inventory_contains_private_path")
    return payload, notices


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--web-notices", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload, notices = inventory(args.root.resolve())
    except (OSError, ValueError):
        # Dependency paths/metadata need not be copied into public CI output.
        raise SystemExit("Dependency inventory rejected; inspect declared license/notice evidence locally.") from None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.web_notices.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.web_notices.write_text(notices, encoding="utf-8", newline="\n")
    print(json.dumps({"python_packages": len(payload["python"]),
                      "web_packages": len(payload["web"]["packages"]),
                      "web_notices": payload["web"]["notice_count"], "status": "passed"}))


if __name__ == "__main__":
    main()
