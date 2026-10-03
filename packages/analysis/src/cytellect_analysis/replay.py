"""Offline replay from exact original TIFFs and approved saved masks."""
import argparse
import json
import math
from pathlib import Path

import numpy as np

from .contracts import Recipe, StatisticsRequest
from .exports import _json
from .exports_csv import write_csv
from .figures import render_figures
from .images import read_tiff, sha256
from .masks import polygon_mask
from .measurement import apply_gfp_gate, measure
from .region_sensitivity import validate_region_configs, validate_region_masks, validate_region_reports
from .review import unresolved_nucleolar_failures
from .statistics import analyze_sensitivity


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _inside(root, relative):
    root = root.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError("replay_path_outside_package")
    return path


def remeasure(config, expected, masks_root: Path, raw_dir: Path):
    """Recalculate one saved, reviewed region definition from exact original pixels."""
    recipe = Recipe.model_validate(config["recipe"])
    confirmed = config.get("review_record", {}).get("confirmed_at")
    if (isinstance(confirmed, bool) or not isinstance(confirmed, (int, float)) or not math.isfinite(confirmed) or confirmed <= 0
            or expected.get("field_failures")
            or unresolved_nucleolar_failures(expected, config)
            or set(expected.get("invalidated_nucleoli", [])) - set(config.get("review_record", {}).get("accepted_invalidated_fields", []))):
        raise ValueError("replay_requires_complete_reviewed_masks")
    excluded_failures = expected.get("excluded_failed_fields", [])
    excluded_ids = {entry["field_id"] for entry in excluded_failures}
    explicit = {entry["field_id"]: entry["reason"] for entry in config.get("exclusions", [])
                if entry["nucleus_id"] is None}
    if (len(excluded_ids) != len(excluded_failures) or not excluded_ids.issubset(config["field_ids"])
            or any(explicit.get(entry["field_id"]) != entry["reason"] for entry in excluded_failures)
            or any(row["field_id"] in excluded_ids for row in expected.get("cells", []))):
        raise ValueError("replay_excluded_field_inconsistent")
    cells, objects, manual_rows = [], [], []
    for fid in config["field_ids"]:
        if fid in excluded_ids:
            continue  # Explicitly excluded failed inputs have no accepted mask or measurement.
        snapshot = config["field_snapshot"][fid]
        info = snapshot["image_info"]
        folder = _inside(raw_dir, fid)
        for role, source in info["inputs"].items():
            if role not in ("dapi", "ncl", "gfp", "ome"):
                raise ValueError("unsupported_replay_channel")
            if sha256(folder / f"{role}.tif") != source["sha256"]:
                raise ValueError("replay_original_hash_mismatch")
        if "ome" in info["inputs"]:
            stack = read_tiff(folder / "ome.tif", channel_indices=info["channel_mapping"])
            channels = dict(zip(info.get("channel_roles", ("dapi", "ncl", "gfp")), stack, strict=True))
        else:
            channels = {role: read_tiff(folder / f"{role}.tif", legacy=info["legacy"])
                        for role in info["inputs"]}
        with np.load(_inside(masks_root, f"{fid}/labels.npz"), allow_pickle=False) as masks:
            nuclei, nucleoli, manual = masks["nuclei"], masks["nucleoli"], masks["manual"]
            background = (polygon_mask(nuclei.shape, config["backgrounds"][fid]["polygon"])
                          if recipe.id != "ncl-legacy-rgb" else None)
            states = expected.get("engine_provenance", {}).get(fid, {}).get("nucleolar_states", {})
            measured = measure(channels, nuclei, nucleoli, background, recipe, snapshot["metadata"], fid, manual,
                               nucleolar_states={int(key): value for key, value in states.items()})
        field_cells, field_objects, field_manual = measured
        exclusions = [entry for entry in config.get("exclusions", []) if entry["field_id"] == fid]
        field_reason = next((entry["reason"] for entry in exclusions if entry["nucleus_id"] is None), None)
        nucleus_reasons = {entry["nucleus_id"]: entry["reason"] for entry in exclusions}
        for row in field_cells:
            reason = field_reason or nucleus_reasons.get(row["nucleus_id"])
            if reason:
                row["excluded"], row["exclusion_reason"] = True, reason
        cells.extend(field_cells)
        objects.extend(field_objects)
        manual_rows.extend(field_manual)
    cells = apply_gfp_gate(cells, recipe)
    return {**expected, "cells": cells, "nucleoli": objects, "manual_rois": manual_rows}


def replay(bundle_dir: Path, raw_dir: Path, output_dir: Path):
    bundle_dir, raw_dir = bundle_dir.resolve(), raw_dir.resolve()
    if output_dir.resolve().is_relative_to(bundle_dir) or bundle_dir.is_relative_to(output_dir.resolve()):
        raise ValueError("replay_output_must_be_separate")
    manifest = _read(bundle_dir / "manifest.json")
    required = {"revision.json", "measurements.json", "provenance.json", "environment.json"}
    entries = manifest.get("files", {})
    actual = {path.relative_to(bundle_dir).as_posix() for path in bundle_dir.rglob("*")
              if path.is_file() and path != bundle_dir / "manifest.json"}
    if (manifest.get("format") != "cytellect-reproducibility/1" or not isinstance(entries, dict)
            or not required.issubset(entries) or set(entries) != actual):
        raise ValueError("replay_manifest_incomplete")
    for relative, expected_hash in manifest["files"].items():
        if sha256(_inside(bundle_dir, relative)) != expected_hash:
            raise ValueError("replay_bundle_hash_mismatch")
    revision = _read(bundle_dir / "revision.json")
    config = revision["config"]
    expected = _read(bundle_dir / "measurements.json")
    if expected.get("revision_id") != revision["id"] or manifest.get("revision_id") != revision["id"]:
        raise ValueError("replay_revision_identity_mismatch")
    result = remeasure(config, expected, bundle_dir / "masks", raw_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    _json(output_dir / "measurements.json", result)
    for filename, data in (("cells.csv", result["cells"]), ("nucleoli.csv", result["nucleoli"]), ("manual-rois.csv", result["manual_rois"])):
        write_csv(output_dir / filename, data)
    for stats_path in sorted((bundle_dir / "statistics").glob("*/result.json")):
        recorded = _read(stats_path)
        if recorded.get("analysis_kind") == "descriptive":
            from .descriptive import validate_legacy_description
            from .descriptive_figures import render_descriptive

            fresh_description = validate_legacy_description(recorded, result, config)
            folder = output_dir / "statistics" / stats_path.parent.name
            fresh_description["figure"] = render_descriptive(fresh_description, folder)
            _json(folder / "result.json", fresh_description)
            continue
        spec = StatisticsRequest.model_validate(recorded["spec"])
        alternate_rows = {}
        sources = recorded.get("region_sensitivity_sources", [])
        if [source["revision_id"] for source in sources] != spec.sensitivity_region_revision_ids:
            raise ValueError("replay_alternate_revision_identity_mismatch")
        for ordinal, source in enumerate(sources):
            rid = source["revision_id"]
            if (source.get("reviewed") is not True
                    or source["relative_path"] != f"alternatives/{ordinal}"):
                raise ValueError("replay_alternate_revision_identity_mismatch")
            snapshot_root = _inside(stats_path.parent, source["relative_path"])
            alternate_revision = _read(snapshot_root / "revision.json")
            alternate_expected = _read(snapshot_root / "measurements.json")
            if alternate_revision["id"] != rid or alternate_expected["revision_id"] != rid:
                raise ValueError("replay_alternate_revision_identity_mismatch")
            alternate_config = alternate_revision["config"]
            validate_region_configs(config, alternate_config)
            validate_region_reports(config, expected)
            validate_region_reports(alternate_config, alternate_expected)
            validate_region_masks(bundle_dir / "masks", snapshot_root / "masks", config["field_ids"],
                                  filename="labels.npz")
            alternate = remeasure(alternate_config, alternate_expected, snapshot_root / "masks", raw_dir)
            alternate_rows[rid] = alternate["cells"]
            alternate_output = output_dir / "statistics" / stats_path.parent.name / source["relative_path"]
            alternate_output.mkdir(parents=True)
            _json(alternate_output / "measurements.json", alternate)
        fresh = analyze_sensitivity(result["cells"], spec, alternate_rows=alternate_rows)
        if sources:
            fresh["region_sensitivity_sources"] = sources
        fresh["revision_id"] = expected["revision_id"]
        folder = output_dir / "statistics" / stats_path.parent.name
        fresh["figure"] = render_figures(fresh, folder)
        _json(folder / "result.json", fresh)
    return result


def main():
    parser = argparse.ArgumentParser(description="Replay approved-mask measurements from hash-verified TIFFs")
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    replay(arguments.bundle_dir, arguments.raw_dir, arguments.output_dir)


if __name__ == "__main__":
    main()
