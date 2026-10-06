"""Automatic background candidate, algorithm protocol 1.0.0.

The candidate is automatic and is never a human-confirmed background ROI. It
only selects pixels; the measurement layer computes ``b = median(I[B])`` from
original pixel values. Failure returns no mask and a fixed reason; it is never
a zero background.

Per field and channel:

1. Exclude every labelled pixel of the supplied region set (plus any additional
   exclusion supplied by the caller), dilated by a Euclidean margin of
   ``PERINUCLEAR_MARGIN_PX``.
2. Exclude bright pixels of this channel: values strictly above
   ``median + BRIGHT_K * MAD_SCALE * max(MAD, BRIGHT_MAD_FLOOR)`` of the pixels
   left after step 1. The floor is one storage unit, so a quantized background
   whose MAD is zero does not exclude every pixel above its median. A robust
   rule is used instead of Otsu because Otsu always splits even a unimodal noise
   distribution and would discard about half of a clean background.
3. Tile the plane into ``TILE_SIZE_PX`` square tiles from the origin; partial
   edge tiles are dropped. A tile is eligible when at least 90 % of its pixels
   are unexcluded.
4. For eligible tiles, compute the median and MAD of their unexcluded original
   pixels. In one non-iterative pass, reject a tile when
   ``|median - M| > TILE_MEDIAN_K * MAD_SCALE * MAD(medians)`` (M is the median of
   tile medians) or when ``tile MAD > D + TILE_DISPERSION_K * MAD_SCALE *
   MAD(tile MADs)`` (D is the median of tile MADs).
5. Require at least ``MIN_TILES`` retained tiles whose centres fall in at least
   ``MIN_QUADRANTS`` image quadrants. The background mask is the unexcluded
   pixels of the retained tiles.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

ALGORITHM = "cytellect-automatic-background"
PROTOCOL_VERSION = "1.0.0"
TILE_SIZE_PX = 32
PERINUCLEAR_MARGIN_PX = 8
MIN_UNEXCLUDED_NUMERATOR, MIN_UNEXCLUDED_DENOMINATOR = 9, 10
MAD_SCALE = 1.4826
BRIGHT_K = 3.0
BRIGHT_MAD_FLOOR = 1.0
TILE_MEDIAN_K = 3.0
TILE_DISPERSION_K = 3.0
MIN_TILES = 4
MIN_QUADRANTS = 3

CONSTANTS = {
    "tile_size_px": TILE_SIZE_PX,
    "perinuclear_margin_px": PERINUCLEAR_MARGIN_PX,
    "margin_metric": "euclidean",
    "min_unexcluded_fraction": MIN_UNEXCLUDED_NUMERATOR / MIN_UNEXCLUDED_DENOMINATOR,
    "bright_rule": "above_median_plus_k_scaled_mad_of_unexcluded_pixels",
    "bright_k": BRIGHT_K,
    "bright_mad_floor": BRIGHT_MAD_FLOOR,
    "mad_scale": MAD_SCALE,
    "tile_median_k": TILE_MEDIAN_K,
    "tile_dispersion_k": TILE_DISPERSION_K,
    "rejection_passes": 1,
    "min_tiles": MIN_TILES,
    "min_quadrants": MIN_QUADRANTS,
    "quadrant_rule": "tile_centre_at_or_after_half_extent",
}
INSUFFICIENT_TILES = "automatic_background_insufficient_tiles"
INSUFFICIENT_COVERAGE = "automatic_background_insufficient_coverage"
FAILURE_REASONS = (INSUFFICIENT_TILES, INSUFFICIENT_COVERAGE)


def _mad(values: np.ndarray, centre: float) -> float:
    return float(np.median(np.abs(values - centre)))


def automatic_background(image: np.ndarray, regions: np.ndarray, *,
                         protocol: str = PROTOCOL_VERSION) -> tuple[np.ndarray | None, dict]:
    """Return a boolean background candidate mask, or None with a reason.

    ``regions`` is a label array or boolean mask in original image coordinates;
    every nonzero pixel is excluded. Neither input is modified.
    """
    if protocol != PROTOCOL_VERSION:
        raise ValueError("automatic_background_protocol_unknown")
    if (not isinstance(image, np.ndarray) or image.ndim != 2
            or image.dtype not in (np.dtype("uint8"), np.dtype("uint16"))):
        raise ValueError("region_source_shape_or_dtype_invalid")
    if not isinstance(regions, np.ndarray) or regions.shape != image.shape:
        raise ValueError("region_background_exclusion_invalid")
    height, width = image.shape
    occupied = regions != 0
    if occupied.any():
        excluded = ndimage.distance_transform_edt(~occupied) <= PERINUCLEAR_MARGIN_PX
    else:
        excluded = np.zeros(image.shape, dtype=bool)
    record: dict = {
        "algorithm": ALGORITHM, "algorithm_version": protocol, "constants": dict(CONSTANTS),
        "bright_threshold": None, "excluded_pixel_count": 0, "eligible_tile_count": 0,
        "median_rejected_tile_count": 0, "dispersion_rejected_tile_count": 0, "retained_tile_count": 0,
        "quadrants": [], "retained_tile_median_min": None, "retained_tile_median_max": None,
        "reason": INSUFFICIENT_TILES,
    }
    remaining = image[~excluded].astype(np.float64)
    if remaining.size:
        centre = float(np.median(remaining))
        threshold = centre + BRIGHT_K * MAD_SCALE * max(_mad(remaining, centre), BRIGHT_MAD_FLOOR)
        record["bright_threshold"] = threshold
        excluded = excluded | (image > threshold)
    record["excluded_pixel_count"] = int(excluded.sum())
    rows, columns = height // TILE_SIZE_PX, width // TILE_SIZE_PX
    if not remaining.size or rows * columns == 0:
        return None, record

    def tiles(array: np.ndarray) -> np.ndarray:
        cropped = array[:rows * TILE_SIZE_PX, :columns * TILE_SIZE_PX]
        return (cropped.reshape(rows, TILE_SIZE_PX, columns, TILE_SIZE_PX)
                .transpose(0, 2, 1, 3).reshape(rows * columns, TILE_SIZE_PX * TILE_SIZE_PX))

    tile_values = tiles(image).astype(np.float64)
    tile_kept = ~tiles(excluded)
    tile_size = TILE_SIZE_PX * TILE_SIZE_PX
    eligible = np.flatnonzero(MIN_UNEXCLUDED_DENOMINATOR * tile_kept.sum(axis=1)
                              >= MIN_UNEXCLUDED_NUMERATOR * tile_size)
    record["eligible_tile_count"] = int(eligible.size)
    if eligible.size < MIN_TILES:
        return None, record
    values = np.where(tile_kept[eligible], tile_values[eligible], np.nan)
    medians = np.nanmedian(values, axis=1)
    dispersions = np.nanmedian(np.abs(values - medians[:, None]), axis=1)
    centre = float(np.median(medians))
    median_rejected = np.abs(medians - centre) > TILE_MEDIAN_K * MAD_SCALE * _mad(medians, centre)
    spread = float(np.median(dispersions))
    dispersion_rejected = dispersions > spread + TILE_DISPERSION_K * MAD_SCALE * _mad(dispersions, spread)
    retained = eligible[~(median_rejected | dispersion_rejected)]
    record.update(median_rejected_tile_count=int(median_rejected.sum()),
                  dispersion_rejected_tile_count=int(dispersion_rejected.sum()),
                  retained_tile_count=int(retained.size))
    quadrants = sorted({2 * int(2 * (index // columns * TILE_SIZE_PX + TILE_SIZE_PX // 2) >= height)
                        + int(2 * (index % columns * TILE_SIZE_PX + TILE_SIZE_PX // 2) >= width)
                        for index in retained.tolist()})
    record["quadrants"] = quadrants
    if retained.size:
        kept_medians = medians[~(median_rejected | dispersion_rejected)]
        record.update(retained_tile_median_min=float(kept_medians.min()),
                      retained_tile_median_max=float(kept_medians.max()))
    if retained.size < MIN_TILES:
        return None, record
    if len(quadrants) < MIN_QUADRANTS:
        record["reason"] = INSUFFICIENT_COVERAGE
        return None, record
    selected = np.zeros(rows * columns, dtype=bool)
    selected[retained] = True
    tile_mask = np.zeros(image.shape, dtype=bool)
    tile_mask[:rows * TILE_SIZE_PX, :columns * TILE_SIZE_PX] = np.repeat(
        np.repeat(selected.reshape(rows, columns), TILE_SIZE_PX, axis=0), TILE_SIZE_PX, axis=1)
    record["reason"] = None
    return tile_mask & ~excluded, record
