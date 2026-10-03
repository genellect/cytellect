"""A detector recipe is explicit, while original manual wire JSON stays stable."""
import json

import pytest
from cytellect_analysis.region_contracts import (
    NuclearDetectorSpec,
    RegionAnalysisRequest,
    RegionNuclearRecipe,
)
from pydantic import ValidationError


def nuclear_recipe():
    return {"id": "region-2d", "version": "1.1.0", "region_set_id": "nuclei", "label": "Nuclei",
            "source": "stardist_nuclear", "defining_channel_id": "hoechst", "nuclear_stain_confirmed": True}


def test_manual_recipe_json_does_not_gain_unused_detector_fields():
    expected = {"id": "region-2d", "version": "1.0.0", "region_set_id": "regions", "label": "Regions",
                "source": "manual", "defining_channel_id": None}
    for recipe in (expected, {k: v for k, v in expected.items() if k != "version"}):
        parsed = RegionAnalysisRequest.model_validate({"recipe": recipe})
        assert parsed.recipe.model_dump(mode="json") == expected
        assert RegionAnalysisRequest.model_validate_json(parsed.model_dump_json()) == parsed


def test_nuclear_recipe_records_actual_channel_and_fixed_model():
    request = RegionAnalysisRequest.model_validate({"recipe": nuclear_recipe()})
    assert isinstance(request.recipe, RegionNuclearRecipe)
    assert request.recipe.defining_channel_id == "hoechst"
    assert request.recipe.detector == NuclearDetectorSpec()
    assert RegionAnalysisRequest.model_validate(json.loads(request.model_dump_json())) == request


@pytest.mark.parametrize("change", [
    {"version": "1.0.0"}, {"defining_channel_id": None}, {"defining_channel_id": "../dna"},
    {"nuclear_stain_confirmed": False}, {"nuclear_stain_confirmed": 1},
    {"nuclear_stain_confirmed": "true"}, {"detector": {"model": "Cellpose"}},
    {"detector": {"url": "https://example.invalid/model"}},
    {"detector": {"probability": 0}}, {"detector": {"nms": 1}},
    {"detector": {"percentile_low": 99.8, "percentile_high": 99.8}},
    {"detector": {"probability": True}}, {"source": "cell-boundaries"},
])
def test_nuclear_scope_and_parameters_cannot_be_guessed_or_coerced(change):
    with pytest.raises(ValidationError):
        RegionAnalysisRequest.model_validate({"recipe": {**nuclear_recipe(), **change}})


def test_automatic_recipe_requires_explicit_new_version_and_confirmation():
    for key in ("version", "nuclear_stain_confirmed", "defining_channel_id"):
        with pytest.raises(ValidationError):
            RegionAnalysisRequest.model_validate({"recipe": {k: v for k, v in nuclear_recipe().items() if k != key}})
