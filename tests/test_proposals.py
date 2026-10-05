"""Model-drafted proposals are validated locally and never become executable by themselves."""
import io
import json
import urllib.error

import pytest
from cytellect_analysis.proposal_contracts import ProposalContext, ProposalDraft, draft_json_schema
from cytellect_analysis.proposal_validation import ProposalRejected, validate_draft
from cytellect_api import proposals
from test_api_worker import HEADERS, authenticated

CONTEXT = ProposalContext(goal="核小体と核質のNCL輝度を比較したい", field_count=12, condition_count=2,
                          units_known=True, channels=[{"token": "dapi", "stain": "DAPI", "role": "nuclear"},
                                                      {"token": "ncl", "stain": "NCL"}, {"token": "c3"}])


def draft(**changes):
    value = {
        "recipe": "nuclear-ncl",
        "channels": [{"token": "dapi", "stain": "DAPI", "role": "nuclear", "reason": "核染色"},
                     {"token": "ncl", "stain": "NCL", "role": "measure", "reason": "測定対象"},
                     {"token": "c3", "stain": None, "role": "measure", "reason": "名前から染色を確定できない"}],
        "metrics": [{"metric": "area", "channel": None},
                    {"metric": "ncl_log2_nucleoplasm_over_nucleoli", "channel": "ncl"},
                    {"metric": "mean_raw", "channel": "c3"}],
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
    assert result.needs_confirmation == ["c3"]
    assert len(result.context_sha256) == 64


@pytest.mark.parametrize(("change", "code"), [
    ({"channels": [*draft()["channels"][:2], {"token": "c3", "stain": "GFP", "role": "measure", "reason": "緑"}]},
     "proposal_stain_not_established"),
    ({"channels": draft()["channels"][:2]}, "proposal_channels_mismatch"),
    ({"metrics": [{"metric": "mean_raw", "channel": "gfp"}]}, "proposal_metric_channel_invalid"),
    ({"metrics": [{"metric": "mean_corrected", "channel": "ncl"}], "figures": []}, "proposal_background_not_available"),
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
    three = CONTEXT.model_copy(update={"condition_count": 3})
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


def configured(tmp_path, monkeypatch, reply):
    client, app, settings = authenticated(tmp_path)
    object.__setattr__(settings, "proposal_url", "https://proposal.example")
    object.__setattr__(settings, "proposal_token", "device-secret")
    calls = []

    def urlopen(request, timeout):
        calls.append(json.loads(request.data))
        assert request.headers["Authorization"] == "Bearer device-secret"
        return reply(request)
    monkeypatch.setattr(proposals.urllib.request, "urlopen", urlopen)
    wid = client.post("/v1/workspaces", json={"title": "w"}, headers=HEADERS).json()["id"]
    return client, wid, calls


def test_route_validates_reuses_identical_input_and_sends_metadata_only(tmp_path, monkeypatch):
    body = json.dumps({"draft": draft(), "model": "test-model", "prompt_version": "2026-10-05.1"}).encode()
    client, wid, calls = configured(tmp_path, monkeypatch, lambda request: FakeResponse(body))
    payload = CONTEXT.model_dump(mode="json")
    first = client.post(f"/v1/workspaces/{wid}/proposals", json=payload, headers=HEADERS)
    second = client.post(f"/v1/workspaces/{wid}/proposals", json=payload, headers=HEADERS)
    assert first.status_code == 200, first.text
    assert first.json() == second.json() and len(calls) == 1
    assert set(calls[0]) == {"context"} and set(calls[0]["context"]) == set(ProposalContext.model_fields)
    assert client.post(f"/v1/workspaces/{wid}/proposals", json={**payload, "path": "C:/x"}, headers=HEADERS).status_code == 422


def test_route_rejects_invalid_drafts_and_maps_service_failures(tmp_path, monkeypatch):
    bad = json.dumps({"draft": draft(rationale="https://x"), "model": "m", "prompt_version": "p"}).encode()
    client, wid, _ = configured(tmp_path, monkeypatch, lambda request: FakeResponse(bad))
    response = client.post(f"/v1/workspaces/{wid}/proposals", json=CONTEXT.model_dump(mode="json"), headers=HEADERS)
    assert response.status_code == 502
    assert response.json()["detail"] == {"code": "proposal_rejected", "reasons": ["proposal_text_not_allowed"]}

    def quota(request):
        raise urllib.error.HTTPError(request.full_url, 429, "quota", {}, None)
    client, wid, _ = configured(tmp_path / "q", monkeypatch, quota)
    response = client.post(f"/v1/workspaces/{wid}/proposals", json=CONTEXT.model_dump(mode="json"), headers=HEADERS)
    assert (response.status_code, response.json()["detail"]) == (429, "proposal_quota_exhausted")


def test_route_is_disabled_without_configuration_and_checks_ownership(tmp_path):
    client, _, _ = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", json={"title": "w"}, headers=HEADERS).json()["id"]
    response = client.post(f"/v1/workspaces/{wid}/proposals", json=CONTEXT.model_dump(mode="json"), headers=HEADERS)
    assert (response.status_code, response.json()["detail"]) == (503, "proposal_service_disabled")
    assert client.post("/v1/workspaces/missing/proposals", json=CONTEXT.model_dump(mode="json"),
                       headers=HEADERS).status_code == 404
