"""Field-summary observations 1.0.0: one value per field (WP3, implementation pending).

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


def field_summary_values(fields: Sequence[FieldInput], selection: FieldSummarySelection) -> list[FieldSummaryRow]:
    """Return one row per input field, in input order."""
    raise NotImplementedError("field_summary_not_implemented")
