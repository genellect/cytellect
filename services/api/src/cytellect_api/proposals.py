"""Optional analysis proposal drafts through the Cytellect proposal service.

Disabled unless an operator configures the service URL and this installation's
device credential. The researcher supplies at most a goal sentence; every other
input is derived from the workspace. Only normalized metadata leaves the PC;
the service calls the language model and returns a draft validated here.
Registered-recipe analysis never depends on this route.
"""
import base64
import dataclasses
import functools
import hashlib
import io
import json
import re
import time
import urllib.error
import urllib.request
import uuid
from typing import Annotated, Literal
from urllib.parse import urlsplit

import numpy as np
from cytellect_analysis.images import render_preview_with_display
from cytellect_analysis.proposal_contracts import (
    INTENT_FIELDS,
    PROPOSAL_CONTEXT_PROTOCOL,
    PROPOSAL_PROTOCOL,
    DraftProcessing,
    ProposalContext,
    ProposalDraft,
    ValidatedProposal,
    context_protocol,
)
from cytellect_analysis.proposal_validation import (
    ProposalRejected,
    context_sha256,
    reply_text,
    validate_draft,
)
from cytellect_analysis.region_contracts import (
    AdoptedNuclearRecipe,
    AutoScaledNuclearRecipe,
    RegionImageInfo,
    ScaledNuclearRecipe,
    validate_nuclear_role_evidence,
)
from fastapi import Depends, HTTPException
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import select, update

from .channel_assignments import apply_channel_assignments
from .db import assistant_messages, fields, proposal_drafts, revisions, workspaces
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


class _LazyOpener:
    """Builds the no-redirect opener at first use.

    Python 3.14 creates an SSL context when the HTTPS handler is built. Doing that
    at import time fails in restricted environments (e.g. a Windows child process
    without its usual variables) that never make a request.
    """

    def open(self, *args, **kwargs):
        return _no_redirect_opener().open(*args, **kwargs)


@functools.cache
def _no_redirect_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_NoRedirect)


_OPENER = _LazyOpener()


class ProposalServiceError(Exception):
    def __init__(self, status: int, code: str, *, may_have_charged: bool = True):
        super().__init__(code)
        self.status = status
        self.code = code
        self.may_have_charged = may_have_charged


def service_url(settings) -> str | None:
    url = (settings.proposal_url or "").rstrip("/")
    if not url or not settings.proposal_token:
        return None
    parts = urlsplit(url)
    local = parts.hostname in ("127.0.0.1", "localhost")
    if parts.scheme != "https" and not (local and parts.scheme == "http"):
        raise ValueError("proposal_service_requires_https")
    return url


def effective_settings(settings, credentials=None):
    """The proposal service to call and its device token.

    An operator's explicit configuration (``CYTELLECT_PROPOSAL_URL``) keeps
    precedence. Otherwise a local installation uses its signed-in cloud account:
    ``credentials`` returns that account's base URL and device token, or None.
    ``service_url`` then applies the same https rule to either source.
    """
    if settings.proposal_url or credentials is None:
        return settings
    account = credentials()
    if not account:
        return settings
    return dataclasses.replace(settings, proposal_url=account[0], proposal_token=account[1])


def request_draft(settings, context: ProposalContext, request_id: str | None = None,
                  previews: list[dict] | None = None) -> dict:
    """POST the context (and previews) to the service; never logs or retries the request body."""
    content = {"context": context.model_dump(mode="json"), "prompt_version": settings.proposal_prompt_version}
    if previews:
        content["previews"] = previews
    return post_to_service(settings, "/v1/proposals", content, request_id)


def post_to_service(settings, path: str, content: dict, request_id: str | None = None) -> dict:
    """One POST to the proposal service; the same credential, limits and failure codes for every route."""
    try:
        url = service_url(settings)
    except ValueError:
        raise ProposalServiceError(503, "proposal_service_misconfigured", may_have_charged=False) from None
    if url is None:
        raise ProposalServiceError(503, "proposal_service_disabled", may_have_charged=False)
    body = json.dumps(content).encode("utf-8")
    request = urllib.request.Request(f"{url}{path}", data=body, method="POST", headers={
        "authorization": f"Bearer {settings.proposal_token}", "content-type": "application/json",
        "user-agent": "Cytellect/0.1",
        "Idempotency-Key": request_id or str(uuid.uuid4())})
    try:
        with _OPENER.open(request, timeout=settings.proposal_timeout_seconds) as response:
            data = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as error:
        unbilled = error.code in (401, 403, 429)
        code = {401: "proposal_service_unauthorized", 403: "proposal_service_unauthorized",
                409: "proposal_request_already_sent", 429: "proposal_quota_exhausted"}.get(error.code, "proposal_service_unavailable")
        status = error.code if error.code in (409, 429) else 503
        if error.code == 403:
            # The cloud service ends a revoked user's access; say so instead of a key problem.
            try:
                data = error.read(2049)
                failure = json.loads(data) if len(data) <= 2048 else None
                if isinstance(failure, dict) and failure.get("code") == "revoked":
                    code = "proposal_access_revoked"
            except (ValueError, OSError, AttributeError):
                pass
        if error.code == 400:
            # The service does not know this client's prompt version yet (it is deployed before a release that
            # sends a new one): a version mismatch, not a connection problem.
            try:
                data = error.read(2049)
                failure = json.loads(data) if len(data) <= 2048 else None
                if isinstance(failure, dict) and failure.get("code") == "prompt_version_unsupported":
                    code, status = "proposal_service_version_mismatch", 502
                    unbilled = True
                elif isinstance(failure, dict) and failure.get("code") in ("request_invalid", "request_id_required"):
                    code, status, unbilled = "proposal_service_request_incompatible", 502, True
            except (ValueError, OSError, AttributeError):
                pass
        if error.code in (502, 503):
            try:
                data = error.read(2049)
                failure = json.loads(data) if len(data) <= 2048 else None
                reason = failure.get("code") if isinstance(failure, dict) else None
                if error.code == 502 and reason in ("model_refused", "model_output_invalid", "model_output_incomplete", "model_usage_exceeded"):
                    code, status = f"proposal_{reason}", 502
                elif error.code == 503 and reason in ("proposal_service_disabled", "budget_reconciliation_required", "model_unavailable"):
                    code = reason if reason == "proposal_service_disabled" else f"proposal_{reason}"
                    if reason == "proposal_service_disabled":
                        unbilled = True
                    if reason == "model_unavailable" and isinstance(failure, dict):
                        provider_code = failure.get("provider_error_code")
                        provider_status = failure.get("provider_http_status")
                        if isinstance(provider_code, str) and provider_code in PROVIDER_ERROR_CODES:
                            code = f"proposal_provider_{provider_code}"
                        elif type(provider_status) is int and 400 <= provider_status <= 599:
                            code = f"proposal_provider_http_{provider_status}"
            except (ValueError, OSError, AttributeError):
                pass
        raise ProposalServiceError(status, code, may_have_charged=not unbilled) from None
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

    `transmission_confirmed` records that the researcher sent this instruction to
    the AI (L03); the workspace sets it on that action. Without it nothing leaves
    the PC.
    """
    model_config = ConfigDict(extra="forbid")
    goal: Annotated[str, Field(max_length=2000)] = ""
    transmission_confirmed: StrictBool = False
    # The researcher's setting: also send display-scaled previews of one representative field (default on).
    include_previews: StrictBool = True
    retry_failed: StrictBool = False
    field_id: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    current_processing: Annotated[dict, Field(max_length=4)] | None = None
    previous_goal: Annotated[str, Field(max_length=2000)] = ""
    previous_proposal: Annotated[dict, Field(max_length=18)] | None = None
    # The message this request sends again (its 「再送」); a new message otherwise (#284 W2).
    message_id: Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")] | None = None


MessageEffect = Literal["none", "settings", "run"]


class AssistantMessage(BaseModel):
    """One message of the researcher to the AI and what came back (#284 W2). `applicable` is true when the
    answer carries settings the researcher may apply, false when its settings were refused (`reasons` and `stage`
    say why), and null when there is nothing to apply: a question's answer (#284 W7), or a message still pending
    or failed. Nothing here changes settings."""
    id: str
    field_id: str | None
    created: float
    text: str
    state: Literal["pending", "answered", "failed"]
    reply: str | None
    applicable: bool | None
    reasons: list[str]
    stage: Literal["context", "service", "validation"] | None
    effect: MessageEffect


def _applicable(draft) -> bool | None:
    """A question's answer (`intent: answer`) has no settings: it is neither applicable nor refused."""
    return None if getattr(draft, "intent", None) == "answer" else True


class AssistantMessages(BaseModel):
    messages: list[AssistantMessage]


class AssistantEffect(BaseModel):
    model_config = ConfigDict(extra="forbid")
    effect: MessageEffect


class ProposalChannelLink(BaseModel):
    token: str
    channel_id: str
    stain: str | None


class ProposalFieldLink(BaseModel):
    """The context's opaque field identifier (`f1`…) and the workspace field it names (context 1.3.0, #284 W7)."""
    token: str
    field_id: str


class ProposalDraftResponse(BaseModel):
    # None when the model answered but its settings cannot be applied: the answer is in `message.reply`.
    proposal: ValidatedProposal | None
    channels: list[ProposalChannelLink]
    message: AssistantMessage | None = None
    # The fields an answer's assignment suggestions name; empty for a context before 1.3.0.
    fields: list[ProposalFieldLink] = Field(default_factory=list)


def message_view(row) -> AssistantMessage:
    return AssistantMessage(id=row["id"], field_id=row["field_id"], created=row["created"], text=row["text"],
                            state=row["state"], reply=row["reply"], applicable=row["applicable"],
                            reasons=list(row["reasons"] or []), stage=row["stage"], effect=row["effect"])


def answer_text(rationale: str, missing: tuple[str, ...] | list[str], answer: str | None = None) -> str:
    """The answer as the researcher reads it: the direct answer, the rationale, then each item to confirm."""
    return "\n".join(text.strip() for text in [answer or "", rationale, *missing] if text and text.strip())


class AiStatus(BaseModel):
    """Local configuration only: no provider call, credential, service URL or research data."""
    state: Literal["available", "sign_in_required", "unconfigured", "misconfigured"]
    source: Literal["operator", "account", "none"]


class AiCompatibility(BaseModel):
    state: Literal["compatible", "unconfigured", "misconfigured", "unavailable", "unauthorized", "incompatible"]


LEGACY_STAINS = {"ncl": ("NCL", "measure"), "gfp": ("GFP", "measure"), "dapi": (None, "nuclear")}


def _complete(rows, key):
    return bool(rows) and all(row["metadata"].get(key) not in (None, "") for row in rows)


def _adopted_selection(store, wid: str) -> tuple[dict, set[str]]:
    """The adopted selection and the fields the researcher excluded in it; neither proposals nor previews use those."""
    from .workspace_selection import selection_at
    with store.engine.connect() as conn:
        selection = selection_at(conn, wid)
    return selection, {entry["field_id"] for entry in selection["entries"] if entry.get("exclusion_reason")}


def build_context(store, wid: str, goal: str, field_id: str | None = None, *, protocol: str = PROPOSAL_CONTEXT_PROTOCOL,
                  field_links: list | None = None) -> tuple[ProposalContext, list[ProposalChannelLink]]:
    """Derive every proposal input from the workspace; nothing else is asked of the researcher.

    The model reads the workspace as the researcher recorded it (docs/drafts/llm-assistant/plan.md): channel
    tokens with their labels and recorded stains, every field's name and metadata, counts and current settings.
    Context 1.3.0 (#284 W7) adds an opaque identifier per field, the folder-relative names its files were added with
    and its run and group, and the design's run and group names; `field_links` then receives identifier → field.
    Absolute paths and measured values stay local; downscaled previews are built separately (`representative_previews`).
    """
    rows = store.rows(fields, workspace_id=wid)
    adopted_selection, excluded = _adopted_selection(store, wid)
    if field_id is not None and not any(row["id"] == field_id for row in rows):
        raise HTTPException(404, "field_not_found")
    if field_id in excluded:
        raise HTTPException(409, "proposal_selected_field_excluded")
    rows = [row for row in rows if row["id"] not in excluded]
    workspace_row = store.one(workspaces, id=wid)
    if workspace_row is None:
        raise HTTPException(404, "workspace_not_found")
    active = store.one(revisions, id=workspace_row["active_revision"], workspace_id=wid) if workspace_row["active_revision"] else None
    config = active["config"] if active else {}
    snapshots = config.get("field_snapshot", {})
    # The researcher-visible name is recorded at registration, not in snapshots.
    display_names = {row["id"]: row.get("display_name") for row in rows}
    # Saved metadata edits take precedence over immutable registration metadata.
    rows = [snapshots.get(row["id"], row) for row in rows]
    links: list[ProposalChannelLink] = []
    channels: list[dict] = []
    region = [row for row in rows if is_region(row)]
    if region and len(region) != len(rows):
        raise HTTPException(409, "proposal_mixed_input_modes")
    if region:
        if config.get("recipe", {}).get("version") in ("1.2.0", "1.5.0", "1.7.0"):
            version = config["recipe"]["version"]
            adopted: AdoptedNuclearRecipe | ScaledNuclearRecipe | AutoScaledNuclearRecipe = (
                ScaledNuclearRecipe.model_validate(config["recipe"]) if version == "1.5.0"
                else AutoScaledNuclearRecipe.model_validate(config["recipe"]) if version == "1.7.0"
                else AdoptedNuclearRecipe.model_validate(config["recipe"]))
            for row in region:
                validate_nuclear_role_evidence(adopted, RegionImageInfo.model_validate(row["image_info"]))
        # Current user assignments override old adopted-recipe identities for a
        # new proposal. They never rewrite the source field or saved revisions.
        region = apply_channel_assignments(store, wid, region, include_roles=True)
        if field_id is not None:
            selected = next(row for row in region if row["id"] == field_id)
            def configuration(row):
                info = row["image_info"]
                return (info.get("input_mode", "native"), sorted((spec["channel_id"], spec.get("stain") or "", spec.get("assignment_role") or "")
                    for spec in info["channels"]))
            region = [row for row in region if configuration(row) == configuration(selected)]
            rows = region
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
            adopted_role = (recipe.get("version") in ("1.2.0", "1.5.0", "1.7.0")
                            and recipe.get("nuclear_role_source") in ("recorded_stain", "user_selected_role"))
            role = ("nuclear" if recipe.get("defining_channel_id") == channel_id
                    and (recipe.get("nuclear_stain_confirmed") is True or adopted_role) else None)
            if "assignment_role" in spec:
                role = spec["assignment_role"]
            label = spec.get("label")
            channels.append({"token": token, "stain": spec.get("stain"), "role": role,
                             "label": label[:80] if isinstance(label, str) and label.strip() else None})
    else:
        roles = dict.fromkeys(role for row in rows for role in row["image_info"].get("channel_roles", []))
        if any(set(row["image_info"].get("channel_roles", [])) != set(roles) for row in rows):
            raise HTTPException(409, "proposal_channel_coverage_incomplete")
        for index, role in enumerate(sorted(roles)):
            stain, kind = LEGACY_STAINS.get(role, (None, None))
            token = f"ch{index + 1}"
            links.append(ProposalChannelLink(token=token, channel_id=role, stain=stain))
            channels.append({"token": token, "stain": stain, "role": kind, "label": role[:80] or None})
    if rows and not channels:
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
    # Persisted configuration is authoritative; only opaque channels/settings leave the PC.
    from .analysis_spec import analysis_spec_at
    with store.engine.connect() as conn:
        specification = analysis_spec_at(conn, wid).get("spec") or {}
    channel_tokens = {link.channel_id: link.token for link in links}
    background_mode = specification.get("settings", {}).get("background")
    gate = specification.get("selection", {}).get("gfp")
    current_gfp = None
    registered_controls = False
    if gate and gate.get("gfp_channel_id") in channel_tokens:
        control_ids = gate.get("control_field_ids", [])
        registered_controls = bool(control_ids) and set(control_ids) <= {row["id"] for row in rows}
        current_gfp = {"channel": channel_tokens[gate["gfp_channel_id"]], "unit": gate.get("unit", "nucleus"),
                       "method": gate.get("method", "negative_control"), "threshold": gate.get("threshold"),
                       "values": gate.get("values", "raw"), "keep": gate.get("keep", "positive"),
                       "percentile": gate.get("percentile", 99)}
    if background_mode == "confirmed_roi":
        recorded = specification.get("backgrounds", {})
        background_available = bool(rows) and all(all(recorded.get(row["id"], {}).get(link.channel_id, {}).get("confirmed")
            for link in links) for row in rows)
    adopted_cells = set()
    for entry in adopted_selection["entries"]:
        cell_revision = entry.get("target_revisions", {}).get("cell")
        if cell_revision:
            cell_record = store.one(revisions, id=cell_revision, workspace_id=wid)
            cell_recipe = cell_record["config"].get("recipe", {}) if cell_record else {}
            if cell_record and cell_record["state"] == "succeeded" and cell_recipe.get("source") == "manual" and cell_recipe.get("region_set_id") == "cell":
                adopted_cells.add(entry["field_id"])
    sent = rows[:200]
    extended = protocol == "1.3.0"
    stored_experiment = specification.get("experiment") if extended else None
    experiment: dict = stored_experiment if isinstance(stored_experiment, dict) else {}
    added = {entry["field_id"]: entry["intake"].get("names") or [] for entry in adopted_selection["entries"]
             if entry.get("field_id") and isinstance(entry.get("intake"), dict)}
    field_records = [_field_record(row, display_names.get(row["id"])) for row in sent]
    if extended:
        stored_fields = experiment.get("fields")
        assigned: dict = stored_fields if isinstance(stored_fields, dict) else {}
        run_names = {run.get("id"): _label(run.get("label")) for run in experiment.get("runs") or [] if isinstance(run, dict)}
        group_names = {group.get("id"): _label(group.get("label")) for group in experiment.get("groups") or [] if isinstance(group, dict)}
        for index, (row, record) in enumerate(zip(sent, field_records)):
            stored_place = assigned.get(row["id"])
            placed: dict = stored_place if isinstance(stored_place, dict) else {}
            names = [name for name in (_added_name(value) for value in added.get(row["id"], [])[:4]) if name]
            record.update({"id": f"f{index + 1}", "paths": names, "run": run_names.get(placed.get("run_id")),
                           "group": group_names.get(placed.get("group_id"))})
            if field_links is not None:
                field_links.append(ProposalFieldLink(token=f"f{index + 1}", field_id=row["id"]))
    groups = [label for label in group_names.values() if label] if extended else []
    design = ({"layout": experiment.get("layout"), "runs": [label for label in run_names.values() if label][:50],
               "groups": groups} if extended and experiment.get("layout") in ("single", "pair") and 1 <= len(groups) <= 2 else None)
    image_metadata: list[dict] = []
    for row in region:
        info = row["image_info"]
        calibration = info.get("calibration") or {}
        image = {"width": info["shape"][1], "height": info["shape"][0], "axes": "YX",
                 "input_mode": info.get("input_mode", "native"),
                 "pixel_size_x_um": calibration.get("pixel_size_x_um"),
                 "pixel_size_y_um": calibration.get("pixel_size_y_um")}
        if image not in image_metadata and len(image_metadata) < 8:
            image_metadata.append(image)
    context = ProposalContext.model_validate(dict(
        protocol=protocol, design=design, goal=goal, channels=channels, field_count=len(rows), condition_count=len(conditions),
        units_known=_complete(rows, "experimental_unit") and _complete(rows, "condition"), pairing_known=pairing_known,
        units_per_condition=unit_counts, complete_pair_count=len(pair_groups) if pairing_known else 0,
        supplied_regions=bool(region) and all(row["image_info"].get("labels_array") or row["id"] in adopted_cells for row in region),
        # This route plans the image cohort, not unrelated numerical tables.
        measured_table=False, background_available=background_available,
        current_background={"mode": background_mode} if background_mode else None,
        current_gfp=current_gfp, negative_control_fields_known=registered_controls,
        acquired_dates_known=_complete(rows, "acquisition_date"),
        image_metadata=image_metadata,
        fields=field_records,
    ))
    return context, links


def _text(value) -> str | None:
    return value.strip()[:120] if isinstance(value, str) and value.strip() else None


def _label(value) -> str | None:
    """A run or group name of the design (at most 24 characters, as the design stores it)."""
    return value if isinstance(value, str) and value.strip() and len(value) <= 24 else None


_ABSOLUTE = re.compile(r"^(?:/|~|[A-Za-z]:)")


def _added_name(value) -> str | None:
    """A name a file was added with, relative to the folder the researcher chose. An absolute path is never sent:
    only its file name is. Empty, `.` and `..` segments are dropped."""
    if not isinstance(value, str):
        return None
    path = value.replace("\\", "/")
    if _ABSOLUTE.match(path):
        path = path.rsplit("/", 1)[-1]
    text = "/".join(part for part in path.split("/") if part.strip() and part not in (".", ".."))
    if len(text) > 255:
        text = text.rsplit("/", 1)[-1]
    return text[:255] or None


def _field_record(row, display_name: str | None) -> dict:
    """A field's researcher-visible name and recorded metadata; never a path."""
    metadata = row.get("metadata") or {}
    name = display_name or metadata.get("filename") or metadata.get("display_name")
    if isinstance(name, str):
        name = name.replace("\\", "/").rsplit("/", 1)[-1]
    return {"name": _text(name), **{key: _text(metadata.get(key))
                                   for key in ("condition", "experimental_unit", "pair", "acquisition_date")}}


PREVIEW_SIDE = 512
# Auto-contrast for the model's previews: a few saturated or hot pixels must not turn the whole field dark.
PREVIEW_PERCENTILES = (0.1, 99.9)


def _block_mean(pixels: np.ndarray, side: int) -> np.ndarray:
    """Reduce a 2D plane to at most about `side` pixels a side by averaging square blocks, one band of rows at a time.

    Averaging keeps small structures (puncta, nucleoli of 1-3 px) visible where taking every n-th pixel would drop them,
    and reading one band at a time keeps a memory-mapped field from being loaded whole.
    """
    step = max(1, -(-max(pixels.shape[:2]) // side))
    if step == 1:
        return np.asarray(pixels, dtype=np.float32)
    height, width = (pixels.shape[0] // step) * step, (pixels.shape[1] // step) * step
    if not height or not width:
        return np.asarray(pixels, dtype=np.float32)
    bands = [np.asarray(pixels[top:top + step, :width], dtype=np.float32).reshape(step, width // step, step).mean(axis=(0, 2))
             for top in range(0, height, step)]
    return np.stack(bands)


def representative_previews(store, wid: str, links: list[ProposalChannelLink], field_id: str | None = None) -> list[dict]:
    """Display-scaled PNG previews (at most 512 px a side, one per channel) of one representative field.

    The selected field when given, otherwise the first registered native field the researcher has not excluded.
    Previews are for the model to see the images; they are display renderings and never measurements.
    """
    _, excluded = _adopted_selection(store, wid)
    rows = [row for row in store.rows(fields, workspace_id=wid) if is_region(row) and row["id"] not in excluded]
    row = next((row for row in rows if row["id"] == field_id), None) if field_id else (rows[0] if rows else None)
    if row is None or row["image_info"].get("input_mode", "native") != "native":
        return []
    previews = []
    for link in links[:6]:
        path = store.safe_path("workspaces", wid, "fields", row["id"], f"channel-{link.channel_id}.npy")
        if not path.is_file():
            continue
        pixels = _block_mean(np.load(path, allow_pickle=False, mmap_mode="r"), PREVIEW_SIDE)
        png, _display = render_preview_with_display({link.channel_id: pixels}, link.channel_id, *PREVIEW_PERCENTILES, 1,
                                                    field_id=row["id"], composite=False)
        image: Image.Image = Image.open(io.BytesIO(png))
        image.thumbnail((PREVIEW_SIDE, PREVIEW_SIDE))
        if image.mode not in ("L", "RGB"):
            image = image.convert("RGB")
        output = io.BytesIO()
        image.save(output, format="PNG", optimize=True)
        encoded = base64.b64encode(output.getvalue()).decode("ascii")
        if len(encoded) <= 700_000:
            previews.append({"channel": link.token, "png_base64": encoded})
    return previews


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


def _continuation_context(context: ProposalContext, links: list[ProposalChannelLink], body: ProposalDraftRequest) -> ProposalContext:
    """Normalize only closed settings; never send private channel IDs or arbitrary JSON."""
    channel_tokens = {link.channel_id: link.token for link in links}

    def normalized(value, depth=0):
        if depth > 12:
            raise ValueError("proposal_continuation_invalid")
        if isinstance(value, list):
            if len(value) > 8:
                raise ValueError("proposal_continuation_invalid")
            return [normalized(item, depth + 1) for item in value]
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                if key in ("channel", "token") and item is not None:
                    if not isinstance(item, str) or item not in channel_tokens:
                        raise ValueError("proposal_continuation_channel_unknown")
                    result[key] = channel_tokens[item]
                else:
                    result[key] = normalized(item, depth + 1)
            return result
        return value

    current = DraftProcessing.model_validate(normalized(body.current_processing)) if body.current_processing else None
    prior = normalized(body.previous_proposal) if body.previous_proposal else None
    if isinstance(prior, dict) and context.protocol != "1.3.0":
        # A prompt before 2026-11-26.1 reads the previous proposal without the kind of request.
        prior = {key: value for key, value in prior.items() if key not in INTENT_FIELDS}
    previous = ProposalDraft.model_validate(prior) if prior else None
    if not context.field_count and current is not None:
        raise ValueError("proposal_continuation_requires_images")
    return ProposalContext.model_validate({**context.model_dump(), "current_processing":current,
        "previous_goal":body.previous_goal, "previous_proposal":previous})


def register_proposal_routes(api, store, settings, owner, workspace, credentials=None):
    Owner = Annotated[str, Depends(owner)]

    @api.get("/v1/ai/status", response_model=AiStatus)
    def ai_status(who: Owner):
        explicit = bool(settings.proposal_url or settings.proposal_token)
        source: Literal["operator", "account", "none"] = "operator" if explicit else "account" if credentials is not None else "none"
        try:
            configured = service_url(effective_settings(settings, credentials))
        except (ValueError, OSError):
            return AiStatus(state="misconfigured", source=source)
        if configured:
            return AiStatus(state="available", source=source)
        if explicit:
            return AiStatus(state="misconfigured", source=source)
        return AiStatus(state="sign_in_required" if credentials is not None else "unconfigured", source=source)

    @api.post("/v1/ai/check", response_model=AiCompatibility)
    def ai_check(who: Owner):
        """An explicit, protocol-only check. Never accept a URL/token or send an idempotency key."""
        from .proposal_preflight import check_versions, probe_status

        service = effective_settings(settings, credentials)
        try:
            if service_url(service) is None:
                return AiCompatibility(state="unconfigured")
        except ValueError:
            return AiCompatibility(state="misconfigured")
        responses = []
        def probe(request, timeout):
            response = probe_status(request, timeout=min(timeout, 15))
            responses.append(response)
            return response
        checks = check_versions(service.proposal_url or "", service.proposal_token or "", probe,
            proposal_prompt=service.proposal_prompt_version, discussion_prompt=service.discussion_prompt_version,
            allow_loopback=True)
        if all(check[2] for check in checks):
            return AiCompatibility(state="compatible")
        if not responses:
            return AiCompatibility(state="misconfigured")
        if any(status in (401, 403) for status, _ in responses):
            return AiCompatibility(state="unauthorized")
        if any(status == 400 and code in ("request_invalid", "prompt_version_unsupported") for status, code in responses):
            return AiCompatibility(state="incompatible")
        return AiCompatibility(state="unavailable")

    def open_message(conn, wid: str, body: ProposalDraftRequest, now: float) -> str:
        """Writes the message as sent (or reopens it for its 「再送」) before the model is called (#284 W2)."""
        values: dict = {"state": "pending", "reply": None, "applicable": None, "reasons": [], "stage": None,
                  "request_id": None, "draft_id": None}
        if body.message_id:
            found = conn.execute(select(assistant_messages.c.id).where(assistant_messages.c.id == body.message_id,
                assistant_messages.c.workspace_id == wid)).first()
            if found is None:
                raise HTTPException(404, "assistant_message_not_found")
            conn.execute(update(assistant_messages).where(assistant_messages.c.id == body.message_id).values(**values))
            return body.message_id
        mid = str(uuid.uuid4())
        conn.execute(assistant_messages.insert().values(id=mid, workspace_id=wid, field_id=body.field_id, created=now,
            text=body.goal, effect="none", **values))
        return mid

    def close_message(mid: str, **values):
        with store.transaction() as conn:
            conn.execute(update(assistant_messages).where(assistant_messages.c.id == mid).values(**values))
            return message_view(conn.execute(select(assistant_messages).where(assistant_messages.c.id == mid)).mappings().one())

    @api.get("/v1/workspaces/{wid}/assistant-messages", response_model=AssistantMessages)
    def list_messages(wid: str, who: Owner):
        workspace(wid, who)
        with store.engine.connect() as conn:
            rows = conn.execute(select(assistant_messages).where(assistant_messages.c.workspace_id == wid)
                                .order_by(assistant_messages.c.created, assistant_messages.c.id)).mappings().all()
        return AssistantMessages(messages=[message_view(row) for row in rows])

    @api.patch("/v1/workspaces/{wid}/assistant-messages/{mid}", response_model=AssistantMessage)
    def record_effect(wid: str, mid: str, body: AssistantEffect, who: Owner):
        """What the researcher did with an answer (applied its settings, ran it). The answer never does it."""
        workspace(wid, who)
        with store.transaction() as conn:
            row = conn.execute(select(assistant_messages).where(assistant_messages.c.id == mid,
                assistant_messages.c.workspace_id == wid)).mappings().first()
            if row is None:
                raise HTTPException(404, "assistant_message_not_found")
            if body.effect != "none" and not (row["state"] == "answered" and row["applicable"]):
                raise HTTPException(409, "assistant_message_not_applicable")
            conn.execute(update(assistant_messages).where(assistant_messages.c.id == mid).values(effect=body.effect))
            return message_view(conn.execute(select(assistant_messages).where(assistant_messages.c.id == mid)).mappings().one())

    @api.post("/v1/workspaces/{wid}/proposal-drafts", response_model=ProposalDraftResponse)
    def draft_proposal(wid: str, body: ProposalDraftRequest, who: Owner):
        workspace(wid, who)
        if body.transmission_confirmed is not True:
            raise HTTPException(428, "proposal_transmission_not_confirmed")
        protocol = context_protocol(settings.proposal_prompt_version)
        field_links: list[ProposalFieldLink] = []
        try:
            context, links = build_context(store, wid, body.goal, body.field_id, protocol=protocol, field_links=field_links)
            context = _continuation_context(context, links, body)
        except (ValueError, HTTPException) as error:
            # The message is kept with why it could not be sent, under the message itself.
            code = error.detail if isinstance(error, HTTPException) and isinstance(error.detail, str) else "proposal_context_unsupported"
            status = error.status_code if isinstance(error, HTTPException) else 409
            with store.transaction() as conn:
                mid = open_message(conn, wid, body, time.time())
            close_message(mid, state="failed", reasons=[code], stage="context")
            raise HTTPException(status, code) from None
        source_stamp = _source_stamp(store, wid)
        service = effective_settings(settings, credentials)
        identity = {"context": context_sha256(context), "protocol": PROPOSAL_PROTOCOL,
                    "model": settings.proposal_model, "prompt": settings.proposal_prompt_version,
                    "service": service.proposal_url, "channels": [link.model_dump() for link in links], "source": source_stamp,
                    "previews": body.include_previews}
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        request_id = str(uuid.uuid4())
        now = time.time()
        with store.transaction() as conn:
            live = conn.execute(select(workspaces).where(workspaces.c.id == wid)).mappings().first()
            if not store.workspace_is_live(live, now) or live["owner"] != who:
                raise HTTPException(404, "workspace_not_found")
            cached = conn.execute(select(proposal_drafts).where(
                proposal_drafts.c.workspace_id == wid, proposal_drafts.c.cache_key == key)).mappings().first()
            if cached and cached["state"] == "complete":
                # The same question in the same context: answered from the record, the model is not called.
                mid = open_message(conn, wid, body, now)
                cached_proposal = ValidatedProposal.model_validate(cached["proposal"])
                conn.execute(update(assistant_messages).where(assistant_messages.c.id == mid).values(
                    state="answered", applicable=_applicable(cached_proposal.draft), draft_id=cached["id"], request_id=cached["request_id"],
                    reply=reply_text(cached_proposal.draft)))
                row = conn.execute(select(assistant_messages).where(assistant_messages.c.id == mid)).mappings().one()
                return ProposalDraftResponse(proposal=cached_proposal, channels=links, message=message_view(row), fields=field_links)
            if cached:
                if cached["state"] == "pending" and cached["lease_until"] > now:
                    raise HTTPException(409, "proposal_request_in_progress")
                if not body.retry_failed and cached["state"] != "unbilled":
                    # A timeout may already have incurred cost; never silently pay again.
                    raise HTTPException(409, "proposal_explicit_retry_required")
                draft_id = cached["id"]
                conn.execute(update(proposal_drafts).where(proposal_drafts.c.id == cached["id"]).values(
                    request_id=request_id, state="pending", lease_until=now + settings.proposal_timeout_seconds + 30))
            else:
                draft_id = str(uuid.uuid4())
                conn.execute(proposal_drafts.insert().values(id=draft_id, workspace_id=wid, cache_key=key,
                    request_id=request_id, state="pending", created=now,
                    lease_until=now + settings.proposal_timeout_seconds + 30))
            mid = open_message(conn, wid, body, now)
            conn.execute(update(assistant_messages).where(assistant_messages.c.id == mid).values(request_id=request_id))
        proposal = None
        unbilled = False
        refused: ProposalRejected | None = None
        try:
            try:
                previews = representative_previews(store, wid, links, body.field_id) if body.include_previews else []
            except Exception:
                # Previews are optional: an unreadable array or image sends the request without them.
                previews = []
            payload = request_draft(service, context, request_id, previews)
            if payload["model"] not in {settings.proposal_model, *settings.proposal_models} or payload["prompt_version"] != settings.proposal_prompt_version:
                raise ProposalServiceError(502, "proposal_service_version_mismatch")
            proposal = validate_draft(context, payload.get("draft"), model=payload["model"],
                                      prompt_version=payload["prompt_version"])
        except ProposalServiceError as error:
            unbilled = not error.may_have_charged
            close_message(mid, state="failed", reasons=[error.code], stage="service")
            raise HTTPException(error.status, error.code) from None
        except ProposalRejected as error:
            # Codes only: the draft text itself is never echoed into logs.
            if error.rationale is None:
                close_message(mid, state="failed", reasons=error.codes, stage="validation")
                if "proposal_association_same_region_required" in error.codes:
                    raise HTTPException(502, "proposal_association_same_region_required") from None
                raise HTTPException(502, {"code": "proposal_rejected", "reasons": error.codes}) from None
            refused = error
        except ValueError:
            close_message(mid, state="failed", reasons=["proposal_service_misconfigured"], stage="service")
            raise HTTPException(503, "proposal_service_misconfigured") from None
        except Exception:
            close_message(mid, state="failed", reasons=["proposal_internal_error"], stage="service")
            raise
        finally:
            if proposal is None:
                with store.transaction() as conn:
                    conn.execute(update(proposal_drafts).where(proposal_drafts.c.workspace_id == wid,
                        proposal_drafts.c.cache_key == key, proposal_drafts.c.request_id == request_id,
                        proposal_drafts.c.state == "pending").values(state="unbilled" if unbilled else "failed"))
        if refused is not None:
            # The answer is shown; its settings are not applicable. The cached request stays failed, so the same
            # question needs an explicit resend as before (the answer is already in the message).
            message = close_message(mid, state="answered", applicable=False, reasons=refused.codes, stage="validation",
                                    reply=answer_text(refused.rationale or "", refused.missing_information, refused.answer))
            return ProposalDraftResponse(proposal=None, channels=links, message=message, fields=field_links)
        assert proposal is not None  # Every other path above returned or raised.
        workspace(wid, who)  # Revocation/expiry during the external call blocks publication.
        try:
            refreshed, refreshed_links = build_context(store, wid, body.goal, body.field_id, protocol=protocol)
            refreshed = _continuation_context(refreshed, refreshed_links, body)
            changed = (context_sha256(refreshed) != context_sha256(context) or refreshed_links != links
                       or _source_stamp(store, wid) != source_stamp)
        except (ValueError, HTTPException):
            changed = True
        if changed:
            # Release the request instead of leaving it pending until the lease ends.
            with store.transaction() as conn:
                conn.execute(update(proposal_drafts).where(proposal_drafts.c.workspace_id == wid,
                    proposal_drafts.c.cache_key == key, proposal_drafts.c.request_id == request_id,
                    proposal_drafts.c.state == "pending").values(state="failed"))
            close_message(mid, state="failed", reasons=["proposal_context_changed"], stage="context")
            raise HTTPException(409, "proposal_context_changed")
        with store.transaction() as conn:
            result = conn.execute(update(proposal_drafts).where(proposal_drafts.c.workspace_id == wid,
                proposal_drafts.c.cache_key == key, proposal_drafts.c.request_id == request_id).values(
                    state="complete", proposal=proposal.model_dump(mode="json")))
            superseded = result.rowcount != 1
        if superseded:
            close_message(mid, state="failed", reasons=["proposal_request_superseded"], stage="service")
            raise HTTPException(409, "proposal_request_superseded")
        message = close_message(mid, state="answered", applicable=_applicable(proposal.draft), draft_id=draft_id, reply=reply_text(proposal.draft))
        return ProposalDraftResponse(proposal=proposal, channels=links, message=message, fields=field_links)
