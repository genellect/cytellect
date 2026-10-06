"""Nucleolar candidate detector protocol 2.0.0 (researcher-selected definition source).

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

All filtering runs on detection copies; measurement always uses original pixels.
Each parent nucleus receives a recorded state; a nucleus without a candidate is
``no_candidate``, a constant interior is ``indeterminate``.
"""
from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import Field, FiniteFloat, model_validator
from scipy import ndimage as ndi
from skimage.measure import regionprops
from skimage.restoration import rolling_ball

from .masks import validate_label_array
from .regions import RegionModel

PROTOCOL = "2.0.0"


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


def _components(mask: np.ndarray) -> tuple[np.ndarray, int]:
    labels, count = ndi.label(mask, structure=np.ones((3, 3), bool))
    return labels, int(count)


def detect_nucleoli_v2(nuclear: np.ndarray, marker: np.ndarray | None, nuclei: np.ndarray,
                       parameters: NucleolarDetectorV20) -> tuple[np.ndarray, dict]:
    """Return original-coordinate nucleolar labels and per-parent states/thresholds."""
    parameters = NucleolarDetectorV20.model_validate(parameters)
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
        detection = ndi.gaussian_filter(detection, 0.7, mode="nearest")
    out = np.zeros(nuclei.shape, np.uint32)
    states: dict[int, str] = {}
    thresholds: dict[int, dict] = {}
    next_id = 1
    structure = np.ones((3, 3), bool)
    for parent in (int(value) for value in np.unique(nuclei) if value):
        inside = nuclei == parent
        interior = ndi.binary_erosion(inside, structure, iterations=parameters.rim_exclusion_px) \
            if parameters.rim_exclusion_px else inside
        values = detection[interior]
        if values.size == 0 or float(values.max()) == float(values.min()):
            states[parent] = "indeterminate"
            thresholds[parent] = {"missing_reason": "uniform_or_empty_interior"}
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
                                  "rule": "background-subtracted smoothed marker > min + fraction x (max - min)"}
        labels, count = _components(selected)
        kept = 0
        for region in regionprops(labels):
            if region.area < parameters.minimum_area_px:
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
        "nucleolar_detector_protocol_version": PROTOCOL,
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
    return out, info
