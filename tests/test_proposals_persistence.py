"""No real provider calls: scientific proposal and billing-state invariants."""
import json
import threading
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor

import pytest
from cytellect_analysis.proposal_contracts import ProposalContext
from cytellect_analysis.proposal_validation import validate_draft
from cytellect_api import proposals
from cytellect_api.app import create_app
from cytellect_api.db import fields, proposal_drafts, revisions, workspaces
from fastapi.testclient import TestClient
from sqlalchemy import update
from test_api_worker import HEADERS
from test_proposals import ACTIN_DRAFT, CONTEXT, FakeResponse, codes, configured, draft
from test_region_api import make_field, region_request

BODY = {"transmission_confirmed": True}
REPLY = json.dumps({"draft": ACTIN_DRAFT, "model": "gpt-6.1-sol", "prompt_version": "2026-10-06.1"}).encode()


def test_ratio_requires_background_and_paired_three_conditions_are_unsupported():
    assert "proposal_background_not_available" in codes(draft(), CONTEXT.model_copy(update={"background_available": False}))
    paired = draft(statistics={"kind": "comparison", "test": "paired-t", "omnibus": None, "association": None})
    assert "proposal_paired_condition_count_unsupported" in codes(
        paired, CONTEXT.model_copy(update={"condition_count": 3, "pairing_known": True}))
    assert "proposal_independent_units_insufficient" in codes(draft(), CONTEXT.model_copy(update={"units_per_condition": [1, 3]}))
    assert "proposal_design_requires_paired" in codes(draft(), CONTEXT.model_copy(update={"pairing_known": True}))


def test_association_axes_and_regions_are_executable_and_multiple_analyses_are_separate():
    metric = {"metric": "mean_raw", "channel": "c3", "region": "nucleus"}
    ratio = {"metric": "ncl_log2_nucleoplasm_over_nucleoli", "channel": "ncl", "region": None}
    association = {"kind": "association", "test": None, "omnibus": None, "association": "spearman", "x": metric, "y": ratio}
    raw = draft(additional_analyses=[association], figures=[
        *draft()["figures"], {"kind": "association-scatter", **ratio, "analysis_index": 1}])
    assert len(validate_draft(CONTEXT, raw, model="m", prompt_version="p").draft.additional_analyses) == 1
    association["y"] = metric
    assert "proposal_association_axes_identical" in codes(raw)
    assert "proposal_metric_region_required" in codes(draft(metrics=[{"metric": "mean_raw", "channel": "c3"}]))
    with pytest.raises(ValueError, match="proposal_context_channel_duplicate"):
        ProposalContext(field_count=1, channels=[{"token": "a"}, {"token": "a"}])


def test_cached_proposal_survives_restart_and_checks_ownership(tmp_path, monkeypatch):
    client, wid, calls = configured(tmp_path, monkeypatch, lambda request: FakeResponse(REPLY))
    path = f"/v1/workspaces/{wid}/proposal-drafts"
    first = client.post(path, json=BODY, headers=HEADERS)
    assert first.status_code == 200, first.text
    app = create_app(client.app.state.settings)
    restarted = TestClient(app)
    restarted.cookies.update(client.cookies)
    assert restarted.post(path, json=BODY, headers=HEADERS).json() == first.json()
    assert len(calls) == 1
    stranger = TestClient(app)
    stranger.post("/v1/invitations/redeem", json={"token": app.state.store.invite()}, headers=HEADERS)
    assert stranger.post(path, json=BODY, headers=HEADERS).status_code == 404
    object.__setattr__(app.state.settings, "proposal_prompt_version", "different")
    assert restarted.post(path, json=BODY, headers=HEADERS).json()["detail"] == "proposal_service_version_mismatch"
    assert len(calls) == 2


def test_concurrent_requests_make_only_one_provider_call(tmp_path, monkeypatch):
    entered, release = threading.Event(), threading.Event()

    def blocked(request):
        entered.set()
        assert release.wait(10)
        return FakeResponse(REPLY)

    client, wid, calls = configured(tmp_path, monkeypatch, blocked)
    path = f"/v1/workspaces/{wid}/proposal-drafts"
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(client.post, path, json=BODY, headers=HEADERS)
        assert entered.wait(10)
        second = client.post(path, json=BODY, headers=HEADERS)
        release.set()
        assert second.status_code == 409 and second.json()["detail"] == "proposal_request_in_progress"
        assert first.result().status_code == 200
    assert len(calls) == 1


def test_timeout_needs_explicit_retry_and_uses_new_provider_request_id(tmp_path, monkeypatch):
    ids = []

    def timeout(request):
        ids.append(request.headers["Idempotency-key"])
        raise urllib.error.URLError("sanitized")

    client, wid, calls = configured(tmp_path, monkeypatch, timeout)
    path = f"/v1/workspaces/{wid}/proposal-drafts"
    assert client.post(path, json=BODY, headers=HEADERS).status_code == 503
    assert client.post(path, json=BODY, headers=HEADERS).json()["detail"] == "proposal_explicit_retry_required"
    assert len(calls) == 1
    assert client.post(path, json={**BODY, "retry_failed": True}, headers=HEADERS).status_code == 503
    assert len(ids) == 2 and ids[0] != ids[1]


def test_background_only_from_current_complete_cohort_and_no_mixed_region_claim(tmp_path, monkeypatch):
    client, wid, _ = configured(tmp_path, monkeypatch, lambda request: FakeResponse(REPLY))
    store = client.app.state.store
    fid = store.rows(fields, workspace_id=wid)[0]["id"]
    assert not proposals.build_context(store, wid, "")[0].background_available
    response = client.post(f"/v1/workspaces/{wid}/region-analyses", json=region_request(fid), headers=HEADERS)
    assert response.status_code == 202, response.text
    assert proposals.build_context(store, wid, "")[0].background_available
    assert make_field(client, wid, labels=False).status_code == 201
    context, _ = proposals.build_context(store, wid, "")
    assert not context.background_available and not context.supplied_regions
    # An old complete revision never lends its background to a newer empty one.
    rid = response.json()["revision_id"]
    with store.transaction() as conn:
        revision = store.one(revisions, id=rid)
        conn.execute(update(revisions).where(revisions.c.id == rid).values(config={**revision["config"], "backgrounds": {}}))
    assert not proposals.build_context(store, wid, "")[0].background_available


def test_expiry_during_provider_call_never_publishes_result(tmp_path, monkeypatch):
    client, wid, _ = configured(tmp_path, monkeypatch, lambda request: FakeResponse(REPLY))
    store = client.app.state.store

    def expire(request, timeout):
        with store.transaction() as conn:
            conn.execute(update(workspaces).where(workspaces.c.id == wid).values(expires=time.time() - 1))
        return FakeResponse(REPLY)

    monkeypatch.setattr(proposals._OPENER, "open", expire)
    assert client.post(f"/v1/workspaces/{wid}/proposal-drafts", json=BODY, headers=HEADERS).status_code == 404
    assert all(row["proposal"] is None for row in store.rows(proposal_drafts, workspace_id=wid))


def test_channel_tokens_are_opaque_and_cannot_collide(tmp_path, monkeypatch):
    client, wid, _ = configured(tmp_path, monkeypatch, lambda request: FakeResponse(REPLY))
    store = client.app.state.store
    row = store.rows(fields, workspace_id=wid)[0]
    info = {**row["image_info"], "channels": [
        {**row["image_info"]["channels"][0], "channel_id": identifier} for identifier in ("A", "a", "ch1")]}
    with store.transaction() as conn:
        conn.execute(update(fields).where(fields.c.id == row["id"]).values(image_info=info))
    context, links = proposals.build_context(store, wid, "")
    assert [item.token for item in context.channels] == ["ch1", "ch2", "ch3"]
    assert [item.channel_id for item in links] == ["A", "a", "ch1"]


def test_cleanup_removes_private_drafts_and_cache_rejects_changed_local_design(tmp_path, monkeypatch):
    from cytellect_worker.main import cleanup

    client, wid, calls = configured(tmp_path, monkeypatch, lambda request: FakeResponse(REPLY))
    store = client.app.state.store
    path = f"/v1/workspaces/{wid}/proposal-drafts"
    assert client.post(path, json=BODY, headers=HEADERS).status_code == 200
    row = store.rows(fields, workspace_id=wid)[0]
    with store.transaction() as conn:
        conn.execute(update(fields).where(fields.c.id == row["id"]).values(metadata={**row["metadata"], "condition": "other"}))
    assert client.post(path, json=BODY, headers=HEADERS).status_code == 200
    assert len(calls) == 2  # Same anonymous counts, different private experimental design.
    assert client.delete(f"/v1/workspaces/{wid}", headers=HEADERS).status_code == 200
    assert client.post(path, json=BODY, headers=HEADERS).status_code == 404
    cleanup(store)
    assert store.rows(proposal_drafts, workspace_id=wid) == []


def test_context_change_during_call_releases_the_request(tmp_path, monkeypatch):
    client, wid, calls = configured(tmp_path, monkeypatch, lambda request: FakeResponse(REPLY))
    stamps = iter(["before", "after"])
    monkeypatch.setattr(proposals, "_source_stamp", lambda store, workspace_id: next(stamps, "after"))
    path = f"/v1/workspaces/{wid}/proposal-drafts"
    changed = client.post(path, json=BODY, headers=HEADERS)
    assert changed.status_code == 409 and changed.json()["detail"] == "proposal_context_changed"
    store = client.app.state.store
    with store.transaction() as conn:
        assert [row.state for row in conn.execute(proposal_drafts.select())] == ["failed"]
    # The changed workspace is a new request; the stale one is not left pending.
    assert client.post(path, json=BODY, headers=HEADERS).status_code == 200
    assert len(calls) == 2
