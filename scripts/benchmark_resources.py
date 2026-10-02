"""Bounded local resource observations; no cloud-sizing or maximum-capacity guarantee.

Runs a fresh Python child per case, sampling its RSS plus all descendants. Shared
pages may be counted more than once, and sub-sample spikes may be missed. Outputs
are scratch-only; no private image path or arbitrary source URL is accepted.
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

REPOSITORY = Path(__file__).resolve().parents[1]
PUBLIC_HASH = "d703dfedcf3894b781d0dbf2659f7ef81b60feea8660c39844ea14e150caa775"
CASES = ("public-ncl", "capacity-4096")


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def phase(output, name):
    save(output / "phase.json", {"phase": name, "utc": datetime.now(UTC).isoformat()})


def child(arguments):
    import cytellect_analysis.engine as engine_module
    import numpy as np
    from cytellect_analysis.contracts import Recipe
    from cytellect_analysis.engine import detect
    from cytellect_analysis.images import read_tiff
    from cytellect_analysis.measurement import apply_gfp_gate, measure

    output = arguments.output
    if arguments.experimental_java_heap_gib is not None:
        original_run = engine_module._run
        def experimental_run(command, directory, timeout, environment):
            modified = [f"-Xmx{arguments.experimental_java_heap_gib}g" if item.startswith("-Xmx") else item
                        for item in command] if "CytellectEngine" in command else command
            return original_run(modified, directory, timeout, environment)
        engine_module._run = experimental_run
    phase(output, "load_or_generate_input")
    if arguments.child == "public-ncl":
        if file_hash(arguments.public_image) != PUBLIC_HASH:
            raise ValueError("registered_public_source_hash_mismatch")
        stack = read_tiff(arguments.public_image, channel_indices=[1, 0])
        channels = dict(zip(("dapi", "ncl"), stack, strict=True))
        source = {"kind": "registered-published-image", "accession": "4DNFI7FAWT6C",
                  "original_file_sha256": PUBLIC_HASH, "channel_map": {"dapi": 1, "ncl": 0},
                  "mapping_limitation": "Portal and embedded OME names disagree; adopted mapping retained from manifest."}
    else:
        # A deterministic capacity workload, not a simulated biological validation set.
        seed, side = 20261003, 4096
        random = np.random.default_rng(seed)
        channels = {role: random.integers(80, 121, size=(side, side), dtype=np.uint16)
                    for role in ("dapi", "ncl", "gfp")}
        yy, xx = np.ogrid[-32:32, -32:32]
        nucleus = xx * xx + yy * yy <= 28**2
        foci = ((xx-9)**2 + (yy-6)**2 <= 6**2) | ((xx+8)**2 + (yy+5)**2 <= 5**2)
        for y in range(128, side, 256):
            for x in range(128, side, 256):
                channels["dapi"][y-32:y+32, x-32:x+32] += nucleus.astype(np.uint16) * 2200
                channels["ncl"][y-32:y+32, x-32:x+32] += nucleus.astype(np.uint16) * 400 + foci.astype(np.uint16) * 2400
                channels["gfp"][y-32:y+32, x-32:x+32] += nucleus.astype(np.uint16) * 900
        source = {"kind": "deterministic-capacity-input", "seed": seed, "generator": "grid-disks-and-foci/v1",
                  "nominal_disks": 256, "purpose": "memory/runtime capacity only, not detector-accuracy validation"}
    shape = list(channels["dapi"].shape)
    metadata = {**source, "shape_yx": shape, "channels": {
        role: {"dtype": str(array.dtype), "shape": list(array.shape),
               "sha256_c_order_pixels": hashlib.sha256(array.tobytes(order="C")).hexdigest()}
        for role, array in channels.items()}}
    requested_tiles = 1
    while shape[0] * shape[1] > 262144 * requested_tiles:
        requested_tiles *= 4
    metadata["engine_request"] = {
        "requested_tiles_from_pinned_bridge": requested_tiles,
        "tile_policy": "1,4,16,... until nominal tile area <= 512*512; this is request policy, not successful inference evidence",
        "adapter_sha256": file_hash(Path(engine_module.__file__)),
        "bridge_sha256": file_hash(REPOSITORY / "engines/fiji/CytellectEngine.java"),
        "runtime_lock_sha256": file_hash(REPOSITORY / "engines/fiji/runtime.lock.json"),
        "experimental_java_heap_gib": arguments.experimental_java_heap_gib}
    save(output / "input.json", metadata)
    recipe = Recipe()
    save(output / "recipe.json", recipe.model_dump())
    phase(output, "fiji_detection")
    started = time.perf_counter()
    nuclei, nucleoli, provenance = detect(channels, recipe, output / "engine", str(arguments.fiji))
    detection_seconds = time.perf_counter() - started
    phase(output, "python_measurement")
    background = np.zeros(nuclei.shape, dtype=bool)
    for y in range(0, nuclei.shape[0] - 15, 15):
        for x in range(0, nuclei.shape[1] - 15, 15):
            if not np.any(nuclei[y:y+15, x:x+15]):
                background[y:y+15, x:x+15] = True
                break
        if background.any():
            break
    if not background.any():
        raise ValueError("no_clear_reference_offset_roi")
    # Used only to exercise arithmetic/memory: not a certified cell-free background.
    started = time.perf_counter()
    cells, objects, _ = measure(channels, nuclei, nucleoli, background, recipe,
                                {"condition": "capacity-check", "experimental_unit": "benchmark-unit",
                                 "sample": "benchmark-sample", "acquisition_date": "benchmark"}, "benchmark-field")
    cells = apply_gfp_gate(cells, recipe)
    measurement_seconds = time.perf_counter() - started
    save(output / "child-result.json", {"status": "succeeded", "nuclei": len(cells),
         "nucleolar_candidates": len(objects), "detection_seconds": detection_seconds,
         "measurement_seconds": measurement_seconds, "engine": provenance,
         "background_scope": "first non-nuclear 15x15 arithmetic reference offset only"})
    phase(output, "complete")


def stop_tree(root):
    try:
        descendants = root.children(recursive=True)
    except psutil.Error:
        descendants = []
    # Stop root first so it cannot create new work while descendants are reaped.
    for process in [root, *reversed(descendants)]:
        try:
            process.terminate()
        except psutil.Error:
            pass
    _, alive = psutil.wait_procs([root, *descendants], timeout=3)
    for process in alive:
        try:
            process.kill()
        except psutil.Error:
            pass
    psutil.wait_procs(alive, timeout=3)


def run_case(arguments, name):
    folder = arguments.output / name
    folder.mkdir(parents=True, exist_ok=False)
    environment = os.environ.copy()
    environment.update(TMPDIR=str(folder), TEMP=str(folder), TMP=str(folder), OMP_NUM_THREADS="1")
    command = [sys.executable, str(Path(__file__).resolve()), "--child", name,
               "--output", str(folder), "--fiji", str(arguments.fiji),
               "--public-image", str(arguments.public_image)]
    if arguments.experimental_java_heap_gib is not None:
        command += ["--experimental-java-heap-gib", str(arguments.experimental_java_heap_gib)]
    start = time.perf_counter()
    peak_rss, peak_processes, samples, access_failures = 0, 0, 0, 0
    peaks_by_phase = {}
    current_phase, status = "python_startup", "running"
    with (folder / "stdout.log").open("wb") as stdout, (folder / "stderr.log").open("wb") as stderr:
        worker = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=environment,
                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        root = psutil.Process(worker.pid)
        try:
            while worker.poll() is None:
                elapsed = time.perf_counter() - start
                if elapsed >= arguments.timeout_seconds:
                    status = "timeout"
                    stop_tree(root)
                    break
                try:
                    processes = [root, *root.children(recursive=True)]
                except psutil.NoSuchProcess:
                    break
                except psutil.AccessDenied:
                    processes = [root]
                    access_failures += 1
                rss = 0
                alive_count = 0
                for process in processes:
                    try:
                        rss += process.memory_info().rss
                        alive_count += 1
                    except psutil.NoSuchProcess:
                        continue
                    except psutil.AccessDenied:
                        access_failures += 1
                try:
                    current_phase = json.loads((folder / "phase.json").read_text(encoding="utf-8"))["phase"]
                except (OSError, json.JSONDecodeError):
                    pass
                peaks_by_phase[current_phase] = max(peaks_by_phase.get(current_phase, 0), rss)
                peak_rss, peak_processes = max(peak_rss, rss), max(peak_processes, alive_count)
                samples += 1
                # Preserve an interactive host; this is a reported guard, not a successful capacity result.
                if psutil.virtual_memory().available < 1024**3:
                    status = "host_memory_guard"
                    stop_tree(root)
                    break
                time.sleep(arguments.sample_seconds)
        finally:
            if worker.poll() is None:
                stop_tree(root)
            worker.wait(timeout=10)
    elapsed = time.perf_counter() - start
    child_result = json.loads((folder / "child-result.json").read_text(encoding="utf-8")) if (folder / "child-result.json").is_file() else {}
    if status == "running":
        status = "succeeded" if worker.returncode == 0 and child_result.get("status") == "succeeded" else "failed"
    input_info = json.loads((folder / "input.json").read_text(encoding="utf-8")) if (folder / "input.json").is_file() else None
    report = {"case": name, "status": status, "exit_code": worker.returncode, "elapsed_seconds": elapsed,
              "timeout_seconds": arguments.timeout_seconds, "sample_interval_seconds": arguments.sample_seconds,
              "samples": samples, "observed_average_sample_spacing_seconds": elapsed / samples if samples else None,
              "rss_access_failures": access_failures,
              "peak_summed_rss_bytes": peak_rss, "peak_summed_rss_gib": peak_rss / 1024**3,
              "peak_process_count": peak_processes, "peak_rss_by_phase_bytes": peaks_by_phase,
              "last_phase": current_phase, "input": input_info, "result": child_result}
    save(folder / "benchmark.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fiji", type=Path, required=True)
    parser.add_argument("--public-image", type=Path, required=True)
    parser.add_argument("--case", choices=(*CASES, "all"), default="all")
    parser.add_argument("--timeout-seconds", type=float, default=300)
    parser.add_argument("--sample-seconds", type=float, default=.05)
    parser.add_argument("--child", choices=CASES)
    parser.add_argument("--experimental-java-heap-gib", type=int, choices=(4,), help="Benchmark-only child command override; production adapter is unchanged")
    arguments = parser.parse_args()
    arguments.output = arguments.output.resolve()
    if arguments.output == REPOSITORY or arguments.output.is_relative_to(REPOSITORY):
        parser.error("Benchmark images/results must stay outside the repository")
    if not 1 <= arguments.timeout_seconds <= 300 or not .02 <= arguments.sample_seconds <= 1:
        parser.error("Bounded timeout 1..300 seconds and sampling .02..1 seconds required")
    if arguments.child:
        child(arguments)
        return
    arguments.output.mkdir(parents=True, exist_ok=False)
    host = {"utc": datetime.now(UTC).isoformat(), "system": platform.system(), "release": platform.release(),
            "machine": platform.machine(), "processor": platform.processor(), "python": platform.python_version(),
            "logical_cpus": psutil.cpu_count(), "physical_cpus": psutil.cpu_count(logical=False),
            "total_memory_bytes": psutil.virtual_memory().total,
            "available_memory_before_bytes": psutil.virtual_memory().available,
            "script_sha256": file_hash(Path(__file__)),
            "java_heap_setting": (f"-Xmx{arguments.experimental_java_heap_gib}g experimental benchmark-only override"
                                  if arguments.experimental_java_heap_gib is not None else "-Xmx2g in pinned adapter"),
            "experimental_java_heap_gib": arguments.experimental_java_heap_gib,
            "measurement": "sampled sum of RSS of benchmark Python child and all descendants; controller excluded",
            "limitations": ["shared pages may be double-counted", "sub-sample spikes can be missed",
                            "other host workloads affect timing", "no container cgroup limit applied",
                            "single case does not establish worst-case memory or cloud throughput"]}
    save(arguments.output / "host.json", host)
    results = []
    for name in CASES if arguments.case == "all" else (arguments.case,):
        result = run_case(arguments, name)
        results.append(result)
        print(json.dumps({k: result[k] for k in ("case", "status", "elapsed_seconds", "peak_summed_rss_gib", "last_phase")}), flush=True)
    save(arguments.output / "summary.json", {"host": host, "cases": results})
    if any(result["status"] != "succeeded" for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
