"""Experiment design 1.0.0: declared groups/runs/samples derive the existing comparison metadata."""
import pytest
from cytellect_analysis.experiment_design import (
    ExperimentDesign,
    comparison_defaults,
    field_metadata,
    readiness,
)
from cytellect_analysis.group_comparison_contracts import (
    ComparisonEstimates,
    CompartmentSummarySelectionV11,
    EstimateInterval,
    FieldSummarySelection,
    metric_scale,
)
from pydantic import ValidationError


def design(**overrides):
    value = {
        "layout": "pair",
        "groups": [{"id": "dmso", "label": "DMSO"}, {"id": "drug", "label": "Drug 1 uM"}],
        "control_group_id": "dmso",
        "runs": [{"id": "r1", "label": "2026-10-01", "performed_on": "2026-10-01", "acquired_on": "2026-10-02"},
                 {"id": "r2", "label": "2026-10-08", "performed_on": "2026-10-08"}],
        "independence_confirmed": True,
        "fields": {
            "f1": {"group_id": "dmso", "run_id": "r1"},
            "f2": {"group_id": "drug", "run_id": "r1", "acquired_on": "2026-10-03"},
            "f3": {"group_id": "dmso", "run_id": "r2", "sample": "CS1"},
            "f4": {"group_id": "dmso", "run_id": "r2", "sample": "CS2"},
            "f5": {"group_id": "drug", "run_id": "r2", "sample": "CS1"},
        },
    }
    value.update(overrides)
    return ExperimentDesign.model_validate(value)


def test_metadata_keeps_runs_samples_pairs_and_dates_distinct():
    derived = {key: value.model_dump() for key, value in field_metadata(design()).items()}
    assert derived["f1"] == {"condition": "DMSO", "experimental_unit": "2026-10-01 · DMSO", "sample": "2026-10-01 · DMSO",
                             "acquisition_date": "2026-10-02", "pair": "2026-10-01", "repeat_length": None}
    assert derived["f2"]["acquisition_date"] == "2026-10-03"  # the field's own imaging date wins
    assert derived["f3"]["sample"] == "2026-10-08 · CS1" and derived["f4"]["sample"] == "2026-10-08 · CS2"
    assert derived["f3"]["experimental_unit"] == derived["f4"]["experimental_unit"] == "2026-10-08 · DMSO"
    # The same coverslip name in another group is another sample of another unit.
    assert derived["f5"]["sample"] == "2026-10-08 · CS1" and derived["f5"]["experimental_unit"] == "2026-10-08 · Drug 1 uM"
    # Unknown dates stay unknown; nothing is invented.
    assert derived["f3"]["acquisition_date"] is None


def test_single_layout_has_no_pairs_or_control():
    single = design(layout="single", groups=[{"id": "wt", "label": "WT"}], control_group_id=None,
                    fields={"f1": {"group_id": "wt", "run_id": "r1"}})
    assert field_metadata(single)["f1"].pair is None
    with pytest.raises(ValueError, match="experiment_design_control_required"):
        comparison_defaults(single)
    with pytest.raises(ValidationError, match="experiment_design_control_requires_pair"):
        design(layout="single", groups=[{"id": "wt", "label": "WT"}])


def test_pair_defaults_put_treatment_first_so_effect_is_treatment_minus_control():
    assert comparison_defaults(design()) == {
        "conditions": ["DMSO", "Drug 1 uM"], "control": "DMSO", "treatment": "Drug 1 uM",
        "contrasts": [["Drug 1 uM", "DMSO"]], "design": "paired",
        "pairing_basis": "control and treatment from the same independent experimental run"}
    swapped = design(control_group_id="drug")
    assert comparison_defaults(swapped)["contrasts"] == [["DMSO", "Drug 1 uM"]]


@pytest.mark.parametrize("patch, code", [
    ({"groups": [{"id": "a", "label": "A"}]}, "experiment_design_group_count"),
    ({"groups": [{"id": "a", "label": "WT"}, {"id": "b", "label": "wt"}], "control_group_id": "a",
      "fields": {}}, "experiment_design_duplicate"),
    ({"runs": [{"id": "r1", "label": "x"}, {"id": "r1", "label": "y"}], "fields": {}}, "experiment_design_duplicate"),
    ({"control_group_id": "other"}, "experiment_design_unknown_group"),
    ({"fields": {"f1": {"group_id": "dmso", "run_id": "missing"}}}, "experiment_design_unknown_run"),
    ({"groups": [{"id": "a", "label": "A · B"}, {"id": "b", "label": "C"}], "control_group_id": "a", "fields": {}},
     "experiment_design_invalid_label"),
    ({"groups": [{"id": "a", "label": " A"}, {"id": "b", "label": "C"}], "control_group_id": "a", "fields": {}},
     "experiment_design_invalid_label"),
])
def test_invalid_designs_are_rejected(patch, code):
    with pytest.raises(ValidationError, match=code):
        design(**patch)


def test_labels_and_dates_are_bounded():
    with pytest.raises(ValidationError):
        design(runs=[{"id": "r1", "label": "x" * 25}], fields={})
    with pytest.raises(ValidationError):
        design(runs=[{"id": "r1", "label": "x", "performed_on": "10/01/2026"}], fields={})


def test_readiness_reports_missing_combinations_and_unconfirmed_independence():
    incomplete = design(independence_confirmed=False, fields={"f1": {"group_id": "dmso", "run_id": "r1"},
                                                               "f2": {"group_id": "drug", "run_id": "r1"},
                                                               "f3": {"group_id": "dmso", "run_id": "r2"}})
    assert readiness(incomplete, ["f1", "f2", "f3", "f9"]) == [
        {"code": "experiment_design_unassigned_fields", "field_ids": ["f9"]},
        {"code": "experiment_design_missing_combination", "run_id": "r2", "group_ids": ["drug"]},
        {"code": "experiment_design_independence_unconfirmed"},
    ]
    assert readiness(design(), ["f1", "f2", "f3", "f4", "f5"]) == []
    no_control = design(control_group_id=None)
    assert {"code": "experiment_design_control_required"} in readiness(no_control, ["f1", "f2", "f3", "f4", "f5"])


def test_derived_metadata_passes_the_existing_paired_ledger_rules():
    # Paired comparisons need one unit per condition and pair, and samples that never
    # map to two units within a condition (region_comparison._ledger rules).
    derived = field_metadata(design())
    units = {}
    for value in derived.values():
        units.setdefault((value.condition, value.pair), set()).add(value.experimental_unit)
    assert all(len(found) == 1 for found in units.values())
    samples = {}
    for value in derived.values():
        samples.setdefault((value.condition, value.sample), set()).add(value.experimental_unit)
    assert all(len(found) == 1 for found in samples.values())


def test_field_summary_selection_requires_positive_gate_only_for_positivity():
    gate = {"version": "1.1.0", "gate_protocol": "gfp-gate/3.0.0", "gfp_channel_id": "gfp", "method": "manual",
            "threshold": 100.0, "keep": "positive"}
    FieldSummarySelection.model_validate({"source": "field-summary", "region_set_id": "nuclei", "metric": "nucleus_count"})
    FieldSummarySelection.model_validate({"source": "field-summary", "region_set_id": "nuclei",
                                          "metric": "positive_fraction", "positivity": gate})
    with pytest.raises(ValidationError, match="field_summary_positivity_mismatch"):
        FieldSummarySelection.model_validate({"source": "field-summary", "region_set_id": "nuclei",
                                              "metric": "positive_fraction"})
    with pytest.raises(ValidationError, match="field_summary_positivity_keep_positive_required"):
        FieldSummarySelection.model_validate({"source": "field-summary", "region_set_id": "nuclei",
                                              "metric": "positive_count", "positivity": {**gate, "keep": "negative"}})


def test_compartment_summary_v11_adds_area_and_shape_without_channels():
    CompartmentSummarySelectionV11.model_validate({"source": "compartment-summary", "version": "1.1.0",
                                                  "region_set_id": "n", "metric": "nucleolar_eccentricity"})
    with pytest.raises(ValidationError, match="compartment_summary_channel_must_be_unset"):
        CompartmentSummarySelectionV11.model_validate({"source": "compartment-summary", "version": "1.1.0",
                                                      "region_set_id": "n", "metric": "nucleolar_area_px",
                                                      "channel_id": "ncl"})


def test_metric_scales_follow_requirement_s04():
    assert metric_scale("area_um2") == "ratio" and metric_scale("nucleus_count") == "ratio"
    assert metric_scale("positive_fraction") == "fraction" and metric_scale("nucleolar_area_fraction") == "fraction"
    assert metric_scale("log2_nucleoplasm_over_nucleolus") == "log2"
    assert metric_scale("mean_corrected") == "difference" and metric_scale("nucleolar_eccentricity") == "difference"
    with pytest.raises(ValueError, match="comparison_estimates_unknown_metric"):
        metric_scale("cell_count")


def test_estimate_intervals_are_complete_or_explained():
    EstimateInterval(estimate=1.0, ci_low=0.5, ci_high=1.5, basis="mean of per-run differences", unavailable_reason=None)
    EstimateInterval(estimate=None, ci_low=None, ci_high=None, basis=None, unavailable_reason="rank_test")
    with pytest.raises(ValidationError, match="comparison_estimates_interval_inconsistent"):
        EstimateInterval(estimate=None, ci_low=0.1, ci_high=None, basis=None, unavailable_reason="rank_test")
    with pytest.raises(ValidationError, match="comparison_estimates_interval_inconsistent"):
        EstimateInterval(estimate=1.0, ci_low=None, ci_high=None, basis=None, unavailable_reason=None)
    assert ComparisonEstimates.model_fields["direction"].default == "treatment_minus_control"
