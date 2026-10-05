param([ValidateSet('Start', 'Stop', 'Status', 'Invite', 'Build')][string]$Action = 'Start')
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$dockerCommand = Get-Command docker.exe -ErrorAction SilentlyContinue
$dockerExe = if ($dockerCommand) { $dockerCommand.Source } else { Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe' }
if (-not (Test-Path -LiteralPath $dockerExe)) { throw 'Install and start Docker Desktop with Linux containers first.' }
$previousRuntime = $env:CYTELLECT_RUNTIME_DIR
# The overlay replaces this base bind mount with a Docker-managed Linux volume.
$env:CYTELLECT_RUNTIME_DIR = '/unused'
$composeArgs = @('compose', '--project-name', 'cytellect-human-e2e', '-f', (Join-Path $repoRoot 'compose.yaml'), '-f', (Join-Path $repoRoot 'infra\compose.desktop.yaml'))
try {
    & $dockerExe info --format '{{.ServerVersion}}' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop and wait until its Linux engine is running.' }
    switch ($Action) {
        'Start' { & $dockerExe @composeArgs up -d --build --wait --wait-timeout 120 }
        'Stop' { & $dockerExe @composeArgs stop }
        'Status' { & $dockerExe @composeArgs ps }
        'Build' { & $dockerExe @composeArgs build }
        # Run only in a private operator terminal. Never capture this in CI/logs.
        'Invite' { & $dockerExe @composeArgs exec -T api cytellect invite --hours 24 }
    }
    if ($LASTEXITCODE -ne 0) { throw "Docker action failed: $Action" }
    if ($Action -eq 'Start') { Write-Host 'Cytellect: http://127.0.0.1:3087/' }
} finally {
    $env:CYTELLECT_RUNTIME_DIR = $previousRuntime
}
