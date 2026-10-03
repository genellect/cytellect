# Release-builder preparation only. Never called by the researcher installer.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Python,
    [Parameter(Mandatory = $true)][string]$CacheRoot,
    [Parameter(Mandatory = $true)][string]$ScratchRoot,
    [Parameter(Mandatory = $true)][string]$Output
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$env:PSModulePath = (Join-Path $PSHOME 'Modules') + [IO.Path]::PathSeparator + $env:PSModulePath
$script:PreparePhase = 'validate_paths'
$script:PrepareProcess = $null
$script:PrepareProcesses = [Collections.Generic.List[object]]::new()
$script:PrepareCancel = $null

function Assert-PreparePath([string]$Path) {
    if (-not [IO.Path]::IsPathRooted($Path)) { throw 'prepare_absolute_path_required' }
    $full = [IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
    if ($full -eq [IO.Path]::GetPathRoot($full).TrimEnd('\', '/')) { throw 'prepare_root_forbidden' }
    $cursor = $full
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw 'prepare_redirected_path'
            }
        }
        $cursor = Split-Path -Parent $cursor
    }
    return $full
}

function Get-PrepareChild([string]$Root, [string]$Name) {
    if ([IO.Path]::IsPathRooted($Name) -or $Name.Contains(':') -or $Name.Contains('\') -or
        @($Name.Split('/') | Where-Object { $_ -in @('', '.', '..') }).Count -gt 0) {
        throw 'prepare_unsafe_child'
    }
    $full = Assert-PreparePath (Join-Path $Root $Name)
    if (-not $full.StartsWith($Root.TrimEnd('\', '/') + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'prepare_unsafe_child'
    }
    return $full
}

function Test-PrepareArtifact([string]$Path, $Specification) {
    $null = Assert-PreparePath $Path
    return ((Test-Path -LiteralPath $Path -PathType Leaf) -and
        (Get-Item -LiteralPath $Path).Length -eq $Specification.bytes -and
        (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() -ceq $Specification.sha256)
}

function Assert-PrepareActive {
    if ($script:PrepareCancel -and (Test-Path -LiteralPath $script:PrepareCancel)) { throw 'prepare_cancelled' }
}

function Get-PrepareArtifact([string]$Root, [string]$Name, $Specification) {
    if ($Specification.sha256 -cnotmatch '^[a-f0-9]{64}$' -or $Specification.bytes -le 0 -or
        $Specification.bytes -gt 64MB -or $Specification.url -cnotmatch
        '^https://www\.python\.org/ftp/python/3\.14\.8/(python-3\.14\.8-amd64\.zip|amd64/tcltk\.msi)$') {
        throw 'prepare_artifact_spec_invalid'
    }
    $target = Get-PrepareChild $Root $Name
    Assert-PrepareActive
    if (Test-PrepareArtifact $target $Specification) { return $target }
    if (Test-Path -LiteralPath $target) { throw 'prepare_cached_artifact_modified' }
    $partial = Get-PrepareChild $Root ($Name + '.partial-' + [Guid]::NewGuid().ToString('N'))
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $client = [Net.WebClient]::new()
    $timer = [Diagnostics.Stopwatch]::StartNew()
    try {
        $transfer = $client.DownloadFileTaskAsync([Uri]$Specification.url, $partial)
        while (-not $transfer.IsCompleted) {
            Assert-PrepareActive
            if ($timer.Elapsed.TotalSeconds -gt 900 -or
                ((Test-Path -LiteralPath $partial) -and (Get-Item -LiteralPath $partial).Length -gt $Specification.bytes)) {
                throw 'prepare_download_limit'
            }
            Start-Sleep -Milliseconds 100
        }
        $transfer.GetAwaiter().GetResult() | Out-Null
        if (-not (Test-PrepareArtifact $partial $Specification)) { throw 'prepare_download_hash_mismatch' }
        [IO.File]::Move($partial, $target)
    } finally {
        $client.CancelAsync()
        $client.Dispose()
    }
    return $target
}

function Assert-PreparePsfSignature([string]$Path) {
    $signature = Get-AuthenticodeSignature -LiteralPath $Path
    if ($signature.Status -ne 'Valid' -or
        $signature.SignerCertificate.Subject -notmatch 'O=Python Software Foundation(?:,|$)') {
        throw 'prepare_psf_signature_invalid'
    }
    return @{ status = 'Valid'; signer_thumbprint = $signature.SignerCertificate.Thumbprint }
}

function Test-PrepareBaseSignatures([string]$Archive, [string]$Scratch, $Specification) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($Archive)
    $result = [Collections.Generic.List[object]]::new()
    try {
        foreach ($launcher in $Specification.launchers) {
            $entry = $zip.GetEntry($launcher.path)
            if ($null -eq $entry -or $entry.Length -le 0 -or $entry.Length -gt 2MB -or
                $launcher.sha256 -cnotmatch '^[a-f0-9]{64}$') { throw 'prepare_base_launcher_invalid' }
            $target = Get-PrepareChild $Scratch ('signature-inputs/' + $launcher.path)
            [IO.Directory]::CreateDirectory((Split-Path -Parent $target)) | Out-Null
            $input = $entry.Open()
            $file = [IO.File]::Open($target, [IO.FileMode]::CreateNew)
            try { $input.CopyTo($file) } finally { $input.Dispose(); $file.Dispose() }
            if ((Get-FileHash -LiteralPath $target).Hash.ToLowerInvariant() -cne $launcher.sha256) {
                throw 'prepare_base_launcher_hash'
            }
            $signature = Assert-PreparePsfSignature $target
            $result.Add(@{ path = $launcher.path; sha256 = $launcher.sha256; signature = $signature })
        }
    } finally { $zip.Dispose() }
    return ,$result.ToArray()
}

function ConvertTo-PrepareArgument([string]$Value) {
    $escaped = [regex]::Replace($Value, '(\\*)"', '${1}${1}\"')
    $escaped = [regex]::Replace($escaped, '(\\+)$', '${1}${1}')
    return '"' + $escaped + '"'
}

function Get-PrepareMsiArguments([string]$Msi, [string]$Target, [string]$Log) {
    foreach ($path in @($Msi, $Target, $Log)) {
        $null = Assert-PreparePath $path
        if ($path -match '[\x00-\x1f"]') { throw 'prepare_msi_argument_invalid' }
    }
    # Windows Installer parses its own command line. Keep fixed switches raw
    # and quote file paths and only the TARGETDIR property's value.
    return '/a "' + $Msi + '" /qn /norestart TARGETDIR="' + $Target + '" /L*V "' + $Log + '"'
}

function Stop-PrepareProcess {
    if ($null -eq $script:PrepareProcess -or $script:PrepareProcess.HasExited) { return }
    # Only this launched process tree. Never target Windows Installer services.
    $stop = [Diagnostics.ProcessStartInfo]::new()
    $stop.FileName = Join-Path $env:SystemRoot 'System32/taskkill.exe'
    $stop.Arguments = '/PID ' + $script:PrepareProcess.Id + ' /T /F'
    $stop.UseShellExecute = $false
    $stop.CreateNoWindow = $true
    $stop.RedirectStandardOutput = $true
    $stop.RedirectStandardError = $true
    $killer = [Diagnostics.Process]::Start($stop)
    try { $killer.WaitForExit(10000) | Out-Null } finally { $killer.Dispose() }
    if (-not $script:PrepareProcess.WaitForExit(10000)) { throw 'prepare_process_stop_unconfirmed' }
}

function Invoke-PrepareProcess([string]$Executable, [string[]]$Arguments, [string]$Directory,
    [ValidateSet('administrative_extraction','data_builder')][string]$Stage, [int]$TimeoutSeconds = 900,
    [string]$NativeMsiArguments = '') {
    Assert-PrepareActive
    $start = [Diagnostics.ProcessStartInfo]::new()
    $start.FileName = $Executable
    if ($Stage -ceq 'administrative_extraction') {
        if (-not $NativeMsiArguments -or $Arguments.Count -ne 0) { throw 'prepare_msi_argument_invalid' }
        $start.Arguments = $NativeMsiArguments
    } else {
        if ($NativeMsiArguments) { throw 'prepare_msi_argument_invalid' }
        $start.Arguments = ($Arguments | ForEach-Object { ConvertTo-PrepareArgument $_ }) -join ' '
    }
    $start.WorkingDirectory = $Directory
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.WindowStyle = [Diagnostics.ProcessWindowStyle]::Hidden
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $start.EnvironmentVariables['PYTHONDONTWRITEBYTECODE'] = '1'
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $record = @{ stage = $Stage; exit_code = $null; stopped = $false; timed_out = $false; cancelled = $false
        started_utc = [DateTime]::UtcNow.ToString('o') }
    try {
        $script:PrepareProcess = [Diagnostics.Process]::Start($start)
        $stdout = $script:PrepareProcess.StandardOutput.ReadToEndAsync()
        $stderr = $script:PrepareProcess.StandardError.ReadToEndAsync()
        while (-not $script:PrepareProcess.WaitForExit(100)) {
            Assert-PrepareActive
            if ($timer.Elapsed.TotalSeconds -gt $TimeoutSeconds) {
                $record.timed_out = $true
                throw 'prepare_process_timeout'
            }
        }
        $record.exit_code = $script:PrepareProcess.ExitCode
        $null = $stdout.GetAwaiter().GetResult()
        $null = $stderr.GetAwaiter().GetResult()
        if ($record.exit_code -ne 0) { throw 'prepare_process_failed' }
    } catch {
        if ($_.Exception.Message -ceq 'prepare_cancelled') { $record.cancelled = $true }
        throw
    } finally {
        try { Stop-PrepareProcess } finally {
            if ($null -ne $script:PrepareProcess) {
                $record.stopped = $script:PrepareProcess.HasExited
                if ($record.stopped -and $null -eq $record.exit_code) { $record.exit_code = $script:PrepareProcess.ExitCode }
                $script:PrepareProcess.Dispose()
                $script:PrepareProcess = $null
            }
            $record.finished_utc = [DateTime]::UtcNow.ToString('o')
            $record.elapsed_ms = $timer.ElapsedMilliseconds
            $script:PrepareProcesses.Add($record)
        }
    }
}

function Get-PrepareScriptZips([string]$Extracted, $Specifications) {
    $pending = [Collections.Generic.Stack[string]]::new()
    $pending.Push($Extracted)
    $found = @{}
    while ($pending.Count -gt 0) {
        foreach ($path in [IO.Directory]::EnumerateFileSystemEntries($pending.Pop())) {
            $item = Get-Item -LiteralPath $path -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'prepare_extracted_reparse' }
            if ($item.PSIsContainer) { $pending.Push($item.FullName); continue }
            foreach ($spec in $Specifications) {
                $name = 'lib' + $spec.id + $spec.version + '.zip'
                if ($item.Name -ceq $name) {
                    if ($found.ContainsKey($spec.id) -or -not (Test-PrepareArtifact $item.FullName $spec)) {
                        throw 'prepare_extracted_zip_mismatch'
                    }
                    $found[$spec.id] = $item.FullName
                }
            }
        }
    }
    if ($found.Count -ne 2 -or -not $found.ContainsKey('tcl') -or -not $found.ContainsKey('tk')) {
        throw 'prepare_extracted_zips_missing'
    }
    return $found
}

function Invoke-WindowsRuntimeDataPreparation {
    $source = Assert-PreparePath (Split-Path -Parent $PSScriptRoot)
    $cache = Assert-PreparePath $CacheRoot
    $scratch = Assert-PreparePath $ScratchRoot
    $output = Assert-PreparePath $Output
    $python = Assert-PreparePath $Python
    foreach ($path in @($cache, $scratch, $output)) {
        if ($path -eq $source -or $path.StartsWith($source + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw 'prepare_output_inside_checkout'
        }
    }
    if ($cache -eq $scratch -or $cache.StartsWith($scratch + '\', [StringComparison]::OrdinalIgnoreCase) -or
        $scratch.StartsWith($cache + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'prepare_roots_overlap' }
    if ((Test-Path -LiteralPath $scratch) -or (Test-Path -LiteralPath $output) -or
        (Test-Path -LiteralPath ($output + '.sha256'))) { throw 'prepare_fresh_outputs_required' }
    if (-not (Test-Path -LiteralPath $python -PathType Leaf) -or [IO.Path]::GetFileName($python) -ine 'python.exe') {
        throw 'prepare_explicit_python_required'
    }
    [IO.Directory]::CreateDirectory($scratch) | Out-Null
    [IO.File]::WriteAllText((Join-Path $scratch 'ownership.json'), '{"schema":"cytellect-runtime-data-preparation/1"}')
    $script:PrepareCancel = Get-PrepareChild $scratch 'cancel.request'
    $receipt = @{ schema = 'cytellect-runtime-data-preparation/1'; passed = $false; phase = $script:PreparePhase
        extraction_performed = $false; consumer_installation = $false; source_changed = $false }
    try {
        $receipt.helper_sha256 = (Get-FileHash -LiteralPath (Get-PrepareChild $source 'scripts/prepare_windows_runtime_data.ps1')).Hash.ToLowerInvariant()
        $lockPath = Get-PrepareChild $source 'engines/python/windows-runtime.lock.json'
        $lock = Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($lock.schema -cne 'cytellect-windows-runtime/1' -or $lock.python.version -cne '3.14.8' -or
            $lock.platform -cne 'windows-x64') { throw 'prepare_lock_invalid' }
        $receipt.lock_sha256 = (Get-FileHash -LiteralPath $lockPath).Hash.ToLowerInvariant()
        $receipt.composition_version = $lock.composition_version
        [IO.Directory]::CreateDirectory($cache) | Out-Null
        $script:PreparePhase = 'verify_inputs'
        $base = Get-PrepareArtifact $cache 'python-3.14.8-amd64.zip' $lock.python
        $msi = Get-PrepareArtifact $cache 'tcltk.msi' $lock.parent_msi
        $receipt.base_sha256 = $lock.python.sha256
        $receipt.parent_msi_sha256 = $lock.parent_msi.sha256
        $receipt.parent_msi_signature = Assert-PreparePsfSignature $msi
        $receipt.base_launcher_signatures = Test-PrepareBaseSignatures $base $scratch $lock.python
        $extracted = Get-PrepareChild $scratch 'extracted'
        [IO.Directory]::CreateDirectory($extracted) | Out-Null
        $script:PreparePhase = 'administrative_extraction'
        $msiexec = Join-Path $env:SystemRoot 'System32/msiexec.exe'
        $log = Get-PrepareChild $scratch 'admin-extraction.private.log'
        $msiArguments = Get-PrepareMsiArguments $msi $extracted $log
        Invoke-PrepareProcess $msiexec @() $scratch 'administrative_extraction' -NativeMsiArguments $msiArguments
        $receipt.extraction_performed = $true
        $scripts = Get-PrepareScriptZips $extracted $lock.script_archives
        $receipt.scripts = @($lock.script_archives | ForEach-Object { @{id=$_.id;sha256=$_.sha256;bytes=$_.bytes} })
        $script:PreparePhase = 'data_builder'
        $builder = Get-PrepareChild $source 'scripts/build_windows_runtime_data.py'
        $receipt.builder_sha256 = (Get-FileHash -LiteralPath $builder).Hash.ToLowerInvariant()
        Invoke-PrepareProcess $python @('-B', $builder, '--parent-msi', $msi, '--base-zip', $base,
            '--tcl-zip', $scripts.tcl, '--tk-zip', $scripts.tk, '--output', $output) $source 'data_builder'
        if (-not (Test-PrepareArtifact $output $lock.data_asset)) { throw 'prepare_output_hash_mismatch' }
        $receipt.data_asset = $lock.data_asset
        $receipt.passed = $true
        $script:PreparePhase = 'complete'
    } catch {
        $code = $_.Exception.Message
        $receipt.error_code = if ($code -cmatch '^prepare_[a-z_]+$') { $code } else { 'prepare_operation_failed' }
        if ($_.Exception -is [ComponentModel.Win32Exception]) { $receipt.native_error_code = $_.Exception.NativeErrorCode }
        throw
    } finally {
        $receipt.phase = $script:PreparePhase
        $receipt.processes = @($script:PrepareProcesses.ToArray())
        $receipt.raw_msi_log = 'private scratch only; never publish'
        [IO.File]::WriteAllText((Get-PrepareChild $scratch 'receipt.json'), ($receipt | ConvertTo-Json -Depth 10),
            [Text.UTF8Encoding]::new($false))
    }
    return @{passed=$true;composition_version=$receipt.composition_version;data_asset=$receipt.data_asset}
}

try { Invoke-WindowsRuntimeDataPreparation | ConvertTo-Json -Depth 8 -Compress }
catch { Write-Output ('Windows runtime data preparation failed: ' + $script:PreparePhase); exit 1 }
