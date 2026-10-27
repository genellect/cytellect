"""The researcher's field names label figures and legends; field IDs stay beside them.

Uploads reuse the minimal 12x12 integer label fixture of test_region_api (synthetic: one
labelled square); the names are labels only and no measurement depends on them.
"""
import copy
import json

import numpy as np
import pytest
from cytellect_analysis.descriptive_figures import _caption
from cytellect_analysis.descriptive_pages import field_labels
from cytellect_api.db import fields, jobs
from cytellect_api.storage import read_json
from cytellect_worker.main import process_one
from test_api_worker import HEADERS, authenticated
from test_descriptive_pages import description
from test_region_api import region_request, tiff_bytes
from test_region_ome import image_bytes

KEY = "20000000-0000-0000-0000-000000000001"


def named_field(client, wid, name, *, key=None):
    spec = {"channels": [{"channel_id": "actin", "label": "Actin", "identity_confirmed": True}],
            "metadata": {"condition": "control"}, "display_name": name}
    if key:
        spec["client_upload_id"] = key
    pixels = np.full((12, 12), 10, np.uint16)
    pixels[4:6, 4:6] = np.array([[20, 30], [40, 50]], dtype=np.uint16)
    plane = np.zeros((12, 12), np.uint32)
    plane[4:6, 4:6] = 17
    return client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS, data={"specification": json.dumps(spec)},
                       files={"ch0": ("untrusted-original-name.tif", tiff_bytes(pixels), "image/tiff"),
                              "labels": ("labels.tif", tiff_bytes(plane), "image/tiff")})


def test_names_are_saved_labels_and_never_paths_or_identity(tmp_path):
    client, app, _ = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "Names"}).json()["id"]
    for invalid in ("", " A01", "A\u000701", "x" * 121):
        assert named_field(client, wid, invalid).status_code == 422
    first = named_field(client, wid, "A01", key=KEY)
    assert first.status_code == 201, first.text
    assert first.json()["display_name"] == "A01" and "untrusted-original-name" not in first.text
    assert named_field(client, wid, "A01", key=KEY).json() == first.json()
    assert named_field(client, wid, "A06", key=KEY).status_code == 409
    assert [row["display_name"] for row in app.state.store.rows(fields, workspace_id=wid)] == ["A01"]
    content, _ = image_bytes(names=["DAPI", "GFP", "NCL", "dye"])
    ome = {"ome": ("private-name.ome.tif", content, "image/tiff")}
    assert client.post(f"/v1/workspaces/{wid}/region-fields/ome", headers=HEADERS,
                       data={"display_name": "B\u000702"}, files=ome).status_code == 422
    saved = client.post(f"/v1/workspaces/{wid}/region-fields/ome", headers=HEADERS,
                        data={"display_name": "B02"}, files=ome)
    assert saved.status_code == 201 and saved.json()["display_name"] == "B02"
    assert "private-name" not in saved.text


def test_paged_figure_legend_and_methods_name_fields_with_their_ids(tmp_path):
    client, app, settings = authenticated(tmp_path)
    store = app.state.store
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "Labels"}).json()["id"]
    a01, a06 = (named_field(client, wid, name).json()["id"] for name in ("A01", "A06"))
    config = region_request(a01)
    config["field_ids"] = [a01, a06]
    config["backgrounds"] = {fid: region_request(fid)["backgrounds"][fid] for fid in (a01, a06)}
    rid = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=config).json()["revision_id"]
    assert process_one(store, settings)
    edited = client.post(f"/v1/revisions/{rid}/region-edits", headers=HEADERS, json={
        "field_id": a01, "region_set_id": "objects", "operation": "add", "polygon": [[8, 8], [11, 8], [11, 11], [8, 11]]})
    rid = edited.json()["revision_id"]
    assert process_one(store, settings)
    assert client.post(f"/v1/revisions/{rid}/review", headers=HEADERS).status_code == 200
    body = {"mode": "descriptive", "selection": {"source": "region", "region_set_id": "objects", "metric": "area_px"},
            "plot": {"preset": "nature-single", "language": "en"},
            "figure_policy": {"version": "2.0.0", "layout": "field-pages"}}
    jid = client.post(f"/v1/revisions/{rid}/descriptive", headers=HEADERS, json=body).json()["job_id"]
    assert process_one(store, settings)
    result = client.get(f"/v1/jobs/{jid}/result").json()
    assert result["figure"]["status"] == "ready"
    assert {field["field_id"]: field["display_name"] for field in result["source_fields"]} == {a01: "A01", a06: "A06"}
    folder = store.safe_path(store.one(jobs, id=jid)["result_dir"])
    assert read_json(folder / "figure-data.json")["field_labels"] == {a01: "A01", a06: "A06"}
    caption = client.get(f"/v1/jobs/{jid}/files/figure-caption.md").text
    assert f"- A01: field_id={a01};" in caption and f"A06: field_id={a06}" in caption
    assert "A01: 1 added (1 initial, 2 measured regions)" in caption
    methods = client.get(f"/v1/jobs/{jid}/files/methods.md").text
    assert f"A01 (field_id={a01}): 1 initial regions; 1 added; 2 regions measured." in methods
    assert "A01" in (folder / "figure-001.svg").read_text(encoding="utf-8")


def test_tick_labels_fall_back_to_global_numbers():
    result, _, _ = description(5)
    order = [field["field_id"] for field in result["source_fields"]]
    for field, name in zip(result["source_fields"], ("A01", "核の視野", "A03", "A03", "x" * 13), strict=True):
        field["display_name"] = name
    assert list(field_labels(result, order, False).values()) == ["A01", "Field 2", "Field 3", "Field 4", "Field 5"]
    assert list(field_labels(result, order, True).values()) == ["A01", "核の視野", "視野 3", "視野 4", "視野 5"]
    result["source_fields"][0]["display_name"] = "Field 2"
    assert field_labels(result, order, False)[order[0]] == "Field 1"
    unnamed, _, _ = description(2)
    assert list(field_labels(unnamed, order[:2], False).values()) == ["Field 1", "Field 2"]


@pytest.mark.parametrize("language", ["en", "ja"])
def test_legend_keeps_a_long_name_beside_its_numbered_label(language):
    result, _, _ = description(1, language=language)
    named = copy.deepcopy(result)
    fid = named["source_fields"][0]["field_id"]
    named["source_fields"][0]["display_name"] = "plate 3 well A01 site 4"
    label = "視野 1" if language == "ja" else "Field 1"
    assert f"- {label} (plate 3 well A01 site 4): field_id={fid};" in _caption(named, {fid: label})
    assert f"- {label}: field_id={fid};" in _caption(result, {fid: label})
