"""Fixed ImageJ threshold / MorphoLibJ candidate regions on original pixels."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

import numpy as np
import tifffile
from pydantic import Field, FiniteFloat, model_validator

from .regions import RegionModel, _array_hash


class SignalDetectorSpec(RegionModel):
    engine: Literal["fiji-positive-regions"] = "fiji-positive-regions"
    protocol_version: Literal["1.0.0"] = "1.0.0"
    threshold_method: Literal["otsu", "manual"]
    threshold: Annotated[FiniteFloat, Field(ge=0, le=65535)] | None = None
    smoothing_sigma_px: Annotated[FiniteFloat, Field(ge=0, le=10)] = 0.0
    minimum_area_px: Annotated[int, Field(ge=1, le=100000)] = 1
    split_touching: bool = False

    @model_validator(mode="after")
    def explicit_threshold_rule(self):
        if (self.threshold_method == "manual") != (self.threshold is not None):
            raise ValueError("signal_threshold_rule_invalid")
        return self


def detect_positive_regions(
    image: np.ndarray, parameters: SignalDetectorSpec, output_dir: Path,
    executable: str, scratch_root: Path | None = None,
) -> tuple[np.ndarray, dict]:
    """Return threshold candidates, never inferred whole cells or GFP biology.

    Native/display-RGB identity belongs to the calling versioned channel contract.
    Otsu is a per-field exploratory rule. Neither mode uses a nuclear mask, and
    measurements must always use the unchanged source plane, not detection blur.
    """
    from . import engine

    parameters = SignalDetectorSpec.model_validate(parameters)
    if (not isinstance(image, np.ndarray) or image.ndim != 2 or min(image.shape) < 1
            or max(image.shape) > 4096 or image.dtype not in (np.uint8, np.uint16)):
        raise ValueError("fiji_input_format")
    runtime, java, lock = engine.runtime_info(executable)
    output = output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    tifffile.imwrite(output / "signal.tif", image, photometric="minisblack")
    request = {"directory": str(output), "mode": "signal-only",
               "detector": parameters.model_dump(mode="json")}
    (output / "request.json").write_text(json.dumps(request), encoding="utf-8")
    assets = engine._execute_bridge(output, runtime, java, scratch_root)
    array = tifffile.imread(output / "regions.tif")
    if (array.shape != image.shape or not np.isfinite(array).all() or np.any(array < 0)
            or np.any(array != np.floor(array)) or np.any(array >= 2**24)):
        raise engine.EngineUnavailable("fiji_invalid_output_labels")
    labels = array.astype(np.uint32)
    info = json.loads((output / "engine-result.json").read_text(encoding="utf-8"))
    if (info.get("operation") != "signal-only"
            or info.get("parameters") != parameters.model_dump(mode="json")
            or info.get("status") not in {"candidate", "no_candidate", "indeterminate"}
            or (info.get("status") == "candidate") != bool(labels.any())
            or info.get("biological_positivity_established") is not False):
        raise engine.EngineUnavailable("fiji_invalid_output_provenance")
    identity = engine._engine_identity(assets, java, lock, automatic=False)
    # This operation never loads StarDist. Do not imply its model made these masks.
    identity.pop("model_sha256")
    info.update(identity)
    info.update({"signal_detector_protocol_version": "1.0.0", "input_shape_yx": list(image.shape),
                 "input_dtype": image.dtype.name, "exploratory_threshold": True,
                 "input_sha256": _array_hash(image, "|u1" if image.dtype.itemsize == 1 else "<u2"),
                 "canonical_labels_sha256": _array_hash(labels, "<u4")})
    (output / "engine-result.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    return labels, info
