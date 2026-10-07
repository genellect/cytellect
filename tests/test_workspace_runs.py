"""Durable job orchestration, private ownership and explicit adoption only."""

from cytellect_api.app import create_app
from cytellect_api.db import Store, jobs, workspace_analysis_runs
from cytellect_api.workspace_runs import advance_workspace_runs
from fastapi.testclient import TestClient
from test_api_worker import HEADERS, authenticated
from test_region_api import make_field
from test_region_cohorts import finish_analysis


def setup(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "run"}).json()["id"]
    fid = make_field(client, wid, labels=False).json()["id"]
    assert (
        client.put(
            f"/v1/workspaces/{wid}/channel-assignments",
            headers=HEADERS,
            json={"version": 0, "assignments": [{"channel_id": "actin", "stain": None, "role": "measure"}]},
        ).status_code
        == 200
    )
    spec = {"channel_assignment_version": 1, "target": "cell"}
    assert (
        client.put(
            f"/v1/workspaces/{wid}/analysis-spec", headers=HEADERS, json={"version": 0, "spec": spec}
        ).status_code
        == 200
    )
    path = f"/v1/workspaces/{wid}/runs"
    body = {"request_id": "first", "spec_version": 1, "target": "cell", "field_ids": [fid]}
    return client, app, settings, wid, fid, path, body


def complete(app, settings):
    assert advance_workspace_runs(app.state.store, settings)
    finish_analysis(app, settings)
    assert advance_workspace_runs(app.state.store, settings)


def test_manual_cell_initialization_without_stain_or_role_assignment(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "manual"}).json()["id"]
    fid = make_field(client, wid, labels=False).json()["id"]
    saved = client.put(f"/v1/workspaces/{wid}/analysis-spec", headers=HEADERS,
                       json={"version": 0, "spec": {"channel_assignment_version": 0, "target": "cell"}})
    assert saved.status_code == 200, saved.text
    path = f"/v1/workspaces/{wid}/runs"
    created = client.post(path, headers=HEADERS, json={"request_id": "manual-without-roles",
                          "spec_version": 1, "target": "cell", "field_ids": [fid]})
    assert created.status_code == 202, created.text
    complete(app, settings)
    result = client.get(f"{path}/{created.json()['id']}").json()
    assert result["state"] == "succeeded", result
    assert result["steps"][0]["recipe"]["source"] == "manual"
    assert result["steps"][0]["recipe"]["defining_channel_id"] is None
    assert client.post(f"{path}/{created.json()['id']}/accept", headers=HEADERS).status_code == 200


def test_manual_cell_runs_survive_restart_without_adoption_and_accept_exact_candidate(tmp_path):
    client, app, settings, wid, fid, path, body = setup(tmp_path)
    original = client.get(f"/v1/workspaces/{wid}/selection").json()
    response = client.post(path, headers=HEADERS, json=body)
    assert response.status_code == 202, response.text
    run_id = response.json()["id"]
    assert client.post(path, headers=HEADERS, json=body).json()["id"] == run_id
    complete(app, settings)
    assert client.get(f"/v1/workspaces/{wid}/selection").json() == original
    saved = client.get(f"{path}/{run_id}").json()
    assert saved["state"] == "succeeded"
    assert saved["steps"][0]["recipe"]["source"] == "manual"
    restarted = TestClient(create_app(settings))
    restarted.cookies.update(client.cookies)
    assert restarted.get(f"{path}/{run_id}").json() == saved
    accepted = restarted.post(f"{path}/{run_id}/accept", headers=HEADERS)
    assert accepted.status_code == 200, accepted.text
    selected = restarted.get(f"/v1/workspaces/{wid}/selection").json()
    assert selected["entries"][0]["target_revisions"]["cell"] == saved["steps"][0]["revision_id"]
    assert restarted.post(f"{path}/{run_id}/accept", headers=HEADERS).status_code == 200
    assert restarted.get(f"/v1/workspaces/{wid}/selection").json() == selected


def test_submission_owner_cas_unknown_fields_and_request_id_conflict(tmp_path):
    client, app, settings, wid, fid, path, body = setup(tmp_path)
    foreign = TestClient(app)
    foreign.post("/v1/invitations/redeem", headers=HEADERS, json={"token": app.state.store.invite()})
    assert foreign.post(path, headers=HEADERS, json=body).status_code == 404
    assert foreign.get(path).status_code == 404
    assert client.post(path, json=body).status_code == 403
    assert client.post(path, headers=HEADERS, json={**body, "spec_version": 9}).status_code == 409
    assert client.post(path, headers=HEADERS, json={**body, "field_ids": ["missing"]}).status_code == 422
    created = client.post(path, headers=HEADERS, json=body).json()
    assert foreign.get(f"{path}/{created['id']}").status_code == 404
    assert client.post(path, headers=HEADERS, json={**body, "target": "nuclei"}).status_code == 409
    assert len(app.state.store.rows(workspace_analysis_runs, workspace_id=wid)) == 1


def test_repeated_coordinator_does_not_duplicate_jobs(tmp_path):
    client, app, settings, wid, fid, path, body = setup(tmp_path)
    run = client.post(path, headers=HEADERS, json=body).json()
    advance_workspace_runs(app.state.store, settings)
    advance_workspace_runs(Store(settings.data_dir), settings)
    assert len(app.state.store.rows(jobs, workspace_id=wid)) == 1
    assert client.get(f"{path}/{run['id']}").json()["steps"][0]["state"] == "queued"


def test_changed_spec_or_adoption_refuses_candidate_adoption(tmp_path):
    client, app, settings, wid, fid, path, body = setup(tmp_path)
    run = client.post(path, headers=HEADERS, json=body).json()
    complete(app, settings)
    saved = client.get(f"/v1/workspaces/{wid}/analysis-spec").json()
    saved["spec"]["settings"]["nuclearProbability"] = 0.7
    assert client.put(f"/v1/workspaces/{wid}/analysis-spec", headers=HEADERS, json=saved).status_code == 200
    assert client.post(f"{path}/{run['id']}/accept", headers=HEADERS).status_code == 409
    assert client.get(f"/v1/workspaces/{wid}/selection").json()["entries"][0]["revision_id"] is None


def test_cancel_keeps_adopted_results_and_never_starts_pending_steps(tmp_path):
    client, app, settings, wid, fid, path, body = setup(tmp_path)
    run = client.post(path, headers=HEADERS, json=body).json()
    assert client.post(f"{path}/{run['id']}/cancel", headers=HEADERS).json()["state"] == "cancelled"
    assert not advance_workspace_runs(app.state.store, settings)
    assert app.state.store.rows(jobs, workspace_id=wid) == []
    assert client.post(f"{path}/{run['id']}/accept", headers=HEADERS).status_code == 409


def test_dependency_candidates_pin_parent_masks_and_adopt_together(tmp_path, monkeypatch):
    import numpy as np
    from cytellect_analysis.compartment_engine import derive_compartment_masks

    client, app, settings, wid, fid, path, body = setup(tmp_path)
    assert (
        client.put(
            f"/v1/workspaces/{wid}/channel-assignments",
            headers=HEADERS,
            json={"version": 1, "assignments": [{"channel_id": "actin", "stain": None, "role": "nuclear"}]},
        ).status_code
        == 200
    )
    spec = {"channel_assignment_version": 2, "target": "nucleoplasm", "settings": {"nuclearMaxSide": 128}}
    assert (
        client.put(
            f"/v1/workspaces/{wid}/analysis-spec", headers=HEADERS, json={"version": 1, "spec": spec}
        ).status_code
        == 200
    )
    nuclei = np.zeros((12, 12), np.uint32)
    nuclei[2:10, 2:10] = 17
    nucleoli = np.zeros_like(nuclei)
    nucleoli[5:7, 5:7] = 53
    monkeypatch.setattr(
        "cytellect_worker.regions.detect_nuclei", lambda *a, **kw: (nuclei, {"engine": "synthetic-test"})
    )
    monkeypatch.setattr(
        "cytellect_worker.regions.detect_compartments",
        lambda **kw: derive_compartment_masks(kw["nuclei"], nucleoli, {17: "candidate"}),
    )
    run = client.post(path, headers=HEADERS, json={**body, "spec_version": 2, "target": "nucleoplasm"}).json()
    advance_workspace_runs(app.state.store, settings)
    for _ in range(3):
        report = finish_analysis(app, settings)
        assert report["field_failures"] == []
        advance_workspace_runs(app.state.store, settings)
    saved = client.get(f"{path}/{run['id']}").json()
    assert saved["state"] == "succeeded", saved
    nucleus, child, plasm = saved["steps"]
    assert child["recipe"]["nuclear_revision_id"] == nucleus["revision_id"]
    assert plasm["recipe"]["nuclear_revision_id"] == nucleus["revision_id"]
    assert plasm["recipe"]["nucleolar_revision_id"] == child["revision_id"]
    assert client.get(f"/v1/workspaces/{wid}/selection").json()["entries"][0]["revision_id"] is None
    accepted = client.post(f"{path}/{run['id']}/accept", headers=HEADERS)
    assert accepted.status_code == 200, accepted.text
    selected = client.get(f"/v1/workspaces/{wid}/selection").json()["entries"][0]["target_revisions"]
    assert selected == {step["target"]: step["revision_id"] for step in saved["steps"]}
    # An unchanged request reuses corrected/adopted definitions instead of detecting again.
    again = client.post(
        path,
        headers=HEADERS,
        json={**body, "request_id": "again", "spec_version": 2, "target": "nucleoplasm"},
    ).json()
    advance_workspace_runs(app.state.store, settings)
    assert {step["state"] for step in client.get(f"{path}/{again['id']}").json()["steps"]} == {"reused"}


def test_measurement_policy_change_reuses_original_mask_revision(tmp_path):
    from cytellect_api.db import revisions
    from cytellect_api.storage import read_json

    client, app, settings, wid, fid, path, body = setup(tmp_path)
    run = client.post(path, headers=HEADERS, json=body).json()
    complete(app, settings)
    assert client.post(f"{path}/{run['id']}/accept", headers=HEADERS).status_code == 200
    original = client.get(f"{path}/{run['id']}").json()["steps"][0]["revision_id"]
    spec = client.get(f"/v1/workspaces/{wid}/analysis-spec").json()
    spec["spec"]["settings"]["background"] = "automatic"
    spec["spec"]["measurement"] = {"version": "1.2.0", "mode": "automatic_background"}
    assert client.put(f"/v1/workspaces/{wid}/analysis-spec", headers=HEADERS, json=spec).status_code == 200
    next_run = client.post(
        path, headers=HEADERS, json={**body, "request_id": "background", "spec_version": 2}
    ).json()
    complete(app, settings)
    revised = client.get(f"{path}/{next_run['id']}").json()["steps"][0]["revision_id"]
    assert app.state.store.one(revisions, id=revised)["config"]["reuse_revision"] == original

    def mask(rid):
        rev = app.state.store.one(revisions, id=rid)
        return read_json(app.state.store.safe_path(rev["result_dir"], "measurements.json"))["field_masks"][
            fid
        ]

    assert mask(revised)["mask_revision_id"] == mask(original)["mask_revision_id"]
    assert mask(revised)["mask_sha256"] == mask(original)["mask_sha256"]


def test_background_pending_preview_cannot_be_adopted_as_confirmed_measurement(tmp_path):
    client, app, settings, wid, fid, path, body = setup(tmp_path)
    spec = client.get(f"/v1/workspaces/{wid}/analysis-spec").json()
    spec["spec"]["settings"]["background"] = "confirmed_roi"
    spec["spec"]["measurement"] = None
    response = client.put(f"/v1/workspaces/{wid}/analysis-spec", headers=HEADERS, json=spec)
    assert response.status_code == 200, response.text
    run = client.post(path, headers=HEADERS, json={**body, "spec_version": 2, "purpose": "preview"}).json()
    complete(app, settings)
    saved = client.get(f"{path}/{run['id']}").json()
    assert saved["state"] == "succeeded"
    assert saved["steps"][0]["background_pending"] is True
    assert (
        client.post(f"{path}/{run['id']}/accept", headers=HEADERS).json()["detail"]
        == "analysis_run_background_required"
    )
    assert (
        client.get(f"/v1/workspaces/{wid}/analysis-spec").json()["spec"]["settings"]["background"]
        == "confirmed_roi"
    )
    assert client.get(f"/v1/workspaces/{wid}/selection").json()["entries"][0]["revision_id"] is None


def test_changed_adoption_ledger_refuses_complete_candidate(tmp_path):
    client, app, settings, wid, fid, path, body = setup(tmp_path)
    run = client.post(path, headers=HEADERS, json=body).json()
    complete(app, settings)
    selection = client.get(f"/v1/workspaces/{wid}/selection").json()
    selection["entries"][0]["exclusion_reason"] = "explicit researcher decision"
    assert client.post(f"/v1/workspaces/{wid}/selection", headers=HEADERS, json=selection).status_code == 200
    response = client.post(f"{path}/{run['id']}/accept", headers=HEADERS)
    assert response.status_code == 409 and response.json()["detail"] == "workspace_selection_changed"
