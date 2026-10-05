"""Per-field descriptions without tests, confidence intervals or replicate inference."""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from typing import Any

from .descriptive_contracts import (
    DescriptiveResult,
    LegacySelection,
    NumericalSelection,
    PagedDescriptiveRequest,
    PagedDescriptiveResult,
    RegionSelection,
    parse_descriptive_request,
)
from .region_measurement_v2 import region_table_from_json, require_region_metric
from .region_policy import MEASUREMENT_POLICY, measurement_protocol
from .regions import CHANNEL_SPEC, Calibration2D
from .review import unresolved_nucleolar_failures

VERSION = "1.0.0"
METADATA = ("condition", "experimental_unit", "sample", "acquisition_date", "pair")
SAFE_ERROR_CODES = frozenset({
    "descriptive_source_mismatch", "descriptive_unresolved_field_failures",
    "descriptive_exclusion_reason_required", "descriptive_field_coverage_mismatch",
    "descriptive_invalid_metadata", "descriptive_invalid_value", "descriptive_duplicate_observation",
    "invalid_selection_flags", "no_valid_selected_measurements", "inconsistent_field_metadata",
    "descriptive_observation_identity_mismatch", "descriptive_metric_missing_from_source",
    "nucleolar_processing_failed", "descriptive_unknown_exclusion", "descriptive_duplicate_exclusion",
    "descriptive_region_identity_mismatch", "descriptive_channel_identity_mismatch",
    "descriptive_region_status_mismatch", "descriptive_channel_coverage_mismatch",
    "descriptive_area_channel_mismatch", "descriptive_calibration_mismatch",
    "descriptive_shape_mismatch",
    "descriptive_region_definition_mismatch", "descriptive_numeric_field_required",
    "no_measurements", "numeric_csv_single_assay_and_unit_required",
    "descriptive_area_channel_must_be_unset", "descriptive_intensity_channel_required",
    "descriptive_result_required", "descriptive_inference_not_allowed", "descriptive_figure_source_mismatch",
    "descriptive_review_required", "descriptive_saved_result_mismatch", "descriptive_revision_mismatch",
    "descriptive_failure_exclusion_mismatch",
    "region_measurement_protocol_mismatch", "region_metric_not_measured",
    "descriptive_page_preset_unsupported", "descriptive_page_policy_required", "descriptive_page_limit_exceeded",
    "descriptive_output_manifest_mismatch", "descriptive_output_source_mismatch",
    "descriptive_output_artifact_mismatch", "descriptive_output_artifact_not_found",
    "descriptive_output_source_required",
})


def _request(request, source):
    parsed = parse_descriptive_request(request)
    if parsed.selection.source != source:
        raise ValueError("descriptive_source_mismatch")
    return parsed


def _coverage(report, snapshots, successful):
    if report.get("field_failures"):
        raise ValueError("descriptive_unresolved_field_failures")
    excluded = report.get("excluded_failed_fields", [])
    excluded_ids = []
    for row in excluded:
        if not isinstance(row.get("reason"), str) or not row["reason"].strip():
            raise ValueError("descriptive_exclusion_reason_required")
        excluded_ids.append(row["field_id"])
    if (not snapshots or len(excluded_ids) != len(set(excluded_ids))
            or set(successful) & set(excluded_ids)
            or set(successful) | set(excluded_ids) != set(snapshots)):
        raise ValueError("descriptive_field_coverage_mismatch")
    return excluded


def _metadata(snapshot):
    result = {key: snapshot.get("metadata", {}).get(key) for key in METADATA}
    if any(value is not None and (not isinstance(value, str) or not value.strip()) for value in result.values()):
        raise ValueError("descriptive_invalid_metadata")
    return result


def _finite(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("descriptive_invalid_value")
    return float(value)


def _quantile(values, probability):
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    low, high = math.floor(index), math.ceil(index)
    # Convex form avoids overflow when two large finite values are averaged.
    fraction = index - low
    return (1 - fraction) * ordered[low] + fraction * ordered[high]


def _metric_unit(metric):
    if metric.endswith("area_px") or metric == "area_px":
        return "pixel²"
    if metric.endswith("area_um2") or metric == "area_um2":
        return "µm²"
    if "integrated" in metric:
        return "a.u. × pixel"
    if metric.endswith("count"):
        return "count"
    if "fraction" in metric or "over_nucleoli" in metric or metric == "ncl_legacy_release":
        return "dimensionless"
    return "a.u."


def _finish(observations, fields, request, source_kind, observation_kind, unit, excluded_fields=()):
    selected, missingness, selection_records = [], [], []
    totals: Counter[str] = Counter()
    per_field: dict[str, Counter] = defaultdict(Counter)
    seen = set()
    for item in observations:
        oid = item["observation_id"]
        if oid in seen:
            raise ValueError("descriptive_duplicate_observation")
        seen.add(oid)
        value = _finite(item["value"])
        if type(item["excluded"]) is not bool or type(item["gate_selected"]) is not bool:
            raise ValueError("invalid_selection_flags")
        if item["excluded"] and not str(item.get("exclusion_reason") or "").strip():
            raise ValueError("descriptive_exclusion_reason_required")
        count = per_field[item["field_id"]]
        count["input_rows"] += 1
        selection_records.append({key: item.get(key) for key in (
            "observation_id", "field_id", "excluded", "exclusion_reason", "gate_selected",
            "gfp_gate_method", "gfp_gate_threshold", "gfp_gate_maximum", "missing_reason")})
        if item["excluded"]:
            count["excluded"] += 1
        elif not item["gate_selected"]:
            count["gate_unselected"] += 1
        else:
            if value is None:
                reason = item.get("missing_reason") or "metric_unavailable"
                missingness.append({"observation_id": oid, "field_id": item["field_id"], "reason": reason})
                count["missing_metric_selected"] += 1
            else:
                count["selected_rows"] += 1
                selected.append({**item, "value": value})
    if not selected:
        raise ValueError("no_valid_selected_measurements")
    summary = []
    for field in fields:
        fid = field["field_id"]
        count = per_field[fid]
        totals.update(count)
        values = [row["value"] for row in selected if row["field_id"] == fid]
        summary.append({"field_id": fid, "condition": field["metadata"].get("condition"),
                        **{key: count[key] for key in ("input_rows", "excluded", "gate_unselected",
                                                     "missing_metric_selected", "selected_rows")},
                        "status": "selected" if values else ("no_regions" if not count["input_rows"] else "no_selected_values"),
                        "median": _quantile(values, .5) if values else None,
                        "q1": _quantile(values, .25) if values else None,
                        "q3": _quantile(values, .75) if values else None,
                        "minimum": min(values) if values else None, "maximum": max(values) if values else None})
    model = PagedDescriptiveResult if isinstance(request, PagedDescriptiveRequest) else DescriptiveResult
    return model(
        spec=request, source_kind=source_kind, observation_kind=observation_kind,
        metric=request.selection.metric, unit=unit,
        metric_definition=f"{request.selection.metric}; per-field observed values; original measurement scale",
        plot_data=selected, field_summary=summary,
        counts={"observations": len(selected), "input_fields": len(fields) + len(excluded_fields),
                "selected_fields": sum(row["selected_rows"] > 0 for row in summary),
                "excluded_failed_fields": len(excluded_fields), "experimental_units": None},
        selection={**{key: totals[key] for key in ("input_rows", "excluded", "gate_unselected",
                    "missing_metric_selected", "selected_rows")}, "by_field": summary,
                   "records": selection_records},
        missingness=missingness, source_fields=fields, excluded_failed_fields=list(excluded_fields),
        warnings=["descriptive_independence_not_assessed", "acquisition_comparability_not_established",
                  *(["missing_outcomes_excluded_inspect_fieldwise_missingness"] if missingness else [])],
    ).model_dump(mode="json")


def describe_legacy(report, field_snapshot, request):
    """Caller must first apply the revision's immutable review/exclusion gates."""
    request = _request(request, "legacy-cell")
    assert isinstance(request.selection, LegacySelection)
    metric = request.selection.metric
    excluded_ids = {item["field_id"] for item in report.get("excluded_failed_fields", [])}
    successful = {fid: value for fid, value in report.get("engine_provenance", {}).items() if fid not in excluded_ids}
    excluded = _coverage(report, field_snapshot, successful)
    fields = [{"field_id": fid, "metadata": _metadata(field_snapshot[fid]),
               "image_info": field_snapshot[fid].get("image_info", {}),
               "analysis_revision_id": report.get("revision_id"), "recipe": report.get("recipe", {}),
               "engine_provenance": successful[fid]} for fid in sorted(successful)]
    observations = []
    for row in report.get("cells", []):
        fid, nid = row["field_id"], row["nucleus_id"]
        if fid not in successful or type(nid) is not int or nid <= 0:
            raise ValueError("descriptive_observation_identity_mismatch")
        metadata = _metadata(field_snapshot[fid])
        if any(key in row and row[key] != value for key, value in metadata.items()):
            raise ValueError("inconsistent_field_metadata")
        if metric not in row:
            raise ValueError("descriptive_metric_missing_from_source")
        if row.get("nucleolar_status") == "processing_failed" and not row.get("excluded"):
            raise ValueError("nucleolar_processing_failed")
        reason = row.get("ratio_missing_reason") if "over_nucleoli" in metric else None
        if row[metric] is None and not reason:
            unavailable_ncl = (row.get("recipe_id") == "gfp-nuclear-2d"
                               and (metric.startswith(("ncl_", "nucleolar_", "nucleoplasm_"))))
            if unavailable_ncl:
                reason = "ncl_not_measured_recipe"
            elif metric.endswith("_um2") and field_snapshot[fid].get("metadata", {}).get("pixel_size_um") is None:
                reason = "calibration_unknown"
            else:
                reason = "channel_or_compartment_unavailable"
        observations.append({"observation_id": json.dumps([fid, nid], separators=(",", ":")),
                             "field_id": fid, "nucleus_id": nid, **metadata,
                             "analysis_revision_id": report.get("revision_id"),
                             "value": row[metric], "excluded": row.get("excluded", False),
                             "exclusion_reason": row.get("exclusion_reason"),
                             "gate_selected": row.get("gfp_positive", True), "missing_reason": reason,
                             **{key: row.get(key) for key in ("gfp_gate_method", "gfp_gate_threshold",
                                                            "gfp_gate_maximum", "gfp_gate_exploratory")}})
    unit = _metric_unit(metric)
    if "integrated" in metric and report.get("recipe", {}).get("id") == "ncl-legacy-rgb":
        unit = "a.u. × scaled pixel"
    result = _finish(observations, fields, request, "legacy-image-measurements", "nuclei", unit, excluded)
    if metric.startswith("ncl_") and not metric.startswith("ncl_nucleus_"):
        result["warnings"].append("ncl_defined_regions_can_change_with_the_measured_ncl_distribution")
    if any(row.get("gfp_gate_exploratory") is True for row in observations):
        result["warnings"].append("data_derived_or_manual_gfp_selection_requires_predeclared_or_independent_validation")
    return result


def _region_exclusions(report, field_ids, objects, region_set_id):
    exclusions = {}
    for item in report.get("exclusions", []):
        fid, rid = item["field_id"], item.get("region_id")
        reason = item.get("reason")
        if (fid not in field_ids or item.get("region_set_id", region_set_id) != region_set_id
                or (rid is not None and (type(rid) is not int or (fid, rid) not in objects))):
            raise ValueError("descriptive_unknown_exclusion")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("descriptive_exclusion_reason_required")
        if (fid, rid) in exclusions:
            raise ValueError("descriptive_duplicate_exclusion")
        exclusions[fid, rid] = reason
    return exclusions


def region_report_measurement_policy(report):
    # Retain the v1 adapter's historical minimal dictionaries. Only an explicit
    # v2 protocol and strict policy can make area-only values available.
    protocol = report.get("protocol_version", "1.0.0")
    if protocol == "1.0.0" and report.get("measurement") is None:
        return None
    if protocol in ("2.0.0", "3.0.0"):
        try:
            return MEASUREMENT_POLICY.validate_python(report.get("measurement"))
        except ValueError:
            pass
    raise ValueError("region_measurement_protocol_mismatch")


def prepare_region_observations(report, field_snapshot, selector):
    """Validate every source observation before selection or statistical aggregation."""
    selector = RegionSelection.model_validate(selector)
    measurement = region_report_measurement_policy(report)
    require_region_metric(measurement, selector.metric)
    tables = {fid: region_table_from_json(json.dumps(value))
              for fid, value in report.get("field_tables", {}).items()}
    for table in tables.values():
        if (table.protocol_version != measurement_protocol(measurement)
                or getattr(table, "measurement", None) != measurement):
            raise ValueError("region_measurement_protocol_mismatch")
    excluded = _coverage(report, field_snapshot, tables)
    fields, objects, definitions, identities = [], {}, set(), set()
    for fid, table in sorted(tables.items()):
        if table.field_id != fid or table.region_set.region_set_id != selector.region_set_id:
            raise ValueError("descriptive_region_identity_mismatch")
        if report.get("revision_id") is not None and table.analysis_revision_id != report["revision_id"]:
            raise ValueError("descriptive_region_identity_mismatch")
        image_info = field_snapshot[fid].get("image_info", {})
        if tuple(image_info.get("shape", ())) != table.shape_yx:
            raise ValueError("descriptive_shape_mismatch")
        recorded_calibration = image_info.get("calibration")
        expected_calibration = (Calibration2D.model_validate_json(json.dumps(recorded_calibration))
                                if recorded_calibration is not None else None)
        if expected_calibration != table.calibration:
            raise ValueError("descriptive_calibration_mismatch")
        definitions.add((table.region_set.label, table.region_set.defining_channel_id))
        declared = [CHANNEL_SPEC.validate_python(item) for item in field_snapshot[fid].get("image_info", {}).get("channels", [])]
        channel_map = {item.channel_id: item for item in declared}
        provenance_map = {item.channel.channel_id: item for item in table.channel_provenance}
        if (not channel_map or len(channel_map) != len(declared)
                or len(provenance_map) != len(table.channel_provenance)
                or set(channel_map) != set(provenance_map)
                or any(channel_map[cid] != provenance_map[cid].channel for cid in channel_map)):
            raise ValueError("descriptive_channel_identity_mismatch")
        if selector.channel_id is not None:
            if selector.channel_id not in channel_map:
                raise ValueError("descriptive_channel_identity_mismatch")
            channel = channel_map[selector.channel_id]
            identities.add((channel.label, channel.stain))
        rows: dict[int, dict[str, Any]] = defaultdict(dict)
        for row in table.rows:
            if (row.field_id != fid or row.analysis_revision_id != table.analysis_revision_id
                    or row.region_set_id != table.region_set.region_set_id
                    or row.mask_revision_id != table.region_set.mask_revision_id
                    or row.channel_id not in channel_map or row.region_id <= 0 or row.area_px <= 0):
                raise ValueError("descriptive_region_identity_mismatch")
            if row.channel_id in rows[row.region_id]:
                raise ValueError("descriptive_duplicate_observation")
            rows[row.region_id][row.channel_id] = row
        if bool(rows) != (table.status == "measured"):
            raise ValueError("descriptive_region_status_mismatch")
        for rid, channels in rows.items():
            if set(channels) != set(channel_map):
                raise ValueError("descriptive_channel_coverage_mismatch")
            areas = {(row.area_px, row.area_um2, row.area_missing_reason) for row in channels.values()}
            if len(areas) != 1:
                raise ValueError("descriptive_area_channel_mismatch")
            area_px, area_um2, missing_reason = next(iter(areas))
            if table.calibration is None:
                if area_um2 is not None or missing_reason != "calibration_unknown":
                    raise ValueError("descriptive_calibration_mismatch")
            else:
                expected = area_px * (table.calibration.pixel_size_x_um * table.calibration.pixel_size_y_um)
                if area_um2 != expected or missing_reason is not None:
                    raise ValueError("descriptive_calibration_mismatch")
            chosen = channels[selector.channel_id] if selector.channel_id is not None else next(iter(channels.values()))
            objects[fid, rid] = chosen
        fields.append({"field_id": fid, "metadata": _metadata(field_snapshot[fid]),
                       "image_info": image_info,
                       "analysis_revision_id": table.analysis_revision_id,
                       "region_set": table.region_set.model_dump(mode="json"),
                       "mask_sha256": table.mask_sha256, "hash_format": table.hash_format,
                       "calibration": table.calibration.model_dump(mode="json") if table.calibration else None,
                       "channel_provenance": [item.model_dump(mode="json") for item in table.channel_provenance]})
        if measurement is not None:
            fields[-1].update(measurement_protocol=measurement_protocol(measurement), measurement=measurement.model_dump(mode="json"))
    if len(definitions) > 1:
        raise ValueError("descriptive_region_definition_mismatch")
    if len(identities) > 1:
        raise ValueError("descriptive_channel_identity_mismatch")
    exclusions = _region_exclusions(report, set(field_snapshot), objects, selector.region_set_id)
    if any(exclusions.get((item["field_id"], None)) != item["reason"] for item in excluded):
        raise ValueError("descriptive_failure_exclusion_mismatch")
    observations = []
    for (fid, rid), row in sorted(objects.items()):
        reason = exclusions.get((fid, None)) or exclusions.get((fid, rid))
        observations.append({"observation_id": json.dumps([fid, selector.region_set_id, rid], separators=(",", ":")),
                             "field_id": fid, "region_id": rid, "region_set_id": selector.region_set_id,
                             "mask_revision_id": row.mask_revision_id, "analysis_revision_id": row.analysis_revision_id,
                             "channel_id": selector.channel_id, **_metadata(field_snapshot[fid]),
                             "value": getattr(row, selector.metric), "excluded": bool(reason),
                             "exclusion_reason": reason, "gate_selected": True,
                             "missing_reason": row.area_missing_reason if selector.metric == "area_um2" else None})
    return observations, fields, _metric_unit(selector.metric), excluded


def describe_regions(report, field_snapshot, request):
    request = _request(request, "region")
    observations, fields, unit, excluded = prepare_region_observations(report, field_snapshot, request.selection)
    return _finish(observations, fields, request, "region-2d", "regions", unit, excluded)


def describe_numeric(rows, request):
    """Describe already strictly imported numeric CSV rows; no new import semantics."""
    request = _request(request, "numerical")
    assert isinstance(request.selection, NumericalSelection)
    if not rows:
        raise ValueError("no_measurements")
    if len({(row.get("unit", ""), row.get("assay", "")) for row in rows}) != 1:
        raise ValueError("numeric_csv_single_assay_and_unit_required")
    fields: dict[str, dict[str, Any]] = {}
    observations = []
    for index, row in enumerate(rows):
        fid = row.get("field_id")
        if not isinstance(fid, str) or not fid.strip():
            raise ValueError("descriptive_numeric_field_required")
        metadata = _metadata({"metadata": row})
        if fid in fields and fields[fid]["metadata"] != metadata:
            raise ValueError("inconsistent_field_metadata")
        fields[fid] = {"field_id": fid, "metadata": metadata, "assay": row.get("assay", "")}
        observations.append({"observation_id": f"csv-row-{index + 2}", "field_id": fid,
                             "source_row": index + 2, **metadata, "value": row["value"],
                             "excluded": False, "gate_selected": True, "missing_reason": None})
    return _finish(observations, list(fields.values()), request, "measured-numerical-assay",
                   "observations", rows[0].get("unit", ""))


def validate_legacy_description(recorded, report, config):
    """Recompute a saved description against its reviewed measurement snapshot.

    Export checks the current source table; replay supplies freshly remeasured
    original pixels. The figure manifest is derived presentation metadata.
    """
    review = config.get("review_record") or {}
    confirmed = review.get("confirmed_at")
    if (isinstance(confirmed, bool) or not isinstance(confirmed, (int, float))
            or not math.isfinite(confirmed) or confirmed <= 0
            or report.get("field_failures") or unresolved_nucleolar_failures(report, config)
            or set(report.get("invalidated_nucleoli", [])) - set(review.get("accepted_invalidated_fields", []))):
        raise ValueError("descriptive_review_required")
    if (recorded.get("revision_id") != report.get("revision_id") or not report.get("revision_id")
            or report.get("recipe") != config.get("recipe")
            or len(config.get("field_ids", [])) != len(set(config.get("field_ids", [])))
            or set(config.get("field_ids", [])) != set(config.get("field_snapshot", {}))):
        raise ValueError("descriptive_revision_mismatch")
    excluded_fields = {item["field_id"]: item["reason"] for item in config.get("exclusions", [])
                       if item.get("nucleus_id") is None}
    if any(excluded_fields.get(item["field_id"]) != item.get("reason")
           for item in report.get("excluded_failed_fields", [])):
        raise ValueError("descriptive_review_required")
    fresh = describe_legacy(report, config["field_snapshot"], parse_descriptive_request(recorded["spec"]))
    fresh["revision_id"] = report["revision_id"]
    if set(recorded) - set(fresh) - {"figure"} or any(recorded.get(key) != value for key, value in fresh.items()):
        raise ValueError("descriptive_saved_result_mismatch")
    return fresh
