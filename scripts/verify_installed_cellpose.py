"""Run one real Cellpose inference through an installed Windows Cytellect.

Release/CI acceptance only. Uses the installed app's analysis package, the setup's
settings/cellpose.json and a registered public image; nothing is downloaded. The
object count shows that the runtime executes, not segmentation accuracy.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Cytellect installation root")
    parser.add_argument("--app", type=Path, required=True, help="installed app directory")
    parser.add_argument("--image", type=Path, required=True, help="registered public 2D TIFF")
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    # Resolve caller-relative paths before switching to the app directory.
    args.root, args.app, args.image, args.receipt = (
        path.resolve() for path in (args.root, args.app, args.image, args.receipt))
    receipt: dict = {"schema": "cytellect-installed-cellpose-check/1", "status": "failed"}
    try:
        settings = json.loads((args.root / "settings" / "cellpose.json").read_text(encoding="utf-8-sig"))
        if settings.get("schema") != "cytellect-cellpose-local/1":
            raise RuntimeError("cellpose_settings_invalid")
        os.environ["CYTELLECT_CELLPOSE_PYTHON"] = settings["python"]
        os.environ["CYTELLECT_CELLPOSE_MODEL_DIR"] = settings["model_dir"]
        os.environ.pop("CYTELLECT_CELLPOSE_ASSETS", None)
        # The launcher runs from the app directory; its release-bound adapter is used.
        os.chdir(args.app)
        import numpy as np
        import tifffile
        from cytellect_analysis.cellpose_engine import CellposeDetectorSpec, detect_cellpose, runtime_status

        status = runtime_status()
        if not status.get("available"):
            raise RuntimeError(str(status.get("error", "cellpose_runtime_unavailable")))
        image = np.asarray(tifffile.imread(args.image))
        if image.ndim != 2:
            raise RuntimeError("cellpose_check_image_invalid")
        with tempfile.TemporaryDirectory(prefix="cytellect-cellpose-check-") as scratch:
            labels, info = detect_cellpose(image[:320, :320], CellposeDetectorSpec(), Path(scratch))
        objects = int(np.unique(labels[labels > 0]).size)
        if objects < 1:
            raise RuntimeError("cellpose_check_no_objects")
        receipt.update(status="succeeded", objects=objects, model_sha256=status.get("model_sha256"),
                       runtime_packages=status.get("packages"), engine=info.get("engine"))
    except Exception as error:  # fixed codes only; never third-party text or paths
        name = str(error)
        receipt["error"] = name if name.startswith("cellpose_") and len(name) < 80 else type(error).__name__
    args.receipt.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({key: receipt[key] for key in ("status", "objects", "error") if key in receipt}))
    return 0 if receipt["status"] == "succeeded" else 1


if __name__ == "__main__":
    sys.exit(main())
