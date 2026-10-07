"""Editing intent persists without creating jobs, adopting masks or inventing study design."""
from copy import deepcopy

import pytest
from cytellect_api.analysis_spec import AnalysisSpec
from cytellect_api.app import create_app
from cytellect_api.db import Store, jobs, workspace_analysis_specs
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_api_worker import HEADERS, authenticated


def setup(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "settings"}).json()["id"]
    return client, app, settings, wid, f"/v1/workspaces/{wid}/analysis-spec"


def test_empty_workspace_spec_round_trip_and_cas_without_execution(tmp_path):
    client, app, settings, wid, path = setup(tmp_path)
    assert client.get(path).json() == {"version": 0, "spec": None}
    spec = AnalysisSpec(channel_assignment_version=0).model_dump(mode="json")
    spec["settings"]["nuclearProbability"] = 0.65
    spec["target"] = "nucleoli"
    response = client.put(path, headers=HEADERS, json={"version": 0, "spec": spec})
    assert response.status_code == 200, response.text
    assert response.json() == {"version": 1, "spec": spec}
    assert app.state.store.one(jobs, workspace_id=wid) is None
    assert client.get(f"/v1/workspaces/{wid}/selection").json()["entries"] == []
    restarted = TestClient(create_app(settings))
    restarted.cookies.update(client.cookies)
    assert restarted.get(path).json() == response.json()
    assert client.put(path, headers=HEADERS, json={"version": 0, "spec": spec}).status_code == 409
    assert client.get(path).json() == response.json()
    spec["settings"]["nuclearProbability"] = 0.7
    assert client.put(path, headers=HEADERS, json={"version": 1, "spec": spec}).json()["version"] == 2


def test_spec_owner_csrf_expiry_and_channel_version(tmp_path):
    client, app, _, wid, path = setup(tmp_path)
    body = {"version": 0, "spec": {"channel_assignment_version": 0}}
    foreign = TestClient(app)
    foreign.post("/v1/invitations/redeem", headers=HEADERS, json={"token": app.state.store.invite()})
    assert foreign.get(path).status_code == 404
    assert foreign.put(path, headers=HEADERS, json=body).status_code == 404
    assert client.put(path, json=body).status_code == 403
    stale = deepcopy(body)
    stale["spec"]["channel_assignment_version"] = 2
    assert client.put(path, headers=HEADERS, json=stale).status_code == 409
    assert client.get(path).json()["version"] == 0
    assert client.put(path, headers=HEADERS, json=body).status_code == 200
    assert client.delete(f"/v1/workspaces/{wid}", headers=HEADERS).status_code < 300
    assert client.get(path).status_code == 404
    assert client.put(path, headers=HEADERS, json=body).status_code == 404


@pytest.mark.parametrize("patch", [
    {"target": "gfp"}, {"target": "manual"}, {"arbitrary_macro": "run()"},
    {"settings": {"nuclearProbability": 2}}, {"settings": {"nuclearProbability": "0.5"}},
    {"settings": {"nucleolarMinimumArea": 20, "nucleolarMaximumArea": 5}},
    {"selection": {"field_ids": ["same", "same"]}},
    {"figure": {"plot": {"y_min": 10, "y_max": 1}}},
    {"measurement": {"version": "1.2.0", "mode": "automatic_background"}},
])
def test_invalid_drafts_are_rejected(patch):
    with pytest.raises(ValidationError):
        AnalysisSpec.model_validate({"channel_assignment_version": 0, **patch})


def test_unknown_field_is_not_saved(tmp_path):
    client, _, _, _, path = setup(tmp_path)
    response = client.put(path, headers=HEADERS, json={"version": 0, "spec": {
        "channel_assignment_version": 0, "selection": {"field_ids": ["other-workspace-field"]}}})
    assert response.status_code == 422
    assert client.get(path).json()["spec"] is None


def test_scatter_and_axis_metrics_persist(tmp_path):
    client, _, _, _, path = setup(tmp_path)
    draft = {"channel_assignment_version": 0, "figure": {"plot": {"kind": "scatter"}},
             "statistics": {"metric": "mean", "x_metric": "median", "x_channel_id": "gfp"}}
    response = client.put(path, headers=HEADERS, json={"version": 0, "spec": draft})
    assert response.status_code == 200, response.text
    assert response.json()["spec"]["figure"]["plot"]["kind"] == "scatter"
    assert response.json()["spec"]["statistics"]["x_metric"] == "median"


@pytest.mark.parametrize("method,threshold", [("manual", 15), ("batch_otsu", None)])
def test_exploratory_gfp_intent_saved_without_control_fields(tmp_path, method, threshold):
    client, _, _, _, path = setup(tmp_path)
    gate = {"version": "1.1.0", "gate_protocol": "gfp-gate/3.0.0", "gfp_channel_id": "gfp",
            "method": method, "threshold": threshold, "values": "raw", "keep": "positive"}
    response = client.put(path, headers=HEADERS, json={"version": 0, "spec": {
        "channel_assignment_version": 0, "selection": {"gfp": gate}}})
    assert response.status_code == 200, response.text
    assert response.json()["spec"]["selection"]["gfp"] == gate


def test_migration_creates_empty_spec_table(tmp_path):
    store = Store(tmp_path)
    with store.transaction() as conn:
        conn.exec_driver_sql("DROP TABLE workspace_field_links")
        conn.exec_driver_sql("ALTER TABLE workspace_channel_assignments DROP COLUMN groups")
        conn.exec_driver_sql("ALTER TABLE workspace_channel_assignments DROP COLUMN global_field_ids")
        conn.exec_driver_sql("DROP TABLE workspace_analysis_runs")
        conn.exec_driver_sql("DROP TABLE workspace_analysis_specs")
        conn.exec_driver_sql("UPDATE alembic_version SET version_num = '0005'")
    store.engine.dispose()
    migrated = Store(tmp_path)
    assert migrated.one(workspace_analysis_specs, workspace_id="absent") is None
    with migrated.engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one() == "0009"
