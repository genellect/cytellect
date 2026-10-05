"""Extract unchanged registered public TIFF bytes for the actual browser test."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from zipfile import ZipFile

from public_bbbc007 import MANIFEST, external_directory, sha256, verify_archive


def prepare(data: Path, output: Path) -> None:
    data, output = external_directory(data), external_directory(output)
    manifest_bytes = MANIFEST.read_bytes()
    manifest = json.loads(manifest_bytes)
    archive_name = "BBBC007_v1_images.zip"
    archive = data / archive_name
    verify_archive(archive, manifest["archives"][archive_name])
    field = next(item for item in manifest["fields"] if item["id"] == "a9")
    output.mkdir(parents=True, exist_ok=True)
    identities = {}
    with ZipFile(archive) as source:
        for channel in ("actin", "dna"):
            content = source.read(field["members"][channel])
            name = f"a9-{channel}.tif"
            (output / name).write_bytes(content)
            identities[name] = sha256(content)
    (output / "manifest.json").write_text(json.dumps({
        "dataset": manifest["dataset"], "source": manifest["source"],
        "license": manifest["license"], "files": identities,
        "registered_manifest_sha256": sha256(manifest_bytes),
        "archive_sha256": manifest["archives"][archive_name]["sha256"],
        "scope": "Unchanged archival TIFF bytes; chemical stain identities and native radiometry unverified.",
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    prepare(args.data_dir, args.output)
