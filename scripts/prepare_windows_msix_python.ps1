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
# Reuse the EXE's path checks without running its setup entry point.
$tokens = $null
$parseErrors = $null
$setup = [Management.Automation.Language.Parser]::ParseFile(
    (Join-Path $PSScriptRoot 'local_setup.ps1'), [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw 'msix_setup_parse_failed' }
$safeChild = $setup.Find({
    param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq 'Get-SafeChild'
}, $false)
if ($null -eq $safeChild) { throw 'msix_path_validator_missing' }
. ([scriptblock]::Create($safeChild.Extent.Text))
. (Join-Path $Release 'scripts\windows_runtime.ps1')
$script:PinnedPythonInput = $Archive

function Update-SetupStatus([string]$Phase, [string]$Text) { }
function Copy-OfflineArtifact([string]$Sha256, [long]$Bytes, [string]$Target) {
    if (-not (Test-RuntimeFile $script:PinnedPythonInput $Bytes $Sha256)) { throw 'msix_python_archive_mismatch' }
    [IO.File]::Copy($script:PinnedPythonInput, $Target)
    return $true
}

if ((Test-Path -LiteralPath $Output) -or (Test-Path -LiteralPath $Scratch)) { throw 'msix_runtime_target_exists' }
$runtime = Initialize-PinnedPythonRuntime $Scratch $Release
[IO.Directory]::Move($runtime.path, $Output)
