"""Proposal settings must survive validation and use the real detector contracts."""
import pytest
from cytellect_analysis.compartment_engine import NucleolarDetectorV11
from cytellect_analysis.nucleolar_detector_v2 import NucleolarDetectorV20
from cytellect_analysis.proposal_contracts import ContextChannel, DraftProcessing, draft_json_schema
from cytellect_analysis.proposal_validation import validate_draft
from cytellect_analysis.region_contracts import (
    NuclearDetectorSpec,
    RegionCompartmentRecipe,
    ScaledNuclearRecipe,
)
from cytellect_api.proposals import ProposalChannelLink, ProposalDraftRequest, _continuation_context
from test_proposals import CONTEXT, codes, draft


def processing():
    return {
        "version": "1.0.0",
        "nuclei": {"channel": "dapi", "detection_max_side_px": 1024,
                   "detector": NuclearDetectorSpec(probability=0.65).model_dump()},
        "nucleoli": {"channel": "dapi", "detector": NucleolarDetectorV20(relative_threshold=0.55).model_dump()},
        "signal": None,
    }


def test_exact_proposed_settings_build_registered_execution_recipes():
    raw = draft(processing=processing())
    result = validate_draft(CONTEXT, raw, model="test", prompt_version="2026-10-07.1")
    settings = result.draft.processing
    assert settings is not None and settings.nuclei is not None and settings.nucleoli is not None
    nucleus = ScaledNuclearRecipe(region_set_id="nuclei", label="nuclei", defining_channel_id=settings.nuclei.channel,
                                  nuclear_role_source="recorded_stain", detector=settings.nuclei.detector,
                                  detection_max_side_px=settings.nuclei.detection_max_side_px)
    assert nucleus.detector.probability == 0.65 and nucleus.detection_max_side_px == 1024
    child = RegionCompartmentRecipe(region_set_id="nucleoli", label="nucleoli", compartment="nucleoli",
                                    nuclear_revision_id="adopted-parent", nuclear_channel_id="dapi",
                                    defining_channel_id=settings.nucleoli.channel, detector=settings.nucleoli.detector)
    assert child.detector.relative_threshold == 0.55


def test_historical_drafts_remain_readable_without_new_settings():
    assert validate_draft(CONTEXT, draft(), model="test", prompt_version="old").draft.processing is None
    assert "processing" not in draft_json_schema(legacy=True)["properties"]
    assert "processing" in draft_json_schema()["required"]


@pytest.mark.parametrize("mutation", [
    lambda p: p["nuclei"]["detector"].update(probability=0),
    lambda p: p["nuclei"]["detector"].update(percentile_low=99.9),
    lambda p: p["nuclei"].update(detection_max_side_px=8192),
    lambda p: p["nucleoli"]["detector"].update(minimum_area_px=100, maximum_area_px=10),
    lambda p: p["nucleoli"]["detector"].update(engine="run-python"),
])
def test_invalid_settings_never_reach_execution(mutation):
    value = processing()
    mutation(value)
    assert codes(draft(processing=value)) == ["proposal_shape_invalid"]


def test_dapi_poor_uses_nuclear_channel_and_marker_requires_actual_identity():
    value = processing()
    value["nucleoli"]["channel"] = "ncl"
    assert "proposal_processing_nucleoli_channel_invalid" in codes(draft(processing=value))
    value["nucleoli"]["detector"]["source"] = "marker"
    assert "proposal_processing_marker_not_established" in codes(draft(processing=value))
    context = CONTEXT.model_copy(update={"channels": [*CONTEXT.channels[:2],
        ContextChannel(token="c3", stain="FBL")]})
    value["nucleoli"]["channel"] = "c3"
    raw = draft(processing=value)
    raw["channels"][2]["stain"] = "FBL"
    assert validate_draft(context, raw, model="test", prompt_version="new").draft.processing is not None


def test_legacy_ncl_definition_is_explicit_not_silently_upgraded():
    value = processing()
    value["nucleoli"] = {"channel": "ncl", "detector": NucleolarDetectorV11().model_dump()}
    assert validate_draft(CONTEXT, draft(processing=value), model="test", prompt_version="new").draft.processing.nucleoli.detector.protocol_version == "1.1.0"


def test_signal_is_a_registered_pixel_detector_not_gfp_cell_classification():
    value = processing()
    value["signal"] = {"channel": "c3", "detector": {"threshold_method": "manual", "threshold": 420}}
    assert DraftProcessing.model_validate(value).signal.detector.threshold == 420
    value["signal"]["channel"] = "unacquired"
    assert "proposal_processing_signal_channel_invalid" in codes(draft(processing=value))


def test_follow_up_carries_actual_settings_and_last_turn_with_opaque_channels():
    links = [ProposalChannelLink(token="ch1", channel_id="dapi", stain="DAPI"),
             ProposalChannelLink(token="ch2", channel_id="ncl", stain="NCL"),
             ProposalChannelLink(token="ch3", channel_id="c3", stain=None)]
    body = ProposalDraftRequest(goal="もう少し細かく", current_processing=processing(),
                                previous_goal="核小体を検出", previous_proposal=draft())
    continued = _continuation_context(CONTEXT, links, body)
    assert continued.current_processing.nuclei.channel == "ch1"
    assert continued.current_processing.nuclei.detector.probability == 0.65
    assert continued.previous_proposal.metrics[1].channel == "ch2"
    assert continued.previous_goal == "核小体を検出"
    assert continued.current_processing.nucleoli.channel == "ch1"
    with pytest.raises(ValueError):
        _continuation_context(CONTEXT, links[:1], body)
    malicious = processing()
    malicious["nuclei"]["file_path"] = "private-file"
    with pytest.raises(ValueError):
        _continuation_context(CONTEXT, links, ProposalDraftRequest(current_processing=malicious))
