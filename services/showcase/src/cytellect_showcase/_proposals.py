"""Replay of recorded proposal-service responses; the service is never contacted.

``proposals.json`` in the seed holds the exact payloads the proposal service
returned (``{"model", "prompt_version", "draft"}``), keyed by
``context_sha256`` of the normalized context the API sent. The API still
validates every replayed draft with the same ``validate_draft`` as production.

Entries whose ``source`` is ``showcase-authored`` are drafts written for the demo's
preset instructions (no model was called; the draft depends only on the
instruction). When the exact context was not recorded (the visitor changed a
setting first), such a draft is still returned for the same instruction if it
passes ``validate_draft`` for the current context. Model outputs are only ever
replayed for the exact context they were recorded for.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

NOT_RECORDED = "showcase_proposal_not_recorded"
FORMAT_VERSION = 1
AUTHORED = "showcase-authored"


class Recordings:
    def __init__(self, entries: dict[str, dict]):
        self.entries = entries
        identities = {(payload["model"], payload["prompt_version"]) for payload in entries.values()}
        if len(identities) > 1:
            raise ValueError("showcase_proposals_mixed_model_or_prompt")
        self.identity = next(iter(identities)) if identities else None

    @classmethod
    def load(cls, path: Path) -> "Recordings":
        if not path.is_file():
            return cls({})
        data = json.loads(path.read_text(encoding="utf-8"))
        if data == {}:
            # No genuine recorded outputs: every request is "not recorded".
            return cls({})
        if not isinstance(data, dict) or data.get("version") != FORMAT_VERSION or not isinstance(data.get("entries"), dict):
            raise ValueError("showcase_proposals_invalid")
        entries = {}
        for key, payload in data["entries"].items():
            if (not isinstance(key, str) or re.fullmatch(r"[0-9a-f]{64}", key) is None
                    or not isinstance(payload, dict) or not isinstance(payload.get("model"), str)
                    or not isinstance(payload.get("prompt_version"), str) or not isinstance(payload.get("draft"), dict)):
                raise ValueError("showcase_proposals_invalid")
            entries[key] = payload
        return cls(entries)

    def request_draft(self, settings, context, request_id=None) -> dict:
        """Drop-in for ``cytellect_api.proposals.request_draft``."""
        from cytellect_analysis.proposal_validation import context_sha256
        from cytellect_api.proposals import ProposalServiceError

        payload = self.entries.get(context_sha256(context)) or self._authored(context)
        if payload is None:
            raise ProposalServiceError(409, NOT_RECORDED)
        return copy.deepcopy(payload)

    def _authored(self, context) -> dict | None:
        """The demo-authored draft for this preset instruction, valid for the current context."""
        from cytellect_analysis.proposal_validation import ProposalRejected, validate_draft

        goal = context.goal.strip()
        candidates = [payload for payload in self.entries.values()
                      if payload.get("source") == AUTHORED and isinstance(payload.get("goal"), str)
                      and payload["goal"].strip() == goal]
        # Prefer the recording made after the same previous instruction, then any other.
        candidates.sort(key=lambda payload: payload.get("previous_goal", "") != context.previous_goal)
        for payload in candidates:
            try:
                validate_draft(context, copy.deepcopy(payload["draft"]), model=payload["model"],
                               prompt_version=payload["prompt_version"])
            except ProposalRejected:
                continue
            return payload
        return None
