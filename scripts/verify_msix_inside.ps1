# CI harness only. Launched with Invoke-CommandInDesktopPackage -PreventBreakaway
# so Python, Node and their children use the installed package's execution context.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$AppRoot,
      [Parameter(Mandatory=$true)][string]$DataRoot,
      [Parameter(Mandatory=$true)][string]$WorkRoot,
      [Parameter(Mandatory=$true)][string]$RepoRoot,
      [Parameter(Mandatory=$true)][string]$NodeExecutable,
      [Parameter(Mandatory=$true)][string]$BrowserCache,
      [Parameter(Mandatory=$true)][string]$ExpectedSource)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $RepoRoot
$python=Join-Path $AppRoot 'runtime/python.exe'
$result=[ordered]@{schema='cytellect-msix-inside/1';phase='start';passed=$false
    fiji=$false;public_browser=$false;numerical_replay=$false}
try {
    $result.phase='hosted_runner_guard'
    if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted') {
        throw 'msix_acceptance_requires_disposable_hosted_runner'
    }
    $env:CYTELLECT_ENGINE_ASSETS=Join-Path $AppRoot 'engines/fiji'
    $env:CYTELLECT_CELLPOSE_ASSETS=Join-Path $AppRoot 'engines/cellpose'
    $env:PYTHONPATH=$null
    $env:PYTHONHOME=$null
    $env:PYTHONDONTWRITEBYTECODE='1'
    $result.phase='fiji'
    & $python -I -B -m cytellect_analysis.install_check --fiji (Join-Path $AppRoot 'fiji') --scratch $WorkRoot --result (Join-Path $WorkRoot 'fiji.json') *> (Join-Path $WorkRoot 'fiji.private.log')
    if ($LASTEXITCODE -ne 0) { throw 'msix_ci_fiji_failed' }
    $result.fiji=$true
    $result.phase='public_inputs'
    $bbbc=Join-Path $WorkRoot 'public-bbbc007'
    $inputs=Join-Path $WorkRoot 'workspace-inputs'
    & $python -I -B scripts/public_bbbc007.py --data-dir $bbbc --download *> (Join-Path $WorkRoot 'public-download.private.log')
    if ($LASTEXITCODE -ne 0) { throw 'msix_ci_public_download_failed' }
    & $python -I -B scripts/prepare_workspace_bbbc007.py --data-dir $bbbc --output $inputs *> (Join-Path $WorkRoot 'public-inputs.private.log')
    if ($LASTEXITCODE -ne 0) { throw 'msix_ci_public_inputs_failed' }
    $env:CYTELLECT_TEST_LOCAL='1'
    $env:CYTELLECT_WEB_URL='http://127.0.0.1:8765'
    $env:CYTELLECT_TEST_API_ORIGIN=$env:CYTELLECT_WEB_URL
    $env:CYTELLECT_TEST_PYTHON=$python
    $env:CYTELLECT_TEST_DATA_DIR=$DataRoot
    $env:CYTELLECT_REAL_INPUTS=$inputs
    $env:CYTELLECT_REAL_OUTPUT=Join-Path $WorkRoot 'browser-evidence'
    $env:CYTELLECT_REQUIRE_REAL_FIJI='1'
    $env:CYTELLECT_COMPARISON_REAL='1'
    $env:PLAYWRIGHT_JSON_OUTPUT_FILE=Join-Path $WorkRoot 'browser.json'
    $env:PLAYWRIGHT_BROWSERS_PATH=$BrowserCache
    $result.phase='public_browser'
    Set-Location -LiteralPath (Join-Path $RepoRoot 'apps/web')
    & $NodeExecutable node_modules/@playwright/test/cli.js test tests/workspace-real-fiji.spec.ts tests/workspace-comparison-real.spec.ts --reporter=json *> (Join-Path $WorkRoot 'browser.private.log')
    Set-Location -LiteralPath $RepoRoot
    if ($LASTEXITCODE -ne 0) { throw 'msix_ci_browser_failed' }
    $browser=Get-Content -LiteralPath $env:PLAYWRIGHT_JSON_OUTPUT_FILE -Raw | ConvertFrom-Json
    if ($browser.stats.expected -ne 2 -or $browser.stats.skipped -ne 0 -or $browser.stats.unexpected -ne 0) {
        throw 'msix_ci_browser_incomplete'
    }
    $result.public_browser=$true
    $result.phase='numerical_replay'
    & $python -I -B scripts/verify_installed_regions.py --app $AppRoot --expected-source $ExpectedSource --origin $env:CYTELLECT_WEB_URL --output (Join-Path $WorkRoot 'numerical') *> (Join-Path $WorkRoot 'numerical.private.log')
    if ($LASTEXITCODE -ne 0) { throw 'msix_ci_numerical_failed' }
    $result.numerical_replay=$true
    $result.phase='complete'
    $result.passed=$true
} catch {
    # Fixed phase only; test errors can include generated tokens or paths.
    $result.passed=$false
} finally {
    $temporary=Join-Path $WorkRoot 'inside-receipt.partial'
    $result | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $temporary -Encoding utf8
    Move-Item -LiteralPath $temporary -Destination (Join-Path $WorkRoot 'inside-receipt.json')
}
