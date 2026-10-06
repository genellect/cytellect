import numpy as np
import pytest
from cytellect_analysis.masks import apply_compartment_edit


def planes():
    nuclei = np.zeros((40, 80), np.uint32)
    nuclei[5:35, 5:35] = 1
    nuclei[5:35, 45:75] = 2
    nucleoli = np.zeros_like(nuclei)
    nucleoli[10:15, 10:15] = 1
    nucleoli[10:15, 50:55] = 2
    return nuclei, nucleoli


def square(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def test_drawn_nucleolus_inside_one_parent_is_added():
    nuclei, nucleoli = planes()
    edited = apply_compartment_edit(nucleoli, nuclei, "nucleoli", "add", [], square(20, 20, 28, 28))
    new = edited == 3
    assert new.any() and set(np.unique(nuclei[new])) == {1}
    assert np.array_equal(edited[nucleoli > 0], nucleoli[nucleoli > 0])


@pytest.mark.parametrize("polygon", [square(30, 10, 50, 20), square(36, 10, 44, 20), square(0, 0, 8, 8)])
def test_drawn_nucleolus_spanning_or_leaving_its_parent_is_rejected(polygon):
    nuclei, nucleoli = planes()
    with pytest.raises(ValueError, match="nucleolus_outside_parent"):
        apply_compartment_edit(nucleoli, nuclei, "nucleoli", "add", [], polygon)


def test_replacement_cannot_move_a_nucleolus_into_another_nucleus():
    nuclei, nucleoli = planes()
    with pytest.raises(ValueError, match="nucleolus_outside_parent"):
        apply_compartment_edit(nucleoli, nuclei, "nucleoli", "replace", [1], square(30, 10, 50, 20))


def test_merge_across_parents_is_rejected_but_within_one_parent_is_allowed():
    nuclei, nucleoli = planes()
    with pytest.raises(ValueError, match="nucleoli_span_parents"):
        apply_compartment_edit(nucleoli, nuclei, "nucleoli", "merge", [1, 2], [])
    nucleoli[20:25, 20:25] = 3
    merged = apply_compartment_edit(nucleoli, nuclei, "nucleoli", "merge", [1, 3], [])
    assert set(np.unique(merged)) == {0, 1, 2}


def test_nucleoplasm_is_derived_and_never_edited_directly():
    nuclei, nucleoli = planes()
    with pytest.raises(ValueError, match="nucleoplasm_is_derived"):
        apply_compartment_edit(nucleoli, nuclei, "nucleoplasm", "delete", [1], [])


def test_nucleoplasm_uses_adopted_edited_nucleoli_not_a_new_threshold():
    from cytellect_analysis.compartment_engine import nucleoplasm_from_adopted_nucleoli
    nuclei, nucleoli = planes()
    # The researcher deleted nucleus 2's only candidate and drew a new one in nucleus 1.
    edited = apply_compartment_edit(nucleoli, nuclei, "nucleoli", "delete", [2], [])
    edited = apply_compartment_edit(edited, nuclei, "nucleoli", "add", [], square(20, 20, 28, 28))
    plasm, details = nucleoplasm_from_adopted_nucleoli(nuclei, edited, {1: "candidate", 2: "candidate"})
    expected = np.where((nuclei == 1) & (edited == 0), 1, 0)
    assert np.array_equal(plasm, expected)
    assert details["nucleolar_states"] == {1: "candidate", 2: "no_candidate"}
    assert details["compartment_status"] == "incomplete"
    assert details["nucleolar_source"] == "adopted_revision"


def test_recipe_accepts_adopted_nucleoli_only_for_nucleoplasm():
    from cytellect_analysis.region_contracts import RegionCompartmentRecipe
    base = {"region_set_id": "plasm", "label": "Nucleoplasm", "compartment": "nucleoplasm",
            "nuclear_revision_id": "n1", "nuclear_channel_id": "dapi", "defining_channel_id": "ncl"}
    assert RegionCompartmentRecipe.model_validate({**base, "nucleolar_revision_id": "o1"}).nucleolar_revision_id == "o1"
    assert RegionCompartmentRecipe.model_validate(base).nucleolar_revision_id is None
    with pytest.raises(ValueError, match="nucleolar_revision_only_for_nucleoplasm"):
        RegionCompartmentRecipe.model_validate({**base, "compartment": "nucleoli", "nucleolar_revision_id": "o1"})
