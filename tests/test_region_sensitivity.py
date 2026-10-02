"""Reviewed region alternatives require identical non-region scientific inputs."""
import copy

import numpy as np
import pytest
from cytellect_analysis.contracts import Recipe, StatisticsRequest
from cytellect_analysis.region_sensitivity import (
    validate_region_configs,
    validate_region_masks,
    validate_region_reports,
)
from cytellect_analysis.statistics import analyze_sensitivity
from cytellect_api.db import jobs, revisions, uid
from cytellect_api.storage import read_json, write_json
from cytellect_worker.main import process_one
from fastapi.testclient import TestClient
from sqlalchemy import update
from test_api_worker import HEADERS, authenticated
from test_lifecycle import demo


def configs():
    primary = {"recipe": Recipe().model_dump(), "field_ids": ["f"],
               "field_snapshot": {"f": {"image_info": {"inputs": {"ncl": {"sha256": "source"}}},
                                        "metadata": {"condition": "A"}}},
               "backgrounds": {"f": {"polygon": [[0, 0], [1, 0], [1, 1]], "confirmed": True}},
               "exclusions": [], "review_record": {"accepted_invalidated_fields": []}}
    alternate = copy.deepcopy(primary)
    alternate["recipe"]["smoothing_sigma_px"] = 1
    return primary, alternate


@pytest.mark.parametrize(("change", "error"), [
    ("field", "fields_differ"), ("image", "inputs_or_metadata_differ"),
    ("condition", "inputs_or_metadata_differ"), ("background", "backgrounds_differ"),
    ("exclusion", "exclusions_differ"), ("gfp", "nonregion_parameters_differ"),
    ("nuclear", "nonregion_parameters_differ"), ("recipe", "requires_native_ncl"),
])
def test_nonregion_changes_cannot_be_reported_as_region_sensitivity(change, error):
    primary, alternate = configs()
    if change == "field":
        alternate["field_ids"] = ["different"]
    elif change == "image":
        alternate["field_snapshot"]["f"]["image_info"]["inputs"]["ncl"]["sha256"] = "changed"
    elif change == "condition":
        alternate["field_snapshot"]["f"]["metadata"]["condition"] = "B"
    elif change == "background":
        alternate["backgrounds"]["f"]["polygon"][0] = [2, 2]
    elif change == "exclusion":
        alternate["exclusions"] = [{"field_id": "f", "nucleus_id": 1, "reason": "quality"}]
    elif change == "gfp":
        alternate["recipe"].update(gfp_gate="manual", gfp_threshold=20)
    elif change == "nuclear":
        alternate["recipe"]["probability"] = .7
    else:
        alternate["recipe"]["id"] = "gfp-nuclear-2d"
    with pytest.raises(ValueError, match=error):
        validate_region_configs(primary, alternate)


def test_equal_label_count_cannot_hide_different_nuclear_pixels(tmp_path):
    primary, alternate = configs()
    validate_region_configs(primary, alternate)
    labels = np.zeros((6, 6), np.uint32)
    labels[2:4, 2:4] = 1
    changed = np.roll(labels, 1, axis=0)
    for folder, nuclei in ((tmp_path / "primary", labels), (tmp_path / "alternate", changed)):
        (folder / "f").mkdir(parents=True)
        np.savez_compressed(folder / "f" / "labels.npz", nuclei=nuclei, manual=np.zeros_like(labels))
    with pytest.raises(ValueError, match="nuclear_or_manual_masks_differ"):
        validate_region_masks(tmp_path / "primary", tmp_path / "alternate", ["f"], filename="labels.npz")


def test_failed_or_stale_review_does_not_qualify_as_completed_alternative():
    primary, _ = configs()
    for report in ({"field_failures": [{"field_id": "f"}]},
                   {"excluded_failed_fields": [{"field_id": "f"}]},
                   {"invalidated_nucleoli": ["f"]}):
        with pytest.raises(ValueError, match="complete_reviewed_masks"):
            validate_region_reports(primary, report)
    with pytest.raises(ValueError, match="nucleolar_processing_failed"):
        validate_region_reports(primary, {"cells": [{"field_id": "f", "nucleus_id": 1,
                                                      "nucleolar_status": "processing_failed"}]})


def reviewed_pair(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid, fids, primary, _ = demo(client, app, settings)
    assert client.post(f"/v1/revisions/{primary}/review", json={}, headers=HEADERS).status_code == 200
    config = app.state.store.one(revisions, id=primary)["config"]
    recipe = {**config["recipe"], "smoothing_sigma_px": 1.5}
    reply = client.post(f"/v1/revisions/{primary}/resegment", json={"field_ids": fids, "recipe": recipe}, headers=HEADERS)
    assert reply.status_code == 202, reply.json()
    alternate = reply.json()["revision_id"]
    assert process_one(app.state.store, settings)
    assert client.post(f"/v1/revisions/{alternate}/review", json={}, headers=HEADERS).status_code == 200
    spec = {"metric": "ncl_nucleoli_mean_corrected", "baseline": "Control", "comparisons": [["Control", "Treatment"]],
            "paired": True, "independent_units_confirmed": True, "sensitivity_region_revision_ids": [alternate]}
    return client, app, settings, wid, primary, alternate, spec


def test_reviewed_region_comparison_uses_new_measurements_and_saves_masks(tmp_path):
    client, app, settings, _, primary, alternate, spec = reviewed_pair(tmp_path)
    posted = client.post(f"/v1/revisions/{primary}/statistics", json=spec, headers=HEADERS)
    assert posted.status_code == 202, posted.json()
    jid = posted.json()["job_id"]
    assert process_one(app.state.store, settings)
    record = app.state.store.one(jobs, id=jid)
    assert record["state"] == "succeeded", record["error"]
    result = client.get(f"/v1/jobs/{jid}/result").json()
    scenario = result["sensitivities"][0]
    assert scenario["scenario"] == f"region_revision:{alternate}"
    assert scenario["status"] == "succeeded"
    # Real per-nucleus resegmentation changes the union-measurement distribution.
    assert scenario["result"]["means"] != result["means"]
    source = result["region_sensitivity_sources"][0]
    assert source["revision_id"] == alternate
    snapshot = app.state.store.safe_path(record["result_dir"], source["relative_path"])
    metadata = read_json(snapshot / "revision.json")
    assert metadata["id"] == alternate and metadata["config"]["recipe"]["smoothing_sigma_px"] == 1.5
    for fid in metadata["config"]["field_ids"]:
        assert (snapshot / "masks" / fid / "labels.npz").is_file()
    assert read_json(snapshot / "measurements.json")["revision_id"] == alternate
    assert (snapshot / "provenance.json").is_file()
    assert client.get(f"/v1/jobs/{jid}/files/sensitivity-comparisons.csv").status_code == 200
    with pytest.raises(ValueError, match="snapshots_required"):
        analyze_sensitivity(result["plot_data"], StatisticsRequest.model_validate(spec))


def test_api_checks_other_owner_unreviewed_different_input_and_stale_review(tmp_path):
    client, app, _, _, primary, alternate, spec = reviewed_pair(tmp_path)
    second = TestClient(app)
    token = app.state.store.invite()
    assert second.post("/v1/invitations/redeem", json={"token": token}, headers=HEADERS).status_code == 200
    assert second.post(f"/v1/revisions/{primary}/statistics", json=spec, headers=HEADERS).status_code == 404
    original = app.state.store.one(revisions, id=alternate)
    foreign_workspace = second.post("/v1/workspaces", json={"title": "synthetic-other-owner"}, headers=HEADERS).json()
    foreign_id = uid()
    with app.state.store.transaction() as conn:
        conn.execute(revisions.insert().values(**{**dict(original), "id": foreign_id,
                                                  "workspace_id": foreign_workspace["id"]}))
    denied = client.post(f"/v1/revisions/{primary}/statistics", headers=HEADERS,
                         json={**spec, "sensitivity_region_revision_ids": [foreign_id]})
    assert denied.status_code == 404  # An owned primary cannot reveal a foreign alternative.
    with app.state.store.transaction() as conn:
        conn.execute(update(revisions).where(revisions.c.id == alternate).values(reviewed=False))
    denied = client.post(f"/v1/revisions/{primary}/statistics", json=spec, headers=HEADERS)
    assert denied.status_code == 409 and denied.json()["detail"] == "region_sensitivity_review_required"
    changed = copy.deepcopy(original["config"])
    fid = changed["field_ids"][0]
    role = next(iter(changed["field_snapshot"][fid]["image_info"]["inputs"]))
    changed["field_snapshot"][fid]["image_info"]["inputs"][role]["sha256"] = "different input"
    with app.state.store.transaction() as conn:
        conn.execute(update(revisions).where(revisions.c.id == alternate).values(reviewed=True, config=changed))
    denied = client.post(f"/v1/revisions/{primary}/statistics", json=spec, headers=HEADERS)
    assert denied.status_code == 409 and denied.json()["detail"] == "region_sensitivity_inputs_or_metadata_differ"
    with app.state.store.transaction() as conn:
        conn.execute(update(revisions).where(revisions.c.id == alternate).values(config=original["config"]))
    path = app.state.store.safe_path(original["result_dir"], "measurements.json")
    report = read_json(path)
    report["invalidated_nucleoli"] = [fid]
    write_json(path, report)
    denied = client.post(f"/v1/revisions/{primary}/statistics", json=spec, headers=HEADERS)
    assert denied.status_code == 409 and denied.json()["detail"] == "region_sensitivity_complete_reviewed_masks_required"
