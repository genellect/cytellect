"""The installer bundle must not accidentally distribute runtime/research files."""
import importlib.util
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "build_local_bundle", Path(__file__).resolve().parents[1] / "scripts/build_local_bundle.py"
)
assert spec is not None and spec.loader is not None
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


@pytest.mark.parametrize("name", [".env.local", "runtime/session.sqlite", "private.tiff", "report.pdf",
                                  "services/api/src/.env", "services/api/src/private.tif",
                                  "services/api/src/__pycache__/app.pyc", "apps/web/public/private.png"])
def test_source_allowlist_denies_research_and_runtime(name):
    assert not bundle.source_allowed(name)


def fixture_tree(root):
    names = bundle.ROOT_FILES | bundle.SCRIPTS | bundle.RUNTIME_RECORDS | bundle.CELLPOSE_ASSETS | {
        "scripts/windows/Cytellect Setup.cmd"}
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("reviewed source", encoding="utf-8")
    web = root / "apps/web/out"
    web.mkdir(parents=True)
    (web / "index.html").write_text("<html>local</html>", encoding="utf-8")
    return sorted(names), web


def test_manifest_has_exact_hashes_and_protects_existing_release(tmp_path):
    names, web = fixture_tree(tmp_path)
    files = bundle.collect_files(tmp_path, names, web)
    output = tmp_path / "release.zip"
    digest = bundle.write_bundle(output, files, "0.1.0-local.1", "a" * 40)
    import hashlib

    with zipfile.ZipFile(output) as archive:
        manifest = json.loads(archive.read("local-release.json"))
        assert manifest["source_commit"] == "a" * 40
        assert {entry["path"] for entry in manifest["files"]} == set(files)
        for entry in manifest["files"]:
            assert hashlib.sha256(archive.read(entry["path"])).hexdigest() == entry["sha256"]
    assert digest == hashlib.sha256(output.read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):
        bundle.write_bundle(output, files, "0.1.0-local.1", "a" * 40)


def test_cellpose_code_locks_and_setup_are_required_in_bundle(tmp_path):
    names, web = fixture_tree(tmp_path)
    files = bundle.collect_files(tmp_path, names, web)
    assert bundle.CELLPOSE_ASSETS <= files.keys()
    assert {"scripts/cellpose_setup.py", "scripts/cellpose_setup.ps1"} <= files.keys()
    assert bundle.source_allowed("packages/analysis/src/cytellect_analysis/cellpose_engine.py")
    assert not bundle.source_allowed("engines/cellpose/cpsam_v2")
    assert not bundle.source_allowed("engines/cellpose/private.npy")
    assert not bundle.source_allowed("engines/cellpose/private-settings.json")
    names.remove("engines/cellpose/runner.py")
    with pytest.raises(ValueError, match="bundle_required_source_missing"):
        bundle.collect_files(tmp_path, names, web)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows optional setup requires Windows PowerShell")
def test_cellpose_optional_setup_missing_python_preserves_settings(tmp_path):
    root = Path(__file__).resolve().parents[1]
    existing = tmp_path / "installation/settings/cellpose.json"
    existing.parent.mkdir(parents=True)
    existing.write_text("existing accepted configuration", encoding="utf-8")
    missing = tmp_path / "missing-python.exe"
    result = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                             str(root / "scripts/cellpose_setup.ps1"),
                             "-Python312", str(missing), "-InstallRoot", str(tmp_path / "installation")],
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    assert result.returncode == 1
    assert "https://www.python.org/downloads/windows/" in result.stdout
    assert str(missing) not in result.stdout + result.stderr
    assert existing.read_text(encoding="utf-8") == "existing accepted configuration"


def test_unexpected_static_file_is_not_silently_distributed(tmp_path):
    names, web = fixture_tree(tmp_path)
    (web / ".env").write_text("not public", encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected_web_asset"):
        bundle.collect_files(tmp_path, names, web)


def test_bundle_rejects_malformed_windows_flight_export(tmp_path):
    names, web = fixture_tree(tmp_path)
    malformed = web / "plan/__next.plan/__PAGE__.txt"
    malformed.parent.mkdir(parents=True)
    malformed.write_bytes(b"flight response")
    with pytest.raises(ValueError, match="bundle_malformed_flight_export"):
        bundle.collect_files(tmp_path, names, web)
    malformed.unlink()
    malformed.parent.rmdir()
    canonical = web / "plan/__next.plan.__PAGE__.txt"
    canonical.write_bytes(b"flight response")
    assert bundle.collect_files(tmp_path, names, web)[
        "apps/web/out/plan/__next.plan.__PAGE__.txt"
    ].read_bytes() == b"flight response"


@pytest.mark.parametrize("suffix", [".mp4", ".csv", ".glb", ".md"])
@pytest.mark.parametrize("folder", ["marketing", "measurements"])
def test_marketing_media_requires_registered_origin_and_exact_bytes(tmp_path, suffix, folder):
    import hashlib

    names, web = fixture_tree(tmp_path)
    relative = f"{folder}/public-example{suffix}"
    asset = web / relative
    asset.parent.mkdir()
    asset.write_bytes(b"public fixture")
    with pytest.raises(ValueError, match="unregistered_marketing_asset"):
        bundle.collect_files(tmp_path, names, web)
    registry = tmp_path / "fixtures/public/allowlist.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(json.dumps({f"apps/web/public/{relative}": {
        "source": "https://example.org/public-fixture", "license": "CC0",
        "sha256": hashlib.sha256(asset.read_bytes()).hexdigest(),
    }}))
    if folder != "marketing":
        with pytest.raises(ValueError, match="unregistered_marketing_asset"):
            bundle.collect_files(tmp_path, names, web)
        return
    assert f"apps/web/out/{relative}" in bundle.collect_files(tmp_path, names, web)
    asset.write_bytes(b"changed content")
    with pytest.raises(ValueError, match="unregistered_marketing_asset"):
        bundle.collect_files(tmp_path, names, web)


def test_current_public_assets_fit_the_local_release_boundary(tmp_path):
    root = Path(__file__).resolve().parents[1]
    names, web = fixture_tree(tmp_path)
    public = subprocess.check_output(
        ["git", "-c", f"safe.directory={root.as_posix()}", "ls-files", "-z", "apps/web/public"],
        cwd=root,
    ).decode().strip("\0").split("\0")
    registry = tmp_path / "fixtures/public/allowlist.json"
    registry.parent.mkdir(parents=True)
    shutil.copyfile(root / "fixtures/public/allowlist.json", registry)
    for name in public:
        relative = Path(name).relative_to("apps/web/public")
        target = web / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, target)
    files = bundle.collect_files(tmp_path, names, web)
    assert len(files) >= len(public)
    assert "apps/web/out/marketing/figure-caption.md" in files


def test_generated_license_is_hashed_but_arbitrary_generated_files_are_rejected(tmp_path):
    names, web = fixture_tree(tmp_path)
    files = bundle.collect_files(tmp_path, names, web)
    output = tmp_path / "notices.zip"
    bundle.write_bundle(output, files, "0.1.0-local.1", "b" * 40,
                        {"THIRD_PARTY_WEB_NOTICES.txt": b"upstream license"})
    with zipfile.ZipFile(output) as archive:
        manifest = json.loads(archive.read("local-release.json"))
        assert "THIRD_PARTY_WEB_NOTICES.txt" in {entry["path"] for entry in manifest["files"]}
    with pytest.raises(ValueError, match="generated_asset_invalid"):
        bundle.write_bundle(tmp_path / "invalid.zip", files, "0.1.0-local.1", "b" * 40,
                            {"private.json": b"never distribute"})


def test_runtime_payload_requires_exact_reviewed_asset_and_enters_release_manifest(tmp_path):
    import hashlib

    names, web = fixture_tree(tmp_path)
    artifact = tmp_path / "runtime-data.zip"
    artifact.write_bytes(b"public data-only fixture")
    data = artifact.read_bytes()
    lock = {"schema": "cytellect-windows-runtime/1", "data_asset": {
        "path": bundle.RUNTIME_DATA, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
    }}
    (tmp_path / "engines/python/windows-runtime.lock.json").write_text(json.dumps(lock))
    payload = bundle.runtime_data(tmp_path, artifact)
    output = tmp_path / "runtime-bundle.zip"
    bundle.write_bundle(output, bundle.collect_files(tmp_path, names, web), "0.1.0-local.1", "c" * 40,
                        {bundle.RUNTIME_DATA: payload})
    with zipfile.ZipFile(output) as archive:
        manifest = json.loads(archive.read("local-release.json"))
        entry = next(row for row in manifest["files"] if row["path"] == bundle.RUNTIME_DATA)
        assert entry["sha256"] == hashlib.sha256(data).hexdigest()
        assert archive.read(bundle.RUNTIME_DATA) == data
    artifact.write_bytes(b"PUBLIC DATA-ONLY FIXTURE")
    with pytest.raises(ValueError, match="bundle_runtime_data_hash_mismatch"):
        bundle.runtime_data(tmp_path, artifact)


CANONICAL_REQUIREMENTS = b"numpy==2.4.6 --hash=sha256:" + b"a" * 64 + b"\n"


def package_inputs(root, fault=None):
    project = {"name": "cytellect", "version": "0.1.0", "requires-python": ">=3.12,<3.15,!=3.13.*"}
    (root / "pyproject.toml").write_text(
        '[project]\n' + "\n".join(f'{key} = "{value}"' for key, value in project.items())
        + '\ndependencies = ["NumPy>=2.2,<3", "public_example>=1,<2; python_version >= \'3.12\'"]\n')
    (root / "uv.lock").write_bytes(b"fixed public fixture lock; never resolved\n")
    files = {}
    for prefix, package in zip(bundle.SOURCE_TREES, ("cytellect_analysis", "cytellect_api", "cytellect_worker")):
        name = package + "/__init__.py"
        path = root / prefix / name
        path.parent.mkdir(parents=True)
        path.write_bytes(b"# public package fixture\n")
        files[name] = path.read_bytes()
    if fault == "modified":
        files["cytellect_analysis/__init__.py"] = b"# unreviewed source\n"
    elif fault == "missing":
        files.pop("cytellect_worker/__init__.py")
    elif fault == "extra_code":
        files["cytellect_api/extra.py"] = b"# extra module\n"
    elif fault == "extra_payload":
        files["outside.pth"] = b"# unreviewed path\n"
    support = ">=3.14" if fault == "support" else "!=3.13.*,<3.15,>=3.12"
    dependencies = ["numpy<3,>=2.2", 'public-example<2,>=1; python_version >= "3.12"']
    if fault == "dependency_changed":
        dependencies[0] = "numpy>=2.1,<3"
    elif fault == "dependency_missing":
        dependencies.pop()
    elif fault == "dependency_extra":
        dependencies.append("unreviewed-math>=1")
    elif fault == "dependency_marker":
        dependencies[1] = 'public-example<2,>=1; python_version >= "3.14"'
    elif fault == "dependency_invalid":
        dependencies[0] = "not a valid requirement >="
    files["cytellect-0.1.0.dist-info/METADATA"] = (
        "Metadata-Version: 2.4\nName: cytellect\nVersion: 0.1.0\nRequires-Python: " + support + "\n"
        + "".join("Requires-Dist: " + value + "\n" for value in dependencies)).encode()
    wheel = root / "cytellect-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "x") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    requirements = root / "exported-requirements.txt"
    requirements.write_bytes(CANONICAL_REQUIREMENTS)
    return wheel, requirements


def test_normal_wheel_and_hash_requirements_are_bound_to_release_source(tmp_path, monkeypatch):
    import hashlib

    wheel, requirements = package_inputs(tmp_path)
    monkeypatch.setattr(bundle, "canonical_requirements", lambda root: CANONICAL_REQUIREMENTS)
    payload = bundle.install_payload(tmp_path, wheel, requirements)
    assert payload["wheels/" + wheel.name] == wheel.read_bytes()
    assert ("./wheels/" + wheel.name + " --hash=sha256:" + hashlib.sha256(wheel.read_bytes()).hexdigest()
            in payload[bundle.INSTALL_REQUIREMENTS].decode())
    assert payload[bundle.INSTALL_REQUIREMENTS].decode().startswith(requirements.read_text())


@pytest.mark.parametrize("fault", ["modified", "missing", "extra_code", "extra_payload", "support",
                                 "dependency_changed", "dependency_missing", "dependency_extra",
                                 "dependency_marker", "dependency_invalid"])
def test_normal_wheel_rejects_source_or_metadata_drift(tmp_path, fault):
    wheel, requirements = package_inputs(tmp_path, fault)
    with pytest.raises(ValueError, match="bundle_project_wheel_"):
        bundle.install_payload(tmp_path, wheel, requirements)


@pytest.mark.parametrize("content", ["", "public-example==1", "-e .\n--hash=sha256:" + "a" * 64,
                                     "file:///private.whl --hash=sha256:" + "a" * 64])
def test_consumer_requirements_cannot_fall_back_to_editable_or_unhashed_input(tmp_path, content):
    wheel, requirements = package_inputs(tmp_path)
    requirements.write_text(content)
    with pytest.raises(ValueError, match="bundle_hashed_requirements_required"):
        bundle.install_payload(tmp_path, wheel, requirements)


@pytest.mark.parametrize("changed", [
    CANONICAL_REQUIREMENTS.replace(b"2.4.6", b"2.3.0"),  # Still inside project NumPy>=2.2,<3.
    CANONICAL_REQUIREMENTS.replace(b"a" * 64, b"b" * 64),
    CANONICAL_REQUIREMENTS.replace(b" --hash", b"; python_version < '3.14' --hash"),
    CANONICAL_REQUIREMENTS + b"unreviewed-math==1 --hash=sha256:" + b"c" * 64 + b"\n",
    CANONICAL_REQUIREMENTS.replace(b"\n", b"\r\n"),
])
def test_compatible_but_different_lock_export_cannot_change_consumer_math(tmp_path, monkeypatch, changed):
    wheel, requirements = package_inputs(tmp_path)
    requirements.write_bytes(changed)
    monkeypatch.setattr(bundle, "canonical_requirements", lambda root: CANONICAL_REQUIREMENTS)
    with pytest.raises(ValueError, match="^bundle_requirements_lock_mismatch$"):
        bundle.install_payload(tmp_path, wheel, requirements)


def stub_export(root, monkeypatch, *, version=b"uv 0.12.2 (reviewed-build)\n", fail=False, mutate=False):
    calls = []
    uv = str(root / "tools/uv.exe")
    monkeypatch.setattr(bundle.shutil, "which", lambda name: uv if name == "uv" else None)
    monkeypatch.setenv("UV_PYTHON", "unreviewed-runtime")
    monkeypatch.setenv("UV_EXCLUDE_NEWER", "2000-01-01")
    monkeypatch.setenv("PIP_INDEX_URL", "https://invalid.example/not-used")

    def run(command, **options):
        calls.append((command, options))
        if command == [uv, "--version"]:
            return subprocess.CompletedProcess(command, 0, stdout=version)
        if fail:
            raise subprocess.CalledProcessError(1, command, stderr=b"private local diagnostic")
        if mutate:
            (root / "uv.lock").write_bytes(b"different lock\n")
        return subprocess.CompletedProcess(command, 0, stdout=CANONICAL_REQUIREMENTS)

    monkeypatch.setattr(bundle.subprocess, "run", run)
    return uv, calls


def test_canonical_export_uses_pinned_offline_locked_source_without_user_overrides(tmp_path, monkeypatch):
    package_inputs(tmp_path)
    uv, calls = stub_export(tmp_path, monkeypatch)
    assert bundle.canonical_requirements(tmp_path) == CANONICAL_REQUIREMENTS
    assert calls[1][0] == [uv, "export", "--locked", "--no-dev", "--no-emit-project", "--no-header",
                           "--no-config", "--offline", "--no-cache", "--no-python-downloads"]
    for _, options in calls:
        assert options["cwd"] == tmp_path and options["check"] is True and options["capture_output"] is True
        assert not any(key.upper().startswith(("UV_", "PIP_")) for key in options["env"])


@pytest.mark.parametrize("version", [b"uv 0.12.3\n", b"uv 0.12.2-extra\n"])
def test_changed_export_tool_never_produces_release_inputs(tmp_path, monkeypatch, version):
    package_inputs(tmp_path)
    _, calls = stub_export(tmp_path, monkeypatch, version=version)
    with pytest.raises(ValueError, match="^bundle_pinned_uv_required$"):
        bundle.canonical_requirements(tmp_path)
    assert len(calls) == 1


@pytest.mark.parametrize(("failure", "expected"), [
    ({"fail": True}, "bundle_locked_export_failed"),
    ({"mutate": True}, "bundle_locked_export_source_changed"),
])
def test_export_failure_or_changed_source_cannot_be_certified(tmp_path, monkeypatch, failure, expected):
    package_inputs(tmp_path)
    stub_export(tmp_path, monkeypatch, **failure)
    with pytest.raises(ValueError, match="^" + expected + "$"):
        bundle.canonical_requirements(tmp_path)
