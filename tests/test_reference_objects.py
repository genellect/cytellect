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
