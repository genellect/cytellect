"""Real public-image Fiji check while its actual JNI DLL remains locked >30 s.

Run with the installed interpreter. This is technical runtime acceptance, not
Edge/GUI installation or biological accuracy acceptance. Receipts contain only
fixed codes, durations, public provenance and counts; never native output/paths.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import threading
import time
from pathlib import Path
from typing import Any, BinaryIO

from cytellect_analysis import engine, engine_diagnostics, install_check, temporary_storage


def verify(fiji: str, scratch: Path, output: Path, source_commit: str | None) -> bool:
    if os.name != "nt":
        raise RuntimeError("windows_recovery_check_requires_windows")
    scratch.mkdir(parents=True, exist_ok=True)
    preserved = scratch / "preserved-public-test.txt"
    with preserved.open("x", encoding="ascii") as sentinel:
        sentinel.write("preserve this unrelated test file")
    original = engine.run_native_check
    held: list[BinaryIO] = []
    timers: list[threading.Timer] = []
    observed: dict[str, Any] = {}
    receipt: dict[str, Any] = {"schema": "cytellect-windows-cleanup-recovery/1", "passed": False,
               "python": platform.python_version(), "source_commit": source_commit,
               "scope": "real public-image runtime and native DLL lock; not GUI or biological accuracy acceptance"}

    def checked(command, directory, timeout, env):
        event = original(command, directory, timeout, env)
        if event["operation"] == "run_engine":
            root = Path(next(arg.split("=", 1)[1] for arg in command if arg.startswith("-Djava.io.tmpdir=")))
            members = list(root.rglob("tensorflow_jni.dll"))
            if not members:
                raise RuntimeError("recovery_native_library_missing")
            handle = members[0].open("rb")
            held.append(handle)
            started = time.monotonic()
            observed["dll_sha256"] = hashlib.file_digest(handle, "sha256").hexdigest()

            def release():
                handle.close()
                observed["held_seconds"] = round(time.monotonic() - started, 3)

            timer = threading.Timer(32, release)
            timers.append(timer)
            timer.start()
        return event

    try:
        engine.run_native_check = checked
        report = install_check.run_check(fiji, scratch, output.with_name(output.stem + "-check.json"))
        receipt.update(check_passed=report["status"] == "passed", attempts=len(report["attempts"]),
                       fixture_sha256=report.get("fixture_sha256"), nuclei=report.get("nuclei"),
                       failed_attempt_codes=[attempt.get("error_code") for attempt in report["attempts"]
                                             if attempt["status"] == "failed"],
                       deferred_events=sum(event["state"] == "deferred" for attempt in report["attempts"]
                                           for event in attempt["events"]))
        for timer in timers:
            timer.join(timeout=40)
        receipt.update(observed)
        recovered = temporary_storage.reap_owned_temporaries(scratch, recursive=True)
        receipt.update(recovered=recovered["recovered"], remaining_journals=len(list(scratch.rglob(".cytellect-scratch-*.json"))),
                       unrelated_preserved=preserved.read_text() == "preserve this unrelated test file")
        receipt["passed"] = bool(receipt["check_passed"] and 1 <= receipt["attempts"] <= 2
                                 and "fiji_temporary_cleanup_failed" not in receipt["failed_attempt_codes"]
                                 and receipt["deferred_events"] >= 1 and receipt.get("held_seconds", 0) >= 30
                                 and receipt["remaining_journals"] == 0 and receipt["unrelated_preserved"])
    except (OSError, RuntimeError, StopIteration):
        receipt["error_code"] = "windows_cleanup_recovery_check_failed"
    finally:
        engine.run_native_check = original
        for timer in timers:
            timer.join(timeout=40)
        for handle in held:
            handle.close()
        temporary_storage.reap_owned_temporaries(scratch, recursive=True)
        preserved.unlink(missing_ok=True)
        implementation = {}
        for module in (engine, engine_diagnostics, install_check, temporary_storage):
            if module.__file__ is None:
                raise RuntimeError("recovery_source_unavailable")
            implementation[module.__name__] = hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
        receipt["implementation_sha256"] = implementation
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt["passed"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fiji", required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    return 0 if verify(args.fiji, args.scratch, args.out, args.source_commit) else 1


if __name__ == "__main__":
    raise SystemExit(main())
