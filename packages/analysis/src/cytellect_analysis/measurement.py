"""Measurements on immutable source pixels and original-coordinate label masks."""
import math
import numpy as np
import pandas as pd
from skimage.filters import threshold_otsu
from .contracts import Recipe
from .masks import validate_labels

def robust_sigma(values):
    return float(1.4826 * np.median(np.abs(values - np.median(values))))

def region_values(raw, mask, background, legacy=False):
    values = raw[mask].astype(np.float64)
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

def measure(channels, nuclei, nucleoli, background_mask, recipe: Recipe, metadata, field_id, manual=None):
    validate_labels(nuclei, nucleoli)
    if not background_mask.any() or (background_mask & (nuclei > 0)).any():
        raise ValueError("background_must_be_nonempty_and_outside_nuclei")
    legacy = recipe.id == "ncl-legacy-rgb"
    background = {c: float(np.median(a[background_mask])) for c, a in channels.items()}
    sigma = {c: robust_sigma(a[background_mask].astype(float)) for c, a in channels.items()}
    epsilon = max(sigma["ncl"], 1.0)
    cells, objects = [], []
    for nucleus in np.unique(nuclei):
        if nucleus == 0:
            continue
        whole = nuclei == nucleus
        enriched = whole & (nucleoli > 0)
        plasma = whole & ~enriched
        row = {**metadata, "field_id": field_id, "nucleus_id": int(nucleus),
               "recipe_id": recipe.id, "recipe_version": recipe.version,
               "nucleus_area_px": int(whole.sum()), "nucleolar_area_px": int(enriched.sum()),
               "nucleolar_count": int(len(np.unique(nucleoli[enriched]))),
               "nucleolar_area_fraction": float(enriched.sum() / whole.sum()),
               "nucleolar_status": "candidate" if enriched.any() else "none_or_indeterminate",
               "excluded": False, "exclusion_reason": "", "gfp_positive": True}
        pixel_size = metadata.get("pixel_size_um")
        row["nucleus_area_um2"] = float(whole.sum() * pixel_size**2) if pixel_size else None
        row["nucleolar_area_um2"] = float(enriched.sum() * pixel_size**2) if pixel_size else None
        for compartment, mask in [("nucleus", whole), ("nucleoli", enriched), ("nucleoplasm", plasma)]:
            row.update({f"ncl_{compartment}_{k}": v for k, v in region_values(channels["ncl"], mask, background["ncl"], legacy).items()})
        row.update({f"gfp_{k}": v for k, v in region_values(channels["gfp"], whole, background["gfp"], legacy).items()})
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
        cells.append(row)
        for label in np.unique(nucleoli[enriched]):
            mask = nucleoli == label
            objects.append({"field_id": field_id, "nucleus_id": int(nucleus), "nucleolus_id": int(label),
                            "area_px": int(mask.sum()), **region_values(channels["ncl"], mask, background["ncl"], legacy)})
    manual_rows = []
    if manual is not None:
        for label in np.unique(manual):
            if not label:
                continue
            row = {"field_id": field_id, "roi_id": int(label), "area_px": int((manual == label).sum())}
            for c, a in channels.items():
                row.update({f"{c}_{k}": v for k, v in region_values(a, manual == label, background[c], legacy).items()})
            manual_rows.append(row)
    return cells, objects, manual_rows

def apply_gfp_gate(rows, recipe: Recipe):
    if not rows:
        return []
    frame = pd.DataFrame(rows)
    thresholds = {}
    if recipe.gfp_gate == "otsu-batch":
        for date, group in frame.groupby("acquisition_date"):
            values = group.gfp_mean_corrected.dropna().to_numpy()
            thresholds[date] = float(threshold_otsu(values)) if len(values) > 1 and np.ptp(values) > 0 else None
    for row in rows:
        threshold = thresholds.get(row["acquisition_date"]) if recipe.gfp_gate == "otsu-batch" else recipe.gfp_threshold
        value = row["gfp_mean_corrected"]
        positive = True if recipe.gfp_gate == "none" else (value is not None and threshold is not None and value >= threshold)
        if recipe.gfp_maximum is not None:
            positive = positive and value is not None and value <= recipe.gfp_maximum
        row["gfp_positive"] = bool(positive)
        row["gfp_gate_threshold"] = threshold
        row["gfp_gate_method"] = recipe.gfp_gate
        row["gfp_gate_exploratory"] = recipe.gfp_gate == "otsu-batch"
    return rows
