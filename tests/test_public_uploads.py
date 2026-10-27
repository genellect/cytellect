"""A shared development environment accepts registered public files only; installations are unaffected.

Every upload here is a registered public real image. A BBBC039 image, registered in the repository but not on
the upload list, stands in for an image the shared environment must refuse.
"""
import hashlib
import json
from pathlib import Path

import pytest
from cytellect_api.app import create_app
from cytellect_api.config import Settings
from cytellect_api.public_uploads import load_allowlist
from fastapi.testclient import TestClient
from test_api_optional_channels import metadata
from test_api_worker import HEADERS

ROOT = Path(__file__).resolve().parents[1]
UPLOADS = ROOT / "fixtures/public/uploads.json"
LISTED = (ROOT / "fixtures/public/bbbc013/A01-dapi.tif").read_bytes()
LISTED_GFP = (ROOT / "fixtures/public/bbbc013/A01-gfp.tif").read_bytes()
UNLISTED = (ROOT / "fixtures/public/bbbc039/image/IXMtest_A09_s1_w1CE70AD49-290D-4312-82E6-CDC717F32637.tif").read_bytes()
SPEC = json.dumps({"channels": [{"channel_id": "dapi", "label": "DAPI", "identity_confirmed": True}],
                   "metadata": {"condition": "control"}})


def client_for(tmp_path, allowlist):
    app = create_app(Settings(tmp_path, app_origin="http://test", secure_cookies=False, upload_allowlist=allowlist))
    client = TestClient(app)
    assert client.post("/v1/invitations/redeem", json={"token": app.state.store.invite()}, headers=HEADERS).status_code == 200
    return client


def workspace(client):
    return client.post("/v1/workspaces", headers=HEADERS, json={"title": "shared"}).json()["id"]


def region_field(client, wid, data):
    return client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS,
                       data={"specification": SPEC}, files={"ch0": ("a.tif", data, "image/tiff")})


def test_only_listed_public_images_are_accepted_and_refused_files_are_not_kept(tmp_path):
    client = client_for(tmp_path, load_allowlist(UPLOADS))
    wid = workspace(client)
    refused = region_field(client, wid, UNLISTED)
    assert refused.status_code == 403 and refused.json()["detail"] == "unregistered_upload"
    assert not any((tmp_path / "workspaces" / wid / "fields").glob("*/*"))
    assert region_field(client, wid, LISTED).status_code == 201
    ome = client.post(f"/v1/workspaces/{wid}/region-fields/ome", headers=HEADERS, files={"ome": ("o.tif", UNLISTED, "image/tiff")})
    assert ome.status_code == 403
    table = client.post(f"/v1/workspaces/{wid}/tables", headers=HEADERS, files={"file": ("t.csv", UNLISTED, "text/csv")})
    assert table.status_code == 403
    fields = workspace(client)
    mixed = client.post(f"/v1/workspaces/{fields}/fields", headers=HEADERS, data={"metadata": json.dumps(metadata())},
                        files={"dapi": ("d.tif", LISTED, "image/tiff"), "gfp": ("g.tif", UNLISTED, "image/tiff")})
    assert mixed.status_code == 403
    listed = client.post(f"/v1/workspaces/{fields}/fields", headers=HEADERS, data={"metadata": json.dumps(metadata())},
                         files={"dapi": ("d.tif", LISTED, "image/tiff"), "gfp": ("g.tif", LISTED_GFP, "image/tiff")})
    assert listed.status_code == 201, listed.text


def test_installations_accept_images_outside_the_list(tmp_path):
    client = client_for(tmp_path, None)
    assert region_field(client, workspace(client), UNLISTED).status_code == 201


def test_the_upload_list_matches_the_committed_public_images_and_refuses_an_empty_list(tmp_path):
    listed = load_allowlist(UPLOADS)
    assert {hashlib.sha256(LISTED).hexdigest(), hashlib.sha256(LISTED_GFP).hexdigest()} <= listed
    assert hashlib.sha256(UNLISTED).hexdigest() not in listed
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"files": []}))
    with pytest.raises(ValueError, match="upload_allowlist_invalid"):
        load_allowlist(empty)
