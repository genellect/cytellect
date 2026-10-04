"""Real scratch trees exercise collection; never inspect a user installation."""
import json
import os
import subprocess

import pytest
from cytellect_api import local_storage as storage


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def installation(tmp_path):
    write(tmp_path / "setup-root.json", {"product": "cytellect-local", "schema": 1})
    return tmp_path


def install(root, number, runtime="a" * 16):
    version = f"0.1.0-local.{number}"
    commit = f"{number:040x}"
    app = root / f"apps/{version}-{commit[:12]}"
    created = []
    for relative in [f"runtimes/fiji-{runtime}", "runtimes/python-test"]:
        path = root / relative
        if not path.exists():
            path.mkdir(parents=True)
            (path / "engine.bin").write_bytes(b"fixed public test runtime")
            created.append(relative)
    import hashlib
    payload = b"public test application"
    write(app / "local-release.json", {"version": version, "source_commit": commit,
          "files": [{"path": "payload.bin", "sha256": hashlib.sha256(payload).hexdigest()}]})
    write(app / "setup-complete.json", {"version": version, "source_commit": commit,
          "app": str(app), "fiji": str(root / f"runtimes/fiji-{runtime}"), "python_build": "test"})
    (app / "payload.bin").write_bytes(payload)
    result = storage.maintain(root, app, created, processes=[])
    return app, result


def test_three_versions_keep_current_previous_share_one_fiji(installation):
    root = installation
    one, _ = install(root, 1)
    two, _ = install(root, 2)
    assert one.exists() and two.exists()
    three, result = install(root, 3)
    assert not one.exists() and two.exists() and three.exists()
    assert result["retained_apps"] == 2 and result["reclaimed_bytes"] > 0
    assert len(list((root / "runtimes").glob("fiji-*"))) == 1
    assert storage.maintain(root, three, [], processes=[])["reclaimed_bytes"] == 0


def test_wheel_members_and_empty_uv_lock_are_owned_but_modified_members_are_not(installation):
    import base64
    import hashlib
    app, _ = install(installation, 1)
    site = app / ".venv/Lib/site-packages"
    record = site / "example-1.dist-info/RECORD"
    record.parent.mkdir(parents=True)
    payload = b"public package bytes"
    (site / "example.py").write_bytes(payload)
    (app / ".venv/.lock").write_bytes(b"")
    digest = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).decode().rstrip("=")
    record.write_text(f"example.py,sha256={digest},{len(payload)}\nexample-1.dist-info/RECORD,,\n")
    relative = app.relative_to(installation).as_posix()
    release = json.loads((app / "local-release.json").read_text())
    storage.declared_app_files(installation, relative, release, storage.inventory(installation, relative))
    (site / "example.py").write_bytes(b"changed")
    with pytest.raises(ValueError, match="storage_wheel_modified"):
        storage.declared_app_files(installation, relative, release, storage.inventory(installation, relative))


@pytest.mark.parametrize("protection", ["file_changed", "extra_file", "extra_directory", "active_app", "active_runtime", "unobservable"])
def test_never_collect_modified_or_running_versions(installation, monkeypatch, protection):
    root = installation
    one, _ = install(root, 1)
    install(root, 2)
    if protection == "file_changed":
        (one / "payload.bin").write_bytes(b"changed")
    if protection == "extra_file":
        (one / "private-file.txt").write_bytes(b"do not delete")
    if protection == "extra_directory":
        (one / "private-empty").mkdir()
    original = storage.maintain
    if protection.startswith("active") or protection == "unobservable":
        processes = None if protection == "unobservable" else [str(one if protection == "active_app" else root / ("runtimes/fiji-" + "a" * 16))]
        monkeypatch.setattr(storage, "maintain", lambda root, app, created, **kwargs: original(root, app, created, processes=processes))
    install(root, 3)
    assert one.is_dir()


def test_obsolete_runtime_only_removed_after_last_reference(installation):
    root = installation
    install(root, 1, "a" * 16)
    install(root, 2, "b" * 16)
    install(root, 3, "b" * 16)
    assert not (root / ("runtimes/fiji-" + "a" * 16)).exists()
    assert (root / ("runtimes/fiji-" + "b" * 16)).exists()


def test_modified_retained_app_makes_runtime_references_untrusted(installation):
    root = installation
    install(root, 1, "a" * 16)
    two, _ = install(root, 2, "b" * 16)
    marker_path = two / "setup-complete.json"
    marker = json.loads(marker_path.read_text())
    marker["fiji"] = str(root / ("runtimes/fiji-" + "a" * 16))
    write(marker_path, marker)
    install(root, 3, "b" * 16)
    assert (root / ("runtimes/fiji-" + "a" * 16)).exists()


def test_unknown_incomplete_and_research_data_untouched(installation):
    root = installation
    one, _ = install(root, 1)
    install(root, 2)
    unknown = root / "apps/unknown"
    write(unknown / "private.json", {"never": "delete"})
    write(root / "data/private.json", {"never": "delete"})
    # A failed new setup never invokes the success hook; merely creating its
    # partial directory cannot make it a successful generation.
    (root / "apps/incomplete").mkdir()
    assert one.exists()
    install(root, 3, "b" * 16)
    assert (unknown / "private.json").exists() and (root / "data/private.json").exists()
    assert (root / "apps/incomplete").exists()
    assert (root / ("runtimes/fiji-" + "a" * 16)).exists()


def test_corrupt_ledger_cannot_target_data(installation):
    root = installation
    one, _ = install(root, 1)
    ledger = json.loads((root / "setup-storage.json").read_text())
    ledger["order"] = ["data"]
    ledger["apps"]["data"] = ledger["apps"].pop(one.relative_to(root).as_posix())
    write(root / "setup-storage.json", ledger)
    with pytest.raises(ValueError, match="storage_ledger_invalid"):
        install(root, 2)
    assert one.exists()


def test_redirected_member_and_ancestor_are_rejected(installation, tmp_path):
    root = installation
    one, _ = install(root, 1)
    outside = root / "data"
    outside.mkdir()
    if os.name == "nt":
        # Junction creation is unprivileged. Both targets are scratch-owned;
        # the collector must reject this before following or deleting anything.
        subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                        "New-Item -ItemType Junction -Path $env:STORAGE_LINK -Value $env:STORAGE_TARGET | Out-Null"],
                       env={**os.environ, "STORAGE_LINK": str(one / "redirect"), "STORAGE_TARGET": str(outside)},
                       check=True, capture_output=True, timeout=30)
    else:
        (one / "redirect").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="redirected_storage_path"):
        storage.inventory(root, one.relative_to(root).as_posix())
    assert outside.exists()


def test_process_inventory_failure_disables_collection(monkeypatch):
    def denied():
        raise storage.psutil.AccessDenied()
    monkeypatch.setattr(storage.psutil, "Process", denied)
    assert storage.process_paths() is None


def test_launch_and_prune_share_an_os_released_lock(installation):
    with storage.usage_lock(installation):
        with pytest.raises(ValueError, match="local_runtime_already_in_use"):
            with storage.usage_lock(installation):
                pytest.fail("concurrent launch/collection lock admitted")
    with storage.usage_lock(installation):
        pass


def test_known_archives_are_pruned_unknown_or_modified_cache_is_preserved(installation):
    root = installation
    one, _ = install(root, 1)
    # Add cache records exactly as a successful runtime setup does.
    cache = root / "setup-cache"
    cache.mkdir()
    old_hash = "a" * 64
    owned = cache / f"python-{old_hash}.zip"
    owned.write_bytes(b"owned cache")
    import hashlib
    digest = hashlib.sha256(owned.read_bytes()).hexdigest()
    ledger = json.loads((root / "setup-storage.json").read_text())
    ledger["archives"][owned.relative_to(root).as_posix()] = digest
    ledger["apps"][one.relative_to(root).as_posix()]["archives"] = [owned.relative_to(root).as_posix()]
    write(root / "setup-storage.json", ledger)
    unknown = cache / "unknown.zip"
    unknown.write_bytes(b"do not delete")
    install(root, 2)
    assert owned.exists()
    _, result = install(root, 3)
    assert not owned.exists() and unknown.exists()
    assert result["unmanaged_cache_retained"]


@pytest.mark.parametrize("extra", ["research.txt", ".venv/Lib/site-packages/private.txt"])
def test_retry_cannot_adopt_undeclared_files_as_owned(installation, extra):
    root = installation
    app, _ = install(root, 1)
    ledger = json.loads((root / "setup-storage.json").read_text())
    ledger["order"] = []
    ledger["apps"] = {}
    write(root / "setup-storage.json", ledger)
    write(app / extra, {"research": "not owned by installer"})
    with pytest.raises(ValueError, match="storage_(unowned|wheel_inventory_missing)"):
        storage.maintain(root, app, [], processes=[])
    assert (app / extra).exists()


def test_commit_failure_after_removal_recovers_missing_recorded_tree(installation, monkeypatch):
    root = installation
    one, _ = install(root, 1)
    install(root, 2)
    original = storage.persist
    calls = 0

    def fail_final(root, ledger):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("controlled final-write failure")
        original(root, ledger)

    monkeypatch.setattr(storage, "persist", fail_final)
    with pytest.raises(OSError, match="controlled"):
        install(root, 3)
    assert not one.exists()
    monkeypatch.setattr(storage, "persist", original)
    # An old interrupted fixed-name temp is not a permanent lock or an adopted file.
    write(root / "setup-storage.new.json", {"unrelated": "preserve"})
    app = root / ("apps/0.1.0-local.3-" + "0" * 12)
    storage.maintain(root, app, [], processes=[])
    ledger = json.loads((root / "setup-storage.json").read_text())
    assert len(ledger["apps"]) == 2 and ledger["pending"] == []
    assert (root / "setup-storage.new.json").exists()


def test_interrupted_member_removal_resumes_only_verified_remaining_files(installation, monkeypatch):
    root = installation
    one, _ = install(root, 1)
    install(root, 2)
    original = type(one).unlink
    failed = False

    def interrupted(path, *args, **kwargs):
        nonlocal failed
        result = original(path, *args, **kwargs)
        if path.parent == one and not failed:
            failed = True
            raise OSError("controlled interruption after unlink")
        return result

    monkeypatch.setattr(type(one), "unlink", interrupted)
    app, _ = install(root, 3)
    assert one.exists()
    monkeypatch.setattr(type(one), "unlink", original)
    storage.maintain(root, app, [], processes=[])
    assert not one.exists()
