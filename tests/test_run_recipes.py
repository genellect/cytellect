import pytest
from cytellect_api.analysis_spec import AnalysisSpec
from cytellect_api.run_recipes import build_run_request

ASSIGNMENTS = {"version": 1, "assignments": [{"channel_id": "dna", "stain": "DAPI", "role": "nuclear"},
                                             {"channel_id": "marker", "stain": "FBL", "role": "measure"}]}


def spec(**settings):
    return AnalysisSpec(channel_assignment_version=1, settings=settings).model_dump(mode="json")


def nucleus(draft=None):
    request = build_run_request(draft or spec(), "nuclei", "field", {}, ASSIGNMENTS)
    return {"id": "nuclear_rev", "config": {"recipe": request.recipe.model_dump(mode="json")}}


def test_nuclear_and_compartment_defaults_preserve_source_binding():
    draft = spec()
    parent = nucleus(draft)
    recipe = parent["config"]["recipe"]
    assert recipe["version"] == "1.7.0"
    assert recipe["defining_channel_id"] == "dna"
    assert recipe["detector"]["probability"] == 0.5
    child = build_run_request(draft, "nucleoli", "field", {"nuclei": parent}, ASSIGNMENTS)
    assert child.recipe.detector.rim_exclusion_px == 4
    assert child.recipe.detector.minimum_area_px == 4
    children = {"nuclei": parent, "nucleoli": {"id": "child_rev", "config": {"recipe": child.recipe.model_dump(mode="json")}}}
    inner = build_run_request(draft, "nucleoplasm", "field", children, ASSIGNMENTS)
    assert inner.recipe.nuclear_revision_id == "nuclear_rev"
    assert inner.recipe.nucleolar_revision_id == "child_rev"


def test_visible_settings_and_background_apply_to_nuclei():
    request = build_run_request(spec(nuclearMaxSide=1024, nuclearProbability=0.7, nuclearNms=0.2, background="automatic"), "nuclei", "field", {}, ASSIGNMENTS)
    assert request.recipe.version == "1.5.0"
    assert request.recipe.detector.probability == 0.7
    assert request.measurement.mode == "automatic_background"


def test_calibrated_marker_and_manual_overrides():
    draft = spec(nucleolarDefinition={"source": "marker", "marker": "marker", "pixelUm": 0.1, "relative": 0.6}, nucleolarSigma=3, nucleolarMinimumArea=12)
    request = build_run_request(draft, "nucleoli", "field", {"nuclei": nucleus(draft)}, ASSIGNMENTS)
    assert request.recipe.defining_channel_id == "marker"
    assert request.recipe.detector.source == "marker"
    assert request.recipe.detector.smoothing_sigma_px == 3
    assert request.recipe.detector.minimum_area_px == 12
    assert request.recipe.detector.rim_exclusion_px == 6


def test_missing_roles_and_stale_assignment_are_not_guessed():
    with pytest.raises(ValueError, match="channel_assignments_changed"):
        build_run_request(spec(), "nuclei", "field", {}, {"version": 0, "assignments": []})
    with pytest.raises(ValueError, match="nuclear_channel_required"):
        build_run_request(spec(), "nuclei", "field", {}, {"version": 1, "assignments": []})
    with pytest.raises(ValueError, match="nuclear_parent_required"):
        build_run_request(spec(), "nucleoli", "field", {}, ASSIGNMENTS)


def test_manual_cell_is_distinct_from_nucleus():
    assignments = {"version": 1, "assignments": [{"channel_id": "actin", "role": "measure", "stain": "actin"}]}
    request = build_run_request(spec(), "cell", "field", {}, assignments)
    assert request.recipe.source == "manual"
    assert request.recipe.region_set_id == "cell"
    assert request.recipe.defining_channel_id == "actin"


def test_manual_cell_requires_no_channel_roles_or_nuclear_image():
    request = build_run_request(spec(), "cell", "field", {}, {"version": 1, "assignments": []})
    assert request.recipe.source == "manual"
    assert request.recipe.region_set_id == "cell"
    assert request.recipe.defining_channel_id is None
    assert request.measurement.mode == "raw_intensity"


def test_background_confirmation_is_scoped_to_each_field_images():
    draft = spec(background="confirmed_roi")
    roi = {"polygon": [[0, 0], [2, 0], [2, 2]], "confirmed": True}
    draft["backgrounds"] = {"field": {"marker": roi}, "other": {"different": roi}}
    draft["confirmed_channel_ids"] = ["marker", "different"]
    request = build_run_request(draft, "cell", "field", {}, ASSIGNMENTS)
    assert request.confirmed_channel_ids == ["marker"]
    assert set(request.backgrounds) == {"field"}
    assert request.measurement is None
