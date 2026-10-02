"""Independent ImageJ arithmetic check on separately acquired public NCL images."""
import argparse
import json
from pathlib import Path

import numpy as np
import tifffile
from cytellect_analysis.contracts import Recipe
from cytellect_analysis.measurement import measure
from public_bbbc013 import digest, imagej_reference, reference_offset


def evaluate(image, masks, output, fiji):
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "fixtures/public/nucleolar/manifest.json").read_text())
    if digest(image.read_bytes()) != manifest["sha256"]:
        raise ValueError("public_ncl_source_hash_mismatch")
    array = tifffile.imread(image)
    roles = manifest["schema"]["channel_map"]
    channels = {role: array[index] for role, index in roles.items()}
    with np.load(masks, allow_pickle=False) as labels:
        nuclei, nucleoli = labels["nuclei"], labels["nucleoli"]
    offset, offset_rect = reference_offset(nuclei)
    recipe = Recipe(gfp_gate="none")
    cells, objects, _ = measure(channels, nuclei, nucleoli, offset, recipe, {}, manifest["accession"])
    output.mkdir(parents=True, exist_ok=True)
    raw_path = (output / "original-ncl-plane.tif").resolve()
    tifffile.imwrite(raw_path, channels["ncl"], photometric="minisblack", metadata=None)
    records = []
    compartment_masks = {"nucleus": nuclei, "nucleoli": np.where(nucleoli > 0, nuclei, 0),
                         "nucleoplasm": np.where(nucleoli == 0, nuclei, 0), "object": nucleoli}
    for compartment, labels in compartment_masks.items():
        combined = labels.astype(np.uint32).copy()
        combined[offset] = 999999
        reference = imagej_reference(raw_path, combined, (output / compartment).resolve(), fiji)
        lookup = {row["id"]: row for row in reference}
        background = lookup[999999]["median"]
        rows = objects if compartment == "object" else cells
        prefix = "" if compartment == "object" else f"ncl_{compartment}_"
        errors: dict[str, list[float]] = {key: [] for key in ("count", "raw_mean", "raw_median", "raw_integrated", "corrected_mean", "corrected_median", "corrected_integrated")}
        compared = []
        histogram_differences = 0
        for row in rows:
            object_id = row["nucleolus_id"] if compartment == "object" else row["nucleus_id"]
            if row[prefix+"mean"] is None:
                assert object_id not in lookup
                continue
            ref = lookup[object_id]
            count = (row["area_px"] if compartment == "object" else
                     row["nucleus_area_px"] if compartment == "nucleus" else
                     row["nucleolar_area_px"] if compartment == "nucleoli" else
                     row["nucleus_area_px"] - row["nucleolar_area_px"])
            pairs = {"count": (count, ref["count"]), "raw_mean": (row[prefix+"mean"], ref["mean"]),
                     "raw_median": (row[prefix+"median"], ref["median_midpoint"]),
                     "raw_integrated": (row[prefix+"integrated"], ref["integrated"]),
                     "corrected_mean": (row[prefix+"mean_corrected"], ref["mean"]-background),
                     "corrected_median": (row[prefix+"median_corrected"], ref["median_midpoint"]-background),
                     "corrected_integrated": (row[prefix+"integrated_corrected"], ref["integrated"]-background*count)}
            for key, (actual, expected) in pairs.items():
                error = abs(actual-expected)
                errors[key].append(error)
                if error > (1e-6 if "integrated" in key else 1e-10):
                    raise AssertionError(f"Independent ImageJ mismatch: {compartment} {object_id} {key}")
            histogram_differences += row[prefix+"median"] != ref["median"]
            compared.append({"id": int(object_id), "cytellect": {key: value[0] for key, value in pairs.items()}, "imagej": ref})
        record = {"compartment": compartment, "regions": len(compared), "offset_median": background,
                  "maximum_absolute_errors": {key: max(values, default=0) for key, values in errors.items()},
                  "histogram_median_convention_differences": histogram_differences, "rows": compared}
        records.append(record)
        print(json.dumps({key: value for key, value in record.items() if key != "rows"}), flush=True)
    unions = {row["id"]: row["imagej"] for row in records[1]["rows"]}
    plasma = {row["id"]: row["imagej"] for row in records[2]["rows"]}
    ratio_rows = []
    for cell in cells:
        key = cell["nucleus_id"]
        corrected_union = unions[key]["mean"] - records[1]["offset_median"] if key in unions else None
        corrected_plasma = plasma[key]["mean"] - records[2]["offset_median"] if key in plasma else None
        ratio = None
        log_ratio = None
        if corrected_union is not None and corrected_plasma is not None and corrected_union > 0 and corrected_plasma > 0:
            ratio = corrected_plasma / corrected_union
            log_ratio = float(np.log2(ratio))
        for actual, expected in ((cell["ncl_nucleoplasm_over_nucleoli"], ratio), (cell["ncl_log2_nucleoplasm_over_nucleoli"], log_ratio)):
            if expected is None:
                assert actual is None
            else:
                assert abs(actual - expected) <= 1e-12
        ratio_rows.append({"nucleus_id": key, "imagej_derived_ratio": ratio, "imagej_derived_log2_ratio": log_ratio,
                           "cytellect_ratio": cell["ncl_nucleoplasm_over_nucleoli"],
                           "cytellect_log2_ratio": cell["ncl_log2_nucleoplasm_over_nucleoli"]})
    report = {"source": manifest["source"], "image_sha256": manifest["sha256"], "mask_sha256": digest(masks.read_bytes()),
              "channel_map": roles, "channel_conflict": manifest["schema"]["channel_conflict"],
              "scope": "Fixed-mask pixel arithmetic only; adopted channel mapping conflict retained; no accuracy/biology claim",
              "reference": "ImageJ ROI getStatistics plus independent Java midpoint median", "dtype": str(channels["ncl"].dtype),
              "reference_bridge_hash_normalization": "LF newlines", "reference_bridge_sha256": digest((root / "engines/fiji/Bbbc013Reference.java").read_bytes().replace(b"\r\n", b"\n")),
              "offset_roi": offset_rect, "offset_caveat": "Spatially selected reference-offset ROI, not certified cell-free background",
              "compartments": records, "ratios": ratio_rows}
    (output / "imagej-comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--masks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fiji", required=True)
    args = parser.parse_args()
    evaluate(args.image, args.masks, args.output, args.fiji)
