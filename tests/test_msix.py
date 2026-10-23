"""Packaging boundaries and the Store adapter; no private images or paid APIs."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest
from cytellect_api import local, msix

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("msix_payload", ROOT / "scripts/msix_payload.py")
assert spec and spec.loader
payload = importlib.util.module_from_spec(spec)
spec.loader.exec_module(payload)


@pytest.fixture(autouse=True)
def restore_launch_environment(monkeypatch):
    for name in ("CYTELLECT_CODE_REVISION", "CYTELLECT_ENGINE_ASSETS", "CYTELLECT_CELLPOSE_ASSETS",
                 "PYTHONDONTWRITEBYTECODE"):
        monkeypatch.delenv(name, raising=False)


def source_zip(tmp_path, *, extra=None, bad_hash=False):
    data = b"approved source"
    release = {"schema": "cytellect-local-release/1", "platform": "windows-x64", "source_commit": "a" * 40,
               "files": [{"path": "README.md", "size": len(data),
                          "sha256": ("0" * 64 if bad_hash else hashlib.sha256(data).hexdigest())}]}
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("README.md", data)
        bundle.writestr("local-release.json", json.dumps(release))
        if extra:
            bundle.writestr(extra, b"unapproved")
    return archive


@pytest.mark.parametrize("extra", ["settings/cellpose-remote.json", "data/research.tif", "../escape",
                                   "README.MD", "apps/web/out/../../data/image.tif", "C:/escape"])
def test_source_rejects_extra_data_and_paths_before_extraction(tmp_path, extra):
    target = tmp_path / "extracted"
    with pytest.raises(ValueError):
        payload.extract_release(source_zip(tmp_path, extra=extra), target)
    assert not target.exists()


def test_source_rejects_tampering_before_extraction(tmp_path):
    target = tmp_path / "extracted"
    with pytest.raises(ValueError, match="hash_mismatch"):
        payload.extract_release(source_zip(tmp_path, bad_hash=True), target)
    assert not target.exists()


def test_verified_source_stage_does_not_copy_builder_settings(tmp_path):
    source, stage = tmp_path / "source", tmp_path / "stage"
    payload.extract_release(source_zip(tmp_path), source)
    (source / "settings").mkdir()
    (source / "settings/private.json").write_text("not a release input")
    payload.stage_source(source, stage)
    assert (stage / "README.md").read_bytes() == b"approved source"
    assert not (stage / "settings").exists()


def test_manifest_identity_escaping_and_retention(tmp_path):
    payload.write_manifest(ROOT / "packaging/windows/AppxManifest.xml", tmp_path,
                           "Example.Cytellect", 'CN=Example & Co', 'Example & Co', "1.2.3.0")
    tree = ET.parse(tmp_path / "AppxManifest.xml")
    ns = {"f": payload.FOUNDATION,
          "d": "http://schemas.microsoft.com/appx/manifest/desktop/windows10/6",
          "v": "http://schemas.microsoft.com/appx/manifest/virtualization/windows10",
          "r": "http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"}
    assert tree.find("f:Identity", ns).attrib["Publisher"] == 'CN=Example & Co'
    assert tree.find("f:Properties/d:FileSystemWriteVirtualization", ns).text == "disabled"
    assert tree.find(".//v:ExcludedDirectory", ns).text == r"$(KnownFolder:LocalAppData)\Cytellect"
    assert {c.attrib["Name"] for c in tree.findall("f:Capabilities/r:Capability", ns)} == {
        "runFullTrust", "unvirtualizedResources"}
    assert 'xmlns:virtualization=' in (tmp_path / "AppxManifest.xml").read_text()


@pytest.mark.parametrize("version", ["0.0.0.0", "1.0.0", "1.0.0.1", "65536.0.0.0", "01.0.0.0", "-1.0.0.0"])
def test_store_version_rejected(tmp_path, version):
    with pytest.raises(ValueError, match="version_invalid"):
        payload.write_manifest(ROOT / "packaging/windows/AppxManifest.xml", tmp_path,
                               "Cytellect.Test", "CN=Test", "Test", version)


def test_inventory_rejects_user_data(tmp_path):
    stage = tmp_path / "stage"
    (stage / "data").mkdir(parents=True)
    (stage / "data/image.tif").write_bytes(b"not a package input")
    with pytest.raises(ValueError, match="private_path"):
        payload.write_inventory(stage, tmp_path / "inventory.json")


def test_store_launch_shares_data_and_preserves_manual_retention(tmp_path, monkeypatch):
    package, user = tmp_path / "package", tmp_path / "user"
    (package / "fiji").mkdir(parents=True)
    (package / "apps/web/out").mkdir(parents=True)
    (package / "apps/web/out/index.html").write_text("workspace")
    (user / "data").mkdir(parents=True)
    marker = user / "data/.manual-workspace-retention"
    marker.touch()
    original = user / "data/existing-work.txt"
    original.write_text("preserve")
    monkeypatch.setenv("CYTELLECT_CODE_REVISION", "untrusted")
    monkeypatch.setattr(msix, "installed_source_revision", lambda root: "b" * 40)
    calls = []
    monkeypatch.setattr(msix, "run_local", lambda settings, web, **kw: calls.append((settings, web, kw)))
    msix.launch(package, user)
    settings, web, options = calls[0]
    assert settings.data_dir == user / "data"
    assert settings.workspace_retention_mode == "manual"
    assert settings.proposal_token == "" and settings.proposal_url == ""
    assert web == package / "apps/web/out"
    assert options == {"gui": True, "open_browser": True}
    assert original.read_text() == "preserve" and marker.is_file()


def test_store_refuses_unverified_source(tmp_path, monkeypatch):
    (tmp_path / "fiji").mkdir()
    (tmp_path / "apps/web/out").mkdir(parents=True)
    (tmp_path / "apps/web/out/index.html").touch()
    monkeypatch.setattr(msix, "installed_source_revision", lambda root: None)
    with pytest.raises(ValueError, match="source_identity_invalid"):
        msix.launch(tmp_path, tmp_path / "user")


@pytest.mark.parametrize("package", ["cytellect_analysis", "cytellect_api", "cytellect_worker"])
@pytest.mark.parametrize("fault", [None, "modified", "extra"])
def test_msix_revision_checks_executed_wheel_sources(tmp_path, monkeypatch, package, fault):
    entries = []
    site = tmp_path / "runtime/Lib/site-packages"
    for name, prefix in [("cytellect_analysis", "packages/analysis"), ("cytellect_api", "services/api"),
                         ("cytellect_worker", "services/worker")]:
        for filename in ["__init__.py", "local.py"]:
            relative = f"{prefix}/src/{name}/{filename}"
            source = tmp_path / relative
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b"# exact wheel source\n")
            installed = site / name / filename
            installed.parent.mkdir(parents=True, exist_ok=True)
            installed.write_bytes(source.read_bytes())
            entries.append({"path": relative, "size": source.stat().st_size,
                            "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
    (tmp_path / "local-release.json").write_text(json.dumps({"schema": "cytellect-local-release/1",
                                                          "source_commit": "c" * 40, "files": entries}))
    monkeypatch.setattr(local, "__file__", str(site / "cytellect_api/local.py"))
    if fault == "modified":
        (site / package / "local.py").write_bytes(b"# changed executed source\n")
    elif fault == "extra":
        (site / package / "unlisted.py").touch()
    assert local.installed_source_revision() == (None if fault else "c" * 40)
