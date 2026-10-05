"""Recorded nuclear evidence is checked before detection and saved-mask replay."""
import pytest
from cytellect_analysis.descriptive import describe_regions
from cytellect_analysis.descriptive_contracts import DescriptiveResult
from cytellect_analysis.region_contracts import (
    AdoptedNuclearRecipe,
    RegionImageInfo,
    scientific_specification,
)
from cytellect_analysis.region_policy import RawIntensityPolicy
from cytellect_api.proposals import build_context
from test_api_worker import HEADERS, authenticated
from test_descriptive import region_fixture, request
from test_region_api import make_field
from test_region_nuclear_worker import install_detector, nuclear_fields
from test_region_worker import execute


def adopted(source="recorded_stain", channel="dna"):
    return AdoptedNuclearRecipe(region_set_id="nuclei", label="Nuclei", defining_channel_id=channel,
                                nuclear_role_source=source)


def test_api_requires_actual_recorded_stain_instead_of_role_claim(tmp_path):
    client, _, _ = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", json={"title": "test"}, headers=HEADERS).json()["id"]
    assert make_field(client, wid, labels=False).status_code == 201
    body = {"recipe": adopted(channel="actin").model_dump(mode="json"),
            "measurement": {"version": "1.1.0", "mode": "raw_intensity"}, "backgrounds": {}}
    rejected = client.post(f"/v1/workspaces/{wid}/region-analyses", json=body, headers=HEADERS)
    assert rejected.status_code == 422 and rejected.json()["detail"] == "nuclear_recorded_stain_required"
    body["recipe"]["nuclear_role_source"] = "user_selected_role"
    accepted = client.post(f"/v1/workspaces/{wid}/region-analyses", json=body, headers=HEADERS)
    assert accepted.status_code == 202, accepted.text
    context, _ = build_context(client.app.state.store, wid, "")
    assert context.channels[0].role == "nuclear" and context.channels[0].stain is None


def test_worker_rechecks_saved_evidence_before_calling_fiji(tmp_path, monkeypatch):
    store, settings, config = nuclear_fields(tmp_path)
    calls = install_detector(monkeypatch)
    config["recipe"] = adopted().model_dump(mode="json")
    config["field_snapshot"]["f1"]["image_info"]["channels"][0]["stain"] = "phalloidin"
    report = execute(store, settings, config)
    assert report["field_tables"] == {} and calls == []
    assert report["field_failures"] == [{"field_id": "f1", "reason": "nuclear_recorded_stain_required"}]


@pytest.mark.parametrize("stain", [None, "GFP", "DAPI-positive cells"])
def test_replay_specification_rejects_invented_recorded_stain(tmp_path, stain):
    store, _, config = nuclear_fields(tmp_path)
    raw = config["field_snapshot"]["f1"]["image_info"]
    raw["channels"][0]["stain"] = stain
    info = RegionImageInfo.model_validate(raw)
    with pytest.raises(ValueError, match="nuclear_recorded_stain_required"):
        scientific_specification(field_id="f1", revision_id="r1", mask_revision_id="m1", recipe=adopted(),
                                 image_info=info, measurement=RawIntensityPolicy(version="1.1.0", mode="raw_intensity"))
    store.engine.dispose()


def test_optional_review_marker_does_not_rewrite_historical_output():
    report, snapshot = region_fixture()
    legacy = describe_regions(report, snapshot, request())
    assert "source_review" not in legacy
    assert DescriptiveResult.model_validate(legacy).model_dump(mode="json") == legacy
    current = {**legacy, "source_review": "automatic_unreviewed"}
    assert DescriptiveResult.model_validate(current).model_dump(mode="json") == current
