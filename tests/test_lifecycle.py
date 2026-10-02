"""Security and immutable-version integration using synthetic data only."""

import io
import zipfile
from dataclasses import replace

from cytellect_api.db import Store, jobs, revisions, workspaces
from cytellect_worker.main import cleanup, process_one
from fastapi.testclient import TestClient
from sqlalchemy import update
from test_api_worker import HEADERS, authenticated


def demo(client, app, settings):
    w = client.post("/v1/workspaces", json={"title": "synthetic"}, headers=HEADERS).json()
    made = client.post(f"/v1/workspaces/{w['id']}/synthetic", headers=HEADERS).json()
    ids = made["field_ids"]
    config = {"backgrounds": {fid: {"confirmed": True, "polygon": made["background_polygon"]} for fid in ids}}
    job = client.post(f"/v1/workspaces/{w['id']}/analyses", json=config, headers=HEADERS).json()
    assert process_one(app.state.store, settings)
    return w["id"], ids, job["revision_id"], config


def test_invite_single_use_revocation_and_validation_do_not_echo_token(tmp_path):
    client, app, _ = authenticated(tmp_path)
    token = app.state.store.invite()
    other = TestClient(app)
    assert other.post("/v1/invitations/redeem", json={"token": token}, headers=HEADERS).status_code == 200
    assert client.post("/v1/invitations/redeem", json={"token": token}, headers=HEADERS).status_code == 401
    assert other.delete("/v1/session", headers=HEADERS).status_code == 200
    assert other.get("/v1/workspaces").status_code == 401
    bad = client.post("/v1/invitations/redeem", json={"token": "secret-short"}, headers=HEADERS)
    assert bad.status_code == 422
    assert "secret-short" not in bad.text


def test_versions_review_statistics_export_and_private_downloads(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid, fids, rid, config = demo(client, app, settings)
    before = client.get(f"/v1/revisions/{rid}/measurements").json()
    edit = {"field_id": fids[0], "layer": "nuclei", "operation": "delete", "ids": [1]}
    changed = client.post(f"/v1/revisions/{rid}/edits", json=edit, headers=HEADERS)
    assert changed.status_code == 202
    newer = changed.json()["revision_id"]
    assert client.post(f"/v1/revisions/{rid}/edits", json=edit, headers=HEADERS).status_code == 409
    assert process_one(app.state.store, settings)
    after = client.get(f"/v1/revisions/{newer}/measurements").json()
    assert len(after["cells"]) == len(before["cells"]) - 1
    assert after["invalidated_nucleoli"] == [fids[0]]
    assert client.get(f"/v1/revisions/{rid}/measurements").json() == before
    assert client.post(f"/v1/revisions/{newer}/review", json={}, headers=HEADERS).status_code == 409
    redetected = client.post(
        f"/v1/revisions/{newer}/resegment", json={"field_ids": [fids[0]]}, headers=HEADERS
    )
    assert redetected.status_code == 202
    latest = redetected.json()["revision_id"]
    assert process_one(app.state.store, settings)
    assert client.get(f"/v1/revisions/{latest}/measurements").json()["invalidated_nucleoli"] == []
    assert client.post(f"/v1/revisions/{latest}/review", json={}, headers=HEADERS).status_code == 200
    stats = client.post(
        f"/v1/revisions/{latest}/statistics",
        headers=HEADERS,
        json={
            "metric": "ncl_nucleus_mean_corrected",
            "baseline": "Control",
            "comparisons": [["Treatment", "Control"]],
            "paired": True,
            "independent_units_confirmed": True,
            "plot": {"kind": "paired"},
        },
    )
    assert stats.status_code == 202
    sid = stats.json()["job_id"]
    assert process_one(app.state.store, settings)
    assert client.get(f"/v1/jobs/{sid}").json()["state"] == "succeeded"
    assert client.get(f"/v1/jobs/{sid}/result").json()["revision_id"] == latest
    assert client.get(f"/v1/jobs/{sid}/files/figure.svg").status_code == 200
    export = client.post(f"/v1/revisions/{latest}/export", headers=HEADERS).json()["job_id"]
    assert process_one(app.state.store, settings)
    artifact = client.get(f"/v1/jobs/{export}/files/analysis.zip")
    assert artifact.status_code == 200, client.get(f"/v1/jobs/{export}").json()
    assert artifact.headers["cache-control"] == "no-store"
    with zipfile.ZipFile(io.BytesIO(artifact.content)) as bundle:
        assert not any(n.startswith("raw/") for n in bundle.namelist())
        assert any(n.endswith(".roi") or n.endswith(".zip") for n in bundle.namelist())
    second = TestClient(app)
    second.post("/v1/invitations/redeem", json={"token": app.state.store.invite()}, headers=HEADERS)
    private_routes = [
        f"/v1/fields/{fids[0]}/preview",
        f"/v1/revisions/{latest}/fields/{fids[0]}/masks",
        f"/v1/jobs/{sid}/files/figure.svg",
        f"/v1/jobs/{export}/files/analysis.zip",
    ]
    for route in private_routes:
        assert second.get(route).status_code == 404
    expires = app.state.store.one(workspaces, id=wid)["expires"]
    client.get(f"/v1/jobs/{sid}")
    assert app.state.store.one(workspaces, id=wid)["expires"] == expires
    assert client.delete(f"/v1/workspaces/{wid}", headers=HEADERS).status_code == 200
    for route in private_routes:
        assert client.get(route).status_code == 404
    cleanup(app.state.store)
    assert not app.state.store.safe_path("workspaces", wid).exists()
    assert not app.state.store.rows(revisions, workspace_id=wid)


def test_failed_field_cannot_be_silently_omitted_and_exclusion_is_versioned(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid, fids, rid, config = demo(client, app, settings)
    source = app.state.store.safe_path("workspaces", wid, "fields", fids[0], "ncl.npy")
    source.write_bytes(b"deliberately broken synthetic test")
    queued = client.post(f"/v1/revisions/{rid}/reconfigure", json=config, headers=HEADERS).json()
    assert process_one(app.state.store, settings)
    damaged = queued["revision_id"]
    report = client.get(f"/v1/revisions/{damaged}/measurements").json()
    assert report["field_failures"][0]["reason"] == "field_analysis_failed"
    assert client.post(f"/v1/revisions/{damaged}/review", headers=HEADERS).status_code == 409
    config["exclusions"] = [{"field_id": fids[0], "reason": "synthetic corruption"}]
    child = client.post(f"/v1/revisions/{damaged}/reconfigure", json=config, headers=HEADERS).json()[
        "revision_id"
    ]
    assert process_one(app.state.store, settings)
    report = client.get(f"/v1/revisions/{child}/measurements").json()
    assert report["field_failures"] == []
    assert report["excluded_failed_fields"] == [{"field_id": fids[0], "reason": "synthetic corruption"}]
    assert client.post(f"/v1/revisions/{child}/review", headers=HEADERS).status_code == 200


def test_deadline_retry_lease_fencing_and_cleanup_protect_running_attempt(tmp_path):
    client, app, settings = authenticated(tmp_path)
    w = client.post("/v1/workspaces", json={"title": "synthetic"}, headers=HEADERS).json()
    made = client.post(f"/v1/workspaces/{w['id']}/synthetic", headers=HEADERS).json()
    config = {
        "backgrounds": {
            fid: {"confirmed": True, "polygon": made["background_polygon"]} for fid in made["field_ids"]
        }
    }
    queued = client.post(f"/v1/workspaces/{w['id']}/analyses", json=config, headers=HEADERS).json()
    assert process_one(app.state.store, replace(settings, job_timeout_seconds=0))
    original = app.state.store.one(jobs, id=queued["job_id"])
    assert original["state"] == "failed"
    assert original["error"] == "job_time_limit"
    retried = client.post(f"/v1/jobs/{original['id']}/retry", headers=HEADERS)
    assert retried.status_code == 202
    assert client.post(f"/v1/jobs/{original['id']}/retry", headers=HEADERS).status_code == 409
    successor = app.state.store.claim()
    assert successor
    assert not app.state.store.finish(dict(original), "invalid-stale-result")
    with app.state.store.transaction() as conn:
        conn.execute(update(workspaces).where(workspaces.c.id == w["id"]).values(deleted=True))
    folder = app.state.store.safe_path("workspaces", w["id"])
    cleanup(app.state.store)
    assert folder.exists()
    with app.state.store.transaction() as conn:
        conn.execute(update(jobs).where(jobs.c.id == successor["id"]).values(lease_until=0))
    cleanup(app.state.store)
    assert not folder.exists()


def test_versioned_migration_upgrades_existing_bootstrap_and_is_idempotent(tmp_path):
    import sqlite3

    tmp_path.mkdir(exist_ok=True)
    with sqlite3.connect(tmp_path / "cytellect.sqlite") as connection:
        connection.execute(
            "CREATE TABLE revisions (id VARCHAR PRIMARY KEY, workspace_id VARCHAR NOT NULL, parent_id VARCHAR, config JSON NOT NULL, state VARCHAR NOT NULL, reviewed BOOLEAN NOT NULL, result_dir VARCHAR, created FLOAT NOT NULL)"
        )
    first = Store(tmp_path)
    second = Store(tmp_path)
    with second.engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one() == "0001"
        assert "review_record" in {r[1] for r in connection.exec_driver_sql("PRAGMA table_info(revisions)")}
    first.engine.dispose()
    second.engine.dispose()
