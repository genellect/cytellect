"""Versioned, validated scientific inputs shared by API and workers."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

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

class Recipe(StrictModel):
    id: Literal["ncl-native-2d", "ncl-legacy-rgb"] = "ncl-native-2d"
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
    gfp_gate: Literal["none", "manual", "otsu-batch"] = "none"
    gfp_threshold: FiniteFloat | None = None
    gfp_maximum: FiniteFloat | None = None
    seed: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def valid(self):
        if self.percentile_low >= self.percentile_high:
            raise ValueError("Invalid normalization interval")
        if self.gfp_gate == "manual" and self.gfp_threshold is None:
            raise ValueError("Manual GFP gate requires a threshold")
        if self.gfp_maximum is not None and self.gfp_threshold is not None and self.gfp_maximum < self.gfp_threshold:
            raise ValueError("GFP maximum is below threshold")
        return self

class Exclusion(StrictModel):
    field_id: str
    nucleus_id: int | None = Field(default=None, ge=1)
    reason: str = Field(min_length=1, max_length=200)

class AnalysisRequest(StrictModel):
    recipe: Recipe = Field(default_factory=Recipe)
    backgrounds: dict[str, Background] = Field(default_factory=dict)
    exclusions: list[Exclusion] = Field(default_factory=list, max_length=10000)

class MaskEdit(StrictModel):
    field_id: str
    layer: Literal["nuclei", "nucleoli", "manual"]
    operation: Literal["add", "replace", "delete", "merge", "split"]
    ids: list[int] = Field(default_factory=list, max_length=1000)
    polygon: list[Point] = Field(default_factory=list, max_length=10000)
    parent_id: int | None = Field(default=None, ge=1)

class PlotSpec(StrictModel):
    kind: Literal["distribution", "scatter", "paired"] = "distribution"
    language: Literal["en", "ja"] = "en"
    width_inches: Annotated[FiniteFloat, Field(ge=3, le=16)] = 7
    height_inches: Annotated[FiniteFloat, Field(ge=3, le=16)] = 5
    font_size: Annotated[FiniteFloat, Field(ge=6, le=24)] = 10
    x_label: str = Field(default="", max_length=120)
    y_label: str = Field(default="", max_length=120)
    group_order: list[str] = Field(default_factory=list, max_length=30)

class StatisticsRequest(StrictModel):
    metric: Literal["ncl_log2_nucleoplasm_over_nucleoli", "ncl_legacy_release", "ncl_nucleus_mean_corrected", "gfp_mean_corrected", "nucleolar_area_fraction"] = "ncl_log2_nucleoplasm_over_nucleoli"
    mode: Literal["experimental-unit", "exploratory"] = "experimental-unit"
    baseline: str = Field(min_length=1, max_length=80)
    comparisons: list[tuple[str, str]] = Field(min_length=1, max_length=100)
    paired: bool = False
    independent_units_confirmed: bool = False
    plot: PlotSpec = Field(default_factory=PlotSpec)
