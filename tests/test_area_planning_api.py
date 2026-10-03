"""Area-only plans bind to actual masks/modes without rewriting older plans."""
from __future__ import annotations

import copy
import io
import json
import zipfile

import pytest
from cytellect_analysis.images import sha256
from cytellect_analysis.region_exports import replay_region_bundle
from cytellect_api.db import revisions
from cytellect_api.planning import inherit_plan_resolution
from test_api_worker import HEADERS, authenticated
from test_planning_api import execute, legacy_fixture, plan
from test_region_api import make_field, region_request
from test_region_area_api import area_request, complete
from test_region_area_worker import POLICY


def planned_area(client, version="2.1.0"):
    value = plan()
    value["version"] = version
    value["answers"]["measurement"] = "area"
    response = client.post("/v1/workspaces", headers=HEADERS, json={
        "title": "Known area", "plan": value, "plan_candidate_id": "regions-imported",
    })
    assert response.status_code == 201, response.text
    return response.json()


def choose(workspace, *, policy=POLICY, ack=False):
    return {"version": "1.1.0", "plan_sha256": workspace["analysis_plan"]["sha256"],
            "candidate_id": "regions-imported", "metric": "area_px", "channel_id": None,
            "measurement": copy.deepcopy(policy), "changes_acknowledged": ack}


def config_for(app, rid):
    return app.state.store.one(revisions, id=rid)["config"]


def test_area_plan_survives_actual_edit_metadata_batch_export_and_replay(tmp_path):
    client, app, settings = authenticated(tmp_path)
    workspace = planned_area(client)
    wid = workspace["id"]
    fid = make_field(client, wid).json()["id"]
    body = {**area_request(fid), "plan_resolution": choose(workspace)}
    first, original = complete(client, app, settings, client.post(
        f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=body,
    ))
    original_record = copy.deepcopy(config_for(app, first))
    record = original_record["analysis_plan"]
    assert record["changes"] == [] and record["resolved"]["measurement"] == POLICY
    assert record["resolution"]["version"] == "1.1.0"
    assert original["field_tables"][fid]["rows"][0]["area_px"] == 4
    edit = {"field_id": fid, "region_set_id": "objects", "operation": "replace", "ids": [17],
            "polygon": [[4, 4], [6, 4], [6, 6], [4, 6]], "expected_mask_revision_id": first}
    edited, edited_report = complete(client, app, settings, client.post(
        f"/v1/revisions/{first}/region-edits", headers=HEADERS, json=edit,
    ))
    assert config_for(app, edited)["analysis_plan"] == record
    metadata, _ = complete(client, app, settings, client.post(
        f"/v1/revisions/{edited}/region-metadata", headers=HEADERS,
        json={"fields": {fid: {"condition": "A", "sample": "sample-a", "experimental_unit": "unit-a"}}},
    ))
    assert config_for(app, metadata)["analysis_plan"] == record
    second = make_field(client, wid).json()["id"]
    body.update(field_ids=[fid, second], reuse_revision=metadata)
    body.pop("plan_resolution")  # Same mode may retain the explicit saved choice.
    batch, batch_report = complete(client, app, settings, client.post(
        f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=body,
    ))
    saved = config_for(app, batch)
    assert saved["analysis_plan"] == record and saved["measurement"] == POLICY and saved["backgrounds"] == {}
    assert batch_report["field_masks"][fid] == edited_report["field_masks"][fid]
    assert saved["field_snapshot"][fid]["metadata"]["experimental_unit"] == "unit-a"
    assert saved["field_snapshot"][second]["metadata"]["experimental_unit"] is None
    assert all(table["rows"][0]["mean"] is None for table in batch_report["field_tables"].values())
    assert config_for(app, first) == original_record
    assert not app.state.store.one(revisions, id=batch)["reviewed"]
    assert client.post(f"/v1/revisions/{batch}/review", headers=HEADERS).status_code == 200
    _, export_job = execute(client, app, settings, client.post(f"/v1/revisions/{batch}/export", headers=HEADERS))
    response = client.get(f"/v1/jobs/{export_job}/files/analysis.zip")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    output = tmp_path / "bundle"
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert not any(name.startswith("raw/") or "/background-" in name for name in archive.namelist())
        archive.extractall(output)
    methods = (output / "methods.md").read_text(encoding="utf-8")
    assert "Guide 2.1.0" in methods and "Explicit measurement choice: area_only; measurement protocol 2.0.0." in methods
    assert workspace["analysis_plan"]["sha256"] in methods
    raw = app.state.store.safe_path("workspaces", wid, "fields")
    replay = replay_region_bundle(output, raw, tmp_path / "replay")
    assert replay["matched_saved_measurements"]
    revision_path = output / "revision.json"
    exported = json.loads(revision_path.read_text(encoding="utf-8"))
    assert exported["config"]["analysis_plan"] == record
    exported["config"]["analysis_plan"]["resolved"]["measurement_protocol"] = "1.0.0"
    revision_path.write_text(json.dumps(exported), encoding="utf-8")
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["revision.json"] = sha256(revision_path)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="planning_revision_record_mismatch"):
        replay_region_bundle(output, raw, tmp_path / "tampered-replay")


def test_old_plan_mode_upgrade_and_return_require_explicit_choices_not_inherited_ack(tmp_path):
    client, app, settings = authenticated(tmp_path)
    workspace = planned_area(client, "2.0.0")
    wid = workspace["id"]
    fid = make_field(client, wid).json()["id"]
    body = {**area_request(fid), "plan_resolution": choose(workspace, ack=True)}
    area, area_report = complete(client, app, settings, client.post(
        f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=body,
    ))
    assert config_for(app, area)["analysis_plan"]["changes"] == ["measurement_mode"]
    assert client.post(f"/v1/revisions/{area}/review", headers=HEADERS).status_code == 200
    current = copy.deepcopy(config_for(app, area))
    intensity_body = region_request(fid)
    rejected = client.post(f"/v1/revisions/{area}/region-reconfigure", headers=HEADERS, json=intensity_body)
    assert rejected.status_code == 422 and rejected.json()["detail"] == "planning_measurement_mismatch"
    assert config_for(app, area) == current and client.get(f"/v1/workspaces/{wid}").json()["active_revision"] == area
    legacy_choice = {key: value for key, value in choose(workspace, policy=None).items()
                     if key not in {"version", "measurement"}}
    for route, additional in ((f"/v1/revisions/{area}/region-reconfigure", {}),
                              (f"/v1/workspaces/{wid}/region-analyses", {"reuse_revision": area})):
        rejected = client.post(route, headers=HEADERS, json={
            **intensity_body, **additional, "plan_resolution": legacy_choice,
        })
        assert rejected.status_code == 422 and rejected.json()["detail"] == "planning_resolution_required"
    assert config_for(app, area) == current
    # Returning to the originally proposed mode is no deviation from that plan.
    # It still needs an explicit nullable choice and creates an unreviewed child.
    intensity_body["plan_resolution"] = choose(workspace, policy=None)
    intensity, intensity_report = complete(client, app, settings, client.post(
        f"/v1/revisions/{area}/region-reconfigure", headers=HEADERS, json=intensity_body,
    ))
    assert config_for(app, intensity)["analysis_plan"]["changes"] == []
    assert config_for(app, intensity)["plan_resolution"]["measurement"] is None
    assert "measurement" not in config_for(app, intensity)
    assert not app.state.store.one(revisions, id=intensity)["reviewed"]
    assert intensity_report["field_masks"] == area_report["field_masks"]
    assert intensity_report["field_tables"][fid]["rows"][0]["mean_corrected"] == 25
    area_body = area_request(fid)
    rejected = client.post(f"/v1/revisions/{intensity}/region-reconfigure", headers=HEADERS, json=area_body)
    assert rejected.status_code == 422 and rejected.json()["detail"] == "planning_measurement_mismatch"
    area_body["plan_resolution"] = choose(workspace)
    rejected = client.post(f"/v1/revisions/{intensity}/region-reconfigure", headers=HEADERS, json=area_body)
    assert rejected.status_code == 422 and rejected.json()["detail"] == "planning_changes_review_required"
    area_body["plan_resolution"]["changes_acknowledged"] = True
    restored, restored_report = complete(client, app, settings, client.post(
        f"/v1/revisions/{intensity}/region-reconfigure", headers=HEADERS, json=area_body,
    ))
    assert config_for(app, restored)["analysis_plan"]["changes"] == ["measurement_mode"]
    assert restored_report["field_masks"] == area_report["field_masks"]


@pytest.mark.parametrize("explicit", [None, "legacy", "wrong-mode"])
def test_area_plan_rejects_omitted_legacy_or_mismatched_mode_choice_before_queue(tmp_path, explicit):
    client, app, _ = authenticated(tmp_path)
    workspace = planned_area(client)
    wid = workspace["id"]
    fid = make_field(client, wid).json()["id"]
    body = area_request(fid)
    if explicit == "legacy":
        body["plan_resolution"] = {key: value for key, value in choose(workspace).items()
                                   if key not in {"measurement", "version"}}
    elif explicit == "wrong-mode":
        body["plan_resolution"] = choose(workspace, policy=None, ack=True)
    response = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=body)
    assert response.status_code == 422 and response.headers["cache-control"] == "no-store"
    assert response.json()["detail"] == ("planning_measurement_mismatch" if explicit == "wrong-mode"
                                          else "planning_resolution_required")
    assert app.state.store.rows(revisions) == []


@pytest.mark.parametrize("changed", [False, True])
def test_inheritance_resets_ack_on_policy_change_without_rewriting_choice(changed):
    parent = {"recipe": {"version": "1.0.0"}, "measurement": POLICY,
              "plan_resolution": {"version": "1.1.0", "measurement": POLICY, "changes_acknowledged": True}}
    before = copy.deepcopy(parent)
    child: dict = {"recipe": copy.deepcopy(parent["recipe"])}
    if not changed:
        child["measurement"] = copy.deepcopy(POLICY)
    inherit_plan_resolution(child, parent)
    assert child["plan_resolution"]["changes_acknowledged"] is (not changed)
    assert child["plan_resolution"]["measurement"] == POLICY and parent == before


@pytest.mark.parametrize("operation", ["batch", "reconfigure", "resegment"])
def test_native_parent_explicit_nullable_choice_cannot_downgrade_protocol(tmp_path, operation):
    client, app, settings = authenticated(tmp_path)
    workspace, body = legacy_fixture(client)
    wid = workspace["id"]
    body["plan_resolution"].update(version="1.1.0", measurement=None)
    start = f"/v1/workspaces/{wid}/analyses"
    rid, _ = execute(client, app, settings, client.post(start, headers=HEADERS, json=body))
    saved = copy.deepcopy(config_for(app, rid))
    assert saved["analysis_plan"]["resolved"]["measurement"] is None
    assert "measurement_protocol" not in saved["analysis_plan"]["resolved"]
    measured = client.get(f"/v1/revisions/{rid}/measurements").json()
    assert measured["recipe"]["id"] == "gfp-nuclear-2d" and measured["cells"]
    assert {row["measurement_protocol_version"] for row in measured["cells"]} == {"1.1.1"}
    assert {row["recipe_id"] for row in measured["cells"]} == {"gfp-nuclear-2d"}
    assert "measurement" not in saved
    assert client.post(f"/v1/revisions/{rid}/review", headers=HEADERS).status_code == 200
    request = copy.deepcopy(body)
    request["recipe"] = saved["recipe"]
    if operation == "batch":
        route = start
        request["reuse_revision"] = rid
    else:
        route = f"/v1/revisions/{rid}/{operation}"
    request["plan_resolution"].pop("measurement")
    request["plan_resolution"]["version"] = "1.0.0"
    rejected = client.post(route, headers=HEADERS, json=request)
    assert rejected.status_code == 422 and rejected.json()["detail"] == "planning_resolution_required"
    assert client.get(f"/v1/workspaces/{wid}").json()["active_revision"] == rid
    request["plan_resolution"] = saved["plan_resolution"]
    child, _ = execute(client, app, settings, client.post(route, headers=HEADERS, json=request))
    assert config_for(app, child)["analysis_plan"] == saved["analysis_plan"]
    assert config_for(app, child)["plan_resolution"]["measurement"] is None
    assert client.get(f"/v1/revisions/{child}/measurements").json()["cells"] == measured["cells"]
    assert "measurement" not in config_for(app, child)
    assert not app.state.store.one(revisions, id=child)["reviewed"]
