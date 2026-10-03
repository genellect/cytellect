# Functions only. Explicit setup supplies Get-SafeChild and Update-SetupStatus.
# No system Python, PATH, registry, application-control or MSI changes.
Set-StrictMode -Version Latest

function Test-RuntimeFile([string]$Path, [long]$Bytes, [string]$Sha256) {
    return ((Test-Path -LiteralPath $Path -PathType Leaf) -and
        (Get-Item -LiteralPath $Path).Length -eq $Bytes -and
        (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() -ceq $Sha256)
}

function Assert-RuntimeDigest([string]$Sha256) {
    if ($Sha256 -cnotmatch '^[a-f0-9]{64}$') { throw 'invalid_python_runtime_lock' }
}

function Get-RuntimeDigest([byte[]]$Bytes) {
    $hasher = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($hasher.ComputeHash($Bytes)).Replace('-', '').ToLowerInvariant() }
    finally { $hasher.Dispose() }
}

function Get-PythonRuntimeArchive([string]$Root, $Specification) {
    Assert-RuntimeDigest $Specification.sha256
    if ($Specification.url -cnotmatch '^https://www\.python\.org/ftp/python/[0-9.]+/python-[0-9.]+-amd64\.zip$' -or
        $Specification.bytes -le 0 -or $Specification.bytes -gt 100MB) {
        throw 'invalid_python_runtime_lock'
    }
    $cache = Get-SafeChild $Root 'setup-cache'
    [IO.Directory]::CreateDirectory($cache) | Out-Null
    $archive = Get-SafeChild $cache ('python-' + $Specification.sha256 + '.zip')
    if (Test-RuntimeFile $archive $Specification.bytes $Specification.sha256) { return $archive }
    if (Test-Path -LiteralPath $archive) { throw 'python_archive_modified' }
    $partial = Get-SafeChild $cache ('python-' + $Specification.sha256 + '.partial')
    # A partial transfer has no execution role and belongs to this exact digest.
    if (Test-Path -LiteralPath $partial) { Remove-Item -LiteralPath $partial }
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $client = [Net.WebClient]::new()
    $timer = [Diagnostics.Stopwatch]::StartNew()
    try {
        $transfer = $client.DownloadFileTaskAsync([Uri]$Specification.url, $partial)
        while (-not $transfer.IsCompleted) {
            Update-SetupStatus 'download_python' 'Pythonを取得・検証しています…'
            if ($timer.Elapsed.TotalSeconds -gt 900 -or
                ((Test-Path -LiteralPath $partial) -and (Get-Item -LiteralPath $partial).Length -gt $Specification.bytes)) {
                throw 'python_download_limit'
            }
            Start-Sleep -Milliseconds 100
        }
        $transfer.GetAwaiter().GetResult() | Out-Null
        if (-not (Test-RuntimeFile $partial $Specification.bytes $Specification.sha256)) {
            throw 'python_archive_hash_mismatch'
        }
        [IO.File]::Move($partial, $archive)
    } finally {
        $client.CancelAsync()
        $client.Dispose()
    }
    return $archive
}

function Read-PinnedRuntimeZip([string]$Archive, [string]$Destination, [long]$MaximumBytes,
    [int]$ExpectedFiles, [hashtable]$RequiredFiles = @{}, [switch]$DataOnly) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($Archive)
    $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $inventory = [Collections.Generic.List[object]]::new()
    try {
        # Validate the complete directory before creating any output file.
        $expanded = [long]0
        foreach ($entry in $zip.Entries) {
            $name = [string]$entry.FullName
            $null = Get-SafeChild $Destination $name
            foreach ($part in $name.Split('/')) {
                if ($part -match '[\x00-\x1f<>"|?*]' -or $part -match '[. ]$' -or
                    $part -match '^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)') {
                    throw 'python_archive_invalid'
                }
            }
            $kind = ($entry.ExternalAttributes -shr 16) -band 0xF000
            if (-not $entry.Name -or -not $seen.Add($name) -or $kind -notin @(0, 0x8000) -or
                ($entry.ExternalAttributes -band 0x400) -ne 0 -or
                $entry.Length -lt 0 -or $entry.Length -gt $MaximumBytes) { throw 'python_archive_invalid' }
            $expanded += $entry.Length
            if ($expanded -gt $MaximumBytes) { throw 'python_archive_size_exceeded' }
            if ($RequiredFiles.Count -gt 0 -and (-not $RequiredFiles.ContainsKey($name) -or
                $RequiredFiles[$name].bytes -ne $entry.Length)) { throw 'python_data_member_mismatch' }
            if ($DataOnly -and [IO.Path]::GetExtension($name) -match '^\.(exe|dll|pyd|com|scr|msi)$') {
                throw 'python_data_executable_forbidden'
            }
        }
        if ($seen.Count -ne $ExpectedFiles -or
            ($RequiredFiles.Count -gt 0 -and $RequiredFiles.Count -ne $ExpectedFiles)) {
            throw 'python_archive_members_mismatch'
        }
        foreach ($name in $seen) {
            $separator = $name.LastIndexOf('/')
            while ($separator -ge 0) {
                if ($seen.Contains($name.Substring(0, $separator))) { throw 'python_archive_file_directory_collision' }
                $separator = $name.LastIndexOf('/', $separator - 1)
            }
        }
        $index = 0
        foreach ($entry in $zip.Entries) {
            if (($index++ % 40) -eq 0) { Update-SetupStatus 'install_python' '専用のPython環境を検証しています…' }
            $name = [string]$entry.FullName
            $target = Get-SafeChild $Destination $name
            $memory = [IO.MemoryStream]::new()
            $stream = $entry.Open()
            try { $stream.CopyTo($memory); $bytes = $memory.ToArray() }
            finally { $stream.Dispose(); $memory.Dispose() }
            if ($bytes.Length -ne $entry.Length) { throw 'python_archive_member_size' }
            if ($DataOnly -and $bytes.Length -ge 2 -and $bytes[0] -eq 0x4d -and $bytes[1] -eq 0x5a) {
                throw 'python_data_executable_forbidden'
            }
            $digest = Get-RuntimeDigest $bytes
            if ($RequiredFiles.Count -gt 0 -and $RequiredFiles[$name].sha256 -cne $digest) {
                throw 'python_data_member_hash'
            }
            if (Test-Path -LiteralPath $target) {
                if (-not (Test-RuntimeFile $target $bytes.Length $digest)) { throw 'installed_python_modified' }
            } else {
                [IO.Directory]::CreateDirectory((Split-Path -Parent $target)) | Out-Null
                # Finish each member before making it visible. An interrupted
                # transfer can retry without overwriting an accepted file.
                $partial = Get-SafeChild $Destination ($name + '.cytellect-partial')
                if (Test-Path -LiteralPath $partial) { Remove-Item -LiteralPath $partial }
                $output = [IO.File]::Open($partial, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
                try { $output.Write($bytes, 0, $bytes.Length) } finally { $output.Dispose() }
                [IO.File]::Move($partial, $target)
            }
            $inventory.Add(@{ path = $name; bytes = $bytes.Length; sha256 = $digest })
        }
        return ,$inventory.ToArray()
    } finally { $zip.Dispose() }
}

function Assert-PythonRuntimeLaunchers([string]$Runtime, $Specification) {
    foreach ($launcher in $Specification.launchers) {
        Assert-RuntimeDigest $launcher.sha256
        $path = Get-SafeChild $Runtime $launcher.path
        if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or
            (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $launcher.sha256) {
            throw 'python_launcher_hash_mismatch'
        }
        $signature = Get-AuthenticodeSignature -LiteralPath $path
        if ($signature.Status -ne 'Valid' -or
            $signature.SignerCertificate.Subject -notmatch 'O=Python Software Foundation(?:,|$)') {
            throw 'python_launcher_signature_invalid'
        }
    }
}

function Assert-SignedPythonVenv([string]$App, $Runtime, [switch]$IfPresent) {
    $environment = Get-SafeChild $App '.venv'
    $configuration = Get-SafeChild $environment 'pyvenv.cfg'
    if (Test-Path -LiteralPath $configuration) {
        $venvHomeLines = @(Get-Content -LiteralPath $configuration | Where-Object { $_ -match '^home\s*=' })
        if ($venvHomeLines.Count -ne 1) { throw 'python_venv_base_mismatch' }
        $venvHomePath = ($venvHomeLines[0] -split '=', 2)[1].Trim()
        if ($venvHomePath -notmatch '^[A-Za-z]:[\\/]' -or [IO.Path]::GetFullPath($venvHomePath) -ine $Runtime.path) {
            throw 'python_venv_base_mismatch'
        }
    } elseif (-not $IfPresent) { throw 'python_venv_configuration_missing' }
    foreach ($pair in @(@('python.exe', 'venvlauncher.exe'), @('pythonw.exe', 'venvwlauncher.exe'))) {
        $relative = 'Scripts/' + $pair[0]
        $path = Get-SafeChild $environment $relative
        if ($IfPresent -and -not (Test-Path -LiteralPath $path)) { continue }
        $original = @($Runtime.specification.python.launchers | Where-Object { $_.path -ceq ('Lib/venv/scripts/nt/' + $pair[1]) })
        if ($original.Count -ne 1) { throw 'invalid_python_runtime_lock' }
        Assert-PythonRuntimeLaunchers $environment @{ launchers = @(@{ path = $relative; sha256 = $original[0].sha256 }) }
    }
}

function Assert-PythonRuntimeInventory([string]$Runtime, [object[]]$Expected) {
    if ($Expected.Count -eq 0 -or -not (Test-Path -LiteralPath $Runtime -PathType Container)) {
        throw 'invalid_python_runtime_inventory'
    }
    $rootPath = [IO.Path]::GetFullPath($Runtime).TrimEnd('\', '/')
    $rootItem = Get-Item -LiteralPath $rootPath -Force
    if ($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'redirected_install_path' }
    $files = @{}
    $directories = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($entry in $Expected) {
        $null = Get-SafeChild $rootPath $entry.path
        Assert-RuntimeDigest $entry.sha256
        if ($entry.bytes -lt 0 -or $files.ContainsKey($entry.path)) { throw 'invalid_python_runtime_inventory' }
        $files[$entry.path] = $entry
        $separator = $entry.path.LastIndexOf('/')
        while ($separator -ge 0) {
            $null = $directories.Add($entry.path.Substring(0, $separator))
            $separator = $entry.path.LastIndexOf('/', $separator - 1)
        }
    }
    $pending = [Collections.Generic.Stack[string]]::new()
    $pending.Push($rootPath)
    $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    while ($pending.Count -gt 0) {
        $directory = $pending.Pop()
        # Check each entry before descending; never traverse a junction/link.
        foreach ($path in [IO.Directory]::EnumerateFileSystemEntries($directory)) {
            $item = Get-Item -LiteralPath $path -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'redirected_install_path' }
            $relative = $item.FullName.Substring($rootPath.Length + 1).Replace('\', '/')
            if ($item.PSIsContainer) {
                if (-not $directories.Contains($relative)) { throw 'installed_python_unexpected_entry' }
                $pending.Push($item.FullName)
                continue
            }
            if (-not $files.ContainsKey($relative) -or $files[$relative].path -cne $relative -or
                -not $seen.Add($relative)) { throw 'installed_python_unexpected_entry' }
            $record = $files[$relative]
            $safePath = Get-SafeChild $rootPath $relative
            if (-not (Test-RuntimeFile $safePath $record.bytes $record.sha256)) { throw 'installed_python_modified' }
        }
    }
    if ($seen.Count -ne $files.Count) { throw 'installed_python_missing_entry' }
    # No pycache/pth exception. Runtime callers must suppress bytecode writes.
    # Do not remove or repair unrecorded content: refuse the composition.
}

function Initialize-PinnedPythonRuntime([string]$Root, [string]$App) {
    $lockPath = Get-SafeChild $App 'engines/python/windows-runtime.lock.json'
    $lock = Get-Content -LiteralPath $lockPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($lock.schema -cne 'cytellect-windows-runtime/1' -or $lock.platform -cne 'windows-x64' -or
        $lock.composition_version -cnotmatch '^[a-z0-9.-]+$' -or $lock.python.version -cne '3.14.8' -or
        $lock.python.file_count -ne 2203 -or $lock.python.expanded_bytes -ne 117742377) {
        throw 'invalid_python_runtime_lock'
    }
    Assert-RuntimeDigest $lock.data_asset.sha256
    Assert-RuntimeDigest $lock.data_asset.manifest_sha256
    $dataArchive = Get-SafeChild $App $lock.data_asset.path
    if (-not (Test-RuntimeFile $dataArchive $lock.data_asset.bytes $lock.data_asset.sha256)) {
        throw 'python_data_hash_mismatch'
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($dataArchive)
    try {
        $entry = $zip.GetEntry($lock.data_asset.manifest_path)
        if ($null -eq $entry -or $entry.Length -gt 1MB) { throw 'python_data_manifest_invalid' }
        $reader = [IO.MemoryStream]::new()
        $input = $entry.Open()
        try { $input.CopyTo($reader); $manifestBytes = $reader.ToArray() }
        finally { $input.Dispose(); $reader.Dispose() }
        if ((Get-RuntimeDigest $manifestBytes) -cne $lock.data_asset.manifest_sha256) { throw 'python_data_manifest_hash' }
        $manifest = [Text.Encoding]::UTF8.GetString($manifestBytes) | ConvertFrom-Json
    } finally { $zip.Dispose() }
    if ($manifest.schema -cne 'cytellect-windows-runtime-data/1' -or
        $manifest.composition_version -cne $lock.composition_version -or $manifest.python_version -cne $lock.python.version) {
        throw 'python_data_manifest_invalid'
    }
    $required = @{}
    foreach ($file in $manifest.files) {
        Assert-RuntimeDigest $file.sha256
        if ($required.ContainsKey($file.path) -or $file.bytes -lt 0) { throw 'python_data_manifest_invalid' }
        $required[$file.path] = $file
    }
    if ($required.ContainsKey($lock.data_asset.manifest_path)) { throw 'python_data_manifest_invalid' }
    $required[$lock.data_asset.manifest_path] = @{ bytes = $manifestBytes.Length; sha256 = $lock.data_asset.manifest_sha256 }
    $archive = Get-PythonRuntimeArchive $Root $lock.python
    $runtime = Get-SafeChild $Root ('runtimes/python-' + $lock.composition_version)
    [IO.Directory]::CreateDirectory($runtime) | Out-Null
    $original = Read-PinnedRuntimeZip $archive $runtime $lock.python.expanded_bytes $lock.python.file_count
    foreach ($file in $original) {
        if ($required.ContainsKey($file.path)) { throw 'python_data_overwrites_runtime' }
    }
    $added = Read-PinnedRuntimeZip $dataArchive $runtime 10MB $lock.data_asset.member_count $required -DataOnly
    Assert-PythonRuntimeInventory $runtime (@($original) + @($added))
    Assert-PythonRuntimeLaunchers $runtime $lock.python
    $receipt = @{ schema = 'cytellect-installed-python/1'; composition_version = $lock.composition_version
        lock_sha256 = (Get-FileHash -LiteralPath $lockPath -Algorithm SHA256).Hash.ToLowerInvariant()
        python_sha256 = $lock.python.sha256; data_sha256 = $lock.data_asset.sha256; files = @($original) + @($added) }
    $receiptPath = Get-SafeChild $Root ('setup-cache/python-' + $lock.composition_version + '.json')
    [IO.File]::WriteAllText($receiptPath, ($receipt | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
    return @{ path = $runtime; specification = $lock; receipt = $receiptPath; inventory = @($original) + @($added) }
}
