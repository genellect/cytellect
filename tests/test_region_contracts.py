"""JSON/DB boundaries do not weaken scientific validation or invent identity."""
import json

import pytest
from cytellect_analysis.region_contracts import (
    RegionAnalysisRequest,
    RegionFieldInput,
    RegionImageInfo,
    RegionMaskEdit,
)
from pydantic import ValidationError


def test_region_wire_json_lists_round_trip_without_scientific_tuple_coercion():
    body = {
        "field_ids": ["f1"],
        "recipe": {"region_set_id": "reviewed", "label": "Cell regions", "source": "imported"},
        "backgrounds": {"f1": {"actin": {"confirmed": True, "polygon": [[0, 0], [2, 0], [2, 1]]}}},
    }
    first = RegionAnalysisRequest.model_validate(body)
    stored = json.loads(json.dumps(first.model_dump(mode="json")))
    assert RegionAnalysisRequest.model_validate(stored) == first
    field = RegionFieldInput.model_validate({"channels": [
        {"channel_id": "actin", "label": "Actin", "identity_confirmed": True},
    ]})
    assert field.metadata.experimental_unit is None
    assert field.channels[0].stain is None
    assert field.calibration is None
    assert RegionFieldInput.model_validate(json.loads(field.model_dump_json())) == field


@pytest.mark.parametrize("value", [1, "true", False, None])
def test_wire_background_confirmation_requires_actual_true(value):
    with pytest.raises(ValidationError):
        RegionAnalysisRequest.model_validate({
            "recipe": {"region_set_id": "r", "label": "Regions", "source": "manual"},
            "backgrounds": {"f": {"channel": {"polygon": [[0, 0], [1, 0], [1, 1]], "confirmed": value}}},
        })


@pytest.mark.parametrize("update", [
    {"channels": [{"channel_id": "../actin", "label": "Actin", "identity_confirmed": True}]},
    {"metadata": {"experimental_unit": " "}},
    {"metadata": {"pixel_size_um": 0.5}},
    {"calibration": {"pixel_size_x_um": 0.5, "confirmed": True}},
    {"metadata": {"sample": 1}},
])
def test_wire_rejects_unsafe_or_ambiguous_metadata(update):
    body = {"channels": [{"channel_id": "actin", "label": "Actin", "identity_confirmed": True}], **update}
    with pytest.raises(ValidationError):
        RegionFieldInput.model_validate(body)


def test_recipe_rejects_unimplemented_auto_and_duplicate_ids():
    with pytest.raises(ValidationError):
        RegionAnalysisRequest.model_validate({
            "recipe": {"region_set_id": "r", "label": "Nuclei", "source": "stardist_nuclear"},
        })
    with pytest.raises(ValidationError):
        RegionAnalysisRequest.model_validate({
            "field_ids": ["f", "f"],
            "recipe": {"region_set_id": "r", "label": "Regions", "source": "manual"},
        })
    with pytest.raises(ValidationError):
        RegionFieldInput.model_validate({"channels": [
            {"channel_id": "actin", "label": "Actin", "identity_confirmed": True},
            {"channel_id": "actin", "label": "GFP", "identity_confirmed": True},
        ]})


@pytest.mark.parametrize("operation,ids,polygon", [
    ("add", [1], [[0, 0], [1, 0], [1, 1]]),
    ("replace", [], [[0, 0], [1, 0], [1, 1]]),
    ("split", [1], []),
    ("merge", [1, 1], []),
    ("delete", [], []),
    ("delete", [1], [[0, 0], [1, 0], [1, 1]]),
])
def test_edit_requires_explicit_noncontradictory_geometry(operation, ids, polygon):
    with pytest.raises(ValidationError):
        RegionMaskEdit.model_validate({"field_id": "f", "region_set_id": "r", "operation": operation,
                                      "ids": ids, "polygon": polygon})


def test_stored_mapping_cannot_default_to_legacy_channels():
    with pytest.raises(ValidationError):
        RegionImageInfo.model_validate({
            "shape": [8, 8], "channels": [{"channel_id": "actin", "label": "Actin", "identity_confirmed": True}],
            "inputs": {"ch0": {"sha256": "a" * 64, "bytes": 1}},
            "channel_arrays": {"gfp": {"sha256": "a" * 64, "bytes": 1}},
        })


def test_channel_ids_cannot_collide_on_windows_and_source_slots_are_complete():
    with pytest.raises(ValidationError, match="duplicate_region_channel_ids"):
        RegionFieldInput.model_validate({"channels": [
            {"channel_id": "DNA", "label": "DNA", "identity_confirmed": True},
            {"channel_id": "dna", "label": "Other marker", "identity_confirmed": True},
        ]})
    with pytest.raises(ValidationError, match="region_stored_input_slots_invalid"):
        RegionImageInfo.model_validate({
            "shape": [8, 8], "channels": [{"channel_id": "actin", "label": "Actin", "identity_confirmed": True}],
            "inputs": {"other_file": {"sha256": "a" * 64, "bytes": 1}},
            "channel_arrays": {"actin": {"sha256": "a" * 64, "bytes": 1}},
        })
