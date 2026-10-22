#requires -Version 7.0
param(
    [Parameter(Mandatory)][string]$SourceCommit,
    [Parameter(Mandatory)][string]$Candidate,
    [Parameter(Mandatory)][string]$OutputDirectory
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$dockerContext = $null

function Require($Condition, [string]$Code) { if (-not $Condition) { throw $Code } }
function Digest([byte[]]$Data) {
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($algorithm.ComputeHash($Data)).Replace('-','').ToLowerInvariant() }
    finally { $algorithm.Dispose() }
}
function PlainPath([string]$Path) {
    Require ([IO.Path]::IsPathFullyQualified($Path)) 'absolute_path_required'
    $full = [IO.Path]::GetFullPath($Path).TrimEnd([IO.Path]::DirectorySeparatorChar)
    Require ($full.Length -gt [IO.Path]::GetPathRoot($full).Length) 'filesystem_root_refused'
    for ($part = $full; $part; $part = Split-Path $part -Parent) {
        if (Test-Path -LiteralPath $part) {
            Require (-not ((Get-Item -LiteralPath $part -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) 'linked_path_refused'
        }
    }
    return $full
}
function Run([string]$Exe, [string[]]$Arguments, [switch]$DiscardOutput) {
    # No shell interpolation and no raw tool output in errors/receipts.
    $info = [Diagnostics.ProcessStartInfo]::new($Exe)
    $info.UseShellExecute = $false
    $info.RedirectStandardOutput = $true; $info.RedirectStandardError = $true
    foreach ($arg in $Arguments) { $info.ArgumentList.Add($arg) }
    $p = [Diagnostics.Process]::Start($info)
    $out = [IO.MemoryStream]::new()
    try {
        $copy = $p.StandardOutput.BaseStream.CopyToAsync($(if ($DiscardOutput) { [IO.Stream]::Null } else { $out }))
        $errorRead = $p.StandardError.BaseStream.CopyToAsync([IO.Stream]::Null)
        $p.WaitForExit(); $null = $copy.GetAwaiter().GetResult(); $null = $errorRead.GetAwaiter().GetResult()
        Require ($p.ExitCode -eq 0) 'build_tool_failed'
        return ,$out.ToArray()
    } finally { $out.Dispose(); $p.Dispose() }
}
function Git([string[]]$Arguments) {
    return ,(Run $script:gitExe (@('--no-replace-objects', '-C', $repoRoot) + $Arguments))
}
function GitText([string[]]$Arguments) { [Text.Encoding]::UTF8.GetString((Git $Arguments)).TrimEnd("`r", "`n") }
function Blob([string]$Oid) { return ,(Git @('cat-file', 'blob', $Oid)) }
function WriteNew([string]$Path, [byte[]]$Data) {
    $stream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $stream.Write($Data); $stream.Flush($true) } finally { $stream.Dispose() }
}
function WriteJson([string]$Path, $Value) {
    WriteNew $Path ([Text.Encoding]::UTF8.GetBytes(($Value | ConvertTo-Json -Depth 20)))
}
function Selected([string]$Name) {
    # Only inputs consumed by these Dockerfiles. No broad checkout COPY/export.
    if ($Name -in @('.dockerignore', 'pyproject.toml', 'uv.lock', 'README.md', 'LICENSE',
        'package.json', 'pnpm-lock.yaml', 'pnpm-workspace.yaml',
        'infra/Dockerfile.python', 'infra/Dockerfile.web', 'infra/runtime-entrypoint.py',
        'scripts/build-lab-release.ps1', 'scripts/fiji_setup.py', 'scripts/cellpose_setup.py',
        'scripts/container_smoke.py', 'fixtures/planning/decisions-v2.json', 'fixtures/planning/decisions-v21.json')) { return $true }
    if ($Name -match '(^|/)(__tests__|tests|node_modules|\.next)(/|$)|\.(test|spec)\.') { return $false }
    return ($Name -cmatch '^(packages/analysis/src/cytellect_analysis/|services/(api/src/cytellect_api|worker/src/cytellect_worker)/).+\.py$' -or
        $Name -cmatch '^packages/contracts/[^/]+\.json$' -or
        $Name -cmatch '^engines/(cellpose|fiji)/[^/]+\.(py|java|json|lock|txt|md)$' -or
        $Name -cmatch '^apps/web/src/.+\.(ts|tsx|js|css|json|svg)$' -or
        $Name -cmatch '^apps/web/[^/]+\.(json|ts|mjs|js)$' -or
        $Name -cmatch '^apps/web/public/.+')
}
function AuditBlob([string]$Name, [byte[]]$Data, $Registry) {
    Require ($Name -cmatch '^[A-Za-z0-9_./@()\[\]-]+$' -and $Name -notmatch '(^|/)\.\.?(/|$)') 'context_path_invalid'
    Require ($Name -notmatch '(?i)(^|/)(private|research|data|runtime|work|secrets|credentials)(/|$)|(^|/)\.env|\.(tiff?|czi|nd2|lif|npy|npz|pt|pth|safetensors|sqlite\w*|db|pem|pfx|key|zip|tar|gz)$') 'context_private_path_refused'
    Require ($Data.Length -le 64MB) 'context_blob_too_large'
    $extension = [IO.Path]::GetExtension($Name).ToLowerInvariant()
    if ($extension -in @('.png', '.jpg', '.jpeg', '.webp', '.mp4', '.glb', '.woff2', '.woff', '.ttf')) {
        Require ($Name.StartsWith('apps/web/public/', [StringComparison]::Ordinal) -and $Registry.Contains($Name)) 'context_binary_unregistered'
        $entry = $Registry[$Name]
        Require ($entry.source -and $entry.license -and (Digest $Data) -ceq $entry.sha256) 'context_public_asset_mismatch'
        return
    }
    Require ($extension -in @('', '.ps1', '.py', '.java', '.json', '.lock', '.toml', '.yaml', '.md', '.txt', '.ts', '.tsx', '.js', '.mjs', '.css', '.html', '.svg', '.csv', '.python', '.web', '.dockerignore')) 'context_type_refused'
    try { $text = [Text.UTF8Encoding]::new($false, $true).GetString($Data) }
    catch { throw 'context_non_text_refused' }
    Require (-not $text.Contains([char]0)) 'context_non_text_refused'
    # Defense in depth, not a substitute for the fixed source's privacy review.
    Require ($text -notmatch '(?i)(?:gh[pousr]_|github_pat_|hf_|sk_live_|sk-proj-)[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----') 'context_secret_pattern'
    Require ($text -notmatch '(?i)[A-Z]:[/\\]Users[/\\](?!<|example[/\\]|user[/\\])[A-Za-z0-9_-]+|/(?:home|Users)/(?!(?:example|user)/)[A-Za-z0-9_-]+/') 'context_private_path_pattern'
}
function ReadContext([string]$Commit) {
    $tree = @{}
    foreach ($line in (GitText @('ls-tree', '-rz', $Commit)).Split([char]0)) {
        if (-not $line) { continue }
        Require ($line -cmatch '^(100644|100755) blob ([0-9a-f]{40})\t(.+)$') 'context_link_or_gitlink_refused'
        $oid = $Matches[2]; $name = $Matches[3]
        Require (-not $tree.ContainsKey($name.ToLowerInvariant())) 'context_case_collision'
        $tree[$name.ToLowerInvariant()] = @{name=$name; oid=$oid}
    }
    $registryName = 'fixtures/public/allowlist.json'
    Require ($tree.ContainsKey($registryName)) 'public_registry_missing'
    $registry = [Text.Encoding]::UTF8.GetString((Blob $tree[$registryName].oid)) | ConvertFrom-Json -AsHashtable
    $selected = @{}; $total = 0L
    foreach ($entry in $tree.Values) {
        if (-not (Selected $entry.name)) { continue }
        $null = PlainPath (Join-Path $repoRoot $entry.name)
        # Length is checked before reading each Git object, including binary assets.
        $size = [long](GitText @('cat-file', '-s', $entry.oid))
        Require ($size -ge 0 -and $size -le 64MB) 'context_blob_too_large'
        $total += $size; Require ($total -le 256MB) 'context_total_too_large'
        $data = Blob $entry.oid
        AuditBlob $entry.name $data $registry
        $selected[$entry.name] = @{data=$data; sha256=(Digest $data); bytes=$data.Length}
    }
    return $selected
}
function ContextText($Context, [string]$Name) {
    Require ($Context.ContainsKey($Name)) 'required_build_input_missing'
    return [Text.Encoding]::UTF8.GetString($Context[$Name].data)
}
function Models($Context, [string]$Choice) {
    $runtime = (ContextText $Context 'engines/cellpose/runtime.lock.json') | ConvertFrom-Json -AsHashtable
    $provision = (ContextText $Context 'engines/cellpose/provisioning.lock.json') | ConvertFrom-Json -AsHashtable
    Require ($runtime.schema -ceq 'cytellect-cellpose-runtime/1' -and $provision.schema -ceq 'cytellect-cellpose-provisioning/1') 'model_schema_invalid'
    Require ($runtime.runtime_downloads -eq $false -and $provision.runtime_downloads -eq $false) 'runtime_downloads_refused'
    Require ($runtime.requirements_sha256 -ceq $provision.requirements_sha256 -and $runtime.requirements_sha256 -ceq $Context['engines/cellpose/requirements.lock'].sha256) 'runtime_requirements_mismatch'
    Require ($runtime.runner_sha256 -ceq $Context['engines/cellpose/runner.py'].sha256) 'runtime_runner_mismatch'
    Require (($runtime.packages | ConvertTo-Json -Compress) -ceq ($provision.packages | ConvertTo-Json -Compress) -and $runtime.python -ceq $provision.python) 'runtime_packages_mismatch'
    $models = @($runtime.model); $other = @($provision.model)
    Require ($models[0].id -ceq 'cpsam_v2') 'baseline_required'
    if ($Choice -cne 'none') {
        Require ($Choice -cmatch '^ncl-[a-zA-Z0-9_-]+$' -and $runtime.Contains('ncl_candidates') -and $provision.Contains('ncl_candidates')) 'candidate_not_registered'
        Require ($runtime.ncl_candidates.Contains($Choice) -and $provision.ncl_candidates.Contains($Choice)) 'candidate_not_registered'
        $models += $runtime.ncl_candidates[$Choice]; $other += $provision.ncl_candidates[$Choice]
        Require ($models[1].id -ceq $Choice -and $models[1].status -ceq 'experimental_development_candidate') 'candidate_not_experimental'
        Require ($models[1].base_model_sha256 -ceq $models[0].sha256) 'candidate_baseline_mismatch'
        Require ($models[1].status -ceq $other[1].status -and $models[1].base_model_sha256 -ceq $other[1].base_model_sha256) 'candidate_lineage_mismatch'
    }
    for ($i=0; $i -lt $models.Count; $i++) {
        $model=$models[$i]; $pair=$other[$i]
        foreach ($key in @('id','revision','url','sha256','size','license')) { Require ($model.Contains($key) -and $pair.Contains($key) -and $model[$key] -ceq $pair[$key]) 'model_lock_mismatch' }
        Require ($model.revision -cmatch '^[0-9a-f]{40}$' -and $model.sha256 -cmatch '^[0-9a-f]{64}$' -and $model.size -is [long] -and $model.size -gt 0 -and $model.license) 'model_identity_invalid'
        Require ($model.url -cmatch '^https://huggingface\.co/[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+/resolve/([0-9a-f]{40})/[A-Za-z0-9_./-]+$' -and $Matches[1] -ceq $model.revision -and $model.url -notmatch '/\.\.?/') 'model_fixed_url_required'
    }
    return @{baseline=$models[0]; candidate=$(if ($models.Count -eq 2) { $models[1] } else { $null })}
}
function ManualSource($Context) {
    foreach ($name in @('services/api/src/cytellect_api/config.py', 'services/api/src/cytellect_api/db.py',
        'services/api/src/cytellect_api/app.py', 'services/worker/src/cytellect_worker/main.py', 'services/worker/src/cytellect_worker/child.py')) {
        Require ((ContextText $Context $name).Contains('workspace_retention_mode')) 'manual_source_capability_missing'
    }
    Require ((ContextText $Context 'services/api/src/cytellect_api/config.py').Contains('CYTELLECT_WORKSPACE_RETENTION_MODE')) 'manual_source_capability_missing'
    # A capability precheck only; external review must establish full API/worker/UI semantics.
}
function DockerJson([string[]]$Arguments) {
    return ,([Text.Encoding]::UTF8.GetString((Run $script:dockerExe (@('--context', $script:dockerContext) + $Arguments))) | ConvertFrom-Json -AsHashtable -NoEnumerate)
}
function LocalEngine {
    $args = @('context','inspect')
    if ($script:dockerContext) { $args += $script:dockerContext }
    $context = [Text.Encoding]::UTF8.GetString((Run $script:dockerExe $args)) | ConvertFrom-Json -AsHashtable -NoEnumerate
    Require ($context.Count -eq 1 -and $context[0].Endpoints.docker.Host -ceq 'npipe:////./pipe/dockerDesktopLinuxEngine') 'local_desktop_endpoint_required'
    Require ($context[0].Name -cmatch '^[a-zA-Z0-9_-]+$') 'desktop_context_name_invalid'
    $script:dockerContext = $context[0].Name
    $info = DockerJson @('info','--format','{{json .}}')
    Require ($info.OSType -ceq 'linux' -and $info.Architecture -in @('x86_64','amd64') -and $info.OperatingSystem -ceq 'Docker Desktop' -and $info.ID) 'local_desktop_engine_required'
    # Docker's default builder is bound to the explicitly pinned daemon context.
    # https://docs.docker.com/build/builders/#default-builder
    return $info.ID
}
function VerifyContext([string]$Root, $Context) {
    $files = @(Get-ChildItem -LiteralPath $Root -Recurse -Force -File)
    Require ($files.Count -eq $Context.Count) 'export_context_changed'
    foreach ($file in $files) {
        $null = PlainPath $file.FullName
        $name = [IO.Path]::GetRelativePath($Root, $file.FullName).Replace('\','/')
        Require ($Context.ContainsKey($name) -and (Digest ([IO.File]::ReadAllBytes($file.FullName))) -ceq $Context[$name].sha256) 'export_context_changed'
    }
}
function BuildImages([string]$Output, [string]$ContextRoot, $Context, $Models, [string]$Commit, [string]$Choice, [string]$EngineId) {
    $result = @{}
    foreach ($service in @('api','worker','web')) {
        Require ((LocalEngine) -ceq $EngineId) 'engine_changed'
        VerifyContext $ContextRoot $Context
        $iid = Join-Path $Output ($service + '.iid')
        Require (-not (Test-Path -LiteralPath $iid)) 'stale_iid_refused'
        WriteJson (Join-Path $Output ($service + '-started.json')) @{service=$service; utc=[DateTime]::UtcNow.ToString('o')}
        Write-Host "Building lab-$service"
        $file = if ($service -eq 'web') { 'infra/Dockerfile.web' } else { 'infra/Dockerfile.python' }
        $candidateSha = if ($null -eq $Models.candidate) { 'none' } else { $Models.candidate.sha256 }
        $args = @('--context',$script:dockerContext,'build','--builder','default','--platform','linux/amd64','--pull=false','--target',"lab-$service",'--file',(Join-Path $ContextRoot $file),'--iidfile',$iid,
            '--build-arg',"CYTELLECT_SOURCE_COMMIT=$Commit",'--build-arg',"CYTELLECT_BASELINE_SHA256=$($Models.baseline.sha256)",'--build-arg',"CYTELLECT_CANDIDATE_SHA256=$candidateSha")
        if ($service -eq 'worker') { $args += @('--build-arg',"CYTELLECT_LAB_MODEL=$Choice") }
        $null = Run $script:dockerExe ($args + @($ContextRoot)) -DiscardOutput
        $null = PlainPath $iid
        $id = (Get-Content -LiteralPath $iid -Raw).Trim()
        Require ($id -cmatch '^sha256:[0-9a-f]{64}$') 'build_iid_invalid'
        $image = (DockerJson @('image','inspect',$id))[0]
        Require ($image.Id -ceq $id -and $image.Os -ceq 'linux' -and $image.Architecture -ceq 'amd64') 'built_image_mismatch'
        $labels = $image.Config.Labels
        Require ($labels['org.opencontainers.image.revision'] -ceq $Commit -and $labels['io.cytellect.lab-contract'] -ceq 'manual-v1' -and $labels['io.cytellect.baseline-sha256'] -ceq $Models.baseline.sha256 -and $labels['io.cytellect.candidate-sha256'] -ceq $candidateSha) 'built_label_mismatch'
        if ($service -eq 'web') { Require ($labels['io.cytellect.api-origin'] -ceq 'http://127.0.0.1:8001' -and $labels['io.cytellect.desktop-owner'] -ceq 'true') 'built_web_origin_mismatch' }
        Require ((LocalEngine) -ceq $EngineId) 'engine_changed'
        VerifyContext $ContextRoot $Context
        $result[$service] = @{id=$id; repo_digests=@($image.RepoDigests)}
        WriteJson (Join-Path $Output ($service + '-verified.json')) $result[$service]
    }
    return $result
}

# Validate everything possible before creating output or contacting Docker.
Require ($SourceCommit -cmatch '^[0-9a-f]{40}$') 'exact_source_commit_required'
Require ($Candidate -ceq 'none' -or $Candidate -cmatch '^ncl-[a-zA-Z0-9_-]+$') 'explicit_model_required'
Require (-not (Get-ChildItem Env: | Where-Object Name -Match '^(DOCKER_|BUILDX_|BUILDKIT_|COMPOSE_|CYTELLECT_|GIT_)')) 'build_environment_override_refused'
$repoRoot = PlainPath $repoRoot
$output = PlainPath $OutputDirectory
Require (-not $output.Equals($repoRoot,[StringComparison]::OrdinalIgnoreCase) -and -not $output.StartsWith($repoRoot + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) 'output_outside_source_required'
Require (-not (Test-Path -LiteralPath $output) -and (Test-Path -LiteralPath (Split-Path $output -Parent) -PathType Container)) 'new_output_required'
$gitExe = (Get-Command git -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
Require ((GitText @('rev-parse','HEAD')) -ceq $SourceCommit) 'source_commit_mismatch'
Require (-not (GitText @('status','--porcelain','--untracked-files=all'))) 'clean_source_required'
$context = ReadContext $SourceCommit
Require ((Digest ([IO.File]::ReadAllBytes($PSCommandPath))) -ceq $context['scripts/build-lab-release.ps1'].sha256) 'builder_source_mismatch'
ManualSource $context
$models = Models $context $Candidate
$dockerExe = (Get-Command docker.exe -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
$engineId = LocalEngine

# Exclusive reservation: interruption leaves a non-reusable directory; no implicit cleanup.
$reservation = [IO.File]::Open($output + '.reservation', [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try {
    Require (-not (Test-Path -LiteralPath $output)) 'new_output_required'
    $null = [IO.Directory]::CreateDirectory($output)
    $contextRoot = Join-Path $output 'context'
    $null = [IO.Directory]::CreateDirectory($contextRoot)
    $inventory = @{}
    foreach ($name in $context.Keys) {
        $target = Join-Path $contextRoot $name
        $null = [IO.Directory]::CreateDirectory((Split-Path $target -Parent))
        WriteNew $target $context[$name].data
        $inventory[$name] = @{sha256=$context[$name].sha256; bytes=$context[$name].bytes}
    }
    WriteJson (Join-Path $output 'context.json') @{source_commit=$SourceCommit; files=$inventory}
    $images = BuildImages $output $contextRoot $context $models $SourceCommit $Candidate $engineId
    WriteJson (Join-Path $output 'build-completed.json') @{schema_version=1; status='built_not_release_accepted'; source_commit=$SourceCommit; platform='linux/amd64'; engine_id=$engineId; images=$images; baseline=$models.baseline; candidate=$models.candidate; context_sha256=(Digest ([IO.File]::ReadAllBytes((Join-Path $output 'context.json')))); startup_verified=$false; scientific_acceptance=$false; backup_restore_verified=$false}
    Write-Host 'Three image identities verified; release/startup acceptance remains separate.'
} catch {
    if (Test-Path -LiteralPath $output -PathType Container) {
        WriteJson (Join-Path $output 'build-failed.json') @{status='failed_or_incomplete'; code='lab_build_failed'; utc=[DateTime]::UtcNow.ToString('o'); success_receipt_issued=$false}
    }
    throw 'lab_build_failed; preserve the private output and reservation for review'
} finally { $reservation.Dispose() }
