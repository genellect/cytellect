import time

from cytellect_api.app import create_app
from cytellect_api.config import Settings
from cytellect_api.db import jobs
from cytellect_worker.main import cleanup, process_one
from fastapi.testclient import TestClient

HEADERS = {"origin": "http://test", "x-cytellect-request": "1"}


def authenticated(tmp_path):
    settings = Settings(tmp_path, app_origin="http://test", secure_cookies=False)
    app = create_app(settings)
    client = TestClient(app)
    token = app.state.store.invite()
    response = client.post("/v1/invitations/redeem", json={"token": token}, headers=HEADERS)
    assert response.status_code == 200
    return client, app, settings


def test_mutation_requires_origin_and_csrf(tmp_path):
    client, _, _ = authenticated(tmp_path)
    assert client.post("/v1/workspaces", json={"title": "x"}).status_code == 403
    assert client.post("/v1/workspaces", json={"title": "x"}, headers={"origin": "http://evil"}).status_code == 403
    assert client.post("/v1/workspaces", json={"title": "x"}, headers=HEADERS).status_code == 201


def test_ownership_is_enforced_without_leaking_existence(tmp_path):
    first, app, _ = authenticated(tmp_path)
    workspace = first.post("/v1/workspaces", json={"title": "owner"}, headers=HEADERS).json()
    second = TestClient(app)
    token = app.state.store.invite()
    assert second.post("/v1/invitations/redeem", json={"token": token}, headers=HEADERS).status_code == 200
    assert second.get(f"/v1/workspaces/{workspace['id']}").status_code == 404


def test_synthetic_analysis_worker_vertical_slice(tmp_path):
    client, app, settings = authenticated(tmp_path)
    workspace = client.post("/v1/workspaces", json={"title": "synthetic"}, headers=HEADERS).json()
    created = client.post(f"/v1/workspaces/{workspace['id']}/synthetic", headers=HEADERS)
    assert created.status_code == 201
    ids = created.json()["field_ids"]
    backgrounds = {field_id: {"polygon": [[0, 0], [15, 0], [15, 15], [0, 15]], "confirmed": True} for field_id in ids}
    queued = client.post(f"/v1/workspaces/{workspace['id']}/analyses", json={"backgrounds": backgrounds}, headers=HEADERS)
    assert queued.status_code == 202
    assert process_one(app.state.store, settings)
    revision_id = queued.json()["revision_id"]
    revision = client.get(f"/v1/revisions/{revision_id}").json()
    assert revision["state"] == "succeeded"
    report = client.get(f"/v1/revisions/{revision_id}/measurements").json()
    assert len(report["cells"]) == 54
    assert report["field_failures"] == []
    stored = app.state.store.one(jobs, id=queued.json()["job_id"])
    assert stored["state"] == "succeeded"


def test_cleanup_revokes_expired_workspace_files(tmp_path):
    client, app, _ = authenticated(tmp_path)
    workspace = client.post("/v1/workspaces", json={"title": "expired"}, headers=HEADERS).json()
    folder = app.state.store.safe_path("workspaces", workspace["id"])
    folder.mkdir(parents=True)
    with app.state.store.transaction() as conn:
        from cytellect_api.db import workspaces
        from sqlalchemy import update
        conn.execute(update(workspaces).where(workspaces.c.id == workspace["id"]).values(expires=time.time() - 1))
    assert client.get(f"/v1/workspaces/{workspace['id']}").status_code == 404
    assert cleanup(app.state.store) == {"workspaces_removed": 1}
    assert not folder.exists()
