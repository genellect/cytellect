# Invoked by sac-audit.ps1 on a disposable hosted Windows runner.
function Invoke-CiAppx([string]$Command) {
    # AppX ships with Windows PowerShell. All commands here are constant script bodies.
    $result = & "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -Command $Command
    if ($LASTEXITCODE -ne 0) { throw 'AppX command failed on the runner' }
    return $result
}

function Install-CiMsix([string]$Path) {
    $env:CYTELLECT_CI_MSIX = $Path
    try {
        $json = Invoke-CiAppx @'
$ErrorActionPreference = 'Stop'
Add-AppxPackage -Path $env:CYTELLECT_CI_MSIX
$package = Get-AppxPackage -Name Cytellect.Development
if (-not $package) { throw 'Development identity is missing' }
$package | Select-Object PackageFullName,PackageFamilyName,InstallLocation | ConvertTo-Json -Compress
'@
        return $json | ConvertFrom-Json
    } finally {
        Remove-Item Env:CYTELLECT_CI_MSIX
    }
}

function Uninstall-CiMsix {
    Invoke-CiAppx @'
$ErrorActionPreference = 'Stop'
Get-AppxPackage -Name Cytellect.Development | Remove-AppxPackage
if (Get-AppxPackage -Name Cytellect.Development) { throw 'Development package remains installed' }
'@
}

function Start-CiMsix($Package, [string]$ExpectedVersion) {
    $null = Start-Process explorer.exe -ArgumentList "shell:AppsFolder\$($Package.PackageFamilyName)!Cytellect"
    $watch = [Diagnostics.Stopwatch]::StartNew()
    while ($watch.Elapsed.TotalSeconds -lt 240) {
        $setup = $null
        try { $setup = Invoke-RestMethod -NoProxy -TimeoutSec 5 -Uri "$Origin/v1/local/setup" } catch { }
        if ($null -ne $setup) {
            if ($setup.version -cne $ExpectedVersion -or -not $setup.fiji_configured) {
                throw 'Packaged launcher did not report the expected version and Fiji'
            }
            $listener = Get-NetTCPConnection -LocalPort $script:Port -State Listen
            $process = Get-Process -Id $listener.OwningProcess
            if ($process.Path -ine (Join-Path $Package.InstallLocation 'python\pythonw.exe')) {
                throw 'App activation did not start package Python'
            }
            return $process
        }
        Start-Sleep -Seconds 1
    }
    throw 'Packaged launcher did not answer'
}

function Stop-CiMsix($Process) {
    if (-not $Process.CloseMainWindow() -or -not $Process.WaitForExit(30000)) {
        throw 'Packaged launcher could not shut down cleanly'
    }
    if (Get-NetTCPConnection -LocalPort $script:Port -State Listen -ErrorAction SilentlyContinue) {
        throw 'Packaged launcher kept listening after shutdown'
    }
}
