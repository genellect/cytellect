"""NCL compartments within supplied, immutable original-coordinate nuclei."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Annotated, Literal

import numpy as np
from pydantic import Field, FiniteFloat, TypeAdapter, model_validator

from .contracts import Recipe
from .masks import validate_label_array, validate_labels
from .measurement import normalize_nucleolar_states
from .regions import RegionModel, _array_hash


class NucleolarDetectorSpec(RegionModel):
    engine: Literal["fiji-nucleolar-compartments"] = "fiji-nucleolar-compartments"
    protocol_version: Literal["1.0.0"] = "1.0.0"
    smoothing_sigma_px: Annotated[FiniteFloat, Field(ge=0, le=10)] = 0.0
    minimum_area_px: Annotated[int, Field(ge=1, le=100000)] = 1
    split_touching: bool = False


class NucleolarDetectorV11(RegionModel):
    """Opt-in threshold/area controls; the saved 1.0 detector remains unchanged."""
    engine: Literal["fiji-nucleolar-compartments"] = "fiji-nucleolar-compartments"
    protocol_version: Literal["1.1.0"] = "1.1.0"
    threshold_method: Literal["otsu", "manual"] = "otsu"
    threshold: Annotated[FiniteFloat, Field(ge=0, le=65535)] | None = None
    smoothing_sigma_px: Annotated[FiniteFloat, Field(ge=0, le=10)] = 0.0
    minimum_area_px: Annotated[int, Field(strict=True, ge=1, le=100000)] = 1
    maximum_area_px: Annotated[int, Field(strict=True, ge=1, le=16777216)] | None = None
    split_touching: bool = False

    @model_validator(mode="after")
    def valid_threshold_and_area(self):
        if (self.threshold_method == "manual") != (self.threshold is not None):
            raise ValueError("nucleolar_threshold_rule_invalid")
        if self.maximum_area_px is not None and self.maximum_area_px < self.minimum_area_px:
            raise ValueError("nucleolar_area_range_invalid")
        return self


NucleolarDetector = Annotated[NucleolarDetectorSpec | NucleolarDetectorV11,
                              Field(discriminator="protocol_version")]


class _ControlledCompartmentRecipe(Recipe):
    """Internal fixed-bridge extension, never an alternate legacy/GFP recipe."""
    compartment_threshold_method: Literal["otsu", "manual"]
    compartment_threshold: Annotated[FiniteFloat, Field(ge=0, le=65535)] | None = None
    maximum_area_px: int | None = None


def derive_compartment_masks(
    nuclei: np.ndarray, nucleoli: np.ndarray, states: dict,
) -> tuple[dict[str, np.ndarray], dict]:
    """Require a classified candidate before deriving its complementary region.

    A detector's candidate-free result does not establish that the whole nucleus
    is biological nucleoplasm. Retain the parent and its reason in provenance,
    but do not manufacture a valid compartment mask or a zero-intensity row.
    """
    validate_labels(nuclei, nucleoli)
    outcomes = normalize_nucleolar_states({"nucleolar_states": states})
    nucleus_ids = {int(value) for value in np.unique(nuclei) if value}
    if set(outcomes) != nucleus_ids:
        raise ValueError("compartment_parent_states_incomplete")
    child_ids, first_pixels = np.unique(nucleoli, return_index=True)
    parents = {int(child): int(nuclei.flat[index])
               for child, index in zip(child_ids, first_pixels, strict=True) if child}
    candidate_parents = set(parents.values())
    eligible = {parent for parent, state in outcomes.items() if state == "candidate"}
    if eligible - candidate_parents:
        raise ValueError("compartment_candidate_mask_missing")
    omitted = {parent: state for parent, state in outcomes.items() if parent not in eligible}
    valid_nuclei = np.isin(nuclei, sorted(eligible))
    nucleolar_labels = np.where(valid_nuclei, nucleoli, 0).astype(np.uint32)
    nucleoplasm_labels = np.where(valid_nuclei & (nucleolar_labels == 0), nuclei, 0).astype(np.uint32)
    kept_parents = {child: parent for child, parent in parents.items() if parent in eligible}
    missing_nucleoplasm = sorted(eligible - {int(value) for value in np.unique(nucleoplasm_labels) if value})
    return {"nucleoli": nucleolar_labels, "nucleoplasm": nucleoplasm_labels}, {
        "compartment_protocol_version": "1.0.1",
        "compartment_status": "incomplete" if omitted or missing_nucleoplasm else "complete" if nucleus_ids else "no_nuclei",
        "nucleolar_states": outcomes, "parent_ids": kept_parents,
        "nuclear_count": len(nucleus_ids), "eligible_nucleus_ids": sorted(eligible),
        "excluded_nucleus_ids": omitted, "missing_parent_count": len(omitted),
        "missing_parent_reasons": dict(sorted(Counter(omitted.values()).items())),
        "compartment_missing_parent_count": {"nucleoli": len(omitted),
                                             "nucleoplasm": len(omitted) + len(missing_nucleoplasm)},
        "nucleoplasm_missing_reasons": {parent: "empty_after_subtraction" for parent in missing_nucleoplasm},
        "candidate_free_policy": "omit_both_compartments_retain_parent_state",
        "nucleoplasm_definition": "eligible parent nuclear pixels minus union of its NCL candidates",
        "nucleoplasm_label_identity": "parent_nucleus_id",
    }


def detect_compartments(
    channels: dict[str, np.ndarray], nuclei: np.ndarray, parameters: NucleolarDetector,
    output_dir: Path, executable: str, scratch_root: Path | None = None,
) -> tuple[dict[str, np.ndarray], dict]:
    """Reuse ImageJ per-nucleus Otsu / MorphoLibJ, never rerun StarDist.

    The caller verifies source revision ownership/hash and records native versus
    display-RGB semantics. These internal role names do not infer a stain from an
    arbitrary plane. All returned masks and measurements use original coordinates.
    """
    from . import engine

    if isinstance(parameters, dict) and "protocol_version" not in parameters:
        parameters = {"protocol_version": "1.0.0", **parameters}
    parameters = TypeAdapter(NucleolarDetector).validate_python(parameters)
    validate_label_array(nuclei)
    if set(channels) != {"dapi", "ncl"}:
        raise ValueError("compartment_channels_required")
    if (max(nuclei.shape) > 4096 or int(nuclei.max()) >= 2**24
            or any(not isinstance(image, np.ndarray) or image.shape != nuclei.shape
                   or image.dtype not in (np.uint8, np.uint16) for image in channels.values())):
        raise ValueError("compartment_source_shape_or_dtype_invalid")
    source_hashes = {role: _array_hash(image, "|u1" if image.dtype.itemsize == 1 else "<u2")
                     for role, image in channels.items()}
    nuclear_hash = _array_hash(nuclei, "<u4")
    recipe = Recipe(id="ncl-native-2d", nucleolar_method="ncl-otsu",
                    smoothing_sigma_px=parameters.smoothing_sigma_px,
                    minimum_area_px=parameters.minimum_area_px,
                    split_touching=parameters.split_touching)
    if isinstance(parameters, NucleolarDetectorV11):
        if parameters.threshold is not None and parameters.threshold > np.iinfo(channels["ncl"].dtype).max:
            raise ValueError("nucleolar_threshold_outside_input_range")
        recipe = _ControlledCompartmentRecipe(
            **recipe.model_dump(), compartment_threshold_method=parameters.threshold_method,
            compartment_threshold=parameters.threshold, maximum_area_px=parameters.maximum_area_px,
        )
    returned_nuclei, nucleoli, info = engine.detect(
        channels, recipe, output_dir, executable, nuclei=nuclei, scratch_root=scratch_root,
    )
    if (_array_hash(nuclei, "<u4") != nuclear_hash
            or any(_array_hash(image, "|u1" if image.dtype.itemsize == 1 else "<u2") != source_hashes[role]
                   for role, image in channels.items())):
        raise engine.EngineUnavailable("compartment_source_modified")
    if not np.array_equal(returned_nuclei, nuclei) or info.get("nuclei_reused") is not True:
        raise engine.EngineUnavailable("fiji_modified_preserved_nuclei")
    masks, details = derive_compartment_masks(nuclei, nucleoli, normalize_nucleolar_states(info))
    info.update(details)
    info.update({"operation": "nuclear-compartments", "engine": "Fiji / ImageJ / MorphoLibJ",
                 "parameters": parameters.model_dump(mode="json"),
                 "input_sha256": source_hashes, "parent_nuclear_mask_sha256": nuclear_hash,
                 "canonical_mask_sha256": {name: _array_hash(mask, "<u4") for name, mask in masks.items()},
                 "input_shape_yx": list(nuclei.shape), "nuclear_detection_performed": False,
                 "coordinate_transform": {"scale_x": 1, "scale_y": 1},
                 "ncl_definition_circularity": "candidate masks depend on the NCL signal being measured"})
    if isinstance(parameters, NucleolarDetectorV11):
        info["nucleolar_detector_protocol_version"] = "1.1.0"
    # The retained runtime contains this model, but it was not used in this call.
    info.pop("model", None)
    info.pop("model_sha256", None)
    return masks, info
