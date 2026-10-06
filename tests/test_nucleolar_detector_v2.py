import numpy as np
import pytest
from cytellect_analysis.compartment_engine import detect_compartments
from cytellect_analysis.nucleolar_detector_v2 import NucleolarDetectorV20, detect_nucleoli_v2
from cytellect_analysis.region_contracts import RegionCompartmentRecipe


def disk(shape, cy, cx, r):
    y, x = np.ogrid[:shape[0], :shape[1]]
    return (y - cy) ** 2 + (x - cx) ** 2 <= r * r


def field():
    shape = (120, 240)
    nuclei = np.zeros(shape, np.uint32)
    nuclei[disk(shape, 60, 60, 40)] = 1
    nuclei[disk(shape, 60, 180, 40)] = 2
    dapi = np.full(shape, 10, np.uint16)
    dapi[nuclei > 0] = 1000
    holes = disk(shape, 50, 50, 8) | disk(shape, 72, 75, 6) | disk(shape, 60, 180, 9)
    dapi[holes] = 300
    # Nucleus 1 is unstressed: NCL is enriched in the holes. Nucleus 2 is stressed:
    # NCL has left its nucleolus, which is now NCL-poor, yet still a DNA-poor hole.
    ncl = np.full(shape, 5, np.uint16)
    ncl[nuclei == 1] = 200
    ncl[(nuclei == 1) & holes] = 900
    ncl[nuclei == 2] = 400
    ncl[(nuclei == 2) & holes] = 150
    return nuclei, dapi, ncl, holes


def test_dapi_poor_finds_nucleoli_whether_or_not_ncl_has_left_them():
    nuclei, dapi, _, holes = field()
    labels, info = detect_nucleoli_v2(dapi, None, nuclei, NucleolarDetectorV20(smoothing_sigma_px=0))
    assert info["nucleolar_states"] == {1: "candidate", 2: "candidate"}
    assert np.array_equal(labels > 0, holes & (nuclei > 0))
    assert set(np.unique(nuclei[labels > 0])) == {1, 2}
    assert info["nucleolar_definition_source"] == "dapi_poor" and info["references"] == ["kodiha-2011"]


def test_dapi_poor_without_holes_is_no_candidate_and_uniform_is_indeterminate():
    nuclei, dapi, _, holes = field()
    dapi[holes] = 1000
    labels, info = detect_nucleoli_v2(dapi, None, nuclei, NucleolarDetectorV20(smoothing_sigma_px=0))
    assert not labels.any() and info["nucleolar_states"] == {1: "indeterminate", 2: "indeterminate"}
    dapi[disk(dapi.shape, 60, 60, 3)] = 990
    _, info = detect_nucleoli_v2(dapi, None, nuclei, NucleolarDetectorV20(smoothing_sigma_px=0))
    assert info["nucleolar_states"][1] == "no_candidate"


def test_rim_exclusion_ignores_dark_nuclear_edges():
    nuclei, dapi, _, holes = field()
    edge = (nuclei == 1) & ~disk(dapi.shape, 60, 60, 38)
    dapi[edge] = 200
    labels, _ = detect_nucleoli_v2(dapi, None, nuclei, NucleolarDetectorV20(smoothing_sigma_px=0, rim_exclusion_px=4))
    assert not (labels > 0)[edge].any()
    assert (labels > 0)[holes & (nuclei == 1)].all()


def test_size_and_solidity_filters_apply():
    nuclei, dapi, _, _ = field()
    params = NucleolarDetectorV20(smoothing_sigma_px=0, minimum_area_px=150)
    labels, info = detect_nucleoli_v2(dapi, None, nuclei, params)
    assert info["nucleolar_thresholds"][1]["candidates"] == 1
    with pytest.raises(ValueError):
        NucleolarDetectorV20(minimum_area_px=10, maximum_area_px=5)


def test_marker_source_uses_relative_threshold_and_is_reported_as_fc_defined():
    nuclei, dapi, _, holes = field()
    marker = np.full(dapi.shape, 20, np.uint16)
    marker[nuclei > 0] = 60
    marker[holes] = 800
    labels, info = detect_nucleoli_v2(dapi, marker, nuclei, NucleolarDetectorV20(source="marker", minimum_solidity=0))
    assert info["nucleolar_states"] == {1: "candidate", 2: "candidate"}
    assert (labels > 0).sum() > 0 and not (labels > 0)[(nuclei > 0) & ~holes].any()
    assert info["mask_meaning"].startswith("FC/rDNA") and info["references"] == ["potapova-2023"]
    with pytest.raises(ValueError, match="nucleolar_marker_channel_required"):
        detect_nucleoli_v2(dapi, None, nuclei, NucleolarDetectorV20(source="marker"))


def test_detect_compartments_derives_nucleoplasm_from_dapi_poor_nucleoli_without_fiji():
    nuclei, dapi, ncl, holes = field()
    masks, info = detect_compartments({"dapi": dapi, "ncl": dapi}, nuclei,
                                      NucleolarDetectorV20(smoothing_sigma_px=0), output_dir=None, executable="")
    assert np.array_equal(masks["nucleoli"] > 0, holes & (nuclei > 0))
    assert np.array_equal(masks["nucleoplasm"] > 0, (nuclei > 0) & ~holes)
    assert info["compartment_status"] == "complete" and info["nuclear_detection_performed"] is False
    # The stressed nucleus (2): nucleoplasm NCL exceeds nucleolar NCL, measured from original pixels.
    assert ncl[masks["nucleoplasm"] == 2].mean() > ncl[(masks["nucleoli"] > 0) & (nuclei == 2)].mean()


def test_recipe_requires_nuclear_channel_for_dapi_poor_and_distinct_channel_otherwise():
    base = {"region_set_id": "nucleoli", "label": "Nucleoli", "compartment": "nucleoli",
            "nuclear_revision_id": "n1", "nuclear_channel_id": "dapi"}
    ok = RegionCompartmentRecipe.model_validate({**base, "defining_channel_id": "dapi",
                                                 "detector": {"protocol_version": "2.0.0"}})
    assert ok.detector.source == "dapi_poor"
    with pytest.raises(ValueError, match="dapi_poor_nucleoli_use_the_nuclear_channel"):
        RegionCompartmentRecipe.model_validate({**base, "defining_channel_id": "ncl", "detector": {"protocol_version": "2.0.0"}})
    RegionCompartmentRecipe.model_validate({**base, "defining_channel_id": "ubf",
                                            "detector": {"protocol_version": "2.0.0", "source": "marker"}})
    with pytest.raises(ValueError, match="compartment_requires_distinct_channels"):
        RegionCompartmentRecipe.model_validate({**base, "defining_channel_id": "dapi",
                                                "detector": {"protocol_version": "2.0.0", "source": "marker"}})


def test_methods_text_names_the_chosen_nucleolar_definition_and_adopted_nucleoplasm():
    from cytellect_analysis.region_exports import _compartment_initial
    base = {"region_set_id": "nucleoli", "label": "Nucleoli", "compartment": "nucleoli",
            "nuclear_revision_id": "n1", "nuclear_channel_id": "dapi"}
    dapi = RegionCompartmentRecipe(**base, defining_channel_id="dapi", detector=NucleolarDetectorV20())
    text = _compartment_initial(dapi)
    assert "DNA-poor" in text and "0.7 ×" in text and "10.1186/1471-2121-12-25" in text and "NCL-enriched" not in text
    marker = RegionCompartmentRecipe(**base, defining_channel_id="ubf",
                                     detector=NucleolarDetectorV20(source="marker", maximum_area_px=500))
    text = _compartment_initial(marker)
    assert "marker channel" in text and "0.4 × (max − min)" in text and "4–500 px" in text and "10.7554/eLife.88799" in text
    plasm = RegionCompartmentRecipe(**{**base, "region_set_id": "nucleoplasm", "compartment": "nucleoplasm"},
                                    defining_channel_id="dapi", detector=NucleolarDetectorV20(), nucleolar_revision_id="o1")
    assert "adopted, researcher-reviewed nucleoli of revision o1" in _compartment_initial(plasm)
