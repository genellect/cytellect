"""Build registered recipes from persisted intent, never from a client-supplied job script."""
from copy import deepcopy
from math import floor

from cytellect_analysis.region_contracts import RegionAnalysisRequest

from .analysis_spec import AnalysisSpec


def _round(value):
    # Match JavaScript Math.round for the nonnegative detector calibrations.
    return floor(value + 0.5)


def _nucleolar_defaults(definition):
    um = definition["pixelUm"]

    def pixels(length, fallback, maximum):
        return min(maximum, max(1, _round(length / um))) if um else fallback

    return {"engine": "cytellect-nucleolar-v2", "protocol_version": "2.1.0" if definition["source"] == "marker" else "2.0.0",
            "source": "marker" if definition["source"] == "marker" else "dapi_poor",
            "smoothing_sigma_px": 0.7 if definition["source"] == "marker" else (min(20, _round(0.35 / um * 10) / 10) if um else 2),
            "rim_exclusion_px": pixels(0.6, 4, 100), "relative_threshold": definition["relative"],
            "marker_fraction": 0.4, "background_radius_px": pixels(1.0, 10, 200),
            "minimum_area_px": max(1, _round(0.3 / (um * um))) if um else 4,
            "maximum_area_px": None, "minimum_solidity": 0.6}


def build_run_request(spec: dict, target: str, field_id: str, parents: dict,
                      channel_assignments: dict) -> RegionAnalysisRequest:
    """Mirror runtimeRecipe; parents are persisted, owned revisions resolved by orchestration."""
    spec = AnalysisSpec.model_validate(spec).model_dump(mode="json")
    if target not in ("nuclei", "nucleoli", "nucleoplasm", "cell"):
        raise ValueError("analysis_run_target_invalid")
    if channel_assignments["version"] != spec["channel_assignment_version"]:
        raise ValueError("analysis_run_channel_assignments_changed")
    settings = spec["settings"]
    processing = spec["processing"] or {}
    parent = parents.get("nuclei")
    parent_recipe = (parent or {}).get("config", {}).get("recipe", {})
    choices = [item["channel_id"] for item in channel_assignments["assignments"] if item["role"] == "nuclear"]
    if not choices and channel_assignments["version"] == 0 and parent_recipe.get("source") == "stardist_nuclear":
        choices = [parent_recipe["defining_channel_id"]]
    if target == "cell":
        choices = [item["channel_id"] for item in channel_assignments["assignments"] if item["role"] != "unused"][:1]
    if target != "cell" and len(choices) != 1:
        raise ValueError("analysis_run_nuclear_channel_required")
    # A hand-drawn cell boundary has no detector channel requirement. Unknown
    # stain identities remain unknown; the registered images are still measured.
    channel = choices[0] if choices else None
    if target == "cell":
        recipe = {"id": "region-2d", "version": "1.0.0", "source": "manual", "region_set_id": "cell",
                  "label": "細胞ROI", "defining_channel_id": channel}
    elif target == "nuclei":
        side = settings["nuclearMaxSide"]
        proposed = processing.get("nuclei")
        detector = deepcopy(proposed["detector"]) if proposed and proposed["channel"] == channel else {
            "engine": "fiji-stardist-2d", "model": "Versatile (fluorescent nuclei)",
            "percentile_low": 1, "percentile_high": 99.8}
        detector.update(probability=settings["nuclearProbability"], nms=settings["nuclearNms"])
        role = parent_recipe.get("nuclear_role_source") if parent_recipe.get("defining_channel_id") == channel else None
        recipe = {"id": "region-2d", "version": "1.7.0" if side is None else "1.5.0", "region_set_id": "nuclei",
                  "label": "核", "source": "stardist_nuclear", "defining_channel_id": channel,
                  "nuclear_role_source": role or "user_selected_role", "detector": detector,
                  **({"detection_scale": "nuclear-size/1.0.0"} if side is None else {"detection_max_side_px": side})}
    else:
        if not parent or parent_recipe.get("source") != "stardist_nuclear" or parent_recipe.get("defining_channel_id") != channel:
            raise ValueError("analysis_run_nuclear_parent_required")
        definition = settings["nucleolarDefinition"]
        defining = channel if definition["source"] == "dapi_poor" else definition["marker"]
        if not defining:
            raise ValueError("analysis_run_nucleolar_marker_required")
        if channel_assignments["version"] and defining not in {item["channel_id"] for item in channel_assignments["assignments"] if item["role"] != "unused"}:
            raise ValueError("analysis_run_nucleolar_marker_unknown")
        proposed = processing.get("nucleoli")
        proposed_detector = proposed["detector"] if proposed and proposed["channel"] == defining else None
        historical = (parents.get("nucleoli") or {}).get("config", {}).get("recipe", {})
        historical_detector = historical.get("detector", {})
        if (not proposed and definition["source"] == "marker"
                and historical.get("defining_channel_id") == defining
                and historical_detector.get("engine") == "cytellect-nucleolar-v2"
                and historical_detector.get("source") == "marker"
                and historical_detector.get("protocol_version") == "2.0.0"):
            proposed_detector = historical_detector
        if definition["source"] == "ncl":
            detector = deepcopy(proposed_detector) if proposed_detector and proposed_detector["engine"] == "fiji-nucleolar-compartments" else {
                "engine": "fiji-nucleolar-compartments", "protocol_version": "1.1.0", "threshold_method": "otsu",
                "threshold": None, "smoothing_sigma_px": 0, "minimum_area_px": 1, "maximum_area_px": None, "split_touching": False}
            # Visible explicit settings override the compatible saved/AI detector.
            # Null sigma/minimum retain its setting (or the established default);
            # null maximum explicitly removes the upper area bound.
            for source, destination in (("nucleolarSigma", "smoothing_sigma_px"), ("nucleolarMinimumArea", "minimum_area_px")):
                if settings[source] is not None:
                    detector[destination] = settings[source]
            detector["maximum_area_px"] = settings["nucleolarMaximumArea"]
        else:
            detector = _nucleolar_defaults(definition)
            if proposed_detector and proposed_detector["engine"] == "cytellect-nucleolar-v2" and proposed_detector["source"] == detector["source"]:
                detector = deepcopy(proposed_detector)
            detector["relative_threshold"] = definition["relative"]
            for source, destination in (("nucleolarSigma", "smoothing_sigma_px"), ("nucleolarRim", "rim_exclusion_px"), ("nucleolarMinimumArea", "minimum_area_px")):
                if settings[source] is not None and not (
                    source == "nucleolarSigma" and detector["source"] == "marker"
                    and detector["protocol_version"] == "2.0.0"
                ):
                    detector[destination] = settings[source]
            detector["maximum_area_px"] = settings["nucleolarMaximumArea"]
        recipe = {"id": "region-2d", "version": "1.4.0", "source": "fiji_nuclear_compartment", "region_set_id": target,
                  "label": "核小体" if target == "nucleoli" else "核質", "compartment": target,
                  "nuclear_revision_id": parent["id"], "nuclear_channel_id": channel,
                  "defining_channel_id": defining, "detector": detector}
        if target == "nucleoplasm":
            child = parents.get("nucleoli")
            child_recipe = (child or {}).get("config", {}).get("recipe", {})
            if not child or child_recipe.get("nuclear_revision_id") != parent["id"]:
                raise ValueError("analysis_run_nucleolar_parent_required")
            recipe["nucleolar_revision_id"] = child["id"]
    measurement = spec["measurement"] or ({"version": "1.2.0", "mode": "automatic_background"}
                  if settings["background"] == "automatic" else {"version": "1.1.0", "mode": "raw_intensity"})
    backgrounds = {}
    confirmed = []
    if settings["background"] == "confirmed_roi":
        measurement = None
        backgrounds = {field_id: spec["backgrounds"].get(field_id, {})}
        confirmed = [cid for cid in spec["confirmed_channel_ids"] if cid in backgrounds[field_id]]
        if not backgrounds[field_id] or set(backgrounds[field_id]) - set(confirmed):
            raise ValueError("analysis_run_background_confirmation_required")
    return RegionAnalysisRequest.model_validate({"field_ids": [field_id], "recipe": recipe,
                                                 "measurement": measurement, "backgrounds": backgrounds,
                                                 "confirmed_channel_ids": confirmed})
