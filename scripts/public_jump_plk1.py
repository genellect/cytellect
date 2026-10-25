"""Fetch and verify the public JUMP images of the group-comparison browser test (C1).

JUMP Cell Painting cpg0016-jump, source_13 CRISPR plates (CC0 1.0, Cell Painting Gallery):
plates CP-CC9-R1/R2/R3-01 (batches Run1-Run3), wells A02 (non-targeting) and A23 (PLK1),
sites 1-6, channels DNA, RNA, ER and AGP (the browser test uses sites 1-5; the public demo uses DNA and RNA of sites 4-6). The list is fixed in
fixtures/public/jump-plk1/files.json; `--write-list` (re)creates it from the published
load_data mapping and the downloaded bytes. Images are kept outside the checkout.

    python scripts/public_jump_plk1.py --output ../public-jump-plk1          # download and verify
    python scripts/public_jump_plk1.py --output ../public-jump-plk1 --verify # verify only
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LIST = REPO / "fixtures" / "public" / "jump-plk1" / "files.json"
BASE = "https://cellpainting-gallery.s3.amazonaws.com/cpg0016-jump/source_13/images"
RUNS = [("Run1", "20220914_Run1", "R1"), ("Run2", "20221009_Run2", "R2"), ("Run3", "20221017_Run3", "R3")]
WELLS = [("A02", "Non-targeting"), ("A23", "PLK1 KO")]
# JUMP channel → file suffix (load_data URL_Orig* columns).
CHANNELS = [("DNA", "A01Z01C01"), ("RNA", "A02Z01C03"), ("ER", "A03Z01C04"), ("AGP", "A04Z01C05")]
SITES = [1, 2, 3, 4, 5, 6]


def entries():
    for run, batch, tag in RUNS:
        plate = f"CP-CC9-{tag}-01"
        for well, group in WELLS:
            for site in SITES:
                for channel, suffix in CHANNELS:
                    name = f"{plate}_{well}_T0001F{site:03d}L01{suffix}.tif"
                    yield {"run": run, "group": group, "plate": plate, "well": well, "site": site, "channel": channel,
                           "name": name, "url": f"{BASE}/{batch}/images/{plate}/{name}"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--write-list", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if output == REPO or REPO in output.parents:
        raise SystemExit("keep the images outside the checkout")
    output.mkdir(parents=True, exist_ok=True)
    pinned = {} if args.write_list else {item["name"]: item for item in json.loads(LIST.read_text())["files"]}
    files = []
    for item in entries():
        target = output / item["name"]
        if not target.exists():
            if args.verify:
                raise SystemExit(f"missing {item['name']}")
            with urllib.request.urlopen(item["url"], timeout=120) as response:
                target.write_bytes(response.read())
        digest = sha256(target)
        if not args.write_list and pinned[item["name"]]["sha256"] != digest:
            raise SystemExit(f"sha256 mismatch {item['name']}")
        files.append({**item, "sha256": digest, "bytes": target.stat().st_size})
    if args.write_list:
        LIST.write_text(json.dumps({
            "dataset": "JUMP Cell Painting cpg0016-jump source_13 (Cell Painting Gallery)",
            "license": "CC0-1.0", "license_quoted": "All the data is released with CC0 1.0 Universal (CC0 1.0).",
            "use": "Browser test of the two-group workflow (goals C1): entry, missing combinations, one to two "
                   "screens, measurement and statistics. Not an accuracy or biological validation.",
            "files": files}, indent=1) + "\n")
    print(json.dumps({"files": len(files), "bytes": sum(item["bytes"] for item in files)}))


if __name__ == "__main__":
    sys.exit(main())
