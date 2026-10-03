"""Private preview of deterministic guidance; no images or remote services."""
from copy import deepcopy
from typing import Annotated

from cytellect_analysis.plan_adoption import SAFE_ERROR_CODES, resolve_plan
from cytellect_analysis.planning import PlanInput, PlanSnapshot, snapshot_plan
from fastapi import Depends, HTTPException


def inherit_plan_resolution(config, parent_config):
    resolution = deepcopy(parent_config.get("plan_resolution"))
    if resolution is not None and config["recipe"] != parent_config["recipe"]:
        # Consent to a prior change is not consent to a different actual recipe.
        resolution["changes_acknowledged"] = False
    config["plan_resolution"] = resolution


def bind_revision_plan(config, workspace_plan):
    try:
        record = resolve_plan(workspace_plan, config.get("plan_resolution"), config["recipe"],
                              list(config["field_snapshot"].values()),
                              "regions" if config.get("analysis_kind") == "region-2d" else "nuclear")
    except ValueError as exc:
        code = str(exc) if str(exc) in SAFE_ERROR_CODES else "planning_adoption_mismatch"
        raise HTTPException(422, code) from None
    if record is not None:
        config["analysis_plan"] = record
    else:
        config.pop("analysis_plan", None)
        config.pop("plan_resolution", None)


def register_planning_routes(api, owner):
    Owner = Annotated[str, Depends(owner)]

    @api.post("/v1/plans/preview", response_model=PlanSnapshot)
    def preview_plan(body: PlanInput, who: Owner):
        return snapshot_plan(body)
