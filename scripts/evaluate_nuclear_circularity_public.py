"""Digitisation error of nuclear circularity 4πA/P² on public nucleus masks (genellect/cytellect#257 E-1, decision 5).

The other nuclear shape metrics (solidity, axis ratio, eccentricity; nuclear-features/1.0.0) take their 96 px minimum
area from the check of genellect/cytellect#258 (``scripts/evaluate_shape_minimum_area.py`` on that branch, recorded in
its docs/methods.md "Region shape 1.0.0"). This script applies that check, with its rules unchanged, to circularity
alone, so that circularity is offered for nuclei only under the same procedure as the other three.

Rules, fixed in this file before it was run on the current demo seed (the #258 record already reported circularity on
the #258 seed, so the evaluation set is not blind for circularity; see docs/public-nuclear-circularity-validation.md):

1. Perimeter estimator: the Crofton estimate with 4 directions on the object's binary image (scikit-image
   ``regionprops(...).perimeter_crofton``, which is ``perimeter_crofton(image, directions=4)``), in pixels. Circularity
   is ``4πA / P²`` with ``A`` the pixel count. No clipping. One estimator only: no other estimator, number of
   directions or clipping is tried on these data.
2. Masks: the adopted nuclear label images of the public demo seed (unique by content hash), as in #258. Tuning set:
   JUMP cpg0016 (PLK1 scene, CC0). Evaluation set: Zenodo 6643470 DS6a (CC BY 4.0) nuclei.
3. Reference objects: nuclei of at least 400 px that do not touch the image border. Each mask is sampled every k-th
   pixel (k = 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16, 20; offset k // 2), which keeps the outline and leaves fewer pixels. A
   sampled nucleus that touches the border, has a zero perimeter or minor axis, or is no longer one 4-connected piece
   is left out. The error is |circularity(sampled) − circularity(reference)| against the sampled area.
4. Tolerance: the 90th percentile of the error ≤ 0.05 in an area bin (bins from 4, 8, 16, 24, 32, 48, 64, 96, 128 and
   256 px), the #258 tolerance for circularity.
5. Circularity's minimum area is chosen on the tuning set only: the smallest bin edge from which this bin and every
   larger bin with objects are within tolerance. The minimum used for circularity is the larger of that edge and the
   96 px of the other nuclear shape metrics.
6. Circularity passes when the tuning set gives a minimum, and on the evaluation set every bin with objects at or
   above that minimum is within tolerance and at least one such bin exists. Otherwise it fails and is not offered.
7. Reported only, no part in the verdict: the same error on the registered BBBC039 manual nucleus annotations (CC0,
   fixtures/public/bbbc039); the #258 joint table of solidity, axis ratio and eccentricity (to check that this script
   reproduces #258); and the agreement of scikit-image's Crofton perimeter with an independent count of boundary
   crossings along the four line families (agreement: relative difference ≤ 1e-9 for every object of every mask).
8. Reproduction: run on the #258 seed (``git show 3edab2001:apps/web/public/showcase/seed.zip`` and its
   ``snapshot/scenes.json``), this script must give the #258 mask counts (JUMP 18, DS6a 29) and circularity p90 at
   96–128 px (JUMP 0.048, DS6a 0.208, three decimals). If it does not, no verdict is drawn from either seed.

This measures the formula on pixel grids only. Re-detection at a coarser pixel size (the 2 x 2 check of the nucleolar
record) needs the Fiji StarDist detector and is not part of this script; it is not needed for a verdict of "fails".

    uv run python -I scripts/evaluate_nuclear_circularity_public.py [--seed …/seed.zip] [--scenes …/scenes.json] \
        [--out fixtures/public/nuclear-circularity/summary.json]
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import math
import zipfile
from pathlib import Path

import numpy as np
from scipy.ndimage import label

ROOT = Path(__file__).resolve().parents[1]
PERIMETER_ESTIMATOR = "crofton-4"
TOLERANCE = {"circularity": 0.05}
# The #258 joint check, reported to show that this script reproduces it.
JOINT_TOLERANCE = {"circularity": 0.05, "solidity": 0.05, "axis_ratio_relative": 0.10}
REPORTED = {"eccentricity": 0.05}
QUANTILE = 0.90
REFERENCE_MINIMUM_AREA = 400
OTHER_SHAPE_MINIMUM_AREA = 96
FACTORS = (2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16, 20)
BINS = (4, 8, 16, 24, 32, 48, 64, 96, 128, 256)
TUNING, EVALUATION = "cpg0016-jump-source13-plk1", "zenodo-6643470"
CROFTON_AGREEMENT = 1e-9
# SHA-256 of the #258 seed (git show 3edab2001:apps/web/public/showcase/seed.zip).
SEED_258_SHA256 = "f967ce59c7a274bffa962ce33010d16ef03366240075e86ee9e21c2cc1932693"
REPRODUCTION = {"masks": {TUNING: 18, EVALUATION: 29}, "circularity_p90_96": {TUNING: 0.048, EVALUATION: 0.208}}


def region_shapes(labels: np.ndarray) -> list[dict]:
    """Shape values of every label (ascending, minimum area 1 px), as in the #258 region-shape/1.0.0 check.

    Solidity, axis ratio, eccentricity and the border and degenerate rules are the shared implementation's
    (``nuclear_features.nuclear_shapes``); only the Crofton perimeter and circularity are added here. A nucleus with a
    zero or non-finite perimeter is ``degenerate``, as in #258.
    """
    from cytellect_analysis.nuclear_features import nuclear_shapes
    from skimage.measure import regionprops

    shared = nuclear_shapes(labels, minimum_area_px=1)
    # regionprops makes one slot per label value: compact sparse saved IDs first, as the shared implementation does.
    present = np.unique(labels[labels > 0])
    compact = np.zeros(labels.shape, np.int64)
    compact[labels > 0] = np.searchsorted(present, labels[labels > 0]) + 1
    perimeters = {int(present[region.label - 1]): float(region.perimeter_crofton) for region in regionprops(compact)}
    rows = []
    for rid, values in sorted(shared.items()):
        row = {"region_id": rid, "area_px": values["area_px"], "perimeter_px": None, "circularity": None,
               "solidity": values["solidity"], "axis_ratio": values["axis_ratio"],
               "eccentricity": values["eccentricity"], "missing_reason": values["missing_reason"]}
        perimeter = perimeters[rid]
        if row["missing_reason"] is None:
            if not perimeter > 0 or not math.isfinite(perimeter):
                row.update(missing_reason="degenerate", solidity=None, axis_ratio=None, eccentricity=None)
            else:
                row.update(perimeter_px=perimeter, circularity=4 * math.pi * row["area_px"] / perimeter ** 2)
        rows.append(row)
    return rows


def crossings_perimeter(mask: np.ndarray) -> float:
    """Independent Crofton estimate: boundary crossings along rows, columns and both diagonals of the padded mask.

    Cauchy-Crofton with 4 directions of weight π/4, line spacing 1 (rows, columns) and 1/√2 (diagonals):
    P = (π/8) (n_0 + n_90 + (n_45 + n_135) / √2).
    """
    padded = np.pad(mask.astype(np.int8), 1)
    rows = np.count_nonzero(padded[:, 1:] != padded[:, :-1])
    columns = np.count_nonzero(padded[1:, :] != padded[:-1, :])
    diagonal = np.count_nonzero(padded[1:, 1:] != padded[:-1, :-1])
    anti = np.count_nonzero(padded[1:, :-1] != padded[:-1, 1:])
    return math.pi / 8 * (rows + columns + (diagonal + anti) / math.sqrt(2))


def database_scenes(seed: Path, scenes_path: Path) -> dict[str, str]:
    """Field ID -> scene ID from the seed's database (``fields.workspace_id``), for fields the archive paths miss."""
    import sqlite3
    import tempfile

    scenes = json.loads(scenes_path.read_text(encoding="utf-8"))["scenes"]
    by_workspace = {scene["workspaceId"]: scene["id"] for scene in scenes}
    with tempfile.TemporaryDirectory() as folder, zipfile.ZipFile(seed) as archive:
        path = Path(folder) / "cytellect.sqlite"
        path.write_bytes(archive.read("cytellect.sqlite"))
        connection = sqlite3.connect(path)
        try:
            rows = connection.execute("select id, workspace_id from fields").fetchall()
        finally:
            connection.close()
    return {field: by_workspace.get(workspace, "") for field, workspace in rows}


def nuclear_masks(seed: Path, scenes_path: Path, fallback: dict[str, str] | None = None) -> dict[str, list[np.ndarray]]:
    """Unique adopted nuclear label images per dataset (by content hash), as in #258.

    The dataset of a mask is the scene of the workspace whose archive path holds its field (#258). With ``fallback``
    (reported only), a field no archive path holds takes its scene from the database instead.
    """
    scenes = json.loads(scenes_path.read_text(encoding="utf-8"))["scenes"]
    by_workspace = {scene["workspaceId"]: scene["id"] for scene in scenes}
    masks: dict[str, list[np.ndarray]] = {}
    seen: set[str] = set()
    with zipfile.ZipFile(seed) as archive:
        names = set(archive.namelist())
        dataset = {parts[3]: by_workspace.get(parts[1], "") for parts in (name.split("/") for name in names)
                   if len(parts) > 4 and parts[0] == "workspaces" and parts[2] == "fields"}
        for name in sorted(names):
            if not name.endswith("output/measurements.json"):
                continue
            if json.loads(archive.read(name))["recipe"].get("region_set_id") != "nuclei":
                continue
            folder = name.rsplit("/", 1)[0]
            for labels_name in sorted(value for value in names
                                      if value.startswith(folder + "/") and value.endswith("/labels.npy")):
                data = archive.read(labels_name)
                digest = hashlib.sha256(data).hexdigest()
                if digest in seen:
                    continue
                seen.add(digest)
                field = labels_name.rsplit("/", 2)[-2]
                scene = dataset.get(field) or (fallback or {}).get(field, "")
                key = TUNING if scene == TUNING else EVALUATION if scene.startswith(EVALUATION) else "other"
                masks.setdefault(key, []).append(np.load(io.BytesIO(data), allow_pickle=False))
    return masks


def bbbc039_masks() -> list[np.ndarray]:
    source = ROOT / "scripts/public_bbbc039.py"
    spec = importlib.util.spec_from_file_location("public_bbbc039", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest = module.verify()
    return [module.decode_ground_truth(module.FIXTURE / item["mask"]["path"]).astype(np.int64)
            for item in manifest["images"]]


def errors(masks: list[np.ndarray]) -> list[dict]:
    """One record per (reference nucleus, factor) whose sampled object still has shape values."""
    records = []
    for labels in masks:
        reference = {row["region_id"]: row for row in region_shapes(labels)
                     if row["missing_reason"] is None and row["area_px"] >= REFERENCE_MINIMUM_AREA}
        for factor in FACTORS:
            offset = factor // 2
            sampled = np.ascontiguousarray(labels[offset::factor, offset::factor])
            for row in region_shapes(sampled):
                full = reference.get(row["region_id"])
                if full is None or row["missing_reason"] is not None or label(sampled == row["region_id"])[1] != 1:
                    continue
                records.append({"area_px": row["area_px"], "factor": factor,
                                "circularity": abs(row["circularity"] - full["circularity"]),
                                "solidity": abs(row["solidity"] - full["solidity"]),
                                "axis_ratio_relative": abs(row["axis_ratio"] - full["axis_ratio"]) / full["axis_ratio"],
                                "eccentricity": abs(row["eccentricity"] - full["eccentricity"])})
    return records


def summary(records: list[dict], tolerance: dict[str, float]) -> list[dict]:
    rows = []
    for low, high in zip(BINS, (*BINS[1:], None), strict=True):
        inside = [record for record in records if record["area_px"] >= low and (high is None or record["area_px"] < high)]
        row = {"area_from_px": low, "area_below_px": high, "objects": len(inside)}
        for key in (*JOINT_TOLERANCE, *REPORTED):
            row[f"{key}_p90"] = float(np.quantile([record[key] for record in inside], QUANTILE)) if inside else None
        row["within_tolerance"] = bool(inside) and all(row[f"{key}_p90"] <= limit for key, limit in tolerance.items())
        rows.append(row)
    return rows


def minimum_area(rows: list[dict]) -> int | None:
    """The smallest bin edge from which this bin and every larger bin with objects are within tolerance."""
    for index, row in enumerate(rows):
        later = [value for value in rows[index:] if value["objects"]]
        if row["objects"] and all(value["within_tolerance"] for value in later):
            return row["area_from_px"]
    return None


def reference_circularity(masks: list[np.ndarray]) -> dict:
    """Circularity of the reference nuclei at full resolution (distribution only)."""
    values = [row["circularity"] for labels in masks for row in region_shapes(labels)
              if row["missing_reason"] is None and row["area_px"] >= REFERENCE_MINIMUM_AREA]
    if not values:
        return {"nuclei": 0}
    quantiles = np.quantile(values, (0.1, 0.5, 0.9))
    return {"nuclei": len(values), "p10": float(quantiles[0]), "median": float(quantiles[1]),
            "p90": float(quantiles[2]), "max": float(max(values)), "above_one": int(sum(value > 1 for value in values))}


def crofton_agreement(masks: list[np.ndarray]) -> dict:
    from skimage.measure import regionprops

    worst, objects = 0.0, 0
    for labels in masks:
        for region in regionprops(labels.astype(np.int64)):
            estimate = float(region.perimeter_crofton)
            independent = crossings_perimeter(region.image)
            worst = max(worst, abs(estimate - independent) / max(independent, 1e-300))
            objects += 1
    return {"objects": objects, "max_relative_difference": float(worst), "agree": bool(worst <= CROFTON_AGREEMENT)}


def at_96(rows: list[dict]) -> float | None:
    return next((row["circularity_p90"] for row in rows if row["area_from_px"] == 96), None)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=Path, default=ROOT / "apps/web/public/showcase/seed.zip")
    parser.add_argument("--scenes", type=Path, default=None, help="scenes.json of the seed (default: beside it)")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    scenes = args.scenes or args.seed.parent / "snapshot/scenes.json"
    masks = nuclear_masks(args.seed, scenes)
    tuning_records, evaluation_records = errors(masks.get(TUNING, [])), errors(masks.get(EVALUATION, []))
    tuning = summary(tuning_records, TOLERANCE)
    found = minimum_area(tuning)
    chosen = None if found is None else max(found, OTHER_SHAPE_MINIMUM_AREA)
    evaluation = summary(evaluation_records, TOLERANCE)
    held_out = [row for row in evaluation if row["objects"] and chosen is not None and row["area_from_px"] >= chosen]
    passed = chosen is not None and bool(held_out) and all(row["within_tolerance"] for row in held_out)
    bbbc039 = bbbc039_masks()
    joint_tuning = summary(tuning_records, JOINT_TOLERANCE)
    joint_evaluation = summary(evaluation_records, JOINT_TOLERANCE)
    counts = {key: len(value) for key, value in masks.items()}
    reproduced = {
        "masks": {key: counts.get(key) for key in REPRODUCTION["masks"]},
        "circularity_p90_96": {TUNING: at_96(tuning), EVALUATION: at_96(evaluation)},
    }
    seed_sha256 = hashlib.sha256(args.seed.read_bytes()).hexdigest()
    # Rule 8 is read on the #258 seed only; on another seed the values are shown beside #258's without a verdict.
    reproduced["is_258_seed"] = seed_sha256 == SEED_258_SHA256
    reproduced["matches_258"] = None if not reproduced["is_258_seed"] else (
        reproduced["masks"] == REPRODUCTION["masks"]
        and all(value is not None and round(value, 3) == REPRODUCTION["circularity_p90_96"][key]
                for key, value in reproduced["circularity_p90_96"].items()))
    # Reported only: masks whose field no archive path holds, placed by the database (rule 2 leaves them out).
    with_unmapped = nuclear_masks(args.seed, scenes, database_scenes(args.seed, scenes))
    unmapped_bins = summary(errors(with_unmapped.get(EVALUATION, [])), TOLERANCE)
    unmapped_held_out = [row for row in unmapped_bins
                         if row["objects"] and chosen is not None and row["area_from_px"] >= chosen]
    result = {
        "protocol": "nuclear-circularity-check/1.0.0", "perimeter_estimator": PERIMETER_ESTIMATOR,
        "tolerance": TOLERANCE, "quantile": QUANTILE, "reference_minimum_area_px": REFERENCE_MINIMUM_AREA,
        "factors": FACTORS, "bins": BINS,
        "seed_sha256": seed_sha256, "masks": counts,
        "tuning": {"dataset": TUNING, "bins": tuning, "circularity_minimum_area_px": found,
                   "minimum_area_used_px": chosen, "reference": reference_circularity(masks.get(TUNING, []))},
        "evaluation": {"dataset": EVALUATION, "bins": evaluation, "passed": passed,
                       "reference": reference_circularity(masks.get(EVALUATION, []))},
        "reported": {
            "bbbc039_manual": {"masks": len(bbbc039), "bins": summary(errors(bbbc039), TOLERANCE),
                               "reference": reference_circularity(bbbc039)},
            "joint_258": {"tuning_minimum_area_px": minimum_area(joint_tuning), "tuning": joint_tuning,
                          "evaluation": joint_evaluation},
            "crofton_agreement": crofton_agreement([*masks.get(TUNING, []), *masks.get(EVALUATION, []), *bbbc039]),
            "reproduction_of_258": reproduced,
            "evaluation_with_unmapped_masks": {
                "masks": {key: len(value) for key, value in with_unmapped.items()}, "bins": unmapped_bins,
                "within_tolerance_from_minimum": bool(unmapped_held_out)
                and all(row["within_tolerance"] for row in unmapped_held_out),
                "reference": reference_circularity(with_unmapped.get(EVALUATION, []))},
        },
    }
    text = json.dumps(result, indent=1, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
