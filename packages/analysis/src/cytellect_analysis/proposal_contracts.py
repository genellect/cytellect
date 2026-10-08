"""Analysis proposal protocol 1.0.0 (workspace redesign L01–L06).

The language model only drafts a combination of registered recipes, metrics,
statistics and figures. It never produces measurements, masks or p-values.
`ProposalContext` is what leaves the PC; `ProposalDraft` is what the model may
return. Both are validated locally before anything is shown or adopted.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, StrictBool, model_validator

from .cellpose_engine import CellposeDetectorSpec, NclCellposeDetectorSpec, NclParentCellposeDetectorSpec
from .compartment_engine import NucleolarDetectorV11
from .ncl_objects import NclObjectDetector
from .nucleolar_detector_v2 import NucleolarDetectorV20, NucleolarDetectorV21
from .planning import ReferenceId
from .region_contracts import NuclearDetectorSpec
from .signal_engine import SignalDetectorSpec

PROPOSAL_PROTOCOL = "1.1.0"
PROPOSAL_PROMPT_VERSION = "2026-10-08.5"
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
RegionId = Literal["nucleus", "nucleoli", "nucleoplasm", "supplied"]

INTENSITY_METRICS = frozenset({"mean_raw", "integral_raw", "mean_corrected", "integral_corrected"})
NCL_METRICS = frozenset({"ncl_log2_nucleoplasm_over_nucleoli", "nucleolar_area_fraction", "nucleolar_count"})


class ProposalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ContextChannel(ProposalModel):
    token: Token
    stain: Stain | None = None
    role: Literal["nuclear", "measure", "unused"] | None = None


class DraftBackground(ProposalModel):
    mode: Literal["raw", "automatic", "confirmed_roi"]


class DraftGfpSelection(ProposalModel):
    channel: Token
    unit: Literal["nucleus", "cell_roi"] = "nucleus"
    method: Literal["manual", "batch_otsu", "negative_control"]
    threshold: FiniteFloat | None = None
    values: Literal["raw", "corrected"] = "raw"
    keep: Literal["positive", "negative"] = "positive"
    percentile: Annotated[FiniteFloat, Field(ge=50, lt=100)] = 99.0

    @model_validator(mode="after")
    def explicit_threshold(self):
        if (self.method == "manual") != (self.threshold is not None):
            raise ValueError("proposal_gfp_threshold_invalid")
        if self.method == "negative_control" and self.values != "raw":
            raise ValueError("proposal_control_gate_uses_raw_values")
        return self


class ContextImage(ProposalModel):
    width: Annotated[int, Field(ge=1, le=4096)]
    height: Annotated[int, Field(ge=1, le=4096)]
    axes: Literal["YX"] = "YX"
    input_mode: Literal["native", "display-rgb"]
    pixel_size_x_um: Annotated[FiniteFloat, Field(gt=0)] | None = None
    pixel_size_y_um: Annotated[FiniteFloat, Field(gt=0)] | None = None


class ProposalContext(ProposalModel):
    """Normalized metadata sent to the proposal service; no paths, names or values."""
    protocol: Literal["1.1.0"] = "1.1.0"
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
    current_processing: DraftProcessing | None = None
    current_background: DraftBackground | None = None
    current_gfp: DraftGfpSelection | None = None
    negative_control_fields_known: StrictBool = False
    acquired_dates_known: StrictBool = False
    image_metadata: list[ContextImage] = Field(default_factory=list, max_length=8)
    previous_goal: Annotated[str, Field(max_length=2000)] = ""
    previous_proposal: ProposalDraft | None = None

    @model_validator(mode="after")
    def unique_channels(self):
        if self.field_count == 0:
            if (self.channels or self.condition_count or self.units_known or self.pairing_known
                    or self.units_per_condition or self.complete_pair_count or self.supplied_regions
                    or self.measured_table or self.background_available or self.image_metadata or not self.goal.strip()):
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


class DraftNuclearProcessing(ProposalModel):
    channel: Token
    detection_max_side_px: Annotated[int, Field(strict=True, ge=64, le=2048)] | None = None
    detector: NuclearDetectorSpec = Field(default_factory=NuclearDetectorSpec)


class DraftNucleolarProcessing(ProposalModel):
    channel: Token
    detector: NucleolarDetectorV11 | NucleolarDetectorV20 | NucleolarDetectorV21 | NclObjectDetector | CellposeDetectorSpec | NclCellposeDetectorSpec | NclParentCellposeDetectorSpec


class DraftCellProcessing(ProposalModel):
    channel: Token
    detector: CellposeDetectorSpec = Field(default_factory=CellposeDetectorSpec)


class DraftSignalProcessing(ProposalModel):
    channel: Token
    detector: SignalDetectorSpec


class DraftProcessing(ProposalModel):
    """Registered execution settings only; not code, masks or biological confirmations."""
    version: Literal["1.0.0"] = "1.0.0"
    nuclei: DraftNuclearProcessing | None
    nucleoli: DraftNucleolarProcessing | None
    signal: DraftSignalProcessing | None
    cells: DraftCellProcessing | None = None


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
    # Old saved drafts and old clients retain their historical meaning.
    processing: DraftProcessing | None = None
    background: DraftBackground | None = None
    gfp_selection: DraftGfpSelection | None = None


class ValidatedProposal(ProposalModel):
    protocol: Literal["1.1.0"] = "1.1.0"
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


def _strict_model_schema(model) -> dict[str, Any]:
    schema = model.model_json_schema()
    definitions = schema.get("$defs", {})

    def convert(value):
        if "$ref" in value:
            return convert(definitions[value["$ref"].split("/")[-1]])
        if "anyOf" in value:
            return {"anyOf": [convert(branch) for branch in value["anyOf"]]}
        if value.get("type") == "object":
            return _object({key: convert(prop) for key, prop in value["properties"].items()})
        if "const" in value:
            return {"type": value["type"], "enum": [value["const"]]}
        return {key: value[key] for key in ("type", "enum") if key in value}

    return convert(schema)


def draft_json_schema(*, legacy: bool = False, processing_only: bool = False) -> dict[str, Any]:
    """Strict Structured Outputs schema for ProposalDraft.

    Length and pattern limits are enforced by local validation; the strict
    schema carries only shape, required keys and enumerations.
    """
    token = {"type": "string"}
    metric = _object({"metric": _enum(MetricId), "channel": _nullable(token), "region": _nullable(_enum(RegionId))})
    statistics = _object({"kind": {"type": "string", "enum": ["descriptive", "comparison", "association"]},
                          "test": _nullable(_enum(TestId)), "omnibus": _nullable(_enum(OmnibusId)),
                          "association": _nullable(_enum(AssociationId)), "x": _nullable(metric), "y": _nullable(metric)})
    schema = _object({
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
    })
    if not legacy:
        schema["properties"]["processing"] = _nullable(_strict_model_schema(DraftProcessing))
        schema["required"].append("processing")
        if not processing_only:
            schema["properties"]["background"] = _nullable(_strict_model_schema(DraftBackground))
            schema["properties"]["gfp_selection"] = _nullable(_strict_model_schema(DraftGfpSelection))
            schema["required"].extend(["background", "gfp_selection"])
    return schema


ProposalContext.model_rebuild()
