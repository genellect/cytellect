import json

import numpy as np
from cytellect_worker.regions import run_region_analysis
from test_api_worker import HEADERS, authenticated
from test_region_api import tiff_bytes

RECIPE = {"version": "1.2.0", "region_set_id": "nuclei", "label": "Nuclei", "source": "stardist_nuclear",
          "defining_channel_id": "dapi", "nuclear_role_source": "recorded_stain"}
RAW = {"version": "1.1.0", "mode": "raw_intensity"}


def field(gfp_values):
    labels = np.zeros((100, 100), np.uint32)
    dapi = np.full(labels.shape, 10, np.uint16)
    gfp = np.full(labels.shape, 5, np.uint16)
    for index, value in enumerate(gfp_values):
        y, x = divmod(index, 5)
        labels[y * 20 + 4:y * 20 + 14, x * 20 + 4:x * 20 + 14] = index + 1
        gfp[labels == index + 1] = value
    dapi[labels > 0] = 500
    return labels, dapi, gfp


def test_gfp_gate_uses_control_percentile_per_date_on_adopted_nuclei(tmp_path, monkeypatch):
    client, app, settings = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "Synthetic fixture"}).json()["id"]
    planes = {"control": field([20 + i for i in range(25)]), "treated": field([10, 40, 50, 60, 15] + [30] * 20)}
    spec = {"version": "1.1.0", "channels": [{"channel_id": "dapi", "label": "DAPI", "stain": "DAPI", "identity_source": "filename"},
                                              {"channel_id": "gfp", "label": "GFP", "stain": "GFP", "identity_source": "filename"}],
            "metadata": {"acquisition_date": "d1"}}
    revisions = {}
    for name, (labels, dapi, gfp) in planes.items():
        uploaded = client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS, data={"specification": json.dumps(spec)},
                               files={"ch0": ("a.tif", tiff_bytes(dapi), "image/tiff"), "ch1": ("b.tif", tiff_bytes(gfp), "image/tiff")})
        assert uploaded.status_code == 201, uploaded.text
        fid = uploaded.json()["id"]
        monkeypatch.setattr("cytellect_worker.regions.detect_nuclei", lambda *a, _labels=labels, **k: (_labels, {"engine": "test-fixture"}))
        accepted = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS,
                               json={"field_ids": [fid], "recipe": RECIPE, "measurement": RAW, "backgrounds": {}})
        assert accepted.status_code == 202, accepted.text
        claimed = app.state.store.claim()
        output = app.state.store.safe_path("results", claimed["id"])
        run_region_analysis(app.state.store, settings, claimed, output)
        assert app.state.store.finish(claimed, app.state.store.relative_path(output))
        revisions[name] = (fid, accepted.json()["revision_id"])
    body = {"gfp_channel_id": "gfp", "percentile": 99, "fields": [
        {"field_id": revisions["control"][0], "revision_id": revisions["control"][1], "control": True},
        {"field_id": revisions["treated"][0], "revision_id": revisions["treated"][1]}]}
    gated = client.post(f"/v1/workspaces/{wid}/gfp-gate", headers=HEADERS, json=body)
    assert gated.status_code == 200, gated.text
    result = gated.json()
    threshold = result["dates"]["d1"]["threshold"]
    assert threshold == np.percentile([20 + i for i in range(25)], 99)
    assert result["field_counts"][revisions["treated"][0]] == {"positive": 2, "negative": 23, "control": 0, "unselected": 0}
    no_controls = client.post(f"/v1/workspaces/{wid}/gfp-gate", headers=HEADERS, json={**body, "fields": body["fields"][1:]})
    assert no_controls.status_code == 422
    client.close()
    app.state.store.engine.dispose()
