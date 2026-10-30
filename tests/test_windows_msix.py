"""The Microsoft Store (MSIX) edition: package builder, packaged entry point, engine natives."""
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import pytest
from cytellect_analysis import engine
from cytellect_api import packaged

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_windows_msix as msix  # noqa: E402
from build_windows_installer import BuildError  # noqa: E402

FOUNDATION = "{http://schemas.microsoft.com/appx/manifest/foundation/windows10}"


@pytest.mark.parametrize(("version", "expected"), [
    ("0.1.0-local.21", "0.1.21.0"), ("0.0.0-local.1", "0.0.1.0"), ("1.2.3", "1.2.3000.0"),
    ("0.1.1-local.3", "0.1.1003.0")])
def test_store_version_keeps_order_and_a_zero_revision(version, expected):
    assert msix.msix_version(version) == expected


@pytest.mark.parametrize("version", ["0.1.0-beta", "0.1.66-local.1", "0.1.0-local.1000", "1.2"])
def test_store_version_rejects_what_it_cannot_order(version):
    with pytest.raises(BuildError):
        msix.msix_version(version)


CI_IDENTITY = ROOT / "packaging/windows/msix/ci-test-identity.json"


def manifest(identity=None, version="0.1.0-local.21"):
    identity = identity or msix.load_identity(CI_IDENTITY)
    return ElementTree.fromstring(msix.render_manifest(msix.TEMPLATE.read_text(encoding="utf-8"), identity, version))


def test_manifest_runs_packaged_python_with_full_trust_and_shares_the_data_folder():
    root = manifest()
    identity = root.find(FOUNDATION + "Identity")
    assert identity.get("Version") == "0.1.21.0" and identity.get("ProcessorArchitecture") == "x64"
    assert identity.get("Publisher") == "CN=Cytellect CI Test Package"
    application = root.find(f"{FOUNDATION}Applications/{FOUNDATION}Application")
    assert application.get("Executable") == "python\\pythonw.exe"
    assert application.get("EntryPoint") == "Windows.FullTrustApplication"
    assert application.get("{http://schemas.microsoft.com/appx/manifest/uap/windows10/10}Parameters") == \
        "-B -E -m cytellect_api.packaged"
    virtualization = root.find(f"{FOUNDATION}Properties/"
                               "{http://schemas.microsoft.com/appx/manifest/desktop/windows10/6}"
                               "FileSystemWriteVirtualization")
    assert virtualization.text == "disabled"
    restricted = {element.get("Name") for element in root.iter(
        "{http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities}Capability")}
    assert restricted == {"runFullTrust", "unvirtualizedResources"}
    minimum = root.find(f"{FOUNDATION}Dependencies/{FOUNDATION}TargetDeviceFamily").get("MinVersion")
    assert minimum == "10.0.19041.0"


def test_manifest_escapes_partner_center_values_and_rejects_invalid_identity():
    identity = {"schema": "cytellect-msix-identity/1", "identity_name": "12345Lab.Cytellect",
                "publisher": 'CN=ABCD, O="Lab & Co"', "publisher_display_name": "Lab & Co", "partner_center": True}
    root = manifest(identity)
    assert root.find(FOUNDATION + "Identity").get("Publisher") == 'CN=ABCD, O="Lab & Co"'
    assert root.find(f"{FOUNDATION}Properties/{FOUNDATION}PublisherDisplayName").text == "Lab & Co"
    with pytest.raises(BuildError):
        msix.render_manifest("<a>{{UNKNOWN}}</a>", identity, "0.1.0-local.1")


def test_identity_placeholders_are_marked_as_not_from_partner_center(tmp_path):
    # The Store identity waits for the owner's Partner Center values; CI signs only its own test identity.
    assert msix.load_identity(msix.IDENTITY)["partner_center"] is False
    assert msix.load_identity(CI_IDENTITY)["partner_center"] is False
    assert msix.load_identity(CI_IDENTITY)["identity_name"] != msix.load_identity(msix.IDENTITY)["identity_name"]
    bad = tmp_path / "identity.json"
    bad.write_text(json.dumps({"schema": "cytellect-msix-identity/1", "identity_name": "x", "publisher": "O=x",
                               "publisher_display_name": "x"}))
    with pytest.raises(BuildError):
        msix.load_identity(bad)


def pe_bytes() -> bytes:
    header = bytearray(128)
    header[:2] = b"MZ"
    header[60:64] = (64).to_bytes(4, "little")
    header[64:68] = b"PE\0\0"
    return bytes(header)


def test_pe_detection_reads_content_not_names(tmp_path):
    (tmp_path / "python").mkdir()
    (tmp_path / "python/renamed.bin").write_bytes(pe_bytes())
    (tmp_path / "python/fake.dll").write_bytes(b"MZ but not an image")
    (tmp_path / "AppxManifest.xml").write_text("<x/>")
    assert msix.is_pe(tmp_path / "python/renamed.bin") and not msix.is_pe(tmp_path / "python/fake.dll")
    assert msix.pe_inventory(tmp_path) == {"python": 1}


def fiji_with_tensorflow(tmp_path: Path) -> tuple[Path, Path]:
    release, fiji = tmp_path / "release", tmp_path / "fiji"
    (fiji / "jars").mkdir(parents=True)
    jar = fiji / "jars/libtensorflow_jni-1.15.0.jar"
    with zipfile.ZipFile(jar, "w") as archive:
        archive.writestr("org/tensorflow/native/windows-x86_64/tensorflow_jni.dll", pe_bytes())
        archive.writestr("org/tensorflow/native/windows-x86_64/LICENSE", "license")
        archive.writestr("org/tensorflow/native/linux-x86_64/libtensorflow_jni.so", b"\x7fELF")
    lock = {"plugins": [{"path": "jars/libtensorflow_jni-1.15.0.jar",
                         "sha256": hashlib.sha256(jar.read_bytes()).hexdigest()}]}
    (release / "engines/fiji").mkdir(parents=True)
    (release / "engines/fiji/runtime.lock.json").write_text(json.dumps(lock))
    return release, fiji


def test_tensorflow_jni_is_pre_extracted_with_its_origin_and_found_by_the_engine(tmp_path):
    release, fiji = fiji_with_tensorflow(tmp_path)
    record = msix.extract_natives(fiji, release)
    assert [entry["name"] for entry in record["files"]] == ["tensorflow_jni.dll"]
    assert record["files"][0]["member"] == "org/tensorflow/native/windows-x86_64/tensorflow_jni.dll"
    assert (fiji / "natives/tensorflow_jni.dll").read_bytes() == pe_bytes()
    assert sorted(path.name for path in (fiji / "natives").iterdir()) == ["natives.json", "tensorflow_jni.dll"]
    assert engine._native_library_flags(fiji) == ["-Djava.library.path=" + str(fiji / "natives")]


def test_extraction_refuses_a_jar_that_does_not_match_the_lock(tmp_path):
    release, fiji = fiji_with_tensorflow(tmp_path)
    with zipfile.ZipFile(fiji / "jars/libtensorflow_jni-1.15.0.jar", "a") as archive:
        archive.writestr("extra", "changed")
    with pytest.raises(BuildError, match="tensorflow_jni_hash_mismatch"):
        msix.extract_natives(fiji, release)


def test_engine_adds_no_library_path_without_natives_and_refuses_a_broken_list(tmp_path):
    assert engine._native_library_flags(tmp_path) == []
    (tmp_path / "natives").mkdir()
    (tmp_path / "natives/natives.json").write_text(json.dumps(
        {"schema": "cytellect-fiji-natives/1", "files": [{"name": "../escape.dll"}]}))
    with pytest.raises(engine.EngineUnavailable, match="fiji_natives_invalid"):
        engine._native_library_flags(tmp_path)
    (tmp_path / "natives/natives.json").write_text(json.dumps(
        {"schema": "cytellect-fiji-natives/1", "files": [{"name": "missing.dll"}]}))
    with pytest.raises(engine.EngineUnavailable, match="fiji_natives_invalid"):
        engine._native_library_flags(tmp_path)


def test_store_assets_have_the_declared_sizes(tmp_path):
    from PIL import Image

    names = msix.write_assets(tmp_path / "Assets")
    assert set(names) == set(msix.ASSETS)
    for name, size in msix.ASSETS.items():
        with Image.open(tmp_path / "Assets" / name) as image:
            assert image.size == size and image.mode == "RGBA"


def package_layout(tmp_path: Path) -> Path:
    root = tmp_path / "package"
    (root / "python").mkdir(parents=True)
    (root / "fiji").mkdir()
    (root / "apps/web/out").mkdir(parents=True)
    (root / "apps/web/out/index.html").write_text("<html></html>")
    (root / packaged.PACKAGE_MARKER).write_text(json.dumps(
        {"schema": packaged.PACKAGE_SCHEMA, "edition": "msix", "fiji": "fiji", "web": "apps/web/out"}))
    return root


def test_packaged_entry_point_finds_its_package_from_the_interpreter(tmp_path):
    root = package_layout(tmp_path)
    assert packaged.package_root(root / "python") == root
    package = packaged.read_package(root)
    assert package["fiji_path"] == root / "fiji" and package["web_path"] == root / "apps/web/out"
    marker = json.loads((root / packaged.PACKAGE_MARKER).read_text())
    for value in ("../fiji", "C:/fiji", "fiji\\x"):
        (root / packaged.PACKAGE_MARKER).write_text(json.dumps({**marker, "fiji": value}))
        with pytest.raises(packaged.PackageError):
            packaged.read_package(root)


def test_fresh_data_folder_is_owned_and_keeps_workspaces_like_the_installer_default(tmp_path):
    root = tmp_path / "Cytellect"
    data = packaged.prepare_root(root)
    assert data == root / "data" and data.is_dir()
    assert (root / "setup-root.json").read_text() == packaged.ROOT_MARKER
    assert json.loads((root / "settings/retention.json").read_text()) == packaged.RETENTION
    from cytellect_api.local import local_retention_mode
    assert local_retention_mode(data) == "manual"


def test_existing_installation_keeps_its_retention_choice_and_files(tmp_path):
    root = tmp_path / "Cytellect"
    (root / "data").mkdir(parents=True)
    (root / "setup-root.json").write_text('{"product":"cytellect-local","schema":1}')
    (root / "data/cytellect.sqlite").write_bytes(b"kept")
    packaged.prepare_root(root)
    assert not (root / "settings/retention.json").exists()  # the installer user chose 24-hour deletion
    assert (root / "data/cytellect.sqlite").read_bytes() == b"kept"


@pytest.mark.parametrize("marker", [None, '{"product":"other"}', "not json"])
def test_a_folder_that_cytellect_does_not_own_is_left_unchanged(tmp_path, marker):
    root = tmp_path / "Cytellect"
    root.mkdir()
    (root / "notes.txt").write_text("someone else's")
    if marker is not None:
        (root / "setup-root.json").write_text(marker)
    with pytest.raises(packaged.PackageError, match="install_directory_not_owned"):
        packaged.prepare_root(root)
    assert sorted(path.name for path in root.iterdir()) == sorted(
        ["notes.txt"] + (["setup-root.json"] if marker is not None else []))


def test_data_root_is_the_installer_folder_under_local_app_data(tmp_path):
    assert packaged.data_root({"LOCALAPPDATA": str(tmp_path)}) == tmp_path / "Cytellect"


def test_entry_point_starts_the_local_launcher_with_package_paths(tmp_path, monkeypatch):
    from cytellect_api import local

    root = package_layout(tmp_path)
    started = []
    monkeypatch.setattr(sys, "prefix", str(root / "python"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(local, "main", lambda argv: started.append(argv))
    packaged.main(["--no-browser"])
    data = tmp_path / "local/Cytellect/data"
    assert started == [["--data-dir", str(data), "--web-dir", str(root / "apps/web/out"), "--fiji", str(root / "fiji"),
                        "--gui", "--no-browser"]]


def test_entry_point_reports_an_unowned_folder_without_starting(tmp_path, monkeypatch):
    from cytellect_api import local

    root = package_layout(tmp_path)
    (tmp_path / "local/Cytellect").mkdir(parents=True)
    (tmp_path / "local/Cytellect/other.txt").write_text("x")
    reported = []
    monkeypatch.setattr(sys, "prefix", str(root / "python"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(local, "main", lambda argv: pytest.fail("must not start"))
    monkeypatch.setattr(local, "_report_startup_error", lambda message, gui, **_: reported.append(message))
    with pytest.raises(SystemExit):
        packaged.main([])
    assert reported == [packaged.NOT_OWNED]


def test_only_python_orgs_own_pip_may_be_in_site_packages_before_the_install(tmp_path):
    site = tmp_path / "Lib/site-packages"
    (site / "pip").mkdir(parents=True)
    (site / "pip-26.2.1.dist-info").mkdir()
    (site / "README.txt").write_text("python.org")
    assert msix.runtime_pip(tmp_path) == "pip-26.2.1"
    (site / "numpy").mkdir()
    with pytest.raises(BuildError, match="staged_python_not_clean"):
        msix.runtime_pip(tmp_path)
