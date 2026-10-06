"""Compartment requests cannot select an absent or unowned nuclear source."""
from cytellect_analysis.region_contracts import RegionCompartmentRecipe
from test_api_worker import HEADERS, authenticated
from test_region_nuclear_api import upload


def test_missing_nuclear_source_is_rejected_before_job_creation(tmp_path):
    client, app, _ = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "Compartments"}).json()["id"]
    fid = upload(client, wid)
    recipe = RegionCompartmentRecipe(region_set_id="nucleoli", label="NCL candidates", compartment="nucleoli", nuclear_revision_id="absent", nuclear_channel_id="dna", defining_channel_id="hoechst").model_dump(mode="json")
    response = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json={"field_ids": [fid], "recipe": recipe, "measurement": {"version": "1.1.0", "mode": "raw_intensity"}})
    assert response.status_code == 422
    assert response.json()["detail"] == "compartment_nuclear_source_invalid"
    assert client.get("/v1/revisions/absent/region-compartment-status").status_code == 404
