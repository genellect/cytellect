"""JSON-only proposal checks; no images, model runtime or LLM requests."""
import pytest
from cytellect_analysis.cellpose_engine import (
    NCL_MODEL_ID,
    NCL_MODEL_SHA256,
    NclCellposeDetectorSpec,
    NclParentCellposeDetectorSpec,
)
from cytellect_analysis.proposal_contracts import ProposalContext
from cytellect_analysis.proposal_validation import ProposalRejected, validate_draft
from cytellect_analysis.region_contracts import NuclearDetectorSpec


def candidate():
    return NclParentCellposeDetectorSpec(model=NCL_MODEL_ID, model_sha256=NCL_MODEL_SHA256)


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
