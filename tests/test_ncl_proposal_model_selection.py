"""JSON-only proposal checks; no images, model runtime or LLM requests."""
import pytest
from cytellect_analysis.cellpose_engine import (
    NCL_750_MODEL_ID,
    NCL_750_MODEL_SHA256,
    NCL_MODEL_ID,
    NCL_MODEL_SHA256,
    NclCellposeDetectorSpec,
    NclParentCellposeDetectorSpec,
)
from cytellect_analysis.proposal_contracts import ProposalContext
from cytellect_analysis.proposal_validation import ProposalRejected, validate_draft
from cytellect_analysis.region_contracts import NuclearDetectorSpec


def candidate(model_id=NCL_MODEL_ID):
    return NclParentCellposeDetectorSpec(model=model_id, model_sha256=(
        NCL_MODEL_SHA256 if model_id == NCL_MODEL_ID else NCL_750_MODEL_SHA256))


def processing(detector, channel="ncl"):
    return {"version": "1.0.0", "nuclei": {
        "channel": "dna", "detection_max_side_px": None, "detector": NuclearDetectorSpec().model_dump()},
        "nucleoli": {"channel": channel, "detector": detector.model_dump()}, "signal": None}


def validate(detector, current=None):
    channels = [{"token": "dna", "stain": "DAPI", "role": "nuclear"},
                {"token": "ncl", "stain": "NCL", "role": "measure"},
                {"token": "other", "stain": "NCL", "role": "measure"}]
    context = ProposalContext(field_count=1, channels=channels, current_processing=current)
    draft = {"recipe": "nuclear-ncl", "channels": [{**channel, "reason": "recorded stain"} for channel in channels],
             "processing": processing(detector), "metrics": [{"metric": "area", "channel": None, "region": "nucleoli"}],
             "statistics": {"kind": "descriptive", "test": None, "omnibus": None, "association": None},
             "figures": [], "missing_information": [], "reference_ids": [], "rationale": ""}
    return validate_draft(context, draft, model="contract-only", prompt_version="contract-only")


@pytest.mark.parametrize("current", [
    None,
    processing(NclParentCellposeDetectorSpec()),
    processing(candidate(), "other"),
    processing(NclParentCellposeDetectorSpec(protocol_version="4.2.1")),
    processing(NclCellposeDetectorSpec()),
])
def test_ai_cannot_introduce_or_move_experimental_weights(current):
    with pytest.raises(ProposalRejected) as error:
        validate(candidate(), current)
    assert "proposal_experimental_model_not_selected" in error.value.codes


def test_ai_can_retain_selected_identity_while_proposing_other_settings():
    changed = candidate().model_copy(update={"diameter_px": 90.0})
    result = validate(changed, processing(candidate()))
    assert result.draft.processing.nucleoli.detector.model == NCL_MODEL_ID
    assert result.draft.processing.nucleoli.detector.diameter_px == 90.0


def test_ai_cannot_silently_revert_selected_weights_within_same_method():
    with pytest.raises(ProposalRejected) as error:
        validate(NclParentCellposeDetectorSpec(), processing(candidate()))
    assert "proposal_model_selection_changed" in error.value.codes


def test_baseline_and_explicitly_different_algorithm_proposals_remain_supported():
    assert validate(NclParentCellposeDetectorSpec()).draft.processing.nucleoli.detector.model == "cpsam_v2"
    result = validate(NclCellposeDetectorSpec(), processing(candidate()))
    assert result.draft.processing.nucleoli.detector.engine == "cellpose-sam-ncl"


@pytest.mark.parametrize("model_id,other_id", [(NCL_750_MODEL_ID, NCL_MODEL_ID), (NCL_MODEL_ID, NCL_750_MODEL_ID)])
def test_ai_preserves_each_candidate_without_introducing_or_switching_weights(model_id, other_id):
    selected = candidate(model_id)
    for current in (None, processing(NclParentCellposeDetectorSpec()), processing(candidate(other_id)),
                    processing(selected, "other")):
        with pytest.raises(ProposalRejected) as error:
            validate(selected, current)
        assert "proposal_experimental_model_not_selected" in error.value.codes
    assert validate(selected, processing(selected)).draft.processing.nucleoli.detector.model == model_id
    with pytest.raises(ProposalRejected) as error:
        validate(NclParentCellposeDetectorSpec(), processing(selected))
    assert "proposal_model_selection_changed" in error.value.codes


def envelope_candidate():
    return NclParentCellposeDetectorSpec(
        model=NCL_750_MODEL_ID, model_sha256=NCL_750_MODEL_SHA256,
        postprocessing_mode="single-anchor-envelope-v1")


def test_envelope_mode_is_explicit_saved_and_ai_cannot_switch_it():
    legacy = candidate(NCL_750_MODEL_ID)
    selected = envelope_candidate()
    assert "postprocessing_mode" not in legacy.model_dump()
    assert selected.model_dump()["postprocessing_mode"] == "single-anchor-envelope-v1"
    assert NclParentCellposeDetectorSpec.model_validate(selected.model_dump()) == selected
    for current in (None, processing(legacy), processing(selected, "other")):
        with pytest.raises(ProposalRejected) as error:
            validate(selected, current)
        assert "proposal_experimental_postprocessing_not_selected" in error.value.codes
    with pytest.raises(ProposalRejected) as error:
        validate(legacy, processing(selected))
    assert "proposal_postprocessing_selection_changed" in error.value.codes
    assert validate(selected, processing(selected)).draft.processing.nucleoli.detector == selected


def test_envelope_requires_fixed_750_and_explicit_ncl_stain():
    from cytellect_analysis.cellpose_engine import validate_envelope_stain
    from pydantic import ValidationError

    for spec in (NclParentCellposeDetectorSpec(), candidate()):
        with pytest.raises(ValidationError, match="cellpose_envelope_model_protocol_mismatch"):
            NclParentCellposeDetectorSpec.model_validate(
                {**spec.model_dump(), "postprocessing_mode": "single-anchor-envelope-v1"})
    for stain in (None, "", "NPM1", "DAPI"):
        with pytest.raises(ValueError, match="cellpose_envelope_ncl_stain_required"):
            validate_envelope_stain(envelope_candidate(), stain)
        validate_envelope_stain(candidate(NCL_750_MODEL_ID), stain)
    for stain in ("NCL", " Nucleolin "):
        validate_envelope_stain(envelope_candidate(), stain)
