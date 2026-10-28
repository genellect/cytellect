"""Rejected region uploads name a cause the researcher can act on, with public BBBC039 pixels."""

import json
import sys
from pathlib import Path

import numpy as np
import pytest
import tifffile
from test_api_worker import HEADERS, authenticated
from test_region_api import tiff_bytes

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from public_bbbc039 import FIXTURE, decode_ground_truth, verify  # noqa: E402


@pytest.fixture(scope="module")
def public_field():
    field = verify()["images"][0]
    image = tifffile.imread(FIXTURE / field["image"]["path"])
    labels = decode_ground_truth(FIXTURE / field["mask"]["path"]).astype(np.uint32)
    assert image.dtype == np.uint16 and image.shape == labels.shape and labels.max() > 0
    return tiff_bytes(image), labels


def send(client, wid, channel, labels=None):
    spec = {"channels": [{"channel_id": "c1", "label": "Hoechst", "identity_confirmed": True}], "metadata": {}}
    files = {"ch0": ("A09-hoechst.tif", channel, "image/tiff")}
    if labels is not None:
        files["labels"] = ("A09-labels.tif", tiff_bytes(labels), "image/tiff")
    return client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS,
                       data={"specification": json.dumps(spec)}, files=files)


def test_a_label_image_sent_as_a_channel_is_named_as_the_wrong_bit_depth(tmp_path, public_field):
    client, _, _ = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "intake"}).json()["id"]
    image, labels = public_field
    rejected = send(client, wid, tiff_bytes(labels))
    assert rejected.status_code == 422 and rejected.json()["detail"] == "region_image_bit_depth_unsupported"
    assert "A09" not in rejected.text
    assert send(client, wid, image, labels).status_code == 201


def test_label_problems_are_reported_as_label_problems(tmp_path, public_field):
    client, _, _ = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "intake"}).json()["id"]
    image, labels = public_field
    cropped = send(client, wid, image, labels[:-1])
    assert cropped.status_code == 422 and cropped.json()["detail"] == "region_labels_shape_or_type_mismatch"
    floating = send(client, wid, image, labels.astype(np.float32))
    assert floating.status_code == 422 and floating.json()["detail"] == "region_labels_shape_or_type_mismatch"
    assert "A09" not in cropped.text + floating.text
    assert client.get(f"/v1/workspaces/{wid}/region-fields").json() == []
