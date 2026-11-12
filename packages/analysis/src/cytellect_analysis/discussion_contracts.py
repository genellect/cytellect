"""Result discussion protocol 1.0.0 (requirements AC-01–AC-09, docs/drafts/results-and-demo-story).

A language model drafts a short discussion of one saved two-group comparison: what it may suggest,
other explanations and limits, and what to check next. It never produces values, significance or
references. `DiscussionContext` is all that leaves the PC: the saved result's numbers and labels and
the researcher's short description of the experiment, never images, file names or paths (AC-03).
`DiscussionDraft` is what the model may return; it is checked by `discussion_validation` before it is
shown, and shown apart from the computed result (AC-01).
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

DISCUSSION_PROTOCOL: Literal["result-discussion/1.0.0"] = "result-discussion/1.0.0"
DISCUSSION_PROMPT_VERSION = "2026-11-12.2"

Label = Annotated[str, Field(min_length=1, max_length=80)]
Note = Annotated[str, Field(min_length=1, max_length=500)]
Item = Annotated[str, Field(min_length=1, max_length=200)]
WarningCode = Annotated[str, Field(pattern=r"^[a-z0-9_]{1,120}$")]


class DiscussionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ExperimentNote(DiscussionModel):
    """What the researcher wrote about the experiment; optional, short, and never a file or path."""
    purpose: Note | None = None
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


class DiscussionResult(DiscussionModel):
    """One saved comparison, as the result summary states it (RS-01–RS-04); every number is saved."""
    metric: Label
    region: Label | None = None
    stain: Label | None = None
    unit: Annotated[str, Field(max_length=20)] = ""
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
    # The result's heading as the summary shows it. The API leaves it out: it never forwards text from the
    # browser as part of the result, because every number in it would become a number the draft may state.
    heading: Annotated[str, Field(min_length=1, max_length=200)] | None = None


class DiscussionContext(DiscussionModel):
    protocol: Literal["result-discussion/1.0.0"] = DISCUSSION_PROTOCOL
    language: Literal["ja"] = "ja"
    experiment: ExperimentNote = Field(default_factory=ExperimentNote)
    result: DiscussionResult


class DiscussionDraft(DiscussionModel):
    """The three headings of the discussion (AC-04), one sentence per item."""
    protocol: Literal["result-discussion/1.0.0"] = DISCUSSION_PROTOCOL
    implications: list[Item] = Field(min_length=1, max_length=3)
    alternatives: list[Item] = Field(default_factory=list, max_length=2)
    next_steps: list[Item] = Field(default_factory=list, max_length=3)


class ValidatedDiscussion(DiscussionModel):
    protocol: Literal["result-discussion/1.0.0"] = DISCUSSION_PROTOCOL
    # "example": written for the public demo, not by a model, and shown as such (AC-08). It passes the same checks.
    origin: Literal["model", "example"] = "model"
    context_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    prompt_version: str = DISCUSSION_PROMPT_VERSION
    model: Annotated[str, Field(min_length=1, max_length=80)]
    draft: DiscussionDraft


def draft_json_schema() -> dict[str, Any]:
    """The strict Structured Outputs schema given to the model: the three headings as lists of sentences.

    Every key is required and nothing else is allowed (strict mode). Item counts and lengths are checked by
    `DiscussionDraft` and `discussion_validation` after the answer, as for analysis proposals.
    """
    sentences = {"type": "array", "items": {"type": "string"}}
    return {"type": "object", "additionalProperties": False, "required": ["implications", "alternatives", "next_steps"],
            "properties": {"implications": sentences, "alternatives": sentences, "next_steps": sentences}}
