"""Release compatibility probes: omit Idempotency-Key to stop before admission and any model call."""
from __future__ import annotations

import json
import urllib.request
from urllib.parse import urlsplit


def version_payloads() -> list[dict]:
    """Public protocol sentinels, never workspace data. Validate with the client's actual models."""
    from cytellect_analysis.discussion_contracts import (
        DISCUSSION_PROMPT_VERSION,
        DiscussionContext,
        DiscussionResult,
    )
    from cytellect_analysis.proposal_contracts import PROPOSAL_PROMPT_VERSION, ProposalContext

    proposal = ProposalContext(goal="Release compatibility probe", channels=[], field_count=0)
    discussion = DiscussionContext(result=DiscussionResult(
        metric="area_px", scale="difference", control="probe-control", treatment="probe-treatment",
        design="independent", test="none", n_control=0, n_treatment=0, groups=[]))
    return [{"route": "/v1/proposals", "prompt_version": PROPOSAL_PROMPT_VERSION,
             "context": proposal.model_dump(mode="json")},
            {"route": "/v1/discussions", "prompt_version": DISCUSSION_PROMPT_VERSION,
             "context": discussion.model_dump(mode="json")}]


def check_versions(service: str, token: str, probe) -> list[tuple[str, str, bool, str]]:
    parts = urlsplit(service)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or not token:
        return [("AI service", "", False, "set an HTTPS service URL and device token before release")]
    results = []
    for item in version_payloads():
        route = item["route"]
        body = {key: value for key, value in item.items() if key != "route"}
        request = urllib.request.Request(service.rstrip("/") + route, method="POST",
            data=json.dumps(body).encode(), headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
        # No retries and no Idempotency-Key: accepted versions must stop before claim/count/reserve.
        status, code = probe(request, timeout=30)
        accepted = status == 400 and code == "request_id_required"
        detail = ("accepted; no model call or usage count" if accepted else
                  "prompt version unsupported; deploy the matching Worker before releasing the client"
                  if status == 400 and code == "prompt_version_unsupported" else
                  "client context rejected; deploy the matching Worker before releasing the client"
                  if status == 400 and code == "request_invalid" else
                  f"compatibility not proven (HTTP {status or 'unreachable'}); do not release")
        results.append((route, item["prompt_version"], accepted, detail))
    return results
