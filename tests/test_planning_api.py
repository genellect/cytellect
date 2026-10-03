"""Actual-source planning adoption survives private API revision and replay boundaries."""

import io
import json
import zipfile
from copy import deepcopy

import pytest
from cytellect_analysis.images import sha256
from cytellect_analysis.region_exports import replay_region_bundle
from cytellect_api.db import fields, jobs, revisions, workspaces
from cytellect_worker.main import process_one
from fastapi.testclient import TestClient
from test_api_worker import HEADERS, authenticated
from test_region_api import make_field, region_request


def plan(source="imported"):
    return {"format": "cytellect-analysis-plan", "version": "2.0.0", "answers": {
        "measurement": "mean", "region": "custom", "definition": source, "signal": "other",
        "input": "grayscale-2d", "comparison": "descriptive"}}


def planned_workspace(client, *, source="imported"):
    response = client.post("/v1/workspaces", headers=HEADERS, json={
        "title": "Known pixels", "plan": plan(source), "plan_candidate_id": f"regions-{source}"})
    assert response.status_code == 201, response.text
    return response.json()


def request_for(workspace, fid, *, source="imported"):
    request = region_request(fid, source=source)
    request["plan_resolution"] = {"plan_sha256": workspace["analysis_plan"]["sha256"],
                                  "candidate_id": f"regions-{source}",
                                  "metric": "mean_corrected", "channel_id": "actin"}
    return request


def execute(client, app, settings, queued):
    assert queued.status_code == 202, queued.text
    value = queued.json()
    assert process_one(app.state.store, settings)
    job = client.get(f"/v1/jobs/{value['job_id']}").json()
    assert job["state"] == "succeeded", job
    return value.get("revision_id"), value["job_id"]


def assert_plan(app, rid, workspace, *, metric="mean_corrected"):
    revision = app.state.store.one(revisions, id=rid)
    record = revision["config"]["analysis_plan"]
    adopted = workspace["analysis_plan"]
    assert record["sha256"] == adopted["sha256"]
    assert record["input"] == adopted["input"]
    assert record["decision"] == adopted["decision"]
    assert record["accepted_at"] == adopted["accepted_at"]
    assert record["scope"] == "planning-intent-only"
    assert record["resolved"]["metric"] == metric
    assert record["resolved"]["channel"]["channel_id"] == "actin"
    assert record["resolved"]["channel"]["label"] == "Actin"
    return revision


def test_private_plan_preview_and_adoption_recompute_trustworthy_snapshot(tmp_path):
    client, app, _ = authenticated(tmp_path)
    preview = client.post("/v1/plans/preview", headers=HEADERS, json=plan())
    assert preview.status_code == 200, preview.text
    assert preview.headers["cache-control"] == "no-store"
    assert preview.json()["decision"]["status"] == "planning-only-not-adopted"
    assert preview.json()["decision"]["candidates"][0]["source"] == "imported"
    assert app.state.store.rows(workspaces) == []
    assert app.state.store.rows(jobs) == []
    assert TestClient(app).post("/v1/plans/preview", headers=HEADERS, json=plan()).status_code == 401
    assert client.post("/v1/plans/preview", json=plan()).status_code == 403
    workspace = planned_workspace(client)
    saved = workspace["analysis_plan"]
    assert saved["sha256"] == preview.json()["sha256"]
    assert saved["decision"] == preview.json()["decision"]
    assert saved["selected_candidate_id"] == "regions-imported"
    assert saved["accepted_at"] > 0
    assert client.get(f"/v1/workspaces/{workspace['id']}").json()["analysis_plan"] == saved
    assert client.get("/v1/workspaces").json()[0]["analysis_plan"] == saved
    assert app.state.store.rows(jobs) == []


@pytest.mark.parametrize("invalid", ["candidate", "decision", "legacy-version", "no-choice", "no-input"])
def test_workspace_rejects_unavailable_candidate_or_forged_plan_without_side_effects(tmp_path, invalid):
    client, app, _ = authenticated(tmp_path)
    body = {"title": "Invalid plan", "plan": plan(), "plan_candidate_id": "regions-imported"}
    if invalid == "candidate":
        body["plan_candidate_id"] = "legacy-ncl"
    elif invalid == "decision":
        body["plan"]["decision"] = {"candidates": [{"id": "legacy-ncl"}]}
    elif invalid == "legacy-version":
        body["plan"]["version"] = "1.0.0"
    elif invalid == "no-choice":
        del body["plan_candidate_id"]
    else:
        del body["plan"]
    response = client.post("/v1/workspaces", headers=HEADERS, json=body)
    assert response.status_code == 422
    assert app.state.store.rows(workspaces) == app.state.store.rows(revisions) == app.state.store.rows(jobs) == []


@pytest.mark.parametrize(("change", "code"), [
    ("missing", "planning_resolution_required"), ("plan-sha", "planning_adoption_mismatch"),
    ("candidate", "planning_adoption_mismatch"), ("unsupported-metric", "planning_metric_unavailable"),
    ("missing-channel", "planning_channel_unavailable"), ("unknown-channel", "planning_channel_unavailable"),
    ("physical-area", "planning_calibration_required"), ("changed-metric", "planning_changes_review_required"),
])
def test_resolution_requires_explicit_actual_metric_channel_and_changes(tmp_path, change, code):
    client, app, _ = authenticated(tmp_path)
    workspace = planned_workspace(client)
    wid = workspace["id"]
    fid = make_field(client, wid).json()["id"]
    request = request_for(workspace, fid)
    resolution = request["plan_resolution"]
    if change == "missing":
        del request["plan_resolution"]
    elif change == "plan-sha":
        resolution["plan_sha256"] = "0" * 64
    elif change == "candidate":
        resolution["candidate_id"] = "regions-manual"
    elif change == "unsupported-metric":
        resolution["metric"] = "invented_mean"
    elif change == "missing-channel":
        resolution["channel_id"] = None
    elif change == "unknown-channel":
        resolution["channel_id"] = "missing"
    elif change == "physical-area":
        resolution.update(metric="area_um2", channel_id=None)
    else:
        resolution["metric"] = "integrated_corrected"
    rejected = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=request)
    assert rejected.status_code == 422 and rejected.json() == {"detail": code}
    assert rejected.headers["cache-control"] == "no-store"
    assert app.state.store.one(workspaces, id=wid)["active_revision"] is None
    assert app.state.store.rows(revisions) == app.state.store.rows(jobs) == []


def test_explicit_metric_change_is_recorded_and_cannot_adopt_foreign_workspace(tmp_path):
    client, app, settings = authenticated(tmp_path)
    workspace = planned_workspace(client)
    wid = workspace["id"]
    fid = make_field(client, wid).json()["id"]
    request = request_for(workspace, fid)
    request["plan_resolution"].update(metric="integrated_corrected", changes_acknowledged=True)
    foreign = TestClient(app)
    foreign.post("/v1/invitations/redeem", headers=HEADERS, json={"token": app.state.store.invite()})
    assert foreign.get(f"/v1/workspaces/{wid}").status_code == 404
    assert foreign.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=request).status_code == 404
    assert app.state.store.rows(revisions) == []
    rid, _ = execute(client, app, settings, client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=request))
    revision = assert_plan(app, rid, workspace, metric="integrated_corrected")
    assert revision["config"]["analysis_plan"]["changes"] == ["measurement"]
    row = client.get(f"/v1/revisions/{rid}/region-measurements").json()["field_tables"][fid]["rows"][0]
    assert row["integrated_corrected"] == 100


@pytest.mark.parametrize("source", ["manual", "imported"])
def test_plan_survives_edit_reconfigure_metadata_batch_methods_export_and_replay(tmp_path, source):
    client, app, settings = authenticated(tmp_path)
    workspace = planned_workspace(client, source=source)
    wid = workspace["id"]
    fid = make_field(client, wid, labels=source == "imported").json()["id"]
    original_upload = deepcopy(dict(app.state.store.one(fields, id=fid)))
    request = request_for(workspace, fid, source=source)
    rid, _ = execute(client, app, settings, client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=request))
    first_record = deepcopy(dict(assert_plan(app, rid, workspace)))
    polygon = [[4, 4], [6, 4], [6, 6], [4, 6]]
    edit = {"field_id": fid, "region_set_id": "objects", "operation": "add" if source == "manual" else "replace",
            "ids": [] if source == "manual" else [17], "polygon": polygon, "expected_mask_revision_id": rid}
    edited, _ = execute(client, app, settings, client.post(f"/v1/revisions/{rid}/region-edits", headers=HEADERS, json=edit))
    assert_plan(app, edited, workspace)
    assert client.post(f"/v1/revisions/{edited}/review", headers=HEADERS).status_code == 200
    request["backgrounds"][fid]["actin"]["polygon"] = [[9, 9], [11, 9], [11, 11], [9, 11]]
    configured, _ = execute(client, app, settings, client.post(f"/v1/revisions/{edited}/region-reconfigure", headers=HEADERS, json=request))
    assert_plan(app, configured, workspace)
    metadata = {"condition": "A", "experimental_unit": "culture-1", "sample": "sample-1"}
    described, _ = execute(client, app, settings, client.post(f"/v1/revisions/{configured}/region-metadata", headers=HEADERS,
                                                            json={"fields": {fid: metadata}}))
    assert_plan(app, described, workspace)
    assert dict(app.state.store.one(fields, id=fid)) == original_upload
    second = make_field(client, wid, labels=source == "imported").json()["id"]
    request.update(field_ids=[fid, second], reuse_revision=described)
    request["backgrounds"][second] = deepcopy(request["backgrounds"][fid])
    batch, _ = execute(client, app, settings, client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=request))
    if source == "manual":
        edit.update(field_id=second, expected_mask_revision_id=batch)
        batch, _ = execute(client, app, settings, client.post(f"/v1/revisions/{batch}/region-edits", headers=HEADERS, json=edit))
    adopted = assert_plan(app, batch, workspace)
    assert adopted["config"]["field_snapshot"][fid]["metadata"]["experimental_unit"] == "culture-1"
    assert adopted["config"]["field_snapshot"][second]["metadata"]["experimental_unit"] is None
    assert not adopted["reviewed"]
    assert dict(app.state.store.one(revisions, id=rid)) == first_record
    measured = client.get(f"/v1/revisions/{batch}/region-measurements").json()
    assert all(table["rows"][0]["mean_corrected"] == 25 for table in measured["field_tables"].values())
    assert measured["field_masks"][fid]["mask_revision_id"] == edited
    assert client.post(f"/v1/revisions/{batch}/review", headers=HEADERS).status_code == 200
    _, exported = execute(client, app, settings, client.post(f"/v1/revisions/{batch}/export", headers=HEADERS))
    response = client.get(f"/v1/jobs/{exported}/files/analysis.zip")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    folder = tmp_path / "downloaded"
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert not any(name.startswith("raw/") for name in archive.namelist())
        archive.extractall(folder)
    exported_config = json.loads((folder / "revision.json").read_text(encoding="utf-8"))["config"]
    assert exported_config["analysis_plan"] == adopted["config"]["analysis_plan"]
    methods = (folder / "methods.md").read_text(encoding="utf-8")
    assert workspace["analysis_plan"]["sha256"] in methods
    assert "mean_corrected" in methods and "Adopted planning intent" in methods
    replay = replay_region_bundle(folder, app.state.store.safe_path("workspaces", wid, "fields"), tmp_path / "replayed")
    assert replay["matched_saved_measurements"]
    # A fresh manifest cannot authorize a changed scientific plan-resolution record.
    record = json.loads((folder / "revision.json").read_text(encoding="utf-8"))
    record["config"]["analysis_plan"]["resolved"]["metric"] = "integrated_corrected"
    (folder / "revision.json").write_text(json.dumps(record), encoding="utf-8")
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    manifest["files"]["revision.json"] = sha256(folder / "revision.json")
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="planning_revision_record_mismatch"):
        replay_region_bundle(folder, app.state.store.safe_path("workspaces", wid, "fields"), tmp_path / "tampered-replay")
    assert client.delete(f"/v1/workspaces/{wid}", headers=HEADERS).status_code == 200
    assert client.get(f"/v1/jobs/{exported}/files/analysis.zip").status_code == 404


def test_no_plan_keeps_previous_region_requests_and_rejects_unattached_resolution(tmp_path):
    client, app, settings = authenticated(tmp_path)
    workspace = client.post("/v1/workspaces", headers=HEADERS, json={"title": "Previous API"}).json()
    assert workspace["analysis_plan"] is None
    wid = workspace["id"]
    fid = make_field(client, wid).json()["id"]
    request = region_request(fid)
    request["plan_resolution"] = {"plan_sha256": "0" * 64, "candidate_id": "regions-imported",
                                  "metric": "mean", "channel_id": "actin"}
    invalid = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=request)
    assert invalid.status_code == 422 and invalid.json()["detail"] == "planning_resolution_without_plan"
    del request["plan_resolution"]
    rid, _ = execute(client, app, settings, client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=request))
    config = app.state.store.one(revisions, id=rid)["config"]
    assert "analysis_plan" not in config and "plan_resolution" not in config
    row = client.get(f"/v1/revisions/{rid}/region-measurements").json()["field_tables"][fid]["rows"][0]
    assert row["mean_corrected"] == 25


def legacy_fixture(client):
    """Fixed synthetic truth tests legacy routing, not nuclear-model performance."""
    value = plan()
    value["answers"].update(region="nucleus", definition="nuclear-stain", nuclear_stain="yes", signal="gfp")
    created = client.post("/v1/workspaces", headers=HEADERS, json={
        "title": "Legacy numerical fixture", "plan": value, "plan_candidate_id": "legacy-gfp-nuclear"})
    assert created.status_code == 201, created.text
    workspace = created.json()
    generated = client.post(f"/v1/workspaces/{workspace['id']}/synthetic", headers=HEADERS)
    assert generated.status_code == 201, generated.text
    fid = generated.json()["field_ids"][0]
    request = {"field_ids": [fid], "recipe": {"id": "gfp-nuclear-2d"},
               "backgrounds": {fid: {"confirmed": True, "polygon": [[0, 0], [3, 0], [3, 3], [0, 3]]}},
               "plan_resolution": {"plan_sha256": workspace["analysis_plan"]["sha256"],
                                   "candidate_id": "legacy-gfp-nuclear", "metric": "gfp_integrated_corrected",
                                   "channel_id": "gfp", "changes_acknowledged": True}}
    return workspace, request


@pytest.mark.parametrize("workflow", ["regions", "legacy"])
@pytest.mark.parametrize("operation", ["batch", "reconfigure"])
def test_omitted_resolution_inherits_same_recipe_but_explicit_null_never_discards_plan(tmp_path, workflow, operation):
    client, app, settings = authenticated(tmp_path)
    if workflow == "regions":
        workspace = planned_workspace(client)
        fid = make_field(client, workspace["id"]).json()["id"]
        request = request_for(workspace, fid)
        request["plan_resolution"].update(metric="integrated_corrected", changes_acknowledged=True)
    else:
        workspace, request = legacy_fixture(client)
    wid = workspace["id"]
    start_url = f"/v1/workspaces/{wid}/" + ("region-analyses" if workflow == "regions" else "analyses")
    rid, _ = execute(client, app, settings, client.post(start_url, headers=HEADERS, json=request))
    parent = app.state.store.one(revisions, id=rid)
    child = deepcopy(request)
    child["recipe"] = parent["config"]["recipe"]
    child["plan_resolution"] = None
    if operation == "batch":
        child["reuse_revision"] = rid
        url = start_url
    else:
        url = f"/v1/revisions/{rid}/" + ("region-reconfigure" if workflow == "regions" else "reconfigure")
    rejected = client.post(url, headers=HEADERS, json=child)
    assert rejected.status_code == 422 and rejected.json()["detail"] == "planning_resolution_required"
    assert rejected.headers["cache-control"] == "no-store"
    assert app.state.store.one(workspaces, id=wid)["active_revision"] == rid
    del child["plan_resolution"]
    accepted, _ = execute(client, app, settings, client.post(url, headers=HEADERS, json=child))
    config = app.state.store.one(revisions, id=accepted)["config"]
    assert config["plan_resolution"] == parent["config"]["plan_resolution"]
    assert config["plan_resolution"]["changes_acknowledged"] is True
    assert config["analysis_plan"] == parent["config"]["analysis_plan"]


@pytest.mark.parametrize("operation", ["reconfigure", "resegment"])
def test_old_acknowledgment_cannot_authorize_new_legacy_recipe_change(tmp_path, operation):
    client, app, settings = authenticated(tmp_path)
    workspace, request = legacy_fixture(client)
    wid = workspace["id"]
    rid, _ = execute(client, app, settings, client.post(f"/v1/workspaces/{wid}/analyses", headers=HEADERS, json=request))
    parent = app.state.store.one(revisions, id=rid)
    assert parent["config"]["analysis_plan"]["changes"] == ["measurement"]
    changed_recipe = {**parent["config"]["recipe"], "gfp_gate": "manual", "gfp_threshold": 1.0}
    body = {"field_ids": request["field_ids"], "recipe": changed_recipe, "backgrounds": request["backgrounds"]}
    url = f"/v1/revisions/{rid}/{operation}"
    rejected = client.post(url, headers=HEADERS, json=body)
    assert rejected.status_code == 422 and rejected.json()["detail"] == "planning_changes_review_required"
    assert app.state.store.one(workspaces, id=wid)["active_revision"] == rid
    assert len(app.state.store.rows(jobs, workspace_id=wid)) == 1
    body["plan_resolution"] = request["plan_resolution"]
    fresh = client.post(url, headers=HEADERS, json=body)
    assert fresh.status_code == 202, fresh.text
    config = app.state.store.one(revisions, id=fresh.json()["revision_id"])["config"]
    assert config["analysis_plan"]["changes"] == ["measurement", "gfp_selection"]
