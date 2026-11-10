"""Owned scratch-only Windows recovery boundaries; no installation or GUI."""
import json
import os
import subprocess
from pathlib import Path

import pytest
from test_windows_setup_cleanup import ROOT, SCRIPT

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows setup recovery")


def run_script(tmp_path, body):
    header = SCRIPT.split("$root=$env:CYTELLECT_CLEANUP_ROOT")[0]
    header += "\n$env:PSModulePath=(Join-Path $PSHOME 'Modules')+[IO.Path]::PathSeparator+$env:PSModulePath\n"
    shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    result = subprocess.run([str(shell), "-NoProfile", "-NonInteractive", "-Command", header + body],
        env={**os.environ, "CYTELLECT_SETUP": str(ROOT / "scripts/local_setup.ps1"),
             "CYTELLECT_CLEANUP_ROOT": str(tmp_path / "install")},
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_locked_scratch_does_not_block_app_runtime_or_empty_creation_recovery(tmp_path):
    result = run_script(tmp_path, r'''
$root=$env:CYTELLECT_CLEANUP_ROOT
[IO.Directory]::CreateDirectory((Join-Path $root 'setup-cache')) | Out-Null
# Both interruptions leave only creation intent and an empty directory.
foreach($number in @(1,2)) {
    $a=New-SetupAttempt $root ('apps/0.1.0-test.'+$number+'-'+('a'*12))
    $a.app_owned=$true
    Write-SetupAttempt $root $a
    $app=Get-SafeChild $root $a.app
    [IO.Directory]::CreateDirectory($app) | Out-Null
    if($number -eq 2) {
        [IO.File]::WriteAllText((Join-Path $app '.setup-owner.json'),'proof removed just before empty-directory failure')
        [IO.File]::Delete((Join-Path $app '.setup-owner.json'))
    }
    $closed=Close-SetupAttempt $root $a
    if(Test-Path -LiteralPath $app) { throw 'empty_creation_not_recovered' }
}
$b=New-SetupAttempt $root ('apps/0.1.0-test.3-'+('b'*12))
OwnedApp $root $b
Register-SetupRuntime $root $b 'runtimes/python-test'
[IO.Directory]::CreateDirectory((Join-Path $root 'runtimes/python-test')) | Out-Null
[IO.File]::WriteAllText((Join-Path $root 'runtimes/python-test/unit.txt'),'owned')
$scratch=Get-SafeChild $root ($b.directory+'/scratch')
[IO.Directory]::CreateDirectory($scratch) | Out-Null
$file=Join-Path $scratch 'locked.bin'
[IO.File]::WriteAllText($file,'owned scratch bytes')
$handle=[IO.File]::Open($file,'Open','ReadWrite','None')
try { $first=Close-SetupAttempt $root $b } finally { $handle.Dispose() }
$independent=(-not(Test-Path -LiteralPath (Get-SafeChild $root $b.app)) -and
    -not(Test-Path -LiteralPath (Join-Path $root 'runtimes/python-test')) -and
    (Test-Path -LiteralPath (Get-SafeChild $root $b.directory)) -and $first.deferred_types -contains 'scratch')
$second=Close-SetupAttempt $root $b
[ordered]@{independent=$independent;recovered=($second.deferred_items -eq 0 -and
    -not(Test-Path -LiteralPath (Get-SafeChild $root $b.directory)))} | ConvertTo-Json -Compress
''')
    assert result == {"independent": True, "recovered": True}


def test_failed_and_successful_setup_history_is_atomic_bounded_and_retained(tmp_path):
    result = run_script(tmp_path, r'''
$root=$env:CYTELLECT_CLEANUP_ROOT
foreach($number in 1..2) {
    $id=('{0:x32}' -f $number)
    $summary=@{schema='cytellect-setup-result/1';attempt_id=$id;success=($number -eq 2);
        error_code=$(if($number -eq 1){'setup_stage_timeout'}else{$null})}
    Write-SetupSummary $root $summary
}
$logs=Join-Path $root 'logs'
$both=([IO.File]::Exists((Join-Path $logs ('setup-'+('{0:x32}' -f 1)+'.json'))) -and
    [IO.File]::Exists((Join-Path $logs ('setup-'+('{0:x32}' -f 2)+'.json'))))
foreach($number in 3..12) {
    Write-SetupSummary $root @{schema='cytellect-setup-result/1';attempt_id=('{0:x32}' -f $number);success=$true}
}
$history=@(Get-ChildItem -LiteralPath $logs -Filter 'setup-*.json' | Where-Object {$_.Name -cmatch '^setup-[a-f0-9]{32}\.json$'})
$latest=Get-Content -LiteralPath (Join-Path $logs 'setup-latest.json') -Raw | ConvertFrom-Json
[ordered]@{both=$both;history=$history.Count;latest=$latest.attempt_id;
    temporary=@(Get-ChildItem -LiteralPath $logs -Filter '*.tmp').Count} | ConvertTo-Json -Compress
''')
    assert result == {"both": True, "history": 10, "latest": f"{12:032x}", "temporary": 0}


def test_verified_legacy_locks_protect_only_the_runtimes_the_old_app_references(tmp_path):
    result = run_script(tmp_path, r"""
$root=$env:CYTELLECT_CLEANUP_ROOT
[IO.Directory]::CreateDirectory((Join-Path $root 'setup-cache')) | Out-Null
$old=Get-SafeChild $root ('apps/0.1.0-local.21-'+('a'*12))
[IO.Directory]::CreateDirectory((Join-Path $old 'engines/python')) | Out-Null
[IO.Directory]::CreateDirectory((Join-Path $old 'engines/fiji')) | Out-Null
[IO.Directory]::CreateDirectory((Join-Path $old 'scripts')) | Out-Null
[IO.File]::WriteAllText((Join-Path $old 'engines/python/windows-runtime.lock.json'),'{"composition_version":"old"}')
[IO.File]::WriteAllText((Join-Path $old 'engines/fiji/runtime.lock.json'),'{"fixed":"old"}')
[IO.File]::WriteAllText((Join-Path $old 'scripts/local_setup.ps1'),'$script:UvVersion = ''0.12.2''')
$files=@()
foreach($name in @('engines/python/windows-runtime.lock.json','engines/fiji/runtime.lock.json','scripts/local_setup.ps1')) {
    $files += @{path=$name;sha256=(Get-FileHash -LiteralPath (Join-Path $old $name)).Hash.ToLowerInvariant()}
}
[IO.File]::WriteAllText((Join-Path $old 'local-release.json'),(@{schema='cytellect-local-release/1';
    version='0.1.0-local.21';source_commit=('a'*40);files=$files}|ConvertTo-Json -Depth 5))
$oldProtected=Test-SetupRuntimeReferenced $root 'runtimes/python-old'
$newUnreferenced=-not(Test-SetupRuntimeReferenced $root 'runtimes/python-new')
$a=New-SetupAttempt $root ('apps/0.1.0-test.1-'+('b'*12))
OwnedApp $root $a
Register-SetupRuntime $root $a 'runtimes/python-new'
[IO.Directory]::CreateDirectory((Join-Path $root 'runtimes/python-new')) | Out-Null
[IO.File]::WriteAllText((Join-Path $root 'runtimes/python-new/partial.bin'),'owned')
$closed=Close-SetupAttempt $root $a
[ordered]@{old_protected=$oldProtected;new_unreferenced=$newUnreferenced;
    new_recovered=(-not(Test-Path -LiteralPath (Join-Path $root 'runtimes/python-new')));
    old_preserved=(Test-Path -LiteralPath $old)} | ConvertTo-Json -Compress
""")
    assert result == {"old_protected": True, "new_unreferenced": True,
                      "new_recovered": True, "old_preserved": True}


def test_completed_receipt_before_journal_commit_preserves_app_and_finalizes_ownership(tmp_path):
    result = run_script(tmp_path, r'''
$root=$env:CYTELLECT_CLEANUP_ROOT
[IO.Directory]::CreateDirectory((Join-Path $root 'setup-cache')) | Out-Null
$a=New-SetupAttempt $root ('apps/0.1.0-test.1-'+('a'*12))
OwnedApp $root $a
$app=Get-SafeChild $root $a.app
[IO.File]::WriteAllText((Join-Path $app 'local-release.json'),(@{schema='cytellect-local-release/1';
    platform='windows-x64';version='0.1.0-test.1';source_commit=('a'*40)}|ConvertTo-Json))
[IO.File]::WriteAllText((Join-Path $app 'setup-complete.json'),(@{app=$app;
    version='0.1.0-test.1';source_commit=('a'*40)}|ConvertTo-Json))
$before=Close-SetupAttempt $root $a
$protected=([IO.File]::Exists((Join-Path $app 'partial.txt')) -and $before.deferred_types -contains 'app_receipt')
Finalize-SetupAttempt $root $a
$saved=@(Read-SetupAttempts $root)[0]
$after=Close-SetupAttempt $root $saved -Committed
[ordered]@{protected=$protected;validated=$saved.validated;
    app_preserved=(Test-Path -LiteralPath $app);owner_removed=(-not(Test-Path -LiteralPath (Join-Path $app '.setup-owner.json')));
    journal_closed=(-not(Test-Path -LiteralPath (Get-SafeChild $root $a.directory)))} | ConvertTo-Json -Compress
''')
    assert result == {"protected": True, "validated": True, "app_preserved": True,
                      "owner_removed": True, "journal_closed": True}


def test_a_partly_removed_runtime_or_app_is_never_taken_for_a_complete_one(tmp_path):
    """Filesystem fixtures only. A locked file stops the rollback midway; what is left is reported as
    unrecovered whether or not another app could refer to it, and is removed once the lock is gone."""
    result = run_script(tmp_path, r"""
$root=$env:CYTELLECT_CLEANUP_ROOT
[IO.Directory]::CreateDirectory((Join-Path $root 'setup-cache')) | Out-Null
$fiji='runtimes/fiji-'+('a'*16)
$a=New-SetupAttempt $root ('apps/0.1.0-test.1-'+('a'*12))
OwnedApp $root $a
Register-SetupRuntime $root $a $fiji
[IO.Directory]::CreateDirectory((Get-SafeChild $root ($fiji+'/jars'))) | Out-Null
[IO.File]::WriteAllText((Get-SafeChild $root ($fiji+'/first.txt')),'removed before the locked file')
$readonly=Get-SafeChild $root ($fiji+'/jars/readonly.jar')
[IO.File]::WriteAllText($readonly,'archive entry without write permission')
[IO.File]::SetAttributes($readonly,[IO.FileAttributes]::ReadOnly)
[IO.File]::WriteAllText((Get-SafeChild $root ($fiji+'/jars/used.jar')),'in use')
$runtimeLock=[IO.File]::Open((Get-SafeChild $root ($fiji+'/jars/used.jar')),'Open','ReadWrite','None')
$first=Close-SetupAttempt $root $a
$pending=@(Read-SetupAttempts $root | Where-Object { $_.id -ceq $a.id })[0]
$partly=(-not [IO.File]::Exists((Get-SafeChild $root ($fiji+'/first.txt'))) -and
    [IO.File]::Exists((Get-SafeChild $root ($fiji+'/jars/used.jar'))))
$unrecovered=(@(Get-UnrecoveredSetupRuntimes $root $pending) -ccontains $fiji)
$ownAppGone=(-not (Test-SetupAppCleanupPending $root $pending))

# Another attempt's app whose removal stops midway cannot be read: it could refer to the runtime,
# so removal of the runtime is deferred. Its reuse is still refused.
$b=New-SetupAttempt $root ('apps/0.1.0-test.2-'+('b'*12))
OwnedApp $root $b
$appLock=[IO.File]::Open((Get-SafeChild $root ($b.app+'/partial.txt')),'Open','ReadWrite','None')
$appClosed=Close-SetupAttempt $root $b
$appPending=[bool](Test-SetupAppCleanupPending $root $b)
$runtimeLock.Dispose()
$second=Close-SetupAttempt $root $pending
$referenced=[bool](Test-SetupRuntimeReferenced $root $fiji)
$stillUnrecovered=(@(Get-UnrecoveredSetupRuntimes $root $pending) -ccontains $fiji)

$appLock.Dispose()
$null=Close-SetupAttempt $root $b
$appRecovered=(-not (Test-Path -LiteralPath (Get-SafeChild $root $b.app)) -and
    -not (Test-SetupAppCleanupPending $root $b))
$third=Close-SetupAttempt $root $pending
$removed=(-not (Test-Path -LiteralPath (Get-SafeChild $root $fiji)) -and
    @(Get-UnrecoveredSetupRuntimes $root $pending).Count -eq 0 -and
    -not (Test-Path -LiteralPath (Get-SafeChild $root $a.directory)))
[IO.Directory]::CreateDirectory((Get-SafeChild $root $fiji)) | Out-Null
$present=@(Get-UnrecoveredSetupRuntimes $root $pending).Count
$pending.validated=$true
[ordered]@{first=@($first.deferred_types);partly=$partly;unrecovered=$unrecovered;own_app_gone=$ownAppGone;
    app_closed=@($appClosed.deferred_types);app_pending=$appPending;
    second=@($second.deferred_types);referenced=$referenced;still_unrecovered=$stillUnrecovered;
    app_recovered=$appRecovered;third=$third.deferred_items;removed=$removed;
    present=$present;validated=@(Get-UnrecoveredSetupRuntimes $root $pending).Count} | ConvertTo-Json -Compress
""")
    assert result == {"first": ["runtime"], "partly": True, "unrecovered": True, "own_app_gone": True,
                      "app_closed": ["app"], "app_pending": True,
                      "second": ["runtime_reference"], "referenced": True, "still_unrecovered": True,
                      "app_recovered": True, "third": 0, "removed": True, "present": 1, "validated": 0}
