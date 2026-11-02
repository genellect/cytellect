"""Bounded installer diagnostics; never retain native output or local paths."""
from __future__ import annotations

import subprocess
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class InstallationExecutionPolicy:
    compile_seconds: int
    execution_seconds: int
    record: Callable[[dict[str, Any]], None]


_policy: ContextVar[InstallationExecutionPolicy | None] = ContextVar("installation_execution_policy", default=None)


def current_policy() -> InstallationExecutionPolicy | None:
    return _policy.get()


@contextmanager
def installation_execution_policy(compile_seconds: int, execution_seconds: int,
                                  record: Callable[[dict[str, Any]], None]) -> Iterator[None]:
    if (type(compile_seconds) is not int or not 1 <= compile_seconds <= 300
            or type(execution_seconds) is not int or not 1 <= execution_seconds <= 1800):
        raise ValueError("installation_timeout_invalid")
    token = _policy.set(InstallationExecutionPolicy(compile_seconds, execution_seconds, record))
    try:
        yield
    finally:
        _policy.reset(token)


class NativeCheckFailure(RuntimeError):
    def __init__(self, code: str, event: dict[str, Any]):
        super().__init__(code)
        self.event = event
        self.diagnostic = event


def cleanup_owned_temporary(cleanup: Callable[[], None]) -> None:
    """Retry only Windows sharing violations, after the owned Java process exited."""
    started = time.monotonic()
    attempts = 0
    native_error = None
    while True:
        attempts += 1
        try:
            cleanup()
            break
        except OSError as error:
            native_error = getattr(error, "winerror", None) or error.errno
            remaining = 10 - (time.monotonic() - started)
            if getattr(error, "winerror", None) in {32, 33} and remaining > 0:
                time.sleep(min(0.25 * attempts, 1, remaining))
                continue
            event = {"operation": "cleanup_scratch", "state": "failed", "attempts": attempts,
                     "timeout_seconds": 10, "elapsed_seconds": round(time.monotonic() - started, 3),
                     "native_error_code": native_error, "native_hint": "file_in_use" if native_error in {32, 33} else None,
                     "error_code": "fiji_temporary_cleanup_failed"}
            if (policy := current_policy()) is not None:
                policy.record(event)
            raise NativeCheckFailure("fiji_temporary_cleanup_failed", event) from None
    if attempts > 1 and (policy := current_policy()) is not None:
        policy.record({"operation": "cleanup_scratch", "state": "passed", "attempts": attempts,
                       "timeout_seconds": 10, "elapsed_seconds": round(time.monotonic() - started, 3),
                       "native_error_code": native_error, "error_code": None})


@contextmanager
def owned_temporary_directory(*, prefix: str, directory: Path) -> Iterator[Path]:
    temporary = tempfile.TemporaryDirectory(prefix=prefix, dir=directory)
    try:
        yield Path(temporary.name)
    except BaseException:
        # Preserve the first execution failure if cleanup also fails. Its separate
        # fixed event remains in the installer report, and setup owns the parent.
        try:
            cleanup_owned_temporary(temporary.cleanup)
        except NativeCheckFailure:
            pass
        raise
    else:
        cleanup_owned_temporary(temporary.cleanup)


def native_hint(output: bytes) -> str | None:
    """Reduce in-memory output to fixed codes; no text supplied by Java is persisted."""
    lower = output.decode("utf-8", errors="replace").lower()
    for needle, code in (
        ("os error 4551", "windows_application_control_blocked"),
        ("outofmemoryerror", "java_heap_exhausted"),
        ("could not reserve enough space", "java_memory_reservation_failed"),
        ("unsatisfiedlinkerror", "java_native_library_error"),
        ("classnotfoundexception", "java_class_missing"),
        ("noclassdeffounderror", "java_class_missing"),
        ("could not find or load main class", "java_main_class_missing"),
        ("accessdeniedexception", "file_access_denied"),
        ("access is denied", "file_access_denied"),
    ):
        if needle in lower:
            return code
    return None


def run_native_check(command: list[str], directory: Path, timeout: int, env: dict) -> dict[str, Any]:
    """Drain stderr without deadlock, retaining at most 64 KiB in memory only."""
    started = time.monotonic()
    operation = "compile_bridge" if Path(command[0]).stem.lower() == "javac" else "run_engine"
    event: dict[str, Any] = {"operation": operation, "timeout_seconds": timeout,
                             "exit_code": None, "native_error_code": None, "native_hint": None}
    captured = bytearray()
    code = None
    try:
        with subprocess.Popen(command, cwd=directory, env=env, stdout=subprocess.DEVNULL,
                              stderr=subprocess.PIPE) as process:
            assert process.stderr is not None
            stream = process.stderr

            def drain() -> None:
                try:
                    while chunk := stream.read(4096):
                        captured.extend(chunk[:max(0, 65536 - len(captured))])
                except OSError:
                    pass

            reader = threading.Thread(target=drain, daemon=True)
            reader.start()
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                code = "fiji_timeout"
                process.kill()
                process.wait()
            finally:
                reader.join()
            event["exit_code"] = process.returncode
            event["native_hint"] = native_hint(bytes(captured))
            if process.returncode and code is None:
                code = "fiji_execution_failed"
    except OSError as error:
        code = "fiji_process_unavailable"
        event["native_error_code"] = getattr(error, "winerror", None) or error.errno
        if getattr(error, "winerror", None) == 4551:
            event["native_hint"] = "windows_application_control_blocked"
    event["elapsed_seconds"] = round(time.monotonic() - started, 3)
    event["error_code"] = code
    if code is not None:
        raise NativeCheckFailure(code, event)
    return event


def pinned_java_environment(source: dict) -> dict:
    """The fixed runtime must not inherit options for another Java installation."""
    implicit = {"JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS", "JDK_JAVAC_OPTIONS",
                "JAVA_HOME", "JRE_HOME", "CLASSPATH"}
    return {key: value for key, value in source.items() if key.upper() not in implicit}
