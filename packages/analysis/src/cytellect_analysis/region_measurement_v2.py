"""Area-only 2.0.0, raw 3.0.0 and automatic-background 4.0.0; corrected protocol 1.0.0 is unchanged."""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Annotated, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, TypeAdapter, model_validator

from . import background_candidate
from .masks import validate_label_array
from .measurement import region_values
from .region_policy import (
    MEASUREMENT_POLICY,
    MODE_BY_PROTOCOL,
    AutomaticBackgroundPolicy,
    MeasurementPolicy,
    RawIntensityPolicy,
)
from .region_policy import RegionMeasurementPolicy as RegionMeasurementPolicy
from .regions import (
    Calibration2D,
    ChannelSpecType,
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
    "region_metric_not_measured", "region_automatic_background_roi_conflict",
    "region_background_exclusion_invalid",
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
    channels: Annotated[tuple[ChannelSpecType, ...], Field(min_length=1, max_length=4)]
    calibration: Calibration2D | None = None

    @model_validator(mode="after")
    def consistent_channel_ids(self):
        if self.measurement.mode != MODE_BY_PROTOCOL[self.protocol_version]:
            raise ValueError("region_measurement_protocol_mismatch")
        ids = [channel.channel_id for channel in self.channels]
        if len(ids) != len({cid.casefold() for cid in ids}):
            raise ValueError("duplicate_region_channel_ids")
        if self.region_set.defining_channel_id is not None and self.region_set.defining_channel_id not in ids:
            raise ValueError("unknown_defining_channel")
        return self


class ChannelProvenanceV2(RegionModel):
    channel: ChannelSpecType
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
    channel_provenance: Annotated[tuple[ChannelProvenanceV2, ...], Field(min_length=1, max_length=4)]
    rows: tuple[RegionMeasurementRowV2, ...]

    @model_validator(mode="after")
    def complete_measurement_table(self):
        if self.measurement.mode != MODE_BY_PROTOCOL[self.protocol_version]:
            raise ValueError("region_measurement_protocol_mismatch")
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


class RegionMeasurementSpecV3(RegionMeasurementSpecV2):
    measurement: RawIntensityPolicy  # type: ignore[assignment]
    protocol_version: Literal["3.0.0"] = "3.0.0"  # type: ignore[assignment]


class RawBackgroundProvenance(RegionModel):
    status: Literal["not_established"] = "not_established"  # type: ignore[assignment]
    reason: Literal["raw_measurement_only"] = "raw_measurement_only"  # type: ignore[assignment]


class ChannelProvenanceV3(ChannelProvenanceV2):
    background: RawBackgroundProvenance  # type: ignore[assignment]


class RegionMeasurementRowV3(RegionMeasurementRowV2):
    mean: Annotated[FiniteFloat, Field(ge=0, le=65535)]  # type: ignore[assignment]
    median: Annotated[FiniteFloat, Field(ge=0, le=65535)]  # type: ignore[assignment]
    integrated: Annotated[FiniteFloat, Field(ge=0)]  # type: ignore[assignment]
    intensity_missing_reason: None = None  # type: ignore[assignment]
    correction_missing_reason: Literal["background_not_established"] = "background_not_established"  # type: ignore[assignment]
    storage_limit_fraction: Annotated[FiniteFloat, Field(ge=0, le=1)]  # type: ignore[assignment]
    storage_limit_missing_reason: None = None  # type: ignore[assignment]
    acquisition_saturation_fraction: Annotated[FiniteFloat, Field(ge=0, le=1)] | None  # type: ignore[assignment]
    acquisition_saturation_missing_reason: Literal["acquisition_limit_unknown"] | None  # type: ignore[assignment]

    @model_validator(mode="after")
    def consistent_raw_values(self):
        if not math.isclose(self.integrated, self.mean * self.area_px, rel_tol=1e-12, abs_tol=1e-9):
            raise ValueError("region_raw_intensity_inconsistent")
        if (self.acquisition_saturation_fraction is None) != (self.acquisition_saturation_missing_reason is not None):
            raise ValueError("region_raw_intensity_inconsistent")
        return self


class RegionMeasurementTableV3(RegionMeasurementTableV2):
    measurement: RawIntensityPolicy  # type: ignore[assignment]
    protocol_version: Literal["3.0.0"] = "3.0.0"  # type: ignore[assignment]
    channel_provenance: Annotated[tuple[ChannelProvenanceV3, ...], Field(min_length=1, max_length=4)]  # type: ignore[assignment]
    rows: tuple[RegionMeasurementRowV3, ...]  # type: ignore[assignment]


class RegionMeasurementSpecV4(RegionMeasurementSpecV2):
    measurement: AutomaticBackgroundPolicy  # type: ignore[assignment]
    protocol_version: Literal["4.0.0"] = "4.0.0"  # type: ignore[assignment]


class _AutomaticRecord(BaseModel):
    # Deliberately not RegionModel: RegionModel only admits confirmed=True,
    # and this record must state that no person confirmed the background.
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, revalidate_instances="always")


class AutomaticBackgroundConstants(_AutomaticRecord):
    tile_size_px: int
    perinuclear_margin_px: int
    margin_metric: str
    min_unexcluded_fraction: float
    bright_rule: str
    bright_k: float
    bright_mad_floor: float
    mad_scale: float
    tile_median_k: float
    tile_dispersion_k: float
    rejection_passes: int
    min_tiles: int
    min_quadrants: int
    quadrant_rule: str

    @model_validator(mode="after")
    def recorded_protocol_constants(self):
        if self.model_dump() != background_candidate.CONSTANTS:
            raise ValueError("automatic_background_constants_mismatch")
        return self


AutomaticBackgroundFailure = Literal["automatic_background_insufficient_tiles",
                                     "automatic_background_insufficient_coverage"]
Count = Annotated[int, Field(ge=0)]


class AutomaticBackgroundProvenance(_AutomaticRecord):
    status: Literal["established", "not_established"]
    background_source: Literal["automatic_candidate"] = "automatic_candidate"
    confirmed: Literal[False] = False
    algorithm: Literal["cytellect-automatic-background"]
    algorithm_version: Literal["1.0.0"]
    constants: AutomaticBackgroundConstants
    exclusion_mask_sha256: Digest64
    additional_exclusion: bool
    bright_threshold: FiniteFloat | None
    excluded_pixel_count: Count
    eligible_tile_count: Count
    median_rejected_tile_count: Count
    dispersion_rejected_tile_count: Count
    retained_tile_count: Count
    quadrants: tuple[Annotated[int, Field(ge=0, le=3)], ...]
    retained_tile_median_min: FiniteFloat | None
    retained_tile_median_max: FiniteFloat | None
    background_mask_sha256: Digest64 | None
    background_pixel_count: Annotated[int, Field(gt=0)] | None
    background_median: Annotated[FiniteFloat, Field(ge=0, le=65535)] | None
    reason: AutomaticBackgroundFailure | None

    @model_validator(mode="after")
    def consistent_outcome(self):
        established = self.status == "established"
        values = (self.background_mask_sha256, self.background_pixel_count, self.background_median)
        if (established != (self.reason is None)
                or any((value is not None) != established for value in values)
                or list(self.quadrants) != sorted(set(self.quadrants))
                or (established and (self.retained_tile_count < self.constants.min_tiles
                                     or len(self.quadrants) < self.constants.min_quadrants))):
            raise ValueError("automatic_background_provenance_inconsistent")
        return self


class ChannelProvenanceV4(ChannelProvenanceV2):
    background: AutomaticBackgroundProvenance  # type: ignore[assignment]


class RegionMeasurementRowV4(RegionMeasurementRowV3):
    mean_corrected: FiniteFloat | None  # type: ignore[assignment]
    median_corrected: FiniteFloat | None  # type: ignore[assignment]
    integrated_corrected: FiniteFloat | None  # type: ignore[assignment]
    correction_missing_reason: AutomaticBackgroundFailure | None  # type: ignore[assignment]

    @model_validator(mode="after")
    def consistent_correction(self):
        corrected = (self.mean_corrected, self.median_corrected, self.integrated_corrected)
        if any((value is None) != (self.correction_missing_reason is not None) for value in corrected):
            raise ValueError("region_corrected_intensity_inconsistent")
        return self


class RegionMeasurementTableV4(RegionMeasurementTableV3):
    measurement: AutomaticBackgroundPolicy  # type: ignore[assignment]
    protocol_version: Literal["4.0.0"] = "4.0.0"  # type: ignore[assignment]
    channel_provenance: Annotated[tuple[ChannelProvenanceV4, ...], Field(min_length=1, max_length=4)]  # type: ignore[assignment]
    rows: tuple[RegionMeasurementRowV4, ...]  # type: ignore[assignment]

    @model_validator(mode="after")
    def corrections_follow_channel_background(self):
        backgrounds = {item.channel.channel_id: item.background for item in self.channel_provenance}
        for row in self.rows:
            background = backgrounds[row.channel_id]
            if background.background_median is None:
                if row.mean_corrected is not None or row.correction_missing_reason != background.reason:
                    raise ValueError("region_corrected_intensity_inconsistent")
                continue
            b = background.background_median
            assert row.mean_corrected is not None and row.integrated_corrected is not None
            assert row.median_corrected is not None
            scale = max(1.0, abs(row.integrated), row.area_px * b)
            if (not math.isclose(row.mean_corrected, row.mean - b, rel_tol=1e-9, abs_tol=1e-9)
                    or not math.isclose(row.median_corrected, row.median - b, rel_tol=1e-9, abs_tol=1e-9)
                    or not math.isclose(row.integrated_corrected, row.integrated - row.area_px * b,
                                        rel_tol=0, abs_tol=1e-9 * scale)):
                raise ValueError("region_corrected_intensity_inconsistent")
        return self


_SpecUnion = RegionMeasurementSpec | RegionMeasurementSpecV2 | RegionMeasurementSpecV3 | RegionMeasurementSpecV4
_TableUnion = RegionMeasurementTable | RegionMeasurementTableV2 | RegionMeasurementTableV3 | RegionMeasurementTableV4
RegionMeasurementSpecType = Annotated[_SpecUnion, Field(discriminator="protocol_version")]
RegionMeasurementTableType = Annotated[_TableUnion, Field(discriminator="protocol_version")]
_SPEC: TypeAdapter[_SpecUnion] = TypeAdapter(RegionMeasurementSpecType)
_TABLE: TypeAdapter[_TableUnion] = TypeAdapter(RegionMeasurementTableType)


def validate_area_backgrounds(measurement: MeasurementPolicy | None, backgrounds: Mapping) -> None:
    """Versioned policies never accept ROI backgrounds; None keeps confirmed protocol 1.0.0."""
    if measurement is None:
        return
    measurement = MEASUREMENT_POLICY.validate_python(measurement)
    if not isinstance(backgrounds, Mapping) or backgrounds:
        # A confirmed ROI and an automatic candidate are never mixed in one request.
        raise ValueError("region_automatic_background_roi_conflict" if measurement.mode == "automatic_background"
                         else "region_area_only_backgrounds_forbidden")


def require_region_metric(measurement: MeasurementPolicy | None, metric: str) -> None:
    if measurement is None:
        return
    measurement = MEASUREMENT_POLICY.validate_python(measurement)
    allowed = {
        "area_only": ("area_px", "area_um2"),
        "raw_intensity": ("area_px", "area_um2", "mean", "median", "integrated"),
        "automatic_background": ("area_px", "area_um2", "mean", "median", "integrated",
                                 "mean_corrected", "median_corrected", "integrated_corrected"),
    }[measurement.mode]
    if metric not in allowed:
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
                              specification: RegionMeasurementSpecType, *,
                              background_exclusion: np.ndarray | None = None) -> RegionMeasurementTableType:
    """``background_exclusion`` adds nonzero pixels (e.g. source nuclei) to the
    automatic-background exclusion of protocol 4.0.0; other protocols refuse it."""
    specification = _SPEC.validate_python(specification, strict=True)
    if isinstance(specification, RegionMeasurementSpecV4):
        return _measure_automatic_background(channels, labels, background_masks, specification,
                                             background_exclusion)
    if background_exclusion is not None:
        raise ValueError("region_background_exclusion_invalid")
    if isinstance(specification, RegionMeasurementSpecV3):
        validate_area_backgrounds(specification.measurement, background_masks)
        area_spec = RegionMeasurementSpecV2(
            **{**specification.model_dump(), "protocol_version": "2.0.0",
               "measurement": RegionMeasurementPolicy(version="1.0.0", mode="area_only")})
        area = measure_regions_area(channels, labels, area_spec)
        rows = []
        for row in area.rows:
            values = channels[row.channel_id][labels == row.region_id].astype(np.float64)
            channel = next(c for c in specification.channels if c.channel_id == row.channel_id)
            limit = channel.acquisition_saturation_value
            rows.append(RegionMeasurementRowV3(**{**row.model_dump(),
                "mean": float(values.mean()), "median": float(np.median(values)),
                "integrated": float(values.sum()), "intensity_missing_reason": None,
                "storage_limit_fraction": float(np.mean(values == np.iinfo(channels[row.channel_id].dtype).max)),
                "storage_limit_missing_reason": None,
                "acquisition_saturation_fraction": None if limit is None else float(np.mean(values >= limit)),
                "acquisition_saturation_missing_reason": "acquisition_limit_unknown" if limit is None else None}))
        provenance = tuple(ChannelProvenanceV3(**{**p.model_dump(), "background": RawBackgroundProvenance()})
                           for p in area.channel_provenance)
        return RegionMeasurementTableV3(**{**area.model_dump(), "protocol_version": "3.0.0",
            "measurement": specification.measurement, "rows": tuple(rows), "channel_provenance": provenance})
    if isinstance(specification, RegionMeasurementSpecV2):
        validate_area_backgrounds(specification.measurement, background_masks)
        return measure_regions_area(channels, labels, specification)
    return measure_regions(channels, labels, background_masks, specification)


def _measure_automatic_background(channels: dict[str, np.ndarray], labels: np.ndarray,
                                  background_masks: Mapping, specification: RegionMeasurementSpecV4,
                                  background_exclusion: np.ndarray | None) -> RegionMeasurementTableV4:
    """Raw protocol 3.0.0 values plus corrections from an automatic background candidate.

    ``b = median(I[B])`` and the corrections use the shared ``region_values`` on
    original pixels: corrected mean ``mean(I[R]) - b`` and corrected integral
    ``sum(I[R]) - |R| b``, signed and unclipped. A channel without a candidate keeps
    its raw values and leaves every corrected value missing with the reason.
    """
    validate_area_backgrounds(specification.measurement, background_masks)
    raw = measure_regions_versioned(channels, labels, {}, RegionMeasurementSpecV3(
        **{**specification.model_dump(), "protocol_version": "3.0.0",
           "measurement": RawIntensityPolicy(version="1.1.0", mode="raw_intensity")}))
    assert isinstance(raw, RegionMeasurementTableV3)
    exclusion = labels != 0
    if background_exclusion is not None:
        if not isinstance(background_exclusion, np.ndarray) or background_exclusion.shape != labels.shape:
            raise ValueError("region_background_exclusion_invalid")
        exclusion = exclusion | (background_exclusion != 0)
    exclusion_sha256 = _array_hash(exclusion, "|u1")
    backgrounds: dict[str, AutomaticBackgroundProvenance] = {}
    medians: dict[str, float | None] = {}
    for channel in specification.channels:
        image = channels[channel.channel_id]
        mask, record = background_candidate.automatic_background(image, exclusion)
        median = None
        if mask is not None:
            if not mask.any() or np.any(mask & exclusion):
                raise ValueError("automatic_background_provenance_inconsistent")
            median = float(np.median(image[mask]))
        medians[channel.channel_id] = median
        backgrounds[channel.channel_id] = AutomaticBackgroundProvenance(
            **{**record, "quadrants": tuple(record["quadrants"])}, status="not_established" if mask is None else "established",
            exclusion_mask_sha256=exclusion_sha256, additional_exclusion=background_exclusion is not None,
            background_mask_sha256=None if mask is None else _array_hash(mask, "|u1"),
            background_pixel_count=None if mask is None else int(mask.sum()),
            background_median=median,
        )
    rows = []
    for row in raw.rows:
        b = medians[row.channel_id]
        if b is None:
            corrected = {"mean_corrected": None, "median_corrected": None, "integrated_corrected": None,
                         "correction_missing_reason": backgrounds[row.channel_id].reason}
        else:
            values = region_values(channels[row.channel_id], labels == row.region_id, b)
            corrected = {key: values[key] for key in ("mean_corrected", "median_corrected", "integrated_corrected")}
            corrected["correction_missing_reason"] = None
        rows.append(RegionMeasurementRowV4(**{**row.model_dump(), **corrected}))
    provenance = tuple(ChannelProvenanceV4(**{**item.model_dump(), "background": backgrounds[item.channel.channel_id]})
                       for item in raw.channel_provenance)
    return RegionMeasurementTableV4(**{**raw.model_dump(), "protocol_version": "4.0.0",
        "measurement": specification.measurement, "rows": tuple(rows), "channel_provenance": provenance})
