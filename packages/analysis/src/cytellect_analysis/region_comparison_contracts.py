"""Explicit experimental design for source-bound generic-region comparisons."""
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator, model_validator

from .contracts import PlotSpec
from .descriptive_contracts import RegionSelection
from .regions import Id, RegionModel

Text = Annotated[str, Field(min_length=1, max_length=200)]
Condition = Annotated[str, Field(min_length=1, max_length=80)]


class ComparisonDesign(RegionModel):
    kind: Literal["independent", "paired"]
    confirmed: Literal[True]
    unit_definition: Text
    pairing_basis: Text | None = None

    @model_validator(mode="after")
    def declared_pairing(self):
        if (self.kind == "paired") != (self.pairing_basis is not None):
            raise ValueError("region_comparison_pairing_basis_required")
        return self


class AcquisitionReview(RegionModel):
    confirmed: Literal[True]
    basis: Literal["same-settings", "calibrated-area"]
    # Actual acquisition batches; omitted entries use recorded acquisition_date.
    # No generated IDs or dates are used to manufacture acquisition knowledge.
    field_batches: dict[Id, Condition] = Field(default_factory=dict)
    spatial_sampling_confirmed: bool = False


class ComparisonFamily(RegionModel):
    family_id: Id
    kind: Literal["control", "planned"]
    control: Condition | None = None
    contrasts: Annotated[list[Annotated[list[Condition], Field(min_length=2, max_length=2)]],
                         Field(min_length=1, max_length=100)]

    @model_validator(mode="after")
    def declared_family(self):
        if ((self.kind == "control") != (self.control is not None)
                or any(a == b for a, b in self.contrasts)
                or len({frozenset(pair) for pair in self.contrasts}) != len(self.contrasts)):
            raise ValueError("region_comparison_invalid_family")
        if self.control is not None and any(self.control not in pair for pair in self.contrasts):
            raise ValueError("region_comparison_invalid_family")
        return self


class RegionComparisonPlot(PlotSpec):
    kind: Literal["distribution", "paired"] = "distribution"


class RegionComparisonRequest(RegionModel):
    mode: Literal["region-experimental-unit"]
    version: Literal["1.0.0"] = "1.0.0"
    selection: RegionSelection
    design: ComparisonDesign
    conditions: Annotated[list[Condition], Field(min_length=2, max_length=30)]
    comparison_family: ComparisonFamily
    acquisition_review: AcquisitionReview
    missingness_confirmed: Literal[True]
    aggregation: Literal["field-median_sample-mean_unit-mean-v1"] = "field-median_sample-mean_unit-mean-v1"
    missingness_policy: Literal["available-observations_require-unexcluded-units-v1"] = "available-observations_require-unexcluded-units-v1"
    plot: RegionComparisonPlot = Field(default_factory=RegionComparisonPlot)

    @field_validator("missingness_confirmed", mode="before")
    @classmethod
    def genuine_confirmation(cls, value):
        if type(value) is not bool or value is not True:
            raise ValueError("explicit_confirmation_required")
        return value

    @model_validator(mode="after")
    def explicit_scope(self):
        if (len(self.conditions) != len(set(self.conditions))
                or set(self.conditions) != {group for pair in self.comparison_family.contrasts for group in pair}):
            raise ValueError("region_comparison_condition_scope_mismatch")
        if self.plot.kind == "paired" and self.design.kind != "paired":
            raise ValueError("paired_plot_requires_paired_inference")
        if self.plot.group_order and (len(set(self.plot.group_order)) != len(self.plot.group_order)
                                     or set(self.plot.group_order) != set(self.conditions)):
            raise ValueError("group_order_must_match_groups")
        text = [*self.conditions, self.design.unit_definition, *self.acquisition_review.field_batches.values()]
        if self.design.pairing_basis is not None:
            text.append(self.design.pairing_basis)
        if any(not value.strip() or any(ord(char) < 32 for char in value) for value in text):
            raise ValueError("region_comparison_invalid_text")
        return self


class RegionComparisonResult(RegionModel):
    analysis_kind: Literal["region-comparison"] = "region-comparison"
    source_kind: Literal["region-2d"] = "region-2d"
    region_comparison_version: Literal["1.0.0"] = "1.0.0"
    inference_version: str
    revision_id: str
    source_fingerprint: str
    spec: RegionComparisonRequest
    metric: str
    unit: str
    region: dict[str, Any]
    channel: dict[str, Any] | None
    source_fields: list[dict[str, Any]]
    source_field_ledger: list[dict[str, Any]]
    observation_ledger: list[dict[str, Any]]
    plot_data: list[dict[str, Any]]
    field_summary: list[dict[str, Any]]
    sample_summary: list[dict[str, Any]]
    unit_summary: list[dict[str, Any]]
    unit_ledger: list[dict[str, Any]]
    pair_ledger: list[dict[str, Any]]
    counts: list[dict[str, Any]]
    selection: dict[str, Any]
    missingness: list[dict[str, Any]]
    excluded_failed_fields: list[dict[str, Any]]
    acquisition: dict[str, Any]
    comparisons: list[dict[str, Any]]
    means: list[dict[str, Any]]
    warnings: list[str]
