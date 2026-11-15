# Build host only. Assemble the same pinned, validated Python used by the EXE.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Release,
    [Parameter(Mandatory = $true)][string]$Archive,
    [Parameter(Mandatory = $true)][string]$Scratch,
    [Parameter(Mandatory = $true)][string]$Output
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$env:PSModulePath = (Join-Path $PSHOME 'Modules') + [IO.Path]::PathSeparator + $env:PSModulePath
. (Join-Path $Release 'scripts\windows_runtime.ps1')

function Update-SetupStatus([string]$Phase, [string]$Text) { }
function Copy-OfflineArtifact([string]$Sha256, [long]$Bytes, [string]$Target) {
    if (-not (Test-RuntimeFile $Archive $Bytes $Sha256)) { throw 'msix_python_archive_mismatch' }
    [IO.File]::Copy($Archive, $Target)
    return $true
}

if ((Test-Path -LiteralPath $Output) -or (Test-Path -LiteralPath $Scratch)) { throw 'msix_runtime_target_exists' }
$runtime = Initialize-PinnedPythonRuntime $Scratch $Release
[IO.Directory]::Move($runtime.path, $Output)
