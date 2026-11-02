import json
import os
import sys
import threading

import pytest
from cytellect_analysis.engine_diagnostics import (
    NativeCheckFailure,
    current_policy,
    installation_execution_policy,
    pinned_java_environment,
    run_native_check,
)


def test_installer_execution_policy_is_scoped_and_resets_after_failure():
    assert current_policy() is None
    with pytest.raises(RuntimeError):
        with installation_execution_policy(12, 34, lambda event: None):
            assert current_policy().compile_seconds == 12
            assert current_policy().execution_seconds == 34
            raise RuntimeError("control flow")
    assert current_policy() is None


def test_native_failure_drains_large_output_but_retains_only_fixed_codes(tmp_path):
    private_path = "/".join(("C:", "Users", "PrivateUser", "study.tif"))
    script = f"import sys; sys.stderr.write('OutOfMemoryError '+{private_path!r}+' secret@example.test\\n'+'x'*200000); sys.exit(7)"
    with pytest.raises(NativeCheckFailure) as caught:
        run_native_check([sys.executable, "-c", script], tmp_path, 10, os.environ.copy())
    event = caught.value.event
    assert str(caught.value) == "fiji_execution_failed"
    assert event["exit_code"] == 7 and event["native_hint"] == "java_heap_exhausted"
    assert all(value not in json.dumps(event) for value in ("PrivateUser", "study.tif", "example.test", "x" * 100))


def test_native_timeout_reaps_owned_process(tmp_path):
    with pytest.raises(NativeCheckFailure) as caught:
        run_native_check([sys.executable, "-c", "import time; time.sleep(30)"], tmp_path, 1, os.environ.copy())
    assert str(caught.value) == "fiji_timeout"
    assert caught.value.event["exit_code"] is not None
    assert caught.value.event["elapsed_seconds"] < 10


def test_fixed_java_does_not_inherit_another_installations_options():
    source = {"JAVA_TOOL_OPTIONS": "-invalid", "jdk_java_options": "--bad", "_JAVA_OPTIONS": "-wrong",
              "JDK_JAVAC_OPTIONS": "bad", "JAVA_HOME": "another", "JRE_HOME": "other", "CLASSPATH": "other",
              "PATH": "keep", "SystemRoot": "keep-too"}
    assert pinned_java_environment(source) == {"PATH": "keep", "SystemRoot": "keep-too"}
    assert source["JAVA_TOOL_OPTIONS"] == "-invalid"


def test_sharing_violation_cleanup_retries_and_reports_without_rerunning_engine(tmp_path, monkeypatch):
    from cytellect_analysis import engine_diagnostics as diagnostics

    preserved = tmp_path / "preserved.txt"
    preserved.write_text("keep")
    temporary = diagnostics.tempfile.TemporaryDirectory(prefix="owned-", dir=tmp_path)
    (diagnostics.Path(temporary.name) / "generated.dll").write_bytes(b"unit cleanup bytes")
    calls = []

    def cleanup():
        calls.append(1)
        if len(calls) < 3:
            error = PermissionError("private path must not be persisted")
            error.winerror = 32
            raise error
        temporary.cleanup()

    monkeypatch.setattr(diagnostics.time, "sleep", lambda seconds: None)
    events = []
    with installation_execution_policy(120, 300, events.append):
        diagnostics.cleanup_owned_temporary(cleanup)
    assert len(calls) == 3 and list(tmp_path.iterdir()) == [preserved]
    assert events[0]["state"] == "passed" and events[0]["attempts"] == 3
    assert "private" not in json.dumps(events)


def test_persistent_sharing_violation_has_a_finite_budget(monkeypatch):
    from cytellect_analysis import engine_diagnostics as diagnostics

    clock = [0.0]
    monkeypatch.setattr(diagnostics.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(diagnostics.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))

    def locked():
        error = PermissionError("redacted")
        error.winerror = 32
        raise error

    with pytest.raises(NativeCheckFailure, match="fiji_temporary_cleanup_failed") as caught:
        diagnostics.cleanup_owned_temporary(locked)
    assert clock[0] == 10 and caught.value.event["native_error_code"] == 32
    assert caught.value.event["native_hint"] == "file_in_use"


def test_cleanup_failure_never_replaces_the_first_engine_error(tmp_path, monkeypatch):
    from cytellect_analysis import engine_diagnostics as diagnostics

    actual = diagnostics.tempfile.TemporaryDirectory
    temporary = actual(prefix="owned-", dir=tmp_path)

    class Locked:
        name = temporary.name

        def cleanup(self):
            error = PermissionError("not retryable access denial")
            error.winerror = 5
            raise error

    monkeypatch.setattr(diagnostics.tempfile, "TemporaryDirectory", lambda **kwargs: Locked())
    events = []
    with installation_execution_policy(120, 300, events.append):
        with pytest.raises(RuntimeError, match="first_engine_error"):
            with diagnostics.owned_temporary_directory(prefix="owned-", directory=tmp_path):
                raise RuntimeError("first_engine_error")
    assert events[-1]["error_code"] == "fiji_temporary_cleanup_failed"
    assert events[-1]["attempts"] == 1
    temporary.cleanup()


@pytest.mark.skipif(os.name != "nt", reason="Actual Windows sharing violation")
def test_actual_windows_file_lock_is_released_and_owned_temp_is_removed(tmp_path):
    from cytellect_analysis import engine_diagnostics as diagnostics

    temporary = diagnostics.tempfile.TemporaryDirectory(prefix="owned-", dir=tmp_path)
    path = diagnostics.Path(temporary.name) / "generated.dll"
    path.write_bytes(b"non-executable unit cleanup fixture")
    handle = path.open("rb")
    release = threading.Timer(0.5, handle.close)
    release.start()
    events = []
    try:
        with installation_execution_policy(120, 300, events.append):
            diagnostics.cleanup_owned_temporary(temporary.cleanup)
    finally:
        release.join()
        handle.close()
        temporary.cleanup()
    assert not path.parent.exists()
    assert events[-1]["state"] == "passed" and events[-1]["native_error_code"] == 32
