"""Independent arithmetic, source identity and experimental design acceptance."""
import copy
import json
import math

import numpy as np
import pytest
from cytellect_analysis.region_comparison import compare_regions, source_fingerprint
from cytellect_analysis.region_comparison_contracts import RegionComparisonRequest
from cytellect_analysis.regions import (
    BackgroundSpec,
    ChannelSpec,
    RegionMeasurementSpec,
    RegionSetSpec,
    measure_regions,
)
from pydantic import ValidationError


def comparison_request(*, paired=False, metric="mean_corrected", **changes):
    data = {"mode": "region-experimental-unit", "selection": {"source": "region", "region_set_id": "regions",
            "channel_id": None if metric.startswith("area_") else "actin", "metric": metric},
            "design": {"kind": "paired" if paired else "independent", "confirmed": True,
                       "unit_definition": "Independently treated culture preparations",
                       "pairing_basis": "Matched preparations split before treatment" if paired else None},
            "conditions": ["A", "B"], "comparison_family": {"family_id": "primary", "kind": "control",
                      "control": "A", "contrasts": [["A", "B"]]},
            "acquisition_review": {"confirmed": True, "basis": "same-settings", "spatial_sampling_confirmed": True},
            "missingness_confirmed": True, "plot": {"preset": "nature-double"}}
    return RegionComparisonRequest.model_validate({**data, **changes})


def comparison_fixture(values=(('A', [0, 2]), ('B', [3, 5]))):
    channels = (ChannelSpec(channel_id="actin", label="Actin", stain="phalloidin", identity_confirmed=True),
                ChannelSpec(channel_id="dna", label="DNA", stain="Hoechst", identity_confirmed=True))
    recipe = {"id": "region-2d", "version": "1.0.0", "region_set_id": "regions", "label": "Cell interiors",
              "source": "manual", "defining_channel_id": None}
    report = {"analysis_kind": "region-2d", "revision_id": "analysis_1", "recipe": recipe,
              "field_tables": {}, "field_failures": [], "excluded_failed_fields": [], "exclusions": []}
    snapshot = {}
    for group, numbers in values:
        for index, value in enumerate(numbers):
            fid = f"{group}{index}"
            pixels = np.full((5, 5), 20, dtype=np.uint16)
            pixels[2, 2], pixels[3, 2] = 20 + value - 1, 20 + value + 1
            labels = np.zeros((5, 5), dtype=np.uint32)
            labels[2, 2], labels[3, 2] = 7, 19
            background = np.zeros((5, 5), dtype=bool)
            background[0] = True
            spec = RegionMeasurementSpec(field_id=fid, analysis_revision_id="analysis_1",
                   region_set=RegionSetSpec(region_set_id="regions", label="Cell interiors", mask_revision_id=f"m_{fid}", source="manual"),
                   channels=channels, backgrounds=tuple(BackgroundSpec(channel_id=c.channel_id, roi_revision_id=f"bg_{fid}", confirmed=True) for c in channels))
            table = measure_regions({c.channel_id: pixels for c in channels}, labels,
                                    {c.channel_id: background for c in channels}, spec)
            report["field_tables"][fid] = table.model_dump(mode="json")
            snapshot[fid] = {"metadata": {"condition": group, "experimental_unit": fid, "sample": f"s_{fid}",
                                         "acquisition_date": "batch", "pair": f"p{index}"},
                             "image_info": {"shape": [5, 5], "calibration": None,
                                            "channels": [c.model_dump(mode="json") for c in channels]}}
    config = {"field_ids": list(snapshot), "field_snapshot": snapshot, "recipe": recipe,
              "backgrounds": {}, "exclusions": [], "review_record": {"confirmed_at": 123.0}}
    return report, config


def test_measured_pixels_to_welch_match_closed_form_without_channel_duplication():
    report, config = comparison_fixture()
    result = compare_regions(report, config, comparison_request())
    contrast = result["comparisons"][0]
    assert contrast["estimate"] == -3
    assert contrast["degrees_of_freedom"] == 2
    assert contrast["standard_error"] == pytest.approx(math.sqrt(2))
    assert contrast["p_value"] == pytest.approx(1 - 3 / math.sqrt(13))
    assert contrast["p_holm"] == contrast["p_value"]
    assert len(result["plot_data"]) == 8  # 16 channel rows are not 16 observations.
    assert min(row["value"] for row in result["plot_data"]) == -1
    assert [row["value"] for row in result["unit_summary"]] == [0, 2, 3, 5]
    assert all(row["experimental_units"] == 2 and row["observations"] == 4 for row in result["counts"])
    assert result["channel"]["stain"] == "phalloidin"
    assert result["source_fingerprint"] == source_fingerprint(report, config)
    assert "gfp" not in json.dumps(result)
    assert "cells" not in result["counts"][0]


def test_paired_pixels_and_full_input_ledger_match_closed_form():
    report, config = comparison_fixture((('A', [3, 8, 2]), ('B', [4, 10, 5])))
    result = compare_regions(report, config, comparison_request(paired=True))
    comparison = result["comparisons"][0]
    assert comparison["estimate"] == -2 and comparison["complete_pairs"] == 3
    assert comparison["p_value"] == pytest.approx(1 - math.sqrt(6 / 7))
    assert len(result["unit_ledger"]) == 6 and len(result["pair_ledger"]) == 3
    assert all(row["status"] == "selected" for row in result["pair_ledger"])


@pytest.mark.parametrize("path", [("design", "confirmed"), ("acquisition_review", "confirmed"), ("missingness_confirmed",)])
@pytest.mark.parametrize("false_confirmation", [False, 1, "true"])
def test_confirmation_is_actual_boolean_not_coercion(path, false_confirmation):
    raw = comparison_request().model_dump(mode="json")
    node = raw
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = false_confirmation
    with pytest.raises(ValidationError):
        RegionComparisonRequest.model_validate(raw)


@pytest.mark.parametrize("change,error", [
    (lambda r, c: c["review_record"].update(confirmed_at=True), "review_required"),
    (lambda r, c: r["field_failures"].append({"field_id": "A0"}), "review_required"),
    (lambda r, c: c["field_snapshot"]["A0"]["metadata"].update(experimental_unit=None), "metadata_required"),
    (lambda r, c: c["field_snapshot"]["A0"]["metadata"].update(condition=None), "metadata_required"),
    (lambda r, c: c["field_snapshot"]["A1"]["metadata"].update(sample="s_A0"), "sample_identity_mismatch"),
    (lambda r, c: c["field_snapshot"]["B0"]["metadata"].update(experimental_unit="A0"), "shared_units"),
    (lambda r, c: c["field_snapshot"]["A0"]["image_info"].update(shape=[8, 8]), "shape_mismatch"),
    (lambda r, c: c["field_snapshot"]["A0"]["metadata"].update(acquisition_date=None), "batch_required"),
])
def test_review_and_metadata_cannot_be_inferred_from_measurement_rows(change, error):
    report, config = comparison_fixture()
    change(report, config)
    with pytest.raises(ValueError, match=error):
        compare_regions(report, config, comparison_request())


def test_both_sides_of_a_missing_pair_cannot_disappear_silently():
    report, config = comparison_fixture((('A', [3, 8, 2]), ('B', [4, 10, 5])))
    for fid in ("A0", "B0"):
        report["field_tables"][fid].update(rows=[], status="no_regions")
    with pytest.raises(ValueError, match="unit_without_values"):
        compare_regions(report, config, comparison_request(paired=True))
    for fid in ("A0", "B0"):
        report["exclusions"].append({"field_id": fid, "region_id": None, "reason": "Unusable matched specimens"})
    config["exclusions"] = copy.deepcopy(report["exclusions"])
    result = compare_regions(report, config, comparison_request(paired=True))
    assert result["pair_ledger"][0]["status"] == "excluded"
    assert len(result["pair_ledger"]) == 3 and result["comparisons"][0]["complete_pairs"] == 2
    assert all(row["input_units"] == 3 and row["experimental_units"] == 2 for row in result["counts"])


@pytest.mark.parametrize("mutation,error", [
    (lambda c: c["field_snapshot"]["B0"]["metadata"].update(pair=None), "metadata_required"),
    (lambda c: c["field_snapshot"]["B0"]["metadata"].update(pair="p1"), "unique_complete_pairs"),
    (lambda c: c["field_snapshot"]["B0"]["metadata"].update(pair="other"), "incomplete_pairs"),
    (lambda c: c["field_snapshot"]["B0"]["metadata"].update(experimental_unit="A1"), "inconsistent_pair_identity"),
])
def test_pairs_must_be_explicit_and_consistent_before_selection(mutation, error):
    report, config = comparison_fixture((('A', [3, 8, 2]), ('B', [4, 10, 5])))
    mutation(config)
    with pytest.raises(ValueError, match=error):
        compare_regions(report, config, comparison_request(paired=True))


def test_condition_separated_acquisition_batches_do_not_become_treatment_effects():
    report, config = comparison_fixture()
    for field in config["field_snapshot"].values():
        field["metadata"]["acquisition_date"] = field["metadata"]["condition"]
    with pytest.raises(ValueError, match="condition_batch_confounded"):
        compare_regions(report, config, comparison_request())


def test_actual_batch_confirmation_does_not_fill_an_unknown_date():
    report, config = comparison_fixture()
    for field in config["field_snapshot"].values():
        field["metadata"]["acquisition_date"] = None
    result = compare_regions(report, config, comparison_request(acquisition_review={"confirmed": True,
                 "basis": "same-settings", "field_batches": {fid: "recorded_session" for fid in config["field_ids"]}}))
    assert all(row["acquisition_date"] is None for row in result["source_field_ledger"])
    assert set(result["acquisition"]["field_batches"].values()) == {"recorded_session"}


def test_saturated_selected_regions_block_intensity_but_explicit_exclusion_is_respected():
    report, config = comparison_fixture()
    report["field_tables"]["A0"]["rows"][0]["storage_limit_fraction"] = 1.0
    with pytest.raises(ValueError, match="saturated_signal"):
        compare_regions(report, config, comparison_request())
    report["exclusions"] = [{"field_id": "A0", "region_id": 7, "reason": "Saturated region"}]
    config["exclusions"] = copy.deepcopy(report["exclusions"])
    result = compare_regions(report, config, comparison_request())
    assert result["selection"]["excluded"] == 1


def test_hypothesis_family_is_prespecified_without_legacy_repeat_semantics():
    report, config = comparison_fixture((('A', [0, 2]), ('B', [3, 5]), ('C', [6, 8])))
    request = comparison_request(conditions=["A", "B", "C"], comparison_family={"family_id": "mechanism",
           "kind": "planned", "contrasts": [["A", "B"], ["B", "C"]]})
    result = compare_regions(report, config, request)
    expected_p = 1 - 3 / math.sqrt(13)
    assert all(row["p_holm"] == pytest.approx(2 * expected_p) for row in result["comparisons"])
    assert all(row["correction_family"] == "mechanism" for row in result["comparisons"])
    raw = request.model_dump(mode="json")
    raw["comparison_family"]["contrasts"].append(["B", "A"])
    with pytest.raises(ValidationError, match="invalid_family"):
        RegionComparisonRequest.model_validate(raw)


@pytest.mark.parametrize("metric,scale", [("area_px", 1), ("area_um2", .1)])
def test_area_uses_each_region_once_across_channels_and_retains_measurement_scale(metric, scale):
    from cytellect_analysis.regions import Calibration2D
    report, config = comparison_fixture()
    for fid, value in zip(config["field_ids"], [0, 2, 3, 5], strict=True):
        labels = np.zeros((8, 8), np.uint32)
        labels.flat[10:11 + value] = 7
        labels.flat[30:33 + value] = 19
        image = np.full((8, 8), 20, np.uint16)
        background = np.zeros((8, 8), bool)
        background[0] = True
        channels = tuple(ChannelSpec.model_validate(c) for c in config["field_snapshot"][fid]["image_info"]["channels"])
        calibration = Calibration2D(pixel_size_x_um=.2, pixel_size_y_um=.5, confirmed=True) if metric == "area_um2" else None
        spec = RegionMeasurementSpec(field_id=fid, analysis_revision_id="analysis_1",
               region_set=RegionSetSpec(region_set_id="regions", label="Cell interiors", mask_revision_id=f"m_{fid}", source="manual"),
               channels=channels, backgrounds=tuple(BackgroundSpec(channel_id=c.channel_id, roi_revision_id=f"bg_{fid}", confirmed=True) for c in channels), calibration=calibration)
        report["field_tables"][fid] = measure_regions({c.channel_id: image for c in channels}, labels,
                    {c.channel_id: background for c in channels}, spec).model_dump(mode="json")
        config["field_snapshot"][fid]["image_info"].update(shape=[8, 8], calibration=calibration.model_dump(mode="json") if calibration else None)
    result = compare_regions(report, config, comparison_request(metric=metric))
    assert result["comparisons"][0]["estimate"] == pytest.approx(-3 * scale)
    assert [row["value"] for row in result["unit_summary"]] == pytest.approx([2 * scale, 4 * scale, 5 * scale, 7 * scale])
    assert len(result["plot_data"]) == 8 and all(row["experimental_units"] == 2 for row in result["counts"])
    assert result["channel"] is None


def test_empty_field_is_visible_and_does_not_become_a_zero_value():
    report, config = comparison_fixture()
    empty = copy.deepcopy(report["field_tables"]["A0"])
    empty.update(field_id="A_empty", status="no_regions", rows=[])
    report["field_tables"]["A_empty"] = empty
    config["field_snapshot"]["A_empty"] = copy.deepcopy(config["field_snapshot"]["A0"])
    config["field_ids"].append("A_empty")
    result = compare_regions(report, config, comparison_request())
    assert result["comparisons"][0]["estimate"] == -3
    row = next(field for field in result["source_field_ledger"] if field["field_id"] == "A_empty")
    assert row["status"] == "no_regions" and row["input_observations"] == 0
    assert result["counts"][0]["input_fields"] == 3 and result["counts"][0]["selected_fields"] == 2


def test_explicit_failed_pair_remains_in_counts_with_unknown_observations():
    report, config = comparison_fixture((('A', [3, 8, 2]), ('B', [4, 10, 5])))
    for fid in ("A0", "B0"):
        report["field_tables"].pop(fid)
        report["excluded_failed_fields"].append({"field_id": fid, "reason": "Failed image reviewed"})
        report["exclusions"].append({"field_id": fid, "region_id": None, "reason": "Failed image reviewed"})
    config["exclusions"] = copy.deepcopy(report["exclusions"])
    result = compare_regions(report, config, comparison_request(paired=True))
    assert len(result["excluded_failed_fields"]) == 2
    assert all(row["input_units"] == 3 and row["explicitly_excluded_units"] == 1 for row in result["counts"])
    assert result["comparisons"][0]["complete_pairs"] == 2
    assert len(result["plot_data"]) == 8


@pytest.mark.parametrize("recorded_reason", [None, "different reviewed reason"])
def test_failed_unit_cannot_be_dropped_without_the_same_saved_exclusion(recorded_reason):
    report, config = comparison_fixture((('A', [0, 2, 4]), ('B', [3, 5, 7])))
    report["field_tables"].pop("A0")
    report["excluded_failed_fields"].append({"field_id": "A0", "reason": "reviewed failure"})
    if recorded_reason is not None:
        report["exclusions"].append({"field_id": "A0", "region_id": None, "reason": recorded_reason})
    config["exclusions"] = copy.deepcopy(report["exclusions"])
    with pytest.raises(ValueError, match="descriptive_failure_exclusion_mismatch"):
        compare_regions(report, config, comparison_request())


def test_declared_family_failure_cannot_shrink_holm_denominator():
    report, config = comparison_fixture((('A', [0, 0]), ('B', [3, 3]), ('C', [6, 8])))
    request = comparison_request(conditions=["A", "B", "C"], comparison_family={"family_id": "primary", "kind": "control",
                                                                                 "control": "A", "contrasts": [["A", "C"], ["A", "B"]]})
    with pytest.raises(ValueError, match="comparison_not_estimable"):
        compare_regions(report, config, request)


def test_source_fingerprint_binds_metadata_masks_and_review_without_changing_input():
    report, config = comparison_fixture()
    original = source_fingerprint(report, config)
    for edit in (lambda r, c: c["field_snapshot"]["A0"]["metadata"].update(sample="different"),
                 lambda r, c: r["field_tables"]["A0"].update(mask_sha256="0" * 64),
                 lambda r, c: c["review_record"].update(confirmed_at=124.0)):
        r, c = copy.deepcopy(report), copy.deepcopy(config)
        edit(r, c)
        assert source_fingerprint(r, c) != original
    assert source_fingerprint(report, config) == original
