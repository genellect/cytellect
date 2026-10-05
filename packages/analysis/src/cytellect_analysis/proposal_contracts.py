"""Analysis proposal protocol 1.0.0 (workspace redesign L01–L06).

The language model only drafts a combination of registered recipes, metrics,
statistics and figures. It never produces measurements, masks or p-values.
`ProposalContext` is what leaves the PC; `ProposalDraft` is what the model may
return. Both are validated locally before anything is shown or adopted.
"""
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from .planning import ReferenceId

PROPOSAL_PROTOCOL = "1.0.0"

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
    protocol: Literal["1.0.0"] = "1.0.0"
    goal: Annotated[str, Field(max_length=2000)] = ""
    channels: Annotated[list[ContextChannel], Field(min_length=1, max_length=6)]
    field_count: Annotated[int, Field(ge=1, le=10000)]
    condition_count: Annotated[int, Field(ge=0, le=100)] = 0
    units_known: StrictBool = False
    pairing_known: StrictBool = False
    supplied_regions: StrictBool = False
    measured_table: StrictBool = False
    background_available: StrictBool = False


class DraftChannel(ProposalModel):
    token: Token
    stain: Stain | None
    role: Role
    reason: ShortText


class DraftMetric(ProposalModel):
    metric: MetricId
    channel: Token | None


class DraftStatistics(ProposalModel):
    kind: Literal["descriptive", "comparison", "association"]
    test: TestId | None
    omnibus: OmnibusId | None
    association: AssociationId | None


class DraftFigure(ProposalModel):
    kind: FigureKind
    metric: MetricId
    channel: Token | None


class ProposalDraft(ProposalModel):
    recipe: RecipeId
    channels: Annotated[list[DraftChannel], Field(max_length=6)]
    metrics: Annotated[list[DraftMetric], Field(max_length=8)]
    statistics: DraftStatistics
    figures: Annotated[list[DraftFigure], Field(max_length=6)]
    missing_information: Annotated[list[ShortText], Field(max_length=6)]
    reference_ids: Annotated[list[ReferenceId], Field(max_length=6)]
    rationale: Annotated[str, Field(max_length=600)]


class ValidatedProposal(ProposalModel):
    protocol: Literal["1.0.0"] = "1.0.0"
    origin: Literal["llm-draft"] = "llm-draft"
    requires_adoption: Literal[True] = True
    draft: ProposalDraft
    # Tokens whose role the model suggested although the stain is not established.
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
    return _object({
        "recipe": _enum(RecipeId),
        "channels": {"type": "array", "items": _object({
            "token": token, "stain": _nullable({"type": "string"}), "role": _enum(Role), "reason": {"type": "string"}})},
        "metrics": {"type": "array", "items": _object({"metric": _enum(MetricId), "channel": _nullable(token)})},
        "statistics": _object({"kind": {"type": "string", "enum": ["descriptive", "comparison", "association"]},
                               "test": _nullable(_enum(TestId)), "omnibus": _nullable(_enum(OmnibusId)),
                               "association": _nullable(_enum(AssociationId))}),
        "figures": {"type": "array", "items": _object({"kind": _enum(FigureKind), "metric": _enum(MetricId),
                                                       "channel": _nullable(token)})},
        "missing_information": {"type": "array", "items": {"type": "string"}},
        "reference_ids": {"type": "array", "items": _enum(ReferenceId)},
        "rationale": {"type": "string"},
    })
