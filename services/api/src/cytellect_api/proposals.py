"""Optional analysis proposal drafts through the Cytellect proposal service.

Disabled unless an operator configures the service URL and this installation's
device credential. The researcher supplies at most a goal sentence; every other
input is derived from the workspace. Only normalized metadata leaves the PC;
the service calls the language model and returns a draft validated here.
Registered-recipe analysis never depends on this route.
"""
import hashlib
import json
import time
import urllib.error
import urllib.request
import uuid
from typing import Annotated
from urllib.parse import urlsplit

from cytellect_analysis.proposal_contracts import PROPOSAL_PROTOCOL, ProposalContext, ValidatedProposal
from cytellect_analysis.proposal_validation import ProposalRejected, context_sha256, validate_draft
from cytellect_analysis.region_contracts import (
    AdoptedNuclearRecipe,
    RegionImageInfo,
    validate_nuclear_role_evidence,
)
from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import select, update

from .db import fields, proposal_drafts, revisions, workspaces
from .regions import is_region

MAX_RESPONSE_BYTES = 64 * 1024
PROVIDER_ERROR_CODES = frozenset({
    "model_not_found", "invalid_api_key", "insufficient_quota", "rate_limit_exceeded",
    "invalid_request_error", "invalid_value", "invalid_json_schema", "unsupported_parameter",
    "unsupported_value", "missing_required_parameter", "context_length_exceeded",
    "permission_denied", "authentication_error", "server_error", "overloaded_error",
})


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect would resend the device credential to another URL; refuse it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


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


def request_draft(settings, context: ProposalContext, request_id: str | None = None) -> dict:
    """POST the context to the service; never logs or retries the request body."""
    url = service_url(settings)
    if url is None:
        raise ProposalServiceError(503, "proposal_service_disabled")
    body = json.dumps({"context": context.model_dump(mode="json")}).encode("utf-8")
    request = urllib.request.Request(f"{url}/v1/proposals", data=body, method="POST", headers={
        "authorization": f"Bearer {settings.proposal_token}", "content-type": "application/json",
        "user-agent": "Cytellect/0.1",
        "Idempotency-Key": request_id or str(uuid.uuid4())})
    try:
        with _OPENER.open(request, timeout=settings.proposal_timeout_seconds) as response:
            data = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as error:
        code = {401: "proposal_service_unauthorized", 403: "proposal_service_unauthorized",
                409: "proposal_request_already_sent", 429: "proposal_quota_exhausted"}.get(error.code, "proposal_service_unavailable")
        status = error.code if error.code in (409, 429) else 503
        if error.code in (502, 503):
            try:
                data = error.read(2049)
                failure = json.loads(data) if len(data) <= 2048 else None
                reason = failure.get("code") if isinstance(failure, dict) else None
                if error.code == 502 and reason in ("model_refused", "model_output_invalid", "model_output_incomplete", "model_usage_exceeded"):
                    code, status = f"proposal_{reason}", 502
                elif error.code == 503 and reason in ("proposal_service_disabled", "budget_reconciliation_required", "model_unavailable"):
                    code = reason if reason == "proposal_service_disabled" else f"proposal_{reason}"
                    if reason == "model_unavailable" and isinstance(failure, dict):
                        provider_code = failure.get("provider_error_code")
                        provider_status = failure.get("provider_http_status")
                        if isinstance(provider_code, str) and provider_code in PROVIDER_ERROR_CODES:
                            code = f"proposal_provider_{provider_code}"
                        elif type(provider_status) is int and 400 <= provider_status <= 599:
                            code = f"proposal_provider_http_{provider_status}"
            except (ValueError, OSError, AttributeError):
                pass
        raise ProposalServiceError(status, code) from None
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
    """The only researcher input: an optional goal in their own words.

    `transmission_confirmed` records that the researcher has seen what is sent
    and enabled it (L03). The UI asks once and remembers; without it nothing
    leaves the PC.
    """
    model_config = ConfigDict(extra="forbid")
    goal: Annotated[str, Field(max_length=2000)] = ""
    transmission_confirmed: StrictBool = False
    retry_failed: StrictBool = False


class ProposalChannelLink(BaseModel):
    token: str
    channel_id: str
    stain: str | None


class ProposalDraftResponse(BaseModel):
    proposal: ValidatedProposal
    channels: list[ProposalChannelLink]


LEGACY_STAINS = {"ncl": ("NCL", "measure"), "gfp": ("GFP", "measure"), "dapi": (None, "nuclear")}


def _complete(rows, key):
    return bool(rows) and all(row["metadata"].get(key) not in (None, "") for row in rows)


def build_context(store, wid: str, goal: str) -> tuple[ProposalContext, list[ProposalChannelLink]]:
    """Derive every proposal input from the workspace; nothing else is asked of the researcher.

    Only channel tokens, recorded stains and counts/flags leave the PC. Channel
    labels, file names, metadata values, images and measurements stay local.
    """
    rows = store.rows(fields, workspace_id=wid)
    workspace_row = store.one(workspaces, id=wid)
    if workspace_row is None:
        raise HTTPException(404, "workspace_not_found")
    active = store.one(revisions, id=workspace_row["active_revision"], workspace_id=wid) if workspace_row["active_revision"] else None
    config = active["config"] if active else {}
    snapshots = config.get("field_snapshot", {})
    # Saved metadata edits take precedence over immutable registration metadata.
    rows = [snapshots.get(row["id"], row) for row in rows]
    links: list[ProposalChannelLink] = []
    channels: list[dict] = []
    region = [row for row in rows if is_region(row)]
    if region and len(region) != len(rows):
        raise HTTPException(409, "proposal_mixed_input_modes")
    if region:
        if config.get("recipe", {}).get("version") == "1.2.0":
            adopted = AdoptedNuclearRecipe.model_validate(config["recipe"])
            for row in region:
                validate_nuclear_role_evidence(adopted, RegionImageInfo.model_validate(row["image_info"]))
        seen: dict[str, dict] = {}
        for row in region:
            for spec in row["image_info"]["channels"]:
                previous = seen.setdefault(spec["channel_id"], spec)
                if previous.get("stain") != spec.get("stain"):
                    raise HTTPException(409, "proposal_channel_identity_conflict")
        if any({spec["channel_id"] for spec in row["image_info"]["channels"]} != set(seen) for row in region):
            raise HTTPException(409, "proposal_channel_coverage_incomplete")
        for index, (channel_id, spec) in enumerate(sorted(seen.items())):
            # Labels and IDs can contain research information; use opaque tokens.
            token = f"ch{index + 1}"
            links.append(ProposalChannelLink(token=token, channel_id=channel_id, stain=spec.get("stain")))
            recipe = config.get("recipe", {})
            adopted_role = (recipe.get("version") == "1.2.0"
                            and recipe.get("nuclear_role_source") in ("recorded_stain", "user_selected_role"))
            role = ("nuclear" if recipe.get("defining_channel_id") == channel_id
                    and (recipe.get("nuclear_stain_confirmed") is True or adopted_role) else None)
            channels.append({"token": token, "stain": spec.get("stain"), "role": role})
    else:
        roles = dict.fromkeys(role for row in rows for role in row["image_info"].get("channel_roles", []))
        if any(set(row["image_info"].get("channel_roles", [])) != set(roles) for row in rows):
            raise HTTPException(409, "proposal_channel_coverage_incomplete")
        for index, role in enumerate(sorted(roles)):
            stain, kind = LEGACY_STAINS.get(role, (None, None))
            token = f"ch{index + 1}"
            links.append(ProposalChannelLink(token=token, channel_id=role, stain=stain))
            channels.append({"token": token, "stain": stain, "role": kind})
    if not channels:
        raise HTTPException(409, "proposal_requires_images")
    if len(channels) > 6:
        raise HTTPException(409, "proposal_channel_limit")
    conditions = {row["metadata"].get("condition") for row in rows if row["metadata"].get("condition")}
    backgrounds = config.get("backgrounds", {})
    background_available = bool(rows) and all(
        row["id"] in snapshots and (
            bool(backgrounds.get(row["id"], {}).get("confirmed")) if not region else
            all(backgrounds.get(row["id"], {}).get(link.channel_id, {}).get("confirmed") for link in links)
        ) for row in rows
    )
    pair_groups: dict[str, dict[str, set[str]]] = {}
    for row in rows:
        metadata = row["metadata"]
        if metadata.get("pair") and metadata.get("condition") and metadata.get("experimental_unit"):
            pair_groups.setdefault(metadata["pair"], {}).setdefault(metadata["condition"], set()).add(metadata["experimental_unit"])
    pairing_known = (_complete(rows, "pair") and _complete(rows, "experimental_unit") and len(conditions) == 2
                     and all(set(groups) == conditions and all(len(units) == 1 for units in groups.values())
                             for groups in pair_groups.values()))
    unit_counts = [len({row["metadata"].get("experimental_unit") for row in rows
                       if row["metadata"].get("condition") == condition and row["metadata"].get("experimental_unit")})
                   for condition in sorted(conditions)]
    context = ProposalContext.model_validate(dict(
        goal=goal, channels=channels, field_count=len(rows), condition_count=len(conditions),
        units_known=_complete(rows, "experimental_unit") and _complete(rows, "condition"), pairing_known=pairing_known,
        units_per_condition=unit_counts, complete_pair_count=len(pair_groups) if pairing_known else 0,
        supplied_regions=bool(region) and all(row["image_info"].get("labels_array") for row in region),
        # This route plans the image cohort, not unrelated numerical tables.
        measured_table=False, background_available=background_available,
    ))
    return context, links


def _source_stamp(store, wid: str) -> str:
    """Private change guard, never transmitted or logged; ignore plot styling."""
    record = store.one(workspaces, id=wid)
    if record is None:
        raise HTTPException(404, "workspace_not_found")
    active = store.one(revisions, id=record["active_revision"], workspace_id=wid) if record["active_revision"] else None
    config = active["config"] if active else {}
    payload = {"fields": sorted([dict(row) for row in store.rows(fields, workspace_id=wid)], key=lambda row: row["id"]),
               "recipe": config.get("recipe"), "measurement": config.get("measurement"),
               "backgrounds": config.get("backgrounds"), "snapshot": config.get("field_snapshot")}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def register_proposal_routes(api, store, settings, owner, workspace):
    Owner = Annotated[str, Depends(owner)]

    @api.post("/v1/workspaces/{wid}/proposal-drafts", response_model=ProposalDraftResponse)
    def draft_proposal(wid: str, body: ProposalDraftRequest, who: Owner):
        workspace(wid, who)
        if body.transmission_confirmed is not True:
            raise HTTPException(428, "proposal_transmission_not_confirmed")
        try:
            context, links = build_context(store, wid, body.goal)
        except ValueError:
            raise HTTPException(409, "proposal_context_unsupported") from None
        source_stamp = _source_stamp(store, wid)
        identity = {"context": context_sha256(context), "protocol": PROPOSAL_PROTOCOL,
                    "model": settings.proposal_model, "prompt": settings.proposal_prompt_version,
                    "service": settings.proposal_url, "channels": [link.model_dump() for link in links], "source": source_stamp}
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        request_id = str(uuid.uuid4())
        now = time.time()
        with store.transaction() as conn:
            live = conn.execute(select(workspaces).where(workspaces.c.id == wid)).mappings().first()
            if not live or live["owner"] != who or live["deleted"] or live["expires"] <= now:
                raise HTTPException(404, "workspace_not_found")
            cached = conn.execute(select(proposal_drafts).where(
                proposal_drafts.c.workspace_id == wid, proposal_drafts.c.cache_key == key)).mappings().first()
            if cached and cached["state"] == "complete":
                return ProposalDraftResponse(proposal=ValidatedProposal.model_validate(cached["proposal"]), channels=links)
            if cached:
                if cached["state"] == "pending" and cached["lease_until"] > now:
                    raise HTTPException(409, "proposal_request_in_progress")
                if not body.retry_failed:
                    # A timeout may already have incurred cost; never silently pay again.
                    raise HTTPException(409, "proposal_explicit_retry_required")
                conn.execute(update(proposal_drafts).where(proposal_drafts.c.id == cached["id"]).values(
                    request_id=request_id, state="pending", lease_until=now + settings.proposal_timeout_seconds + 30))
            else:
                conn.execute(proposal_drafts.insert().values(id=str(uuid.uuid4()), workspace_id=wid, cache_key=key,
                    request_id=request_id, state="pending", created=now,
                    lease_until=now + settings.proposal_timeout_seconds + 30))
        proposal = None
        try:
            payload = request_draft(settings, context, request_id)
            if payload["model"] != settings.proposal_model or payload["prompt_version"] != settings.proposal_prompt_version:
                raise ProposalServiceError(502, "proposal_service_version_mismatch")
            proposal = validate_draft(context, payload.get("draft"), model=payload["model"],
                                      prompt_version=payload["prompt_version"])
        except ProposalServiceError as error:
            raise HTTPException(error.status, error.code) from None
        except ProposalRejected as error:
            # Codes only: the draft text itself is never echoed into logs.
            raise HTTPException(502, {"code": "proposal_rejected", "reasons": error.codes}) from None
        except ValueError:
            raise HTTPException(503, "proposal_service_misconfigured") from None
        finally:
            if proposal is None:
                with store.transaction() as conn:
                    conn.execute(update(proposal_drafts).where(proposal_drafts.c.workspace_id == wid,
                        proposal_drafts.c.cache_key == key, proposal_drafts.c.request_id == request_id,
                        proposal_drafts.c.state == "pending").values(state="failed"))
        workspace(wid, who)  # Revocation/expiry during the external call blocks publication.
        try:
            refreshed, refreshed_links = build_context(store, wid, body.goal)
            changed = (context_sha256(refreshed) != context_sha256(context) or refreshed_links != links
                       or _source_stamp(store, wid) != source_stamp)
        except ValueError:
            changed = True
        if changed:
            # Release the request instead of leaving it pending until the lease ends.
            with store.transaction() as conn:
                conn.execute(update(proposal_drafts).where(proposal_drafts.c.workspace_id == wid,
                    proposal_drafts.c.cache_key == key, proposal_drafts.c.request_id == request_id,
                    proposal_drafts.c.state == "pending").values(state="failed"))
            raise HTTPException(409, "proposal_context_changed")
        with store.transaction() as conn:
            result = conn.execute(update(proposal_drafts).where(proposal_drafts.c.workspace_id == wid,
                proposal_drafts.c.cache_key == key, proposal_drafts.c.request_id == request_id).values(
                    state="complete", proposal=proposal.model_dump(mode="json")))
            if result.rowcount != 1:
                raise HTTPException(409, "proposal_request_superseded")
        return ProposalDraftResponse(proposal=proposal, channels=links)
