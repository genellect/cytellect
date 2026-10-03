"""Exercise the real PowerShell release-verification boundary without installation."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell installer contract")
ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ASSETS = (
    "scripts/windows_runtime.ps1", "engines/python/windows-runtime.lock.json",
    "engines/python/windows-install.json", "engines/python/windows-requirements.txt",
    "engines/python/windows-tcltk-9.0.4-data.zip",
)


def release_fixture(directory, payloads=None):
    directory.mkdir()
    files = []
    contents = {name: b"public installer boundary test\n" for name in (
        "pyproject.toml", "uv.lock", "scripts/fiji_setup.py",
        "services/api/src/cytellect_api/local.py", "engines/fiji/runtime.lock.json", "apps/web/out/index.html",
        *RUNTIME_ASSETS,
    )}
    contents.update(payloads or {})
    for name, content in contents.items():
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        files.append({"path": name, "sha256": hashlib.sha256(content).hexdigest(), "size": len(content)})
    return {"schema": "cytellect-local-release/1", "platform": "windows-x64",
            "version": "0.1.0-local.1", "source_commit": "a" * 40, "files": files}


def verify(directory, install_root):
    shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    return subprocess.run(
        [str(shell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts/local_setup.ps1"),
         "-SourceRoot", str(directory), "-InstallRoot", str(install_root), "-Console", "-VerifyOnly", "-NoShortcut"],
        capture_output=True, text=True, check=False, timeout=30,
    )


def test_verified_release_does_not_install_or_download(tmp_path):
    source = tmp_path / "source with spaces"
    manifest = release_fixture(source)
    (source / "local-release.json").write_text(json.dumps(manifest))
    result = verify(source, tmp_path / "installation")
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (tmp_path / "installation").exists()


@pytest.mark.parametrize("fault", ["modified", "traversal", "duplicate", "missing", "absolute", "alternate_stream", "platform"])
def test_release_rejects_unverified_or_unsafe_files(tmp_path, fault):
    source = tmp_path / "source"
    manifest = release_fixture(source)
    if fault == "modified":
        (source / "uv.lock").write_bytes(b"changed after manifest")
    elif fault == "traversal":
        manifest["files"][0]["path"] = "../outside.toml"
    elif fault == "duplicate":
        manifest["files"].append(manifest["files"][0].copy())
    elif fault == "missing":
        manifest["files"] = manifest["files"][:-1]
    elif fault == "absolute":
        manifest["files"][0]["path"] = str(source / "pyproject.toml")
    elif fault == "alternate_stream":
        manifest["files"][0]["path"] = "pyproject.toml:stream"
    else:
        manifest["platform"] = "unexpected-platform"
    (source / "local-release.json").write_text(json.dumps(manifest))
    result = verify(source, tmp_path / "installation")
    assert result.returncode == 1
    assert not (tmp_path / "installation").exists()
    assert str(source) not in result.stdout + result.stderr


@pytest.mark.parametrize("asset", RUNTIME_ASSETS)
@pytest.mark.parametrize("fault", ["omitted", "modified"])
def test_new_runtime_assets_are_required_and_hash_verified_before_install(tmp_path, asset, fault):
    source = tmp_path / "source"
    manifest = release_fixture(source)
    if fault == "omitted":
        manifest["files"] = [entry for entry in manifest["files"] if entry["path"] != asset]
    else:
        (source / asset).write_bytes(b"changed runtime or installation input\n")
    (source / "local-release.json").write_text(json.dumps(manifest))
    result = verify(source, tmp_path / "installation")
    assert result.returncode == 1
    assert not (tmp_path / "installation").exists()
    assert str(source) not in result.stdout + result.stderr


def test_private_dacl_initial_retry_and_new_version_do_not_require_admin(tmp_path):
    """Preserve the initial owner/group while privatizing and re-entering the DACL."""
    shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    harness = tmp_path / "verify-acl.ps1"
    harness.write_text(r'''
param([string]$Setup, [string]$Destination)
$ErrorActionPreference='Stop'
$env:PSModulePath=(Join-Path $PSHOME 'Modules')+[IO.Path]::PathSeparator+$env:PSModulePath
$tokens=$null; $errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($Setup,[ref]$tokens,[ref]$errors)
if ($errors.Count) { throw 'parse_failed' }
foreach ($name in @('Get-SafeChild','Initialize-PrivateRoot')) {
    $function=$ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name},$true)
    Invoke-Expression $function.Extent.Text
}
$InstallRoot=$Destination
$SourceRoot=Split-Path -Parent $Setup
# An elevated Windows runner may create directories owned by Administrators.
# Setup promises a private DACL, not ownership replacement or extra privileges.
[IO.Directory]::CreateDirectory($Destination) | Out-Null
$initialAcl=[IO.DirectoryInfo]::new($Destination).GetAccessControl()
$initialOwner=$initialAcl.GetOwner([Security.Principal.SecurityIdentifier]).Value
$initialGroup=$initialAcl.GetGroup([Security.Principal.SecurityIdentifier]).Value
$actual=Initialize-PrivateRoot
$preserved=Join-Path $actual 'data/preserved.txt'
[IO.Directory]::CreateDirectory((Split-Path -Parent $preserved)) | Out-Null
[IO.File]::WriteAllText($preserved,'preserve existing research placeholder')
[IO.Directory]::CreateDirectory((Join-Path $actual 'apps/first-version')) | Out-Null
$null=Initialize-PrivateRoot
[IO.Directory]::CreateDirectory((Join-Path $actual 'apps/second-version')) | Out-Null
$null=Initialize-PrivateRoot
if ([IO.File]::ReadAllText($preserved) -ne 'preserve existing research placeholder') { throw 'existing_file_changed' }
$acl=[IO.DirectoryInfo]::new($actual).GetAccessControl()
$user=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
$group=$acl.GetGroup([Security.Principal.SecurityIdentifier]).Value
if ($owner -ne $initialOwner -or $group -ne $initialGroup) { throw 'owner_or_group_changed' }
if (-not $acl.AreAccessRulesProtected) { throw 'inheritance_not_protected' }
$rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
if ($rules.Count -ne 2) { throw 'unexpected_acl' }
foreach ($rule in $rules) {
    if ($rule.IdentityReference.Value -notin @($user,'S-1-5-18') -or $rule.IsInherited -or
        $rule.AccessControlType -ne 'Allow' -or $rule.FileSystemRights -ne 'FullControl' -or
        $rule.InheritanceFlags -ne [Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit') {
        throw 'acl_not_private'
    }
}
Write-Host 'private_dacl_reentry_passed'
''', encoding="utf-8-sig")
    result = subprocess.run(
        [str(shell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(harness),
         "-Setup", str(ROOT / "scripts/local_setup.ps1"), "-Destination", str(tmp_path / "owned installation")],
        capture_output=True, text=True, check=False, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "private_dacl_reentry_passed" in result.stdout
