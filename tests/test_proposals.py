"""Model-drafted proposals are validated locally and never become executable by themselves."""
import io
import json
import urllib.error

import pytest
from cytellect_analysis.proposal_contracts import ProposalContext, ProposalDraft, draft_json_schema
from cytellect_analysis.proposal_validation import ProposalRejected, validate_draft
from cytellect_api import proposals
from test_api_worker import HEADERS, authenticated
from test_region_api import make_field

CONTEXT = ProposalContext(goal="核小体と核質のNCL輝度を比較したい", field_count=12, condition_count=2,
                          units_known=True, units_per_condition=[3, 3], background_available=True, channels=[{"token": "dapi", "stain": "DAPI", "role": "nuclear"},
                                                      {"token": "ncl", "stain": "NCL"}, {"token": "c3"}])


def draft(**changes):
    value = {
        "recipe": "nuclear-ncl",
        "channels": [{"token": "dapi", "stain": "DAPI", "role": "nuclear", "reason": "核染色"},
                     {"token": "ncl", "stain": "NCL", "role": "measure", "reason": "測定対象"},
                     {"token": "c3", "stain": None, "role": "measure", "reason": "名前から染色を確定できない"}],
        "metrics": [{"metric": "area", "channel": None, "region": "nucleus"},
                    {"metric": "ncl_log2_nucleoplasm_over_nucleoli", "channel": "ncl"},
                    {"metric": "mean_raw", "channel": "c3", "region": "nucleus"}],
        "statistics": {"kind": "comparison", "test": "welch-t", "omnibus": None, "association": None},
        "figures": [{"kind": "unit-comparison", "metric": "ncl_log2_nucleoplasm_over_nucleoli", "channel": "ncl"}],
        "missing_information": ["c3 の染色名"],
        "reference_ids": ["kodiha-2011", "lazic-2018"],
        "rationale": "NCLの核小体/核質比を実験単位で比較する。",
    }
    value.update(changes)
    return value


def codes(raw, context=CONTEXT):
    with pytest.raises(ProposalRejected) as error:
        validate_draft(context, raw, model="m", prompt_version="p")
    return error.value.codes


def test_valid_draft_requires_adoption_and_flags_unestablished_stains():
    result = validate_draft(CONTEXT, draft(), model="test-model", prompt_version="2026-10-05.1")
    assert result.requires_adoption is True and result.origin == "llm-draft"
    assert result.needs_confirmation == []
    assert len(result.context_sha256) == 64


@pytest.mark.parametrize(("change", "code"), [
    ({"channels": [*draft()["channels"][:2], {"token": "c3", "stain": "GFP", "role": "measure", "reason": "緑"}]},
     "proposal_stain_not_established"),
    ({"channels": draft()["channels"][:2]}, "proposal_channels_mismatch"),
    ({"metrics": [{"metric": "mean_raw", "channel": "gfp"}]}, "proposal_metric_channel_invalid"),
    ({"recipe": "supplied-regions"}, "proposal_supplied_regions_absent"),
    ({"statistics": {"kind": "comparison", "test": "paired-t", "omnibus": None, "association": None}, "figures": []},
     "proposal_pairing_required"),
    ({"rationale": "See https://example.org"}, "proposal_text_not_allowed"),
    ({"missing_information": ["run(\"Analyze Particles\")"]}, "proposal_text_not_allowed"),
    ({"figures": [{"kind": "unit-comparison", "metric": "area", "channel": "dapi"}]}, "proposal_figure_metric_not_proposed"),
])
def test_semantic_rejections(change, code):
    assert code in codes(draft(**change))


def test_absent_ncl_and_unknown_units_are_never_filled_in():
    no_ncl = ProposalContext(field_count=3, channels=[{"token": "dapi", "stain": "DAPI"}, {"token": "gfp", "stain": "GFP"}])
    raw = draft(channels=[{"token": "dapi", "stain": "DAPI", "role": "nuclear", "reason": "x"},
                          {"token": "gfp", "stain": "GFP", "role": "measure", "reason": "x"}])
    found = codes(raw, no_ncl)
    assert {"proposal_ncl_channel_not_acquired", "proposal_ncl_metric_invalid", "proposal_units_required"} <= set(found)


def test_three_conditions_require_the_matching_omnibus():
    three = CONTEXT.model_copy(update={"condition_count": 3, "units_per_condition": [3, 3, 3]})
    assert "proposal_omnibus_required" in codes(draft(), three)
    fixed = draft(statistics={"kind": "comparison", "test": "welch-t", "omnibus": "welch-anova", "association": None})
    assert validate_draft(three, fixed, model="m", prompt_version="p").draft.statistics.omnibus == "welch-anova"


def test_shape_errors_and_unregistered_values_are_rejected():
    assert codes({"recipe": "custom-macro"}) == ["proposal_shape_invalid"]
    assert codes(draft(reference_ids=["made-up-2026"])) == ["proposal_shape_invalid"]
    assert codes(draft(statistics={"kind": "comparison", "test": "glmm", "omnibus": None, "association": None})) == [
        "proposal_shape_invalid"]


def test_strict_schema_matches_the_pydantic_draft():
    schema = draft_json_schema()
    assert set(schema["required"]) == set(ProposalDraft.model_fields) == set(schema["properties"])
    assert schema["additionalProperties"] is False
    stats = schema["properties"]["statistics"]
    assert "regression" not in json.dumps(stats)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


ACTIN_DRAFT = {
    "recipe": "supplied-regions",
    "channels": [{"token": "ch1", "stain": None, "role": "measure", "reason": "既存の領域内を測定する"}],
    "metrics": [{"metric": "area", "channel": None, "region": "supplied"}, {"metric": "mean_raw", "channel": "ch1", "region": "supplied"}],
    "statistics": {"kind": "descriptive", "test": None, "omnibus": None, "association": None},
    "figures": [{"kind": "field-distribution", "metric": "mean_raw", "channel": "ch1", "region": "supplied"}],
    "missing_information": ["独立した実験単位"], "reference_ids": ["senft-2023"], "rationale": "視野ごとの分布を示す。",
}


def configured(tmp_path, monkeypatch, reply, *, upload=True):
    client, app, settings = authenticated(tmp_path)
    object.__setattr__(settings, "proposal_url", "https://proposal.example")
    object.__setattr__(settings, "proposal_token", "device-secret")
    calls = []

    def urlopen(request, timeout):
        calls.append(json.loads(request.data))
        assert request.headers["Authorization"] == "Bearer device-secret"
        assert request.headers["User-agent"] == "Cytellect/0.1"
        return reply(request)
    monkeypatch.setattr(proposals._OPENER, "open", urlopen)
    wid = client.post("/v1/workspaces", json={"title": "w"}, headers=HEADERS).json()["id"]
    if upload:
        assert make_field(client, wid).status_code == 201
    return client, wid, calls


def test_only_a_goal_is_asked_and_the_context_is_derived_from_the_workspace(tmp_path, monkeypatch):
    body = json.dumps({"draft": ACTIN_DRAFT, "model": "gpt-6.1-sol", "prompt_version": "2026-10-06.1"}).encode()
    client, wid, calls = configured(tmp_path, monkeypatch, lambda request: FakeResponse(body))
    first = client.post(f"/v1/workspaces/{wid}/proposal-drafts", json={"goal": "細胞ごとのアクチン輝度", "transmission_confirmed": True}, headers=HEADERS)
    second = client.post(f"/v1/workspaces/{wid}/proposal-drafts", json={"goal": "細胞ごとのアクチン輝度", "transmission_confirmed": True}, headers=HEADERS)
    assert first.status_code == 200, first.text
    assert first.json() == second.json() and len(calls) == 1
    assert first.json()["channels"] == [{"token": "ch1", "channel_id": "actin", "stain": None}]
    assert first.json()["proposal"]["needs_confirmation"] == []
    sent = calls[0]["context"]
    # Derived, not entered: counts and flags only; no labels, file names, metadata values or pixels.
    assert sent == {"protocol": "1.1.0", "goal": "細胞ごとのアクチン輝度", "channels": [{"token": "ch1", "stain": None, "role": None}],
                    "field_count": 1, "condition_count": 1, "units_known": False, "pairing_known": False,
                    "supplied_regions": True, "measured_table": False, "background_available": False,
                    "units_per_condition": [0], "complete_pair_count": 0}
    assert "Actin" not in json.dumps(calls) and "untrusted-original-name" not in json.dumps(calls)
    assert client.post(f"/v1/workspaces/{wid}/proposal-drafts", json={"goal": "x", "field_count": 9, "transmission_confirmed": True},
                       headers=HEADERS).status_code == 422
    # An empty goal is valid: the proposal is built from the images alone.
    assert client.post(f"/v1/workspaces/{wid}/proposal-drafts", json={"transmission_confirmed": True}, headers=HEADERS).status_code == 200


def test_route_rejects_invalid_drafts_and_maps_service_failures(tmp_path, monkeypatch):
    bad = json.dumps({"draft": {**ACTIN_DRAFT, "rationale": "https://x"}, "model": "gpt-6.1-sol", "prompt_version": "2026-10-06.1"}).encode()
    client, wid, _ = configured(tmp_path, monkeypatch, lambda request: FakeResponse(bad))
    response = client.post(f"/v1/workspaces/{wid}/proposal-drafts", json={"transmission_confirmed": True}, headers=HEADERS)
    assert response.status_code == 502
    assert response.json()["detail"] == {"code": "proposal_rejected", "reasons": ["proposal_text_not_allowed"]}

    def quota(request):
        raise urllib.error.HTTPError(request.full_url, 429, "quota", {}, None)
    client, wid, _ = configured(tmp_path / "q", monkeypatch, quota)
    response = client.post(f"/v1/workspaces/{wid}/proposal-drafts", json={"transmission_confirmed": True}, headers=HEADERS)
    assert (response.status_code, response.json()["detail"]) == (429, "proposal_quota_exhausted")


def test_route_needs_images_is_disabled_without_configuration_and_checks_ownership(tmp_path, monkeypatch):
    client, wid, calls = configured(tmp_path, monkeypatch, lambda request: FakeResponse(b"{}"), upload=False)
    assert client.post(f"/v1/workspaces/{wid}/proposal-drafts", json={"transmission_confirmed": True}, headers=HEADERS).status_code == 409
    assert calls == []
    other, _, _ = authenticated(tmp_path / "plain")
    wid = other.post("/v1/workspaces", json={"title": "w"}, headers=HEADERS).json()["id"]
    assert make_field(other, wid).status_code == 201
    response = other.post(f"/v1/workspaces/{wid}/proposal-drafts", json={"transmission_confirmed": True}, headers=HEADERS)
    assert (response.status_code, response.json()["detail"]) == (503, "proposal_service_disabled")
    assert other.post("/v1/workspaces/missing/proposal-drafts", json={"transmission_confirmed": True}, headers=HEADERS).status_code == 404


@pytest.mark.parametrize(("failure", "expected"), [
    ({"code": "proposal_service_disabled"}, "proposal_service_disabled"),
    ({"code": "budget_reconciliation_required"}, "proposal_budget_reconciliation_required"),
    ({"code": "model_unavailable"}, "proposal_model_unavailable"),
    ({"code": "model_unavailable", "provider_error_code": "invalid_json_schema", "provider_http_status": 400}, "proposal_provider_invalid_json_schema"),
    ({"code": "model_unavailable", "provider_error_code": "insufficient_quota", "provider_http_status": 429}, "proposal_provider_insufficient_quota"),
    ({"code": "model_unavailable", "provider_error_code": "private-unknown", "provider_http_status": 403}, "proposal_provider_http_403"),
    ({"code": "model_unavailable", "provider_error_code": ["private-context"], "provider_http_status": True}, "proposal_model_unavailable"),
    ({"code": "model_unavailable", "provider_http_status": "private-status"}, "proposal_model_unavailable"),
    ({"code": "private-unknown"}, "proposal_service_unavailable"),
])
def test_sanitized_service_diagnostics_are_distinct_and_never_echo_raw_body(tmp_path, monkeypatch, failure, expected):
    def fail(request):
        payload = {**failure, "message": "private-key private-research-context", "headers": {"authorization": "private-token"}}
        raise urllib.error.HTTPError(request.full_url, 503, "private-provider-message", {}, io.BytesIO(json.dumps(payload).encode()))
    client, wid, calls = configured(tmp_path, monkeypatch, fail)
    response = client.post(f"/v1/workspaces/{wid}/proposal-drafts", json={"transmission_confirmed": True}, headers=HEADERS)
    assert response.status_code == 503
    assert response.json() == {"detail": expected}
    assert "private" not in response.text and len(calls) == 1


@pytest.mark.parametrize("body", [b"<html>private upstream error</html>", b"x" * 2049])
def test_malformed_or_oversized_service_diagnostics_are_discarded(tmp_path, monkeypatch, body):
    def fail(request):
        raise urllib.error.HTTPError(request.full_url, 503, "error", {}, io.BytesIO(body))
    client, wid, _ = configured(tmp_path, monkeypatch, fail)
    response = client.post(f"/v1/workspaces/{wid}/proposal-drafts", json={"transmission_confirmed": True}, headers=HEADERS)
    assert response.json() == {"detail": "proposal_service_unavailable"}


def test_nothing_is_sent_without_the_researchers_transmission_confirmation(tmp_path, monkeypatch):
    client, wid, calls = configured(tmp_path, monkeypatch, lambda request: FakeResponse(b"{}"))
    for body in ({}, {"transmission_confirmed": False}, {"goal": "x"}):
        response = client.post(f"/v1/workspaces/{wid}/proposal-drafts", json=body, headers=HEADERS)
        assert (response.status_code, response.json()["detail"]) == (428, "proposal_transmission_not_confirmed")
    assert client.post(f"/v1/workspaces/{wid}/proposal-drafts", json={"transmission_confirmed": "yes"},
                       headers=HEADERS).status_code == 422
    assert calls == []


def test_redirects_are_refused_so_the_device_credential_never_follows_them():
    import http.server
    import threading
    hits = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            hits.append(("POST", self.headers.get("Authorization")))
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/elsewhere")
            self.end_headers()

        def do_GET(self):
            hits.append(("GET", self.headers.get("Authorization")))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass
    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    settings = type("S", (), {"proposal_url": f"http://127.0.0.1:{server.server_port}", "proposal_token": "device-secret",
                              "proposal_timeout_seconds": 5})()
    with pytest.raises(proposals.ProposalServiceError):
        proposals.request_draft(settings, CONTEXT)
    thread.join(5)
    server.server_close()
    assert hits == [("POST", "Bearer device-secret")]
