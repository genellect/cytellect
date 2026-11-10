"""Per-nucleus nucleolar eccentricity.

Definitions are in docs/methods.md, "Compartment-summary selection 1.1.0". Uses
saved original-coordinate label images only; pixel values are not read.
"""
from __future__ import annotations

import math
from typing import TypedDict

import numpy as np
from scipy import ndimage

from .masks import validate_labels


class NucleolarShape(TypedDict):
    nucleolar_eccentricity: float | None
    objects: int
    measured_objects: int
    missing_reason: str | None


def object_eccentricity(rows: np.ndarray, columns: np.ndarray) -> float | None:
    """sqrt(1 − λmin/λmax) of the population covariance of pixel centres; None for one pixel."""
    coordinates = np.vstack([rows, columns]).astype(np.float64)
    covariance = np.cov(coordinates, bias=True) if coordinates.shape[1] > 1 else np.zeros((2, 2))
    low, high = np.linalg.eigvalsh(covariance)
    if high <= 0:
        return None
    return math.sqrt(min(1.0, max(0.0, 1.0 - max(low, 0.0) / high)))


def nucleolar_objects(nuclei: np.ndarray, nucleoli: np.ndarray) -> dict[int, list[int]]:
    """Nucleolus labels inside each parent nucleus, ascending; parents without one are absent."""
    inside = nucleoli > 0
    children: dict[int, list[int]] = {}
    if inside.any():
        pairs = np.unique(np.stack([nuclei[inside].astype(np.int64), nucleoli[inside].astype(np.int64)]), axis=1)
        for parent, child in pairs.T:
            children.setdefault(int(parent), []).append(int(child))
    return children


def _object_pixels(nucleoli: np.ndarray):
    """Return a function giving one object's pixel centres in original coordinates and C order.

    Labels are compacted before `find_objects`, so sparse 32-bit label values do not
    allocate one slot per possible value; each object is then read from its bounding box.
    """
    values, inverse = np.unique(nucleoli, return_inverse=True)
    if values.size and values[0] != 0:
        values, inverse = np.concatenate([[0], values]), inverse + 1
    compact = inverse.reshape(nucleoli.shape)
    boxes = ndimage.find_objects(compact)

    def pixels(label: int):
        index = int(np.searchsorted(values, label))
        box = boxes[index - 1]
        rows, columns = np.nonzero(compact[box] == index)
        return rows + box[0].start, columns + box[1].start
    return pixels


def nucleolar_eccentricity(nuclei: np.ndarray, nucleoli: np.ndarray) -> dict[int, NucleolarShape]:
    """Return one entry per nucleus label in `nuclei`, keyed by the parent nucleus ID."""
    validate_labels(nuclei, nucleoli)
    children = nucleolar_objects(nuclei, nucleoli)
    pixels = _object_pixels(nucleoli)
    shapes: dict[int, NucleolarShape] = {}
    for parent in (int(value) for value in np.unique(nuclei) if value):
        objects = children.get(parent, [])
        weighted, weight, measured = 0.0, 0, 0
        for label in objects:
            rows, columns = pixels(label)
            value = object_eccentricity(rows, columns)
            if value is None:
                continue
            weighted += value * rows.size
            weight += rows.size
            measured += 1
        reason = "no_nucleolus" if not objects else None if measured else "degenerate_objects"
        shapes[parent] = {"nucleolar_eccentricity": weighted / weight if measured else None,
                          "objects": len(objects), "measured_objects": measured, "missing_reason": reason}
    return shapes
