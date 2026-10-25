"""Acquire the preregistered public DS6a subset without changing image pixels.

Use --verify for an existing download or --download for missing files. Output
must be outside this checkout. This tool does not detect, measure or select by
phenotype. Adoption and independent-replicate status remain owner decisions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
import urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "fixtures/public/group-comparison/ds6a-manifest.json"


def validate_manifest(manifest):
    seen = set()
    for item in manifest["files"]:
        name = item["name"]
        if not re.fullmatch(r"40x_1\.4_Rep[123]_(Untreated|ActD1)_20211201_01_\d+\.tif", name):
            raise ValueError("invalid_public_filename")
        if name in seen:
            raise ValueError("duplicate_public_filename")
        seen.add(name)
        expected = f"https://zenodo.org/api/records/6643470/files/{name}/content"
        if item["url"] != expected or not re.fullmatch(r"[0-9a-f]{32}", item["md5"]):
            raise ValueError("invalid_public_source")
        if not isinstance(item["bytes"], int) or not 0 < item["bytes"] < 50_000_000:
            raise ValueError("invalid_public_size")
        if item.get("sha256") and not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise ValueError("invalid_public_sha256")
    return manifest


def verify_file(path, item):
    if path.stat().st_size != item["bytes"]:
        raise ValueError("public_size_mismatch")
    md5, sha = hashlib.md5(usedforsecurity=False), hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            md5.update(chunk)
            sha.update(chunk)
    if md5.hexdigest() != item["md5"] or (item.get("sha256") and sha.hexdigest() != item["sha256"]):
        raise ValueError("public_hash_mismatch")
    return sha.hexdigest()


def metadata(path):
    # TIFF headers and OME XML only: no pixels, segmentation or intensity reads.
    import tifffile
    with tifffile.TiffFile(path) as tif:
        root = ET.fromstring(tif.ome_metadata or "")
        ns = {"o": root.tag.split("}")[0][1:]}
        pixels = root.find(".//o:Pixels", ns)
        objective = root.find(".//o:Objective", ns)
        if pixels is None:
            raise ValueError("ome_pixels_missing")
        return {"series_shape": list(tif.series[0].shape), "series_axes": tif.series[0].axes,
                "dtype": str(tif.series[0].dtype), "pages": len(tif.pages),
                "pixels": dict(pixels.attrib),
                "channels": [dict(c.attrib) for c in pixels.findall("o:Channel", ns)],
                "tiff_data": [dict(c.attrib) for c in pixels.findall("o:TiffData", ns)],
                "planes": [dict(c.attrib) for c in pixels.findall("o:Plane", ns)],
                "objective": dict(objective.attrib) if objective is not None else None,
                "acquisition_date": root.findtext(".//o:AcquisitionDate", namespaces=ns)}


def acquire_one(output, item, download):
    target = output / item["name"]
    if target.is_symlink():
        raise ValueError("public_target_symlink")
    if target.exists():
        return verify_file(target, item)  # never replace a mismatching existing file
    if not download:
        raise FileNotFoundError(item["name"])
    with tempfile.NamedTemporaryFile(dir=output, suffix=".partial", delete=False) as temp:
        temporary = Path(temp.name)
    try:
        with urllib.request.urlopen(item["url"], timeout=60) as response, temporary.open("wb") as stream:
            size = 0
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > item["bytes"]:
                    raise ValueError("public_size_exceeded")
                stream.write(chunk)
        digest = verify_file(temporary, item)
        # Exclusive creation preserves any concurrently created target.
        with target.open("xb") as stream, temporary.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                stream.write(chunk)
        verify_file(target, item)
        return digest
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--download", action="store_true")
    mode.add_argument("--verify", action="store_true")
    parser.add_argument("--metadata-samples", action="store_true", help="only the frozen first file of each condition in Rep1")
    args = parser.parse_args()
    output = args.output.resolve()
    if output == ROOT or output.is_relative_to(ROOT):
        parser.error("output must be outside checkout")
    manifest = validate_manifest(json.loads(MANIFEST.read_text(encoding="utf-8")))
    files = [f for f in manifest["files"] if f["metadata_sample"]] if args.metadata_samples else manifest["files"]
    output.mkdir(parents=True, exist_ok=True)
    receipt = {"dataset": manifest["dataset"], "adoption": "pending_owner", "independence": "unconfirmed",
               "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
               "scope": "metadata_samples" if args.metadata_samples else "selected_subset", "files": []}
    for item in files:
        sha = acquire_one(output, item, args.download)
        receipt["files"].append({"name": item["name"], "sha256": sha, "md5_verified": True,
                                 "metadata": metadata(output / item["name"])})
    (output / "verification.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps({"verified_files": len(files), "scope": receipt["scope"], "adoption": receipt["adoption"]}))


if __name__ == "__main__":
    main()
