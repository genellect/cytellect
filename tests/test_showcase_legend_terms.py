"""Public demo facts and replay scoping, not biological or model-quality evidence."""
import copy
import json
from pathlib import Path

import pytest
from cytellect_analysis.proposal_contracts import ContextField
from cytellect_showcase._proposals import AUTHORED, Recordings
from test_proposals import CONTEXT, draft

ROOT = Path(__file__).resolve().parents[1]
SCENES = ["zenodo-6643470-oxaliplatin", "zenodo-6643470-cisplatin", "zenodo-6643470-nucleolar", "cpg0016-jump-source13-plk1"]


def test_presets_are_unambiguous_also_in_the_existing_public_wheel():
    # The already-published wheel falls back by goal only. It must never choose another treatment's terms.
    goals = [preset["instruction"] for scene in SCENES
             for preset in json.loads((ROOT / f"services/showcase/datasets/{scene}.json").read_text(encoding="utf-8"))["scenario"]["proposals"]["presets"]]
    assert len(goals) == len(set(goals)) == 11


@pytest.mark.parametrize("scene", SCENES)
def test_every_public_preset_has_only_its_recorded_legend_facts(scene):
    data = json.loads((ROOT / f"services/showcase/datasets/{scene}.json").read_text(encoding="utf-8"))
    scope = data["dataset"]["scope"]
    for preset in data["scenario"]["proposals"]["presets"]:
        presentation = preset["draft"]["figure_presentation"]
        assert presentation["composition"] == "quantification"
        terms = presentation["legend_terms"]
        assert "Hoechst" in terms["stains"] and "Hoechst" in scope
        if "zenodo" in scene:
            assert terms["cell_line"].replace("U2OS with", "U2OS cells with") + "," in scope
            assert all(name in terms["cell_line"] for name in ("FBL-sfGFP", "NPM1-mTagRFP"))
            assert all(name in terms["stains"] and name in scope for name in ("5-EU", "Alexa Fluor 647 azide"))
            assert "FBL" not in terms["stains"] and "NPM1" not in terms["stains"]
            assert "FBL" not in data["dataset"]["modifications"]  # Not a displayed channel.
            assert "nominal concentration inferred from the source filename label" in terms["treatment"]
            label = terms["treatment"].split("label ")[1].split(")")[0]
            assert any(label in item["filename"] for item in data["sources"].values())
        else:
            assert terms["cell_line"] in scope and terms["treatment"] in scope
            assert terms["stains"] == "Hoechst 33342 (DNA)"


def test_changed_settings_cannot_replay_another_scenes_treatment_facts():
    context = CONTEXT.model_copy(update={"fields":[ContextField(condition="Oxaliplatin")]})
    entries = {}
    for index, condition in enumerate(["Cisplatin", "Oxaliplatin"]):
        value = copy.deepcopy(draft())
        value["rationale"] = condition
        entries[str(index) * 64] = {"model":"showcase-preset","prompt_version":"1","source":AUTHORED,
            "goal":context.goal,"conditions":[condition],"draft":value}
    recording = Recordings(entries)
    assert recording._authored(context)["draft"]["rationale"] == "Oxaliplatin"
    assert recording._authored(context.model_copy(update={"fields":[ContextField(condition="ActD")]})) is None
