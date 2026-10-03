import hashlib
import json
import os
import shutil
import subprocess

import pytest
from cytellect_api import local
from cytellect_api.local import installed_source_revision

PACKAGES = {
    "cytellect_analysis": "packages/analysis/src/cytellect_analysis",
    "cytellect_api": "services/api/src/cytellect_api",
    "cytellect_worker": "services/worker/src/cytellect_worker",
}


def release(tmp_path):
    entries = []
    for relative in ("packages/analysis/src/cytellect_analysis", "services/api/src/cytellect_api",
                     "services/worker/src/cytellect_worker"):
        file = tmp_path / relative / "__init__.py"
        file.parent.mkdir(parents=True)
        file.write_bytes(b"# packaged source\n")
        entries.append({"path": file.relative_to(tmp_path).as_posix(), "size": file.stat().st_size,
                        "sha256": hashlib.sha256(file.read_bytes()).hexdigest()})
    data = {"schema": "cytellect-local-release/1", "source_commit": "a" * 40, "files": entries}
    (tmp_path / "local-release.json").write_text(json.dumps(data), encoding="utf-8")
    return data


def test_packaged_revision_requires_unchanged_and_complete_source(tmp_path):
    release(tmp_path)
    assert installed_source_revision(tmp_path) == "a" * 40
    source = tmp_path / "packages/analysis/src/cytellect_analysis/__init__.py"
    source.write_bytes(b"# changed source!\n")
    assert installed_source_revision(tmp_path) is None


def test_unlisted_extra_source_or_missing_manifest_never_claim_commit(tmp_path):
    assert installed_source_revision(tmp_path) is None
    release(tmp_path)
    (tmp_path / "services/api/src/cytellect_api/unlisted.py").write_text("# not in release")
    assert installed_source_revision(tmp_path) is None


def test_incomplete_and_escaping_manifest_cannot_claim_commit(tmp_path):
    data = release(tmp_path)
    data["files"].pop()
    manifest = tmp_path / "local-release.json"
    manifest.write_text(json.dumps(data))
    assert installed_source_revision(tmp_path) is None
    data["files"][0]["path"] = "../outside.py"
    manifest.write_text(json.dumps(data))
    assert installed_source_revision(tmp_path) is None


def normal_wheel_fixture(root, monkeypatch):
    """Byte fixtures only: no wheel build, install or imported fixture code."""
    data = release(root)
    for relative in PACKAGES.values():
        for name in ("local.py", "nested/operation.py"):
            path = root / relative / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"# never executed: " + relative.encode() + b"/" + name.encode() + b"\n")
            data["files"].append({"path": path.relative_to(root).as_posix(), "size": path.stat().st_size,
                                  "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    (root / "local-release.json").write_text(json.dumps(data), encoding="utf-8")
    installed = root / ".venv/Lib/site-packages"
    for package, relative in PACKAGES.items():
        shutil.copytree(root / relative, installed / package)
    monkeypatch.setattr(local, "__file__", str(installed / "cytellect_api/local.py"))
    return installed


def test_normal_wheel_requires_matching_source_and_all_installed_packages(tmp_path, monkeypatch):
    normal_wheel_fixture(tmp_path, monkeypatch)
    assert installed_source_revision() == "a" * 40
    assert installed_source_revision(tmp_path) == "a" * 40
    source = tmp_path / PACKAGES["cytellect_analysis"] / "nested/operation.py"
    source.write_bytes(b"# source modified independently of the installed wheel\n")
    assert installed_source_revision() is None


@pytest.mark.parametrize("package", PACKAGES)
@pytest.mark.parametrize("fault", ["extra", "missing", "modified", "missing-package"])
def test_normal_wheel_rejects_unrecorded_missing_or_changed_python_payload(tmp_path, monkeypatch, package, fault):
    installed = normal_wheel_fixture(tmp_path, monkeypatch)
    directory = installed / package
    if fault == "extra":
        (directory / "nested/unlisted.py").write_bytes(b"# not in the recorded source\n")
    elif fault == "missing":
        (directory / "nested/operation.py").unlink()
    elif fault == "missing-package":
        directory.rename(installed / (package + "-absent"))
    else:
        target = directory / "nested/operation.py"
        original = target.read_bytes()
        target.write_bytes(b"!" + original[1:])  # Same length: a size-only check must fail.
    assert installed_source_revision(tmp_path) is None
    assert installed_source_revision() is None


def test_explicit_unrelated_root_remains_manifest_inspection(tmp_path, monkeypatch):
    active = tmp_path / "active"
    active.mkdir()
    installed = normal_wheel_fixture(active, monkeypatch)
    (installed / "cytellect_worker/nested/operation.py").unlink()
    inspected = tmp_path / "inspected"
    inspected.mkdir()
    release(inspected)
    assert installed_source_revision() is None
    assert installed_source_revision(inspected) == "a" * 40


def test_editable_execution_keeps_complete_manifest_verification(tmp_path, monkeypatch):
    normal_wheel_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(local, "__file__", str(tmp_path / PACKAGES["cytellect_api"] / "local.py"))
    # Unused wheel files do not override the active editable source identity.
    (tmp_path / ".venv/Lib/site-packages/cytellect_worker/nested/operation.py").unlink()
    assert installed_source_revision() == "a" * 40
    (tmp_path / PACKAGES["cytellect_worker"] / "not-recorded.py").write_bytes(b"# changed editable source")
    assert installed_source_revision() is None


@pytest.mark.skipif(os.name != "nt", reason="Windows normal-wheel junction boundary")
@pytest.mark.parametrize("package", PACKAGES)
def test_normal_wheel_rejects_package_junction_even_to_identical_bytes_in_app(tmp_path, monkeypatch, package):
    installed = normal_wheel_fixture(tmp_path, monkeypatch)
    directory = installed / package
    redirected = tmp_path / "redirected" / package
    redirected.parent.mkdir()
    directory.rename(redirected)
    # mklink /J only creates a scratch junction; it needs no policy/registry change.
    result = subprocess.run(
        [os.environ["ComSpec"], "/c", "mklink", "/J", str(directory), str(redirected)],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert result.returncode == 0, "test junction creation failed"
    assert directory.resolve() == redirected.resolve()
    assert installed_source_revision(tmp_path) is None
    assert installed_source_revision() is None


@pytest.mark.skipif(os.name != "nt", reason="Windows normal-wheel junction boundary")
def test_normal_wheel_rejects_extra_linked_subpackage_outside_recorded_file_set(tmp_path, monkeypatch):
    installed = normal_wheel_fixture(tmp_path, monkeypatch)
    redirected = tmp_path / "unrecorded"
    redirected.mkdir()
    (redirected / "__init__.py").write_bytes(b"# unrecorded package supplied through a junction")
    junction = installed / "cytellect_analysis/extra"
    result = subprocess.run(
        [os.environ["ComSpec"], "/c", "mklink", "/J", str(junction), str(redirected)],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert result.returncode == 0, "test junction creation failed"
    assert installed_source_revision() is None
