#requires -Version 7.0
param(
    [ValidateSet('Start', 'Open', 'Stop', 'Status', 'Invite', 'Build')][string]$Action = 'Start',
    [Parameter(Mandatory)][string]$ReleaseManifest,
    [Parameter(Mandatory)][string]$ManifestSha256,
    [Parameter(Mandatory)][string]$InstallationDirectory
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent

function Require($Condition, [string]$Code) { if (-not $Condition) { throw $Code } }
function Keys($Object, [string[]]$Expected) {
    Require ($Object -is [System.Collections.IDictionary]) 'release_object_required'
    Require ((@($Object.Keys | Sort-Object) -join '|') -ceq (@($Expected | Sort-Object) -join '|')) 'release_fields_invalid'
}
function Hash([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Sha($Value) { Require ($Value -is [string] -and $Value -cmatch '^[0-9a-f]{64}$') 'release_sha_invalid' }
function PlainPath([string]$Path) {
    Require ([IO.Path]::IsPathFullyQualified($Path)) 'absolute_path_required'
    $full = [IO.Path]::GetFullPath($Path).TrimEnd([IO.Path]::DirectorySeparatorChar)
    Require ([IO.Path]::IsPathFullyQualified($full)) 'filesystem_root_refused'
    for ($part = $full; $part; $part = Split-Path $part -Parent) {
        if (Test-Path -LiteralPath $part) {
            Require (-not ((Get-Item -LiteralPath $part -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) 'linked_path_refused'
        }
    }
    return $full
}
function Model($Value) {
    Keys $Value @('id', 'repo', 'revision', 'file', 'sha256', 'bytes')
    Require ($Value.id -cmatch '^[a-zA-Z0-9_-]+$') 'model_id_invalid'
    Require ($Value.repo -cmatch '^[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+$') 'model_repo_invalid'
    Require ($Value.revision -cmatch '^[0-9a-f]{40}$') 'model_revision_invalid'
    Require ($Value.file -cmatch '^[a-zA-Z0-9_-][a-zA-Z0-9_./-]*$' -and $Value.file -notmatch '\.\.') 'model_file_invalid'
    Sha $Value.sha256
    Require ($Value.bytes -is [long] -and $Value.bytes -gt 0) 'model_bytes_invalid'
}
function EnvironmentMap($Entries) {
    $map = @{}
    foreach ($entry in @($Entries)) {
        $parts = $entry.Split('=', 2)
        Require ($parts.Count -eq 2 -and -not $map.ContainsKey($parts[0])) 'duplicate_container_environment'
        $map[$parts[0]] = $parts[1]
    }
    return $map
}
function Docker([string[]]$Arguments) {
    # Never print inspect payloads: labels/environment may contain private metadata.
    $result = & $script:dockerExe @Arguments 2>$null
    Require ($LASTEXITCODE -eq 0) ('docker_failed_' + $Arguments[0])
    return ($result -join "`n")
}
function JsonDocker([string[]]$Arguments) { return ,(Docker $Arguments | ConvertFrom-Json -AsHashtable -NoEnumerate) }
function WriteNew([string]$Path, [string]$Text) {
    $stream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $bytes = [Text.Encoding]::UTF8.GetBytes($Text); $stream.Write($bytes); $stream.Flush($true) }
    finally { $stream.Dispose() }
}

# Every rejection here happens before Docker, directory creation or lock acquisition.
Require ($Action -in @('Start', 'Open', 'Stop', 'Status')) 'release_action_unsupported'
Sha $ManifestSha256
$manifestPath = PlainPath $ReleaseManifest
Require ((Hash $manifestPath) -ceq $ManifestSha256) 'release_manifest_hash_mismatch'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json -AsHashtable
Keys $manifest @('schema_version', 'source_commit', 'platform', 'retention', 'runtime_contract', 'files', 'images', 'baseline', 'candidate')
Require ($manifest.schema_version -eq 1) 'release_schema_unsupported'
Require ($manifest.source_commit -cmatch '^[0-9a-f]{40}$') 'release_source_invalid'
Require ($manifest.platform -ceq 'linux/amd64') 'release_platform_unsupported'
Require ($manifest.retention -ceq 'manual' -and $manifest.runtime_contract -ceq 'manual-v1') 'manual_release_required'
Model $manifest.baseline
Require ($manifest.baseline.id -ceq 'cpsam_v2') 'baseline_default_required'
if ($null -ne $manifest.candidate) {
    Keys $manifest.candidate @('model', 'status', 'limits')
    Model $manifest.candidate.model
    Require ($manifest.candidate.status -ceq 'experimental' -and $manifest.candidate.model.id -cne 'cpsam_v2') 'experimental_candidate_required'
    Require ($manifest.candidate.limits -is [string] -and $manifest.candidate.limits.Length -gt 0) 'candidate_limits_required'
}
$launchFiles = @('scripts/docker-desktop.ps1', 'scripts/docker-lab-release.ps1', 'infra/compose.release.yaml', 'engines/cellpose/runtime.lock.json')
Keys $manifest.files $launchFiles
foreach ($file in $launchFiles) {
    Sha $manifest.files[$file]
    $path = PlainPath (Join-Path $repoRoot $file)
    Require ((Hash $path) -ceq $manifest.files[$file]) 'release_launch_file_changed'
}
$baseline = (Get-Content -LiteralPath (Join-Path $repoRoot 'engines/cellpose/runtime.lock.json') -Raw | ConvertFrom-Json -AsHashtable).model
Require ($manifest.baseline.id -ceq $baseline.id -and $manifest.baseline.revision -ceq $baseline.revision -and $manifest.baseline.sha256 -ceq $baseline.sha256 -and $manifest.baseline.bytes -eq $baseline.size) 'shipped_baseline_mismatch'
Require (('https://huggingface.co/' + $manifest.baseline.repo + '/resolve/' + $manifest.baseline.revision + '/' + $manifest.baseline.file) -ceq $baseline.url) 'shipped_baseline_source_mismatch'
Keys $manifest.images @('api', 'worker', 'web')
foreach ($service in @('api', 'worker', 'web')) {
    $pin = $manifest.images[$service]
    Keys $pin @('id', 'repo_digest')
    Require ($pin.id -cmatch '^sha256:[0-9a-f]{64}$') 'release_image_id_required'
    Require ($null -eq $pin.repo_digest -or $pin.repo_digest -cmatch '^[a-z0-9][a-z0-9./:_-]+@sha256:[0-9a-f]{64}$') 'release_digest_invalid'
}
$install = PlainPath $InstallationDirectory
Require (-not ($install.Equals($repoRoot, [StringComparison]::OrdinalIgnoreCase) -or $install.StartsWith($repoRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase))) 'private_installation_outside_checkout_required'

# Explicit environment isolation applies even to read-only/status and stop operations.
$prior = @{}
$lock = $null
try {
    foreach ($item in Get-ChildItem Env:) {
        if ($item.Name -match '^(COMPOSE_|CYTELLECT_|DOCKER_)') { $prior[$item.Name] = $item.Value }
    }
    # Do not redirect to a remote Docker engine through inherited context/host flags.
    Require (-not ($prior.Keys | Where-Object { $_ -match '^DOCKER_' })) 'docker_environment_override_refused'
    foreach ($name in $prior.Keys) { [Environment]::SetEnvironmentVariable($name, $null, 'Process') }
    $dockerExe = (Get-Command docker.exe -ErrorAction Stop).Source
    $context = JsonDocker @('context', 'inspect')
    Require ($context.Count -eq 1 -and $context[0].Endpoints.docker.Host -match '^npipe://') 'local_desktop_engine_required'
    $info = JsonDocker @('info', '--format', '{{json .}}')
    Require ($info.OSType -ceq 'linux' -and $info.Architecture -in @('x86_64', 'amd64')) 'linux_amd64_engine_required'
    $images = @{}
    foreach ($service in @('api', 'worker', 'web')) {
        $pin = $manifest.images[$service]
        $image = (JsonDocker @('image', 'inspect', $pin.id))[0]
        $images[$service] = $image
        Require ($image.Id -ceq $pin.id -and $image.Os -ceq 'linux' -and $image.Architecture -ceq 'amd64') 'local_image_identity_mismatch'
        if ($pin.repo_digest) { Require ($pin.repo_digest -cin @($image.RepoDigests)) 'local_image_digest_mismatch' }
        $labels = $image.Config.Labels
        Require ($labels['org.opencontainers.image.revision'] -ceq $manifest.source_commit) 'image_source_revision_mismatch'
        Require ($labels['io.cytellect.lab-contract'] -ceq 'manual-v1') 'image_manual_capability_missing'
        Require ($labels['io.cytellect.baseline-sha256'] -ceq $manifest.baseline.sha256) 'image_baseline_mismatch'
        $candidateSha = if ($null -eq $manifest.candidate) { 'none' } else { $manifest.candidate.model.sha256 }
        Require ($labels['io.cytellect.candidate-sha256'] -ceq $candidateSha) 'image_candidate_mismatch'
        Require (-not $image.Config['Volumes']) 'image_implicit_volume_refused'
        if ($service -eq 'web') {
            Require ($labels['io.cytellect.api-origin'] -ceq 'http://127.0.0.1:8001' -and $labels['io.cytellect.desktop-owner'] -ceq 'true') 'web_build_contract_missing'
        }
    }
    $recordPath = Join-Path $install 'installation.json'
    if (-not (Test-Path -LiteralPath $install)) {
        Require ($Action -in @('Start', 'Open')) 'installation_missing'
        $null = New-Item -ItemType Directory -Path $install
    }
    $null = PlainPath $install
    $lockPath = Join-Path $install 'launcher.lock'
    if (Test-Path -LiteralPath $lockPath) { $null = PlainPath $lockPath }
    $lock = [IO.File]::Open($lockPath, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    if (Test-Path -LiteralPath $recordPath) {
        $null = PlainPath $recordPath
        $record = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json -AsHashtable
        Keys $record @('schema_version', 'installation_id', 'installation_directory', 'project', 'volume', 'manifest_sha256', 'retention')
        Require ($record.schema_version -eq 1 -and $record.installation_id -cmatch '^[0-9a-f]{32}$') 'installation_record_invalid'
        Require ([string]$record.installation_directory -ceq $install) 'installation_directory_mismatch'
        Require ($record.project -ceq ('cytellect-lab-' + $record.installation_id) -and $record.volume -ceq ($record.project + '-research')) 'installation_identity_invalid'
        Require ($record.manifest_sha256 -ceq $ManifestSha256 -and $record.retention -ceq 'manual') 'release_change_requires_backup_update_procedure'
    } else {
        Require ($Action -in @('Start', 'Open')) 'installation_missing'
        Require (@(Get-ChildItem -LiteralPath $install -Force | Where-Object Name -ne 'launcher.lock').Count -eq 0) 'unowned_installation_directory'
        $id = [Guid]::NewGuid().ToString('N')
        $record = @{schema_version=1; installation_id=$id; installation_directory=$install; project="cytellect-lab-$id"; volume="cytellect-lab-$id-research"; manifest_sha256=$ManifestSha256; retention='manual'}
        # Durable reservation precedes any Docker mutation. Torn records fail closed.
        WriteNew $recordPath ($record | ConvertTo-Json)
    }
    $ownership = @{'io.cytellect.installation'=$record.installation_id; 'io.cytellect.manifest'=$ManifestSha256}
    $template = Get-Content -LiteralPath (Join-Path $repoRoot 'infra/compose.release.yaml') -Raw
    Require (-not $template.Contains('$')) 'compose_interpolation_refused'
    $config = $template | ConvertFrom-Json -AsHashtable
    $config.name = $record.project
    $config.volumes.research.name = $record.volume
    foreach ($service in $config.services.Keys) {
        $imageKey = if ($service -eq 'data-init') { 'api' } else { $service }
        $config.services[$service].image = $manifest.images[$imageKey].id
        $config.services[$service].labels = $ownership
        if ($service -in @('api', 'worker')) { $config.services[$service].environment.CYTELLECT_CODE_REVISION = $manifest.source_commit }
    }
    foreach ($network in $config.networks.Keys) {
        $config.networks[$network].name = $record.project + '-' + $network
        $config.networks[$network].labels = $ownership
    }
    $configPath = Join-Path $install 'compose.json'
    $configText = $config | ConvertTo-Json -Depth 30
    if (Test-Path -LiteralPath $configPath) {
        $null = PlainPath $configPath
        Require ((Get-Content -LiteralPath $configPath -Raw) -ceq $configText) 'installation_config_changed'
    } else { WriteNew $configPath $configText }
    $emptyEnv = Join-Path $install 'empty.env'
    if (-not (Test-Path -LiteralPath $emptyEnv)) { WriteNew $emptyEnv '' }
    $null = PlainPath $emptyEnv
    Require ((Get-Item -LiteralPath $emptyEnv).Length -eq 0) 'installation_env_changed'
    $compose = @('compose', '--project-name', $record.project, '--project-directory', $install, '--env-file', $emptyEnv, '-f', $configPath)
    $resolved = JsonDocker ($compose + @('config', '--format', 'json'))
    # Check the effective configuration, not a YAML environment promise.
    Require ((@($resolved.services.Keys | Sort-Object) -join ',') -ceq 'api,data-init,web,worker') 'compose_service_drift'
    foreach ($service in $config.services.Keys) {
        $expected = $config.services[$service]; $actual = $resolved.services[$service]
        Require ($actual.image -ceq $expected.image -and -not $actual.Contains('build') -and -not $actual.Contains('env_file')) 'compose_image_drift'
        foreach ($key in @('environment', 'labels')) {
            $wanted = if ($expected.Contains($key)) { $expected[$key] } else { @{} }
            $found = if ($actual.Contains($key)) { $actual[$key] } else { @{} }
            Keys $found @($wanted.Keys)
            foreach ($name in $wanted.Keys) { Require ([string]$found[$name] -ceq [string]$wanted[$name]) 'compose_environment_drift' }
        }
        $actualMounts = @(if ($actual.Contains('volumes')) { $actual.volumes })
        Require ($actualMounts.Count -eq $(if ($service -eq 'web') { 0 } else { 1 })) 'compose_mount_drift'
        if ($service -ne 'web') { Require ($actual.volumes[0].type -ceq 'volume' -and $actual.volumes[0].source -ceq 'research' -and $actual.volumes[0].target -ceq '/data') 'compose_mount_drift' }
        foreach ($key in @('user', 'platform', 'network_mode', 'read_only', 'restart', 'init', 'pids_limit')) {
            Require ([string]$actual[$key] -ceq [string]$expected[$key]) 'compose_isolation_drift'
        }
        foreach ($key in @('cap_drop', 'cap_add', 'security_opt')) {
            Require ((@($actual[$key]) -join '|') -ceq (@($expected[$key]) -join '|')) 'compose_security_drift'
        }
        if ($service -eq 'worker') { Require ($actual.mem_limit -eq 5368709120) 'compose_resource_drift' }
        if ($service -in @('api', 'web')) {
            Require (@($actual.ports).Count -eq 1) 'compose_port_drift'
            foreach ($key in @('host_ip', 'target', 'published', 'protocol')) { Require ([string]$actual.ports[0][$key] -ceq [string]$expected.ports[0][$key]) 'compose_port_drift' }
        } else { Require (-not $actual['ports']) 'compose_port_drift' }
        $expectedNetworks = if ($expected.Contains('networks')) { @($expected.networks.Keys | Sort-Object) } else { @() }
        $actualNetworks = if ($actual.Contains('networks')) { @($actual.networks.Keys | Sort-Object) } else { @() }
        Require (($expectedNetworks -join '|') -ceq ($actualNetworks -join '|')) 'compose_network_drift'
    }
    Require ($resolved.volumes.research.external -eq $true -and $resolved.volumes.research.name -ceq $record.volume) 'compose_volume_drift'
    Keys $resolved.networks @('private', 'edge')
    foreach ($network in $config.networks.Keys) {
        Require ($resolved.networks[$network].name -ceq $config.networks[$network].name) 'compose_network_drift'
        Require ([bool]$resolved.networks[$network]['internal'] -eq [bool]$config.networks[$network]['internal']) 'compose_network_drift'
    }

    function Owned($Labels) {
        Require ($Labels['io.cytellect.installation'] -ceq $record.installation_id -and $Labels['io.cytellect.manifest'] -ceq $ManifestSha256) 'unowned_docker_resource'
    }
    function Containers {
        $ids = Docker @('ps', '-aq', '--filter', ('label=com.docker.compose.project=' + $record.project))
        $items = @()
        foreach ($id in @($ids -split "`n" | Where-Object { $_ })) {
            $item = (JsonDocker @('container', 'inspect', $id))[0]
            Owned $item.Config.Labels
            $service = $item.Config.Labels['com.docker.compose.service']
            Require ($config.services.Contains($service)) 'unexpected_installation_service'
            Require (@($items | Where-Object { $_.Config.Labels['com.docker.compose.service'] -ceq $service }).Count -eq 0) 'duplicate_installation_service'
            Require ($item.Image -ceq $config.services[$service].image) 'container_image_mismatch'
            $mounts = @($item.Mounts)
            Require ($mounts.Count -eq $(if ($service -eq 'web') { 0 } else { 1 })) 'container_mount_mismatch'
            if ($service -ne 'web') { Require ($mounts[0].Type -ceq 'volume' -and $mounts[0].Name -ceq $record.volume -and $mounts[0].Destination -ceq '/data') 'container_mount_mismatch' }
            if ($service -in @('api', 'worker')) {
                Require ('CYTELLECT_WORKSPACE_RETENTION_MODE=manual' -cin $item.Config.Env -and ('CYTELLECT_CODE_REVISION=' + $manifest.source_commit) -cin $item.Config.Env) 'container_runtime_mismatch'
            }
            $expected = $config.services[$service]
            $imageKey = if ($service -eq 'data-init') { 'api' } else { $service }
            $expectedEnv = EnvironmentMap $images[$imageKey].Config.Env
            if ($expected.Contains('environment')) {
                foreach ($name in $expected.environment.Keys) { $expectedEnv[$name] = [string]$expected.environment[$name] }
            }
            $actualEnv = EnvironmentMap $item.Config.Env
            Keys $actualEnv @($expectedEnv.Keys)
            foreach ($name in $expectedEnv.Keys) { Require ($actualEnv[$name] -ceq $expectedEnv[$name]) 'container_environment_mismatch' }
            foreach ($pair in @(@('entrypoint', 'Entrypoint'), @('command', 'Cmd'))) {
                $want = if ($expected.Contains($pair[0])) { $expected[$pair[0]] } else { $images[$imageKey].Config[$pair[1]] }
                Require ((ConvertTo-Json -InputObject @($item.Config[$pair[1]]) -Compress) -ceq (ConvertTo-Json -InputObject @($want) -Compress)) 'container_command_mismatch'
            }
            Require (-not $item.HostConfig.Privileged -and [bool]$item.HostConfig.ReadonlyRootfs -eq [bool]$expected['read_only']) 'container_security_mismatch'
            Require ((@($item.HostConfig.CapDrop) -join '|') -ceq 'ALL') 'container_security_mismatch'
            Require ((@($item.HostConfig.CapAdd | Sort-Object) -join '|') -ceq (@($expected['cap_add'] | Sort-Object) -join '|')) 'container_security_mismatch'
            Require ((@($item.HostConfig.SecurityOpt) -join '|') -ceq 'no-new-privileges:true') 'container_security_mismatch'
            Require (-not $item.HostConfig.Devices -and -not $item.HostConfig.VolumesFrom -and -not $item.HostConfig.PidMode) 'container_security_mismatch'
            if ($service -ne 'web') { Require ($item.Config.User -ceq $expected.user) 'container_user_mismatch' }
            else { Require ($item.Config.User -ceq $images.web.Config.User) 'container_user_mismatch' }
            if ($service -eq 'worker') { Require ($item.HostConfig.Memory -eq 5368709120 -and $item.HostConfig.PidsLimit -eq 512 -and $item.HostConfig.Init -eq $true) 'container_resource_mismatch' }
            if ($service -in @('worker', 'data-init')) { Require ($item.HostConfig.NetworkMode -ceq 'none' -and -not $item.HostConfig.PortBindings) 'container_network_mismatch' }
            else {
                $port = if ($service -eq 'api') { '8000/tcp' } else { '3000/tcp' }
                $published = if ($service -eq 'api') { '8001' } else { '3087' }
                Keys $item.HostConfig.PortBindings @($port)
                Require (@($item.HostConfig.PortBindings[$port]).Count -eq 1 -and $item.HostConfig.PortBindings[$port][0].HostIp -ceq '127.0.0.1' -and $item.HostConfig.PortBindings[$port][0].HostPort -ceq $published) 'container_port_mismatch'
                $expectedNetworks = @($expected.networks.Keys | ForEach-Object { $record.project + '-' + $_ } | Sort-Object)
                Require ((@($item.NetworkSettings.Networks.Keys | Sort-Object) -join '|') -ceq ($expectedNetworks -join '|')) 'container_network_mismatch'
            }
            $items += $item
        }
        $volumeUsers = Docker @('ps', '-aq', '--filter', ('volume=' + $record.volume))
        foreach ($id in @($volumeUsers -split "`n" | Where-Object { $_ })) {
            Require (@($items | Where-Object { $_.Id.StartsWith($id) }).Count -eq 1) 'foreign_volume_user'
        }
        return ,$items
    }
    $volumes = Docker @('volume', 'ls', '--format', '{{.Name}}')
    $hasVolume = $record.volume -cin @($volumes -split "`n")
    $volumeMarker = Join-Path $install 'volume-established'
    if (Test-Path -LiteralPath $volumeMarker) {
        $null = PlainPath $volumeMarker
        Require ((Get-Content -LiteralPath $volumeMarker -Raw) -ceq $record.volume) 'installation_volume_record_changed'
        Require $hasVolume 'established_volume_missing_preserve_installation'
    }
    if ($hasVolume) { Owned (JsonDocker @('volume', 'inspect', $record.volume))[0].Labels }
    $existingNetworks = @()
    foreach ($network in $config.networks.Keys) {
        $name = $config.networks[$network].name
        $found = Docker @('network', 'ls', '--filter', ('name=^' + $name + '$'), '--format', '{{.ID}}')
        if ($found) {
            $item = (JsonDocker @('network', 'inspect', $name))[0]
            Owned $item.Labels
            Require ($item.Driver -ceq 'bridge' -and $item.Scope -ceq 'local' -and [bool]$item.Internal -eq [bool]$config.networks[$network]['internal']) 'network_isolation_mismatch'
            $existingNetworks += $item
        }
    }
    $before = Containers
    foreach ($network in $existingNetworks) {
        foreach ($id in $network.Containers.Keys) { Require (@($before | Where-Object { $_.Id -ceq $id }).Count -eq 1) 'foreign_network_user' }
    }
    Require ($hasVolume -or $before.Count -eq 0) 'installation_volume_missing'
    if ($Action -in @('Status', 'Stop')) {
        Require $hasVolume 'installation_volume_missing'
        if ($Action -eq 'Stop') {
            # Exact inspected IDs, never a project-wide stop that could include newcomers.
            foreach ($item in $before) { $null = Docker @('container', 'stop', $item.Id) }
        } else { Write-Host ('Verified installation: ' + $record.project + '; containers=' + $before.Count) }
        return
    }
    if (-not $hasVolume) {
        $null = Docker @('volume', 'create', '--label', ('io.cytellect.installation=' + $record.installation_id), '--label', ('io.cytellect.manifest=' + $ManifestSha256), $record.volume)
        Owned (JsonDocker @('volume', 'inspect', $record.volume))[0].Labels
    }
    if (-not (Test-Path -LiteralPath $volumeMarker)) { WriteNew $volumeMarker $record.volume }
    $runningBefore = @($before | Where-Object { $_.State.Running } | ForEach-Object { $_.Id })
    try {
        $null = Docker ($compose + @('up', '-d', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '180'))
        $after = Containers
        Require ($after.Count -eq 4) 'installation_service_missing'
        Require (@($after | Where-Object { $_.Config.Labels['com.docker.compose.service'] -ceq 'data-init' -and -not $_.State.Running -and $_.State.ExitCode -eq 0 }).Count -eq 1) 'installation_initialization_incomplete'
        foreach ($service in @('api', 'worker', 'web')) {
            Require (@($after | Where-Object { $_.Config.Labels['com.docker.compose.service'] -ceq $service -and $_.State.Running }).Count -eq 1) 'installation_not_running'
        }
    } catch {
        # Only stop verifiably owned, newly started containers; preserve every volume.
        $failure = $_
        try {
            $ids = Docker @('ps', '-q', '--filter', ('label=com.docker.compose.project=' + $record.project), '--filter', ('label=io.cytellect.installation=' + $record.installation_id), '--filter', ('label=io.cytellect.manifest=' + $ManifestSha256))
            foreach ($id in @($ids -split "`n" | Where-Object { $_ })) {
                $item = (JsonDocker @('container', 'inspect', $id))[0]
                Owned $item.Config.Labels
                if ($item.Id -cnotin $runningBefore) { $null = Docker @('container', 'stop', $item.Id) }
            }
        } catch { Write-Warning 'Could not safely stop all newly started services; preserve the installation for inspection.' }
        throw $failure
    }
    Write-Host 'Fixed lab release started: http://127.0.0.1:3087/ (release identity checked; scientific acceptance is separate).'
    if ($Action -eq 'Open') { Start-Process 'http://127.0.0.1:3087/' }
} finally {
    if ($lock) { $lock.Dispose() }
    foreach ($name in $prior.Keys) { [Environment]::SetEnvironmentVariable($name, $prior[$name], 'Process') }
}
