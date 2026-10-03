"""Synthetic policy-error classification; does not install or run a blocked binary."""
import json
import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell installer contract")
ROOT = Path(__file__).resolve().parents[1]
CODE = "windows_application_control_blocked"
PRIVATE = r"C:\__synthetic_private__\example-study\python.exe"

HARNESS = r'''
$ErrorActionPreference='Stop'
$tokens=$null; $errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($env:CYTELLECT_TEST_SETUP,[ref]$tokens,[ref]$errors)
if ($errors.Count) { throw 'parse_failed' }
foreach ($name in @('Get-SetupFailureCode','Get-SetupFailureText')) {
    $function=$ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name},$true)
    if ($null -eq $function) { throw 'test_function_absent' }
    Invoke-Expression $function.Extent.Text
}
$case=ConvertFrom-Json $env:CYTELLECT_TEST_CASE
$failure=$null
if ($case.kind -eq 'native') {
    $failure=[ComponentModel.Win32Exception]::new([int]$case.native_code,[string]$case.detail)
} elseif ($case.kind -eq 'ordinary') {
    $failure=[InvalidOperationException]::new([string]$case.detail)
} elseif ($case.kind -eq 'marker') {
    $failure=[InvalidOperationException]::new('windows_application_control_blocked')
    $failure.Data['CytellectSetupFailure']='windows_application_control_blocked'
}
if ($case.wrapped) { $failure=[Reflection.TargetInvocationException]::new($failure) }
$code=Get-SetupFailureCode -Exception $failure -ExitCode $case.exit_code -StandardError $case.detail -UvProcess:$case.uv
[ordered]@{code=$code;text=(Get-SetupFailureText -Code $code -Phase 'install_dependencies')} | ConvertTo-Json -Compress
'''


@pytest.mark.parametrize(
    "kind,native_code,wrapped,exit_code,uv,detail,expected",
    [
        ("native", 4551, False, 0, False, PRIVATE, CODE),
        ("native", 4551, True, 0, False, PRIVATE, CODE),
        ("native", 5, False, 0, False, PRIVATE + " (os error 4551)", None),
        ("ordinary", 0, False, 0, False, "windows_application_control_blocked", None),
        ("marker", 0, True, 0, False, PRIVATE, CODE),
        ("uv", 0, False, 2, True, PRIVATE + " (os error 4551)", CODE),
        ("uv", 0, False, 0, True, PRIVATE + " (os error 4551)", None),
        ("uv", 0, False, 2, False, PRIVATE + " (os error 4551)", None),
        ("uv", 0, False, 2, True, PRIVATE + " (os error 45510)", None),
        ("uv", 0, False, 2, True, PRIVATE + " os error 4551", None),
        ("uv", 0, False, 4551, True, PRIVATE + " (os error 5)", None),
        ("uv", 0, False, 2, True, "", None),
        ("ordinary", 0, False, 0, False, "setup_cancelled", None),
        ("ordinary", 0, False, 0, False, "setup_stage_timeout", None),
    ],
)
def test_precise_error_mapping_without_output_disclosure(
    kind, native_code, wrapped, exit_code, uv, detail, expected,
):
    shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    case = {
        "kind": kind, "native_code": native_code, "wrapped": wrapped,
        "exit_code": exit_code, "uv": uv, "detail": detail,
    }
    environment = {
        **os.environ,
        "CYTELLECT_TEST_SETUP": str(ROOT / "scripts/local_setup.ps1"),
        "CYTELLECT_TEST_CASE": json.dumps(case),
    }
    result = subprocess.run(
        [str(shell), "-NoProfile", "-NonInteractive", "-Command", HARNESS],
        env=environment, capture_output=True, text=True, encoding="utf-8", errors="strict",
        check=False, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "__synthetic_private__" not in result.stdout + result.stderr
    assert result.stderr == ""
    actual = json.loads(result.stdout)
    assert actual["code"] == expected
    if expected:
        assert "Windows" in actual["text"] and "4551" in actual["text"]
        assert "再試行" not in actual["text"]
        assert "接続" not in actual["text"]
        assert "無効" not in actual["text"]
    else:
        assert actual["text"] == "準備を停止しました (install_dependencies)。接続・空き容量を確認して再試行してください。"


PROCESS_HARNESS = r'''
$ErrorActionPreference='Stop'
$tokens=$null; $errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($env:CYTELLECT_TEST_SETUP,[ref]$tokens,[ref]$errors)
if ($errors.Count) { throw 'parse_failed' }
foreach ($name in @('ConvertTo-NativeArgument','Stop-SetupProcess','Get-SetupFailureCode','Invoke-SetupProcess')) {
    $function=$ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name},$true)
    if ($null -eq $function) { throw 'test_function_absent' }
    Invoke-Expression $function.Extent.Text
}
$case=ConvertFrom-Json $env:CYTELLECT_TEST_CASE
$Console=$true
$script:RunningProcess=$null
$script:Cancelled=[bool]$case.cancel
$shell=Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
$directory=Split-Path -Parent $env:CYTELLECT_TEST_SETUP
$outcomes=@()
foreach ($command in $case.commands) {
    try {
        Invoke-SetupProcess -Executable $shell -Arguments @('-NoProfile','-NonInteractive','-Command',$command) `
            -Directory $directory -TimeoutSeconds 10 -UvProcess:$case.uv
        $outcomes += 'success'
    } catch {
        $code=Get-SetupFailureCode -Exception $_.Exception
        if ($null -ne $code) { $outcomes += $code }
        elseif ($_.Exception.Message -in @('setup_stage_failed','setup_cancelled')) {
            $outcomes += $_.Exception.Message
        } else { $outcomes += 'unexpected_test_exception' }
    }
    if ($null -ne $script:RunningProcess) { throw 'process_not_released' }
    $script:Cancelled=$false
}
[ordered]@{outcomes=$outcomes;process_released=($null -eq $script:RunningProcess)} | ConvertTo-Json -Compress
'''


@pytest.mark.parametrize(
    "uv,cancel,commands,expected",
    [
        (True, False, [f"[Console]::Error.WriteLine('{PRIVATE} (os error 4551)'); exit 2"], [CODE]),
        (False, False, [f"[Console]::Error.WriteLine('{PRIVATE} (os error 4551)'); exit 2"],
         ["setup_stage_failed"]),
        (True, False, [f"[Console]::Error.WriteLine('{PRIVATE} (os error 4551)'); exit 0"], ["success"]),
        (True, False, [f"[Console]::Error.WriteLine('{PRIVATE} (os error 5)'); exit 2", "exit 0"],
         ["setup_stage_failed", "success"]),
        (True, True, ["[Threading.Thread]::Sleep(9000)", "exit 0"], ["setup_cancelled", "success"]),
    ],
)
def test_controlled_child_failure_cleanup_and_retry(uv, cancel, commands, expected):
    """Signed Windows shell emits synthetic results; no uv/Python/Fiji install is run."""
    shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    result = subprocess.run(
        [str(shell), "-NoProfile", "-NonInteractive", "-Command", PROCESS_HARNESS],
        env={
            **os.environ,
            "CYTELLECT_TEST_SETUP": str(ROOT / "scripts/local_setup.ps1"),
            "CYTELLECT_TEST_CASE": json.dumps({"uv": uv, "cancel": cancel, "commands": commands}),
        },
        capture_output=True, text=True, encoding="utf-8", errors="strict", check=False, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "__synthetic_private__" not in result.stdout + result.stderr
    assert result.stderr == ""
    assert json.loads(result.stdout) == {"outcomes": expected, "process_released": True}
