"""Versioned read-only partition-table transport and CSV; arithmetic lives in region_partition."""
from __future__ import annotations

import io
import json
from typing import Annotated, Literal

from pydantic import Field, FiniteFloat, model_validator

from .exports_csv import _write_rows
from .region_contracts import RegionStoredFile
from .regions import Calibration2D, ChannelSpecType, Id, Label, RegionModel

Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
RegionId = Annotated[int, Field(ge=1, le=4294967295)]
Reason = Annotated[str, Field(pattern=r"^[a-z0-9_]+$", max_length=120)]


class PartitionSource(RegionModel):
    revision_id: Id
    region_set_id: Id
    label: Label
    source: Literal["stardist_nuclear", "manual", "imported", "fiji_nuclear_compartment"]
    mask_revision_id: Id
    mask_sha256: Digest
    effective_mask_sha256: Digest
    label_file: RegionStoredFile
    report_sha256: Digest
    provenance_sha256: Digest
    reviewed: bool
    adopted: bool


class PartitionPixelSource(RegionModel):
    channel: ChannelSpecType
    input_mode: Literal["native"] = "native"
    dtype: Literal["uint8", "uint16"]
    pixel_sha256: Digest
    array_file: RegionStoredFile
    original_files: dict[Id, RegionStoredFile]


class PartitionBackground(RegionModel):
    status: Literal["confirmed", "missing"]
    reason: Literal["background_not_confirmed"] | None
    source_revision_id: Id
    roi_revision_id: Id | None
    mask_sha256: Digest | None
    pixel_count: Annotated[int, Field(gt=0)] | None
    median: FiniteFloat | None
    polygon: tuple[tuple[FiniteFloat, FiniteFloat], ...] | None


class PartitionExclusion(RegionModel):
    source: Literal["nuclear", "target", "reference"]
    region_id: RegionId | None
    reason: Annotated[str, Field(min_length=1, max_length=200)]


class PartitionRegionMeasurement(RegionModel):
    area_px: Annotated[int, Field(gt=0)] | None
    area_um2: Annotated[FiniteFloat, Field(gt=0)] | None
    area_missing_reason: Reason | None
    raw_mean: FiniteFloat | None
    raw_integrated: FiniteFloat | None
    corrected_mean: FiniteFloat | None
    corrected_integrated: FiniteFloat | None
    raw_missing_reason: Reason | None
    corrected_missing_reason: Reason | None


class PartitionRatioMeasurement(RegionModel):
    k: Annotated[FiniteFloat, Field(gt=0)] | None
    log2_k: FiniteFloat | None
    missing_reasons: tuple[Reason, ...]


class RegionPartitionTableRow(RegionModel):
    nucleus_id: RegionId
    nucleus_area_px: Annotated[int, Field(gt=0)]
    nucleus_area_um2: Annotated[FiniteFloat, Field(gt=0)] | None
    excluded: bool
    exclusions: tuple[PartitionExclusion, ...]
    target_state: Reason
    reference_state: Reason
    target: PartitionRegionMeasurement
    reference: PartitionRegionMeasurement
    raw: PartitionRatioMeasurement
    corrected: PartitionRatioMeasurement


class RegionPartitionTable(RegionModel):
    protocol: Literal["region-partition-table/1.0.0"] = "region-partition-table/1.0.0"
    calculation_protocol: Literal["region-partition/1.0.0"] = "region-partition/1.0.0"
    review_status: Literal["reviewed", "preview"]
    workspace_id: Id
    field_id: Id
    nuclear_source: PartitionSource
    target_source: PartitionSource
    reference_source: PartitionSource
    pixel_source: PartitionPixelSource
    background: PartitionBackground
    calibration: Calibration2D | None
    area_unit: Literal["px"] = "px"
    calibrated_area_unit: Literal["um2"] = "um2"
    mean_unit: Literal["native_intensity"] = "native_intensity"
    integrated_unit: Literal["native_intensity_px"] = "native_intensity_px"
    ratio_unit: Literal["dimensionless"] = "dimensionless"
    log2_unit: Literal["log2"] = "log2"
    methods: str
    rows: tuple[RegionPartitionTableRow, ...]

    @model_validator(mode="after")
    def actual_source_review(self):
        expected = "reviewed" if all(source.reviewed for source in (
            self.nuclear_source, self.target_source, self.reference_source,
        )) else "preview"
        if self.review_status != expected:
            raise ValueError("partition_review_status_mismatch")
        return self


def partition_table_csv(table: RegionPartitionTable) -> bytes:
    """Serialize server values unchanged, with BOM and shared formula-safe text escaping.

    Source provenance and Methods are repeated as JSON/text columns. An empty
    nuclear source has one explicitly labelled report record, never a zero-valued
    nucleus. Signed numeric measurements remain numbers, not escaped strings.
    """
    data = table.model_dump(mode="json")
    metadata = {key: value for key, value in data.items() if key != "rows"}
    common = {"protocol": table.protocol, "review_status": table.review_status,
              "workspace_id": table.workspace_id, "field_id": table.field_id,
              "channel_id": table.pixel_source.channel.channel_id,
              "channel_label": table.pixel_source.channel.label, "channel_stain": table.pixel_source.channel.stain,
              "target_label": table.target_source.label, "reference_label": table.reference_source.label,
              "provenance_json": json.dumps(metadata, ensure_ascii=False, separators=(",", ":")),
              "methods": table.methods}
    for role in ("nuclear", "target", "reference"):
        source = getattr(table, f"{role}_source")
        common[f"{role}_reviewed"] = source.reviewed
        common[f"{role}_adopted"] = source.adopted
    columns = ["record_type", *common, "nucleus_id", "nucleus_area_px", "nucleus_area_um2", "excluded",
               "exclusions_json", "target_state", "reference_state"]
    for side in ("target", "reference"):
        columns.extend(f"{side}_{name}" for name in PartitionRegionMeasurement.model_fields)
    for basis in ("raw", "corrected"):
        columns.extend(f"{basis}_{name}" for name in ("k", "log2_k", "missing_reasons"))
    rows = []
    for item in data["rows"]:
        row = {"record_type": "nucleus", **common,
               **{key: value for key, value in item.items() if key not in ("target", "reference", "raw", "corrected", "exclusions")},
               "exclusions_json": json.dumps(item["exclusions"], ensure_ascii=False, separators=(",", ":"))}
        for side in ("target", "reference"):
            row.update({f"{side}_{key}": value for key, value in item[side].items()})
        for basis in ("raw", "corrected"):
            row.update({f"{basis}_{key}": ";".join(value) if key == "missing_reasons" else value
                        for key, value in item[basis].items()})
        rows.append(row)
    if not rows:
        rows.append({"record_type": "report", **common})
    stream = io.StringIO(newline="")
    _write_rows(stream, rows, columns=columns)
    return stream.getvalue().encode("utf-8-sig")
