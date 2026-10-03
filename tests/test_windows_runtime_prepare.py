"""Builder preparation boundaries; no MSI installation or network use in unit tests."""
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

import psutil
import pytest

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell release preparation")
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/prepare_windows_runtime_data.ps1"

HARNESS = r'''
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$env:PSModulePath=(Join-Path $PSHOME 'Modules')+[IO.Path]::PathSeparator+$env:PSModulePath
$tokens=$null; $errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($env:CYTELLECT_TEST_SCRIPT,[ref]$tokens,[ref]$errors)
if($errors.Count) { throw 'parse_failed' }
foreach($function in $ast.FindAll({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst]},$true)) {
    Invoke-Expression $function.Extent.Text
}
$script:PrepareCancel=Join-Path $env:CYTELLECT_TEST_ROOT 'cancel.request'
$script:PrepareProcess=$null
$script:PrepareProcesses=[Collections.Generic.List[object]]::new()
$case=Get-Content -LiteralPath $env:CYTELLECT_TEST_CASE -Raw | ConvertFrom-Json
$before=@(Get-ChildItem -LiteralPath $env:CYTELLECT_TEST_ROOT -File -Recurse | ForEach-Object {$_.Name})
try {
    switch($case.action) {
        'cached' {
            $path=Get-PrepareArtifact $env:CYTELLECT_TEST_ROOT 'cached.zip' $case.specification
            @{ok=$true;name=[IO.Path]::GetFileName($path)} | ConvertTo-Json -Compress
        }
        'child' {
            $null=Get-PrepareChild $env:CYTELLECT_TEST_ROOT $case.name
            @{ok=$true} | ConvertTo-Json -Compress
        }
        'scripts' {
            $paths=Get-PrepareScriptZips (Join-Path $env:CYTELLECT_TEST_ROOT 'extracted') $case.specifications
            @{ok=$true;count=$paths.Count;names=@($paths.Values | ForEach-Object {[IO.Path]::GetFileName($_)})} | ConvertTo-Json -Compress
        }
        'signature' {
            function Get-AuthenticodeSignature([string]$LiteralPath) {
                return [pscustomobject]@{Status=$case.status;SignerCertificate=[pscustomobject]@{Subject=$case.subject;Thumbprint='synthetic'}}
            }
            $result=Assert-PreparePsfSignature 'never-executed'
            @{ok=$true;status=$result.status} | ConvertTo-Json -Compress
        }
        'process' {
            $shell=Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
            if ($case.PSObject.Properties['stop_command']) {
                # Test-only replacement: exercise the real drain/deadline/target gate.
                function Start-PrepareStopCommand([int]$ProcessId) {
                    $start=[Diagnostics.ProcessStartInfo]::new()
                    $start.FileName=$shell
                    $start.Arguments=(@('-NoProfile','-NonInteractive','-Command',$case.stop_command) | ForEach-Object {ConvertTo-PrepareArgument $_}) -join ' '
                    $start.WorkingDirectory=$env:CYTELLECT_TEST_ROOT
                    $start.UseShellExecute=$false
                    $start.CreateNoWindow=$true
                    $start.RedirectStandardOutput=$true
                    $start.RedirectStandardError=$true
                    return [Diagnostics.Process]::Start($start)
                }
            }
            Invoke-PrepareProcess $shell @('-NoProfile','-NonInteractive','-Command',$case.command) $env:CYTELLECT_TEST_ROOT 'data_builder' $case.timeout
            @{ok=$true;released=($null -eq $script:PrepareProcess);processes=@($script:PrepareProcesses.ToArray())} | ConvertTo-Json -Depth 5 -Compress
        }
        'msi_arguments' {
            $msi='C:\synthetic build\tcltk.msi';$target='C:\synthetic build\fresh\extracted'
            $arguments=Get-PrepareMsiArguments $msi $target 'C:\synthetic build\private.log'
            @{ok=$true;command=$arguments} | ConvertTo-Json -Compress
        }
        default { throw 'test_action_invalid' }
    }
} catch {
    $code=$_.Exception.Message
    if ($code -cnotmatch '^prepare_[a-z_]+$') {$code='unclassified_test_failure'}
    @{ok=$false;code=$code;released=($null -eq $script:PrepareProcess);processes=@($script:PrepareProcesses.ToArray())} | ConvertTo-Json -Depth 5 -Compress
    exit 1
}
'''


def owned_command(command, identity):
    """Record only synthetic child identity, for exact PID/creation-time cleanup."""
    return (
        "$owned=[Diagnostics.Process]::GetCurrentProcess();"
        "$identity=@{pid=$PID;created=$owned.StartTime.ToFileTimeUtc()} | ConvertTo-Json -Compress;"
        f"[IO.File]::WriteAllText('{identity}',$identity);"
        + command
    )


def cleanup_owned_processes(tmp_path):
    cleaned = []
    for name in ("owned-child.json", "owned-stop.json"):
        path = tmp_path / name
        if not path.exists():
            continue
        identity = json.loads(path.read_text(encoding="utf-8-sig"))
        try:
            process = psutil.Process(identity["pid"])
            created = identity["created"] / 10_000_000 - 11_644_473_600
            # Never terminate an unrelated process after PID reuse.
            if abs(process.create_time() - created) >= 0.0001:
                continue
            process.kill()
            process.wait(timeout=5)
            cleaned.append(name)
        except psutil.NoSuchProcess:
            continue
    return cleaned


def run(tmp_path, case, *, expect_live_target=False):
    case = dict(case)
    if case["action"] == "process":
        case["command"] = owned_command(case["command"], "owned-child.json")
        if "stop_command" in case:
            case["stop_command"] = owned_command(case["stop_command"], "owned-stop.json")
    specification = tmp_path / "case.json"
    specification.write_text(json.dumps(case), encoding="utf-8")
    shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    try:
        # File-backed capture avoids communicate() waiting for inherited pipe handles
        # after a deliberately unkillable target outlives the PowerShell harness.
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            result = subprocess.run(
                [str(shell), "-NoProfile", "-NonInteractive", "-Command", HARNESS],
                env={**os.environ, "CYTELLECT_TEST_SCRIPT": str(SCRIPT),
                     "CYTELLECT_TEST_ROOT": str(tmp_path), "CYTELLECT_TEST_CASE": str(specification)},
                stdout=stdout, stderr=stderr, check=False, timeout=40,
            )
            stdout.seek(0)
            stderr.seek(0)
            output, error = stdout.read().decode("utf-8"), stderr.read().decode("utf-8")
    finally:
        cleaned = cleanup_owned_processes(tmp_path)
    assert output.strip(), error
    assert str(tmp_path) not in output
    assert "synthetic-private-error" not in output + error
    receipt = json.loads(output)
    (tmp_path / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    assert cleaned == (["owned-child.json"] if expect_live_target else []), (cleaned, receipt)
    return result.returncode, receipt


def artifact(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "url": "https://www.python.org/ftp/python/3.14.8/python-3.14.8-amd64.zip"}


def test_verified_cached_artifact_uses_no_network_and_preserves_bytes(tmp_path):
    raw = b"test-only pinned cache"
    (tmp_path / "cached.zip").write_bytes(raw)
    for _ in range(2):
        code, receipt = run(tmp_path, {"action": "cached", "specification": artifact(raw)})
        assert code == 0 and receipt == {"ok": True, "name": "cached.zip"}
        assert (tmp_path / "cached.zip").read_bytes() == raw


@pytest.mark.parametrize("change", ["hash", "size", "url", "cancel"])
def test_cached_tamper_and_nonpinned_origin_or_cancel_fail_without_network(tmp_path, change):
    raw = b"test-only pinned cache"
    (tmp_path / "cached.zip").write_bytes(raw)
    spec = artifact(raw)
    if change == "hash":
        spec["sha256"] = "0" * 64
    elif change == "size":
        spec["bytes"] += 1
    elif change == "url":
        spec["url"] = "https://invalid.example/not-requested"
    else:
        (tmp_path / "cancel.request").write_bytes(b"")
    code, receipt = run(tmp_path, {"action": "cached", "specification": spec})
    assert code == 1 and receipt["code"] == {
        "hash": "prepare_cached_artifact_modified", "size": "prepare_cached_artifact_modified",
        "url": "prepare_artifact_spec_invalid", "cancel": "prepare_cancelled",
    }[change]
    assert (tmp_path / "cached.zip").read_bytes() == raw


@pytest.mark.parametrize("name", ["../outside", "/absolute", "nested/../bad", "C:/absolute", "a\\b", "a:stream"])
def test_extraction_child_paths_cannot_escape_owned_scratch(tmp_path, name):
    code, receipt = run(tmp_path, {"action": "child", "name": name})
    assert code == 1 and receipt["code"] == "prepare_unsafe_child"


@pytest.mark.parametrize("status,subject,passes", [
    ("Valid", "CN=Python Software Foundation, O=Python Software Foundation, C=US", True),
    ("NotSigned", "O=Python Software Foundation, C=US", False),
    ("HashMismatch", "O=Python Software Foundation, C=US", False),
    ("Valid", "O=Unrelated publisher, C=US", False),
])
def test_signature_requires_valid_psf_evidence(tmp_path, status, subject, passes):
    code, receipt = run(tmp_path, {"action": "signature", "status": status, "subject": subject})
    assert (code == 0) is passes
    assert receipt["ok"] is passes


@pytest.mark.parametrize("fault", [None, "missing", "duplicate", "modified"])
def test_exact_two_derived_archives_are_located_by_name_and_identity(tmp_path, fault):
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    specs = []
    for kind in ("tcl", "tk"):
        raw = f"synthetic {kind} data archive".encode()
        name = f"lib{kind}9.0.4.zip"
        (extracted / name).write_bytes(raw)
        specs.append({**artifact(raw), "id": kind, "version": "9.0.4"})
    if fault == "missing":
        (extracted / "libtk9.0.4.zip").unlink()
    elif fault == "modified":
        (extracted / "libtk9.0.4.zip").write_bytes(b"modified")
    elif fault == "duplicate":
        nested = extracted / "other"
        nested.mkdir()
        (nested / "libtk9.0.4.zip").write_bytes((extracted / "libtk9.0.4.zip").read_bytes())
    code, receipt = run(tmp_path, {"action": "scripts", "specifications": specs})
    assert (code == 0) is (fault is None)
    if fault is None:
        assert receipt["count"] == 2
        assert set(receipt["names"]) == {"libtcl9.0.4.zip", "libtk9.0.4.zip"}
    else:
        assert receipt["code"] in {"prepare_extracted_zip_mismatch", "prepare_extracted_zips_missing"}


@pytest.mark.parametrize("command,timeout,expected", [
    ("[Console]::WriteLine('synthetic-private-error'); exit 0", 5, None),
    ("[Console]::Error.WriteLine('synthetic-private-error'); exit 7", 5, "prepare_process_failed"),
    ("Start-Sleep -Seconds 90", 3, "prepare_process_timeout"),
    ("[IO.File]::WriteAllText('cancel.request','cancel'); Start-Sleep -Seconds 90", 5, "prepare_cancelled"),
])
def test_hidden_child_is_bounded_and_raw_output_is_not_logged(tmp_path, command, timeout, expected):
    code, receipt = run(tmp_path, {"action": "process", "command": command, "timeout": timeout})
    assert (code == 0) is (expected is None)
    assert receipt["released"] is True
    assert receipt["processes"][0]["stopped"] is True, receipt
    assert receipt["processes"][0]["elapsed_ms"] >= 0
    assert receipt["processes"][0]["started_utc"] <= receipt["processes"][0]["finished_utc"]
    assert receipt["processes"][0]["elapsed_ms"] < 30_000  # Cannot pass by natural 90 s exit.
    if expected:
        assert receipt["code"] == expected
    if expected in {"prepare_process_timeout", "prepare_cancelled"}:
        stop = receipt["processes"][0]["stop_command"]
        assert stop == {"attempted": True, "command_failed": False, "command_stopped": True,
                        "exit_code": 0, "output_drained": True, "timed_out": False}


@pytest.mark.parametrize("stop_command,exit_code,timed_out", [
    ("exit 0", 0, False),
    ("[Console]::Write('synthetic-private-error' * 10000);"
     "[Console]::Error.Write('synthetic-private-error' * 10000); exit 5", 5, False),
    ("Start-Sleep -Seconds 90", None, True),
])
def test_unconfirmed_stop_retains_target_failure_and_bounds_stop_command(
    tmp_path, stop_command, exit_code, timed_out,
):
    code, receipt = run(tmp_path, {
        "action": "process", "timeout": 5,
        "command": "[IO.File]::WriteAllText('cancel.request','cancel'); Start-Sleep -Seconds 90",
        "stop_command": stop_command,
    }, expect_live_target=True)
    assert code == 1 and receipt["code"] == "prepare_process_stop_unconfirmed"
    process = receipt["processes"][0]
    assert receipt["released"] is True  # Disposed handle is not stopped-process evidence.
    assert process["stopped"] is False and process["exit_code"] is None
    assert process["cancelled"] is True and process["timed_out"] is False
    assert process["elapsed_ms"] < 30_000
    stop = process["stop_command"]
    assert stop["command_stopped"] is True and stop["output_drained"] is True
    assert stop["timed_out"] is timed_out
    if exit_code is not None:
        assert stop["exit_code"] == exit_code
        assert stop["command_failed"] is (exit_code != 0)
    else:
        assert stop["exit_code"] is not None


def test_failed_tree_stop_is_not_replaced_by_parent_natural_exit(tmp_path):
    code, receipt = run(tmp_path, {
        "action": "process", "timeout": 5,
        "command": "[IO.File]::WriteAllText('cancel.request','cancel'); Start-Sleep -Seconds 3",
        "stop_command": "exit 5",
    })
    assert code == 1 and receipt["code"] == "prepare_process_stop_unconfirmed"
    process = receipt["processes"][0]
    assert process["stopped"] is True and process["exit_code"] == 0
    assert process["cancelled"] is True
    assert process["stop_command"]["command_failed"] is True
    assert process["stop_command"]["exit_code"] == 5


def test_prestart_cancellation_does_not_start_child(tmp_path):
    (tmp_path / "cancel.request").write_bytes(b"")
    code, receipt = run(tmp_path, {"action": "process", "command": "throw 'must not run'", "timeout": 5})
    assert code == 1 and receipt["code"] == "prepare_cancelled"
    assert receipt["released"] is True and receipt["processes"] == []


def test_msi_arguments_keep_administrative_mode_and_quoted_target(tmp_path):
    code, receipt = run(tmp_path, {"action": "msi_arguments"})
    assert code == 0
    command = receipt["command"]
    assert command.startswith('/a "C:\\synthetic build\\tcltk.msi"')
    assert ' /qn /norestart ' in command
    assert 'TARGETDIR="C:\\synthetic build\\fresh\\extracted"' in command
    assert '"/a"' not in command and '"/qn"' not in command and ' /i ' not in command
