"""Input checks of the group-comparison metrics and estimates, and real-shape agreement.

Reference values live in test_group_comparison_reference.py (written from the
specification before these implementations). The shape check below uses the
public, CC0 BBBC039 manual nuclear annotations, not generated images.
"""
import importlib.util
from pathlib import Path

import numpy as np
import pytest
from cytellect_analysis.comparison_estimates import comparison_estimates
from cytellect_analysis.field_summary import field_summary_values
from cytellect_analysis.group_comparison_contracts import FieldSummarySelection
from cytellect_analysis.nucleolar_shape import object_eccentricity
from skimage.measure import regionprops

source = Path(__file__).resolve().parents[1] / "scripts/public_bbbc039.py"
spec = importlib.util.spec_from_file_location("public_bbbc039", source)
bbbc039 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bbbc039)


def test_eccentricity_matches_scikit_image_on_public_manual_annotations():
    manifest = bbbc039.verify()
    checked = 0
    for item in manifest["images"]:
        truth = bbbc039.decode_ground_truth(bbbc039.FIXTURE / item["mask"]["path"])
        for region in regionprops(truth):
            rows, columns = region.coords[:, 0], region.coords[:, 1]
            value = object_eccentricity(rows, columns)
            if region.area == 1:
                assert value is None
                continue
            assert value == pytest.approx(region.eccentricity, abs=1e-9)
            checked += 1
    assert checked > 100


def test_field_summary_rejects_inconsistent_inputs():
    selection = FieldSummarySelection.model_validate({"source": "field-summary", "region_set_id": "n",
                                                      "metric": "nucleus_count"})
    field = {"field_id": "f", "status": "no_regions", "shape": (10, 10), "pixel_size_um": None,
             "regions": [{"region_id": 1, "touches_border": False, "positive": None}], "excluded_region_ids": []}
    with pytest.raises(ValueError, match="field_summary_status_mismatch"):
        field_summary_values([field], selection)
    duplicate = {**field, "status": "measured", "regions": field["regions"] * 2}
    with pytest.raises(ValueError, match="field_summary_region_identity"):
        field_summary_values([duplicate], selection)
    excluded = {**field, "status": "measured", "excluded_region_ids": [1]}
    with pytest.raises(ValueError, match="field_summary_region_identity"):
        field_summary_values([excluded], selection)
    with pytest.raises(ValueError, match="field_summary_invalid_calibration"):
        field_summary_values([{**field, "status": "measured", "pixel_size_um": 0.0}], selection)


@pytest.mark.parametrize("kwargs, code", [
    ({"design": "paired", "test": "welch-t", "pairs": ["a", "b"]}, "comparison_estimates_test_design_mismatch"),
    ({"design": "paired", "test": "paired-t", "pairs": ["a"]}, "comparison_estimates_pairs_mismatch"),
    ({"design": "independent", "test": "welch-t", "metric": "cell_count"}, "comparison_estimates_unknown_metric"),
])
def test_estimates_reject_inconsistent_requests(kwargs, code):
    options = {"control_label": "C", "treatment_label": "T", "metric": "area_px", **kwargs}
    with pytest.raises(ValueError, match=code):
        comparison_estimates([1.0, 2.0], [3.0, 4.0], **options)


def test_estimates_reject_nonfinite_values():
    with pytest.raises(ValueError, match="comparison_estimates_nonfinite"):
        comparison_estimates([1.0, np.nan], [3.0, 4.0], control_label="C", treatment_label="T",
                             design="independent", test="welch-t", metric="area_px")
