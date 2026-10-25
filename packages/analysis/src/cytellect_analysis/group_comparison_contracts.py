"""Contracts for the group-comparison workflow (planned observation sources and estimates).

These additive contracts are defined before their implementations so that the
metric modules (field_summary.py, nucleolar_shape.py) and the estimate module
(comparison_estimates.py) can be built and reviewed in parallel. The common-statistics
comparison request accepts them (ComparisonSelection); the descriptive request does
not yet. Definitions are in docs/methods.md, "Group comparison contracts".
"""
from typing import Annotated, Literal, Union

from pydantic import Discriminator, Field, FiniteFloat, Tag, model_validator

from .contracts import StrictModel
from .descriptive_contracts import (
    CompartmentSummaryMetric,
    CompartmentSummarySelection,
    GfpFilter,
    RegionSelection,
    _omit_default,
    _OptionalGate,
)
from .regions import Id, RegionModel

FIELD_SUMMARY_VERSION: Literal["1.0.0"] = "1.0.0"
COMPARTMENT_SUMMARY_SELECTION_V11: Literal["1.1.0"] = "1.1.0"
ESTIMATES_PROTOCOL: Literal["comparison-estimates/1.0.0"] = "comparison-estimates/1.0.0"

FieldSummaryMetric = Literal["nucleus_count", "nucleus_density_per_mm2", "positive_count", "positive_fraction"]
NucleolarSummaryMetric = Literal["nucleolar_area_px", "nucleolar_area_um2", "nucleolar_eccentricity"]


class FieldSummarySelection(StrictModel):
    """One observation per field: nucleus counts and positivity among adopted nuclei.

    Positivity reuses the recorded nucleus gates (negative-control gfp-gate/2.0.0
    or exploratory gfp-gate/3.0.0) with keep="positive"; the gate channel is the
    channel that is judged, whatever its stain.
    """
    source: Literal["field-summary"]
    version: Literal["1.0.0"] = FIELD_SUMMARY_VERSION
    region_set_id: Id
    metric: FieldSummaryMetric
    positivity: GfpFilter | None = Field(default=None, json_schema_extra=_omit_default)

    @model_validator(mode="after")
    def positivity_for_positive_metrics(self):
        positive = self.metric.startswith("positive_")
        if positive != (self.positivity is not None):
            raise ValueError("field_summary_positivity_mismatch")
        if self.positivity is not None and self.positivity.keep != "positive":
            raise ValueError("field_summary_positivity_keep_positive_required")
        return self


class CompartmentSummarySelectionV11(_OptionalGate):
    """Compartment-summary selection 1.1.0: 1.0.0 metrics plus nucleolar total area and shape.

    Like 1.0.0, values describe nuclei with at least one adopted nucleolus; a
    candidate-free nucleus is missing (no_nucleolus), never zero.
    """
    source: Literal["compartment-summary"]
    version: Literal["1.1.0"]
    region_set_id: Id
    channel_id: Id | None = None
    metric: CompartmentSummaryMetric | NucleolarSummaryMetric
    gfp_gate: GfpFilter | None = Field(default=None, json_schema_extra=_omit_default)

    @model_validator(mode="after")
    def channel_for_intensity_ratio_only(self):
        if self.metric == "log2_nucleoplasm_over_nucleolus":
            if self.channel_id is None:
                raise ValueError("compartment_summary_channel_required")
        elif self.channel_id is not None:
            raise ValueError("compartment_summary_channel_must_be_unset")
        return self


def _selection_tag(value):
    get = value.get if isinstance(value, dict) else lambda key, default=None: getattr(value, key, default)
    source = get("source")
    # Historical compartment 1.0.0 selections may omit their defaulted version.
    return f"compartment-summary/{get('version', '1.0.0')}" if source == "compartment-summary" else source


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
