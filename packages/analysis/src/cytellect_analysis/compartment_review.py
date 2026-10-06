"""Prevent unclassified nuclear compartments from disappearing from inference."""
from copy import deepcopy


def comparable_region_recipe(recipe: dict) -> dict:
    value = deepcopy(recipe)
    if value.get("source") == "fiji_nuclear_compartment":
        value.pop("nuclear_revision_id", None)
    return value


def assert_complete_compartments(config: dict, report: dict, provenance: dict, field_ids=None) -> None:
    recipe = config.get("recipe", {})
    if recipe.get("source") != "fiji_nuclear_compartment":
        return
    excluded = {item["field_id"] for item in report.get("exclusions", []) if item.get("region_id") is None}
    selected = set(field_ids if field_ids is not None else config.get("field_ids", [])) - excluded
    for fid in selected:
        engine = provenance.get("fields", {}).get(fid, {}).get("detector", {}).get("engine", {})
        states = engine.get("nucleolar_states")
        count = engine.get("missing_parent_count")
        if (not isinstance(states, dict) or type(count) is not int or count != 0
                or any(state != "candidate" for state in states.values())
                or (recipe.get("compartment") == "nucleoplasm" and engine.get("nucleoplasm_missing_reasons"))):
            raise ValueError("unresolved_nuclear_compartments")
