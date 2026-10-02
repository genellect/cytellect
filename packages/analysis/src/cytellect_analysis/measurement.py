"""Measurements on immutable source pixels and original-coordinate label masks."""
import math

import numpy as np
import pandas as pd
from skimage.filters import threshold_otsu

from .contracts import Recipe, required_channel_roles
from .masks import validate_label_array, validate_labels
from .signal_qc import native_signal_quality


def robust_sigma(values):
    return float(1.4826 * np.median(np.abs(values - np.median(values))))

def region_values(raw, mask, background, legacy=False):
    values = raw[mask].astype(np.float64) if raw is not None else np.array([], dtype=float)
    if not len(values):
        return {k: None for k in ("mean", "median", "integrated", "mean_corrected", "median_corrected", "integrated_corrected")}
    corrected = values - background
    if legacy:
        corrected = np.maximum(corrected, 0)
    return {
        "mean": float(values.mean()), "median": float(np.median(values)), "integrated": float(values.sum()),
        "mean_corrected": float(corrected.mean()), "median_corrected": float(np.median(corrected)),
        "integrated_corrected": float(corrected.sum())
    }

NUCLEOLAR_STATES = frozenset({"candidate", "no_candidate", "indeterminate", "unclassified",
                             "review_required", "processing_failed", "not_measured_recipe", "legacy_candidate", "none_after_edit"})


def normalize_nucleolar_states(provenance):
    """Normalize recorded detector outcomes without inferring absent detections."""
    states = provenance.get("nucleolar_states", provenance.get("nucleolar_status", provenance.get("candidate_status", {})))
    if isinstance(states, list):
        states = {item["nucleus_id"]: item["status"] for item in states}
    aliases = {"candidates": "candidate", "none": "no_candidate", "not_applicable_no_ncl": "not_measured_recipe"}
    result = {int(key): aliases.get(value, value) for key, value in states.items()}
    if not set(result.values()).issubset(NUCLEOLAR_STATES):
        raise ValueError("nucleolar_state_invalid")
    return result


def measure(channels, nuclei, nucleoli, background_mask, recipe: Recipe, metadata, field_id, manual=None,
            *, nucleolar_states=None):
    states = normalize_nucleolar_states({"nucleolar_states": nucleolar_states or {}})
    validate_labels(nuclei, nucleoli)
    if not required_channel_roles(recipe).issubset(channels) or not set(channels).issubset({"dapi", "ncl", "gfp"}):
        raise ValueError("recipe_required_channels_missing")
    for image in channels.values():
        if image.shape != nuclei.shape or image.dtype not in (np.dtype("uint8"), np.dtype("uint16")):
            raise ValueError("measurement_source_shape_or_dtype_invalid")
    if manual is not None:
        validate_label_array(manual)
        if manual.shape != nuclei.shape:
            raise ValueError("manual_shape_mismatch")
    if recipe.id == "gfp-nuclear-2d" and nucleoli.any():
        raise ValueError("nucleolar_masks_disabled_for_gfp_recipe")
    if recipe.id == "ncl-legacy-rgb":
        from .legacy import measure_legacy
        result = measure_legacy(channels, nuclei, nucleoli, recipe, metadata, field_id, manual)
        for row in result[0]:
            row["measurement_protocol_version"] = "1.1.1"
            row["nucleoplasm_area_px"] = row["nucleus_area_px"] - row["nucleolar_area_px"]
            pixel_size = metadata.get("pixel_size_um")
            row["nucleoplasm_area_um2"] = row["nucleoplasm_area_px"] * pixel_size**2 if pixel_size else None
            row["nucleolar_status"] = states.get(row["nucleus_id"], row["nucleolar_status"])
        return result
    if background_mask is None or background_mask.dtype != np.bool_ or background_mask.shape != nuclei.shape:
        raise ValueError("background_boolean_shape_required")
    if not background_mask.any() or (background_mask & (nuclei > 0)).any():
        raise ValueError("background_must_be_nonempty_and_outside_nuclei")
    legacy = recipe.id == "ncl-legacy-rgb"
    background = {c: float(np.median(a[background_mask])) for c, a in channels.items()}
    sigma = {c: robust_sigma(a[background_mask].astype(float)) for c, a in channels.items()}
    epsilon = max(sigma.get("ncl", 0), 1.0)
    cells, objects = [], []
    for nucleus in np.unique(nuclei):
        if nucleus == 0:
            continue
        whole = nuclei == nucleus
        enriched = whole & (nucleoli > 0)
        plasma = whole & ~enriched
        row = {**metadata, "field_id": field_id, "nucleus_id": int(nucleus),
               "recipe_id": recipe.id, "recipe_version": recipe.version, "measurement_protocol_version": "1.1.1",
               "channel_availability": {role: role in channels for role in ("dapi", "ncl", "gfp")},
               "nucleus_area_px": int(whole.sum()), "nucleolar_area_px": int(enriched.sum()),
               "nucleoplasm_area_px": int(plasma.sum()),
               "nucleolar_count": int(len(np.unique(nucleoli[enriched]))),
               "nucleolar_area_fraction": float(enriched.sum() / whole.sum()),
               "nucleolar_status": states.get(int(nucleus), "candidate" if enriched.any() else "unclassified"),
               "excluded": False, "exclusion_reason": "", "gfp_positive": True}
        pixel_size = metadata.get("pixel_size_um")
        row["nucleus_area_um2"] = float(whole.sum() * pixel_size**2) if pixel_size else None
        row["nucleolar_area_um2"] = float(enriched.sum() * pixel_size**2) if pixel_size else None
        row["nucleoplasm_area_um2"] = float(plasma.sum() * pixel_size**2) if pixel_size else None
        for compartment, mask in [("nucleus", whole), ("nucleoli", enriched), ("nucleoplasm", plasma)]:
            row.update({f"ncl_{compartment}_{k}": v for k, v in region_values(channels.get("ncl") if recipe.id != "gfp-nuclear-2d" else None, mask, background.get("ncl", 0), legacy).items()})
        row.update({f"gfp_{k}": v for k, v in region_values(channels.get("gfp"), whole, background.get("gfp", 0), legacy).items()})
        for c in channels:
            row[f"{c}_background"] = background[c]
            row[f"{c}_background_sigma"] = sigma[c]
            row[f"{c}_saturation_fraction"] = float(np.mean(channels[c][whole] == np.iinfo(channels[c].dtype).max))
        row["touches_border"] = bool(whole[0].any() or whole[-1].any() or whole[:,0].any() or whole[:,-1].any())
        p, n = row["ncl_nucleoplasm_mean_corrected"], row["ncl_nucleoli_mean_corrected"]
        valid = p is not None and n is not None and p > 0 and n > 0
        row["ncl_nucleoplasm_over_nucleoli"] = p / n if valid else None
        row["ncl_log2_nucleoplasm_over_nucleoli"] = math.log2(p / n) if valid else None
        row["ratio_missing_reason"] = "" if valid else ("no_compartment" if p is None or n is None else "nonpositive_signal")
        row["ncl_legacy_release"] = None
        row["legacy_epsilon"] = epsilon if legacy else None
        if legacy and n is not None:
            row["ncl_legacy_release"] = math.log2((row["ncl_nucleus_mean_corrected"] + epsilon) / (n + epsilon))
        if recipe.id == "gfp-nuclear-2d":
            for key in ("nucleolar_area_px", "nucleolar_area_um2", "nucleoplasm_area_px", "nucleoplasm_area_um2",
                        "nucleolar_count", "nucleolar_area_fraction"):
                row[key] = None
            row["nucleolar_status"] = "not_measured_recipe"
            row["ratio_missing_reason"] = "ncl_not_measured_recipe"
        elif row["nucleolar_status"] == "processing_failed":
            # Nucleus pixels remain measurable, but neither U nor N-U was
            # successfully defined. Empty storage masks cannot stand for absence.
            if enriched.any():
                raise ValueError("failed_nucleolar_mask_not_empty")
            for key in list(row):
                if key.startswith(("ncl_nucleoli_", "ncl_nucleoplasm_", "nucleolar_area", "nucleoplasm_area")):
                    row[key] = None
            row["nucleolar_count"] = None
            row["ncl_log2_nucleoplasm_over_nucleoli"] = None
            row["ratio_missing_reason"] = "nucleolar_processing_failed"
        row.update(native_signal_quality(row, recipe.native_signal_qc_minimum_ratio))
        cells.append(row)
        for label in np.unique(nucleoli[enriched]):
            mask = nucleoli == label
            objects.append({"field_id": field_id, "nucleus_id": int(nucleus), "nucleolus_id": int(label),
                            "area_px": int(mask.sum()), **region_values(channels.get("ncl") if recipe.id != "gfp-nuclear-2d" else None, mask, background.get("ncl", 0), legacy)})
    manual_rows = []
    if manual is not None:
        for label in np.unique(manual):
            if not label:
                continue
            row = {"field_id": field_id, "roi_id": int(label), "area_px": int((manual == label).sum())}
            for c, a in channels.items():
                row.update({f"{c}_{k}": v for k, v in region_values(a if recipe.id != "gfp-nuclear-2d" or c != "ncl" else None, manual == label, background[c], legacy).items()})
            manual_rows.append(row)
    return cells, objects, manual_rows

def apply_gfp_gate(rows, recipe: Recipe):
    if not rows:
        return []
    if recipe.id == "ncl-legacy-rgb" and recipe.legacy.gfp_mode == "otsu-qc-batch":
        from .legacy import apply_legacy_gfp_gate
        return apply_legacy_gfp_gate(rows, recipe)
    frame = pd.DataFrame(rows)
    if (recipe.gfp_gate != "none" or recipe.gfp_maximum is not None) and any(
            row.get("gfp_mean_corrected") is None for row in rows):
        raise ValueError("gfp_gate_requires_acquired_channel")
    thresholds = {}
    if recipe.gfp_gate == "otsu-batch":
        for date, group in frame.groupby("acquisition_date"):
            values = group.loc[~group.get("excluded", pd.Series(False, index=group.index)), "gfp_mean_corrected"].dropna().to_numpy()
            thresholds[date] = float(threshold_otsu(values)) if len(values) > 1 and np.ptp(values) > 0 else None
    for row in rows:
        threshold = thresholds.get(row["acquisition_date"]) if recipe.gfp_gate == "otsu-batch" else recipe.gfp_threshold
        value = row["gfp_mean_corrected"]
        positive = True if recipe.gfp_gate == "none" else (value is not None and threshold is not None and value >= threshold)
        if recipe.gfp_maximum is not None:
            positive = positive and value is not None and value <= recipe.gfp_maximum
        row["gfp_selection_protocol_version"] = "1.1.1"
        row["gfp_positive"] = bool(positive)
        row["gfp_gate_threshold"] = threshold
        row["gfp_gate_method"] = "confirmed-negative-control" if recipe.gfp_gate == "negative-control" else recipe.gfp_gate
        row["gfp_negative_control_fields"] = recipe.gfp_negative_control_fields if recipe.gfp_gate == "negative-control" else []
        row["gfp_gate_exploratory"] = recipe.gfp_gate in ("otsu-batch", "manual") or recipe.gfp_maximum is not None
        row["gfp_gate_maximum"] = recipe.gfp_maximum
        row["gfp_selection_reason"] = "included" if positive else "outside_gfp_gate"
    return rows
