"""Opt-in detection resolution does not replace original pixels or saved masks."""
import copy

import numpy as np
import pytest
from cytellect_analysis.region_contracts import (
    AdoptedNuclearRecipe,
    RegionAnalysisRequest,
    ScaledNuclearRecipe,
)
from cytellect_analysis.region_exports import region_methods
from cytellect_api.storage import read_json
from cytellect_worker import regions
from pydantic import ValidationError
from test_api_worker import HEADERS, authenticated
from test_region_nuclear_api import upload
from test_region_nuclear_worker import detected_labels, nuclear_fields
from test_region_worker import execute


def scaled_recipe(size=320):
    return ScaledNuclearRecipe(region_set_id="nuclei", label="Nuclei", defining_channel_id="dna",
                               nuclear_role_source="recorded_stain", detection_max_side_px=size)


@pytest.mark.parametrize("value", [63, 2049, True, 320.0, "320", None])
def test_scale_requires_explicit_bounded_integer(value):
    with pytest.raises(ValidationError):
        scaled_recipe(value)


def test_scale_is_separate_version_and_requires_parameter():
    data = scaled_recipe().model_dump(mode="json")
    assert data["version"] == "1.5.0"
    assert RegionAnalysisRequest.model_validate({"field_ids": ["f1"], "recipe": data}).recipe == scaled_recipe()
    data.pop("detection_max_side_px")
    with pytest.raises(ValidationError):
        ScaledNuclearRecipe.model_validate(data)
    data["version"] = "1.2.0"
    original = AdoptedNuclearRecipe.model_validate(data)
    assert "detection_max_side_px" not in original.model_dump()


def test_worker_forwards_scale_and_preserves_original_measurements_and_reused_mask(tmp_path, monkeypatch):
    store, settings, config = nuclear_fields(tmp_path)
    config["recipe"] = scaled_recipe().model_dump(mode="json")
    calls = []
    def detector(image, parameters, destination, executable, scratch_root=None, *, detection_max_side=None):
        assert not image.flags.writeable
        calls.append((image.copy(), detection_max_side))
        return detected_labels(), {"requested_detection_max_side_px": detection_max_side}
    monkeypatch.setattr(regions, "detect_nuclei", detector)
    report = execute(store, settings, config)
    assert not report["field_failures"]
    assert len(calls) == 1 and calls[0][1] == 320
    assert {(r["region_id"], r["channel_id"], r["mean"]) for r in report["field_tables"]["f1"]["rows"]} == {
        (7, "dna", 6), (7, "actin", 26), (19, "dna", 20), (19, "actin", 40)}
    provenance = read_json(store.safe_path("results", "r1", "provenance.json"))
    assert "Requested detection maximum side: 320 px" in region_methods(config, report, provenance)
    original = np.load(store.safe_path("results", "r1", "f1", "labels.npy")).copy()
    repeated = execute(store, settings, {**config, "reuse_revision": "r1"}, "r2")
    assert not repeated["field_failures"] and len(calls) == 1
    np.testing.assert_array_equal(original, np.load(store.safe_path("results", "r1", "f1", "labels.npy")))
    event = read_json(store.safe_path("results", "r2", "provenance.json"))["fields"]["f1"]["detector"]
    assert event["detection_max_side_px"] == 320 and not event["executed_this_attempt"]
    output = store.safe_path("results", "export-scaled")
    regions.run_region_export(store, {"revision_id": "r2", "workspace_id": "w", "payload": {}}, output)
    assert (output / "analysis.zip").is_file()
    changed = copy.deepcopy(config)
    changed["reuse_revision"] = "r1"
    changed["recipe"]["detection_max_side_px"] = 640
    with pytest.raises(ValueError):
        execute(store, settings, changed, "r3")
    np.testing.assert_array_equal(original, np.load(store.safe_path("results", "r1", "f1", "labels.npy")))


def test_scaled_recipe_api_queues_without_changing_registered_image(tmp_path):
    client, app, _ = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "Scale test"}).json()["id"]
    fid = upload(client, wid)
    before = client.get(f"/v1/workspaces/{wid}/region-fields").json()
    recipe = scaled_recipe().model_dump(mode="json")
    recipe["defining_channel_id"] = "hoechst"
    response = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json={
        "field_ids": [fid], "recipe": recipe,
        "measurement": {"version": "1.1.0", "mode": "raw_intensity"}})
    assert response.status_code == 202, response.text
    assert client.get(f"/v1/workspaces/{wid}/region-fields").json() == before
