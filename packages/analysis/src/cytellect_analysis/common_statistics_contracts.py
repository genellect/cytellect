"""New opt-in contracts; historical generic comparison v1 remains unchanged."""
from typing import Annotated, Any, Literal

from pydantic import Field, StrictBool, TypeAdapter, field_validator, model_validator

from .contracts import PlotSpec
from .descriptive_contracts import RegionSelection
from .region_comparison_contracts import (
    AcquisitionReview,
    ComparisonDesign,
    Condition,
    RegionComparisonRequest,
    RegionComparisonResult,
)
from .regions import RegionModel


class CommonComparisonPlot(PlotSpec):
    # Opt-in protocol expands this enum without changing the historical PlotSpec schema.
    kind: Literal["distribution", "paired", "histogram", "box", "violin"] = "distribution"  # type: ignore[assignment]
    histogram_bins: Annotated[int, Field(strict=True, ge=3, le=50)] = 10


class RegionComparisonRequestV2(RegionComparisonRequest):
    # Pydantic overrides are intentional version discriminators, not substitutable v1 inputs.
    version: Literal["2.0.0"]  # type: ignore[assignment]
    test: Literal["welch-t", "paired-t", "mann-whitney-u", "wilcoxon"]
    omnibus: Literal["welch-anova", "kruskal-wallis"] | None = None
    plot: CommonComparisonPlot = Field(default_factory=CommonComparisonPlot)  # type: ignore[assignment]

    @model_validator(mode="after")
    def method_matches_design(self):
        if (self.test in ("paired-t", "wilcoxon")) != (self.design.kind == "paired"):
            raise ValueError("common_statistics_test_design_mismatch")
        if self.omnibus is not None and (self.design.kind != "independent" or len(self.conditions) < 3):
            raise ValueError("common_statistics_omnibus_design_mismatch")
        if len(self.conditions) >= 3 and self.design.kind == "independent" and self.omnibus is None:
            raise ValueError("common_statistics_omnibus_required")
        if self.omnibus == "welch-anova" and self.test != "welch-t":
            raise ValueError("common_statistics_omnibus_contrast_mismatch")
        if self.omnibus == "kruskal-wallis" and self.test != "mann-whitney-u":
            raise ValueError("common_statistics_omnibus_contrast_mismatch")
        return self


class RegionComparisonResultV2(RegionComparisonResult):
    # Preserve the historical result schema; this explicit discriminator selects v2.
    region_comparison_version: Literal["2.0.0"] = "2.0.0"  # type: ignore[assignment]
    spec: RegionComparisonRequestV2
    omnibus: dict[str, Any] | None
    method_settings: dict[str, Any]


class AssociationPlot(PlotSpec):
    kind: Literal["scatter"] = "scatter"


class RegionAssociationRequest(RegionModel):
    mode: Literal["region-association"]
    version: Literal["1.0.0"]
    x_selection: RegionSelection
    y_selection: RegionSelection
    design: ComparisonDesign
    conditions: Annotated[list[Condition], Field(min_length=1, max_length=30)]
    acquisition_review: AcquisitionReview
    missingness_confirmed: Literal[True]
    method: Literal["pearson", "spearman"]
    scope: Literal["per-condition", "pooled"] = "per-condition"
    pooling_confirmed: StrictBool = False
    aggregation: Literal["field-median_sample-mean_unit-mean-v1"] = "field-median_sample-mean_unit-mean-v1"
    missingness_policy: Literal["require-matched-unexcluded-units-v1"] = "require-matched-unexcluded-units-v1"
    plot: AssociationPlot = Field(default_factory=AssociationPlot)

    @field_validator("missingness_confirmed", mode="before")
    @classmethod
    def genuine_confirmation(cls, value):
        if type(value) is not bool or value is not True:
            raise ValueError("explicit_confirmation_required")
        return value

    @model_validator(mode="after")
    def explicit_association(self):
        if self.missingness_confirmed is not True or self.design.kind != "independent":
            raise ValueError("common_statistics_independent_association_required")
        if self.x_selection == self.y_selection:
            raise ValueError("common_statistics_distinct_metrics_required")
        if self.x_selection.region_set_id != self.y_selection.region_set_id:
            raise ValueError("common_statistics_matched_region_set_required")
        if self.scope == "pooled" and not self.pooling_confirmed:
            raise ValueError("common_statistics_pooling_confirmation_required")
        if len(set(self.conditions)) != len(self.conditions):
            raise ValueError("region_comparison_condition_scope_mismatch")
        if any(not value.strip() or any(ord(char) < 32 for char in value)
               for value in [*self.conditions, self.design.unit_definition, *self.acquisition_review.field_batches.values()]):
            raise ValueError("region_comparison_invalid_text")
        if self.plot.group_order and (set(self.plot.group_order) != set(self.conditions)
                                     or len(self.plot.group_order) != len(self.conditions)):
            raise ValueError("group_order_must_match_groups")
        return self


class RegionAssociationResult(RegionModel):
    analysis_kind: Literal["region-association"] = "region-association"
    source_kind: Literal["region-2d"] = "region-2d"
    region_association_version: Literal["1.0.0"] = "1.0.0"
    inference_version: str
    revision_id: str
    source_fingerprint: str
    spec: RegionAssociationRequest
    x_source: dict[str, Any]
    y_source: dict[str, Any]
    unit_summary: list[dict[str, Any]]
    unit_ledger: list[dict[str, Any]]
    associations: list[dict[str, Any]]
    counts: list[dict[str, Any]]
    missingness: list[dict[str, Any]]
    warnings: list[str]


CommonStatisticsRequest = Annotated[RegionComparisonRequestV2 | RegionAssociationRequest, Field(discriminator="mode")]
CommonStatisticsResult = Annotated[RegionComparisonResultV2 | RegionAssociationResult, Field(discriminator="analysis_kind")]


def parse_common_statistics_request(value):
    return TypeAdapter(CommonStatisticsRequest).validate_python(value)
