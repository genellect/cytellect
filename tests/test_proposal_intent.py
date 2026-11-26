"""The kind of request, the answer's items to confirm and assignment suggestions (genellect/cytellect#284 W7).

Every model answer here comes from a fake provider; no model is called. An answer never changes a setting or starts a
job: `intent` only chooses which actions the workspace offers the researcher.
"""
import json

import pytest
from cytellect_analysis.proposal_contracts import (
    FIGURE_PROMPT_VERSION,
    PROPOSAL_PROMPT_VERSION,
    ProposalContext,
    ProposalDraft,
    context_protocol,
)
from cytellect_analysis.proposal_validation import (
    ProposalRejected,
    carries_settings,
    reply_text,
    validate_draft,
)
from cytellect_api.db import jobs
from test_api_worker import HEADERS
from test_proposals import ACTIN_DRAFT, FakeResponse, configured
from test_region_api import make_field

CHANNELS = [{"token": "ch1", "stain": None, "role": None, "label": "DRAQ"},
            {"token": "ch2", "stain": None, "role": None, "label": "GFP"}]
FIELDS = [{"name": "A01-DRAQ.tif", "id": "f1", "paths": ["Rep1/未処理/A01-DRAQ.tif"]},
          {"name": "A02-DRAQ.tif", "id": "f2", "paths": ["Rep1/ActD/A02-DRAQ.tif"]}]
# Units, pairing and a nuclear channel are all unknown: a question is still answered.
CONTEXT = ProposalContext(goal="この画像のチャンネル名を教えてください。まだ測定しないでください。", channels=CHANNELS,
                          field_count=2, fields=FIELDS)
DESIGNED = ProposalContext(**{**CONTEXT.model_dump(), "design": {"layout": "pair", "runs": ["Rep1"], "groups": ["未処理", "ActD"]}})


def answer(**changes):
    value = {"recipe": "none", "channels": [], "metrics": [], "additional_analyses": [], "figures": [],
             "statistics": {"kind": "descriptive", "test": None, "omnibus": None, "association": None, "x": None, "y": None},
             "missing_information": [], "reference_ids": [], "rationale": "", "processing": None, "background": None,
             "gfp_selection": None, "figure_presentation": None, "intent": "answer",
             "answer": "ch1 は DRAQ、ch2 は GFP という名前です（ファイル名から）。核染色の確認が必要です。", "scope": None,
             "choices": [{"question": "核染色のチャンネル", "options": ["核染色は DRAQ", "核染色は GFP"]}], "assignments": []}
    value.update(changes)
    return value


def refused(raw, context=CONTEXT):
    with pytest.raises(ProposalRejected) as error:
        validate_draft(context, raw, model="m", prompt_version=PROPOSAL_PROMPT_VERSION)
    return error.value


def test_a_question_is_answered_whatever_the_workspace_holds():
    """Finding 14: an answer with no settings passes, though no nuclear channel, units or pairing is known."""
    result = validate_draft(CONTEXT, answer(), model="m", prompt_version=PROPOSAL_PROMPT_VERSION)
    assert result.draft.intent == "answer" and result.needs_confirmation == []
    assert reply_text(result.draft) == answer()["answer"]
    # Listing every channel as it is recorded is no setting; nor is an empty workspace.
    unchanged = [{"token": "ch1", "stain": None, "role": "unused", "reason": "DRAQ と記録"},
                 {"token": "ch2", "stain": None, "role": "unused", "reason": "GFP と記録"}]
    validate_draft(CONTEXT, answer(channels=unchanged), model="m", prompt_version="p")
    empty = ProposalContext(goal="核小体を比べたい", channels=[], field_count=0)
    validate_draft(empty, answer(choices=[]), model="m", prompt_version="p")


NO_STATISTICS = {"kind": "descriptive", "test": None, "omnibus": None, "association": None, "x": None, "y": None}


@pytest.mark.parametrize("change", [
    {"recipe": "nuclear-intensity"},
    {"metrics": [{"metric": "area", "channel": None, "region": "nucleus"}]},
    {"statistics": {"kind": "comparison", "test": "welch-t", "omnibus": None, "association": None}},
    {"additional_analyses": [{"kind": "comparison", "test": "welch-t", "omnibus": None, "association": None}]},
    {"figures": [{"kind": "field-distribution", "metric": "area", "channel": None, "region": "nucleus"}]},
    {"processing": {"nuclei": {"channel": "ch1"}, "nucleoli": None, "signal": None}},
    {"background": {"mode": "automatic"}},
    {"gfp_selection": {"channel": "ch2", "method": "batch_otsu"}},
    {"figure_presentation": {"composition": "quantification", "legend_terms": None}},
    {"channels": [{"token": "ch1", "stain": None, "role": "nuclear", "reason": "核染色の候補"},
                  {"token": "ch2", "stain": None, "role": "unused", "reason": "x"}]},
    {"channels": [{"token": "ch1", "stain": "DRAQ5", "role": "unused", "reason": "名前から"}]},
    {"channels": [{"token": "ch9", "stain": None, "role": "measure", "reason": "登録にないチャンネル"}]},
    # Everything at once, as a model that drafted a whole proposal for a question would write it.
    {"recipe": "nuclear-intensity", "metrics": [{"metric": "area", "channel": None, "region": "nucleus"}],
     "channels": [{"token": "ch1", "stain": "DRAQ5", "role": "nuclear", "reason": "核染色の候補"},
                  {"token": "ch2", "stain": "GFP", "role": "measure", "reason": "測定の候補"}],
     "processing": {"nuclei": {"channel": "ch1"}, "nucleoli": None, "signal": None}, "background": {"mode": "automatic"}},
])
def test_settings_in_an_answer_are_left_out_and_its_text_choices_and_suggestions_stay(change):
    """A question's answer has no way to apply a setting (decision 4). A setting it carries is left out instead of
    refusing the answer, so the choices and the suggestions the researcher asked for still arrive."""
    suggestions = [{"field": "f1", "run": "Rep1", "group": "未処理"}, {"field": "f2", "run": "Rep1", "group": "ActD"}]
    raw = answer(assignments=suggestions, **change)
    assert carries_settings(CONTEXT, ProposalDraft.model_validate(raw))
    result = validate_draft(CONTEXT, raw, model="m", prompt_version=PROPOSAL_PROMPT_VERSION)
    kept = result.draft
    # The invariant after validation: an answer holds nothing the workspace could apply.
    assert not carries_settings(CONTEXT, kept) and result.needs_confirmation == []
    assert (kept.recipe, kept.metrics, kept.figures, kept.additional_analyses) == ("none", [], [], [])
    assert kept.statistics.model_dump() == NO_STATISTICS
    assert (kept.processing, kept.background, kept.gfp_selection, kept.figure_presentation) == (None, None, None, None)
    assert all((channel.stain, channel.role) == (None, "unused") for channel in kept.channels)
    assert {channel.token for channel in kept.channels} <= {"ch1", "ch2"}
    assert kept.intent == "answer" and reply_text(kept) == answer()["answer"]
    assert [choice.model_dump() for choice in kept.choices] == answer()["choices"]
    assert [assignment.model_dump() for assignment in kept.assignments] == suggestions


def test_an_answers_channels_keep_only_the_stain_and_role_the_workspace_records():
    recorded = ProposalContext(goal="核染色はどれですか。", field_count=2, fields=FIELDS, channels=[
        {"token": "ch1", "stain": "DAPI", "role": "nuclear", "label": "DAPI"},
        {"token": "ch2", "stain": None, "role": None, "label": "GFP"}])
    listed = [{"token": "ch1", "stain": None, "role": "unused", "reason": "DAPI と記録"},
              {"token": "ch2", "stain": "GFP", "role": "measure", "reason": "名前から GFP の候補"},
              {"token": "ch2", "stain": None, "role": "nuclear", "reason": "同じチャンネルの 2 行目"},
              {"token": "ch9", "stain": None, "role": "measure", "reason": "登録にないチャンネル"}]
    kept = validate_draft(recorded, answer(channels=listed), model="m", prompt_version="p").draft
    assert [channel.model_dump() for channel in kept.channels] == [
        {"token": "ch1", "stain": "DAPI", "role": "nuclear", "reason": "DAPI と記録"},
        {"token": "ch2", "stain": None, "role": "unused", "reason": "名前から GFP の候補"}]
    assert not carries_settings(recorded, kept)


def test_an_answer_with_settings_is_still_checked_for_its_text_choices_and_suggestions():
    setting = {"recipe": "nuclear-intensity", "channels": [{"token": "ch1", "stain": None, "role": "nuclear", "reason": "核染色の候補"}]}
    # The text check reads the answer as the model wrote it, the parts that are left out included.
    remote = refused(answer(channels=[{"token": "ch9", "stain": None, "role": "measure", "reason": "https://example.org を参照"}]))
    assert remote.codes == ["proposal_text_not_allowed"] and remote.answer is None
    choice = refused(answer(**setting, choices=[{"question": "核染色", "options": ["DRAQ"]}]))
    assert choice.codes == ["proposal_choice_invalid"] and choice.answer == answer()["answer"]
    unknown = refused(answer(**setting, assignments=[{"field": "f9", "run": "Rep1", "group": "未処理"}]))
    assert unknown.codes == ["proposal_assignment_field_unknown"]
    assert refused(answer(**{**setting, "answer": None})).codes == ["proposal_answer_missing"]


def test_an_answer_needs_its_text():
    assert refused(answer(answer=None)).codes == ["proposal_answer_missing"]
    assert refused(answer(answer="  ")).codes == ["proposal_answer_missing"]
    # The reasoning alone is an answer too.
    validate_draft(CONTEXT, answer(answer=None, rationale="ch1 は DRAQ です。"), model="m", prompt_version="p")


@pytest.mark.parametrize("choices", [
    [{"question": "核染色", "options": ["DRAQ"]}],
    [{"question": "核染色", "options": ["DRAQ", "draq"]}],
    [{"question": "", "options": ["DRAQ", "GFP"]}],
    [{"question": "核染色", "options": ["DRAQ", "x" * 81]}],
    [{"question": "核染色", "options": ["DRAQ", "GFP\n核"]}],
    [{"question": f"項目 {index}", "options": ["a", "b"]} for index in range(5)],
])
def test_choices_are_short_distinct_options(choices):
    error = refused(answer(choices=choices))
    assert error.codes == ["proposal_choice_invalid"] and error.answer


def test_the_text_check_covers_the_answer_and_its_choices():
    for change in ({"answer": "https://example.org を参照"}, {"choices": [{"question": "q", "options": ["a", "run(\"x\")"]}]}):
        error = refused(answer(**change))
        assert error.codes == ["proposal_text_not_allowed"] and error.answer is None and error.rationale is None


def test_assignments_name_registered_fields_and_the_designs_groups():
    good = [{"field": "f1", "run": "Rep1", "group": "未処理"}, {"field": "f2", "run": "Rep1", "group": "ActD"}]
    for context in (CONTEXT, DESIGNED):
        assert validate_draft(context, answer(assignments=good), model="m", prompt_version="p").draft.assignments[1].group == "ActD"
    cases = [
        ([{"field": "f9", "run": "Rep1", "group": "未処理"}], "proposal_assignment_field_unknown"),
        ([good[0], {**good[1], "field": "f1"}], "proposal_assignment_duplicate"),
        ([{**good[0], "group": "未処理 · 1"}], "proposal_assignment_label_invalid"),
        ([{**good[0], "run": "r" * 25}], "proposal_assignment_label_invalid"),
        ([{**good[0], "run": " Rep1"}], "proposal_assignment_label_invalid"),
    ]
    for assignments, code in cases:
        assert refused(answer(assignments=assignments)).codes == [code]
    three = ProposalContext(**{**CONTEXT.model_dump(), "field_count": 3,
                                "fields": [*FIELDS, {"name": "c.tif", "id": "f3"}]})
    triple = [*good, {"field": "f3", "run": "Rep1", "group": "CX-5461"}]
    assert refused(answer(assignments=triple), three).codes == ["proposal_assignment_group_invalid"]
    single = ProposalContext(**{**CONTEXT.model_dump(), "design": {"layout": "single", "runs": ["Rep1"], "groups": ["未処理"]}})
    assert refused(answer(assignments=good), single).codes == ["proposal_assignment_group_invalid"]
    # A context before 1.3.0 has no field identifiers, so no assignment can be named.
    legacy = ProposalContext(protocol="1.2.0", goal="x", channels=CHANNELS, field_count=2)
    assert refused(answer(assignments=good), legacy).codes == ["proposal_assignment_field_unknown"]


def settings_draft(**changes):
    value = {"recipe": "nuclear-intensity",
             "channels": [{"token": "ch1", "stain": None, "role": "nuclear", "reason": "DRAQ の名前"},
                          {"token": "ch2", "stain": None, "role": "measure", "reason": "GFP の名前"}],
             "metrics": [{"metric": "area", "channel": None, "region": "nucleus"}],
             "statistics": {"kind": "descriptive", "test": None, "omnibus": None, "association": None},
             "figures": [], "missing_information": [], "reference_ids": [], "rationale": "DRAQ で核を検出する。",
             "intent": "settings", "answer": "核染色を DRAQ にします。", "scope": None}
    value.update(changes)
    return value


def test_settings_and_run_requests_are_checked_as_proposals():
    settings = validate_draft(CONTEXT, settings_draft(), model="m", prompt_version="p")
    assert settings.needs_confirmation == ["ch1"]
    run = validate_draft(CONTEXT, settings_draft(intent="run", scope="all"), model="m", prompt_version="p")
    assert run.draft.scope == "all"
    assert refused(settings_draft(intent="run")).codes == ["proposal_scope_required"]
    assert "proposal_run_requires_analysis" in refused(settings_draft(intent="run", scope="selected", recipe="none")).codes
    # The channel checks still apply to a settings request, and its text stays with the codes.
    mismatch = refused(settings_draft(channels=settings_draft()["channels"][:1]))
    assert mismatch.codes == ["proposal_channels_mismatch"] and mismatch.answer == "核染色を DRAQ にします。"
    assert reply_text(settings.draft) == "核染色を DRAQ にします。\nDRAQ で核を検出する。"


def test_a_malformed_intent_is_a_shape_error():
    for change in ({"intent": "execute"}, {"scope": "everything"}, {"assignments": [{"field": "f1"}]}, {"choices": [{"question": "q"}]}):
        assert refused(answer(**change)).codes == ["proposal_shape_invalid"]


def test_each_prompt_version_reads_its_own_context():
    assert context_protocol(PROPOSAL_PROMPT_VERSION) == "1.3.0"
    assert context_protocol(FIGURE_PROMPT_VERSION) == context_protocol("2026-10-09.1") == "1.2.0"
    with pytest.raises(ValueError, match="proposal_context_protocol_mismatch"):
        ProposalContext(protocol="1.2.0", goal="x", channels=CHANNELS, field_count=2, fields=FIELDS)
    with pytest.raises(ValueError, match="proposal_context_field_duplicate"):
        ProposalContext(goal="x", channels=CHANNELS, field_count=2, fields=[FIELDS[0], FIELDS[0]])
    # A 1.2.0 context and an earlier draft keep their bytes: absent additions are left out.
    legacy = ProposalContext(protocol="1.2.0", goal="x", channels=CHANNELS, field_count=1, fields=[{"name": "a.tif"}],
                             previous_proposal=ACTIN_DRAFT)
    dumped = legacy.model_dump(mode="json")
    assert "design" not in dumped and set(dumped["fields"][0]) == {"name", "condition", "experimental_unit", "pair", "acquisition_date"}
    assert not {"intent", "answer", "scope", "choices", "assignments"} & set(dumped["previous_proposal"])


ROW_A, ROW_B = "5b0c7c7e-2f40-4c1e-9a1e-0d6b8f1a2c3d", "6c1d8d8f-3a51-4d2f-8b2f-1e7c9a2b3d4e"


def designed_workspace(tmp_path, monkeypatch, drafts, prompt=PROPOSAL_PROMPT_VERSION):
    """Two synthetic fields added from a folder (one name absolute, as a client could misreport it) and a design."""
    replies = iter(drafts)
    client, wid, calls = configured(tmp_path, monkeypatch, lambda request: FakeResponse(json.dumps(
        {"draft": next(replies), "model": "gpt-6.1-sol", "prompt_version": prompt}).encode()), upload=False)
    path = f"/v1/workspaces/{wid}/selection"
    selection = client.get(path).json()
    for row, name in ((ROW_A, "Rep1/未処理/synthetic-A01-DRAQ.tif"), (ROW_B, "C:/Users/example/Rep1/ActD/synthetic-A02-DRAQ.tif")):
        selection["entries"].append({"id": row, "field_id": None, "revision_id": None, "exclusion_reason": None,
                                     "intake": {"names": [name], "state": "pending"}})
    assert client.post(path, headers=HEADERS, json=selection).status_code == 200
    ids = [make_field(client, wid, client_upload_id=row).json()["id"] for row in (ROW_A, ROW_B)]
    design = {"layout": "pair", "groups": [{"id": "g1", "label": "未処理"}, {"id": "g2", "label": "ActD"}],
              "runs": [{"id": "r1", "label": "Rep1"}], "fields": {ids[1]: {"group_id": "g2", "run_id": "r1"}}}
    spec = client.put(f"/v1/workspaces/{wid}/analysis-spec", headers=HEADERS,
                      json={"version": 0, "spec": {"channel_assignment_version": 0, "experiment": design}})
    assert spec.status_code == 200, spec.text
    if prompt != PROPOSAL_PROMPT_VERSION:
        object.__setattr__(client.app.state.settings, "proposal_prompt_version", prompt)
    return client, wid, calls, ids


def send(client, wid, goal):
    response = client.post(f"/v1/workspaces/{wid}/proposal-drafts", headers=HEADERS,
                           json={"goal": goal, "transmission_confirmed": True})
    return response


def test_the_context_names_fields_by_identifier_with_their_folder_relative_names(tmp_path, monkeypatch):
    actin = {"token": "ch1", "stain": None, "role": "unused", "reason": "Actin と記録"}
    suggestion = answer(channels=[actin], choices=[],
                        answer="フォルダーの名前から、A01 を未処理、A02 を ActD とする案です。",
                        assignments=[{"field": "f1", "run": "Rep1", "group": "未処理"}, {"field": "f2", "run": "Rep1", "group": "ActD"}])
    client, wid, calls, ids = designed_workspace(tmp_path, monkeypatch, [suggestion])
    response = send(client, wid, "未処理と ActD に分けて")
    assert response.status_code == 200, response.text
    body = response.json()
    sent = calls[0]["context"]
    assert sent["protocol"] == "1.3.0"
    assert sent["design"] == {"layout": "pair", "runs": ["Rep1"], "groups": ["未処理", "ActD"]}
    assert [(field["id"], field.get("paths"), field.get("run"), field.get("group")) for field in sent["fields"]] == [
        ("f1", ["Rep1/未処理/synthetic-A01-DRAQ.tif"], None, None),
        ("f2", ["synthetic-A02-DRAQ.tif"], "Rep1", "ActD")]
    # An absolute path never leaves the PC, nor the private data directory.
    assert "C:/" not in json.dumps(calls) and "example" not in json.dumps(calls) and str(tmp_path) not in json.dumps(calls)
    assert body["fields"] == [{"token": "f1", "field_id": ids[0]}, {"token": "f2", "field_id": ids[1]}]
    assert body["proposal"]["draft"]["assignments"][0] == {"field": "f1", "run": "Rep1", "group": "未処理"}
    assert body["message"]["reply"] == suggestion["answer"] and body["message"]["applicable"] is None


def test_an_installed_clients_prompt_keeps_context_1_2_0(tmp_path, monkeypatch):
    client, wid, calls, _ = designed_workspace(tmp_path, monkeypatch, [ACTIN_DRAFT], prompt=FIGURE_PROMPT_VERSION)
    assert send(client, wid, "細胞ごとのアクチン輝度").status_code == 200
    sent = calls[0]["context"]
    assert sent["protocol"] == "1.2.0" and "design" not in sent
    assert all(set(field) == {"name", "condition", "experimental_unit", "pair", "acquisition_date"} for field in sent["fields"])
    assert "Rep1" not in json.dumps(sent["fields"])


@pytest.mark.parametrize(("goal", "draft", "expected"), [
    ("この画像のチャンネル名を教えてください。まだ測定しないでください。",
     answer(channels=[], choices=[{"question": "核染色", "options": ["核染色は Actin", "核染色なし"]}]), ("answer", None, [])),
    ("Actin を測定に使う", {**ACTIN_DRAFT, "intent": "settings", "answer": "Actin を測定に使います。", "scope": None},
     ("settings", True, [])),
    ("全視野で測って", {**ACTIN_DRAFT, "intent": "run", "answer": "全視野で測定します。", "scope": "all"}, ("run", True, [])),
    ("全視野で測って", {**ACTIN_DRAFT, "intent": "run", "answer": "全視野で測定します。", "scope": None},
     (None, False, ["proposal_scope_required"])),
    # A question's answer that drafted settings is still an answer: the settings are left out, nothing is refused.
    ("チャンネルを教えて", answer(recipe="nuclear-intensity", metrics=[{"metric": "area", "channel": None, "region": "nucleus"}],
                         channels=[{"token": "ch1", "stain": None, "role": "nuclear", "reason": "核染色の候補"}]),
     ("answer", None, [])),
])
def test_no_intent_changes_settings_or_starts_a_job(tmp_path, monkeypatch, goal, draft, expected):
    """Decision 4: whatever the model declares, the answer only comes back; settings and jobs stay as they were."""
    client, wid, calls, _ = designed_workspace(tmp_path, monkeypatch, [draft])
    spec_before = client.get(f"/v1/workspaces/{wid}/analysis-spec").json()
    selection_before = client.get(f"/v1/workspaces/{wid}/selection").json()
    response = send(client, wid, goal)
    assert response.status_code == 200, response.text
    body = response.json()
    intent, applicable, reasons = expected
    assert (body["proposal"]["draft"].get("intent") if body["proposal"] else None) == intent
    assert (body["message"]["applicable"], body["message"]["reasons"], body["message"]["effect"]) == (applicable, reasons, "none")
    assert body["message"]["reply"]
    if intent == "answer":
        kept = body["proposal"]["draft"]
        assert (kept["recipe"], kept["metrics"], kept["processing"]) == ("none", [], None)
        assert all(channel["role"] == "unused" for channel in kept["channels"])
        assert kept.get("choices", []) == draft["choices"]
    assert client.get(f"/v1/workspaces/{wid}/analysis-spec").json() == spec_before
    assert client.get(f"/v1/workspaces/{wid}/selection").json() == selection_before
    assert client.app.state.store.one(jobs, workspace_id=wid) is None
    assert client.get(f"/v1/workspaces/{wid}/runs").json() in ([], {"runs": []})
    assert len(calls) == 1


def test_a_malformed_or_mismatched_answer_is_shown_with_its_reason(tmp_path, monkeypatch):
    mismatched = {**ACTIN_DRAFT, "channels": [], "intent": "settings", "answer": "設定を変えます。", "scope": None}
    client, wid, _, _ = designed_workspace(tmp_path, monkeypatch, [{"intent": "answer"}, mismatched])
    malformed = send(client, wid, "チャンネルは？")
    assert malformed.status_code == 502 and malformed.json()["detail"]["reasons"] == ["proposal_shape_invalid"]
    shown = send(client, wid, "Actin を測る")
    assert shown.status_code == 200 and shown.json()["proposal"] is None
    assert shown.json()["message"]["reasons"] == ["proposal_channels_mismatch", "proposal_metric_channel_invalid"]
    assert shown.json()["message"]["reply"].startswith("設定を変えます。")


def as_the_workspace_sends(draft, links):
    """A received draft as the workspace keeps it for the next message: channels by their workspace identifiers."""
    ids = {link["token"]: link["channel_id"] for link in links}

    def named(value):
        if isinstance(value, list):
            return [named(item) for item in value]
        if isinstance(value, dict):
            return {key: ids[item] if key in ("channel", "token") and item is not None else named(item) for key, item in value.items()}
        return value
    return named(draft)


@pytest.mark.parametrize("prompt", [PROPOSAL_PROMPT_VERSION, FIGURE_PROMPT_VERSION])
def test_a_proposal_with_many_suggestions_does_not_stop_the_next_message(tmp_path, monkeypatch, prompt):
    """Review of W7: nine fields, so nine suggestions. The workspace sends the whole proposal back as the previous
    one; the next message is still sent, and neither the suggestions nor the choices travel again."""
    first = {**ACTIN_DRAFT, "intent": "run", "answer": "全視野で測定し、名前から群に分ける案を示します。", "scope": "all",
             "choices": [{"question": "実験回", "options": ["すべて Rep1", "日付ごとに分ける"]}],
             "assignments": [{"field": f"f{index}", "run": "Rep1", "group": "未処理" if index % 2 else "ActD"} for index in range(1, 10)]}
    replies = iter([first, {**ACTIN_DRAFT, "intent": "settings", "answer": "Actin を測定に使います。", "scope": None}])
    client, wid, calls = configured(tmp_path, monkeypatch, lambda request: FakeResponse(json.dumps(
        {"draft": next(replies), "model": "gpt-6.1-sol", "prompt_version": PROPOSAL_PROMPT_VERSION}).encode()))
    for _ in range(8):
        assert make_field(client, wid).status_code == 201
    proposed = send(client, wid, "全視野で測って、未処理と ActD に分けて")
    assert proposed.status_code == 200, proposed.text
    assert len(proposed.json()["proposal"]["draft"]["assignments"]) == 9 and proposed.json()["message"]["restorable"] is True
    # An operator may pin an earlier prompt after the proposal was made: its context reads no kind of request at all.
    object.__setattr__(client.app.state.settings, "proposal_prompt_version", prompt)
    previous = as_the_workspace_sends(proposed.json()["proposal"]["draft"], proposed.json()["channels"])
    following = client.post(f"/v1/workspaces/{wid}/proposal-drafts", headers=HEADERS, json={
        "goal": "図は要らない", "transmission_confirmed": True, "previous_goal": "全視野で測って、未処理と ActD に分けて",
        "previous_proposal": previous})
    if prompt != PROPOSAL_PROMPT_VERSION:
        # The fake service answered with the other version; what matters here is that the request was sent.
        assert (following.status_code, following.json()["detail"]) == (502, "proposal_service_version_mismatch")
    else:
        assert following.status_code == 200, following.text
        assert following.json()["message"]["state"] == "answered"
    continued = calls[1]["context"]["previous_proposal"]
    assert "assignments" not in continued and "choices" not in continued
    assert (continued["recipe"], continued["channels"][0]["token"]) == ("supplied-regions", "ch1")
    kind = {key: continued.get(key) for key in ("intent", "scope", "answer")}
    assert kind == ({"intent": "run", "scope": "all", "answer": first["answer"]} if prompt == PROPOSAL_PROMPT_VERSION
                    else {"intent": None, "scope": None, "answer": None})
    assert calls[1]["context"]["previous_goal"] == "全視野で測って、未処理と ActD に分けて"


def test_the_listing_says_which_answers_hold_choices_or_suggestions_to_read_again(tmp_path, monkeypatch):
    """Review of W7: a reload shows the text only. `restorable` tells the workspace which messages to offer 「再送」
    for, and that resend is answered from the record without a model call."""
    with_choices = answer(channels=[], recipe="nuclear-intensity")
    settings = {**ACTIN_DRAFT, "intent": "settings", "answer": "Actin を測定に使います。", "scope": None}
    plain = answer(channels=[], choices=[], answer="チャンネルは 1 つで、Actin と記録されています。")
    suggested = {**settings, "assignments": [{"field": "f1", "run": "Rep1", "group": "未処理"}]}
    refused_run = {**settings, "intent": "run", "choices": answer()["choices"]}
    client, wid, calls, _ = designed_workspace(tmp_path, monkeypatch, [with_choices, settings, plain, suggested, refused_run, {"intent": "answer"}])
    goals = ["核染色はどれですか。", "Actin を測定に使う", "チャンネルはいくつですか。", "Actin を測定に使い、群に分けて", "全視野で測って", "形の崩れた回答"]
    sent = [send(client, wid, goal) for goal in goals]
    assert [response.status_code for response in sent] == [200, 200, 200, 200, 200, 502]
    expected = [True, False, False, True, False, False]
    assert [response.json()["message"]["restorable"] for response in sent[:5]] == expected[:5]
    listed = client.get(f"/v1/workspaces/{wid}/assistant-messages").json()["messages"]
    assert [(message["text"], message["restorable"]) for message in listed] == list(zip(goals, expected))
    assert [(message["state"], message["applicable"]) for message in listed] == [
        ("answered", None), ("answered", True), ("answered", None), ("answered", True), ("answered", False), ("failed", None)]
    # Recording what the researcher did keeps the flag.
    applied = client.patch(f"/v1/workspaces/{wid}/assistant-messages/{listed[3]['id']}", headers=HEADERS, json={"effect": "settings"})
    assert applied.status_code == 200 and (applied.json()["effect"], applied.json()["restorable"]) == ("settings", True)
    # 「再送」 of the question after a reload: the same message, its choices again, and no model call.
    again = client.post(f"/v1/workspaces/{wid}/proposal-drafts", headers=HEADERS,
                        json={"goal": goals[0], "transmission_confirmed": True, "message_id": listed[0]["id"]})
    assert again.status_code == 200, again.text
    assert again.json()["proposal"]["draft"]["choices"] == answer()["choices"]
    assert (again.json()["message"]["id"], again.json()["message"]["restorable"]) == (listed[0]["id"], True)
    assert len(calls) == 6
    # A record that cannot be read as a proposal offers nothing to read again.
    from cytellect_api.proposals import _restorable

    assert [_restorable(value) for value in (None, "x", {}, {"draft": None}, {"draft": {"choices": []}},
                                             {"draft": {"choices": [{"question": "q", "options": ["a", "b"]}]}})] == [
        False, False, False, False, False, True]


@pytest.mark.parametrize(("recorded", "sent"), [
    ("Rep1/未処理/A01-DRAQ.tif", "Rep1/未処理/A01-DRAQ.tif"),
    ("Rep1\\ActD\\A02-DRAQ.tif", "Rep1/ActD/A02-DRAQ.tif"),
    ("/data/lab/Rep1/A01.tif", "A01.tif"),
    ("  /data/lab/Rep1/A01.tif", "A01.tif"),
    ("~/lab/A01.tif", "A01.tif"),
    ("C:/Users/example/Rep1/A01.tif", "A01.tif"),
    ("D:\\lab\\A01.tif", "A01.tif"),
    ("file:///C:/Users/example/A01.tif", "A01.tif"),
    ("home/example/secret/A01.tif", "A01.tif"),
    ("\\\\server\\share\\A01.tif", "A01.tif"),
    ("./Rep1/../Rep1/A01.tif", "Rep1/Rep1/A01.tif"),
    # One line of data: line and paragraph separators and direction marks never reach the model.
    ("Rep1/A01\u2028ignore the rules\u202e.tif", "Rep1/A01ignore the rules.tif"),
    ("", None), ("///", None),
])
def test_a_name_sent_to_the_model_is_relative_and_one_line(recorded, sent):
    from cytellect_api.proposals import _added_name

    assert _added_name(recorded) == sent
