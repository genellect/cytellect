"""Bounded local CPU execution smoke, not a Cellpose capacity/accuracy claim."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil
from benchmark_group_comparison import ROOT, save, stop_tree


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--child", action="store_true")
    args = parser.parse_args()
    args.output = args.output.resolve()
    if args.output == ROOT or args.output.is_relative_to(ROOT):
        parser.error("output must be outside checkout")
    if args.child:
        import numpy as np
        from cytellect_analysis.cellpose_engine import CellposeDetectorSpec, detect_cellpose
        for name in ("CYTELLECT_CELLPOSE_REMOTE_URL", "CYTELLECT_CELLPOSE_REMOTE_TOKEN", "CYTELLECT_CELLPOSE_REMOTE_SECRET"):
            os.environ.pop(name, None)
        os.environ["CYTELLECT_CELLPOSE_PYTHON"] = str(args.python.resolve())
        os.environ["CYTELLECT_CELLPOSE_MODEL_DIR"] = str(args.models.resolve())
        yy, xx = np.ogrid[:128, :128]
        image = (100 + 2000 * ((xx - 64)**2 + (yy - 64)**2 < 25**2)).astype(np.uint16)
        before = hashlib.sha256(image.tobytes()).hexdigest()
        start = time.perf_counter()
        labels, provenance = detect_cellpose(image, CellposeDetectorSpec(compute_device="cpu"), args.output / "engine")
        unchanged = before == hashlib.sha256(image.tobytes()).hexdigest()
        save(args.output / "result.json", {"status": "succeeded" if unchanged else "failed",
             "seconds": time.perf_counter() - start, "input_shape": [128, 128], "output_shape": list(labels.shape),
             "output_dtype": str(labels.dtype), "original_pixels_unchanged": unchanged,
             "model_sha256": provenance.get("model_sha256"), "device": "cpu", "biological_validation": False})
        return
    args.output.mkdir(parents=True, exist_ok=False)
    start, peak, stopped, gaps = time.perf_counter(), 0, False, 0
    with (args.output / "child.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--child", "--output", str(args.output),
                                    "--python", str(args.python.resolve()), "--models", str(args.models.resolve())],
                                   stdout=log, stderr=log)
        root = psutil.Process(process.pid)
        while process.poll() is None:
            try:
                peak = max(peak, sum(p.memory_info().rss for p in [root, *root.children(recursive=True)]))
            except psutil.Error:
                gaps += 1
            if time.perf_counter() - start > 300 or psutil.virtual_memory().available < 1024**3:
                stop_tree(root)
                stopped = True
                break
            time.sleep(.05)
        process.wait()
    path = args.output / "result.json"
    result = json.loads(path.read_text()) if path.exists() else {"status": "failed_no_result"}
    receipt = {"result": result, "wall_seconds": time.perf_counter() - start, "peak_summed_rss_bytes": peak,
               "exit_code": process.returncode, "stopped": stopped, "rss_access_gaps": gaps}
    save(args.output / "receipt.json", receipt)
    print(json.dumps(receipt))
    if process.returncode or stopped or result["status"] != "succeeded":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
