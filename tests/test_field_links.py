"""Reference images remain immutable and can be restored to the analysis selection."""

from cytellect_api.db import fields
from fastapi.testclient import TestClient
from test_api_worker import HEADERS, authenticated
from test_region_api import make_field


def setup(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "reference"}).json()["id"]
    first = make_field(client, wid, labels=False).json()["id"]
    second = make_field(client, wid, labels=False).json()["id"]
    return client, app, wid, first, second, f"/v1/workspaces/{wid}/field-links"


def test_reference_switch_preserves_pixels_results_and_previous_exclusion(tmp_path):
    client, app, wid, first, second, path = setup(tmp_path)
    original = dict(app.state.store.one(fields, id=second))
    image = app.state.store.safe_path("workspaces", wid, "fields", second, "channel-actin.npy")
    pixels = image.read_bytes()
    response = client.put(
        f"{path}/{second}",
        headers=HEADERS,
        json={"version": 0, "selection_version": 0, "kind": "reference", "reference_for_field_id": first},
    )
    assert response.status_code == 200, response.text
    assert response.json()["entries"][0]["reference_for_field_id"] == first
    selection = client.get(f"/v1/workspaces/{wid}/selection").json()
    assert next(row for row in selection["entries"] if row["field_id"] == second)["exclusion_reason"]
    assert dict(app.state.store.one(fields, id=second)) == original
    assert image.read_bytes() == pixels
    restored = client.put(
        f"{path}/{second}", headers=HEADERS, json={"version": 1, "selection_version": 1, "kind": "analysis"}
    )
    assert restored.status_code == 200, restored.text
    selection = client.get(f"/v1/workspaces/{wid}/selection").json()
    assert next(row for row in selection["entries"] if row["field_id"] == second)["exclusion_reason"] is None


def test_owned_links_reject_unknown_self_reference_stale_cas_and_chains(tmp_path):
    client, app, wid, first, second, path = setup(tmp_path)
    foreign = TestClient(app)
    foreign.post("/v1/invitations/redeem", headers=HEADERS, json={"token": app.state.store.invite()})
    body = {"version": 0, "selection_version": 0, "kind": "reference", "reference_for_field_id": first}
    assert foreign.get(path).status_code == 404
    assert foreign.put(f"{path}/{second}", headers=HEADERS, json=body).status_code == 404
    assert client.put(f"{path}/{second}", json=body).status_code == 403
    assert client.put(f"{path}/{first}", headers=HEADERS, json=body).status_code == 422
    assert (
        client.put(
            f"{path}/{second}", headers=HEADERS, json={**body, "reference_for_field_id": "unknown"}
        ).status_code
        == 404
    )
    assert client.put(f"{path}/{second}", headers=HEADERS, json=body).status_code == 200
    assert client.put(f"{path}/{second}", headers=HEADERS, json=body).status_code == 409
    assert (
        client.put(
            f"{path}/{first}",
            headers=HEADERS,
            json={**body, "version": 1, "selection_version": 1, "reference_for_field_id": second},
        ).status_code
        == 409
    )
