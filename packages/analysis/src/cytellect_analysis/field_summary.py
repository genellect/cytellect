"""Field-summary observations 1.0.0: one value per field.

Definitions are in docs/methods.md, "Field-summary selection 1.0.0". The caller
supplies the adopted, non-excluded regions of the selected nuclear region set
and, for positive_* metrics, each nucleus's gate result from the recorded gate
protocol; this module never re-thresholds pixels or reads images.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, TypedDict

from .group_comparison_contracts import FieldSummarySelection


class RegionInput(TypedDict):
    region_id: int
    touches_border: bool
    # Gate result for positive_* metrics: True/False, or None when the nucleus has no gate value.
    positive: bool | None


class FieldInput(TypedDict):
    field_id: str
    status: Literal["measured", "no_regions", "failed", "excluded"]
    shape: tuple[int, int]
    # Confirmed square XY pixel size in µm; None when calibration is unknown.
    pixel_size_um: float | None
    regions: list[RegionInput]
    excluded_region_ids: list[int]


class FieldSummaryRow(TypedDict):
    field_id: str
    value: float | None
    missing_reason: str | None
    nucleus_count: int | None
    border_count: int | None
    evaluable_count: int | None
    positive_count: int | None
    excluded_region_count: int
    field_area_mm2: float | None


def _area_mm2(field: FieldInput) -> float | None:
    size = field["pixel_size_um"]
    if size is None:
        return None
    if not size > 0:
        raise ValueError("field_summary_invalid_calibration")
    rows, columns = field["shape"]
    return rows * columns * size * size * 1e-6


def field_summary_values(fields: Sequence[FieldInput], selection: FieldSummarySelection) -> list[FieldSummaryRow]:
    """Return one row per input field, in input order."""
    positive = selection.metric.startswith("positive_")
    rows: list[FieldSummaryRow] = []
    for field in fields:
        row: FieldSummaryRow = {
            "field_id": field["field_id"], "value": None, "missing_reason": None, "nucleus_count": None,
            "border_count": None, "evaluable_count": None, "positive_count": None,
            "excluded_region_count": len(field["excluded_region_ids"]), "field_area_mm2": _area_mm2(field)}
        if field["status"] in ("failed", "excluded"):
            # Not an observation; the comparison ledger keeps the field and its reason.
            row["missing_reason"] = "field_failed" if field["status"] == "failed" else "field_excluded"
            rows.append(row)
            continue
        regions = field["regions"]
        if field["status"] == "no_regions" and regions:
            raise ValueError("field_summary_status_mismatch")
        ids = [region["region_id"] for region in regions]
        if len(ids) != len(set(ids)) or set(ids) & set(field["excluded_region_ids"]):
            raise ValueError("field_summary_region_identity")
        row["nucleus_count"] = len(regions)
        row["border_count"] = sum(1 for region in regions if region["touches_border"])
        if positive:
            evaluable = [region for region in regions if region["positive"] is not None]
            row["evaluable_count"] = len(evaluable)
            row["positive_count"] = sum(1 for region in evaluable if region["positive"])
        metric = selection.metric
        if metric == "nucleus_count":
            row["value"] = float(len(regions))
        elif metric == "nucleus_density_per_mm2":
            if row["field_area_mm2"] is None:
                row["missing_reason"] = "calibration_unknown"
            else:
                row["value"] = len(regions) / row["field_area_mm2"]
        elif metric == "positive_count":
            row["value"] = float(row["positive_count"] or 0)
        elif row["evaluable_count"]:
            row["value"] = (row["positive_count"] or 0) / row["evaluable_count"]
        else:
            row["missing_reason"] = "no_evaluable_nuclei"
        rows.append(row)
    return rows
