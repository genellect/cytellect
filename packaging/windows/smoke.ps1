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
    [string]$PreviousZip = '',
    # A newer installer of the same source, for the in-app update and its rollback (I7).
    [string]$UpdateInstaller = '',
    [string]$UpdateVersion = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$UninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{6F1E0A2C-4C1B-4E57-9B2D-3C7A1F0E9D21}_is1'
# The launcher's port (8765 unless --port is given); Use-Port switches every request to another.
function Use-Port([int]$Port) {
    $script:Port = $Port
    $script:Origin = "http://127.0.0.1:$Port"
    $script:Headers = @{ Origin = $script:Origin; 'X-Cytellect-Request' = '1' }
}
Use-Port 8765
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
    # The distributed copy has no signing key built in yet (docs/release-signing.md): it never
    # updates in the app. Offline nothing newer is known, so there is nothing to ask for either.
    if ($update.current -cne $Version -or $update.available -or $update.state -cne 'unsupported' -or $update.error) {
        throw ('unexpected update status ' + $update.state + ' ' + $update.error)
    }
    Write-Host 'update status without a signing key, offline: unsupported'

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
if ($UpdateInstaller) {
    # In-app update (I7, T1) against a generated release feed on 127.0.0.1. The test hook in
    # packaging/windows/update-test is copied into one installed version's site-packages as a
    # .pth import (it loads under -E); it is never part of the ZIP or the installer.
    $feedDirectory = Join-Path $Scratch 'update-feed'
    New-Item -ItemType Directory -Path $feedDirectory | Out-Null
    $feedPort = 8799
    $base = "http://127.0.0.1:$feedPort"
    $name = "Cytellect-Setup-$UpdateVersion.exe"
    Copy-Item -LiteralPath $UpdateInstaller -Destination (Join-Path $feedDirectory $name)
    # The signed manifest, as the release workflow publishes it, but signed with a key made for
    # this run; only the CI hook (never a distributed copy) lets the installed version trust it.
    $manifest = "Cytellect-update-$UpdateVersion.json"
    $commit = (& git -C $Checkout rev-parse HEAD).Trim()
    & $python -B (Join-Path $Checkout 'packaging\windows\update-test\sshsig_test_signer.py') --installer $UpdateInstaller --version $UpdateVersion --commit $commit --output-dir $feedDirectory
    if ($LASTEXITCODE -ne 0) { throw 'signing the generated release failed' }
    $feed = @(@{ tag_name = "v$UpdateVersion"; draft = $false
        html_url = "https://github.com/genellect/cytellect/releases/tag/v$UpdateVersion"
        assets = @(@{ name = $name; size = (Get-Item -LiteralPath $UpdateInstaller).Length; browser_download_url = "$base/$name" },
                   @{ name = $manifest; browser_download_url = "$base/$manifest" },
                   @{ name = "$manifest.sig"; browser_download_url = "$base/$manifest.sig" }) })
    [IO.File]::WriteAllText((Join-Path $feedDirectory 'releases.json'), (ConvertTo-Json -InputObject $feed -Depth 6))
    $server = Start-Process -FilePath $python -PassThru -WindowStyle Hidden -ArgumentList @(
        '-m', 'http.server', "$feedPort", '--bind', '127.0.0.1', '--directory', ('"' + $feedDirectory + '"'))
    $env:CYTELLECT_TEST_RELEASES = "$base/releases.json"
    $env:CYTELLECT_TEST_UPDATE_KEY = [IO.File]::ReadAllText((Join-Path $feedDirectory 'update-test-key.pub')).Trim()

    function Install-UpdateHook([string]$Root) {
        $site = Join-Path (Get-App $Root).app '.venv\Lib\site-packages'
        Copy-Item -LiteralPath (Join-Path $Checkout 'packaging\windows\update-test\cytellect_ci_update_hook.py') -Destination $site
        [IO.File]::WriteAllText((Join-Path $site 'cytellect_ci_update_hook.pth'), "import cytellect_ci_update_hook`n")
    }

    function Stop-Root([string]$Root) {
        Get-CimInstance -ClassName Win32_Process | Where-Object {
            $_.Name -in @('python.exe', 'pythonw.exe') -and $_.ExecutablePath -and
            $_.ExecutablePath.StartsWith($Root, [StringComparison]::OrdinalIgnoreCase) } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        for ($attempt = 0; $attempt -lt 60; $attempt++) {
            if (-not (Get-NetTCPConnection -LocalPort $script:Port -State Listen -ErrorAction SilentlyContinue)) { return }
            Start-Sleep -Milliseconds 500
        }
        throw 'launcher kept listening after stop'
    }

    function Wait-UpdateState([string]$Current, [string]$State) {
        # The launcher stops and another starts in between; ask again with a new session each time.
        $watch = [Diagnostics.Stopwatch]::StartNew()
        $last = ''
        while ($watch.Elapsed.TotalSeconds -lt 1200) {
            try {
                $status = Invoke-RestMethod -NoProxy -TimeoutSec 10 -Uri "$Origin/v1/app/update" -WebSession (New-Session)
                $observed = $status.current + ' ' + $status.state + ' ' + $status.error
                if ($observed -cne $last) { Write-Host ('update status: ' + $observed); $last = $observed }
                if ($status.current -ceq $Current -and $status.state -ceq $State) {
                    Write-Host ('update reached {0} after {1:N0} s' -f $State, $watch.Elapsed.TotalSeconds)
                    return $status
                }
                if ($status.state -ceq 'failed') { throw ('update failed: ' + $status.error) }
            } catch {
                # Between launchers nothing answers; only a reported failure ends the wait.
                if ($_.Exception.Message -like 'update failed:*') { throw }
            }
            Start-Sleep -Seconds 3
        }
        throw "update did not reach $State"
    }

    function Get-RefusalCode([scriptblock]$Request) {
        try { & $Request | Out-Null; return 'accepted' }
        catch {
            $detail = $null
            if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
                try { $detail = ($_.ErrorDetails.Message | ConvertFrom-Json).detail } catch { }
            }
            return ('{0} {1}' -f [int]$_.Exception.Response.StatusCode, $detail)
        }
    }

    function Assert-TestKey($Status, [string]$Stage) {
        # Only the CI hook makes the installed copy trust this run's key; a distributed copy cannot.
        if (-not $Status.available -or $Status.latest -cne $UpdateVersion -or $Status.state -cne 'idle' -or $Status.error) {
            throw ('{0}: the test signing key is not in effect ({1} {2})' -f $Stage, $Status.state, $Status.error)
        }
        Write-Host ('{0}: the test signing key is in effect; {1} is offered' -f $Stage, $UpdateVersion)
    }

    function Assert-ShortcutVersion([string]$Root, [string]$Expected) {
        $link = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path ([Environment]::GetFolderPath('Programs')) 'Cytellect.lnk'))
        if (-not $link.TargetPath.StartsWith((Join-Path $Root "apps\$Expected-"), [StringComparison]::OrdinalIgnoreCase)) {
            throw "shortcut does not open $Expected"
        }
    }

    try {
        Step 'without a built-in signing key, a newer release asks for its installer'
        $root = Join-Path $Scratch 'update'
        if ((Invoke-Installer $root -Offline) -ne 0) { throw 'installation for the update failed' }
        Install-UpdateHook $root
        # The hook points this copy at the generated release list but, without the test key,
        # the copy keeps the empty built-in key, as distributed.
        $testKey = $env:CYTELLECT_TEST_UPDATE_KEY
        $env:CYTELLECT_TEST_UPDATE_KEY = $null
        $process = Start-Cytellect $root
        try {
            $session = New-Session
            $manual = Invoke-RestMethod -NoProxy -Uri "$Origin/v1/app/update" -WebSession $session
            if ($manual.available -or $manual.latest -cne $UpdateVersion -or $manual.state -cne 'unsupported' -or $manual.error -cne 'update_signing_key_missing') {
                throw ('a copy without a signing key reported ' + $manual.state + ' ' + $manual.error)
            }
            $refusal = Get-RefusalCode { Invoke-RestMethod -NoProxy -Method Post -Uri "$Origin/v1/app/update" -Headers $Headers -WebSession $session }
            if ($refusal -cne '409 update_unsupported') { throw ('a copy without a signing key answered the update with ' + $refusal) }
            Write-Host ('without a signing key: {0} is named for its installer (update_signing_key_missing); the update is refused (409 update_unsupported)' -f $UpdateVersion)
        } finally { Stop-Cytellect $process; $env:CYTELLECT_TEST_UPDATE_KEY = $testKey }

        Step 'in-app update: verify the signed manifest, download, install beside, switch to the new version'
        $process = Start-Cytellect $root
        $session = New-Session
        $created = Invoke-RestMethod -NoProxy -Method Post -Uri "$Origin/v1/workspaces" -Headers $Headers -WebSession $session -ContentType 'application/json' -Body '{"title":"Update check"}'
        Assert-TestKey (Invoke-RestMethod -NoProxy -Uri "$Origin/v1/app/update" -WebSession $session) 'in-app update'
        $null = Invoke-RestMethod -NoProxy -Method Post -Uri "$Origin/v1/app/update" -Headers $Headers -WebSession $session
        $null = Wait-UpdateState $UpdateVersion 'updated'
        # The tab that started the update keeps its cookie, which the stopped launcher revoked.
        # The new version refuses it with 401 until the local session is opened again, as the
        # workspace's update banner does (followUpdate in apps/web/src/lib/cloud-account.ts).
        $refused = 'answered'
        try { $null = Invoke-RestMethod -NoProxy -Uri "$Origin/v1/app/update" -WebSession $session }
        catch { $refused = [int]$_.Exception.Response.StatusCode }
        if ($refused -ne 401) { throw "the revoked session was not refused with 401 ($refused)" }
        Invoke-WebRequest -UseBasicParsing -NoProxy -Method Post -Uri "$Origin/v1/local/session" -Headers $Headers -WebSession $session | Out-Null
        $resumed = Invoke-RestMethod -NoProxy -Uri "$Origin/v1/app/update" -WebSession $session
        if ($resumed.state -cne 'updated' -or $resumed.current -cne $UpdateVersion) { throw 'the reopened session does not see the completed update' }
        $kept = Invoke-RestMethod -NoProxy -Uri "$Origin/v1/workspaces/$($created.id)" -Headers $Headers -WebSession (New-Session)
        if ($kept.title -cne 'Update check') { throw 'workspace lost in the in-app update' }
        Assert-ShortcutVersion $root $UpdateVersion
        if (@(Get-ChildItem -LiteralPath (Join-Path $root 'updates') -Recurse -Filter '*.exe' -ErrorAction SilentlyContinue).Count) {
            throw 'the downloaded installer remained'
        }
        Stop-Root $root
        Invoke-Uninstaller $root @('/DELETEDATA')

        Step 'in-app update whose new version does not start returns to the previous version (port 8791)'
        # Started with --port, the relauncher must start both versions on that port, or the
        # health check and the open tab would not reach them.
        Use-Port 8791
        $root = Join-Path $Scratch 'rollback'
        if ((Invoke-Installer $root -Offline) -ne 0) { throw 'installation for the rollback failed' }
        Install-UpdateHook $root
        $env:CYTELLECT_TEST_FAIL_VERSION = $UpdateVersion
        $process = Start-Cytellect $root
        $session = New-Session
        $created = Invoke-RestMethod -NoProxy -Method Post -Uri "$Origin/v1/workspaces" -Headers $Headers -WebSession $session -ContentType 'application/json' -Body '{"title":"Rollback check"}'
        Assert-TestKey (Invoke-RestMethod -NoProxy -Uri "$Origin/v1/app/update" -WebSession $session) 'rollback'
        $null = Invoke-RestMethod -NoProxy -Method Post -Uri "$Origin/v1/app/update" -Headers $Headers -WebSession $session
        $status = Wait-UpdateState $Version 'rolled_back'
        if ($status.error -cne 'update_new_version_failed_to_start') { throw ('unexpected rollback reason ' + $status.error) }
        $kept = Invoke-RestMethod -NoProxy -Uri "$Origin/v1/workspaces/$($created.id)" -Headers $Headers -WebSession (New-Session)
        if ($kept.title -cne 'Rollback check') { throw 'workspace lost in the rollback' }
        Assert-ShortcutVersion $root $Version
        if (@(Get-ChildItem -LiteralPath (Join-Path $root 'updates\rollback') -Filter '*.sqlite' -ErrorAction SilentlyContinue).Count) {
            throw 'the database copy remained after a successful rollback'
        }
        Stop-Root $root
        Invoke-Uninstaller $root @('/DELETEDATA')
    } finally {
        $env:CYTELLECT_TEST_RELEASES = $null; $env:CYTELLECT_TEST_FAIL_VERSION = $null; $env:CYTELLECT_TEST_UPDATE_KEY = $null
        Use-Port 8765
        if (-not $server.HasExited) { Stop-Process -Id $server.Id -Force }
    }
}

if ($null -ne $guiFailure) { throw ('the shortcut launcher window did not start: ' + $guiFailure) }
Write-Host 'installer smoke passed'
