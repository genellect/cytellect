"""Channel corrections persist while original pixels and scientific history stay immutable."""
import copy
import json

import numpy as np
from cytellect_api.app import create_app
from cytellect_api.db import Store, fields, revisions, workspace_channel_assignments
from cytellect_worker.main import cleanup
from fastapi.testclient import TestClient
from test_api_worker import HEADERS, authenticated
from test_region_api import make_field, region_request, tiff_bytes


def setup(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "channels"}).json()["id"]
    field = make_field(client, wid).json()
    return client, app, settings, wid, field


def assignment(stain="GFP", role="measure", version=0):
    return {"version": version, "assignments": [{"channel_id": "actin", "stain": stain, "role": role}]}


def test_assignment_persists_without_changing_upload_pixels_or_old_snapshot(tmp_path):
    client, app, settings, wid, field = setup(tmp_path)
    path = f"/v1/workspaces/{wid}/channel-assignments"
    assert client.get(path).json() == {"version": 0, "assignments": [], "global_field_ids": [], "groups": []}
    pixels_path = app.state.store.safe_path("workspaces", wid, "fields", field["id"], "channel-actin.npy")
    original_pixels = pixels_path.read_bytes()
    original_record = copy.deepcopy(dict(app.state.store.one(fields, id=field["id"])))
    request = region_request(field["id"])
    old_response = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=request)
    assert old_response.status_code == 202, old_response.text
    old_id = old_response.json()["revision_id"]
    old_snapshot = copy.deepcopy(app.state.store.one(revisions, id=old_id)["config"])
    response = client.put(path, headers=HEADERS, json=assignment())
    assert response.status_code == 200, response.text
    assert response.json() == {**assignment(version=1), "global_field_ids": [field["id"]], "groups": []}
    restarted = TestClient(create_app(settings))
    restarted.cookies.update(client.cookies)
    assert restarted.get(path).json() == response.json()
    new_response = restarted.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS,
                                 json={**request, "backgrounds": {}, "measurement": {"version": "1.1.0", "mode": "raw_intensity"}})
    assert new_response.status_code == 202, new_response.text
    config = app.state.store.one(revisions, id=new_response.json()["revision_id"])["config"]
    channel = config["field_snapshot"][field["id"]]["image_info"]["channels"][0]
    assert channel["stain"] == "GFP" and channel["identity_source"] == "user_entered"
    assert config["channel_assignments"] == response.json()
    assert app.state.store.one(revisions, id=old_id)["config"] == old_snapshot
    assert dict(app.state.store.one(fields, id=field["id"])) == original_record
    assert pixels_path.read_bytes() == original_pixels


def test_assignment_ownership_cas_unknown_and_unresolved(tmp_path):
    client, app, _, wid, _ = setup(tmp_path)
    path = f"/v1/workspaces/{wid}/channel-assignments"
    foreign = TestClient(app)
    foreign.post("/v1/invitations/redeem", headers=HEADERS, json={"token": app.state.store.invite()})
    assert foreign.get(path).status_code == 404
    assert foreign.put(path, headers=HEADERS, json=assignment()).status_code == 404
    unknown = assignment()
    unknown["assignments"][0]["channel_id"] = "missing"
    assert client.put(path, headers=HEADERS, json=unknown).status_code == 422
    assert client.put(path, headers=HEADERS, json={"version": 0, "assignments": []}).status_code == 422
    assert client.put(path, headers=HEADERS, json=assignment(" ")).status_code == 422
    assert client.put(path, json=assignment()).status_code == 403
    saved = client.put(path, headers=HEADERS, json=assignment(None, "unused"))
    assert saved.status_code == 200
    assert saved.json()["assignments"] == assignment(None, "unused", 1)["assignments"]
    assert client.put(path, headers=HEADERS, json=assignment()).status_code == 409
    assert client.get(path).json() == saved.json()


def test_additional_import_uses_corrected_identity_and_retention_removes_assignments(tmp_path):
    client, app, _, wid, _ = setup(tmp_path)
    path = f"/v1/workspaces/{wid}/channel-assignments"
    assert client.put(path, headers=HEADERS, json=assignment()).status_code == 200
    spec = {"version": "1.1.0", "channels": [{"channel_id": "actin", "label": "GFP", "stain": "GFP", "identity_source": "user_entered"}]}
    response = client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS,
        data={"specification": json.dumps(spec)},
        files={"ch0": ("additional.tif", tiff_bytes(np.full((12, 12), 10, np.uint16)), "image/tiff")})
    assert response.status_code == 201, response.text
    client.delete(f"/v1/workspaces/{wid}", headers=HEADERS)
    cleanup(app.state.store)
    assert app.state.store.one(workspace_channel_assignments, workspace_id=wid) is None


def test_upgrade_from_previous_schema(tmp_path):
    store = Store(tmp_path)
    with store.transaction() as conn:
        conn.exec_driver_sql("DROP TABLE workspace_field_links")
        conn.exec_driver_sql("DROP TABLE workspace_analysis_runs")
        conn.exec_driver_sql("DROP TABLE workspace_analysis_specs")
        conn.exec_driver_sql("DROP TABLE workspace_channel_assignments")
        conn.exec_driver_sql("UPDATE alembic_version SET version_num = '0004'")
    store.engine.dispose()
    upgraded = Store(tmp_path)
    with upgraded.engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one() == "0009"
        assert conn.exec_driver_sql("SELECT count(*) FROM workspace_channel_assignments").scalar_one() == 0


def test_explicit_unused_and_non_nuclear_roles_block_detection(tmp_path):
    from test_region_nuclear_contracts import nuclear_recipe

    client, _, _, wid, field = setup(tmp_path)
    path = f"/v1/workspaces/{wid}/channel-assignments"
    recipe = nuclear_recipe()
    recipe["defining_channel_id"] = "actin"
    for version, role, expected in [(0, "unused", "channel_assignment_unused"), (1, "measure", "channel_assignment_nuclear_role_required")]:
        saved = client.put(path, headers=HEADERS, json=assignment("DAPI", role, version))
        assert saved.status_code == 200, saved.text
        response = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS,
            json={"field_ids": [field["id"]], "recipe": recipe})
        assert response.status_code == 422 and response.json()["detail"] == expected
    ambiguous = {"version": 2, "assignments": [
        {"channel_id": "actin", "stain": "DAPI", "role": "nuclear"},
        {"channel_id": "another", "stain": "Hoechst", "role": "nuclear"},
    ]}
    assert client.put(path, headers=HEADERS, json=ambiguous).status_code == 422


def test_assignment_put_browser_preflight(tmp_path):
    client, _, _, wid, _ = setup(tmp_path)
    path = f"/v1/workspaces/{wid}/channel-assignments"
    response = client.options(path, headers={"origin": "http://test", "access-control-request-method": "PUT",
        "access-control-request-headers": "content-type,x-cytellect-request"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://test"
    assert "PUT" in response.headers["access-control-allow-methods"]
    foreign = client.options(path, headers={"origin": "http://foreign", "access-control-request-method": "PUT"})
    assert foreign.status_code == 400 and "access-control-allow-origin" not in foreign.headers
