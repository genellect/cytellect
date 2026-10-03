"""Hand-computed generic measurements and strict scientific input boundaries."""
import numpy as np
import pytest
from cytellect_analysis.regions import (
    BackgroundSpec,
    Calibration2D,
    ChannelSpec,
    RegionMeasurementSpec,
    RegionSetSpec,
    measure_regions,
)
from pydantic import ValidationError


def specification(*, channel=None, calibration=None):
    channel = channel or ChannelSpec(channel_id="actin", label="Actin", stain="phalloidin",
                                     identity_confirmed=True)
    return RegionMeasurementSpec(
        field_id="field_1", analysis_revision_id="analysis_2",
        region_set=RegionSetSpec(region_set_id="cells", label="Cell interiors", mask_revision_id="mask_3",
                                source="imported"),
        channels=(channel,), backgrounds=(BackgroundSpec(channel_id=channel.channel_id,
                                                        roi_revision_id="background_4", confirmed=True),),
        calibration=calibration,
    )


def arrays():
    raw = np.array([[9, 11, 13], [100, 2, 10], [100, 6, 20]], dtype=np.uint8)
    labels = np.array([[0, 0, 0], [0, 7, 7], [0, 7, 19]], dtype=np.uint32)
    background = np.array([[True, True, True], [False, False, False], [False, False, False]])
    return raw, labels, background


def test_hand_computed_signed_intensity_and_anisotropic_area():
    raw, labels, background = arrays()
    original = raw.copy(), labels.copy(), background.copy()
    config = specification(calibration=Calibration2D(pixel_size_x_um=.2, pixel_size_y_um=.5, confirmed=True))
    table = measure_regions({"actin": raw}, labels, {"actin": background}, config)
    assert table.protocol_version == "1.0.0" and table.status == "measured"
    assert [row.region_id for row in table.rows] == [7, 19]
    first, second = table.rows
    # Region 7 contains 2, 10, 6; background median is 11.
    assert (first.area_px, first.mean, first.median, first.integrated) == (3, 6, 6, 18)
    assert (first.mean_corrected, first.median_corrected, first.integrated_corrected) == (-5, -5, -15)
    assert first.area_um2 == pytest.approx(.3)
    assert second.area_um2 == pytest.approx(.1)
    assert first.area_missing_reason is None
    assert second.mean_corrected == second.integrated_corrected == 9
    assert first.channel_id == second.channel_id == "actin"
    assert table.channel_provenance[0].channel.stain == "phalloidin"
    assert table.channel_provenance[0].background_median == 11
    assert first.acquisition_saturation_fraction is None
    assert first.acquisition_saturation_missing_reason == "acquisition_limit_unknown"
    assert not any("gfp" in key or "ncl" in key for key in first.model_dump())
    for actual, expected in zip((raw, labels, background), original, strict=True):
        np.testing.assert_array_equal(actual, expected)


def test_long_table_keeps_different_channels_and_saturation_definitions():
    raw, labels, background = arrays()
    detector = np.array([[100, 100, 100], [0, 4095, 100], [0, 4095, 0]], dtype=np.uint16)
    base = specification()
    dna = ChannelSpec(channel_id="dna", label="DNA染色", stain="Hoechst",
                      identity_confirmed=True, acquisition_saturation_value=4095,
                      acquisition_saturation_confirmed=True)
    config = RegionMeasurementSpec(
        **{**base.model_dump(), "channels": (base.channels[0], dna),
           "backgrounds": (*base.backgrounds, BackgroundSpec(channel_id="dna", roi_revision_id="bg_dna", confirmed=True))})
    table = measure_regions({"actin": raw, "dna": detector}, labels,
                            {"actin": background, "dna": background}, config)
    assert [(row.region_id, row.channel_id) for row in table.rows] == [
        (7, "actin"), (7, "dna"), (19, "actin"), (19, "dna")]
    row = table.rows[1]
    assert row.integrated == 8290 and row.integrated_corrected == 7990
    assert row.median == 4095 and row.median_corrected == 3995
    assert row.mean == pytest.approx(8290 / 3)
    assert row.storage_limit_fraction == 0
    assert row.acquisition_saturation_fraction == pytest.approx(2 / 3)
    assert row.acquisition_saturation_missing_reason is None
    assert row.area_um2 is None and row.area_missing_reason == "calibration_unknown"
    assert table.channel_provenance[1].storage_maximum == 65535


def test_uint16_integral_does_not_overflow_and_storage_limit_is_observable():
    _, labels, background = arrays()
    raw = np.full(labels.shape, 65535, dtype=np.uint16)
    raw[background] = 0
    table = measure_regions({"actin": raw}, labels, {"actin": background}, specification())
    assert table.rows[0].integrated == table.rows[0].integrated_corrected == 196605
    assert table.rows[0].storage_limit_fraction == 1
    assert table.rows[0].acquisition_saturation_fraction is None


def test_even_background_and_even_region_use_midpoint_medians():
    raw = np.array([[2, 4], [0, 9]], dtype=np.uint8)
    labels = np.array([[0, 0], [2, 2]], dtype=np.uint32)
    background = labels == 0
    table = measure_regions({"actin": raw}, labels, {"actin": background}, specification())
    assert table.channel_provenance[0].background_median == 3
    assert table.rows[0].median == table.rows[0].mean == 4.5
    assert table.rows[0].median_corrected == table.rows[0].mean_corrected == 1.5
    assert table.rows[0].integrated_corrected == 3


def test_empty_regions_return_no_rows_not_zero_measurements():
    raw, labels, background = arrays()
    labels[:] = 0
    table = measure_regions({"actin": raw}, labels, {"actin": background}, specification())
    assert table.status == "no_regions" and table.rows == ()
    assert len(table.channel_provenance) == 1


def test_mask_background_and_channel_provenance_are_separate_and_deterministic():
    raw, labels, background = arrays()
    first = measure_regions({"actin": raw}, labels, {"actin": background}, specification())
    repeated = measure_regions({"actin": raw.copy()}, labels.copy(), {"actin": background.copy()}, specification())
    assert first == repeated
    changed = raw.copy()
    changed[1, 1] += 1
    second = measure_regions({"actin": changed}, labels, {"actin": background}, specification())
    assert first.mask_sha256 == second.mask_sha256
    assert first.channel_provenance[0].pixel_sha256 != second.channel_provenance[0].pixel_sha256
    assert first.channel_provenance[0].background_mask_sha256 == second.channel_provenance[0].background_mask_sha256
    assert first.rows[0].analysis_revision_id == "analysis_2"
    assert first.rows[0].mask_revision_id == "mask_3"


@pytest.mark.parametrize("bad_labels", [
    np.ones((3, 3), dtype=bool), np.ones((3, 3), dtype=float),
    np.full((3, 3), -1, dtype=np.int32), np.full((3, 3), 2**32, dtype=np.uint64),
    np.zeros((0, 3), dtype=np.uint32), np.zeros((1, 3, 3), dtype=np.uint32),
])
def test_invalid_labels_are_rejected(bad_labels):
    raw, _, background = arrays()
    with pytest.raises(ValueError, match="invalid_label_array"):
        measure_regions({"actin": raw}, bad_labels, {"actin": background}, specification())


@pytest.mark.parametrize("bad_image", [
    np.zeros((3, 3, 3), dtype=np.uint8), np.zeros((4, 3), dtype=np.uint8),
    np.zeros((3, 3), dtype=np.float32), np.zeros((3, 3), dtype=np.int16),
])
def test_source_rgb_shape_and_dtype_are_not_reinterpreted(bad_image):
    _, labels, background = arrays()
    with pytest.raises(ValueError, match="source_shape_or_dtype"):
        measure_regions({"actin": bad_image}, labels, {"actin": background}, specification())


@pytest.mark.parametrize("bad_background", [
    np.zeros((3, 3), dtype=bool), np.ones((2, 3), dtype=bool), np.ones((3, 3), dtype=np.uint8),
])
def test_background_must_be_nonempty_boolean_with_matching_shape(bad_background):
    raw, labels, _ = arrays()
    with pytest.raises(ValueError, match="background_nonempty_boolean_shape"):
        measure_regions({"actin": raw}, labels, {"actin": bad_background}, specification())


def test_background_overlap_or_missing_channel_is_rejected():
    raw, labels, background = arrays()
    with pytest.raises(ValueError, match="background_overlaps"):
        measure_regions({"actin": raw}, labels, {"actin": np.ones((3, 3), dtype=bool)}, specification())
    with pytest.raises(ValueError, match="mapping_mismatch"):
        measure_regions({"unconfirmed": raw}, labels, {"actin": background}, specification())
    with pytest.raises(ValueError, match="mapping_mismatch"):
        measure_regions({"actin": raw}, labels, {}, specification())


@pytest.mark.parametrize("kwargs", [
    {"pixel_size_x_um": .2, "confirmed": True},
    {"pixel_size_x_um": .2, "pixel_size_y_um": .5, "confirmed": False},
    {"pixel_size_x_um": float("nan"), "pixel_size_y_um": .5, "confirmed": True},
    {"pixel_size_x_um": 0., "pixel_size_y_um": .5, "confirmed": True},
    {"pixel_size_x_um": 1e300, "pixel_size_y_um": 1e300, "confirmed": True},
    {"pixel_size_x_um": 1e-300, "pixel_size_y_um": 1e-300, "confirmed": True},
])
def test_partial_unconfirmed_or_unrepresentable_calibration_is_rejected(kwargs):
    with pytest.raises(ValidationError):
        Calibration2D(**kwargs)


@pytest.mark.parametrize("kwargs", [
    {"acquisition_saturation_value": 4095}, {"acquisition_saturation_confirmed": True},
    {"acquisition_saturation_value": 0, "acquisition_saturation_confirmed": True},
    {"acquisition_saturation_value": 12.5, "acquisition_saturation_confirmed": True},
])
def test_acquisition_limit_requires_matching_explicit_confirmation(kwargs):
    with pytest.raises(ValidationError):
        ChannelSpec(channel_id="actin", label="Actin", identity_confirmed=True, **kwargs)


@pytest.mark.parametrize("limit", [90, 4095])
def test_acquisition_limit_cannot_contradict_samples_or_dtype(limit):
    raw, labels, background = arrays()
    config = specification(channel=ChannelSpec(channel_id="actin", label="Actin", identity_confirmed=True,
                                               acquisition_saturation_value=limit,
                                               acquisition_saturation_confirmed=True))
    with pytest.raises(ValueError, match="acquisition_limit_inconsistent"):
        measure_regions({"actin": raw}, labels, {"actin": background}, config)


def test_identity_background_confirmation_and_extra_fields_are_required():
    with pytest.raises(ValidationError):
        ChannelSpec(channel_id="actin", label="Actin", identity_confirmed=False)
    with pytest.raises(ValidationError):
        BackgroundSpec(channel_id="actin", roi_revision_id="bg", confirmed=False)
    with pytest.raises(ValidationError):
        ChannelSpec(channel_id="actin", label="Actin", identity_confirmed=True, automatic_stain_guess=True)


@pytest.mark.parametrize("value", [1, "true", None])
def test_confirmations_are_explicit_booleans_not_coerced(value):
    with pytest.raises(ValidationError):
        ChannelSpec(channel_id="actin", label="Actin", identity_confirmed=value)
    with pytest.raises(ValidationError):
        BackgroundSpec(channel_id="actin", roi_revision_id="bg", confirmed=value)
    with pytest.raises(ValidationError):
        Calibration2D(pixel_size_x_um=.2, pixel_size_y_um=.5, confirmed=value)


def test_extreme_valid_calibration_multiplies_pixel_area_before_region_count():
    raw, labels, background = arrays()
    calibration = Calibration2D(pixel_size_x_um=1e308, pixel_size_y_um=1e-308, confirmed=True)
    table = measure_regions({"actin": raw}, labels, {"actin": background}, specification(calibration=calibration))
    assert table.rows[0].area_um2 == pytest.approx(3)


def test_metadata_copy_cannot_bypass_scientific_validation():
    raw, labels, background = arrays()
    config = specification()
    forged = config.model_copy(update={"channels": (config.channels[0].model_copy(update={"identity_confirmed": False}),)})
    with pytest.raises(ValidationError):
        measure_regions({"actin": raw}, labels, {"actin": background}, forged)


def test_duplicate_channels_missing_background_and_unknown_defining_channel_fail():
    base = specification()
    with pytest.raises(ValidationError, match="duplicate_channel"):
        RegionMeasurementSpec(**{**base.model_dump(), "channels": (base.channels[0], base.channels[0])})
    with pytest.raises(ValidationError, match="every_channel_requires_background"):
        RegionMeasurementSpec(**{**base.model_dump(), "backgrounds": (
            BackgroundSpec(channel_id="other", roi_revision_id="bg", confirmed=True),)})
    with pytest.raises(ValidationError, match="unknown_defining_channel"):
        RegionMeasurementSpec(**{**base.model_dump(), "region_set": RegionSetSpec(
            region_set_id="cells", label="Cells", mask_revision_id="m", source="manual", defining_channel_id="other")})
    with pytest.raises(ValidationError, match="requires_defining_channel"):
        RegionSetSpec(region_set_id="nuclei", label="Nuclei", mask_revision_id="m", source="stardist_nuclear")
