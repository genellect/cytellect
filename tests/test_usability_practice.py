"""Artificial task material catches hierarchy errors; this is not a human evaluation."""
import copy
import csv
import hashlib
import importlib.util
import json
import math
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest
import tifffile
from cytellect_analysis.descriptive import describe_regions
from cytellect_analysis.descriptive_contracts import DescriptiveRequest
from cytellect_analysis.region_comparison import compare_regions
from cytellect_analysis.region_comparison_contracts import RegionComparisonRequest
from cytellect_analysis.region_contracts import RegionFieldInput
from cytellect_analysis.regions import (
    BackgroundSpec,
    ChannelSpec,
    RegionMeasurementSpec,
    RegionSetSpec,
    measure_regions,
)
from cytellect_api.region_inputs import read_label_tiff

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("usability_practice", REPO / "scripts/prepare_usability_practice.py")
assert SPEC and SPEC.loader
PRACTICE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PRACTICE)
EXPECTED = [[-2, 2, 10], [4], [8, 12], [5], [1, 5, 9], [6, 8],
            [1, 5, 13], [7], [11, 15], [4], [0, 4, 8], [8, 10]]


def test_practice_pixels_record_cards_and_hierarchical_units(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    manifest = PRACTICE.prepare(first)
    assert PRACTICE.prepare(second) == manifest
    for item in manifest["files"]:
        content = (first / item["path"]).read_bytes()
        assert content == (second / item["path"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == item["sha256"]
    assert manifest["human_evaluation_performed"] is False
    assert len(list((first / "participant/images").glob("*.tif"))) == 12
    assert len(list((first / "participant/masks").glob("*.tif"))) == 12
    channel = ChannelSpec(channel_id="channel-1", label="練習信号", stain=None, identity_confirmed=True)
    recipe = {"id": "region-2d", "version": "1.0.0", "region_set_id": "regions",
              "label": "人工領域", "source": "imported", "defining_channel_id": None}
    report = {"analysis_kind": "region-2d", "revision_id": "practice-test", "recipe": recipe,
              "field_tables": {}, "field_failures": [], "excluded_failed_fields": [], "exclusions": []}
    for index, values in enumerate(EXPECTED, 1):
        fid = f"f{index:02d}"
        with tifffile.TiffFile(first / f"participant/images/{fid}-signal.tif") as tif:
            assert len(tif.pages) == 1 and tif.series[0].axes == "YX"
            image = tif.asarray()
        labels = read_label_tiff(first / f"participant/masks/{fid}-labels.tif", [80, 80])
        assert image.dtype == np.uint16 and labels.dtype == np.uint32
        expected_labels = np.zeros((80, 80), dtype=np.uint32)
        for rid, (y, x) in enumerate(((24, 16), (24, 48), (52, 32))[:len(values)], 1):
            expected_labels[y:y + 12, x:x + 12] = rid
        assert np.array_equal(labels, expected_labels)
        assert np.all(image[labels == 0] == 10)
        for rid, value in enumerate(values, 1):
            assert np.all(image[labels == rid] == value + 10)
        background = np.zeros((80, 80), dtype=bool)
        background[:13, :13] = True
        spec = RegionMeasurementSpec(field_id=fid, analysis_revision_id="practice-test",
            region_set=RegionSetSpec(region_set_id="regions", label="人工領域", mask_revision_id=f"m-{fid}", source="imported"),
            channels=(channel,), backgrounds=(BackgroundSpec(channel_id="channel-1", roi_revision_id=f"bg-{fid}", confirmed=True),))
        table = measure_regions({"channel-1": image}, labels, {"channel-1": background}, spec)
        assert [row.mean_corrected for row in table.rows] == values
        assert all(row.area_px == 144 and row.area_um2 is None and row.integrated_corrected == 144 * value
                   for row, value in zip(table.rows, values, strict=True))
        report["field_tables"][fid] = table.model_dump(mode="json")
    assert sum(len(table["rows"]) for table in report["field_tables"].values()) == 24
    selection = {"source": "region", "region_set_id": "regions", "channel_id": "channel-1", "metric": "mean_corrected"}
    for variant in ("independent", "paired", "missing"):
        snapshot = {}
        with (first / f"participant/cards/{variant}-records.csv").open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                md = {key: row[label] or None for key, label in (
                    ("condition", "条件"), ("sample", "試料"), ("experimental_unit", "独立実験単位"),
                    ("acquisition_date", "撮影日／バッチ"), ("pair", "対応ペア"))}
                parsed = RegionFieldInput.model_validate({"channels": [channel.model_dump()], "metadata": md})
                snapshot[row["視野"]] = {"metadata": parsed.metadata.model_dump(), "image_info": {
                    "shape": [80, 80], "calibration": None, "channels": [channel.model_dump()]}}
        config = {"field_ids": list(snapshot), "field_snapshot": snapshot, "recipe": recipe,
                  "backgrounds": {}, "exclusions": [], "review_record": {"confirmed_at": 1.0}}
        # This confirmation is a test fixture, not a record of participant review.
        paired = variant == "paired"
        request = RegionComparisonRequest.model_validate({"mode": "region-experimental-unit", "selection": selection,
            "design": {"kind": "paired" if paired else "independent", "confirmed": True,
                       "unit_definition": "Artificial record-card units", "pairing_basis": "Same artificial unit" if paired else None},
            "conditions": ["A", "B"], "comparison_family": {"family_id": "practice", "kind": "control", "control": "A", "contrasts": [["A", "B"]]},
            "acquisition_review": {"confirmed": True, "basis": "same-settings"}, "missingness_confirmed": True})
        if variant == "missing":
            assert snapshot["f02"]["metadata"]["experimental_unit"] is None
            with pytest.raises(ValueError, match="^region_comparison_metadata_required$"):
                compare_regions(report, config, request)
            result = describe_regions(report, snapshot, DescriptiveRequest.model_validate({"mode": "descriptive", "selection": selection}))
            assert result["counts"]["observations"] == 24 and result["counts"]["selected_fields"] == 12
            assert result["counts"]["experimental_units"] is None
            continue
        result = compare_regions(copy.deepcopy(report), config, request)
        assert [r["value"] for r in result["field_summary"]] == [2, 4, 10, 5, 5, 7, 5, 7, 13, 4, 4, 9]
        assert {r["sample"]: r["value"] for r in result["sample_summary"]} == {
            "A1-s1": 3, "A1-s2": 10, "A2-s1": 5, "A3-s1": 7, "B1-s1": 6, "B1-s2": 13, "B2-s1": 4, "B3-s1": 9}
        assert [r["value"] for r in result["unit_summary"]] == [6.5, 5, 7, 9.5, 4, 9]
        assert all(c["experimental_units"] == 3 and c["selected_fields"] == 6 and c["observations"] == 12 for c in result["counts"])
        contrast = result["comparisons"][0]
        assert contrast["estimate"] == pytest.approx(-4 / 3)
        assert contrast["standard_error"] == pytest.approx(math.sqrt(13 if paired else 31) / 3)
        assert contrast["degrees_of_freedom"] == pytest.approx(2 if paired else 15376 / 6245)
        if paired:
            assert contrast["complete_pairs"] == 3
            assert contrast["p_value"] == pytest.approx(1 - 4 / math.sqrt(42))
    reference = json.loads((first / "observer/reference.json").read_text(encoding="utf-8"))
    for condition, rows in (("A", EXPECTED[:6]), ("B", EXPECTED[6:])):
        naive = sum(Fraction(v) for row in rows for v in row) / sum(map(len, rows))
        assert naive == Fraction(reference["wrong_region_pool"][condition])
    assert Fraction(reference["wrong_region_pool"]["effect"]) != Fraction(reference["effect_a_minus_b"])


def test_practice_requires_explicit_empty_output_outside_checkout(tmp_path):
    with pytest.raises(ValueError, match="outside_checkout"):
        PRACTICE.prepare(REPO / "not-created-practice")
    marker = tmp_path / "preserve.txt"
    marker.write_text("User data", encoding="utf-8")
    with pytest.raises(ValueError, match="must_be_empty"):
        PRACTICE.prepare(tmp_path)
    assert marker.read_text(encoding="utf-8") == "User data"
    with pytest.raises(ValueError, match="must_be_empty"):
        PRACTICE.prepare(marker)
    with pytest.raises(SystemExit) as caught:
        PRACTICE.main([])
    assert caught.value.code == 2
