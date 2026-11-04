"""Legacy/interrupted installation migration on owned filesystem byte fixtures."""
import hashlib
import json

import pytest
from cytellect_api import local_storage as storage
from test_local_storage import install, write


@pytest.fixture
def root(tmp_path):
    write(tmp_path / "setup-root.json", {"product": "cytellect-local", "schema": 1})
    return tmp_path


def failed_legacy(root):
    relative = "apps/0.1.0-local.21-" + "a" * 12
    app = root / relative
    app.mkdir(parents=True)
    payload = b"public filesystem ownership fixture"
    (app / "payload.bin").write_bytes(payload)
    write(app / "local-release.json", {"schema": "cytellect-local-release/1", "platform": "windows-x64",
        "version": "0.1.0-local.21", "source_commit": "a" * 40,
        "files": [{"path": "payload.bin", "sha256": hashlib.sha256(payload).hexdigest()}]})
    return app


def attempt(root, app, runtimes):
    identity = "12345678" + "0" * 24
    write(root / "setup-cache/a-12345678/setup-attempt.json", {
        "schema": "cytellect-setup-attempt/1", "id": identity, "directory": "setup-cache/a-12345678",
        "app": app.relative_to(root).as_posix(), "app_owned": True, "validated": True, "runtimes": runtimes})
    return identity


def test_failed_legacy_app_no_longer_blocks_obsolete_managed_runtime_collection(root):
    one, _ = install(root, 1)
    legacy = failed_legacy(root)
    install(root, 2, "b" * 16)
    _, result = install(root, 3, "b" * 16)
    assert not legacy.exists() and not one.exists()
    assert not (root / ("runtimes/fiji-" + "a" * 16)).exists()
    assert not result["unknown_apps_retained"]


@pytest.mark.parametrize("protection", ["extra_file", "changed_file", "active"])
def test_legacy_recovery_preserves_unknown_modified_or_running_trees(root, protection):
    current, _ = install(root, 1)
    legacy = failed_legacy(root)
    processes = []
    if protection == "extra_file":
        (legacy / "unowned.txt").write_text("preserve")
    elif protection == "changed_file":
        (legacy / "payload.bin").write_text("changed; preserve")
    else:
        processes = [str(legacy / ".venv/Scripts/python.exe")]
    result = storage.maintain(root, current, [], processes=processes)
    assert legacy.exists() and (legacy / "payload.bin").exists()
    assert result["unknown_apps_retained"]


def test_legacy_removal_recovers_after_proof_files_have_already_been_deleted(root, monkeypatch):
    current, _ = install(root, 1)
    legacy = failed_legacy(root)
    original = type(legacy).rmdir

    def interrupted(path):
        if path == legacy:
            raise PermissionError("controlled empty-directory removal interruption")
        return original(path)

    monkeypatch.setattr(type(legacy), "rmdir", interrupted)
    storage.maintain(root, current, [], processes=[])
    assert legacy.is_dir() and list(legacy.iterdir()) == []
    monkeypatch.setattr(type(legacy), "rmdir", original)
    storage.maintain(root, current, [], processes=[])
    assert not legacy.exists()


def test_next_version_recovers_validated_unregistered_prior_generation(root):
    first, _ = install(root, 1)
    ledger_path = root / "setup-storage.json"
    ledger = json.loads(ledger_path.read_text())
    identity = attempt(root, first, list(ledger["runtimes"]))
    ledger_path.unlink()  # Power loss before the first storage commit.
    second, result = install(root, 2, "b" * 16)
    assert first.exists() and second.exists()
    assert result["committed_attempt_ids"] == [identity] and result["recovery_errors"] == []
    third, _ = install(root, 3, "b" * 16)
    assert not first.exists() and second.exists() and third.exists()
    assert not (root / ("runtimes/fiji-" + "a" * 16)).exists()


def test_modified_prior_generation_is_preserved_and_recovery_error_is_visible(root):
    first, _ = install(root, 1)
    ledger_path = root / "setup-storage.json"
    ledger = json.loads(ledger_path.read_text())
    attempt(root, first, list(ledger["runtimes"]))
    ledger_path.unlink()
    (first / "extra.txt").write_text("unowned; preserve")
    second, result = install(root, 2, "b" * 16)
    assert first.exists() and second.exists()
    assert result["recovery_errors"] == ["storage_unowned_app_files"]
    assert result["committed_attempt_ids"] == []


@pytest.mark.parametrize("fixed", [True, False])
def test_storage_cli_exposes_only_fixed_error_codes(root, monkeypatch, capsys, fixed):
    import sys

    def fail(*args, **kwargs):
        if fixed:
            raise ValueError("storage_runtime_modified")
        raise PermissionError("private path and arbitrary exception text")

    monkeypatch.setattr(sys, "argv", ["local_storage", "--root", str(root), "--app", str(root / "apps/current")])
    monkeypatch.setattr(storage, "maintain", fail)
    monkeypatch.setattr(storage, "process_paths", lambda: [])
    assert storage.main() == 1
    expected = "storage_runtime_modified" if fixed else "storage_management_failed"
    assert capsys.readouterr().err == "CYTELLECT_STORAGE: " + expected + "\n"


@pytest.mark.parametrize("form", ["inventory", "files"])
def test_exact_input_proof_adopts_reused_unmanaged_runtime_and_later_collects_it(root, form):
    current, _ = install(root, 1)
    ledger_path = root / "setup-storage.json"
    ledger = json.loads(ledger_path.read_text())
    name = "runtimes/fiji-" + "a" * 16
    expected = ledger["runtimes"].pop(name)
    write(ledger_path, ledger)
    claim = {"inventory": expected} if form == "inventory" else {"files": [
        {"path": "engine.bin", "sha256": expected["files"]["engine.bin"], "bytes": expected["bytes"]}]}
    result = storage.maintain(root, current, [], processes=[], runtime_claims={name: claim})
    assert result["recovery_errors"] == []
    assert json.loads(ledger_path.read_text())["runtimes"][name] == expected
    install(root, 2, "b" * 16)
    install(root, 3, "b" * 16)
    assert not (root / name).exists()


def test_reused_runtime_proof_never_adopts_extra_files_or_blocks_app_registration(root):
    current, _ = install(root, 1)
    ledger_path = root / "setup-storage.json"
    ledger = json.loads(ledger_path.read_text())
    name = "runtimes/fiji-" + "a" * 16
    expected = ledger["runtimes"].pop(name)
    write(ledger_path, ledger)
    extra = root / name / "unowned.txt"
    extra.write_text("preserve")
    result = storage.maintain(root, current, [], processes=[], runtime_claims={name: {"inventory": expected}})
    assert result["recovery_errors"] == ["storage_runtime_claim_deferred"]
    assert name not in json.loads(ledger_path.read_text())["runtimes"]
    assert extra.read_text() == "preserve"


@pytest.mark.parametrize("extra", [False, True])
def test_fiji_existing_runtime_proof_requires_every_file_to_match(tmp_path, extra):
    import runpy
    from pathlib import Path

    verify_existing_runtime = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/fiji_setup.py"))["verify_existing_runtime"]

    expected, actual = tmp_path / "expected", tmp_path / "actual"
    for folder in (expected, actual):
        folder.mkdir()
        (folder / "public-runtime.txt").write_bytes(b"fixed public filesystem fixture")
    output = tmp_path / "proof.json"
    if extra:
        (actual / "unowned.txt").write_text("preserve")
        with pytest.raises(RuntimeError, match="storage_runtime_unverified"):
            verify_existing_runtime(expected, actual, output)
        assert not output.exists() and (actual / "unowned.txt").exists()
    else:
        verify_existing_runtime(expected, actual, output)
        assert json.loads(output.read_text()) == storage.inventory(actual.parent, actual.name)
