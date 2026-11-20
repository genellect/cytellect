"""Nuclear pixel CV and positive-area fraction on public original images, against an independent count (#257 NS-02).

The demo seed (apps/web/public/showcase/seed.zip) holds the registered public DS6a images (Zenodo 6643470, CC BY 4.0:
Hoechst, NPM1, 5-EU) with Cytellect's adopted nuclear masks. For every adopted nuclear mask and every stained channel:

- nuclear-signal/1.0.0 and region-features/1.0.0 (`field_features`, the implementation statistics use) give each
  nucleus's raw mean, population SD, CV and positive-area fraction with the field's Otsu threshold;
- an independent calculation (scipy.ndimage per-label mean and variance; positive pixels counted with numpy at the same
  recorded threshold) gives the same quantities.

The check passes when every value agrees within 1e-9 (relative) and both have the same missing nuclei. NCL is not among
the registered channels: the NCL area fraction of NS-02 needs another public source (#257 F-6).

    uv run python scripts/check_nuclear_signal_public.py [--seed apps/web/public/showcase/seed.zip]
"""
from __future__ import annotations

import argparse
import io
import json
import tempfile
import zipfile
from pathlib import Path

import numpy as np
from cytellect_analysis.images import read_tiff
from cytellect_analysis.nuclear_signal import nuclear_signal
from cytellect_analysis.region_features import field_features
from cytellect_analysis.regions import _array_hash
from scipy import ndimage

DATASET = "zenodo-6643470"


def _workspaces(root: Path) -> set[str]:
    scenes = json.loads((root / "snapshot/scenes.json").read_text())["scenes"]
    return {scene["workspaceId"] for scene in scenes if scene["id"].startswith(DATASET)}


def _independent(labels: np.ndarray, image: np.ndarray, threshold: float | None, excluded: set[int]):
    ids = [int(value) for value in np.unique(labels) if value and int(value) not in excluded]
    pixels = image.astype(np.float64)
    means = ndimage.mean(pixels, labels, ids)
    variances = ndimage.variance(pixels, labels, ids)
    counts = ndimage.sum(np.ones_like(pixels), labels, ids)
    positive = ndimage.sum(pixels >= threshold, labels, ids) if threshold is not None else [None] * len(ids)
    return {rid: (float(mean), float(np.sqrt(var)), float(np.sqrt(var)) / float(mean) if mean > 0 else None,
                  None if hit is None else float(hit) / float(count))
            for rid, mean, var, count, hit in zip(ids, means, variances, counts, positive, strict=True)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=Path, default=Path("apps/web/public/showcase/seed.zip"))
    args = parser.parse_args()
    workspaces = _workspaces(args.seed.parent)
    summary = {"fields": 0, "channels": {}, "nuclei_compared": 0, "max_relative_difference": 0.0,
               "missing_mismatches": 0, "seen_masks": 0}
    seen: set[str] = set()
    with zipfile.ZipFile(args.seed) as archive, tempfile.TemporaryDirectory() as scratch:
        names = set(archive.namelist())
        fields = {}
        for name in names:
            parts = name.split("/")
            if len(parts) == 5 and parts[0] == "workspaces" and parts[2] == "fields" and parts[1] in workspaces:
                fields.setdefault(parts[3], (parts[1], []))[1].append(name)
        for name in sorted(names):
            if not name.endswith("measurements.json"):
                continue
            report = json.loads(archive.read(name))
            if report.get("recipe", {}).get("region_set_id") != "nuclei":
                continue
            folder = name.rsplit("/", 1)[0]
            for fid, table in sorted(report.get("field_tables", {}).items()):
                labels_name = f"{folder}/{fid}/labels.npy"
                if fid not in fields or labels_name not in names:
                    continue
                labels = np.load(io.BytesIO(archive.read(labels_name)), allow_pickle=False)
                key = f"{fid}:{_array_hash(labels, '<u4')}"
                if key in seen:
                    continue
                seen.add(key)
                summary["seen_masks"] += 1
                excluded = {int(item["region_id"]) for item in report.get("exclusions", [])
                            if item.get("field_id") == fid and item.get("region_id") is not None}
                tiffs = {}
                for tif in sorted(value for value in fields[fid][1] if value.endswith(".tif")):
                    path = Path(scratch) / tif.replace("/", "_")
                    path.write_bytes(archive.read(tif))
                    image = read_tiff(path)
                    tiffs[_array_hash(image, "|u1" if image.dtype.itemsize == 1 else "<u2")] = image
                summary["fields"] += 1
                for provenance in table["channel_provenance"]:
                    image = tiffs.get(provenance["pixel_sha256"])
                    if image is None or image.shape != labels.shape:
                        continue
                    stain = provenance["channel"].get("stain") or provenance["channel"]["label"]
                    rows = {row["nucleus_id"]: row for row in nuclear_signal(labels, image, excluded=frozenset(excluded))["rows"]}
                    cv = field_features(labels, "cv", image=image, excluded=frozenset(excluded))["values"]
                    positive = field_features(labels, "positive_area_fraction", image=image, excluded=frozenset(excluded))
                    threshold = positive["threshold"]["value"]
                    reference = _independent(labels, image, threshold, excluded)
                    summary["channels"][stain] = summary["channels"].get(stain, 0) + len(reference)
                    for rid, (ref_mean, ref_sd, ref_cv, ref_fraction) in reference.items():
                        ours = (rows[rid]["mean"], rows[rid]["sd"], cv[rid]["value"], positive["values"][rid]["value"])
                        for mine, theirs in zip(ours, (ref_mean, ref_sd, ref_cv, ref_fraction), strict=True):
                            if (mine is None) != (theirs is None):
                                summary["missing_mismatches"] += 1
                            elif mine is not None and theirs is not None:
                                difference = abs(mine - theirs) / max(abs(theirs), 1e-12)
                                summary["max_relative_difference"] = max(summary["max_relative_difference"], difference)
                        summary["nuclei_compared"] += 1
    summary["passed"] = (summary["nuclei_compared"] > 0 and summary["missing_mismatches"] == 0
                         and summary["max_relative_difference"] <= 1e-9)
    print(json.dumps(summary, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
