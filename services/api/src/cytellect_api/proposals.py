"""Optional analysis proposal drafts through the Cytellect proposal service.

Disabled unless an operator configures the service URL and this installation's
device credential. Only normalized metadata leaves the PC; the service calls
the language model and returns a draft that is validated here before use.
Registered-recipe analysis never depends on this route.
"""
import json
import urllib.error
import urllib.request
from collections import OrderedDict
from typing import Annotated
from urllib.parse import urlsplit

from cytellect_analysis.proposal_contracts import ProposalContext, ValidatedProposal
from cytellect_analysis.proposal_validation import ProposalRejected, context_sha256, validate_draft
from fastapi import Depends, HTTPException

MAX_RESPONSE_BYTES = 64 * 1024
CACHE_SIZE = 64


class ProposalServiceError(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status = status
        self.code = code


def service_url(settings) -> str | None:
    url = (settings.proposal_url or "").rstrip("/")
    if not url or not settings.proposal_token:
        return None
    parts = urlsplit(url)
    local = parts.hostname in ("127.0.0.1", "localhost")
    if parts.scheme != "https" and not (local and parts.scheme == "http"):
        raise ValueError("proposal_service_requires_https")
    return url


def request_draft(settings, context: ProposalContext) -> dict:
    """POST the context to the service; never logs or retries the request body."""
    url = service_url(settings)
    if url is None:
        raise ProposalServiceError(503, "proposal_service_disabled")
    body = json.dumps({"context": context.model_dump(mode="json")}).encode("utf-8")
    request = urllib.request.Request(f"{url}/v1/proposals", data=body, method="POST", headers={
        "authorization": f"Bearer {settings.proposal_token}", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=settings.proposal_timeout_seconds) as response:
            data = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as error:
        code = {401: "proposal_service_unauthorized", 403: "proposal_service_unauthorized",
                429: "proposal_quota_exhausted", 503: "proposal_service_disabled"}.get(error.code, "proposal_service_unavailable")
        raise ProposalServiceError(429 if code == "proposal_quota_exhausted" else 503, code) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ProposalServiceError(503, "proposal_service_unavailable") from None
    if len(data) > MAX_RESPONSE_BYTES:
        raise ProposalServiceError(502, "proposal_response_invalid")
    try:
        payload = json.loads(data)
    except ValueError:
        raise ProposalServiceError(502, "proposal_response_invalid") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("model"), str) or not isinstance(payload.get("prompt_version"), str):
        raise ProposalServiceError(502, "proposal_response_invalid")
    return payload


def register_proposal_routes(api, settings, owner, workspace):
    Owner = Annotated[str, Depends(owner)]
    cache: OrderedDict[tuple[str, str, str], ValidatedProposal] = OrderedDict()

    @api.post("/v1/workspaces/{wid}/proposals", response_model=ValidatedProposal)
    def draft_proposal(wid: str, body: ProposalContext, who: Owner):
        workspace(wid, who)
        key = (who, wid, context_sha256(body))
        if key in cache:
            # Identical input reuses the earlier validated draft without another billable call.
            cache.move_to_end(key)
            return cache[key]
        try:
            payload = request_draft(settings, body)
            proposal = validate_draft(body, payload.get("draft"), model=payload["model"][:100],
                                      prompt_version=payload["prompt_version"][:40])
        except ProposalServiceError as error:
            raise HTTPException(error.status, error.code) from None
        except ProposalRejected as error:
            # Codes only: the draft text itself is never echoed into logs.
            raise HTTPException(502, {"code": "proposal_rejected", "reasons": error.codes}) from None
        except ValueError:
            raise HTTPException(503, "proposal_service_misconfigured") from None
        cache[key] = proposal
        while len(cache) > CACHE_SIZE:
            cache.popitem(last=False)
        return proposal
