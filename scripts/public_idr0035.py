"""Acquire the preregistered IDR0035 candidate without changing image pixels.

First-use --register-hashes records trust-on-first-HTTPS-download checksums.
They are not publisher checksums. Subsequent downloads require exact matches.
This script does not segment, measure, or select images by their appearance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "fixtures/public/group-comparison/idr0035-manifest.json"
BASE = "https://ftp.ebi.ac.uk/pub/databases/IDR/idr0035-caie-drugresponse/images/Week1_22123/"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--register-hashes", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if output == ROOT or output.is_relative_to(ROOT):
        parser.error("output must be outside checkout")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest["license"] != "CC-BY-4.0" or len(manifest["files"]) != 18:
        raise ValueError("unexpected_candidate_manifest")
    names = set()
    for item in manifest["files"]:
        name = item["name"]
        if not re.fullmatch(r"Week1_150607_B(?:02|11)_s[123]_w[124][A-F0-9-]{36}\.tif", name):
            raise ValueError("invalid_public_filename")
        if name in names or item["url"] != BASE + name:
            raise ValueError("invalid_public_source")
        names.add(name)
        if not item["sha256"] and not args.register_hashes:
            raise ValueError("unregistered_checksum")
    output.mkdir(parents=True, exist_ok=True)
    receipt = {"dataset": manifest["dataset"], "adoption": "pending_owner", "files": []}
    import tifffile
    for item in manifest["files"]:
        path = output / item["name"]
        if path.is_symlink():
            raise ValueError("public_target_symlink")
        if not path.exists():
            if not args.download:
                raise FileNotFoundError(item["name"])
            with urllib.request.urlopen(item["url"], timeout=60) as response:
                data = response.read(8_000_001)
            if len(data) > 8_000_000:
                raise ValueError("unexpected_public_size")
        else:
            data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if item["sha256"] and (digest != item["sha256"] or len(data) != item["bytes"]):
            raise ValueError("public_hash_mismatch")
        if not path.exists():
            with path.open("xb") as stream:
                stream.write(data)
        # Header inspection only, no pixel decode or phenotype measurement.
        with tifffile.TiffFile(path) as tif:
            header = {"shape": list(tif.series[0].shape), "dtype": str(tif.series[0].dtype),
                      "axes": tif.series[0].axes, "pages": len(tif.pages)}
        if args.register_hashes and not item["sha256"]:
            item.update(sha256=digest, bytes=len(data), header=header)
        receipt["files"].append({"name": item["name"], "sha256": digest,
                                 "bytes": len(data), "header": header})
    if args.register_hashes:
        MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    receipt["manifest_sha256"] = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    (output / "verification.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verified_files": len(receipt["files"]), "adoption": "pending_owner"}))


if __name__ == "__main__":
    main()
