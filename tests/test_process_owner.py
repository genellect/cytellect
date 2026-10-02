"""A Windows shim owns its interpreter; an unrelated launching shell does not."""
import sys
from types import SimpleNamespace

import pytest
from cytellect_api import process_owner


def test_direct_interpreter_does_not_watch_shell(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")

    def unexpected_parent_lookup():
        pytest.fail("ordinary launching shell must not control the application lifetime")

    monkeypatch.setattr(process_owner.psutil, "Process", lambda: SimpleNamespace(
        exe=lambda: sys.executable, parent=unexpected_parent_lookup))
    assert process_owner.redirector_owner() is None


def test_redirector_missing_before_application_start_fails_closed(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(process_owner.os.path, "samefile", lambda *_: False)
    monkeypatch.setattr(process_owner.psutil, "Process", lambda: SimpleNamespace(
        exe=lambda: "base-python.exe", parent=lambda: None))
    with pytest.raises(RuntimeError, match="local_redirector_owner_missing"):
        process_owner.redirector_owner()
