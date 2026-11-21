"""Digitisation error of region shape 1.0.0 against object area, on the public demo's adopted masks (#257 RP-02).

The demo seed (apps/web/public/showcase/seed.zip) holds Cytellect's adopted nuclear masks of registered public images:
JUMP Cell Painting cpg0016 (PLK1 scene, CC0) and Zenodo 6643470 DS6a (CC BY 4.0). Large nuclei away from the border are
measured at full resolution, then on the same mask sampled every k-th pixel, which keeps the object's outline but leaves
fewer pixels. The error of circularity, solidity and axis ratio is recorded against the sampled area.

This measures the error of the shape formulas on pixel grids only. It says nothing about segmentation error of small,
dim objects, which needs independent hand-drawn outlines (requirement NS-03).

The tolerance is fixed here before the data are read: the 90th percentile of |Δ circularity| ≤ 0.05, of |Δ solidity| ≤
0.05 and of |Δ axis ratio| / axis ratio ≤ 0.10, in an area bin and every larger bin. The minimum area is chosen on the
PLK1 (JUMP) nuclei only and then checked, unchanged, on the DS6a nuclei, which play no part in choosing it.

Eccentricity (|Δ| ≤ 0.05) was added after the first run, before its values were read. It is reported per bin
but takes no part in choosing the minimum area.

    uv run python scripts/evaluate_shape_minimum_area.py [--seed apps/web/public/showcase/seed.zip]
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path

import numpy as np
from cytellect_analysis.region_shape import region_shapes
from scipy.ndimage import label

TOLERANCE = {"circularity": 0.05, "solidity": 0.05, "axis_ratio_relative": 0.10}
REPORTED = {"eccentricity": 0.05}
QUANTILE = 0.90
REFERENCE_MINIMUM_AREA = 400
FACTORS = (2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16, 20)
BINS = (4, 8, 16, 24, 32, 48, 64, 96, 128, 256)
TUNING, EVALUATION = "cpg0016-jump-source13-plk1", "zenodo-6643470"


def nuclear_masks(seed: Path) -> dict[str, list[np.ndarray]]:
    """Unique adopted nuclear label images per dataset (by content hash)."""
    root = seed.parents[0]
    scenes = json.loads((root / "snapshot/scenes.json").read_text())["scenes"]
    by_workspace = {scene["workspaceId"]: scene["id"] for scene in scenes}
    masks: dict[str, list[np.ndarray]] = {}
    seen: set[str] = set()
    with zipfile.ZipFile(seed) as archive:
        names = set(archive.namelist())
        # Each field belongs to one workspace (workspaces/<workspace>/fields/<field>/), and each workspace to one scene.
        dataset = {parts[3]: by_workspace.get(parts[1], "") for parts in (name.split("/") for name in names)
                   if len(parts) > 4 and parts[0] == "workspaces" and parts[2] == "fields"}
        for name in sorted(names):
            if not name.endswith("output/measurements.json"):
                continue
            if json.loads(archive.read(name))["recipe"].get("region_set_id") != "nuclei":
                continue
            folder = name.rsplit("/", 1)[0]
            for labels_name in sorted(value for value in names if value.startswith(folder + "/") and value.endswith("/labels.npy")):
                data = archive.read(labels_name)
                digest = hashlib.sha256(data).hexdigest()
                if digest in seen:
                    continue
                seen.add(digest)
                field = labels_name.rsplit("/", 2)[-2]
                scene = dataset.get(field, "")
                key = TUNING if scene == TUNING else EVALUATION if scene.startswith(EVALUATION) else "other"
                masks.setdefault(key, []).append(np.load(io.BytesIO(data), allow_pickle=False))
    return masks


def errors(masks: list[np.ndarray]) -> list[dict]:
    """One record per (reference nucleus, factor) whose sampled object still has shape values."""
    records = []
    for labels in masks:
        reference = {row["region_id"]: row for row in region_shapes(labels, minimum_area_px=1)["rows"]
                     if row["missing_reason"] is None and row["area_px"] >= REFERENCE_MINIMUM_AREA}
        for factor in FACTORS:
            offset = factor // 2
            sampled = np.ascontiguousarray(labels[offset::factor, offset::factor])
            for row in region_shapes(sampled, minimum_area_px=1)["rows"]:
                full = reference.get(row["region_id"])
                # A sampled nucleus split into pieces is not one object any more: it is left out.
                if full is None or row["missing_reason"] is not None or label(sampled == row["region_id"])[1] != 1:
                    continue
                records.append({"area_px": row["area_px"], "factor": factor,
                                "circularity": abs(row["circularity"] - full["circularity"]),
                                "solidity": abs(row["solidity"] - full["solidity"]),
                                "axis_ratio_relative": abs(row["axis_ratio"] - full["axis_ratio"]) / full["axis_ratio"],
                                "eccentricity": abs(row["eccentricity"] - full["eccentricity"])})
    return records


def summary(records: list[dict]) -> list[dict]:
    rows = []
    for low, high in zip(BINS, (*BINS[1:], None), strict=True):
        inside = [record for record in records if record["area_px"] >= low and (high is None or record["area_px"] < high)]
        row = {"area_from_px": low, "area_below_px": high, "objects": len(inside)}
        for key in (*TOLERANCE, *REPORTED):
            row[f"{key}_p90"] = float(np.quantile([record[key] for record in inside], QUANTILE)) if inside else None
        row["within_tolerance"] = bool(inside) and all(row[f"{key}_p90"] <= limit for key, limit in TOLERANCE.items())
        for key, limit in {**TOLERANCE, **REPORTED}.items():
            row[f"{key}_within"] = bool(inside) and row[f"{key}_p90"] <= limit
        rows.append(row)
    return rows


def minimum_area(rows: list[dict]) -> int | None:
    """The smallest bin edge from which this bin and every larger bin with objects are within tolerance."""
    for index, row in enumerate(rows):
        later = [value for value in rows[index:] if value["objects"]]
        if later and all(value["within_tolerance"] for value in later):
            return row["area_from_px"]
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=Path, default=Path("apps/web/public/showcase/seed.zip"))
    args = parser.parse_args()
    masks = nuclear_masks(args.seed)
    tuning = summary(errors(masks.get(TUNING, [])))
    chosen = minimum_area(tuning)
    evaluation = summary(errors(masks.get(EVALUATION, [])))
    held_out = [row for row in evaluation if row["objects"] and chosen is not None and row["area_from_px"] >= chosen]
    print(json.dumps({"protocol": "region-shape/1.0.0", "tolerance": TOLERANCE, "reported": REPORTED, "quantile": QUANTILE,
                      "masks": {key: len(value) for key, value in masks.items()},
                      "tuning": {"dataset": TUNING, "bins": tuning, "minimum_area_px": chosen},
                      "evaluation": {"dataset": EVALUATION, "bins": evaluation,
                                     "within_tolerance_from_minimum": bool(held_out) and all(row["within_tolerance"] for row in held_out)}},
                     indent=1))


if __name__ == "__main__":
    main()
