"""Versioned area guidance preserves prior plans, fingerprints and confirmations."""
from __future__ import annotations

import copy

import numpy as np
import pytest
from cytellect_analysis.contracts import Recipe
from cytellect_analysis.measurement import measure
from cytellect_analysis.plan_adoption import (
    PlanResolution,
    adopt_plan,
    planning_methods,
    resolve_plan,
    validate_revision_plan,
)
from cytellect_analysis.planning import PlanInput, evaluate_plan, snapshot_plan, validate_plan_snapshot
from pydantic import ValidationError
from test_legacy import case as legacy_case
from test_plan_adoption import adopted, generic_fields, generic_recipe, legacy_fields, resolve_generic
from test_planning import plan

POLICY = {"version": "1.0.0", "mode": "area_only"}


def area_plan(version="2.1.0", **answers):
    return {**plan(measurement="area", **answers), "version": version}


def area_adoption(version="2.1.0"):
    return adopt_plan(PlanInput.model_validate(area_plan(version)), "regions-manual", 1700000000.0)


def area_resolution(saved, *, policy=POLICY, **changes):
    return {"version": "1.1.0", "plan_sha256": saved.sha256, "candidate_id": saved.selected_candidate_id,
            "metric": "area_px", "channel_id": None, "measurement": copy.deepcopy(policy), **changes}


@pytest.mark.parametrize("measurement,plan_sha,resolution_sha", [
    ("area", "576939adb455e4d40fccb32f99cbcf74d0413807fc3536266e96c2154a3afa46",
     "9b61d1b3e44d49c28e1ef846ff926d861d1ed2ae4868da3ec0a95f98a048b131"),
    ("mean", "d2c5c508bffc5ad6288cd5510145324ef66c411ae6396441ddd60a05e7e9a283",
     "b6e396eb8eed5ca5466c9486cf4aa3dee91a2418418d8822dc8860daf8019b13"),
    ("integrated", "19dee53bcdd6b08d7c5b185590bf35decbae3961711fdf4f643af9843b90c218",
     "e39b865006e46959a73d5547066020e89ffd951bd802f38bb1f3452c9ae80c40"),
])
def test_saved_v20_plan_and_v10_resolution_hashes_remain_exact(measurement, plan_sha, resolution_sha):
    # Hashes captured from the unchanged v2.0 implementation before this change.
    snapshot = snapshot_plan(plan(measurement=measurement))
    assert snapshot.sha256 == plan_sha
    assert validate_plan_snapshot(snapshot.model_dump(mode="json")) == snapshot
    assert all("measurement" not in item for item in snapshot.model_dump(mode="json")["decision"]["candidates"])
    saved = adopted(measurement=measurement)
    resolved = resolve_generic(saved, metric="area_px" if measurement == "area" else measurement,
                               channel_id=None if measurement == "area" else "signal")
    assert resolved["resolution_sha256"] == resolution_sha
    assert "measurement" not in resolved["resolution"] and "measurement" not in resolved["resolved"]
    assert "measurement_protocol" not in resolved["resolved"]


@pytest.mark.parametrize("definition,region,candidate", [
    ("manual", "custom", "regions-manual"), ("imported", "custom", "regions-imported"),
    ("nuclear-stain", "nucleus", "regions-nuclei"),
])
def test_v21_generic_area_suggests_shared_policy_without_background_tasks(definition, region, candidate):
    result = evaluate_plan(area_plan(definition=definition, region=region, signal="unknown", nuclear_stain="yes"))
    assert result.version == "2.1.0" and len(result.candidates) == 1
    chosen = result.candidates[0]
    assert chosen.id == candidate and chosen.measurement.model_dump(mode="json") == POLICY
    assert "background-rois" not in chosen.actual_review_required
    assert "background" not in {item.id for item in result.questions}
    assert "actual-adoption-area" in {item.id for item in result.decisions}
    assert {"native-input", "channel-mapping", "mask-quality", "calibration-for-physical-area"}.issubset(
        chosen.actual_review_required,
    )


def test_mixed_area_and_native_gfp_candidates_retain_only_required_background_task():
    result = evaluate_plan(area_plan(region="nucleus", definition="nuclear-stain", nuclear_stain="yes", signal="gfp"))
    generic, native = result.candidates
    assert generic.measurement is not None and "background-rois" not in generic.actual_review_required
    assert native.measurement is None and "background-rois" in native.actual_review_required
    assert "background-candidate" in {item.id for item in result.questions}
    assert "measurement" not in native.model_dump(mode="json")


@pytest.mark.parametrize("definition,signal,region,gating", [
    ("ncl-enrichment", "ncl", "nucleolus", "none"),
    ("nuclear-stain", "gfp", "nucleus", "negative-control"),
])
def test_v21_native_area_recipes_keep_background_requirements(definition, signal, region, gating):
    result = evaluate_plan(area_plan(definition=definition, signal=signal, region=region,
                                     nuclear_stain="yes", gating=gating))
    assert result.candidates and all(candidate.workflow == "nuclear" for candidate in result.candidates)
    assert all(candidate.measurement is None and "background-rois" in candidate.actual_review_required
               for candidate in result.candidates)
    assert "background" in {item.id for item in result.questions}


def test_v20_candidate_cannot_be_reinterpreted_by_adding_new_policy_even_null():
    snapshot = snapshot_plan(area_plan("2.0.0")).model_dump(mode="json")
    for policy in (POLICY, None):
        altered = copy.deepcopy(snapshot)
        altered["decision"]["candidates"][0]["measurement"] = policy
        with pytest.raises(ValidationError, match="planning_snapshot_mismatch"):
            validate_plan_snapshot(altered)


@pytest.mark.parametrize("version,supplied,policy", [
    ("1.0.0", True, None), ("1.0.0", True, POLICY), ("1.1.0", False, None),
])
def test_resolution_protocol_never_guesses_or_strips_policy_input(version, supplied, policy):
    value = {"version": version, "plan_sha256": "a" * 64, "candidate_id": "regions-manual", "metric": "area_px"}
    if supplied:
        value["measurement"] = policy
    with pytest.raises(ValidationError, match="planning_measurement_mismatch"):
        PlanResolution.model_validate(value)


def test_new_area_candidate_resolves_without_fluorescence_or_auto_confirmation():
    saved = area_adoption()
    result = resolve_plan(saved, area_resolution(saved), generic_recipe(), generic_fields(), "regions", measurement=POLICY)
    assert result["changes"] == []
    assert result["resolved"]["channel"] is None
    assert result["resolved"]["measurement"] == POLICY and result["resolved"]["measurement_protocol"] == "2.0.0"
    assert not {"backgrounds", "confirmed", "independent_units_confirmed"} & result["resolved"].keys()


def test_old_area_plan_requires_new_resolution_and_explicit_mode_change_acknowledgement():
    saved = area_adoption("2.0.0")
    old = {key: value for key, value in area_resolution(saved).items() if key not in {"version", "measurement"}}
    with pytest.raises(ValueError, match="planning_resolution_required"):
        resolve_plan(saved, old, generic_recipe(), generic_fields(), "regions", measurement=POLICY)
    with pytest.raises(ValueError, match="planning_changes_review_required"):
        resolve_plan(saved, area_resolution(saved), generic_recipe(), generic_fields(), "regions", measurement=POLICY)
    chosen = area_resolution(saved, changes_acknowledged=True)
    result = resolve_plan(saved, chosen, generic_recipe(), generic_fields(), "regions", measurement=POLICY)
    assert result["changes"] == ["measurement_mode"] and result["input"]["version"] == "2.0.0"


def test_new_area_plan_requires_explicit_null_and_ack_to_use_corrected_route():
    saved = area_adoption()
    chosen = area_resolution(saved, policy=None)
    with pytest.raises(ValueError, match="planning_changes_review_required"):
        resolve_plan(saved, chosen, generic_recipe(), generic_fields(), "regions")
    chosen["changes_acknowledged"] = True
    result = resolve_plan(saved, chosen, generic_recipe(), generic_fields(), "regions")
    assert result["changes"] == ["measurement_mode"]
    assert result["resolution"]["measurement"] is None and result["resolved"]["measurement"] is None
    assert result["resolved"]["measurement_protocol"] == "1.0.0"


@pytest.mark.parametrize("actual,selected", [(POLICY, None), (None, POLICY)])
def test_resolution_policy_must_match_actual_execution_even_with_ack(actual, selected):
    saved = area_adoption()
    with pytest.raises(ValueError, match="planning_measurement_mismatch"):
        resolve_plan(saved, area_resolution(saved, policy=selected, changes_acknowledged=True), generic_recipe(),
                     generic_fields(), "regions", measurement=actual)


@pytest.mark.parametrize("policy", [{"version": "2.0.0", "mode": "area_only"},
                                   {"version": "1.0.0", "mode": "area_and_raw"}])
def test_actual_unknown_policy_never_becomes_v1_defaults(policy):
    saved = area_adoption()
    with pytest.raises(ValueError, match="planning_measurement_policy_invalid"):
        resolve_plan(saved, area_resolution(saved), generic_recipe(), generic_fields(), "regions", measurement=policy)


def test_area_policy_cannot_enable_unmeasured_intensity_or_native_recipe():
    saved = area_adoption()
    with pytest.raises(ValueError, match="planning_metric_unavailable"):
        resolve_plan(saved, area_resolution(saved, metric="mean", channel_id="signal", changes_acknowledged=True),
                     generic_recipe(), generic_fields(), "regions", measurement=POLICY)
    native = adopted("legacy-ncl", region="nucleolus", definition="ncl-enrichment", signal="ncl", nuclear_stain="yes")
    with pytest.raises(ValueError, match="planning_workflow_mismatch"):
        resolve_plan(native, area_resolution(native), Recipe().model_dump(mode="json"), legacy_fields(), "nuclear",
                     measurement=POLICY)


def test_saved_revision_recomputes_actual_policy_and_rejects_changed_record():
    saved = area_adoption()
    chosen = area_resolution(saved)
    record = resolve_plan(saved, chosen, generic_recipe(), generic_fields(), "regions", measurement=POLICY)
    config = {"analysis_kind": "region-2d", "recipe": generic_recipe(), "plan_resolution": chosen,
              "measurement": POLICY, "field_snapshot": {"f": generic_fields()[0]}, "analysis_plan": record}
    assert validate_revision_plan(config) == record
    absent = {key: value for key, value in config.items() if key != "measurement"}
    with pytest.raises(ValueError, match="planning_measurement_mismatch"):
        validate_revision_plan(absent)
    changed = copy.deepcopy(config)
    changed["analysis_plan"]["resolved"]["measurement_protocol"] = "1.0.0"
    with pytest.raises(ValueError, match="planning_revision_record_mismatch"):
        validate_revision_plan(changed)


@pytest.mark.parametrize("signal,candidate,definition,region,metric,recipe_id", [
    ("gfp", "legacy-gfp-nuclear", "nuclear-stain", "nucleus", "gfp_mean_corrected", "gfp-nuclear-2d"),
    ("ncl", "legacy-ncl", "ncl-enrichment", "nucleolus", "ncl_nucleoli_mean_corrected", "ncl-native-2d"),
])
def test_nullable_native_choice_does_not_mislabel_actual_measurement_version(
        signal, candidate, definition, region, metric, recipe_id):
    saved = adopted(candidate, signal=signal, definition=definition, region=region, nuclear_stain="yes")
    chosen = area_resolution(saved, policy=None, metric=metric, channel_id=signal)
    recipe = Recipe(id=recipe_id)
    record = resolve_plan(saved, chosen, recipe.model_dump(mode="json"), legacy_fields(), "nuclear")
    assert record["resolved"]["measurement"] is None
    assert "measurement_protocol" not in record["resolved"]
    config = {"recipe": recipe.model_dump(mode="json"), "plan_resolution": chosen,
              "analysis_plan": record, "field_snapshot": {"field-a": legacy_fields()[0]}}
    methods = "\n".join(planning_methods(config))
    assert "Explicit measurement choice:" not in methods
    assert "area_and_background_corrected_intensity" not in methods
    # Independent fixed original pixel values: 20 background, 60 GFP throughout
    # the 1600-pixel nucleus, 120 NCL in the 100-pixel nucleolar mask.
    channels, nuclei = legacy_case()
    nucleoli = np.zeros_like(nuclei)
    if signal == "ncl":
        nucleoli[30:40, 30:40] = 1
    row = measure(channels, nuclei, nucleoli, nuclei == 0, recipe, {}, "field-a")[0][0]
    assert row["measurement_protocol_version"] == "1.1.1"
    assert row["recipe_id"] == recipe_id and row["recipe_version"] == "1.0.0"
    assert row[metric] == (40 if signal == "gfp" else 100)


def test_nullable_resolution_does_not_enable_or_relabel_rgb_compatibility_recipe():
    channels, nuclei = legacy_case()
    nucleoli = np.zeros_like(nuclei)
    nucleoli[30:40, 30:40] = 1
    recipe = Recipe(id="ncl-legacy-rgb")
    row = measure(channels, nuclei, nucleoli, None, recipe, {}, "field-a")[0][0]
    assert row["recipe_id"] == "ncl-legacy-rgb" and row["recipe_version"] == "1.0.0"
    assert row["legacy_protocol_version"] == "1.0.0" and row["measurement_protocol_version"] == "1.1.1"
    assert row["measurement_grid"] == "legacy-downsampled"
    saved = adopted("legacy-ncl", signal="ncl", definition="ncl-enrichment", region="nucleolus", nuclear_stain="yes")
    with pytest.raises(ValueError, match="planning_workflow_mismatch"):
        resolve_plan(saved, area_resolution(saved, policy=None, metric="ncl_nucleoli_mean", channel_id="ncl"),
                     recipe.model_dump(mode="json"), legacy_fields(), "nuclear")
