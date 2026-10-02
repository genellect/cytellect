"""Real HTTP TIFF ingestion and worker orchestration with deterministic nuclear masks."""
import io
import json

import numpy as np
import pytest
import tifffile
from cytellect_api.db import jobs
from cytellect_api.storage import read_json
from cytellect_worker.main import run_analysis
from test_api_worker import HEADERS, authenticated


def tif_bytes(array, ome=False):
    stream = io.BytesIO()
    tifffile.imwrite(stream, array, ome=ome, metadata={"axes": "CYX" if ome else "YX"})
    return stream.getvalue()


def metadata():
    return {"condition": "test", "experimental_unit": "unit", "sample": "sample", "acquisition_date": "date"}


@pytest.mark.parametrize("recipe_id,signal_role", [("ncl-native-2d", "ncl"), ("gfp-nuclear-2d", "gfp")])
@pytest.mark.parametrize("ome", [False, True])
def test_two_channel_upload_analysis_measurement_and_private_preview(tmp_path, monkeypatch, recipe_id, signal_role, ome):
    client, app, settings = authenticated(tmp_path)
    workspace = client.post("/v1/workspaces", json={"title": "two channels"}, headers=HEADERS).json()
    shape = (16, 16)
    nuclei = np.zeros(shape, np.uint32)
    nuclei[5:11, 5:11] = 1
    nucleoli = np.zeros(shape, np.uint32)
    if signal_role == "ncl":
        nucleoli[7:9, 7:9] = 1
    dapi = (nuclei * 100 + 4).astype(np.uint16)
    signal = (nuclei * 10 + nucleoli * 30 + 2).astype(np.uint16)
    data = {"metadata": json.dumps(metadata())}
    if ome:
        files = {"ome": ("user-name.ome.tif", tif_bytes(np.stack([signal, dapi]), True), "image/tiff")}
        data.update(mapping="[1,0]", channel_roles=json.dumps(["dapi", signal_role]))
    else:
        files = {role: ("private-name.tif", tif_bytes(array), "image/tiff") for role, array in [("dapi", dapi), (signal_role, signal)]}
    uploaded = client.post(f"/v1/workspaces/{workspace['id']}/fields", data=data, files=files, headers=HEADERS)
    assert uploaded.status_code == 201, uploaded.text
    field = uploaded.json()
    fid = field["id"]
    assert field["image_info"]["channel_roles"] == ["dapi", signal_role]
    folder = app.state.store.safe_path("workspaces", workspace["id"], "fields", fid)
    missing = "gfp" if signal_role == "ncl" else "ncl"
    assert not (folder / f"{missing}.npy").exists()
    assert client.get(f"/v1/fields/{fid}/preview").status_code == 200
    assert client.get(f"/v1/fields/{fid}/preview?channel={missing}").status_code == 422
    body = {"recipe": {"id": recipe_id}, "backgrounds": {fid: {"polygon": [[0, 0], [3, 0], [3, 3], [0, 3]], "confirmed": True}}}
    queued = client.post(f"/v1/workspaces/{workspace['id']}/analyses", json=body, headers=HEADERS)
    assert queued.status_code == 202, queued.text
    def deterministic_masks(field, folder, channels, recipe, settings, destination, nuclei=None):
        assert set(channels) == {"dapi", signal_role}
        n = np.zeros(shape, np.uint32)
        n[5:11, 5:11] = 1
        return n, nucleoli, np.zeros_like(n), {"engine": "deterministic-test-labels"}
    monkeypatch.setattr("cytellect_worker.main._initial_masks", deterministic_masks)
    job = app.state.store.one(jobs, id=queued.json()["job_id"])
    output = tmp_path / "test-worker-result"
    run_analysis(app.state.store, settings, job, output)
    result = read_json(output / "measurements.json")
    assert result["field_failures"] == [] and len(result["cells"]) == 1
    row = result["cells"][0]
    assert row["channel_availability"][missing] is False
    if signal_role == "ncl":
        assert row["gfp_mean_corrected"] is None
        assert row["ncl_log2_nucleoplasm_over_nucleoli"] == -2
        body["recipe"]["gfp_gate"] = "manual"
        body["recipe"]["gfp_threshold"] = 1
        rejected = client.post(f"/v1/workspaces/{workspace['id']}/analyses", json=body, headers=HEADERS)
        assert rejected.status_code == 422 and rejected.json()["detail"] == "recipe_required_channels_missing"
    else:
        assert row["gfp_mean_corrected"] == 10
        assert row["ncl_nucleus_mean_corrected"] is None and row["nucleolar_count"] is None
        assert result["nucleoli"] == []


def test_ome_role_map_is_explicit_and_not_inferred_from_channel_count(tmp_path):
    client, _, _ = authenticated(tmp_path)
    workspace = client.post("/v1/workspaces", json={"title": "map"}, headers=HEADERS).json()
    image = tif_bytes(np.zeros((2, 16, 16), np.uint16), True)
    for roles in ('["dapi","dapi"]', '["ncl","gfp"]', '["dapi","ncl","gfp"]'):
        result = client.post(f"/v1/workspaces/{workspace['id']}/fields",
                             data={"metadata": json.dumps(metadata()), "mapping": "[0,1]", "channel_roles": roles},
                             files={"ome": ("input.tif", image, "image/tiff")}, headers=HEADERS)
        assert result.status_code == 422
