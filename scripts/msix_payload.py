"""Validate the source-only release and assemble an explicit MSIX payload.

Never accept a user's installed application, runtime data or settings as input.
Third-party runtimes are provisioned separately by build_msix.ps1 from locks.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
import shutil
import stat
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path, PurePosixPath
from xml.sax.saxutils import escape, quoteattr

from build_local_bundle import (
    INSTALL_MANIFEST,
    INSTALL_REQUIREMENTS,
    RUNTIME_DATA,
    source_allowed,
    verify_file,
)
from sbom import python_component

FOUNDATION = "http://schemas.microsoft.com/appx/manifest/foundation/windows10"


def safe_name(name: str) -> bool:
    return (bool(name) and "\\" not in name and ":" not in name
            and not name.startswith("/") and all(
                part not in {"", ".", ".."} and not part.endswith((".", " "))
                and not re.search(r'[\x00-\x1f<>"|?*]', part)
                and not re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", part)
                for part in name.split("/")))


def release_allowed(name: str) -> bool:
    generated = {"local-release.json", "Cytellect Setup.cmd", "THIRD_PARTY_WEB_NOTICES.txt",
                 "web-license-inventory.json", RUNTIME_DATA, INSTALL_MANIFEST, INSTALL_REQUIREMENTS}
    return (source_allowed(name) or name in generated
            or bool(re.fullmatch(r"wheels/cytellect-[0-9][0-9a-z.+]*-py3-none-any\.whl", name))
            or name.startswith("apps/web/out/"))


def extract_release(archive: Path, destination: Path) -> dict:
    if destination.exists():
        raise ValueError("msix_source_destination_exists")
    with zipfile.ZipFile(archive) as bundle:
        entries = bundle.infolist()
        names = [item.filename for item in entries]
        if (len(names) != len(set(name.casefold() for name in names))
                or sum(item.file_size for item in entries) > 150 * 1024**2
                or any(not safe_name(item.filename) or not release_allowed(item.filename)
                       or item.is_dir() or stat.S_ISLNK(item.external_attr >> 16) for item in entries)):
            raise ValueError("msix_source_archive_invalid")
        release = json.loads(bundle.read("local-release.json"))
        if (release["schema"] != "cytellect-local-release/1" or release["platform"] != "windows-x64"
                or not re.fullmatch(r"[a-f0-9]{40}", release["source_commit"])):
            raise ValueError("msix_release_invalid")
        expected = {item["path"]: item for item in release["files"]}
        if (len(expected) != len(release["files"]) or set(names) != set(expected) | {"local-release.json"}):
            raise ValueError("msix_source_manifest_invalid")
        # Verify every member before writing any output.
        for name, item in expected.items():
            data = bundle.read(name)
            if len(data) != item["size"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
                raise ValueError("msix_source_hash_mismatch")
        destination.mkdir(parents=True)
        bundle.extractall(destination)
    return release


def stage_source(source: Path, stage: Path) -> None:
    release = json.loads((source / "local-release.json").read_text(encoding="utf-8"))
    # Retain the complete verified source manifest for scientific revision checks,
    # including the normal wheel and locked installer inputs, never any builder data.
    for name in ["local-release.json", *[item["path"] for item in release["files"]]]:
        if not safe_name(name) or not release_allowed(name):
            raise ValueError("msix_source_path_invalid")
        path = source / name
        verify_file(source, path)
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)


def write_manifest(template: Path, stage: Path, name: str, publisher: str, publisher_name: str,
                   version: str) -> None:
    if (not re.fullmatch(r"[A-Za-z0-9.-]{3,50}", name) or not publisher.startswith("CN=")
            or not publisher_name.strip() or any(ord(c) < 32 for c in publisher + publisher_name)):
        raise ValueError("msix_identity_invalid")
    parts = version.split(".")
    if (len(parts) != 4 or any(not re.fullmatch(r"0|[1-9][0-9]*", p) or int(p) > 65535 for p in parts)
            or parts[0] == "0" and parts[1:] == ["0", "0", "0"] or parts[-1] != "0"):
        raise ValueError("msix_store_version_invalid")
    tree = ET.parse(template)
    identity = tree.find(f"{{{FOUNDATION}}}Identity")
    assert identity is not None
    identity.attrib.update(Name=name, Publisher=publisher, Version=version)
    label = tree.find(f"{{{FOUNDATION}}}Properties/{{{FOUNDATION}}}PublisherDisplayName")
    assert label is not None
    label.text = publisher_name
    # Preserve declared namespace prefixes (including those referenced only by
    # IgnorableNamespaces); ElementTree drops unused xmlns declarations.
    text = template.read_text(encoding="utf-8")
    text = re.sub(r"(?<=<Identity )[^>]+", lambda _: " ".join(
        f"{k}={quoteattr(v)}" for k, v in identity.attrib.items()) + " /", text, count=1)
    text = re.sub(r"<PublisherDisplayName>.*?</PublisherDisplayName>",
                  lambda _: "<PublisherDisplayName>" + escape(label.text) + "</PublisherDisplayName>", text)
    ET.fromstring(text)
    (stage / "AppxManifest.xml").write_text(text, encoding="utf-8")


def write_inventory(stage: Path, output: Path) -> None:
    files = []
    for path in sorted(stage.rglob("*")):
        if path.is_symlink() or path.is_junction():
            raise ValueError("msix_payload_link_forbidden")
        if not path.is_file():
            continue
        relative = path.relative_to(stage).as_posix()
        if not safe_name(relative) or PurePosixPath(relative).parts[0] in {"data", "settings", "setup-cache"}:
            raise ValueError("msix_payload_private_path")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        files.append({"path": relative, "bytes": path.stat().st_size, "sha256": digest})
    output.write_text(json.dumps({"schema": "cytellect-msix-payload/1", "files": files}, indent=2) + "\n",
                      encoding="utf-8")


def write_notices_inventory(stage: Path) -> None:
    python = [python_component(distribution) for distribution in importlib.metadata.distributions(
        path=[str(stage / "runtime/Lib/site-packages")])]
    if not python:
        raise ValueError("msix_python_inventory_empty")
    fiji = json.loads((stage / "engines/fiji/runtime.lock.json").read_text(encoding="utf-8"))
    value = {"schema": "cytellect-msix-third-party/1", "python": python, "fiji": fiji,
             "web": json.loads((stage / "web-license-inventory.json").read_text(encoding="utf-8")),
             "redistribution_review": "required before Store submission; inventory is not legal clearance"}
    (stage / "THIRD_PARTY_INVENTORY.json").write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    extract = commands.add_parser("extract")
    extract.add_argument("archive", type=Path)
    extract.add_argument("destination", type=Path)
    stage = commands.add_parser("stage")
    stage.add_argument("source", type=Path)
    stage.add_argument("destination", type=Path)
    manifest = commands.add_parser("manifest")
    manifest.add_argument("template", type=Path)
    manifest.add_argument("destination", type=Path)
    manifest.add_argument("--name", required=True)
    manifest.add_argument("--publisher", required=True)
    manifest.add_argument("--publisher-name", required=True)
    manifest.add_argument("--version", required=True)
    inventory = commands.add_parser("inventory")
    inventory.add_argument("stage", type=Path)
    inventory.add_argument("output", type=Path)
    notices = commands.add_parser("notices")
    notices.add_argument("stage", type=Path)
    args = parser.parse_args()
    if args.command == "extract":
        extract_release(args.archive, args.destination)
    elif args.command == "stage":
        stage_source(args.source, args.destination)
    elif args.command == "manifest":
        write_manifest(args.template, args.destination, args.name, args.publisher, args.publisher_name, args.version)
    elif args.command == "inventory":
        write_inventory(args.stage, args.output)
    else:
        write_notices_inventory(args.stage)


if __name__ == "__main__":
    main()
