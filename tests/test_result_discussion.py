"""A model-drafted discussion is shown only when it adds no number, significance, "no change" or reference."""
import pytest
from cytellect_analysis.discussion_contracts import (
    DISCUSSION_PROTOCOL,
    DiscussionContext,
    DiscussionDraft,
    draft_json_schema,
)
from cytellect_analysis.discussion_validation import DiscussionRejected, allowed_numbers, context_sha256, validate_discussion

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


def test_a_draft_built_on_the_saved_numbers_is_shown():
    shown = validate_discussion(draft("3 回の実験すべてで、PLK1 KO の視野あたりの核数は 79〜84% 少なく、PLK1 の欠失で細胞の増殖や生存が損なわれた可能性がある。",
                                      alternatives=["視野の選び方や播種の密度が、核数に影響した可能性がある。"],
                                      next_steps=["2 つ目の独立したガイド RNA で、同じ向きの変化が出るかを確かめる。"]),
                                DESCRIPTIVE, model="test-model")
    assert shown.protocol == DISCUSSION_PROTOCOL and shown.model == "test-model"
    assert shown.context_sha256 == context_sha256(DESCRIPTIVE)
    assert len(shown.draft.implications) == 1


def test_names_with_digits_and_counting_words_are_not_values():
    validate_discussion(draft("U2OS の PLK1 KO では、Hoechst で数えた核が 418 から 74.4 に減った。"), DESCRIPTIVE, model="m")


def test_a_number_the_result_does_not_hold_is_rejected():
    with pytest.raises(DiscussionRejected) as rejected:
        validate_discussion(draft("核数は約 60% 減少し、細胞周期の G2/M 期での停止が 35% の細胞で起きたと考えられる。"), DESCRIPTIVE, model="m")
    assert "discussion_number_not_in_result" in rejected.value.codes


def test_a_descriptive_result_is_not_called_significant_or_proven():
    with pytest.raises(DiscussionRejected) as rejected:
        validate_discussion(draft("PLK1 KO で核数が有意に減少することが示された。"), DESCRIPTIVE, model="m")
    assert rejected.value.codes == ["discussion_claims_significance"]
    # A tested result with an interval away from 0 may be called significant.
    validate_discussion(draft("PLK1 KO で、視野あたりの核数が有意に減少した（p = 0.012）。"), TESTED, model="m")


def test_an_unclear_result_is_never_called_no_change():
    with pytest.raises(DiscussionRejected) as rejected:
        validate_discussion(draft("PLK1 KO は視野あたりの核数に影響しない。"), UNCLEAR, model="m")
    assert "discussion_claims_no_change" in rejected.value.codes
    validate_discussion(draft("この実験では違いは不明確で、違いがないことを示すものではない。"), UNCLEAR, model="m")


def test_references_and_links_are_rejected():
    for text in ["Smith et al. も同じ現象を報告している。", "詳しくは https://example.org を参照。", "doi: 10.1000/xyz を参照。"]:
        with pytest.raises(DiscussionRejected) as rejected:
            validate_discussion(draft(text), DESCRIPTIVE, model="m")
        assert "discussion_reference_or_link" in rejected.value.codes


def test_the_shape_is_fixed_and_bounded():
    with pytest.raises(DiscussionRejected) as rejected:
        validate_discussion({"implications": [], "alternatives": [], "next_steps": []}, DESCRIPTIVE, model="m")
    assert rejected.value.codes == ["discussion_schema_invalid"]
    with pytest.raises(DiscussionRejected):
        validate_discussion(draft("a", "b", "c", "d"), DESCRIPTIVE, model="m")
    with pytest.raises(DiscussionRejected):
        validate_discussion({**draft("a"), "values": [1]}, DESCRIPTIVE, model="m")
    schema = draft_json_schema()
    assert schema["additionalProperties"] is False and set(schema["properties"]) == {"protocol", "implications", "alternatives", "next_steps"}


def test_the_context_carries_no_image_file_or_path():
    with pytest.raises(ValueError):
        DiscussionContext(result=DESCRIPTIVE.result, image="field.tif")
    with pytest.raises(ValueError):
        DiscussionContext(experiment={"purpose": "x", "path": "/data/field.tif"}, result=DESCRIPTIVE.result)
    keys = set(DESCRIPTIVE.model_dump())
    assert keys == {"protocol", "language", "experiment", "result"}


def test_the_allowed_numbers_include_the_summary_forms():
    allowed = allowed_numbers(DESCRIPTIVE)
    for value in (418, 74.4, -376, 3, 79, 84, 82.5):
        assert any(abs(abs(value) - abs(candidate)) < 0.6 for candidate in allowed), value
    assert isinstance(DiscussionDraft.model_validate(draft("x")), DiscussionDraft)
