# Functions only. Explicit setup supplies Get-SafeChild, Update-SetupStatus,
# Invoke-SetupProcess and the pinned Python runtime helpers. No system Python,
# PATH, registry or application-control change is made.
Set-StrictMode -Version Latest

function Assert-CellposeVenv([string]$Runtime, $Specification) {
    # A Python 3.12 venv copies the signed PSF launchers from Lib/venv/scripts/nt.
    foreach ($name in @('python.exe', 'pythonw.exe')) {
        $original = @($Specification.python.launchers | Where-Object { $_.path -ceq ('Lib/venv/scripts/nt/' + $name) })
        if ($original.Count -ne 1) { throw 'cellpose_runtime_lock_invalid' }
        Assert-PythonRuntimeLaunchers $Runtime @{ launchers = @(@{ path = ('Scripts/' + $name); sha256 = $original[0].sha256 }) }
    }
}

function Install-CellposeRuntime([string]$Root, [string]$App, [string]$AppPython, [string]$Uv, [hashtable]$Environment) {
    $specification = Get-Content -LiteralPath (Get-SafeChild $App 'engines/cellpose/windows-python.lock.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $lock = Get-Content -LiteralPath (Get-SafeChild $App 'engines/cellpose/runtime.lock.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($specification.schema -cne 'cytellect-cellpose-windows-python/1' -or $specification.platform -cne 'windows-x64' -or
        $specification.python.version -cnotmatch '^3\.12\.[0-9]+$' -or
        $lock.schema -cne 'cytellect-cellpose-runtime/1' -or $lock.python -cne '3.12') {
        throw 'cellpose_runtime_lock_invalid'
    }
    Assert-RuntimeDigest $lock.requirements_sha256
    Assert-RuntimeDigest $lock.model.sha256
    # The official signed PSF 3.12 ZIP replaces the former manual prerequisite.
    $archive = Get-PythonRuntimeArchive $Root $specification.python
    $base = Get-SafeChild $Root ('runtimes/cellpose-python-' + $specification.python.version + '-' +
        $specification.python.sha256.Substring(0, 16))
    [IO.Directory]::CreateDirectory($base) | Out-Null
    $null = Read-PinnedRuntimeZip $archive $base $specification.python.expanded_bytes $specification.python.file_count
    Assert-PythonRuntimeLaunchers $base $specification.python
    $runtime = Get-SafeChild $Root ('runtimes/cellpose-' + $lock.requirements_sha256.Substring(0, 16))
    $models = Get-SafeChild $Root ('models/cellpose-' + $lock.model.sha256.Substring(0, 16))
    Update-SetupStatus 'install_cellpose' 'Cellpose（核小体・細胞の自動検出）を準備しています。初回は約2 GBを取得するため、数分から数十分かかります…'
    Invoke-SetupProcess $AppPython @('-B', 'scripts/cellpose_setup.py', $runtime, '--model-cache', $models,
        '--python', (Get-SafeChild $base 'python.exe'), '--uv', $Uv) $App $Environment 5400 -UvProcess
    Assert-CellposeVenv $runtime $specification
    Update-SetupStatus 'verify_cellpose' 'Cellposeの読み込みを確認しています…'
    $python = Get-SafeChild $runtime 'Scripts/python.exe'
    # The runner imports Torch and Cellpose exactly as an analysis job does. Its
    # fixed-code receipt distinguishes an application-control DLL rejection.
    $check = Get-SafeChild $Root 'setup-cache/cellpose-self-check.json'
    if (Test-Path -LiteralPath $check) { Remove-Item -LiteralPath $check }
    try {
        Invoke-SetupProcess $python @('-I', '-B', 'engines/cellpose/runner.py', '--self-check', $check) $App @{} 600
    } catch {
        if ($_.Exception.Message -ne 'setup_cancelled' -and (Test-Path -LiteralPath $check) -and
            (Get-Content -LiteralPath $check -Raw -Encoding UTF8 | ConvertFrom-Json).error -ceq 'windows_application_control_blocked') {
            $failure = [InvalidOperationException]::new('windows_application_control_blocked')
            $failure.Data['CytellectSetupFailure'] = 'windows_application_control_blocked'
            throw $failure
        }
        throw
    }
    $settings = Get-SafeChild $Root 'settings'
    [IO.Directory]::CreateDirectory($settings) | Out-Null
    $configuration = [ordered]@{ schema = 'cytellect-cellpose-local/1'; python = $python; model_dir = $models }
    $path = Get-SafeChild $Root 'settings/cellpose.json'
    $temporary = Get-SafeChild $Root ('settings/cellpose-' + [Guid]::NewGuid().ToString('N') + '.json')
    [IO.File]::WriteAllText($temporary, ($configuration | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
    if ([IO.File]::Exists($path)) { [IO.File]::Replace($temporary, $path, [NullString]::Value) }
    else { [IO.File]::Move($temporary, $path) }
    return [ordered]@{ status = 'ready'; python_version = $specification.python.version
        python_sha256 = $specification.python.sha256; requirements_sha256 = $lock.requirements_sha256
        model_sha256 = $lock.model.sha256 }
}
