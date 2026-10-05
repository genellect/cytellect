"""Raw-only protocol 3 replay uses source pixels, never invented backgrounds."""
import copy
import csv
import json

import numpy as np
import pytest
import tifffile
from cytellect_analysis.descriptive import describe_regions
from cytellect_analysis.descriptive_contracts import DescriptiveRequest
from cytellect_analysis.descriptive_figures import descriptive_methods
from cytellect_analysis.region_comparison import compare_regions
from cytellect_analysis.region_comparison_contracts import RegionComparisonRequest
from cytellect_analysis.region_comparison_figures import region_comparison_methods
from cytellect_analysis.region_exports import build_region_bundle, replay_region_bundle
from cytellect_analysis.statistical_methods import CURRENT_METHODS_TEMPLATE
from cytellect_api.db import fields
from cytellect_api.storage import read_json
from sqlalchemy import update
from test_region_area_worker import execute_versioned
from test_region_comparison import comparison_request
from test_region_export import bundle_inputs
from test_region_worker import _record, setup_fields

POLICY = {"version": "1.1.0", "mode": "raw_intensity"}
OFFSETS = (0, 2, 7, 3)


def raw_sources(tmp_path):
    store, settings, original = setup_fields(tmp_path, count=4)
    config = {**copy.deepcopy(original), "measurement": POLICY.copy(), "backgrounds": {}}
    originals = {}
    for index, offset in enumerate(OFFSETS):
        fid = f"f{index + 1}"
        snapshot = config["field_snapshot"][fid]
        folder = store.safe_path("workspaces", "w", "fields", fid)
        array_path, tiff_path = folder / "channel-actin.npy", folder / "ch0.tif"
        image = np.load(array_path, allow_pickle=False) + offset
        np.save(array_path, image, allow_pickle=False)
        tifffile.imwrite(tiff_path, image, photometric="minisblack")
        originals[fid] = tiff_path.read_bytes()
        info = snapshot["image_info"]
        info["inputs"]["ch0"], info["channel_arrays"]["actin"] = _record(tiff_path), _record(array_path)
        snapshot["metadata"].update(condition="A" if index < 2 else "B", experimental_unit=f"unit{index}",
                                    sample=f"sample{index}", acquisition_date="batch", pair=None)
        with store.transaction() as connection:
            connection.execute(update(fields).where(fields.c.id == fid).values(image_info=info, metadata=snapshot["metadata"]))
    report = execute_versioned(store, settings, config)
    assert report["field_failures"] == []
    for fid, content in originals.items():
        assert store.safe_path("workspaces", "w", "fields", fid, "ch0.tif").read_bytes() == content
    config["review_record"] = {"confirmed_at": 123.0}
    return store, config, report


def raw_statistics(config, report):
    selection = {"source": "region", "region_set_id": "reviewed", "channel_id": "actin", "metric": "mean"}
    described = describe_regions(report, config["field_snapshot"], DescriptiveRequest.model_validate({
        "mode": "descriptive", "selection": selection}))
    described["revision_id"] = report["revision_id"]
    comparison = comparison_request(metric="mean").model_dump(mode="json")
    comparison["selection"] = selection
    compared = compare_regions(report, config, RegionComparisonRequest.model_validate(comparison))
    return described, compared


def assert_no_background_claim(text):
    assert "background" in text.casefold()
    for claim in ("background-subtracted counterparts", "reviewed masks/backgrounds were used",
                  "Native negative background-corrected values were retained", "mask and background provenance is stored",
                  "converted RGB", "max(R,G,B)", "clipped to zero", "For each channel, a user-confirmed ROI"):
        assert claim not in text


@pytest.mark.parametrize("template", [None, CURRENT_METHODS_TEMPLATE])
def test_raw_descriptive_and_comparison_methods_do_not_claim_background_correction(tmp_path, template):
    store, config, report = raw_sources(tmp_path)
    described, compared = raw_statistics(config, report)
    assert [item["value"] for item in described["plot_data"]] == [value + offset for offset in OFFSETS for value in (6, 20)]
    assert [item["value"] for item in compared["unit_summary"]] == [13 + offset for offset in OFFSETS]
    assert all(count["experimental_units"] == 2 for count in compared["counts"])
    for text in (descriptive_methods(described, methods_template=template),
                 region_comparison_methods(compared, methods_template=template)):
        assert_no_background_claim(text)
        assert "raw" in text.casefold()
        assert "background" in text.casefold() and ("not established" in text or "No background" in text)
    store.engine.dispose()


def test_raw_bundle_replays_measurements_comparison_and_editable_figures_exactly(tmp_path):
    store, config, report = raw_sources(tmp_path)
    assert report["protocol_version"] == "3.0.0" and report["measurement"] == POLICY
    for index, offset in enumerate(OFFSETS):
        rows = report["field_tables"][f"f{index + 1}"]["rows"]
        assert [(row["mean"], row["median"], row["integrated"]) for row in rows] == [
            (6 + offset, 6 + offset, 24 + 4 * offset), (20 + offset, 20 + offset, 80 + 4 * offset)]
        assert all(row["mean_corrected"] is None and row["integrated_corrected"] is None
                   and row["correction_missing_reason"] == "background_not_established" for row in rows)
    described, compared = raw_statistics(config, report)
    for result in (described, compared):
        result["figure"] = {"methods_template": CURRENT_METHODS_TEMPLATE.model_dump(mode="json")}
    output = tmp_path / "export"
    build_region_bundle(output, **bundle_inputs(store, config, report), statistics_results=[described, compared], include_raw=True)
    bundle, replay = output / "bundle", tmp_path / "replay"
    assert read_json(bundle / "manifest.json")["format"] == "cytellect-region-reproducibility/3"
    assert not list(bundle.rglob("background-*.npy"))
    rows = list(csv.DictReader((bundle / "regions.csv").read_text(encoding="utf-8-sig").splitlines()))
    assert [float(row["mean"]) for row in rows] == [value + offset for offset in OFFSETS for value in (6, 20)]
    assert all(row["mean_corrected"] == "" and row["correction_missing_reason"] == "background_not_established" for row in rows)
    text = (bundle / "methods.md").read_text(encoding="utf-8")
    assert "Methods template 1.3.0; region measurement protocol 3.0.0" in text
    assert_no_background_claim(text)
    verified = replay_region_bundle(bundle, bundle / "raw", replay)
    assert verified["matched_saved_measurements"] and verified["matched_saved_descriptions"] and verified["matched_saved_comparisons"]
    assert read_json(replay / "measurements.json")["field_tables"] == report["field_tables"]
    for index in (0, 1):
        for root in (bundle, replay):
            folder = root / "statistics" / str(index)
            assert (folder / "figure.pdf").read_bytes().startswith(b"%PDF")
            assert "<svg" in (folder / "figure.svg").read_text(encoding="utf-8")
            assert_no_background_claim((folder / "methods.md").read_text(encoding="utf-8"))
            figure_data = read_json(folder / "figure-data.json")
            assert figure_data["spec"]["selection"]["metric"] == "mean"
            assert all(field["measurement_protocol"] == "3.0.0" and field["measurement"] == POLICY
                       for field in figure_data["source_fields"])
        assert (bundle / "statistics" / str(index) / "methods.md").read_bytes() == (replay / "statistics" / str(index) / "methods.md").read_bytes()
    manifest = read_json(bundle / "manifest.json")
    manifest["format"] = "cytellect-region-reproducibility/2"
    (bundle / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="region_measurement_protocol_mismatch"):
        replay_region_bundle(bundle, bundle / "raw", tmp_path / "wrong-format-replay")
    store.engine.dispose()


@pytest.mark.parametrize("fault", ["missing_policy", "area_policy", "wrong_table_protocol", "background"])
def test_raw_bundle_refuses_mixed_measurement_policy(tmp_path, fault):
    store, config, report = raw_sources(tmp_path)
    if fault == "missing_policy":
        config.pop("measurement")
    elif fault == "area_policy":
        report["measurement"] = {"version": "1.0.0", "mode": "area_only"}
    elif fault == "wrong_table_protocol":
        report["field_tables"]["f1"]["protocol_version"] = "2.0.0"
    else:
        config["backgrounds"] = {"f1": {"actin": {"confirmed": True, "polygon": [[0, 0], [2, 0], [2, 2]]}}}
    with pytest.raises(ValueError):
        build_region_bundle(tmp_path / "rejected", **bundle_inputs(store, config, report))
    assert not (tmp_path / "rejected").exists()
    store.engine.dispose()
