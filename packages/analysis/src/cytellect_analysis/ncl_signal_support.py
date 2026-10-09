"""Versioned conservative boundary refinement of parent-bound model instances.

Signal alone never creates an object. Unmatched model instances are retained;
only supported, enriched components join/extend existing model anchors.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi
from skimage.filters import threshold_multiotsu
from skimage.morphology import disk, h_maxima
from skimage.segmentation import watershed

from .masks import validate_label_array

SUPPORT_POLICY = {
    "protocol_version": "1.0.0",
    "smoothing_sigma_px": 0.9,
    "crop_padding_px": 24,
    "threshold": "upper_threshold_three_class_multiotsu_per_parent",
    "closing_disk_radius_px": 2,
    "fill_holes": True,
    "connectivity": 8,
    "watershed": "negative_euclidean_distance",
    "peak_h_fraction": 0.15,
    "peak_h_minimum_px": 1,
    "minimum_anchor_overlap_fraction": 0.5,
    "maximum_parent_coverage": 0.5,
    "local_background_dilation_iterations": 8,
    "local_background_connectivity": 4,
    "enrichment": "original_mean_object_greater_than_original_mean_local_background",
    "boundary_erosion_connectivity": 4,
    "policy": "retain_model_pixels_union_matching_support_split_disconnected_objects",
    "parameter_units": "original_image_pixels",
}


def refine_ncl_signal_support(image: np.ndarray, anchors: np.ndarray,
                              nuclei: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict]:
    """Keep canonical parent masks and original measurement pixels immutable."""
    validate_label_array(anchors)
    validate_label_array(nuclei)
    if image.ndim != 2 or image.dtype not in (np.uint8, np.uint16) or not image.size:
        raise ValueError("cellpose_input_invalid")
    if image.shape != anchors.shape or image.shape != nuclei.shape:
        raise ValueError("cellpose_parent_shape_invalid")
    for ident in (int(v) for v in np.unique(anchors) if v):
        parents = np.unique(nuclei[anchors == ident])
        if len(parents) != 1 or not parents[0]:
            raise ValueError("cellpose_refinement_anchor_parent_invalid")

    # Smooth before restricting to any parent: no artificial dark nuclear rim.
    smooth = ndi.gaussian_filter(image.astype(np.float32), 0.9)
    output = np.zeros(anchors.shape, np.uint32)
    support_labels = np.zeros(anchors.shape, np.uint32)
    objects: dict[int, dict] = {}
    parent_ids: dict[int, int] = {}
    records = []
    next_id, next_support = 1, 1
    boxes = ndi.find_objects(nuclei)
    for parent in (int(v) for v in np.unique(nuclei) if v):
        box = boxes[parent - 1]
        assert box is not None
        y0, y1 = max(0, box[0].start - 24), min(image.shape[0], box[0].stop + 24)
        x0, x1 = max(0, box[1].start - 24), min(image.shape[1], box[1].stop + 24)
        scope = nuclei[y0:y1, x0:x1] == parent
        source = anchors[y0:y1, x0:x1].copy()
        source[~scope] = 0
        ids = [int(v) for v in np.unique(source) if v]
        if not ids:
            records.append({"parent_id": parent, "status": "no_model_anchor"})
            continue
        values = smooth[y0:y1, x0:x1]
        original = image[y0:y1, x0:x1]
        accepted: list[dict] = []
        grown = np.zeros(source.shape, np.uint32)
        record: dict = {"parent_id": parent, "crop_yxyx": [y0, y1, x0, x1], "segments": []}
        try:
            threshold = float(threshold_multiotsu(values[scope], classes=3)[-1])
        except ValueError:
            # A constant/insufficient-class support image cannot refine a model
            # object. Preserve its mask; do not manufacture a whole-nucleus ROI.
            record["status"] = "insufficient_signal_classes"
        else:
            record.update({"status": "evaluated", "upper_threshold": threshold})
            support = (values >= threshold) & scope
            support = ndi.binary_closing(support, structure=disk(2)) & scope
            support = ndi.binary_fill_holes(support) & scope
            components, count = ndi.label(support, np.ones((3, 3), bool))
            for component in range(1, count + 1):
                member = components == component
                distance = ndi.distance_transform_edt(member)
                peaks = h_maxima(distance, max(1, float(distance.max()) * 0.15)) & member
                markers, _ = ndi.label(peaks)
                segments = watershed(-distance, markers, mask=member)
                for segment in (int(v) for v in np.unique(segments) if v):
                    mask = segments == segment
                    overlapped = [int(v) for v in np.unique(source[mask]) if v]
                    linked = [v for v in overlapped
                              if np.count_nonzero(mask & (source == v)) / np.count_nonzero(source == v) >= 0.5]
                    if not linked:
                        continue
                    boundary = bool((mask & ~ndi.binary_erosion(scope)).any())
                    coverage = float(mask.sum() / scope.sum())
                    ring = ndi.binary_dilation(mask, iterations=8) & ~support & scope
                    enriched = bool(ring.any() and original[mask].mean() > original[ring].mean())
                    item: dict = {"source_ids": linked, "area": int(mask.sum()), "parent_coverage": coverage,
                            "nuclear_boundary": boundary, "enriched": enriched}
                    record["segments"].append(item)
                    if boundary or coverage > 0.5 or not enriched:
                        continue
                    grown[mask] = next_support
                    support_labels[y0:y1, x0:x1][mask] = next_support
                    item["support_id"] = next_support
                    accepted.append(item)
                    next_support += 1

        # Transitive anchor groups: an accepted cohesive body may join model
        # fragments. Other bodies/unmatched model anchors remain independent.
        groups = {ident: {ident} for ident in ids}
        for item in accepted:
            group_links = set(item["source_ids"])
            for ident in item["source_ids"]:
                group_links.update(groups[ident])
            for ident in group_links:
                groups[ident] = group_links
        seen: set[int] = set()
        for ident in ids:
            group = groups[ident]
            if ident in seen:
                continue
            seen.update(group)
            membership = np.isin(source, sorted(group))
            mask = membership & scope
            attached = []
            for item in accepted:
                if set(item["source_ids"]) & group:
                    mask |= (grown == item["support_id"]) & ((source == 0) | membership) & scope
                    attached.append(item["support_id"])
            pieces, count = ndi.label(mask, np.ones((3, 3), bool))
            for component in range(1, count + 1):
                member = pieces == component
                if ((output[y0:y1, x0:x1] > 0) & member).any():
                    raise ValueError("cellpose_refinement_overlap_invalid")
                output[y0:y1, x0:x1][member] = next_id
                parent_ids[next_id] = parent
                objects[next_id] = {"parent_id": parent, "source_anchor_ids": sorted(group),
                                    "support_ids": attached, "component": component,
                                    "area": int(member.sum())}
                next_id += 1
        records.append(record)
    return output, support_labels, {"parent_ids": parent_ids, "objects": objects,
                                    "signal_support_policy": dict(SUPPORT_POLICY),
                                    "signal_support_parents": records}
