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
from .plan_adoption import planning_methods, validate_revision_plan
from .region_contracts import (
    AdoptedNuclearRecipe,
    RegionAnalysisRequest,
    RegionCompartmentRecipe,
    RegionImageInfo,
    RegionNuclearRecipe,
    RegionSignalRecipe,
    region_report_from_json,
    scientific_specification,
    validate_region_report_policy,
)
from .region_measurement_v2 import measure_regions_versioned
from .regions import _array_hash
from .roi import export_roi_zip

FORMAT = "cytellect-region-reproducibility/1"
METHODS_VERSION = "1.1.0"
AREA_FORMAT = "cytellect-region-reproducibility/2"
AREA_METHODS_VERSION = "1.2.0"
RAW_FORMAT = "cytellect-region-reproducibility/3"


def bundle_format(policy):
    return FORMAT if policy is None else (AREA_FORMAT if policy.mode == "area_only" else RAW_FORMAT)


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
    validate_revision_plan(config)
    if config.get("analysis_kind") != "region-2d":
        raise ValueError("region_bundle_kind_mismatch")
    request = RegionAnalysisRequest.model_validate({
        key: config[key] for key in ("field_ids", "recipe", "backgrounds", "exclusions", "measurement") if key in config
    })
    if not request.field_ids or set(config.get("field_snapshot", {})) != set(request.field_ids):
        raise ValueError("region_bundle_snapshot_invalid")
    return request


def region_methods(config, report, provenance):
    request = _request(config)
    validate_region_report_policy(region_report_from_json(json.dumps(report)), config)
    area_only = request.measurement is not None and request.measurement.mode == "area_only"
    raw_only = request.measurement is not None and request.measurement.mode == "raw_intensity"
    nuclear = isinstance(request.recipe, (RegionNuclearRecipe, AdoptedNuclearRecipe))
    initial = ("Initial masks: a confirmed nuclear-stain channel was submitted to the fixed offline Fiji/StarDist 2D "
               "Versatile (fluorescent nuclei) model. This model defines nuclei, not whole cells or nucleoli."
               if nuclear else f"Initial masks: {request.recipe.source}; no automatic detector was executed in this recipe.")
    signal = isinstance(request.recipe, RegionSignalRecipe)
    if signal:
        initial = ("Initial masks: Fiji/ImageJ thresholding and connected components on the defining channel. "
                   "These exploratory signal-positive areas do not establish biological positivity, nuclei or nucleoli.")
    compartment = isinstance(request.recipe, RegionCompartmentRecipe)
    if compartment:
        initial = ("Initial masks: within-nucleus NCL-enriched candidates from the recorded Fiji compartment detector. "
                   "Nucleoplasm is the source nucleus minus the candidate union only for eligible classified nuclei. "
                   "Unclassified or failed nuclei are retained as missing parents, never whole-nucleus substitutes.")
    lines = ["# Cytellect region measurement Methods", "",
             "Generated from recorded settings; review the biological definitions before publication.", "",
             (f"Methods template {AREA_METHODS_VERSION}; region measurement protocol 2.0.0." if area_only else
              f"Methods template {METHODS_VERSION}; region measurement protocol 1.0.0."),
             f"Analysis revision: {report['revision_id']}.",
             f"Region definition: {request.recipe.label}; logical ID {request.recipe.region_set_id}.",
             initial,
             "Saved integer labels in original image coordinates define measured pixel unions. "
             "A region ID does not by itself establish a whole biological cell.",
             "Measurement uses unchanged native 8/16-bit grayscale values. Display LUTs are not measurements.",
             ("Area-only measurement was requested. No fluorescence summary, signal-saturation fraction or "
              "background correction was calculated; unavailable values are null with explicit not-requested reasons." if area_only else
              "For each channel, a user-confirmed ROI outside all measured regions supplies the background median. "
             "Raw mean, midpoint median and pixel sum are reported with their background-subtracted counterparts. "
              "Negative corrected intensities remain signed; integrated intensity is not concentration."),
             ("Physical area requires confirmed X and Y pixel sizes; otherwise only pixel area is available." if area_only else
              "Physical area requires confirmed X and Y pixel sizes; otherwise only pixel area is available. "
              "Storage-limit and confirmed acquisition-saturation fractions are distinct; unknown limits remain missing."), ""]
    if raw_only:
        lines[4] = "Methods template 1.3.0; region measurement protocol 3.0.0."
        lines = [line for line in lines if not line.startswith("For each channel, a user-confirmed ROI")]
        lines.append("Raw mean, midpoint median and pixel sum use unchanged source pixels. No background has been established; corrected values remain null (background_not_established).")
    display_fields = [fid for fid in request.field_ids
                      if config["field_snapshot"][fid]["image_info"].get("input_mode") == "display-rgb"]
    if display_fields:
        lines = [line.replace("Measurement uses unchanged native 8/16-bit grayscale values. Display LUTs are not measurements.",
                              "Native inputs retain original grayscale pixels; display RGB inputs use the conversion below.")
                 .replace("use unchanged source pixels", "use the recorded input measurement plane") for line in lines]
        lines.append("Display-RGB input transform 1.0.0: max(R,G,B), ignoring alpha, at original resolution. "
                     "These intensities are display-code values (0–255), not acquired raw fluorescence. "
                     "Acquisition LUTs, clipping and gamma cannot be reversed. Original TIFFs and input mode are retained for replay.")
        lines.append("Display-RGB fields: " + ", ".join(display_fields) + ".")
    if isinstance(request.recipe, AdoptedNuclearRecipe):
        lines = [line.replace("a confirmed nuclear-stain channel", "the adopted nuclear-role channel") for line in lines]
        lines.append(f"Nuclear role evidence: {request.recipe.nuclear_role_source}; adoption does not certify segmentation quality.")
    if isinstance(request.recipe, (RegionNuclearRecipe, AdoptedNuclearRecipe)):
        detector = request.recipe.detector
        lines.extend([
            (f"Nuclear recipe {request.recipe.version}; defining channel {request.recipe.defining_channel_id}."
             if isinstance(request.recipe, AdoptedNuclearRecipe) else
             f"Nuclear recipe {request.recipe.version}; confirmed defining channel {request.recipe.defining_channel_id}."),
            f"Detection normalization percentiles {detector.percentile_low:g}–{detector.percentile_high:g}; "
            f"probability threshold {detector.probability:g}; NMS threshold {detector.nms:g}.",
            "Saved labels use original image coordinates. Detection preprocessing does not alter "
            "measurement pixels. Corrected labels are preserved when metadata/background changes or a batch expands.",
        ])
    if signal:
        lines.append(f"Signal detector protocol 1.0.0; recipe {request.recipe.version}; "
                     f"defining channel {request.recipe.defining_channel_id}; settings "
                     + json.dumps(request.recipe.detector.model_dump(mode="json"), sort_keys=True) + ".")
    for fid in request.field_ids:
        info = RegionImageInfo.model_validate(config["field_snapshot"][fid]["image_info"])
        labels = "; ".join(f"{channel.channel_id}: {channel.label} (stain: {channel.stain or 'not recorded'})"
                           for channel in info.channels)
        lines.append(f"Field {fid}: {labels}.")
        event = provenance.get("fields", {}).get(fid, {}).get("detector")
        if (nuclear or signal or compartment) and event:
            engine = event.get("engine", {})
            if compartment:
                lines.append(f"Field {fid} nuclear source: " + json.dumps(provenance["fields"][fid].get("nuclear_source"), sort_keys=True) + ".")
                lines.append(f"Field {fid} compartment parent states: " + json.dumps({key: engine.get(key) for key in ("nucleolar_states", "parent_ids", "eligible_nucleus_ids", "excluded_nucleus_ids", "missing_parent_count", "missing_parent_reasons", "nucleoplasm_missing_reasons", "compartment_missing_parent_count")}, sort_keys=True) + ".")
            if engine.get("nuclear_detector_protocol_version") == "1.1.0":
                transform = engine["coordinate_transform"]
                lines.append(
                    f"Field {fid} detection protocol 1.1.0: original image {transform['original_shape_yx']} YX; "
                    f"detection image {transform['detection_shape_yx']} YX; "
                    f"scale X={transform['scale_x']}, Y={transform['scale_y']}. "
                    "Detection-only resizing uses anti-aliased bilinear interpolation and numpy-rint to source dtype. "
                    "Labels are restored by nearest-neighbour pixel-centre mapping to original coordinates. "
                    "Measurement uses the original-resolution measurement planes. "
                    "Reduced detection resolution may change segmentation and requires inspection.")
            lines.append(f"Field {fid} detector origin: revision {event.get('origin_revision_id')}; "
                         f"executed in this attempt: {event.get('executed_this_attempt')}; "
                         f"source pixels SHA-256: {event.get('input_sha256')}; "
                         f"model SHA-256: {engine.get('model_sha256', 'unavailable')}.")
        elif nuclear:
            lines.append(f"Field {fid}: no successful detector origin is recorded; inspect the retained failure ledger.")
    lines.extend(["", f"Unresolved failed fields: {len(report.get('field_failures', []))}; "
                  f"explicitly excluded failed fields: {len(report.get('excluded_failed_fields', []))}.",
                  "Failures, absent regions, exclusions and missing calibration/saturation are retained in measurements.json. "
                  "Exclusions do not overwrite raw measurements. Independent replication is not inferred from regions or fields.",
                  "Descriptive figures display observations without inferential confidence intervals or p-values. "
                  "Experimental-unit comparisons, when present, have separately recorded design, acquisition review, "
                  "aggregation, contrast families, missingness and statistical Methods.",
                  "Replay validates original file hashes and remeasures the saved masks of successfully measured fields. "
                  "Failed/unmeasured fields are preserved diagnostically and are not reclassified by replay. "
                  "No model download or automatic segmentation is executed.",
                  f"Scientific source identity: {provenance.get('software', {}).get('source_sha256', 'unavailable')}.",
                  "Original images are excluded unless explicitly requested. This bundle contains research information; keep it private.", ""])
    if config.get("workspace_selection"):
        lines.extend(["Workspace adoption ledger (including failed uploads/analyses excluded by the user):",
                      json.dumps(config["workspace_selection"], ensure_ascii=False, sort_keys=True), ""])
    return "\n".join(lines + planning_methods(config))


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
                         "input_mode": config["field_snapshot"][fid]["image_info"].get("input_mode", "native"),
                         "intensity_source": ("display_code_max_rgb" if
                             config["field_snapshot"][fid]["image_info"].get("input_mode") == "display-rgb"
                             else "acquired_grayscale"),
                         **metadata, "excluded": bool(reason), "exclusion_reason": reason})
    return rows


def _uses_common_statistics(result):
    return (result.get("analysis_kind") == "region-association"
            or (result.get("analysis_kind") == "region-comparison"
                and result.get("region_comparison_version") == "2.0.0"))


def _statistics_methods_template(result):
    if _uses_common_statistics(result):
        from .common_statistics_figures import CommonStatisticsMethodsTemplate

        return CommonStatisticsMethodsTemplate.model_validate(
            result.get("figure", {}).get("common_statistics_methods")
        ).model_dump(mode="json")
    from .statistical_methods import saved_methods_template

    return saved_methods_template(result)


def _recompute_statistics(report, config, result):
    from .descriptive import describe_regions
    from .descriptive_contracts import parse_descriptive_request
    _statistics_methods_template(result)
    if result.get("analysis_kind") not in ("descriptive", "region-comparison", "region-association") or result.get("source_kind") != "region-2d":
        raise ValueError("region_export_statistics_unsupported")
    if result.get("revision_id") != report["revision_id"]:
        raise ValueError("region_export_statistics_revision_mismatch")
    confirmed_at = (config.get("review_record") or {}).get("confirmed_at")
    if isinstance(confirmed_at, bool) or not isinstance(confirmed_at, (int, float)):
        raise ValueError("region_export_statistics_review_required")
    if not math.isfinite(confirmed_at) or confirmed_at <= 0:
        raise ValueError("region_export_statistics_review_required")
    if config.get("exclusions", []) != report.get("exclusions", []):
        raise ValueError("region_export_statistics_source_mismatch")
    # The shared adapter enforces coverage, explicit exclusions, channel identity,
    # units and source selection; exporting a figure cannot bypass those checks.
    if _uses_common_statistics(result):
        from .common_statistics import analyze_region_association, analyze_region_comparison
        from .common_statistics_contracts import parse_common_statistics_request

        request = parse_common_statistics_request(result["spec"])
        calculate = analyze_region_association if request.mode == "region-association" else analyze_region_comparison
        calculated = calculate(report, config, request)
    elif result["analysis_kind"] == "region-comparison":
        from .region_comparison import compare_regions
        from .region_comparison_contracts import RegionComparisonRequest

        calculated = compare_regions(report, config, RegionComparisonRequest.model_validate(result["spec"]))
    else:
        calculated = describe_regions(report, config["field_snapshot"], parse_descriptive_request(result["spec"]))
    calculated["revision_id"] = report["revision_id"]
    if result.get("source_review") == "automatic_unreviewed":
        if config.get("recipe", {}).get("version") not in ("1.2.0", "1.3.0", "1.4.0") or result["spec"].get("mode") != "descriptive":
            raise ValueError("region_export_statistics_unrecognized_fields")
        calculated["source_review"] = "automatic_unreviewed"
    if set(result) - (set(calculated) | {"figure"}):
        raise ValueError("region_export_statistics_unrecognized_fields")
    return calculated


def _render_statistics(calculated, folder, *, methods_template=None, saved_figure=None):
    if _uses_common_statistics(calculated):
        from .common_statistics_figures import render_common_statistics

        version = (saved_figure or {}).get("common_statistics_figure_version", "1.0.0")
        return render_common_statistics(calculated, folder, methods_template=methods_template,
                                        figure_version=version)
    if calculated["analysis_kind"] == "region-comparison":
        from .region_comparison_figures import render_region_comparison

        return render_region_comparison(calculated, folder, methods_template=methods_template)
    from .descriptive_figures import render_descriptive

    return render_descriptive(calculated, folder, methods_template=methods_template)


def build_region_bundle(destination: Path, *, report, config, provenance, mask_files,
                        raw_files=(), statistics_results=(), statistics_roots=(), include_raw=False):
    """Bundle owned server paths only; public URL/access checks belong to the API."""
    request = _request(config)
    validate_region_report_policy(region_report_from_json(json.dumps(report)), config)
    if report.get("analysis_kind") != "region-2d" or report.get("recipe") != request.recipe.model_dump(mode="json"):
        raise ValueError("region_bundle_report_mismatch")
    mask_files = dict(mask_files)
    if set(mask_files) != set(report["field_masks"]):
        raise ValueError("region_bundle_masks_incomplete")
    statistics_results = list(statistics_results)
    statistics_roots = dict(statistics_roots)
    descriptions = []
    for result in statistics_results:
        calculated = _recompute_statistics(report, config, result)
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
        if fid in report["field_tables"] and request.measurement is None:
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
    for index, calculated in enumerate(descriptions):
        folder = content / "statistics" / str(index)
        if calculated["analysis_kind"] == "descriptive" and "figure_policy" in calculated["spec"]:
            from .descriptive_output import copy_descriptive_output

            if index not in statistics_roots:
                raise ValueError("descriptive_output_source_required")
            figure = copy_descriptive_output(statistics_results[index], Path(statistics_roots[index]), folder)
        else:
            figure = _render_statistics(calculated, folder, methods_template=_statistics_methods_template(statistics_results[index]),
                                        saved_figure=statistics_results[index].get("figure"))
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
        "fields remain diagnostic and are not reassessed. Descriptive or experimental-unit figures are regenerated "
        "from the recorded selector, design and source metadata. A zero exit status confirms regenerated "
        "measurements and statistical values equal the saved values. "
        "It does not confirm biological annotation correctness. Keep input and output directories private.\n", encoding="utf-8")
    members = sorted(path for path in content.rglob("*") if path.is_file())
    _json(content / "manifest.json", {
        "format": bundle_format(request.measurement),
        "revision_id": report["revision_id"], "raw_included": include_raw, "raw_files": raw_manifest,
        "replay_scope": "saved masks of measured fields -> measurements -> recorded statistics and figures; failures preserved",
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
    if manifest.get("format") not in (FORMAT, AREA_FORMAT, RAW_FORMAT):
        raise ValueError("region_bundle_format_unsupported")
    for relative, expected_hash in manifest["files"].items():
        path = _safe_path(bundle_dir, relative)
        if not path.is_file() or sha256(path) != expected_hash:
            raise ValueError("region_bundle_file_hash_mismatch")
    record = json.loads((bundle_dir / "revision.json").read_text(encoding="utf-8"))
    config = record["config"]
    request = _request(config)
    report = json.loads((bundle_dir / "measurements.json").read_text(encoding="utf-8"))
    validate_region_report_policy(region_report_from_json(json.dumps(report)), config)
    expected_format = bundle_format(request.measurement)
    if manifest["format"] != expected_format:
        raise ValueError("region_measurement_protocol_mismatch")
    if request.measurement is not None and (
            any(re.fullmatch(r"masks/[^/]+/background-[^/]+\.npy", name) for name in manifest["files"])
            or any((bundle_dir / "masks").glob("*/background-*.npy"))):
        raise ValueError("region_area_only_backgrounds_forbidden")
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
        channels = {channel.channel_id: read_tiff(_safe_path(raw_dir, f"{fid}/ch{index}.tif"),
                                               legacy=info.input_mode == "display-rgb")
                    for index, channel in enumerate(info.channels)}
        if any(list(array.shape) != info.shape for array in channels.values()):
            raise ValueError("region_replay_input_shape_mismatch")
        mask_record = report["field_masks"][fid]
        path = _safe_path(bundle_dir, f"masks/{fid}/labels.npy")
        labels = np.load(path, mmap_mode="r", allow_pickle=False)
        validate_label_array(labels)
        if _array_hash(labels, "<u4") != mask_record["mask_sha256"] or list(labels.shape) != mask_record["shape"]:
            raise ValueError("region_bundle_mask_pixels_mismatch")
        backgrounds = ({cid: polygon_mask(labels.shape, background.polygon)
                        for cid, background in request.backgrounds[fid].items()}
                       if request.measurement is None else {})
        table = measure_regions_versioned(channels, labels, backgrounds, scientific_specification(
            field_id=fid, revision_id=report["revision_id"], mask_revision_id=mask_record["mask_revision_id"],
            recipe=request.recipe, image_info=info, measurement=request.measurement,
        ))
        tables[fid] = table.model_dump(mode="json")
    reproduced = {**report, "field_tables": tables}
    _json(output_dir / "measurements.json", reproduced)
    write_csv(output_dir / "regions.csv", _long_rows(reproduced, config))
    descriptions_match = True
    comparisons_match = True
    has_comparisons = False
    associations_match = True
    has_associations = False
    paged_outputs = []
    for path in sorted((bundle_dir / "statistics").glob("*/result.json")):
        result = json.loads(path.read_text(encoding="utf-8"))
        replayed = _recompute_statistics(reproduced, config, result)
        matches = all(result.get(key) == value for key, value in replayed.items())
        if result["analysis_kind"] == "region-comparison":
            has_comparisons = True
            comparisons_match &= matches
        elif result["analysis_kind"] == "region-association":
            has_associations = True
            associations_match &= matches
        else:
            descriptions_match &= matches
        folder = output_dir / "statistics" / path.parent.name
        if replayed["analysis_kind"] == "descriptive" and "figure_policy" in replayed["spec"]:
            from .descriptive_output import replay_descriptive_output

            replayed["figure"] = replay_descriptive_output(result, replayed, path.parent, folder)
            paged_outputs.append({"statistics_index": path.parent.name, "status": replayed["figure"]["status"]})
        else:
            replayed["figure"] = _render_statistics(replayed, folder, methods_template=_statistics_methods_template(result),
                                                    saved_figure=result.get("figure"))
        _json(folder / "result.json", replayed)
    comparison = {
        "matched_saved_measurements": tables == report["field_tables"],
        "matched_saved_descriptions": descriptions_match,
        "measured_fields_replayed": sorted(tables),
        "unmeasured_fields_preserved_not_reassessed": sorted(set(request.field_ids or []) - set(tables)),
    }
    if has_comparisons:
        comparison["matched_saved_comparisons"] = comparisons_match
    if has_associations:
        comparison["matched_saved_associations"] = associations_match
    if paged_outputs:
        comparison["descriptive_outputs"] = paged_outputs
        comparison["descriptive_figures_ready"] = all(item["status"] == "ready" for item in paged_outputs)
    _json(output_dir / "replay-verification.json", comparison)
    return comparison


def main():
    parser = argparse.ArgumentParser(description="Replay generic measurements with verified original pixels and saved masks")
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = replay_region_bundle(args.bundle_dir, args.raw_dir, args.output_dir)
    if (not result["matched_saved_measurements"] or not result["matched_saved_descriptions"]
            or not result.get("matched_saved_comparisons", True)
            or not result.get("matched_saved_associations", True)):
        raise SystemExit("region_replay_measurement_mismatch")
    if not result.get("descriptive_figures_ready", True):
        raise SystemExit("descriptive_replay_figure_unavailable")


if __name__ == "__main__":
    main()
