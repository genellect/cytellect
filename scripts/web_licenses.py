"""Collect installed Web license texts, including bundled vendor notices.

The inventory is intentionally overinclusive: it includes all locally installed
pnpm packages (development/build tools too), not an asserted production graph.
No package downloads or dependency resolution occur here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

NOTICE_NAME = re.compile(r"^(?:licen[cs]e|notice|copying|copyright)(?:[._ -].*)?$", re.I)


def notice_name(name: str) -> bool:
    normalized = name.lower().replace("-", "").replace("_", "")
    return bool(NOTICE_NAME.fullmatch(name) or normalized.startswith("thirdpartynotice"))


def package_directories(store: Path):
    seen = set()
    for slot in sorted(store.iterdir()):
        modules = slot / "node_modules"
        if not modules.is_dir():
            continue
        for entry in sorted(modules.iterdir()):
            candidates = sorted(entry.iterdir()) if entry.name.startswith("@") and entry.is_dir() else [entry]
            for candidate in candidates:
                resolved = candidate.resolve()
                if resolved in seen or not resolved.is_relative_to(store.resolve()):
                    continue
                if (resolved / "package.json").is_file():
                    seen.add(resolved)
                    yield resolved


def notice_files(package: Path):
    for directory, folders, files in os.walk(package, followlinks=False):
        root = Path(directory)
        folders[:] = sorted(name for name in folders if name not in {"node_modules", ".git"}
                            and not (root / name).is_symlink() and not (root / name).is_junction())
        for name in sorted(files):
            file = root / name
            if notice_name(name) and file.is_file() and not file.is_symlink():
                yield file


def collect_notices(root: Path) -> tuple[str, dict]:
    store = root / "node_modules/.pnpm"
    web_manifest = json.loads((root / "apps/web/package.json").read_text(encoding="utf-8-sig"))
    required = set(web_manifest.get("dependencies", {})) | {"react", "react-dom", "next"}
    if not store.is_dir():
        raise ValueError("web_licenses_installed_store_missing")
    inventory: dict[tuple[str, str], dict] = {}
    notices = {}
    with_own_text = set()
    for package in package_directories(store):
        metadata = json.loads((package / "package.json").read_text(encoding="utf-8-sig"))
        name, version = metadata.get("name"), metadata.get("version")
        if (not isinstance(name, str) or not isinstance(version, str)
                or any(char in name + version for char in "\r\n\x00")):
            raise ValueError("web_licenses_package_metadata_invalid")
        key = (name, version)
        record = inventory.setdefault(key, {"name": name, "version": version,
                                           "declared_license": metadata.get("license", "not declared"),
                                           "license_files": []})
        for file in notice_files(package):
            raw = file.read_bytes()
            if not raw or len(raw) > 25 * 1024**2:
                raise ValueError("web_licenses_text_invalid")
            sha = hashlib.sha256(raw).hexdigest()
            relative = file.relative_to(package).as_posix()
            try:
                text = raw.decode("utf-8-sig")
                encoding = "UTF-8"
            except UnicodeDecodeError:
                # Preserve every source byte instead of silently replacing
                # copyright holder names; mark the source interpretation.
                text, encoding = raw.decode("latin-1"), "Latin-1 byte-preserving interpretation"
            notice_key = (name, version, relative, sha)
            notices[notice_key] = (text, encoding)
            item = {"path": relative, "sha256": sha}
            if item not in record["license_files"]:
                record["license_files"].append(item)
            if file.parent == package and NOTICE_NAME.fullmatch(file.name):
                with_own_text.add(name)
    if required - with_own_text:
        raise ValueError("web_licenses_required_license_text_missing: " + ", ".join(sorted(required - with_own_text)))
    if not notices:
        raise ValueError("web_licenses_empty")
    records = [inventory[key] for key in sorted(inventory)]
    report = {"schema": "cytellect-web-notices/1", "scope": "all-installed-pnpm-packages-overinclusive",
              "required_direct_dependencies": sorted(required), "packages": records,
              "notice_count": len(notices)}
    output = ["Cytellect Web — third-party licenses and notices", "",
              "Scope: all installed pnpm packages, including development/build dependencies.",
              "This overinclusive inventory is not a production-only dependency graph.",
              "Bundled vendor license and notice files found inside packages are included.",
              "A declared SPDX identifier without a license file is listed as metadata only.",
              "The package licenses remain separate from Cytellect's own Apache-2.0 license.", "",
              "Installed inventory (name@version; declared license; included text files):"]
    for record in records:
        license_id = json.dumps(record["declared_license"], ensure_ascii=False, sort_keys=True)
        output.append(f"- {record['name']}@{record['version']}; {license_id}; {len(record['license_files'])}")
    for (name, version, relative, sha), (text, encoding) in sorted(notices.items()):
        output.extend(["", "=" * 72, f"{name}@{version} — {relative}", f"Source SHA-256: {sha}",
                       f"Source encoding: {encoding}", "-" * 72, text.rstrip(), ""])
    return "\n".join(output) + "\n", report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--inventory", type=Path)
    args = parser.parse_args()
    text, report = collect_notices(args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8", newline="\n")
    if args.inventory:
        args.inventory.parent.mkdir(parents=True, exist_ok=True)
        args.inventory.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"packages": len(report["packages"]), "notices": report["notice_count"]}))


if __name__ == "__main__":
    main()
