"""Reproducible BBBC007 acquisition and independent, generic-channel pixel checks.

This is a developer validation tool. It is not an upload API or a new product
recipe. Actin is never passed off as GFP/NCL. All acquired images and run outputs
must be outside the checkout. Unsupported fields remain in the report.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

import numpy as np
import tifffile
from public_bbbc013 import imagej_reference, reference_offset
from public_bbbc039 import match_instances
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "fixtures/public/bbbc007/manifest.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def external_directory(value: Path) -> Path:
    resolved = value.resolve()
    if resolved == ROOT or ROOT in resolved.parents:
        raise ValueError("public_validation_data_must_be_outside_checkout")
    return resolved


def acquire(directory: Path) -> None:
    directory = external_directory(directory)
    directory.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for name, entry in manifest["archives"].items():
        destination = directory / name
        if not destination.exists():
            with urlopen(entry["url"], timeout=60) as response:
                content = response.read(entry["bytes"] + 1)
            if len(content) != entry["bytes"] or sha256(content) != entry["sha256"]:
                raise ValueError("public_archive_identity_mismatch")
            destination.write_bytes(content)
        verify_archive(destination, entry)


def verify_archive(path: Path, entry: dict) -> None:
    if path.stat().st_size != entry["bytes"] or sha256(path.read_bytes()) != entry["sha256"]:
        raise ValueError("public_archive_identity_mismatch")


def strict_plane(array: np.ndarray) -> np.ndarray:
    """Do not reinterpret inconsistent RGB source TIFFs as raw grayscale data."""
    if array.ndim != 2:
        raise ValueError("unsupported_rgb_or_multiaxis_source")
    if array.dtype not in (np.dtype("uint8"), np.dtype("uint16")):
        raise ValueError("unsupported_source_dtype")
    return array


def contour_interiors(array: np.ndarray) -> np.ndarray:
    """Decode bounded 4-connected black components, excluding contour pixels.

    This is an explicit derived evaluation convention, not an author-supplied
    instance-mask interpretation. Open contours are not closed or repaired.
    """
    if array.ndim != 2 or not set(np.unique(array).tolist()).issubset({0, 1, 255}):
        raise ValueError("unsupported_outline_encoding")
    components, _ = ndimage.label(array == 0, structure=ndimage.generate_binary_structure(2, 1))
    exterior = np.unique(np.concatenate((components[0], components[-1], components[:, 0], components[:, -1])))
    regions = components.copy()
    regions[np.isin(regions, exterior)] = 0
    result = np.zeros(array.shape, dtype=np.uint32)
    for new_id, old_id in enumerate(np.unique(regions[regions > 0]), start=1):
        result[regions == old_id] = new_id
    return result


def load_field(images: ZipFile, outlines: ZipFile, entry: dict) -> tuple[dict, dict]:
    arrays, identities = {}, {}
    for role, member in entry["members"].items():
        archive = outlines if role.endswith("outline") else images
        source = archive.read(member)
        array = tifffile.imread(io.BytesIO(source))
        arrays[role] = array
        identities[role] = {
            "member": member, "sha256": sha256(source), "shape": list(array.shape), "dtype": str(array.dtype),
        }
        if array.ndim == 3 and array.shape[-1] == 3:
            identities[role]["rgb_planes_identical"] = bool(
                np.array_equal(array[..., 0], array[..., 1]) and np.array_equal(array[..., 0], array[..., 2]))
    return arrays, identities


def check_regions(raw: np.ndarray, labels: np.ndarray, offset: np.ndarray, raw_path: Path,
                  directory: Path, executable: str) -> dict:
    from cytellect_analysis.measurement import region_values

    if (offset & (labels > 0)).any():
        raise ValueError("reference_offset_overlaps_regions")
    combined = labels.copy()
    combined[offset] = 999999
    reference = imagej_reference(raw_path, combined, directory.resolve(), executable)
    lookup = {row["id"]: row for row in reference}
    background = lookup[999999]["median_midpoint"]
    python_background = float(np.median(raw[offset]))
    if python_background != background:
        raise AssertionError("independent_background_mismatch")
    comparisons, errors = [], []
    for object_id in np.unique(labels[labels > 0]):
        mask = labels == object_id
        measured = region_values(raw, mask, python_background)
        ref = lookup[int(object_id)]
        expected = {"area_px": ref["count"], "mean": ref["mean"], "median": ref["median_midpoint"],
                    "integrated": ref["integrated"], "mean_corrected": ref["mean"] - background,
                    "median_corrected": ref["median_midpoint"] - background,
                    "integrated_corrected": ref["integrated"] - background * ref["count"]}
        actual = {"area_px": int(mask.sum()), **measured}
        differences = {key: abs(actual[key] - value) for key, value in expected.items()}
        errors.append(differences)
        comparisons.append({"id": int(object_id), "cytellect": actual, "imagej": ref,
                            "absolute_errors": differences})
    maximum = {key: max((row[key] for row in errors), default=0.) for key in (
        "area_px", "mean", "median", "integrated", "mean_corrected", "median_corrected", "integrated_corrected")}
    # Report the complete field before deciding pass/fail; retain discordant rows.
    passed = all(value <= (1e-8 if "integrated" in key else 1e-10) for key, value in maximum.items())
    report = {"regions": len(comparisons), "passed": passed, "offset_median": background,
              "maximum_absolute_errors": maximum, "rows": comparisons}
    (directory / "comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {key: value for key, value in report.items() if key != "rows"}


def evaluate(directory: Path, output: Path, executable: str) -> dict:
    from cytellect_analysis.contracts import Recipe
    from cytellect_analysis.engine import detect

    directory, output = external_directory(directory), external_directory(output)
    if output.exists():
        raise ValueError("validation_output_already_exists")
    output.mkdir(parents=True)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for name, archive in manifest["archives"].items():
        verify_archive(directory / name, archive)
    records = []
    with ZipFile(directory / "BBBC007_v1_images.zip") as images, ZipFile(directory / "BBBC007_v1_outlines.zip") as outlines:
        for entry in manifest["fields"]:
            run = output / entry["id"]
            run.mkdir()
            arrays, identities = load_field(images, outlines, entry)
            record = {"field": entry["id"], "inputs": identities}
            try:
                dna, actin = strict_plane(arrays["dna"]), strict_plane(arrays["actin"])
                if dna.shape != actin.shape or any(arrays[role].shape != dna.shape for role in ("nuclear_outline", "cell_outline")):
                    raise ValueError("source_dimensions_mismatch")
                # Invoke only the shared nucleus detector. No GFP source or GFP
                # measurement exists in this developer validation workflow.
                nuclei, nucleoli, engine = detect(
                    {"dapi": dna}, Recipe(id="gfp-nuclear-2d", gfp_gate="none"), run / "detection", executable,
                    scratch_root=output / "scratch",
                )
                if nucleoli.any():
                    raise AssertionError("unexpected_nucleolar_output")
                manual_nuclei = contour_interiors(arrays["nuclear_outline"])
                manual_cells = contour_interiors(arrays["cell_outline"])
                occupied = (nuclei > 0) | (manual_nuclei > 0) | (manual_cells > 0)
                offset, offset_rect = reference_offset(occupied.astype(np.uint32))
                actin_path = (run / "actin-original-pixels.tif").resolve()
                tifffile.imwrite(actin_path, actin, photometric="minisblack", metadata=None)
                np.savez_compressed(run / "masks.npz", nuclei=nuclei, manual_nuclei=manual_nuclei,
                                    manual_cells=manual_cells, reference_offset=offset)
                measurements = {
                    name: check_regions(actin, labels, offset, actin_path, run / name, executable)
                    for name, labels in (("detected_nuclei", nuclei), ("manual_nuclear_interiors", manual_nuclei),
                                         ("manual_cell_interiors", manual_cells))
                }
                record.update({"status": "passed" if all(row["passed"] for row in measurements.values()) else "arithmetic_failed",
                               "engine": engine, "measurements": measurements, "offset_rectangle": offset_rect,
                               "contour_interior_comparison": match_instances(manual_nuclei, nuclei)})
            except (ValueError, RuntimeError, AssertionError, OSError) as exc:
                reason = str(exc) if re.fullmatch(r"[a-z_]+", str(exc)) else "validation_execution_error"
                record.update({"status": "failed", "reason": reason, "error_type": type(exc).__name__})
            records.append(record)
            (run / "field-report.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
            print(json.dumps({"field": entry["id"], "status": record["status"], "reason": record.get("reason"),
                              "measurements": record.get("measurements")}), flush=True)
    report = {
        "validation_version": "1.0.0", "dataset": manifest["dataset"], "source": manifest["source"],
        "manifest_sha256": sha256(MANIFEST.read_bytes()), "recipe_scope": "shared nuclear detector plus generic region_values; not full product generic-channel workflow",
        "reference": "Actual ImageJ ROI statistics and separate Java midpoint median; source actin never labelled GFP/NCL",
        "reference_bridge_sha256_lf": sha256((ROOT / "engines/fiji/Bbbc013Reference.java").read_bytes().replace(b"\r\n", b"\n")),
        "offset_scope": "Fixed first 15x15 region-free block; arithmetic offset only, not confirmed biological background",
        "annotation_scope": "Bounded four-connected contour interiors, original drawn boundary pixels excluded; no contour repair; not author-provided instance masks",
        "accuracy_scope": "Exploratory contour-interior agreement only; not the original cell-boundary metric, independent holdout evidence or nucleolar accuracy",
        "performance_accepted": False,
        "performance_exclusion_reason": "Thick annotation strokes make interior-only masks smaller than the intended nuclei; filling/boundary conventions are unresolved. Do not interpret contour-interior F1 as detector accuracy or tune detector parameters to it.",
        "training_overlap": "Not established; do not claim independently held-out model performance",
        "fields": records,
        "summary": {"selected": len(records), "passed": sum(row["status"] == "passed" for row in records),
                    "failed": sum(row["status"] != "passed" for row in records),
                    "compared_regions": sum(item["regions"] for row in records for item in row.get("measurements", {}).values())},
    }
    (output / "benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def check_report(report: dict) -> None:
    """CI checks expected source rejection and arithmetic, not biological accuracy."""
    fields = {row["field"]: row for row in report["fields"]}
    if len(report["fields"]) != 4 or set(fields) != {"a9", "f113", "f96_17", "f9620"}:
        raise ValueError("fixed_subset_changed")
    for name in ("f113", "f96_17"):
        if fields[name].get("status") != "failed" or fields[name].get("reason") != "unsupported_rgb_or_multiaxis_source":
            raise ValueError("unsupported_field_not_explicitly_rejected")
    for name in ("a9", "f9620"):
        item = fields[name]
        if item.get("status") != "passed" or set(item.get("measurements", {})) != {
                "detected_nuclei", "manual_nuclear_interiors", "manual_cell_interiors"}:
            raise ValueError("public_image_arithmetic_failed")
        for comparison in item["measurements"].values():
            if not comparison["passed"] or comparison["regions"] < 1:
                raise ValueError("public_image_arithmetic_failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--evaluate", type=Path)
    parser.add_argument("--fiji", default="")
    parser.add_argument("--check-report", type=Path,
                        help="Check a completed report; requires both rejected RGB fields and both numerical successes")
    arguments = parser.parse_args()
    if arguments.download:
        acquire(arguments.data_dir)
    if arguments.evaluate:
        print(json.dumps(evaluate(arguments.data_dir, arguments.evaluate, arguments.fiji)["summary"]))
    if arguments.check_report:
        check_report(json.loads(arguments.check_report.read_text(encoding="utf-8")))
        print("BBBC007 arithmetic and explicit input-rejection checks passed; segmentation accuracy is not accepted")
