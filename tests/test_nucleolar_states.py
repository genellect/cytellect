"""Preserve detector evidence separately from what an empty label image proves."""
import json

import numpy as np
import pytest
from cytellect_analysis.contracts import Recipe
from cytellect_analysis.measurement import measure, normalize_nucleolar_states
from cytellect_analysis.review import unresolved_nucleolar_failures
from cytellect_api.db import revisions
from cytellect_api.storage import read_json
from cytellect_worker.main import run_analysis
from sqlalchemy import update
from test_api_optional_channels import metadata, tif_bytes
from test_api_worker import HEADERS, authenticated
from test_input_science import inputs


@pytest.mark.parametrize("state", ["no_candidate", "indeterminate", "review_required", "unclassified"])
def test_empty_mask_keeps_recorded_state_and_known_nucleoplasm_area(state):
    nuclei, nucleoli, bg, channels, meta = inputs()
    row = measure(channels, nuclei, np.zeros_like(nucleoli), bg, Recipe(),
                  {**meta, "pixel_size_um": .5}, "f", nucleolar_states={1: state})[0][0]
    assert row["nucleolar_status"] == state
    assert row["nucleus_area_px"] == row["nucleoplasm_area_px"] == 16
    assert row["nucleoplasm_area_um2"] == 4
    assert row["nucleolar_area_px"] == 0
    assert row["ncl_nucleoli_mean"] is None
    assert row["measurement_protocol_version"] == "1.1.1"


def test_native_union_areas_are_complementary_and_unknown_scale_is_missing():
    nuclei, nucleoli, bg, channels, meta = inputs()
    row = measure(channels, nuclei, nucleoli, bg, Recipe(), meta, "f")[0][0]
    assert (row["nucleus_area_px"], row["nucleolar_area_px"], row["nucleoplasm_area_px"]) == (16, 4, 12)
    assert row["nucleoplasm_area_um2"] is None
    assert row["nucleolar_status"] == "candidate"
    empty = measure(channels, nuclei, np.zeros_like(nucleoli), bg, Recipe(), meta, "f")[0][0]
    assert empty["nucleolar_status"] == "unclassified"
    gfp = measure(channels, nuclei, np.zeros_like(nucleoli), bg, Recipe(id="gfp-nuclear-2d"), meta, "f")[0][0]
    assert gfp["nucleoplasm_area_px"] is gfp["nucleoplasm_area_um2"] is None
    assert gfp["nucleolar_status"] == "not_measured_recipe"


def test_legacy_canonical_areas_and_detector_state_do_not_change_intensities():
    from cytellect_analysis.legacy import detect_legacy_nucleoli
    from test_legacy import case
    channels, nuclei = case()
    recipe = Recipe(id="ncl-legacy-rgb")
    nucleoli, states = detect_legacy_nucleoli(channels, nuclei, recipe)
    row = measure(channels, nuclei, nucleoli, None, recipe, {"pixel_size_um": .5}, "f",
                  nucleolar_states=normalize_nucleolar_states({"nucleolar_status": states}))[0][0]
    assert row["nucleoplasm_area_px"] == 1500
    assert row["nucleoplasm_area_um2"] == 375
    assert row["ncl_nucleoli_mean_corrected"] == 100
    assert row["nucleolar_status"] == "legacy_candidate"


def test_detector_vocabulary_is_normalized_without_combining_empty_outcomes():
    assert normalize_nucleolar_states({"nucleolar_status": {"1": "candidates", "2": "no_candidate",
                                                            "3": "indeterminate"}}) == {
        1: "candidate", 2: "no_candidate", 3: "indeterminate"}
    assert normalize_nucleolar_states({"candidate_status": {1: "none"}}) == {1: "no_candidate"}
    with pytest.raises(ValueError, match="nucleolar_state_invalid"):
        normalize_nucleolar_states({"nucleolar_states": {1: "unknown"}})


def test_failed_compartments_are_missing_and_require_explicit_reasoned_exclusion():
    nuclei, nucleoli, bg, channels, meta = inputs()
    row = measure(channels, nuclei, np.zeros_like(nucleoli), bg, Recipe(), meta, "f",
                  nucleolar_states={1: "processing_failed"})[0][0]
    assert row["ncl_nucleus_mean"] == 22.5 and row["gfp_mean"] == 16
    assert row["ncl_nucleoplasm_mean"] is row["ncl_nucleoli_mean"] is None
    assert row["nucleolar_area_fraction"] is row["nucleoplasm_area_px"] is None
    assert row["ratio_missing_reason"] == "nucleolar_processing_failed"
    failure = [{"field_id": "f", "nucleus_id": 1}]
    report = {"cells": [row], "nucleolar_failures": failure}
    assert unresolved_nucleolar_failures(report, {}) == failure
    row["excluded"] = True  # Mutable row flags or broad review cannot clear evidence.
    assert unresolved_nucleolar_failures(report, {"review_record": {"accepted_invalidated_fields": ["f"]}}) == failure
    for nucleus in (None, 1):
        config = {"exclusions": [{"field_id": "f", "nucleus_id": nucleus, "reason": "candidate failure confirmed"}]}
        assert unresolved_nucleolar_failures(report, config) == []
    assert unresolved_nucleolar_failures(report, {"exclusions": [{"field_id": "f", "nucleus_id": 1, "reason": " "}]}) == failure


def test_failed_state_cannot_hide_nonempty_partial_candidates():
    nuclei, nucleoli, bg, channels, meta = inputs()
    with pytest.raises(ValueError, match="failed_nucleolar_mask_not_empty"):
        measure(channels, nuclei, nucleoli, bg, Recipe(), meta, "f", nucleolar_states={1: "processing_failed"})


@pytest.mark.parametrize("initial_state", ["no_candidate", "processing_failed"])
def test_worker_state_survives_reuse_edits_and_redetection(tmp_path, monkeypatch, initial_state):
    client, app, settings = authenticated(tmp_path)
    store = app.state.store
    wid = client.post("/v1/workspaces", json={"title": "states"}, headers=HEADERS).json()["id"]
    nuclei = np.zeros((24, 24), np.uint32)
    nuclei[5:10, 5:10] = 1
    nuclei[14:19, 14:19] = 2
    image = (nuclei * 50 + 4).astype(np.uint16)
    uploaded = client.post(f"/v1/workspaces/{wid}/fields", data={"metadata": json.dumps(metadata())},
                          files={role: ("synthetic.tif", tif_bytes(image), "image/tiff") for role in ("dapi", "ncl")},
                          headers=HEADERS)
    assert uploaded.status_code == 201
    fid = uploaded.json()["id"]
    def detector(*args, nuclei=None, **kwargs):
        labels = np.zeros((24, 24), np.uint32) if nuclei is None else nuclei.copy()
        if nuclei is None:
            labels[5:10, 5:10], labels[14:19, 14:19] = 1, 2
        return labels, np.zeros_like(labels), np.zeros_like(labels), {
            "engine": "deterministic-states", "nucleolar_status": {
                "1": initial_state if nuclei is None else "no_candidate", "2": "indeterminate"}}
    monkeypatch.setattr("cytellect_worker.main._initial_masks", detector)
    def finish(response):
        assert response.status_code == 202, response.text
        job = store.claim()
        output = store.safe_path("results", job["revision_id"])
        run_analysis(store, settings, job, output)
        assert store.finish(job, str(output.relative_to(store.root)))
        report = read_json(output / "measurements.json")
        assert not report["field_failures"]
        states = {row["nucleus_id"]: row["nucleolar_status"] for row in report["cells"]}
        assert report["engine_provenance"][fid]["nucleolar_states"] == {str(k): v for k, v in states.items()}
        assert report["nucleolar_failures"] == [{"field_id": fid, "nucleus_id": label}
                                               for label, state in states.items() if state == "processing_failed"]
        return response.json()["revision_id"], states
    config = {"backgrounds": {fid: {"confirmed": True, "polygon": [[0, 0], [3, 0], [3, 3], [0, 3]]}}}
    rid, states = finish(client.post(f"/v1/workspaces/{wid}/analyses", json=config, headers=HEADERS))
    assert states == {1: initial_state, 2: "indeterminate"}
    if initial_state == "processing_failed":
        rejected = client.post(f"/v1/revisions/{rid}/review", json={}, headers=HEADERS)
        assert rejected.status_code == 409
        assert rejected.json()["detail"] == "resolve_or_explicitly_exclude_failed_nucleoli"
        # Defence in depth for a historical reviewed row: endpoint must recheck
        # retained failure evidence, not trust only a stored reviewed boolean.
        with store.transaction() as connection:
            connection.execute(update(revisions).where(revisions.c.id == rid).values(reviewed=True))
        rejected = client.post(f"/v1/revisions/{rid}/statistics", headers=HEADERS,
                               json={"metric": "ncl_nucleus_mean_corrected", "baseline": "test",
                                     "comparisons": [["test", "other"]], "independent_units_confirmed": True})
        assert rejected.status_code == 409
        assert rejected.json()["detail"] == "resolve_or_explicitly_exclude_failed_nucleoli"
        with store.transaction() as connection:
            connection.execute(update(revisions).where(revisions.c.id == rid).values(reviewed=False))
        # Nuclear geometry changes cannot bypass the failed-candidate gate.
        outline = {"field_id": fid, "layer": "nuclei", "operation": "replace", "ids": [1],
                   "polygon": [[5, 5], [9, 5], [9, 9], [5, 9]]}
        rid, states = finish(client.post(f"/v1/revisions/{rid}/edits", json=outline, headers=HEADERS))
        assert states == {1: "processing_failed", 2: "indeterminate"}
        rejected = client.post(f"/v1/revisions/{rid}/review", headers=HEADERS,
                               json={"accept_invalidated_fields": [fid]})
        assert rejected.status_code == 409
        assert rejected.json()["detail"] == "resolve_or_explicitly_exclude_failed_nucleoli"
    edit = {"field_id": fid, "layer": "nucleoli", "operation": "add", "parent_id": 1,
            "polygon": [[6, 6], [8, 6], [8, 8], [6, 8]]}
    rid, states = finish(client.post(f"/v1/revisions/{rid}/edits", json=edit, headers=HEADERS))
    assert states == {1: "candidate", 2: "indeterminate"}
    reviewed = client.post(f"/v1/revisions/{rid}/review", headers=HEADERS,
                           json={"accept_invalidated_fields": [fid] if initial_state == "processing_failed" else []})
    assert reviewed.status_code == 200, reviewed.text
    edit = {"field_id": fid, "layer": "nucleoli", "operation": "delete", "ids": [1]}
    rid, states = finish(client.post(f"/v1/revisions/{rid}/edits", json=edit, headers=HEADERS))
    assert states == {1: "no_candidate", 2: "indeterminate"}
    edit = {"field_id": fid, "layer": "nuclei", "operation": "replace", "ids": [1],
            "polygon": [[5, 5], [11, 5], [11, 11], [5, 11]]}
    rid, states = finish(client.post(f"/v1/revisions/{rid}/edits", json=edit, headers=HEADERS))
    assert states == {1: "review_required", 2: "indeterminate"}
    rid, states = finish(client.post(f"/v1/revisions/{rid}/resegment", json={"field_ids": [fid]}, headers=HEADERS))
    assert states == {1: "no_candidate", 2: "indeterminate"}
