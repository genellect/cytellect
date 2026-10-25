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
from .group_comparison_contracts import FieldSummarySelection

UNITS = {"nucleus_count": "nuclei per field", "nucleus_density_per_mm2": "nuclei per mm²",
         "positive_count": "positive nuclei per field", "positive_fraction": "fraction of evaluable nuclei"}
DEFINITIONS = {
    "nucleus_count": "adopted nuclei per field, including nuclei touching the image border (field-summary/1.0.0)",
    "nucleus_density_per_mm2": "adopted nuclei per field / imaged field area in mm², calibrated fields only (field-summary/1.0.0)",
}


# Region sources that delineate nuclei. Positive regions, nuclear compartments and
# Cellpose cells are not nuclei; supplied (manual/imported) regions are the researcher's.
NUCLEAR_SOURCES = frozenset({"stardist_nuclear", "manual", "imported"})


def prepare_field_summary_observations(report, field_snapshot, selection):
    selection = FieldSummarySelection.model_validate(selection)
    if (report.get("recipe") or {}).get("source") not in NUCLEAR_SOURCES:
        raise ValueError("field_summary_nuclear_source_required")
    if selection.positivity is not None:
        # Positivity needs the recorded nucleus gate per field; it is not connected yet.
        raise ValueError("field_summary_positivity_not_connected")
    regions, fields, _, excluded = prepare_region_observations(report, field_snapshot, RegionSelection(
        source="region", region_set_id=selection.region_set_id, channel_id=None, metric="area_px"))
    border = {}
    for fid, table in report.get("field_tables", {}).items():
        for row in table["rows"]:
            border[fid, row["region_id"]] = bool(row.get("touches_border", False))
    whole_field = {item["field_id"]: item["reason"] for item in report.get("exclusions", []) if item.get("region_id") is None}
    inputs: list[FieldInput] = []
    for field in fields:
        fid = field["field_id"]
        rows = [row for row in regions if row["field_id"] == fid]
        calibration = field["calibration"]
        size = (math.sqrt(calibration["pixel_size_x_um"] * calibration["pixel_size_y_um"])
                if calibration is not None else None)
        shape = tuple(field["image_info"]["shape"])
        inputs.append({"field_id": fid, "status": "excluded" if fid in whole_field else "measured" if rows else "no_regions",
                       "shape": (int(shape[0]), int(shape[1])), "pixel_size_um": size,
                       "regions": [{"region_id": row["region_id"], "touches_border": border[fid, row["region_id"]],
                                    "positive": None} for row in rows if not row["excluded"]],
                       "excluded_region_ids": [row["region_id"] for row in rows if row["excluded"]]})
    observations = []
    for field, summary in zip(fields, field_summary_values(inputs, selection), strict=True):
        fid = field["field_id"]
        metadata = _metadata(field_snapshot[fid])
        reason = whole_field.get(fid)
        field["field_summary"] = {"nucleus_count": summary["nucleus_count"], "border_count": summary["border_count"],
                                  "excluded_region_count": summary["excluded_region_count"],
                                  "field_area_mm2": summary["field_area_mm2"]}
        observations.append({
            "observation_id": json.dumps([fid, selection.region_set_id, "field"], separators=(",", ":")),
            "field_id": fid, "region_id": None, "region_set_id": selection.region_set_id,
            "mask_revision_id": field["region_set"]["mask_revision_id"],
            "analysis_revision_id": field["analysis_revision_id"], "channel_id": None, **metadata,
            "value": summary["value"], "excluded": bool(reason), "exclusion_reason": reason,
            "gate_selected": True, "missing_reason": None if summary["value"] is not None or reason else summary["missing_reason"]})
    return observations, fields, UNITS[selection.metric], excluded
