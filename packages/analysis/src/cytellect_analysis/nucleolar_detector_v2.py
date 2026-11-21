"""Nucleolar candidate detector protocols 2.0.0 and marker-only 2.1.0 and 2.2.0.

NCL relocates out of nucleoli under nucleolar stress, so a mask defined by NCL
itself fails exactly where the measurement matters. Protocol 2.0.0 therefore
defines nucleoli from a source the researcher selects:

* ``dapi_poor`` (default): nucleoli are DNA-poor holes in the nuclear stain
  (Kodiha et al., BMC Cell Biol 2011, doi:10.1186/1471-2121-12-25). Per parent
  nucleus, a smoothed copy of the nuclear channel is compared with the median of
  the parent's interior (rim excluded); pixels below ``relative_threshold`` x
  median are candidates, then size and solidity filters apply.
* ``marker``: a stable nucleolar marker channel such as UBF or FBL (Potapova
  et al., eLife 2023, doi:10.7554/eLife.88799): small-radius rolling-ball
  background subtraction, Gaussian sigma 0.7 px, a per-nucleus threshold at
  ``fraction`` of the min-max range, objects below the minimum size removed.
  UBF marks fibrillar centres (rDNA), not the whole nucleolus; masks are not
  dilated and are reported as "FC/rDNA-defined".

Protocol 2.1.0 keeps the marker operations but uses the recorded Gaussian sigma,
with 0.7 px as its default. Protocol 2.0.0 marker replay remains fixed at 0.7 px.

Protocol 2.2.0 (2026-11-21, owner decisions 20, 22 of genellect/cytellect#257) keeps the
2.1.0 operations and adds two rules. (1) A parent whose marker contrast is below
``minimum_contrast_snr`` times the field's noise is ``indeterminate``
(``insufficient_marker_contrast``); its candidates are not adopted. The contrast and
noise are those of cellpose-sam-ncl-parent/4.2.0: the original marker plane smoothed
with Gaussian sigma 0.9 px; parent signal = 99th minus 75th percentile of the
smoothed parent; noise = 1.4826 x MAD of (original - smoothed) over nuclear pixels at
or below the 75th percentile of the smoothed nuclear pixels, at least half an
intensity code unit. The criterion is against noise, never against nucleolar
enrichment, and no object is removed for its brightness. (2) With an image
calibration, the minimum area is max(``minimum_area_px``, ``minimum_area_um2`` in
pixels); without one it is ``minimum_area_px``. The effective value is recorded.

All filtering runs on detection copies; measurement always uses original pixels.
Each parent nucleus receives a recorded state; a nucleus without a candidate is
``no_candidate``, a constant interior is ``indeterminate``.
"""
from __future__ import annotations

import math
from typing import Literal

import numpy as np
from pydantic import Field, FiniteFloat, TypeAdapter, model_validator
from scipy import ndimage as ndi
from skimage.measure import regionprops
from skimage.restoration import rolling_ball

from .masks import validate_label_array
from .regions import RegionModel

PROTOCOL = "2.0.0"
# Protocol 2.2.0: minimum parent marker contrast in units of the field noise. Chosen on the tuning split of the
# public validation (docs/public-nucleolar-shape-validation.md) before the evaluation split was run.
MINIMUM_CONTRAST_SNR = 5.0
# Marker contrast statistic of cellpose-sam-ncl-parent/4.2.0, reused unchanged by protocol 2.2.0.
CONTRAST_SMOOTHING_SIGMA_PX = 0.9
CONTRAST_BACKGROUND_PERCENTILE = 75.0
CONTRAST_SIGNAL_PERCENTILE = 99.0
NOISE_FLOOR = 0.5
MAD_SCALE = 1.4826


class NucleolarDetectorV20(RegionModel):
    engine: Literal["cytellect-nucleolar-v2"] = "cytellect-nucleolar-v2"
    protocol_version: Literal["2.0.0"] = "2.0.0"
    source: Literal["dapi_poor", "marker"] = "dapi_poor"
    smoothing_sigma_px: FiniteFloat = Field(default=2.0, ge=0, le=20)
    rim_exclusion_px: int = Field(default=4, ge=0, le=100)
    relative_threshold: FiniteFloat = Field(default=0.7, gt=0, lt=1)
    marker_fraction: FiniteFloat = Field(default=0.4, gt=0, lt=1)
    background_radius_px: int = Field(default=10, ge=1, le=200)
    minimum_area_px: int = Field(default=4, ge=1, le=100000)
    maximum_area_px: int | None = Field(default=None, ge=1, le=16777216)
    minimum_solidity: FiniteFloat = Field(default=0.6, ge=0, le=1)

    @model_validator(mode="after")
    def consistent(self):
        if self.maximum_area_px is not None and self.maximum_area_px < self.minimum_area_px:
            raise ValueError("nucleolar_area_range_invalid")
        return self


class NucleolarDetectorV21(NucleolarDetectorV20):
    """Marker-only revision: the recorded smoothing sigma is the effective value."""
    protocol_version: Literal["2.1.0"] = "2.1.0"  # type: ignore[assignment]
    source: Literal["marker"] = "marker"
    smoothing_sigma_px: FiniteFloat = Field(default=0.7, ge=0, le=20)


class NucleolarDetectorV22(NucleolarDetectorV21):
    """Marker revision with a noise-based contrast rule per parent and a physical minimum area."""
    protocol_version: Literal["2.2.0"] = "2.2.0"  # type: ignore[assignment]
    minimum_contrast_snr: FiniteFloat = Field(default=MINIMUM_CONTRAST_SNR, gt=0, le=100)
    minimum_area_um2: FiniteFloat | None = Field(default=0.3, gt=0, le=10000)


AnyNucleolarDetectorV2 = NucleolarDetectorV20 | NucleolarDetectorV21 | NucleolarDetectorV22


def _round_half_up(value: float) -> int:
    # Match JavaScript Math.round for the nonnegative calibrated pixel counts.
    return int(math.floor(value + 0.5))


def effective_minimum_area(parameters: AnyNucleolarDetectorV2, pixel_area_um2: float | None) -> dict:
    """The minimum object area in pixels actually applied, and where it came from."""
    floor = int(parameters.minimum_area_px)
    physical = getattr(parameters, "minimum_area_um2", None)
    if physical is None:
        return {"px": floor, "source": "pixels", "pixel_area_um2": pixel_area_um2}
    if pixel_area_um2 is None:
        return {"px": floor, "source": "pixels_without_calibration", "pixel_area_um2": None}
    if not math.isfinite(pixel_area_um2) or pixel_area_um2 <= 0:
        raise ValueError("nucleolar_pixel_area_invalid")
    calibrated = _round_half_up(float(physical) / float(pixel_area_um2))
    return {"px": max(floor, calibrated), "source": "calibration" if calibrated > floor else "pixel_floor",
            "pixel_area_um2": float(pixel_area_um2), "calibrated_px": calibrated}


def marker_noise(marker: np.ndarray, nuclei: np.ndarray) -> tuple[np.ndarray, float]:
    """Smoothed marker plane and the field noise of cellpose-sam-ncl-parent/4.2.0."""
    original = marker.astype(np.float64)
    smoothed = ndi.gaussian_filter(original, CONTRAST_SMOOTHING_SIGMA_PX, mode="reflect")
    noise = NOISE_FLOOR
    active = nuclei > 0
    if active.any():
        lower = active & (smoothed <= np.percentile(smoothed[active], CONTRAST_BACKGROUND_PERCENTILE))
        residual = (original - smoothed)[lower]
        if residual.size:
            noise = max(noise, float(MAD_SCALE * np.median(np.abs(residual - np.median(residual)))))
    return smoothed, noise


def effective_smoothing_sigma(parameters: AnyNucleolarDetectorV2) -> float:
    # Historical marker records can contain an unused sigma (commonly 2).
    # Replaying them must continue using the actual 2.0.0 operation, 0.7 px.
    if parameters.protocol_version == "2.0.0" and parameters.source == "marker":
        return 0.7
    return float(parameters.smoothing_sigma_px)


def _components(mask: np.ndarray) -> tuple[np.ndarray, int]:
    labels, count = ndi.label(mask, structure=np.ones((3, 3), bool))
    return labels, int(count)


def detect_nucleoli_v2(nuclear: np.ndarray, marker: np.ndarray | None, nuclei: np.ndarray,
                       parameters: AnyNucleolarDetectorV2, *,
                       pixel_area_um2: float | None = None) -> tuple[np.ndarray, dict]:
    """Return original-coordinate nucleolar labels and per-parent states/thresholds.

    ``pixel_area_um2`` is the field's confirmed calibration (x size times y size); only protocol
    2.2.0 uses it, for the physical minimum area.
    """
    parameters = TypeAdapter(AnyNucleolarDetectorV2).validate_python(parameters)
    contrast = isinstance(parameters, NucleolarDetectorV22)
    minimum = effective_minimum_area(parameters, pixel_area_um2) if contrast else None
    minimum_area_px = minimum["px"] if minimum else parameters.minimum_area_px
    validate_label_array(nuclei)
    if nuclear.shape != nuclei.shape or (marker is not None and marker.shape != nuclei.shape):
        raise ValueError("compartment_source_shape_or_dtype_invalid")
    if parameters.source == "marker" and marker is None:
        raise ValueError("nucleolar_marker_channel_required")
    if parameters.source == "dapi_poor":
        detection = nuclear.astype(np.float64)
        if parameters.smoothing_sigma_px > 0:
            detection = ndi.gaussian_filter(detection, parameters.smoothing_sigma_px, mode="nearest")
    else:
        assert marker is not None
        raw = marker.astype(np.float64)
        detection = raw - rolling_ball(raw, radius=parameters.background_radius_px)
        detection = ndi.gaussian_filter(detection, effective_smoothing_sigma(parameters), mode="nearest")
    if contrast:
        assert marker is not None
        contrast_plane, noise = marker_noise(marker, nuclei)
    out = np.zeros(nuclei.shape, np.uint32)
    states: dict[int, str] = {}
    thresholds: dict[int, dict] = {}
    next_id = 1
    structure = np.ones((3, 3), bool)
    for parent in (int(value) for value in np.unique(nuclei) if value):
        inside = nuclei == parent
        interior: np.ndarray = ndi.binary_erosion(inside, structure, iterations=parameters.rim_exclusion_px) \
            if parameters.rim_exclusion_px else inside
        values = detection[interior]
        if values.size == 0 or float(values.max()) == float(values.min()):
            states[parent] = "indeterminate"
            thresholds[parent] = {"missing_reason": "uniform_or_empty_interior"}
            continue
        record: dict = {}
        if contrast:
            parent_values = contrast_plane[inside]
            signal = float(np.percentile(parent_values, CONTRAST_SIGNAL_PERCENTILE)
                           - np.percentile(parent_values, CONTRAST_BACKGROUND_PERCENTILE))
            record = {"marker_signal": signal, "marker_noise": noise, "marker_contrast_snr": signal / noise}
            if signal < parameters.minimum_contrast_snr * noise:
                states[parent] = "indeterminate"
                thresholds[parent] = {"missing_reason": "insufficient_marker_contrast", **record}
                continue
        if parameters.source == "dapi_poor":
            reference = float(np.median(values))
            threshold = parameters.relative_threshold * reference
            selected = interior & (detection < threshold)
            thresholds[parent] = {"reference_median": reference, "threshold": threshold,
                                  "rule": "smoothed nuclear signal < relative_threshold x interior median"}
        else:
            low, high = float(values.min()), float(values.max())
            threshold = low + parameters.marker_fraction * (high - low)
            selected = interior & (detection > threshold)
            thresholds[parent] = {"minimum": low, "maximum": high, "threshold": threshold,
                                  "rule": "background-subtracted smoothed marker > min + fraction x (max - min)",
                                  **record}
        labels, count = _components(selected)
        kept = 0
        for region in regionprops(labels):
            if region.area < minimum_area_px:
                continue
            if parameters.maximum_area_px is not None and region.area > parameters.maximum_area_px:
                continue
            if region.solidity < parameters.minimum_solidity:
                continue
            out[labels == region.label] = next_id
            next_id += 1
            kept += 1
        states[parent] = "candidate" if kept else "no_candidate"
        thresholds[parent]["components_before_filters"] = count
        thresholds[parent]["candidates"] = kept
    info = {
        "nucleolar_detector_protocol_version": parameters.protocol_version,
        "operation": "nuclear-compartments",
        "engine": "cytellect_analysis (NumPy / SciPy / scikit-image)",
        "nucleolar_definition_source": parameters.source,
        "nucleolar_states": states,
        "nucleolar_thresholds": thresholds,
        "parameters": parameters.model_dump(mode="json"),
        "references": ["kodiha-2011"] if parameters.source == "dapi_poor" else ["potapova-2023"],
        "mask_meaning": "DNA-poor nucleolar holes" if parameters.source == "dapi_poor"
        else "FC/rDNA-defined marker regions (not dilated)",
        "measurement_pixels": "original, unchanged",
    }
    if contrast:
        assert minimum is not None
        info["minimum_area"] = minimum
        info["marker_contrast"] = {
            "noise": noise, "minimum_contrast_snr": parameters.minimum_contrast_snr,
            "rule": "99th - 75th percentile of the Gaussian(0.9 px) smoothed original marker in the parent "
                    ">= minimum_contrast_snr x noise, else indeterminate (insufficient_marker_contrast)",
            "noise_estimator": "1.4826*MAD(original-smoothed) over nuclear pixels <= 75th percentile of smoothed "
                               "nuclear pixels; floor 0.5",
            "precedent": "cellpose-sam-ncl-parent/4.2.0"}
    return out, info
