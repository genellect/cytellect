# CI acceptance of the compiled installer on a disposable Windows runner (plan §7.1 T1/T4).
# Every installation goes to a scratch folder; only public generated workspaces are used.
# Prints fixed step names and counts only.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Installer,
    [Parameter(Mandatory)][string]$Scratch,
    [Parameter(Mandatory)][string]$Version,
    [Parameter(Mandatory)][string]$Checkout,
    # A published ZIP release to migrate from (I7: 0.1.0-local.20 data directories).
    [string]$PreviousZip = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$UninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{6F1E0A2C-4C1B-4E57-9B2D-3C7A1F0E9D21}_is1'
$Origin = 'http://127.0.0.1:8765'
$Headers = @{ Origin = $Origin; 'X-Cytellect-Request' = '1' }
$Description = 'Cytellect local analysis and control window'
New-Item -ItemType Directory -Path $Scratch -Force | Out-Null

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
    $arguments = @('-B', '-m', 'cytellect_api.local', '--data-dir', ('"' + $Root + '\data"'),
        '--web-dir', ('"' + $marker.app + '\apps\web\out"'), '--fiji', ('"' + $marker.fiji + '"'), '--no-browser')
    if ($Gui) { $arguments += '--gui' }
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
    Write-Host ('listening on 8765: ' + [bool](Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue))
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
        if (-not (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue)) { return }
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

function Assert-Shortcuts([string]$Root, [bool]$Present) {
    $shell = New-Object -ComObject WScript.Shell
    foreach ($folder in @([Environment]::GetFolderPath('DesktopDirectory'), [Environment]::GetFolderPath('Programs'))) {
        $path = Join-Path $folder 'Cytellect.lnk'
        if (-not $Present) { if (Test-Path -LiteralPath $path) { throw 'shortcut remained after uninstall' }; continue }
        if (-not (Test-Path -LiteralPath $path)) { throw 'shortcut missing' }
        $link = $shell.CreateShortcut($path)
        if ($link.Description -cne $Description -or
            -not $link.TargetPath.StartsWith((Join-Path $Root 'apps') + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw 'shortcut does not open this installation'
        }
    }
}

$python = Join-Path $Checkout '.venv\Scripts\python.exe'
$builder = Join-Path $Checkout 'scripts\build_windows_installer.py'

Step 'refuse a destination that holds other files, without changes'
$foreign = Join-Path $Scratch 'foreign'
New-Item -ItemType Directory -Path $foreign | Out-Null
[IO.File]::WriteAllText((Join-Path $foreign 'keep.txt'), 'not Cytellect')
if ((Invoke-Installer $foreign -Offline) -eq 0) { throw 'installer accepted a foreign destination' }
if (@(Get-ChildItem -LiteralPath $foreign -Force).Count -ne 1) { throw 'refused installation changed the destination' }
if (Test-Path -LiteralPath $UninstallKey) { throw 'refused installation registered itself' }

Step 'fresh installation without network'
$root = Join-Path $Scratch 'fresh'
if ((Invoke-Installer $root -Offline) -ne 0) { throw 'fresh installation failed' }
$marker = Get-App $root
if ($marker.workspace_retention -ne 'manual') { throw 'fresh installation did not keep workspaces' }
Assert-Shortcuts $root $true
$entry = Get-ItemProperty -LiteralPath $UninstallKey
if ($entry.DisplayName -cne 'Cytellect' -or $entry.DisplayVersion -cne $Version) { throw 'Windows Apps entry is wrong' }
if (@(Get-ChildItem -LiteralPath (Join-Path $root 'setup-cache') -Filter '*.partial' -ErrorAction SilentlyContinue).Count) {
    throw 'an interrupted download remained'
}
$footprint = (Get-ChildItem -LiteralPath $root -Recurse -File -Force | Measure-Object -Property Length -Sum).Sum
Write-Host ('installed footprint {0:N2} GB' -f ($footprint / 1GB))

Step 'no credentials in the installation (T4)'
& $python -B $builder scan $root
if ($LASTEXITCODE -ne 0) { throw 'credential-shaped content in the installation' }

Step 'the shortcut launcher window starts and answers'
# Checked first and reported at the end, so that one failure still yields the later evidence.
$guiFailure = $null
try { Stop-Cytellect (Start-Cytellect $root -Gui) } catch { $guiFailure = $_.Exception.Message; Write-Host ('GUI launch failed: ' + $guiFailure) }
Get-Process -Name python, pythonw -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

Step 'start, health, session, workspace and update status while offline'
$env:HTTPS_PROXY = 'http://127.0.0.1:9'
$process = Start-Cytellect $root
try {
    $session = New-Session
    $created = Invoke-RestMethod -NoProxy -Method Post -Uri "$Origin/v1/workspaces" -Headers $Headers -WebSession $session -ContentType 'application/json' -Body '{"title":"Installer preservation check"}'
    $update = Invoke-RestMethod -NoProxy -Uri "$Origin/v1/app/update" -WebSession $session
    if ($update.current -cne $Version -or $update.available -or $update.state -cne 'idle') { throw 'unexpected update status' }

    Step 'uninstall refuses while Cytellect runs'
    Invoke-Uninstaller $root -ExpectRefusal

    Step 'installer re-run while Cytellect runs'
    if ((Invoke-Installer $root -Offline) -ne 0) { throw 're-run while running failed' }
    if ((Invoke-WebRequest -UseBasicParsing -NoProxy -Uri "$Origin/v1/local/setup").StatusCode -ne 200) { throw 'running copy stopped' }
} finally { Stop-Cytellect $process; $env:HTTPS_PROXY = $null }

Step 'idempotent re-run'
if ((Invoke-Installer $root -Offline) -ne 0) { throw 're-run failed' }
$null = Get-App $root

Step 'the shortcut launcher window after earlier starts'
try { Stop-Cytellect (Start-Cytellect $root -Gui); Write-Host 'GUI launch after earlier starts passed' }
catch { $guiFailure = ($guiFailure, 'again after earlier starts') -join '; '; Write-Host 'GUI launch after earlier starts failed' }
Get-Process -Name python, pythonw -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

Step 'uninstall keeps research data, reinstall keeps the workspace'
Invoke-Uninstaller $root
foreach ($gone in @('apps', 'runtimes', 'tools', 'uninstall')) {
    if (Test-Path -LiteralPath (Join-Path $root $gone)) { throw "uninstall left $gone" }
}
if (-not (Test-Path -LiteralPath (Join-Path $root 'data\cytellect.sqlite'))) { throw 'uninstall removed research data' }
Assert-Shortcuts $root $false
if ((Invoke-Installer $root -Offline) -ne 0) { throw 'reinstall over kept data failed' }
$process = Start-Cytellect $root
try {
    $kept = Invoke-RestMethod -NoProxy -Uri "$Origin/v1/workspaces/$($created.id)" -Headers $Headers -WebSession (New-Session)
    if ($kept.title -cne 'Installer preservation check') { throw 'workspace lost across uninstall and reinstall' }
} finally { Stop-Cytellect $process }

Step 'uninstall with research data deletion'
Invoke-Uninstaller $root @('/DELETEDATA')
if (@(Get-ChildItem -LiteralPath $root -Force -ErrorAction SilentlyContinue).Count) { throw 'data deletion left files' }

Step 'interrupted installation resumes on the next run'
$root = Join-Path $Scratch 'interrupted'
$saved = $env:HTTPS_PROXY
$env:HTTPS_PROXY = 'http://127.0.0.1:9'
$running = Start-Process -FilePath $Installer -PassThru -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', ('/DIR="' + $root + '"'))
$env:HTTPS_PROXY = $saved
$interrupted = $false
for ($attempt = 0; $attempt -lt 1200; $attempt++) {
    if ($running.HasExited) { break }
    if (@(Get-ChildItem -LiteralPath (Join-Path $root 'apps') -Filter 'pyvenv.cfg' -Recurse -ErrorAction SilentlyContinue).Count) {
        & "$env:SystemRoot\System32\taskkill.exe" /PID $running.Id /T /F | Out-Null
        $interrupted = $true
        break
    }
    Start-Sleep -Milliseconds 500
}
if (-not $interrupted) { throw 'installation could not be interrupted at the dependency stage' }
Start-Sleep -Seconds 5
# Stop any setup child that outlived the killed installer (as when a PC loses power).
Get-CimInstance -ClassName Win32_Process | Where-Object {
    $_.Name -in @('powershell.exe', 'python.exe', 'pythonw.exe', 'uv.exe') -and $_.CommandLine -and
    $_.CommandLine.IndexOf($root, [StringComparison]::OrdinalIgnoreCase) -ge 0 } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
if ((Invoke-Installer $root -Offline) -ne 0) { throw 'resumed installation failed' }
$null = Get-App $root
Invoke-Uninstaller $root @('/DELETEDATA')

if ($PreviousZip) {
    Step 'migrate a 0.1.0-local.20 ZIP installation and keep its workspace'
    $root = Join-Path $Scratch 'migrated'
    $source = Join-Path $Scratch 'previous-source'
    Expand-Archive -LiteralPath $PreviousZip -DestinationPath $source
    $previous = (Get-Content -LiteralPath (Join-Path $source 'local-release.json') -Raw | ConvertFrom-Json).version
    & "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "$source\scripts\local_setup.ps1" -SourceRoot $source -InstallRoot $root -Console -NoShortcut
    if ($LASTEXITCODE -ne 0) { throw 'previous release setup failed' }
    $process = Start-Cytellect $root $previous
    try {
        $created = Invoke-RestMethod -NoProxy -Method Post -Uri "$Origin/v1/workspaces" -Headers $Headers -WebSession (New-Session) -ContentType 'application/json' -Body '{"title":"Migration check"}'
    } finally { Stop-Cytellect $process }
    if ((Invoke-Installer $root -Offline) -ne 0) { throw 'installer over the previous release failed' }
    Assert-Shortcuts $root $true
    $process = Start-Cytellect $root
    try {
        $session = New-Session
        $kept = Invoke-RestMethod -NoProxy -Uri "$Origin/v1/workspaces/$($created.id)" -Headers $Headers -WebSession $session
        if ($kept.title -cne 'Migration check') { throw 'workspace lost in migration' }
        if ((Invoke-RestMethod -NoProxy -Uri "$Origin/v1/local/setup").retention_mode -cne 'manual') { throw 'retention changed in migration' }
        if ((Invoke-RestMethod -NoProxy -Uri "$Origin/v1/app/update" -WebSession $session).current -cne $Version) { throw 'update status names the wrong version' }
    } finally { Stop-Cytellect $process }
    Invoke-Uninstaller $root @('/DELETEDATA')
}
if ($null -ne $guiFailure) { throw ('the shortcut launcher window did not start: ' + $guiFailure) }
Write-Host 'installer smoke passed'
