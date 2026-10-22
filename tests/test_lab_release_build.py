"""Text/metadata-only build contract tests; never run Docker, image decoding or models."""

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build-lab-release.ps1"
PWSH = shutil.which("pwsh")
pytestmark = pytest.mark.skipif(PWSH is None, reason="PowerShell 7 required")


def run_case(tmp_path, code, *, repo=None, values=None):
    # Define functions from the AST only; the real build entry is never evaluated.
    loader = r"""
    Set-StrictMode -Version Latest
    $ErrorActionPreference='Stop'
    $errors=$null; $tokens=$null
    $ast=[Management.Automation.Language.Parser]::ParseFile($env:CASE_SCRIPT,[ref]$tokens,[ref]$errors)
    if ($errors.Count) { throw 'parse_failure' }
    foreach ($node in $ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst]},$false)) {
        . ([scriptblock]::Create($node.Extent.Text))
    }
    $repoRoot=$env:CASE_REPO
    $gitExe=(Get-Command git -CommandType Application | Select-Object -First 1).Source
    $dockerExe='never-an-executable'
    $dockerContext='desktop-linux'
    $caseRoot=$env:CASE_ROOT
    $values=Get-Content -LiteralPath (Join-Path $caseRoot 'values.json') -Raw | ConvertFrom-Json -AsHashtable
    """
    (tmp_path / "values.json").write_text(json.dumps(values or {}), encoding="utf-8")
    case = tmp_path / "case.ps1"
    case.write_text(loader + code, encoding="utf-8")
    env = dict(os.environ, CASE_SCRIPT=str(SCRIPT), CASE_ROOT=str(tmp_path), CASE_REPO=str(repo or ROOT))
    return subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", str(case)],
                          text=True, capture_output=True, env=env, timeout=90)


def passed(result):
    assert result.returncode == 0, result.stderr


def test_developer_targets_and_explicit_lab_compilation():
    python = (ROOT / "infra/Dockerfile.python").read_text()
    web = (ROOT / "infra/Dockerfile.web").read_text()
    assert re.findall(r"^FROM .+ AS (.+)$", python, re.M)[-1] == "worker"
    assert re.findall(r"^FROM .+ AS (.+)$", web, re.M)[-1] == "builder"
    lab_web = web.split("FROM web-source AS lab-web\n")[1].split("FROM web-source AS builder")[0]
    assert lab_web.index("NEXT_PUBLIC_API_ORIGIN=http://127.0.0.1:8001") < lab_web.index("RUN pnpm build")
    assert "NEXT_PUBLIC_CYTELLECT_DESKTOP_OWNER=true" in lab_web
    lab_model = python.split("FROM cellpose-build AS lab-cellpose-build")[1].split("FROM api AS lab-api")[0]
    assert '--runtime-only --model-only --model "$CYTELLECT_LAB_MODEL"' in lab_model
    assert '!= none' in lab_model
    assert "workspace_retention_mode='manual'" in python


@pytest.mark.parametrize("args,code", [
    (["-SourceCommit", "invalid", "-Candidate", "none"], "exact_source_commit_required"),
    (["-SourceCommit", "a" * 40, "-Candidate", "latest"], "explicit_model_required"),
])
def test_entry_rejects_before_output_or_docker(tmp_path, args, code):
    output = tmp_path / "new-output"
    result = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", str(SCRIPT),
                             *args, "-OutputDirectory", str(output)], capture_output=True, text=True, timeout=20)
    assert result.returncode != 0 and code in result.stderr
    assert not output.exists()


def test_environment_override_and_incomplete_arguments(tmp_path):
    output = tmp_path / "new-output"
    result = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", str(SCRIPT),
                             "-SourceCommit", "a" * 40, "-Candidate", "none", "-OutputDirectory", str(output)],
                            capture_output=True, text=True, timeout=20,
                            env=dict(os.environ, DOCKER_HOST="not-a-real-endpoint"))
    assert "build_environment_override_refused" in result.stderr
    partial = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", str(SCRIPT),
                              "-Candidate", "none"], capture_output=True, text=True, timeout=20)
    assert partial.returncode != 0
    assert not output.exists()


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def text_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "Metadata test")
    git(repo, "config", "user.email", "metadata@example.invalid")
    files = {"fixtures/public/allowlist.json": "{}", ".gitignore": "ignored.py\n",
             "packages/analysis/src/cytellect_analysis/keep.py": "answer = 1\n",
             "apps/web/src/app/icon.svg": "<svg/>\n"}
    for name, content in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "Text-only context fixture")
    return repo


def test_git_tree_context_excludes_ignored_untracked_and_working_edits(tmp_path):
    repo = text_repo(tmp_path)
    source = repo / "packages/analysis/src/cytellect_analysis"
    (source / "ignored.py").write_text("private ignored text", encoding="utf-8")
    (source / "untracked.py").write_text("private untracked text", encoding="utf-8")
    (source / "keep.py").write_text("working copy was changed", encoding="utf-8")
    result = run_case(tmp_path, r"""
    $c=ReadContext (GitText @('rev-parse','HEAD'))
    Require ($c.Count -eq 2) 'unexpected_context_members'
    Require ((ContextText $c 'packages/analysis/src/cytellect_analysis/keep.py') -eq "answer = 1`n") 'not_commit_bytes'
    Require ($c.ContainsKey('apps/web/src/app/icon.svg')) 'icon_lost'
    """, repo=repo)
    passed(result)


def test_git_symlink_and_gitlink_are_rejected_without_following(tmp_path):
    repo = text_repo(tmp_path)
    blob = git(repo, "rev-parse", "HEAD:packages/analysis/src/cytellect_analysis/keep.py")
    git(repo, "update-index", "--add", "--cacheinfo", f"120000,{blob},linked-file")
    tree = git(repo, "write-tree")
    result = run_case(tmp_path, "ReadContext $values.tree", repo=repo, values={"tree": tree})
    assert result.returncode != 0 and "context_link_or_gitlink_refused" in result.stderr
    git(repo, "update-index", "--force-remove", "linked-file")
    git(repo, "update-index", "--add", "--cacheinfo", f"160000,{git(repo, 'rev-parse', 'HEAD')},submodule")
    result = run_case(tmp_path, "ReadContext $values.tree", repo=repo, values={"tree": git(repo, "write-tree")})
    assert result.returncode != 0 and "context_link_or_gitlink_refused" in result.stderr


def test_path_secret_and_binary_policy_is_fail_closed(tmp_path):
    passed(run_case(tmp_path, r"""
    foreach ($name in @('services/api/src/cytellect_api/private/x.py','apps/web/public/weights.pt','apps/web/.env.local')) {
        $caught=$false
        try { AuditBlob $name ([Text.Encoding]::UTF8.GetBytes('ordinary text')) @{} } catch { $caught=$true }
        Require $caught 'private_path_was_accepted'
    }
    $caught=$false
    try { AuditBlob 'packages/analysis/src/cytellect_analysis/x.py' ([Text.Encoding]::UTF8.GetBytes(('hf_' + ('x'*24)))) @{} } catch { $caught=$true }
    Require $caught 'secret_not_rejected'
    # Font marker is ordinary text, not a generated image input.
    $font=[Text.Encoding]::UTF8.GetBytes('font metadata marker')
    $caught=$false
    try { AuditBlob 'apps/web/public/fonts/a.woff2' $font @{} } catch { $caught=$true }
    Require $caught 'unregistered_binary_accepted'
    $registry=@{'apps/web/public/fonts/a.woff2'=@{sha256=(Digest $font);source='https://example.invalid/font';license='test-only'}}
    AuditBlob 'apps/web/public/fonts/a.woff2' $font $registry
    $registry['apps/web/public/fonts/a.woff2'].sha256='0'*64
    $caught=$false
    try { AuditBlob 'apps/web/public/fonts/a.woff2' $font $registry } catch { $caught=$true }
    Require $caught 'wrong_binary_hash_accepted'
    """))


def test_models_match_and_none_never_masks_candidate_failure(tmp_path):
    passed(run_case(tmp_path, r"""
    $c=@{}
    foreach ($name in @('runtime.lock.json','provisioning.lock.json','runner.py','requirements.lock')) {
        $bytes=[IO.File]::ReadAllBytes((Join-Path $repoRoot ('engines/cellpose/'+$name)))
        $c['engines/cellpose/'+$name]=@{data=$bytes;sha256=(Digest $bytes)}
    }
    $m=Models $c none
    Require ($m.baseline.id -ceq 'cpsam_v2' -and $null -eq $m.candidate) 'baseline_missing'
    $caught=$false
    try { Models $c ncl-unregistered } catch { $caught=$true }
    Require $caught 'candidate_fell_back'
    $p=(ContextText $c 'engines/cellpose/provisioning.lock.json') | ConvertFrom-Json -AsHashtable
    $p.model.sha256='0'*64
    $c['engines/cellpose/provisioning.lock.json'].data=[Text.Encoding]::UTF8.GetBytes(($p | ConvertTo-Json -Depth 12))
    $caught=$false
    try { Models $c none } catch { $caught=$true }
    Require $caught 'mismatched_model_accepted'
    $caught=$false
    try { ManualSource @{} } catch { $caught=$true }
    Require $caught 'missing_manual_source_accepted'
    """))


def test_new_outputs_refuse_reuse_and_changed_context(tmp_path):
    passed(run_case(tmp_path, r"""
    $dir=Join-Path $caseRoot 'context'; $null=[IO.Directory]::CreateDirectory($dir)
    $bytes=[Text.Encoding]::UTF8.GetBytes('text source')
    $target=Join-Path $dir 'source.py'; WriteNew $target $bytes
    $c=@{'source.py'=@{sha256=(Digest $bytes)}}
    VerifyContext $dir $c
    $caught=$false
    try { WriteNew $target $bytes } catch { $caught=$true }
    Require $caught 'overwrite_allowed'
    WriteNew (Join-Path $dir 'extra.py') $bytes
    $caught=$false
    try { VerifyContext $dir $c } catch { $caught=$true }
    Require $caught 'extra_context_allowed'
    """))


@pytest.mark.parametrize("failure", ["none", "worker", "labels", "stale"])
def test_three_build_commands_and_partial_failure_receipts(tmp_path, failure):
    passed(run_case(tmp_path, r"""
    $script:builds=[Collections.Generic.List[object]]::new()
    $script:failure=$values.failure
    $script:lastService=''
    $script:commit='a'*40
    $script:baseline='b'*64
    $script:models=@{baseline=@{sha256=$script:baseline};candidate=$null}
    $out=Join-Path $caseRoot 'output'; $null=[IO.Directory]::CreateDirectory($out)
    function LocalEngine { return 'metadata-engine' }
    function VerifyContext { }
    function Run($Exe,$Arguments,[switch]$DiscardOutput) {
        Require ($Exe -ceq 'never-an-executable' -and $DiscardOutput) 'unexpected_tool'
        $script:builds.Add($Arguments)
        $target=$Arguments[[Array]::IndexOf($Arguments,'--target')+1]
        $script:lastService=$target.Substring(4)
        if ($script:failure -ceq $script:lastService) { throw 'controlled_build_failure' }
        $iid=$Arguments[[Array]::IndexOf($Arguments,'--iidfile')+1]
        WriteNew $iid ([Text.Encoding]::UTF8.GetBytes(('sha256:' + ('c'*64))))
        return ,([byte[]]@())
    }
    function DockerJson($Arguments) {
        Require (($Arguments[0..1] -join ' ') -ceq 'image inspect') 'unexpected_docker'
        $labels=@{'org.opencontainers.image.revision'=$script:commit;'io.cytellect.lab-contract'='manual-v1';'io.cytellect.baseline-sha256'=$script:baseline;'io.cytellect.candidate-sha256'='none';'io.cytellect.api-origin'='http://127.0.0.1:8001';'io.cytellect.desktop-owner'='true'}
        if ($script:failure -ceq 'labels') { $labels['io.cytellect.lab-contract']='wrong' }
        return ,@(@{Id=('sha256:'+('c'*64));Os='linux';Architecture='amd64';Config=@{Labels=$labels};RepoDigests=@()})
    }
    if ($script:failure -ceq 'stale') { WriteNew (Join-Path $out 'api.iid') ([Text.Encoding]::UTF8.GetBytes('old')) }
    $failed=$false
    try { $result=BuildImages $out (Join-Path $out 'context') @{} $script:models $script:commit none 'metadata-engine' } catch { $failed=$true }
    if ($script:failure -ceq 'none') {
        Require (-not $failed -and $result.Count -eq 3 -and $script:builds.Count -eq 3) 'build_sequence_failed'
    } else {
        Require $failed 'failure_not_stopped'
        $expected=if ($script:failure -ceq 'worker') {2} elseif ($script:failure -ceq 'stale') {0} else {1}
        Require ($script:builds.Count -eq $expected) 'later_build_started'
        Require (-not (Test-Path -LiteralPath (Join-Path $out 'web-verified.json'))) 'false_success'
    }
    foreach ($args in $script:builds) {
        Require (($args[0..3] -join ' ') -ceq '--context desktop-linux build --builder') 'endpoint_not_fixed'
        Require ($args[4] -ceq 'default' -and '--pull=false' -cin $args -and '--iidfile' -cin $args) 'build_flags_changed'
        Require (-not ('--push' -cin $args)) 'publication_requested'
    }
    """, values={"failure": failure}))


def test_tracked_asset_selection_covers_current_docker_copy_metadata(tmp_path):
    # Read tracked names only, never decode public bitmap inputs or run Docker.
    names = git(ROOT, "ls-tree", "-r", "--name-only", "HEAD").splitlines()
    expected = [n for n in names if n.startswith(("apps/web/public/", "engines/cellpose/", "engines/fiji/"))]
    expected = [n for n in expected if not n.endswith("requirements.in")]
    expected += ["apps/web/src/app/icon.svg", "pyproject.toml", "uv.lock", "README.md", "LICENSE"]
    passed(run_case(tmp_path, r"""
    foreach ($name in $values.required) { Require (Selected $name) 'required_asset_not_selected' }
    Require (-not (Selected 'apps/web/src/private.test.ts')) 'test_in_context'
    """, values={"required": expected}))


def test_sha_uses_compatible_implementation(tmp_path):
    passed(run_case(tmp_path, "Require ((Digest ([Text.Encoding]::UTF8.GetBytes('abc'))) -ceq $values.sha) 'digest_wrong'",
                    values={"sha": hashlib.sha256(b"abc").hexdigest()}))


def test_autocrlf_clean_checkout_uses_existing_lf_attributes(tmp_path):
    repo = text_repo(tmp_path)
    git(repo, "config", "core.autocrlf", "true")
    (repo / ".gitattributes").write_bytes((ROOT / ".gitattributes").read_bytes())
    target = repo / "scripts/build-lab-release.ps1"
    target.parent.mkdir()
    target.write_bytes(SCRIPT.read_bytes())
    git(repo, "add", ".gitattributes", "scripts/build-lab-release.ps1")
    git(repo, "commit", "-qm", "Builder text with repository LF policy")
    git(repo, "checkout-index", "--force", "scripts/build-lab-release.ps1")
    committed = subprocess.check_output(["git", "-C", str(repo), "show", "HEAD:scripts/build-lab-release.ps1"])
    assert target.read_bytes() == committed
    assert not git(repo, "status", "--porcelain")
    assert "eol: lf" in git(repo, "check-attr", "eol", "--", "scripts/build-lab-release.ps1")


def test_junction_ancestor_is_rejected(tmp_path):
    if os.name != "nt":
        pytest.skip("Windows junction metadata check")
    passed(run_case(tmp_path, r"""
    $target=Join-Path $caseRoot 'text-only-target'; $null=[IO.Directory]::CreateDirectory($target)
    $link=Join-Path $caseRoot 'junction'
    $null=New-Item -ItemType Junction -Path $link -Target $target
    $caught=$false
    try { PlainPath (Join-Path $link 'not-created.txt') } catch { $caught=$true }
    Require $caught 'junction_accepted'
    """))


def test_remote_endpoint_is_rejected_before_engine_or_build(tmp_path):
    passed(run_case(tmp_path, r"""
    $script:count=0
    function Run($Exe,$Arguments) {
        $script:count++
        return ,([Text.Encoding]::UTF8.GetBytes('[{"Name":"test","Endpoints":{"docker":{"Host":"ssh://example.invalid"}}}]'))
    }
    $caught=$false
    try { LocalEngine } catch { $caught=$true }
    Require ($caught -and $script:count -eq 1) 'remote_engine_contacted'
    """))


def test_explicit_candidate_lock_and_lineage_metadata(tmp_path):
    passed(run_case(tmp_path, r"""
    $c=@{}
    foreach ($name in @('runtime.lock.json','provisioning.lock.json','runner.py','requirements.lock')) {
        $bytes=[IO.File]::ReadAllBytes((Join-Path $repoRoot ('engines/cellpose/'+$name)))
        $c['engines/cellpose/'+$name]=@{data=$bytes;sha256=(Digest $bytes)}
    }
    # Identity-only fixture. No weights, image, approved manifest or download exists.
    $r=(ContextText $c 'engines/cellpose/runtime.lock.json') | ConvertFrom-Json -AsHashtable
    $p=(ContextText $c 'engines/cellpose/provisioning.lock.json') | ConvertFrom-Json -AsHashtable
    $candidate=@{id='ncl-metadata-test';revision=$r.model.revision;url=$r.model.url;sha256=$r.model.sha256;size=$r.model.size;license=$r.model.license;status='experimental_development_candidate';base_model_sha256=$r.model.sha256}
    $r.ncl_candidates=@{'ncl-metadata-test'=$candidate.Clone()}
    $p.ncl_candidates=@{'ncl-metadata-test'=$candidate.Clone()}
    $c['engines/cellpose/runtime.lock.json'].data=[Text.Encoding]::UTF8.GetBytes(($r | ConvertTo-Json -Depth 12))
    $c['engines/cellpose/provisioning.lock.json'].data=[Text.Encoding]::UTF8.GetBytes(($p | ConvertTo-Json -Depth 12))
    $m=Models $c ncl-metadata-test
    Require ($m.baseline.id -ceq 'cpsam_v2' -and $m.candidate.id -ceq 'ncl-metadata-test') 'candidate_not_explicit'
    $p.ncl_candidates['ncl-metadata-test'].base_model_sha256='0'*64
    $c['engines/cellpose/provisioning.lock.json'].data=[Text.Encoding]::UTF8.GetBytes(($p | ConvertTo-Json -Depth 12))
    $caught=$false
    try { Models $c ncl-metadata-test } catch { $caught=$true }
    Require $caught 'lineage_mismatch_accepted'
    """))
