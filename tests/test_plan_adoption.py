"""Planning intention never replaces actual source identity or review evidence."""
import copy
import hashlib
import json

import pytest
from cytellect_analysis.contracts import Recipe
from cytellect_analysis.plan_adoption import (
    PlanResolution,
    adopt_plan,
    planning_methods,
    resolve_plan,
    validate_adopted_plan,
    validate_revision_plan,
)
from cytellect_analysis.planning import PlanInput
from pydantic import ValidationError


def adopted(candidate="regions-manual", **answers):
    base = {"measurement": "mean", "region": "custom", "definition": "manual",
            "signal": "other", "input": "grayscale-2d", **answers}
    return adopt_plan(PlanInput(version="2.0.0", answers=base), candidate, 1700000000.0)


def generic_fields():
    return [{"id": "field-a", "metadata": {"experimental_unit": None, "sample": None},
             "image_info": {"channels": [{"channel_id": "signal", "label": "Actual actin signal",
                                          "stain": "phalloidin", "identity_confirmed": True,
                                          "acquisition_saturation_value": None,
                                          "acquisition_saturation_confirmed": False}],
                            "calibration": {"pixel_size_x_um": 0.2, "pixel_size_y_um": 0.5,
                                            "confirmed": True}}}]


def generic_recipe(**updates):
    return {"id": "region-2d", "version": "1.0.0", "source": "manual",
            "region_set_id": "objects", "label": "Manually reviewed regions",
            "defining_channel_id": None, **updates}


def legacy_fields():
    return [{"id": "field-a", "metadata": {"pixel_size_um": 0.2},
             "image_info": {"channel_roles": ["dapi", "ncl", "gfp"]}}]


def resolution(saved, metric="mean", channel_id="signal", **updates):
    return {"plan_sha256": saved.sha256, "candidate_id": saved.selected_candidate_id,
            "metric": metric, "channel_id": channel_id, **updates}


def resolve_generic(saved=None, *, metric="mean", channel_id="signal", fields=None, recipe=None, **updates):
    saved = saved or adopted()
    return resolve_plan(saved, resolution(saved, metric, channel_id, **updates),
                        recipe or generic_recipe(), fields if fields is not None else generic_fields(), "regions")


def resolve_legacy(saved, metric, role, *, fields=None, recipe=None, **updates):
    return resolve_plan(saved, resolution(saved, metric, role, **updates),
                        recipe or Recipe().model_dump(mode="json"),
                        fields if fields is not None else legacy_fields(), "nuclear")


@pytest.mark.parametrize("measurement,metrics", [("mean", ("mean", "mean_corrected")),
                                                 ("integrated", ("integrated", "integrated_corrected"))])
def test_actual_generic_channel_and_raw_corrected_metric_remain_explicit(measurement, metrics):
    saved = adopted(measurement=measurement)
    records = [resolve_generic(saved, metric=metric) for metric in metrics]
    for record, metric in zip(records, metrics, strict=True):
        assert record["resolved"]["metric"] == metric
        assert record["resolved"]["channel"] == generic_fields()[0]["image_info"]["channels"][0]
        assert record["resolved"]["channel"]["stain"] == "phalloidin"
        assert record["changes"] == []
        assert "gfp" not in json.dumps(record["resolved"]) and "ncl" not in json.dumps(record["resolved"])
    assert records[0]["resolution_sha256"] != records[1]["resolution_sha256"]


@pytest.mark.parametrize("metric", ["area_px", "area_um2"])
def test_area_binds_region_once_without_a_fabricated_measurement_channel(metric):
    record = resolve_generic(adopted(measurement="area", signal="unknown"), metric=metric, channel_id=None)
    assert record["resolved"]["channel"] is None
    assert record["resolved"]["region_set_id"] == "objects"
    assert record["resolved"]["metric"] == metric


def test_pixel_area_is_possible_without_physical_calibration():
    fields = generic_fields()
    fields[0]["image_info"]["calibration"] = None
    assert resolve_generic(adopted(measurement="area"), metric="area_px", channel_id=None,
                           fields=fields)["resolved"]["metric"] == "area_px"


@pytest.mark.parametrize("calibration", [None, {},
    {"pixel_size_x_um": 0.2, "pixel_size_y_um": 0.5, "confirmed": False},
    {"pixel_size_x_um": -0.2, "pixel_size_y_um": 0.5, "confirmed": True},
    {"pixel_size_x_um": float("nan"), "pixel_size_y_um": 0.5, "confirmed": True},
    {"pixel_size_x_um": 0.2, "pixel_size_y_um": 0.5, "confirmed": 1}])
def test_planning_area_answer_cannot_supply_invalid_actual_calibration(calibration):
    fields = generic_fields()
    fields[0]["image_info"]["calibration"] = calibration
    with pytest.raises((ValueError, ValidationError), match="planning_calibration_required"):
        resolve_generic(adopted(measurement="area"), metric="area_um2", channel_id=None, fields=fields)


@pytest.mark.parametrize("channel_id,metric", [(None, "mean"), ("missing", "mean"), ("signal", "area_px")])
def test_channel_selection_matches_exact_intensity_or_area_contract(channel_id, metric):
    with pytest.raises(ValueError, match="planning_channel_unavailable"):
        resolve_generic(metric=metric, channel_id=channel_id, changes_acknowledged=True)


@pytest.mark.parametrize("confirmation", [False, 1, "true", None])
def test_planning_yes_cannot_confirm_actual_channel_identity(confirmation):
    fields = generic_fields()
    fields[0]["image_info"]["channels"][0]["identity_confirmed"] = confirmation
    with pytest.raises((ValueError, ValidationError), match="planning_channel_unavailable"):
        resolve_generic(adopted(background="yes", acquisition="matched"), fields=fields)


def test_same_internal_channel_id_with_different_actual_stain_is_not_pooled():
    fields = generic_fields()
    second = copy.deepcopy(fields[0])
    second["id"] = "field-b"
    second["image_info"]["channels"][0]["stain"] = "tubulin antibody"
    with pytest.raises(ValueError, match="planning_channel_unavailable"):
        resolve_generic(fields=[*fields, second])


def test_missing_selected_channel_in_any_field_is_not_skipped():
    fields = generic_fields() + generic_fields()
    fields[1]["image_info"]["channels"] = []
    with pytest.raises(ValueError, match="planning_channel_unavailable"):
        resolve_generic(fields=fields)


@pytest.mark.parametrize("metric,region", [("ncl_nucleus_mean_corrected", "nucleus"),
    ("ncl_nucleoli_mean", "nucleolus"), ("ncl_nucleoplasm_mean", "nucleoplasm")])
def test_ncl_actual_compartment_is_the_exact_saved_metric(metric, region):
    saved = adopted("legacy-ncl", region=region, definition="ncl-enrichment", signal="ncl", nuclear_stain="yes")
    record = resolve_legacy(saved, metric, "ncl")
    assert record["resolved"]["metric"] == metric and record["changes"] == []
    assert record["resolved"]["channel"]["channel_id"] == "ncl"


@pytest.mark.parametrize("metric", ["ncl_nucleoplasm_over_nucleoli", "ncl_log2_nucleoplasm_over_nucleoli"])
def test_native_ncl_ratio_never_becomes_legacy_release_metric(metric):
    saved = adopted("legacy-ncl", measurement="ncl-ratio", region="nucleolus",
                    definition="ncl-enrichment", signal="ncl", nuclear_stain="yes")
    record = resolve_legacy(saved, metric, "ncl")
    assert record["resolved"]["metric"] == metric and record["changes"] == []
    with pytest.raises(ValueError, match="planning_metric_unavailable"):
        resolve_legacy(saved, "ncl_legacy_release", "ncl", changes_acknowledged=True)


def test_gfp_recipe_preserves_gfp_and_rejects_ncl_even_with_acknowledgement():
    saved = adopted("legacy-gfp-nuclear", region="nucleus", definition="nuclear-stain",
                    nuclear_stain="yes", signal="gfp")
    recipe = Recipe(id="gfp-nuclear-2d").model_dump(mode="json")
    assert resolve_legacy(saved, "gfp_mean_corrected", "gfp", recipe=recipe)["changes"] == []
    with pytest.raises(ValueError, match="planning_metric_unavailable"):
        resolve_legacy(saved, "ncl_nucleus_mean", "ncl", recipe=recipe, changes_acknowledged=True)


@pytest.mark.parametrize("roles", [None, [], ["dapi", "gfp"]])
def test_missing_explicit_ncl_acquisition_role_is_not_filled_from_the_plan(roles):
    saved = adopted("legacy-ncl", region="nucleus", definition="ncl-enrichment", signal="ncl", nuclear_stain="yes")
    fields = legacy_fields()
    if roles is None:
        fields[0]["image_info"].pop("channel_roles")
    else:
        fields[0]["image_info"]["channel_roles"] = roles
    with pytest.raises(ValueError, match="planning_channel_unavailable"):
        resolve_legacy(saved, "ncl_nucleus_mean", "ncl", fields=fields)


@pytest.mark.parametrize("pixel_size", [None, 0, -0.2, 1e-300, 1e300, float("nan"), float("inf"), True, "0.2"])
def test_legacy_physical_area_requires_actual_positive_finite_numeric_calibration(pixel_size):
    saved = adopted("legacy-ncl", measurement="area", region="nucleus", definition="ncl-enrichment",
                    signal="ncl", nuclear_stain="yes")
    fields = legacy_fields()
    fields[0]["metadata"]["pixel_size_um"] = pixel_size
    with pytest.raises(ValueError, match="planning_calibration_required"):
        resolve_legacy(saved, "nucleus_area_um2", None, fields=fields)


def test_metric_and_region_method_changes_require_explicit_acknowledgement():
    saved = adopted()
    recipe = generic_recipe(source="imported")
    with pytest.raises(ValueError, match="planning_changes_review_required"):
        resolve_generic(saved, metric="integrated_corrected", recipe=recipe)
    record = resolve_generic(saved, metric="integrated_corrected", recipe=recipe, changes_acknowledged=True)
    assert record["changes"] == ["region_source", "measurement"]
    assert record["resolved"]["metric"] == "integrated_corrected"
    assert record["resolved"]["region_source"] == "imported"


@pytest.mark.parametrize("invalid", [0, 1, "true", "false", None])
def test_change_acknowledgement_is_a_boolean_not_a_truthy_input(invalid):
    saved = adopted()
    with pytest.raises(ValidationError):
        PlanResolution.model_validate(resolution(saved, changes_acknowledged=invalid))


def test_ncl_definition_and_gfp_selection_changes_remain_visible():
    saved = adopted("legacy-ncl", region="nucleus", definition="ncl-enrichment", signal="ncl", nuclear_stain="yes")
    recipe = Recipe(nucleolar_method="dapi-low", gfp_maximum=120).model_dump(mode="json")
    with pytest.raises(ValueError, match="planning_changes_review_required"):
        resolve_legacy(saved, "ncl_nucleus_mean", "ncl", recipe=recipe)
    assert resolve_legacy(saved, "ncl_nucleus_mean", "ncl", recipe=recipe,
                          changes_acknowledged=True)["changes"] == ["region_definition", "gfp_selection"]


@pytest.mark.parametrize("gate", ["manual", "otsu-batch"])
def test_exploratory_gate_resolves_only_to_explicit_existing_exploratory_method(gate):
    saved = adopted("legacy-gfp-nuclear", region="nucleus", definition="nuclear-stain",
                    nuclear_stain="yes", signal="gfp", gating="exploratory")
    recipe = Recipe(id="gfp-nuclear-2d", gfp_gate=gate, gfp_threshold=2 if gate == "manual" else None).model_dump(mode="json")
    record = resolve_legacy(saved, "gfp_mean", "gfp", recipe=recipe)
    assert record["changes"] == []


def test_no_plan_is_optional_but_a_resolution_cannot_forge_one():
    assert resolve_plan(None, None, {}, [], "regions") is None
    with pytest.raises(ValueError, match="planning_resolution_without_plan"):
        resolve_plan(None, resolution(adopted()), {}, [], "regions")
    with pytest.raises(ValueError, match="planning_resolution_required"):
        resolve_plan(adopted(), None, generic_recipe(), generic_fields(), "regions")


def test_workflow_and_missing_inputs_cannot_be_overridden_by_acknowledgement():
    saved = adopted()
    with pytest.raises(ValueError, match="planning_workflow_mismatch"):
        resolve_plan(saved, resolution(saved, changes_acknowledged=True), Recipe().model_dump(), legacy_fields(), "nuclear")
    with pytest.raises(ValueError, match="planning_inputs_required"):
        resolve_generic(saved, fields=[])
    with pytest.raises(ValueError, match="planning_recipe_invalid"):
        resolve_generic(saved, recipe={"id": "ncl-native-2d"}, changes_acknowledged=True)


@pytest.mark.parametrize("metric", ["unknown", "ncl_nucleus_mean", "eval_code"])
def test_acknowledgement_does_not_make_an_unknown_or_other_workflow_metric_valid(metric):
    with pytest.raises(ValueError, match="planning_metric_unavailable"):
        resolve_generic(metric=metric, changes_acknowledged=True)


@pytest.mark.parametrize("key,value", [("plan_sha256", "0" * 64), ("candidate_id", "regions-imported")])
def test_resolution_must_match_the_exact_adopted_plan_and_candidate(key, value):
    saved = adopted()
    proposed = resolution(saved)
    proposed[key] = value
    with pytest.raises(ValueError, match="planning_adoption_mismatch"):
        resolve_plan(saved, proposed, generic_recipe(), generic_fields(), "regions")


@pytest.mark.parametrize("tamper", ["hash", "guidance", "candidate", "answers"])
def test_saved_plan_cannot_replace_server_decisions_or_approved_candidate(tamper):
    saved = adopted().model_dump(mode="json")
    if tamper == "hash":
        saved["sha256"] = "0" * 64
    elif tamper == "guidance":
        saved["decision"]["questions"][0]["detail"] = "The acquisition is automatically scientifically valid."
    elif tamper == "candidate":
        saved["selected_candidate_id"] = "legacy-ncl"
    else:
        saved["input"]["answers"]["measurement"] = "integrated"
    with pytest.raises(ValueError, match="planning_(snapshot_mismatch|candidate_unavailable)"):
        validate_adopted_plan(saved)


def test_old_plan_json_and_untrusted_guidance_cannot_become_an_adoption():
    with pytest.raises(ValidationError, match="planning_legacy_requires_review"):
        adopt_plan({"version": "1.0.1", "answers": {}}, "regions-manual", 1700000000.0)
    with pytest.raises(ValidationError):
        PlanInput.model_validate({"version": "2.0.0", "answers": {}, "guidance": "execute anything"})


def test_revision_receipt_binds_actual_source_and_recomputes_on_export():
    saved = adopted(comparison="independent", allocation="biological", background="yes", acquisition="matched")
    record = resolve_generic(saved)
    config = {"analysis_kind": "region-2d", "analysis_plan": record,
              "plan_resolution": resolution(saved), "recipe": generic_recipe(),
              "field_snapshot": {"field-a": generic_fields()[0]}}
    assert validate_revision_plan(config) == record
    unsigned = {key: value for key, value in record.items() if key != "resolution_sha256"}
    expected = hashlib.sha256(json.dumps(unsigned, ensure_ascii=False, sort_keys=True,
                                        separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    assert record["resolution_sha256"] == expected
    assert "independent_units_confirmed" not in record["resolved"]
    assert "background_confirmed" not in record["resolved"]
    assert not ({"independent_units_confirmed", "acquisition_confirmed", "background_confirmed"}
                & record["resolved"].keys())
    methods = "\n".join(planning_methods(config))
    assert "Those require actual-source review" in methods and "later statistical" in methods
    changed = copy.deepcopy(config)
    changed["field_snapshot"]["field-a"]["image_info"]["channels"][0]["stain"] = "Changed actual marker"
    with pytest.raises(ValueError, match="planning_revision_record_mismatch"):
        validate_revision_plan(changed)
    changed = copy.deepcopy(config)
    changed["analysis_plan"]["resolved"]["metric"] = "mean_corrected"
    with pytest.raises(ValueError, match="planning_revision_record_mismatch"):
        validate_revision_plan(changed)


def test_preview_questions_stay_separate_from_actual_source_confirmations():
    saved = adopted(background="yes", acquisition="matched", comparison="paired", allocation="biological")
    fields = generic_fields()
    before = copy.deepcopy(fields)
    record = resolve_generic(saved, fields=fields)
    assert fields == before
    assert fields[0]["metadata"]["experimental_unit"] is None
    assert record["decision"]["comparison_intent"] == "paired-candidate"
    assert not ({"independent_units_confirmed", "pair_id", "acquisition_confirmed", "backgrounds"} & record.keys())


def nuclear_recipe(**updates):
    return generic_recipe(version="1.1.0", source="stardist_nuclear", defining_channel_id="signal",
                          nuclear_stain_confirmed=True, **updates)


def test_nuclear_area_can_use_one_real_nuclear_channel_without_fabricated_extra_channels():
    saved = adopted("regions-nuclei", measurement="area", region="nucleus", definition="nuclear-stain",
                    nuclear_stain="yes", signal="unknown")
    fields = generic_fields()
    fields[0]["image_info"]["channels"][0].update(label="Nuclear stain", stain="Hoechst")
    record = resolve_generic(saved, metric="area_px", channel_id=None, fields=fields, recipe=nuclear_recipe())
    assert record["changes"] == [] and record["resolved"]["channel"] is None
    assert record["resolved"]["region_source"] == "stardist_nuclear"


@pytest.mark.parametrize("confirmation", [False, 1, "true", None])
def test_plan_yes_does_not_replace_actual_nuclear_stain_confirmation(confirmation):
    saved = adopted("regions-nuclei", region="nucleus", definition="nuclear-stain", nuclear_stain="yes")
    recipe = nuclear_recipe()
    recipe["nuclear_stain_confirmed"] = confirmation
    with pytest.raises(ValueError, match="planning_recipe_invalid"):
        resolve_generic(saved, recipe=recipe)


def test_nuclear_defining_channel_must_exist_in_every_actual_field():
    saved = adopted("regions-nuclei", region="nucleus", definition="nuclear-stain", nuclear_stain="yes")
    recipe = nuclear_recipe()
    recipe["defining_channel_id"] = "missing"
    with pytest.raises(ValueError, match="planning_channel_unavailable"):
        resolve_generic(saved, recipe=recipe)


@pytest.mark.parametrize("roles", [["dapi"], ["ncl"], ["gfp"], []])
def test_ncl_area_requires_detection_channels_even_without_intensity_selector(roles):
    saved = adopted("legacy-ncl", measurement="area", region="nucleus", definition="ncl-enrichment",
                    signal="unknown", nuclear_stain="yes")
    fields = legacy_fields()
    fields[0]["image_info"]["channel_roles"] = roles
    with pytest.raises(ValueError, match="planning_channel_unavailable"):
        resolve_legacy(saved, "nucleus_area_px", None, fields=fields)


def test_ncl_only_acquisition_needs_no_gfp_without_a_gfp_selection():
    saved = adopted("legacy-ncl", region="nucleolus", definition="ncl-enrichment", signal="ncl", nuclear_stain="yes")
    fields = legacy_fields()
    fields[0]["image_info"]["channel_roles"] = ["dapi", "ncl"]
    record = resolve_legacy(saved, "ncl_nucleoli_mean", "ncl", fields=fields)
    assert record["changes"] == []
    gated = Recipe(gfp_gate="manual", gfp_threshold=2).model_dump(mode="json")
    with pytest.raises(ValueError, match="planning_channel_unavailable"):
        resolve_legacy(saved, "ncl_nucleoli_mean", "ncl", fields=fields, recipe=gated, changes_acknowledged=True)


@pytest.mark.parametrize("invalid", ["arbitrary_detector", "https://example.invalid/recipe"])
def test_acknowledgement_does_not_allow_unregistered_region_sources(invalid):
    with pytest.raises(ValueError, match="planning_recipe_invalid"):
        resolve_generic(recipe=generic_recipe(source=invalid), changes_acknowledged=True)


def test_duplicate_actual_channel_ids_cannot_choose_the_first_silently():
    fields = generic_fields()
    fields[0]["image_info"]["channels"] *= 2
    with pytest.raises(ValueError, match="planning_channel_unavailable"):
        resolve_generic(fields=fields)


def test_actual_channel_default_fields_are_normalized_without_claiming_acquisition_limit():
    fields = generic_fields()
    fields[0]["image_info"]["channels"][0].pop("acquisition_saturation_value")
    fields[0]["image_info"]["channels"][0].pop("acquisition_saturation_confirmed")
    channel = resolve_generic(fields=fields)["resolved"]["channel"]
    assert channel["acquisition_saturation_value"] is None
    assert channel["acquisition_saturation_confirmed"] is False


@pytest.mark.parametrize("region,prefix", [("nucleus", "ncl_nucleus"), ("nucleolus", "ncl_nucleoli"),
                                          ("nucleoplasm", "ncl_nucleoplasm")])
@pytest.mark.parametrize("measurement,suffix", [("mean", "mean"), ("mean", "mean_corrected"),
                                               ("integrated", "integrated"), ("integrated", "integrated_corrected")])
def test_all_proposed_ncl_mean_and_sum_choices_match_the_actual_native_compartment(region, prefix, measurement, suffix):
    saved = adopted("legacy-ncl", measurement=measurement, region=region, definition="ncl-enrichment",
                    signal="ncl", nuclear_stain="yes")
    metric = f"{prefix}_{suffix}"
    result = resolve_legacy(saved, metric, "ncl")
    assert result["resolved"]["metric"] == metric and result["changes"] == []
    assert result["resolved"]["recipe_id"] == "ncl-native-2d"


@pytest.mark.parametrize("region,prefix", [("nucleus", "nucleus"), ("nucleolus", "nucleolar"),
                                          ("nucleoplasm", "nucleoplasm")])
@pytest.mark.parametrize("unit", ["px", "um2"])
def test_ncl_compartment_area_uses_its_exact_existing_metric_without_an_intensity_channel(region, prefix, unit):
    saved = adopted("legacy-ncl", measurement="area", region=region, definition="ncl-enrichment",
                    signal="unknown", nuclear_stain="yes")
    metric = f"{prefix}_area_{unit}"
    result = resolve_legacy(saved, metric, None)
    assert result["resolved"]["metric"] == metric and result["changes"] == []
    assert result["resolved"]["channel"] is None


@pytest.mark.parametrize("metric", ["gfp_integrated", "gfp_integrated_corrected"])
def test_gfp_integrated_plan_keeps_existing_integrated_metric(metric):
    saved = adopted("legacy-gfp-nuclear", measurement="integrated", region="nucleus",
                    definition="nuclear-stain", signal="gfp", nuclear_stain="yes")
    recipe = Recipe(id="gfp-nuclear-2d").model_dump(mode="json")
    result = resolve_legacy(saved, metric, "gfp", recipe=recipe)
    assert result["resolved"]["metric"] == metric and result["changes"] == []


@pytest.mark.parametrize("forbidden", ["independent_units_confirmed", "acquisition_confirmed", "background_confirmed"])
def test_resolution_cannot_upgrade_planning_answers_into_statistical_or_acquisition_review(forbidden):
    saved = adopted(comparison="independent", allocation="biological", acquisition="matched", background="yes")
    proposed = resolution(saved)
    proposed[forbidden] = True
    with pytest.raises(ValidationError):
        resolve_plan(saved, proposed, generic_recipe(), generic_fields(), "regions")


def test_negative_control_planning_answer_cannot_confirm_actual_gfp_control():
    saved = adopted("legacy-gfp-nuclear", region="nucleus", definition="nuclear-stain", signal="gfp",
                    nuclear_stain="yes", gating="negative-control")
    recipe = Recipe(id="gfp-nuclear-2d").model_dump(mode="json")
    recipe.update(gfp_gate="negative-control", gfp_threshold=1, gfp_negative_control_fields=["field-a"],
                  gfp_negative_control_confirmed=False)
    with pytest.raises(ValueError, match="planning_recipe_invalid"):
        resolve_legacy(saved, "gfp_mean", "gfp", recipe=recipe)


def test_unknown_independence_keeps_a_valid_measurement_plan_without_creating_replicates():
    saved = adopted(comparison="independent", allocation="unknown")
    record = resolve_generic(saved)
    assert record["decision"]["comparison_intent"] == "undetermined"
    assert record["decision"]["descriptive_allowed"] is True
    assert record["resolved"]["metric"] == "mean"
    assert "experimental_unit" not in record["resolved"] and "n" not in record["resolved"]
