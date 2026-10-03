"""Area-only measurement protocol 2.0.0; original corrected protocol is unchanged."""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Annotated, Literal

import numpy as np
from pydantic import Field, FiniteFloat, TypeAdapter, model_validator

from .masks import validate_label_array
from .region_policy import RegionMeasurementPolicy as RegionMeasurementPolicy
from .regions import (
    Calibration2D,
    ChannelSpec,
    Id,
    RegionMeasurementSpec,
    RegionMeasurementTable,
    RegionModel,
    RegionSetSpec,
    _array_hash,
    measure_regions,
)

Digest64 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
PositiveBoundedInt = Annotated[int, Field(ge=1, le=4096)]
SAFE_ERROR_CODES = frozenset({
    "region_area_only_backgrounds_forbidden", "region_measurement_protocol_mismatch",
    "region_metric_not_measured",
})


class AreaBackgroundProvenance(RegionModel):
    status: Literal["not_measured"] = "not_measured"
    reason: Literal["not_required_for_area"] = "not_required_for_area"


class RegionMeasurementSpecV2(RegionModel):
    protocol_version: Literal["2.0.0"] = "2.0.0"
    measurement: RegionMeasurementPolicy
    field_id: Id
    analysis_revision_id: Id
    region_set: RegionSetSpec
    channels: Annotated[tuple[ChannelSpec, ...], Field(min_length=1, max_length=3)]
    calibration: Calibration2D | None = None

    @model_validator(mode="after")
    def consistent_channel_ids(self):
        ids = [channel.channel_id for channel in self.channels]
        if len(ids) != len({cid.casefold() for cid in ids}):
            raise ValueError("duplicate_region_channel_ids")
        if self.region_set.defining_channel_id is not None and self.region_set.defining_channel_id not in ids:
            raise ValueError("unknown_defining_channel")
        return self


class ChannelProvenanceV2(RegionModel):
    channel: ChannelSpec
    dtype: Literal["uint8", "uint16"]
    pixel_sha256: Digest64
    storage_maximum: Literal[255, 65535]
    background: AreaBackgroundProvenance

    @model_validator(mode="after")
    def consistent_storage_limit(self):
        maximum = 255 if self.dtype == "uint8" else 65535
        if self.storage_maximum != maximum:
            raise ValueError("region_channel_provenance_inconsistent")
        limit = self.channel.acquisition_saturation_value
        if limit is not None and limit > maximum:
            raise ValueError("acquisition_limit_inconsistent_with_source")
        return self


class RegionMeasurementRowV2(RegionModel):
    field_id: Id
    analysis_revision_id: Id
    region_set_id: Id
    mask_revision_id: Id
    region_id: Annotated[int, Field(ge=1, le=4294967295)]
    channel_id: Id
    area_px: Annotated[int, Field(gt=0)]
    area_um2: Annotated[FiniteFloat, Field(gt=0)] | None
    area_missing_reason: Literal["calibration_unknown"] | None
    mean: None
    median: None
    integrated: None
    mean_corrected: None
    median_corrected: None
    integrated_corrected: None
    intensity_missing_reason: Literal["not_requested"]
    storage_limit_fraction: None
    storage_limit_missing_reason: Literal["not_requested"]
    acquisition_saturation_fraction: None
    acquisition_saturation_missing_reason: Literal["not_requested"]
    touches_border: bool


class RegionMeasurementTableV2(RegionModel):
    protocol_version: Literal["2.0.0"] = "2.0.0"
    measurement: RegionMeasurementPolicy
    status: Literal["measured", "no_regions"]
    field_id: Id
    analysis_revision_id: Id
    region_set: RegionSetSpec
    shape_yx: tuple[PositiveBoundedInt, PositiveBoundedInt]
    mask_sha256: Digest64
    hash_format: Literal["cytellect-array-v1"] = "cytellect-array-v1"
    calibration: Calibration2D | None
    channel_provenance: Annotated[tuple[ChannelProvenanceV2, ...], Field(min_length=1, max_length=3)]
    rows: tuple[RegionMeasurementRowV2, ...]

    @model_validator(mode="after")
    def complete_measurement_table(self):
        channels = [item.channel.channel_id for item in self.channel_provenance]
        if len(channels) != len({cid.casefold() for cid in channels}):
            raise ValueError("duplicate_region_channel_ids")
        if (self.region_set.defining_channel_id is not None
                and self.region_set.defining_channel_id not in channels):
            raise ValueError("unknown_defining_channel")
        if bool(self.rows) != (self.status == "measured"):
            raise ValueError("region_measurement_table_inconsistent")
        regions: dict[int, dict[str, RegionMeasurementRowV2]] = {}
        maximum_area = self.shape_yx[0] * self.shape_yx[1]
        for row in self.rows:
            if (row.field_id != self.field_id or row.analysis_revision_id != self.analysis_revision_id
                    or row.region_set_id != self.region_set.region_set_id
                    or row.mask_revision_id != self.region_set.mask_revision_id
                    or row.channel_id not in channels or row.area_px > maximum_area):
                raise ValueError("region_measurement_table_inconsistent")
            if row.channel_id in regions.setdefault(row.region_id, {}):
                raise ValueError("region_measurement_table_inconsistent")
            regions[row.region_id][row.channel_id] = row
        total_area = 0
        for group in regions.values():
            if set(group) != set(channels):
                raise ValueError("region_measurement_table_inconsistent")
            areas = {(row.area_px, row.area_um2, row.area_missing_reason, row.touches_border)
                     for row in group.values()}
            if len(areas) != 1:
                raise ValueError("region_measurement_table_inconsistent")
            area_px, area_um2, reason, _ = next(iter(areas))
            total_area += area_px
            expected_area = (area_px * (self.calibration.pixel_size_x_um * self.calibration.pixel_size_y_um)
                             if self.calibration is not None else None)
            if expected_area is not None and (not math.isfinite(expected_area) or expected_area <= 0):
                raise ValueError("calibrated_region_area_unrepresentable")
            if (area_um2 != expected_area or
                    reason != ("calibration_unknown" if self.calibration is None else None)):
                raise ValueError("region_area_calibration_mismatch")
        if total_area > maximum_area:
            raise ValueError("region_measurement_table_inconsistent")
        return self


RegionMeasurementSpecType = Annotated[
    RegionMeasurementSpec | RegionMeasurementSpecV2, Field(discriminator="protocol_version"),
]
RegionMeasurementTableType = Annotated[
    RegionMeasurementTable | RegionMeasurementTableV2, Field(discriminator="protocol_version"),
]
_SPEC: TypeAdapter[RegionMeasurementSpec | RegionMeasurementSpecV2] = TypeAdapter(RegionMeasurementSpecType)
_TABLE: TypeAdapter[RegionMeasurementTable | RegionMeasurementTableV2] = TypeAdapter(RegionMeasurementTableType)


def validate_area_backgrounds(measurement: RegionMeasurementPolicy | None, backgrounds: Mapping) -> None:
    if measurement is None:
        return
    RegionMeasurementPolicy.model_validate(measurement)
    if not isinstance(backgrounds, Mapping) or backgrounds:
        raise ValueError("region_area_only_backgrounds_forbidden")


def require_region_metric(measurement: RegionMeasurementPolicy | None, metric: str) -> None:
    if measurement is None:
        return
    RegionMeasurementPolicy.model_validate(measurement)
    if metric not in ("area_px", "area_um2"):
        raise ValueError("region_metric_not_measured")


def region_table_from_json(value: str) -> RegionMeasurementTableType:
    return _TABLE.validate_json(value, strict=True)


def measure_regions_area(channels: dict[str, np.ndarray], labels: np.ndarray,
                         specification: RegionMeasurementSpecV2) -> RegionMeasurementTableV2:
    specification = RegionMeasurementSpecV2.model_validate(specification)
    validate_label_array(labels)
    if max(labels.shape) > 4096:
        raise ValueError("region_plane_limit_exceeded")
    if set(channels) != {channel.channel_id for channel in specification.channels}:
        raise ValueError("region_channel_or_background_mapping_mismatch")
    for channel in specification.channels:
        image = channels[channel.channel_id]
        if (not isinstance(image, np.ndarray) or image.ndim != 2 or image.shape != labels.shape
                or image.dtype not in (np.dtype("uint8"), np.dtype("uint16"))):
            raise ValueError("region_source_shape_or_dtype_invalid")
        limit = channel.acquisition_saturation_value
        if limit is not None and (limit > np.iinfo(image.dtype).max or int(image.max()) > limit):
            raise ValueError("acquisition_limit_inconsistent_with_source")
    provenance = tuple(ChannelProvenanceV2(
        channel=channel, dtype="uint8" if channels[channel.channel_id].dtype.itemsize == 1 else "uint16",
        pixel_sha256=_array_hash(channels[channel.channel_id],
                                 "|u1" if channels[channel.channel_id].dtype.itemsize == 1 else "<u2"),
        storage_maximum=255 if channels[channel.channel_id].dtype.itemsize == 1 else 65535,
        background=AreaBackgroundProvenance(),
    ) for channel in specification.channels)
    object_ids, counts = np.unique(labels, return_counts=True)
    border_ids = set(np.concatenate((labels[0], labels[-1], labels[:, 0], labels[:, -1])).tolist())
    rows = []
    for object_id, count in zip(object_ids, counts, strict=True):
        if object_id == 0:
            continue
        area_px = int(count)
        calibration = specification.calibration
        area_um2 = (area_px * (calibration.pixel_size_x_um * calibration.pixel_size_y_um)
                    if calibration is not None else None)
        if area_um2 is not None and (not math.isfinite(area_um2) or area_um2 <= 0):
            raise ValueError("calibrated_region_area_unrepresentable")
        for channel in specification.channels:
            rows.append(RegionMeasurementRowV2(
                field_id=specification.field_id, analysis_revision_id=specification.analysis_revision_id,
                region_set_id=specification.region_set.region_set_id,
                mask_revision_id=specification.region_set.mask_revision_id,
                region_id=int(object_id), channel_id=channel.channel_id,
                area_px=area_px, area_um2=area_um2,
                area_missing_reason="calibration_unknown" if calibration is None else None,
                mean=None, median=None, integrated=None, mean_corrected=None, median_corrected=None,
                integrated_corrected=None, intensity_missing_reason="not_requested",
                storage_limit_fraction=None, storage_limit_missing_reason="not_requested",
                acquisition_saturation_fraction=None, acquisition_saturation_missing_reason="not_requested",
                touches_border=int(object_id) in border_ids,
            ))
    return RegionMeasurementTableV2(
        measurement=specification.measurement, status="measured" if rows else "no_regions",
        field_id=specification.field_id, analysis_revision_id=specification.analysis_revision_id,
        region_set=specification.region_set, shape_yx=tuple(labels.shape), mask_sha256=_array_hash(labels, "<u4"),
        calibration=specification.calibration, channel_provenance=provenance, rows=tuple(rows),
    )


def measure_regions_versioned(channels: dict[str, np.ndarray], labels: np.ndarray,
                              background_masks: dict[str, np.ndarray],
                              specification: RegionMeasurementSpecType) -> RegionMeasurementTableType:
    specification = _SPEC.validate_python(specification, strict=True)
    if isinstance(specification, RegionMeasurementSpecV2):
        validate_area_backgrounds(specification.measurement, background_masks)
        return measure_regions_area(channels, labels, specification)
    return measure_regions(channels, labels, background_masks, specification)
