"""Manuscript prose follows saved science, not a new calculation or imagined design."""
import copy
import hashlib

import numpy as np
import pytest
from cytellect_analysis.descriptive import describe_legacy, describe_numeric, describe_regions
from cytellect_analysis.descriptive_contracts import PagedDescriptiveOutput
from cytellect_analysis.descriptive_figures import descriptive_methods
from cytellect_analysis.measurement import region_values
from cytellect_analysis.region_comparison import compare_regions
from cytellect_analysis.region_comparison_figures import region_comparison_methods
from cytellect_analysis.statistical_methods import CURRENT_METHODS_TEMPLATE, saved_methods_template
from pydantic import ValidationError
from test_descriptive import legacy_fixture, region_fixture, request
from test_region_comparison import comparison_fixture, comparison_request

CURRENT = CURRENT_METHODS_TEMPLATE


@pytest.mark.parametrize("compatibility", [False, True])
def test_negative_pixel_hand_reference_is_described_in_its_actual_recipe(compatibility):
    values = region_values(np.array([[2, 10]], np.uint8), np.ones((1, 2), bool), 11, legacy=compatibility)
    assert values["mean_corrected"] == (0 if compatibility else -5)
    report, snapshot = legacy_fixture((values["mean_corrected"],))
    report["recipe"]["id"] = "ncl-legacy-rgb" if compatibility else "gfp-nuclear-2d"
    result = describe_legacy(report, snapshot, request("legacy-cell", "gfp_mean_corrected"))
    before = copy.deepcopy(result)
    text = descriptive_methods(result, methods_template=CURRENT)
    assert result == before
    assert ("Corrected negative pixels were clipped to zero" in text) is compatibility
    assert ("Native negative corrected values remain signed" in text) is not compatibility
    assert ("For RGB inputs, the compatibility importer used max(R,G,B)." in text) is compatibility
    assert "The compatibility recipe converted RGB" not in text
    assert "No hypothesis test" in text and "Independent experimental n was not assessed" in text
    assert "NCL compartments" not in text
    assert "Statistical Methods template: cytellect-statistical-methods 1.0.0" in text


@pytest.mark.parametrize("metric", ["mean", "mean_corrected", "integrated_corrected", "area_px", "area_um2"])
def test_actual_generic_marker_units_and_selected_formula(metric):
    report, snapshot = region_fixture()
    result = describe_regions(report, snapshot, request(metric=metric))
    text = descriptive_methods(result, methods_template=CURRENT)
    assert "Manual regions" in text and "GFP" not in text and "NCL" not in text
    if metric.startswith("area"):
        assert "recorded X and Y pixel sizes" in text and "stain:" not in text
    else:
        assert "Measured channel: Actin; stain: phalloidin" in text
        if metric == "mean":
            assert "arithmetic mean of (I)" in text and "selected raw outcome does not subtract background" in text
            assert "negative corrected" not in text
        else:
            assert "I − b" in text and "median of the saved user-confirmed background ROI" in text
        if metric == "integrated_corrected":
            assert "sum of (I − b)" in text and "not concentration" in text


def test_compatibility_compartments_and_fraction_do_not_claim_biological_nucleoli():
    report, snapshot = legacy_fixture((0,))
    report["recipe"]["id"] = "ncl-legacy-rgb"
    report["cells"][0].update(ncl_nucleoli_mean_corrected=3, nucleolar_area_fraction=.2)
    intensity = describe_legacy(report, snapshot, request("legacy-cell", "ncl_nucleoli_mean_corrected"))
    fraction = describe_legacy(report, snapshot, request("legacy-cell", "nucleolar_area_fraction"))
    assert "high intensity does not establish biological nucleolar identity" in descriptive_methods(intensity, methods_template=CURRENT)
    assert "compatibility measurement grid" in descriptive_methods(fraction, methods_template=CURRENT)


def test_auxiliary_region_definition_is_not_reported_as_ncl_detection():
    report, snapshot = legacy_fixture((0,))
    report["recipe"] = {"id": "ncl-native-2d", "nucleolar_method": "dapi-low"}
    report["cells"][0]["ncl_nucleoli_mean_corrected"] = 3
    result = describe_legacy(report, snapshot, request("legacy-cell", "ncl_nucleoli_mean_corrected"))
    text = descriptive_methods(result, methods_template=CURRENT)
    assert "Where regions were defined using NCL" in text
    assert result["source_fields"][0]["recipe"]["nucleolar_method"] == "dapi-low"


def test_many_observations_keep_complete_ledger_without_embedding_it_in_methods():
    small_report, snapshot = legacy_fixture((1, 9))
    large_report, _ = legacy_fixture(tuple(range(20_000)))
    small = describe_legacy(small_report, snapshot, request("legacy-cell", "gfp_mean_corrected"))
    large = describe_legacy(large_report, snapshot, request("legacy-cell", "gfp_mean_corrected"))
    small_text = descriptive_methods(small, methods_template=CURRENT)
    large_text = descriptive_methods(large, methods_template=CURRENT)
    assert len(large_text) - len(small_text) < 30
    assert "Selected observations: 20000" in large_text and "Selection: {" not in large_text
    assert "selection.csv" in large_text and "figure-data.json" in large_text
    assert len(large["selection"]["records"]) == len(large["plot_data"]) == 20_000


def test_gfp_filter_missingness_and_failed_fields_remain_explained():
    report, snapshot = legacy_fixture((3, 4, None, -5, 0))
    report["cells"][0].update(excluded=True, exclusion_reason="edge", gfp_positive=False)
    report["cells"][1].update(gfp_positive=False, gfp_gate_exploratory=True, gfp_gate_method="manual", gfp_gate_threshold=5)
    report["cells"][3].update(gfp_gate_method="manual", gfp_gate_threshold=6, gfp_gate_maximum=12)
    report["excluded_failed_fields"] = [{"field_id": "f2", "reason": "recorded failure"}]
    snapshot["f2"] = copy.deepcopy(snapshot["f1"])
    result = describe_legacy(report, snapshot, request("legacy-cell", "gfp_mean_corrected"))
    text = descriptive_methods(result, methods_template=CURRENT)
    assert "1 were explicitly excluded, 1 were unselected" in text
    assert "1 otherwise selected outcomes were missing" in text
    assert "Explicitly excluded failed fields: 1; their observation counts remain unknown" in text
    assert "lower threshold varies by field" in text and "upper bound: 12" in text
    assert "is exploratory" in text


@pytest.mark.parametrize("paired", [False, True])
def test_only_actual_saved_test_and_independent_n_with_interval_direction(paired):
    report, config = comparison_fixture((('A', [3, 8, 2]), ('B', [4, 10, 5])))
    result = compare_regions(report, config, comparison_request(paired=paired))
    before = copy.deepcopy(result)
    text = region_comparison_methods(result, methods_template=CURRENT)
    assert result == before
    assert "n=3 independent experimental units" in text and "6 selected region observations" in text
    assert "n=6" not in text and "Student t with n−1" in text and "not simultaneous or multiplicity-adjusted" in text
    assert "Holm correction covered the complete declared family primary: A minus B" in text
    if paired:
        assert "Two-sided paired t-tests" in text and "3 complete pairs" in text and "Welch" not in text
        assert "mean within-pair difference" in text
    else:
        assert "two-sided Welch t-tests" in text and "paired t-test" not in text
        assert "Welch–Satterthwaite" in text
    corrupted = copy.deepcopy(result)
    corrupted["comparisons"][0]["method"] = "Welch t-test" if paired else "paired t-test"
    with pytest.raises(ValueError, match="source_invalid"):
        region_comparison_methods(corrupted, methods_template=CURRENT)


def test_numeric_table_does_not_invent_an_image_or_background():
    result = describe_numeric([{"field_id": "f1", "assay": "RNA", "unit": "ng", "value": -3}], request("numerical", "value"))
    text = descriptive_methods(result, methods_template=CURRENT)
    assert "Previously measured numerical values" in text
    assert "performed no image measurement or background correction" in text
    assert "negative corrected" not in text and "Region definition:" not in text


@pytest.mark.parametrize("metadata", [None, {}, {"id": "other", "version": "1.0.0"},
                                     {"id": CURRENT.id, "version": "2.0.0"}, {**CURRENT.model_dump(), "text": "override"}])
def test_unknown_explicit_document_template_is_not_historical(metadata):
    with pytest.raises((ValueError, ValidationError)):
        saved_methods_template({"figure": {"methods_template": metadata}})
    assert saved_methods_template({"figure": {}}) is None


@pytest.mark.parametrize("recipe", [{}, {"id": "unknown"}])
def test_unknown_source_recipe_never_becomes_native_prose(recipe):
    report, snapshot = legacy_fixture()
    report["recipe"] = recipe
    result = describe_legacy(report, snapshot, request("legacy-cell", "gfp_mean_corrected"))
    with pytest.raises(ValueError, match="source_invalid"):
        descriptive_methods(result, methods_template=CURRENT)


def test_old_default_methods_are_not_replaced_by_the_new_template():
    report, snapshot = legacy_fixture()
    result = describe_legacy(report, snapshot, request("legacy-cell", "gfp_mean_corrected"))
    text = descriptive_methods(result)
    assert "Selection: {" in text and "cytellect-statistical-methods" not in text
    # Pinned below against the unchanged baseline formatter and deterministic source fixture.
    assert hashlib.sha256(text.encode()).hexdigest() == "b1e837d3517f588f489ab291b51a8cd00022443af7ec0aaa1065364fca63b2ea"


def test_methods_schema_allows_absence_but_does_not_advertise_null_or_null_default():
    for mode in ("validation", "serialization"):
        schema = PagedDescriptiveOutput.model_json_schema(mode=mode)
        prop = schema["properties"]["methods_template"]
        assert prop["$ref"] == "#/$defs/StatisticalMethodsTemplate"
        assert set(prop) <= {"$ref", "title"}
        assert "methods_template" not in schema.get("required", [])
    assert PagedDescriptiveOutput.model_fields["methods_template"].default is None
