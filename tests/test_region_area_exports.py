"""Area-only source, inference and replay with explicit independent references."""
import copy
import csv
import hashlib
import json
import math

import numpy as np
import pytest
import tifffile
from cytellect_analysis.descriptive import describe_regions
from cytellect_analysis.descriptive_contracts import DescriptiveRequest
from cytellect_analysis.region_comparison import compare_regions, source_fingerprint
from cytellect_analysis.region_comparison_contracts import RegionComparisonRequest
from cytellect_analysis.region_exports import build_region_bundle, replay_region_bundle
from cytellect_api.db import fields
from cytellect_api.storage import read_json
from sqlalchemy import update
from test_region_area_worker import POLICY, area_config, execute_versioned
from test_region_comparison import comparison_request
from test_region_export import bundle_inputs
from test_region_worker import _record, setup_fields


def sources(tmp_path):
    store, settings, original = setup_fields(tmp_path, count=4)
    config = area_config(original)
    for index, count in enumerate((2, 4, 7, 5)):
        fid = f"f{index + 1}"
        snapshot = config["field_snapshot"][fid]
        folder = store.safe_path("workspaces", "w", "fields", fid)
        labels = np.zeros((8, 8), np.uint32)
        labels[2, :count] = 7
        tifffile.imwrite(folder / "labels.tif", labels, photometric="minisblack")
        np.save(folder / "labels.npy", labels, allow_pickle=False)
        info = snapshot["image_info"]
        info["inputs"]["labels"] = _record(folder / "labels.tif")
        info["labels_array"] = _record(folder / "labels.npy")
        info["calibration"] = None
        snapshot["metadata"].update(condition="A" if index < 2 else "B", experimental_unit=f"unit{index}",
                                    sample=f"sample{index}", acquisition_date="batch", pair=f"pair{index % 2}")
        with store.transaction() as connection:
            connection.execute(update(fields).where(fields.c.id == fid).values(
                image_info=info, metadata=snapshot["metadata"]))
    report = execute_versioned(store, settings, config)
    assert report["field_failures"] == []
    config["review_record"] = {"confirmed_at": 123.0}
    return store, config, report


def descriptive(metric="area_px"):
    return DescriptiveRequest.model_validate({"mode": "descriptive", "selection": {
        "source": "region", "region_set_id": "reviewed", "channel_id": None, "metric": metric}})


def comparison(paired=False):
    request = comparison_request(paired=paired).model_dump(mode="json")
    request["selection"].update(region_set_id="reviewed", channel_id=None, metric="area_px")
    return RegionComparisonRequest.model_validate(request)


@pytest.mark.parametrize("paired", [False, True])
def test_area_inference_keeps_unit_n_and_matches_closed_form(tmp_path, paired):
    _, config, report = sources(tmp_path)
    result = compare_regions(report, config, comparison(paired))
    test = result["comparisons"][0]
    assert test["estimate"] == -3
    assert test["degrees_of_freedom"] == (1 if paired else 2)
    assert test["standard_error"] == pytest.approx(2 if paired else math.sqrt(2))
    assert test["p_value"] == pytest.approx(1 - 2 * math.atan(1.5) / math.pi if paired else 1 - 3 / math.sqrt(13))
    assert [item["value"] for item in result["unit_summary"]] == [2, 4, 7, 5]
    assert all(item["experimental_units"] == 2 for item in result["counts"])
    assert all(item["measurement_protocol"] == "2.0.0" and item["measurement"] == POLICY
               for item in result["source_fields"])
    assert result["source_fingerprint"] == source_fingerprint(report, config)


def test_area_description_has_traceable_values_and_unknown_scale(tmp_path):
    _, config, report = sources(tmp_path)
    result = describe_regions(report, config["field_snapshot"], descriptive())
    assert [item["value"] for item in result["plot_data"]] == [2, 4, 7, 5]
    assert result["counts"]["experimental_units"] is None
    assert all(item["channel_id"] is None for item in result["plot_data"])
    with pytest.raises(ValueError, match="no_valid_selected_measurements"):
        describe_regions(report, config["field_snapshot"], descriptive("area_um2"))
    request = descriptive().model_dump(mode="json")
    request["selection"].update(metric="mean_corrected", channel_id="actin")
    with pytest.raises(ValueError, match="region_metric_not_measured"):
        describe_regions(report, config["field_snapshot"], request)


@pytest.mark.parametrize("fault", ["report_missing_policy", "report_wrong_protocol", "config_missing_policy",
                                  "table_wrong_protocol", "backgrounds"])
def test_area_export_refuses_mixed_or_fabricated_mode(tmp_path, fault):
    store, config, report = sources(tmp_path)
    if fault == "report_missing_policy":
        report.pop("measurement")
    elif fault == "report_wrong_protocol":
        report["protocol_version"] = "1.0.0"
    elif fault == "config_missing_policy":
        config.pop("measurement")
    elif fault == "table_wrong_protocol":
        report["field_tables"]["f1"]["protocol_version"] = "1.0.0"
    else:
        config["backgrounds"] = {"f1": {}}
    with pytest.raises(ValueError):
        build_region_bundle(tmp_path / "rejected", **bundle_inputs(store, config, report))
    assert not (tmp_path / "rejected").exists()


def test_area_bundle_replays_measured_pixels_figures_and_inference_without_backgrounds(tmp_path):
    store, config, report = sources(tmp_path)
    described = describe_regions(report, config["field_snapshot"], descriptive())
    described["revision_id"] = report["revision_id"]
    compared = compare_regions(report, config, comparison())
    output = tmp_path / "export"
    build_region_bundle(output, **bundle_inputs(store, config, report),
                        statistics_results=[described, compared], include_raw=True)
    bundle = output / "bundle"
    manifest = read_json(bundle / "manifest.json")
    assert manifest["format"] == "cytellect-region-reproducibility/2"
    assert not list(bundle.rglob("background-*.npy"))
    assert read_json(bundle / "revision.json")["config"]["backgrounds"] == {}
    rows = list(csv.DictReader((bundle / "regions.csv").read_text(encoding="utf-8-sig").splitlines()))
    assert [int(row["area_px"]) for row in rows] == [2, 4, 7, 5]
    assert all(row["mean"] == "" and row["mean_corrected"] == ""
               and row["intensity_missing_reason"] == "not_requested" for row in rows)
    methods = (bundle / "methods.md").read_text(encoding="utf-8")
    assert "Methods template 1.2.0" in methods and "No fluorescence summary" in methods
    assert "background-subtracted counterparts" not in methods
    verification = replay_region_bundle(bundle, bundle / "raw", tmp_path / "replay")
    assert verification["matched_saved_measurements"] and verification["matched_saved_descriptions"]
    assert verification["matched_saved_comparisons"]
    for index in (0, 1):
        for extension in ("svg", "pdf", "png"):
            assert (tmp_path / "replay/statistics" / str(index) / f"figure.{extension}").is_file()
        for parent in (bundle, tmp_path / "replay"):
            figures = parent / "statistics" / str(index)
            individual_methods = (figures / "methods.md").read_text(encoding="utf-8")
            assert "protocol 2.0.0" in individual_methods and "policy 1.0.0 (area_only)" in individual_methods
            assert "Region area was computed from reviewed masks in original image coordinates." in individual_methods
            assert "Fluorescence intensity and signal-saturation fractions were not measured." in individual_methods
            assert "Background estimation and correction were not performed." in individual_methods
            assert "reviewed masks/backgrounds were used" not in individual_methods
            assert "Native negative background-corrected values were retained" not in individual_methods
            assert "mask and background provenance is stored" not in individual_methods
            source = read_json(figures / "figure-data.json")
            assert source["spec"]["selection"]["metric"] == "area_px"
            assert source["spec"]["selection"]["channel_id"] is None
            assert all(field["measurement_protocol"] == "2.0.0" and field["measurement"] == POLICY
                       and field["region_set"]["source"] == config["recipe"]["source"]
                       for field in source["source_fields"])
        assert (bundle / "statistics" / str(index) / "methods.md").read_bytes() == (
            tmp_path / "replay/statistics" / str(index) / "methods.md").read_bytes()
    assert "masks, backgrounds and channel identities are recorded" not in (
        bundle / "statistics/0/figure-caption.md").read_text(encoding="utf-8")
    # An attacker updating the outer hashes still cannot add a background to
    # an area-only replay. Hash integrity and measurement semantics are distinct.
    path = bundle / "masks/f1/background-actin.npy"
    np.save(path, np.zeros((8, 8), bool), allow_pickle=False)
    changed = copy.deepcopy(manifest)
    changed["files"]["masks/f1/background-actin.npy"] = hashlib.sha256(path.read_bytes()).hexdigest()
    (bundle / "manifest.json").write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="region_area_only_backgrounds_forbidden"):
        replay_region_bundle(bundle, bundle / "raw", tmp_path / "rejected-replay")
