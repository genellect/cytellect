[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Msix,
    [Parameter(Mandatory)][string]$Version,
    [Parameter(Mandatory)][string]$Output
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -cne 'true' -or $env:RUNNER_ENVIRONMENT -cne 'github-hosted') {
    throw 'MSIX migration runs only on a disposable GitHub-hosted Windows runner'
}
. (Join-Path (Split-Path -Parent $PSScriptRoot) 'installer-helpers.ps1')
. (Join-Path $PSScriptRoot 'ci-activation.ps1')

$root = Join-Path $env:LOCALAPPDATA 'Cytellect'
$previousTest = Join-Path $env:LOCALAPPDATA 'Cytellect-msix-ci-fresh'
$parent = (Resolve-Path -LiteralPath $env:LOCALAPPDATA).Path
if (((Resolve-Path -LiteralPath $root).Path -ine (Join-Path $parent 'Cytellect')) -or
    ((Get-Item -LiteralPath $root).Attributes -band [IO.FileAttributes]::ReparsePoint) -or
    ([IO.Path]::GetFullPath($previousTest) -ine (Join-Path $parent 'Cytellect-msix-ci-fresh')) -or
    (Test-Path -LiteralPath $previousTest)) {
    throw 'The hosted runner workspace location was not isolated'
}
$marker = Get-Content -LiteralPath (Join-Path $root 'setup-root.json') -Raw | ConvertFrom-Json
if ($marker.product -cne 'cytellect-local' -or $marker.channel -cne 'store') {
    throw 'Expected an isolated workspace created by the preceding MSIX test'
}
Move-Item -LiteralPath $root -Destination $previousTest

$legacyVersion = '0.1.0-local.23'
$legacySha256 = 'c54805cb5afa15912b52b53f44c0442db79b86986be83121fe46676ba94fe2fe'
$file = "Cytellect-Setup-$legacyVersion.exe"
$Installer = Join-Path $env:RUNNER_TEMP $file
Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/genellect/cytellect/releases/download/v$legacyVersion/$file" -OutFile $Installer
if ((Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash.ToLowerInvariant() -cne $legacySha256) {
    throw 'Published EXE checksum mismatch'
}
if ((Invoke-Installer $root -Offline) -ne 0) { throw 'Published EXE did not install on the runner' }

$title = 'MSIX migration from the released Windows installer'
$legacy = Start-Cytellect $root -Expected $legacyVersion
try {
    $session = New-Session
    $body = @{ title = $title } | ConvertTo-Json -Compress
    $workspace = Invoke-RestMethod -NoProxy -Method Post -Uri "$Origin/v1/workspaces" -Headers $Headers -WebSession $session -ContentType 'application/json' -Body $body
} finally { Stop-Cytellect $legacy }
if (-not $workspace.id) { throw 'The EXE did not create a workspace' }

$package = Install-CiMsix $Msix
try {
    $process = Start-CiMsix $package $Version
    try {
        $session = New-Session
        $saved = Invoke-RestMethod -NoProxy -Uri "$Origin/v1/workspaces/$($workspace.id)" -WebSession $session
        if ($saved.id -ne $workspace.id -or $saved.title -cne $title) {
            throw 'The Store package did not reopen the workspace created by the published EXE'
        }
    } finally { Stop-CiMsix $process }
} finally { Uninstall-CiMsix }

@{ schema = 'cytellect-msix-migration/1'; legacy_version = $legacyVersion; legacy_sha256 = $legacySha256
   version = $Version; msix_sha256 = (Get-FileHash -LiteralPath $Msix -Algorithm SHA256).Hash.ToLowerInvariant()
   workspace_reopened = $true } | ConvertTo-Json | Set-Content -LiteralPath $Output -Encoding utf8
