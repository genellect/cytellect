from copy import deepcopy

import pytest
from cytellect_analysis.compartment_review import assert_complete_compartments, comparable_region_recipe


def fixture():
    config = {
        "recipe": {
            "source": "fiji_nuclear_compartment",
            "compartment": "nucleoli",
            "nuclear_revision_id": "a",
        },
        "field_ids": ["f"],
    }
    report = {"exclusions": []}
    provenance = {
        "fields": {
            "f": {"detector": {"engine": {"nucleolar_states": {"1": "candidate"}, "missing_parent_count": 0}}}
        }
    }
    return config, report, provenance


def test_complete_compartments_are_usable_but_missing_parents_are_not():
    config, report, provenance = fixture()
    assert_complete_compartments(config, report, provenance)
    provenance["fields"]["f"]["detector"]["engine"]["nucleolar_states"]["2"] = "no_candidate"
    with pytest.raises(ValueError, match="unresolved_nuclear_compartments"):
        assert_complete_compartments(config, report, provenance)
    report["exclusions"] = [{"field_id": "f", "region_id": None, "reason": "reviewed"}]
    assert_complete_compartments(config, report, provenance)


def test_missing_provenance_fails_closed_only_for_compartment_recipe():
    config, report, _ = fixture()
    with pytest.raises(ValueError, match="unresolved_nuclear_compartments"):
        assert_complete_compartments(config, report, {})
    config["recipe"]["source"] = "stardist_nuclear"
    assert_complete_compartments(config, report, {})


def test_empty_nucleoplasm_is_not_a_valid_observation():
    config, report, provenance = fixture()
    config["recipe"]["compartment"] = "nucleoplasm"
    provenance["fields"]["f"]["detector"]["engine"]["nucleoplasm_missing_reasons"] = {
        "1": "empty_after_subtraction"
    }
    with pytest.raises(ValueError, match="unresolved_nuclear_compartments"):
        assert_complete_compartments(config, report, provenance)


def test_cohort_identity_ignores_only_parent_revision_not_parameters():
    config, _, _ = fixture()
    recipe = config["recipe"]
    other = deepcopy(recipe)
    other["nuclear_revision_id"] = "b"
    assert comparable_region_recipe(recipe) == comparable_region_recipe(other)
    other["defining_channel_id"] = "different"
    assert comparable_region_recipe(recipe) != comparable_region_recipe(other)
    assert recipe["nuclear_revision_id"] == "a"
