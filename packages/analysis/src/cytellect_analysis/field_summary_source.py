"""Field-summary selection 1.0.0 as an observation source: one observation per field.

Validates the reviewed nuclear region source exactly as region selections do, then
turns each field's adopted regions into one value (field_summary.field_summary_values).
The single field value is the field summary; samples and units aggregate as before.
"""
from __future__ import annotations

import json
import math

from .descriptive import _metadata, prepare_region_observations
from .descriptive_contracts import RegionSelection
from .field_summary import FieldInput, field_summary_values
from .gfp_selection import finish_gated_description, gate_record_key, gate_source_observations
from .group_comparison_contracts import FieldSummarySelection

UNITS = {"nucleus_count": "nuclei per field", "nucleus_density_per_mm2": "nuclei per mm²",
         "positive_count": "positive nuclei per field", "positive_fraction": "fraction of evaluable nuclei"}
DEFINITIONS = {
    "nucleus_count": "adopted nuclei per field, including nuclei touching the image border (field-summary/1.0.0)",
    "nucleus_density_per_mm2": "adopted nuclei per field / imaged field area in mm², calibrated fields only (field-summary/1.0.0)",
    "positive_count": "positive nuclei per field from the recorded gate, before subset selection (field-summary/1.0.0)",
    "positive_fraction": "positive / all evaluable positive and negative nuclei before subset selection; unclassified, excluded and control nuclei are outside the denominator (field-summary/1.0.0)",
}


# Region sources that delineate nuclei. Positive regions, nuclear compartments and
# Cellpose cells are not nuclei; supplied (manual/imported) regions are the researcher's.
NUCLEAR_SOURCES = frozenset({"stardist_nuclear", "manual", "imported"})


def exploratory_positivity(selection) -> bool:
    """True when positive nuclei are judged by a threshold that no designated negative
    control fixed (manual or Otsu). Such a classification is exploratory: positive counts
    and fractions are described, never tested (Methods, "Field positivity review")."""
    judged = getattr(selection, "positivity", None)
    if judged is None:
        return False
    # Legacy GFP: the exploratory filter is its own contract version; channel gate: its method.
    return getattr(judged, "method", "negative_control") != "negative_control"


def prepare_field_summary_observations(report, field_snapshot, selection, nuclear=None, *, with_gate_record=False):
    selection = FieldSummarySelection.model_validate(selection)
    if (report.get("recipe") or {}).get("source") not in NUCLEAR_SOURCES:
        raise ValueError("field_summary_nuclear_source_required")
    regions, fields, _, excluded = prepare_region_observations(report, field_snapshot, RegionSelection(
        source="region", region_set_id=selection.region_set_id, channel_id=None, metric="area_px"))
    gate_record = None
    if selection.positivity is not None:
        from .channel_gate_contracts import ChannelGateFilter
        neutral = isinstance(selection.positivity, ChannelGateFilter)
        selector = RegionSelection(source="region", region_set_id=selection.region_set_id, metric="area_px",
                                   **{"channel_gate" if neutral else "gfp_gate": selection.positivity})
        regions, gate_record = gate_source_observations(
            report, report.get("recipe"), field_snapshot, selector, regions, excluded, nuclear=nuclear)
        gate_record = {**gate_record, "purpose": "field_positivity"}
    border = {}
    for fid, table in report.get("field_tables", {}).items():
        for row in table["rows"]:
            border[fid, row["region_id"]] = bool(row.get("touches_border", False))
    whole_field = {item["field_id"]: item["reason"] for item in report.get("exclusions", []) if item.get("region_id") is None}
    controls = set() if gate_record is None else set(gate_record["control_field_ids"])
    def positivity(row):
        if "channel_positive" in row:
            return row["channel_positive"]
        return row.get("gfp_positive") if row.get("gfp_gate_reason") in (
            "above_control_threshold", "within_control_range", "above_exploratory_threshold",
            "at_or_below_exploratory_threshold") else None
    inputs: list[FieldInput] = []
    for field in fields:
        fid = field["field_id"]
        rows = [row for row in regions if row["field_id"] == fid]
        calibration = field["calibration"]
        size = (math.sqrt(calibration["pixel_size_x_um"] * calibration["pixel_size_y_um"])
                if calibration is not None else None)
        shape = tuple(field["image_info"]["shape"])
        inputs.append({"field_id": fid, "status": "excluded" if fid in whole_field or fid in controls else "measured" if rows else "no_regions",
                       "shape": (int(shape[0]), int(shape[1])), "pixel_size_um": size,
                       "regions": [{"region_id": row["region_id"], "touches_border": border[fid, row["region_id"]],
                                    "positive": positivity(row)} for row in rows if not row["excluded"]],
                       "excluded_region_ids": [row["region_id"] for row in rows if row["excluded"]]})
    observations = []
    for field, summary in zip(fields, field_summary_values(inputs, selection), strict=True):
        fid = field["field_id"]
        metadata = _metadata(field_snapshot[fid])
        reason = whole_field.get(fid) or ("negative_control" if fid in controls else None)
        field["field_summary"] = {"nucleus_count": summary["nucleus_count"], "border_count": summary["border_count"],
                                  "excluded_region_count": summary["excluded_region_count"],
                                  "field_area_mm2": summary["field_area_mm2"]}
        positive_counts = {}
        if selection.positivity is not None:
            evaluable, positives, total = summary["evaluable_count"], summary["positive_count"], summary["nucleus_count"]
            positive_counts = {"evaluable_count": summary["evaluable_count"], "positive_count": summary["positive_count"],
                               "negative_count": None if evaluable is None or positives is None else evaluable - positives,
                               "unclassified_count": None if total is None or evaluable is None else total - evaluable}
            field["field_summary"].update(positive_counts)
        observations.append({
            "observation_id": json.dumps([fid, selection.region_set_id, "field"], separators=(",", ":")),
            "field_id": fid, "region_id": None, "region_set_id": selection.region_set_id,
            "mask_revision_id": field["region_set"]["mask_revision_id"],
            "analysis_revision_id": field["analysis_revision_id"], "channel_id": None, **metadata,
            "value": summary["value"], "excluded": bool(reason), "exclusion_reason": reason,
            "gate_selected": True, "missing_reason": None if summary["value"] is not None or reason else summary["missing_reason"],
            **positive_counts})
    result = observations, fields, UNITS[selection.metric], excluded
    return (*result, gate_record) if with_gate_record else result


def describe_field_summary(report, field_snapshot, request, nuclear=None):
    """Describe the same saved field values consumed by group comparisons."""
    from .descriptive import _finish, _request

    request = _request(request, "field-summary")
    observations, fields, unit, excluded, gate_record = prepare_field_summary_observations(
        report, field_snapshot, request.selection, nuclear, with_gate_record=True)
    keys = ("evaluable_count", "positive_count", "negative_count", "unclassified_count") if gate_record is not None else ()
    result = _finish(observations, fields, request, "region-2d", "fields", unit, excluded, keys)
    if gate_record is not None:
        result["selection"][gate_record_key(gate_record)] = gate_record
        result = finish_gated_description(result, gate_record)
    result["metric_definition"] = f"{DEFINITIONS[request.selection.metric]}; one observation per field"
    return result
