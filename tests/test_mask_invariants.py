"""Exact native raster invariants for manual nuclear merge and split."""
import numpy as np
import pytest
from cytellect_analysis.contracts import MaskEdit, Recipe
from cytellect_analysis.masks import apply_edit, validate_labels
from cytellect_analysis.measurement import measure


def field():
    nuclei = np.zeros((14, 18), np.uint32)
    nuclei[3:8, 2:6], nuclei[3:8, 6:10], nuclei[3:8, 12:16] = 1, 2, 3
    nucleoli = np.zeros_like(nuclei)
    nucleoli[4:6, 3:5], nucleoli[4:6, 7:9], nucleoli[4:6, 13:15] = 11, 22, 33
    manual = np.zeros_like(nuclei)
    manual[10:12, 3:8] = 7
    channels = {"dapi": (nuclei * 10 + 5).astype(np.uint16),
                "ncl": (nuclei * 20 + 8 + (nucleoli > 0) * 100).astype(np.uint16)}
    background = np.zeros(nuclei.shape, bool)
    background[0] = True
    return nuclei, nucleoli, manual, channels, background


@pytest.mark.parametrize("operation", ["merge", "split"])
def test_nuclear_edit_invalidates_all_affected_children_and_remeasures_exact_pixels(operation):
    nuclei, nucleoli, manual, channels, background = field()
    originals = [a.copy() for a in (nuclei, nucleoli, manual)]
    edit = MaskEdit(field_id="fixed", layer="nuclei", operation=operation,
                    ids=[1, 2] if operation == "merge" else [1],
                    polygon=[] if operation == "merge" else [(2, 3), (4, 3), (4, 8), (2, 8)])
    new_nuclei, new_nucleoli, new_manual = apply_edit(nuclei, nucleoli, manual, edit)
    validate_labels(new_nuclei, new_nucleoli)
    np.testing.assert_array_equal(new_nuclei > 0, nuclei > 0)
    np.testing.assert_array_equal(new_manual, manual)
    np.testing.assert_array_equal(new_nuclei == 3, nuclei == 3)
    np.testing.assert_array_equal(new_nucleoli == 33, nucleoli == 33)
    affected = np.isin(nuclei, [1, 2] if operation == "merge" else [1])
    assert not new_nucleoli[affected].any()
    if operation == "merge":
        np.testing.assert_array_equal(new_nuclei == 1, np.isin(nuclei, [1, 2]))
        assert 2 not in np.unique(new_nuclei)
    else:
        assert set(np.unique(new_nuclei[nuclei == 1])) == {1, 4}
        assert (new_nuclei == 1).sum() == (new_nuclei == 4).sum() == 10
        np.testing.assert_array_equal(new_nuclei == 2, nuclei == 2)
        np.testing.assert_array_equal(new_nucleoli == 22, nucleoli == 22)
    rows, _, manual_rows = measure(channels, new_nuclei, new_nucleoli, background,
                                   Recipe(), {}, "fixed", new_manual)
    for row in rows:
        expected = channels["ncl"][new_nuclei == row["nucleus_id"]].astype(float)
        assert row["nucleus_area_px"] == len(expected)
        assert row["ncl_nucleus_mean"] == expected.mean()
        assert row["ncl_nucleus_integrated_corrected"] == (expected - 8).sum()
    assert manual_rows[0]["area_px"] == 10
    for actual, unchanged in zip((nuclei, nucleoli, manual), originals, strict=True):
        np.testing.assert_array_equal(actual, unchanged)


def test_nucleolar_merge_across_parents_is_rejected_without_input_mutation():
    nuclei, nucleoli, manual, _, _ = field()
    original = nucleoli.copy()
    with pytest.raises(ValueError, match="nucleolus_requires_single_parent"):
        apply_edit(nuclei, nucleoli, manual,
                   MaskEdit(field_id="fixed", layer="nucleoli", operation="merge", ids=[11, 22]))
    np.testing.assert_array_equal(nucleoli, original)


@pytest.mark.parametrize("polygon", [[(2, 3), (6, 3), (6, 8), (2, 8)],
                                   [(11, 10), (13, 10), (13, 12), (11, 12)]])
def test_nuclear_split_rejects_whole_or_empty_partition(polygon):
    nuclei, nucleoli, manual, _, _ = field()
    with pytest.raises(ValueError, match="split_requires_partial_region"):
        apply_edit(nuclei, nucleoli, manual,
                   MaskEdit(field_id="fixed", layer="nuclei", operation="split", ids=[1], polygon=polygon))
