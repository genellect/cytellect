"""Reading a model-written result discussion (requirements AC-04–AC-06).

Only the structure is checked: three lists of points, with at least one interpretation. The text is shown
as the model wrote it, without checks of its numbers, wording or references and without notes added to it
(2026-11-17, the owner's decision, docs/drafts/llm-assistant/plan.md §8): rules on the surface of the text
stopped correct, careful sentences and bent the discussion toward generalities. The computed result stays
the only source of values and is never affected by a discussion (AC-01, AC-07).
"""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import ValidationError

from .discussion_contracts import (
    DISCUSSION_PROMPT_VERSION,
    DiscussionContext,
    DiscussionDraft,
    ValidatedDiscussion,
)


class DiscussionRejected(ValueError):
    def __init__(self, codes: list[str]):
        super().__init__(",".join(codes))
        self.codes = codes


def context_sha256(context: DiscussionContext) -> str:
    canonical = json.dumps(context.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_discussion(raw: object, context: DiscussionContext, *, model: str,
                        prompt_version: str = DISCUSSION_PROMPT_VERSION,
                        origin: Literal["model", "example"] = "model") -> ValidatedDiscussion:
    """Read a draft as the three headings; raise `DiscussionRejected` only when it does not have that structure."""
    try:
        draft = raw if isinstance(raw, DiscussionDraft) else DiscussionDraft.model_validate(raw)
    except ValidationError:
        raise DiscussionRejected(["discussion_schema_invalid"]) from None
    return ValidatedDiscussion(context_sha256=context_sha256(context), prompt_version=prompt_version, model=model,
                               origin=origin, draft=draft)
