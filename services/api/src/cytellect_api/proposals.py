"""Optional analysis proposal drafts through the Cytellect proposal service.

Disabled unless an operator configures the service URL and this installation's
device credential. The researcher supplies at most a goal sentence; every other
input is derived from the workspace. Only normalized metadata leaves the PC;
the service calls the language model and returns a draft validated here.
Registered-recipe analysis never depends on this route.
"""
import json
import re
import urllib.error
import urllib.request
from collections import OrderedDict
from typing import Annotated
from urllib.parse import urlsplit

from cytellect_analysis.proposal_contracts import ProposalContext, ValidatedProposal
from cytellect_analysis.proposal_validation import ProposalRejected, context_sha256, validate_draft
from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .db import fields, revisions, tables
from .regions import is_region

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


class ProposalDraftRequest(BaseModel):
    """The only researcher input: an optional goal in their own words."""
    model_config = ConfigDict(extra="forbid")
    goal: Annotated[str, Field(max_length=2000)] = ""


class ProposalChannelLink(BaseModel):
    token: str
    channel_id: str
    stain: str | None


class ProposalDraftResponse(BaseModel):
    proposal: ValidatedProposal
    channels: list[ProposalChannelLink]


TOKEN = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,31}$")
LEGACY_STAINS = {"ncl": ("NCL", "measure"), "gfp": ("GFP", "measure"), "dapi": (None, "nuclear")}


def _complete(rows, key):
    return bool(rows) and all(row["metadata"].get(key) not in (None, "") for row in rows)


def build_context(store, wid: str, goal: str) -> tuple[ProposalContext, list[ProposalChannelLink]]:
    """Derive every proposal input from the workspace; nothing else is asked of the researcher.

    Only channel tokens, recorded stains and counts/flags leave the PC. Channel
    labels, file names, metadata values, images and measurements stay local.
    """
    rows = store.rows(fields, workspace_id=wid)
    links: list[ProposalChannelLink] = []
    channels: list[dict] = []
    region = [row for row in rows if is_region(row)]
    if region:
        seen: dict[str, dict] = {}
        for row in region:
            for spec in row["image_info"]["channels"]:
                seen.setdefault(spec["channel_id"], spec)
        for index, (channel_id, spec) in enumerate(seen.items()):
            token = channel_id.lower() if TOKEN.match(channel_id.lower()) else f"ch{index + 1}"
            links.append(ProposalChannelLink(token=token, channel_id=channel_id, stain=spec.get("stain")))
            channels.append({"token": token, "stain": spec.get("stain")})
    else:
        roles = dict.fromkeys(role for row in rows for role in row["image_info"].get("channel_roles", []))
        for role in roles:
            stain, kind = LEGACY_STAINS.get(role, (None, None))
            links.append(ProposalChannelLink(token=role, channel_id=role, stain=stain))
            channels.append({"token": role, "stain": stain, "role": kind})
    if not channels:
        raise HTTPException(409, "proposal_requires_images")
    configs = [revision["config"] for revision in store.rows(revisions, workspace_id=wid)]
    conditions = {row["metadata"].get("condition") for row in rows if row["metadata"].get("condition")}
    context = ProposalContext.model_validate(dict(
        goal=goal, channels=channels[:6], field_count=len(rows), condition_count=len(conditions),
        units_known=_complete(rows, "experimental_unit"), pairing_known=_complete(rows, "pair"),
        supplied_regions=any(row["image_info"].get("labels_array") for row in region),
        measured_table=bool(store.rows(tables, workspace_id=wid)),
        background_available=any(config.get("backgrounds") or config.get("background") for config in configs),
    ))
    return context, links[:6]


def register_proposal_routes(api, store, settings, owner, workspace):
    Owner = Annotated[str, Depends(owner)]
    cache: OrderedDict[tuple[str, str, str], ValidatedProposal] = OrderedDict()

    @api.post("/v1/workspaces/{wid}/proposal-drafts", response_model=ProposalDraftResponse)
    def draft_proposal(wid: str, body: ProposalDraftRequest, who: Owner):
        workspace(wid, who)
        context, links = build_context(store, wid, body.goal)
        key = (who, wid, context_sha256(context))
        if key in cache:
            # Identical input reuses the earlier validated draft without another billable call.
            cache.move_to_end(key)
            return ProposalDraftResponse(proposal=cache[key], channels=links)
        try:
            payload = request_draft(settings, context)
            proposal = validate_draft(context, payload.get("draft"), model=payload["model"][:100],
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
        return ProposalDraftResponse(proposal=proposal, channels=links)
