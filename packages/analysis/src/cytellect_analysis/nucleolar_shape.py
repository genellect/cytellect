"""Per-nucleus nucleolar eccentricity (WP3, implementation pending).

Definitions are in docs/methods.md, "Compartment-summary selection 1.1.0". Uses
saved original-coordinate label images only; pixel values are not read.
"""
from __future__ import annotations

from typing import TypedDict

import numpy as np


class NucleolarShape(TypedDict):
    nucleolar_eccentricity: float | None
    objects: int
    measured_objects: int
    missing_reason: str | None


def nucleolar_eccentricity(nuclei: np.ndarray, nucleoli: np.ndarray) -> dict[int, NucleolarShape]:
    """Return one entry per nucleus label in `nuclei`, keyed by the parent nucleus ID."""
    raise NotImplementedError("nucleolar_shape_not_implemented")
