"""A model-written discussion is shown as written once it has the three headings (plan §8, 2026-11-17).

Only the structure is checked: the text's numbers, wording and references are the model's, and no note is
added to them. The fixtures are the public demo's JUMP comparison as the result summary states it.
"""
import pytest
from cytellect_analysis.discussion_contracts import (
    DISCUSSION_PROTOCOL,
    DiscussionContext,
    DiscussionDraft,
    draft_json_schema,
)
from cytellect_analysis.discussion_validation import (
    DiscussionRejected,
    context_sha256,
    validate_discussion,
)

# The public demo's JUMP comparison as the result summary states it (descriptive: independence not confirmed).
DESCRIPTIVE = DiscussionContext(
    experiment={"purpose": "PLK1 のノックアウトで細胞が減るかを確かめる", "cells": "U2OS", "stains": ["Hoechst"]},
    result={"metric": "視野あたりの核数", "region": "核", "unit": "個／視野", "scale": "ratio", "control": "Non-targeting", "treatment": "PLK1 KO",
            "design": "paired", "test": "none", "n_control": 3, "n_treatment": 3, "n_runs": 3,
            "groups": [{"condition": "Non-targeting", "mean": 418}, {"condition": "PLK1 KO", "mean": 74.4}],
            "runs": [{"run": "Run1", "control": 456, "treatment": 80, "difference": -376, "ratio": 0.175},
                     {"run": "Run2", "control": 347, "treatment": 73, "difference": -274, "ratio": 0.21},
                     {"run": "Run3", "control": 450, "treatment": 70.3, "difference": -380, "ratio": 0.156}],
            "heading": "PLK1 KO で、視野あたりの核数が 79〜84% 減少"})
TESTED = DiscussionContext(result={**DESCRIPTIVE.result.model_dump(), "test": "paired-t", "p_value": 0.012,
                                   "difference": {"estimate": -343, "ci_low": -480, "ci_high": -206},
                                   "heading": "PLK1 KO で、視野あたりの核数が約 82% 減少"})
UNCLEAR = DiscussionContext(result={**TESTED.result.model_dump(), "p_value": 0.3, "difference": {"estimate": -40, "ci_low": -120, "ci_high": 40},
                                    "heading": "PLK1 KO による視野あたりの核数の違いは不明確"})


def draft(*implications, alternatives=(), next_steps=()):
    return {"implications": list(implications), "alternatives": list(alternatives), "next_steps": list(next_steps)}


# Correct, careful sentences that the checks used until 2026-11-17 rejected (plan §8.3).
CAREFUL = [
    "検定は行っていないため、有意差の有無はこの結果からは言えない。",
    "区間が 0 を含むため、変化がないとは言えない。",
    "既報（Lens et al.）と同様に、PLK1 の欠失は分裂期の停止を起こす可能性がある。",
    "24 時間後と 48 時間後の時間経過で確かめる必要がある。",
    "確認された事実ではなく、仮説である。",
    "核数が約 5 分の 1 になったことは、増殖の停止と整合する。",
]


def test_a_draft_is_stored_with_its_source():
    shown = validate_discussion(draft("3 回の実験すべてで、PLK1 KO の視野あたりの核数は 79〜84% 少なく、PLK1 の欠失で細胞の増殖や生存が損なわれた可能性がある。",
                                      alternatives=["視野の選び方や播種の密度が、核数に影響した可能性がある。"],
                                      next_steps=["2 つ目の独立したガイド RNA で、同じ向きの変化が出るかを確かめる。"]),
                                DESCRIPTIVE, model="test-model")
    assert shown.protocol == DISCUSSION_PROTOCOL and shown.model == "test-model"
    assert shown.context_sha256 == context_sha256(DESCRIPTIVE)


@pytest.mark.parametrize("context", [DESCRIPTIVE, TESTED, UNCLEAR], ids=["descriptive", "tested", "unclear"])
def test_careful_scientific_sentences_are_shown_as_written(context):
    shown = validate_discussion(draft(*CAREFUL[:3], alternatives=CAREFUL[3:5], next_steps=CAREFUL[5:]), context, model="m")
    assert [*shown.draft.implications, *shown.draft.alternatives, *shown.draft.next_steps] == CAREFUL


def test_numbers_claims_references_and_length_are_the_models_choice():
    """No rule on the surface of the text: numbers outside the result, a claim, a reference or a long point are shown."""
    texts = ["核数は約 60% 減少し、G2/M 期での停止が 35% の細胞で起きた可能性がある。", "PLK1 KO で核数が有意に減少することが示された。",
             "PLK1 KO は視野あたりの核数に影響しない。", "https://doi.org/10.0000/example を参照。", "あ" * 2000]
    shown = validate_discussion(draft(*texts, alternatives=[f"代替説明 {index}" for index in range(10)],
                                      next_steps=[f"追加検証 {index}" for index in range(10)]), DESCRIPTIVE, model="m")
    assert list(shown.draft.implications) == texts and len(shown.draft.alternatives) == len(shown.draft.next_steps) == 10


def test_only_an_answer_without_the_three_headings_is_rejected():
    for raw in ({"implications": [], "alternatives": [], "next_steps": []},
                {**draft("a"), "values": [1]}, {"implications": [1], "alternatives": [], "next_steps": []},
                draft(""), "a discussion"):
        with pytest.raises(DiscussionRejected) as rejected:
            validate_discussion(raw, DESCRIPTIVE, model="m")
        assert rejected.value.codes == ["discussion_schema_invalid"]
    schema = draft_json_schema()
    assert schema["additionalProperties"] is False and set(schema["properties"]) == set(schema["required"]) == {
        "implications", "alternatives", "next_steps"}
    assert "maxItems" not in str(schema) and "maxLength" not in str(schema)


def test_the_context_carries_no_image_file_or_path():
    with pytest.raises(ValueError):
        DiscussionContext(result=DESCRIPTIVE.result, image="field.tif")
    with pytest.raises(ValueError):
        DiscussionContext(experiment={"purpose": "x", "path": "/data/field.tif"}, result=DESCRIPTIVE.result)
    assert set(DESCRIPTIVE.model_dump()) == {"protocol", "language", "experiment", "result"}


def test_the_purpose_may_be_as_long_as_a_proposal_goal():
    """The purpose starts from the goal written to the AI, which may run to 2000 characters."""
    assert DiscussionContext(experiment={"purpose": "目" * 2000}, result=DESCRIPTIVE.result).experiment.purpose


def test_the_researchers_names_and_definitions_are_part_of_the_context():
    result = DESCRIPTIVE.result.model_dump()
    result.update(metric="positive_fraction", metric_label="判定可能な核の陽性率", unit="fraction of evaluable nuclei",
                  metric_definition="positive / all evaluable positive and negative nuclei before subset selection",
                  channel_label="GFP 488", region_label="細胞の内側")
    context = DiscussionContext(experiment=DESCRIPTIVE.experiment, result=result)
    assert context.protocol == DISCUSSION_PROTOCOL == "result-discussion/1.1.0"
    assert context.result.region_label == "細胞の内側"


def test_protocol_1_0_contexts_and_drafts_remain_readable():
    legacy = DiscussionContext.model_validate({**DESCRIPTIVE.model_dump(mode="json"), "protocol": "result-discussion/1.0.0"})
    assert legacy.protocol == "result-discussion/1.0.0" and legacy.result.metric_label is None
    stored = DiscussionDraft.model_validate({"protocol": "result-discussion/1.0.0", **draft("a")})
    assert stored.protocol == "result-discussion/1.0.0"
