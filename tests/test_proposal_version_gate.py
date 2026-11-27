"""Protocol-only synthetic probes: no workspace, GPU, model or billed admission."""
import argparse
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import dev  # noqa: E402
from proposal_preflight import check_versions, version_payloads  # noqa: E402


def test_worker_fixture_is_the_current_clients_validated_payload():
    assert json.loads((ROOT / "fixtures/proposal-version-probes.json").read_text()) == version_payloads()


def test_probe_sends_the_context_the_checked_prompt_reads():
    # A pinned earlier prompt (a service not yet updated) is sent the earlier context by real requests; the check
    # sends the same pair, so the service that answers it is not reported as incompatible (#284 W7).
    assert version_payloads()[0]["context"]["protocol"] == "1.3.0"
    pinned = version_payloads("2026-11-19.1")[0]
    assert (pinned["prompt_version"], pinned["context"]["protocol"]) == ("2026-11-19.1", "1.2.0")


@pytest.mark.parametrize("response,accepted", [((400, "request_id_required"), True),
    ((400, "prompt_version_unsupported"), False), ((400, "request_invalid"), False),
    ((401, "unauthorized"), False), ((503, "proposal_service_disabled"), False),
    ((200, ""), False), ((0, "unreachable"), False)])
def test_only_the_pre_admission_stop_proves_compatibility(response, accepted):
    requests = []
    def probe(request, timeout):
        requests.append(request)
        assert timeout == 30 and not request.has_header("Idempotency-key")
        assert request.get_header("Authorization") == "Bearer test-only-token"
        assert request.get_header("User-agent") == "Cytellect/0.1"
        return response
    result = check_versions("https://service.example", "test-only-token", probe)
    assert len(requests) == len(result) == 2  # No retry.
    assert all(item[2] is accepted for item in result)
    assert "test-only-token" not in str(result)
    assert [json.loads(request.data)["prompt_version"] for request in requests] == [item["prompt_version"] for item in version_payloads()]


@pytest.mark.parametrize("url,token", [("", ""), ("http://service.example", "token"),
    ("https://service.example", ""), ("https://user:password@service.example", "token")])
def test_unconfigured_or_unsafe_service_never_receives_a_credential(url, token):
    def refuse(*args, **kwargs):
        raise AssertionError("must not make an HTTP request")
    assert not check_versions(url, token, refuse)[0][2]


def test_doctor_compatibility_mode_does_not_probe_gpu_or_require_tools(monkeypatch, capsys):
    import proposal_preflight
    def refuse(*args, **kwargs):
        raise AssertionError("normal doctor must not run")
    monkeypatch.setattr(dev, "pinned_versions", refuse)
    monkeypatch.setattr(proposal_preflight, "check_versions", lambda *args: [("/v1/proposals", "test", False, "unsupported")])
    with pytest.raises(SystemExit, match="do not distribute"):
        dev.doctor(argparse.Namespace(proposal_version=True))
    assert "[NG]" in capsys.readouterr().out


def test_a_different_service_cannot_certify_the_packaged_client():
    def refuse(*args, **kwargs):
        raise AssertionError("wrong service must not receive the token")
    assert not check_versions("https://other.example", "test-token", refuse,
                              expected_service="https://api.cytellect.app")[0][2]


def test_effective_operator_prompt_overrides_are_checked():
    sent = []
    def probe(request, timeout):
        sent.append(json.loads(request.data)["prompt_version"])
        return 400, "request_id_required"
    result = check_versions("https://service.example", "test-token", probe,
                            proposal_prompt="configured-proposal", discussion_prompt="configured-discussion")
    assert all(row[2] for row in result)
    assert sent == ["configured-proposal", "configured-discussion"]


def test_both_distribution_paths_require_the_protected_gate():
    import re
    def jobs(file):
        text = (ROOT / ".github/workflows" / file).read_text(encoding="utf-8")
        chunks = re.split(r"(?m)^  ([\w-]+):\s*$", text[text.index("jobs:\n") + 6:])
        return dict(zip(chunks[1::2], chunks[2::2], strict=True))
    def ancestors(mapping, job):
        found = re.search(r"(?m)^    needs: (.+)$", mapping[job])
        parents = [part.strip() for part in found[1].strip("[]").split(",")] if found else []
        return set(parents) | {ancestor for parent in parents for ancestor in ancestors(mapping, parent)}
    for file, targets in [("local-release.yml", ["package"]), ("windows-store-release.yml", ["package", "submit"])]:
        mapping = jobs(file)
        for target in targets:
            assert "proposal-compatibility" in ancestors(mapping, target)
        gates = [name for name in mapping if name.endswith("proposal-compatibility")]
        for gate in (mapping[name] for name in gates):
            if file == "local-release.yml":
                assert "inputs.automatic) && 'windows-exe-preflight' || 'proposal-preflight'" in gate
            else:
                # Merging into main approves the Store submission: its check waits for no reviewer.
                assert "environment: windows-exe-preflight" in gate
                assert "proposal-preflight" not in gate
            assert "doctor --proposal-version --packaged-client" in gate
            assert "persist-credentials: false" in gate  # the job that holds the token keeps no repository token
            assert "pull_request" not in (ROOT / ".github/workflows" / file).read_text(encoding="utf-8").split("jobs:")[0]
        assert [name for name, body in mapping.items() if "PROPOSAL_PREFLIGHT_DEVICE_TOKEN" in body] == gates
    store = jobs("windows-store-release.yml")
    assert list(store) == ["source", "proposal-compatibility", "package", "submit"]
    assert "needs.proposal-compatibility.result == 'success'" in store["submit"]
    assert 'ref: "${{ needs.source.outputs.commit }}"' in store["proposal-compatibility"]
    # `package` is skipped when the commit is already built: without a status function `submit` would be skipped too.
    assert "always() && !cancelled()" in store["submit"]
    assert "always()" not in store["package"] and "needs: [source, proposal-compatibility]" in store["package"]


def test_the_store_route_submits_only_the_selected_verified_commit_without_a_reviewer():
    text = (ROOT / ".github/workflows/windows-store-release.yml").read_text(encoding="utf-8")
    header, body = text.split("jobs:\n", 1)
    assert "workflow_run:\n    workflows: [Verify]\n    branches: [main]\n    types: [completed]" in header
    assert "  push:" not in header and "schedule:" in header and "workflow_dispatch:" in header
    assert "permissions:\n  contents: read\n" in header
    # The run's own SHA is the head of main, not the source: no job may build or submit it.
    assert "github.sha" not in body and "GITHUB_SHA" not in body and "context.sha" not in body
    assert "ls-remote" not in body
    import re
    chunks = re.split(r"(?m)^  ([\w-]+):\s*$", body)
    store = dict(zip(chunks[1::2], chunks[2::2], strict=True))
    source = store["source"]
    # The code that reads main's history sees main as it is now, not the commit this run started from.
    assert "ref: main\n          fetch-depth: 0" in source
    for job in ("package", "submit"):
        assert "path: automation\n          ref: main\n          fetch-depth: 0" in store[job]
    for condition in ("github.ref == 'refs/heads/main'", "github.repository == 'genellect/cytellect'",
                      "github.event.workflow_run.conclusion == 'success'",
                      "github.event.workflow_run.event == 'push'",
                      "github.event.workflow_run.head_branch == 'main'",
                      "github.event.workflow_run.head_repository.id == github.event.repository.id"):
        assert condition in source
    assert "selectStore(github, context, core)" in source and "environment:" not in source
    # The check and the build check out the selected commit; the submission checks out only main
    # (its script runs from main, the package is the one built from the selected commit).
    for name, expected in (("proposal-compatibility", 1), ("package", 1), ("submit", 0)):
        checkouts = re.findall(r"- uses: actions/checkout@[0-9a-f]{40} # v\d+(?:\.\d+)*\n\s+with: \{(.*)\}", store[name])
        assert checkouts == ['ref: "${{ needs.source.outputs.commit }}", persist-credentials: false'] * expected, name
    package = store["package"]
    assert "(git rev-parse HEAD).Trim() -cne $env:STORE_COMMIT" in package
    assert "--commit $env:STORE_COMMIT" in package
    assert "name: store-msix-${{ needs.source.outputs.commit }}" in package
    # A run that waited for a build of the same commit reuses its package: the check runs first, from
    # main, and every later step runs only when nothing was built meanwhile.
    steps = re.split(r"(?m)^      - ", package.split("    steps:\n", 1)[1])[1:]
    assert "path: automation" in steps[0] and "ref: main" in steps[0]
    assert "builtStore(github, context, core, release.mainHistory('automation'))" in steps[1]
    assert "id: built" in steps[1] and "if:" not in steps[1]
    assert all("if: steps.built.outputs.artifact-run == ''" in step for step in steps[2:]), steps[2:]
    assert "Remove-Item -LiteralPath automation" in steps[2]
    assert "actions: read" in package and "artifact-run: ${{ steps.built.outputs.artifact-run }}" in package
    submit = store["submit"]
    assert ("run-id: ${{ needs.source.outputs.artifact-run || needs.package.outputs.artifact-run || "
            "github.run_id }}") in submit
    assert "vars.STORE_SUBMISSIONS_ENABLED == 'true'" in submit
    assert "environment: store-release" in submit
    # Submissions stay serial; a run that builds or submits nothing joins neither shared group.
    assert ("(needs.package.result == 'skipped' && needs.source.outputs.artifact-run != '')) &&\n"
            "        'windows-store-submission' || format('windows-store-submission-idle-{0}', github.run_id) }}\n"
            "      cancel-in-progress: false") in submit
    assert submit.count("windows-store-submission'") == 1 and "github.ref" not in package + submit
    # One build per commit; a later run of the same commit waits instead of cancelling it.
    assert ("format('store-msix-build-{0}', needs.source.outputs.commit) ||\n"
            "        format('store-msix-build-idle-{0}', github.run_id) }}\n      cancel-in-progress: false") in package
    assert "cancel-in-progress: true" not in text
    for job in (package, submit):
        group = job.split("concurrency:\n", 1)[1].split("cancel-in-progress", 1)[0]
        assert "needs.source.outputs.commit != ''" in group
    # The freshness check runs from main and precedes every step that touches the package or a secret.
    helper = next(step for step in submit.split("      - ") if "path: automation" in step)
    assert ("sparse-checkout: |\n            scripts/windows_exe_release.cjs\n"
            "            scripts/submit_windows_msix.py\n") in helper and "persist-credentials: false" in helper
    assert "ref: main" in helper
    assert "confirmStore(github, context, core, release.mainHistory('automation'))" in submit
    assert submit.index("confirmStore") < submit.index("download-artifact") < submit.index("STORE_CLIENT_SECRET")
    assert submit.count("if: steps.newest.outputs.current == 'true'") == 3
    # The script runs from main, so an older selected commit's copy (without `--history`) is never used.
    assert ('python -B automation/scripts/submit_windows_msix.py --commit "$STORE_COMMIT" --history automation'
            in submit)
    assert "python -B scripts/" not in submit
    receipt = submit.split("name: store-submitted-${{ needs.source.outputs.commit }}", 1)[1]
    # The receipt keeps the Store from going back; it outlives a package (14 days).
    assert "retention-days: 90" in receipt
    # Store credentials reach the submission only; every third-party action is pinned to a commit.
    assert [name for name, job in store.items() if "STORE_CLIENT_SECRET" in job] == ["submit"]
    assert all(re.fullmatch(r"[\w-]+/[\w-]+@[0-9a-f]{40}", use) for use in re.findall(r"uses: (\S+)", body))
    assert "contents: write" not in text and "id-token" not in text
