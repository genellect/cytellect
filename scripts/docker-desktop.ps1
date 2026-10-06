param(
    [ValidateSet('Start', 'Open', 'Stop', 'Status', 'Invite', 'Build')][string]$Action = 'Start',
    [string]$ProposalConfig = $env:CYTELLECT_PROPOSAL_OPERATOR_CONFIG
)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$dockerCommand = Get-Command docker.exe -ErrorAction SilentlyContinue
$dockerExe = if ($dockerCommand) { $dockerCommand.Source } else { Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe' }
if (-not (Test-Path -LiteralPath $dockerExe)) { throw 'Install and start Docker Desktop with Linux containers first.' }
$trackedEnvironment = @('CYTELLECT_RUNTIME_DIR', 'CYTELLECT_PROPOSAL_URL', 'CYTELLECT_PROPOSAL_TOKEN_FILE', 'CYTELLECT_CODE_REVISION')
$priorEnvironment = @{}
foreach ($name in $trackedEnvironment) { $priorEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
$composeArgs = @('compose', '--project-name', 'cytellect-human-e2e', '-f', (Join-Path $repoRoot 'compose.yaml'), '-f', (Join-Path $repoRoot 'infra\compose.desktop.yaml'))
try {
    # The Desktop overlay uses a Docker-managed Linux volume instead of this base bind.
    $env:CYTELLECT_RUNTIME_DIR = '/unused'
    if ($ProposalConfig) {
        $configPath = [IO.Path]::GetFullPath($ProposalConfig)
        if ($configPath.StartsWith($repoRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Keep the operator configuration outside the repository.' }
        $operatorConfig = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
        $relay = [Uri]$operatorConfig.url
        if ($relay.Scheme -ne 'https' -or $relay.UserInfo -or $relay.Query -or $relay.Fragment -or $relay.AbsolutePath -ne '/') { throw 'Use the approved HTTPS relay origin.' }
        $tokenPath = [IO.Path]::GetFullPath([string]$operatorConfig.tokenFile)
        if (-not [IO.Path]::IsPathFullyQualified([string]$operatorConfig.tokenFile) -or $tokenPath.StartsWith($repoRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or -not (Test-Path -LiteralPath $tokenPath -PathType Leaf)) { throw 'The device-token file must exist outside the repository.' }
        $env:CYTELLECT_PROPOSAL_URL = $relay.GetLeftPart([UriPartial]::Authority)
        $env:CYTELLECT_PROPOSAL_TOKEN_FILE = $tokenPath
        $composeArgs += @('-f', (Join-Path $repoRoot 'infra\compose.proposal.yaml'))
    }
    $sourceState = & git -c "safe.directory=$repoRoot" -C $repoRoot status --porcelain
    if ($LASTEXITCODE -eq 0 -and -not $sourceState) {
        $env:CYTELLECT_CODE_REVISION = (& git -c "safe.directory=$repoRoot" -C $repoRoot rev-parse HEAD).Trim()
    } else { $env:CYTELLECT_CODE_REVISION = '' }
    & $dockerExe info --format '{{.ServerVersion}}' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop and wait until its Linux engine is running.' }
    switch ($Action) {
        'Start' { & $dockerExe @composeArgs up -d --build --wait --wait-timeout 180 }
        'Open' { & $dockerExe @composeArgs up -d --wait --wait-timeout 180 }
        'Stop' { & $dockerExe @composeArgs stop }
        'Status' { & $dockerExe @composeArgs ps }
        'Build' { & $dockerExe @composeArgs build }
        # Use only in the owner's private terminal. Never capture this in CI or shared logs.
        'Invite' { & $dockerExe @composeArgs exec -T api cytellect invite --hours 24 }
    }
    if ($LASTEXITCODE -ne 0) { throw "Docker action failed: $Action" }
    if ($Action -in @('Start', 'Open')) {
        Write-Host 'Cytellect: http://127.0.0.1:3087/'
        if ($Action -eq 'Open') { Start-Process 'http://127.0.0.1:3087/' }
    }
} finally {
    foreach ($name in $trackedEnvironment) { [Environment]::SetEnvironmentVariable($name, $priorEnvironment[$name], 'Process') }
}
