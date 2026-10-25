"""Bounded Windows resource probe using local HTTP handlers and the common worker.

Capacity data only; no biological validation. No existing installation or data is
opened. Results, synthetic images and the isolated local store stay outside Git.
The worker is called directly after the real API enqueue; supervisor/browser
overhead is explicitly outside this measurement. No limit or recipe is patched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8")


def generate(side, field):
    import numpy as np
    rng = np.random.default_rng(20261025 + field)
    planes = [rng.integers(80, 121, (side, side), dtype=np.uint16) for _ in range(4)]
    yy, xx = np.ogrid[-32:32, -32:32]
    disk = (xx * xx + yy * yy) <= 28**2
    foci = ((xx - 9)**2 + (yy - 6)**2 <= 6**2) | ((xx + 8)**2 + (yy + 5)**2 <= 5**2)
    for y in range(128, side, 256):
        for x in range(128, side, 256):
            for i, amplitude in enumerate((2200, 900, 400, 700)):
                planes[i][y-32:y+32, x-32:x+32] += disk.astype(np.uint16) * amplitude
            planes[2][y-32:y+32, x-32:x+32] += foci.astype(np.uint16) * 2400
    return planes


def child(args):
    import io

    import tifffile
    from cytellect_api.config import Settings
    from cytellect_api.local import create_local_app
    from cytellect_worker import regions
    from fastapi.testclient import TestClient

    result = {"status": "running", "side": args.side, "fields_requested": args.fields,
              "channels": 4, "input_kind": "synthetic-capacity-only", "field_records": [],
              "stage_seconds": {}, "engine_calls": []}
    def phase(name):
        save(args.output / "phase.json", {"phase": name})
    def timed(name, function):
        def call(*values, **kwargs):
            phase(name)
            start = time.perf_counter()
            try:
                value = function(*values, **kwargs)
                if name == "detection":
                    p = value[1]
                    result["engine_calls"].append({k: p.get(k) for k in (
                        "nuclear_detector_protocol_version", "input_shape_yx", "coordinate_transform",
                        "requested_detection_max_side_px", "model_sha256", "n_tiles")})
                return value
            finally:
                times = result["stage_seconds"]
                times[name] = times.get(name, 0) + time.perf_counter() - start
        return call
    # Timing-only forwarding wrappers: the original scientific functions execute.
    regions.detect_nuclei = timed("detection", regions.detect_nuclei)
    regions.measure_regions_versioned = timed("measurement", regions.measure_regions_versioned)
    origin = "http://127.0.0.1:8765"
    headers = {"Origin": origin, "X-Cytellect-Request": "1", "Sec-Fetch-Site": "same-origin"}
    web = args.output / "shell"
    web.mkdir()
    (web / "index.html").write_text("<title>Capacity harness only</title>", encoding="utf-8")
    settings = Settings(args.output / "store", app_origin=origin, secure_cookies=False,
                        fiji_executable=str(args.fiji))
    phase("startup")
    app = create_local_app(settings, web, 8765)
    with TestClient(app, base_url=origin, client=("127.0.0.1", 45000)) as client:
        response = client.post("/v1/local/session", headers=headers)
        response.raise_for_status()  # ephemeral local cookie is never recorded
        response = client.post("/v1/workspaces", headers=headers, json={"title": "Synthetic resource workload"})
        response.raise_for_status()
        wid = response.json()["id"]
        ids = []
        for field in range(args.fields):
            phase("generate")
            planes = generate(args.side, field)
            before = [hashlib.sha256(p.tobytes()).hexdigest() for p in planes]
            files = {}
            for index, plane in enumerate(planes):
                stream = io.BytesIO()
                tifffile.imwrite(stream, plane, photometric="minisblack")
                files[f"ch{index}"] = (f"synthetic-{index}.tif", stream.getvalue(), "image/tiff")
            spec = {"channels": [{"channel_id": role, "label": f"Synthetic {role}",
                      "stain": "DAPI" if role == "dna" else None, "identity_confirmed": True}
                     for role in ("dna", "signal1", "signal2", "boundary")],
                    "metadata": {"condition": "capacity", "sample": "synthetic"}}
            phase("registration")
            started = time.perf_counter()
            response = client.post(f"/v1/workspaces/{wid}/region-fields", headers=headers,
                                   data={"specification": json.dumps(spec)}, files=files)
            row = {"field_index": field, "status_code": response.status_code,
                   "registration_seconds": time.perf_counter() - started,
                   "source_pixel_sha256": before}
            result["field_records"].append(row)
            if response.status_code != 201:
                result.update(status="registration_rejected", detail=response.json().get("detail"))
                save(args.output / "result.json", result)
                return
            ids.append(response.json()["id"])
            del planes, files, stream
        phase("enqueue")
        recipe = {"id": "region-2d", "version": "1.1.0", "region_set_id": "nuclei", "label": "Nuclei",
                  "source": "stardist_nuclear", "defining_channel_id": "dna", "nuclear_stain_confirmed": True}
        response = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=headers, json={
            "field_ids": ids, "recipe": recipe, "measurement": {"version": "1.1.0", "mode": "raw_intensity"}})
        if response.status_code != 202:
            result.update(status="enqueue_rejected", status_code=response.status_code, detail=response.json().get("detail"))
            save(args.output / "result.json", result)
            return
        rid = response.json()["revision_id"]
        output = app.state.store.safe_path("results", rid)
        start = time.perf_counter()
        regions.run_region_analysis(app.state.store, settings, {"workspace_id": wid, "revision_id": rid}, output)
        result["worker_seconds"] = time.perf_counter() - start
        report = json.loads((output / "measurements.json").read_text(encoding="utf-8"))
        result["field_failures"] = report["field_failures"]
        result["field_outcomes"] = list(report["field_outcomes"].values())
        result["measurement_rows"] = sum(len(t["rows"]) for t in report["field_tables"].values())
        phase("verify_original_pixels")
        import numpy as np
        intact = True
        for fid, record in zip(ids, result["field_records"], strict=True):
            folder = app.state.store.safe_path("workspaces", wid, "fields", fid)
            hashes = [hashlib.sha256(np.load(folder / f"channel-{role}.npy", allow_pickle=False).tobytes()).hexdigest()
                      for role in ("dna", "signal1", "signal2", "boundary")]
            intact = intact and hashes == record["source_pixel_sha256"]
        result["original_pixels_unchanged"] = intact
        result["status"] = "succeeded" if intact and not report["field_failures"] else "failed"
        save(args.output / "result.json", result)
        phase("complete")


def stop_tree(process):
    try:
        descendants = process.children(recursive=True)
    except psutil.Error:
        descendants = []
    for p in [process, *descendants]:
        try:
            p.terminate()
        except psutil.Error:
            pass
    _, live = psutil.wait_procs([process, *descendants], timeout=3)
    for p in live:
        try:
            p.kill()
        except psutil.Error:
            pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fiji", type=Path, required=True)
    parser.add_argument("--side", type=int, choices=(2048, 4096), required=True)
    parser.add_argument("--fields", type=int, choices=(1, 3, 5, 10), required=True)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--child", action="store_true")
    args = parser.parse_args()
    args.output, args.fiji = args.output.resolve(), args.fiji.resolve()
    if args.output == ROOT or args.output.is_relative_to(ROOT):
        parser.error("outputs must be outside checkout")
    if not 30 <= args.timeout <= 1800:
        parser.error("timeout must be 30..1800 seconds")
    if args.child:
        child(args)
        return
    args.output.mkdir(parents=True, exist_ok=False)
    host = {"utc": datetime.now(UTC).isoformat(), "system": platform.system(), "release": platform.release(),
            "python": platform.python_version(), "processor": platform.processor(),
            "logical_cpus": psutil.cpu_count(), "physical_cpus": psutil.cpu_count(logical=False),
            "ram_bytes": psutil.virtual_memory().total, "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "scope": "local API in-process + direct scientific worker; no browser/supervisor; synthetic capacity only"}
    save(args.output / "host.json", host)
    start = time.perf_counter()
    peak, samples, gaps = 0, 0, 0
    phases = {}
    stopped = None
    with (args.output / "child.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--output", str(args.output),
                                    "--fiji", str(args.fiji), "--side", str(args.side), "--fields", str(args.fields),
                                    "--child"], stdout=log, stderr=log, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        root = psutil.Process(process.pid)
        while process.poll() is None:
            try:
                rss = sum(p.memory_info().rss for p in [root, *root.children(recursive=True)])
                peak, samples = max(peak, rss), samples + 1
                try:
                    phase = json.loads((args.output / "phase.json").read_text())["phase"]
                    phases[phase] = max(phases.get(phase, 0), rss)
                except (OSError, ValueError):
                    pass
            except psutil.Error:
                gaps += 1
            if time.perf_counter() - start > args.timeout or psutil.virtual_memory().available < 1024**3:
                stopped = "timeout_or_available_memory_below_1GiB"
                stop_tree(root)
                break
            time.sleep(.05)
        process.wait()
    result_path = args.output / "result.json"
    result = json.loads(result_path.read_text()) if result_path.exists() else {"status": "failed_no_result"}
    receipt = {"host": host, "side": args.side, "fields": args.fields, "exit_code": process.returncode,
               "stopped": stopped, "wall_seconds": time.perf_counter()-start, "peak_summed_rss_bytes": peak,
               "peak_by_phase_bytes": phases, "samples": samples, "rss_access_gaps": gaps, "result": result,
               "limitations": ["shared pages may be counted twice", "subsample spikes may be missed",
                               "one host and synthetic workload; not a supported-capacity guarantee"]}
    save(args.output / "receipt.json", receipt)
    print(json.dumps({k: receipt[k] for k in ("side", "fields", "exit_code", "wall_seconds", "peak_summed_rss_bytes")}))
    if process.returncode or stopped or result["status"] != "succeeded":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
