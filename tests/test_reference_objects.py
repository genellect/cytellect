"""Matching published object centres to adopted labels.

Synthetic minimal label arrays (not cell images): the cases are exact by construction.
"""
import numpy as np
import pytest
from cytellect_analysis.reference_objects import match_reference_centres


def labels():
    image = np.zeros((10, 12), np.uint32)
    image[2:5, 2:5] = 1      # one reference centre inside
    image[2:6, 7:11] = 2     # two reference centres inside (split by the reference method)
    image[7:9, 4:6] = 3      # no reference centre (labels only)
    image[0:2, 0:2] = 4      # touches the border: never "labels only"
    return image


def test_each_reference_centre_and_label_is_classified():
    result = match_reference_centres(labels(), [(3, 3), (8, 3), (9.4, 4.6), (6, 8), (0.4, 0.6)])
    assert result["reference"] == ["both", "split", "split", "reference_only", "both"]
    assert result["labels_only"] == [3]
    assert result["border_labels"] == [4]
    assert result["summary"] == {"reference_objects": 5, "both": 2, "split": 2, "reference_only": 1, "labels_only": 1,
                                 "labels": 4, "labels_away_from_border": 3}


def test_centres_outside_the_image_are_refused():
    with pytest.raises(ValueError, match="reference_centre_outside_image"):
        match_reference_centres(labels(), [(12.0, 1.0)])


def test_group_summary_keeps_control_first_and_pools_reference_only_areas():
    from cytellect_showcase.cellprofiler import group_summary

    def row(interior, count, only, areas):
        return {"labels_away_from_border": interior, "count_nuclei": count, "reference_only": only, "split": 0, "labels_only": 1,
                "both": count - only, "reference_objects": count, "reference_only_area_px": areas, "both_area_px": [900.0]}

    design = {"control_group_id": "control", "groups": [{"id": "treatment", "label": "KO"}, {"id": "control", "label": "NT"}],
              "runs": [{"id": "run1", "label": "Run1"}],
              "fields": {"a": {"group_id": "control", "run_id": "run1"}, "b": {"group_id": "treatment", "run_id": "run1"},
                         "c": {"group_id": "treatment", "run_id": "run1"}}}
    compared = {"A.tif": row(100, 102, 1, [300.0]), "B.tif": row(10, 40, 30, [200.0, 400.0]), "C.tif": row(20, 30, 10, [330.0])}
    summary = group_summary(compared, design, {"A.tif": "a", "B.tif": "b", "C.tif": "c"})
    assert [group["id"] for group in summary["groups"]] == ["control", "treatment"]
    treatment = summary["groups"][1]
    assert treatment["fields"] == 2 and treatment["cytellect_per_field"] == 15 and treatment["cellprofiler_per_field"] == 35
    assert treatment["reference_only_median_area_px"] == 330.0
    assert treatment["matched_fraction"] == 30 / 70
    assert [group["id"] for group in summary["runs"][0]["groups"]] == ["control", "treatment"]
    assert summary["ratio"] == {"cytellect": 15 / 100, "cellprofiler": 35 / 102}
