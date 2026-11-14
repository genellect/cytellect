"""Offline runtime check on a registered public DRAQ image, plus exact arithmetic."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np
import tifffile

from .engine import detect_nuclei
from .engine_diagnostics import installation_execution_policy, owned_temporary_directory
from .measurement import region_values
from .region_contracts import NuclearDetectorSpec
from .temporary_storage import scratch_ownership_scope

SCHEMA = "cytellect-installation-check/2"
FIXTURE_SHA256 = "06fbe48a163131acf02934765458b3a8f22c542b895ce607614e1e7b06afb21e"
FIXTURE_PIXEL_SHA256 = "d498ff570f685959b32d9e7266897ba6ebe6f686bce4838d949baad15f5dda1f"
FIXTURE = Path(__file__).parent / "assets/install-check/BBBC013-A01-draq.tif"
# StarDist found 350 nuclei in this public image on Linux (2026-11-10). The band (half to double)
# only catches a broken runtime (nothing or far too much detected) across platforms; it is not a
# check of detection accuracy and was not tuned on evaluation data.
EXPECTED_NUCLEI = range(175, 701)
ERROR_CODES = frozenset({
    "fiji_timeout", "fiji_execution_failed", "fiji_process_unavailable", "fiji_temporary_path_invalid",
    "fiji_temporary_path_too_long", "windows_application_control_blocked", "installation_fixture_invalid",
    "installation_detection_check_failed", "installation_pixels_changed", "installation_arithmetic_check_failed",
    "installation_file_access_failed", "installation_check_failed", "installation_report_write_failed",
    "fiji_temporary_cleanup_failed",
    "fiji_temporary_cleanup_pending",
})


def verify_installation(fiji: str, scratch: Path) -> dict:
    scratch.mkdir(parents=True, exist_ok=True)
    if hashlib.sha256(FIXTURE.read_bytes()).hexdigest() != FIXTURE_SHA256:
        raise RuntimeError("installation_fixture_invalid")
    image = tifffile.imread(FIXTURE)
    if (image.shape != (640, 640) or image.dtype != np.uint8
            or hashlib.sha256(image.tobytes()).hexdigest() != FIXTURE_PIXEL_SHA256):
        raise RuntimeError("installation_fixture_invalid")
    original = image.copy()
    with owned_temporary_directory(prefix="cytellect-install-", directory=scratch) as temporary:
        deep_output = temporary / ("a" * 36) / "output" / ("b" * 36) / "engine"
        nuclei, info = detect_nuclei(image, NuclearDetectorSpec(), deep_output, fiji,
                                    scratch_root=temporary)
        count = len(np.unique(nuclei)) - 1
        if nuclei.shape != image.shape or not np.issubdtype(nuclei.dtype, np.integer) or count not in EXPECTED_NUCLEI:
            raise RuntimeError("installation_detection_check_failed")
        if not np.array_equal(image, original):
            raise RuntimeError("installation_pixels_changed")
        # This minimal array checks only arithmetic, not image appearance or detection quality.
        values = region_values(np.array([[0, 2], [4, 6]], dtype=np.uint16), np.ones((2, 2), bool), 3)
        if values != {"mean": 3.0, "median": 3.0, "integrated": 12.0,
                      "mean_corrected": 0.0, "median_corrected": 0.0, "integrated_corrected": 0.0}:
            raise RuntimeError("installation_arithmetic_check_failed")
        return {"scope": "public-image runtime and exact arithmetic check; not biological accuracy",
                "python": platform.python_version(), "fixture": "BBBC013v1/A01/DRAQ",
                "fixture_sha256": FIXTURE_SHA256, "nuclei": count,
                "model_sha256": info["model_sha256"], "runtime_lock_sha256": info["runtime_lock_sha256"],
                "bridge_sha256": info["bridge_sha256"]}


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix="check-", suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            json.dump(value, output, ensure_ascii=True, indent=2, allow_nan=False)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _error_code(error: Exception) -> str:
    diagnostic = getattr(error, "diagnostic", None) or {}
    if diagnostic.get("native_hint") == "windows_application_control_blocked":
        return "windows_application_control_blocked"
    if str(error) in ERROR_CODES:
        return str(error)
    if isinstance(error, OSError):
        return "installation_file_access_failed"
    return "installation_check_failed"


def _retryable(error: Exception, code: str) -> bool:
    diagnostic = getattr(error, "diagnostic", None) or {}
    if diagnostic.get("native_hint") is not None:
        return False
    return (code in {"fiji_timeout", "fiji_execution_failed"}
            or (code == "fiji_process_unavailable" and diagnostic.get("native_error_code") in {32, 33}))


def run_check(fiji: str, scratch: Path, result: Path, *, attempts: int = 2, compile_seconds: int = 300,
              execution_seconds: int = 300, status_file: Path | None = None,
              recovery_scope: Path | None = None) -> dict:
    if type(attempts) is not int or not 1 <= attempts <= 2:
        raise ValueError("installation_attempts_invalid")
    if (type(compile_seconds) is not int or not 1 <= compile_seconds <= 300
            or type(execution_seconds) is not int or not 1 <= execution_seconds <= 1800):
        raise ValueError("installation_timeout_invalid")
    report: dict[str, Any] = {"schema": SCHEMA, "status": "running", "attempts": [],
                              "maximum_seconds": attempts * (compile_seconds + execution_seconds) + 120}

    def publish(phase: str) -> None:
        try:
            _write_json(result, report)
            if status_file is not None:
                status_file.write_text(phase, encoding="ascii")
        except OSError:
            # Keep execution's first fixed code even if diagnostic I/O also fails.
            report["report_error_code"] = "installation_report_write_failed"

    for number in range(1, attempts + 1):
        attempt: dict[str, Any] = {"number": number, "status": "running", "events": []}
        report["attempts"].append(attempt)
        report["status"] = "running"
        report.pop("error_code", None)
        publish("check_analysis_retry" if number > 1 else "check_analysis_fixture")
        started = time.monotonic()

        def record(event: dict[str, Any]) -> None:
            attempt["events"].append(event)
            phases = {"compile_bridge": "check_analysis_compile", "run_engine": "check_analysis_engine",
                      "cleanup_scratch": "check_analysis_cleanup"}
            publish(phases[event["operation"]])

        try:
            with scratch_ownership_scope(recovery_scope or scratch), installation_execution_policy(compile_seconds, execution_seconds, record):
                verified = verify_installation(fiji, scratch)
        except Exception as error:
            code = _error_code(error)
            attempt.update(status="failed", error_code=code,
                           elapsed_seconds=round(time.monotonic() - started, 3))
            report.update(status="failed", error_code=code)
            publish("check_analysis")
            if number < attempts and _retryable(error, code):
                attempt["retry_scheduled"] = True
                time.sleep(1)
                continue
            return report
        attempt.update(status="passed", elapsed_seconds=round(time.monotonic() - started, 3))
        report.update(verified)
        report.update(status="passed")
        publish("check_analysis")
        return report
    raise AssertionError("unreachable_installation_attempt")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fiji", required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--status-file", type=Path)
    parser.add_argument("--recovery-scope", type=Path)
    parser.add_argument("--attempts", type=int, choices=(1, 2), default=2)
    parser.add_argument("--compile-seconds", type=int, default=300)
    parser.add_argument("--execution-seconds", type=int, default=300)
    args = parser.parse_args()
    try:
        report = run_check(args.fiji, args.scratch, args.result, attempts=args.attempts,
                           compile_seconds=args.compile_seconds, execution_seconds=args.execution_seconds,
                           status_file=args.status_file, recovery_scope=args.recovery_scope)
    except OSError:
        print("CYTELLECT_INSTALL_CHECK: installation_report_write_failed", file=sys.stderr)
        return 2
    if report["status"] != "passed":
        print("CYTELLECT_INSTALL_CHECK: " + report["error_code"], file=sys.stderr)
        return 1
    if report.get("report_error_code"):
        print("CYTELLECT_INSTALL_CHECK: installation_report_write_failed", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
