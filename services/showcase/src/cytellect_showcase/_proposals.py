"""Replay of recorded proposal-service responses; the service is never contacted.

``proposals.json`` in the seed holds the exact payloads the proposal service
returned (``{"model", "prompt_version", "draft"}``), keyed by
``context_sha256`` of the normalized context the API sent. The API still
validates every replayed draft with the same ``validate_draft`` as production.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

NOT_RECORDED = "showcase_proposal_not_recorded"
FORMAT_VERSION = 1


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

        payload = self.entries.get(context_sha256(context))
        if payload is None:
            raise ProposalServiceError(409, NOT_RECORDED)
        return copy.deepcopy(payload)
