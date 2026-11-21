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
                assert "environment: proposal-preflight" in gate
            assert "doctor --proposal-version --packaged-client" in gate
            assert "persist-credentials: false" in gate  # the job that holds the token keeps no repository token
            assert "pull_request" not in (ROOT / ".github/workflows" / file).read_text(encoding="utf-8").split("jobs:")[0]
        assert [name for name, body in mapping.items() if "PROPOSAL_PREFLIGHT_DEVICE_TOKEN" in body] == gates
    store = jobs("windows-store-release.yml")
    assert "needs.proposal-compatibility.result == 'success'" in store["submit"]
    # A scheduled run asks for the owner's approval only when a package waits to be submitted.
    assert "github.event_name != 'schedule'" in store["proposal-compatibility"]
    scheduled = store["scheduled-proposal-compatibility"]
    assert "needs: select" in scheduled and "needs.select.outputs.run-id != ''" in scheduled
    assert "github.event_name == 'schedule'" in scheduled
    assert "needs.scheduled-proposal-compatibility.result == 'success'" in store["submit"]
    # `package` is skipped on a schedule: without a status function its dependants would be skipped too.
    assert "always() && !cancelled()" in scheduled and "always() && !cancelled()" in store["submit"]
