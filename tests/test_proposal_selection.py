import pytest
from cytellect_analysis.proposal_contracts import ContextChannel, ProposalContext, draft_json_schema
from cytellect_analysis.proposal_validation import ProposalRejected, validate_draft
from test_proposals import CONTEXT, draft


def context():
    return CONTEXT.model_copy(update={"channels": [*CONTEXT.channels[:2], ContextChannel(token="c3", stain="GFP", role="measure")],
                                      "background_available": False})


def proposal(**changes):
    result = draft(**changes)
    result["channels"][2]["stain"] = "GFP"
    result["recipe"] = "nuclear-intensity"
    result["metrics"] = [{"metric":"area","channel":None,"region":"nucleus"}]
    result["statistics"] = {"kind":"descriptive","test":None,"omnibus":None,"association":None}
    result["figures"] = [{"kind":"field-distribution","metric":"area","channel":None,"region":"nucleus"}]
    return result


def gate(**changes):
    return {"channel":"c3", "unit":"nucleus", "method":"manual", "threshold":100,
            "values":"raw", "keep":"positive", "percentile":99, **changes}


def validate(raw, ctx=None):
    return validate_draft(ctx or context(), raw, model="test", prompt_version="2026-10-08.1")


def test_automatic_background_and_object_threshold_are_structured():
    result = validate(proposal(background={"mode":"automatic"}, gfp_selection=gate(values="corrected")))
    assert result.draft.background.mode == "automatic"
    assert result.draft.gfp_selection.threshold == 100
    assert result.draft.gfp_selection.unit == "nucleus"


@pytest.mark.parametrize("selection,code", [
    (gate(channel="dapi"), "proposal_gfp_channel_not_established"),
    (gate(method="negative_control", threshold=None), "proposal_gfp_controls_not_registered"),
    (gate(method="batch_otsu", threshold=None), "proposal_acquisition_dates_required"),
    (gate(values="corrected"), "proposal_background_not_available"),
    (gate(unit="cell_roi"), "proposal_supplied_regions_absent"),
])
def test_unknown_prerequisites_are_not_invented(selection, code):
    with pytest.raises(ProposalRejected) as error:
        validate(proposal(gfp_selection=selection))
    assert code in error.value.codes


def test_roi_confirmation_cannot_be_created_by_the_model():
    with pytest.raises(ProposalRejected) as error:
        validate(proposal(background={"mode":"confirmed_roi"}))
    assert "proposal_background_not_available" in error.value.codes


def test_recorded_controls_are_used_without_disclosing_their_identifiers():
    ctx = context().model_copy(update={"negative_control_fields_known":True})
    result = validate(proposal(gfp_selection=gate(method="negative_control",threshold=None)), ctx)
    assert result.draft.gfp_selection.method == "negative_control"
    assert "control_field_ids" not in result.draft.gfp_selection.model_dump()


def test_saved_drafts_and_processing_schema_keep_original_shape():
    assert "gfp_selection" in draft_json_schema()["required"]
    assert "gfp_selection" not in draft_json_schema(processing_only=True)["properties"]
    assert "processing" not in draft_json_schema(legacy=True)["properties"]
    assert validate(proposal()).draft.gfp_selection is None
    empty = ProposalContext(channels=[],field_count=0,goal="Compare images")
    with pytest.raises(ProposalRejected):
        validate_draft(empty,{"recipe":"none","channels":[],"metrics":[],"statistics":{"kind":"descriptive","test":None,"omnibus":None,"association":None},"figures":[],"missing_information":["画像"],"reference_ids":[],"rationale":"", "background":{"mode":"automatic"}},model="test",prompt_version="new")
