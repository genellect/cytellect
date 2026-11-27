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
# 2026-11-26.1 (genellect/cytellect#284 W7) adds the kind of request (`intent`), the direct answer, the fields a run
# covers (`scope`), the items to confirm (`choices`) and run and group suggestions (`assignments`), and reads context
# 1.3.0. The service keeps answering 2026-11-19.1 (the figure presentation, publication figures plan.md FM-01) and the
# earlier versions of installed clients.
PROPOSAL_PROMPT_VERSION = "2026-11-26.1"
FIGURE_PROMPT_VERSION = "2026-11-19.1"
# Context 1.2.0 (docs/drafts/llm-assistant/plan.md) adds the researcher's channel labels, field names and
# metadata; installed clients up to 0.1.0-local.23 send 1.1.0. Context 1.3.0 (#284 W7) adds, per field, an opaque
# identifier, the folder-relative names the field was added with and its run and group, and the design's run and
# group names; only the prompt that reads it (INTENT_PROMPT_VERSIONS) is sent it.
PROPOSAL_CONTEXT_PROTOCOL = "1.3.0"
LEGACY_CONTEXT_PROTOCOL = "1.2.0"
INTENT_PROMPT_VERSIONS = frozenset({PROPOSAL_PROMPT_VERSION})


def context_protocol(prompt_version: str) -> str:
    """The context a prompt version reads: 1.3.0 for the intent prompt, 1.2.0 for every earlier or unknown one, so an
    operator who pins an earlier prompt (a service not yet updated) sends exactly what that prompt was written for."""
    return PROPOSAL_CONTEXT_PROTOCOL if prompt_version in INTENT_PROMPT_VERSIONS else LEGACY_CONTEXT_PROTOCOL
PROPOSAL_MODEL = "gpt-6.1-sol"
# Models the service may answer with (docs/drafts/llm-assistant/plan.md): the response names the one it used, and
# the workspace stores that name with the draft. A model outside this list is refused as a version mismatch.
PROPOSAL_MODELS = ("gpt-6.1-sol", "claude-opus-5-5", "claude-sonnet-5-5")

Token = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,31}$")]
Stain = Annotated[str, Field(min_length=1, max_length=40)]
# The model's explanation to the researcher; its length is the model's choice (docs/drafts/llm-assistant/plan.md §8).
Prose = Annotated[str, Field(min_length=1)]

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
    # The researcher's name for the channel. It suggests a stain only; a stain is established by `stain`.
    label: Annotated[str, Field(min_length=1, max_length=80)] | None = None


FieldText = Annotated[str, Field(min_length=1, max_length=120)]
# A name a file was added with, relative to the folder the researcher chose (or the file name alone); never absolute.
AddedName = Annotated[str, Field(min_length=1, max_length=255)]
FieldToken = Annotated[str, Field(pattern=r"^f[1-9][0-9]{0,2}$")]
DesignLabel = Annotated[str, Field(min_length=1, max_length=24)]


def _absent(value) -> bool:
    return value is None or value == []


class ContextField(ProposalModel):
    """One image field as the researcher recorded it: its name and metadata. From context 1.3.0 also an opaque
    identifier (`f1`, `f2`…) that assignment suggestions name, the folder-relative names its files were added with, and
    its run and group in the experiment design. Never an absolute path. Absent values are left out of the context, so
    a 1.2.0 context is unchanged."""
    name: FieldText | None = None
    condition: FieldText | None = None
    experimental_unit: FieldText | None = None
    pair: FieldText | None = None
    acquisition_date: FieldText | None = None
    id: FieldToken | None = Field(default=None, exclude_if=_absent)
    paths: Annotated[list[AddedName], Field(max_length=4)] = Field(default_factory=list, exclude_if=_absent)
    run: DesignLabel | None = Field(default=None, exclude_if=_absent)
    group: DesignLabel | None = Field(default=None, exclude_if=_absent)


class ContextDesign(ProposalModel):
    """The experiment design's run and group names (context 1.3.0); no dates, samples or statements."""
    layout: Literal["single", "pair"]
    runs: Annotated[list[DesignLabel], Field(max_length=50)] = Field(default_factory=list)
    groups: Annotated[list[DesignLabel], Field(min_length=1, max_length=2)]


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
    """What the proposal service's model reads: the goal, channels with their labels, the fields with their names
    and recorded metadata, counts and current settings. From 1.3.0 a field also carries the names its files were
    added with, as paths that start at the folder the researcher chose. Locations on the PC above that folder and
    measured values are not part of it; downscaled previews travel next to it."""
    protocol: Literal["1.1.0", "1.2.0", "1.3.0"] = "1.3.0"
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
    fields: list[ContextField] = Field(default_factory=list, max_length=200)
    previous_goal: Annotated[str, Field(max_length=2000)] = ""
    previous_proposal: ProposalDraft | None = None
    design: ContextDesign | None = Field(default=None, exclude_if=_absent)

    @model_validator(mode="after")
    def unique_channels(self):
        if self.protocol != "1.3.0" and (self.design is not None or any(
                field.id or field.paths or field.run or field.group for field in self.fields)):
            # Identifiers, added names and the design are read only by the prompt written for context 1.3.0.
            raise ValueError("proposal_context_protocol_mismatch")
        ids = [field.id for field in self.fields if field.id]
        if len(set(ids)) != len(ids):
            raise ValueError("proposal_context_field_duplicate")
        if self.field_count == 0:
            if (self.channels or self.condition_count or self.units_known or self.pairing_known
                    or self.units_per_condition or self.complete_pair_count or self.supplied_regions
                    or self.measured_table or self.background_available or self.image_metadata or self.fields
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
    reason: Prose


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


class DraftLegendTerms(ProposalModel):
    """Facts of the figure legend the workspace does not record, as the researcher stated them.
    Never values, effects or conclusions (publication figures plan.md FM-01, FL-05)."""
    cell_line: Prose | None
    treatment: Prose | None
    stains: Prose | None


class DraftFigurePresentation(ProposalModel):
    """How the main figure is composed (common-statistics figure 2.0.0); the researcher adopts it."""
    composition: Literal["quantification", "images-quantification"]
    legend_terms: DraftLegendTerms | None


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


class DraftChoice(ProposalModel):
    """An item the researcher decides and the images and records do not (which channel is the nuclear stain, which
    group a field belongs to): a short question and options, each written as the researcher's next message. Lengths
    and counts are checked by validation, so a long option refuses the settings but keeps the answer's text."""
    question: str
    options: list[str]


class DraftAssignment(ProposalModel):
    """A run and group suggestion for one field (`field` is a context field identifier). Shown in the experiment
    table and saved only by the researcher's 「案を適用」; checked against the fields and the design by validation."""
    field: str
    run: str
    group: str


Intent = Literal["answer", "settings", "run"]
Scope = Literal["selected", "all"]
INTENT_FIELDS = ("intent", "answer", "scope", "choices", "assignments")


class ProposalDraft(ProposalModel):
    recipe: RecipeId
    channels: Annotated[list[DraftChannel], Field(max_length=6)]
    metrics: Annotated[list[DraftMetric], Field(max_length=8)]
    statistics: DraftStatistics
    additional_analyses: Annotated[list[DraftStatistics], Field(max_length=3)] = Field(default_factory=list)
    figures: Annotated[list[DraftFigure], Field(max_length=6)]
    missing_information: list[Prose]
    reference_ids: Annotated[list[ReferenceId], Field(max_length=6)]
    rationale: str
    # Old saved drafts and old clients retain their historical meaning.
    processing: DraftProcessing | None = None
    background: DraftBackground | None = None
    gfp_selection: DraftGfpSelection | None = None
    # Prompt 2026-11-19.1 and later; earlier drafts have none.
    figure_presentation: DraftFigurePresentation | None = None
    # Prompt 2026-11-26.1 and later (#284 W7); earlier drafts have none and keep their earlier meaning. `intent` only
    # chooses which actions the workspace shows: an answer never changes a setting or runs anything by itself.
    # Absent values are left out, so an earlier draft (a stored one, or a previous proposal in a context) keeps its bytes.
    intent: Intent | None = Field(default=None, exclude_if=_absent)
    answer: str | None = Field(default=None, exclude_if=_absent)
    scope: Scope | None = Field(default=None, exclude_if=_absent)
    choices: list[DraftChoice] = Field(default_factory=list, exclude_if=_absent)
    assignments: list[DraftAssignment] = Field(default_factory=list, exclude_if=_absent)


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


def draft_json_schema(*, legacy: bool = False, processing_only: bool = False, figure: bool = False,
                      intent: bool = False) -> dict[str, Any]:
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
    if figure or intent:
        schema["properties"]["figure_presentation"] = _nullable(_strict_model_schema(DraftFigurePresentation))
        schema["required"].append("figure_presentation")
    if intent:
        text = {"type": "string"}
        schema["properties"].update({
            "intent": _enum(Intent), "answer": _nullable(text), "scope": _nullable(_enum(Scope)),
            "choices": {"type": "array", "items": _object({"question": text, "options": {"type": "array", "items": text}})},
            "assignments": {"type": "array", "items": _object({"field": text, "run": text, "group": text})},
        })
        schema["required"].extend(INTENT_FIELDS)
    return schema


ProposalContext.model_rebuild()
