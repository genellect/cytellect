"""Per-nucleus nucleolar eccentricity.

Definitions are in docs/methods.md, "Compartment-summary selection 1.1.0". Uses
saved original-coordinate label images only; pixel values are not read.
"""
from __future__ import annotations

import math
from typing import TypedDict

import numpy as np

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


def nucleolar_eccentricity(nuclei: np.ndarray, nucleoli: np.ndarray) -> dict[int, NucleolarShape]:
    """Return one entry per nucleus label in `nuclei`, keyed by the parent nucleus ID."""
    validate_labels(nuclei, nucleoli)
    shapes: dict[int, NucleolarShape] = {}
    for parent in (int(value) for value in np.unique(nuclei) if value):
        inside = nuclei == parent
        objects = [int(value) for value in np.unique(nucleoli[inside]) if value]
        weighted, weight, measured = 0.0, 0, 0
        for label in objects:
            rows, columns = np.nonzero(nucleoli == label)
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
