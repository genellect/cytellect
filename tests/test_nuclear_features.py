"""Numeric checks of nuclear-features/1.0.0 (genellect/cytellect#257 E-1, E-3, E-7; requirements M-06).

The public checks use the registered BBBC039 Hoechst fields and their manual nucleus annotations (CC0, fixtures/
public/bbbc039): every value of the shared implementation is compared with a calculation written here from first
principles (NumPy and SciPy only) and with the independent Otsu rule of the public nucleolar check. The fixture
stands in for a StarDist nuclear set (its source is recorded as such) because the values depend only on the label
image and the pixels, not on how the labels were drawn.

The small arrays further down are 合成 (synthetic) label and value arrays for rule checks only, as
docs/development-principles.md allows: each one fixes one branch (saturation, a zero background spread, an equality
at the threshold, a missing acquisition date) whose expected value cannot be pinned on a real image, and none of them
sets a detection, threshold or biological claim.
"""
import copy
import sys
from pathlib import Path

import numpy as np
import pytest
import tifffile
from cytellect_analysis import nuclear_features
from cytellect_analysis.background_candidate import automatic_background
from cytellect_analysis.common_statistics import analyze_region_comparison
from cytellect_analysis.descriptive import describe_regions
from cytellect_analysis.descriptive_contracts import RegionSelection
from cytellect_analysis.nuclear_features import (
    background_spread,
    compute_features,
    nuclear_shapes,
    nuclear_signal,
)
from cytellect_analysis.region_measurement_v2 import (
    RegionMeasurementSpecV4,
    measure_regions_versioned,
    require_region_metric,
)
from test_public_bbbc039 import benchmark

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import validate_nucleolar_shape_public as independent  # noqa: E402

FLOOR = 1.0
POLICY = {"version": "1.2.0", "mode": "automatic_background"}


@pytest.fixture(autouse=True)
def floor(monkeypatch):
    monkeypatch.setattr(nuclear_features, "MINIMUM_SIGNAL_TO_BACKGROUND", FLOOR)


def public_fields(count=3):
    manifest = benchmark.verify()
    out = []
    for item in manifest["images"][:count]:
        pixels = tifffile.imread(benchmark.FIXTURE / item["image"]["path"])
        labels = benchmark.decode_ground_truth(benchmark.FIXTURE / item["mask"]["path"]).astype(np.uint32)
        out.append((item["id"], pixels, labels))
    return out


def public_report(dates=("2026-01-01", "2026-01-01", "2026-01-02"), conditions=("A", "B", "A")):
    fields = public_fields(len(dates))
    tables, snapshot, images, labels_by = {}, {}, {}, {}
    channel = {"channel_id": "dna", "label": "DNA", "stain": "Hoechst", "identity_confirmed": True}
    for index, ((_, pixels, labels), date, condition) in enumerate(zip(fields, dates, conditions, strict=True)):
        fid = f"f{index}"
        spec = RegionMeasurementSpecV4.model_validate({
            "field_id": fid, "analysis_revision_id": "r", "measurement": POLICY,
            "region_set": {"region_set_id": "nuclei", "label": "Nuclei", "source": "stardist_nuclear",
                           "mask_revision_id": "m", "defining_channel_id": "dna"},
            "channels": (channel,)})
        tables[fid] = measure_regions_versioned({"dna": pixels}, labels, {}, spec).model_dump(mode="json")
        snapshot[fid] = {"metadata": {"condition": condition, "experimental_unit": f"u{index}", "sample": f"s{index}",
                                      "acquisition_date": date},
                         "image_info": {"shape": list(pixels.shape), "calibration": None, "channels": [channel]}}
        images[fid], labels_by[fid] = pixels, labels
    report = {"revision_id": "r", "analysis_kind": "region-2d", "protocol_version": "4.0.0", "measurement": POLICY,
              "recipe": {"source": "stardist_nuclear"}, "field_tables": tables, "field_failures": [],
              "excluded_failed_fields": [], "exclusions": []}
    return report, snapshot, images, labels_by


def features_for(report, snapshot, images, labels, keys):
    return compute_features(keys, report, snapshot, labels.__getitem__, lambda fid, _channel: images[fid])


def test_public_shape_values_match_first_principles():
    for _, _, labels in public_fields():
        rows = nuclear_shapes(labels)
        border = independent.border_ids(labels)
        checked = 0
        for rid, row in rows.items():
            area = int((labels == rid).sum())
            assert row["area_px"] == area
            if rid in border:
                assert row["missing_reason"] == "touches_border" and row["solidity"] is None
                continue
            if area < nuclear_features.MINIMUM_AREA_PX:
                assert row["missing_reason"] == "below_minimum_area" and row["eccentricity"] is None
                continue
            coords = np.argwhere(labels == rid)
            solidity, axis_ratio, eccentricity = independent.shape_independent(coords)
            assert row["solidity"] == pytest.approx(solidity, abs=1e-12)
            assert row["axis_ratio"] == pytest.approx(axis_ratio, rel=1e-9)
            assert row["eccentricity"] == pytest.approx(eccentricity, abs=1e-7)
            checked += 1
        assert checked >= 20


def test_public_signal_values_match_first_principles():
    report, snapshot, images, labels = public_report()
    features = features_for(report, snapshot, images, labels, {("cv_corrected", "dna"), ("positive_area_fraction", "dna")})
    pools: dict[str, list[np.ndarray]] = {}
    expected_cv = {}
    for fid, image in images.items():
        field_labels = labels[fid]
        background = report["field_tables"][fid]["channel_provenance"][0]["background"]
        assert background["status"] == "established"
        mask, _ = automatic_background(image, field_labels)
        pixels = image[mask].astype(np.float64)
        median = float(np.median(pixels))
        spread = 1.4826 * float(np.median(np.abs(pixels - median)))
        assert median == background["background_median"]
        record = features["cv_corrected", "dna"][fid]
        assert record["background_median"] == median and record["background_spread"] == pytest.approx(spread, rel=1e-12)
        border = independent.border_ids(field_labels)
        for rid in (int(value) for value in np.unique(field_labels) if value):
            raw = image[field_labels == rid].astype(np.float64)
            value = record["values"][rid]
            if rid in border:
                assert value["value"] is None and value["missing_reason"] == "touches_border"
                continue
            corrected = raw - median
            if (raw >= 65535).any() or corrected.mean() <= 0 or corrected.mean() / spread < FLOOR:
                assert value["value"] is None
                continue
            assert value["value"] == pytest.approx(corrected.std() / corrected.mean(), rel=1e-12)
            assert value["mean_corrected"] == pytest.approx(corrected.mean(), rel=1e-12)
            assert value["cv_raw"] == pytest.approx(raw.std() / raw.mean(), rel=1e-12)
            expected_cv[fid, rid] = value["value"]
            pools.setdefault(snapshot[fid]["metadata"]["acquisition_date"], []).append(corrected)
    assert len(expected_cv) >= 40
    # One threshold per acquisition date, pooled over that date's fields only.
    for fid, image in images.items():
        date = snapshot[fid]["metadata"]["acquisition_date"]
        threshold = independent.otsu_independent(np.concatenate(pools[date]))
        record = features["positive_area_fraction", "dna"][fid]
        assert record["threshold"]["acquisition_date"] == date
        assert record["threshold"]["value"] == pytest.approx(threshold, rel=1e-12)
        assert record["threshold"]["nuclei"] == len(pools[date])
        for rid, value in record["values"].items():
            if (fid, rid) not in expected_cv:
                assert value["value"] is None
                continue
            corrected = image[labels[fid] == rid].astype(np.float64) - record["background_median"]
            assert value["value"] == np.count_nonzero(corrected > threshold) / corrected.size
    first, third = (features["positive_area_fraction", "dna"][fid]["threshold"]["value"] for fid in ("f0", "f2"))
    assert first != third


def test_public_statistics_use_the_bound_values_and_record_how():
    report, snapshot, images, labels = public_report()
    keys = {("solidity", None)}
    features = features_for(report, snapshot, images, labels, keys)
    request = {"mode": "descriptive", "selection": {"source": "region", "region_set_id": "nuclei", "metric": "solidity"}}
    result = describe_regions(report, snapshot, request, features=features)
    expected = sorted(value["value"] for record in features["solidity", None].values()
                      for value in record["values"].values() if value["value"] is not None)
    assert sorted(row["value"] for row in result["plot_data"]) == pytest.approx(expected)
    assert result["unit"] == "dimensionless"
    source = result["source_fields"][0]["nuclear_features"]
    assert source["protocol"] == "nuclear-features/1.0.0" and "values" not in source
    assert source["minimum_area_px"] == nuclear_features.MINIMUM_AREA_PX
    assert sum(source["nuclei_by_status"].values()) == len(features["solidity", None]["f0"]["values"])
    missing = {row["reason"] for row in result["missingness"]}
    assert "touches_border" in missing and "metric_unavailable" not in missing
    with pytest.raises(ValueError, match="nuclear_features_unavailable"):
        describe_regions(report, snapshot, request)
    # The pixel CV and positive-area fraction did not pass the public check: they are not statistics metrics.
    for metric in ("cv_corrected", "positive_area_fraction"):
        with pytest.raises(ValueError):
            RegionSelection(source="region", region_set_id="nuclei", channel_id="dna", metric=metric)


def test_public_comparison_keeps_runs_and_sampling():
    report, snapshot, images, labels = public_report(dates=("d1", "d1", "d1"), conditions=("A", "B", "A"))
    features = features_for(report, snapshot, images, labels, {("solidity", None)})
    config = {"recipe": report["recipe"], "field_ids": sorted(snapshot), "field_snapshot": snapshot,
              "exclusions": [], "review_record": {"confirmed_at": 1.0}, "measurement": POLICY}
    request = {"mode": "region-experimental-unit", "version": "2.0.0",
               "selection": {"source": "region", "region_set_id": "nuclei", "metric": "solidity"},
               "design": {"kind": "independent", "confirmed": True, "unit_definition": "culture", "pairing_basis": None},
               "conditions": ["A", "B"], "test": "none",
               "comparison_family": {"family_id": "primary", "kind": "control", "control": "A", "contrasts": [["A", "B"]]},
               "acquisition_review": {"confirmed": True, "basis": "same-settings", "field_batches": {},
                                      "spatial_sampling_confirmed": False},
               "missingness_confirmed": True, "aggregation": "field-median_sample-mean_unit-mean-v1",
               "missingness_policy": "available-observations_require-unexcluded-units-v1"}
    with pytest.raises(ValueError, match="region_comparison_incompatible_sampling"):
        analyze_region_comparison(report, config, request, features=features)
    sampled = copy.deepcopy(request)
    sampled["acquisition_review"]["spatial_sampling_confirmed"] = True
    result = analyze_region_comparison(report, config, sampled, features=features)
    assert {row["value"] for row in result["plot_data"]} <= {
        value["value"] for record in features["solidity", None].values() for value in record["values"].values()}


def test_features_are_for_nuclei_only():
    with pytest.raises(ValueError, match="nuclear_features_nuclei_only"):
        RegionSelection(source="region", region_set_id="nucleoli", metric="solidity")
    with pytest.raises(ValueError, match="descriptive_area_channel_must_be_unset"):
        RegionSelection(source="region", region_set_id="nuclei", channel_id="c", metric="eccentricity")
    report, snapshot, images, labels = public_report()
    other = copy.deepcopy(report)
    for table in other["field_tables"].values():
        table["region_set"]["source"] = "imported"
    with pytest.raises(ValueError, match="nuclear_features_nuclei_only"):
        features_for(other, snapshot, images, labels, {("solidity", None)})
    # Shape reads labels only; the signal metrics are refused under every measurement.
    require_region_metric(None, "solidity")
    require_region_metric({"version": "1.0.0", "mode": "area_only"}, "axis_ratio")
    for measurement in (None, {"version": "1.0.0", "mode": "area_only"}, {"version": "1.1.0", "mode": "raw_intensity"},
                        POLICY):
        for metric in ("cv_corrected", "positive_area_fraction"):
            with pytest.raises(ValueError, match="region_metric_not_measured"):
                require_region_metric(measurement, metric)


def test_saved_background_must_be_the_recomputed_one():
    report, snapshot, images, labels = public_report()
    record = report["field_tables"]["f0"]["channel_provenance"][0]["background"]
    changed = {**record, "background_median": record["background_median"] + 1}
    with pytest.raises(ValueError, match="nuclear_features_mismatch"):
        background_spread(images["f0"], labels["f0"], changed)
    assert background_spread(images["f0"], labels["f0"], {**record, "status": "not_established"})[2] == \
        "background_not_established"


# Synthetic rule checks (see the module docstring).
def _two_nuclei(background=100):
    labels = np.zeros((40, 40), np.uint32)
    labels[5:15, 5:15] = 1
    labels[20:30, 20:30] = 2
    image = np.full(labels.shape, background, np.uint16)
    return labels, image


def test_reasons_never_become_zero():
    labels, image = _two_nuclei()
    image[5:15, 5:15] = 140
    image[20:30, 20:30] = 65535
    rows = nuclear_signal(labels, image, background=100.0, spread=10.0, minimum_ratio=FLOOR)
    assert rows[1]["cv_corrected"] == 0 and rows[1]["signal_to_background"] == 4
    assert rows[2]["missing_reason"] == "saturated_pixels" and rows[2]["cv_corrected"] is None
    limited = nuclear_signal(labels, np.where(labels == 2, 200, image).astype(np.uint16), background=100.0, spread=10.0,
                             minimum_ratio=FLOOR, saturation_value=200)
    assert limited[2]["missing_reason"] == "saturated_pixels"
    assert nuclear_signal(labels, image, background=140.0, spread=10.0, minimum_ratio=FLOOR)[1]["missing_reason"] == \
        "nonpositive_mean"
    assert nuclear_signal(labels, image, background=100.0, spread=0.0, minimum_ratio=FLOOR)[1]["missing_reason"] == \
        "background_spread_zero"
    assert nuclear_signal(labels, image, background=100.0, spread=50.0, minimum_ratio=FLOOR)[1]["missing_reason"] == \
        "below_background_spread"
    rows = nuclear_signal(labels, image, background=None, spread=None, background_reason="background_not_established",
                          minimum_ratio=FLOOR)
    assert {row["missing_reason"] for row in rows.values()} == {"background_not_established"}
    edge = labels.copy()
    edge[0, 5] = 1
    assert nuclear_signal(edge, image, background=100.0, spread=10.0, minimum_ratio=FLOOR)[1]["missing_reason"] == \
        "touches_border"


def test_date_threshold_reasons_and_strict_positivity():
    assert nuclear_features.date_threshold([np.array([1.0, 2.0])], None)["missing_reason"] == "acquisition_date_required"
    assert nuclear_features.date_threshold([], "d")["missing_reason"] == "too_few_nuclei"
    assert nuclear_features.date_threshold([np.array([3.0, 3.0])], "d")["missing_reason"] == "uniform_distribution"
    assert nuclear_features.positive_fraction(np.array([1.0, 2.0, 2.0, 3.0]), 2.0) == 0.25
