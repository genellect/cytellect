"""Explicit descriptive-only contracts; existing inferential requests are unchanged."""
from typing import Annotated, Any, Literal

from pydantic import Field, model_validator

from .contracts import PlotSpec, StrictModel
from .regions import Id

LegacyMetric = Literal[
    "ncl_nucleus_mean", "ncl_nucleus_median", "ncl_nucleus_integrated",
    "ncl_nucleus_mean_corrected", "ncl_nucleus_median_corrected", "ncl_nucleus_integrated_corrected",
    "ncl_nucleoli_mean", "ncl_nucleoli_median", "ncl_nucleoli_integrated",
    "ncl_nucleoli_mean_corrected", "ncl_nucleoli_median_corrected", "ncl_nucleoli_integrated_corrected",
    "ncl_nucleoplasm_mean", "ncl_nucleoplasm_median", "ncl_nucleoplasm_integrated",
    "ncl_nucleoplasm_mean_corrected", "ncl_nucleoplasm_median_corrected", "ncl_nucleoplasm_integrated_corrected",
    "gfp_mean", "gfp_median", "gfp_integrated", "gfp_mean_corrected", "gfp_median_corrected",
    "gfp_integrated_corrected", "nucleus_area_px", "nucleus_area_um2", "nucleolar_area_px",
    "nucleolar_area_um2", "nucleoplasm_area_px", "nucleoplasm_area_um2", "nucleolar_count",
    "nucleolar_area_fraction", "ncl_nucleoplasm_over_nucleoli", "ncl_log2_nucleoplasm_over_nucleoli",
    "ncl_legacy_release",
]
RegionMetric = Literal[
    "area_px", "area_um2", "mean", "median", "integrated",
    "mean_corrected", "median_corrected", "integrated_corrected",
]


class DescriptivePlot(PlotSpec):
    kind: Literal["distribution"] = "distribution"


class LegacySelection(StrictModel):
    source: Literal["legacy-cell"]
    metric: LegacyMetric


class RegionSelection(StrictModel):
    source: Literal["region"]
    region_set_id: Id
    channel_id: Id | None = None
    metric: RegionMetric

    @model_validator(mode="after")
    def channel_for_intensity_only(self):
        if self.metric.startswith("area_"):
            if self.channel_id is not None:
                raise ValueError("descriptive_area_channel_must_be_unset")
        elif self.channel_id is None:
            raise ValueError("descriptive_intensity_channel_required")
        return self


class NumericalSelection(StrictModel):
    source: Literal["numerical"]
    metric: Literal["value"] = "value"


class DescriptiveRequest(StrictModel):
    mode: Literal["descriptive"]
    selection: Annotated[LegacySelection | RegionSelection | NumericalSelection, Field(discriminator="source")]
    group_by: Literal["field"] = "field"
    plot: DescriptivePlot = Field(default_factory=DescriptivePlot)


class DescriptiveResult(StrictModel):
    analysis_kind: Literal["descriptive"] = "descriptive"
    descriptive_version: Literal["1.0.0"] = "1.0.0"
    spec: DescriptiveRequest
    source_kind: Literal["legacy-image-measurements", "region-2d", "measured-numerical-assay"]
    observation_kind: Literal["nuclei", "regions", "observations"]
    metric: str
    unit: str
    metric_definition: str
    plot_data: list[dict[str, Any]]
    field_summary: list[dict[str, Any]]
    counts: dict[str, Any]
    selection: dict[str, Any]
    missingness: list[dict[str, Any]]
    source_fields: list[dict[str, Any]]
    excluded_failed_fields: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str]
    independence_status: Literal["not_assessed_in_descriptive_analysis"] = "not_assessed_in_descriptive_analysis"
