"""Metadata-only retention checks: no images, pixel arrays, engines or workers run."""
import time

import pytest
from cytellect_api.app import create_app
from cytellect_api.config import Settings
from cytellect_api.db import Store, digest, jobs, sessions, uid, workspaces
from cytellect_worker.child import lease_is_live
from cytellect_worker.main import cleanup
from fastapi.testclient import TestClient
from sqlalchemy import update


def workspace_record(store, *, expires=1, deleted=False):
    wid = uid()
    with store.transaction() as conn:
        conn.execute(workspaces.insert().values(
            id=wid, owner="metadata-owner", title="Retention check", created=1,
            expires=expires, deleted=deleted, bytes=0))
    return wid


def queued_job(store, wid):
    jid = uid()
    with store.transaction() as conn:
        conn.execute(jobs.insert().values(
            id=jid, workspace_id=wid, revision_id="metadata-only-revision", kind="export", state="queued", payload={},
            created=1, attempts=0))
    return jid


@pytest.mark.parametrize("mode", ["ttl", "manual"])
def test_past_deadline_claim_and_cleanup(tmp_path, mode):
    store = Store(tmp_path, workspace_retention_mode=mode)
    wid = workspace_record(store)
    folder = store.safe_path("workspaces", wid)
    folder.mkdir(parents=True)
    (folder / "metadata-only.txt").write_text("retention sentinel", encoding="utf-8")
    queued_job(store, wid)
    job = store.claim()
    if mode == "ttl":
        assert job is None
        assert cleanup(store)["workspaces_removed"] == 1
    else:
        assert job is not None
        assert store.heartbeat(job)
        assert not store.heartbeat({**job, "lease": "stale-metadata-lease"})
        assert not store.finish({**job, "lease": "stale-metadata-lease"})
        assert store.finish(job, error="metadata_only_check")
        assert cleanup(store)["workspaces_removed"] == 0
        assert (folder / "metadata-only.txt").read_text(encoding="utf-8") == "retention sentinel"
        assert store.workspace_view(store.one(workspaces, id=wid))["expires"] is None
        assert store.one(workspaces, id=wid)["expires"] == 1
        with store.transaction() as conn:
            conn.execute(update(workspaces).where(workspaces.c.id == wid).values(deleted=True))
            conn.execute(update(jobs).where(jobs.c.id == job["id"]).values(lease_until=0))
        assert not store.workspace_is_live(store.one(workspaces, id=wid))
        assert cleanup(store)["workspaces_removed"] == 1


def test_manual_policy_survives_restart_and_rejects_ttl(tmp_path):
    legacy = Store(tmp_path)
    wid = workspace_record(legacy)
    manual = Store(tmp_path, workspace_retention_mode="manual")
    assert manual.workspace_is_live(manual.one(workspaces, id=wid))
    with pytest.raises(ValueError, match="manual_to_ttl_forbidden"):
        Store(tmp_path)
    with pytest.raises(ValueError, match="manual_to_ttl_forbidden"):
        cleanup(legacy)
    with pytest.raises(ValueError, match="manual_to_ttl_forbidden"):
        legacy.claim()
    assert Store(tmp_path, workspace_retention_mode="manual").workspace_is_live(
        manual.one(workspaces, id=wid))


def test_mode_validation_and_default(tmp_path, monkeypatch):
    monkeypatch.setenv("CYTELLECT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("CYTELLECT_WORKSPACE_RETENTION_MODE", raising=False)
    assert Settings.from_env().workspace_retention_mode == "ttl"
    monkeypatch.setenv("CYTELLECT_WORKSPACE_RETENTION_MODE", "manual")
    assert Settings.from_env().retention_policy == {"retention_mode": "manual", "retention_hours": None}
    monkeypatch.setenv("CYTELLECT_WORKSPACE_RETENTION_MODE", "unlimited")
    with pytest.raises(ValueError, match="mode_invalid"):
        Settings.from_env()


class MetadataParent:
    def is_running(self):
        return True

    def create_time(self):
        return 1


def test_child_watchdog_keeps_lease_and_delete_guards(tmp_path):
    store = Store(tmp_path, workspace_retention_mode="manual")
    wid = workspace_record(store)
    queued_job(store, wid)
    job = store.claim()
    parent = MetadataParent()
    assert lease_is_live(store, job, parent, 1)
    assert not lease_is_live(store, {**job, "lease": "stale"}, parent, 1)
    assert not lease_is_live(store, job, parent, 2)
    with store.transaction() as conn:
        conn.execute(update(jobs).where(jobs.c.id == job["id"]).values(lease_until=0))
    assert not lease_is_live(store, job, parent, 1)
    with store.transaction() as conn:
        conn.execute(update(jobs).where(jobs.c.id == job["id"]).values(lease_until=time.time()+60))
        conn.execute(update(workspaces).where(workspaces.c.id == wid).values(deleted=True))
    assert not lease_is_live(store, job, parent, 1)
    assert not store.heartbeat(job)
    assert not store.finish(job)


@pytest.mark.parametrize("mode,expected", [("ttl", 404), ("manual", 200)])
def test_actual_api_metadata_access_touch_owner_and_session_expiry(tmp_path, mode, expected):
    settings = Settings(tmp_path, secure_cookies=False, workspace_retention_mode=mode)
    app = create_app(settings)
    store = app.state.store
    wid = workspace_record(store)
    # These deliberately non-secret strings are metadata-only test identities.
    token = "metadata-only-session"
    other = "metadata-only-other"
    with store.transaction() as conn:
        for value, owner in [(token, "metadata-owner"), (other, "other-owner")]:
            conn.execute(sessions.insert().values(digest=digest(value), owner=owner,
                                                 expires=time.time()+60, revoked=False))
    with TestClient(app) as client:
        client.cookies.set(settings.cookie_name, token)
        headers = {"Origin": settings.app_origin, "X-Cytellect-Request": "1"}
        response = client.get(f"/v1/workspaces/{wid}")
        assert response.status_code == expected
        assert len(client.get("/v1/workspaces").json()) == (1 if mode == "manual" else 0)
        assert client.post(f"/v1/workspaces/{wid}/touch", headers=headers).status_code == expected
        assert store.one(workspaces, id=wid)["expires"] == 1
        policy = client.get("/v1/session").json()
        assert policy["retention_mode"] == mode
        assert policy["retention_hours"] == (None if mode == "manual" else 24)
        if mode == "manual":
            assert response.json()["expires"] is None
        # Empty request only: exercise the upload authorization guard without
        # supplying an image, invoking decoding or writing an upload.
        assert client.post(f"/v1/workspaces/{wid}/region-fields", headers=headers).status_code == (
            415 if mode == "manual" else 404)
        client.cookies.set(settings.cookie_name, other)
        assert client.get(f"/v1/workspaces/{wid}").status_code == 404
        client.cookies.set(settings.cookie_name, token)
        assert client.delete(f"/v1/workspaces/{wid}", headers=headers).status_code == expected
        assert client.get(f"/v1/workspaces/{wid}").status_code == 404
        with store.transaction() as conn:
            conn.execute(update(sessions).where(sessions.c.digest == digest(token)).values(expires=0))
        assert client.get(f"/v1/workspaces/{wid}").status_code == 401
        assert client.get("/v1/session").status_code == 401
