"""Generic region jobs using the shared original-pixel measurement protocol.

HTTP ownership/CAS and fenced publication belong to the existing API/supervisor.
This worker independently validates snapshots and source files before measuring.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import numpy as np
from cytellect_analysis.cellpose_engine import detect_cellpose
from cytellect_analysis.compartment_engine import detect_compartments, nucleoplasm_from_adopted_nucleoli
from cytellect_analysis.compartment_review import comparable_region_recipe
from cytellect_analysis.compartment_summary import compartment_summary
from cytellect_analysis.engine import detect_nuclei
from cytellect_analysis.images import sha256
from cytellect_analysis.masks import (
    apply_compartment_edit,
    apply_label_edit,
    polygon_mask,
    validate_label_array,
)
from cytellect_analysis.nuclear_scale import automatic_detection_max_side, estimate_nuclear_diameter
from cytellect_analysis.plan_adoption import validate_revision_plan
from cytellect_analysis.region_contracts import (
    AdoptedNuclearRecipe,
    AutoScaledNuclearRecipe,
    RegionAnalysisRequest,
    RegionCellposeRecipe,
    RegionCompartmentRecipe,
    RegionFieldMetadata,
    RegionImageInfo,
    RegionMaskEdit,
    RegionNuclearRecipe,
    RegionSignalRecipe,
    RegionStoredFile,
    ScaledNuclearRecipe,
    region_report_from_json,
    scientific_specification,
    validate_nuclear_role_evidence,
    validate_region_report_policy,
)
from cytellect_analysis.region_measurement_v2 import measure_regions_versioned
from cytellect_analysis.region_metadata import validate_region_reuse
from cytellect_analysis.region_policy import measurement_protocol
from cytellect_analysis.regions import _array_hash
from cytellect_analysis.signal_engine import detect_positive_regions
from cytellect_api.db import fields, jobs, revisions
from cytellect_api.mask_dependencies import can_rebind_compartment
from cytellect_api.storage import read_json, write_json

from .provenance import software_identity

REGION_FIELD_ERRORS = {
    "cellpose_adapter_missing", "cellpose_runtime_missing", "cellpose_model_missing",
    "cellpose_adapter_integrity_failed", "cellpose_model_integrity_failed", "cellpose_input_invalid",
    "cellpose_inference_failed", "cellpose_inference_timeout", "cellpose_output_shape_invalid",
    "cellpose_gpu_unavailable", "cellpose_runtime_version_mismatch", "cellpose_memory_exhausted",
    "region_input_file_missing", "region_input_file_size_mismatch", "region_input_file_hash_mismatch",
    "region_source_array_invalid", "region_source_shape_or_dtype_invalid",
    "region_source_snapshot_missing", "region_source_snapshot_mismatch", "region_field_kind_mismatch",
    "region_imported_labels_required", "region_manual_source_has_imported_labels",
    "region_parent_mask_missing", "region_parent_mask_mismatch", "region_stale_mask_revision",
    "region_edit_requires_parent", "region_edit_set_mismatch", "region_unknown_excluded_object",
    "region_unknown_defining_channel", "region_channel_or_background_mapping_mismatch",
    "region_background_nonempty_boolean_shape_required", "region_background_overlaps_measured_regions",
    "acquisition_limit_inconsistent_with_source", "calibrated_region_area_unrepresentable",
    "region_plane_limit_exceeded", "invalid_label_array", "invalid_edit_labels", "unknown_label",
    "label_id_exhausted", "replace_requires_one_label", "overlap_requires_explicit_merge",
    "select_labels", "merge_requires_multiple_labels", "split_requires_one_label",
    "split_requires_partial_region", "invalid_polygon", "polygon_outside_image",
    "degenerate_polygon", "empty_polygon", "unsupported_label_operation",
    "nucleolus_outside_parent", "nucleoli_span_parents", "nucleoplasm_is_derived",
    "compartment_nucleolar_source_invalid", "compartment_nucleolar_mask_mismatch",
    "region_automatic_source_has_imported_labels", "region_parent_detector_provenance_invalid",
    "fiji_not_configured", "fiji_assets_unavailable", "fiji_artifact_hash_mismatch", "fiji_model_hash_mismatch",
    "fiji_bundled_jdk_unavailable", "fiji_detection_capacity_exceeded", "fiji_timeout",
    "fiji_process_unavailable", "fiji_execution_failed", "fiji_input_dimensions", "fiji_input_format",
    "fiji_invalid_output_labels", "fiji_invalid_output_provenance",
    "fiji_temporary_path_invalid", "fiji_temporary_path_too_long",
    "region_area_only_backgrounds_forbidden", "region_measurement_protocol_mismatch",
    "region_automatic_background_roi_conflict", "region_background_exclusion_invalid",
    "region_metric_not_measured", "signal_threshold_indeterminate",
    "compartment_nuclear_source_invalid", "compartment_source_image_mismatch",
    "compartment_nuclear_mask_mismatch", "compartment_nuclear_source_excluded",
    "nuclear_recorded_stain_required", "unknown_defining_channel",
    "cohort_source_invalid", "cohort_source_changed", "cohort_source_field_not_measured",
}


def _verify_file(path: Path, record: RegionStoredFile) -> None:
    if not path.is_file():
        raise ValueError("region_input_file_missing")
    if path.stat().st_size != record.bytes:
        raise ValueError("region_input_file_size_mismatch")
    if sha256(path) != record.sha256:
        raise ValueError("region_input_file_hash_mismatch")


def _load_array(path: Path, record: RegionStoredFile) -> np.ndarray:
    _verify_file(path, record)
    array = np.load(path, allow_pickle=False, mmap_mode="r")
    if not isinstance(array, np.ndarray):
        raise ValueError("region_source_array_invalid")
    return array


def _file_record(path: Path) -> dict:
    return {"sha256": sha256(path), "bytes": path.stat().st_size}


def _initial_labels(folder: Path, image_info: RegionImageInfo, source: str) -> np.ndarray:
    if source == "manual":
        if image_info.labels_array is not None:
            raise ValueError("region_manual_source_has_imported_labels")
        return np.zeros(image_info.shape, dtype=np.uint32)
    if image_info.labels_array is None:
        raise ValueError("region_imported_labels_required")
    labels = _load_array(folder / "labels.npy", image_info.labels_array)
    validate_label_array(labels)
    if list(labels.shape) != image_info.shape:
        raise ValueError("region_source_shape_or_dtype_invalid")
    return labels


def _compartment_nuclei(store, recipe, workspace_id, fid, image_info):
    source = store.one(revisions, id=recipe.nuclear_revision_id)
    if (not source or source["workspace_id"] != workspace_id or source["state"] != "succeeded"
            or not source["result_dir"] or source["config"].get("analysis_kind") != "region-2d"
            or source["config"].get("recipe", {}).get("source") != "stardist_nuclear"
            or source["config"]["recipe"].get("defining_channel_id") != recipe.nuclear_channel_id):
        raise ValueError("compartment_nuclear_source_invalid")
    original = source["config"].get("field_snapshot", {}).get(fid)
    if (original is None or RegionImageInfo.model_validate(original["image_info"]) != image_info):
        raise ValueError("compartment_source_image_mismatch")
    report = read_json(store.safe_path(source["result_dir"], "measurements.json"))
    validate_region_report_policy(region_report_from_json(json.dumps(report)), source["config"])
    mask = report.get("field_masks", {}).get(fid)
    if (not mask or fid not in report.get("field_tables", {}) or mask["source"] != "stardist_nuclear"
            or mask["shape"] != image_info.shape):
        raise ValueError("compartment_nuclear_source_invalid")
    labels = _load_array(store.safe_path(source["result_dir"], fid, "labels.npy"),
                         RegionStoredFile.model_validate(mask["file"]))
    validate_label_array(labels)
    if list(labels.shape) != image_info.shape or _array_hash(labels, "<u4") != mask["mask_sha256"]:
        raise ValueError("compartment_nuclear_mask_mismatch")
    exclusions = [item for item in report["exclusions"] if item["field_id"] == fid]
    if any(item["region_id"] is None for item in exclusions):
        raise ValueError("compartment_nuclear_source_excluded")
    source_labels = np.asarray(labels)
    labels = labels.copy()
    excluded_ids = [item["region_id"] for item in exclusions]
    labels[np.isin(labels, excluded_ids)] = 0
    return labels, source_labels, {"revision_id": source["id"], "mask_revision_id": mask["mask_revision_id"],
                    "mask_sha256": mask["mask_sha256"], "exclusions": exclusions,
                    "effective_mask_sha256": _array_hash(labels, "<u4"),
                    "nuclear_channel_id": recipe.nuclear_channel_id}


def _compartment_summary_report(inputs, nucleoplasm, channels, table) -> dict:
    """Per-nucleus ratios from original pixels: raw values always, corrected values
    only from an established automatic background (protocol 4.0.0); a channel
    without one keeps its corrected summary missing with the reason."""
    nuclei, nucleoli, identity = inputs
    report = {"nucleolar_revision": identity,
              "channels": {cid: compartment_summary(nuclei, nucleoli, nucleoplasm, plane)
                           for cid, plane in channels.items()}}
    if table.protocol_version == "4.0.0":
        corrected = {}
        for item in table.channel_provenance:
            cid, background = item.channel.channel_id, item.background
            corrected[cid] = (compartment_summary(nuclei, nucleoli, nucleoplasm, channels[cid],
                                                  background.background_median)
                              if background.status == "established"
                              else {"protocol": "compartment-summary/1.0.0", "rows": [],
                                    "missing_reason": background.reason})
        report["corrected_channels"] = corrected
        report["background"] = "automatic_candidate"
    return report


def _adopted_nucleoli(store, recipe, workspace_id, fid, image_info):
    """Load the adopted nucleoli labels (with exclusions) that define nucleoplasm."""
    source = store.one(revisions, id=recipe.nucleolar_revision_id)
    source_recipe = (source or {}).get("config", {}).get("recipe", {})
    if (not source or source["workspace_id"] != workspace_id or source["state"] != "succeeded"
            or not source["result_dir"] or source["config"].get("analysis_kind") != "region-2d"
            or source_recipe.get("source") != "fiji_nuclear_compartment"
            or source_recipe.get("compartment") != "nucleoli"
            or source_recipe.get("nuclear_revision_id") != recipe.nuclear_revision_id
            or source_recipe.get("nuclear_channel_id") != recipe.nuclear_channel_id
            or source_recipe.get("defining_channel_id") != recipe.defining_channel_id):
        raise ValueError("compartment_nucleolar_source_invalid")
    report = read_json(store.safe_path(source["result_dir"], "measurements.json"))
    validate_region_report_policy(region_report_from_json(json.dumps(report)), source["config"])
    mask = report.get("field_masks", {}).get(fid)
    if not mask or mask["shape"] != image_info.shape:
        raise ValueError("compartment_nucleolar_source_invalid")
    labels = _load_array(store.safe_path(source["result_dir"], fid, "labels.npy"),
                         RegionStoredFile.model_validate(mask["file"]))
    validate_label_array(labels)
    if _array_hash(labels, "<u4") != mask["mask_sha256"]:
        raise ValueError("compartment_nucleolar_mask_mismatch")
    exclusions = [item for item in report["exclusions"] if item["field_id"] == fid]
    labels = labels.copy()
    labels[np.isin(labels, [item["region_id"] for item in exclusions if item["region_id"] is not None])] = 0
    provenance = read_json(store.safe_path(source["result_dir"], "provenance.json"))
    engine = provenance.get("fields", {}).get(fid, {}).get("detector", {}).get("engine", {})
    return labels, engine.get("nucleolar_states", {}), {
        "revision_id": source["id"], "mask_revision_id": mask["mask_revision_id"],
        "mask_sha256": mask["mask_sha256"], "exclusions": exclusions,
        "effective_mask_sha256": _array_hash(labels, "<u4")}


def run_region_analysis(store, settings, job, output):
    """Measure manual/imported or confirmed nuclear regions without invented markers."""
    revision = store.one(revisions, id=job["revision_id"])
    if revision is None or revision["workspace_id"] != job["workspace_id"]:
        raise ValueError("revision_not_found")
    config = revision["config"]
    validate_revision_plan(config)
    if config.get("analysis_kind") != "region-2d":
        raise ValueError("region_revision_kind_mismatch")
    request = RegionAnalysisRequest.model_validate({
        key: config[key] for key in ("field_ids", "reuse_revision", "recipe", "backgrounds", "exclusions", "measurement")
        if key in config
    })
    selected = request.field_ids
    if not selected or set(config.get("field_snapshot", {})) != set(selected):
        raise ValueError("region_field_snapshot_invalid")
    if (set(request.backgrounds) - set(selected)
            or any(item.field_id not in selected for item in request.exclusions)):
        raise ValueError("region_unknown_field_reference")
    edit = RegionMaskEdit.model_validate(config["region_edit"]) if config.get("region_edit") else None
    if edit and (edit.field_id not in selected or edit.region_set_id != request.recipe.region_set_id):
        raise ValueError("region_edit_set_mismatch")
    parent = None
    dependency_rebind = False
    previous_report, previous_provenance = {}, {}
    if config.get("reuse_revision"):
        parent = store.one(revisions, id=config["reuse_revision"])
        if (parent is None or parent["workspace_id"] != revision["workspace_id"]
                or parent["state"] != "succeeded" or not parent["result_dir"]
                or parent["config"].get("analysis_kind") != "region-2d"):
            raise ValueError("parent_revision_unavailable")
        dependency_rebind = can_rebind_compartment(
            store, parent["config"]["recipe"], request.recipe.model_dump(mode="json"),
            revision["workspace_id"], selected,
        )
        validate_region_reuse(parent, config, request.recipe.model_dump(mode="json"),
                              verified_dependency_rebind=dependency_rebind)
        previous_report = read_json(store.safe_path(parent["result_dir"], "measurements.json"))
        validate_region_report_policy(region_report_from_json(json.dumps(previous_report)), parent["config"])
        previous_provenance = read_json(store.safe_path(parent["result_dir"], "provenance.json"))
    elif edit:
        raise ValueError("region_edit_requires_parent")
    cohort = config.get("cohort_sources") if not config.get("reuse_revision") else None
    if cohort is not None and (config.get("cohort_version") not in ("1.0.0", "1.1.0") or set(cohort) != set(selected)
                               or (config.get("cohort_version") == "1.0.0"
                                   and config.get("measurement") != {"version": "1.1.0", "mode": "raw_intensity"})):
        raise ValueError("cohort_source_invalid")
    output.mkdir(parents=True, exist_ok=False)
    field_tables, field_masks, provenance_fields = {}, {}, {}
    outcomes: dict[str, str] = {}
    failures, excluded_failures = [], []
    detector_executed = False
    detector_attempted = False
    for fid in selected:
        field_exclusion = next((item.reason for item in request.exclusions
                                if item.field_id == fid and item.region_id is None), None)
        detection_started = False
        try:
            if cohort is not None:
                pin = cohort[fid]
                parent = store.one(revisions, id=pin["revision_id"])
                if (not parent or parent["workspace_id"] != revision["workspace_id"] or parent["state"] != "succeeded"
                        or not parent["result_dir"] or comparable_region_recipe(parent["config"].get("recipe", {})) != comparable_region_recipe(config["recipe"])
                        or parent["config"].get("measurement") != config.get("measurement")
                        or parent["config"].get("backgrounds", {}).get(fid) != config.get("backgrounds", {}).get(fid)):
                    raise ValueError("cohort_source_invalid")
                root = store.safe_path(parent["result_dir"])
                if (sha256(root / "measurements.json") != pin["report_sha256"]
                        or sha256(root / "provenance.json") != pin["provenance_sha256"]):
                    raise ValueError("cohort_source_changed")
                previous_report = read_json(root / "measurements.json")
                previous_provenance = read_json(root / "provenance.json")
                validate_region_report_policy(region_report_from_json(json.dumps(previous_report)), parent["config"])
                original = parent["config"].get("field_snapshot", {}).get(fid)
                supplied = config["field_snapshot"][fid]
                if (original is None or {**original, "metadata": supplied["metadata"]} != supplied):
                    raise ValueError("cohort_source_changed")
                mask = previous_report.get("field_masks", {}).get(fid)
                if (fid not in previous_report["field_tables"] or not mask
                        or mask["mask_revision_id"] != pin["mask_revision_id"] or mask["mask_sha256"] != pin["mask_sha256"]):
                    raise ValueError("cohort_source_field_not_measured")
                source_exclusions = [item for item in parent["config"].get("exclusions", []) if item["field_id"] == fid]
                if source_exclusions != [item for item in config.get("exclusions", []) if item["field_id"] == fid]:
                    raise ValueError("cohort_source_changed")
            field = store.one(fields, id=fid)
            snapshot = config["field_snapshot"][fid]
            if field is None or field["workspace_id"] != revision["workspace_id"]:
                raise ValueError("region_source_snapshot_missing")
            if snapshot.get("id") != fid or snapshot.get("workspace_id") != revision["workspace_id"]:
                raise ValueError("region_source_snapshot_mismatch")
            image_info = RegionImageInfo.model_validate(snapshot["image_info"])
            validate_nuclear_role_evidence(request.recipe, image_info)
            RegionFieldMetadata.model_validate(snapshot["metadata"])
            folder = store.safe_path("workspaces", revision["workspace_id"], "fields", fid)
            for slot, record in image_info.inputs.items():
                _verify_file(folder / f"{slot}.tif", record)
            channels = {channel.channel_id: _load_array(folder / f"channel-{channel.channel_id}.npy",
                                                         image_info.channel_arrays[channel.channel_id])
                        for channel in image_info.channels}
            if any(list(array.shape) != image_info.shape or array.dtype not in (np.uint8, np.uint16)
                   for array in channels.values()):
                raise ValueError("region_source_shape_or_dtype_invalid")
            if request.recipe.defining_channel_id is not None and request.recipe.defining_channel_id not in channels:
                raise ValueError("region_unknown_defining_channel")
            nuclear = isinstance(request.recipe, (RegionNuclearRecipe, AdoptedNuclearRecipe, ScaledNuclearRecipe, AutoScaledNuclearRecipe, RegionSignalRecipe, RegionCompartmentRecipe, RegionCellposeRecipe))
            if nuclear and image_info.labels_array is not None:
                raise ValueError("region_automatic_source_has_imported_labels")
            previously_selected = parent is not None and fid in parent["config"]["field_snapshot"]
            old_mask = previous_report.get("field_masks", {}).get(fid) if previously_selected else None
            mask_revision_id = revision["id"]
            history = list(previous_provenance.get("fields", {}).get(fid, {}).get("history", []))
            if cohort is not None:
                history.append({"revision_id": revision["id"], "operation": "cohort_assembly",
                                "source_revision_id": cohort[fid]["revision_id"], "metadata_supplied": True})
            if fid in config.get("region_metadata_edit", {}).get("fields", {}):
                history.append({"revision_id": revision["id"], "operation": "metadata",
                                "metadata_edit_version": "1.0.0"})
            provenance_fields[fid] = {"history": history, "inputs": image_info.model_dump(mode="json")["inputs"],
                                      "source_channels": [c.model_dump(mode="json") for c in image_info.channels]}
            source_nuclei = None
            summary_inputs = None
            # Every source nucleus, including excluded ones, is kept out of an
            # automatic background candidate; it is never used for measurement.
            background_exclusion = None
            if isinstance(request.recipe, RegionCompartmentRecipe) or (isinstance(request.recipe, RegionCellposeRecipe) and request.recipe.nuclear_revision_id is not None):
                source_recipe = (type(request.recipe).model_validate(parent["config"]["recipe"])
                                 if cohort is not None and parent is not None else request.recipe)
                source_nuclei, background_exclusion, source_identity = _compartment_nuclei(
                    store, source_recipe, revision["workspace_id"], fid, image_info)
                provenance_fields[fid]["nuclear_source"] = source_identity
                if old_mask is not None:
                    previous_identity = previous_provenance.get("fields", {}).get(fid, {}).get("nuclear_source")
                    if dependency_rebind and isinstance(previous_identity, dict):
                        previous_identity = {**previous_identity, "revision_id": source_identity["revision_id"]}
                    if previous_identity != source_identity:
                        raise ValueError("compartment_nuclear_mask_mismatch")
            destination = output / fid
            destination.mkdir()
            if old_mask is not None:
                assert parent is not None
                labels = _load_array(store.safe_path(parent["result_dir"], fid, "labels.npy"),
                                     RegionStoredFile.model_validate(old_mask["file"]))
                validate_label_array(labels)
                if (list(labels.shape) != image_info.shape or old_mask["shape"] != image_info.shape
                        or old_mask["region_set_id"] != request.recipe.region_set_id
                        or old_mask["source"] != request.recipe.source
                        or _array_hash(labels, "<u4") != old_mask["mask_sha256"]):
                    raise ValueError("region_parent_mask_mismatch")
                mask_revision_id = old_mask["mask_revision_id"]
                if isinstance(request.recipe, (RegionNuclearRecipe, AdoptedNuclearRecipe, ScaledNuclearRecipe, AutoScaledNuclearRecipe, RegionSignalRecipe, RegionCompartmentRecipe, RegionCellposeRecipe)):
                    detector = deepcopy(previous_provenance.get("fields", {}).get(fid, {}).get("detector"))
                    channel = next(c for c in image_info.channels if c.channel_id == request.recipe.defining_channel_id)
                    image = channels[channel.channel_id]
                    pixel_hash = _array_hash(image, "|u1" if image.dtype.itemsize == 1 else "<u2")
                    recorded_channel = detector.get("defining_channel") if isinstance(detector, dict) else None
                    current_channel = channel.model_dump(mode="json")
                    same_channel = recorded_channel == current_channel
                    if not same_channel and isinstance(recorded_channel, dict) and current_channel.get("identity_confirmed") is True:
                        # Explicit identity confirmation changes evidence only, never acquisition metadata.
                        same_channel = ({key: value for key, value in recorded_channel.items() if key not in ("identity_source", "identity_confirmed")}
                                        == {key: value for key, value in current_channel.items() if key not in ("identity_source", "identity_confirmed")})
                    if (not isinstance(detector, dict) or not detector.get("origin_revision_id")
                            or not isinstance(detector.get("engine"), dict)
                            or not same_channel
                            or detector.get("input_sha256") != pixel_hash
                            or detector.get("parameters") != request.recipe.detector.model_dump(mode="json")):
                        raise ValueError("region_parent_detector_provenance_invalid")
                    if (isinstance(request.recipe, ScaledNuclearRecipe)
                            and detector.get("detection_max_side_px") != request.recipe.detection_max_side_px):
                        raise ValueError("region_parent_detector_provenance_invalid")
                    if (isinstance(request.recipe, AutoScaledNuclearRecipe)
                            and (detector.get("detection_scale") or {}).get("protocol") != request.recipe.detection_scale):
                        raise ValueError("region_parent_detector_provenance_invalid")
                    detector["executed_this_attempt"] = False
                    provenance_fields[fid]["detector"] = detector
            else:
                if (edit and edit.field_id == fid) or (previously_selected and fid in previous_report.get("field_tables", {})):
                    raise ValueError("region_parent_mask_missing")
                if isinstance(request.recipe, (RegionNuclearRecipe, AdoptedNuclearRecipe, ScaledNuclearRecipe, AutoScaledNuclearRecipe, RegionSignalRecipe, RegionCompartmentRecipe, RegionCellposeRecipe)):
                    channel = next(c for c in image_info.channels if c.channel_id == request.recipe.defining_channel_id)
                    image = channels[channel.channel_id]
                    detection_started = True
                    detector_attempted = True
                    if (isinstance(request.recipe, RegionCompartmentRecipe)
                            and request.recipe.nucleolar_revision_id is not None):
                        assert source_nuclei is not None
                        adopted, states, nucleolar_identity = _adopted_nucleoli(
                            store, request.recipe, revision["workspace_id"], fid, image_info)
                        labels, engine_info = nucleoplasm_from_adopted_nucleoli(source_nuclei, adopted, states)
                        engine_info["nucleolar_revision"] = nucleolar_identity
                        # Written after measurement so an automatic background can be applied.
                        summary_inputs = (source_nuclei, adopted, nucleolar_identity)
                        provenance_fields[fid]["nucleolar_source"] = nucleolar_identity
                    elif isinstance(request.recipe, RegionCompartmentRecipe):
                        assert source_nuclei is not None
                        masks, engine_info = detect_compartments(
                            channels={"dapi": channels[request.recipe.nuclear_channel_id], "ncl": image},
                            nuclei=source_nuclei, parameters=request.recipe.detector,
                            output_dir=destination / "engine", executable=settings.fiji_executable or "",
                            scratch_root=output.parent,
                        )
                        labels = masks[request.recipe.compartment]
                    elif isinstance(request.recipe, RegionCellposeRecipe):
                        labels, engine_info = detect_cellpose(image, request.recipe.detector, destination / "engine")
                        if source_nuclei is not None:
                            pairs = {}
                            for nucleus_id in (int(v) for v in np.unique(source_nuclei) if v):
                                values, counts = np.unique(labels[source_nuclei == nucleus_id], return_counts=True)
                                pairs[nucleus_id] = {int(v): int(n) for v, n in zip(values, counts, strict=True)}
                            engine_info["nuclear_cell_overlap_pixels"] = pairs
                            engine_info["nuclear_association_policy"] = "record_all_overlaps_no_forced_one_to_one"
                    elif isinstance(request.recipe, RegionSignalRecipe):
                        labels, engine_info = detect_positive_regions(
                            image, request.recipe.detector, destination / "engine", settings.fiji_executable or "",
                            scratch_root=output.parent,
                        )
                    elif isinstance(request.recipe, AutoScaledNuclearRecipe):
                        # The detection copy is sized from this field's own nuclear pixels.
                        scale_record = estimate_nuclear_diameter(image)
                        scale_record["detection_max_side_px"] = automatic_detection_max_side(
                            image.shape, scale_record["diameter_px"])
                        labels, engine_info = detect_nuclei(
                            image, request.recipe.detector, destination / "engine", settings.fiji_executable or "",
                            scratch_root=output.parent, detection_max_side=scale_record["detection_max_side_px"],
                        )
                    elif isinstance(request.recipe, ScaledNuclearRecipe):
                        labels, engine_info = detect_nuclei(
                            image, request.recipe.detector, destination / "engine", settings.fiji_executable or "",
                            scratch_root=output.parent, detection_max_side=request.recipe.detection_max_side_px,
                        )
                    else:
                        labels, engine_info = detect_nuclei(
                            image, request.recipe.detector, destination / "engine", settings.fiji_executable or "",
                            scratch_root=output.parent,
                        )
                    validate_label_array(labels)
                    if list(labels.shape) != image_info.shape:
                        raise ValueError("fiji_invalid_output_labels")
                    detector_executed = True
                    provenance_fields[fid]["detector"] = {
                        "protocol_version": "1.0.0", "origin_revision_id": revision["id"],
                        "defining_channel": channel.model_dump(mode="json"),
                        "input_sha256": _array_hash(image, "|u1" if image.dtype.itemsize == 1 else "<u2"),
                        "parameters": request.recipe.detector.model_dump(mode="json"),
                        "engine": engine_info, "executed_this_attempt": True,
                    }
                    if isinstance(request.recipe, ScaledNuclearRecipe):
                        provenance_fields[fid]["detector"]["detection_max_side_px"] = request.recipe.detection_max_side_px
                    if isinstance(request.recipe, AutoScaledNuclearRecipe):
                        provenance_fields[fid]["detector"]["detection_scale"] = scale_record
                    detection_started = False
                    if isinstance(request.recipe, RegionSignalRecipe) and engine_info.get("status") == "indeterminate":
                        raise ValueError("signal_threshold_indeterminate")
                else:
                    labels = _initial_labels(folder, image_info, request.recipe.source)
                history.append({"revision_id": revision["id"], "operation": "initialize",
                                "source": request.recipe.source})
            if edit and edit.field_id == fid:
                if (edit.expected_mask_revision_id is not None
                        and edit.expected_mask_revision_id != mask_revision_id):
                    raise ValueError("region_stale_mask_revision")
                if isinstance(request.recipe, RegionCompartmentRecipe):
                    assert source_nuclei is not None
                    labels = apply_compartment_edit(labels, source_nuclei, request.recipe.compartment,
                                                    edit.operation, edit.ids, edit.polygon)
                else:
                    labels = apply_label_edit(labels, edit.operation, edit.ids, edit.polygon)
                mask_revision_id = revision["id"]
                history.append({"revision_id": revision["id"], "operation": "edit",
                                "edit": edit.model_dump(mode="json")})
            label_path = destination / "labels.npy"
            np.save(label_path, np.asarray(labels, dtype=np.uint32), allow_pickle=False)
            # Geometry survives background/measurement errors for recovery and review.
            field_masks[fid] = {
                "mask_revision_id": mask_revision_id, "mask_sha256": _array_hash(labels, "<u4"),
                "region_set_id": request.recipe.region_set_id, "source": request.recipe.source,
                "shape": list(labels.shape), "file": _file_record(label_path),
            }
            excluded_objects = {item.region_id for item in request.exclusions
                                if item.field_id == fid and item.region_id is not None}
            if not excluded_objects.issubset(set(np.unique(labels)) - {0}):
                raise ValueError("region_unknown_excluded_object")
            backgrounds = request.backgrounds.get(fid, {})
            if request.measurement is None and set(backgrounds) != set(channels):
                raise ValueError("region_channel_or_background_mapping_mismatch")
            background_masks = {cid: polygon_mask(labels.shape, background.polygon)
                                for cid, background in backgrounds.items()}
            specification = scientific_specification(
                field_id=fid, revision_id=revision["id"], mask_revision_id=mask_revision_id,
                recipe=request.recipe, image_info=image_info,
                measurement=request.measurement,
            )
            automatic = request.measurement is not None and request.measurement.mode == "automatic_background"
            table = measure_regions_versioned(channels, labels, background_masks, specification,
                                              background_exclusion=background_exclusion if automatic else None)
            if (summary_inputs is None and isinstance(request.recipe, RegionCompartmentRecipe)
                    and isinstance(source_recipe, RegionCompartmentRecipe)
                    and source_recipe.nucleolar_revision_id is not None):
                # Remeasuring an adopted nucleoplasm mask must also regenerate
                # its compartment summaries from the same pinned parent masks.
                # Never redetect or copy summary values from an older policy.
                assert source_nuclei is not None
                adopted, _, nucleolar_identity = _adopted_nucleoli(
                    store, source_recipe, revision["workspace_id"], fid, image_info)
                summary_inputs = (source_nuclei, adopted, nucleolar_identity)
                provenance_fields[fid]["nucleolar_source"] = nucleolar_identity
            for cid, background in background_masks.items():
                np.save(destination / f"background-{cid}.npy", background, allow_pickle=False)
            if summary_inputs is not None:
                write_json(destination / "compartment-summary.json",
                           _compartment_summary_report(summary_inputs, labels, channels, table))
            field_tables[fid] = table.model_dump(mode="json")
            outcomes[fid] = table.status
        except Exception as exc:
            error = str(exc) if str(exc) in REGION_FIELD_ERRORS else "region_field_analysis_failed"
            if detection_started:
                provenance_fields[fid]["history"].append({
                    "revision_id": revision["id"], "operation": "detection_failed", "error": error,
                })
            if field_exclusion:
                excluded_failures.append({"field_id": fid, "reason": field_exclusion, "error": error})
                outcomes[fid] = "excluded_failed"
            else:
                failures.append({"field_id": fid, "reason": error})
                outcomes[fid] = "failed"
    protocol = measurement_protocol(request.measurement)
    policy = {"measurement": request.measurement.model_dump(mode="json")} if request.measurement is not None else {}
    report = {
        "analysis_kind": "region-2d", "protocol_version": protocol, "revision_id": revision["id"],
        "recipe": request.recipe.model_dump(mode="json"), "field_tables": field_tables,
        "field_masks": field_masks, "field_outcomes": outcomes, "field_failures": failures,
        "excluded_failed_fields": excluded_failures,
        "exclusions": [item.model_dump(mode="json") for item in request.exclusions],
        **policy,
    }
    # Refuse mixed or unknown table protocols before publishing a result. JSON
    # validation preserves the strict tuple-bearing scientific models.
    validate_region_report_policy(region_report_from_json(json.dumps(report)), config)
    write_json(output / "measurements.json", report)
    write_json(output / "provenance.json", {
        "analysis_kind": "region-2d", "revision_id": revision["id"], "fields": provenance_fields,
        "software": software_identity(), "recipe": request.recipe.model_dump(mode="json"),
        "measurement_protocol": protocol, "detector_executed": detector_executed,
        "detector_attempted": detector_attempted,
        **({"cohort_sources": cohort, "cohort_version": config["cohort_version"]} if cohort is not None else {}),
        **policy,
    })
    return output


def run_region_export(store, job, output):
    """Use the same private job/download boundary as the legacy export path."""
    from cytellect_analysis.region_exports import build_region_bundle

    revision = store.one(revisions, id=job["revision_id"])
    if revision is None or revision["workspace_id"] != job["workspace_id"]:
        raise ValueError("revision_not_found")
    config = revision["config"]
    if config.get("analysis_kind") != "region-2d" or revision["state"] != "succeeded":
        raise ValueError("region_revision_kind_mismatch")
    root = store.safe_path(revision["result_dir"])
    report = read_json(root / "measurements.json")
    raw = []
    include_raw = bool(job["payload"].get("include_raw", False))
    if include_raw:
        for fid, snapshot in config["field_snapshot"].items():
            for slot in snapshot["image_info"]["inputs"]:
                raw.append((f"{fid}/{slot}.tif", store.safe_path("workspaces", revision["workspace_id"],
                                                                "fields", fid, f"{slot}.tif")))
    from .region_export_sources import collect_dependencies

    records = store.rows(jobs, revision_id=revision["id"], kind="statistics", state="succeeded")
    provenance = read_json(root / "provenance.json")
    dependencies = collect_dependencies(store, revision, report, provenance)
    statistics = [read_json(store.safe_path(record["result_dir"], "result.json")) for record in records]
    statistics_roots = [(index, store.safe_path(record["result_dir"])) for index, record in enumerate(records)]
    build_region_bundle(
        output, report=report, config={**config, "review_record": revision["review_record"] or {}},
        provenance=provenance,
        mask_files={fid: store.safe_path(root, fid, "labels.npy") for fid in report["field_masks"]},
        raw_files=raw, statistics_results=statistics, statistics_roots=statistics_roots, include_raw=include_raw,
        dependencies=dependencies,
    )
    summary = {"files": ["analysis.zip", "methods.md"], "raw_included": include_raw, "revision_id": revision["id"]}
    write_json(output / "result.json", summary)
    return output
