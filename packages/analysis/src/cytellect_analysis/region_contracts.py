"""JSON-native transport contracts for the generic 2D region workflow.

These models intentionally use lists at HTTP/database boundaries. The immutable
scientific models in ``regions`` remain strict, with explicit tuple conversion.
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, FiniteFloat, field_validator, model_validator

from .plan_adoption import PlanResolution
from .regions import (
    BackgroundSpec,
    Calibration2D,
    ChannelSpec,
    Id,
    Label,
    RegionMeasurementSpec,
    RegionMeasurementTable,
    RegionModel,
    RegionSetSpec,
)

Point = Annotated[list[FiniteFloat], Field(min_length=2, max_length=2)]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
OptionalText = Annotated[str, Field(min_length=1, max_length=80)]


class RegionFieldMetadata(RegionModel):
    condition: OptionalText | None = None
    experimental_unit: OptionalText | None = None
    sample: OptionalText | None = None
    acquisition_date: OptionalText | None = None
    pair: OptionalText | None = None
    repeat_length: Annotated[FiniteFloat, Field(ge=0)] | None = None

    @field_validator("condition", "experimental_unit", "sample", "acquisition_date", "pair")
    @classmethod
    def nonblank_metadata(cls, value):
        if value is not None and (not value.strip() or any(ord(char) < 32 for char in value)):
            raise ValueError("region_metadata_invalid")
        return value


class RegionMetadataEdit(RegionModel):
    version: Literal["1.0.0"] = "1.0.0"
    fields: Annotated[dict[Id, RegionFieldMetadata], Field(min_length=1, max_length=100)]


class RegionMetadataChange(RegionMetadataEdit):
    source_revision_id: Id


class RegionFieldInput(RegionModel):
    version: Literal["1.0.0"] = "1.0.0"
    client_upload_id: Annotated[str, Field(
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )] | None = None
    channels: Annotated[list[ChannelSpec], Field(min_length=1, max_length=3)]
    metadata: RegionFieldMetadata = Field(default_factory=RegionFieldMetadata)
    calibration: Calibration2D | None = None

    @model_validator(mode="after")
    def unique_channels(self):
        ids = [channel.channel_id for channel in self.channels]
        if len(ids) != len({cid.casefold() for cid in ids}):
            raise ValueError("duplicate_region_channel_ids")
        return self


class RegionStoredFile(RegionModel):
    sha256: Digest
    bytes: Annotated[int, Field(gt=0)]


class RegionImageInfo(RegionModel):
    kind: Literal["region-2d"] = "region-2d"
    shape: Annotated[list[Annotated[int, Field(ge=1, le=4096)]], Field(min_length=2, max_length=2)]
    axes: Literal["YX"] = "YX"
    channels: Annotated[list[ChannelSpec], Field(min_length=1, max_length=3)]
    inputs: dict[Id, RegionStoredFile]
    channel_arrays: dict[Id, RegionStoredFile]
    labels_array: RegionStoredFile | None = None
    calibration: Calibration2D | None = None

    @model_validator(mode="after")
    def stored_channel_mapping(self):
        ids = [channel.channel_id for channel in self.channels]
        if len(ids) != len({cid.casefold() for cid in ids}) or set(ids) != set(self.channel_arrays):
            raise ValueError("region_stored_channel_mapping_invalid")
        slots = {f"ch{index}" for index in range(len(ids))}
        if self.labels_array is not None:
            slots.add("labels")
        if set(self.inputs) != slots:
            raise ValueError("region_stored_input_slots_invalid")
        return self


class RegionRecipe(RegionModel):
    id: Literal["region-2d"] = "region-2d"
    version: Literal["1.0.0"] = "1.0.0"
    region_set_id: Id
    label: Label
    source: Literal["manual", "imported"]
    defining_channel_id: Id | None = None

    @field_validator("label")
    @classmethod
    def nonblank_label(cls, value):
        if not value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError("region_label_invalid")
        return value


class NuclearDetectorSpec(RegionModel):
    """Allowlisted, offline nucleus model; never an arbitrary image classifier."""
    engine: Literal["fiji-stardist-2d"] = "fiji-stardist-2d"
    model: Literal["Versatile (fluorescent nuclei)"] = "Versatile (fluorescent nuclei)"
    probability: Annotated[FiniteFloat, Field(gt=0, lt=1)] = 0.5
    nms: Annotated[FiniteFloat, Field(gt=0, lt=1)] = 0.3
    percentile_low: Annotated[FiniteFloat, Field(ge=0, lt=100)] = 1.0
    percentile_high: Annotated[FiniteFloat, Field(gt=0, le=100)] = 99.8

    @model_validator(mode="after")
    def normalization_interval(self):
        if self.percentile_low >= self.percentile_high:
            raise ValueError("nuclear_normalization_interval_invalid")
        return self


class RegionNuclearRecipe(RegionModel):
    id: Literal["region-2d"] = "region-2d"
    version: Literal["1.1.0"] = "1.1.0"
    region_set_id: Id
    label: Label
    source: Literal["stardist_nuclear"] = "stardist_nuclear"
    defining_channel_id: Id
    nuclear_stain_confirmed: Literal[True]
    detector: NuclearDetectorSpec = Field(default_factory=NuclearDetectorSpec)

    @field_validator("nuclear_stain_confirmed", mode="before")
    @classmethod
    def actual_confirmation(cls, value):
        if type(value) is not bool or value is not True:
            raise ValueError("nuclear_stain_confirmation_required")
        return value

    @field_validator("label")
    @classmethod
    def nonblank_label(cls, value):
        if not value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError("region_label_invalid")
        return value


RegionRecipeType = Annotated[RegionRecipe | RegionNuclearRecipe, Field(discriminator="version")]


class RegionBackground(RegionModel):
    polygon: Annotated[list[Point], Field(min_length=3, max_length=1000)]
    confirmed: Literal[True]


class RegionExclusion(RegionModel):
    field_id: Id
    region_id: Annotated[int, Field(ge=1, le=4294967295)] | None = None
    reason: Annotated[str, Field(min_length=1, max_length=200)]

    @field_validator("reason")
    @classmethod
    def nonblank_reason(cls, value):
        if not value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError("region_exclusion_reason_invalid")
        return value


class RegionAnalysisRequest(RegionModel):
    field_ids: Annotated[list[Id], Field(min_length=1, max_length=100)] | None = None
    reuse_revision: Id | None = None
    plan_resolution: PlanResolution | None = None
    recipe: RegionRecipeType
    backgrounds: dict[Id, dict[Id, RegionBackground]] = Field(default_factory=dict)
    exclusions: Annotated[list[RegionExclusion], Field(max_length=10000)] = Field(default_factory=list)

    @field_validator("recipe", mode="before")
    @classmethod
    def historical_recipe_default(cls, value):
        # Original HTTP callers could omit the v1.0 version. Its persisted JSON
        # stays identical; automatic recipes must explicitly select v1.1.
        if isinstance(value, dict) and "version" not in value:
            return {**value, "version": "1.0.0"}
        return value

    @model_validator(mode="after")
    def unique_field_and_exclusion_ids(self):
        if self.field_ids is not None and len(self.field_ids) != len(set(self.field_ids)):
            raise ValueError("duplicate_region_fields")
        exclusions = [(item.field_id, item.region_id) for item in self.exclusions]
        if len(exclusions) != len(set(exclusions)):
            raise ValueError("duplicate_region_exclusions")
        return self


class RegionMaskEdit(RegionModel):
    field_id: Id
    region_set_id: Id
    operation: Literal["add", "replace", "delete", "merge", "split"]
    ids: Annotated[list[Annotated[int, Field(ge=1, le=4294967295)]], Field(max_length=1000)] = Field(default_factory=list)
    polygon: Annotated[list[Point], Field(max_length=10000)] = Field(default_factory=list)
    expected_mask_revision_id: Id | None = None

    @model_validator(mode="after")
    def explicit_edit_target(self):
        if len(self.ids) != len(set(self.ids)):
            raise ValueError("duplicate_region_edit_ids")
        if self.operation == "add" and self.ids:
            raise ValueError("add_does_not_take_region_ids")
        if self.operation in ("replace", "split") and len(self.ids) != 1:
            raise ValueError("region_edit_requires_one_id")
        if self.operation == "merge" and len(self.ids) < 2:
            raise ValueError("region_merge_requires_multiple_ids")
        if self.operation == "delete" and not self.ids:
            raise ValueError("region_delete_requires_ids")
        if self.operation in ("add", "replace", "split") and len(self.polygon) < 3:
            raise ValueError("region_edit_requires_polygon")
        if self.operation in ("delete", "merge") and self.polygon:
            raise ValueError("region_edit_unused_polygon")
        return self


def scientific_specification(*, field_id: str, revision_id: str, mask_revision_id: str,
                             recipe: RegionRecipeType, image_info: RegionImageInfo) -> RegionMeasurementSpec:
    """Explicit JSON-list → immutable science-tuple boundary, shared with replay."""
    return RegionMeasurementSpec(
        field_id=field_id, analysis_revision_id=revision_id,
        region_set=RegionSetSpec(
            region_set_id=recipe.region_set_id, label=recipe.label,
            mask_revision_id=mask_revision_id, source=recipe.source,
            defining_channel_id=recipe.defining_channel_id,
        ),
        channels=tuple(image_info.channels), calibration=image_info.calibration,
        backgrounds=tuple(BackgroundSpec(channel_id=channel.channel_id, roi_revision_id=revision_id, confirmed=True)
                          for channel in image_info.channels),
    )


class RegionFieldMask(RegionModel):
    mask_revision_id: Id
    mask_sha256: Digest
    region_set_id: Id
    source: Literal["manual", "imported", "stardist_nuclear"]
    shape: Annotated[list[Annotated[int, Field(ge=1, le=4096)]], Field(min_length=2, max_length=2)]
    file: RegionStoredFile


class RegionFieldFailure(RegionModel):
    field_id: Id
    reason: Annotated[str, Field(pattern=r"^[a-z0-9_]+$")]


class RegionExcludedFailure(RegionModel):
    field_id: Id
    reason: Annotated[str, Field(min_length=1, max_length=200)]
    error: Annotated[str, Field(pattern=r"^[a-z0-9_]+$")]


class RegionReport(RegionModel):
    """Validate persisted JSON with model_validate_json, preserving strict tuples.

    FastAPI should return that validated instance, rather than asking its Python
    response validator to reinterpret tuple-valued science fields from JSON lists.
    """
    analysis_kind: Literal["region-2d"] = "region-2d"
    protocol_version: Literal["1.0.0"] = "1.0.0"
    revision_id: Id
    recipe: RegionRecipeType
    field_tables: dict[Id, RegionMeasurementTable]
    field_masks: dict[Id, RegionFieldMask]
    field_outcomes: dict[Id, Literal["measured", "no_regions", "failed", "excluded_failed"]]
    field_failures: list[RegionFieldFailure]
    excluded_failed_fields: list[RegionExcludedFailure]
    exclusions: list[RegionExclusion]

    @model_validator(mode="after")
    def complete_outcomes(self):
        failed = [item.field_id for item in self.field_failures]
        excluded = [item.field_id for item in self.excluded_failed_fields]
        if len(failed) != len(set(failed)) or len(excluded) != len(set(excluded)):
            raise ValueError("region_report_duplicate_failure")
        expected: dict[str, str] = {fid: table.status for fid, table in self.field_tables.items()}
        if set(expected) & (set(failed) | set(excluded)) or set(failed) & set(excluded):
            raise ValueError("region_report_conflicting_outcome")
        expected.update(dict.fromkeys(failed, "failed"))
        expected.update(dict.fromkeys(excluded, "excluded_failed"))
        if (expected != self.field_outcomes or not expected
                or not set(self.field_masks).issubset(expected)
                or any(item.field_id not in expected for item in self.exclusions)):
            raise ValueError("region_report_field_coverage_invalid")
        if any(mask.region_set_id != self.recipe.region_set_id or mask.source != self.recipe.source
               for mask in self.field_masks.values()):
            raise ValueError("region_report_mask_definition_mismatch")
        for fid, table in self.field_tables.items():
            mask = self.field_masks.get(fid)
            if (mask is None or table.field_id != fid or table.analysis_revision_id != self.revision_id
                    or table.region_set.region_set_id != self.recipe.region_set_id
                    or table.region_set.label != self.recipe.label
                    or table.region_set.source != self.recipe.source
                    or table.region_set.defining_channel_id != self.recipe.defining_channel_id
                    or table.region_set.mask_revision_id != mask.mask_revision_id
                    or table.mask_sha256 != mask.mask_sha256 or list(table.shape_yx) != mask.shape):
                raise ValueError("region_report_table_mask_mismatch")
        return self
