# Smart App Control audit of the compiled installer on a disposable Windows runner (docs/ci.md).
# Deploys App Control audit policies equivalent to Smart App Control, installs and uses Cytellect
# (launcher window, workspace, nucleus detection with Fiji in the worker, export, uninstall), then
# lists every file that Code Integrity would have blocked. Only paths relative to the install root
# (or a fixed placeholder such as <temp>) leave the runner; no user or research path is written.
# Findings never fail the script; an audit policy that cannot be shown to be active does.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Installer,
    [Parameter(Mandatory)][string]$Version,
    [Parameter(Mandatory)][string]$Checkout,
    [Parameter(Mandatory)][string]$Output,
    [string]$Scratch = (Join-Path $env:RUNNER_TEMP 'sac-audit'),
    # Microsoft's Smart App Control audit policies (https://aka.ms/sacauditpolicies), pinned.
    [string]$PolicyZipUrl = 'https://download.microsoft.com/download/b/4/5/b45e7463-6ae0-461d-95ff-89cec7ce5159/SAC%20Audit%20Policies.zip',
    [string]$PolicyZipSha256 = 'd7d729412da6d1b759b460043b401961ef125f1b194574dfff1f53dd985b07c7'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'installer-helpers.ps1')

$CiLog = 'Microsoft-Windows-CodeIntegrity/Operational'
$ScriptLog = 'Microsoft-Windows-AppLocker/MSI and Script'
# Microsoft's signed policy: the Smart App Control rules in audit mode, without cloud reputation.
$NoIsgId = '{5283AC0F-FFF1-49AE-ADA1-8A933130CAD6}'
$IsgName = 'Cytellect CI Smart App Control audit with ISG'
$Root = Join-Path $env:LOCALAPPDATA 'Cytellect'
$ProbeDir = Join-Path $env:LOCALAPPDATA 'CytellectSacProbe'
$Downloads = Join-Path $env:USERPROFILE 'Downloads'
$CiTool = Join-Path $env:SystemRoot 'System32\CiTool.exe'
New-Item -ItemType Directory -Path $Scratch, $Output -Force | Out-Null
$facts = [ordered]@{ version = $Version; policies = [ordered]@{}; use = [ordered]@{}; errors = @() }

function Add-Error([string]$Stage, [string]$Message) {
    # Messages are fixed texts or Windows error codes; strip any drive path just in case.
    $clean = ($Message -replace '[A-Za-z]:\\[^\s''"]*', '<path>')
    if ($clean.Length -gt 300) { $clean = $clean.Substring(0, 300) }
    $script:facts.errors += "${Stage}: $clean"
    Write-Host "::warning::SAC audit ${Stage}: $clean"
}

function Invoke-CiTool([string[]]$Arguments) {
    $text = (& $CiTool @Arguments -json 2>&1 | Out-String)
    $code = $LASTEXITCODE
    $json = $null
    try { $json = $text | ConvertFrom-Json } catch { }
    return [pscustomobject]@{ ExitCode = $code; Json = $json; Text = $text }
}

function Get-ActivePolicies {
    $listed = Invoke-CiTool @('--list-policies')
    if ($null -eq $listed.Json) { return @() }
    return @(@(Get-Prop $listed.Json 'Policies') | Where-Object { $null -ne $_ } | ForEach-Object {
        [pscustomobject]@{ id = [string](Get-Prop $_ 'PolicyID'); name = [string](Get-Prop $_ 'FriendlyName')
            enforced = [string](Get-Prop $_ 'IsEnforced') -eq 'True'; signed = [string](Get-Prop $_ 'IsSignedPolicy') -eq 'True'
            system = [string](Get-Prop $_ 'IsSystemPolicy') -eq 'True' } })
}

function Get-Prop($Object, [string]$Name) {
    # CiTool's JSON fields differ between Windows builds; a missing one reads as empty.
    if ($null -eq $Object) { return $null }
    $property = $Object.PSObject.Properties[$Name]
    if ($property) { return $property.Value } else { return $null }
}

# ---- Path normalization: fixed placeholders instead of user, runner or temporary paths ----
function Get-Tail([string]$Path) { return (($Path -replace '^\\\\\?\\', '') -replace '^[A-Za-z]:', '').TrimEnd('\') + '\' }
$Anchors = @()
function Add-Anchor([string]$Path, [string]$Label) {
    if ($Path) { $script:Anchors += @{ Tail = Get-Tail $Path; Label = $Label } }
}
Add-Anchor $Root '<install>\'
Add-Anchor $ProbeDir '<probe>\'
Add-Anchor $Downloads '<downloads>\'
Add-Anchor ([IO.Path]::GetTempPath()) '<temp>\'
Add-Anchor (Join-Path $env:LOCALAPPDATA 'Temp') '<temp>\'
# The 8.3 short and the long form of %TEMP%, as Code Integrity may report either.
try {
    $fso = New-Object -ComObject Scripting.FileSystemObject
    $folder = $fso.GetFolder([IO.Path]::GetTempPath())
    Add-Anchor $folder.ShortPath '<temp>\'
    Add-Anchor (Get-Item -LiteralPath $folder.Path).FullName '<temp>\'
} catch { }
Add-Anchor $env:RUNNER_TEMP '<runner-temp>\'
Add-Anchor $env:SystemRoot '<windows>\'
Add-Anchor $env:ProgramFiles '<program-files>\'
Add-Anchor ${env:ProgramFiles(x86)} '<program-files-x86>\'

function ConvertTo-SafePath([string]$Path) {
    if (-not $Path) { return '' }
    $p = (($Path -replace '^\\\\\?\\', '') -replace '^\\Device\\HarddiskVolume\d+', '') -replace '^[A-Za-z]:', ''
    foreach ($anchor in $Anchors) {
        if ($p.StartsWith($anchor.Tail, [StringComparison]::OrdinalIgnoreCase)) {
            $rest = $p.Substring($anchor.Tail.Length)
            # Inno Setup's random extraction folders and the installed app's commit-specific folder.
            $rest = $rest -replace '(?i)^is-[a-z0-9]+(-[a-z]+)?\.tmp\\', 'is-*.tmp\'
            # Random folders of jobs and of Java's native-library loaders become wildcards.
            $rest = $rest -replace '(?i)\\[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}(?=\\)', '\*'
            $rest = $rest -replace '(?i)\\(j|cytellect-install)-[a-z0-9_]+(?=\\)', '\$1-*'
            $rest = $rest -replace '(?i)(nativelib-loader_|tensorflow_native_libraries-)[0-9-]+', '$1*'
            return $anchor.Label + $rest
        }
    }
    return '<other>\' + ($p -split '\\')[-1]
}

function Get-Group([string]$SafePath, [string]$Process = '') {
    $p = $SafePath.ToLowerInvariant()
    $leaf = ($p -split '\\')[-1]
    if ($p.StartsWith('<probe>\')) { return 'probe' }
    if ($p -match '^<temp>\\is-\*\.tmp\\' -or $p -match '^<downloads>\\cytellect-setup-' -or $p -match '^<install>\\uninstall\\') { return 'inno-setup' }
    # Not shipped by Cytellect: the runner's own tools, or a DLL found on the runner's PATH.
    if (-not ($p.StartsWith('<install>\') -or $p.StartsWith('<temp>\') -or $p.StartsWith('<downloads>\'))) { return 'runner' }
    # Cytellect's own setup scripts (unpacked with the app); other vendors' scripts stay in their group.
    if ($leaf -match '\.(ps1|psm1|psd1|cmd|bat|vbs|js|wsf)$' -and
        ($p -match '^<install>\\apps\\[^\\]+\\scripts\\' -or $p -match '^<install>\\apps\\[^\\]+\\[^\\]+$')) { return 'own-scripts' }
    # Fiji and its JDK, including native libraries that Fiji's Java plugins unpack at run time.
    if ($p -match '\\runtimes\\fiji-' -or $p -match '\\(nativelib-loader_|tensorflow_native_libraries-)' -or
        $Process -match '(?i)\\runtimes\\fiji-[^\\]+\\.*\\java(w)?\.exe$') { return 'jdk-fiji' }
    if ($p -match '\\runtimes\\python' -or $p -match '\\\.venv\\' -or $p -match '\\site-packages\\' -or $leaf -match '\.pyd$') { return 'python-wheels' }
    return 'other'
}

function Get-EventFields($Record) {
    # EventData (Code Integrity) or UserData (AppLocker script events), flattened to name -> text.
    $xml = [xml]$Record.ToXml()
    $fields = @{}
    foreach ($node in $xml.SelectNodes('//*[local-name()="EventData" or local-name()="UserData"]//*[not(*)]')) {
        $name = if ($node.LocalName -eq 'Data' -and $node.GetAttribute('Name')) { $node.GetAttribute('Name') } else { $node.LocalName }
        $fields[$name] = $node.InnerText
    }
    return $fields
}

function Get-Field($Fields, [string[]]$Names) {
    foreach ($name in $Names) { if ($Fields.ContainsKey($name) -and $Fields[$name]) { return [string]$Fields[$name] } }
    return ''
}

# Signing levels and verification errors stay as Code Integrity's numeric codes (Microsoft's
# event-ID explanations define them).

function Get-Signature([string]$Path) {
    try {
        $s = Get-AuthenticodeSignature -LiteralPath $Path
        $signer = ''
        if ($s.SignerCertificate) { $signer = ($s.SignerCertificate.Subject -replace '^.*?CN=("[^"]+"|[^,]+).*$', '$1').Trim('"') }
        return [pscustomobject]@{ status = [string]$s.Status; signer = $signer; type = [string]$s.SignatureType }
    } catch { return [pscustomobject]@{ status = 'unreadable'; signer = ''; type = '' } }
}

function Get-AuditRows {
    $rows = @()
    $ci = @(Get-WinEvent -FilterHashtable @{ LogName = $CiLog; Id = 3033, 3034, 3076, 3077, 3089 } -ErrorAction SilentlyContinue)
    # 3089 carries the signature details of the 3076/3077 event with the same activity ID.
    $signatures = @{}
    foreach ($record in $ci | Where-Object Id -eq 3089) {
        $f = Get-EventFields $record
        $key = [string]$record.ActivityId
        if (-not $signatures.ContainsKey($key)) { $signatures[$key] = @() }
        $signatures[$key] += ('{0} / {1} ({2})' -f (Get-Field $f @('PublisherName')), (Get-Field $f @('IssuerName')), (Get-Field $f @('VerificationError')))
    }
    foreach ($record in $ci | Where-Object Id -ne 3089) {
        $f = Get-EventFields $record
        $file = ConvertTo-SafePath (Get-Field $f @('File Name', 'FileName'))
        $process = ConvertTo-SafePath (Get-Field $f @('Process Name', 'ProcessName'))
        $requested = Get-Field $f @('Requested Signing Level')
        $validated = Get-Field $f @('Validated Signing Level')
        $rows += [pscustomobject]@{
            event = $record.Id; policy = Get-Field $f @('PolicyName', 'PolicyID', 'PolicyGUID'); file = $file; group = Get-Group $file $process
            process = $process; requested = $requested; validated = $validated
            ci_signatures = (@($signatures[[string]$record.ActivityId]) -join '; ')
            sha256 = Get-Field $f @('SHA256 Hash') }
    }
    $script8028 = @(Get-WinEvent -FilterHashtable @{ LogName = $ScriptLog; Id = 8028, 8029 } -ErrorAction SilentlyContinue)
    foreach ($record in $script8028) {
        $f = Get-EventFields $record
        $file = ConvertTo-SafePath (Get-Field $f @('FilePath', 'FullFilePath', 'File Name', 'FileName'))
        $rows += [pscustomobject]@{ event = $record.Id; policy = Get-Field $f @('PolicyName', 'PolicyNameBuffer'); file = $file
            group = Get-Group $file; process = ''; requested = ''; validated = ''; ci_signatures = ''; sha256 = Get-Field $f @('FileHash') }
    }
    return $rows
}

# ---------------------------------------------------------------- facts about the runner
Step 'runner and Smart App Control state'
$os = Get-CimInstance -ClassName Win32_OperatingSystem
$facts.os = '{0} build {1}' -f $os.Caption, $os.BuildNumber
$sacState = (Get-ItemProperty -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Control\CI\Policy' -Name VerifiedAndReputablePolicyState -ErrorAction SilentlyContinue)
$facts.sac_registry_state = if ($sacState) { [int]$sacState.VerifiedAndReputablePolicyState } else { 'absent' }
$facts.citool = Test-Path -LiteralPath $CiTool
$facts.policies_before = @(Get-ActivePolicies | Where-Object { -not $_.system } | ForEach-Object { $_.name })
Write-Host ('{0}; Smart App Control registry state: {1}; CiTool: {2}' -f $facts.os, $facts.sac_registry_state, $facts.citool)
if (-not $facts.citool) { throw 'CiTool is not available on this runner' }
& wevtutil.exe sl $CiLog /ms:209715200 /e:true | Out-Null
& wevtutil.exe cl $CiLog | Out-Null
& wevtutil.exe cl $ScriptLog 2>$null | Out-Null

# ---------------------------------------------------------------- policy 1: Microsoft's audit policy without ISG
Step 'deploy Microsoft''s Smart App Control audit policy without ISG'
$zip = Join-Path $Scratch 'sac-audit-policies.zip'
Invoke-WebRequest -UseBasicParsing -Uri $PolicyZipUrl -OutFile $zip
if ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant() -ne $PolicyZipSha256) { throw 'Smart App Control policy download hash mismatch' }
Expand-Archive -LiteralPath $zip -DestinationPath (Join-Path $Scratch 'policies') -Force
$noIsg = Join-Path $Scratch 'policies\SmartAppControlAuditNoISG.bin'
$facts.policies.no_isg = [ordered]@{ source = 'Microsoft SmartAppControlAuditNoISG.bin (signed)'; method = ''; active = $false }
$deployed = Invoke-CiTool @('--update-policy', $noIsg)
Write-Host ('CiTool --update-policy (no ISG): exit {0}' -f $deployed.ExitCode)
if ($deployed.ExitCode -eq 0) { $facts.policies.no_isg.method = 'CiTool --update-policy' }
else {
    # Microsoft's documented route for this policy: the EFI system partition, then a refresh.
    Add-Error 'no-ISG policy via CiTool' ('exit ' + $deployed.ExitCode + ' ' + ($deployed.Text -replace '\s+', ' '))
    try {
        & mountvol.exe S: /S | Out-Null
        $efi = 'S:\EFI\Microsoft\Boot\CiPolicies\Active'
        New-Item -ItemType Directory -Path $efi -Force | Out-Null
        Copy-Item -LiteralPath $noIsg -Destination (Join-Path $efi "$NoIsgId.cip") -Force
        $refresh = Invoke-CiTool @('--refresh')
        Write-Host ('EFI copy and CiTool --refresh: exit {0}' -f $refresh.ExitCode)
        $facts.policies.no_isg.method = 'EFI system partition + CiTool --refresh'
    } catch { Add-Error 'no-ISG policy via EFI' $_.Exception.Message }
}

# ---------------------------------------------------------------- policy 2: the example SAC policy in audit mode with ISG
Step 'deploy the example Smart App Control policy in audit mode with ISG'
$example = Join-Path $env:SystemRoot 'schemas\CodeIntegrity\ExamplePolicies\SmartAppControl.xml'
$facts.policies.isg = [ordered]@{ source = 'ExamplePolicies\SmartAppControl.xml + audit mode, unconditional'; method = ''; active = $false; options = @() }
$isgId = $null
if (-not (Test-Path -LiteralPath $example)) { Add-Error 'ISG policy' 'SmartAppControl.xml example policy is not on this runner' }
else {
    try {
        $xmlPath = Join-Path $Scratch 'sac-isg-audit.xml'
        $cipPath = Join-Path $Scratch 'sac-isg-audit.cip'
        Copy-Item -LiteralPath $example -Destination $xmlPath
        # The ConfigCI cmdlets ship with Windows PowerShell. Audit mode (3), unsigned policy (6),
        # ISG (14) and rebootless update (16), without the condition that limits the example to
        # Smart App Control clients; a fresh policy ID so nothing built in is replaced.
        $configure = @'
param([string]$Xml, [string]$Cip, [string]$Name)
$ErrorActionPreference = 'Stop'
Import-Module ConfigCI
foreach ($option in 3, 6, 14, 16) { Set-RuleOption -FilePath $Xml -Option $option }
# The example applies only where Smart App Control runs (a Windows client); make it unconditional.
[xml]$policy = Get-Content -LiteralPath $Xml -Raw
foreach ($rule in @($policy.SiPolicy.Rules.Rule)) {
    if ($rule.Option -eq 'Enabled:Conditional Windows Lockdown Policy') { $null = $policy.SiPolicy.Rules.RemoveChild($rule) }
}
$policy.Save($Xml)
$null = Set-CIPolicyIdInfo -FilePath $Xml -PolicyName $Name -ResetPolicyID
$null = ConvertFrom-CIPolicy -XmlFilePath $Xml -BinaryFilePath $Cip
'@
        $configureScript = Join-Path $Scratch 'configure-isg-policy.ps1'
        [IO.File]::WriteAllText($configureScript, $configure)
        & (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe') -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $configureScript -Xml $xmlPath -Cip $cipPath -Name $IsgName
        if ($LASTEXITCODE -ne 0) { throw 'ConfigCI could not build the ISG audit policy' }
        [xml]$policyXml = Get-Content -LiteralPath $xmlPath -Raw
        $isgId = [string]$policyXml.SiPolicy.PolicyID
        $facts.policies.isg.options = @($policyXml.SiPolicy.Rules.Rule | ForEach-Object { [string]$_.Option })
        # Never deploy an enforcing Smart App Control policy: it would block the runner's own tools.
        if ($facts.policies.isg.options -notcontains 'Enabled:Audit Mode') { $isgId = $null; throw 'the ISG policy is not in audit mode' }
        $cip = Join-Path $Scratch "$isgId.cip"
        Move-Item -LiteralPath $cipPath -Destination $cip
        $deployed = Invoke-CiTool @('--update-policy', $cip)
        Write-Host ('CiTool --update-policy (ISG): exit {0}' -f $deployed.ExitCode)
        if ($deployed.ExitCode -ne 0) { Add-Error 'ISG policy via CiTool' ('exit ' + $deployed.ExitCode) }
        else { $facts.policies.isg.method = 'CiTool --update-policy' }
        # ISG needs the AppID services (appidtel) as documented for App Control with ISG.
        & (Join-Path $env:SystemRoot 'System32\appidtel.exe') start 2>&1 | Out-Null
        $facts.isg_services = @(Get-Service -Name AppIDSvc, AppID -ErrorAction SilentlyContinue |
            ForEach-Object { '{0}={1}' -f $_.Name, $_.Status })
    } catch { Add-Error 'ISG policy' $_.Exception.Message }
}
$active = Get-ActivePolicies
$facts.policies_after = @($active | Where-Object { -not $_.system } | ForEach-Object { '{0} (enforced={1}, signed={2})' -f $_.name, $_.enforced, $_.signed })
$facts.policies_after | ForEach-Object { Write-Host ('active policy: ' + $_) }

# ---------------------------------------------------------------- proof: an unsigned executable must be audited
Step 'an unsigned test executable must appear in the audit'
New-Item -ItemType Directory -Path $ProbeDir -Force | Out-Null
$probe = Join-Path $ProbeDir 'sac-probe.exe'
$source = Join-Path $ProbeDir 'sac-probe.cs'
[IO.File]::WriteAllText($source, 'class P { static int Main() { System.Console.WriteLine("unsigned probe ran"); return 0; } }')
& (Join-Path $env:SystemRoot 'Microsoft.NET\Framework64\v4.0.30319\csc.exe') /nologo /out:$probe $source | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'could not build the unsigned probe' }
$facts.probe_signature = (Get-Signature $probe).status
& $probe | Out-Null
Start-Sleep -Seconds 5

# ---------------------------------------------------------------- install and use, as a researcher would
Step 'silent per-user installation into %LOCALAPPDATA%\Cytellect from the Downloads folder'
if (Test-Path -LiteralPath $Root) { throw 'the default installation folder already exists on this runner' }
New-Item -ItemType Directory -Path $Downloads -Force | Out-Null
$downloaded = Join-Path $Downloads (Split-Path -Leaf $Installer)
Copy-Item -LiteralPath $Installer -Destination $downloaded -Force
$Installer = $downloaded
$facts.use.install_exit = Invoke-Installer $Root -Offline
$failure = $null
try {
    if ($facts.use.install_exit -ne 0) { throw 'installation failed' }
    Step 'the shortcut launcher window starts'
    Stop-Cytellect (Start-Cytellect $Root -Gui)
    Get-Process -Name python, pythonw -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    $facts.use.gui = 'started'

    Step 'workspace, BBBC013 A01 upload, nucleus detection with Fiji in the worker, review and export'
    $process = Start-Cytellect $Root
    try {
        $session = New-Session
        $workspace = Invoke-RestMethod -NoProxy -Method Post -Uri "$Origin/v1/workspaces" -Headers $Headers -WebSession $session -ContentType 'application/json' -Body '{"title":"Smart App Control audit"}'
        $fixtures = Join-Path $Checkout 'fixtures\public\bbbc013'
        $metadata = '{"condition":"BBBC013 A01","experimental_unit":"public-plate","sample":"A01","acquisition_date":"public-acquisition"}'
        $field = Invoke-RestMethod -NoProxy -Method Post -Uri "$Origin/v1/workspaces/$($workspace.id)/fields" -Headers $Headers -WebSession $session -Form @{
            metadata = $metadata; dapi = Get-Item -LiteralPath (Join-Path $fixtures 'A01-dapi.tif'); gfp = Get-Item -LiteralPath (Join-Path $fixtures 'A01-gfp.tif') }
        $null = Invoke-WebRequest -UseBasicParsing -NoProxy -Uri "$Origin/v1/fields/$($field.id)/preview" -WebSession $session
        $body = @{ recipe = @{ id = 'gfp-nuclear-2d' }; backgrounds = @{ $field.id = @{ polygon = @(@(1, 1), @(4, 1), @(4, 4), @(1, 4)); confirmed = $true } } } | ConvertTo-Json -Depth 6
        $trial = Invoke-RestMethod -NoProxy -Method Post -Uri "$Origin/v1/workspaces/$($workspace.id)/analyses" -Headers $Headers -WebSession $session -ContentType 'application/json' -Body $body
        function Wait-CytellectJob([string]$Id) {
            $watch = [Diagnostics.Stopwatch]::StartNew()
            while ($watch.Elapsed.TotalSeconds -lt 900) {
                $job = Invoke-RestMethod -NoProxy -Uri "$Origin/v1/jobs/$Id" -WebSession $session
                if ($job.state -eq 'succeeded') { Write-Host ('job {0} succeeded after {1:N0} s' -f $job.kind, $watch.Elapsed.TotalSeconds); return }
                if ($job.state -in @('failed', 'cancelled')) { throw ('job ' + $job.kind + ' ' + $job.state + ' ' + $job.error) }
                Start-Sleep -Seconds 3
            }
            throw 'job did not finish'
        }
        Wait-CytellectJob $trial.job_id
        $report = Invoke-RestMethod -NoProxy -Uri "$Origin/v1/revisions/$($trial.revision_id)/measurements" -WebSession $session
        $facts.use.nuclei = @($report.cells).Count
        Write-Host ('detected nuclei: {0}' -f $facts.use.nuclei)
        if ($facts.use.nuclei -lt 100) { throw 'nucleus detection found fewer than 100 nuclei' }
        $null = Invoke-RestMethod -NoProxy -Method Post -Uri "$Origin/v1/revisions/$($trial.revision_id)/review" -Headers $Headers -WebSession $session -ContentType 'application/json' -Body '{}'
        $exported = Invoke-RestMethod -NoProxy -Method Post -Uri "$Origin/v1/revisions/$($trial.revision_id)/export" -Headers $Headers -WebSession $session
        Wait-CytellectJob $exported.job_id
        $facts.use.export = 'succeeded'
    } finally { Stop-Cytellect $process }
} catch { $failure = $_.Exception.Message; Add-Error 'use' $failure }

# ---------------------------------------------------------------- signatures and static inventory before uninstall
Step 'signature status of every executable file under the install root'
$inventory = @()
if (Test-Path -LiteralPath $Root) {
    $extensions = @('.exe', '.dll', '.pyd', '.sys', '.ocx', '.cpl', '.ps1', '.psm1', '.psd1', '.cmd', '.bat', '.vbs', '.js', '.msi')
    foreach ($file in Get-ChildItem -LiteralPath $Root -Recurse -File -Force -ErrorAction SilentlyContinue | Where-Object { $_.Extension.ToLowerInvariant() -in $extensions }) {
        $safe = ConvertTo-SafePath $file.FullName
        $group = Get-Group $safe
        # Executable images of every group, and scripts only where Cytellect itself runs them.
        if ($file.Extension -notin @('.exe', '.dll', '.pyd', '.sys', '.ocx', '.cpl') -and $group -ne 'own-scripts') { continue }
        $sig = Get-Signature $file.FullName
        $inventory += [pscustomobject]@{ file = $safe; group = $group; status = $sig.status; signer = $sig.signer }
    }
}
$signatureOf = @{}
foreach ($item in $inventory) { $signatureOf[$item.file.ToLowerInvariant()] = $item }
foreach ($leftover in @($probe, $downloaded)) {
    $sig = Get-Signature $leftover
    $signatureOf[(ConvertTo-SafePath $leftover).ToLowerInvariant()] = [pscustomobject]@{ status = $sig.status; signer = $sig.signer }
}
# Inno Setup's extracted loader and helpers are gone after the run; this one stays for the record.

Step 'uninstall (Inno Setup uninstaller)'
try { if (Test-Path -LiteralPath (Join-Path $Root 'uninstall\unins000.exe')) { Invoke-Uninstaller $Root @('/DELETEDATA') } }
catch { Add-Error 'uninstall' $_.Exception.Message }
Start-Sleep -Seconds 5

# ---------------------------------------------------------------- collect, de-duplicate, report
Step 'collect Code Integrity and script audit events'
$rows = @(Get-AuditRows)
$facts.event_counts = [ordered]@{}
foreach ($id in 3033, 3034, 3076, 3077, 3089, 8028, 8029) { $facts.event_counts["$id"] = @($rows | Where-Object event -eq $id).Count }
$facts.event_counts['3089'] = @(Get-WinEvent -FilterHashtable @{ LogName = $CiLog; Id = 3089 } -ErrorAction SilentlyContinue).Count
$unique = @($rows | Group-Object { '{0}|{1}|{2}' -f $_.event, $_.policy, $_.file.ToLowerInvariant() } | ForEach-Object {
    $first = $_.Group[0]
    $sig = $signatureOf[$first.file.ToLowerInvariant()]
    [pscustomobject]@{ event = $first.event; policy = $first.policy; group = $first.group; file = $first.file
        count = $_.Count; signature = $(if ($sig) { $sig.status } else { 'not on disk after the run' })
        signer = $(if ($sig) { $sig.signer } else { '' }); validated_level = $first.validated; requested_level = $first.requested
        ci_signatures = $first.ci_signatures; process = $first.process; sha256 = $first.sha256 } } | Sort-Object group, file, policy)

# Events name the policy (or, on some builds, only its ID).
function Test-Policy($Row, [string]$Which) {
    if ($Which -eq 'no_isg') { return $Row.policy -like '*AuditNoISG*' -or $Row.policy -like "*$($NoIsgId.Trim('{}'))*" }
    return $Row.policy -eq $IsgName -or ($isgId -and $Row.policy -like "*$($isgId.Trim('{}'))*")
}
$probeSeen = @($unique | Where-Object { $_.group -eq 'probe' -and $_.event -eq 3076 })
$facts.policies.no_isg.active = [bool]@($probeSeen | Where-Object { Test-Policy $_ 'no_isg' }).Count
$facts.policies.isg.active = [bool]@($probeSeen | Where-Object { Test-Policy $_ 'isg' }).Count
$facts.probe_policies = @($probeSeen | ForEach-Object { $_.policy } | Sort-Object -Unique)

$unique | Export-Csv -LiteralPath (Join-Path $Output 'sac-audit-events.csv') -NoTypeInformation -Encoding utf8
$inventory | Sort-Object group, file | Export-Csv -LiteralPath (Join-Path $Output 'sac-inventory.csv') -NoTypeInformation -Encoding utf8
$groups = 'python-wheels', 'jdk-fiji', 'own-scripts', 'inno-setup', 'other', 'runner'
$facts.audited = [ordered]@{}
foreach ($which in 'no_isg', 'isg') {
    $byPolicy = @($unique | Where-Object { (Test-Policy $_ $which) -and $_.group -ne 'probe' })
    $counts = [ordered]@{}
    foreach ($group in $groups) { $counts[$group] = @($byPolicy | Where-Object group -eq $group | ForEach-Object { $_.file.ToLowerInvariant() } | Sort-Object -Unique).Count }
    $facts.audited[$which] = $counts
}
$facts.inventory = [ordered]@{}
foreach ($group in $groups) {
    $items = @($inventory | Where-Object group -eq $group)
    $facts.inventory[$group] = [ordered]@{ files = $items.Count; valid_signature = @($items | Where-Object status -eq 'Valid').Count
        not_signed = @($items | Where-Object status -eq 'NotSigned').Count }
}
# Files that only the policy without ISG audits: the runner's cloud reputation lookups allowed them.
function Get-AuditedFiles([string]$Which) {
    return @($unique | Where-Object { (Test-Policy $_ $Which) -and $_.group -notin @('probe', 'runner') } |
        ForEach-Object { $_.file.ToLowerInvariant() } | Sort-Object -Unique)
}
$isgFiles = Get-AuditedFiles 'isg'
$facts.isg_allowed = @(Get-AuditedFiles 'no_isg' | Where-Object { $_ -notin $isgFiles }).Count
$facts | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $Output 'sac-audit.json') -Encoding utf8

# ---------------------------------------------------------------- step summary
$summary = @('## Smart App Control audit (emulated on the CI runner)', '',
    ('Runner: {0}. Smart App Control itself is not present on Windows Server; Code Integrity enforces the same rules in audit mode.' -f $facts.os), '',
    ('- Microsoft audit policy without ISG (worst case: only files signed by a trusted CA pass): active = **{0}**' -f $facts.policies.no_isg.active),
    ('- Example Smart App Control policy with ISG (cloud reputation): active = **{0}**' -f $facts.policies.isg.active),
    ('- Shipped files audited without ISG but allowed with ISG (reputation as seen from this runner today): {0}' -f $facts.isg_allowed),
    ('- Unsigned probe executable audited by: {0}' -f $(if ($facts.probe_policies) { $facts.probe_policies -join ', ' } else { 'none' })),
    ('- Use: install exit {0}; nuclei detected {1}; export {2}' -f $facts.use.install_exit, $(if ($facts.use.Contains('nuclei')) { $facts.use.nuclei } else { '-' }), $(if ($facts.use.Contains('export')) { $facts.use.export } else { '-' })),
    ('- Events: ' + (($facts.event_counts.GetEnumerator() | ForEach-Object { '{0}={1}' -f $_.Key, $_.Value }) -join ', ')), '',
    '| Group | Audited without ISG | Audited with ISG | Executable files installed | Validly signed | Not signed |', '|---|---:|---:|---:|---:|---:|')
foreach ($group in $groups) {
    $summary += ('| {0} | {1} | {2} | {3} | {4} | {5} |' -f $group, $facts.audited.no_isg[$group], $facts.audited.isg[$group],
        $facts.inventory[$group].files, $facts.inventory[$group].valid_signature, $facts.inventory[$group].not_signed)
}
$summary += @('', 'Examples (without ISG):', '')
foreach ($group in $groups) {
    $examples = @($unique | Where-Object { (Test-Policy $_ 'no_isg') -and $_.group -eq $group } | Select-Object -First 8)
    foreach ($example in $examples) { $summary += ('- {0}: `{1}` ({2}; {3})' -f $group, $example.file, $example.signature, $example.validated_level) }
}
if ($facts.errors) { $summary += @('', 'Problems:', '') + @($facts.errors | ForEach-Object { '- ' + $_ }) }
$summary += @('', 'Findings do not fail this job. A real Windows 11 PC with Smart App Control on can differ: see docs/local.md.')
$summary | ForEach-Object { Write-Host $_ }
if ($env:GITHUB_STEP_SUMMARY) { $summary | Out-File -FilePath $env:GITHUB_STEP_SUMMARY -Append -Encoding utf8 }

# ---------------------------------------------------------------- remove the audit policies
Step 'remove the audit policies'
foreach ($id in @($isgId, $NoIsgId)) {
    if (-not $id) { continue }
    $removed = Invoke-CiTool @('--remove-policy', $id)
    Write-Host ('CiTool --remove-policy {0}: exit {1}' -f $id, $removed.ExitCode)
}
if (Test-Path -LiteralPath 'S:\EFI\Microsoft\Boot\CiPolicies\Active') {
    Remove-Item -LiteralPath "S:\EFI\Microsoft\Boot\CiPolicies\Active\$NoIsgId.cip" -Force -ErrorAction SilentlyContinue
    & mountvol.exe S: /D | Out-Null
}
$null = Invoke-CiTool @('--refresh')
Remove-Item -LiteralPath $ProbeDir, $downloaded -Recurse -Force -ErrorAction SilentlyContinue

if (-not ($facts.policies.no_isg.active -or $facts.policies.isg.active)) { throw 'no audit policy was shown to be active: the unsigned probe was not audited' }
if ($failure) { throw ('the installed application could not be used: ' + $failure) }
Write-Host 'Smart App Control audit finished'
