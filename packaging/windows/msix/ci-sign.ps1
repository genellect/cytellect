# Signs an MSIX with a throwaway certificate whose subject is the package publisher and trusts it
# on this disposable runner only, so the package can be installed for acceptance. The Store signs
# the submitted package itself; with -Output the unsigned original is left unchanged and a signed
# copy with otherwise identical contents is written for the acceptance run.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Msix,
    [Parameter(Mandatory)][string]$Publisher,
    [string]$Output
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -cne 'true' -or $env:RUNNER_ENVIRONMENT -cne 'github-hosted') {
    throw 'MSIX test signing runs only on a disposable GitHub-hosted Windows runner'
}
if (-not $Publisher.StartsWith('CN=')) { throw 'The package publisher must be a distinguished name' }
$target = $Msix
if ($Output) {
    Copy-Item -LiteralPath $Msix -Destination $Output
    $target = $Output
}
$sign = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\10.*\x64\signtool.exe" |
    Sort-Object { [version]$_.Directory.Parent.Name } -Descending | Select-Object -First 1
if (-not $sign) { throw 'Windows SDK SignTool missing' }
$cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject $Publisher -CertStoreLocation 'Cert:\CurrentUser\My' -NotAfter (Get-Date).AddDays(2)
try {
    & $sign.FullName sign /sha1 $cert.Thumbprint /fd SHA256 $target
    if ($LASTEXITCODE -ne 0) { throw 'Test MSIX signing failed' }
    $public = Join-Path $env:RUNNER_TEMP 'cytellect-msix-test.cer'
    Export-Certificate -Cert $cert -FilePath $public | Out-Null
    Import-Certificate -FilePath $public -CertStoreLocation 'Cert:\LocalMachine\TrustedPeople' | Out-Null
} finally {
    Remove-Item -LiteralPath "Cert:\CurrentUser\My\$($cert.Thumbprint)" -DeleteKey
}
