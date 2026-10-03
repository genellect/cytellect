# Windows PowerShell 5.1 bootstrap. Downloads occur only during explicit setup.
[CmdletBinding()]
param(
    [string]$SourceRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'Cytellect'),
    [switch]$Console,
    [switch]$NoShortcut,
    [switch]$VerifyOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
# Preserve access to the Windows inbox modules even when a parent PowerShell 7
# process supplies its own PSModulePath to the bootstrap.
$env:PSModulePath = (Join-Path $PSHOME 'Modules') + [IO.Path]::PathSeparator + $env:PSModulePath
$script:UvVersion = '0.12.2'
$script:UvUrl = 'https://github.com/astral-sh/uv/releases/download/0.12.2/uv-x86_64-pc-windows-msvc.zip'
$script:UvSha256 = '01442d8ce5c7124151a73e697c836d252c6da853c18c73206d3cc4c2378a91d2'
$script:PythonVersion = '3.12.15'
$script:PythonBuild = '20261001'
$script:PythonUrl = 'https://github.com/astral-sh/python-build-standalone/releases/download/20261001/cpython-3.12.15%2B20261001-x86_64-pc-windows-msvc-install_only_stripped.tar.gz'
$script:PythonSha256 = '52124cee54126f3f360eaa378288f6f64c402c983a3c14c95eff67f4af986aaa'
$script:Cancelled = $false
$script:Installing = $false
$script:RunningProcess = $null
$script:Phase = 'verify_release'
$script:StatusLabel = $null
$script:LaunchInfo = $null

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

function Update-SetupStatus([string]$Phase, [string]$Text) {
    $script:Phase = $Phase
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
        'services/api/src/cytellect_api/local.py', 'engines/fiji/runtime.lock.json', 'apps/web/out/index.html')) {
        if (-not $seen.Contains($required)) { throw 'release_file_missing' }
    }
    return $manifest
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
    [hashtable]$Environment = @{}, [int]$TimeoutSeconds = 1800, [switch]$UvProcess) {
    $start = [Diagnostics.ProcessStartInfo]::new()
    $start.FileName = $Executable
    $start.Arguments = ($Arguments | ForEach-Object { ConvertTo-NativeArgument $_ }) -join ' '
    $start.WorkingDirectory = $Directory
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    foreach ($key in @($start.EnvironmentVariables.Keys)) {
        if ($key -like 'UV_*' -or $key -like 'PIP_*' -or $key -in @('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV')) {
            $start.EnvironmentVariables.Remove($key)
        }
    }
    foreach ($key in $Environment.Keys) { $start.EnvironmentVariables[$key] = $Environment[$key] }
    $script:RunningProcess = [Diagnostics.Process]::Start($start)
    $stdout = $script:RunningProcess.StandardOutput.ReadToEndAsync()
    $stderr = $script:RunningProcess.StandardError.ReadToEndAsync()
    $watch = [Diagnostics.Stopwatch]::StartNew()
    try {
        while (-not $script:RunningProcess.WaitForExit(100)) {
            if (-not $Console) { [Windows.Forms.Application]::DoEvents() }
            if ($script:Cancelled) { throw 'setup_cancelled' }
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
    if (-not (Test-Path -LiteralPath $archive) -or
        (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $script:UvSha256) {
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

function Install-Cytellect {
    Update-SetupStatus 'verify_release' '配布ファイルを検証しています…'
    $manifest = Get-VerifiedRelease
    if ($VerifyOnly) { return }
    if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {
        throw 'windows_x64_required'
    }
    $root = Initialize-PrivateRoot
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
    $uv = Get-PinnedUv $root
    $environment = @{
        UV_NO_CONFIG = 'true'; UV_PYTHON_INSTALL_DIR = (Get-SafeChild $root 'python')
        UV_CACHE_DIR = (Get-SafeChild $root 'setup-cache/uv'); UV_PYTHON_BIN_DIR = (Get-SafeChild $root 'tools/python-bin')
        UV_PROJECT_ENVIRONMENT = (Get-SafeChild $app '.venv'); UV_DEFAULT_INDEX = 'https://pypi.org/simple'
        UV_PYTHON_DOWNLOADS = 'manual'
    }
    # A one-entry, source-pinned catalog avoids the older uv release's frozen
    # Python catalog. uv verifies this archive hash while installing it.
    $catalog = @{}
    $catalog['cpython-' + $script:PythonVersion + '-windows-x86_64-none'] = @{
        name = 'cpython'; arch = @{ family = 'x86_64'; variant = $null }; os = 'windows'; libc = 'none'
        major = 3; minor = 12; patch = 15; prerelease = ''; variant = $null
        build = $script:PythonBuild; url = $script:PythonUrl; sha256 = $script:PythonSha256
    }
    $catalogPath = Get-SafeChild $root 'setup-cache/python-downloads.json'
    [IO.File]::WriteAllText($catalogPath, ($catalog | ConvertTo-Json -Depth 5))
    $environment['UV_PYTHON_DOWNLOADS_JSON_URL'] = $catalogPath
    Update-SetupStatus 'install_python' '専用のPython環境を準備しています…'
    Invoke-SetupProcess $uv @('python', 'install', $script:PythonVersion, '--no-bin', '--no-registry', '--no-config') $app $environment 900 -UvProcess
    Update-SetupStatus 'install_dependencies' '解析ライブラリを準備しています…'
    Invoke-SetupProcess $uv @('sync', '--locked', '--no-dev', '--python', $script:PythonVersion,
        '--managed-python', '--no-python-downloads', '--no-config') $app $environment -UvProcess
    $python = Get-SafeChild $app '.venv/Scripts/python.exe'
    $pythonw = Get-SafeChild $app '.venv/Scripts/pythonw.exe'
    Update-SetupStatus 'verify_python_gui' '起動・停止ウィンドウを確認しています…'
    Invoke-SetupProcess $python @('-c', 'import sys,tkinter; assert sys.version_info[:3] == (3,12,15); t=tkinter.Tk(); t.withdraw(); t.update(); t.destroy()') $app @{} 60
    if (-not (Test-Path -LiteralPath $pythonw -PathType Leaf)) { throw 'python_gui_unavailable' }
    $lockHash = (Get-FileHash -LiteralPath (Join-Path $app 'engines/fiji/runtime.lock.json')).Hash.ToLowerInvariant()
    $fiji = Get-SafeChild $root ('runtimes/fiji-' + $lockHash.Substring(0, 16))
    if (-not (Test-Path -LiteralPath $fiji)) {
        Update-SetupStatus 'install_fiji' 'Fijiを取得・検証しています。初回は数分かかる場合があります…'
        Invoke-SetupProcess $python @('scripts/fiji_setup.py', $fiji, '--platform', 'windows-x64') $app @{}
    }
    Update-SetupStatus 'verify_fiji' 'Fijiのプラグインとモデルを検証しています…'
    Invoke-SetupProcess $python @('-c', 'import sys; from cytellect_analysis.engine import runtime_info; runtime_info(sys.argv[1])', $fiji) $app @{} 180
    Update-SetupStatus 'check_analysis' '合成画像で検出と計算を確認しています（実験画像の精度評価ではありません）…'
    Invoke-SetupProcess $python @('-m', 'cytellect_analysis.install_check', '--fiji', $fiji,
        '--scratch', (Get-SafeChild $root 'setup-cache'),
        '--result', (Get-SafeChild $root 'setup-cache/installation-check.json')) $app @{} 180
    $data = Get-SafeChild $root 'data'
    [IO.Directory]::CreateDirectory($data) | Out-Null
    $web = Get-SafeChild $app 'apps/web/out'
    $launchArgs = @('-m', 'cytellect_api.local', '--fiji', $fiji, '--data-dir', $data, '--web-dir', $web, '--gui')
    $script:LaunchInfo = @{ executable = $pythonw; arguments = $launchArgs; directory = $app }
    if (-not $NoShortcut) {
        Update-SetupStatus 'create_shortcut' 'Cytellectのショートカットを作成しています…'
        $shell = New-Object -ComObject WScript.Shell
        foreach ($shortcutDirectory in @([Environment]::GetFolderPath('DesktopDirectory'), [Environment]::GetFolderPath('Programs'))) {
            $shortcutPath = Join-Path $shortcutDirectory ('Cytellect ' + $releaseId + '.lnk')
            if (Test-Path -LiteralPath $shortcutPath) { continue }
            $shortcut = $shell.CreateShortcut($shortcutPath)
            $shortcut.TargetPath = $pythonw
            $shortcut.Arguments = ($launchArgs | ForEach-Object { ConvertTo-NativeArgument $_ }) -join ' '
            $shortcut.WorkingDirectory = $app
            $shortcut.Description = 'Cytellect local analysis and control window'
            $shortcut.Save()
        }
    }
    $state = @{ version = $manifest.version; source_commit = $manifest.source_commit; app = $app; fiji = $fiji; python = $script:PythonVersion; python_build = $script:PythonBuild; python_url = $script:PythonUrl; python_sha256 = $script:PythonSha256; uv = $script:UvVersion; uv_sha256 = $script:UvSha256 }
    [IO.File]::WriteAllText((Get-SafeChild $app 'setup-complete.json'), ($state | ConvertTo-Json))
    Update-SetupStatus 'complete' '準備が完了しました。「開く」でCytellectを起動できます。'
}

if ($Console -or $VerifyOnly) {
    try { Install-Cytellect; exit 0 } catch {
        # Fixed stage and code only; never print arbitrary exceptions or paths.
        $code = Get-SetupFailureCode -Exception $_.Exception
        $suffix = if ($null -ne $code) { ' (' + $code + ')' } else { '' }
        Write-Host ('Cytellect setup failed: ' + $script:Phase + $suffix)
        exit 1
    }
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Windows.Forms.Application]::EnableVisualStyles()
$form = [Windows.Forms.Form]::new()
$form.Text = 'Cytellect セットアップ'
$form.Size = [Drawing.Size]::new(620, 425)
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
$description.Text = "解析用Python・Fijiを専用フォルダーに準備します。`r`n既存ソフトやシステムPATHは変更しません。`r`n初回のみ通信と数GBの空き容量が必要です。`r`n研究画像はPC内で保存。24時間期限、停止中の削除は次回起動時です。"
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
$script:StatusLabel = [Windows.Forms.Label]::new()
$script:StatusLabel.Text = '「セットアップ」を押すと準備を開始します。'
$script:StatusLabel.SetBounds(24, 238, 560, 48)
$form.Controls.Add($script:StatusLabel)
$progress = [Windows.Forms.ProgressBar]::new()
$progress.SetBounds(24, 290, 560, 12)
$form.Controls.Add($progress)
$installButton = [Windows.Forms.Button]::new()
$installButton.Text = 'セットアップ'
$installButton.SetBounds(344, 327, 115, 34)
$form.Controls.Add($installButton)
$closeButton = [Windows.Forms.Button]::new()
$closeButton.Text = '閉じる'
$closeButton.SetBounds(469, 327, 115, 34)
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
    $script:Installing = $true
    $script:Cancelled = $false
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
