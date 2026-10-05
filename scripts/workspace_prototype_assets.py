"""Build the public BBBC013 data used by the workspace prototype's simulated adapter.

Inputs are the registered fixtures and recorded Fiji outputs only: the three
published BBBC013 wells, their benchmark measurements and the A01 outlines from
the public sample viewer. No detection or measurement is performed here.
Previews are display-scaled (1st-99.8th percentile) and never used for values.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import tifffile
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/public/bbbc013"
DEMO = ROOT / "apps/web/public/demo/bbbc013/data.json"
OUTPUT = ROOT / "apps/web/public/prototype/bbbc013"
ALLOWLIST = ROOT / "fixtures/public/allowlist.json"


def _preview(array: np.ndarray) -> bytes:
    low, high = np.percentile(array, [1, 99.8])
    scaled = np.uint8(np.clip((array.astype(float) - low) / max(high - low, 1), 0, 1) * 255)
    buffer = io.BytesIO()
    Image.fromarray(scaled).save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def build() -> dict[str, bytes]:
    manifest = json.loads((FIXTURE / "manifest.json").read_text(encoding="utf-8"))
    benchmark = {field["id"]: field for field in json.loads((FIXTURE / "benchmark.json").read_text(encoding="utf-8"))["fields"]}
    demo = json.loads(DEMO.read_text(encoding="utf-8"))
    files: dict[str, bytes] = {}
    fields = []
    for image in manifest["images"]:
        well = image["id"]
        channels = []
        for role, item in image["channels"].items():
            values = tifffile.imread(FIXTURE / item["path"])
            name = f"{well}-{role}.png"
            files[name] = _preview(values)
            channels.append({
                "source_name": item["source_member"].rsplit("/", 1)[-1],
                "stain": item["stain"], "recorded_role": role, "preview": f"/prototype/bbbc013/{name}",
                "dtype": item["dtype"], "shape": item["shape"], "sha256": item["sha256"],
            })
        rows = [{"region_id": row["id"], "area_px": row["area"], "gfp_mean_raw": row["gfp_raw_mean"],
                 "gfp_integral_raw": row["gfp_raw_integrated"]} for row in benchmark[well]["rows"]]
        fields.append({
            "well": well, "width": image["channels"]["gfp"]["shape"][1], "height": image["channels"]["gfp"]["shape"][0],
            "channels": channels, "measurements": rows,
            "outlines": demo["labels"] if well == demo["image_id"] else None,
        })
    payload = {
        "dataset": manifest["dataset"], "source": manifest["source"], "license": manifest["license"],
        "license_url": manifest["license_url"], "attribution": manifest["attribution"],
        "measurement_source": "Recorded Fiji/StarDist outputs from fixtures/public/bbbc013/benchmark.json; "
                              "same-mask ImageJ agreement only, not segmentation accuracy.",
        "outline_scope": "Outlines are available for A01 only (public sample viewer).",
        "display_transform": {"per_channel_percentiles": [1, 99.8]},
        "fields": fields,
    }
    files["fields.json"] = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    return files


def _same(path: Path, data: bytes) -> bool:
    """PNG bytes depend on the zlib build; compare decoded pixels instead."""
    if not path.exists():
        return False
    if path.suffix != ".png":
        return path.read_bytes() == data
    with Image.open(path) as current, Image.open(io.BytesIO(data)) as expected:
        return current.mode == expected.mode and np.array_equal(np.asarray(current), np.asarray(expected))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if committed files differ")
    args = parser.parse_args()
    files = build()
    allowlist = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    changed = []
    for name, data in files.items():
        path = OUTPUT / name
        if not _same(path, data):
            changed.append(name)
            if not args.check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        if name.endswith(".png") and path.exists():
            # The registry records the committed bytes, whichever zlib produced them.
            key = path.relative_to(ROOT).as_posix()
            entry = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                     "source": "https://bbbc.broadinstitute.org/BBBC013", "license": "CC-BY-3.0"}
            if allowlist.get(key) != entry:
                changed.append(key)
                allowlist[key] = entry
    if args.check and changed:
        raise SystemExit("Workspace prototype assets are stale: " + ", ".join(changed))
    if not args.check:
        ALLOWLIST.write_text(json.dumps(allowlist, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Workspace prototype assets {'verified' if args.check else 'written'}: {len(files)} files.")


if __name__ == "__main__":
    main()
