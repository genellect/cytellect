"""Different-version setup orchestration with real scratch storage collection."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import test_windows_setup_completion as completion
from test_windows_setup import release_fixture
from test_windows_setup_completion import HARNESS, ROOT, RUNTIME_DOUBLE

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows setup integration")


def test_three_application_versions_download_fiji_once_and_bound_storage(tmp_path):
    source = tmp_path / "source"
    wheel_path = "wheels/cytellect-0.1.0-py3-none-any.whl"
    requirements_path = "engines/python/windows-requirements.txt"
    wheel = b"public test wheel; never executed"
    requirements = b"public test requirements"
    inputs = {"schema": "cytellect-windows-install/1",
              "wheel": {"path": wheel_path, "bytes": len(wheel), "sha256": hashlib.sha256(wheel).hexdigest()},
              "requirements": {"path": requirements_path, "bytes": len(requirements),
                               "sha256": hashlib.sha256(requirements).hexdigest()}}
    runtime = {"composition_version": "test", "python": {"version": "3.14.8",
               "url": "https://invalid.example/not-requested", "sha256": "0" * 64},
               "data_asset": {"sha256": "1" * 64}}
    manifest = release_fixture(source, {wheel_path: wheel, requirements_path: requirements,
        "engines/python/windows-install.json": json.dumps(inputs).encode(),
        "engines/python/windows-runtime.lock.json": json.dumps(runtime).encode(),
        "scripts/windows_runtime.ps1": RUNTIME_DOUBLE.encode()})
    (source / "local-release.json").write_text(json.dumps(manifest), encoding="utf-8")
    harness = HARNESS.split("$caught=$false; $failureKind='none'")[0]
    harness = harness.replace("$script:UvVersion='test'", "$script:UvVersion='0.12.2'")
    harness = harness.replace("return $InstallRoot", "[IO.File]::WriteAllText((Join-Path $InstallRoot 'setup-root.json'),'{\"product\":\"cytellect-local\",\"schema\":1}'); return $InstallRoot")
    harness = harness.replace("function Get-PinnedUv([string]$Root) { return", "function Get-PinnedUv([string]$Root) { [IO.Directory]::CreateDirectory((Join-Path $Root 'tools/uv-0.12.2')) | Out-Null; return")
    before = """[IO.File]::WriteAllText((Join-Path $InstallRoot 'setup-storage-result.json'),
                    '{"retained_apps":2,"reclaimed_bytes":0,"unknown_apps_retained":false,"unmanaged_cache_retained":false,"process_inventory_available":true}')"""
    assert before in harness
    # Real collector on actual scratch directories. Only the binary downloader,
    # venv creation and scientific launch checks remain controlled doubles.
    harness = harness.replace(before, """& $env:CYTELLECT_TEST_PYTHON @Arguments
                if ($LASTEXITCODE -ne 0) { throw 'storage_process_failed' }""")
    harness += r'''
$script:Fault='none'; $NoShortcut=$true
$paths=@(); $fijiPaths=@()
$failedSetupPreserved=$false
foreach ($version in @('0.1.0-local.1','0.1.0-local.2','0.1.0-local.3')) {
    $manifest=Get-Content -LiteralPath (Join-Path $SourceRoot 'local-release.json') -Raw | ConvertFrom-Json
    $manifest.version=$version
    [IO.File]::WriteAllText((Join-Path $SourceRoot 'local-release.json'),($manifest | ConvertTo-Json -Depth 5))
    if ($version -eq '0.1.0-local.3') {
        $script:Fault='completion_write'
        $failed=$false
        try { Install-Cytellect } catch { $failed=$true }
        $prior=Get-Content -LiteralPath (Join-Path $InstallRoot 'setup-storage.json') -Raw | ConvertFrom-Json
        $failedSetupPreserved=($failed -and $prior.order.Count -eq 2 -and
            (Test-Path -LiteralPath $paths[0]) -and (Test-Path -LiteralPath $paths[1]))
        $marker=Get-SafeChild $InstallRoot ('apps/'+$version+'-'+('a'*12)+'/setup-complete.json')
        [IO.Directory]::Delete($marker,$false)
        $script:Fault='none'
    }
    Install-Cytellect
    $app=Join-Path $InstallRoot ('apps/'+$version+'-'+('a'*12))
    $paths += $app
    $state=Get-Content -LiteralPath (Join-Path $app 'setup-complete.json') -Raw | ConvertFrom-Json
    $fijiPaths += $state.fiji
}
$result=Get-Content -LiteralPath (Join-Path $InstallRoot 'setup-storage-result.json') -Raw | ConvertFrom-Json
[ordered]@{
    fiji_downloads=@($script:Pipeline | Where-Object {$_ -eq 'fiji-install'}).Count
    fiji_paths_same=(@($fijiPaths | Select-Object -Unique).Count -eq 1)
    oldest_removed=(-not (Test-Path -LiteralPath $paths[0]))
    previous_present=(Test-Path -LiteralPath $paths[1])
    current_present=(Test-Path -LiteralPath $paths[2])
    retained=$result.retained_apps
    reclaimed=($result.reclaimed_bytes -gt 0)
    failed_setup_preserved=$failedSetupPreserved
} | ConvertTo-Json -Compress
'''
    shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    completed = subprocess.run([str(shell), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", harness],
        env={**os.environ, "CYTELLECT_TEST_SETUP": str(ROOT / "scripts/local_setup.ps1"),
             "CYTELLECT_TEST_RUNTIME": str(ROOT / "scripts/windows_runtime.ps1"),
             "CYTELLECT_TEST_SOURCE": str(source), "CYTELLECT_TEST_ROOT": str(tmp_path / "installation"),
             "CYTELLECT_TEST_PYTHON": sys.executable, "CYTELLECT_TEST_FAULT": "none",
             "PYTHONPATH": os.pathsep.join(str(ROOT / p) for p in ["services/api/src", "packages/analysis/src", "services/worker/src"])},
        capture_output=True, text=True, encoding="utf-8", errors="strict", timeout=60)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(completed.stdout) == {"fiji_downloads": 1, "fiji_paths_same": True,
        "oldest_removed": True, "previous_present": True, "current_present": True,
        "retained": 2, "reclaimed": True, "failed_setup_preserved": True}


@pytest.mark.parametrize("fault", ["completion_write", "shortcut"])
def test_failed_completion_restores_previous_stable_shortcut(tmp_path, monkeypatch, fault):
    harness = completion.HARNESS
    harness = harness.replace("throw 'controlled_shortcut_failure'", "[IO.File]::WriteAllText($this.StoredPath,'partial'); throw 'controlled_shortcut_failure'")
    harness = harness.replace("$caught=$false; $failureKind='none'", r'''
    [IO.Directory]::CreateDirectory($InstallRoot) | Out-Null
    $oldShortcut=([ordered]@{
        TargetPath=(Get-SafeChild $InstallRoot 'apps/previous/.venv/Scripts/pythonw.exe');
        Arguments='old preserved arguments'; WorkingDirectory=(Get-SafeChild $InstallRoot 'apps/previous');
        Description='Cytellect local analysis and control window'
    } | ConvertTo-Json)
    $shortcutFile=Join-Path $InstallRoot 'Cytellect.lnk'
    [IO.File]::WriteAllText($shortcutFile,$oldShortcut)
    $caught=$false; $failureKind='none' ''')
    harness = harness.replace("$failurePhase=$script:Phase", r'''
    if ([IO.File]::ReadAllText($shortcutFile) -cne $oldShortcut) { throw 'previous_shortcut_was_not_restored' }
    $failurePhase=$script:Phase''')
    monkeypatch.setattr(completion, "HARNESS", harness)
    completion.test_late_setup_failure_never_keeps_launch_ready_and_retry_finishes(
        tmp_path, fault, fault, "create_shortcut", False, 3 if fault == "shortcut" else 4)
