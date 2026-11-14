"""The discussion route sends only the saved result, checks the draft and stores it with its source.

The proposal service is replaced by a stand-in; no model is called. The saved result comes from the
minimal pixel fixture of test_region_comparison (synthetic numbers for wiring only).
"""
import json
import time

import pytest
from cytellect_analysis.common_statistics import analyze_region_comparison
from cytellect_analysis.discussion_contracts import DISCUSSION_PROMPT_VERSION
from cytellect_api import discussions
from cytellect_api.app import create_app
from cytellect_api.config import Settings
from cytellect_api.db import jobs, result_discussions
from cytellect_api.proposals import ProposalServiceError
from cytellect_api.storage import write_json
from fastapi.testclient import TestClient
from test_api_worker import HEADERS
from test_comparison_estimates_connection import PROTOCOL, request
from test_region_comparison import comparison_fixture

MODEL = "stand-in-model"
DRAFT = {"implications": ["A では B より平均が 2 a.u. 低く、処理で信号が弱まる可能性がある。"],
         "alternatives": ["3 回の実験のうち 1 回は差が小さく、回ごとのばらつきで説明できる余地がある。"],
         "next_steps": ["実験回を増やして、区間が 0 を含まなくなるかを確かめる。"]}


def client_for(tmp_path, *, service=True):
    settings = Settings(tmp_path, app_origin="http://test", secure_cookies=False, proposal_model=MODEL,
                        proposal_url="https://proposal.test" if service else "", proposal_token="token" if service else "")
    app = create_app(settings)
    client = TestClient(app)
    token = app.state.store.invite()
    assert client.post("/v1/invitations/redeem", json={"token": token}, headers=HEADERS).status_code == 200
    return client, app


def saved_job(client, app, *, test="paired-t"):
    """A succeeded statistics job whose result.json is a saved paired comparison with estimates."""
    store = app.state.store
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "discussion"}).json()["id"]
    report, config = comparison_fixture((("A", [3, 8, 2]), ("B", [4, 10, 5])))
    result = analyze_region_comparison(report, config, request(paired=True, test=test, estimates=PROTOCOL))
    folder = store.safe_path("workspaces", wid, "jobs", "statistics")
    folder.mkdir(parents=True)
    write_json(folder / "result.json", result)
    with store.transaction() as conn:
        conn.execute(jobs.insert().values(id="job-1", workspace_id=wid, revision_id=result["revision_id"],
            kind="statistics", state="succeeded", created=time.time(), result_dir=str(folder.relative_to(store.root)),
            payload={"mode": "region-experimental-unit", "version": "2.0.0"}))
    return "job-1", store


@pytest.fixture
def service(monkeypatch):
    calls = []

    def answer(settings, path, content, request_id=None):
        calls.append({"path": path, "content": content})
        return {"model": MODEL, "prompt_version": DISCUSSION_PROMPT_VERSION, "draft": calls[-1].get("draft", DRAFT)}

    monkeypatch.setattr(discussions, "post_to_service", answer)
    return calls


def post(client, job, **body):
    return client.post(f"/v1/jobs/{job}/discussion", headers=HEADERS, json={"transmission_confirmed": True, **body})


def test_sends_only_the_saved_result_and_stores_the_checked_draft(tmp_path, service):
    client, app = client_for(tmp_path)
    job, store = saved_job(client, app)
    response = post(client, job, experiment={"purpose": "処理で信号が変わるかを見る", "cells": "U2OS", "stains": ["phalloidin"]})
    assert response.status_code == 200, response.text
    saved = response.json()["discussion"]
    assert saved["model"] == MODEL and saved["prompt_version"] == DISCUSSION_PROMPT_VERSION
    assert saved["draft"]["implications"] == DRAFT["implications"]
    [call] = service
    assert call["path"] == "/v1/discussions"
    sent = json.dumps(call["content"], ensure_ascii=False)
    # Channel IDs, labels, field IDs, file names, paths and run labels stay local (AC-03).
    for private in ("actin", "Actin", "field", "revision", ".tif", "workspaces", str(tmp_path)):
        assert private not in sent
    result = call["content"]["context"]["result"]
    assert [run["run"] for run in result["runs"]] == ["run 1", "run 2", "run 3"]
    assert result["stain"] == "phalloidin" and result["heading"] is None
    assert client.get(f"/v1/jobs/{job}/discussion").json()["discussion"] == saved
    # The same result and setting reuse the stored discussion instead of paying again.
    assert post(client, job, experiment={"purpose": "処理で信号が変わるかを見る", "cells": "U2OS",
                                         "stains": ["phalloidin"]}).json()["discussion"] == saved
    assert len(service) == 1


def test_nothing_is_sent_without_confirmation_or_a_configured_service(tmp_path, service):
    client, app = client_for(tmp_path)
    job, _ = saved_job(client, app)
    response = client.post(f"/v1/jobs/{job}/discussion", headers=HEADERS, json={})
    assert response.status_code == 428 and response.json()["detail"] == "proposal_transmission_not_confirmed"
    off_client, off_app = client_for(tmp_path / "off", service=False)
    off_job, off_store = saved_job(off_client, off_app)
    response = post(off_client, off_job)
    assert response.status_code == 503 and response.json()["detail"] == "proposal_service_disabled"
    with off_store.engine.connect() as conn:
        assert conn.execute(result_discussions.select()).first() is None
    assert service == []


def test_a_draft_with_a_new_number_is_not_stored_and_needs_an_explicit_retry(tmp_path, monkeypatch):
    client, app = client_for(tmp_path)
    job, store = saved_job(client, app)
    saved_result = next(store.root.rglob("result.json"))
    before = saved_result.read_bytes()
    drafts = [{**DRAFT, "implications": ["平均は 37% 低い。"]}, DRAFT]

    def answer(settings, path, content, request_id=None):
        return {"model": MODEL, "prompt_version": DISCUSSION_PROMPT_VERSION, "draft": drafts.pop(0)}

    monkeypatch.setattr(discussions, "post_to_service", answer)
    response = post(client, job)
    assert response.status_code == 502
    assert response.json()["detail"] == {"code": "discussion_rejected", "reasons": ["discussion_number_not_in_result"]}
    none = client.get(f"/v1/jobs/{job}/discussion")
    assert none.status_code == 200 and none.json() is None
    # A failed call may already have cost money; it is repeated only on an explicit retry (L05).
    assert post(client, job).json()["detail"] == "proposal_explicit_retry_required"
    assert post(client, job, retry_failed=True).status_code == 200
    # The computed result is untouched by either draft (AC-07).
    assert saved_result.read_bytes() == before


def test_service_failures_keep_their_codes_and_a_version_mismatch_is_refused(tmp_path, monkeypatch):
    client, app = client_for(tmp_path)
    job, _ = saved_job(client, app)

    def quota(settings, path, content, request_id=None):
        raise ProposalServiceError(429, "proposal_quota_exhausted")

    monkeypatch.setattr(discussions, "post_to_service", quota)
    response = post(client, job)
    assert response.status_code == 429 and response.json()["detail"] == "proposal_quota_exhausted"
    monkeypatch.setattr(discussions, "post_to_service",
                        lambda *args, **kwargs: {"model": "other", "prompt_version": DISCUSSION_PROMPT_VERSION, "draft": DRAFT})
    response = post(client, job, retry_failed=True)
    assert response.status_code == 502 and response.json()["detail"] == "proposal_service_version_mismatch"


def test_only_a_saved_two_group_comparison_can_be_discussed(tmp_path, service):
    client, app = client_for(tmp_path)
    job, store = saved_job(client, app)
    with store.transaction() as conn:
        conn.execute(jobs.update().where(jobs.c.id == job).values(state="running"))
    assert post(client, job).status_code == 404
    assert client.post("/v1/jobs/missing/discussion", headers=HEADERS, json={"transmission_confirmed": True}).status_code == 404
    assert service == []


def test_a_descriptive_comparison_is_discussed_without_a_test(tmp_path, service):
    """The demo's comparisons are descriptive (independence not confirmed): no contrast, no p value."""
    client, app = client_for(tmp_path)
    job, _ = saved_job(client, app, test="none")
    response = post(client, job)
    assert response.status_code == 200, response.text
    result = service[0]["content"]["context"]["result"]
    assert result["test"] == "none" and result["p_value"] is None and result["difference"] is None


def test_a_redrawn_figure_reads_and_writes_the_discussion_of_its_comparison(tmp_path, service):
    client, app = client_for(tmp_path)
    job, store = saved_job(client, app)
    with store.transaction() as conn:
        source = conn.execute(jobs.select().where(jobs.c.id == job)).mappings().one()
        conn.execute(jobs.insert().values(id="render-1", workspace_id=source["workspace_id"], revision_id=source["revision_id"],
            kind="figure-render", state="succeeded", created=time.time(), result_dir=source["result_dir"],
            payload={"source_job_id": job, "plot": {}, "request_id": "r1"}))
    assert client.get("/v1/jobs/render-1/discussion", headers=HEADERS).json() is None
    drafted = post(client, "render-1")
    assert drafted.status_code == 200, drafted.text
    assert drafted.json()["job_id"] == job
    for jid in (job, "render-1"):
        shown = client.get(f"/v1/jobs/{jid}/discussion", headers=HEADERS).json()
        assert shown["job_id"] == job and shown["discussion"]["draft"]["implications"] == DRAFT["implications"]
    assert len(service) == 1
