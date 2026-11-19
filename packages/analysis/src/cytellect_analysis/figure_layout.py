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
    # Candidate offsets in the order they are tried: 0, +dx/2, -dx/2, +dx, -dx, ...
    steps = np.arange(0, 4 * len(values) + 1)
    candidates = ((steps + 1) // 2) * dx * .5 * np.where(steps % 2, 1, -1)
    batch = 64
    for index in order:
        y = values[index]
        start = bisect_left(placed_y, y - dy)
        chosen = 0.0
        if start == len(placed_y):
            chosen = float(candidates[0])
        else:
            # The same test as for one candidate at a time, for a batch of candidates against every neighbour.
            near_x = np.asarray(placed_x[start:])
            vertical = (y - np.asarray(placed_y[start:])) ** 2 / dy ** 2
            for first in range(0, len(candidates), batch):
                tried = candidates[first:first + batch]
                free = np.all((tried[:, None] - near_x[None, :]) ** 2 / dx ** 2 + vertical[None, :] >= 1, axis=1)
                if free.any():
                    chosen = float(tried[int(np.argmax(free))])
                    break
        offsets[index] = chosen
        position = bisect_left(placed_y, y)
        placed_y.insert(position, y)
        placed_x.insert(position, chosen)
    widest = float(np.max(np.abs(offsets)))
    if widest > half_width:
        offsets *= half_width / widest
    return offsets
