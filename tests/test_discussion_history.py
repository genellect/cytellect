"""Synthetic saved-result wiring: histories stay on their comparison and owner, across reloads."""
import copy
import json

from cytellect_analysis.discussion_contracts import DISCUSSION_PROMPT_VERSION
from cytellect_api import discussions
from cytellect_api.app import create_app
from cytellect_api.config import Settings
from cytellect_api.db import jobs
from cytellect_api.storage import write_json
from fastapi.testclient import TestClient
from test_result_discussion_api import DRAFT, MODEL, client_for, post, saved_job


def next_result(store, source, jid, *, metric=None, kind="statistics"):
    original = store.one(jobs, id=source)
    result = json.loads(store.safe_path(original["result_dir"], "result.json").read_text(encoding="utf-8"))
    result = copy.deepcopy(result)
    result["revision_id"] = "new-revision"
    if metric:
        result["spec"]["selection"]["metric"] = metric
    path = store.safe_path("workspaces", original["workspace_id"], "jobs", jid)
    path.mkdir(parents=True)
    write_json(path / "result.json", result)
    with store.transaction() as conn:
        conn.execute(jobs.insert().values(id=jid, workspace_id=original["workspace_id"], revision_id="new-revision",
            kind=kind, state="succeeded", created=original["created"] + 1,
            result_dir=str(path.relative_to(store.root)), payload={"mode": "region-experimental-unit", "version": "2.0.0"}))
    return jid


def test_previous_discussion_is_separate_from_the_current_result_and_persists(tmp_path, monkeypatch):
    calls = []
    def answer(*args):
        calls.append(True)
        return {"model": MODEL, "prompt_version": DISCUSSION_PROMPT_VERSION, "draft": DRAFT}
    monkeypatch.setattr(discussions, "post_to_service", answer)
    client, app = client_for(tmp_path)
    original, store = saved_job(client, app)
    assert post(client, original).status_code == 200
    current = next_result(store, original, "recalculated")
    other = next_result(store, original, "other-measure", metric="median_corrected")
    history = client.get(f"/v1/jobs/{current}/discussion-history").json()
    assert history["current"] is None and history["previous"]["job_id"] == original
    assert client.get(f"/v1/jobs/{current}/discussion").json() is None
    assert client.get(f"/v1/jobs/{other}/discussion-history").json() == {"current": None, "previous": None}
    assert len(calls) == 1
    # A new local API process and a disabled AI service still read the stored history.
    reopened = TestClient(create_app(Settings(tmp_path, app_origin="http://test", secure_cookies=False)))
    reopened.cookies.update(client.cookies)
    assert reopened.get(f"/v1/jobs/{current}/discussion-history").json() == history
    assert post(client, current).status_code == 200
    history = client.get(f"/v1/jobs/{current}/discussion-history").json()
    assert history["current"]["job_id"] == current and history["previous"]["job_id"] == original
    assert len(calls) == 2
    stranger, _ = client_for(tmp_path)
    assert stranger.get(f"/v1/jobs/{current}/discussion-history").status_code == 404


def test_history_of_a_redrawn_figure_uses_its_source_comparison(tmp_path, monkeypatch):
    monkeypatch.setattr(discussions, "post_to_service", lambda *args: {
        "model": MODEL, "prompt_version": DISCUSSION_PROMPT_VERSION, "draft": DRAFT})
    client, app = client_for(tmp_path)
    original, store = saved_job(client, app)
    assert post(client, original).status_code == 200
    record = store.one(jobs, id=original)
    with store.transaction() as conn:
        conn.execute(jobs.insert().values(id="figure", workspace_id=record["workspace_id"], revision_id=record["revision_id"],
            kind="figure-render", state="succeeded", created=record["created"] + 1, payload={"source_job_id": original}))
    view = client.get("/v1/jobs/figure/discussion-history").json()
    assert view["current"]["job_id"] == original
