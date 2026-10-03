"""Bind a proposed plan to explicit actual choices without copying confirmations."""
import hashlib
import json
import math
from typing import Annotated, Literal, get_args

from pydantic import Field, FiniteFloat, StrictBool, TypeAdapter, model_serializer, model_validator

from .planning import CandidateId, PlanInput, PlanModel, PlanSnapshot, snapshot_plan, validate_plan_snapshot
from .region_policy import RegionMeasurementPolicy

Id = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")]

SAFE_ERROR_CODES = frozenset({
    "planning_candidate_unavailable", "planning_adoption_mismatch", "planning_resolution_required",
    "planning_resolution_without_plan", "planning_workflow_mismatch", "planning_metric_unavailable",
    "planning_channel_unavailable", "planning_calibration_required", "planning_changes_review_required",
    "planning_revision_record_mismatch",
    "planning_inputs_required",
    "planning_recipe_invalid",
    "planning_measurement_mismatch", "planning_measurement_policy_invalid",
})


class AdoptedPlan(PlanSnapshot):
    adoption_version: Literal["1.0.0"] = "1.0.0"
    selected_candidate_id: CandidateId
    accepted_at: Annotated[FiniteFloat, Field(gt=0)]
    scope: Literal["planning-intent-only"] = "planning-intent-only"


class PlanResolution(PlanModel):
    version: Literal["1.0.0", "1.1.0"] = "1.0.0"
    plan_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    candidate_id: CandidateId
    metric: Id
    channel_id: Id | None = None
    changes_acknowledged: StrictBool = False
    measurement: RegionMeasurementPolicy | None = None

    @model_validator(mode="after")
    def explicit_policy_choice(self):
        supplied = "measurement" in self.model_fields_set
        if (self.version == "1.0.0" and supplied) or (self.version == "1.1.0" and not supplied):
            raise ValueError("planning_measurement_mismatch")
        return self

    @model_serializer(mode="wrap")
    def preserve_historical_shape(self, handler):
        value = handler(self)
        if self.version == "1.0.0":
            value.pop("measurement", None)
        return value


def adopt_plan(value: PlanInput, candidate_id: str, accepted_at: float) -> AdoptedPlan:
    snapshot = snapshot_plan(value)
    if candidate_id not in {candidate.id for candidate in snapshot.decision.candidates}:
        raise ValueError("planning_candidate_unavailable")
    return AdoptedPlan.model_validate({**snapshot.model_dump(mode="json"),
                                      "selected_candidate_id": candidate_id, "accepted_at": accepted_at})


def validate_adopted_plan(value) -> AdoptedPlan:
    saved = AdoptedPlan.model_validate(value)
    validate_plan_snapshot({key: saved.model_dump(mode="json")[key] for key in ("input", "decision", "sha256")})
    if saved.selected_candidate_id not in {candidate.id for candidate in saved.decision.candidates}:
        raise ValueError("planning_candidate_unavailable")
    return saved


def resolve_plan(value, resolution, recipe, fields, workflow, measurement=None):
    try:
        actual_policy = RegionMeasurementPolicy.model_validate(measurement) if measurement is not None else None
    except ValueError:
        raise ValueError("planning_measurement_policy_invalid") from None
    if actual_policy is not None and workflow != "regions":
        raise ValueError("planning_workflow_mismatch")
    if value is None:
        if resolution is not None:
            raise ValueError("planning_resolution_without_plan")
        return None
    if resolution is None:
        raise ValueError("planning_resolution_required")
    saved = validate_adopted_plan(value)
    chosen = PlanResolution.model_validate(resolution)
    if chosen.plan_sha256 != saved.sha256 or chosen.candidate_id != saved.selected_candidate_id:
        raise ValueError("planning_adoption_mismatch")
    candidate = next(item for item in saved.decision.candidates if item.id == saved.selected_candidate_id)
    if candidate.workflow != workflow:
        raise ValueError("planning_workflow_mismatch")
    if chosen.version == "1.0.0" and (actual_policy is not None or candidate.measurement is not None):
        raise ValueError("planning_resolution_required")
    if chosen.measurement != actual_policy:
        raise ValueError("planning_measurement_mismatch")
    if not fields:
        raise ValueError("planning_inputs_required")
    # Imported locally to avoid a cycle with the HTTP AnalysisRequest contracts.
    from .contracts import Recipe, required_channel_roles
    from .descriptive_contracts import LegacyMetric, RegionMetric
    from .region_contracts import RegionRecipeType
    from .regions import Calibration2D, ChannelSpec

    generic = workflow == "regions"
    try:
        actual_recipe = TypeAdapter(RegionRecipeType).validate_python(recipe) if generic else Recipe.model_validate(recipe, strict=True)
    except ValueError:
        raise ValueError("planning_recipe_invalid") from None
    recipe = actual_recipe.model_dump(mode="json")
    metric = chosen.metric
    if metric not in get_args(RegionMetric if generic else LegacyMetric):
        raise ValueError("planning_metric_unavailable")
    if actual_policy is not None and metric not in {"area_px", "area_um2"}:
        raise ValueError("planning_metric_unavailable")
    area = metric.startswith("area_") if generic else "_area_" in metric
    source_channel = None
    if generic:
        if recipe.get("id") != "region-2d":
            raise ValueError("planning_workflow_mismatch")
        if area and chosen.channel_id is not None:
            raise ValueError("planning_channel_unavailable")
        for field in fields:
            try:
                channels = [ChannelSpec.model_validate(item) for item in field["image_info"]["channels"]]
            except ValueError:
                raise ValueError("planning_channel_unavailable") from None
            ids = [item.channel_id for item in channels]
            if not ids or len(ids) != len(set(ids)) or (
                    recipe.get("defining_channel_id") is not None and recipe["defining_channel_id"] not in ids):
                raise ValueError("planning_channel_unavailable")
            if not area:
                channel = next((item.model_dump(mode="json") for item in channels
                                if item.channel_id == chosen.channel_id), None)
                if channel is None or (source_channel is not None and channel != source_channel):
                    raise ValueError("planning_channel_unavailable")
                source_channel = channel
            if metric == "area_um2":
                try:
                    Calibration2D.model_validate(field["image_info"].get("calibration"))
                except ValueError:
                    raise ValueError("planning_calibration_required") from None
    else:
        if recipe.get("id") not in ("ncl-native-2d", "gfp-nuclear-2d"):
            raise ValueError("planning_workflow_mismatch")
        if recipe["id"] == "gfp-nuclear-2d" and metric not in {
            "gfp_mean", "gfp_median", "gfp_integrated", "gfp_mean_corrected", "gfp_median_corrected",
            "gfp_integrated_corrected", "nucleus_area_px", "nucleus_area_um2",
        }:
            raise ValueError("planning_metric_unavailable")
        if metric == "ncl_legacy_release":
            raise ValueError("planning_metric_unavailable")
        role = "gfp" if metric.startswith("gfp_") else "ncl" if metric.startswith("ncl_") else None
        if chosen.channel_id != role:
            raise ValueError("planning_channel_unavailable")
        required = required_channel_roles(actual_recipe)
        if role:
            required.add(role)
        if any(not required.issubset(set(f["image_info"].get("channel_roles", []))) for f in fields):
            raise ValueError("planning_channel_unavailable")
        if role:
            source_channel = {"channel_id": role, "identity_basis": "confirmed acquisition role; not inferred dye identity"}
        if metric.endswith("_um2"):
            for field in fields:
                pixel_size = field["metadata"].get("pixel_size_um")
                if (type(pixel_size) not in (int, float) or not math.isfinite(pixel_size)
                        or pixel_size <= 0 or not math.isfinite(pixel_size * pixel_size)
                        or pixel_size * pixel_size <= 0):
                    raise ValueError("planning_calibration_required")
    changes = []
    if recipe.get("id") != candidate.recipe_id:
        changes.append("recipe")
    if generic and recipe.get("source") != candidate.source:
        changes.append("region_source")
    if not generic and recipe.get("id") == "ncl-native-2d" and recipe.get("nucleolar_method") != "ncl-otsu":
        changes.append("region_definition")
    if metric not in candidate.allowed_metrics:
        changes.append("measurement")
    if actual_policy != candidate.measurement:
        changes.append("measurement_mode")
    actual_gate = recipe.get("gfp_gate", "none")
    expected_gate = saved.input.answers.gating
    gate_matches = actual_gate == expected_gate or (expected_gate == "exploratory" and actual_gate in ("manual", "otsu-batch"))
    if not gate_matches or recipe.get("gfp_maximum") is not None:
        changes.append("gfp_selection")
    if changes and not chosen.changes_acknowledged:
        raise ValueError("planning_changes_review_required")
    resolved = {"workflow": workflow, "selection_source": candidate.selection_source,
                "metric": metric, "channel": source_channel, "recipe_id": recipe["id"],
                "region_set_id": recipe.get("region_set_id"), "region_source": recipe.get("source")}
    if chosen.version == "1.1.0":
        resolved["measurement"] = actual_policy.model_dump(mode="json") if actual_policy is not None else None
        if generic:
            resolved["measurement_protocol"] = "2.0.0" if actual_policy is not None else "1.0.0"
    record = {**saved.model_dump(mode="json"), "resolution": chosen.model_dump(mode="json"),
              "resolved": resolved, "changes": changes}
    record["resolution_sha256"] = hashlib.sha256(json.dumps(record, ensure_ascii=False, sort_keys=True,
                                                             separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return record


def validate_revision_plan(config):
    record = config.get("analysis_plan")
    if record is None:
        if config.get("plan_resolution") is not None:
            raise ValueError("planning_resolution_without_plan")
        return None
    adopted = {key: record[key] for key in AdoptedPlan.model_fields if key in record}
    calculated = resolve_plan(adopted, config.get("plan_resolution"), config["recipe"],
                              list(config["field_snapshot"].values()),
                              "regions" if config.get("analysis_kind") == "region-2d" else "nuclear",
                              measurement=config.get("measurement"))
    if calculated != record:
        raise ValueError("planning_revision_record_mismatch")
    return calculated


def planning_methods(config):
    record = validate_revision_plan(config)
    if record is None:
        return []
    resolved = record["resolved"]
    lines = ["", "## Adopted planning intent", "",
            f"Guide {record['input']['version']}; adoption protocol {record['adoption_version']}; plan SHA-256 {record['sha256']}.",
            f"Selected candidate: {record['selected_candidate_id']}; actual recipe: {resolved['recipe_id']}.",
            f"Intended output metric resolved from the actual inputs: {resolved['metric']}.",
            "Planning answers do not establish acquisition comparability, channel identity, background validity, "
            "mask quality or independent replication. Those require actual-source review.",
            "Recorded changes from the proposed method: " + (", ".join(record["changes"]) or "none") + ".",
            "The adopted plan and explicit resolved choices are retained in revision.json; later statistical "
            "requests record their own selected metric and design."]
    if record["resolution"]["version"] == "1.1.0" and resolved["workflow"] == "regions":
        mode = "area_only" if resolved["measurement"] is not None else "area_and_background_corrected_intensity"
        lines.append(f"Explicit measurement choice: {mode}; measurement protocol {resolved['measurement_protocol']}.")
    return lines
