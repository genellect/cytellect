"""Explicit display-RGB compatibility protocol; never used by native analysis."""
import math

import numpy as np
from scipy.stats import trim_mean
from skimage import filters, transform
from skimage import measure as regions


def legacy_shape(shape, recipe):
    scale = min(1., recipe.legacy.target_long_dimension_px / max(shape))
    return tuple(max(1, round(size * scale)) for size in shape)


def prepare_legacy_channels(channels, recipe):
    original_shape = tuple(channels["dapi"].shape)
    target = legacy_shape(original_shape, recipe)
    resized = {name: transform.resize(array, target, order=1, preserve_range=True, anti_aliasing=True)
               for name, array in channels.items()}
    detection = np.rint(resized["dapi"]).astype(channels["dapi"].dtype)
    return resized, detection, {"original_shape": list(original_shape), "measurement_shape": list(target),
                                "scale_y": target[0] / original_shape[0], "scale_x": target[1] / original_shape[1],
                                "image_resampling": "skimage.resize order1 preserve_range anti_aliasing",
                                "detection_rounding": "numpy.rint to source dtype",
                                "label_resampling": "nearest; preserve labels"}


def legacy_detection_input(channels, recipe):
    return prepare_legacy_channels(channels, recipe)[1]


def labels_to_original(labels, original_shape):
    return transform.resize(labels, original_shape, order=0, preserve_range=True, anti_aliasing=False).astype(np.uint32)


def labels_to_legacy(labels, recipe):
    return labels_to_original(labels, legacy_shape(labels.shape, recipe))


def _background(channels, nuclei):
    from .measurement import robust_sigma
    outside = nuclei == 0
    background = {name: float(np.median(array[outside])) if outside.any() else 0.
                  for name, array in channels.items()}
    sigma = {name: robust_sigma(array[outside]) if outside.any() else 0. for name, array in channels.items()}
    return background, sigma


def _high_region(values):
    if np.unique(values).size >= 2:
        threshold = float(filters.threshold_otsu(values))
        high = values > threshold
    else:
        threshold = float(values[0])
        high = np.ones(values.size, dtype=bool)
    fallback = int(high.sum()) < max(3, math.ceil(.01 * values.size))
    if fallback:
        high = values >= np.percentile(values, 90)
    return high, threshold, fallback


def detect_legacy_nucleoli(channels, nuclei_full, recipe):
    resized, _, _ = prepare_legacy_channels(channels, recipe)
    nuclei = labels_to_legacy(nuclei_full, recipe)
    background, _ = _background(resized, nuclei)
    corrected = np.maximum(resized["ncl"] - background["ncl"], 0.)
    labels = np.zeros(nuclei.shape, dtype=np.uint32)
    next_label = 1
    statuses = []
    for label in np.unique(nuclei):
        if not label:
            continue
        whole = nuclei == label
        values = corrected[whole]
        high, threshold, fallback = _high_region(values)
        mask = np.zeros(nuclei.shape, dtype=bool)
        mask[whole] = high
        components = regions.label(mask, connectivity=2)
        for component in np.unique(components):
            if component:
                labels[components == component] = next_label
                next_label += 1
        statuses.append({"nucleus_id": int(label), "status": "legacy_candidate",
                         "otsu_threshold": threshold, "fallback_top10": fallback,
                         "uniform_all_high": bool(np.unique(values).size < 2),
                         "definition": "legacy corrected-NCL Otsu with explicit historical fallback"})
    full = labels_to_original(labels, nuclei_full.shape)
    # Canonical nuclei may have manual outlines finer than the legacy measurement grid.
    expected_parent = labels_to_original(np.where(labels > 0, nuclei, 0), nuclei_full.shape)
    full[expected_parent != nuclei_full] = 0
    return full, statuses


def _gini(values):
    values = np.sort(np.asarray(values, dtype=float))
    total = values.sum()
    if total <= 0:
        return 0.
    rank = np.arange(1, len(values)+1)
    return float((2*np.sum(rank*values)/(len(values)*total)) - (len(values)+1)/len(values))


def measure_legacy(channels, nuclei_full, nucleoli_full, recipe, metadata, field_id, manual_full=None):
    from .masks import validate_labels
    from .measurement import region_values

    validate_labels(nuclei_full, nucleoli_full)
    resized, _, coordinate = prepare_legacy_channels(channels, recipe)
    nuclei = labels_to_legacy(nuclei_full, recipe)
    nucleoli = labels_to_legacy(nucleoli_full, recipe)
    manual = labels_to_legacy(manual_full, recipe) if manual_full is not None else np.zeros_like(nuclei)
    validate_labels(nuclei, nucleoli)
    if (set(np.unique(nuclei_full)) - {0}) - set(np.unique(nuclei)):
        raise ValueError("legacy_nucleus_vanished_at_measurement_scale")
    background, sigma = _background(resized, nuclei)
    epsilon = max(sigma["ncl"], 1.)
    border_ids = set(np.unique(np.concatenate([nuclei[0], nuclei[-1], nuclei[:, 0], nuclei[:, -1]])))
    dapi_max = 255. if np.max(resized["dapi"]) <= 255 else float(np.max(resized["dapi"]))
    cells, objects, manual_rows = [], [], []
    for nucleus in np.unique(nuclei):
        if not nucleus:
            continue
        whole = nuclei == nucleus
        enriched = whole & (nucleoli > 0)
        plasma = whole & ~enriched
        whole_full = nuclei_full == nucleus
        enriched_full = whole_full & (nucleoli_full > 0)
        area = int(whole.sum())
        ncl_values = np.maximum(resized["ncl"][whole] - background["ncl"], 0.)
        dapi_snr = float((np.mean(resized["dapi"][whole])-background["dapi"])/max(sigma["dapi"], 1e-6))
        saturation = float(np.mean(resized["dapi"][whole] >= dapi_max))
        area_pass = recipe.legacy.nucleus_area_min_scaled_px <= area <= recipe.legacy.nucleus_area_max_scaled_px
        quality = (nucleus not in border_ids and area_pass and dapi_snr >= recipe.legacy.dapi_snr_min
                   and saturation <= recipe.legacy.saturation_fraction_max and area >= 20)
        row = {**metadata, "field_id": field_id, "nucleus_id": int(nucleus),
               "recipe_id": recipe.id, "recipe_version": recipe.version,
               "legacy_protocol_version": recipe.legacy.version, "measurement_grid": "legacy-downsampled",
               "measurement_shape": coordinate["measurement_shape"], "measurement_scale_x": coordinate["scale_x"],
               "measurement_scale_y": coordinate["scale_y"], "integral_unit": "intensity * scaled pixel",
               "nucleus_area_px": int(whole_full.sum()), "nucleolar_area_px": int(enriched_full.sum()),
               "legacy_nucleus_area_scaled_px": area, "legacy_nucleolar_area_scaled_px": int(enriched.sum()),
               "nucleolar_count": int(len(np.unique(nucleoli[enriched]))),
               "nucleolar_area_fraction": float(enriched.sum()/area),
               "nucleolar_status": "legacy_candidate" if enriched.any() else "none_after_edit",
               "touches_border": bool(nucleus in border_ids), "legacy_area_qc_pass": bool(area_pass),
               "dapi_snr": dapi_snr, "independent_nucleus_qc_pass": bool(quality),
               "excluded": bool(recipe.legacy.apply_quality_exclusions and not quality),
               "exclusion_reason": "legacy_independent_nucleus_qc" if recipe.legacy.apply_quality_exclusions and not quality else "",
               "gfp_positive": True, "legacy_epsilon": epsilon,
               "ncl_nucleoplasm_over_nucleoli": None, "ncl_log2_nucleoplasm_over_nucleoli": None,
               "ratio_missing_reason": "native_ratio_not_defined_in_legacy"}
        pixel_size = metadata.get("pixel_size_um")
        row["nucleus_area_um2"] = float(whole_full.sum()*pixel_size**2) if pixel_size else None
        row["nucleolar_area_um2"] = float(enriched_full.sum()*pixel_size**2) if pixel_size else None
        for compartment, mask in (("nucleus", whole), ("nucleoli", enriched), ("nucleoplasm", plasma)):
            row.update({f"ncl_{compartment}_{key}": value for key, value in
                        region_values(resized["ncl"], mask, background["ncl"], legacy=True).items()})
        row.update({f"gfp_{key}": value for key, value in
                    region_values(resized["gfp"], whole, background["gfp"], legacy=True).items()})
        for name in channels:
            row[f"{name}_background"] = background[name]
            row[f"{name}_background_sigma"] = sigma[name]
            row[f"{name}_saturation_fraction"] = float(np.mean(resized[name][whole] >= np.iinfo(channels[name].dtype).max))
        row["dapi_saturation_fraction"] = saturation
        high, threshold, fallback = _high_region(ncl_values)
        row["legacy_high_otsu_threshold"] = threshold
        row["legacy_high_fallback_top10"] = fallback
        row["legacy_high_uniform_all_pixels"] = bool(np.unique(ncl_values).size < 2)
        row["legacy_high_mask_modified"] = not np.array_equal(enriched[whole], high)
        high_mean = row["ncl_nucleoli_mean_corrected"]
        row["ncl_legacy_release"] = math.log2((float(ncl_values.mean())+epsilon)/(high_mean+epsilon)) if high_mean is not None else None
        row["legacy_release_missing_reason"] = "" if high_mean is not None else "no_high_region_after_edit"
        row["ncl_legacy_dispersion_log2_median_over_mean"] = math.log2((float(np.median(ncl_values))+epsilon)/(float(np.mean(ncl_values))+epsilon))
        row["ncl_legacy_trimmed_dispersion_log2"] = math.log2((float(trim_mean(ncl_values, .1))+epsilon)/(float(np.mean(ncl_values))+epsilon))
        row["ncl_legacy_gini"] = _gini(ncl_values)
        for percentile in (5, 10, 20):
            subset = ncl_values[ncl_values >= np.percentile(ncl_values, 100-percentile)]
            row[f"ncl_legacy_top{percentile}_release"] = math.log2((float(ncl_values.mean())+epsilon)/(float(subset.mean())+epsilon))
        cells.append(row)
        for label in np.unique(nucleoli[enriched]):
            mask = nucleoli == label
            objects.append({"field_id": field_id, "nucleus_id": int(nucleus), "nucleolus_id": int(label),
                            "area_px": int((nucleoli_full == label).sum()), "area_scaled_px": int(mask.sum()),
                            "measurement_grid": "legacy-downsampled",
                            **region_values(resized["ncl"], mask, background["ncl"], legacy=True)})
    for label in np.unique(manual):
        if not label:
            continue
        mask = manual == label
        row = {"field_id": field_id, "roi_id": int(label), "area_px": int((manual_full == label).sum()),
               "area_scaled_px": int(mask.sum()), "measurement_grid": "legacy-downsampled"}
        for name, array in resized.items():
            row.update({f"{name}_{key}": value for key, value in
                        region_values(array, mask, background[name], legacy=True).items()})
        manual_rows.append(row)
    return cells, objects, manual_rows


def apply_legacy_gfp_gate(rows, recipe):
    from collections import defaultdict
    batches = defaultdict(list)
    for row in rows:
        if row.get("independent_nucleus_qc_pass"):
            value = row["gfp_mean_corrected"]
            if value is not None and np.isfinite(value) and value >= 0:
                batches[row["acquisition_date"]].append(value)
    thresholds = {}
    for batch, values in batches.items():
        thresholds[batch] = float(filters.threshold_otsu(np.asarray(values))) if np.unique(values).size >= 2 else float(np.median(values))
    for row in rows:
        value = row["gfp_mean_corrected"]
        threshold = thresholds.get(row["acquisition_date"])
        selected = value is not None and threshold is not None and value >= threshold
        if recipe.gfp_maximum is not None:
            selected = selected and value <= recipe.gfp_maximum
        row["gfp_positive"] = bool(selected)
        row["gfp_gate_threshold"] = threshold
        row["gfp_gate_maximum"] = recipe.gfp_maximum
        row["gfp_gate_method"] = "legacy-otsu-on-independent-qc-nuclei"
        row["gfp_gate_exploratory"] = True
        row["gfp_selection_reason"] = "included" if selected else ("no_qc_nuclei_in_batch" if threshold is None else "outside_gfp_gate")
        row["gfp_positive_threshold_low"] = bool(value is not None and threshold is not None and value >= .75*threshold)
        row["gfp_positive_threshold_high"] = bool(value is not None and threshold is not None and value >= 1.25*threshold)
        row["gfp_log2_plus1"] = math.log2(max(value, 0)+1) if value is not None else None
    centers = defaultdict(list)
    for row in rows:
        if row["gfp_positive"] and not row["excluded"]:
            centers[row["acquisition_date"]].append(row["gfp_log2_plus1"])
    for row in rows:
        values = centers[row["acquisition_date"]]
        row["gfp_log2_date_centered"] = row["gfp_log2_plus1"] - float(np.median(values)) if values else None
    return rows
