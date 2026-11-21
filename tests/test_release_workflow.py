"""The Windows release ships exactly one green main commit (docs/release-signing.md, docs/ci.md).

The source-resolution script of local-release.yml is run in Node with a stubbed GitHub API, so
the accepted and refused ``commit`` inputs are tested as the workflow evaluates them.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
RELEASE = (WORKFLOWS / "local-release.yml").read_text(encoding="utf-8")
CI = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
HEAD = "a" * 40
OLDER = "b" * 40
CHECKS = ["python", "web", "fiji-browser", "browser-e2e", "cellpose-gpu-image", "local-windows", "windows-installed",
          "windows-installer", "python-windows-314"]


def job(text: str, name: str) -> str:
    lines = text.splitlines()
    start = lines.index(f"  {name}:")
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"^  [\w-]+:\s*$", lines[i])), len(lines))
    return "\n".join(lines[start:end])


def resolve_script() -> str:
    lines = job(RELEASE, "source").splitlines()
    manual = lines.index("        id: resolve")
    start = next(i for i in range(manual, len(lines)) if lines[i].strip() == "script: |") + 1
    indent = len(lines[start]) - len(lines[start].lstrip())
    body = []
    for line in lines[start:]:
        if line.strip() and len(line) - len(line.lstrip()) < indent:
            break
        body.append(line[indent:])
    return "\n".join(body)


HARNESS = r"""
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const notFound = () => Promise.reject(Object.assign(new Error('Not Found'), {status: 404}));
const calls = {checksRef: null, basehead: null};
const outputs = {};
const github = {
  rest: {
    git: {getRef: () => input.tagExists ? Promise.resolve({data: {}}) : notFound()},
    repos: {
      getReleaseByTag: () => notFound(),
      compareCommitsWithBasehead: ({basehead}) => {
        calls.basehead = basehead;
        const base = basehead.split('...')[0];
        const known = input.compare[base];
        return known ? Promise.resolve({data: known}) : notFound();
      }
    },
    checks: {listForRef: 'listForRef'}
  },
  paginate: (endpoint, {ref}) => {
    calls.checksRef = ref;
    return Promise.resolve(input.checks.map(name => ({name, conclusion: 'success', app: {slug: 'github-actions'}})));
  }
};
const core = {setOutput: (key, value) => { outputs[key] = value; }, info: () => {}};
const context = {repo: {owner: 'genellect', repo: 'cytellect'}, sha: input.head};
process.env.RELEASE_VERSION = input.version;
process.env.REQUESTED_COMMIT = input.requested;
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
new AsyncFunction('github', 'context', 'core', input.script)(github, context, core)
  .then(() => console.log(JSON.stringify({ok: true, outputs, calls})))
  .catch(error => console.log(JSON.stringify({ok: false, error: error.message, calls})));
"""


def run_resolve(requested: str, *, checks: list[str] = CHECKS, tag_exists: bool = False,
                version: str = "0.1.0-local.21") -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to evaluate the github-script step")
    compare = {
        HEAD: {"status": "identical", "behind_by": 0, "merge_base_commit": {"sha": HEAD}},
        OLDER: {"status": "ahead", "behind_by": 0, "merge_base_commit": {"sha": OLDER}},
        "c" * 40: {"status": "diverged", "behind_by": 2, "merge_base_commit": {"sha": OLDER}},
        "d" * 40: {"status": "behind", "behind_by": 1, "merge_base_commit": {"sha": HEAD}},
    }
    payload = {"script": resolve_script(), "requested": requested, "head": HEAD, "checks": checks,
               "tagExists": tag_exists, "version": version, "compare": compare}
    result = subprocess.run([node, "-e", HARNESS], input=json.dumps(payload), capture_output=True, text=True,
                            check=True, timeout=60)
    return json.loads(result.stdout)


def test_empty_commit_releases_the_dispatched_main_head():
    result = run_resolve("")
    assert result["ok"], result
    assert result["outputs"] == {"commit": HEAD, "version": "0.1.0-local.21"}
    assert result["calls"]["checksRef"] == HEAD


def test_an_earlier_green_main_commit_is_released_and_gated_on_its_own_checks():
    result = run_resolve(OLDER)
    assert result["ok"], result
    assert result["outputs"] == {"commit": OLDER, "version": "0.1.0-local.21"}
    assert result["calls"] == {"checksRef": OLDER, "basehead": f"{OLDER}...{HEAD}"}


@pytest.mark.parametrize("requested", ["main", "refs/heads/main", "v0.1.0-local.20", "b" * 12, "B" * 40,
                                       f" {OLDER}", f"{OLDER}\n", "b" * 41, "g" * 40, "HEAD~1"])
def test_anything_but_a_full_lowercase_sha_is_refused_before_any_lookup(requested):
    result = run_resolve(requested)
    assert not result["ok"] and "40-character" in result["error"]
    assert result["calls"] == {"checksRef": None, "basehead": None}


@pytest.mark.parametrize("requested", ["c" * 40, "d" * 40, "e" * 40])
def test_a_commit_that_is_not_main_or_one_of_its_ancestors_is_refused(requested):
    result = run_resolve(requested)
    assert not result["ok"] and result["calls"]["checksRef"] is None
    assert "not on main" in result["error"] or "does not exist" in result["error"]


def test_a_missing_check_on_the_requested_commit_refuses_the_release():
    result = run_resolve(OLDER, checks=[name for name in CHECKS if name != "windows-installer"])
    assert not result["ok"] and result["error"] == f"windows-installer has not passed on {OLDER}"


def test_an_existing_version_or_a_malformed_version_is_still_refused():
    assert run_resolve(OLDER, tag_exists=True)["error"] == "Release version already exists"
    assert run_resolve(OLDER, version="0.1.0")["error"] == "Expected a unique local prerelease version"


def test_the_commit_input_is_optional_and_only_reaches_scripts_through_the_environment():
    inputs = RELEASE.split("permissions:", 1)[0]
    assert re.search(r"\n      commit:\n(?:        .*\n)*?        required: false\n", inputs)
    assert '        default: ""' in inputs
    assert RELEASE.count("inputs.commit") == 1
    assert "      REQUESTED_COMMIT: ${{ inputs.commit }}" in job(RELEASE, "source")


def test_every_job_that_builds_signs_or_tags_uses_the_resolved_commit():
    # The workflow file runs from main; the released source is the resolved commit, nothing else.
    assert "github.sha" not in RELEASE and "GITHUB_SHA" not in RELEASE
    assert "context.sha" not in job(RELEASE, "package") + job(RELEASE, "draft")
    for name in ("package", "draft"):
        text = job(RELEASE, name)
        assert "RELEASE_COMMIT: ${{ needs.source.outputs.commit }}" in text, name
        checkouts = re.findall(r"- uses: actions/checkout@v\d+(?:\.\d+)*\n\s+with: \{(.*)\}", text)
        assert checkouts and all('ref: "${{ needs.source.outputs.commit }}"' in c for c in checkouts), name
        helper_checkout_count = 1 if name == "draft" else 0
        assert text.count("actions/checkout@") == len(checkouts) + helper_checkout_count, name
    package = job(RELEASE, "package")
    assert "(git rev-parse HEAD) -cne $env:RELEASE_COMMIT" in package
    assert package.count("$env:RELEASE_COMMIT") >= 7
    draft = job(RELEASE, "draft")
    assert 'git merge-base --is-ancestor "$RELEASE_COMMIT" refs/remotes/origin/main' in draft
    assert '--commit "$RELEASE_COMMIT"' in draft
    assert "sha: process.env.RELEASE_COMMIT" in draft
    assert '--verify-tag --target "$RELEASE_COMMIT"' in draft
    assert '.source_commit "release/Cytellect-Setup-$RELEASE_VERSION.json")" = "$RELEASE_COMMIT"' in draft
    # The release text names the resolved commit, and a commit without its builder stops before the tag.
    assert "release_notes.py --release-dir release --version \"$RELEASE_VERSION\" --commit \"$RELEASE_COMMIT\"" in draft
    assert draft.index("test -f scripts/release_notes.py") < draft.index("sha: process.env.RELEASE_COMMIT")
    assert "GITHUB_SHA" not in draft
    helper_checkout = next(step for step in draft.split("      - ") if "path: automation" in step)
    assert "if: env.AUTOMATIC == 'true'" in helper_checkout
    assert "sparse-checkout: scripts/windows_exe_release.cjs" in helper_checkout
    assert "persist-credentials: false" in helper_checkout
    assert "UPDATE_SIGNING_KEY" not in helper_checkout


def test_manual_and_automatic_routes_enforce_their_release_protections():
    source = job(RELEASE, "source")
    assert "github.ref == 'refs/heads/main' &&" in source
    assert "github.event_name == 'workflow_dispatch' && !inputs.automatic" in source
    assert "vars.WINDOWS_EXE_AUTO_RELEASE == 'true'" in source
    assert "github.event.workflow_run.conclusion == 'success'" in source
    assert "github.event.workflow_run.event == 'push'" in source
    assert "github.event.workflow_run.head_repository.id == github.event.repository.id" in source
    package = job(RELEASE, "package")
    assert "!cancelled() && needs.proposal-compatibility.result == 'success' &&" in package
    assert "github.ref == 'refs/heads/main' && needs.source.outputs.artifact-run == ''" in package
    assert "needs: [source, proposal-compatibility]" in job(RELEASE, "package")
    draft = job(RELEASE, "draft")
    assert "needs: [source, proposal-compatibility, package]" in draft
    assert "inputs.automatic) && 'windows-exe-publish' || 'release'" in draft
    assert "needs.proposal-compatibility.result == 'success'" in draft
    assert "if: env.AUTOMATIC == 'true'" in draft
    assert 'if [ -z "$UPDATE_SIGNING_KEY" ]' in draft
    assert "update_manifest.py verify --release-dir release" in draft and '--previous-source "$previous"' in draft
    assert "format('windows-release-idle-{0}', github.run_id) || 'windows-release' }}\n  cancel-in-progress: false" in RELEASE


def test_ai_compatibility_gates_the_exact_source_without_exposing_tokens_to_packaging():
    gate = job(RELEASE, "proposal-compatibility")
    assert "needs: [source, reserve]" in gate
    assert "needs.source.result == 'success'" in gate
    assert 'ref: "${{ needs.source.outputs.commit }}"' in gate
    assert "scripts/dev.py doctor --proposal-version" in gate
    assert "secrets.PROPOSAL_PREFLIGHT_DEVICE_TOKEN" in gate and "vars.PROPOSAL_PREFLIGHT_URL" in gate
    assert "secrets.PROPOSAL_PREFLIGHT_TOKEN" not in RELEASE
    assert "continue-on-error" not in gate and "doctor --live" not in gate
    assert "PROPOSAL_PREFLIGHT_DEVICE_TOKEN" not in job(RELEASE, "package") + job(RELEASE, "draft")


def test_main_ci_is_never_cancelled_by_a_later_merge():
    # A shared group would also let a newer main run replace a pending one, so main runs get
    # their own group; pull requests and other refs still cancel superseded runs.
    concurrency = CI.split("\nconcurrency:\n", 1)[1].split("\njobs:", 1)[0]
    assert concurrency.splitlines() == [
        "  group: ${{ github.ref == 'refs/heads/main' && format('verify-main-{0}', github.run_id)"
        " || format('verify-{0}', github.ref) }}",
        "  cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}",
    ]
