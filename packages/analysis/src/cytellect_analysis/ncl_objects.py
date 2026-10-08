"""Protocol 3.0.0: local-contrast, compact NCL objects in adopted nuclei.

Detection uses unchanged input code units and original-coordinate pixels.
The unbounded core is also used by the private trial reproduction; the product
entry point always supplies adopted nuclei. No image-size or LUT normalization.
"""
from typing import Literal

import numpy as np
from pydantic import Field, FiniteFloat, model_validator
from scipy import ndimage as ndi
from skimage.measure import regionprops
from skimage.morphology import closing, disk, opening, remove_small_holes

from .masks import validate_label_array
from .regions import RegionModel


class NclObjectDetector(RegionModel):
    engine: Literal["cytellect-ncl-objects"] = "cytellect-ncl-objects"
    protocol_version: Literal["3.0.0"] = "3.0.0"
    smoothing_sigma_px: FiniteFloat = Field(default=0.9, ge=0, le=10)
    background_radius_px: int = Field(default=10, ge=1, le=200)
    coarse_sigma_px: FiniteFloat = Field(default=1.5, gt=0, le=20)
    core_contrast: FiniteFloat = Field(default=36, ge=0, le=65535)
    core_coarse_contrast: FiniteFloat = Field(default=27, ge=0, le=65535)
    minimum_core_area_px: int = Field(default=6, ge=1, le=100000)
    local_crop_radius_px: int = Field(default=24, ge=2, le=200)
    background_inner_radius_px: int = Field(default=12, ge=1, le=200)
    background_outer_radius_px: int = Field(default=22, ge=2, le=200)
    background_signal_floor: FiniteFloat = Field(default=15, ge=0, le=65535)
    minimum_background_pixels: int = Field(default=40, ge=1, le=160000)
    peak_radius_px: int = Field(default=2, ge=1, le=20)
    minimum_peak_difference: FiniteFloat = Field(default=30, ge=0, le=65535)
    minimum_peak_ratio: FiniteFloat = Field(default=1.6, ge=1, le=100)
    boundary_fraction: FiniteFloat = Field(default=0.5, gt=0, lt=1)
    minimum_area_px: int = Field(default=28, ge=1, le=100000)
    maximum_area_px: int | None = Field(default=800, ge=1, le=16777216)
    minimum_solidity: FiniteFloat = Field(default=0.8, ge=0, le=1)
    minimum_circularity: FiniteFloat = Field(default=0.5, ge=0, le=1)
    hole_fill_max_px: int = Field(default=64, ge=0, le=100000)
    overlap_suppression_fraction: FiniteFloat = Field(default=0.5, gt=0, le=1)

    @model_validator(mode="after")
    def consistent(self):
        if self.maximum_area_px is not None and self.maximum_area_px < self.minimum_area_px:
            raise ValueError("nucleolar_area_range_invalid")
        if not self.peak_radius_px < self.background_inner_radius_px < self.background_outer_radius_px < self.local_crop_radius_px:
            raise ValueError("ncl_local_background_range_invalid")
        return self


def detect_ncl_objects(signal, parameters: NclObjectDetector, *, nuclei=None, valid=None):
    """Shared trial core. Without nuclei it is not a product analysis recipe."""
    p = NclObjectDetector.model_validate(parameters)
    if signal.ndim != 2 or signal.dtype not in (np.uint8, np.uint16):
        raise ValueError("compartment_source_shape_or_dtype_invalid")
    valid = np.ones(signal.shape, bool) if valid is None else np.asarray(valid, dtype=bool)
    if valid.shape != signal.shape:
        raise ValueError("compartment_source_shape_or_dtype_invalid")
    if nuclei is not None:
        validate_label_array(nuclei)
        if nuclei.shape != signal.shape:
            raise ValueError("compartment_source_shape_or_dtype_invalid")
    # Do not zero nuclear exterior: it would create an artificial nuclear rim.
    raw = signal.astype(float)
    raw[~valid] = 0
    smooth = ndi.gaussian_filter(raw, p.smoothing_sigma_px)
    contrast = np.maximum(smooth - opening(smooth, disk(p.background_radius_px)), 0)
    coarse = ndi.gaussian_filter(contrast, p.coarse_sigma_px)
    scopes = [0] if nuclei is None else [int(v) for v in np.unique(nuclei) if v]
    accepted, diagnostics, states = [], {}, {}
    structure = np.ones((3, 3), bool)
    for parent in scopes:
        inside = valid if nuclei is None else valid & (nuclei == parent)
        core = (contrast >= p.core_contrast) & (coarse >= p.core_coarse_contrast) & inside
        core = ndi.binary_opening(core, structure=disk(1))
        cores, _ = ndi.label(core, structure)
        candidates, rejected, seeds = [], [], 0
        for obj in regionprops(cores):
            if obj.area < p.minimum_core_area_px:
                continue
            coords = obj.coords
            sy, sx = coords[np.argmax(coarse[tuple(coords.T)])]
            seeds += 1
            radius = p.local_crop_radius_px
            y0, y1 = max(0, sy-radius), min(signal.shape[0], sy+radius+1)
            x0, x1 = max(0, sx-radius), min(signal.shape[1], sx+radius+1)
            yy, xx = np.mgrid[y0:y1, x0:x1]
            dist = np.sqrt((yy-sy)**2 + (xx-sx)**2)
            patch, scope = smooth[y0:y1, x0:x1], inside[y0:y1, x0:x1]
            annulus = (dist >= p.background_inner_radius_px) & (dist <= p.background_outer_radius_px) & (patch > p.background_signal_floor) & scope
            if annulus.sum() < p.minimum_background_pixels:
                rejected.append("insufficient_local_background")
                continue
            base = float(np.median(patch[annulus]))
            peak = float(np.median(patch[(dist <= p.peak_radius_px) & scope]))
            if peak-base < p.minimum_peak_difference or peak < p.minimum_peak_ratio*base:
                rejected.append("weak_peak_contrast")
                continue
            threshold = base + p.boundary_fraction*(peak-base)
            support = closing((patch >= threshold) & scope, disk(1)) & scope
            pieces, _ = ndi.label(support, structure)
            label = int(pieces[sy-y0, sx-x0])
            if not label:
                continue
            mask = pieces == label
            if mask[0].any() or mask[-1].any() or mask[:, 0].any() or mask[:, -1].any():
                rejected.append("open_or_cropped_boundary")
                continue
            if nuclei is not None and (mask & ~ndi.binary_erosion(scope, structure)).any():
                rejected.append("nuclear_boundary")
                continue
            mask = remove_small_holes(mask, max_size=p.hole_fill_max_px) & scope
            props = regionprops(mask.astype(np.uint8))[0]
            circularity = float(min(1., 4*np.pi*props.area/max(props.perimeter_crofton**2, 1)))
            if props.area < p.minimum_area_px or (p.maximum_area_px is not None and props.area > p.maximum_area_px):
                rejected.append("area")
                continue
            if props.solidity < p.minimum_solidity or circularity < p.minimum_circularity:
                rejected.append("noncompact")
                continue
            # Keep bounded candidate crops rather than one full-image array per seed.
            candidates.append({"mask": mask, "bbox": (y0, y1, x0, x1), "parent": parent,
                               "peak": peak, "background": base, "threshold": threshold})
        kept: list[dict] = []
        for candidate in sorted(candidates, key=lambda c: -(c["peak"]-c["background"])):
            def overlap(other):
                a, b = candidate["bbox"], other["bbox"]
                y0, y1, x0, x1 = max(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), min(a[3], b[3])
                if y0 >= y1 or x0 >= x1:
                    return 0
                return int((candidate["mask"][y0-a[0]:y1-a[0], x0-a[2]:x1-a[2]] & other["mask"][y0-b[0]:y1-b[0], x0-b[2]:x1-b[2]]).sum())
            overlaps = [(other, overlap(other)) for other in kept]
            if any(count/min(candidate["mask"].sum(), other["mask"].sum()) > p.overlap_suppression_fraction for other, count in overlaps):
                continue
            if any(count for _, count in overlaps):
                rejected.append("overlapping_ambiguous_objects")
                continue
            kept.append(candidate)
        accepted.extend(kept)
        states[parent] = "candidate" if kept else "indeterminate" if "insufficient_local_background" in rejected or "overlapping_ambiguous_objects" in rejected else "no_candidate"
        diagnostics[parent] = {"seeds": seeds, "candidates": len(kept), "rejections": rejected}
    out = np.zeros(signal.shape, np.uint32)
    parents, objects = {}, {}
    def centre(candidate):
        cy, cx = ndi.center_of_mass(candidate["mask"])
        return cy+candidate["bbox"][0], cx+candidate["bbox"][2]
    for index, candidate in enumerate(sorted(accepted, key=lambda c: centre(c)[0]), 1):
        y0, y1, x0, x1 = candidate["bbox"]
        out[y0:y1, x0:x1][candidate["mask"]] = index
        parents[index] = candidate["parent"]
        objects[index] = {"parent_id": candidate["parent"], "local_background": candidate["background"],
                          "peak": candidate["peak"], "threshold": candidate["threshold"]}
    return out, {"nucleolar_detector_protocol_version": p.protocol_version,
                 "nucleolar_definition_source": "ncl", "nucleolar_states": states,
                 "nucleolar_thresholds": diagnostics, "parent_ids": parents, "objects": objects,
                 "parameters": p.model_dump(mode="json"), "engine": p.engine,
                 "mask_meaning": "compact locally enriched NCL nucleolar candidates",
                 "measurement_pixels": "original, unchanged", "intensity_basis": "input code units",
                 "coordinate_transform": {"scale_x": 1, "scale_y": 1}}
