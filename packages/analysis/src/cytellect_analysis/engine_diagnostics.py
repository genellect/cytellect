"""Bounded installer diagnostics; never retain native output or local paths."""
from __future__ import annotations

import os
import signal
import subprocess
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .temporary_storage import claimed_scratch, remove_scratch


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


def cleanup_owned_temporary(cleanup: Callable[[], None], *, defer: bool = False) -> None:
    """Retry only Windows sharing violations, after the owned Java process exited."""
    started = time.monotonic()
    attempts = 0
    native_error = None
    while True:
        attempts += 1
        try:
            cleanup()
            break
        except (OSError, ValueError) as error:
            native_error = getattr(error, "winerror", None) or getattr(error, "errno", None)
            remaining = 10 - (time.monotonic() - started)
            if getattr(error, "winerror", None) in {32, 33} and remaining > 0:
                time.sleep(min(0.25 * attempts, 1, remaining))
                continue
            event = {"operation": "cleanup_scratch", "state": "deferred" if defer else "failed", "attempts": attempts,
                     "timeout_seconds": 10, "elapsed_seconds": round(time.monotonic() - started, 3),
                     "native_error_code": native_error, "native_hint": "file_in_use" if native_error in {32, 33} else None,
                     "error_code": "fiji_temporary_cleanup_failed"}
            if (policy := current_policy()) is not None:
                policy.record(event)
            if defer:
                return
            raise NativeCheckFailure("fiji_temporary_cleanup_failed", event) from None
    if attempts > 1 and (policy := current_policy()) is not None:
        policy.record({"operation": "cleanup_scratch", "state": "passed", "attempts": attempts,
                       "timeout_seconds": 10, "elapsed_seconds": round(time.monotonic() - started, 3),
                       "native_error_code": native_error, "error_code": None})


@contextmanager
def owned_temporary_directory(*, prefix: str, directory: Path) -> Iterator[Path]:
    with claimed_scratch(directory, prefix) as temporary:
        try:
            yield temporary
        finally:
            # A cleanup-only failure cannot invalidate verified pixels or mask an
            # engine error. The durable journal allows setup/worker recovery later.
            cleanup_owned_temporary(lambda: remove_scratch(temporary), defer=True)


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
    process = None
    try:
        process = subprocess.Popen(command, cwd=directory, env=env, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.PIPE, start_new_session=os.name != "nt",
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        assert process.stderr is not None
        descriptor = process.stderr.fileno()
        # Nonblocking reads also bound EOF handling when a descendant inherits
        # stderr. No reader thread or buffered close can wait for that descendant.
        os.set_blocking(descriptor, False)

        def drain() -> None:
            for _ in range(16):
                try:
                    chunk = os.read(descriptor, 4096)
                except BlockingIOError:
                    break
                if not chunk:
                    break
                captured.extend(chunk[:max(0, 65536 - len(captured))])

        while True:
            drain()
            if process.poll() is not None:
                drain()
                break
            if time.monotonic() - started >= timeout:
                code = "fiji_timeout"
                if os.name == "nt":
                    subprocess.run([str(Path(env.get("SystemRoot", r"C:\Windows")) / "System32/taskkill.exe"),
                                    "/PID", str(process.pid), "/T", "/F"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)
                else:
                    os.killpg(process.pid, signal.SIGKILL)
                break
            time.sleep(0.025)
        event["exit_code"] = process.poll()
        event["native_hint"] = native_hint(bytes(captured))
        if process.returncode and code is None:
            code = "fiji_execution_failed"
    except subprocess.TimeoutExpired:
        code = code or "fiji_timeout"
    except OSError as error:
        code = code or "fiji_process_unavailable"
        event["native_error_code"] = getattr(error, "winerror", None) or error.errno
        if getattr(error, "winerror", None) == 4551:
            event["native_hint"] = "windows_application_control_blocked"
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                code = code or "fiji_timeout"
            event["exit_code"] = process.returncode
            if process.stderr is not None:
                process.stderr.close()
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
