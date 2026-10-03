"""Run the trusted setup orchestration with isolated, non-executing side effects."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest
from test_windows_setup import release_fixture

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell installer contract")
ROOT = Path(__file__).resolve().parents[1]

HARNESS = r'''
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$env:PSModulePath=(Join-Path $PSHOME 'Modules')+[IO.Path]::PathSeparator+$env:PSModulePath
$tokens=$null; $errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($env:CYTELLECT_TEST_SETUP,[ref]$tokens,[ref]$errors)
if ($errors.Count) { throw 'parse_failed' }
foreach ($name in @('Get-SafeChild','Get-VerifiedRelease','Update-SetupStatus',
    'ConvertTo-NativeArgument','Install-Cytellect')) {
    $function=$ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name},$true)
    if ($null -eq $function) { throw 'test_function_absent' }
    Invoke-Expression $function.Extent.Text
}
$runtimeAst=[Management.Automation.Language.Parser]::ParseFile($env:CYTELLECT_TEST_RUNTIME,[ref]$tokens,[ref]$errors)
if ($errors.Count) { throw 'runtime_parse_failed' }
foreach ($name in @('Assert-RuntimeDigest','Test-RuntimeFile')) {
    $function=$runtimeAst.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name},$true)
    if ($null -eq $function) { throw 'test_runtime_function_absent' }
    Invoke-Expression $function.Extent.Text
}
$script:RealUpdate=(Get-Command Update-SetupStatus).ScriptBlock
$script:EntryCleared=@()
function Update-SetupStatus([string]$Phase,[string]$Text) {
    if ($Phase -eq 'verify_release') { $script:EntryCleared += ($null -eq $script:LaunchInfo) }
    if ($Phase -eq 'complete' -and $script:Fault -eq 'cancel_complete') { $script:Cancelled=$true }
    & $script:RealUpdate $Phase $Text
}
# No ACL mutation, downloader, executable, COM object, desktop/start-menu write,
# registry change or GUI is used. All filesystem writes stay in the test root.
function Join-Path([AllowEmptyString()][string]$Path,[string]$ChildPath) {
    # Sandboxed Windows can return an empty special-folder path. Redirect only
    # shortcut destinations, including their existence checks, into scratch.
    if ($ChildPath.EndsWith('.lnk')) { $Path=$InstallRoot }
    Microsoft.PowerShell.Management\Join-Path -Path $Path -ChildPath $ChildPath
}
function Initialize-PrivateRoot {
    [IO.Directory]::CreateDirectory((Join-Path $InstallRoot 'setup-cache')) | Out-Null
    return $InstallRoot
}
function Get-PinnedUv([string]$Root) { return (Join-Path $Root 'never-executed-uv.exe') }
function Invoke-SetupProcess([string]$Executable,[string[]]$Arguments,[string]$Directory,
    [hashtable]$Environment=@{},[int]$TimeoutSeconds=1800,[switch]$UvProcess) {
    $script:ProcessCalls++
    $python=Get-SafeChild $Directory '.venv/Scripts/python.exe'
    if ($Arguments[0] -ceq 'pip') {
        if (-not $UvProcess -or $Executable -cne (Join-Path $InstallRoot 'never-executed-uv.exe') -or
            $Environment.UV_PYTHON_DOWNLOADS -cne 'never' -or $Environment.PYTHONDONTWRITEBYTECODE -cne '1') {
            throw 'unexpected_dependency_environment'
        }
        if ($Arguments[1] -ceq 'sync') {
            $expected=@('pip','sync','--require-hashes','--only-binary',':all:','--python',$python,
                '--no-managed-python','--no-python-downloads','--no-config','engines/python/windows-requirements.txt')
            $script:Pipeline += 'hashed-wheel-sync'
        } elseif ($Arguments[1] -ceq 'check') {
            $expected=@('pip','check','--python',$python,'--no-config')
            $script:Pipeline += 'dependency-check'
        } else { throw 'unexpected_pip_operation' }
        if (($Arguments -join '|') -cne ($expected -join '|')) { throw 'unsafe_dependency_arguments' }
        return
    }
    if ($Arguments[0] -cne '-B' -or $UvProcess) { throw 'python_bytecode_policy_missing' }
    switch ($Arguments[1]) {
        '-c' {
            if ($Executable -cne $python) { throw 'wrong_python_interpreter' }
            if ($Arguments[2] -ceq 'import sys,tkinter; assert sys.version_info[:3] == (3,14,8); t=tkinter.Tk(); t.withdraw(); t.update(); t.destroy()') {
                $script:Pipeline += 'gui-check'
            } elseif ($Arguments[2] -ceq 'import sys; from cytellect_analysis.engine import runtime_info; runtime_info(sys.argv[1])') {
                $script:Pipeline += 'fiji-runtime-check'
            } else { throw 'unexpected_python_check' }
        }
        'scripts/fiji_setup.py' {
            if ($Executable -cne $python) { throw 'wrong_python_interpreter' }
            [IO.Directory]::CreateDirectory($Arguments[2]) | Out-Null
            $script:Pipeline += 'fiji-install'
        }
        '-m' {
            if ($Arguments[2] -ceq 'venv') {
                if ($Arguments.Count -ne 5 -or $Arguments[3] -cne '--without-pip' -or
                    $Arguments[4] -cne (Get-SafeChild $Directory '.venv') -or
                    $Executable -cne (Get-SafeChild $InstallRoot 'runtimes/python-test/python.exe')) {
                    throw 'unexpected_venv_creation'
                }
                $bin=Join-Path $Directory '.venv/Scripts'
                [IO.Directory]::CreateDirectory($bin) | Out-Null
                [IO.File]::WriteAllText((Join-Path $bin 'python.exe'),'not an executable')
                [IO.File]::WriteAllText((Join-Path $bin 'pythonw.exe'),'not an executable')
                $script:Pipeline += 'signed-runtime-venv'
            } elseif ($Arguments[2] -ceq 'cytellect_analysis.install_check') {
                if ($Executable -cne $python) { throw 'wrong_python_interpreter' }
                $script:Pipeline += 'analysis-check'
                if ($script:Fault -eq 'completion_write') {
                    [IO.Directory]::CreateDirectory((Join-Path $Directory 'setup-complete.json')) | Out-Null
                }
            } else { throw 'unexpected_test_command' }
        }
        default { throw 'unexpected_test_command' }
    }
}
function New-Object([string]$ComObject) {
    if ($ComObject -ne 'WScript.Shell') { throw 'unexpected_test_com_object' }
    $shell=[pscustomobject]@{}
    $shell | Add-Member ScriptMethod CreateShortcut {
        param($Path)
        $shortcut=[pscustomobject]@{TargetPath='';Arguments='';WorkingDirectory='';Description=''}
        $shortcut | Add-Member ScriptMethod Save {
            $script:ShortcutSaves++
            if ($script:Fault -eq 'shortcut') { throw 'controlled_shortcut_failure' }
        }
        return $shortcut
    }
    return $shell
}
$SourceRoot=$env:CYTELLECT_TEST_SOURCE
$InstallRoot=$env:CYTELLECT_TEST_ROOT
$Console=$false; $NoShortcut=$false; $VerifyOnly=$false
$script:StatusLabel=$null; $script:Cancelled=$false; $script:Phase='initial'
$script:UvVersion='test'; $script:UvSha256='0'*64
$script:PythonVersion='3.14.8'
$script:ProcessCalls=0; $script:ShortcutSaves=0; $script:Fault=$env:CYTELLECT_TEST_FAULT
$script:Pipeline=@(); $script:RuntimeCalls=0; $script:SignedVenvChecks=@()
$script:LaunchInfo=@{executable='stale-must-not-launch'}
$caught=$false; $failureKind='none'
try { Install-Cytellect } catch {
    $caught=$true
    if ($_.Exception.Message -eq 'setup_cancelled') { $failureKind='cancelled' }
    elseif ($_.Exception.Message -like '*controlled_shortcut_failure*') { $failureKind='shortcut' }
    else { $failureKind='completion_write' }
}
$failurePhase=$script:Phase
$failureLaunchReady=($null -ne $script:LaunchInfo)
$firstProcessCalls=$script:ProcessCalls
$app=Join-Path $InstallRoot ('apps/0.0.0-test.'+$PID+'-'+('a'*12))
$marker=Join-Path $app 'setup-complete.json'
$markerAfterFailure=[IO.File]::Exists($marker)
if ([IO.Directory]::Exists($marker)) { [IO.Directory]::Delete($marker,$false) }
$script:Fault='none'; $script:Cancelled=$false
Install-Cytellect
$state=Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
$install=Get-Content -LiteralPath (Get-SafeChild $app 'engines/python/windows-install.json') -Raw | ConvertFrom-Json
[ordered]@{
    caught=$caught;failure_kind=$failureKind;failure_phase=$failurePhase
    failure_launch_ready=$failureLaunchReady;marker_after_failure=$markerAfterFailure
    entry_cleared=$script:EntryCleared;retry_phase=$script:Phase
    retry_launch_ready=($null -ne $script:LaunchInfo)
    retry_ran_checks=($script:ProcessCalls -gt $firstProcessCalls)
    retry_executable_matches=($script:LaunchInfo.executable -eq (Join-Path $app '.venv/Scripts/pythonw.exe'))
    retry_source_matches=($state.source_commit -eq ('a'*40))
    retry_python=$state.python
    retry_no_bytecode=($script:LaunchInfo.arguments[0] -ceq '-B')
    retry_input_hashes_match=($state.wheel_sha256 -ceq $install.wheel.sha256 -and
        $state.requirements_sha256 -ceq $install.requirements.sha256)
    pipeline=$script:Pipeline;runtime_calls=$script:RuntimeCalls;signed_venv_checks=$script:SignedVenvChecks
    shortcut_saves=$script:ShortcutSaves
} | ConvertTo-Json -Compress
'''


RUNTIME_DOUBLE = r'''
# Controlled runtime/venv side effects; signature verification has separate tests.
function Initialize-PinnedPythonRuntime([string]$Root,[string]$App) {
    $script:RuntimeCalls++
    $runtime=Get-SafeChild $Root 'runtimes/python-test'
    [IO.Directory]::CreateDirectory($runtime) | Out-Null
    $specification=Get-Content -LiteralPath (Get-SafeChild $App 'engines/python/windows-runtime.lock.json') -Raw | ConvertFrom-Json
    return @{path=$runtime;specification=$specification;receipt=(Get-SafeChild $Root 'setup-cache/test-receipt.json');
        inventory=@(@{path='controlled-runtime-entry';sha256=('0'*64);bytes=0})}
}
function Assert-SignedPythonVenv([string]$App,$Runtime,[switch]$IfPresent) {
    $script:SignedVenvChecks += [bool]$IfPresent
    if (-not $IfPresent -and -not (Test-Path -LiteralPath (Get-SafeChild $App '.venv/Scripts/pythonw.exe'))) {
        throw 'test_venv_missing'
    }
}
function Assert-PythonRuntimeInventory([string]$Runtime,$Inventory) {
    if ($Runtime -cne (Get-SafeChild $InstallRoot 'runtimes/python-test') -or
        @($Inventory).Count -ne 1 -or $Inventory[0].path -cne 'controlled-runtime-entry') {
        throw 'test_runtime_inventory_mismatch'
    }
    $script:Pipeline += 'post-analysis-runtime-integrity'
}
'''


@pytest.mark.parametrize(
    "fault,kind,phase,marker_after_failure,shortcut_saves",
    [
        ("shortcut", "shortcut", "create_shortcut", False, 3),
        ("completion_write", "completion_write", "create_shortcut", False, 4),
        ("cancel_complete", "cancelled", "complete", True, 4),
    ],
)
def test_late_setup_failure_never_keeps_launch_ready_and_retry_finishes(
    tmp_path, fault, kind, phase, marker_after_failure, shortcut_saves,
):
    source = tmp_path / "source"
    wheel_path = "wheels/cytellect-0.1.0-py3-none-any.whl"
    requirements_path = "engines/python/windows-requirements.txt"
    wheel = b"public synthetic wheel bytes; never installed\n"
    wheel_hash = hashlib.sha256(wheel).hexdigest()
    requirements = f"./{wheel_path} --hash=sha256:{wheel_hash}\n".encode()
    inputs = {"schema": "cytellect-windows-install/1",
              "wheel": {"path": wheel_path, "bytes": len(wheel), "sha256": wheel_hash},
              "requirements": {"path": requirements_path, "bytes": len(requirements),
                               "sha256": hashlib.sha256(requirements).hexdigest()}}
    runtime = {"composition_version": "test", "python": {"version": "3.14.8",
               "url": "https://invalid.example/not-requested", "sha256": "0" * 64},
               "data_asset": {"sha256": "1" * 64}}
    manifest = release_fixture(source, {
        wheel_path: wheel, requirements_path: requirements,
        "engines/python/windows-install.json": json.dumps(inputs).encode(),
        "engines/python/windows-runtime.lock.json": json.dumps(runtime).encode(),
        "scripts/windows_runtime.ps1": RUNTIME_DOUBLE.encode(),
    })
    # The child PID is included solely to avoid an existing user's shortcut path.
    manifest["version"] = "0.0.0-test"
    (source / "local-release.json").write_text(json.dumps(manifest), encoding="utf-8")
    prelude = r'''
$manifest=Get-Content -LiteralPath (Join-Path $env:CYTELLECT_TEST_SOURCE 'local-release.json') -Raw | ConvertFrom-Json
$manifest.version='0.0.0-test.'+$PID
[IO.File]::WriteAllText((Join-Path $env:CYTELLECT_TEST_SOURCE 'local-release.json'),($manifest | ConvertTo-Json -Depth 5))
'''
    shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    result = subprocess.run(
        # Match the existing trusted Setup.cmd invocation for its local helper;
        # this affects this process only, never system/application-control policy.
        [str(shell), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", prelude + HARNESS],
        env={**os.environ, "CYTELLECT_TEST_SETUP": str(ROOT / "scripts/local_setup.ps1"),
             "CYTELLECT_TEST_RUNTIME": str(ROOT / "scripts/windows_runtime.ps1"),
             "CYTELLECT_TEST_SOURCE": str(source), "CYTELLECT_TEST_ROOT": str(tmp_path / "installation"),
             "CYTELLECT_TEST_FAULT": fault},
        capture_output=True, text=True, encoding="utf-8", errors="strict", check=False, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stderr == ""
    assert str(tmp_path) not in result.stdout
    assert json.loads(result.stdout) == {
        "caught": True, "failure_kind": kind, "failure_phase": phase,
        "failure_launch_ready": False, "marker_after_failure": marker_after_failure,
        "entry_cleared": [True, True], "retry_phase": "complete", "retry_launch_ready": True,
        "retry_ran_checks": True, "retry_executable_matches": True, "retry_source_matches": True,
        "retry_python": "3.14.8", "retry_no_bytecode": True, "retry_input_hashes_match": True,
        "pipeline": ["signed-runtime-venv", "hashed-wheel-sync", "dependency-check", "gui-check",
                     "fiji-install", "fiji-runtime-check", "analysis-check", "post-analysis-runtime-integrity",
                     "signed-runtime-venv", "hashed-wheel-sync", "dependency-check", "gui-check",
                     "fiji-runtime-check", "analysis-check", "post-analysis-runtime-integrity"],
        "runtime_calls": 2, "signed_venv_checks": [True, False, False, False, True, False, False, False],
        "shortcut_saves": shortcut_saves,
    }
