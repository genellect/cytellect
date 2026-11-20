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
