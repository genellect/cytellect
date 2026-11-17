"""Result discussion protocol 1.1.0 (requirements AC-01–AC-09, docs/drafts/results-and-demo-story,
docs/drafts/llm-assistant/plan.md).

A language model writes a discussion of one saved two-group comparison: what it may suggest, other
explanations and limits, and what to check next. The computed result stays the only source of values; the
discussion is shown apart from it (AC-01).
`DiscussionContext` is what the model reads: the saved result as the workspace shows it (the summary's
heading and points, the numbers, n and its breakdown, the method), the researcher's own names for groups,
runs, channels and the region, the metric's definition, and the researcher's description of the experiment.
Protocol 1.0.0 (installed clients up to 0.1.0-local.23) sent anonymous run labels and no definitions;
its contexts and stored discussions remain readable.
`DiscussionDraft` is what the model returns: three lists of points. Only its structure is checked; its text
is shown as written (2026-11-17, the owner's decision, docs/drafts/llm-assistant/plan.md §8).
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

Protocol = Literal["result-discussion/1.0.0", "result-discussion/1.1.0"]
DISCUSSION_PROTOCOL: Protocol = "result-discussion/1.1.0"
DISCUSSION_PROMPT_VERSION = "2026-11-16.1"
# The prompt of protocol 1.0.0, still answered by the service for installed clients.
DISCUSSION_LEGACY_PROMPT_VERSION = "2026-11-12.2"

Label = Annotated[str, Field(min_length=1, max_length=80)]
Note = Annotated[str, Field(min_length=1, max_length=500)]
# The researcher's own description of the experiment, as long as the goal of an analysis proposal.
Purpose = Annotated[str, Field(min_length=1, max_length=2000)]
# A recorded method setting or the researcher's description of the design.
Setting = Annotated[str, Field(min_length=1, max_length=300)]
# One point of the discussion, with its reasoning; its length is the model's choice.
Item = Annotated[str, Field(min_length=1)]
WarningCode = Annotated[str, Field(pattern=r"^[a-z0-9_]{1,120}$")]


class DiscussionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ExperimentNote(DiscussionModel):
    """What the researcher wrote about the experiment (by default, the goal of the analysis proposal)."""
    purpose: Purpose | None = None
    cells: Label | None = None
    stains: list[Label] = Field(default_factory=list, max_length=8)


class Interval(DiscussionModel):
    estimate: FiniteFloat
    ci_low: FiniteFloat
    ci_high: FiniteFloat


class GroupValue(DiscussionModel):
    condition: Label
    mean: FiniteFloat | None


class RunValue(DiscussionModel):
    run: Label
    control: FiniteFloat
    treatment: FiniteFloat
    difference: FiniteFloat
    ratio: FiniteFloat | None = None


class GroupCount(DiscussionModel):
    """The n breakdown of one group, as the result's 「n の内訳と除外」 states it."""
    condition: Label
    observations: Annotated[int, Field(ge=0)] | None = None
    input_fields: Annotated[int, Field(ge=0)] | None = None
    selected_fields: Annotated[int, Field(ge=0)] | None = None
    samples: Annotated[int, Field(ge=0)] | None = None
    experimental_units: Annotated[int, Field(ge=0)] | None = None
    explicitly_excluded_units: Annotated[int, Field(ge=0)] | None = None
    complete_pairs: Annotated[int, Field(ge=0)] | None = None


class DiscussionMethod(DiscussionModel):
    """How the values were aggregated and tested, as the result records it, and the design the researcher declared."""
    comparison: Setting | None = None
    aggregation: Setting | None = None
    correction: Setting | None = None
    alternative: Setting | None = None
    confidence_level: Annotated[float, Field(gt=0, lt=1)] | None = None
    inferential_unit: Setting | None = None
    p_value_method: Setting | None = None
    test_selection: Setting | None = None
    unit_definition: Setting | None = None
    pairing_basis: Setting | None = None
    acquisition_basis: Setting | None = None


class DiscussionResult(DiscussionModel):
    """One saved comparison, as the result summary states it (RS-01–RS-04); every number is saved."""
    metric: Label
    # What the metric is, in the words the workspace shows (for example 「判定可能な核の陽性率」), and its
    # recorded definition (denominator, region, protocol) when the analysis records one.
    metric_label: Label | None = None
    metric_definition: Note | None = None
    region: Label | None = None
    # The researcher's name for the region set (for example 「細胞の内側」).
    region_label: Label | None = None
    stain: Label | None = None
    # The researcher's name for the measured channel.
    channel_label: Label | None = None
    # The analysis package's unit; never a reason to refuse a discussion.
    unit: Annotated[str, Field(max_length=120)] = ""
    scale: Literal["difference", "ratio", "fraction", "log2"]
    control: Label
    treatment: Label
    design: Literal["independent", "paired"]
    # "none": descriptive only (independence not confirmed or an exploratory threshold): no test, no interval.
    test: Literal["welch-t", "paired-t", "mann-whitney-u", "wilcoxon", "none"]
    exploratory_threshold: bool = False
    n_control: Annotated[int, Field(ge=0)]
    n_treatment: Annotated[int, Field(ge=0)]
    n_runs: Annotated[int, Field(ge=0)] | None = None
    p_value: Annotated[float, Field(ge=0, le=1)] | None = None
    effect: FiniteFloat | None = None
    groups: list[GroupValue] = Field(max_length=2)
    difference: Interval | None = None
    ratio: Interval | None = None
    runs: list[RunValue] = Field(default_factory=list, max_length=12)
    # The saved result's warning codes (fixed identifiers such as `few_independent_units_…`), never prose.
    warnings: list[WarningCode] = Field(default_factory=list, max_length=16)
    # The summary as the workspace shows it above the result: the heading (the conclusion in one line) and its
    # points, so that the discussion reads the result the way the researcher does.
    heading: Annotated[str, Field(min_length=1, max_length=500)] | None = None
    summary_points: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(default_factory=list, max_length=8)
    counts: list[GroupCount] = Field(default_factory=list, max_length=2)
    method: DiscussionMethod | None = None


class DiscussionContext(DiscussionModel):
    protocol: Protocol = DISCUSSION_PROTOCOL
    language: Literal["ja"] = "ja"
    experiment: ExperimentNote = Field(default_factory=ExperimentNote)
    result: DiscussionResult


class DiscussionDraft(DiscussionModel):
    """The three headings of the discussion (AC-04). How many points and how long is the model's choice; a draft
    with no interpretation at all is not a discussion."""
    protocol: Protocol = DISCUSSION_PROTOCOL
    implications: list[Item] = Field(min_length=1)
    alternatives: list[Item] = Field(default_factory=list)
    next_steps: list[Item] = Field(default_factory=list)


class ValidatedDiscussion(DiscussionModel):
    protocol: Protocol = DISCUSSION_PROTOCOL
    # "example": written for the public demo, not by a model, and shown as such (AC-08).
    origin: Literal["model", "example"] = "model"
    context_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    prompt_version: str = DISCUSSION_PROMPT_VERSION
    model: Annotated[str, Field(min_length=1, max_length=80)]
    draft: DiscussionDraft


def draft_json_schema() -> dict[str, Any]:
    """The strict Structured Outputs schema given to the model: the three headings as lists of sentences.

    Every key is required and nothing else is allowed (strict mode). Item counts and lengths are the model's choice.
    """
    sentences = {"type": "array", "items": {"type": "string"}}
    return {"type": "object", "additionalProperties": False, "required": ["implications", "alternatives", "next_steps"],
            "properties": {"implications": sentences, "alternatives": sentences, "next_steps": sentences}}
