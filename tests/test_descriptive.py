"""Independent hand arithmetic and adversarial provenance for descriptive outputs."""
import copy
from typing import get_args

import numpy as np
import pytest
from cytellect_analysis.contracts import StatisticsRequest
from cytellect_analysis.descriptive import describe_legacy, describe_numeric, describe_regions
from cytellect_analysis.descriptive_contracts import DescriptiveRequest, LegacyMetric
from cytellect_analysis.regions import (
    BackgroundSpec,
    Calibration2D,
    ChannelSpec,
    RegionMeasurementSpec,
    RegionSetSpec,
    measure_regions,
)
from pydantic import ValidationError


def request(source="region", metric="mean_corrected", **changes):
    selection = {"source": source, "metric": metric}
    if source == "region":
        selection.update(region_set_id="regions", channel_id=None if metric.startswith("area_") else "actin")
    return DescriptiveRequest.model_validate({"mode": "descriptive", "selection": selection, **changes})


def region_fixture(*, second_channel=True, calibration=True, empty=False, field_id="f1"):
    actin = ChannelSpec(channel_id="actin", label="Actin", stain="phalloidin", identity_confirmed=True)
    channels = (actin, ChannelSpec(channel_id="dna", label="DNA", stain="Hoechst", identity_confirmed=True)) if second_channel else (actin,)
    config = RegionMeasurementSpec(
        field_id=field_id, analysis_revision_id="analysis_1",
        region_set=RegionSetSpec(region_set_id="regions", label="Manual regions", mask_revision_id="mask_1", source="manual"),
        channels=channels, backgrounds=tuple(BackgroundSpec(channel_id=c.channel_id, roi_revision_id="bg", confirmed=True) for c in channels),
        calibration=Calibration2D(pixel_size_x_um=.2, pixel_size_y_um=.5, confirmed=True) if calibration else None)
    image = np.array([[9, 11, 13], [100, 2, 10], [100, 6, 20]], dtype=np.uint8)
    labels = np.array([[0, 0, 0], [0, 7, 7], [0, 7, 19]], dtype=np.uint32)
    if empty:
        labels[:] = 0
    background = np.array([[True, True, True], [False, False, False], [False, False, False]])
    table = measure_regions({c.channel_id: image if c == actin else image * 2 for c in channels}, labels,
                            {c.channel_id: background for c in channels}, config)
    report = {"revision_id": "analysis_1", "field_tables": {field_id: table.model_dump(mode="json")},
              "field_failures": [], "excluded_failed_fields": [], "exclusions": []}
    snapshots = {field_id: {"metadata": {"condition": None},
                            "image_info": {"channels": [c.model_dump(mode="json") for c in channels],
                                           "shape": list(image.shape),
                                           "calibration": config.calibration.model_dump(mode="json") if config.calibration else None}}}
    return report, snapshots


def legacy_fixture(values=(1, 9)):
    metadata = {key: None for key in ("condition", "experimental_unit", "sample", "acquisition_date", "pair")}
    rows = [{"field_id": "f1", "nucleus_id": index + 1, **metadata, "gfp_mean_corrected": value,
             "excluded": False, "gfp_positive": True, "exclusion_reason": ""} for index, value in enumerate(values)]
    report = {"cells": rows, "engine_provenance": {"f1": {}}, "field_failures": [], "recipe": {"id": "gfp-nuclear-2d"}}
    return report, {"f1": {"metadata": metadata}}


def test_request_no_hidden_inference_and_metric_registry_matches():
    assert set(get_args(LegacyMetric)) == set(get_args(StatisticsRequest.model_fields["metric"].annotation)) - {"value"}
    for extra in ({"baseline": "A"}, {"independent_units_confirmed": True}, {"comparisons": [["A", "B"]]},
                  {"plot": {"kind": "paired"}}, {"plot": {"kind": "scatter"}}, {"group_by": "condition"}):
        with pytest.raises(ValidationError):
            request(**extra)
    with pytest.raises(ValidationError):
        DescriptiveRequest.model_validate({"selection": {"source": "numerical", "metric": "value"}})


def test_signed_measurements_from_one_field_without_fake_replicates():
    report, snapshots = region_fixture()
    result = describe_regions(report, snapshots, request())
    # Region pixels 2,10,6 => mean 6 minus background median 11 = -5; region19=20-11=9.
    assert [row["value"] for row in result["plot_data"]] == [-5, 9]
    assert result["field_summary"][0]["median"] == 2
    assert result["field_summary"][0]["q1"] == -1.5
    assert result["field_summary"][0]["q3"] == 5.5
    assert result["counts"] == {"observations": 2, "input_fields": 1, "selected_fields": 1,
                                "excluded_failed_fields": 0, "experimental_units": None}
    assert all(row["experimental_unit"] is None for row in result["plot_data"])
    assert not {"comparisons", "means", "model", "unit_summary", "p_value", "ci_low"} & result.keys()
    assert result["source_fields"][0]["channel_provenance"][0]["channel"]["stain"] == "phalloidin"


def test_area_counts_regions_once_and_anisotropic_calibration():
    report, snapshots = region_fixture()
    assert len(report["field_tables"]["f1"]["rows"]) == 4
    px = describe_regions(report, snapshots, request(metric="area_px"))
    um = describe_regions(report, snapshots, request(metric="area_um2"))
    assert [row["value"] for row in px["plot_data"]] == [3, 1]
    assert [row["value"] for row in um["plot_data"]] == pytest.approx([.3, .1])
    assert px["counts"]["observations"] == um["counts"]["observations"] == 2
    assert all(row["channel_id"] is None for row in px["plot_data"])


def test_known_quartiles_singleton_and_signed_zero():
    for values, expected in (((1, 9), (5, 3, 7)), ((4,), (4, 4, 4)), ((-5, 0, 4), (0, -2.5, 2))):
        report, snapshots = legacy_fixture(values)
        summary = describe_legacy(report, snapshots, request("legacy-cell", "gfp_mean_corrected"))["field_summary"][0]
        assert (summary["median"], summary["q1"], summary["q3"]) == expected


def test_legacy_selection_is_partitioned_preserved_and_missing_reason_retained():
    report, snapshots = legacy_fixture((3, 4, None, -5, 0))
    report["cells"][0].update(excluded=True, exclusion_reason="reviewed edge", gfp_positive=False)
    report["cells"][1].update(gfp_positive=False, gfp_gate_exploratory=True, gfp_gate_method="manual", gfp_gate_threshold=5)
    result = describe_legacy(report, snapshots, request("legacy-cell", "gfp_mean_corrected"))
    assert [row["value"] for row in result["plot_data"]] == [-5, 0]
    assert {key: result["selection"][key] for key in ("input_rows", "excluded", "gate_unselected", "missing_metric_selected", "selected_rows")} == {
        "input_rows": 5, "excluded": 1, "gate_unselected": 1, "missing_metric_selected": 1, "selected_rows": 2}
    assert result["selection"]["records"][0]["exclusion_reason"] == "reviewed edge"
    assert result["selection"]["records"][1]["gfp_gate_threshold"] == 5
    assert len(result["missingness"]) == 1
    assert "data_derived_or_manual_gfp_selection_requires_predeclared_or_independent_validation" in result["warnings"]


def test_unbalanced_fields_are_not_pooled_as_independent_unit_means():
    report, snapshots = legacy_fixture((0, 0, 0))
    report["cells"].append({**report["cells"][0], "field_id": "f2", "gfp_mean_corrected": 10})
    report["engine_provenance"]["f2"] = {}
    snapshots["f2"] = copy.deepcopy(snapshots["f1"])
    result = describe_legacy(report, snapshots, request("legacy-cell", "gfp_mean_corrected"))
    assert [row["median"] for row in result["field_summary"]] == [0, 10]
    assert "means" not in result and len(result["plot_data"]) == 4


@pytest.mark.parametrize(("mutation", "error"), [
    (lambda r, s: r["field_failures"].append({"field_id": "f2"}), "unresolved_field"),
    (lambda r, s: s.update(f2=copy.deepcopy(s["f1"])), "coverage_mismatch"),
    (lambda r, s: r["field_tables"]["f1"]["rows"].append(copy.deepcopy(r["field_tables"]["f1"]["rows"][0])), "duplicate_observation"),
    (lambda r, s: r["field_tables"]["f1"]["rows"][1].update(area_px=999), "area_channel_mismatch"),
    (lambda r, s: r["field_tables"]["f1"]["rows"][0].update(mask_revision_id="stale"), "region_identity_mismatch"),
    (lambda r, s: s["f1"]["image_info"]["channels"][0].update(stain="GFP"), "channel_identity_mismatch"),
    (lambda r, s: r["field_tables"]["f1"]["rows"].pop(), "channel_coverage_mismatch"),
    (lambda r, s: r["field_tables"]["f1"].update(status="no_regions"), "region_status_mismatch"),
    (lambda r, s: s["f1"]["image_info"].update(shape=[2, 3]), "shape_mismatch"),
    (lambda r, s: s["f1"]["image_info"].update(calibration=None), "calibration_mismatch"),
    (lambda r, s: r["exclusions"].append({"field_id": "f1", "region_id": 999, "reason": "unknown"}), "unknown_exclusion"),
])
def test_ambiguous_or_corrupted_sources_fail_closed(mutation, error):
    report, snapshots = region_fixture()
    mutation(report, snapshots)
    with pytest.raises(ValueError, match=error):
        describe_regions(report, snapshots, request())


def test_missing_calibration_not_zero_and_no_regions_not_failure():
    report, snapshots = region_fixture(calibration=False)
    with pytest.raises(ValueError, match="no_valid_selected_measurements"):
        describe_regions(report, snapshots, request(metric="area_um2"))
    other, other_snapshot = region_fixture(empty=True, field_id="f2")
    report["field_tables"].update(other["field_tables"])
    snapshots.update(other_snapshot)
    result = describe_regions(report, snapshots, request())
    assert result["field_summary"][1]["status"] == "no_regions"
    assert result["counts"]["input_fields"] == 2 and result["counts"]["selected_fields"] == 1


def test_explicit_failed_field_remains_counted_and_region_exclusion_is_not_channel_selection():
    report, snapshots = region_fixture()
    snapshots["f2"] = copy.deepcopy(snapshots["f1"])
    report["excluded_failed_fields"].append({"field_id": "f2", "reason": "reviewed failure"})
    report["exclusions"].append({"field_id": "f2", "region_id": None, "reason": "reviewed failure"})
    report["exclusions"].append({"field_id": "f1", "region_id": 7, "reason": "edge review"})
    result = describe_regions(report, snapshots, request())
    assert [row["value"] for row in result["plot_data"]] == [9]
    assert result["selection"]["excluded"] == 1
    assert result["counts"]["excluded_failed_fields"] == 1
    assert result["counts"]["input_fields"] == 2
    assert result["excluded_failed_fields"][0]["field_id"] == "f2"


@pytest.mark.parametrize("recorded_reason", [None, "different reviewed reason"])
def test_failed_region_field_requires_the_same_saved_whole_field_exclusion(recorded_reason):
    report, snapshots = region_fixture()
    snapshots["f2"] = copy.deepcopy(snapshots["f1"])
    report["excluded_failed_fields"].append({"field_id": "f2", "reason": "reviewed failure"})
    if recorded_reason is not None:
        report["exclusions"].append({"field_id": "f2", "region_id": None, "reason": recorded_reason})
    with pytest.raises(ValueError, match="descriptive_failure_exclusion_mismatch"):
        describe_regions(report, snapshots, request())


def test_legacy_failure_recorded_after_engine_initialization_is_explicit_not_missing():
    report, snapshots = legacy_fixture()
    report["engine_provenance"]["f2"] = {"engine": "started_before_failure"}
    snapshots["f2"] = copy.deepcopy(snapshots["f1"])
    report["excluded_failed_fields"] = [{"field_id": "f2", "reason": "acknowledged processing failure"}]
    result = describe_legacy(report, snapshots, request("legacy-cell", "gfp_mean_corrected"))
    assert result["counts"]["input_fields"] == 2
    assert result["counts"]["excluded_failed_fields"] == 1
    assert result["counts"]["selected_fields"] == 1


def test_partial_calibration_missingness_preserves_explicit_reason():
    report, snapshots = region_fixture(calibration=True)
    other, other_snapshot = region_fixture(calibration=False, field_id="f2")
    report["field_tables"].update(other["field_tables"])
    snapshots.update(other_snapshot)
    result = describe_regions(report, snapshots, request(metric="area_um2"))
    assert result["selection"]["missing_metric_selected"] == 2
    assert result["field_summary"][1]["selected_rows"] == 0
    assert {row["reason"] for row in result["missingness"]} == {"calibration_unknown"}


def test_metadata_missingness_is_not_a_synthetic_condition():
    report, snapshots = region_fixture()
    other, other_snapshot = region_fixture(field_id="f2")
    other_snapshot["f2"]["metadata"]["condition"] = "条件未設定"
    report["field_tables"].update(other["field_tables"])
    snapshots.update(other_snapshot)
    result = describe_regions(report, snapshots, request())
    assert [row["condition"] for row in result["field_summary"]] == [None, "条件未設定"]
    assert result["counts"]["observations"] == 4  # Same region IDs in separate fields remain distinct.


def test_self_consistent_table_calibration_forgery_cannot_override_snapshot():
    report, snapshots = region_fixture()
    table = report["field_tables"]["f1"]
    table["calibration"]["pixel_size_x_um"] = .4
    for row in table["rows"]:
        row["area_um2"] = row["area_px"] * (.4 * .5)
    with pytest.raises(ValueError, match="calibration_mismatch"):
        describe_regions(report, snapshots, request(metric="area_um2"))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "3"])
def test_invalid_values_are_not_silently_coerced_or_dropped(value):
    report, snapshots = legacy_fixture((1, value))
    with pytest.raises(ValueError, match="descriptive_invalid_value"):
        describe_legacy(report, snapshots, request("legacy-cell", "gfp_mean_corrected"))


def test_legacy_metadata_failure_duplicate_and_source_mismatch():
    report, snapshots = legacy_fixture()
    report["cells"][0]["condition"] = "invented"
    with pytest.raises(ValueError, match="inconsistent_field_metadata"):
        describe_legacy(report, snapshots, request("legacy-cell", "gfp_mean_corrected"))
    report["cells"][0]["condition"] = None
    report["cells"][0]["nucleolar_status"] = "processing_failed"
    with pytest.raises(ValueError, match="nucleolar_processing_failed"):
        describe_legacy(report, snapshots, request("legacy-cell", "gfp_mean_corrected"))
    with pytest.raises(ValueError, match="descriptive_source_mismatch"):
        describe_legacy(report, snapshots, request())


def test_numeric_table_descriptions_do_not_create_independent_replication():
    rows = [{"field_id": "well1", "value": value, "unit": "ng", "assay": "RNA", "experimental_unit": None} for value in (1, 9)]
    result = describe_numeric(rows, request("numerical", "value"))
    assert result["field_summary"][0]["median"] == 5
    assert result["unit"] == "ng" and result["counts"]["experimental_units"] is None
    assert result["plot_data"][0]["source_row"] == 2
    with pytest.raises(ValueError, match="numeric_field_required"):
        describe_numeric([{**rows[0], "field_id": None}], request("numerical", "value"))

def test_native_and_display_rgb_intensities_cannot_be_pooled_but_areas_can():
    report, snapshots = region_fixture()
    other, other_snapshots = region_fixture(field_id="f2")
    other_snapshots["f2"]["image_info"]["input_mode"] = "display-rgb"
    report["field_tables"].update(other["field_tables"])
    snapshots.update(other_snapshots)
    with pytest.raises(ValueError, match="descriptive_channel_identity_mismatch"):
        describe_regions(report, snapshots, request(metric="mean"))
    assert describe_regions(report, snapshots, request(metric="area_px"))["counts"]["input_fields"] == 2
