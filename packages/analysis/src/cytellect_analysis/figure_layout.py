"""Deterministic point placement for category plots (presentation only)."""
from __future__ import annotations

from bisect import bisect_left

import numpy as np


def beeswarm(values, *, dx: float, dy: float, half_width: float) -> np.ndarray:
    """Horizontal offsets that keep every point visible.

    ``dx`` and ``dy`` are one marker diameter in data units along x and y. Points are taken
    in value order and each takes the free offset closest to the centre. When a group is too
    dense for ``half_width``, all offsets are scaled down together, so the swarm keeps the
    shape of the distribution (wider where values are dense). The result depends only on
    the values and their order, never on a random seed.
    """
    values = np.asarray(values, dtype=float)
    offsets = np.zeros(len(values))
    if len(values) < 2 or dx <= 0 or dy <= 0:
        return offsets
    order = np.argsort(values, kind="stable")
    placed_y: list[float] = []
    placed_x: list[float] = []
    for index in order:
        y = values[index]
        start = bisect_left(placed_y, y - dy)
        neighbours = [(placed_x[k], placed_y[k]) for k in range(start, len(placed_y))]
        chosen = 0.0
        for step in range(0, 4 * len(values) + 1):
            candidate = ((step + 1) // 2) * dx * .5 * (1 if step % 2 else -1)
            if all((candidate - px) ** 2 / dx ** 2 + (y - py) ** 2 / dy ** 2 >= 1 for px, py in neighbours):
                chosen = candidate
                break
        offsets[index] = chosen
        position = bisect_left(placed_y, y)
        placed_y.insert(position, y)
        placed_x.insert(position, chosen)
    widest = float(np.max(np.abs(offsets)))
    if widest > half_width:
        offsets *= half_width / widest
    return offsets
