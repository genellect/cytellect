"""Read-only source-bound partition table and CSV from adopted original-coordinate masks."""
import hashlib
import json
import math
from pathlib import Path
from typing import Annotated, Any

import numpy as np
from cytellect_analysis.images import sha256
from cytellect_analysis.masks import polygon_mask, validate_labels
from cytellect_analysis.region_contracts import (
    RegionImageInfo,
    RegionStoredFile,
    region_report_from_json,
    validate_nuclear_role_evidence,
    validate_region_report_policy,
)
from cytellect_analysis.region_metadata import image_pixel_identity
from cytellect_analysis.region_partition import region_partition
from cytellect_analysis.region_partition_table import RegionPartitionTable, partition_table_csv
from cytellect_analysis.regions import _array_hash
from fastapi import Depends, HTTPException, Query, Response

MAX_JSON = 32 * 1024 * 1024
MAX_ARRAY = 4096 * 4096 * 4 + 65536
MAX_ORIGINAL = 2 * 1024 ** 3
IdQuery = Annotated[str, Query(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")]


def _plain_file(store, *parts: str) -> Path:
    """Reject links before resolution, including links to files still inside storage."""
    base = store.root
    path = base.joinpath(*parts)
    if not path.is_relative_to(base) or any(part in ("..", ".") for part in path.relative_to(base).parts):
        raise ValueError("partition_source_path_invalid")
    cursor = path
    while cursor != base:
        if cursor.is_symlink() or (hasattr(cursor, "is_junction") and cursor.is_junction()):
            raise ValueError("partition_source_link_forbidden")
        cursor = cursor.parent
    if not path.resolve().is_relative_to(base.resolve()) or not path.is_file():
        raise ValueError("partition_source_file_missing")
    return path


def _verified_file(store, parts, record: RegionStoredFile, maximum: int) -> Path:
    path = _plain_file(store, *parts)
    if record.bytes > maximum or path.stat().st_size != record.bytes:
        raise ValueError("partition_source_file_size_mismatch")
    if sha256(path) != record.sha256:
        raise ValueError("partition_source_file_hash_mismatch")
    return path


def _json_file(store, *parts):
    path = _plain_file(store, *parts)
    if path.stat().st_size > MAX_JSON:
        raise ValueError("partition_source_json_too_large")
    with path.open("rb") as stream:
        content = stream.read(MAX_JSON + 1)
    if len(content) > MAX_JSON:
        raise ValueError("partition_source_json_too_large")
    return json.loads(content), hashlib.sha256(content).hexdigest()


def _load_source(store, rev, fid):
    config = rev["config"]
    snapshot = config.get("field_snapshot", {}).get(fid)
    if snapshot is None or fid not in config.get("field_ids", []):
        raise ValueError("partition_source_field_mismatch")
    info = RegionImageInfo.model_validate(snapshot["image_info"])
    if snapshot.get("id") != fid or snapshot.get("workspace_id") != rev["workspace_id"]:
        raise ValueError("partition_source_field_mismatch")
    report_data, report_hash = _json_file(store, rev["result_dir"], "measurements.json")
    report = region_report_from_json(json.dumps(report_data))
    validate_region_report_policy(report, config)
    if (report.revision_id != rev["id"] or report.recipe.model_dump(mode="json") != config.get("recipe")
            or [item.model_dump(mode="json") for item in report.exclusions] != config.get("exclusions", [])):
        raise ValueError("partition_source_report_mismatch")
    table, mask = report.field_tables.get(fid), report.field_masks.get(fid)
    if table is None or mask is None:
        raise ValueError("partition_source_field_not_measured")
    path = _verified_file(store, (rev["result_dir"], fid, "labels.npy"), mask.file, MAX_ARRAY)
    labels = np.load(path, allow_pickle=False, mmap_mode="r")
    if (not isinstance(labels, np.ndarray) or labels.dtype != np.uint32 or list(labels.shape) != info.shape
            or _array_hash(labels, "<u4") != mask.mask_sha256 or table.calibration != info.calibration):
        raise ValueError("partition_source_mask_mismatch")
    provenance, provenance_hash = _json_file(store, rev["result_dir"], "provenance.json")
    field_provenance = provenance.get("fields", {}).get(fid)
    if (provenance.get("analysis_kind") != "region-2d" or provenance.get("revision_id") != rev["id"]
            or provenance.get("recipe") != config["recipe"] or not isinstance(field_provenance, dict)
            or field_provenance.get("inputs") != snapshot["image_info"]["inputs"]):
        raise ValueError("partition_source_provenance_mismatch")
    declared = [entry.channel.model_dump(mode="json") for entry in table.channel_provenance]
    if declared != [channel.model_dump(mode="json") for channel in info.channels]:
        raise ValueError("partition_source_channel_mismatch")
    exclusions = [item.model_dump(mode="json") for item in report.exclusions if item.field_id == fid]
    present = {int(value) for value in np.unique(labels) if value}
    ids, counts = np.unique(labels[labels > 0], return_counts=True)
    areas = {int(label): int(count) for label, count in zip(ids, counts, strict=True)}
    channels = {channel.channel_id for channel in info.channels}
    seen = set()
    for row in table.rows:
        key = (row.region_id, row.channel_id)
        if (key in seen or row.region_id not in areas or row.channel_id not in channels
                or row.area_px != areas[row.region_id] or row.field_id != fid
                or row.analysis_revision_id != rev["id"] or row.mask_revision_id != mask.mask_revision_id
                or row.region_set_id != mask.region_set_id):
            raise ValueError("partition_source_rows_mismatch")
        seen.add(key)
    if seen != {(region, channel) for region in areas for channel in channels}:
        raise ValueError("partition_source_rows_mismatch")
    if any(item["region_id"] is not None and item["region_id"] not in present for item in exclusions):
        raise ValueError("partition_source_exclusion_invalid")
    source = {
        "revision_id": rev["id"], "region_set_id": mask.region_set_id, "label": report.recipe.label,
        "source": mask.source, "mask_revision_id": mask.mask_revision_id, "mask_sha256": mask.mask_sha256,
        "effective_mask_sha256": mask.mask_sha256, "label_file": mask.file,
        "report_sha256": report_hash, "provenance_sha256": provenance_hash, "reviewed": True,
    }
    return {"rev": rev, "info": info, "recipe": report.recipe, "table": table, "labels": labels, "source": source,
            "exclusions": exclusions, "provenance": field_provenance}


def _source_membership(source, nuclei, nuclear):
    recipe = source["rev"]["config"]["recipe"]
    kind = recipe.get("source")
    parents = {int(value) for value in np.unique(nuclei) if value}
    states = dict.fromkeys(parents, "adopted")
    if kind == "fiji_nuclear_compartment":
        binding = source["provenance"].get("nuclear_source", {})
        expected = nuclear["source"]
        effective_nuclei = np.array(nuclei, copy=True)
        effective_nuclei[np.isin(effective_nuclei, [item["region_id"] for item in nuclear["exclusions"]
                                                    if item["region_id"] is not None])] = 0
        if (recipe.get("nuclear_revision_id") != nuclear["rev"]["id"]
                or any(binding.get(key) != expected[key] for key in ("revision_id", "mask_revision_id", "mask_sha256"))
                or binding.get("exclusions") != nuclear["exclusions"]
                or binding.get("effective_mask_sha256") != _array_hash(effective_nuclei, "<u4")
                or recipe.get("nuclear_channel_id") != nuclear["rev"]["config"]["recipe"].get("defining_channel_id")):
            raise ValueError("partition_compartment_nuclear_binding_mismatch")
        engine = source["provenance"].get("detector", {}).get("engine", {})
        recorded = engine.get("nucleolar_states")
        if not isinstance(recorded, dict):
            raise ValueError("partition_compartment_states_invalid")
        try:
            if any(str(int(key)) != key for key in recorded):
                raise ValueError("partition_compartment_states_invalid")
            states = {int(key): value for key, value in recorded.items()}
        except (TypeError, ValueError):
            raise ValueError("partition_compartment_states_invalid") from None
        if not set(states).issubset(parents) or any(not isinstance(value, str) or not value.replace("_", "").isalnum()
                                         or len(value) > 80 for value in states.values()):
            raise ValueError("partition_compartment_states_invalid")
        missing_count = engine.get("missing_parent_count")
        if missing_count is not None and (type(missing_count) is not int or missing_count != sum(value != "candidate" for value in states.values())):
            raise ValueError("partition_compartment_states_invalid")
        excluded_nuclei = {item["region_id"] for item in nuclear["exclusions"] if item["region_id"] is not None}
        for parent in parents - set(states):
            states[parent] = "nucleus_excluded" if parent in excluded_nuclei else "unclassified"
        if recipe.get("compartment") == "nucleoplasm":
            for key, value in (engine.get("nucleoplasm_missing_reasons") or {}).items():
                if int(key) not in parents or value != "empty_after_subtraction":
                    raise ValueError("partition_compartment_states_invalid")
                states[int(key)] = value
    elif kind not in ("manual", "imported"):
        raise ValueError("partition_membership_source_invalid")
    labels = np.array(source["labels"], copy=True)
    if np.any((labels > 0) & (nuclei == 0)):
        raise ValueError("partition_membership_outside_nuclei")
    if kind == "fiji_nuclear_compartment":
        validate_labels(nuclei, labels)
    if kind == "fiji_nuclear_compartment" and recipe.get("compartment") == "nucleoplasm" and np.any((labels > 0) & (labels != nuclei)):
        raise ValueError("partition_nucleoplasm_label_identity_mismatch")
    object_parents: dict[int, set[int]] = {}
    for object_id, parent in np.unique(np.stack([labels[labels > 0], nuclei[labels > 0]]), axis=1).T:
        object_parents.setdefault(int(object_id), set()).add(int(parent))
    excluded_objects = {item["region_id"] for item in source["exclusions"] if item["region_id"] is not None}
    if excluded_objects:
        labels[np.isin(labels, list(excluded_objects))] = 0
    # A saved label never overrides an unresolved detector/researcher state.
    unresolved_parents = {parent for parent, state in states.items() if state not in ("candidate", "adopted")}
    if unresolved_parents:
        labels[np.isin(nuclei, list(unresolved_parents))] = 0
    source["source"]["effective_mask_sha256"] = _array_hash(labels, "<u4")
    source["states"] = states
    source["object_parents"] = object_parents
    return labels


def _pixels_and_background(store, nuclear, fid, cid):
    info, table = nuclear["info"], nuclear["table"]
    if info.input_mode != "native":
        raise ValueError("partition_native_channel_required")
    entry = next((item for item in table.channel_provenance if item.channel.channel_id == cid), None)
    if entry is None:
        raise ValueError("partition_channel_unknown")
    folder = ("workspaces", nuclear["rev"]["workspace_id"], "fields", fid)
    record = info.channel_arrays[cid]
    path = _verified_file(store, (*folder, f"channel-{cid}.npy"), record, MAX_ARRAY)
    pixels = np.load(path, allow_pickle=False, mmap_mode="r")
    if (not isinstance(pixels, np.ndarray) or list(pixels.shape) != info.shape
            or pixels.dtype not in (np.uint8, np.uint16) or str(pixels.dtype) != entry.dtype):
        raise ValueError("partition_pixel_source_invalid")
    pixel_hash = _array_hash(pixels, "|u1" if pixels.dtype == np.uint8 else "<u2")
    if pixel_hash != entry.pixel_sha256:
        raise ValueError("partition_pixel_source_mismatch")
    original_files = {key: value for key, value in info.inputs.items() if key != "labels"}
    for slot, original in original_files.items():
        _verified_file(store, (*folder, f"{slot}.tif"), original, MAX_ORIGINAL)
    pixel_source = {"channel": entry.channel, "dtype": entry.dtype, "pixel_sha256": pixel_hash,
                    "array_file": record, "original_files": original_files}
    rid = nuclear["rev"]["id"]
    background = {"status": "missing", "reason": "background_not_confirmed", "source_revision_id": rid,
                  "roi_revision_id": None, "mask_sha256": None, "pixel_count": None, "median": None, "polygon": None}
    # Automatic candidates, area-only and raw-only sources never satisfy confirmed ROI provenance.
    if table.protocol_version != "1.0.0":
        return pixels, pixel_source, background
    roi = nuclear["rev"]["config"].get("backgrounds", {}).get(fid, {}).get(cid)
    if not isinstance(roi, dict) or roi.get("confirmed") is not True:
        raise ValueError("partition_background_provenance_mismatch")
    mask = polygon_mask(pixels.shape, roi["polygon"])
    stored = _plain_file(store, nuclear["rev"]["result_dir"], fid, f"background-{cid}.npy")
    if stored.stat().st_size > MAX_ARRAY:
        raise ValueError("partition_background_provenance_mismatch")
    saved = np.load(stored, allow_pickle=False, mmap_mode="r")
    if (not isinstance(saved, np.ndarray) or saved.dtype != np.bool_ or saved.shape != mask.shape
            or not np.array_equal(saved, mask) or np.any(mask & (nuclear["labels"] > 0))):
        raise ValueError("partition_background_provenance_mismatch")
    median = float(np.median(pixels[mask]))
    mask_hash = _array_hash(mask, "|u1")
    if (not math.isfinite(median) or entry.background_revision_id != rid
            or mask_hash != entry.background_mask_sha256 or int(mask.sum()) != entry.background_pixel_count
            or median != entry.background_median):
        raise ValueError("partition_background_provenance_mismatch")
    background.update(status="confirmed", reason=None, roi_revision_id=rid, mask_sha256=mask_hash,
                      pixel_count=int(mask.sum()), median=median,
                      polygon=tuple(tuple(point) for point in roi["polygon"]))
    return pixels, pixel_source, background


def _missing_region(reason):
    return {"area_px": None, "raw_mean": None, "raw_integrated": None,
            "corrected_mean": None, "corrected_integrated": None,
            "raw_missing_reason": reason, "corrected_missing_reason": reason}


def build_partition_table(store, nuclear, target, reference, field_record, fid, cid) -> RegionPartitionTable:
    """All records are owner-checked before this source-integrity boundary is entered."""
    sources = [_load_source(store, rev, fid) for rev in (nuclear, target, reference)]
    n, t, r = sources
    recipe = nuclear["config"]["recipe"]
    if recipe.get("source") != "stardist_nuclear" or n["table"].region_set.source != "stardist_nuclear":
        raise ValueError("partition_nuclear_source_required")
    validate_nuclear_role_evidence(n["recipe"], n["info"])
    identity = image_pixel_identity(n["info"].model_dump(mode="json"))
    if (field_record["id"] != fid or field_record["workspace_id"] != nuclear["workspace_id"]
            or identity != image_pixel_identity(field_record["image_info"])):
        raise ValueError("partition_current_image_mismatch")
    if any(source["info"].input_mode != "native" or image_pixel_identity(source["info"].model_dump(mode="json")) != identity
           for source in sources):
        raise ValueError("partition_source_image_mismatch")
    nuclei = n["labels"]
    targets = _source_membership(t, nuclei, n)
    references = _source_membership(r, nuclei, n)
    pixels, pixel_source, background = _pixels_and_background(store, n, fid, cid)
    for source in (t, r):
        entry = next((item for item in source["table"].channel_provenance if item.channel.channel_id == cid), None)
        if entry is None or entry.pixel_sha256 != pixel_source["pixel_sha256"] or entry.dtype != pixel_source["dtype"]:
            raise ValueError("partition_source_pixel_provenance_mismatch")
    if np.any((targets > 0) & (references > 0)):
        raise ValueError("partition_memberships_overlap")
    core = region_partition(nuclei, targets, references, pixels, background["median"])
    calibration = n["info"].calibration
    pixel_area = None if calibration is None else calibration.pixel_size_x_um * calibration.pixel_size_y_um
    parents = {item["nucleus_id"] for item in core["rows"]}
    exclusions_by_parent: dict[int, list[dict]] = {}
    excluded_parents: set[int] = set()
    # Index once by exact parent identity; no whole-image or full-ledger scan per row.
    for role, source in zip(("nuclear", "target", "reference"), sources, strict=True):
        for item in source["exclusions"]:
            region = item["region_id"]
            affected = parents if region is None else ({region} if role == "nuclear"
                                                       else source["object_parents"].get(region, set()))
            exclusion = {"source": role, "region_id": region, "reason": item["reason"]}
            for parent in affected:
                exclusions_by_parent.setdefault(parent, []).append(exclusion)
            if role == "nuclear" or region is None:
                excluded_parents.update(affected)
    rows: list[dict[str, Any]] = []
    for core_row in core["rows"]:
        row: dict[str, Any] = dict(core_row)
        parent = row["nucleus_id"]
        exclusions = exclusions_by_parent.get(parent, [])
        excluded = parent in excluded_parents
        for role, source in (("target", t), ("reference", r)):
            state = source["states"][parent]
            row[f"{role}_state"] = state
            if state not in ("adopted", "candidate"):
                row[role] = _missing_region(f"{role}_{state}")
            if excluded:
                row[role] = _missing_region("source_excluded")
            values = row[role]
            area = values["area_px"]
            values["area_um2"] = None if pixel_area is None or area is None else area * pixel_area
            values["area_missing_reason"] = (values["raw_missing_reason"] if area is None else
                                             "calibration_unknown" if pixel_area is None else None)
        for basis in ("raw", "corrected"):
            if excluded:
                row[basis] = {"k": None, "log2_k": None, "missing_reasons": ["source_excluded"]}
            else:
                reasons = list(row[basis]["missing_reasons"])
                for role in ("target", "reference"):
                    reason = row[role][f"{basis}_missing_reason"]
                    if reason is not None:
                        if reason != f"empty_{role}":
                            reasons = [value for value in reasons if value != f"empty_{role}"]
                        reasons.append(reason)
                if reasons:
                    row[basis] = {"k": None, "log2_k": None, "missing_reasons": list(dict.fromkeys(reasons))}
        row.update(excluded=excluded, exclusions=exclusions,
                   nucleus_area_um2=None if pixel_area is None else row["nucleus_area_px"] * pixel_area)
        rows.append(row)
    methods = (
        "Original native channel pixels and exact parent-nucleus labels were used. Target and reference were "
        "explicitly selected adopted sources; no complement region was inferred. Nonzero memberships were required "
        "to lie inside the selected nuclei and to be disjoint. Excluded labels were removed with their recorded reasons; "
        "unresolved compartments remained missing. Mean and integrated intensity use the region union pixels. "
        "K = mean(target) / mean(reference); log2K = log2(K), separately for raw and corrected values. Both means "
        "must be positive; no epsilon, clipping or raw fallback was used. Correction is mean - b and sum - area*b. "
        + ("b is the median of the nuclear revision's saved, confirmed background ROI. "
           if background["status"] == "confirmed" else "No confirmed measurement ROI background was established; corrected values are missing. ")
        + "Areas are pixel counts, with um2 only for confirmed XY calibration. The table is a read-only source-derived "
        "report; biological interpretation, comparisons, figures and replay are not established by this report."
    )
    # JSON validation is the shared list-to-immutable-tuple transport boundary.
    return RegionPartitionTable.model_validate_json(json.dumps({
        "workspace_id": nuclear["workspace_id"], "field_id": fid,
        "nuclear_source": n["source"], "target_source": t["source"], "reference_source": r["source"],
        "pixel_source": pixel_source,
        "background": background, "calibration": None if calibration is None else calibration.model_dump(mode="json"),
        "methods": methods, "rows": rows,
    }, default=lambda value: value.model_dump(mode="json")))


def register_region_partition_routes(api, store, owner, revision, result_root, field_record):
    Owner = Annotated[str, Depends(owner)]

    def report(rid, field_id, target_revision_id, reference_revision_id, channel_id, who):
        revisions = [revision(value, who) for value in (rid, target_revision_id, reference_revision_id)]
        nuclear, target, reference = revisions
        record = field_record(field_id, who)
        if any(rev["workspace_id"] != nuclear["workspace_id"] for rev in revisions) or record["workspace_id"] != nuclear["workspace_id"]:
            raise HTTPException(409, "partition_workspace_mismatch")
        for rev in revisions:
            if rev["config"].get("analysis_kind") != "region-2d":
                raise HTTPException(409, "partition_region_analysis_required")
            if rev["state"] != "succeeded" or not rev.get("result_dir"):
                raise HTTPException(409, "partition_source_not_succeeded")
            if rev.get("reviewed") is not True:
                raise HTTPException(409, "partition_source_not_reviewed")
        try:
            for rev in revisions:
                result_root(rev)
            return build_partition_table(store, nuclear, target, reference, record, field_id, channel_id)
        except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
            detail = str(exc) if str(exc).startswith("partition_") else "partition_source_invalid"
            raise HTTPException(409, detail) from None

    @api.get("/v1/revisions/{rid}/region-partition", response_model=RegionPartitionTable)
    def get_region_partition(rid: str, field_id: IdQuery, target_revision_id: IdQuery,
                             reference_revision_id: IdQuery, channel_id: IdQuery, response: Response, who: Owner):
        response.headers["Cache-Control"] = "no-store"
        return report(rid, field_id, target_revision_id, reference_revision_id, channel_id, who)

    @api.get("/v1/revisions/{rid}/region-partition.csv", response_class=Response)
    def get_region_partition_csv(rid: str, field_id: IdQuery, target_revision_id: IdQuery,
                                 reference_revision_id: IdQuery, channel_id: IdQuery, who: Owner):
        table = report(rid, field_id, target_revision_id, reference_revision_id, channel_id, who)
        return Response(partition_table_csv(table), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="region-partition.csv"',
                                 "Cache-Control": "no-store"})
