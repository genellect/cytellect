"""Versioned, validated scientific inputs shared by API and workers."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

from .plan_adoption import PlanResolution

Point = tuple[FiniteFloat, FiniteFloat]
NonNegative = Annotated[FiniteFloat, Field(ge=0)]

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class FieldMetadata(StrictModel):
    condition: str = Field(min_length=1, max_length=80)
    experimental_unit: str = Field(min_length=1, max_length=80)
    sample: str = Field(min_length=1, max_length=80)
    acquisition_date: str = Field(min_length=1, max_length=40)
    pair: str | None = Field(default=None, max_length=80)
    repeat_length: NonNegative | None = None
    pixel_size_um: Annotated[FiniteFloat, Field(gt=0)] | None = None

class Background(StrictModel):
    polygon: list[Point] = Field(min_length=3, max_length=1000)
    confirmed: bool = False

class LegacyParameters(StrictModel):
    version: Literal["1.0.0"] = "1.0.0"
    target_long_dimension_px: int = Field(default=320, ge=32, le=4096)
    nucleus_area_min_scaled_px: int = Field(default=300, ge=1, le=1000000)
    nucleus_area_max_scaled_px: int = Field(default=6000, ge=1, le=1000000)
    dapi_snr_min: NonNegative = 2.0
    saturation_fraction_max: Annotated[FiniteFloat, Field(ge=0, le=1)] = 0.25
    apply_quality_exclusions: bool = True
    gfp_mode: Literal["otsu-qc-batch", "recipe"] = "otsu-qc-batch"

    @model_validator(mode="after")
    def valid(self):
        if self.nucleus_area_max_scaled_px < self.nucleus_area_min_scaled_px:
            raise ValueError("legacy_area_range_invalid")
        return self


class Recipe(StrictModel):
    id: Literal["ncl-native-2d", "ncl-legacy-rgb", "gfp-nuclear-2d"] = "ncl-native-2d"
    version: Literal["1.0.0"] = "1.0.0"
    probability: Annotated[FiniteFloat, Field(gt=0, lt=1)] = 0.5
    nms: Annotated[FiniteFloat, Field(gt=0, lt=1)] = 0.3
    percentile_low: Annotated[FiniteFloat, Field(ge=0, lt=100)] = 1
    percentile_high: Annotated[FiniteFloat, Field(gt=0, le=100)] = 99.8
    nucleolar_method: Literal["ncl-otsu", "dapi-low"] = "ncl-otsu"
    smoothing_sigma_px: Annotated[FiniteFloat, Field(ge=0, le=10)] = 0
    minimum_area_px: int = Field(default=1, ge=1, le=100000)
    split_touching: bool = False
    dapi_low_percentile: Annotated[FiniteFloat, Field(gt=0, lt=50)] = 10
    gfp_gate: Literal["none", "manual", "otsu-batch", "negative-control"] = "none"
    gfp_threshold: FiniteFloat | None = None
    gfp_negative_control_fields: list[str] = Field(default_factory=list, max_length=100)
    gfp_negative_control_confirmed: bool = False
    gfp_maximum: FiniteFloat | None = None
    native_signal_qc_minimum_ratio: NonNegative | None = None
    seed: int = Field(default=0, ge=0)
    legacy: LegacyParameters = Field(default_factory=LegacyParameters)

    @model_validator(mode="after")
    def valid(self):
        if self.percentile_low >= self.percentile_high:
            raise ValueError("Invalid normalization interval")
        if self.gfp_gate in ("manual", "negative-control") and self.gfp_threshold is None:
            raise ValueError("Manual GFP gate requires a threshold")
        if self.gfp_gate == "negative-control" and (not self.gfp_negative_control_fields or not self.gfp_negative_control_confirmed):
            raise ValueError("Negative-control gate requires explicitly confirmed control fields")
        if len(self.gfp_negative_control_fields) != len(set(self.gfp_negative_control_fields)):
            raise ValueError("Duplicate negative-control field IDs")
        if self.gfp_maximum is not None and self.gfp_threshold is not None and self.gfp_maximum < self.gfp_threshold:
            raise ValueError("GFP maximum is below threshold")
        if self.id == "ncl-legacy-rgb" and self.native_signal_qc_minimum_ratio is not None:
            raise ValueError("native_signal_qc_unavailable_in_legacy")
        return self

class Exclusion(StrictModel):
    field_id: str
    nucleus_id: int | None = Field(default=None, ge=1)
    reason: str = Field(min_length=1, max_length=200)

class AnalysisRequest(StrictModel):
    field_ids: list[str] | None = Field(default=None, min_length=1, max_length=100)
    reuse_revision: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")] | None = None
    recipe: Recipe = Field(default_factory=Recipe)
    backgrounds: dict[str, Background] = Field(default_factory=dict)
    exclusions: list[Exclusion] = Field(default_factory=list, max_length=10000)
    plan_resolution: PlanResolution | None = None

class MaskEdit(StrictModel):
    field_id: str
    layer: Literal["nuclei", "nucleoli", "manual"]
    operation: Literal["add", "replace", "delete", "merge", "split"]
    ids: list[int] = Field(default_factory=list, max_length=1000)
    polygon: list[Point] = Field(default_factory=list, max_length=10000)
    parent_id: int | None = Field(default=None, ge=1)

class PlotSpec(StrictModel):
    preset: Literal["custom", "nature-single", "nature-double"] = "nature-single"
    kind: Literal["distribution", "scatter", "paired"] = "distribution"
    language: Literal["en", "ja"] = "en"
    width_inches: Annotated[FiniteFloat, Field(ge=3, le=16)] = 7
    height_inches: Annotated[FiniteFloat, Field(ge=1, le=16)] = 3.0
    font_size: Annotated[FiniteFloat, Field(ge=5, le=24)] = 7
    x_label: str = Field(default="", max_length=120)
    y_label: str = Field(default="", max_length=120)
    group_order: list[str] = Field(default_factory=list, max_length=30)

class StatisticsRequest(StrictModel):
    metric: Literal[
        "ncl_nucleus_mean", "ncl_nucleus_median", "ncl_nucleus_integrated",
        "ncl_nucleus_mean_corrected", "ncl_nucleus_median_corrected", "ncl_nucleus_integrated_corrected",
        "ncl_nucleoli_mean", "ncl_nucleoli_median", "ncl_nucleoli_integrated",
        "ncl_nucleoli_mean_corrected", "ncl_nucleoli_median_corrected", "ncl_nucleoli_integrated_corrected",
        "ncl_nucleoplasm_mean", "ncl_nucleoplasm_median", "ncl_nucleoplasm_integrated",
        "ncl_nucleoplasm_mean_corrected", "ncl_nucleoplasm_median_corrected", "ncl_nucleoplasm_integrated_corrected",
        "gfp_mean", "gfp_median", "gfp_integrated",
        "gfp_mean_corrected", "gfp_median_corrected", "gfp_integrated_corrected",
        "nucleus_area_px", "nucleus_area_um2", "nucleolar_area_px", "nucleolar_area_um2",
        "nucleoplasm_area_px", "nucleoplasm_area_um2",
        "nucleolar_count", "nucleolar_area_fraction", "ncl_nucleoplasm_over_nucleoli",
        "ncl_log2_nucleoplasm_over_nucleoli", "ncl_legacy_release", "value",
    ] = "ncl_log2_nucleoplasm_over_nucleoli"
    mode: Literal["experimental-unit", "exploratory"] = "experimental-unit"
    baseline: str = Field(min_length=1, max_length=80)
    comparisons: list[tuple[str, str]] = Field(min_length=1, max_length=100)
    paired: bool = False
    independent_units_confirmed: bool = False
    plot: PlotSpec = Field(default_factory=PlotSpec)
    comparison_family: Literal["baseline", "repeat", "all"] = "all"
    gfp_transform: Literal["positive-log2", "legacy-log2p1"] = "positive-log2"
    sensitivity_gfp_thresholds: list[FiniteFloat] = Field(default_factory=list, max_length=10)
    sensitivity_complete_dates: bool = False
    sensitivity_legacy_high_regions: list[Literal[5, 10, 20]] = Field(default_factory=list, max_length=3)
    sensitivity_region_revision_ids: list[Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")]] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def unique_region_sensitivities(self):
        if len(self.sensitivity_region_revision_ids) != len(set(self.sensitivity_region_revision_ids)):
            raise ValueError("duplicate_region_sensitivity_revisions")
        return self

class ReviewInput(StrictModel):
    accept_invalidated_fields: list[str] = Field(default_factory=list, max_length=100)

class ResegmentInput(StrictModel):
    recipe: Recipe | None = None
    field_ids: list[str] = Field(min_length=1, max_length=100)
    backgrounds: dict[str, Background] | None = None
    exclusions: list[Exclusion] | None = Field(default=None, max_length=10000)
    plan_resolution: PlanResolution | None = None



def required_channel_roles(recipe: Recipe) -> set[str]:
    """Actual acquired channels, never zero-filled substitutes."""
    if recipe.id == "ncl-legacy-rgb":
        return {"dapi", "ncl", "gfp"}
    if recipe.id == "gfp-nuclear-2d":
        return {"dapi", "gfp"}
    return {"dapi", "ncl"} | ({"gfp"} if recipe.gfp_gate != "none" or recipe.gfp_maximum is not None else set())
