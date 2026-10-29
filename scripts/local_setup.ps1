# Windows PowerShell 5.1 bootstrap. Downloads occur only during explicit setup.
[CmdletBinding()]
param(
    [string]$SourceRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'Cytellect'),
    [switch]$Console,
    [switch]$NoShortcut,
    [switch]$VerifyOnly,
    # Remote GPU service for Cellpose, from the administrator; blank keeps the saved setting.
    [string]$CellposeRemoteUrl = '',
    [string]$CellposeRemoteToken = '',
    [ValidateSet('manual', 'ttl')][string]$WorkspaceRetention = 'manual',
    # The Windows installer's bundled, hash-listed artifacts; setup then never downloads.
    [string]$OfflineRoot = '',
    # Installer progress and outcome: fixed ASCII phase and failure codes only, never paths.
    [string]$StatusFile = '',
    [string]$ResultFile = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
# Preserve access to the Windows inbox modules even when a parent PowerShell 7
# process supplies its own PSModulePath to the bootstrap.
$env:PSModulePath = (Join-Path $PSHOME 'Modules') + [IO.Path]::PathSeparator + $env:PSModulePath
$script:UvVersion = '0.12.2'
$script:UvUrl = 'https://github.com/astral-sh/uv/releases/download/0.12.2/uv-x86_64-pc-windows-msvc.zip'
$script:UvSha256 = '01442d8ce5c7124151a73e697c836d252c6da853c18c73206d3cc4c2378a91d2'
$script:PythonVersion = '3.14.8'
$script:Cancelled = $false
$script:Installing = $false
$script:RunningProcess = $null
$script:Phase = 'verify_release'
$script:StatusLabel = $null
$script:LaunchInfo = $null
$script:Offline = $null

function Get-SafeChild([string]$Root, [string]$Relative) {
    if ([IO.Path]::IsPathRooted($Relative) -or $Relative.Contains(':') -or $Relative.Contains('\') -or
        @($Relative.Split('/') | Where-Object { $_ -in @('', '.', '..') }).Count -gt 0) {
        throw 'unsafe_release_path'
    }
    $base = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
    $child = [IO.Path]::GetFullPath((Join-Path $base $Relative))
    if (-not $child.StartsWith($base + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'unsafe_release_path'
    }
    $cursor = $child
    while ($cursor.Length -ge $base.Length) {
        if (Test-Path -LiteralPath $cursor) {
            if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw 'redirected_install_path'
            }
        }
        if ($cursor -eq $base) { break }
        $cursor = Split-Path -Parent $cursor
    }
    return $child
}

function Write-SetupMarker([string]$Path, [string]$Value) {
    if (-not $Path) { return }
    try { [IO.File]::WriteAllText($Path, $Value, [Text.Encoding]::ASCII) } catch { }
}

function Update-SetupStatus([string]$Phase, [string]$Text) {
    $script:Phase = $Phase
    Write-SetupMarker $StatusFile $Phase
    if ($null -ne $script:StatusLabel) {
        $script:StatusLabel.Text = $Text
        [Windows.Forms.Application]::DoEvents()
    } elseif ($Console) {
        Write-Host $Phase
    }
    if ($script:Cancelled) { throw 'setup_cancelled' }
}

function Get-VerifiedRelease {
    $manifestPath = Get-SafeChild $SourceRoot 'local-release.json'
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($manifest.schema -ne 'cytellect-local-release/1' -or $manifest.platform -ne 'windows-x64' -or
        $manifest.version -notmatch '^\d+\.\d+\.\d+(?:-[a-z0-9.]+)?$' -or
        $manifest.source_commit -notmatch '^[a-f0-9]{40}$' -or @($manifest.files).Count -lt 1) {
        throw 'invalid_release_manifest'
    }
    $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($entry in $manifest.files) {
        if ($entry.sha256 -notmatch '^[a-f0-9]{64}$' -or $entry.size -lt 0 -or -not $seen.Add([string]$entry.path)) {
            throw 'invalid_release_manifest'
        }
        $file = Get-SafeChild $SourceRoot $entry.path
        if (-not (Test-Path -LiteralPath $file -PathType Leaf) -or
            (Get-Item -LiteralPath $file).Length -ne $entry.size -or
            (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) {
            throw 'release_hash_mismatch'
        }
    }
    foreach ($required in @('pyproject.toml', 'uv.lock', 'scripts/fiji_setup.py',
        'services/api/src/cytellect_api/local.py', 'engines/fiji/runtime.lock.json', 'apps/web/out/index.html',
        'scripts/windows_runtime.ps1', 'engines/python/windows-runtime.lock.json',
        'engines/python/windows-install.json', 'engines/python/windows-requirements.txt',
        'engines/python/windows-tcltk-9.0.4-data.zip')) {
        if (-not $seen.Contains($required)) { throw 'release_file_missing' }
    }
    return $manifest
}

function Get-VerifiedOffline {
    # Bind the bundled artifacts to this exact release; each file is listed by digest.
    if (-not $OfflineRoot) { return $null }
    $manifestPath = Get-SafeChild $OfflineRoot 'offline-manifest.json'
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $releaseDigest = (Get-FileHash -LiteralPath (Get-SafeChild $SourceRoot 'local-release.json') -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($manifest.schema -cne 'cytellect-windows-offline/1' -or $manifest.release_manifest_sha256 -cne $releaseDigest -or
        @($manifest.files).Count -lt 1) {
        throw 'invalid_offline_manifest'
    }
    $artifacts = @{}
    $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($entry in $manifest.files) {
        if ($entry.sha256 -cnotmatch '^[a-f0-9]{64}$' -or $entry.bytes -lt 0 -or -not $seen.Add([string]$entry.path) -or
            ([string]$entry.path -cnotmatch '^(?:sha256/[a-f0-9]{64}|wheels/[A-Za-z0-9_.+-]+\.whl)$') -or
            ($entry.path.StartsWith('sha256/') -and $entry.path -cne ('sha256/' + $entry.sha256))) {
            throw 'invalid_offline_manifest'
        }
        $file = Get-SafeChild $OfflineRoot $entry.path
        if (-not (Test-Path -LiteralPath $file -PathType Leaf) -or (Get-Item -LiteralPath $file).Length -ne $entry.bytes -or
            (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -cne $entry.sha256) {
            throw 'offline_hash_mismatch'
        }
        if ($entry.path.StartsWith('sha256/')) { $artifacts[[string]$entry.sha256] = $file }
    }
    # Every bundled file is listed; an unlisted file must not reach the installed environment.
    foreach ($directory in @('sha256', 'wheels')) {
        $folder = Get-SafeChild $OfflineRoot $directory
        if (-not (Test-Path -LiteralPath $folder -PathType Container)) { throw 'invalid_offline_manifest' }
        foreach ($item in @(Get-ChildItem -LiteralPath $folder -Force)) {
            if ($item.PSIsContainer -or -not $seen.Contains($directory + '/' + $item.Name)) { throw 'offline_unlisted_file' }
        }
    }
    return @{ artifacts = $artifacts; sha256 = (Get-SafeChild $OfflineRoot 'sha256'); wheels = (Get-SafeChild $OfflineRoot 'wheels') }
}

function Copy-OfflineArtifact([string]$Sha256, [long]$Bytes, [string]$Target) {
    # $false means online setup. Offline setup never falls back to a download.
    if ($null -eq $script:Offline) { return $false }
    if (-not $script:Offline.artifacts.ContainsKey($Sha256)) { throw 'offline_artifact_missing' }
    $source = $script:Offline.artifacts[$Sha256]
    if ($Bytes -ge 0 -and (Get-Item -LiteralPath $source).Length -ne $Bytes) { throw 'offline_hash_mismatch' }
    if (Test-Path -LiteralPath $Target) { Remove-Item -LiteralPath $Target }
    [IO.File]::Copy($source, $Target)
    if ((Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash.ToLowerInvariant() -cne $Sha256) {
        Remove-Item -LiteralPath $Target
        throw 'offline_hash_mismatch'
    }
    return $true
}

function Initialize-PrivateRoot {
    $rootPath = [IO.Path]::GetFullPath($InstallRoot).TrimEnd('\', '/')
    $sourcePath = [IO.Path]::GetFullPath($SourceRoot).TrimEnd('\', '/')
    if ($rootPath -eq [IO.Path]::GetPathRoot($rootPath).TrimEnd('\', '/') -or $rootPath -eq $sourcePath -or
        $rootPath.StartsWith($sourcePath + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'install_root_must_be_separate'
    }
    $marker = Get-SafeChild $rootPath 'setup-root.json'
    if (Test-Path -LiteralPath $rootPath) {
        if (-not (Test-Path -LiteralPath $marker) -and @(Get-ChildItem -LiteralPath $rootPath -Force).Count -gt 0) {
            throw 'install_directory_not_owned'
        }
        if (Test-Path -LiteralPath $marker) {
            $state = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
            if ($state.product -ne 'cytellect-local') { throw 'install_directory_not_owned' }
        }
    }
    [IO.Directory]::CreateDirectory($rootPath) | Out-Null
    # Read and persist only the DACL. Set-Acl can attempt SACL/owner updates on
    # an existing root and demand SeSecurityPrivilege, which setup must not need.
    $directory = [IO.DirectoryInfo]::new($rootPath)
    $acl = $directory.GetAccessControl([Security.AccessControl.AccessControlSections]::Access)
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($existingRule in @($acl.GetAccessRules($true, $false, [Security.Principal.SecurityIdentifier]))) {
        $acl.RemoveAccessRuleSpecific($existingRule)
    }
    $inherit = [Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit'
    foreach ($sid in @([Security.Principal.WindowsIdentity]::GetCurrent().User,
        [Security.Principal.SecurityIdentifier]::new('S-1-5-18'))) {
        $rule = [Security.AccessControl.FileSystemAccessRule]::new($sid, 'FullControl', $inherit, 'None', 'Allow')
        $acl.AddAccessRule($rule)
    }
    $directory.SetAccessControl($acl)
    if (-not (Test-Path -LiteralPath $marker)) {
        [IO.File]::WriteAllText($marker, '{"product":"cytellect-local","schema":1}')
    }
    return $rootPath
}

function ConvertTo-NativeArgument([string]$Value) {
    # Windows CRT argument escaping; the result is never executed by a shell.
    $escaped = [regex]::Replace($Value, '(\\*)"', '${1}${1}\"')
    $escaped = [regex]::Replace($escaped, '(\\+)$', '${1}${1}')
    return '"' + $escaped + '"'
}

function Stop-SetupProcess {
    if ($null -eq $script:RunningProcess -or $script:RunningProcess.HasExited) { return }
    $stop = [Diagnostics.ProcessStartInfo]::new()
    $stop.FileName = Join-Path $env:SystemRoot 'System32/taskkill.exe'
    $stop.Arguments = '/PID ' + $script:RunningProcess.Id + ' /T /F'
    $stop.UseShellExecute = $false
    $stop.CreateNoWindow = $true
    $stop.RedirectStandardOutput = $true
    $stop.RedirectStandardError = $true
    $killer = [Diagnostics.Process]::Start($stop)
    $killer.WaitForExit(10000) | Out-Null
    $killer.Dispose()
}

function Get-SetupFailureCode([Exception]$Exception = $null, [int]$ExitCode = 0,
    [string]$StandardError = '', [switch]$UvProcess) {
    # Inspect typed native errors and our own fixed marker, never arbitrary messages.
    $failure = $Exception
    while ($null -ne $failure) {
        if (($failure -is [ComponentModel.Win32Exception] -and $failure.NativeErrorCode -eq 4551) -or
            ($failure.Data.Contains('CytellectSetupFailure') -and
             $failure.Data['CytellectSetupFailure'] -ceq 'windows_application_control_blocked')) {
            return 'windows_application_control_blocked'
        }
        $failure = $failure.InnerException
    }
    # uv wraps a child launch failure in its stderr; retain only the fixed code.
    if ($UvProcess -and $ExitCode -ne 0 -and $StandardError -cmatch '\(os error 4551\)') {
        return 'windows_application_control_blocked'
    }
    return $null
}

function Get-SetupFailureText([string]$Code, [string]$Phase) {
    if ($Code -ceq 'windows_application_control_blocked') {
        return 'Windowsの保護機能により実行が拒否されました（4551）。PCの管理者に配布物の確認を依頼してください。'
    }
    return '準備を停止しました (' + $Phase + ')。接続・空き容量を確認して再試行してください。'
}

function Invoke-SetupProcess([string]$Executable, [string[]]$Arguments, [string]$Directory,
    [hashtable]$Environment = @{}, [int]$TimeoutSeconds = 1800, [switch]$UvProcess,
    [switch]$FinishStorageCommit) {
    $start = [Diagnostics.ProcessStartInfo]::new()
    $start.FileName = $Executable
    $start.Arguments = ($Arguments | ForEach-Object { ConvertTo-NativeArgument $_ }) -join ' '
    $start.WorkingDirectory = $Directory
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    foreach ($key in @($start.EnvironmentVariables.Keys)) {
        if ($key -like 'UV_*' -or $key -like 'PIP_*' -or
            $key -in @('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV', 'TCL_LIBRARY', 'TK_LIBRARY')) {
            $start.EnvironmentVariables.Remove($key)
        }
    }
    foreach ($key in $Environment.Keys) { $start.EnvironmentVariables[$key] = $Environment[$key] }
    $start.EnvironmentVariables['PYTHONDONTWRITEBYTECODE'] = '1'
    $script:RunningProcess = [Diagnostics.Process]::Start($start)
    $stdout = $script:RunningProcess.StandardOutput.ReadToEndAsync()
    $stderr = $script:RunningProcess.StandardError.ReadToEndAsync()
    $watch = [Diagnostics.Stopwatch]::StartNew()
    try {
        while (-not $script:RunningProcess.WaitForExit(100)) {
            if (-not $Console) { [Windows.Forms.Application]::DoEvents() }
            if ($script:Cancelled -and -not $FinishStorageCommit) { throw 'setup_cancelled' }
            if ($watch.Elapsed.TotalSeconds -gt $TimeoutSeconds) { throw 'setup_stage_timeout' }
        }
        # Do not persist third-party output, which can include local paths.
        $stdout.GetAwaiter().GetResult() | Out-Null
        $standardError = $stderr.GetAwaiter().GetResult()
        if ($script:RunningProcess.ExitCode -ne 0) {
            $code = Get-SetupFailureCode -ExitCode $script:RunningProcess.ExitCode `
                -StandardError $standardError -UvProcess:$UvProcess
            if ($null -ne $code) {
                $failure = [InvalidOperationException]::new($code)
                $failure.Data['CytellectSetupFailure'] = $code
                throw $failure
            }
            throw 'setup_stage_failed'
        }
    } finally {
        Stop-SetupProcess
        $script:RunningProcess.Dispose()
        $script:RunningProcess = $null
    }
}

function Get-PinnedUv([string]$Root) {
    Update-SetupStatus 'download_uv' 'セットアップツールを取得・検証しています…'
    $cache = Get-SafeChild $Root 'setup-cache'
    [IO.Directory]::CreateDirectory($cache) | Out-Null
    $archive = Get-SafeChild $cache ('uv-' + $script:UvVersion + '.zip')
    if ((-not (Test-Path -LiteralPath $archive) -or
        (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $script:UvSha256) -and
        -not (Copy-OfflineArtifact $script:UvSha256 -1 $archive)) {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $client = [Net.WebClient]::new()
        try {
            $transfer = $client.DownloadFileTaskAsync([Uri]$script:UvUrl, $archive)
            while (-not $transfer.IsCompleted) {
                if (-not $Console) { [Windows.Forms.Application]::DoEvents() }
                if ($script:Cancelled) { $client.CancelAsync(); throw 'setup_cancelled' }
                Start-Sleep -Milliseconds 100
            }
            $transfer.GetAwaiter().GetResult() | Out-Null
        } finally { $client.Dispose() }
    }
    if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $script:UvSha256) {
        throw 'bootstrap_hash_mismatch'
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $uvDirectory = Get-SafeChild $Root ('tools/uv-' + $script:UvVersion)
    [IO.Directory]::CreateDirectory($uvDirectory) | Out-Null
    $zip = [IO.Compression.ZipFile]::OpenRead($archive)
    try {
        $entries = @($zip.Entries | Where-Object { $_.Name -eq 'uv.exe' })
        if ($entries.Count -ne 1) { throw 'bootstrap_archive_invalid' }
        $uv = Get-SafeChild $uvDirectory 'uv.exe'
        $bytes = [IO.MemoryStream]::new()
        $stream = $entries[0].Open()
        try { $stream.CopyTo($bytes) } finally { $stream.Dispose() }
        $expected = [BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash($bytes.ToArray())).Replace('-', '').ToLowerInvariant()
        if (Test-Path -LiteralPath $uv) {
            if ((Get-FileHash -LiteralPath $uv -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
                throw 'installed_bootstrap_modified'
            }
        } else { [IO.File]::WriteAllBytes($uv, $bytes.ToArray()) }
        $bytes.Dispose()
    } finally { $zip.Dispose() }
    return $uv
}

function Test-CellposeRemoteUrl([string]$Url) {
    return $Url -cmatch '^https://[A-Za-z0-9.-]+(:[0-9]{1,5})?(/[A-Za-z0-9._~/-]*)?$'
}

function Test-CellposeRemoteToken([string]$Token) {
    return $Token -cmatch '^[\x21-\x7e]{1,512}$'
}

function Set-CellposeRemote([string]$Root, [string]$Url, [string]$Token) {
    # Cellpose runs on the administrator's GPU service; the PC keeps no Cellpose runtime.
    # Blank input keeps the saved setting, and a blank key keeps the saved key for the same URL.
    $Url = $Url.Trim()
    $Token = $Token.Trim()
    if (-not $Url -and -not $Token) { return }
    if (-not (Test-CellposeRemoteUrl $Url)) { throw 'cellpose_remote_url_invalid' }
    if ($Token -and -not (Test-CellposeRemoteToken $Token)) { throw 'cellpose_remote_token_invalid' }
    $settings = Get-SafeChild $Root 'settings'
    [IO.Directory]::CreateDirectory($settings) | Out-Null
    $path = Get-SafeChild $Root 'settings/cellpose-remote.json'
    if (-not $Token -and [IO.File]::Exists($path)) {
        try {
            $saved = [IO.File]::ReadAllText($path) | ConvertFrom-Json
            if ($saved.url -ceq $Url -and $saved.token -is [string]) { $Token = $saved.token }
        } catch { }
    }
    $value = [ordered]@{ schema = 'cytellect-cellpose-remote/1'; url = $Url }
    if ($Token) { $value.token = $Token }
    $temporary = Get-SafeChild $Root ('settings/cellpose-remote-' + [Guid]::NewGuid().ToString('N') + '.json')
    [IO.File]::WriteAllText($temporary, ($value | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
    if ([IO.File]::Exists($path)) { [IO.File]::Replace($temporary, $path, [NullString]::Value) }
    else { [IO.File]::Move($temporary, $path) }
}

function Get-CellposeRemoteUrl([string]$Root) {
    try {
        $path = Join-Path $Root 'settings\cellpose-remote.json'
        if (-not [IO.File]::Exists($path)) { return '' }
        $saved = [IO.File]::ReadAllText($path) | ConvertFrom-Json
        if ($saved.schema -ceq 'cytellect-cellpose-remote/1' -and (Test-CellposeRemoteUrl $saved.url)) { return $saved.url }
    } catch { }
    return ''
}

function Remove-LegacyVersionShortcuts([string]$Root, [string[]]$Directories) {
    # Releases before 0.1.0-local.15 created one shortcut per version. After a
    # newer version is ready, an older app must not open its migrated database.
    # Remove only those links that this installation created; never fail setup.
    $apps = (Get-SafeChild $Root 'apps') + '\'
    $shell = New-Object -ComObject WScript.Shell
    $removed = 0
    foreach ($directory in $Directories) {
        if (-not $directory -or -not [IO.Directory]::Exists($directory)) { continue }
        foreach ($legacy in [IO.Directory]::GetFiles($directory, 'Cytellect *.lnk')) {
            try {
                if (([IO.File]::GetAttributes($legacy) -band [IO.FileAttributes]::ReparsePoint) -ne 0) { continue }
                $link = $shell.CreateShortcut($legacy)
                if ($link.Description -ceq 'Cytellect local analysis and control window' -and
                    $link.TargetPath.StartsWith($apps, [StringComparison]::OrdinalIgnoreCase)) {
                    [IO.File]::Delete($legacy)
                    $removed++
                }
            } catch { }
        }
    }
    return $removed
}

function Set-WorkspaceRetention([string]$Root, [string]$Requested) {
    # A per-installation choice. Manual retention is irreversible: once research data
    # has been kept, an earlier 24-hour deadline must never delete it on a later start.
    $path = Get-SafeChild $Root 'settings/retention.json'
    $current = 'ttl'
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        try {
            if ((Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json).mode -ceq 'manual') { $current = 'manual' }
        } catch { }
    }
    # The application leaves a permanent marker beside the database once it has kept
    # data. A lost or damaged settings file must not make setup report 24-hour deletion.
    $kept = Test-Path -LiteralPath (Get-SafeChild $Root 'data/.manual-workspace-retention') -PathType Leaf
    if ($current -eq 'manual' -or ($Requested -ne 'manual' -and -not $kept)) { return $current }
    [IO.Directory]::CreateDirectory((Get-SafeChild $Root 'settings')) | Out-Null
    $temporary = Get-SafeChild $Root ('settings/retention-' + [Guid]::NewGuid().ToString('N') + '.json')
    $value = [ordered]@{ schema = 'cytellect-local-retention/1'; mode = 'manual' } | ConvertTo-Json -Compress
    [IO.File]::WriteAllText($temporary, $value, [Text.UTF8Encoding]::new($false))
    if ([IO.File]::Exists($path)) { [IO.File]::Replace($temporary, $path, [NullString]::Value) }
    else { [IO.File]::Move($temporary, $path) }
    return 'manual'
}

function Install-Cytellect {
    $script:LaunchInfo = $null
    Update-SetupStatus 'verify_release' '配布ファイルを検証しています…'
    $manifest = Get-VerifiedRelease
    $script:Offline = Get-VerifiedOffline
    if ($VerifyOnly) { return }
    if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {
        throw 'windows_x64_required'
    }
    $root = Initialize-PrivateRoot
    # Serialize explicit updates; the lock is never a research-data lock.
    $setupLock = [IO.File]::Open((Get-SafeChild $root 'setup.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    $setupSucceeded = $false
    $shortcutChanges = @()
    try {
    Set-CellposeRemote $root $script:CellposeRemoteUrl $script:CellposeRemoteToken
    $releaseId = $manifest.version + '-' + $manifest.source_commit.Substring(0, 12)
    $app = Get-SafeChild $root ('apps/' + $releaseId)
    [IO.Directory]::CreateDirectory($app) | Out-Null
    $installedManifest = Get-SafeChild $app 'local-release.json'
    if (Test-Path -LiteralPath $installedManifest) {
        if ((Get-FileHash -LiteralPath $installedManifest).Hash -ne
            (Get-FileHash -LiteralPath (Join-Path $SourceRoot 'local-release.json')).Hash) {
            throw 'release_install_conflict'
        }
    } elseif (@(Get-ChildItem -LiteralPath $app -Force).Count -gt 0) {
        throw 'release_install_conflict'
    } else {
        Copy-Item -LiteralPath (Join-Path $SourceRoot 'local-release.json') -Destination $installedManifest
    }
    foreach ($entry in $manifest.files) {
        $target = Get-SafeChild $app $entry.path
        if (Test-Path -LiteralPath $target) {
            if ((Get-FileHash -LiteralPath $target).Hash.ToLowerInvariant() -ne $entry.sha256) {
                throw 'installed_release_modified'
            }
        } else {
            [IO.Directory]::CreateDirectory((Split-Path -Parent $target)) | Out-Null
            Copy-Item -LiteralPath (Get-SafeChild $SourceRoot $entry.path) -Destination $target
        }
    }
    $uvRelative = 'tools/uv-' + $script:UvVersion
    $uvWasPresent = Test-Path -LiteralPath (Get-SafeChild $root $uvRelative)
    $uv = Get-PinnedUv $root
    . (Get-SafeChild $app 'scripts/windows_runtime.ps1')
    Update-SetupStatus 'install_python' '専用のPython環境を準備しています…'
    $pythonSpec = Get-Content -LiteralPath (Get-SafeChild $app 'engines/python/windows-runtime.lock.json') -Raw | ConvertFrom-Json
    $pythonRelative = 'runtimes/python-' + $pythonSpec.composition_version
    $pythonWasPresent = Test-Path -LiteralPath (Get-SafeChild $root $pythonRelative)
    $runtime = Initialize-PinnedPythonRuntime $root $app
    $environment = @{
        UV_NO_CONFIG = 'true'; UV_NO_CACHE = 'true'
        UV_DEFAULT_INDEX = 'https://pypi.org/simple'; UV_PYTHON_DOWNLOADS = 'never'
        PYTHONDONTWRITEBYTECODE = '1'
    }
    Assert-SignedPythonVenv $app $runtime -IfPresent
    # A complete, verified environment is reused: a re-run while this version is open
    # must not rewrite the launchers that the running Cytellect is using.
    $venvComplete = $false
    try { Assert-SignedPythonVenv $app $runtime; $venvComplete = $true } catch { }
    if (-not $venvComplete) {
        Invoke-SetupProcess (Get-SafeChild $runtime.path 'python.exe') @('-B', '-m', 'venv', '--without-pip',
            (Get-SafeChild $app '.venv')) $app $environment 180
    }
    Assert-SignedPythonVenv $app $runtime
    $python = Get-SafeChild $app '.venv/Scripts/python.exe'
    $pythonw = Get-SafeChild $app '.venv/Scripts/pythonw.exe'
    $install = Get-Content -LiteralPath (Get-SafeChild $app 'engines/python/windows-install.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($install.schema -cne 'cytellect-windows-install/1' -or
        $install.requirements.path -cne 'engines/python/windows-requirements.txt' -or
        $install.wheel.path -cnotmatch '^wheels/cytellect-[0-9][0-9a-z.+]*-py3-none-any\.whl$') {
        throw 'invalid_python_install_manifest'
    }
    foreach ($input in @($install.wheel, $install.requirements)) {
        Assert-RuntimeDigest $input.sha256
        if (-not (Test-RuntimeFile (Get-SafeChild $app $input.path) $input.bytes $input.sha256)) {
            throw 'python_install_input_modified'
        }
    }
    Update-SetupStatus 'install_dependencies' '解析ライブラリを準備しています…'
    $syncArgs = @('pip', 'sync', '--require-hashes', '--only-binary', ':all:', '--python', $python,
        '--no-managed-python', '--no-python-downloads', '--no-config')
    # Bundled wheels are hash-listed in the same lock; the installer never contacts an index.
    if ($null -ne $script:Offline) { $syncArgs += @('--offline', '--no-index', '--find-links', $script:Offline.wheels) }
    Invoke-SetupProcess $uv ($syncArgs + @($install.requirements.path)) $app $environment -UvProcess
    Assert-SignedPythonVenv $app $runtime
    Invoke-SetupProcess $uv @('pip', 'check', '--python', $python, '--no-config') $app $environment 180 -UvProcess
    Update-SetupStatus 'verify_python_gui' '起動・停止ウィンドウを確認しています…'
    Invoke-SetupProcess $python @('-B', '-c', 'import sys,tkinter; assert sys.version_info[:3] == (3,14,8); t=tkinter.Tk(); t.withdraw(); t.update(); t.destroy()') $app @{} 60
    if (-not (Test-Path -LiteralPath $pythonw -PathType Leaf)) { throw 'python_gui_unavailable' }
    $lockHash = (Get-FileHash -LiteralPath (Join-Path $app 'engines/fiji/runtime.lock.json')).Hash.ToLowerInvariant()
    $fiji = Get-SafeChild $root ('runtimes/fiji-' + $lockHash.Substring(0, 16))
    $fijiWasPresent = Test-Path -LiteralPath $fiji
    if (-not (Test-Path -LiteralPath $fiji)) {
        Update-SetupStatus 'install_fiji' 'Fijiを取得・検証しています。初回は数分かかる場合があります…'
        $fijiArgs = @('-B', 'scripts/fiji_setup.py', $fiji, '--platform', 'windows-x64')
        if ($null -ne $script:Offline) { $fijiArgs += @('--offline-dir', $script:Offline.sha256) }
        Invoke-SetupProcess $python $fijiArgs $app @{}
    }
    Update-SetupStatus 'verify_fiji' 'Fijiのプラグインとモデルを検証しています…'
    Invoke-SetupProcess $python @('-B', '-c', 'import sys; from cytellect_analysis.engine import runtime_info; runtime_info(sys.argv[1])', $fiji) $app @{} 180
    Update-SetupStatus 'check_analysis' '合成画像で検出と計算を確認しています（実験画像の精度評価ではありません）…'
    Invoke-SetupProcess $python @('-B', '-m', 'cytellect_analysis.install_check', '--fiji', $fiji,
        '--scratch', (Get-SafeChild $root 'setup-cache'),
        '--result', (Get-SafeChild $root 'setup-cache/installation-check.json')) $app @{} 180
    Assert-PythonRuntimeInventory $runtime.path $runtime.inventory
    Assert-SignedPythonVenv $app $runtime
    $retention = Set-WorkspaceRetention $root $WorkspaceRetention
    $data = Get-SafeChild $root 'data'
    [IO.Directory]::CreateDirectory($data) | Out-Null
    $web = Get-SafeChild $app 'apps/web/out'
    $launchArgs = @('-B', '-m', 'cytellect_api.local', '--fiji', $fiji, '--data-dir', $data, '--web-dir', $web, '--gui')
    if (-not $NoShortcut) {
        Update-SetupStatus 'create_shortcut' 'Cytellectのショートカットを作成しています…'
        $shell = New-Object -ComObject WScript.Shell
        foreach ($shortcutDirectory in @([Environment]::GetFolderPath('DesktopDirectory'), [Environment]::GetFolderPath('Programs'))) {
            $shortcutPath = Join-Path $shortcutDirectory 'Cytellect.lnk'
            $shortcut = $shell.CreateShortcut($shortcutPath)
            if ((Test-Path -LiteralPath $shortcutPath) -and
                ($shortcut.Description -ne 'Cytellect local analysis and control window' -or
                 -not $shortcut.TargetPath.StartsWith((Get-SafeChild $root 'apps') + '\', [StringComparison]::OrdinalIgnoreCase))) {
                throw 'shortcut_not_owned'
            }
            $stagedPath = Join-Path $shortcutDirectory ('Cytellect-' + [Guid]::NewGuid().ToString('N') + '.lnk')
            $shortcut = $shell.CreateShortcut($stagedPath)
            $shortcut.TargetPath = $pythonw
            $shortcut.Arguments = ($launchArgs | ForEach-Object { ConvertTo-NativeArgument $_ }) -join ' '
            $shortcut.WorkingDirectory = $app
            $shortcut.Description = 'Cytellect local analysis and control window'
            $before = if ([IO.File]::Exists($shortcutPath)) { [IO.File]::ReadAllBytes($shortcutPath) } else { $null }
            $change = [pscustomobject]@{path=[IO.Path]::GetFullPath($shortcutPath); before=$before; after=$null}
            $shortcutChanges += $change
            try {
                # COM may fail after writing part of a link. Publish only its
                # completed temporary file, keeping the old target intact.
                $shortcut.Save()
                $change.after = [IO.File]::ReadAllBytes($stagedPath)
                if ($null -ne $before) {
                    if ([Convert]::ToBase64String([IO.File]::ReadAllBytes($shortcutPath)) -cne [Convert]::ToBase64String($before)) {
                        throw 'shortcut_changed_during_setup'
                    }
                    [IO.File]::Replace($stagedPath, $shortcutPath, [NullString]::Value)
                } else { [IO.File]::Move($stagedPath, $shortcutPath) }
            } finally {
                if ([IO.File]::Exists($stagedPath)) { [IO.File]::Delete($stagedPath) }
            }
        }
    }
    $state = [ordered]@{ version = $manifest.version; source_commit = $manifest.source_commit; app = $app; fiji = $fiji
        python = $script:PythonVersion; python_build = $runtime.specification.composition_version
        python_url = $runtime.specification.python.url; python_sha256 = $runtime.specification.python.sha256
        python_data_sha256 = $runtime.specification.data_asset.sha256; python_inventory = $runtime.receipt
        wheel_sha256 = $install.wheel.sha256; requirements_sha256 = $install.requirements.sha256
        uv = $script:UvVersion; uv_sha256 = $script:UvSha256
        cellpose_remote = [bool](Get-CellposeRemoteUrl $root); workspace_retention = $retention }
    [IO.File]::WriteAllText((Get-SafeChild $app 'setup-complete.json'), ($state | ConvertTo-Json))
    # Checks above must succeed before registering or removing any prior version.
    # Observe cancellation before entering the storage commit. Once collection
    # starts, finish it before honoring close, so late cancellation cannot tear it.
    Update-SetupStatus 'complete' '動作確認が完了しました。保存環境を整理します…'
    Update-SetupStatus 'manage_storage' '旧版の使用状況と保存容量を確認しています…'
    $storageArgs = @('-B', '-m', 'cytellect_api.local_storage', '--root', $root, '--app', $app)
    if (-not $pythonWasPresent) { $storageArgs += @('--created-runtime', $pythonRelative) }
    if (-not $fijiWasPresent) { $storageArgs += @('--created-runtime', ('runtimes/fiji-' + $lockHash.Substring(0, 16))) }
    if (-not $uvWasPresent) { $storageArgs += @('--created-runtime', $uvRelative) }
    $storageText = '準備完了。旧環境の整理は完了していません。保存先の状態を確認してください。'
    try {
        Invoke-SetupProcess $python $storageArgs $app @{} 600 -FinishStorageCommit
        $storage = Get-Content -LiteralPath (Get-SafeChild $root 'setup-storage-result.json') -Raw | ConvertFrom-Json
        $storageText = ('準備完了。アプリ{0}版を保持、{1:N0} MBを解放しました。' -f $storage.retained_apps, ($storage.reclaimed_bytes / 1MB))
        if ($storage.unknown_apps_retained -or $storage.unmanaged_cache_retained -or -not $storage.process_inventory_available) {
            $storageText += ' 使用中または確認できない旧環境は保持しています。'
        }
    } catch {
        # Housekeeping must never invalidate the successfully checked app.
        # The collector preserves unverified trees; do not print private paths.
    }
    $storageText += $(if ($retention -eq 'manual') { ' 作業データは削除操作まで保持します。' }
        else { ' 作業データは最後の操作から24時間で削除されます。' })
    $storageText += $(if ($state.cellpose_remote) { ' Cellposeはクラウド GPU で実行します。' }
        else { ' クラウド GPU が未設定のため、Cellposeは使えません。管理者から接続先と接続キーを受け取り、セットアップで入力してください。' })
    $script:Phase = 'complete'
    if ($null -ne $script:StatusLabel) { $script:StatusLabel.Text = $storageText }
    if ($Console) { Write-Host $storageText }
    if (-not $NoShortcut) {
        try {
            $null = Remove-LegacyVersionShortcuts $root @([Environment]::GetFolderPath('DesktopDirectory'),
                [Environment]::GetFolderPath('Programs'))
        } catch { }
    }
    $script:LaunchInfo = @{ executable = $pythonw; arguments = $launchArgs; directory = $app }
    $setupSucceeded = $true
    } finally {
        if (-not $setupSucceeded) {
            foreach ($change in $shortcutChanges) {
                if (-not [IO.File]::Exists($change.path)) { continue }
                if ((Get-Item -LiteralPath $change.path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
                $actual = [Convert]::ToBase64String([IO.File]::ReadAllBytes($change.path))
                if ($null -ne $change.after -and $actual -ceq [Convert]::ToBase64String($change.after)) {
                    if ($null -ne $change.before) { [IO.File]::WriteAllBytes($change.path, $change.before) }
                    else { [IO.File]::Delete($change.path) }
                }
            }
        }
        $setupLock.Dispose()
    }
}

if ($Console -or $VerifyOnly) {
    try { Install-Cytellect; Write-SetupMarker $ResultFile 'ok'; exit 0 } catch {
        # Fixed stage and code only; never print arbitrary exceptions or paths.
        $code = Get-SetupFailureCode -Exception $_.Exception
        if ($null -eq $code -and $_.Exception.Message -cin @('cellpose_remote_url_invalid', 'cellpose_remote_token_invalid')) {
            $code = $_.Exception.Message
        }
        $suffix = if ($null -ne $code) { ' (' + $code + ')' } else { '' }
        # The installer reads our own fixed failure markers only (for example offline_hash_mismatch).
        $marker = if ($null -ne $code) { $code } elseif ($_.Exception.Message -cmatch '^[a-z0-9_]{3,64}$') {
            $_.Exception.Message } else { 'setup_failed' }
        Write-SetupMarker $ResultFile ('failed ' + $script:Phase + ' ' + $marker)
        Write-Host ('Cytellect setup failed: ' + $script:Phase + $suffix)
        exit 1
    }
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Windows.Forms.Application]::EnableVisualStyles()
$form = [Windows.Forms.Form]::new()
$form.Text = 'Cytellect セットアップ'
$form.Size = [Drawing.Size]::new(620, 620)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.Font = [Drawing.Font]::new('Yu Gothic UI', 10)
$title = [Windows.Forms.Label]::new()
$title.Text = 'Cytellect セットアップ'
$title.SetBounds(24, 22, 560, 32)
$title.Font = [Drawing.Font]::new('Yu Gothic UI', 14, [Drawing.FontStyle]::Bold)
$form.Controls.Add($title)
$description = [Windows.Forms.Label]::new()
$description.Text = "解析用Python・Fijiを専用フォルダーに準備します。`r`n既存ソフトやシステムPATHは変更しません。`r`n初回・依存環境の更新時は通信と空き容量が必要です。`r`n研究画像はPC内に保存。Cellposeの検出時だけ、設定したクラウドGPUへ送ります。"
$description.SetBounds(24, 66, 560, 94)
$form.Controls.Add($description)
$destinationLabel = [Windows.Forms.Label]::new()
$destinationLabel.Text = '保存先'
$destinationLabel.SetBounds(24, 166, 560, 20)
$form.Controls.Add($destinationLabel)
$destinationBox = [Windows.Forms.TextBox]::new()
$destinationBox.Text = $InstallRoot
$destinationBox.ReadOnly = $true
$destinationBox.SetBounds(24, 188, 560, 32)
$form.Controls.Add($destinationBox)
$retentionBox = [Windows.Forms.CheckBox]::new()
$retentionBox.Text = '作業データを自動で削除せず、削除操作まで保持する（推奨）'
$retentionBox.Checked = ($WorkspaceRetention -eq 'manual')
$retentionBox.SetBounds(24, 226, 560, 24)
$form.Controls.Add($retentionBox)
$retentionNote = [Windows.Forms.Label]::new()
$retentionNote.Text = 'オフにすると最後の操作から24時間で削除します。保持を一度選んだ保存先は、24時間削除に戻せません。'
$retentionNote.SetBounds(44, 250, 540, 36)
$form.Controls.Add($retentionNote)
$savedRemoteUrl = Get-CellposeRemoteUrl $InstallRoot
$remoteLabel = [Windows.Forms.Label]::new()
$remoteLabel.Text = $(if ($savedRemoteUrl) { 'Cellpose用クラウドGPUの接続先（設定済み。変更する場合のみ入力）' }
    else { 'Cellpose用クラウドGPUの接続先（管理者から受け取ったもの。任意）' })
$remoteLabel.SetBounds(24, 296, 560, 20)
$form.Controls.Add($remoteLabel)
$remoteUrlBox = [Windows.Forms.TextBox]::new()
$remoteUrlBox.Text = $(if ($CellposeRemoteUrl) { $CellposeRemoteUrl } else { $savedRemoteUrl })
$remoteUrlBox.SetBounds(24, 318, 560, 28)
$form.Controls.Add($remoteUrlBox)
$remoteTokenLabel = [Windows.Forms.Label]::new()
$remoteTokenLabel.Text = $(if ($savedRemoteUrl) { '接続キー（変更する場合のみ入力）' } else { '接続キー' })
$remoteTokenLabel.SetBounds(24, 352, 560, 20)
$form.Controls.Add($remoteTokenLabel)
$remoteTokenBox = [Windows.Forms.TextBox]::new()
$remoteTokenBox.UseSystemPasswordChar = $true
$remoteTokenBox.SetBounds(24, 374, 560, 28)
$form.Controls.Add($remoteTokenBox)
$script:StatusLabel = [Windows.Forms.Label]::new()
$script:StatusLabel.Text = '「セットアップ」を押すと準備を開始します。'
$script:StatusLabel.SetBounds(24, 414, 560, 60)
$form.Controls.Add($script:StatusLabel)
$progress = [Windows.Forms.ProgressBar]::new()
$progress.SetBounds(24, 484, 560, 12)
$form.Controls.Add($progress)
$installButton = [Windows.Forms.Button]::new()
$installButton.Text = 'セットアップ'
$installButton.SetBounds(344, 520, 115, 34)
$form.Controls.Add($installButton)
$closeButton = [Windows.Forms.Button]::new()
$closeButton.Text = '閉じる'
$closeButton.SetBounds(469, 520, 115, 34)
$form.Controls.Add($closeButton)
$installButton.Add_Click({
    if ($null -ne $script:LaunchInfo) {
        $start = [Diagnostics.ProcessStartInfo]::new()
        $start.FileName = $script:LaunchInfo.executable
        $start.Arguments = ($script:LaunchInfo.arguments | ForEach-Object { ConvertTo-NativeArgument $_ }) -join ' '
        $start.WorkingDirectory = $script:LaunchInfo.directory
        $start.UseShellExecute = $false
        $start.CreateNoWindow = $true
        [Diagnostics.Process]::Start($start) | Out-Null
        $form.Close()
        return
    }
    $url = $remoteUrlBox.Text.Trim()
    $key = $remoteTokenBox.Text.Trim()
    if (($url -or $key) -and -not (Test-CellposeRemoteUrl $url)) {
        $script:StatusLabel.Text = 'クラウドGPUの接続先は、管理者から受け取った https:// で始まるURLを入力してください。'
        return
    }
    if ($key -and -not (Test-CellposeRemoteToken $key)) {
        $script:StatusLabel.Text = '接続キーに使えない文字が含まれています。管理者から受け取った接続キーを貼り付け直してください。'
        return
    }
    # A URL already saved and shown again counts as unchanged, keeping its saved key.
    $script:CellposeRemoteUrl = $(if ($url -ceq $savedRemoteUrl -and -not $key) { '' } else { $url })
    $script:CellposeRemoteToken = $key
    $remoteUrlBox.Enabled = $false
    $remoteTokenBox.Enabled = $false
    $script:Installing = $true
    $script:Cancelled = $false
    $script:WorkspaceRetention = if ($retentionBox.Checked) { 'manual' } else { 'ttl' }
    $retentionBox.Enabled = $false
    $installButton.Enabled = $false
    $closeButton.Text = 'キャンセル'
    $progress.Style = 'Marquee'
    $setupFailureCode = $null
    try {
        Install-Cytellect
        $installButton.Text = '開く'
    } catch {
        $setupFailureCode = Get-SetupFailureCode -Exception $_.Exception
        $script:StatusLabel.Text = Get-SetupFailureText -Code $setupFailureCode -Phase $script:Phase
        $installButton.Text = if ($null -ne $setupFailureCode) { 'セットアップ' } else { '再試行' }
    } finally {
        $script:Installing = $false
        $installButton.Enabled = ($null -eq $setupFailureCode)
        $closeButton.Text = '閉じる'
        $progress.Style = 'Blocks'
        if ($null -ne $script:LaunchInfo) { $progress.Value = 100 }
    }
})
$closeButton.Add_Click({ $form.Close() })
$form.Add_FormClosing({
    if ($script:Installing) {
        $_.Cancel = $true
        $script:Cancelled = $true
        $script:StatusLabel.Text = '準備を停止しています。取得済みファイルは再試行時に再利用します。'
    }
})
[Windows.Forms.Application]::Run($form)
