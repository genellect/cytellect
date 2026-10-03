"""Nuclear-source preflight retains real channel identity and bounded execution."""
import json

import numpy as np
import pytest
from cytellect_api.db import jobs
from test_api_worker import HEADERS, authenticated
from test_region_api import tiff_bytes
from test_region_nuclear_contracts import nuclear_recipe


def upload(client, wid, *, shape=(12, 12), labels=False):
    spec = {"channels": [{"channel_id": "hoechst", "label": "Hoechst", "stain": "Hoechst 33342",
                          "identity_confirmed": True}]}
    files = {"ch0": ("image.tif", tiff_bytes(np.full(shape, 10, np.uint16)), "image/tiff")}
    if labels:
        files["labels"] = ("labels.tif", tiff_bytes(np.zeros(shape, np.uint32)), "image/tiff")
    response = client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS,
                           data={"specification": json.dumps(spec)}, files=files)
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.mark.parametrize("case,expected", [
    ("valid", None), ("labels", "nuclear_source_requires_no_imported_labels"),
    ("large", "fiji_detection_capacity_exceeded"), ("channel", "unknown_defining_channel"),
])
def test_nuclear_queue_does_not_guess_channels_or_resize_input(tmp_path, case, expected):
    client, app, _ = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "Nuclear source"}).json()["id"]
    fid = upload(client, wid, labels=case == "labels", shape=(2050, 20) if case == "large" else (12, 12))
    recipe = nuclear_recipe()
    if case == "channel":
        recipe["defining_channel_id"] = "gfp"
    response = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json={
        "field_ids": [fid], "recipe": recipe,
        "backgrounds": {fid: {"hoechst": {"confirmed": True, "polygon": [[0, 0], [2, 0], [2, 2]]}}},
    })
    if expected is not None:
        assert response.status_code == 422 and response.json()["detail"] == expected
        assert app.state.store.rows(jobs, workspace_id=wid) == []
    else:
        assert response.status_code == 202, response.text
        fields = client.get(f"/v1/workspaces/{wid}/region-fields").json()
        assert fields[0]["image_info"]["channels"][0]["stain"] == "Hoechst 33342"
        assert list(fields[0]["image_info"]["channel_arrays"]) == ["hoechst"]
