"""A model-drafted discussion of one saved comparison (requirements AC-01–AC-09).

Off unless the proposal service is configured, like analysis proposals (L01–L06): the same service,
credential, per-user and monthly limits, and failure codes. The researcher asks for it on one saved
result; computing a result never calls the model (AC-02). Only the result's numbers and fixed
identifiers and the researcher's own short description leave the PC (AC-03). The draft is checked
against the result before it is stored or shown (AC-05), and stored with the result job, model and
prompt version it came from (AC-06). A failure never changes or hides the computed result (AC-07).
"""
import hashlib
import json
import time
import uuid
from typing import Annotated

from cytellect_analysis.discussion_context import DiscussionUnsupported, discussion_context
from cytellect_analysis.discussion_contracts import DISCUSSION_PROTOCOL, ExperimentNote, ValidatedDiscussion
from cytellect_analysis.discussion_validation import DiscussionRejected, context_sha256, validate_discussion
from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, StrictBool, ValidationError
from sqlalchemy import select, update

from .db import result_discussions, workspaces
from .proposals import ProposalServiceError, effective_settings, post_to_service, service_url


class DiscussionRequest(BaseModel):
    """`transmission_confirmed` records that the researcher chose to send this result to the AI (L03)."""
    model_config = ConfigDict(extra="forbid")
    experiment: ExperimentNote = ExperimentNote()
    transmission_confirmed: StrictBool = False
    retry_failed: StrictBool = False


class DiscussionView(BaseModel):
    job_id: str
    # When the discussion was stored (seconds since the epoch), shown with the model's name (AC-06).
    created: float
    discussion: ValidatedDiscussion


def _saved_result(store, job) -> dict:
    payload = job["payload"]
    if (job["kind"] != "statistics" or payload.get("mode") != "region-experimental-unit"
            or payload.get("version") != "2.0.0" or job["state"] != "succeeded" or not job["result_dir"]):
        raise HTTPException(404, "artifact_not_found")
    return json.loads(store.safe_path(job["result_dir"], "result.json").read_text(encoding="utf-8"))


def _context(store, job, experiment: ExperimentNote):
    try:
        return discussion_context(_saved_result(store, job), experiment)
    except (DiscussionUnsupported, ValidationError, KeyError, TypeError):
        raise HTTPException(409, "discussion_result_unsupported") from None


def register_discussion_routes(api, store, settings, owner, job_record, credentials=None):
    Owner = Annotated[str, Depends(owner)]

    @api.get("/v1/jobs/{jid}/discussion", response_model=DiscussionView | None)
    def saved_discussion(jid: str, who: Owner):
        """The latest stored discussion of this result, or null: a recalculated result has its own job and none
        yet. "None yet" is an answer, not an error, so the page reads it without a failed request."""
        job = job_record(jid, who)
        with store.engine.connect() as conn:
            row = conn.execute(select(result_discussions).where(
                result_discussions.c.workspace_id == job["workspace_id"], result_discussions.c.job_id == jid,
                result_discussions.c.state == "complete").order_by(result_discussions.c.created.desc())).mappings().first()
        if row is None:
            return None
        return DiscussionView(job_id=jid, created=row["created"], discussion=ValidatedDiscussion.model_validate(row["discussion"]))

    @api.post("/v1/jobs/{jid}/discussion", response_model=DiscussionView)
    def draft_discussion(jid: str, body: DiscussionRequest, who: Owner):
        job = job_record(jid, who)
        wid = job["workspace_id"]
        if body.transmission_confirmed is not True:
            raise HTTPException(428, "proposal_transmission_not_confirmed")
        context = _context(store, job, body.experiment)
        service = effective_settings(settings, credentials)
        try:
            if service_url(service) is None:
                # Nothing is recorded or sent while the service is off (AC-02 shows how to turn it on).
                raise HTTPException(503, "proposal_service_disabled")
        except ValueError:
            raise HTTPException(503, "proposal_service_misconfigured") from None
        identity = {"context": context_sha256(context), "protocol": DISCUSSION_PROTOCOL, "job": jid,
                    "model": settings.discussion_model, "prompt": settings.discussion_prompt_version,
                    "service": service.proposal_url}
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        request_id = str(uuid.uuid4())
        now = time.time()
        lease = now + settings.proposal_timeout_seconds + 30
        with store.transaction() as conn:
            live = conn.execute(select(workspaces).where(workspaces.c.id == wid)).mappings().first()
            if not store.workspace_is_live(live, now) or live["owner"] != who:
                raise HTTPException(404, "workspace_not_found")
            cached = conn.execute(select(result_discussions).where(
                result_discussions.c.workspace_id == wid, result_discussions.c.cache_key == key)).mappings().first()
            if cached and cached["state"] == "complete":
                return DiscussionView(job_id=jid, created=cached["created"], discussion=ValidatedDiscussion.model_validate(cached["discussion"]))
            if cached:
                if cached["state"] == "pending" and cached["lease_until"] > now:
                    raise HTTPException(409, "proposal_request_in_progress")
                if not body.retry_failed:
                    # A timeout may already have incurred cost; never silently pay again.
                    raise HTTPException(409, "proposal_explicit_retry_required")
                conn.execute(update(result_discussions).where(result_discussions.c.id == cached["id"]).values(
                    request_id=request_id, state="pending", created=now, lease_until=lease))
            else:
                conn.execute(result_discussions.insert().values(
                    id=str(uuid.uuid4()), workspace_id=wid, job_id=jid, cache_key=key, request_id=request_id,
                    state="pending", created=now, lease_until=lease))
        discussion = None
        try:
            payload = post_to_service(service, "/v1/discussions", {
                "context": context.model_dump(mode="json"), "prompt_version": settings.discussion_prompt_version}, request_id)
            if payload["model"] != settings.discussion_model or payload["prompt_version"] != settings.discussion_prompt_version:
                raise ProposalServiceError(502, "proposal_service_version_mismatch")
            discussion = validate_discussion(payload.get("draft"), context, model=payload["model"],
                                             prompt_version=payload["prompt_version"])
        except ProposalServiceError as error:
            raise HTTPException(error.status, error.code) from None
        except DiscussionRejected as error:
            # Codes only: the draft text itself is never echoed into logs.
            raise HTTPException(502, {"code": "discussion_rejected", "reasons": error.codes}) from None
        except ValueError:
            raise HTTPException(503, "proposal_service_misconfigured") from None
        finally:
            if discussion is None:
                with store.transaction() as conn:
                    conn.execute(update(result_discussions).where(
                        result_discussions.c.workspace_id == wid, result_discussions.c.cache_key == key,
                        result_discussions.c.request_id == request_id, result_discussions.c.state == "pending"
                    ).values(state="failed"))
        job_record(jid, who)  # Revocation or expiry during the external call blocks publication.
        with store.transaction() as conn:
            stored = conn.execute(update(result_discussions).where(
                result_discussions.c.workspace_id == wid, result_discussions.c.cache_key == key,
                result_discussions.c.request_id == request_id).values(
                    state="complete", discussion=discussion.model_dump(mode="json")))
            if stored.rowcount != 1:
                raise HTTPException(409, "proposal_request_superseded")
        return DiscussionView(job_id=jid, created=now, discussion=discussion)
