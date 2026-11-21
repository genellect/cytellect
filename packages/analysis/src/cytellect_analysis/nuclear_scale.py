"""Automatic nuclear detection scale (protocols nuclear-size/1.0.0 and 1.1.0).

StarDist 2D "Versatile (fluorescent nuclei)" segments nuclei of the size range of
its training images; much larger nuclei are split into their internal texture
(Schmidt et al., MICCAI 2018; the StarDist documentation advises matching object
size to the training data). High-resolution images such as Airyscan therefore
need a smaller detection copy. This module estimates the typical nucleus
diameter from the nuclear channel and chooses the detection copy so that this
diameter becomes about ``TARGET_DIAMETER_PX``. Measurements always use the
original pixels; small images are never enlarged.

The estimate is a coarse foreground (block mean to a <=512 px grid, Gaussian
smoothing, Otsu threshold, hole filling) and the equivalent diameter of the
area-weighted median component, weighted by area so that small bright specks do not dominate. Touching nuclei that merge enlarge the estimate; the median and
the tolerance of the detector keep that bounded, and the researcher can always
choose an explicit detection size instead.

Protocol 1.1.0 (2026-11-21) subtracts the large-scale background of the smoothed grid
(grey opening with a square whose side is a quarter of the grid's long side) before
the Otsu threshold. Under 1.0.0, a field whose nuclear channel carries a background
that varies across the field by more than the nuclear contrast (uneven illumination,
out-of-focus or mounting-medium fluorescence) is thresholded into one component that
spans much of the field; its size became the "typical nucleus" and the detection copy
shrank to the minimum side, so StarDist returned one nucleus for the whole field
(public DS6b fields, docs/public-nucleolar-shape-validation.md). Structures narrower
than the square are kept; 1.0.0 records replay with the 1.0.0 estimate.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import ndimage as ndi
from skimage.filters import gaussian, threshold_otsu
from skimage.transform import downscale_local_mean

PROTOCOL_1_0 = "nuclear-size/1.0.0"
PROTOCOL = "nuclear-size/1.1.0"
PROTOCOLS = (PROTOCOL_1_0, PROTOCOL)
BACKGROUND_FRACTION = 0.25  # 1.1.0: opening square side / grid long side
TARGET_DIAMETER_PX = 40  # within the range that segmented both test sets correctly (24-40)
ESTIMATE_GRID_SIDE = 512
MINIMUM_COMPONENT_AREA = 16  # grid pixels; removes debris and noise specks
SMOOTHING_SIGMA = 2.0  # grid pixels; merges chromatin texture inside a nucleus
MINIMUM_DETECTION_SIDE = 64
MAXIMUM_DETECTION_SIDE = 2048


def background_opening_side(grid_shape: tuple[int, ...]) -> int:
    """Odd side (grid px) of the 1.1.0 background opening: at least a quarter of the grid's long side."""
    return max(3, 2 * math.ceil(max(grid_shape) * BACKGROUND_FRACTION / 2) + 1)


def estimate_nuclear_diameter(image: np.ndarray, protocol: str = PROTOCOL) -> dict:
    """Median equivalent diameter (original pixels) of coarse nuclear foreground components."""
    if not isinstance(image, np.ndarray) or image.ndim != 2 or min(image.shape) < 1:
        raise ValueError("nuclear_scale_input_invalid")
    if protocol not in PROTOCOLS:
        raise ValueError("nuclear_scale_protocol_invalid")
    factor = max(1, math.ceil(max(image.shape) / ESTIMATE_GRID_SIDE))
    grid = downscale_local_mean(image.astype(np.float64), (factor, factor))
    smooth = gaussian(grid, sigma=SMOOTHING_SIGMA, preserve_range=True)
    record = {"protocol": protocol, "grid_factor": factor, "threshold": None, "components": 0,
              "diameter_px": None, "missing_reason": None}
    if protocol != PROTOCOL_1_0:
        side = background_opening_side(smooth.shape)
        smooth = smooth - ndi.grey_opening(smooth, size=(side, side), mode="nearest")
        record["background_opening_side_grid_px"] = side
    if float(smooth.max()) == float(smooth.min()):
        record["missing_reason"] = "uniform_image"
        return record
    threshold = float(threshold_otsu(smooth))
    foreground = ndi.binary_fill_holes(smooth > threshold)
    labels, count = ndi.label(foreground)
    areas = np.bincount(labels.ravel())[1:] if count else np.array([], dtype=np.int64)
    areas = areas[areas >= MINIMUM_COMPONENT_AREA]
    record.update({"threshold": threshold, "components": int(areas.size)})
    if not areas.size:
        record["missing_reason"] = "no_foreground_component"
        return record
    # Area-weighted median: the component size that covers half of the foreground,
    # so bright specks inside or between nuclei cannot pull the estimate down.
    ordered = np.sort(areas)
    typical = float(ordered[np.searchsorted(np.cumsum(ordered), ordered.sum() / 2.0)])
    record["diameter_px"] = float(2.0 * math.sqrt(typical / math.pi) * factor)
    return record


def automatic_detection_max_side(shape: tuple[int, int], diameter_px: float | None) -> int | None:
    """Detection long side that brings the estimated diameter to the target, or None (no extra scaling)."""
    if diameter_px is None or not math.isfinite(diameter_px) or diameter_px <= 0:
        return None
    side = round(max(shape) * TARGET_DIAMETER_PX / diameter_px)
    if side >= max(shape):
        return None  # nuclei are already small enough; never enlarge
    return int(min(MAXIMUM_DETECTION_SIDE, max(MINIMUM_DETECTION_SIDE, side)))
