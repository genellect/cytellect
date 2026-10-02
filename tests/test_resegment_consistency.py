from cytellect_worker.main import process_one
from test_api_worker import HEADERS, authenticated
from test_lifecycle import demo


def test_changed_recipe_requires_all_fields_and_keeps_dirty_measurement_settings(tmp_path):
    client, app, settings = authenticated(tmp_path)
    _, fids, rid, _ = demo(client, app, settings)
    original = client.get(f"/v1/revisions/{rid}").json()["config"]
    recipe = {**original["recipe"], "smoothing_sigma_px": 1.0}
    rejected = client.post(f"/v1/revisions/{rid}/resegment", headers=HEADERS,
                           json={"field_ids": [fids[0]], "recipe": recipe})
    assert rejected.status_code == 409
    assert rejected.json()["detail"] == "resegment_changed_recipe_requires_all_fields"
    backgrounds = {**original["backgrounds"], fids[0]: {"confirmed": True,
                    "polygon": [[0, 0], [2, 0], [2, 2], [0, 2]]}}
    exclusions = [{"field_id": fids[0], "nucleus_id": 1, "reason": "specified before redetection"}]
    accepted = client.post(f"/v1/revisions/{rid}/resegment", headers=HEADERS,
                           json={"field_ids": fids, "recipe": recipe,
                                 "backgrounds": backgrounds, "exclusions": exclusions})
    assert accepted.status_code == 202
    latest = accepted.json()["revision_id"]
    saved = client.get(f"/v1/revisions/{latest}").json()["config"]
    assert saved["recipe"]["smoothing_sigma_px"] == 1.0
    assert saved["backgrounds"] == backgrounds
    assert saved["exclusions"] == exclusions
    assert client.get(f"/v1/revisions/{rid}").json()["config"] == original
    assert process_one(app.state.store, settings)
    result = client.get(f"/v1/revisions/{latest}/measurements").json()
    assert result["field_failures"] == []
    first = next(row for row in result["cells"] if row["field_id"] == fids[0] and row["nucleus_id"] == 1)
    assert first["excluded"] and first["exclusion_reason"] == exclusions[0]["reason"]


def test_resegment_rejects_unknown_or_unconfirmed_measurement_changes(tmp_path):
    client, app, settings = authenticated(tmp_path)
    _, fids, rid, _ = demo(client, app, settings)
    cases = [
        {"backgrounds": {}},
        {"backgrounds": {"missing": {"confirmed": True, "polygon": [[0, 0], [2, 0], [1, 1]]}}},
        {"exclusions": [{"field_id": "missing", "reason": "not in revision"}]},
    ]
    for change in cases:
        response = client.post(f"/v1/revisions/{rid}/resegment", headers=HEADERS,
                               json={"field_ids": [fids[0]], **change})
        assert response.status_code == 422
