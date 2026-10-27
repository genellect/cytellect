"""A shared development environment accepts registered public files only; installations are unaffected."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from cytellect_api.app import create_app
from cytellect_api.config import Settings
from cytellect_api.public_uploads import load_allowlist
from fastapi.testclient import TestClient
from test_api_optional_channels import metadata
from test_api_worker import HEADERS
from test_region_api import tiff_bytes

ROOT = Path(__file__).resolve().parents[1]
PIXELS = np.arange(144, dtype=np.uint16).reshape(12, 12)
SPEC = json.dumps({"channels": [{"channel_id": "c1", "label": "c1", "identity_confirmed": True}],
                   "metadata": {"condition": "control"}})


def client_for(tmp_path, allowlist):
    app = create_app(Settings(tmp_path, app_origin="http://test", secure_cookies=False, upload_allowlist=allowlist))
    client = TestClient(app)
    assert client.post("/v1/invitations/redeem", json={"token": app.state.store.invite()}, headers=HEADERS).status_code == 200
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "shared"}).json()["id"]
    return client, wid


def upload(client, wid, data):
    return client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS,
                       data={"specification": SPEC}, files={"ch0": ("a.tif", data, "image/tiff")})


def test_unregistered_images_are_refused_and_not_kept(tmp_path):
    registered = tiff_bytes(PIXELS)
    client, wid = client_for(tmp_path, frozenset({hashlib.sha256(registered).hexdigest()}))
    other = upload(client, wid, tiff_bytes(PIXELS + 1))
    assert other.status_code == 403 and other.json()["detail"] == "unregistered_upload"
    assert not any((tmp_path / "workspaces" / wid / "fields").glob("*/*"))
    assert upload(client, wid, registered).status_code == 201
    table = client.post(f"/v1/workspaces/{wid}/tables", headers=HEADERS, files={"file": ("t.csv", b"condition,value\na,1\n", "text/csv")})
    assert table.status_code == 403
    ome = client.post(f"/v1/workspaces/{wid}/region-fields/ome", headers=HEADERS, files={"ome": ("o.tif", tiff_bytes(PIXELS + 2), "image/tiff")})
    assert ome.status_code == 403
    fresh = client.post("/v1/workspaces", headers=HEADERS, json={"title": "fields"}).json()["id"]
    field = client.post(f"/v1/workspaces/{fresh}/fields", headers=HEADERS, data={"metadata": json.dumps(metadata())},
                        files={"dapi": ("d.tif", tiff_bytes(PIXELS + 3), "image/tiff"), "ncl": ("n.tif", registered, "image/tiff")})
    assert field.status_code == 403


def test_installations_accept_their_own_images(tmp_path):
    client, wid = client_for(tmp_path, None)
    assert upload(client, wid, tiff_bytes(PIXELS + 1)).status_code == 201


def test_the_registered_list_is_well_formed_and_refuses_an_empty_list(tmp_path):
    assert len(load_allowlist(ROOT / "fixtures/public/uploads.json")) == 2
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"files": []}))
    with pytest.raises(ValueError, match="upload_allowlist_invalid"):
        load_allowlist(empty)
