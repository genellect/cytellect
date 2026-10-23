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
  uint pid; int error = manager.ActivateApplication(app, null, 0, out pid);
  Marshal.ThrowExceptionForHR(error); return pid;
 }
}
'@
    $activationPid = [MsixActivation]::Start($app.PackageFamilyName + '!Cytellect')
    $ready = $false
    for ($attempt=0; $attempt -lt 60; $attempt++) {
        try {
            $info = Invoke-RestMethod 'http://127.0.0.1:8765/v1/local/setup'
            if ($info.ready) { $ready=$true; break }
        } catch { Start-Sleep -Seconds 1 }
    }
    if (-not $ready) { throw 'msix_ci_activation_failed' }
    $receipt.activation = $true
    if ($info.retention_mode -ne 'manual' -or -not (Test-Path -LiteralPath (Join-Path $userRoot 'data/.manual-workspace-retention'))) {
        throw 'msix_ci_retention_virtualized'
    }
    $receipt.manual_retention=$true
    $env:CYTELLECT_ENGINE_ASSETS = Join-Path $installed 'engines/fiji'
    $env:CYTELLECT_CELLPOSE_ASSETS = Join-Path $installed 'engines/cellpose'
    $env:PYTHONPATH=$null
    $env:PYTHONHOME=$null
    & $python -I -B -m cytellect_analysis.install_check --fiji (Join-Path $installed 'fiji') --scratch $WorkRoot --result (Join-Path $WorkRoot 'fiji.json')
    if ($LASTEXITCODE -ne 0) { throw 'msix_ci_fiji_failed' }
    $receipt.fiji=$true
    $bbbc = Join-Path $WorkRoot 'public-bbbc007'
    $inputs = Join-Path $WorkRoot 'workspace-inputs'
    & $python -I -B scripts/public_bbbc007.py --data-dir $bbbc --download
    if ($LASTEXITCODE -ne 0) { throw 'msix_ci_public_download_failed' }
    & $python -I -B scripts/prepare_workspace_bbbc007.py --data-dir $bbbc --output $inputs
    if ($LASTEXITCODE -ne 0) { throw 'msix_ci_public_inputs_failed' }
    $env:CYTELLECT_TEST_LOCAL='1'
    $env:CYTELLECT_WEB_URL='http://127.0.0.1:8765'
    $env:CYTELLECT_TEST_API_ORIGIN=$env:CYTELLECT_WEB_URL
    $env:CYTELLECT_TEST_PYTHON=$python
    $env:CYTELLECT_TEST_DATA_DIR=Join-Path $userRoot 'data'
    $env:CYTELLECT_REAL_INPUTS=$inputs
    $env:CYTELLECT_REAL_OUTPUT=Join-Path $WorkRoot 'browser-evidence'
    $env:CYTELLECT_REQUIRE_REAL_FIJI='1'
    $env:CYTELLECT_COMPARISON_REAL='1'
    $env:PLAYWRIGHT_JSON_OUTPUT_FILE=Join-Path $WorkRoot 'browser.json'
    pnpm --filter @cytellect/web test:e2e tests/workspace-real-fiji.spec.ts tests/workspace-comparison-real.spec.ts --reporter=json
    if ($LASTEXITCODE -ne 0) { throw 'msix_ci_browser_failed' }
    $browser=Get-Content -LiteralPath $env:PLAYWRIGHT_JSON_OUTPUT_FILE -Raw | ConvertFrom-Json
    if ($browser.stats.expected -ne 2 -or $browser.stats.skipped -ne 0 -or $browser.stats.unexpected -ne 0) {
        throw 'msix_ci_browser_incomplete'
    }
    $receipt.public_browser=$true
    & $python -I -B scripts/verify_installed_regions.py --app $installed --expected-source $env:GITHUB_SHA --origin $env:CYTELLECT_WEB_URL --output (Join-Path $WorkRoot 'numerical')
    if ($LASTEXITCODE -ne 0) { throw 'msix_ci_numerical_failed' }
    $receipt.numerical_replay=$true
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
