"""Generic-region exports retain pixels, scientific identity and missingness."""
import csv
import json
import zipfile

import numpy as np
import pytest
from cytellect_analysis.descriptive import describe_regions
from cytellect_analysis.descriptive_contracts import DescriptiveRequest
from cytellect_analysis.region_exports import build_region_bundle, replay_region_bundle
from cytellect_analysis.roi import import_roi_zip
from cytellect_api.storage import read_json
from cytellect_worker.regions import run_region_export
from test_region_worker import execute, setup_fields


def bundle_inputs(store, config, report):
    return {
        "config": config, "report": report,
        "provenance": read_json(store.safe_path("results", report["revision_id"], "provenance.json")),
        "mask_files": {fid: store.safe_path("results", report["revision_id"], fid, "labels.npy")
                       for fid in report["field_masks"]},
        "raw_files": [(f"{fid}/{slot}.tif", store.safe_path("workspaces", "w", "fields", fid, f"{slot}.tif"))
                      for fid, field in config["field_snapshot"].items() for slot in field["image_info"]["inputs"]],
    }


def test_default_bundle_has_exact_rois_signed_long_csv_and_no_raw(tmp_path):
    store, settings, config = setup_fields(tmp_path)
    config["exclusions"] = [{"field_id": "f1", "region_id": 7, "reason": "=Research note"}]
    report = execute(store, settings, config)
    archive = build_region_bundle(tmp_path / "export", **bundle_inputs(store, config, report))
    with zipfile.ZipFile(archive) as opened:
        names = opened.namelist()
        assert not any(name.startswith("raw/") for name in names)
        assert {"regions.csv", "revision.json", "provenance.json", "manifest.json", "replay.py"}.issubset(names)
        rows = list(csv.DictReader(opened.read("regions.csv").decode("utf-8-sig").splitlines()))
        assert rows[0]["integrated_corrected"] == "-20.0"
        assert rows[0]["channel_label"] == "Actin" and rows[0]["stain"] == ""
        assert rows[0]["experimental_unit"] == "" and rows[0]["excluded"] == "True"
        assert rows[0]["exclusion_reason"] == "'=Research note"
        labels = import_roi_zip(opened.read("masks/f1/regions-rois.zip"))
        np.testing.assert_array_equal(labels, np.load(store.safe_path("results", "r1", "f1", "labels.npy")))
        methods = opened.read("methods.md").decode()
        assert "Actin" in methods and "stain: not recorded" in methods
        assert "no automatic detector" in methods
        manifest = json.loads(opened.read("manifest.json"))
        assert manifest["raw_included"] is False


def test_raw_opt_in_replays_same_measurements_from_tiffs(tmp_path):
    store, settings, config = setup_fields(tmp_path)
    report = execute(store, settings, config)
    output = tmp_path / "export"
    build_region_bundle(output, **bundle_inputs(store, config, report), include_raw=True)
    result = replay_region_bundle(output / "bundle", output / "bundle" / "raw", tmp_path / "replay")
    assert result == {"matched_saved_measurements": True, "matched_saved_descriptions": True,
                      "measured_fields_replayed": ["f1"], "unmeasured_fields_preserved_not_reassessed": []}
    assert read_json(tmp_path / "replay" / "measurements.json")["field_tables"] == report["field_tables"]


def test_diagnostic_export_and_replay_do_not_erase_or_reclassify_failed_fields(tmp_path):
    store, settings, config = setup_fields(tmp_path, count=2)
    config["backgrounds"]["f2"]["actin"]["polygon"] = [[2, 2], [4, 2], [4, 4], [2, 4]]
    report = execute(store, settings, config)
    output = tmp_path / "diagnostic"
    build_region_bundle(output, **bundle_inputs(store, config, report))
    replay = tmp_path / "replay"
    result = replay_region_bundle(output / "bundle", store.safe_path("workspaces", "w", "fields"), replay)
    assert result["matched_saved_measurements"]
    assert result["unmeasured_fields_preserved_not_reassessed"] == ["f2"]
    assert read_json(replay / "measurements.json")["field_failures"] == report["field_failures"]
    assert (output / "bundle" / "masks" / "f2" / "labels.npy").exists()


def test_replay_rejects_changed_originals_and_changed_bundle_members(tmp_path):
    store, settings, config = setup_fields(tmp_path)
    report = execute(store, settings, config)
    output = tmp_path / "export"
    build_region_bundle(output, **bundle_inputs(store, config, report))
    source = store.safe_path("workspaces", "w", "fields", "f1", "ch0.tif")
    raw = source.read_bytes()
    source.write_bytes(raw + b"x")
    with pytest.raises(ValueError, match="region_replay_input_mismatch"):
        replay_region_bundle(output / "bundle", store.safe_path("workspaces", "w", "fields"), tmp_path / "bad-raw")
    source.write_bytes(raw)
    (output / "bundle" / "regions.csv").write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="region_bundle_file_hash_mismatch"):
        replay_region_bundle(output / "bundle", store.safe_path("workspaces", "w", "fields"), tmp_path / "bad-bundle")


def test_reviewed_description_is_recomputed_from_source_for_export_and_replay(tmp_path):
    store, settings, config = setup_fields(tmp_path)
    report = execute(store, settings, config)
    config = {**config, "review_record": {"confirmed_at": 1.0}}
    request = DescriptiveRequest.model_validate({
        "mode": "descriptive", "selection": {"source": "region", "region_set_id": "reviewed",
                                               "channel_id": "actin", "metric": "mean_corrected"},
    })
    result = describe_regions(report, config["field_snapshot"], request)
    result["revision_id"] = "r1"
    output = tmp_path / "export"
    build_region_bundle(output, **bundle_inputs(store, config, report), statistics_results=[result])
    replay = tmp_path / "replay"
    verification = replay_region_bundle(output / "bundle", store.safe_path("workspaces", "w", "fields"), replay)
    assert verification["matched_saved_descriptions"]
    source_result = read_json(output / "bundle" / "statistics" / "0" / "result.json")
    replayed = read_json(replay / "statistics" / "0" / "result.json")
    assert source_result["plot_data"] == replayed["plot_data"]
    assert replayed["counts"]["experimental_units"] is None
    for extension in ("svg", "pdf", "png"):
        assert (replay / "statistics" / "0" / f"figure.{extension}").is_file()


@pytest.mark.parametrize("fault,expected", [("unreviewed", "review_required"), ("changed_value", "source_mismatch"),
                                           ("inference", "unrecognized_fields"), ("bool_review", "review_required"),
                                           ("changed_exclusion", "source_mismatch"),
                                           ("negative_review", "review_required"), ("infinite_review", "review_required")])
def test_figure_export_cannot_bypass_review_or_substitute_source_values(tmp_path, fault, expected):
    store, settings, config = setup_fields(tmp_path)
    report = execute(store, settings, config)
    request = DescriptiveRequest.model_validate({
        "mode": "descriptive", "selection": {"source": "region", "region_set_id": "reviewed", "metric": "area_px"},
    })
    result = describe_regions(report, config["field_snapshot"], request)
    result["revision_id"] = "r1"
    if fault != "unreviewed":
        config = {**config, "review_record": {"confirmed_at": 1.0}}
    if fault == "changed_value":
        result["plot_data"][0]["value"] = 999.0
    if fault == "inference":
        result["comparisons"] = [{"p_value": 0.01}]
    if fault == "bool_review":
        config["review_record"]["confirmed_at"] = True
    if fault == "negative_review":
        config["review_record"]["confirmed_at"] = -1.0
    if fault == "infinite_review":
        config["review_record"]["confirmed_at"] = float("inf")
    if fault == "changed_exclusion":
        config = {**config, "exclusions": [{"field_id": next(iter(config["field_snapshot"])),
                                           "region_id": None, "reason": "Changed after review"}]}
    with pytest.raises(ValueError, match=expected):
        build_region_bundle(tmp_path / "export", **bundle_inputs(store, config, report), statistics_results=[result])


def test_worker_export_writes_private_job_artifacts(tmp_path):
    store, settings, config = setup_fields(tmp_path)
    execute(store, settings, config)
    output = store.safe_path("export-attempt")
    run_region_export(store, {"revision_id": "r1", "workspace_id": "w", "payload": {"include_raw": False}}, output)
    assert read_json(output / "result.json") == {"files": ["analysis.zip", "methods.md"],
                                                 "raw_included": False, "revision_id": "r1"}


def test_missing_saved_statistics_fail_export_instead_of_silently_omitting(tmp_path):
    from cytellect_api.db import jobs

    store, settings, config = setup_fields(tmp_path)
    execute(store, settings, config)
    payload = {"mode": "descriptive", "selection": {"source": "compartment-summary", "region_set_id": "cells",
                                                    "metric": "nucleolar_count"}}
    with store.transaction() as connection:
        connection.execute(jobs.insert().values(id="j_ratio", workspace_id="w", revision_id="r1", kind="statistics",
                                                state="succeeded", payload=payload, created=1.0, result_dir="missing"))
    output = store.safe_path("export-attempt")
    with pytest.raises(FileNotFoundError):
        run_region_export(store, {"revision_id": "r1", "workspace_id": "w", "payload": {"include_raw": False}}, output)
    assert not (output / "analysis.zip").exists()
