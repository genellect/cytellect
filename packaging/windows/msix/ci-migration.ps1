[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Msix,
    [Parameter(Mandatory)][string]$Version,
    [Parameter(Mandatory)][string]$Checkout,
    [Parameter(Mandatory)][string]$Output
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -cne 'true' -or $env:RUNNER_ENVIRONMENT -cne 'github-hosted') {
    throw 'MSIX migration runs only on a disposable GitHub-hosted Windows runner'
}
[IO.Directory]::CreateDirectory((Split-Path -Parent $Output)) | Out-Null
. (Join-Path (Split-Path -Parent $PSScriptRoot) 'installer-helpers.ps1')
. (Join-Path $PSScriptRoot 'ci-activation.ps1')

$root = Join-Path $env:LOCALAPPDATA 'Cytellect'
$parent = (Resolve-Path -LiteralPath $env:LOCALAPPDATA).Path
if (([IO.Path]::GetFullPath($root) -ine (Join-Path $parent 'Cytellect')) -or
    (Test-Path -LiteralPath $root)) {
    throw 'The migration runner must start without a Cytellect workspace'
}

$legacyVersion = '0.1.0-local.23'
$legacySha256 = 'c54805cb5afa15912b52b53f44c0442db79b86986be83121fe46676ba94fe2fe'
$file = "Cytellect-Setup-$legacyVersion.exe"
$Installer = Join-Path $env:RUNNER_TEMP $file
Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/genellect/cytellect/releases/download/v$legacyVersion/$file" -OutFile $Installer
if ((Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash.ToLowerInvariant() -cne $legacySha256) {
    throw 'Published EXE checksum mismatch'
}
if ((Invoke-Installer $root -Offline) -ne 0) { throw 'Published EXE did not install on the runner' }

function Invoke-PublicDetection($Session, [string]$Title) {
    # The same requests as sac-audit.ps1: a workspace with the registered BBBC013 A01 field,
    # and nucleus detection with Fiji in the worker.
    $body = @{ title = $Title } | ConvertTo-Json -Compress
    $workspace = Invoke-RestMethod -NoProxy -Method Post -Uri "$Origin/v1/workspaces" -Headers $Headers -WebSession $Session -ContentType 'application/json' -Body $body
    $fixtures = Join-Path $Checkout 'fixtures\public\bbbc013'
    $metadata = '{"condition":"BBBC013 A01","experimental_unit":"public-plate","sample":"A01","acquisition_date":"public-acquisition"}'
    $field = Invoke-RestMethod -NoProxy -Method Post -Uri "$Origin/v1/workspaces/$($workspace.id)/fields" -Headers $Headers -WebSession $Session -Form @{
        metadata = $metadata; dapi = Get-Item -LiteralPath (Join-Path $fixtures 'A01-dapi.tif'); gfp = Get-Item -LiteralPath (Join-Path $fixtures 'A01-gfp.tif') }
    $body = @{ recipe = @{ id = 'gfp-nuclear-2d' }; backgrounds = @{ $field.id = @{ polygon = @(@(1, 1), @(4, 1), @(4, 4), @(1, 4)); confirmed = $true } } } | ConvertTo-Json -Depth 6
    $trial = Invoke-RestMethod -NoProxy -Method Post -Uri "$Origin/v1/workspaces/$($workspace.id)/analyses" -Headers $Headers -WebSession $Session -ContentType 'application/json' -Body $body
    $watch = [Diagnostics.Stopwatch]::StartNew()
    while ($true) {
        $job = Invoke-RestMethod -NoProxy -Uri "$Origin/v1/jobs/$($trial.job_id)" -WebSession $Session
        if ($job.state -eq 'succeeded') { break }
        if ($job.state -in @('failed', 'cancelled')) { throw ('job ' + $job.kind + ' ' + $job.state + ' ' + $job.error) }
        if ($watch.Elapsed.TotalSeconds -ge 900) { throw 'job did not finish' }
        Start-Sleep -Seconds 3
    }
    $report = Invoke-RestMethod -NoProxy -Uri "$Origin/v1/revisions/$($trial.revision_id)/measurements" -WebSession $Session
    $nuclei = @($report.cells).Count
    if ($nuclei -lt 100) { throw 'nucleus detection found fewer than 100 nuclei' }
    return @{ workspace = $workspace.id; revision = $trial.revision_id; nuclei = $nuclei }
}

$title = 'MSIX migration from the released Windows installer'
$legacy = Start-Cytellect $root -Expected $legacyVersion
try {
    $saved = Invoke-PublicDetection (New-Session) $title
} finally { Stop-Cytellect $legacy }

$package = Install-CiMsix $Msix
try {
    $process = Start-CiMsix $package $Version
    try {
        $session = New-Session
        $reopened = Invoke-RestMethod -NoProxy -Uri "$Origin/v1/workspaces/$($saved.workspace)" -WebSession $session
        $report = Invoke-RestMethod -NoProxy -Uri "$Origin/v1/revisions/$($saved.revision)/measurements" -WebSession $session
        if ($reopened.id -ne $saved.workspace -or $reopened.title -cne $title -or @($report.cells).Count -ne $saved.nuclei) {
            throw 'The Store package did not reopen the analysis saved by the published EXE'
        }
        # The installer's runtimes and settings are still in the shared folder.
        $repeated = Invoke-PublicDetection $session 'MSIX analysis beside the released Windows installer'
    } finally { Stop-CiMsix $process }
} finally { Uninstall-CiMsix }

@{ schema = 'cytellect-msix-migration/1'; legacy_version = $legacyVersion; legacy_sha256 = $legacySha256
   version = $Version; msix_sha256 = (Get-FileHash -LiteralPath $Msix -Algorithm SHA256).Hash.ToLowerInvariant()
   workspace_reopened = $true; legacy_nuclei = $saved.nuclei; msix_nuclei = $repeated.nuclei } | ConvertTo-Json | Set-Content -LiteralPath $Output -Encoding utf8
