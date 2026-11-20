"""A model-written discussion of one saved comparison (requirements AC-01–AC-09).

Off unless the proposal service is configured, like analysis proposals (L01–L06): the same service,
credential, per-user and monthly limits, and failure codes. The researcher asks for it on one saved
result; computing a result never calls the model (AC-02). What leaves the PC is the saved result as the
workspace shows it, with the summary's heading and points, n with its breakdown, the recorded method,
the researcher's names and description (AC-03). The draft is shown as written once it has the three
headings (AC-05), and stored with the result job, model and prompt version it came from (AC-06). A
failure never changes or hides the computed result (AC-07).
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
from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError
from sqlalchemy import select, update

from .db import jobs, result_discussions, workspaces
from .proposals import ProposalServiceError, effective_settings, post_to_service, service_url


class ShownSummary(BaseModel):
    """The summary the workspace shows above this result (its heading and points, RS-02, RS-03)."""
    model_config = ConfigDict(extra="forbid")
    heading: Annotated[str, Field(min_length=1, max_length=500)]
    points: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(default_factory=list, max_length=8)


class DiscussionRequest(BaseModel):
    """`transmission_confirmed` records that the researcher chose to send this result to the AI (L03).
    `summary` is what the screen shows above the result, so that the discussion reads it the same way."""
    model_config = ConfigDict(extra="forbid")
    experiment: ExperimentNote = ExperimentNote()
    summary: ShownSummary | None = None
    transmission_confirmed: StrictBool = False
    retry_failed: StrictBool = False


class DiscussionView(BaseModel):
    job_id: str
    # When the discussion was stored (seconds since the epoch), shown with the model's name (AC-06).
    created: float
    discussion: ValidatedDiscussion


class DiscussionHistory(BaseModel):
    current: DiscussionView | None = None
    previous: DiscussionView | None = None


def _comparison_identity(result: dict) -> dict:
    """The same measure and groups across recalculations, not its revision, values or figure settings."""
    spec = result.get("spec") or {}
    selection = spec.get("selection") or {}
    positivity = selection.get("positivity") or {}
    return {"selection": {key: selection.get(key) for key in ("source", "region_set_id", "metric", "channel_id")},
            "positive_channel": positivity.get("channel_id") or positivity.get("gfp_channel_id"),
            "conditions": spec.get("conditions"), "stratum": (result.get("stratum") or {}).get("levels")}


def _saved_result(store, job) -> dict:
    payload = job["payload"]
    if (job["kind"] != "statistics" or payload.get("mode") != "region-experimental-unit"
            or payload.get("version") != "2.0.0" or job["state"] != "succeeded" or not job["result_dir"]):
        raise HTTPException(404, "artifact_not_found")
    return json.loads(store.safe_path(job["result_dir"], "result.json").read_text(encoding="utf-8"))


def _context(store, job, experiment: ExperimentNote, summary: ShownSummary | None = None):
    try:
        return discussion_context(_saved_result(store, job), experiment,
                                  heading=summary.heading if summary else None, points=summary.points if summary else None)
    except (DiscussionUnsupported, ValidationError, KeyError, TypeError):
        raise HTTPException(409, "discussion_result_unsupported") from None


def register_discussion_routes(api, store, settings, owner, job_record, credentials=None):
    Owner = Annotated[str, Depends(owner)]

    def result_job(jid: str, who: str):
        """A discussion belongs to the result (AC-06): a redrawn figure of a saved comparison reads and writes the
        discussion of the statistics job it was drawn from."""
        job = job_record(jid, who)
        source = job["payload"].get("source_job_id") if job["kind"] == "figure-render" else None
        return (source, job_record(source, who)) if isinstance(source, str) and source else (jid, job)

    @api.get("/v1/jobs/{jid}/discussion", response_model=DiscussionView | None)
    def saved_discussion(jid: str, who: Owner):
        """The latest stored discussion of this result, or null: a recalculated result has its own job and none
        yet. "None yet" is an answer, not an error, so the page reads it without a failed request."""
        jid, job = result_job(jid, who)
        with store.engine.connect() as conn:
            row = conn.execute(select(result_discussions).where(
                result_discussions.c.workspace_id == job["workspace_id"], result_discussions.c.job_id == jid,
                result_discussions.c.state == "complete").order_by(result_discussions.c.created.desc())).mappings().first()
        if row is None:
            return None
        return DiscussionView(job_id=jid, created=row["created"], discussion=ValidatedDiscussion.model_validate(row["discussion"]))

    @api.get("/v1/jobs/{jid}/discussion-history", response_model=DiscussionHistory)
    def discussion_history(jid: str, who: Owner):
        jid, job = result_job(jid, who)
        current = saved_discussion(jid, who)
        identity = _comparison_identity(_saved_result(store, job))
        with store.engine.connect() as conn:
            previous = conn.execute(select(result_discussions, jobs.c.result_dir.label("source_dir"),
                                           jobs.c.payload.label("source_payload"), jobs.c.kind.label("source_kind"),
                                           jobs.c.state.label("source_state")).join(
                jobs, jobs.c.id == result_discussions.c.job_id).where(
                result_discussions.c.workspace_id == job["workspace_id"], jobs.c.workspace_id == job["workspace_id"],
                result_discussions.c.job_id != jid, result_discussions.c.state == "complete",
                jobs.c.created <= job["created"]).order_by(jobs.c.created.desc(), result_discussions.c.created.desc())).mappings().all()
        for row in previous:
            try:
                source = {"kind": row["source_kind"], "payload": row["source_payload"],
                          "state": row["source_state"], "result_dir": row["source_dir"]}
                if _comparison_identity(_saved_result(store, source)) != identity:
                    continue
            except (HTTPException, OSError, ValueError):
                continue
            return DiscussionHistory(current=current, previous=DiscussionView(job_id=row["job_id"], created=row["created"],
                discussion=ValidatedDiscussion.model_validate(row["discussion"])))
        return DiscussionHistory(current=current)

    @api.post("/v1/jobs/{jid}/discussion", response_model=DiscussionView)
    def draft_discussion(jid: str, body: DiscussionRequest, who: Owner):
        jid, job = result_job(jid, who)
        wid = job["workspace_id"]
        if body.transmission_confirmed is not True:
            raise HTTPException(428, "proposal_transmission_not_confirmed")
        context = _context(store, job, body.experiment, body.summary)
        service = effective_settings(settings, credentials)
        try:
            if service_url(service) is None:
                # Nothing is recorded or sent while the service is off (AC-02 shows how to turn it on).
                raise HTTPException(503, "proposal_service_disabled")
        except ValueError:
            raise HTTPException(503, "proposal_service_misconfigured") from None
        identity = {"context": context_sha256(context), "protocol": DISCUSSION_PROTOCOL, "job": jid,
                    "model": settings.proposal_model, "prompt": settings.discussion_prompt_version,
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
            if payload["model"] not in {settings.proposal_model, *settings.proposal_models} or payload["prompt_version"] != settings.discussion_prompt_version:
                raise ProposalServiceError(502, "proposal_service_version_mismatch")
            discussion = validate_discussion(payload.get("draft"), context, model=payload["model"],
                                             prompt_version=payload["prompt_version"])
        except ProposalServiceError as error:
            raise HTTPException(error.status, error.code) from None
        except DiscussionRejected as error:
            # Only an answer without the three headings; codes only, the text is never echoed into logs.
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
