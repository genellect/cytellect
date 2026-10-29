# Windows installer preflight. Read-only: measures this PC and writes fixed ASCII
# key=value lines. The installer stops before any change when a requirement is unmet.
[CmdletBinding()]
param(
    [string]$InstallRoot = '',
    [string]$TempRoot = '',
    # Free space for a first installation, and for an update that reuses Fiji and Python.
    [long]$RequiredInstallMB = 4096,
    [long]$RequiredUpdateMB = 1536,
    # The bundled payload is unpacked to the temporary directory during installation.
    [long]$PayloadMB = 0,
    [string]$ResultFile = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
# Keep the Windows inbox modules (CIM) reachable even under a PowerShell 7 parent.
$env:PSModulePath = (Join-Path $PSHOME 'Modules') + [IO.Path]::PathSeparator + $env:PSModulePath
# Windows 10 1809 or later (Windows 11 reports 10.0.22000+). An 8 GB PC reports
# slightly less than 8192 MiB after hardware reservations.
$script:MinimumBuild = 17763
$script:MinimumMemoryMB = 7168

function Get-CytellectPreflight([Version]$OsVersion, [string]$Architecture, [bool]$Is64BitOs,
    [long]$MemoryMB, [long]$InstallFreeMB, [long]$TempFreeMB, [bool]$SameVolume, [bool]$Update,
    [long]$RequiredInstallMB, [long]$RequiredUpdateMB, [long]$PayloadMB) {
    # Pure decision: callers pass measurements; -1 means the value could not be measured.
    $result = [ordered]@{ code = 'ok'; required_mb = 0; free_mb = $InstallFreeMB; memory_mb = $MemoryMB;
        minimum_memory_mb = $script:MinimumMemoryMB }
    if ($null -eq $OsVersion -or $OsVersion.Major -ne 10 -or $OsVersion.Build -lt $script:MinimumBuild) {
        $result.code = 'os_unsupported'; return $result
    }
    if (-not $Is64BitOs -or $Architecture -cne 'AMD64') {
        $result.code = 'architecture_unsupported'; return $result
    }
    if ($MemoryMB -ge 0 -and $MemoryMB -lt $script:MinimumMemoryMB) {
        $result.code = 'memory_insufficient'; return $result
    }
    $install = $(if ($Update) { $RequiredUpdateMB } else { $RequiredInstallMB })
    if ($SameVolume) {
        $result.required_mb = $install + $PayloadMB
        if ($InstallFreeMB -ge 0 -and $InstallFreeMB -lt $result.required_mb) { $result.code = 'disk_insufficient' }
        return $result
    }
    $result.required_mb = $install
    if ($InstallFreeMB -ge 0 -and $InstallFreeMB -lt $install) { $result.code = 'disk_insufficient'; return $result }
    if ($TempFreeMB -ge 0 -and $TempFreeMB -lt $PayloadMB) {
        $result.code = 'temp_insufficient'; $result.required_mb = $PayloadMB; $result.free_mb = $TempFreeMB
    }
    return $result
}

function Get-FreeMB([string]$Path) {
    try {
        $root = [IO.Path]::GetPathRoot([IO.Path]::GetFullPath($Path))
        return [long]([IO.DriveInfo]::new($root).AvailableFreeSpace / 1MB)
    } catch { return [long]-1 }
}

function Get-MemoryMB {
    try { return [long]((Get-CimInstance -ClassName Win32_ComputerSystem).TotalPhysicalMemory / 1MB) }
    catch { return [long]-1 }
}

function Get-OsVersion {
    try { return [Version](Get-CimInstance -ClassName Win32_OperatingSystem).Version }
    catch { return [Environment]::OSVersion.Version }
}

function Get-NativeArchitecture {
    # A 32-bit host on 64-bit Windows reports the native processor in PROCESSOR_ARCHITEW6432.
    if ($env:PROCESSOR_ARCHITEW6432) { return [string]$env:PROCESSOR_ARCHITEW6432 }
    return [string]$env:PROCESSOR_ARCHITECTURE
}

function Write-PreflightResult($Result) {
    $lines = foreach ($key in $Result.Keys) { $key + '=' + $Result[$key] }
    if ($ResultFile) { [IO.File]::WriteAllLines($ResultFile, [string[]]$lines, [Text.Encoding]::ASCII) }
    else { $lines | ForEach-Object { Write-Output $_ } }
}

if ($MyInvocation.InvocationName -ne '.') {
    try {
        $installPath = [IO.Path]::GetFullPath($InstallRoot)
        $tempPath = [IO.Path]::GetFullPath($(if ($TempRoot) { $TempRoot } else { [IO.Path]::GetTempPath() }))
        $same = [IO.Path]::GetPathRoot($installPath) -ieq [IO.Path]::GetPathRoot($tempPath)
        $update = [IO.File]::Exists([IO.Path]::Combine($installPath, 'setup-root.json'))
        $result = Get-CytellectPreflight (Get-OsVersion) (Get-NativeArchitecture) ([Environment]::Is64BitOperatingSystem) `
            (Get-MemoryMB) (Get-FreeMB $installPath) (Get-FreeMB $tempPath) $same $update `
            $RequiredInstallMB $RequiredUpdateMB $PayloadMB
        Write-PreflightResult $result
        exit $(if ($result.code -ceq 'ok') { 0 } else { 10 })
    } catch {
        # Measurement failures do not block; setup itself still verifies the platform.
        Write-PreflightResult ([ordered]@{ code = 'check_failed' })
        exit 1
    }
}
