# Changes certificate trust / installs packages ONLY on disposable GitHub-hosted CI.
[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$Package,
      [Parameter(Mandatory = $true)][string]$WorkRoot)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted') {
    throw 'msix_acceptance_requires_disposable_hosted_runner'
}
$identity = 'Cytellect.Development'
if (Get-AppxPackage -Name $identity) { throw 'msix_acceptance_existing_package' }
$userRoot = Join-Path $env:LOCALAPPDATA 'Cytellect'
if (Test-Path -LiteralPath $userRoot) { throw 'msix_acceptance_existing_data' }
if (Test-Path -LiteralPath $WorkRoot) { throw 'msix_acceptance_existing_workroot' }
New-Item -ItemType Directory -Path $WorkRoot | Out-Null
$repo = Split-Path -Parent $PSScriptRoot
$receipt = [ordered]@{schema='cytellect-msix-acceptance/1'; source_commit=$env:GITHUB_SHA
    install=$false; activation=$false; manual_retention=$false; fiji=$false
    public_browser=$false; numerical_replay=$false; stopped=$false; uninstall_retention=$false; reinstall=$false
    scope='Disposable Windows runner; public microscopy and generated numerical fixtures; no private-study or lab-policy acceptance'}
$certificate = $null
$app = $null
try {
    $certificate = New-SelfSignedCertificate -Type Custom -Subject 'CN=Cytellect Development' -KeyUsage DigitalSignature -FriendlyName 'Disposable Cytellect MSIX CI' -CertStoreLocation Cert:\CurrentUser\My -TextExtension @('2.5.29.37={text}1.3.6.1.5.5.7.3.3','2.5.29.19={text}')
    $public = Join-Path $WorkRoot 'ci.cer'
    Export-Certificate -Cert $certificate -FilePath $public | Out-Null
    Import-Certificate -FilePath $public -CertStoreLocation Cert:\LocalMachine\TrustedPeople | Out-Null
    $sdk = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits/10'
    $signer = @(Get-ChildItem -LiteralPath (Join-Path $sdk 'bin') -Filter signtool.exe -Recurse |
        Where-Object { $_.Directory.Name -eq 'x64' } | Sort-Object FullName -Descending)[0].FullName
    $signed = Join-Path $WorkRoot 'signed.msix'
    Copy-Item -LiteralPath $Package -Destination $signed
    & $signer sign /fd SHA256 /sha1 $certificate.Thumbprint /s My $signed
    if ($LASTEXITCODE -ne 0) { throw 'msix_ci_signing_failed' }
    & $signer verify /pa /v $signed
    if ($LASTEXITCODE -ne 0) { throw 'msix_ci_signature_verification_failed' }
    # Pre-existing data exercises the unvirtualized ZIP -> Store handoff.
    New-Item -ItemType Directory -Path (Join-Path $userRoot 'data') | Out-Null
    $sentinel = Join-Path $userRoot 'data/retention-test.txt'
    [IO.File]::WriteAllText($sentinel, 'generated retention fixture')
    Add-AppxPackage -Path $signed
    $app = Get-AppxPackage -Name $identity
    if (-not $app -or $app.Status -ne 'Ok') { throw 'msix_ci_install_failed' }
    $receipt.install = $true
    $installed = $app.InstallLocation
    $python = Join-Path $installed 'runtime/python.exe'
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
[ComImport, Guid("2e941141-7f97-4756-ba1d-9decde894a3d"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IActivationManager {
 [PreserveSig] int ActivateApplication([MarshalAs(UnmanagedType.LPWStr)] string app, [MarshalAs(UnmanagedType.LPWStr)] string args, uint options, out uint pid);
}
public static class MsixActivation {
 public static uint Start(string app) {
  var manager = (IActivationManager)Activator.CreateInstance(Type.GetTypeFromCLSID(new Guid("45BA127D-10A8-46EA-8AB7-56EA9078943C")));
  uint pid; int error = manager.ActivateApplication(app, "--diagnostic", 0, out pid);
  Marshal.ThrowExceptionForHR(error); return pid;
 }
}
'@
    $activationPid = [MsixActivation]::Start($app.PackageFamilyName + '!Cytellect')
    $ready = $false
    $diagnosticPaths = @((Join-Path $userRoot 'settings/msix-diagnostic.txt'),
        (Join-Path $env:LOCALAPPDATA ('Packages/' + $app.PackageFamilyName + '/LocalCache/Local/Cytellect/settings/msix-diagnostic.txt')))
    for ($attempt=0; $attempt -lt 60; $attempt++) {
        try {
            $info = Invoke-RestMethod 'http://127.0.0.1:8765/v1/local/setup' -TimeoutSec 2
            if ($info.ready) { $ready=$true; break }
        } catch { Start-Sleep -Seconds 1 }
        $diagnostic=@($diagnosticPaths | Where-Object {Test-Path -LiteralPath $_} | ForEach-Object {Get-Content -LiteralPath $_ -Raw}) -join ';'
        if ($diagnostic -cmatch '^[a-zA-Z0-9_=;\r\n-]+$') {
            $receipt.startup_diagnostic=$diagnostic
            if ($diagnostic -match 'phase=(native_failed|python_exited)') { break }
        }
    }
    if (-not $ready) {
        if ($receipt.Contains('startup_diagnostic')) { Write-Output ('MSIX startup diagnostic: ' + $receipt.startup_diagnostic) }
        throw 'msix_ci_activation_failed'
    }
    $receipt.activation = $true
    if ($info.retention_mode -ne 'manual' -or -not (Test-Path -LiteralPath (Join-Path $userRoot 'data/.manual-workspace-retention'))) {
        throw 'msix_ci_retention_virtualized'
    }
    $receipt.manual_retention=$true
    # WindowsApps' interpreters are not standalone tools. Run the unchanged
    # browser/reference harness in the package context through Microsoft's
    # debugging cmdlet, without adding an interpreter alias to the product.
    $inside=Join-Path $repo 'scripts/verify_msix_inside.ps1'
    $contextPath=Join-Path $WorkRoot 'inside-context.json'
    @{schema='cytellect-msix-ci-context/1';hosted_runner_verified=$true;source_commit=$env:GITHUB_SHA
        parent_process_id=$PID;parent_created=(Get-Process -Id $PID).StartTime.ToUniversalTime().Ticks.ToString()} |
        ConvertTo-Json | Set-Content -LiteralPath $contextPath -Encoding utf8
    $arguments=@('-NoProfile','-NonInteractive','-WindowStyle','Hidden','-ExecutionPolicy','Bypass',
        '-File',$inside,'-AppRoot',$installed,'-DataRoot',(Join-Path $userRoot 'data'),
        '-WorkRoot',$WorkRoot,'-RepoRoot',$repo,'-NodeExecutable',(Get-Command node).Source,
        '-BrowserCache',(Join-Path $env:LOCALAPPDATA 'ms-playwright'),'-ContextPath',$contextPath,
        '-ExpectedSource',$env:GITHUB_SHA)
    if (@($arguments | Where-Object {$_ -match '["\r\n]'}).Count) { throw 'msix_ci_invalid_arguments' }
    $commandArguments=($arguments | ForEach-Object {'"'+$_+'"'}) -join ' '
    Invoke-CommandInDesktopPackage -PackageFamilyName $app.PackageFamilyName -AppId Cytellect `
        -Command (Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe') `
        -Args $commandArguments -PreventBreakaway | Out-Null
    $insideReceipt=Join-Path $WorkRoot 'inside-receipt.json'
    for ($attempt=0;$attempt -lt 1800;$attempt++) {
        if (Test-Path -LiteralPath $insideReceipt) { break }
        Start-Sleep -Seconds 1
    }
    if (-not (Test-Path -LiteralPath $insideReceipt)) { throw 'msix_ci_inside_timeout' }
    $insideResult=Get-Content -LiteralPath $insideReceipt -Raw | ConvertFrom-Json
    $receipt.fiji=$insideResult.fiji
    $receipt.public_browser=$insideResult.public_browser
    $receipt.numerical_replay=$insideResult.numerical_replay
    if (-not $insideResult.passed) {
        $receipt.failed_phase=$insideResult.phase
        throw ('msix_ci_inside_failed_'+$insideResult.phase)
    }
    $windows=@(Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq (Join-Path $installed 'runtime/pythonw.exe') -and $_.MainWindowHandle -ne 0 })
    if ($windows.Count -ne 1 -or -not $windows[0].CloseMainWindow()) { throw 'msix_ci_stop_window_missing' }
    for ($attempt=0; $attempt -lt 30; $attempt++) {
        if (-not (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue)) { $receipt.stopped=$true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $receipt.stopped) { throw 'msix_ci_listener_remained' }
    Remove-AppxPackage -Package $app.PackageFullName
    $app=$null
    if ((Get-Content -LiteralPath $sentinel -Raw) -cne 'generated retention fixture' -or
        -not (Test-Path -LiteralPath (Join-Path $userRoot 'data/cytellect.sqlite'))) { throw 'msix_ci_uninstall_removed_data' }
    $receipt.uninstall_retention=$true
    Add-AppxPackage -Path $signed
    $app=Get-AppxPackage -Name $identity
    if (-not $app -or (Get-Content -LiteralPath $sentinel -Raw) -cne 'generated retention fixture') { throw 'msix_ci_reinstall_failed' }
    $receipt.reinstall=$true
} finally {
    if ($app) {
        # Exact installed-path matches only; never terminate a shared Python.
        Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq (Join-Path $app.InstallLocation 'runtime/pythonw.exe') } | Stop-Process -Force
        Remove-AppxPackage -Package $app.PackageFullName -ErrorAction Continue
    }
    if ($certificate) {
        Remove-Item -LiteralPath ('Cert:\CurrentUser\My\' + $certificate.Thumbprint) -ErrorAction Continue
        Remove-Item -LiteralPath ('Cert:\LocalMachine\TrustedPeople\' + $certificate.Thumbprint) -ErrorAction Continue
    }
    $receipt | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $WorkRoot 'receipt.json') -Encoding utf8
}
