# Builder only: all downloads happen here, never on the researcher's PC.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$SourceZip,
    [Parameter(Mandatory = $true)][string]$Python,
    [Parameter(Mandatory = $true)][string]$WorkRoot,
    [Parameter(Mandatory = $true)][string]$Output,
    [string]$Version = '0.1.0.0',
    [string]$IdentityName = 'Cytellect.Development',
    [string]$Publisher = 'CN=Cytellect Development',
    [string]$PublisherDisplayName = 'Cytellect',
    [string]$MakeAppx = ''
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$Python = (Resolve-Path -LiteralPath $Python).Path
$SourceZip = (Resolve-Path -LiteralPath $SourceZip).Path
$WorkRoot = [IO.Path]::GetFullPath($WorkRoot)
$Output = [IO.Path]::GetFullPath($Output)
if ((Test-Path -LiteralPath $WorkRoot) -or (Test-Path -LiteralPath $Output) -or
    $WorkRoot.StartsWith($repo + '\', [StringComparison]::OrdinalIgnoreCase) -or
    $Output.StartsWith($repo + '\', [StringComparison]::OrdinalIgnoreCase) -or
    $Output.StartsWith($WorkRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'msix_fresh_external_output_required'
}
# Runtime setup must not inherit a developer's service endpoints/keys or Python configuration.
foreach ($key in @([Environment]::GetEnvironmentVariables().Keys)) {
    if ($key -match '^(CYTELLECT_|PYTHON|UV_|PIP_)' -or $key -in @('VIRTUAL_ENV','TCL_LIBRARY','TK_LIBRARY')) {
        [Environment]::SetEnvironmentVariable($key, $null, 'Process')
    }
}
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:UV_NO_CACHE = 'true'
function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw 'msix_build_step_failed' }
}
function Get-SafeChild([string]$Root, [string]$Relative) {
    if ([IO.Path]::IsPathRooted($Relative) -or $Relative.Contains(':') -or $Relative.Contains('\') -or
        @($Relative.Split('/') | Where-Object { $_ -in @('', '.', '..') }).Count) { throw 'msix_unsafe_path' }
    $base = [IO.Path]::GetFullPath($Root).TrimEnd('\','/')
    $path = [IO.Path]::GetFullPath((Join-Path $base $Relative))
    $cursor = $path
    while ($cursor) {
        if ((Test-Path -LiteralPath $cursor) -and
            ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'msix_redirected_path'
        }
        $cursor = Split-Path -Parent $cursor
    }
    if (-not $path.StartsWith($base + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'msix_unsafe_path' }
    return $path
}
function Update-SetupStatus([string]$Phase, [string]$Text) { Write-Host $Phase }
if (-not $MakeAppx) {
    $sdk = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits/10'
    $candidates = @(Get-ChildItem -LiteralPath (Join-Path $sdk 'bin') -Filter makeappx.exe -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.Directory.Name -eq 'x64' } | Sort-Object FullName -Descending)
    $MakeAppx = if ($candidates.Count) { $candidates[0].FullName } else { Join-Path $sdk 'App Certification Kit/makeappx.exe' }
}
if (-not (Test-Path -LiteralPath $MakeAppx -PathType Leaf)) { throw 'msix_windows_sdk_required' }
$null = Get-SafeChild (Split-Path -Parent $WorkRoot) (Split-Path -Leaf $WorkRoot)
$null = Get-SafeChild (Split-Path -Parent $Output) (Split-Path -Leaf $Output)
[IO.Directory]::CreateDirectory($WorkRoot) | Out-Null
$source = Join-Path $WorkRoot 'source'
$stage = Join-Path $WorkRoot 'package'
$buildRuntime = Join-Path $WorkRoot 'builder-runtime'
$helper = Join-Path $PSScriptRoot 'msix_payload.py'
Invoke-Checked $Python @('-B', $helper, 'extract', $SourceZip, $source)
$release = Get-Content -LiteralPath (Join-Path $source 'local-release.json') -Raw | ConvertFrom-Json
$commit = (& git -C $repo rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $release.source_commit -cne $commit -or
    (& git -C $repo status --porcelain --untracked-files=all)) { throw 'msix_exact_clean_source_required' }
[IO.Directory]::CreateDirectory($stage) | Out-Null
Invoke-Checked $Python @('-B', $helper, 'stage', $source, $stage)
. (Join-Path $source 'scripts/windows_runtime.ps1')
$runtime = Initialize-PinnedPythonRuntime $buildRuntime $source
Copy-Item -LiteralPath $runtime.path -Destination (Join-Path $stage 'runtime') -Recurse
$runtimePython = Join-Path $stage 'runtime/python.exe'
$uv = (Get-Command uv -ErrorAction Stop).Source
if ((& $uv --version) -notmatch '^uv 0\.12\.2(?: |$)') { throw 'msix_pinned_uv_required' }
Push-Location $source
try {
    Invoke-Checked $uv @('pip','sync','--python',$runtimePython,'--target',(Join-Path $stage 'runtime/Lib/site-packages'),
        '--require-hashes','--only-binary',':all:','--no-config','--no-python-downloads',
        '--default-index','https://pypi.org/simple','engines/python/windows-requirements.txt')
} finally { Pop-Location }
$env:CYTELLECT_ENGINE_ASSETS = Join-Path $stage 'engines/fiji'
$env:CYTELLECT_CELLPOSE_ASSETS = Join-Path $stage 'engines/cellpose'
Invoke-Checked $runtimePython @('-I','-B', (Join-Path $source 'scripts/fiji_setup.py'), (Join-Path $stage 'fiji'), '--platform','windows-x64')
Invoke-Checked $runtimePython @('-I','-B','-c','import tkinter; t=tkinter.Tk(); t.withdraw(); t.update(); t.destroy()')
Invoke-Checked $runtimePython @('-I','-B','-m','cytellect_analysis.install_check','--fiji',(Join-Path $stage 'fiji'),
    '--scratch',$WorkRoot,'--result',(Join-Path $WorkRoot 'analysis-check.json'))
# CPython computes its stdlib/site paths relative to python.exe; no venv or
# absolute pyvenv.cfg is packaged. Test the final layout after a second move.
$relocated = Join-Path $WorkRoot 'relocated package'
Move-Item -LiteralPath $stage -Destination $relocated
$stage = $relocated
$runtimePython = Join-Path $stage 'runtime/python.exe'
$env:CYTELLECT_ENGINE_ASSETS = Join-Path $stage 'engines/fiji'
Invoke-Checked $runtimePython @('-I','-B','-c','import sys,tkinter,cytellect_api.local; from cytellect_api.local import installed_source_revision; assert installed_source_revision(); t=tkinter.Tk(); t.withdraw(); t.update(); t.destroy()')
Invoke-Checked $runtimePython @('-I','-B','-m','cytellect_analysis.install_check','--fiji',(Join-Path $stage 'fiji'),
    '--scratch',$WorkRoot,'--result',(Join-Path $WorkRoot 'relocated-analysis-check.json'))
Invoke-Checked (Get-Command node -ErrorAction Stop).Source @((Join-Path $repo 'apps/web/scripts/export-msix-icons.mjs'),(Join-Path $stage 'Assets'))
$compiler = Join-Path $env:SystemRoot 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
Invoke-Checked $compiler @('/nologo','/target:winexe','/platform:x64','/optimize+',
    '/reference:System.Windows.Forms.dll',('/out:' + (Join-Path $stage 'Cytellect.exe')),
    (Resolve-Path -LiteralPath (Join-Path $repo 'packaging/windows/Launcher.cs')).Path)
Invoke-Checked $Python @('-B',$helper,'manifest',(Join-Path $repo 'packaging/windows/AppxManifest.xml'),$stage,
    '--name',$IdentityName,'--publisher',$Publisher,'--publisher-name',$PublisherDisplayName,'--version',$Version)
Invoke-Checked $Python @('-B',$helper,'notices',$stage)
Invoke-Checked $Python @('-B',$helper,'inventory',$stage,(Join-Path $WorkRoot 'payload-inventory.json'))
[IO.Directory]::CreateDirectory((Split-Path -Parent $Output)) | Out-Null
# Keep schema validation enabled; never use MakeAppx /nv to hide manifest errors.
Invoke-Checked $MakeAppx @('pack','/d',$stage,'/p',$Output)
$digest = (Get-FileHash -LiteralPath $Output -Algorithm SHA256).Hash.ToLowerInvariant()
[IO.File]::WriteAllText(($Output + '.sha256'), ($digest + '  ' + [IO.Path]::GetFileName($Output) + "`n"), [Text.Encoding]::ASCII)
Write-Host 'Unsigned MSIX prepared. Store identity, signing and installed-copy acceptance are separate gates.'
