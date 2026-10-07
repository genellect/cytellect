"""Owned area-only requests retain masks, history, review and privacy boundaries."""
from __future__ import annotations

import copy
import time

import pytest
from cytellect_analysis.region_contracts import RegionAnalysisRequest, region_request_config
from cytellect_api.db import fields, jobs, revisions, workspaces
from cytellect_api.storage import read_json
from cytellect_worker.main import process_one
from fastapi.testclient import TestClient
from sqlalchemy import update
from test_api_worker import HEADERS, authenticated
from test_region_api import make_field, region_request
from test_region_area_worker import POLICY


def area_request(fid, *, source="imported"):
    return {**region_request(fid, source=source), "measurement": POLICY.copy(), "backgrounds": {}}


def complete(client, app, settings, response):
    assert response.status_code == 202, response.text
    queued = response.json()
    assert process_one(app.state.store, settings)
    job = app.state.store.one(jobs, id=queued["job_id"])
    assert job["state"] == "succeeded", job
    result = client.get(f"/v1/revisions/{queued['revision_id']}/region-measurements")
    assert result.status_code == 200, result.text
    assert result.headers["cache-control"] == "no-store"
    return queued["revision_id"], result.json()


def test_area_to_intensity_and_back_preserves_exact_masks_and_old_config_keys(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "area"}).json()["id"]
    fid = make_field(client, wid).json()["id"]
    body = area_request(fid)
    first_id, first = complete(client, app, settings, client.post(
        f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=body,
    ))
    assert first["protocol_version"] == "2.0.0" and first["measurement"] == POLICY
    row = first["field_tables"][fid]["rows"][0]
    assert row["area_px"] == 4 and row["area_um2"] is None
    assert row["area_missing_reason"] == "calibration_unknown" and row["mean"] is None
    assert app.state.store.one(revisions, id=first_id)["config"]["backgrounds"] == {}
    assert client.post(f"/v1/revisions/{first_id}/review", headers=HEADERS).status_code == 200
    lacking_background = {**body, "measurement": None}
    rejected = client.post(f"/v1/revisions/{first_id}/region-reconfigure", headers=HEADERS, json=lacking_background)
    assert rejected.status_code == 422 and rejected.json()["detail"] == "confirm_background_for_every_channel"
    assert client.get(f"/v1/workspaces/{wid}").json()["active_revision"] == first_id
    intensity = {**region_request(fid), "measurement": None}
    second_id, second = complete(client, app, settings, client.post(
        f"/v1/revisions/{first_id}/region-reconfigure", headers=HEADERS, json=intensity,
    ))
    record = app.state.store.one(revisions, id=second_id)
    assert not record["reviewed"] and "measurement" not in record["config"]
    assert "measurement" not in second and second["protocol_version"] == "1.0.0"
    assert second["field_tables"][fid]["rows"][0]["mean_corrected"] == 25
    assert second["field_masks"] == first["field_masks"]
    third_id, third = complete(client, app, settings, client.post(
        f"/v1/revisions/{second_id}/region-reconfigure", headers=HEADERS, json=body,
    ))
    assert third["field_masks"] == first["field_masks"]
    assert not list(app.state.store.safe_path(app.state.store.one(revisions, id=third_id)["result_dir"]).rglob(
        "background-*.npy",
    ))
    assert client.get(f"/v1/revisions/{first_id}/region-measurements").json() == first
    assert client.get(f"/v1/revisions/{second_id}/region-measurements").json() == second
    # Optional measurement is the only new request field; legacy serialized
    # defaults, including plan/reuse null values, are preserved byte for byte.
    request = RegionAnalysisRequest.model_validate(region_request(fid))
    old_shape = request.model_dump(mode="json")
    old_shape.pop("measurement")
    old_shape.pop("confirmed_channel_ids")
    assert region_request_config(request) == old_shape


def test_area_mask_edit_metadata_and_batch_preserve_policy_and_prior_records(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "area history"}).json()["id"]
    fid = make_field(client, wid).json()["id"]
    rid, original = complete(client, app, settings, client.post(
        f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=area_request(fid),
    ))
    edit = {"field_id": fid, "region_set_id": "objects", "operation": "add",
            "polygon": [[0, 0], [2, 0], [2, 2], [0, 2]], "expected_mask_revision_id": rid}
    edited_id, edited = complete(client, app, settings, client.post(
        f"/v1/revisions/{rid}/region-edits", headers=HEADERS, json=edit,
    ))
    assert edited["field_failures"] == [] and len(edited["field_tables"][fid]["rows"]) == 2
    assert edited["measurement"] == POLICY
    assert client.post(f"/v1/revisions/{rid}/region-edits", headers=HEADERS, json=edit).status_code == 409
    upload = copy.deepcopy(dict(app.state.store.one(fields, id=fid)))
    metadata_id, after_metadata = complete(client, app, settings, client.post(
        f"/v1/revisions/{edited_id}/region-metadata", headers=HEADERS,
        json={"fields": {fid: {"condition": "A", "experimental_unit": "unit-1", "sample": "sample-1"}}},
    ))
    assert after_metadata["measurement"] == POLICY and after_metadata["field_masks"] == edited["field_masks"]
    assert dict(app.state.store.one(fields, id=fid)) == upload
    next_fid = make_field(client, wid).json()["id"]
    request = {**area_request(fid), "field_ids": [fid, next_fid], "reuse_revision": metadata_id}
    batch_id, batch = complete(client, app, settings, client.post(
        f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=request,
    ))
    batch_record = app.state.store.one(revisions, id=batch_id)
    assert batch_record["config"]["measurement"] == POLICY and not batch_record["reviewed"]
    assert batch_record["config"]["field_snapshot"][fid]["metadata"]["experimental_unit"] == "unit-1"
    assert batch_record["config"]["field_snapshot"][next_fid]["metadata"]["experimental_unit"] is None
    assert batch["field_masks"][fid] == edited["field_masks"][fid]
    assert batch["field_masks"][next_fid]["mask_revision_id"] == batch_id
    assert client.get(f"/v1/revisions/{rid}/region-measurements").json() == original


@pytest.mark.parametrize("fault", ["nested_background", "real_background", "unknown_mode", "unknown_version"])
def test_area_request_rejects_unavailable_modes_and_backgrounds_before_queue(tmp_path, fault):
    client, app, _ = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "invalid area"}).json()["id"]
    fid = make_field(client, wid).json()["id"]
    request = area_request(fid)
    if fault == "nested_background":
        request["backgrounds"] = {fid: {}}
    elif fault == "real_background":
        request["backgrounds"] = region_request(fid)["backgrounds"]
    elif fault == "unknown_mode":
        request["measurement"]["mode"] = "area_and_raw"
    else:
        request["measurement"]["version"] = "2.0.0"
    response = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=request)
    assert response.status_code == 422
    assert not app.state.store.rows(jobs, workspace_id=wid)
    assert client.get(f"/v1/workspaces/{wid}").json()["active_revision"] is None


def test_area_results_and_mutations_require_owner_and_unexpired_workspace(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "private area"}).json()["id"]
    fid = make_field(client, wid).json()["id"]
    rid, _ = complete(client, app, settings, client.post(
        f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=area_request(fid),
    ))
    other = TestClient(app)
    other.post("/v1/invitations/redeem", headers=HEADERS, json={"token": app.state.store.invite()})
    assert other.get(f"/v1/revisions/{rid}/region-measurements").status_code == 404
    assert other.get(f"/v1/revisions/{rid}/region-masks?field_id={fid}").status_code == 404
    assert other.post(f"/v1/revisions/{rid}/region-reconfigure", headers=HEADERS,
                      json=area_request(fid)).status_code == 404
    with app.state.store.transaction() as connection:
        connection.execute(update(workspaces).where(workspaces.c.id == wid).values(expires=time.time() - 1))
    assert client.get(f"/v1/revisions/{rid}/region-measurements").status_code == 404
    assert client.post(f"/v1/revisions/{rid}/region-reconfigure", headers=HEADERS,
                       json=area_request(fid)).status_code == 404


def test_failed_area_field_blocks_review_until_reasoned_exclusion_preserves_failure(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "partial area"}).json()["id"]
    first = make_field(client, wid).json()["id"]
    failed = make_field(client, wid).json()["id"]
    path = app.state.store.safe_path("workspaces", wid, "fields", failed, "ch0.tif")
    raw = path.read_bytes()
    path.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
    request = {**area_request(first), "field_ids": [first, failed]}
    rid, report = complete(client, app, settings, client.post(
        f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=request,
    ))
    assert report["field_failures"] == [{"field_id": failed, "reason": "region_input_file_hash_mismatch"}]
    assert client.post(f"/v1/revisions/{rid}/review", headers=HEADERS).status_code == 409
    request["exclusions"] = [{"field_id": failed, "region_id": None, "reason": "Input damaged"}]
    child, revised = complete(client, app, settings, client.post(
        f"/v1/revisions/{rid}/region-reconfigure", headers=HEADERS, json=request,
    ))
    assert revised["excluded_failed_fields"] == [{"field_id": failed, "reason": "Input damaged",
                                                  "error": "region_input_file_hash_mismatch"}]
    assert client.post(f"/v1/revisions/{child}/review", headers=HEADERS).status_code == 200
    assert read_json(app.state.store.safe_path(app.state.store.one(revisions, id=rid)["result_dir"],
                                             "measurements.json")) == report


def test_area_retry_keeps_exact_saved_policy_and_does_not_queue_twice(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "area retry"}).json()["id"]
    fid = make_field(client, wid).json()["id"]
    queued = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS,
                         json=area_request(fid)).json()
    before = copy.deepcopy(app.state.store.one(revisions, id=queued["revision_id"])["config"])
    # Simulate the persisted boundary after a stopped worker; recovery must
    # consume the exact revision rather than constructing new defaults.
    with app.state.store.transaction() as connection:
        connection.execute(update(jobs).where(jobs.c.id == queued["job_id"]).values(state="failed", lease_until=None))
        connection.execute(update(revisions).where(revisions.c.id == queued["revision_id"]).values(state="failed"))
    retried = client.post(f"/v1/jobs/{queued['job_id']}/retry", headers=HEADERS)
    assert retried.status_code == 202
    assert client.post(f"/v1/jobs/{queued['job_id']}/retry", headers=HEADERS).status_code == 409
    rid, report = complete(client, app, settings, retried)
    assert rid == queued["revision_id"] and report["measurement"] == POLICY
    assert app.state.store.one(revisions, id=rid)["config"] == before
    records = app.state.store.rows(jobs, revision_id=rid)
    assert sorted(record["state"] for record in records) == ["failed", "succeeded"]
