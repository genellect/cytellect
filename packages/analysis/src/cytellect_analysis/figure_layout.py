"""Deterministic point placement for category plots (presentation only)."""
from __future__ import annotations

from collections import deque

import numpy as np


def beeswarm(values, *, dx: float, dy: float, half_width: float) -> np.ndarray:
    """Horizontal offsets that keep every point visible.

    ``dx`` and ``dy`` are one marker diameter in data units along x and y. Points are taken
    in value order and each takes the free offset closest to the centre. Where a row of values is
    too dense for ``half_width``, only that row is narrowed: each point takes the factor of the
    points within one diameter of its value, so sparse values keep their spacing and the swarm keeps
    the shape of the distribution (genellect/cytellect#257, owner decision 2026-11-21; narrowing every
    point by the densest row's factor drew sparse values as a thin column). The result depends only
    on the values and their order, never on a random seed.
    """
    values = np.asarray(values, dtype=float)
    offsets = np.zeros(len(values))
    if len(values) < 2 or dx <= 0 or dy <= 0:
        return offsets
    order = np.argsort(values, kind="stable")
    # Points are placed in value order, so the placed values stay sorted and the neighbours of a
    # point (those within one diameter below it) are a window that only moves upwards.
    placed_y = np.empty(len(values))
    placed_x = np.empty(len(values))
    half = dx * .5
    limit = 2 * len(values)  # the farthest offset tried, in half diameters
    start = 0
    for count, index in enumerate(order):
        y = values[index]
        while start < count and placed_y[start] < y - dy:
            start += 1
        px = placed_x[start:count]
        rise = (y - placed_y[start:count]) ** 2 / dy ** 2
        chosen = 0.0
        if len(px):
            # Each neighbour covers an interval of offsets; the half-diameter steps inside it are skipped
            # at once (those at its very edge are left to the exact test below), which keeps the work
            # per point proportional to its neighbours instead of their square.
            reach = dx * np.sqrt(np.clip(1 - rise, 0, None))
            first = np.ceil((px - reach) / half + 1e-6).astype(np.int64)
            last = np.floor((px + reach) / half - 1e-6).astype(np.int64)
            # Two steps past the farthest interval: the step at an interval's edge can still fail the
            # exact test by rounding, the one after it cannot.
            span = int(min(limit, max(int(np.abs(first).max()), int(np.abs(last).max())) + 2))
            covered = first <= last
            marks = np.zeros(2 * span + 2, dtype=np.int64)
            np.add.at(marks, np.clip(first[covered], -span, span) + span, 1)
            np.add.at(marks, np.clip(last[covered], -span, span) + span + 1, -1)
            taken = np.cumsum(marks)[:-1] > 0
            # Nearest the centre first: 0, +1, −1, +2, −2, … half diameters.
            steps = np.zeros(2 * span + 1, dtype=np.int64)
            steps[1::2] = np.arange(1, span + 1)
            steps[2::2] = -np.arange(1, span + 1)
            for step in steps[~taken[steps + span]]:
                candidate = abs(int(step)) * dx * .5 * (1 if step > 0 else -1)
                if np.all((candidate - px) ** 2 / dx ** 2 + rise >= 1):
                    chosen = candidate
                    break
        offsets[index] = chosen
        placed_y[count] = y
        placed_x[count] = chosen
    return _narrow_dense_rows(values, offsets, dy=dy, half_width=half_width)


def _narrow_dense_rows(values: np.ndarray, offsets: np.ndarray, *, dy: float, half_width: float) -> np.ndarray:
    """Scale each point by ``half_width`` over the widest offset among the points within ``dy`` of its value."""
    spread = np.abs(offsets)
    if not len(values) or float(spread.max()) <= half_width:
        return offsets
    order = np.argsort(values, kind="stable")
    ordered, width = values[order], spread[order]
    low = np.searchsorted(ordered, ordered - dy, side="left")
    high = np.searchsorted(ordered, ordered + dy, side="right")
    # Both window edges only move upwards, so a decreasing queue gives each window's widest offset.
    widest = np.empty(len(ordered))
    queue: deque[int] = deque()
    end = 0
    for index in range(len(ordered)):
        while end < high[index]:
            while queue and width[queue[-1]] <= width[end]:
                queue.pop()
            queue.append(end)
            end += 1
        while queue[0] < low[index]:
            queue.popleft()
        widest[index] = width[queue[0]]
    narrowed = offsets.copy()
    narrowed[order] = offsets[order] * np.minimum(1.0, half_width / np.maximum(widest, np.finfo(float).tiny))
    return narrowed
