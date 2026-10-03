"""Private generic-region bundles and hash-checked approved-mask replay."""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import zipfile
from pathlib import Path

import numpy as np
import tifffile

from .exports import environment
from .exports_csv import write_csv
from .images import read_tiff, sha256
from .masks import polygon_mask, validate_label_array
from .region_contracts import RegionAnalysisRequest, RegionImageInfo, scientific_specification
from .regions import _array_hash, measure_regions
from .roi import export_roi_zip

FORMAT = "cytellect-region-reproducibility/1"
METHODS_VERSION = "1.0.0"


def _json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def _safe_path(root: Path, relative: str) -> Path:
    if (not isinstance(relative, str) or not relative
            or any(not re.fullmatch(r"[A-Za-z0-9_.-]+", part) or part in {".", ".."}
                   for part in relative.split("/"))):
        raise ValueError("region_bundle_path_invalid")
    target = root.joinpath(*relative.split("/")).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError("region_bundle_path_invalid")
    return target


def _request(config):
    if config.get("analysis_kind") != "region-2d":
        raise ValueError("region_bundle_kind_mismatch")
    request = RegionAnalysisRequest.model_validate({
        key: config[key] for key in ("field_ids", "recipe", "backgrounds", "exclusions") if key in config
    })
    if not request.field_ids or set(config.get("field_snapshot", {})) != set(request.field_ids):
        raise ValueError("region_bundle_snapshot_invalid")
    return request


def region_methods(config, report, provenance):
    request = _request(config)
    lines = ["# Cytellect region measurement Methods", "",
             "Generated from recorded settings; review the biological definitions before publication.", "",
             f"Methods template {METHODS_VERSION}; region measurement protocol 1.0.0.",
             f"Analysis revision: {report['revision_id']}.",
             f"Region definition: {request.recipe.label}; logical ID {request.recipe.region_set_id}.",
             f"Initial masks: {request.recipe.source}; no automatic detector was executed in this recipe.",
             "Saved integer labels in original image coordinates define measured pixel unions. "
             "A region ID does not by itself establish a whole biological cell.",
             "Measurement uses unchanged native 8/16-bit grayscale values. Display LUTs are not measurements.",
             "For each channel, a user-confirmed ROI outside all measured regions supplies the background median. "
             "Raw mean, midpoint median and pixel sum are reported with their background-subtracted counterparts. "
             "Negative corrected intensities remain signed; integrated intensity is not concentration.",
             "Physical area requires confirmed X and Y pixel sizes; otherwise only pixel area is available. "
             "Storage-limit and confirmed acquisition-saturation fractions are distinct; unknown limits remain missing.", ""]
    for fid in request.field_ids:
        info = RegionImageInfo.model_validate(config["field_snapshot"][fid]["image_info"])
        labels = "; ".join(f"{channel.channel_id}: {channel.label} (stain: {channel.stain or 'not recorded'})"
                           for channel in info.channels)
        lines.append(f"Field {fid}: {labels}.")
    lines.extend(["", f"Unresolved failed fields: {len(report.get('field_failures', []))}; "
                  f"explicitly excluded failed fields: {len(report.get('excluded_failed_fields', []))}.",
                  "Failures, absent regions, exclusions and missing calibration/saturation are retained in measurements.json. "
                  "Exclusions do not overwrite raw measurements. Independent replication is not inferred from regions or fields.",
                  "Descriptive figures, when present, display observations without inferential confidence intervals or p-values.",
                  "Replay validates original file hashes and remeasures the saved masks of successfully measured fields. "
                  "Failed/unmeasured fields are preserved diagnostically and are not reclassified by replay. "
                  "No model download or automatic segmentation is executed.",
                  f"Scientific source identity: {provenance.get('software', {}).get('source_sha256', 'unavailable')}.",
                  "Original images are excluded unless explicitly requested. This bundle contains research information; keep it private.", ""])
    return "\n".join(lines)


def _long_rows(report, config):
    exclusions = {(item["field_id"], item.get("region_id")): item["reason"] for item in report["exclusions"]}
    rows = []
    for fid, table in sorted(report["field_tables"].items()):
        channels = {item["channel"]["channel_id"]: item["channel"] for item in table["channel_provenance"]}
        metadata = config["field_snapshot"][fid]["metadata"]
        for row in table["rows"]:
            channel = channels[row["channel_id"]]
            reason = exclusions.get((fid, None)) or exclusions.get((fid, row["region_id"]))
            rows.append({**row, "region_label": table["region_set"]["label"],
                         "channel_label": channel["label"], "stain": channel["stain"],
                         **metadata, "excluded": bool(reason), "exclusion_reason": reason})
    return rows


def _recompute_description(report, config, result):
    from .descriptive import describe_regions
    from .descriptive_contracts import DescriptiveRequest

    if result.get("analysis_kind") != "descriptive" or result.get("source_kind") != "region-2d":
        raise ValueError("region_export_statistics_unsupported")
    if result.get("revision_id") != report["revision_id"]:
        raise ValueError("region_export_statistics_revision_mismatch")
    confirmed_at = (config.get("review_record") or {}).get("confirmed_at")
    if isinstance(confirmed_at, bool) or not isinstance(confirmed_at, (int, float)):
        raise ValueError("region_export_statistics_review_required")
    if not math.isfinite(confirmed_at) or confirmed_at <= 0:
        raise ValueError("region_export_statistics_review_required")
    # The shared adapter enforces coverage, explicit exclusions, channel identity,
    # units and source selection; exporting a figure cannot bypass those checks.
    calculated = describe_regions(report, config["field_snapshot"], DescriptiveRequest.model_validate(result["spec"]))
    calculated["revision_id"] = report["revision_id"]
    if set(result) - (set(calculated) | {"figure"}):
        raise ValueError("region_export_statistics_unrecognized_fields")
    return calculated


def build_region_bundle(destination: Path, *, report, config, provenance, mask_files,
                        raw_files=(), statistics_results=(), include_raw=False):
    """Bundle owned server paths only; public URL/access checks belong to the API."""
    request = _request(config)
    if report.get("analysis_kind") != "region-2d" or report.get("recipe") != request.recipe.model_dump(mode="json"):
        raise ValueError("region_bundle_report_mismatch")
    mask_files = dict(mask_files)
    if set(mask_files) != set(report["field_masks"]):
        raise ValueError("region_bundle_masks_incomplete")
    descriptions = []
    for result in statistics_results:
        calculated = _recompute_description(report, config, result)
        if any(result.get(key) != value for key, value in calculated.items()):
            raise ValueError("region_export_statistics_source_mismatch")
        descriptions.append(calculated)
    destination.mkdir(parents=True, exist_ok=True)
    content = destination / "bundle"
    content.mkdir(exist_ok=False)
    _json(content / "measurements.json", report)
    _json(content / "revision.json", {"id": report["revision_id"], "config": config})
    _json(content / "provenance.json", provenance)
    _json(content / "environment.json", environment())
    write_csv(content / "regions.csv", _long_rows(report, config))
    write_csv(content / "field-outcomes.csv", [{"field_id": fid, "outcome": status}
                                                for fid, status in report["field_outcomes"].items()])
    for fid, source in sorted(mask_files.items()):
        record = report["field_masks"][fid]
        source = Path(source)
        if source.stat().st_size != record["file"]["bytes"] or sha256(source) != record["file"]["sha256"]:
            raise ValueError("region_bundle_mask_file_mismatch")
        labels = np.load(source, mmap_mode="r", allow_pickle=False)
        validate_label_array(labels)
        if _array_hash(labels, "<u4") != record["mask_sha256"] or list(labels.shape) != record["shape"]:
            raise ValueError("region_bundle_mask_pixels_mismatch")
        folder = _safe_path(content, f"masks/{fid}")
        folder.mkdir(parents=True)
        shutil.copyfile(source, folder / "labels.npy")
        tifffile.imwrite(folder / "labels.tif", np.asarray(labels, dtype=np.uint32), metadata={"axes": "YX"})
        export_roi_zip(labels, folder / "regions-rois.zip")
        # Failed fields may have invalid background geometry; its original input
        # is retained in config, without falsely exporting a confirmed raster.
        if fid in report["field_tables"]:
            for cid, background in request.backgrounds[fid].items():
                mask = polygon_mask(labels.shape, background.polygon)
                np.save(_safe_path(folder, f"background-{cid}.npy"), mask, allow_pickle=False)
    raw_manifest = []
    if include_raw:
        raw_files = list(raw_files)
        expected = {f"{fid}/{slot}.tif": record for fid, snapshot in config["field_snapshot"].items()
                    for slot, record in snapshot["image_info"]["inputs"].items()}
        if len(raw_files) != len(expected) or {name for name, _ in raw_files} != set(expected):
            raise ValueError("region_raw_inputs_incomplete")
        for name, source in raw_files:
            target = _safe_path(content, f"raw/{name}")
            source = Path(source)
            if source.stat().st_size != expected[name]["bytes"] or sha256(source) != expected[name]["sha256"]:
                raise ValueError("region_raw_input_mismatch")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            raw_manifest.append({"path": f"raw/{name}", "sha256": expected[name]["sha256"]})
    from .descriptive_figures import render_descriptive

    for index, calculated in enumerate(descriptions):
        folder = content / "statistics" / str(index)
        figure = render_descriptive(calculated, folder)
        _json(folder / "result.json", {**calculated, "figure": figure})
    methods = region_methods(config, report, provenance)
    (content / "methods.md").write_text(methods, encoding="utf-8")
    (destination / "methods.md").write_text(methods, encoding="utf-8")
    (content / "replay.py").write_text(
        '"""Use the locked Cytellect environment recorded in this bundle."""\n'
        'from cytellect_analysis.region_exports import main\n'
        'if __name__ == "__main__":\n    main()\n', encoding="utf-8")
    (content / "REPLAY.md").write_text(
        "# Reproduce region measurements\n\nUse the exact source/environment recorded in provenance.json and environment.json.\n\n"
        "    python replay.py --bundle-dir . --raw-dir /private/originals --output-dir /private/replayed\n\n"
        "Originals are mapped to `<field_id>/<internal_slot>.tif` from revision.json. Use `--raw-dir raw` only "
        "when source files were explicitly included. Every original file needed by a successfully measured field "
        "is hash-checked. Saved corrected labels are canonical; segmentation is not rerun. Failed/unmeasured "
        "fields remain diagnostic and are not reassessed. Descriptive figures are regenerated from the recorded "
        "selector. A zero exit status confirms the regenerated measurement tables equal the saved values. "
        "It does not confirm biological annotation correctness. Keep input and output directories private.\n", encoding="utf-8")
    members = sorted(path for path in content.rglob("*") if path.is_file())
    _json(content / "manifest.json", {
        "format": FORMAT, "revision_id": report["revision_id"], "raw_included": include_raw, "raw_files": raw_manifest,
        "replay_scope": "saved masks of measured fields -> measurements -> recorded descriptive figures; failures preserved",
        "files": {path.relative_to(content).as_posix(): sha256(path) for path in members},
    })
    archive_path = destination / "analysis.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(path for path in content.rglob("*") if path.is_file()):
            entry = zipfile.ZipInfo(path.relative_to(content).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o600 << 16
            with path.open("rb") as source_stream, archive.open(entry, "w") as archive_target:
                shutil.copyfileobj(source_stream, archive_target, length=1024 * 1024)
    return archive_path


def replay_region_bundle(bundle_dir: Path, raw_dir: Path, output_dir: Path):
    """Recompute successful fields with saved masks; retain failure diagnostics."""
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != FORMAT:
        raise ValueError("region_bundle_format_unsupported")
    for relative, expected_hash in manifest["files"].items():
        path = _safe_path(bundle_dir, relative)
        if not path.is_file() or sha256(path) != expected_hash:
            raise ValueError("region_bundle_file_hash_mismatch")
    record = json.loads((bundle_dir / "revision.json").read_text(encoding="utf-8"))
    config = record["config"]
    request = _request(config)
    report = json.loads((bundle_dir / "measurements.json").read_text(encoding="utf-8"))
    if record["id"] != report["revision_id"] or manifest["revision_id"] != report["revision_id"]:
        raise ValueError("region_bundle_revision_mismatch")
    output_dir.mkdir(parents=True, exist_ok=False)
    tables = {}
    for fid in sorted(report["field_tables"]):
        info = RegionImageInfo.model_validate(config["field_snapshot"][fid]["image_info"])
        for slot, source in info.inputs.items():
            path = _safe_path(raw_dir, f"{fid}/{slot}.tif")
            if not path.is_file() or path.stat().st_size != source.bytes or sha256(path) != source.sha256:
                raise ValueError("region_replay_input_mismatch")
        channels = {channel.channel_id: read_tiff(_safe_path(raw_dir, f"{fid}/ch{index}.tif"))
                    for index, channel in enumerate(info.channels)}
        if any(list(array.shape) != info.shape for array in channels.values()):
            raise ValueError("region_replay_input_shape_mismatch")
        mask_record = report["field_masks"][fid]
        path = _safe_path(bundle_dir, f"masks/{fid}/labels.npy")
        labels = np.load(path, mmap_mode="r", allow_pickle=False)
        validate_label_array(labels)
        if _array_hash(labels, "<u4") != mask_record["mask_sha256"] or list(labels.shape) != mask_record["shape"]:
            raise ValueError("region_bundle_mask_pixels_mismatch")
        backgrounds = {cid: polygon_mask(labels.shape, background.polygon)
                       for cid, background in request.backgrounds[fid].items()}
        table = measure_regions(channels, labels, backgrounds, scientific_specification(
            field_id=fid, revision_id=report["revision_id"], mask_revision_id=mask_record["mask_revision_id"],
            recipe=request.recipe, image_info=info,
        ))
        tables[fid] = table.model_dump(mode="json")
    reproduced = {**report, "field_tables": tables}
    _json(output_dir / "measurements.json", reproduced)
    write_csv(output_dir / "regions.csv", _long_rows(reproduced, config))
    from .descriptive_figures import render_descriptive

    descriptions_match = True
    for path in sorted((bundle_dir / "statistics").glob("*/result.json")):
        result = json.loads(path.read_text(encoding="utf-8"))
        replayed = _recompute_description(reproduced, config, result)
        descriptions_match &= all(result.get(key) == value for key, value in replayed.items())
        folder = output_dir / "statistics" / path.parent.name
        replayed["figure"] = render_descriptive(replayed, folder)
        _json(folder / "result.json", replayed)
    comparison = {
        "matched_saved_measurements": tables == report["field_tables"],
        "matched_saved_descriptions": descriptions_match,
        "measured_fields_replayed": sorted(tables),
        "unmeasured_fields_preserved_not_reassessed": sorted(set(request.field_ids or []) - set(tables)),
    }
    _json(output_dir / "replay-verification.json", comparison)
    return comparison


def main():
    parser = argparse.ArgumentParser(description="Replay generic measurements with verified original pixels and saved masks")
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = replay_region_bundle(args.bundle_dir, args.raw_dir, args.output_dir)
    if not result["matched_saved_measurements"] or not result["matched_saved_descriptions"]:
        raise SystemExit("region_replay_measurement_mismatch")


if __name__ == "__main__":
    main()
