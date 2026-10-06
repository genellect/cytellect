"""Generic, original-pixel region measurements; not connected to the Web API yet.

Scientific protocol 1.0.0. Existing NCL/GFP recipes keep their own contracts and
outputs. A channel label is explicit acquisition metadata, never inferred from
its colour, filename or internal role in another recipe.
"""
from __future__ import annotations

import hashlib
import math
from typing import Annotated, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, TypeAdapter, field_validator, model_validator

from .masks import validate_label_array
from .measurement import region_values

Id = Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")]
Label = Annotated[str, Field(min_length=1, max_length=120)]
Positive = Annotated[FiniteFloat, Field(gt=0)]
PROTOCOL_VERSION: Literal["1.0.0"] = "1.0.0"


class RegionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, revalidate_instances="always")

    @field_validator("identity_confirmed", "confirmed", mode="before", check_fields=False)
    @classmethod
    def explicit_confirmation(cls, value):
        if type(value) is not bool or value is not True:
            raise ValueError("explicit_confirmation_required")
        return value


class ChannelDefinition(RegionModel):
    channel_id: Id
    label: Label
    stain: Label | None = None
    acquisition_saturation_value: Annotated[int, Field(ge=1, le=65535)] | None = None
    acquisition_saturation_confirmed: bool = False

    @field_validator("label", "stain")
    @classmethod
    def descriptive_text(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or any(ord(char) < 32 for char in value)):
            raise ValueError("channel_label_invalid")
        return value

    @model_validator(mode="after")
    def known_acquisition_limit(self):
        if (self.acquisition_saturation_value is not None) != self.acquisition_saturation_confirmed:
            raise ValueError("acquisition_saturation_requires_confirmed_value")
        return self


class ChannelSpec(RegionModel):
    channel_id: Id
    label: Label
    stain: Label | None = None
    identity_confirmed: Literal[True]
    acquisition_saturation_value: Annotated[int, Field(ge=1, le=65535)] | None = None
    acquisition_saturation_confirmed: bool = False

    @field_validator("label", "stain")
    @classmethod
    def descriptive_text(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or any(ord(char) < 32 for char in value)):
            raise ValueError("channel_label_invalid")
        return value

    @model_validator(mode="after")
    def known_acquisition_limit(self):
        if (self.acquisition_saturation_value is not None) != self.acquisition_saturation_confirmed:
            raise ValueError("acquisition_saturation_requires_confirmed_value")
        return self


class ObservedChannelSpec(ChannelDefinition):
    """Recorded import evidence is not a human acquisition confirmation."""
    identity_source: Literal["filename", "ome_metadata", "user_entered", "unresolved"]

    @model_validator(mode="after")
    def unresolved_stain(self):
        if self.identity_source == "unresolved" and self.stain is not None:
            raise ValueError("unresolved_channel_cannot_establish_stain")
        return self


ChannelSpecType = ChannelSpec | ObservedChannelSpec
CHANNEL_SPEC: TypeAdapter[ChannelSpecType] = TypeAdapter(ChannelSpecType)


class Calibration2D(RegionModel):
    pixel_size_x_um: Positive
    pixel_size_y_um: Positive
    confirmed: Literal[True]

    @model_validator(mode="after")
    def finite_pixel_area(self):
        area = self.pixel_size_x_um * self.pixel_size_y_um
        if not math.isfinite(area) or area <= 0:
            raise ValueError("calibration_pixel_area_unrepresentable")
        return self


class RegionSetSpec(RegionModel):
    region_set_id: Id
    label: Label
    mask_revision_id: Id
    source: Literal["manual", "imported", "stardist_nuclear", "fiji_positive_regions"]
    defining_channel_id: Id | None = None

    @field_validator("label")
    @classmethod
    def descriptive_text(cls, value: str) -> str:
        if not value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError("region_label_invalid")
        return value

    @model_validator(mode="after")
    def detector_requires_channel(self):
        if self.source in ("stardist_nuclear", "fiji_positive_regions") and self.defining_channel_id is None:
            raise ValueError("nuclear_detection_requires_defining_channel")
        return self


class BackgroundSpec(RegionModel):
    channel_id: Id
    roi_revision_id: Id
    confirmed: Literal[True]


class RegionMeasurementSpec(RegionModel):
    protocol_version: Literal["1.0.0"] = PROTOCOL_VERSION
    field_id: Id
    analysis_revision_id: Id
    region_set: RegionSetSpec
    channels: Annotated[tuple[ChannelSpec, ...], Field(min_length=1, max_length=4)]
    backgrounds: Annotated[tuple[BackgroundSpec, ...], Field(min_length=1, max_length=4)]
    calibration: Calibration2D | None = None

    @model_validator(mode="after")
    def consistent_channel_ids(self):
        ids = [channel.channel_id for channel in self.channels]
        background_ids = [background.channel_id for background in self.backgrounds]
        if len(ids) != len(set(ids)) or len(background_ids) != len(set(background_ids)):
            raise ValueError("duplicate_channel_or_background_id")
        if set(ids) != set(background_ids):
            raise ValueError("every_channel_requires_background_spec")
        defining = self.region_set.defining_channel_id
        if defining is not None and defining not in ids:
            raise ValueError("unknown_defining_channel")
        return self


class ChannelProvenance(RegionModel):
    channel: ChannelSpec
    dtype: Literal["uint8", "uint16"]
    pixel_sha256: str
    background_mask_sha256: str
    background_revision_id: Id
    background_pixel_count: int
    background_median: float
    storage_maximum: int


class RegionMeasurementRow(RegionModel):
    field_id: Id
    analysis_revision_id: Id
    region_set_id: Id
    mask_revision_id: Id
    region_id: int
    channel_id: Id
    area_px: int
    area_um2: float | None
    area_missing_reason: Literal["calibration_unknown"] | None
    mean: float
    median: float
    integrated: float
    mean_corrected: float
    median_corrected: float
    integrated_corrected: float
    storage_limit_fraction: float
    acquisition_saturation_fraction: float | None
    acquisition_saturation_missing_reason: Literal["acquisition_limit_unknown"] | None
    touches_border: bool


class RegionMeasurementTable(RegionModel):
    protocol_version: Literal["1.0.0"] = PROTOCOL_VERSION
    status: Literal["measured", "no_regions"]
    field_id: Id
    analysis_revision_id: Id
    region_set: RegionSetSpec
    shape_yx: tuple[int, int]
    mask_sha256: str
    hash_format: Literal["cytellect-array-v1"] = "cytellect-array-v1"
    calibration: Calibration2D | None
    channel_provenance: tuple[ChannelProvenance, ...]
    rows: tuple[RegionMeasurementRow, ...]


def _array_hash(array: np.ndarray, dtype: str) -> str:
    """Hash explicit original shape plus canonical little-endian samples."""
    digest = hashlib.sha256()
    digest.update(f"cytellect-array-v1|{dtype}|{array.shape[0]},{array.shape[1]}|".encode("ascii"))
    digest.update(np.ascontiguousarray(array, dtype=np.dtype(dtype)).tobytes(order="C"))
    return digest.hexdigest()


def measure_regions(
    channels: dict[str, np.ndarray], labels: np.ndarray, background_masks: dict[str, np.ndarray],
    specification: RegionMeasurementSpec,
) -> RegionMeasurementTable:
    """Measure all nonzero regions in every explicitly identified channel.

    IDs may be sparse or describe disconnected pixel unions. Neither property
    implies multiple biological cells. All backgrounds must be confirmed and
    outside the union of this region set. No unconfirmed offset is assumed zero.
    """
    specification = RegionMeasurementSpec.model_validate(specification)
    validate_label_array(labels)
    if max(labels.shape) > 4096:
        raise ValueError("region_plane_limit_exceeded")
    ids = {channel.channel_id for channel in specification.channels}
    if set(channels) != ids or set(background_masks) != ids:
        raise ValueError("region_channel_or_background_mapping_mismatch")
    for channel in specification.channels:
        image, background = channels[channel.channel_id], background_masks[channel.channel_id]
        if (not isinstance(image, np.ndarray) or image.ndim != 2 or image.shape != labels.shape
                or image.dtype not in (np.dtype("uint8"), np.dtype("uint16"))):
            raise ValueError("region_source_shape_or_dtype_invalid")
        if (not isinstance(background, np.ndarray) or background.dtype != np.bool_
                or background.shape != labels.shape or not background.any()):
            raise ValueError("region_background_nonempty_boolean_shape_required")
        if np.any(background & (labels > 0)):
            raise ValueError("region_background_overlaps_measured_regions")
        acquisition_limit = channel.acquisition_saturation_value
        if acquisition_limit is not None and (
                acquisition_limit > np.iinfo(image.dtype).max or int(image.max()) > acquisition_limit):
            raise ValueError("acquisition_limit_inconsistent_with_source")

    backgrounds = {entry.channel_id: entry for entry in specification.backgrounds}
    provenance = tuple(ChannelProvenance(
        channel=channel,
        dtype="uint8" if channels[channel.channel_id].dtype.itemsize == 1 else "uint16",
        pixel_sha256=_array_hash(channels[channel.channel_id], "|u1" if channels[channel.channel_id].dtype.itemsize == 1 else "<u2"),
        background_mask_sha256=_array_hash(background_masks[channel.channel_id], "|u1"),
        background_revision_id=backgrounds[channel.channel_id].roi_revision_id,
        background_pixel_count=int(background_masks[channel.channel_id].sum()),
        background_median=float(np.median(channels[channel.channel_id][background_masks[channel.channel_id]])),
        storage_maximum=int(np.iinfo(channels[channel.channel_id].dtype).max),
    ) for channel in specification.channels)
    by_channel = {record.channel.channel_id: record for record in provenance}
    rows = []
    for object_id in np.unique(labels[labels > 0]):
        mask = labels == object_id
        area_px = int(mask.sum())
        calibration = specification.calibration
        area_um2 = (area_px * (calibration.pixel_size_x_um * calibration.pixel_size_y_um)
                    if calibration is not None else None)
        if area_um2 is not None and (not math.isfinite(area_um2) or area_um2 <= 0):
            raise ValueError("calibrated_region_area_unrepresentable")
        border = bool(mask[0].any() or mask[-1].any() or mask[:, 0].any() or mask[:, -1].any())
        for channel in specification.channels:
            image = channels[channel.channel_id]
            origin = by_channel[channel.channel_id]
            saturation = channel.acquisition_saturation_value
            rows.append(RegionMeasurementRow(
                field_id=specification.field_id, analysis_revision_id=specification.analysis_revision_id,
                region_set_id=specification.region_set.region_set_id,
                mask_revision_id=specification.region_set.mask_revision_id,
                region_id=int(object_id), channel_id=channel.channel_id,
                area_px=area_px, area_um2=area_um2,
                area_missing_reason="calibration_unknown" if calibration is None else None,
                **region_values(image, mask, origin.background_median),
                storage_limit_fraction=float(np.mean(image[mask] == origin.storage_maximum)),
                acquisition_saturation_fraction=float(np.mean(image[mask] == saturation)) if saturation is not None else None,
                acquisition_saturation_missing_reason="acquisition_limit_unknown" if saturation is None else None,
                touches_border=border,
            ))
    return RegionMeasurementTable(
        status="measured" if rows else "no_regions", field_id=specification.field_id,
        analysis_revision_id=specification.analysis_revision_id, region_set=specification.region_set,
        shape_yx=tuple(labels.shape), mask_sha256=_array_hash(labels, "<u4"),
        calibration=specification.calibration, channel_provenance=provenance, rows=tuple(rows),
    )
