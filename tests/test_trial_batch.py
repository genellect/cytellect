"""A reviewed trial's canonical pixels must survive expansion to a batch."""

import numpy as np
from cytellect_api.db import revisions
from cytellect_worker.main import process_one
from fastapi.testclient import TestClient
from test_api_worker import HEADERS, authenticated


def trial(client, app, settings):
    wid = client.post("/v1/workspaces", json={"title": "trial"}, headers=HEADERS).json()["id"]
    made = client.post(f"/v1/workspaces/{wid}/synthetic", headers=HEADERS).json()
    fids = made["field_ids"]
    backgrounds = {fid: {"polygon": made["background_polygon"], "confirmed": True} for fid in fids}
    response = client.post(f"/v1/workspaces/{wid}/analyses", headers=HEADERS,
                           json={"field_ids": [fids[0]], "backgrounds": backgrounds})
    assert response.status_code == 202
    assert process_one(app.state.store, settings)
    return wid, fids, backgrounds, response.json()["revision_id"]


def test_batch_preserves_edited_trial_pixels_and_pending_review(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid, fids, backgrounds, rid = trial(client, app, settings)
    edited = client.post(f"/v1/revisions/{rid}/edits", headers=HEADERS,
                         json={"field_id": fids[0], "layer": "nuclei", "operation": "delete", "ids": [1]})
    assert edited.status_code == 202
    assert process_one(app.state.store, settings)
    source = edited.json()["revision_id"]
    before = client.get(f"/v1/revisions/{source}/measurements").json()
    queued = client.post(f"/v1/workspaces/{wid}/analyses", headers=HEADERS,
                         json={"reuse_revision": source, "backgrounds": backgrounds})
    assert queued.status_code == 202
    assert process_one(app.state.store, settings)
    child = queued.json()["revision_id"]
    report = client.get(f"/v1/revisions/{child}/measurements").json()
    assert report["field_failures"] == []
    assert len(report["cells"]) == 53
    assert report["invalidated_nucleoli"] == [fids[0]]
    assert report["engine_provenance"][fids[0]]["source_revision"] == source
    assert report["engine_provenance"][fids[1]]["engine"] == "synthetic-truth"
    for key in ("nuclei", "nucleoli", "manual"):
        parent_dir = app.state.store.one(revisions, id=source)["result_dir"]
        child_dir = app.state.store.one(revisions, id=child)["result_dir"]
        with np.load(app.state.store.safe_path(parent_dir, fids[0], "masks.npz")) as original:
            with np.load(app.state.store.safe_path(child_dir, fids[0], "masks.npz")) as current:
                np.testing.assert_array_equal(original[key], current[key])
    assert client.get(f"/v1/revisions/{source}/measurements").json() == before
    assert client.post(f"/v1/revisions/{child}/review", headers=HEADERS).status_code == 409


def test_batch_reuse_rejects_changed_recipe_stale_and_omitted_trial(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid, fids, backgrounds, rid = trial(client, app, settings)
    payload = {"reuse_revision": rid, "backgrounds": backgrounds}
    for extra, code in [
        ({"recipe": {"probability": 0.6}}, "batch_reuse_requires_unchanged_recipe"),
        ({"field_ids": fids[1:]}, "batch_must_include_reused_fields"),
    ]:
        rejected = client.post(f"/v1/workspaces/{wid}/analyses", headers=HEADERS, json={**payload, **extra})
        assert rejected.status_code == 409
        assert rejected.json()["detail"] == code
    accepted = client.post(f"/v1/workspaces/{wid}/analyses", headers=HEADERS, json=payload)
    assert accepted.status_code == 202
    stale = client.post(f"/v1/workspaces/{wid}/analyses", headers=HEADERS, json=payload)
    assert stale.status_code == 409
    assert stale.json()["detail"] == "stale_revision"


def test_reuse_does_not_cross_workspace_or_owner(tmp_path):
    client, app, settings = authenticated(tmp_path)
    _, _, _, rid = trial(client, app, settings)
    wid, _, backgrounds, _ = trial(client, app, settings)
    response = client.post(f"/v1/workspaces/{wid}/analyses", headers=HEADERS,
                           json={"reuse_revision": rid, "backgrounds": backgrounds})
    assert response.status_code == 404
    second = TestClient(app)
    second.post("/v1/invitations/redeem", headers=HEADERS, json={"token": app.state.store.invite()})
    other_wid, _, other_backgrounds, _ = trial(second, app, settings)
    denied = second.post(f"/v1/workspaces/{other_wid}/analyses", headers=HEADERS,
                         json={"reuse_revision": rid, "backgrounds": other_backgrounds})
    assert denied.status_code == 404
