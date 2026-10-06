"""Independent threshold source admission on existing fields."""
from cytellect_analysis.region_contracts import RegionSignalRecipe
from test_api_worker import HEADERS, authenticated
from test_region_nuclear_api import upload


def test_signal_request_uses_existing_images_and_default_otsu(tmp_path):
    client, app, _ = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "Signal"}).json()["id"]
    fid = upload(client, wid)
    recipe = RegionSignalRecipe(region_set_id="signal", label="Signal-positive areas", defining_channel_id="hoechst").model_dump(mode="json")
    assert recipe["detector"]["threshold_method"] == "otsu"
    response = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json={"field_ids": [fid], "recipe": recipe, "measurement": {"version": "1.1.0", "mode": "raw_intensity"}, "backgrounds": {}})
    assert response.status_code == 202, response.text
    recipe["defining_channel_id"] = "missing"
    assert client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json={"field_ids": [fid], "recipe": recipe, "measurement": {"version": "1.1.0", "mode": "raw_intensity"}}).status_code == 422
