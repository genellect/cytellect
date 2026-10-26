"""Contracts for the group-comparison workflow (planned observation sources and estimates).

These additive contracts are defined before their implementations so that the
metric modules (field_summary.py, nucleolar_shape.py) and the estimate module
(comparison_estimates.py) can be built and reviewed in parallel. The common-statistics
comparison and descriptive requests share the observation-source contracts.
Definitions are in docs/methods.md, "Group comparison contracts".
"""
from typing import Annotated, Literal, Union

from pydantic import Discriminator, Field, FiniteFloat, Tag, model_validator

from .descriptive_contracts import (
    COMPARTMENT_SUMMARY_SELECTION_V11 as COMPARTMENT_SUMMARY_SELECTION_V11,
)
from .descriptive_contracts import (
    FIELD_SUMMARY_VERSION as FIELD_SUMMARY_VERSION,
)
from .descriptive_contracts import (
    CompartmentSummarySelection,
    RegionSelection,
    _selection_tag,
)
from .descriptive_contracts import (
    CompartmentSummarySelectionV11 as CompartmentSummarySelectionV11,
)
from .descriptive_contracts import (
    FieldSummaryMetric as FieldSummaryMetric,
)
from .descriptive_contracts import (
    FieldSummarySelection as FieldSummarySelection,
)
from .descriptive_contracts import (
    NucleolarSummaryMetric as NucleolarSummaryMetric,
)
from .regions import RegionModel

ESTIMATES_PROTOCOL: Literal["comparison-estimates/1.0.0"] = "comparison-estimates/1.0.0"


# The comparison observation sources; compartment summaries are chosen by their own version.
ComparisonSelection = Annotated[
    Union[Annotated[RegionSelection, Tag("region")],
          Annotated[CompartmentSummarySelection, Tag("compartment-summary/1.0.0")],
          Annotated[CompartmentSummarySelectionV11, Tag("compartment-summary/1.1.0")],
          Annotated[FieldSummarySelection, Tag("field-summary")]],
    Discriminator(_selection_tag)]


MetricScale = Literal["ratio", "difference", "fraction", "log2"]

# How a treatment − control effect is expressed (requirements S-04). "ratio": a
# difference in the metric's unit and, when every unit value is positive, a ratio;
# "difference": a difference only (values may be negative or bounded);
# "fraction": a difference in percentage points, no ratio; "log2": a difference
# in log2 units, no ratio.
_SCALES: dict[str, MetricScale] = {
    "area_px": "ratio", "area_um2": "ratio", "mean": "ratio", "median": "ratio", "integrated": "ratio",
    "mean_corrected": "difference", "median_corrected": "difference", "integrated_corrected": "difference",
    "nucleus_count": "ratio", "nucleus_density_per_mm2": "ratio", "positive_count": "ratio",
    "positive_fraction": "fraction",
    "nucleolar_count": "ratio", "nucleolar_area_px": "ratio", "nucleolar_area_um2": "ratio",
    "nucleolar_area_fraction": "fraction", "nucleolar_eccentricity": "difference",
    "log2_nucleoplasm_over_nucleolus": "log2",
}


def metric_scale(metric: str) -> MetricScale:
    try:
        return _SCALES[metric]
    except KeyError:
        raise ValueError("comparison_estimates_unknown_metric") from None


Number = FiniteFloat | None


class EstimateInterval(RegionModel):
    estimate: Number
    ci_low: Number
    ci_high: Number
    confidence_level: float = Field(default=0.95, ge=0.95, le=0.95)
    # A short English description of what the interval is about, for Methods and the result sentence.
    basis: str | None
    unavailable_reason: str | None

    @model_validator(mode="after")
    def complete_or_explained(self):
        values = (self.estimate, self.ci_low, self.ci_high)
        if (self.unavailable_reason is None) == (self.estimate is None):
            raise ValueError("comparison_estimates_interval_inconsistent")
        if self.estimate is None and any(value is not None for value in values):
            raise ValueError("comparison_estimates_interval_inconsistent")
        if self.estimate is not None and (self.ci_low is None or self.ci_high is None
                                          or not self.ci_low <= self.estimate <= self.ci_high):
            raise ValueError("comparison_estimates_interval_inconsistent")
        return self


class GroupEstimate(RegionModel):
    condition: str
    n: Annotated[int, Field(ge=0)]
    mean: Number
    sd: Number
    ci_low: Number
    ci_high: Number
    unavailable_reason: str | None


class RunEstimate(RegionModel):
    """One independent run of a paired comparison, from the saved pair ledger."""
    pair: str
    control: FiniteFloat
    treatment: FiniteFloat
    difference: FiniteFloat
    ratio: Number


class ComparisonEstimates(RegionModel):
    protocol: Literal["comparison-estimates/1.0.0"] = ESTIMATES_PROTOCOL
    direction: Literal["treatment_minus_control"] = "treatment_minus_control"
    control: str
    treatment: str
    design: Literal["independent", "paired"]
    # "none": descriptive only; differences, ratios and intervals are not estimated.
    test: Literal["welch-t", "paired-t", "mann-whitney-u", "wilcoxon", "none"]
    metric: str
    scale: MetricScale
    n_control: Annotated[int, Field(ge=0)]
    n_treatment: Annotated[int, Field(ge=0)]
    n_pairs: Annotated[int, Field(ge=0)] | None
    difference: EstimateInterval
    ratio: EstimateInterval
    groups: list[GroupEstimate]
    runs: list[RunEstimate]
