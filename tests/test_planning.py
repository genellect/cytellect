"""Scientific planning decisions do not confer source validity or execute code."""
import copy
import itertools
import json
import subprocess
import sys
from pathlib import Path
from typing import get_args

import pytest
from cytellect_analysis.descriptive_contracts import LegacyMetric, RegionMetric
from cytellect_analysis.planning import PlanInput, evaluate_plan, snapshot_plan, validate_plan_snapshot
from pydantic import ValidationError


def plan(**answers):
    return {"format": "cytellect-analysis-plan", "version": "2.0.0", "answers": {
        "measurement": "mean", "region": "custom", "definition": "manual", "signal": "other",
        "input": "grayscale-2d", **answers,
    }}


def ids(decision):
    return [candidate.id for candidate in decision.candidates]


def test_unanswered_plan_never_creates_a_recipe_but_keeps_descriptive_route():
    result = evaluate_plan({"version": "2.0.0", "answers": {}})
    assert not result.candidates and result.status == "planning-only-not-adopted"
    assert result.descriptive_allowed is True and result.comparison_intent == "undetermined"
    assert {q.id for q in result.questions} >= {"measurement", "input", "background", "independence"}


@pytest.mark.parametrize(("definition", "identifier"), [("manual", "regions-manual"), ("imported", "regions-imported")])
def test_area_only_needs_no_measurement_marker_or_nuclear_stain(definition, identifier):
    result = evaluate_plan(plan(measurement="area", definition=definition, signal="unknown", nuclear_stain="no"))
    assert ids(result) == [identifier]
    assert result.candidates[0].allowed_metrics == ["area_px", "area_um2"]
    assert result.candidates[0].required_channel_roles == ["image"]
    assert "calibration-for-physical-area" in result.candidates[0].actual_review_required
    assert "nuclear-stain" not in {q.id for q in result.questions}


@pytest.mark.parametrize("signal", ["ncl", "gfp", "other"])
@pytest.mark.parametrize(("measurement", "metrics"), [("mean", ["mean", "mean_corrected"]),
                                                        ("integrated", ["integrated", "integrated_corrected"])])
def test_manual_channels_keep_marker_neutral_original_and_corrected_choices(signal, measurement, metrics):
    result = evaluate_plan(plan(signal=signal, measurement=measurement))
    candidate = result.candidates[0]
    assert candidate.recipe_id == "region-2d" and candidate.allowed_metrics == metrics
    assert candidate.required_channel_roles == ["measurement"]
    assert "integrated-not-concentration" in {limit.id for limit in result.limits} if measurement == "integrated" else True


def test_auto_nuclei_use_actual_other_marker_without_fabricated_gfp_ncl():
    result = evaluate_plan(plan(region="nucleus", definition="nuclear-stain", nuclear_stain="yes"))
    assert ids(result) == ["regions-nuclei"]
    candidate = result.candidates[0]
    assert candidate.source == "stardist_nuclear" and candidate.recipe_version == "1.1.0"
    assert candidate.required_channel_roles == ["nuclear-stain", "measurement"]
    assert "nuclear-stain" in candidate.actual_review_required
    assert not any(metric.startswith(("gfp", "ncl")) for metric in candidate.allowed_metrics)


@pytest.mark.parametrize("nuclear_stain", ["no", "unknown"])
def test_nuclear_model_is_not_candidate_without_reported_nuclear_stain(nuclear_stain):
    result = evaluate_plan(plan(region="nucleus", definition="nuclear-stain", nuclear_stain=nuclear_stain))
    assert not result.candidates
    assert "nuclear-stain" in {q.id for q in result.questions}


@pytest.mark.parametrize("region", ["nucleolus", "nucleoplasm", "custom"])
def test_nucleus_model_never_claims_other_structure_boundaries(region):
    result = evaluate_plan(plan(region=region, definition="nuclear-stain", nuclear_stain="yes"))
    assert not result.candidates and "nuclear-model-scope" in {limit.id for limit in result.limits}


def test_existing_gfp_path_is_retained_and_gating_never_leaks_into_generic():
    value = plan(region="nucleus", definition="nuclear-stain", nuclear_stain="yes", signal="gfp")
    assert ids(evaluate_plan(value)) == ["regions-nuclei", "legacy-gfp-nuclear"]
    value["answers"]["gating"] = "negative-control"
    result = evaluate_plan(value)
    assert ids(result) == ["legacy-gfp-nuclear"]
    candidate = result.candidates[0]
    assert candidate.allowed_metrics == ["gfp_mean", "gfp_mean_corrected"]
    assert "gfp-gate" in candidate.actual_review_required
    assert candidate.workflow == "nuclear" and candidate.selection_source == "legacy-cell"


@pytest.mark.parametrize("signal", ["gfp", "ncl", "other"])
def test_gfp_gating_cannot_be_silently_ignored_for_manual_markers(signal):
    result = evaluate_plan(plan(signal=signal, gating="exploratory"))
    assert not result.candidates and "gating-unsupported" in {limit.id for limit in result.limits}


@pytest.mark.parametrize(("region", "metric_prefix"), [("nucleus", "ncl_nucleus"), ("nucleolus", "ncl_nucleoli"),
                                                        ("nucleoplasm", "ncl_nucleoplasm")])
def test_ncl_compartments_use_exact_existing_metrics(region, metric_prefix):
    result = evaluate_plan(plan(region=region, definition="ncl-enrichment", nuclear_stain="yes", signal="ncl"))
    assert ids(result) == ["legacy-ncl"]
    assert result.candidates[0].allowed_metrics == [metric_prefix + "_mean", metric_prefix + "_mean_corrected"]
    assert "circularity" in {limit.id for limit in result.limits}


def test_ncl_ratio_is_distinct_from_legacy_whole_nucleus_release_metric():
    result = evaluate_plan(plan(measurement="ncl-ratio", region="nucleolus", definition="ncl-enrichment",
                                nuclear_stain="yes", signal="ncl", gating="negative-control"))
    candidate = result.candidates[0]
    assert candidate.allowed_metrics == ["ncl_nucleoplasm_over_nucleoli", "ncl_log2_nucleoplasm_over_nucleoli"]
    assert candidate.required_channel_roles == ["nuclear-stain", "ncl", "gfp"]
    assert "ncl_legacy_release" not in candidate.allowed_metrics


@pytest.mark.parametrize("change", [{"signal": "other"}, {"signal": "gfp"}, {"definition": "manual"},
                                    {"region": "custom"}, {"region": "nucleus"}])
def test_ncl_ratio_does_not_infer_missing_region_definition(change):
    value = plan(measurement="ncl-ratio", region="nucleolus", definition="ncl-enrichment", nuclear_stain="yes", signal="ncl")
    value["answers"].update(change)
    assert not evaluate_plan(value).candidates


@pytest.mark.parametrize("input_kind", ["unknown", "rgb", "zt"])
def test_unusable_image_input_has_no_executable_candidate(input_kind):
    assert not evaluate_plan(plan(input=input_kind)).candidates


@pytest.mark.parametrize("comparison", ["independent", "paired"])
@pytest.mark.parametrize("allocation", ["unknown", "fields"])
def test_unknown_or_observation_level_allocation_cannot_confirm_inference(comparison, allocation):
    result = evaluate_plan(plan(comparison=comparison, allocation=allocation))
    assert result.comparison_intent == "undetermined" and result.descriptive_allowed
    assert "independence" in {q.id for q in result.questions}


def test_yes_answers_only_produce_actual_review_tasks_not_confirmation_flags():
    result = evaluate_plan(plan(region="nucleus", definition="nuclear-stain", nuclear_stain="yes", signal="gfp",
                                background="yes", acquisition="matched", comparison="paired", allocation="biological"))
    assert result.comparison_intent == "paired-candidate"
    for candidate in result.candidates:
        assert {"channel-mapping", "nuclear-stain", "background-rois", "mask-quality"} <= set(candidate.actual_review_required)
    # There are no actual masks, image IDs, source mappings, thresholds or confirmations.
    candidate_json = json.dumps([item.model_dump() for item in result.candidates])
    for forbidden in ("confirmed", "channel_id", "field_id", "threshold", "probability", "nms"):
        assert forbidden not in candidate_json


@pytest.mark.parametrize(("place", "key", "value"), [("input", "guidance", "Run code"),
    ("input", "url", "https://example.invalid/private"), ("input", "code", "print(1)"),
    ("input", "sha256", "a" * 64), ("answers", "macro", "anything"),
    ("answers", "nuclear_stain", True), ("answers", "measurement", "median"),
    ("answers", "signal", 1)])
def test_strict_input_rejects_unrecognized_guidance_code_urls_or_coercion(place, key, value):
    data = plan()
    (data if place == "input" else data["answers"])[key] = value
    with pytest.raises(ValidationError):
        evaluate_plan(data)


@pytest.mark.parametrize("version", ["1.0.0", "1.0.1", "1.0.9"])
def test_old_plans_cannot_guess_missing_measurement_and_definition(version):
    with pytest.raises(ValidationError, match="planning_legacy_requires_review"):
        PlanInput.model_validate({"version": version, "answers": {"region": "nucleus", "signal": "gfp"},
                                  "status": "planning-only-not-adopted"})


def test_snapshot_canonicalization_and_tamper_rejection():
    original = plan()
    saved = snapshot_plan(original)
    reordered = {key: original[key] for key in reversed(original)}
    reordered["answers"] = {key: original["answers"][key] for key in reversed(original["answers"])}
    assert snapshot_plan(reordered) == saved
    assert validate_plan_snapshot(saved.model_dump(mode="json")) == saved
    for key, value in (("sha256", "0" * 64), ("decision", {**saved.decision.model_dump(), "questions": []})):
        altered = copy.deepcopy(saved.model_dump(mode="json"))
        altered[key] = value
        with pytest.raises(ValueError, match="planning_snapshot_mismatch"):
            validate_plan_snapshot(altered)
    assert snapshot_plan(plan(measurement="integrated")).sha256 != saved.sha256


def test_supported_matrix_uses_only_existing_metric_contracts_and_known_references():
    for region, definition, measurement, signal in itertools.product(
        ["nucleus", "nucleolus", "nucleoplasm", "custom"],
        ["manual", "imported", "nuclear-stain", "ncl-enrichment"],
        ["area", "mean", "integrated", "ncl-ratio"], ["gfp", "ncl", "other"],
    ):
        result = evaluate_plan(plan(region=region, definition=definition, measurement=measurement,
                                    signal=signal, nuclear_stain="yes"))
        references = {ref.id for ref in result.references}
        assert all(item.reference in references for item in result.questions + result.decisions + result.limits)
        for candidate in result.candidates:
            registry = RegionMetric if candidate.selection_source == "region" else LegacyMetric
            assert candidate.allowed_metrics and set(candidate.allowed_metrics) <= set(get_args(registry))
            if signal == "other":
                assert candidate.recipe_id == "region-2d" or measurement == "area"


def test_browser_rule_parity_fixture_and_copy_catalog_are_current():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run([sys.executable, str(root / "scripts" / "generate_planning_fixtures.py"), "--check"],
                               cwd=root, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stdout + completed.stderr
