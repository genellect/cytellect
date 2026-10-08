"""Experimental metadata is revised without replacing original uploads or masks."""
from copy import deepcopy

import pytest
from cytellect_analysis.region_contracts import RegionMetadataEdit
from cytellect_analysis.region_metadata import region_metadata_child_config, validate_region_reuse
from cytellect_api.db import fields, revisions
from cytellect_api.storage import read_json
from cytellect_worker.main import process_one
from test_api_worker import HEADERS, authenticated
from test_region_api import make_field, region_request


def test_metadata_changes_are_explicit_and_cannot_modify_other_snapshot_keys():
    parent = {"id": "r0", "config": {"recipe": {"source": "manual"}, "field_ids": ["f"],
              "field_snapshot": {"f": {"id": "f", "metadata": {}, "image_info": {"pixels": "a"}}}}}
    before = deepcopy(parent)
    edit = RegionMetadataEdit.model_validate({"fields": {"f": {"condition": "A", "experimental_unit": "culture-1"}}})
    child = region_metadata_child_config(parent, edit)
    assert parent == before
    validate_region_reuse(parent, child, parent["config"]["recipe"])
    assert child["field_snapshot"]["f"]["metadata"]["sample"] is None
    for mutate in ("image", "unrecorded", "wrong-parent"):
        invalid = deepcopy(child)
        if mutate == "image":
            invalid["field_snapshot"]["f"]["image_info"]["pixels"] = "different"
        elif mutate == "unrecorded":
            invalid.pop("region_metadata_edit")
        else:
            invalid["region_metadata_edit"]["source_revision_id"] = "unrelated"
        with pytest.raises(ValueError):
            validate_region_reuse(parent, invalid, parent["config"]["recipe"])

def test_channel_annotation_edit_preserves_source_identity_and_requires_a_record():
    # Stored metadata only: this regression creates no microscopy/test image.
    parent = {"id": "r0", "config": {"recipe": {"source": "manual"}, "field_snapshot": {
        "f": {"id": "f", "metadata": {}, "image_info": {
            "channels": [{"channel_id": "c4", "label": "c4", "stain": None,
                          "acquisition_saturation_value": None}],
            "channel_arrays": {"c4": {"sha256": "unchanged-pixel-hash"}}, "shape": [1024, 1024]}}}}}
    before = deepcopy(parent)
    child = deepcopy(parent["config"])
    channel = child["field_snapshot"]["f"]["image_info"]["channels"][0]
    channel.update(label="DAPI", stain="DAPI", identity_source="user_entered")
    child["channel_annotation_edit"] = {"version": "1.0.0", "source_revision_id": "r0",
                                        "fields": {"f": [deepcopy(channel)]}}
    validate_region_reuse(parent, child, parent["config"]["recipe"])
    assert parent == before
    for mutation in ("unrecorded", "channel-id", "pixels", "acquisition", "wrong-parent"):
        invalid = deepcopy(child)
        if mutation == "unrecorded":
            invalid.pop("channel_annotation_edit")
        elif mutation == "channel-id":
            invalid["channel_annotation_edit"]["fields"]["f"][0]["channel_id"] = "c3"
        elif mutation == "pixels":
            invalid["field_snapshot"]["f"]["image_info"]["channel_arrays"]["c4"]["sha256"] = "different"
        elif mutation == "acquisition":
            invalid["channel_annotation_edit"]["fields"]["f"][0]["acquisition_saturation_value"] = 200
        else:
            invalid["channel_annotation_edit"]["source_revision_id"] = "other"
        with pytest.raises(ValueError):
            validate_region_reuse(parent, invalid, parent["config"]["recipe"])

    annotated_parent = {"id": "r1", "config": child}
    metadata_edit = RegionMetadataEdit.model_validate({"fields": {"f": {"condition": "A"}}})
    next_child = region_metadata_child_config(annotated_parent, metadata_edit)
    assert "channel_annotation_edit" not in next_child
    validate_region_reuse(annotated_parent, next_child, parent["config"]["recipe"])


def test_metadata_child_preserves_masks_review_and_batch_design(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "metadata"}).json()["id"]
    fid = make_field(client, wid).json()["id"]
    first = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS,
                        json=region_request(fid)).json()
    process_one(app.state.store, settings)
    rid = first["revision_id"]
    before = client.get(f"/v1/revisions/{rid}/region-measurements").json()
    assert client.post(f"/v1/revisions/{rid}/review", headers=HEADERS, json={}).status_code == 200
    original = deepcopy(dict(app.state.store.one(fields, id=fid)))
    metadata = {"condition": "A", "experimental_unit": "culture-1", "sample": "sample-1",
                "acquisition_date": "batch-1", "pair": None, "repeat_length": None}
    response = client.post(f"/v1/revisions/{rid}/region-metadata", headers=HEADERS,
                           json={"fields": {fid: metadata}})
    assert response.status_code == 202, response.text
    child_id = response.json()["revision_id"]
    process_one(app.state.store, settings)
    child = app.state.store.one(revisions, id=child_id)
    assert child["state"] == "succeeded" and not child["reviewed"]
    assert child["config"]["field_snapshot"][fid]["metadata"] == metadata
    assert dict(app.state.store.one(fields, id=fid)) == original
    assert app.state.store.one(revisions, id=rid)["reviewed"]
    after = client.get(f"/v1/revisions/{child_id}/region-measurements").json()
    assert after["field_masks"] == before["field_masks"]
    assert client.post(f"/v1/revisions/{rid}/region-metadata", headers=HEADERS,
                       json={"fields": {fid: metadata}}).status_code == 409
    unknown = client.post(f"/v1/revisions/{child_id}/region-metadata", headers=HEADERS,
                          json={"fields": {"unknown": metadata}})
    assert unknown.status_code == 422
    assert client.post(f"/v1/revisions/{child_id}/review", headers=HEADERS, json={}).status_code == 200
    next_field = make_field(client, wid).json()["id"]
    body = region_request(fid)
    body.update(field_ids=[fid, next_field], reuse_revision=child_id)
    body["backgrounds"][next_field] = body["backgrounds"][fid]
    batch = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=body)
    assert batch.status_code == 202, batch.text
    process_one(app.state.store, settings)
    result = app.state.store.one(revisions, id=batch.json()["revision_id"])
    assert result["state"] == "succeeded"
    assert result["config"]["field_snapshot"][fid]["metadata"] == metadata
    assert result["config"]["field_snapshot"][next_field]["metadata"] == original["metadata"]
    saved = read_json(app.state.store.safe_path(result["result_dir"], "measurements.json"))
    assert saved["field_masks"][fid] == before["field_masks"][fid]
