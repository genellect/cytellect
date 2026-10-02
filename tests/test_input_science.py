"""Input and arithmetic invariants, including genuine two-channel acquisitions."""
import numpy as np
import pytest
import tifffile
from cytellect_analysis.contracts import MaskEdit, Recipe
from cytellect_analysis.images import read_tiff, render_preview
from cytellect_analysis.masks import apply_edit, contours, validate_labels
from cytellect_analysis.measurement import apply_gfp_gate, measure


def test_ome_two_channels_order_and_missing_c_rejected(tmp_path):
    path = tmp_path / "input.ome.tif"
    data = np.stack([np.full((9, 10), 7, np.uint16), np.full((9, 10), 91, np.uint16)])
    tifffile.imwrite(path, data, ome=True, metadata={"axes": "CYX"})
    assert np.array_equal(read_tiff(path, channel_indices=[1, 0]), data[[1, 0]])
    for mapping in ([0, 0], [False, 1], [0, 1, 2]):
        with pytest.raises(ValueError, match="mapping_required"):
            read_tiff(path, channel_indices=mapping)
    single = tmp_path / "single.tif"
    tifffile.imwrite(single, data[0])
    with pytest.raises(ValueError, match="mapping_required"):
        read_tiff(single, channel_indices=[0, 1, 2])


def test_unsupported_axes_and_depth_are_not_inferred(tmp_path):
    for axes, shape, dtype in [("ZYX", (2, 9, 10), np.uint16), ("TYX", (2, 9, 10), np.uint16),
                                ("QYX", (2, 9, 10), np.uint16), ("YX", (9, 10), np.float32)]:
        path = tmp_path / (axes + np.dtype(dtype).name + ".tif")
        tifffile.imwrite(path, np.zeros(shape, dtype), metadata={"axes": axes}, photometric="minisblack")
        with pytest.raises(ValueError):
            read_tiff(path)


def inputs():
    nuclei = np.zeros((8, 8), np.uint32)
    nuclei[2:6, 2:6] = 1
    nucleoli = np.zeros_like(nuclei)
    nucleoli[3:5, 3:5] = 1
    background = np.zeros_like(nuclei, dtype=bool)
    background[0] = True
    dapi = (nuclei * 20 + 2).astype(np.uint16)
    ncl = (nuclei * 10 + nucleoli * 30 + 5).astype(np.uint16)
    gfp = (nuclei * 13 + 3).astype(np.uint16)
    metadata = {"condition": "A", "sample": "s", "experimental_unit": "u", "acquisition_date": "day"}
    return nuclei, nucleoli, background, {"dapi": dapi, "ncl": ncl, "gfp": gfp}, metadata


def test_absent_channels_are_missing_not_zero():
    nuclei, nucleoli, bg, channels, metadata = inputs()
    ncl_only = {"dapi": channels["dapi"], "ncl": channels["ncl"]}
    cells, _, _ = measure(ncl_only, nuclei, nucleoli, bg, Recipe(), metadata, "f")
    row = apply_gfp_gate(cells, Recipe())[0]
    assert row["gfp_mean_corrected"] is None and not row["channel_availability"]["gfp"]
    assert row["ncl_nucleoplasm_mean_corrected"] == 10
    assert row["ncl_nucleoli_mean_corrected"] == 40
    assert row["ncl_log2_nucleoplasm_over_nucleoli"] == -2
    assert render_preview(ncl_only).startswith(b"\x89PNG")
    gfp_only = {"dapi": channels["dapi"], "gfp": channels["gfp"]}
    cells, objects, _ = measure(gfp_only, nuclei, np.zeros_like(nucleoli), bg,
                                Recipe(id="gfp-nuclear-2d"), metadata, "f")
    assert cells[0]["gfp_mean_corrected"] == 13
    assert cells[0]["ncl_nucleus_mean_corrected"] is None
    assert cells[0]["nucleolar_count"] is None and objects == []
    with pytest.raises(ValueError, match="recipe_required_channels_missing"):
        measure(ncl_only, nuclei, nucleoli, bg, Recipe(gfp_gate="manual", gfp_threshold=1), metadata, "f")


def test_integer_background_and_fractional_labels_rejected():
    nuclei, nucleoli, bg, channels, metadata = inputs()
    with pytest.raises(ValueError, match="background_boolean"):
        measure(channels, nuclei, nucleoli, bg.astype(np.uint8), Recipe(), metadata, "f")
    with pytest.raises(ValueError, match="invalid_label"):
        validate_labels(nuclei.astype(float) + .2, nucleoli)
    with pytest.raises(ValueError, match="measurement_source"):
        measure({**channels, "gfp": channels["gfp"][:3]}, nuclei, nucleoli, bg, Recipe(), metadata, "f")


def test_uint32_sparse_contours_and_edit_do_not_overflow():
    labels = np.zeros((8, 8), np.uint32)
    labels[1:3, 1:3] = 3_000_000_000
    assert {c["id"] for c in contours(labels)} == {3_000_000_000}
    edit = MaskEdit(field_id="f", layer="nuclei", operation="add",
                    polygon=[(4, 4), (6, 4), (6, 6), (4, 6)])
    new, _, _ = apply_edit(labels, np.zeros_like(labels), np.zeros_like(labels), edit)
    assert new.max() == 3_000_000_001
    bad = labels.copy()
    bad[1:3, 1:3] = np.iinfo(np.uint32).max
    with pytest.raises(ValueError, match="label_id_exhausted"):
        apply_edit(bad, np.zeros_like(bad), np.zeros_like(bad), edit)



def test_gfp_recipe_does_not_measure_ncl_even_if_extra_channel_is_acquired():
    nuclei, nucleoli, bg, channels, metadata = inputs()
    cells, _, _ = measure(channels, nuclei, np.zeros_like(nucleoli), bg, Recipe(id="gfp-nuclear-2d"), metadata, "f")
    assert cells[0]["channel_availability"]["ncl"]
    assert cells[0]["ncl_nucleus_mean_corrected"] is None
    assert cells[0]["ratio_missing_reason"] == "ncl_not_measured_recipe"


def test_ome_self_uuid_survives_renaming_but_external_uuid_is_rejected(tmp_path):
    import re

    data = np.stack([np.full((9, 10), 7, np.uint16), np.full((9, 10), 91, np.uint16)])
    for external in (False, True):
        path = tmp_path / f"internal-id-{external}.ome.tif"
        tifffile.imwrite(path, data, ome=True, metadata={"axes": "CYX"})
        with tifffile.TiffFile(path) as image:
            xml = image.ome_metadata
        uuid = re.search(r'UUID="([^"]+)"', xml).group(1)
        reference_uuid = "urn:uuid:00000000-0000-0000-0000-000000000001" if external else uuid
        xml = re.sub(r"<TiffData\b[^>]*/>",
                     lambda match: match.group(0)[:-2] + '><UUID FileName="../never-open-this.tif">'
                     + reference_uuid + "</UUID></TiffData>", xml)
        tifffile.tiffcomment(path, xml)
        if external:
            with pytest.raises(ValueError, match="external_ome"):
                read_tiff(path, channel_indices=[1, 0])
        else:
            assert np.array_equal(read_tiff(path, channel_indices=[1, 0]), data[[1, 0]])


@pytest.mark.parametrize("pages,records", [
    (2, '<TiffData IFD="0" PlaneCount="3"/>'),  # Formerly accepted; channel 3 was invented as zeros.
    (3, '<TiffData IFD="0" PlaneCount="2"/>'),
    (3, '<TiffData IFD="0" FirstC="0"/><TiffData IFD="0" FirstC="1"/><TiffData IFD="2" FirstC="2"/>'),
    (3, '<TiffData IFD="0" FirstC="0"/><TiffData IFD="1" FirstC="0"/><TiffData IFD="2" FirstC="2"/>'),
    (3, '<TiffData IFD="0" FirstZ="1" PlaneCount="3"/>'),
    (3, ''),
])
def test_incomplete_or_duplicate_ome_planes_rejected_before_pixel_decode(tmp_path, monkeypatch, pages, records):
    path = tmp_path / "broken.ome.tif"
    xml = ('<?xml version="1.0"?><OME xmlns="http://www.openmicroscopy.org/Schemas/OME/2016-06">'
           '<Image ID="Image:0"><Pixels ID="Pixels:0" DimensionOrder="XYCZT" Type="uint16" '
           'SizeX="4" SizeY="4" SizeC="3" SizeZ="1" SizeT="1">'
           + ''.join(f'<Channel ID="Channel:0:{c}" SamplesPerPixel="1"/>' for c in range(3))
           + records + '</Pixels></Image></OME>')
    tifffile.imwrite(path, np.full((pages, 4, 4), 7, np.uint16),
                     photometric="minisblack", description=xml, metadata=None)
    def forbid_decode(*args, **kwargs):
        raise AssertionError("invalid OME must be rejected before decoding")
    monkeypatch.setattr(tifffile.TiffPageSeries, "asarray", forbid_decode)
    with pytest.raises(ValueError, match="ome_plane_coverage_invalid"):
        read_tiff(path, channel_indices=[0, 1, 2])


def test_ome_reordered_ifds_follow_explicit_channel_records(tmp_path):
    path = tmp_path / "reordered.ome.tif"
    data = np.stack([np.full((9, 10), n, np.uint16) for n in (7, 91, 103)])
    tifffile.imwrite(path, data, ome=True, metadata={"axes": "CYX"})
    import re
    with tifffile.TiffFile(path) as image:
        xml = image.ome_metadata
    xml = re.sub(r"<TiffData\b[^>]*/>", '<TiffData IFD="2" FirstC="0"/>'
                 '<TiffData IFD="0" FirstC="1"/><TiffData IFD="1" FirstC="2"/>', xml)
    tifffile.tiffcomment(path, xml)
    assert np.array_equal(read_tiff(path, channel_indices=[0, 1, 2]), data[[2, 0, 1]])
