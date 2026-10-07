"""Analysis proposal protocol 1.2.0 (workspace redesign L01–L06).

The language model only drafts a combination of registered recipes, metrics,
statistics, figures and the method card's processing options. It never produces
measurements, masks, thresholds or p-values.

Protocol 1.2.0 adds the required `processing` object. Drafts and contexts of
protocol 1.1.0 are rejected, not mapped: a 1.1.0 draft has no processing
choices, and filling them in locally would present invented settings as the
model's proposal. Old cached drafts are never reused because the protocol is
part of the local cache key.
`ProposalContext` is what leaves the PC; `ProposalDraft` is what the model may
return. Both are validated locally before anything is shown or adopted.
"""
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from .planning import ReferenceId

PROPOSAL_PROTOCOL = "1.2.0"
PROPOSAL_PROMPT_VERSION = "2026-10-07.1"
PROPOSAL_MODEL = "gpt-6.1-sol"

Token = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,31}$")]
Stain = Annotated[str, Field(min_length=1, max_length=40)]
ShortText = Annotated[str, Field(min_length=1, max_length=200)]

RecipeId = Literal["nuclear-intensity", "nuclear-ncl", "supplied-regions", "measured-table", "none"]
Role = Literal["nuclear", "measure", "unused"]
MetricId = Literal["area", "mean_raw", "integral_raw", "mean_corrected", "integral_corrected",
                   "ncl_log2_nucleoplasm_over_nucleoli", "nucleolar_area_fraction", "nucleolar_count"]
TestId = Literal["welch-t", "paired-t", "mann-whitney-u", "wilcoxon"]
OmnibusId = Literal["welch-anova", "kruskal-wallis"]
AssociationId = Literal["pearson", "spearman"]
FigureKind = Literal["field-distribution", "unit-comparison", "paired", "association-scatter"]
RegionId = Literal["nucleus", "nucleoli", "nucleoplasm", "supplied", "positive"]
# Method-card processing options (workspace redesign; recipes 1.3.0/1.4.0/1.5.0/1.7.0).
MeasureId = Literal["nuclear", "positive", "nucleolar", "drawn"]
DetectionMaxSide = Literal[256, 320, 640, 1024, 1643, 2048]
ThresholdMethod = Literal["otsu", "manual"]
NucleolarSourceId = Literal["dapi_poor", "marker", "ncl"]
BackgroundMode = Literal["raw", "automatic"]
# Which processing measure each registered image recipe allows.
MEASURES_BY_RECIPE: dict[str, frozenset[str]] = {
    "nuclear-intensity": frozenset({"nuclear", "positive"}),
    "nuclear-ncl": frozenset({"nucleolar"}),
    "supplied-regions": frozenset({"drawn"}),
}

INTENSITY_METRICS = frozenset({"mean_raw", "integral_raw", "mean_corrected", "integral_corrected"})
NCL_METRICS = frozenset({"ncl_log2_nucleoplasm_over_nucleoli", "nucleolar_area_fraction", "nucleolar_count"})


class ProposalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ContextChannel(ProposalModel):
    token: Token
    stain: Stain | None = None
    role: Literal["nuclear", "measure"] | None = None


class ProposalContext(ProposalModel):
    """Normalized metadata sent to the proposal service; no paths, names or values."""
    protocol: Literal["1.2.0"] = "1.2.0"
    # Follow-up turns are composed into this one field by the client
    # (previous instructions plus the new one); there is no other free text.
    goal: Annotated[str, Field(max_length=2000)] = ""
    channels: Annotated[list[ContextChannel], Field(min_length=0, max_length=6)]
    field_count: Annotated[int, Field(ge=0, le=10000)]
    condition_count: Annotated[int, Field(ge=0, le=100)] = 0
    units_known: StrictBool = False
    pairing_known: StrictBool = False
    units_per_condition: Annotated[list[Annotated[int, Field(ge=0, le=10000)]], Field(max_length=100)] = Field(default_factory=list)
    complete_pair_count: Annotated[int, Field(ge=0, le=10000)] = 0
    supplied_regions: StrictBool = False
    measured_table: StrictBool = False
    background_available: StrictBool = False
    # Largest image side over all fields, for choosing a detection size; no other image facts.
    image_long_side_px: Annotated[int, Field(ge=1, le=100000)] | None = None

    @model_validator(mode="after")
    def unique_channels(self):
        if self.field_count == 0:
            if (self.channels or self.condition_count or self.units_known or self.pairing_known
                    or self.units_per_condition or self.complete_pair_count or self.supplied_regions
                    or self.measured_table or self.background_available or self.image_long_side_px is not None
                    or not self.goal.strip()):
                raise ValueError("proposal_empty_workspace_facts_invalid")
        elif not self.channels:
            raise ValueError("proposal_acquired_channels_required")
        if len({channel.token for channel in self.channels}) != len(self.channels):
            raise ValueError("proposal_context_channel_duplicate")
        if self.units_per_condition and len(self.units_per_condition) != self.condition_count:
            raise ValueError("proposal_context_unit_count_mismatch")
        return self


class DraftChannel(ProposalModel):
    token: Token
    stain: Stain | None
    role: Role
    reason: ShortText


class DraftMetric(ProposalModel):
    metric: MetricId
    channel: Token | None
    region: RegionId | None = None


class DraftStatistics(ProposalModel):
    kind: Literal["descriptive", "comparison", "association"]
    test: TestId | None
    omnibus: OmnibusId | None
    association: AssociationId | None
    x: DraftMetric | None = None
    y: DraftMetric | None = None


class DraftFigure(ProposalModel):
    kind: FigureKind
    metric: MetricId
    channel: Token | None
    region: RegionId | None = None
    analysis_index: Annotated[int, Field(ge=0, le=3)] = 0


class DraftPositive(ProposalModel):
    channel: Token
    # A manual value is entered by the researcher; the model never supplies a number.
    threshold: ThresholdMethod


class DraftNucleolarSource(ProposalModel):
    source: NucleolarSourceId
    marker_channel: Token | None


class DraftGfpGate(ProposalModel):
    channel: Token


class DraftProcessingReasons(ProposalModel):
    nuclei: ShortText | None
    measure: ShortText | None
    positive: ShortText | None
    nucleolar: ShortText | None
    background: ShortText | None
    gfp: ShortText | None


class DraftProcessing(ProposalModel):
    """Method-card settings the researcher can change at every step."""
    measure: MeasureId
    # None means automatic sizing (recipe 1.7.0, nuclear-size/1.0.0).
    nuclear_detection_max_side: DetectionMaxSide | None
    positive: DraftPositive | None
    nucleolar_source: DraftNucleolarSource | None
    background: BackgroundMode
    gfp_gate: DraftGfpGate | None
    reasons: DraftProcessingReasons


class ProposalDraft(ProposalModel):
    recipe: RecipeId
    channels: Annotated[list[DraftChannel], Field(max_length=6)]
    metrics: Annotated[list[DraftMetric], Field(max_length=8)]
    statistics: DraftStatistics
    additional_analyses: Annotated[list[DraftStatistics], Field(max_length=3)] = Field(default_factory=list)
    figures: Annotated[list[DraftFigure], Field(max_length=6)]
    missing_information: Annotated[list[ShortText], Field(max_length=6)]
    reference_ids: Annotated[list[ReferenceId], Field(max_length=6)]
    rationale: Annotated[str, Field(max_length=600)]
    # Required key; null only for recipes without image processing (none, measured-table).
    processing: DraftProcessing | None


class ValidatedProposal(ProposalModel):
    protocol: Literal["1.2.0"] = "1.2.0"
    origin: Literal["llm-draft"] = "llm-draft"
    requires_adoption: Literal[True] = True
    draft: ProposalDraft
    # Tokens whose role (nuclear) or marker identity the model suggested although
    # the stain is not established; never auto-applied.
    needs_confirmation: list[Token]
    model: Annotated[str, Field(max_length=100)]
    prompt_version: Annotated[str, Field(max_length=40)]
    context_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def _enum(values: Any) -> dict[str, Any]:
    return {"type": "string", "enum": list(values.__args__)}


def draft_json_schema() -> dict[str, Any]:
    """Strict Structured Outputs schema for ProposalDraft.

    Length and pattern limits are enforced by local validation; the strict
    schema carries only shape, required keys and enumerations.
    """
    token = {"type": "string"}
    metric = _object({"metric": _enum(MetricId), "channel": _nullable(token), "region": _nullable(_enum(RegionId))})
    statistics = _object({"kind": {"type": "string", "enum": ["descriptive", "comparison", "association"]},
                          "test": _nullable(_enum(TestId)), "omnibus": _nullable(_enum(OmnibusId)),
                          "association": _nullable(_enum(AssociationId)), "x": _nullable(metric), "y": _nullable(metric)})
    return _object({
        "recipe": _enum(RecipeId),
        "channels": {"type": "array", "items": _object({
            "token": token, "stain": _nullable({"type": "string"}), "role": _enum(Role), "reason": {"type": "string"}})},
        "metrics": {"type": "array", "items": metric},
        "statistics": statistics,
        "additional_analyses": {"type": "array", "items": statistics},
        "figures": {"type": "array", "items": _object({"kind": _enum(FigureKind), "metric": _enum(MetricId),
                                                       "channel": _nullable(token), "region": _nullable(_enum(RegionId)),
                                                       "analysis_index": {"type": "integer"}})},
        "missing_information": {"type": "array", "items": {"type": "string"}},
        "reference_ids": {"type": "array", "items": _enum(ReferenceId)},
        "rationale": {"type": "string"},
        "processing": _nullable(_object({
            "measure": _enum(MeasureId),
            "nuclear_detection_max_side": _nullable({"type": "integer", "enum": list(DetectionMaxSide.__args__)}),
            "positive": _nullable(_object({"channel": token, "threshold": _enum(ThresholdMethod)})),
            "nucleolar_source": _nullable(_object({"source": _enum(NucleolarSourceId), "marker_channel": _nullable(token)})),
            "background": _enum(BackgroundMode),
            "gfp_gate": _nullable(_object({"channel": token})),
            "reasons": _object({key: _nullable({"type": "string"}) for key in DraftProcessingReasons.model_fields}),
        })),
    })
