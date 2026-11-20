"""2D shape of each adopted region (nuclei or nucleoli): genellect/cytellect#257 E-1.

Definitions are in docs/methods.md, "Region shape 1.0.0". Uses saved original-coordinate label images only; pixel
values are not read. Each object's values come from its own pixels:

- area A: pixel count.
- perimeter P: Crofton estimate with 4 directions on the object's binary image (scikit-image ``perimeter_crofton``,
  ``directions=4``), in pixels. The estimator is fixed so that one version always measures the same way.
- circularity 4πA / P² (1 for a disc in the continuous limit; digitisation makes small objects deviate).
- solidity A / (pixel area of the object's convex hull image).
- axis ratio: major / minor axis of the ellipse with the same second moments (≥ 1); eccentricity sqrt(1 − λmin/λmax)
  of the same covariance, as the nucleolar eccentricity of compartment-summary selection 1.1.0.

An object below ``minimum_area_px``, one touching the image border, or one whose minor axis or perimeter is zero has
no shape values and keeps its reason (``below_minimum_area``, ``touches_border``, ``degenerate``); it is never set to
zero, and it still counts in numbers and areas elsewhere. The minimum is an explicit argument, recorded with the result,
because its value is to be set from the error measured on public real images (owner decision 5 of #257).
2D values are not volumes or sphericities.
"""
from __future__ import annotations

import math
from typing import Literal, TypedDict

import numpy as np

from .masks import validate_label_array

PROTOCOL: Literal["region-shape/1.0.0"] = "region-shape/1.0.0"
PERIMETER_ESTIMATOR: Literal["crofton-4"] = "crofton-4"


class RegionShape(TypedDict):
    region_id: int
    area_px: int
    perimeter_px: float | None
    circularity: float | None
    solidity: float | None
    axis_ratio: float | None
    eccentricity: float | None
    touches_border: bool
    missing_reason: Literal["below_minimum_area", "touches_border", "degenerate"] | None


class RegionShapes(TypedDict):
    protocol: Literal["region-shape/1.0.0"]
    perimeter_estimator: Literal["crofton-4"]
    minimum_area_px: int
    rows: list[RegionShape]


def region_shapes(labels: np.ndarray, *, minimum_area_px: int) -> RegionShapes:
    """One row per label (ascending). ``minimum_area_px`` (≥ 1) is the smallest area given shape values."""
    validate_label_array(labels)
    if isinstance(minimum_area_px, bool) or not isinstance(minimum_area_px, int) or minimum_area_px < 1:
        raise ValueError("region_shape_minimum_area_invalid")
    from skimage.measure import regionprops
    border = np.zeros(labels.shape, dtype=bool)
    border[0, :] = border[-1, :] = border[:, 0] = border[:, -1] = True
    touching = {int(value) for value in np.unique(labels[border]) if value}
    rows: list[RegionShape] = []
    for region in regionprops(labels.astype(np.int64)):
        rid, area = int(region.label), int(region.area)
        row: RegionShape = {"region_id": rid, "area_px": area, "perimeter_px": None, "circularity": None, "solidity": None,
                            "axis_ratio": None, "eccentricity": None, "touches_border": rid in touching, "missing_reason": None}
        if rid in touching:
            row["missing_reason"] = "touches_border"
        elif area < minimum_area_px:
            row["missing_reason"] = "below_minimum_area"
        else:
            perimeter = float(region.perimeter_crofton)
            major, minor = float(region.axis_major_length), float(region.axis_minor_length)
            if perimeter <= 0 or minor <= 0 or not math.isfinite(perimeter):
                row["missing_reason"] = "degenerate"
            else:
                row["perimeter_px"] = perimeter
                row["circularity"] = 4 * math.pi * area / perimeter ** 2
                row["solidity"] = area / float(region.area_convex)
                row["axis_ratio"] = major / minor
                row["eccentricity"] = float(region.eccentricity)
        rows.append(row)
    return {"protocol": PROTOCOL, "perimeter_estimator": PERIMETER_ESTIMATOR, "minimum_area_px": minimum_area_px, "rows": rows}
