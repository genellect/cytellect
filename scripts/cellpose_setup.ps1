# Explicit optional Cellpose setup; never run by an image-analysis job.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Python312,
    [string]$SourceRoot = '',
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'Cytellect')
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$env:PSModulePath = (Join-Path $PSHOME 'Modules') + [IO.Path]::PathSeparator + $env:PSModulePath

function Get-CellposeChild([string]$Root, [string]$Relative) {
    if ([IO.Path]::IsPathRooted($Relative) -or $Relative.Contains(':') -or $Relative.Contains('\') -or
        @($Relative.Split('/') | Where-Object { $_ -in @('', '.', '..') }).Count -gt 0) { throw 'cellpose_setup_path_invalid' }
    $base = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
    $child = [IO.Path]::GetFullPath((Join-Path $base $Relative))
    if (-not $child.StartsWith($base + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'cellpose_setup_path_invalid'
    }
    $cursor = $child
    while ($cursor.Length -ge $base.Length) {
        if ((Test-Path -LiteralPath $cursor) -and
            ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'cellpose_setup_redirected_path'
        }
        if ($cursor -eq $base) { break }
        $cursor = Split-Path -Parent $cursor
    }
    return $child
}

function Invoke-CellposeProcess([string]$Executable, [string[]]$Arguments) {
    # Shell-free fixed arguments. Third-party diagnostics are not persisted.
    function Quote([string]$Value) {
        if ($Value -notmatch '[\s"]') { return $Value }
        return '"' + ($Value -replace '(\\*)"', '$1$1\"' -replace '(\\+)$', '$1$1') + '"'
    }
    $start = [Diagnostics.ProcessStartInfo]::new()
    $start.FileName = $Executable
    $start.Arguments = ($Arguments | ForEach-Object { Quote $_ }) -join ' '
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $start.EnvironmentVariables['PYTHONDONTWRITEBYTECODE'] = '1'
    $start.EnvironmentVariables['PYTHONNOUSERSITE'] = '1'
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $start
    try {
        if (-not $process.Start()) { throw 'cellpose_setup_process_failed' }
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        $process.WaitForExit()
        $diagnostics = $stderr.GetAwaiter().GetResult()
        if ($process.ExitCode -ne 0) {
            if ($process.ExitCode -eq 4551 -or $diagnostics -match 'WinError 4551|os error 4551') {
                throw 'windows_application_control_blocked'
            }
            throw 'cellpose_setup_process_failed'
        }
        return $stdout.GetAwaiter().GetResult().Trim()
    } finally { $process.Dispose() }
}

try {
    if (-not $SourceRoot) { $SourceRoot = Split-Path -Parent $PSScriptRoot }
    if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {
        throw 'cellpose_windows_x64_required'
    }
    if (-not (Test-Path -LiteralPath $Python312 -PathType Leaf)) { throw 'cellpose_python312_missing' }
    $Python312 = [IO.Path]::GetFullPath($Python312)
    if ((Get-AuthenticodeSignature -LiteralPath $Python312).Status -ne 'Valid') {
        throw 'cellpose_signed_python_required'
    }
    if ((Invoke-CellposeProcess $Python312 @('-I', '-c', "import sys;print('%d.%d'%sys.version_info[:2])")) -cne '3.12') {
        throw 'cellpose_python312_missing'
    }
    $root = [IO.Path]::GetFullPath($InstallRoot)
    if (-not (Test-Path -LiteralPath (Get-CellposeChild $root 'apps') -PathType Container)) {
        throw 'cellpose_application_setup_required'
    }
    $manifest = Get-Content -LiteralPath (Get-CellposeChild $SourceRoot 'local-release.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($manifest.schema -cne 'cytellect-local-release/1') { throw 'cellpose_release_invalid' }
    $needed = @('scripts/cellpose_setup.py', 'scripts/cellpose_setup.ps1', 'engines/cellpose/runner.py',
        'engines/cellpose/runtime.lock.json', 'engines/cellpose/requirements.lock')
    foreach ($name in $needed) {
        $entry = @($manifest.files | Where-Object { $_.path -ceq $name })
        $path = Get-CellposeChild $SourceRoot $name
        if ($entry.Count -ne 1 -or $entry[0].sha256 -cnotmatch '^[a-f0-9]{64}$' -or
            (Get-Item -LiteralPath $path).Length -ne $entry[0].size -or
            (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $entry[0].sha256) {
            throw 'cellpose_release_hash_mismatch'
        }
    }
    $lock = Get-Content -LiteralPath (Get-CellposeChild $SourceRoot 'engines/cellpose/runtime.lock.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($lock.schema -cne 'cytellect-cellpose-runtime/1' -or $lock.python -cne '3.12' -or
        $lock.requirements_sha256 -cnotmatch '^[a-f0-9]{64}$' -or $lock.model.sha256 -cnotmatch '^[a-f0-9]{64}$') {
        throw 'cellpose_runtime_lock_invalid'
    }
    $uv = Get-CellposeChild $root 'tools/uv-0.12.2/uv.exe'
    $uvArchive = Get-CellposeChild $root 'setup-cache/uv-0.12.2.zip'
    if (-not (Test-Path -LiteralPath $uv -PathType Leaf) -or -not (Test-Path -LiteralPath $uvArchive -PathType Leaf) -or
        (Get-FileHash -LiteralPath $uvArchive -Algorithm SHA256).Hash.ToLowerInvariant() -cne
        '01442d8ce5c7124151a73e697c836d252c6da853c18c73206d3cc4c2378a91d2') {
        throw 'cellpose_application_setup_required'
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead($uvArchive)
    try {
        $entries = @($archive.Entries | Where-Object { $_.Name -ceq 'uv.exe' })
        if ($entries.Count -ne 1) { throw 'cellpose_uv_integrity_failed' }
        $bytes = [IO.MemoryStream]::new()
        $stream = $entries[0].Open()
        try { $stream.CopyTo($bytes) } finally { $stream.Dispose() }
        $expected = [BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash($bytes.ToArray())).Replace('-', '').ToLowerInvariant()
        $bytes.Dispose()
        if ((Get-FileHash -LiteralPath $uv -Algorithm SHA256).Hash.ToLowerInvariant() -cne $expected) {
            throw 'cellpose_uv_integrity_failed'
        }
    } finally { $archive.Dispose() }
    $setupLock = [IO.File]::Open((Get-CellposeChild $root 'setup.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    try {
        $runtime = Get-CellposeChild $root ('runtimes/cellpose-' + $lock.requirements_sha256.Substring(0, 16))
        $models = Get-CellposeChild $root ('models/cellpose-' + $lock.model.sha256.Substring(0, 16))
        Write-Host 'Cellposeの専用環境とモデルを準備しています。初回は通信と保存容量が必要です。'
        Invoke-CellposeProcess $Python312 @('-I', (Get-CellposeChild $SourceRoot 'scripts/cellpose_setup.py'),
            $runtime, '--model-cache', $models, '--python', $Python312, '--uv', $uv) | Out-Null
        $python = Get-CellposeChild $runtime 'Scripts/python.exe'
        if ((Get-AuthenticodeSignature -LiteralPath $python).Status -ne 'Valid') { throw 'cellpose_signed_python_required' }
        Invoke-CellposeProcess $python @('-I', '-c', 'import fastremap,torch,torchvision;from cellpose import models') | Out-Null
        $settings = Get-CellposeChild $root 'settings'
        [IO.Directory]::CreateDirectory($settings) | Out-Null
        $configuration = [ordered]@{schema='cytellect-cellpose-local/1'; python=$python; model_dir=$models}
        $path = Get-CellposeChild $root 'settings/cellpose.json'
        $temporary = Get-CellposeChild $root ('settings/cellpose-' + [Guid]::NewGuid().ToString('N') + '.json')
        [IO.File]::WriteAllText($temporary, ($configuration | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
        if ([IO.File]::Exists($path)) { [IO.File]::Replace($temporary, $path, [NullString]::Value) }
        else { [IO.File]::Move($temporary, $path) }
        Write-Host 'Cellposeの設定を保存しました。Cytellectを終了して開き直してください。'
    } finally { $setupLock.Dispose() }
} catch {
    $code = [string]$_.Exception.Message
    if ($code -eq 'cellpose_python312_missing') {
        Write-Host 'Python 3.12のpython.exeを指定してください。公式Windows版: https://www.python.org/downloads/windows/'
    } elseif ($code -eq 'cellpose_signed_python_required' -or $code -eq 'windows_application_control_blocked') {
        Write-Host 'Windowsのアプリ制御に適合する署名済みPython 3.12が必要です。PC管理者に配布環境の確認を依頼してください。'
    } elseif ($code -eq 'cellpose_application_setup_required') {
        Write-Host '通常のCytellectセットアップを完了してからCellposeを設定してください。'
    } else { Write-Host 'Cellposeの準備が完了しませんでした。配布ファイルと専用環境を確認してください。' }
    exit 1
}
