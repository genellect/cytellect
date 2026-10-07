import json

import numpy as np
from cytellect_api.channel_assignments import apply_channel_assignments, effective_assignments
from cytellect_api.db import fields
from test_api_worker import HEADERS, authenticated
from test_region_api import make_field, tiff_bytes


def test_mapping_applies_only_to_explicit_field_scope_and_future_imports_stay_unassigned(tmp_path):
    client, app, _ = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "scopes"}).json()["id"]
    first = make_field(client, wid).json()["id"]
    path = f"/v1/workspaces/{wid}/channel-assignments"
    assigned = client.put(path, headers=HEADERS, json={"version": 0, "assignments": [{"channel_id": "actin", "stain": "DAPI", "role": "nuclear"}]})
    assert assigned.status_code == 200, assigned.text
    second = make_field(client, wid).json()["id"]
    snapshot = client.get(path).json()
    assert effective_assignments(snapshot, first)["assignments"][0]["stain"] == "DAPI"
    assert effective_assignments(snapshot, second)["assignments"] == []
    changed = client.put(path, headers=HEADERS, json={"version": 1, "field_ids": [second], "assignments": [{"channel_id": "actin", "stain": "GFP", "role": "measure"}]})
    assert changed.status_code == 200, changed.text
    snapshot = changed.json()
    assert snapshot["global_field_ids"] == [first]
    assert effective_assignments(snapshot, first)["assignments"][0]["stain"] == "DAPI"
    assert effective_assignments(snapshot, second)["assignments"][0]["stain"] == "GFP"
    overlaid = apply_channel_assignments(app.state.store, wid, app.state.store.rows(fields, workspace_id=wid), assignment_snapshot=snapshot)
    assert {row["id"]: row["image_info"]["channels"][0]["stain"] for row in overlaid} == {first: "DAPI", second: "GFP"}
    assert client.put(path, headers=HEADERS, json={"version": 1, "field_ids": [second], "assignments": []}).status_code == 409


def test_group_rejects_mixed_configuration_and_cross_workspace_fields(tmp_path):
    client, _, _ = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "groups"}).json()["id"]
    first = make_field(client, wid).json()["id"]
    spec = {"version": "1.1.0", "channels": [{"channel_id": channel, "label": channel, "identity_source": "unresolved"} for channel in ("c1", "c2")]}
    uploaded = client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS, data={"specification": json.dumps(spec)},
        files={"ch0": ("one.tif", tiff_bytes(np.zeros((12, 12), np.uint16)), "image/tiff"), "ch1": ("two.tif", tiff_bytes(np.zeros((12, 12), np.uint16)), "image/tiff")})
    assert uploaded.status_code == 201, uploaded.text
    path = f"/v1/workspaces/{wid}/channel-assignments"
    for selected, code in (([first, uploaded.json()["id"]], "channel_assignment_mixed_configuration"), (["foreign"], "channel_assignment_unknown_field")):
        response = client.put(path, headers=HEADERS, json={"version": 0, "field_ids": selected, "assignments": []})
        assert response.status_code == 422 and response.json()["detail"] == code


def test_historical_snapshot_keeps_legacy_meaning_but_scoped_empty_snapshot_does_not():
    legacy = {"version": 1, "assignments": [{"channel_id": "c1", "stain": "DAPI", "role": "nuclear"}]}
    assert effective_assignments(legacy, "old")["assignments"]
    assert not effective_assignments({**legacy, "groups": [], "global_field_ids": []}, "new")["assignments"]
