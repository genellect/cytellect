# Shared steps of the installer CI scripts (smoke.ps1, sac-audit.ps1): run the compiled
# installer silently, start the installed launcher, open a local session and uninstall.
# Dot-source it from a script that defines $Installer and $Version; it prints fixed texts only.
$UninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{6F1E0A2C-4C1B-4E57-9B2D-3C7A1F0E9D21}_is1'
# The launcher's port (8765 unless --port is given); Use-Port switches every request to another.
function Use-Port([int]$Port) {
    $script:Port = $Port
    $script:Origin = "http://127.0.0.1:$Port"
    $script:Headers = @{ Origin = $script:Origin; 'X-Cytellect-Request' = '1' }
}
Use-Port 8765

function Step([string]$Name) { Write-Host ('== ' + $Name) }

function Invoke-Installer([string]$Root, [switch]$Offline) {
    # A dead proxy makes any attempted download fail: the installer must not need one.
    $saved = @{ HTTP_PROXY = $env:HTTP_PROXY; HTTPS_PROXY = $env:HTTPS_PROXY; NO_PROXY = $env:NO_PROXY }
    if ($Offline) { $env:HTTP_PROXY = 'http://127.0.0.1:9'; $env:HTTPS_PROXY = 'http://127.0.0.1:9'; $env:NO_PROXY = '' }
    try {
        $watch = [Diagnostics.Stopwatch]::StartNew()
        $process = Start-Process -FilePath $Installer -PassThru -Wait -ArgumentList @(
            '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', ('/DIR="' + $Root + '"'))
        Write-Host ('installer exit {0} after {1:N0} s' -f $process.ExitCode, $watch.Elapsed.TotalSeconds)
        return $process.ExitCode
    } finally {
        foreach ($key in $saved.Keys) { [Environment]::SetEnvironmentVariable($key, $saved[$key]) }
    }
}

function Get-App([string]$Root, [string]$Expected = $Version) {
    $apps = @(Get-ChildItem -LiteralPath (Join-Path $Root 'apps') -Directory |
        Where-Object { $_.Name.StartsWith($Expected + '-') -and (Test-Path -LiteralPath (Join-Path $_.FullName 'setup-complete.json')) })
    if ($apps.Count -ne 1) { throw "expected one completed $Expected application" }
    return Get-Content -LiteralPath (Join-Path $apps[0].FullName 'setup-complete.json') -Raw | ConvertFrom-Json
}

function Start-Cytellect([string]$Root, [string]$Expected = $Version, [switch]$Gui) {
    $marker = Get-App $Root $Expected
    $python = Join-Path $marker.app ('.venv\Scripts\' + $(if ($Gui) { 'pythonw.exe' } else { 'python.exe' }))
    # The same isolation as the shortcut (-E): the user's PYTHON* variables do not apply.
    $arguments = @('-B', '-E', '-m', 'cytellect_api.local', '--data-dir', ('"' + $Root + '\data"'),
        '--web-dir', ('"' + $marker.app + '\apps\web\out"'), '--fiji', ('"' + $marker.fiji + '"'), '--no-browser')
    if ($Gui) { $arguments += '--gui' }
    if ($script:Port -ne 8765) { $arguments += @('--port', "$script:Port") }
    $process = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $marker.app -WindowStyle Hidden -PassThru
    $watch = [Diagnostics.Stopwatch]::StartNew()
    while ($watch.Elapsed.TotalSeconds -lt 240) {
        if ($process.HasExited) { throw ('launcher exited early with ' + $process.ExitCode) }
        try {
            if ((Invoke-WebRequest -UseBasicParsing -NoProxy -TimeoutSec 5 -Uri "$Origin/v1/local/setup").StatusCode -eq 200) {
                Write-Host ('launcher answered after {0:N0} s' -f $watch.Elapsed.TotalSeconds)
                return $process
            }
        } catch { Start-Sleep -Seconds 1 }
    }
    # Fixed facts only: which Python windows are open (an error dialog has the title Cytellect) and the listener.
    Get-Process -Name python, pythonw -ErrorAction SilentlyContinue |
        ForEach-Object { Write-Host ('process {0} window "{1}"' -f $_.ProcessName, $_.MainWindowTitle) }
    Write-Host ("listening on ${script:Port}: " + [bool](Get-NetTCPConnection -LocalPort $script:Port -State Listen -ErrorAction SilentlyContinue))
    # The launcher's dialogs carry fixed texts only (no paths); read them through UI Automation.
    $probe = @'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$condition = New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::NameProperty, 'Cytellect')
foreach ($window in [Windows.Automation.AutomationElement]::RootElement.FindAll([Windows.Automation.TreeScope]::Children, $condition)) {
    foreach ($item in $window.FindAll([Windows.Automation.TreeScope]::Descendants, [Windows.Automation.Condition]::TrueCondition)) {
        if ($item.Current.Name) { 'window text: ' + $item.Current.ControlType.ProgrammaticName + ' ' + $item.Current.Name }
    }
}
'@
    & "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command $probe | ForEach-Object { Write-Host $_ }
    throw 'launcher did not answer'
}

function Stop-Cytellect($Process) {
    if (-not $Process.HasExited) { Stop-Process -Id $Process.Id }
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if (-not (Get-NetTCPConnection -LocalPort $script:Port -State Listen -ErrorAction SilentlyContinue)) { return }
        Start-Sleep -Milliseconds 500
    }
    throw 'launcher kept listening after stop'
}

function New-Session {
    $session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
    Invoke-WebRequest -UseBasicParsing -NoProxy -Method Post -Uri "$Origin/v1/local/session" -Headers $Headers -WebSession $session | Out-Null
    return $session
}

function Invoke-Uninstaller([string]$Root, [string[]]$Extra = @(), [switch]$ExpectRefusal) {
    $uninstaller = Join-Path $Root 'uninstall\unins000.exe'
    if (-not (Test-Path -LiteralPath $uninstaller)) { throw 'uninstaller missing' }
    Start-Process -FilePath $uninstaller -Wait -ArgumentList (@('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART') + $Extra) | Out-Null
    # The uninstaller finishes in a second process; wait for its registry entry to go.
    for ($attempt = 0; $attempt -lt $(if ($ExpectRefusal) { 20 } else { 240 }); $attempt++) {
        if (-not (Test-Path -LiteralPath $UninstallKey)) { break }
        Start-Sleep -Milliseconds 500
    }
    if ($ExpectRefusal) {
        if (-not (Test-Path -LiteralPath $UninstallKey)) { throw 'uninstall removed a running installation' }
        if (-not (Test-Path -LiteralPath (Join-Path $Root 'apps'))) { throw 'uninstall removed files of a running installation' }
        return
    }
    if (Test-Path -LiteralPath $UninstallKey) { throw 'uninstall entry remained' }
    # The second phase removes its own files last.
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if (-not (Test-Path -LiteralPath (Join-Path $Root 'apps')) -and -not (Test-Path -LiteralPath (Join-Path $Root 'uninstall'))) { return }
        Start-Sleep -Milliseconds 500
    }
}
