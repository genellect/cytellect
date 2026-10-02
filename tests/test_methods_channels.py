"""Internal channel roles cannot identify the actual microscopy stain."""
import copy
import json
import zipfile

import pytest
from cytellect_analysis.contracts import Recipe
from cytellect_analysis.exports import METHODS_TEMPLATE_VERSION, build_export_bundle, methods_text


@pytest.mark.parametrize("recipe_id", ["gfp-nuclear-2d", "ncl-native-2d", "ncl-legacy-rgb"])
def test_methods_never_infer_stain_identity_from_historical_role(recipe_id):
    recipe = Recipe(id=recipe_id, nucleolar_method="dapi-low").model_dump()
    config = {"recipe": recipe, "field_snapshot": {"field": {"image_info": {
        "channel_roles": ["dapi", "gfp"] if recipe_id == "gfp-nuclear-2d" else ["dapi", "ncl", "gfp"],
    }}}}
    original = copy.deepcopy(config)
    text = methods_text(config, {}, {"revision_id": "reviewed", "recipe": recipe})
    assert f"Methods template version: {METHODS_TEMPLATE_VERSION}." in text
    assert "historical internal role `dapi`" in text
    assert "no actual stain identity is inferred" in text
    assert "Confirm the stain from acquisition records" in text
    assert "not proof of DAPI staining" in text
    for false_claim in ("DAPI-defined", "detection DAPI", "DAPI SNR minimum", "DAPI-low percentile", "DRAQ-defined"):
        assert false_claim not in text
    assert config == original
    # The saved recipe remains identical; the wording correction cannot change
    # detection, measurement, gate or compatibility parameters.
    recipe_json = text.split("```json\n", 1)[1].split("\n```", 1)[0]
    assert json.loads(recipe_json) == recipe


def test_gfp_only_export_uses_stain_neutral_methods_and_preserves_measurements(tmp_path):
    from test_export import example

    report, config, masks, _ = example(tmp_path)
    recipe = Recipe(id="gfp-nuclear-2d").model_dump()
    config["recipe"] = report["recipe"] = recipe
    info = config["field_snapshot"]["field"]["image_info"]
    info["inputs"].pop("ncl")
    info["channel_roles"] = ["dapi", "gfp"]
    # The role mapping alone cannot distinguish DAPI from another DNA stain.
    # No acquisition marker name is invented in the fixture or the template.
    report["cells"] = [{"field_id": "field", "nucleus_id": 1, "gfp_mean_corrected": -2.5,
                        "ncl_nucleus_mean_corrected": None, "gfp_positive": True}]
    report["nucleoli"] = []
    masks["field"]["nucleoli"][:] = 0
    original_report, original_config = copy.deepcopy(report), copy.deepcopy(config)
    build_export_bundle(tmp_path / "export", report=report, config=config, provenance={}, field_masks=masks)
    with zipfile.ZipFile(tmp_path / "export" / "analysis.zip") as archive:
        text = archive.read("methods.md").decode("utf-8")
        assert "GFP within nuclei delineated using the nuclear-stain channel" in text
        assert "DAPI-defined" not in text and "DRAQ-defined" not in text
        assert "NCL and nucleolar detection are not performed" in text
        assert "negative corrections remain signed" in text
        assert json.loads(archive.read("measurements.json")) == original_report
    assert report == original_report and config == original_config


def test_native_and_legacy_channel_wording_preserves_distinct_quantification_rules():
    native = methods_text({"recipe": Recipe(nucleolar_method="dapi-low").model_dump()}, {}, {})
    assert "candidate definition dapi-low" in native
    assert "low nuclear-stain percentile (parameter `dapi_low_percentile`) 10" in native
    assert "Background is the median of each recorded user-confirmed ROI" in native
    assert "Corrected negative values remain signed" in native
    assert "ratios require both corrected means to be positive" in native
    legacy = methods_text({"recipe": Recipe(id="ncl-legacy-rgb").model_dump()}, {}, {})
    assert "only the nuclear-stain detection input (recorded role `dapi`) is rounded to source dtype" in legacy
    assert "SNR minimum (parameter `dapi_snr_min`) 2.0" in legacy
    assert "Legacy background is the median outside all nuclei on the measurement grid" in legacy
    assert "Corrected negative pixels are clipped to zero" in legacy
    assert "Epsilon=max(1, 1.4826*MAD of background NCL)" in legacy
    assert "log2[(whole-nucleus corrected mean+epsilon)/(high-region corrected mean+epsilon)]" in legacy
