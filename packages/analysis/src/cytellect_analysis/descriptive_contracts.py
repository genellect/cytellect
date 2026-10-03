"""Explicit descriptive-only contracts; existing inferential requests are unchanged."""
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, StrictInt, model_serializer, model_validator
from pydantic.json_schema import SkipJsonSchema

from .contracts import PlotSpec, StrictModel
from .regions import Id
from .statistical_methods import StatisticalMethodsTemplate

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


class DescriptiveFigurePolicy(StrictModel):
    version: Literal["2.0.0"]
    layout: Literal["field-pages"]


class PagedDescriptiveRequest(DescriptiveRequest):
    figure_policy: DescriptiveFigurePolicy

    @model_validator(mode="after")
    def supported_page_width(self):
        if self.plot.preset not in ("nature-single", "nature-double"):
            raise ValueError("descriptive_page_preset_unsupported")
        return self


DescriptiveRequestType = DescriptiveRequest | PagedDescriptiveRequest


def parse_descriptive_request(value: Any) -> DescriptiveRequestType:
    if isinstance(value, (DescriptiveRequest, PagedDescriptiveRequest)):
        value = value.model_dump(mode="json")
    model = PagedDescriptiveRequest if isinstance(value, dict) and "figure_policy" in value else DescriptiveRequest
    return model.model_validate(value)


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


class PagedDescriptiveResult(DescriptiveResult):
    spec: PagedDescriptiveRequest


class OutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class DescriptivePagePlan(OutputModel):
    page_index: Annotated[StrictInt, Field(ge=1, le=999)]
    field_ids: list[Id] = Field(min_length=1, max_length=8)
    field_numbers: list[Annotated[StrictInt, Field(ge=1)]] = Field(min_length=1, max_length=8)


class DescriptivePageFiles(OutputModel):
    svg: str
    pdf: str
    png: str


class DescriptivePage(OutputModel):
    page_index: Annotated[StrictInt, Field(ge=1, le=999)]
    files: DescriptivePageFiles


class DescriptiveOutputFile(OutputModel):
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    bytes: Annotated[StrictInt, Field(ge=0)]


PresentationErrorCode = Literal[
    "figure_labels_overlap", "figure_text_outside_canvas", "japanese_font_not_installed",
    "sans_serif_font_not_installed", "figure_font_glyphs_unavailable",
]


class DescriptiveRenderError(OutputModel):
    code: PresentationErrorCode
    page_index: Annotated[StrictInt, Field(ge=1, le=999)] | None


def _omit_template_default(schema: dict[str, Any]) -> None:
    schema.pop("default", None)


class PagedDescriptiveOutput(OutputModel):
    descriptive_figure_version: Literal["2.0.0"]
    status: Literal["ready", "tables_only"]
    error: DescriptiveRenderError | None
    field_order: list[Id] = Field(min_length=1)
    page_plan: list[DescriptivePagePlan] = Field(min_length=1)
    pages: list[DescriptivePage]
    y_limits: list[FiniteFloat] = Field(min_length=2, max_length=2)
    y_ticks: list[FiniteFloat]
    style: dict[str, Any]
    font_metadata: dict[str, Any] | None
    source_result_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    source_files: list[str]
    files: dict[str, DescriptiveOutputFile]
    methods_template: StatisticalMethodsTemplate | SkipJsonSchema[None] = Field(
        default=None, json_schema_extra=_omit_template_default)

    @model_validator(mode="before")
    @classmethod
    def explicit_template_not_null(cls, value):
        if isinstance(value, dict) and "methods_template" in value and value["methods_template"] is None:
            raise ValueError("statistical_methods_template_invalid")
        return value

    @model_serializer(mode="wrap")
    def retain_historical_shape(self, handler):
        value = handler(self)
        if self.methods_template is None:
            value.pop("methods_template", None)
        return value

    @model_validator(mode="after")
    def internally_consistent(self):
        count = len(self.page_plan)
        if ([page.page_index for page in self.page_plan] != list(range(1, count + 1))
                or len(self.field_order) != len(set(self.field_order))
                or [fid for page in self.page_plan for fid in page.field_ids] != self.field_order
                or [number for page in self.page_plan for number in page.field_numbers]
                != list(range(1, len(self.field_order) + 1))
                or any(len(page.field_ids) != len(page.field_numbers) for page in self.page_plan)
                or not self.y_limits[0] < self.y_limits[1]
                or len(self.source_files) != len(set(self.source_files))
                or set(self.source_files) != set(self.files)):
            raise ValueError("descriptive_output_manifest_mismatch")
        if self.status == "ready":
            if (self.error is not None or self.font_metadata is None
                    or [page.page_index for page in self.pages] != list(range(1, count + 1))):
                raise ValueError("descriptive_output_manifest_mismatch")
        elif self.error is None or self.pages or self.font_metadata is not None:
            raise ValueError("descriptive_output_manifest_mismatch")
        if self.error is not None and self.error.page_index is not None and self.error.page_index > count:
            raise ValueError("descriptive_output_manifest_mismatch")
        for page in self.pages:
            if page.files.model_dump() != {suffix: f"figure-{page.page_index:03d}.{suffix}"
                                           for suffix in ("svg", "pdf", "png")}:
                raise ValueError("descriptive_output_manifest_mismatch")
        return self
