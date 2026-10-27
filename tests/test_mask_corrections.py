"""Hand edits of measured masks are reported from the recorded revisions, never as exclusions.

The worker cases reuse the minimal 8x8 integer label arrays of test_region_worker (synthetic:
two labelled squares). They reconcile region counts against the recorded label operations
only; no detection, threshold or biological claim depends on them.
"""
import copy
import io
import json
import zipfile

import pytest
from cytellect_analysis.descriptive import describe_regions
from cytellect_analysis.descriptive_figures import _caption, descriptive_methods
from cytellect_analysis.mask_corrections import mask_correction_summary, with_mask_corrections
from cytellect_analysis.region_exports import replay_region_bundle
from cytellect_analysis.statistical_methods import CURRENT_METHODS_TEMPLATE, StatisticalMethodsTemplate
from cytellect_api.db import jobs
from cytellect_api.storage import read_json
from cytellect_worker.main import process_one
from test_api_worker import HEADERS, authenticated
from test_descriptive import request
from test_region_api import make_field, region_request
from test_region_worker import execute, setup_fields

V1_0_0 = StatisticalMethodsTemplate(id="cytellect-statistical-methods", version="1.0.0")
SQUARE = [[6, 6], [8, 6], [8, 8], [6, 8]]


def edit(config, parent, operation, ids=(), polygon=()):
    return {**config, "reuse_revision": parent, "region_edit": {
        "field_id": "f1", "region_set_id": "reviewed", "operation": operation, "ids": list(ids),
        "polygon": [list(point) for point in polygon], "expected_mask_revision_id": parent}}


def ledger(store, rid):
    report = read_json(store.safe_path("results", rid, "measurements.json"))
    return report, read_json(store.safe_path("results", rid, "provenance.json"))


def test_trial_edits_carried_into_a_batch_are_counted_per_field(tmp_path):
    store, settings, every = setup_fields(tmp_path, count=2)
    trial = {**every, "field_ids": ["f1"], "field_snapshot": {"f1": every["field_snapshot"]["f1"]},
             "backgrounds": {"f1": every["backgrounds"]["f1"]}}
    initial = execute(store, settings, trial)
    execute(store, settings, edit(trial, "r1", "delete", [7]), "r2")
    execute(store, settings, edit(trial, "r2", "add", polygon=SQUARE), "r3")
    execute(store, settings, {**every, "reuse_revision": "r3"}, "r4")
    summary = mask_correction_summary(*ledger(store, "r4"))
    first, second = summary["fields"]
    assert summary["edited_fields"] == 1 and summary["source"] == "imported"
    assert first["initial_regions"] == len({row["region_id"] for row in initial["field_tables"]["f1"]["rows"]}) == 2
    assert (first["deleted_regions"], first["added_regions"], first["final_regions"]) == (1, 1, 2)
    assert first["edit_revision_ids"] == ["r2", "r3"] and first["mask_revision_id"] == "r3"
    assert second["edit_revision_ids"] == [] and second["initial_regions"] == second["final_regions"] == 2
    assert second["initial_revision_id"] == "r4"


def test_split_merge_and_redraw_reconstruct_the_initial_count(tmp_path):
    store, settings, config = setup_fields(tmp_path)
    execute(store, settings, config)
    split = execute(store, settings, edit(config, "r1", "split", [7], [[2, 2], [3, 2], [3, 4], [2, 4]]), "r2")
    assert len({row["region_id"] for row in split["field_tables"]["f1"]["rows"]}) == 3
    execute(store, settings, edit(config, "r2", "merge", [19, 20]), "r3")
    execute(store, settings, edit(config, "r3", "replace", [19], [[4, 4], [6, 4], [6, 5], [4, 5]]), "r4")
    execute(store, settings, edit(config, "r4", "add", polygon=SQUARE), "r5")
    row = mask_correction_summary(*ledger(store, "r5"))["fields"][0]
    assert row["operations"] == {"add": 1, "replace": 1, "delete": 0, "merge": 1, "split": 1}
    assert (row["split_regions"], row["merged_regions"], row["redrawn_regions"]) == (1, 2, 1)
    assert (row["initial_regions"], row["final_regions"]) == (2, 3)


def test_history_that_does_not_reach_the_measured_mask_is_refused(tmp_path):
    store, settings, config = setup_fields(tmp_path)
    execute(store, settings, config)
    execute(store, settings, edit(config, "r1", "delete", [7]), "r2")
    report, provenance = ledger(store, "r2")
    dropped = copy.deepcopy(provenance)
    dropped["fields"]["f1"]["history"].pop()
    with pytest.raises(ValueError, match="descriptive_mask_history_mismatch"):
        mask_correction_summary(report, dropped)
    other = copy.deepcopy(provenance)
    other["revision_id"] = "r1"
    with pytest.raises(ValueError, match="descriptive_mask_history_mismatch"):
        mask_correction_summary(report, other)
    unrecorded = copy.deepcopy(provenance)
    unrecorded["fields"]["f1"]["history"] = []
    row = mask_correction_summary(report, unrecorded)["fields"][0]
    assert row["status"] == "not_recorded" and row["initial_regions"] is None


def test_methods_and_caption_state_edits_only_in_the_new_template(tmp_path):
    store, settings, config = setup_fields(tmp_path)
    execute(store, settings, config)
    execute(store, settings, edit(config, "r1", "delete", [7]), "r2")
    report, provenance = ledger(store, "r2")
    snapshot = config["field_snapshot"]
    selector = request(metric="area_px")
    selector = selector.model_copy(update={"selection": selector.selection.model_copy(update={"region_set_id": "reviewed"})})
    result = with_mask_corrections(describe_regions(report, snapshot, selector), report, provenance)
    assert result["selection"]["excluded"] == 0
    text = descriptive_methods(result, methods_template=CURRENT_METHODS_TEMPLATE)
    assert "Manual mask edits: masks of 1 of 1 measured field were edited by hand" in text
    assert "Field f1: 2 initial regions; 1 deleted; 1 region measured." in text
    assert "not counted as explicitly excluded" in text and "provenance.json" in text
    assert "Manual mask edits" not in descriptive_methods(result, methods_template=V1_0_0)
    caption = _caption(result, {"f1": "Field 1"}, CURRENT_METHODS_TEMPLATE)
    assert "Field 1: 1 deleted (2 initial regions, 1 measured)" in caption
    assert "definition=reviewed" in caption and "Reviewed regions" not in caption
    japanese = copy.deepcopy(result)
    japanese["spec"]["plot"]["language"] = "ja"
    assert "Field 1 は1 領域を削除（最初 2 領域、測定 1 領域）" in _caption(japanese, {"f1": "Field 1"})


def test_api_edit_to_paged_description_export_replay_and_edited_figure(tmp_path):
    client, app, settings = authenticated(tmp_path)
    store = app.state.store
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "Edits"}).json()["id"]
    fid = make_field(client, wid).json()["id"]
    rid = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=region_request(fid)).json()["revision_id"]
    assert process_one(store, settings)
    for operation in ({"operation": "add", "polygon": [[8, 8], [11, 8], [11, 11], [8, 11]]},
                      {"operation": "delete", "ids": [17]}):
        response = client.post(f"/v1/revisions/{rid}/region-edits", headers=HEADERS,
                               json={"field_id": fid, "region_set_id": "objects", **operation})
        assert response.status_code == 202, response.text
        rid = response.json()["revision_id"]
        assert process_one(store, settings)
    assert client.post(f"/v1/revisions/{rid}/review", headers=HEADERS).status_code == 200
    body = {"mode": "descriptive", "selection": {"source": "region", "region_set_id": "objects", "metric": "area_px"},
            "plot": {"preset": "nature-single", "language": "en"},
            "figure_policy": {"version": "2.0.0", "layout": "field-pages"}}
    jid = client.post(f"/v1/revisions/{rid}/descriptive", headers=HEADERS, json=body).json()["job_id"]
    assert process_one(store, settings)
    result = client.get(f"/v1/jobs/{jid}/result").json()
    row = result["mask_corrections"]["fields"][0]
    assert (row["initial_regions"], row["added_regions"], row["deleted_regions"], row["final_regions"]) == (1, 1, 1, 1)
    assert result["selection"]["excluded"] == 0
    assert result["figure"]["methods_template"] == CURRENT_METHODS_TEMPLATE.model_dump()
    methods = client.get(f"/v1/jobs/{jid}/files/methods.md").text
    assert "1 initial region; 1 deleted, 1 added; 1 region measured." in methods
    assert "Region definition: objects (region set ID objects; regions from an imported label image;" in methods
    assert "Reviewed regions" not in methods
    assert "1 deleted, 1 added (1 initial region, 1 measured)" in client.get(f"/v1/jobs/{jid}/files/figure-caption.md").text
    render = client.post(f"/v1/jobs/{jid}/figure-render", headers=HEADERS,
                         json={"request_id": "edited", "plot": {"y_label": "Area"}}).json()["job_id"]
    assert process_one(store, settings)
    edited = store.safe_path(store.one(jobs, id=render)["result_dir"])
    assert (edited / "methods.md").read_text(encoding="utf-8") == methods
    export = client.post(f"/v1/revisions/{rid}/export", headers=HEADERS).json()["job_id"]
    assert process_one(store, settings)
    archive = client.get(f"/v1/jobs/{export}/files/analysis.zip")
    with zipfile.ZipFile(io.BytesIO(archive.content)) as opened:
        opened.extractall(tmp_path / "bundle")
    saved = json.loads(next((tmp_path / "bundle/statistics").glob("*/result.json")).read_text(encoding="utf-8"))
    assert saved["mask_corrections"] == result["mask_corrections"]
    replayed = replay_region_bundle(tmp_path / "bundle", store.safe_path("workspaces", wid, "fields"), tmp_path / "replay")
    assert replayed["matched_saved_measurements"] and replayed["matched_saved_descriptions"]
