import json
import os
import sys

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
