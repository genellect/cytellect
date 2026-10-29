"""The per-user Windows installer: payload pins, hash binding, credentials and contracts.

Linux checks run the build script with generated files and fake downloads/compiler.
The Windows-only checks run the real preflight and offline verification in PowerShell;
the compiled installer itself is exercised by the windows-installer CI job.
"""
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from cytellect_api import app_update, local

ROOT = Path(__file__).resolve().parents[1]
ISS = ROOT / "packaging/windows/cytellect.iss"
PREFLIGHT = ROOT / "packaging/windows/preflight.ps1"
SETUP = ROOT / "scripts/local_setup.ps1"


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


builder = load("build_windows_installer")
fiji_setup = load("fiji_setup")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def release_zip(directory: Path, extra=None, corrupt=None) -> Path:
    """A setup ZIP shaped like build_local_bundle.py output, with the real pins."""
    members = {name: (ROOT / name).read_bytes() for name in (
        "scripts/local_setup.ps1", "engines/python/windows-runtime.lock.json", "engines/fiji/runtime.lock.json")}
    members["engines/python/windows-requirements.txt"] = (
        b"numpy==2.5.3 \\\n    --hash=sha256:" + b"1" * 64 + b" \\\n    --hash=sha256:" + b"2" * 64 + b"\n"
        b"    # via cytellect\n"
        b"colorama==0.4.6 ; sys_platform == 'linux' \\\n    --hash=sha256:" + b"3" * 64 + b"\n"
        b"./wheels/cytellect-0.1.0-py3-none-any.whl --hash=sha256:" + b"4" * 64 + b"\n")
    files = [{"path": name, "sha256": digest(data), "size": len(data)} for name, data in sorted(members.items())]
    manifest = {"schema": "cytellect-local-release/1", "version": "0.1.0-local.21", "source_commit": "a" * 40,
                "platform": "windows-x64", "files": files}
    archive = directory / "Cytellect-0.1.0-local.21-windows-x64.zip"
    directory.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w") as bundle:
        for name, data in members.items():
            bundle.writestr(name, corrupt.get(name, data) if corrupt else data)
        bundle.writestr("local-release.json", json.dumps(manifest))
        for name, data in (extra or {}).items():
            bundle.writestr(name, data)
    archive.with_name(archive.name + ".sha256").write_text(f"{digest(archive.read_bytes())}  {archive.name}\n")
    return archive


def test_release_zip_must_match_its_checksum_and_manifest(tmp_path):
    assert builder.verify_release_zip(release_zip(tmp_path / "ok"))["version"] == "0.1.0-local.21"
    for name, archive in {
        "extra": release_zip(tmp_path / "extra", extra={"private.tif": b"x"}),
        "corrupt": release_zip(tmp_path / "corrupt", corrupt={"engines/fiji/runtime.lock.json": b"{}"}),
    }.items():
        with pytest.raises(builder.BuildError):
            builder.verify_release_zip(archive)
    archive = release_zip(tmp_path / "checksum")
    archive.with_name(archive.name + ".sha256").write_text("0" * 64 + "  " + archive.name + "\n")
    with pytest.raises(builder.BuildError, match="checksum"):
        builder.verify_release_zip(archive)
    assert not builder.safe_member("../outside") and not builder.safe_member("C:/x") and builder.safe_member("a/b")


def test_bundled_artifacts_are_exactly_the_pins_that_setup_downloads():
    artifacts = builder.pinned_artifacts(ROOT)
    setup = SETUP.read_text(encoding="utf-8-sig")
    roles = [artifact.role for artifact in artifacts]
    assert roles[:3] == ["uv", "python", "fiji"] and set(roles[3:]) == {"fiji_plugin"}
    assert re.search(r"\$script:UvSha256 = '" + artifacts[0].sha256, setup)
    runtime = json.loads((ROOT / "engines/python/windows-runtime.lock.json").read_text())
    fiji = json.loads((ROOT / "engines/fiji/runtime.lock.json").read_text())
    assert artifacts[1].sha256 == runtime["python"]["sha256"] and artifacts[1].size == runtime["python"]["bytes"]
    assert artifacts[2].sha256 == fiji["fiji"]["windows-x64"]["sha256"]
    assert [a.sha256 for a in artifacts[3:]] == [plugin["sha256"] for plugin in fiji["plugins"]]


def test_locked_requirements_apply_target_markers_and_require_hashes():
    text = (ROOT / "engines/python/windows-runtime.lock.json").read_text()  # not a requirements file
    with pytest.raises(builder.BuildError):
        builder.locked_requirements(text)
    locked = builder.locked_requirements(
        "numpy==2.5.3 --hash=sha256:" + "1" * 64 + "\n"
        "colorama==0.4.6 ; sys_platform == 'win32' --hash=sha256:" + "2" * 64 + "\n"
        "uvloop==0.21.0 ; sys_platform != 'win32' --hash=sha256:" + "3" * 64 + "\n"
        "./wheels/cytellect-0.1.0-py3-none-any.whl --hash=sha256:" + "4" * 64 + "\n")
    assert set(locked) == {"numpy", "colorama"}
    assert builder.third_party_requirements("numpy==2.5.3 --hash=sha256:" + "1" * 64 + "\n") == (
        "numpy==2.5.3 --hash=sha256:" + "1" * 64 + "\n")
    for unlocked in ("numpy==2.5.3\n", "numpy>=2 --hash=sha256:" + "1" * 64 + "\n"):
        with pytest.raises(builder.BuildError, match="hash_locked"):
            builder.locked_requirements(unlocked)


def wheelhouse(directory: Path, wheels: dict[str, bytes]) -> str:
    directory.mkdir()
    lines = []
    for name, data in wheels.items():
        (directory / name).write_bytes(data)
        project = name.split("-")[0]
        lines.append(f"{project}==1.0 --hash=sha256:{digest(data)}")
    return "\n".join(lines) + "\n"


def test_wheelhouse_has_one_locked_windows_wheel_per_requirement(tmp_path):
    requirements = wheelhouse(tmp_path / "ok", {"numpy-1.0-cp314-cp314-win_amd64.whl": b"n",
                                                "six-1.0-py2.py3-none-any.whl": b"s"})
    entries = builder.verify_wheelhouse(requirements, tmp_path / "ok")
    assert [entry["path"] for entry in entries] == ["wheels/numpy-1.0-cp314-cp314-win_amd64.whl",
                                                     "wheels/six-1.0-py2.py3-none-any.whl"]
    linux = wheelhouse(tmp_path / "linux", {"numpy-1.0-cp314-cp314-manylinux_2_28_x86_64.whl": b"n"})
    with pytest.raises(builder.BuildError, match="platform"):
        builder.verify_wheelhouse(linux, tmp_path / "linux")
    tampered = wheelhouse(tmp_path / "tampered", {"six-1.0-py3-none-any.whl": b"s"})
    (tmp_path / "tampered/six-1.0-py3-none-any.whl").write_bytes(b"changed")
    with pytest.raises(builder.BuildError, match="hash_not_locked"):
        builder.verify_wheelhouse(tampered, tmp_path / "tampered")
    missing = wheelhouse(tmp_path / "missing", {"six-1.0-py3-none-any.whl": b"s"}) + (
        "numpy==1.0 --hash=sha256:" + "9" * 64 + "\n")
    with pytest.raises(builder.BuildError, match="incomplete"):
        builder.verify_wheelhouse(missing, tmp_path / "missing")
    (tmp_path / "ok/notes.txt").write_text("unexpected")
    with pytest.raises(builder.BuildError, match="unexpected_file"):
        builder.verify_wheelhouse(requirements, tmp_path / "ok")


def fake_token(prefix: str, length: int = 24) -> str:
    # Built at run time so the repository itself never contains a token-shaped literal.
    return prefix + ("a1B2" * 10)[:length]


def test_credentials_are_detected_by_rule_without_reporting_content(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({"key": fake_token("sk-" + "proj-")}))
    (tmp_path / "gpu.ps1").write_text(fake_token("wk" + "-") + "." + fake_token("ws" + "-"))
    (tmp_path / ".env").write_text("anything")
    (tmp_path / "cellpose-remote.json").write_text("{}")
    (tmp_path / "prose.md").write_text("Use the token pair wk-…….ws-…… from the administrator.")
    (tmp_path / "relay.toml").write_text("\n".join([
        "AKIA" + "1B2C3D4E5F6G7H8J", "re_" + "a1B2c3D4" + "_" + "e5F6g7H8j9K0l1M2n3",
        "CLOUDFLARE_API_TOKEN = " + ("a1B2" * 10), "v1.0-" + "0a" * 12 + "-" + "1b" * 60]))
    findings = builder.scan_for_secrets([tmp_path])
    assert findings == {"openai_key": 1, "modal_token": 2, "forbidden_file": 2, "aws_access_key": 1,
                        "resend_key": 1, "cloudflare_token": 1, "cloudflare_origin_ca_key": 1}
    assert all(isinstance(value, int) for value in findings.values())


def test_shipped_sources_contain_no_credentials():
    # The release ZIP carries these trees; the build also scans the actual payload.
    assert builder.scan_for_secrets([ROOT / "services", ROOT / "packages/analysis/src", ROOT / "scripts",
                                     ROOT / "engines", ROOT / "packaging"]) == {}


def test_offline_manifest_binds_the_release_and_rejects_duplicates(tmp_path):
    offline = tmp_path / "offline"
    (offline / "sha256").mkdir(parents=True)
    data = b"bundled artifact"
    (offline / "sha256" / digest(data)).write_bytes(data)
    artifact = builder.Artifact("python", "https://www.python.org/x.zip", digest(data))
    manifest = builder.write_offline_manifest(offline, b"release manifest", "0.1.0-local.21", "a" * 40, [artifact],
                                              [{"path": "wheels/six-1.0-py3-none-any.whl", "sha256": "f" * 64,
                                                "bytes": 1}])
    assert manifest["release_manifest_sha256"] == digest(b"release manifest")
    assert [entry["path"] for entry in manifest["files"]] == ["sha256/" + digest(data),
                                                             "wheels/six-1.0-py3-none-any.whl"]
    assert json.loads((offline / "offline-manifest.json").read_text()) == manifest
    with pytest.raises(builder.BuildError, match="duplicate"):
        builder.write_offline_manifest(offline, b"m", "0.1.0-local.21", "a" * 40, [artifact, artifact], [])
    (offline / "sha256" / digest(data)).write_bytes(b"changed")
    with pytest.raises(builder.BuildError, match="hash_mismatch"):
        builder.write_offline_manifest(offline, b"m", "0.1.0-local.21", "a" * 40, [artifact], [])


def test_compiler_command_versions_and_signing_hook(tmp_path):
    command = builder.iscc_command(Path("ISCC.exe"), tmp_path / "payload", tmp_path / "out", "0.1.0-local.21", 1200,
                                   None)
    assert command[-1] == str(ISS) and "/DNumericVersion=0.1.0.21" in command and "/DPayloadMB=1200" in command
    assert not any(part.startswith("/S") for part in command)
    signed = builder.iscc_command(Path("ISCC.exe"), tmp_path, tmp_path, "0.1.0-local.21", 1, "signtool sign $f")
    assert "/DSignToolName=cytellect" in signed and "/Scytellect=signtool sign $f" in signed
    with pytest.raises(builder.BuildError, match="placeholder"):
        builder.iscc_command(Path("ISCC.exe"), tmp_path, tmp_path, "0.1.0-local.21", 1, "signtool sign")
    assert builder.numeric_version("0.0.0-local.ci") == "0.0.0.0"
    assert re.fullmatch(r"[0-9a-f]{64}", builder.INNO_SHA256) and builder.INNO_URL.startswith("https://github.com/")


def generated_wheel(name="numpy", version="2.5.3", license_text=b"Generated license text\n") -> bytes:
    """A minimal wheel with metadata and a license file; no real package code."""
    import io

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as wheel:
        info = f"{name}-{version}.dist-info"
        wheel.writestr(f"{info}/METADATA", f"Metadata-Version: 2.4\nName: {name}\nVersion: {version}\n"
                                           "License-Expression: BSD-3-Clause\n")
        wheel.writestr(f"{info}/licenses/LICENSE.txt", license_text)
        wheel.writestr(f"{name}/__init__.py", "")
    return buffer.getvalue()


def test_bundled_wheels_contribute_their_license_texts(tmp_path):
    wheel = tmp_path / "numpy-2.5.3-cp314-cp314-win_amd64.whl"
    wheel.write_bytes(generated_wheel())
    notice = builder.wheel_notice(wheel, tmp_path / "licenses/wheels")
    assert notice["license"] == "BSD-3-Clause" and notice["source"] == "https://pypi.org/project/numpy/2.5.3/"
    assert notice["files"] == ["wheels/numpy-2.5.3/licenses__LICENSE.txt"]
    assert (tmp_path / "licenses" / notice["files"][0]).read_bytes() == b"Generated license text\n"


def test_build_assembles_a_verified_offline_payload_and_receipt(tmp_path, monkeypatch):
    archive = release_zip(tmp_path / "release")
    wheel_bytes = generated_wheel()
    blobs = {role: b"generated artifact " + role.encode() for role in ("uv", "python", "fiji")}
    urls = {"uv": "https://github.com/astral-sh/uv/releases/download/0.12.2/uv-x86_64-pc-windows-msvc.zip",
            "python": "https://www.python.org/ftp/python/3.14.8/python-3.14.8-amd64.zip",
            "fiji": "https://downloads.imagej.net/fiji/archive/generated.zip"}
    artifacts = [builder.Artifact(role, urls[role], digest(data)) for role, data in blobs.items()]

    def fetch(artifact, cache):
        cache.mkdir(parents=True, exist_ok=True)
        path = cache / artifact.sha256
        path.write_bytes(blobs[artifact.role])
        return path

    def wheels(requirements, directory, scratch, pip_python):
        directory.mkdir()
        (directory / "numpy-2.5.3-cp314-cp314-win_amd64.whl").write_bytes(wheel_bytes)

    def compile_installer(command, check, timeout):
        output = Path(next(part for part in command if part.startswith("/DOutputDir="))[len("/DOutputDir="):])
        (output / "Cytellect-Setup-0.1.0-local.21.exe").write_bytes(b"installer")

    monkeypatch.setattr(builder, "pinned_artifacts", lambda release: artifacts)
    monkeypatch.setattr(builder, "fetch_artifact", fetch)
    monkeypatch.setattr(builder, "download_wheels", wheels)
    monkeypatch.setattr(builder, "locked_requirements",
                        lambda text: {"numpy": ("numpy==2.5.3", {digest(wheel_bytes)})})
    monkeypatch.setattr(builder.subprocess, "run", compile_installer)
    receipt = builder.build(archive, tmp_path / "out", tmp_path / "work", tmp_path / "cache", Path("ISCC.exe"), None)
    assert receipt["signed"] is False and receipt["version"] == "0.1.0-local.21"
    assert receipt["bundled"]["wheels"] == 1
    installer = tmp_path / "out/Cytellect-Setup-0.1.0-local.21.exe"
    assert (tmp_path / "out/Cytellect-Setup-0.1.0-local.21.exe.sha256").read_text() == (
        f"{digest(b'installer')}  {installer.name}\n")
    payload = tmp_path / "work/payload"
    assert (payload / "release/local-release.json").is_file()
    offline = json.loads((payload / "offline/offline-manifest.json").read_text())
    assert offline["release_manifest_sha256"] == digest((payload / "release/local-release.json").read_bytes())
    # Bundled licenses and corresponding-source addresses ship in the installer and the receipt.
    notices = payload / "licenses/THIRD_PARTY_BUNDLED.txt"
    text = notices.read_text(encoding="utf-8")
    assert "GPL-3.0" in text and "https://github.com/fiji/fiji" in text and "uv 0.12.2" in text
    assert receipt["third_party_notices"]["sha256"] == digest(notices.read_bytes())
    sources = {item["component"]: item["source"] for item in receipt["third_party"]}
    assert sources["numpy"] == "https://pypi.org/project/numpy/2.5.3/"
    assert sources["plugins/MorphoLibJ_-1.6.5.jar"] == "https://github.com/ijpb/MorphoLibJ"
    with pytest.raises(builder.BuildError, match="installer_exists"):
        builder.build(archive, tmp_path / "out", tmp_path / "work2", tmp_path / "cache", Path("ISCC.exe"), None)


def test_fiji_offline_copy_uses_only_the_exact_bundled_bytes(tmp_path):
    data = b"bundled fiji artifact"
    (tmp_path / "offline").mkdir()
    (tmp_path / "offline" / digest(data)).write_bytes(data)
    fiji_setup.download("https://unused.invalid/x", tmp_path / "a", digest(data), tmp_path / "offline")
    assert (tmp_path / "a").read_bytes() == data
    with pytest.raises(RuntimeError, match="offline_artifact_missing"):
        fiji_setup.download("https://unused.invalid/x", tmp_path / "b", "0" * 64, tmp_path / "offline")
    (tmp_path / "offline" / ("1" * 64)).write_bytes(b"not matching")
    with pytest.raises(RuntimeError, match="offline_artifact_hash_mismatch"):
        fiji_setup.download("https://unused.invalid/x", tmp_path / "c", "1" * 64, tmp_path / "offline")
    assert not (tmp_path / "c").exists()


def iss_text() -> str:
    raw = ISS.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "Inno Setup reads Japanese text only from UTF-8 with BOM"
    return raw.decode("utf-8-sig")


def test_installer_is_per_user_without_choices_or_administrator_rights():
    text = iss_text()
    for directive in ("PrivilegesRequired=lowest", r"DefaultDirName={localappdata}\Cytellect", "DisableDirPage=yes",
                      "UsePreviousAppDir=no", "DisableProgramGroupPage=yes", "ArchitecturesAllowed=x64os",
                      r"UninstallFilesDir={app}\uninstall", "OutputBaseFilename=Cytellect-Setup-{#AppVersion}"):
        assert re.search(r"^" + re.escape(directive) + r"$", text, re.M), directive
    assert "PrivilegesRequiredOverridesAllowed" not in text and "admin" not in text.lower().replace("administrator", "")
    app_id = re.search(r"^AppId=\{(\{[0-9A-F-]{36}\})$", text, re.M)
    assert app_id and f"Uninstall\\{app_id.group(1)}_is1" in text
    # The [Code] constants must name the same objects as the launcher and setup.
    assert f"LauncherMutex = '{local.LAUNCHER_MUTEX}'" in text
    assert f"ShortcutDescription = '{app_update.SHORTCUT_DESCRIPTION}'" in text
    assert app_update.SHORTCUT_DESCRIPTION in SETUP.read_text(encoding="utf-8-sig")
    assert "#ifdef SignToolName" in text  # signing hook (D4), skipped without a certificate
    # The bundled software's licenses and source addresses are installed with it (docs/oss.md).
    assert 'Source: "{#PayloadDir}\\licenses\\*"; DestDir: "{app}\\licenses"' in text
    # A self-help step comes before asking an administrator.
    for line in text.splitlines():
        if "管理者にご相談" in line or "管理者に配布物の確認" in line:
            before = line.split("管理者")[0]
            assert any(step in before for step in ("もう一度", "ダウンロードし直", "再起動", "移して")), line


def test_every_setup_phase_and_preflight_code_has_a_japanese_message():
    text = iss_text()
    phases = set(re.findall(r"Update-SetupStatus '([a-z_]+)'", SETUP.read_text(encoding="utf-8-sig")))
    phases |= set(re.findall(r"Update-SetupStatus '([a-z_]+)'", (ROOT / "scripts/windows_runtime.ps1").read_text(
        encoding="utf-8-sig")))
    assert phases and all(re.search(rf"^Phase_{phase}=\S", text, re.M) for phase in phases), phases
    preflight = PREFLIGHT.read_text(encoding="utf-8")
    codes = set(re.findall(r"\$result\.code = '([a-z_]+)'", preflight)) - {"ok"}
    assert codes == {"os_unsupported", "architecture_unsupported", "memory_insufficient", "disk_insufficient",
                     "temp_insufficient"}
    assert all(f"Code = '{code}'" in text for code in codes)
    # A refused preflight changes nothing and says how to continue.
    assert "何も変更" in text and "空きを作ってから" in text


powershell = pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell installer contract")
SHELL = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
DECISION = r'''
$ErrorActionPreference='Stop'
$tokens=$null; $errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($env:CYTELLECT_TEST_PREFLIGHT,[ref]$tokens,[ref]$errors)
if ($errors.Count) { throw 'parse_failed' }
$function=$ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Get-CytellectPreflight'},$true)
Invoke-Expression $function.Extent.Text
$script:MinimumBuild = 17763
$script:MinimumMemoryMB = 7168
$cases = Get-Content -LiteralPath $env:CYTELLECT_TEST_CASES -Raw | ConvertFrom-Json
$out = foreach ($c in $cases) {
    (Get-CytellectPreflight ([Version]$c.os) $c.arch $c.x64 $c.memory $c.free $c.temp $c.same $c.update 4096 1536 1200).code
}
$out -join ','
'''


@powershell
def test_preflight_decisions_in_windows_powershell(tmp_path):
    base = {"os": "10.0.22631", "arch": "AMD64", "x64": True, "memory": 16000, "free": 20000, "temp": 20000,
            "same": True, "update": False}
    cases = [
        base,
        {**base, "os": "6.3.9600"},                  # Windows 8.1
        {**base, "os": "10.0.17134"},                # Windows 10 1803
        {**base, "arch": "ARM64"},
        {**base, "x64": False},
        {**base, "memory": 4000},
        {**base, "memory": 7400},                    # an 8 GB PC after hardware reservations
        {**base, "free": 5000},                      # 4096 + 1200 needed on one drive
        {**base, "free": 3000, "update": True},      # an update reuses Fiji and Python: 1536 + 1200
        {**base, "same": False, "free": 4500, "temp": 500},
        {**base, "memory": -1, "free": -1},          # unmeasurable values never block
    ]
    (tmp_path / "cases.json").write_text(json.dumps(cases))
    script = tmp_path / "decide.ps1"
    script.write_text(DECISION, encoding="utf-8-sig")
    result = subprocess.run([str(SHELL), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                            env={**os.environ, "CYTELLECT_TEST_PREFLIGHT": str(PREFLIGHT),
                                 "CYTELLECT_TEST_CASES": str(tmp_path / "cases.json")},
                            capture_output=True, text=True, check=False, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip().split(",") == [
        "ok", "os_unsupported", "os_unsupported", "architecture_unsupported", "architecture_unsupported",
        "memory_insufficient", "ok", "disk_insufficient", "ok", "temp_insufficient", "ok"]


@powershell
def test_preflight_measures_this_pc_without_changes(tmp_path):
    target = tmp_path / "not created"
    output = tmp_path / "result.txt"
    result = subprocess.run([str(SHELL), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(PREFLIGHT),
                             "-InstallRoot", str(target), "-TempRoot", str(tmp_path), "-PayloadMB", "1",
                             "-RequiredInstallMB", "1", "-ResultFile", str(output)],
                            capture_output=True, text=True, check=False, timeout=60)
    values = dict(line.split("=", 1) for line in output.read_text(encoding="ascii").splitlines())
    assert result.returncode == 0 and values["code"] == "ok", values
    assert int(values["memory_mb"]) > 0 and not target.exists()
    huge = subprocess.run([str(SHELL), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(PREFLIGHT),
                           "-InstallRoot", str(target), "-TempRoot", str(tmp_path), "-PayloadMB", "1",
                           "-RequiredInstallMB", str(10**9), "-ResultFile", str(output)],
                          capture_output=True, text=True, check=False, timeout=60)
    values = dict(line.split("=", 1) for line in output.read_text(encoding="ascii").splitlines())
    assert huge.returncode == 10 and values["code"] == "disk_insufficient" and not target.exists()


def offline_fixture(source: Path, offline: Path) -> dict:
    data = b"bundled public artifact\n"
    wheel = b"bundled wheel\n"
    (offline / "sha256").mkdir(parents=True)
    (offline / "wheels").mkdir()
    (offline / "sha256" / digest(data)).write_bytes(data)
    (offline / "wheels/six-1.0-py3-none-any.whl").write_bytes(wheel)
    manifest = {"schema": "cytellect-windows-offline/1",
                "release_manifest_sha256": digest((source / "local-release.json").read_bytes()),
                "files": [{"path": "sha256/" + digest(data), "sha256": digest(data), "bytes": len(data)},
                          {"path": "wheels/six-1.0-py3-none-any.whl", "sha256": digest(wheel), "bytes": len(wheel)}]}
    (offline / "offline-manifest.json").write_text(json.dumps(manifest))
    return manifest


@powershell
@pytest.mark.parametrize("fault", ["none", "modified", "unlisted", "other_release", "listed_name_mismatch"])
def test_offline_payload_is_verified_before_any_installation(tmp_path, fault):
    from test_windows_setup import release_fixture

    source = tmp_path / "source"
    release = release_fixture(source)
    (source / "local-release.json").write_text(json.dumps(release))
    offline = tmp_path / "offline"
    manifest = offline_fixture(source, offline)
    if fault == "modified":
        (offline / "wheels/six-1.0-py3-none-any.whl").write_bytes(b"changed wheel\n")
    elif fault == "unlisted":
        (offline / "wheels/extra-1.0-py3-none-any.whl").write_bytes(b"unlisted\n")
    elif fault == "other_release":
        manifest["release_manifest_sha256"] = "0" * 64
    elif fault == "listed_name_mismatch":
        manifest["files"][0]["path"] = "sha256/" + "0" * 64
    (offline / "offline-manifest.json").write_text(json.dumps(manifest))
    result_file = tmp_path / "result.txt"
    result = subprocess.run(
        [str(SHELL), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SETUP), "-SourceRoot", str(source),
         "-InstallRoot", str(tmp_path / "installation"), "-OfflineRoot", str(offline), "-Console", "-VerifyOnly",
         "-NoShortcut", "-ResultFile", str(result_file)],
        capture_output=True, text=True, check=False, timeout=60)
    assert not (tmp_path / "installation").exists()
    outcome = result_file.read_text(encoding="ascii")
    if fault == "none":
        assert result.returncode == 0 and outcome == "ok", result.stdout + result.stderr
    else:
        assert result.returncode == 1 and outcome.startswith("failed verify_release "), outcome
        assert str(tmp_path) not in result.stdout + result.stderr + outcome
