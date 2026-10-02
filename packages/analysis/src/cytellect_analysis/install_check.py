"""Offline installation check using only generated pixels, never research images."""
from __future__ import annotations

import argparse
import json
import platform
import tempfile
from pathlib import Path

import numpy as np

from .contracts import Recipe
from .engine import detect
from .measurement import region_values
from .synthetic import synthetic_field


def verify_installation(fiji: str, scratch: Path) -> dict:
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cytellect-install-", dir=scratch) as temporary:
        channels, _, _ = synthetic_field(seed=0)
        originals = {key: value.copy() for key, value in channels.items()}
        deep_output = Path(temporary) / ("a" * 36) / "output" / ("b" * 36) / "engine"
        nuclei, nucleoli, info = detect(channels, Recipe(), deep_output, fiji, scratch_root=Path(temporary))
        if len(np.unique(nuclei)) - 1 != 9 or len(np.unique(nucleoli)) - 1 != 18:
            raise RuntimeError("installation_detection_check_failed")
        if any(not np.array_equal(channels[key], original) for key, original in originals.items()):
            raise RuntimeError("installation_pixels_changed")
        # Independent arithmetic values also detect unwanted negative clipping.
        values = region_values(np.array([[0, 2], [4, 6]], dtype=np.uint16), np.ones((2, 2), bool), 3)
        if values != {"mean": 3.0, "median": 3.0, "integrated": 12.0,
                      "mean_corrected": 0.0, "median_corrected": 0.0, "integrated_corrected": 0.0}:
            raise RuntimeError("installation_arithmetic_check_failed")
        return {"status": "passed", "scope": "synthetic installation and arithmetic check; not biological accuracy",
                "python": platform.python_version(), "nuclei": 9, "nucleolar_candidates": 18,
                "model_sha256": info["model_sha256"], "runtime_lock_sha256": info["runtime_lock_sha256"],
                "bridge_sha256": info["bridge_sha256"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fiji", required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    report = verify_installation(args.fiji, args.scratch)
    args.result.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
