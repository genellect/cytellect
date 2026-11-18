# Builds the current Windows ZIP and an unsigned MSIX from it on a GitHub-hosted Windows runner.
# Shared by windows-msix.yml (development identity) and windows-store-release.yml (Store identity),
# so the package that is submitted is built exactly like the package that is accepted on pull requests.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Commit,
    # The four-part MSIX version, such as 1.0.4.0.
    [Parameter(Mandatory)][string]$Version,
    # The version written into the Windows ZIP, such as 0.1.0-store.4.
    [Parameter(Mandatory)][string]$ReleaseVersion,
    [Parameter(Mandatory)][string]$Output,
    [Parameter(Mandatory)][string]$Scratch,
    # Partner Center identity JSON. Without it the development identity is used.
    [string]$Identity
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -cne 'true' -or $env:RUNNER_ENVIRONMENT -cne 'github-hosted') {
    throw 'The MSIX build runs only on a GitHub-hosted Windows runner'
}
if ((git rev-parse HEAD).Trim() -cne $Commit) { throw 'Unexpected source commit' }

New-Item -ItemType Directory -Path $Scratch, (Split-Path -Parent $Output) -Force | Out-Null
$python = (Resolve-Path '.venv/Scripts/python.exe').Path
$data = Join-Path $Scratch 'windows-tcltk-9.0.4-data.zip'
$archive = Join-Path $Scratch "Cytellect-$ReleaseVersion-windows-x64.zip"
$wheelDir = Join-Path $Scratch 'wheels'

& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/prepare_windows_runtime_data.ps1 -Python $python -CacheRoot (Join-Path $Scratch 'cache') -ScratchRoot (Join-Path $Scratch 'extraction') -Output $data
if ($LASTEXITCODE -ne 0) { throw 'Pinned runtime data preparation failed' }
& $python -B -m hatchling build -t wheel -d $wheelDir
if ($LASTEXITCODE -ne 0) { throw 'Locked wheel build failed' }
$requirements = Join-Path $Scratch 'requirements.txt'
uv export --locked --no-dev --no-emit-project --no-header --output-file $requirements | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Hashed production dependency export failed' }
$wheels = @(Get-ChildItem -LiteralPath $wheelDir -Filter '*.whl')
if ($wheels.Count -ne 1) { throw 'Expected one project wheel' }
& $python -B scripts/build_local_bundle.py --version $ReleaseVersion --output $archive --runtime-data $data --wheel $wheels[0].FullName --requirements $requirements
if ($LASTEXITCODE -ne 0) { throw 'Windows ZIP build failed' }

$arguments = @('-B', 'scripts/build_windows_msix.py', '--release-zip', $archive, '--commit', $Commit,
    '--version', $Version, '--output', $Output, '--cache', (Join-Path $env:RUNNER_TEMP 'installer-cache'),
    '--pip-python', (Get-Command python).Source)
if ($Identity) { $arguments += @('--identity', $Identity) }
& $python @arguments
if ($LASTEXITCODE -ne 0) { throw 'MSIX build failed' }
