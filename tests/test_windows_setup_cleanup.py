"""Exercise ownership-based rollback against real isolated Windows files."""
import json
import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows setup cleanup")
ROOT = Path(__file__).resolve().parents[1]

SCRIPT = r'''
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$tokens=$null; $errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($env:CYTELLECT_SETUP,[ref]$tokens,[ref]$errors)
if ($errors.Count) { throw 'parse_failed' }
foreach ($name in @('Get-SafeChild','Write-SetupAttempt','Test-SetupAttempt','New-SetupAttempt',
    'Register-SetupRuntime','Remove-SetupTree','Test-SetupRuntimeReferenced','Get-UnrecoveredSetupRuntimes','Test-SetupAppCleanupPending',
    'Close-SetupAttempt','Read-SetupAttempts','Finalize-SetupAttempt','Write-SetupSummary')) {
    $function=$ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name},$true)
    Invoke-Expression $function.Extent.Text
}
function OwnedApp($Root,$Attempt) {
    $app=Get-SafeChild $Root $Attempt.app
    [IO.Directory]::CreateDirectory($app) | Out-Null
    $Attempt.app_owned=$true
    Write-SetupAttempt $Root $Attempt
    [IO.File]::WriteAllText((Get-SafeChild $app '.setup-owner.json'),
        (@{schema='cytellect-setup-app/1';id=$Attempt.id;app=$Attempt.app}|ConvertTo-Json))
    [IO.File]::WriteAllText((Get-SafeChild $app 'partial.txt'),'partial')
}
$root=$env:CYTELLECT_CLEANUP_ROOT
[IO.Directory]::CreateDirectory((Get-SafeChild $root 'setup-cache')) | Out-Null
[IO.Directory]::CreateDirectory((Get-SafeChild $root 'data')) | Out-Null
[IO.File]::WriteAllText((Get-SafeChild $root 'data/study.txt'),'preserve')
$a=New-SetupAttempt $root ('apps/0.1.0-test.1-'+('a'*12))
OwnedApp $root $a
Register-SetupRuntime $root $a 'runtimes/python-test'
[IO.Directory]::CreateDirectory((Get-SafeChild $root 'runtimes/python-test')) | Out-Null
[IO.File]::WriteAllText((Get-SafeChild $root 'runtimes/python-test/partial.txt'),'partial-runtime')
[IO.Directory]::CreateDirectory((Get-SafeChild $root ($a.directory+'/scratch'))) | Out-Null
[IO.File]::WriteAllText((Get-SafeChild $root ($a.directory+'/scratch/temp.txt')),'temporary')
# Reload after an imagined process interruption: ownership must survive in the journal.
$recovered=@(Read-SetupAttempts $root)
$closed=Close-SetupAttempt $root $recovered[0]
$rollback=(-not (Test-Path -LiteralPath (Get-SafeChild $root $a.app)) -and
    -not (Test-Path -LiteralPath (Get-SafeChild $root 'runtimes/python-test')) -and
    -not (Test-Path -LiteralPath (Get-SafeChild $root $a.directory)) -and $closed.reclaimed_bytes -gt 0)

# A folder that predates this attempt is never adopted, even without a receipt.
$existing=Get-SafeChild $root ('apps/0.1.0-test.2-'+('b'*12))
[IO.Directory]::CreateDirectory($existing) | Out-Null
[IO.File]::WriteAllText((Get-SafeChild $existing 'unknown.txt'),'preserve')
$b=New-SetupAttempt $root ('apps/0.1.0-test.2-'+('b'*12))
$null=Close-SetupAttempt $root $b
$existingKept=[IO.File]::Exists((Get-SafeChild $existing 'unknown.txt'))

# A changed owner marker blocks deletion; unrelated pre-existing data stays intact.
$c=New-SetupAttempt $root ('apps/0.1.0-test.3-'+('c'*12))
OwnedApp $root $c
[IO.File]::WriteAllText((Get-SafeChild $root ($c.app+'/.setup-owner.json')),
    (@{schema='cytellect-setup-app/1';id=('0'*32);app=$c.app}|ConvertTo-Json))
$deferred=Close-SetupAttempt $root $c
$tamperedKept=([IO.File]::Exists((Get-SafeChild $root ($c.app+'/partial.txt'))) -and
    $deferred.deferred_items -eq 1 -and (Test-Path -LiteralPath (Get-SafeChild $root $c.directory)))

# An unknown other app could refer to a runtime, so retain the runtime and journal.
$d=New-SetupAttempt $root ('apps/0.1.0-test.4-'+('d'*12))
OwnedApp $root $d
Register-SetupRuntime $root $d 'runtimes/python-shared'
[IO.Directory]::CreateDirectory((Get-SafeChild $root 'runtimes/python-shared')) | Out-Null
$sharedResult=Close-SetupAttempt $root $d
$sharedKept=((Test-Path -LiteralPath (Get-SafeChild $root 'runtimes/python-shared')) -and $sharedResult.deferred_items -gt 0)

# Validate the entire tree before deletion; refuse a junction without touching its target.
$e=New-SetupAttempt $root ('apps/0.1.0-test.5-'+('e'*12))
OwnedApp $root $e
$link=Join-Path (Get-SafeChild $root $e.app) 'redirect'
New-Item -ItemType Junction -Path $link -Target (Get-SafeChild $root 'data') | Out-Null
$redirectResult=Close-SetupAttempt $root $e
$redirectRejected=($redirectResult.deferred_types -contains 'app')
$intact=[IO.File]::Exists((Get-SafeChild $root ($e.app+'/partial.txt')))

# A locked partial file leaves the proof intact, allowing a later cleanup retry.
$f=New-SetupAttempt $root ('apps/0.1.0-test.6-'+('f'*12))
OwnedApp $root $f
$locked=[IO.File]::Open((Get-SafeChild $root ($f.app+'/partial.txt')),'Open','ReadWrite','None')
$lockResult=Close-SetupAttempt $root $f
$lockRejected=($lockResult.deferred_types -contains 'app')
$proofKept=[IO.File]::Exists((Get-SafeChild $root ($f.app+'/.setup-owner.json')))
$locked.Dispose()
$null=Close-SetupAttempt $root $f
$lockRecovered=(-not (Test-Path -LiteralPath (Get-SafeChild $root $f.app)))
[ordered]@{recovered=$recovered.Count;rollback=$rollback;existing=$existingKept;tampered=$tamperedKept;
    shared=$sharedKept;redirect_rejected=$redirectRejected;redirect_intact=$intact;
    lock_rejected=$lockRejected;proof_kept=$proofKept;lock_recovered=$lockRecovered;
    data=([IO.File]::ReadAllText((Get-SafeChild $root 'data/study.txt')) -ceq 'preserve')} | ConvertTo-Json -Compress
'''


def test_interrupted_failure_cleanup_preserves_unowned_shared_and_redirected_files(tmp_path):
    shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    result = subprocess.run([str(shell), "-NoProfile", "-NonInteractive", "-Command", SCRIPT],
                            env={**os.environ, "CYTELLECT_SETUP": str(ROOT / "scripts/local_setup.ps1"),
                                 "CYTELLECT_CLEANUP_ROOT": str(tmp_path / "install")},
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"recovered": 1, "rollback": True, "existing": True,
                                        "tampered": True, "shared": True, "redirect_rejected": True,
                                        "redirect_intact": True, "data": True, "lock_rejected": True,
                                        "proof_kept": True, "lock_recovered": True}
