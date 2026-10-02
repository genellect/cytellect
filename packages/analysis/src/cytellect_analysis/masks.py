"""Raster labels are canonical; polygons are edit inputs/display derivatives."""
import numpy as np
from scipy import ndimage as ndi
from skimage import draw, filters, measure, morphology, segmentation
from .contracts import MaskEdit, Recipe

def polygon_mask(shape, polygon):
    p = np.asarray(polygon, dtype=float)
    if p.ndim != 2 or p.shape[1] != 2 or len(p) < 3 or not np.isfinite(p).all():
        raise ValueError("invalid_polygon")
    if (p < 0).any() or (p[:, 0] > shape[1]).any() or (p[:, 1] > shape[0]).any():
        raise ValueError("polygon_outside_image")
    mask = draw.polygon2mask(shape, p[:, ::-1] - 0.5)
    if not mask.any():
        raise ValueError("empty_polygon")
    return mask

def validate_labels(nuclei, nucleoli):
    if nuclei.shape != nucleoli.shape or (nuclei < 0).any() or (nucleoli < 0).any():
        raise ValueError("invalid_label_shapes")
    for label in np.unique(nucleoli):
        if label == 0:
            continue
        parents = np.unique(nuclei[nucleoli == label])
        if len(parents) != 1 or parents[0] == 0:
            raise ValueError("nucleolus_requires_single_parent")

def detect_nucleoli(nuclei, ncl, dapi, recipe: Recipe):
    signal = ncl if recipe.nucleolar_method == "ncl-otsu" else dapi
    detection = filters.gaussian(signal, sigma=recipe.smoothing_sigma_px, preserve_range=True) if recipe.smoothing_sigma_px else signal.astype(float)
    labels = np.zeros_like(nuclei, dtype=np.uint32)
    states = {}
    next_id = 1
    for nucleus in np.unique(nuclei):
        if nucleus == 0:
            continue
        region = nuclei == nucleus
        values = detection[region]
        if np.ptp(values) <= 0:
            states[int(nucleus)] = "indeterminate"
            continue
        if recipe.nucleolar_method == "ncl-otsu":
            candidate = region & (detection > filters.threshold_otsu(values))
        else:
            candidate = region & (detection < np.percentile(values, recipe.dapi_low_percentile))
        candidate = morphology.remove_small_objects(candidate, min_size=recipe.minimum_area_px)
        if recipe.split_touching and candidate.any():
            distance = ndi.distance_transform_edt(candidate)
            maxima = morphology.local_maxima(distance) & candidate
            markers = measure.label(maxima)
            components = segmentation.watershed(-distance, markers, mask=candidate)
        else:
            components = measure.label(candidate, connectivity=2)
        for component in range(1, int(components.max()) + 1):
            if (components == component).sum() >= recipe.minimum_area_px:
                labels[components == component] = next_id
                next_id += 1
        states[int(nucleus)] = "candidate" if (labels[region] > 0).any() else "none"
    return labels, states

def contours(labels):
    result = []
    for region in measure.regionprops(labels.astype(np.int32)):
        y0, x0, y1, x1 = region.bbox
        local = np.pad(labels[y0:y1, x0:x1] == region.label, 1)
        for contour in measure.find_contours(local.astype(float), .5):
            points = [[float(x + x0 - .5), float(y + y0 - .5)] for y, x in contour]
            result.append({"id": int(region.label), "points": points})
    return result

def apply_edit(nuclei, nucleoli, manual, edit: MaskEdit):
    nuclei, nucleoli, manual = nuclei.copy(), nucleoli.copy(), manual.copy()
    layer = {"nuclei": nuclei, "nucleoli": nucleoli, "manual": manual}[edit.layer]
    available = set(np.unique(layer)) - {0}
    if any(i not in available for i in edit.ids):
        raise ValueError("unknown_label")
    before = nuclei.copy()
    if edit.operation in ("add", "replace"):
        selected = polygon_mask(layer.shape, edit.polygon)
        if edit.operation == "replace" and len(edit.ids) != 1:
            raise ValueError("replace_requires_one_label")
        target = edit.ids[0] if edit.operation == "replace" else int(layer.max()) + 1
        if (selected & (layer > 0) & (layer != target)).any():
            raise ValueError("overlap_requires_explicit_merge")
        if edit.layer == "nucleoli" and (edit.parent_id is None or (selected & (nuclei != edit.parent_id)).any()):
            raise ValueError("nucleolus_outside_parent")
        layer[layer == target] = 0
        layer[selected] = target
    elif edit.operation == "delete":
        if not edit.ids:
            raise ValueError("select_labels")
        layer[np.isin(layer, edit.ids)] = 0
    elif edit.operation == "merge":
        if len(edit.ids) < 2:
            raise ValueError("merge_requires_multiple_labels")
        layer[np.isin(layer, edit.ids)] = min(edit.ids)
    elif edit.operation == "split":
        if len(edit.ids) != 1:
            raise ValueError("split_requires_one_label")
        selected = polygon_mask(layer.shape, edit.polygon) & (layer == edit.ids[0])
        if not selected.any() or np.array_equal(selected, layer == edit.ids[0]):
            raise ValueError("split_requires_partial_region")
        layer[selected] = int(layer.max()) + 1
    if edit.layer == "nuclei":
        changed = before != nuclei
        affected = set(np.unique(before[changed])) | set(np.unique(nuclei[changed]))
        # Invalidate all child regions of touched parents, even outside changed pixels.
        invalid = np.isin(before, list(affected - {0})) | np.isin(nuclei, list(affected - {0}))
        nucleoli[invalid] = 0
    validate_labels(nuclei, nucleoli)
    return nuclei, nucleoli, manual
