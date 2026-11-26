"""Model-drafted proposals are validated locally and never become executable by themselves."""
import io
import json
import urllib.error

import pytest
from cytellect_analysis.proposal_contracts import (
    PROPOSAL_PROMPT_VERSION,
    ProposalContext,
    ProposalDraft,
    draft_json_schema,
)
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


def test_a_long_explanation_is_kept_as_written():
    """The explanation's length is the model's choice (plan §8): long reasons and many open questions are kept."""
    rationale = "代表視野では NCL が核小体に集まり、DAPI の核は互いに接していない。" * 40
    channels = [{**channel, "reason": channel["reason"] * 60} for channel in draft()["channels"]]
    missing = [f"確認事項 {index}：独立実験の数と撮影条件" for index in range(12)]
    result = validate_draft(CONTEXT, draft(rationale=rationale, channels=channels, missing_information=missing),
                            model="m", prompt_version="p")
    assert result.draft.rationale == rationale and len(result.draft.missing_information) == 12
    assert result.draft.channels[0].reason == channels[0]["reason"]


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
    ({"channels": [*draft()["channels"][:2], {"token": "c3", "stain": "www.example.org", "role": "measure", "reason": "x"}]},
     "proposal_text_not_allowed"),
    ({"figure_presentation": {"composition": "quantification", "legend_terms": {
        "cell_line": "HeLa", "treatment": "see https://example.org", "stains": None}}}, "proposal_text_not_allowed"),
    ({"figure_presentation": {"composition": "quantification", "legend_terms": {
        "cell_line": None, "treatment": None, "stains": "<script>x</script>"}}}, "proposal_text_not_allowed"),
    ({"figures": [{"kind": "unit-comparison", "metric": "area", "channel": "dapi"}]}, "proposal_figure_metric_not_proposed"),
])
def test_semantic_rejections(change, code):
    assert code in codes(draft(**change))


def test_ordinary_biological_words_in_stains_and_legend_terms_are_kept():
    """Only links and markup are refused outside the explanations: "macro" and "import" are also biology."""
    context = CONTEXT.model_copy(update={"channels": [*CONTEXT.channels[:2], CONTEXT.channels[2].model_copy(update={"stain": "macro-H2A"})]})
    raw = draft(channels=[*draft()["channels"][:2], {"token": "c3", "stain": "macro-H2A", "role": "measure", "reason": "測定対象"}],
                figure_presentation={"composition": "quantification", "legend_terms": {
                    "cell_line": "HeLa", "treatment": "nuclear import inhibitor, 1 h", "stains": "anti-macro-H2A"}})
    result = validate_draft(context, raw, model="m", prompt_version="p")
    assert result.draft.figure_presentation.legend_terms.treatment == "nuclear import inhibitor, 1 h"


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
    # Prompt 2026-11-26.1 adds the kind of request (#284 W7) and 2026-11-19.1 the figure presentation; the earlier
    # schemas keep the other fields.
    schema = draft_json_schema(intent=True)
    intent = {"intent", "answer", "scope", "choices", "assignments"}
    assert set(schema["required"]) == set(ProposalDraft.model_fields) == set(schema["properties"])
    assert set(draft_json_schema(figure=True)["properties"]) == set(ProposalDraft.model_fields) - intent
    assert set(draft_json_schema()["properties"]) == set(ProposalDraft.model_fields) - {"figure_presentation"} - intent
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
        uploaded = make_field(client, wid)
        assert uploaded.status_code == 201, uploaded.text
    return client, wid, calls


def test_only_a_goal_is_asked_and_the_context_is_derived_from_the_workspace(tmp_path, monkeypatch):
    body = json.dumps({"draft": ACTIN_DRAFT, "model": "gpt-6.1-sol", "prompt_version": PROPOSAL_PROMPT_VERSION}).encode()
    client, wid, calls = configured(tmp_path, monkeypatch, lambda request: FakeResponse(body))
    first = client.post(f"/v1/workspaces/{wid}/proposal-drafts", json={"goal": "細胞ごとのアクチン輝度", "transmission_confirmed": True}, headers=HEADERS)
    second = client.post(f"/v1/workspaces/{wid}/proposal-drafts", json={"goal": "細胞ごとのアクチン輝度", "transmission_confirmed": True}, headers=HEADERS)
    assert first.status_code == 200, first.text
    # The same question in the same context is answered from the record: the model is called once, and each
    # sending is its own message (#284 W2).
    without = lambda value: {key: item for key, item in value.items() if key != "message"}  # noqa: E731
    assert without(first.json()) == without(second.json()) and len(calls) == 1
    assert first.json()["message"]["id"] != second.json()["message"]["id"]
    assert second.json()["message"] | {"id": None, "created": None} == first.json()["message"] | {"id": None, "created": None}
    assert first.json()["channels"] == [{"token": "ch1", "channel_id": "actin", "stain": None}]
    assert first.json()["proposal"]["needs_confirmation"] == []
    sent = calls[0]["context"]
    # Derived, not entered (docs/drafts/llm-assistant/plan.md): the model reads the researcher's channel label and
    # field records, the counts and flags, and a downscaled preview of a representative field. No paths.
    fields_sent = sent.pop("fields")
    assert sent == {"protocol": "1.3.0", "goal": "細胞ごとのアクチン輝度",
                    "channels": [{"token": "ch1", "stain": None, "role": None, "label": "Actin"}],
                    "field_count": 1, "condition_count": 1, "units_known": False, "pairing_known": False,
                    "supplied_regions": True, "measured_table": False, "background_available": False,
                    "units_per_condition": [0], "complete_pair_count": 0,
                    "current_processing": None, "previous_goal": "", "previous_proposal": None,
                    "current_background": None, "current_gfp": None,
                    "negative_control_fields_known": False, "acquired_dates_known": False,
                    "image_metadata": [{"width": 12, "height": 12, "axes": "YX", "input_mode": "native",
                                        "pixel_size_x_um": None, "pixel_size_y_um": None}]}
    # Context 1.3.0 (#284 W7): an opaque identifier, and no names the field was added with (this upload has none).
    assert len(fields_sent) == 1 and set(fields_sent[0]) == {"id", "name", "condition", "experimental_unit", "pair", "acquisition_date"}
    assert fields_sent[0]["id"] == "f1" and [link["token"] for link in first.json()["fields"]] == ["f1"]
    assert all("/" not in (value or "") and "\\" not in (value or "") for value in fields_sent[0].values())
    [preview] = calls[0]["previews"]
    assert preview["channel"] == "ch1" and preview["png_base64"].startswith("iVBORw0KGgo")
    assert str(tmp_path) not in json.dumps(calls) and "workspaces" not in json.dumps(calls)
    assert client.post(f"/v1/workspaces/{wid}/proposal-drafts", json={"goal": "x", "field_count": 9, "transmission_confirmed": True},
                       headers=HEADERS).status_code == 422
    # An empty goal is valid: the proposal is built from the images alone.
    assert client.post(f"/v1/workspaces/{wid}/proposal-drafts", json={"transmission_confirmed": True}, headers=HEADERS).status_code == 200


def test_route_rejects_invalid_drafts_and_maps_service_failures(tmp_path, monkeypatch):
    bad = json.dumps({"draft": {**ACTIN_DRAFT, "rationale": "https://x"}, "model": "gpt-6.1-sol", "prompt_version": PROPOSAL_PROMPT_VERSION}).encode()
    client, wid, _ = configured(tmp_path, monkeypatch, lambda request: FakeResponse(bad))
    response = client.post(f"/v1/workspaces/{wid}/proposal-drafts", json={"transmission_confirmed": True}, headers=HEADERS)
    assert response.status_code == 502
    assert response.json()["detail"] == {"code": "proposal_rejected", "reasons": ["proposal_text_not_allowed"]}

    def quota(request):
        raise urllib.error.HTTPError(request.full_url, 429, "quota", {}, None)
    client, wid, _ = configured(tmp_path / "q", monkeypatch, quota)
    response = client.post(f"/v1/workspaces/{wid}/proposal-drafts", json={"transmission_confirmed": True}, headers=HEADERS)
    assert (response.status_code, response.json()["detail"]) == (429, "proposal_quota_exhausted")


def test_a_refused_draft_still_answers_and_every_message_is_recorded_without_its_text_in_logs(tmp_path, monkeypatch, caplog):
    """#284 W2 (judgement 1 and 3, synthetic provider): a well-formed draft refused for its settings returns its
    answer with the reasons; a malformed one or a refused text keeps only the reasons. Nothing is applied."""
    refused_draft = {**ACTIN_DRAFT, "channels": [], "rationale": "ch1 は Actin と記録されています。核染色のチャンネルはありません。",
                     "missing_information": ["核染色のチャンネル"]}
    replies = iter([refused_draft, {"recipe": "nonsense"}, {**ACTIN_DRAFT, "rationale": "see https://x"}])
    client, wid, calls = configured(tmp_path, monkeypatch, lambda request: FakeResponse(json.dumps(
        {"draft": next(replies), "model": "gpt-6.1-sol", "prompt_version": PROPOSAL_PROMPT_VERSION}).encode()))
    question = "この画像のチャンネル名を教えてください。まだ測定を実行しないでください。"
    answered = client.post(f"/v1/workspaces/{wid}/proposal-drafts", json={"goal": question, "transmission_confirmed": True}, headers=HEADERS)
    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["proposal"] is None
    assert body["message"] | {"id": None, "created": None} == {
        "id": None, "created": None, "field_id": None, "text": question, "state": "answered",
        "reply": "ch1 は Actin と記録されています。核染色のチャンネルはありません。\n核染色のチャンネル",
        "applicable": False, "reasons": ["proposal_channels_mismatch", "proposal_metric_channel_invalid"], "stage": "validation", "effect": "none",
        # A refused answer records no proposal, so a reload has nothing more to read for it.
        "restorable": False, "suggests_assignments": False}
    # Applying a refused answer is refused.
    effect = client.patch(f"/v1/workspaces/{wid}/assistant-messages/{body['message']['id']}", json={"effect": "settings"}, headers=HEADERS)
    assert effect.status_code == 409 and effect.json()["detail"] == "assistant_message_not_applicable"
    # A malformed draft and a refused text keep no text, only the reasons; each is resent under its own message.
    malformed = client.post(f"/v1/workspaces/{wid}/proposal-drafts", json={"goal": question, "transmission_confirmed": True, "retry_failed": True}, headers=HEADERS)
    assert malformed.status_code == 502 and malformed.json()["detail"] == {"code": "proposal_rejected", "reasons": ["proposal_shape_invalid"]}
    listed = client.get(f"/v1/workspaces/{wid}/assistant-messages", headers=HEADERS).json()["messages"]
    failed = listed[-1]
    assert (failed["state"], failed["reply"], failed["reasons"], failed["stage"]) == ("failed", None, ["proposal_shape_invalid"], "validation")
    again = client.post(f"/v1/workspaces/{wid}/proposal-drafts", json={"goal": question, "transmission_confirmed": True,
                                                                         "retry_failed": True, "message_id": failed["id"]}, headers=HEADERS)
    assert again.status_code == 502 and again.json()["detail"]["reasons"] == ["proposal_text_not_allowed"]
    listed = client.get(f"/v1/workspaces/{wid}/assistant-messages", headers=HEADERS).json()["messages"]
    assert [(item["state"], item["reasons"]) for item in listed] == [("answered", ["proposal_channels_mismatch", "proposal_metric_channel_invalid"]), ("failed", ["proposal_text_not_allowed"])]
    assert len(calls) == 3
    # The researcher's text and the model's text never reach the logs.
    assert question not in caplog.text and "Actin と記録" not in caplog.text
    # Without the confirmation nothing is sent and no message is made; another workspace's message cannot be resent.
    assert client.post(f"/v1/workspaces/{wid}/proposal-drafts", json={"goal": "x"}, headers=HEADERS).status_code == 428
    other = client.post("/v1/workspaces", json={"title": "o"}, headers=HEADERS).json()["id"]
    assert client.post(f"/v1/workspaces/{other}/proposal-drafts", json={"goal": "x", "transmission_confirmed": True,
                                                                         "message_id": failed["id"]}, headers=HEADERS).status_code in (404, 409)
    assert len(client.get(f"/v1/workspaces/{wid}/assistant-messages", headers=HEADERS).json()["messages"]) == 2


def test_every_rejection_code_is_listed():
    import re
    from pathlib import Path

    from cytellect_analysis import proposal_validation
    source = Path(proposal_validation.__file__).read_text(encoding="utf-8")
    assert set(re.findall(r'"(proposal_[a-z_]+)"', source)) == set(proposal_validation.REJECTION_CODES)


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


def test_a_prompt_version_the_service_does_not_know_is_a_version_mismatch(tmp_path, monkeypatch):
    # The service is deployed before a release that sends a new prompt version; until then it answers 400. The page
    # then says the service is behind the app, not that the connection failed.
    def fail(request):
        raise urllib.error.HTTPError(request.full_url, 400, "bad request", {}, io.BytesIO(b'{"code": "prompt_version_unsupported"}'))
    client, wid, calls = configured(tmp_path, monkeypatch, fail)
    response = client.post(f"/v1/workspaces/{wid}/proposal-drafts", json={"transmission_confirmed": True}, headers=HEADERS)
    assert (response.status_code, response.json()) == (502, {"detail": "proposal_service_version_mismatch"})
    assert len(calls) == 1


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
                              "proposal_timeout_seconds": 5,
                              "proposal_prompt_version": "test"})()
    with pytest.raises(proposals.ProposalServiceError):
        proposals.request_draft(settings, CONTEXT)
    thread.join(5)
    server.server_close()
    assert hits == [("POST", "Bearer device-secret")]


def test_preimport_planning_has_no_invented_acquisitions():
    context = ProposalContext(goal="核の面積を群間比較したい", channels=[], field_count=0)
    raw = draft(recipe="none", channels=[], metrics=[], figures=[],
                statistics={"kind": "descriptive", "test": None, "omnibus": None, "association": None},
                missing_information=["核染色と独立実験数"], rationale="核染色の画像から面積を測定し、独立実験単位で集計します。")
    assert validate_draft(context, raw, model="test", prompt_version="test").draft.recipe == "none"
    assert "proposal_images_not_registered" in codes({**raw, "recipe": "nuclear-intensity"}, context)
    assert "proposal_images_not_registered" in codes({**raw, "metrics": [{"metric": "area", "channel": None}]}, context)
    with pytest.raises(ValueError):
        ProposalContext(goal="planning", channels=[], field_count=1)
    with pytest.raises(ValueError):
        ProposalContext(goal="planning", channels=[], field_count=0, units_known=True)


def test_preimport_context_from_real_empty_workspace(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", json={"title": "planning"}, headers=HEADERS).json()["id"]
    context, links = proposals.build_context(app.state.store, wid, "核面積を比較したい")
    assert context.field_count == 0 and context.channels == [] and links == []
    assert not context.units_known and not context.background_available


def test_previews_follow_the_researchers_setting(tmp_path, monkeypatch):
    """With previews turned off in settings, only the context is sent (docs/drafts/llm-assistant/plan.md §4.5)."""
    body = json.dumps({"draft": ACTIN_DRAFT, "model": "claude-opus-5-5", "prompt_version": PROPOSAL_PROMPT_VERSION}).encode()
    client, wid, calls = configured(tmp_path, monkeypatch, lambda request: FakeResponse(body))
    response = client.post(f"/v1/workspaces/{wid}/proposal-drafts",
                           json={"goal": "核の大きさ", "transmission_confirmed": True, "include_previews": False}, headers=HEADERS)
    assert response.status_code == 200, response.text
    assert "previews" not in calls[0]
    assert response.json()["proposal"]["model"] == "claude-opus-5-5"


def test_a_preview_failure_sends_the_request_without_previews(tmp_path, monkeypatch):
    """Previews are optional: an unreadable array never blocks the proposal or marks it failed."""
    body = json.dumps({"draft": ACTIN_DRAFT, "model": "gpt-6.1-sol", "prompt_version": PROPOSAL_PROMPT_VERSION}).encode()
    client, wid, calls = configured(tmp_path, monkeypatch, lambda request: FakeResponse(body))

    def broken(*args, **kwargs):
        raise OSError("unreadable channel array")
    monkeypatch.setattr(proposals, "representative_previews", broken)
    response = client.post(f"/v1/workspaces/{wid}/proposal-drafts", json={"goal": "核の大きさ", "transmission_confirmed": True},
                           headers=HEADERS)
    assert response.status_code == 200, response.text
    assert "previews" not in calls[0]


def test_previews_skip_fields_the_researcher_excluded(tmp_path, monkeypatch):
    client, wid, calls = configured(tmp_path, monkeypatch, lambda request: FakeResponse(b"{}"))
    store = client.app.state.store
    [field] = store.rows(proposals.fields, workspace_id=wid)
    links = [proposals.ProposalChannelLink(token="ch1", channel_id=field["image_info"]["channels"][0]["channel_id"], stain=None)]
    assert proposals.representative_previews(store, wid, links)
    monkeypatch.setattr("cytellect_api.workspace_selection.selection_at",
                        lambda conn, workspace: {"entries": [{"field_id": field["id"], "exclusion_reason": "out_of_focus"}]})
    assert proposals.representative_previews(store, wid, links) == []



def test_previews_average_blocks_so_small_structures_stay_visible():
    """A 1-px spot survives the reduction to 512 px (review of #231): every-n-th-pixel sampling dropped it."""
    import numpy as np
    from cytellect_api.proposals import _block_mean
    plane = np.zeros((2048, 2048), dtype=np.uint16)
    plane[101, 102] = 4000
    reduced = _block_mean(plane, 512)
    assert reduced.shape == (512, 512) and reduced[25, 25] == 250
    assert _block_mean(np.ones((300, 700), dtype=np.uint16), 512).shape == (150, 350)
    assert _block_mean(np.ones((400, 500), dtype=np.uint16), 512).shape == (400, 500)


def test_the_browser_may_record_an_effect_from_the_app_origin(tmp_path):
    """The effect of a message is recorded with PATCH; a hosted or development screen on another origin sends a
    preflight first, so the method has to be allowed for the app's own origin (and only for it)."""
    client, _, _ = authenticated(tmp_path)
    preflight = {"origin": "http://test", "access-control-request-method": "PATCH", "access-control-request-headers": "content-type,x-cytellect-request"}
    allowed = client.options("/v1/workspaces/w/assistant-messages/m", headers=preflight)
    assert allowed.status_code == 200 and "PATCH" in allowed.headers["access-control-allow-methods"]
    assert allowed.headers["access-control-allow-origin"] == "http://test"
    other = client.options("/v1/workspaces/w/assistant-messages/m", headers={**preflight, "origin": "http://other.example"})
    assert "access-control-allow-origin" not in other.headers
