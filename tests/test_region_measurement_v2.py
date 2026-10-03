"""Area-only hand references and fail-closed persisted scientific contracts."""
import hashlib
import json
from typing import Literal

import numpy as np
import pytest
from cytellect_analysis.region_measurement_v2 import (
    RegionMeasurementPolicy,
    RegionMeasurementSpecV2,
    RegionMeasurementTableV2,
    measure_regions_area,
    measure_regions_versioned,
    region_table_from_json,
    require_region_metric,
    validate_area_backgrounds,
)
from cytellect_analysis.regions import (
    BackgroundSpec,
    Calibration2D,
    ChannelSpec,
    RegionMeasurementSpec,
    RegionModel,
    RegionSetSpec,
    measure_regions,
)
from pydantic import ValidationError


def policy():
    return RegionMeasurementPolicy(version="1.0.0", mode="area_only")


def test_dependency_free_policy_keeps_pre_extraction_schema_and_json():
    from cytellect_analysis.region_policy import RegionMeasurementPolicy as SharedPolicy

    # Exact original base/fields retained as an independent migration reference.
    class OriginalPolicy(RegionModel):
        version: Literal["1.0.0"]
        mode: Literal["area_only"]

    original = OriginalPolicy(version="1.0.0", mode="area_only")
    expected_schema = OriginalPolicy.model_json_schema()
    expected_schema["title"] = "RegionMeasurementPolicy"
    assert SharedPolicy is RegionMeasurementPolicy
    assert SharedPolicy.model_config == OriginalPolicy.model_config
    assert SharedPolicy.model_json_schema() == expected_schema
    assert policy().model_dump_json() == original.model_dump_json()
    with pytest.raises(ValidationError):
        SharedPolicy.model_validate(policy().model_copy(update={"mode": "raw"}))
    for invalid in ({"version": "1.0.0"}, {"mode": "area_only"},
                    {"version": "1.0.0", "mode": "area_only", "background": 0}):
        with pytest.raises(ValidationError):
            SharedPolicy.model_validate(invalid)


def specification(*, channels=None, calibration=None):
    return RegionMeasurementSpecV2(
        measurement=policy(), field_id="field_1", analysis_revision_id="analysis_2",
        region_set=RegionSetSpec(region_set_id="cells", label="Reviewed interiors",
                                mask_revision_id="mask_3", source="imported"),
        channels=channels or (ChannelSpec(channel_id="actin", label="Actin", stain="phalloidin",
                                         identity_confirmed=True),),
        calibration=calibration,
    )


def arrays():
    # Region 7 = a 2 x 3 interior rectangle; region 19 = two 2 x 3 border pieces.
    labels = np.zeros((6, 8), dtype=np.uint32)
    labels[2:4, 2:5] = 7
    labels[0:2, 5:8] = 19
    labels[4:6, 5:8] = 19
    return np.arange(48, dtype=np.uint8).reshape(6, 8), labels


def measured(*, calibration=None):
    raw, labels = arrays()
    return measure_regions_area({"actin": raw}, labels, specification(calibration=calibration))


def test_native_pixel_hand_reference_anisotropic_area_and_hashes():
    raw, labels = arrays()
    saved = raw.copy(), labels.copy()
    result = measure_regions_area({"actin": raw}, labels, specification(
        calibration=Calibration2D(pixel_size_x_um=.2, pixel_size_y_um=.3, confirmed=True)))
    assert [(r.region_id, r.area_px, r.touches_border) for r in result.rows] == [(7, 6, False), (19, 12, True)]
    assert [r.area_um2 for r in result.rows] == pytest.approx([.36, .72])
    assert all(r.area_missing_reason is None for r in result.rows)
    # Independent canonical byte construction, not the production hash helper.
    expected_mask_hash = hashlib.sha256(b"cytellect-array-v1|<u4|6,8|" + labels.astype("<u4").tobytes()).hexdigest()
    expected_image_hash = hashlib.sha256(b"cytellect-array-v1||u1|6,8|" + bytes(range(48))).hexdigest()
    assert result.mask_sha256 == expected_mask_hash
    assert result.channel_provenance[0].pixel_sha256 == expected_image_hash
    for actual, original in zip((raw, labels), saved, strict=True):
        np.testing.assert_array_equal(actual, original)
    assert region_table_from_json(result.model_dump_json()) == result


def test_no_background_or_signal_statistics_even_if_every_pixel_is_a_region(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("area-only must not calculate signal statistics")

    monkeypatch.setattr(np, "median", forbidden)
    monkeypatch.setattr(np, "mean", forbidden)
    raw = np.full((2, 4), 65535, dtype=np.uint16)
    labels = np.full((2, 4), 4294967295, dtype=np.uint32)
    result = measure_regions_versioned({"actin": raw}, labels, {}, specification())
    row = result.rows[0]
    assert row.region_id == 4294967295 and row.area_px == 8
    assert row.area_um2 is None and row.area_missing_reason == "calibration_unknown"
    for name in ("mean", "median", "integrated", "mean_corrected", "median_corrected", "integrated_corrected",
                 "storage_limit_fraction", "acquisition_saturation_fraction"):
        assert getattr(row, name) is None
    assert row.intensity_missing_reason == row.storage_limit_missing_reason == "not_requested"
    assert row.acquisition_saturation_missing_reason == "not_requested"
    provenance = result.channel_provenance[0].model_dump()
    assert provenance["background"] == {"status": "not_measured", "reason": "not_required_for_area"}
    assert not any(name in provenance for name in ("background_median", "background_pixel_count", "confirmed"))


def test_three_channels_repeat_geometry_without_inventing_three_regions_or_stain():
    raw, labels = arrays()
    channels = tuple(ChannelSpec(channel_id=cid, label=label, identity_confirmed=True)
                     for cid, label in (("marker", "Unknown stain"), ("actin", "Actin"), ("dna", "DNA")))
    result = measure_regions_area({c.channel_id: raw.astype(np.uint16) for c in channels}, labels,
                                  specification(channels=channels))
    assert len(result.rows) == 6
    assert {(r.region_id, r.area_px) for r in result.rows} == {(7, 6), (19, 12)}
    assert [r.channel_id for r in result.rows] == ["marker", "actin", "dna"] * 2
    assert all(c.channel.stain is None and c.dtype == "uint16" for c in result.channel_provenance)


def test_empty_regions_keep_source_and_policy_but_no_zero_valued_measurements():
    raw, labels = arrays()
    labels[:] = 0
    result = measure_regions_area({"actin": raw}, labels, specification())
    assert result.status == "no_regions" and result.rows == ()
    assert len(result.channel_provenance) == 1 and result.measurement == policy()


@pytest.mark.parametrize("backgrounds", [{"actin": np.zeros((6, 8), dtype=bool)}, {"field_1": {}}, [], None])
def test_area_only_refuses_supplied_backgrounds_even_if_empty_pixels(backgrounds):
    with pytest.raises(ValueError, match="region_area_only_backgrounds_forbidden"):
        validate_area_backgrounds(policy(), backgrounds)


@pytest.mark.parametrize("value", ["raw", "area_and_raw", "corrected", "AREA_ONLY", None, 1])
def test_unimplemented_policy_cannot_fall_back_to_area_or_legacy(value):
    with pytest.raises(ValidationError):
        RegionMeasurementPolicy(version="1.0.0", mode=value)


@pytest.mark.parametrize("metric", ["mean", "mean_corrected", "integrated", "storage_limit_fraction", "arbitrary"])
def test_intensity_is_unsupported_not_all_missing(metric):
    with pytest.raises(ValueError, match="region_metric_not_measured"):
        require_region_metric(policy(), metric)


def test_area_um2_capability_is_distinct_from_missing_calibration_and_legacy_unchanged():
    for metric in ("area_px", "area_um2"):
        require_region_metric(policy(), metric)
    assert measured().rows[0].area_missing_reason == "calibration_unknown"
    require_region_metric(None, "mean_corrected")
    validate_area_backgrounds(None, {"actin": np.ones((2, 2), dtype=bool)})


@pytest.mark.parametrize("value", [np.zeros((6, 8, 3), dtype=np.uint8), np.zeros((6, 8), dtype=float),
                                 np.zeros((3, 8), dtype=np.uint8), np.zeros((6, 8), dtype=bool)])
def test_source_is_still_native_2d_uint8_or_uint16(value):
    with pytest.raises(ValueError, match="region_source_shape_or_dtype_invalid"):
        measure_regions_area({"actin": value}, arrays()[1], specification())


@pytest.mark.parametrize("value", [np.zeros((6, 8), dtype=bool), np.zeros((6, 8), dtype=float),
                                 np.full((6, 8), -1, dtype=np.int32),
                                 np.full((6, 8), 4294967296, dtype=np.uint64)])
def test_invalid_masks_are_not_approximated(value):
    with pytest.raises(ValueError, match="invalid_label_array"):
        measure_regions_area({"actin": arrays()[0]}, value, specification())


def test_source_limit_and_channel_identity_not_relaxed_for_area():
    with pytest.raises(ValueError, match="region_plane_limit_exceeded"):
        measure_regions_area({"actin": np.zeros((1, 4097), dtype=np.uint8)},
                             np.zeros((1, 4097), dtype=np.uint32), specification())
    with pytest.raises(ValueError, match="region_channel_or_background_mapping_mismatch"):
        measure_regions_area({"gfp": arrays()[0]}, arrays()[1], specification())
    base = specification().model_dump()
    with pytest.raises(ValidationError, match="duplicate_region_channel_ids"):
        RegionMeasurementSpecV2.model_validate({**base, "channels": (base["channels"][0], base["channels"][0])})
    with pytest.raises(ValidationError, match="unknown_defining_channel"):
        RegionMeasurementSpecV2.model_validate({**base, "region_set": {**base["region_set"], "defining_channel_id": "gfp"}})
    with pytest.raises(ValidationError):
        RegionMeasurementSpecV2.model_validate({**base, "backgrounds": ()})


@pytest.mark.parametrize("limit", [10, 256])
def test_confirmed_acquisition_limits_still_must_match_source_even_without_saturation_calculation(limit):
    raw, labels = arrays()
    channel = ChannelSpec(channel_id="actin", label="Actin", identity_confirmed=True,
                          acquisition_saturation_value=limit, acquisition_saturation_confirmed=True)
    with pytest.raises(ValueError, match="acquisition_limit_inconsistent_with_source"):
        measure_regions_area({"actin": raw}, labels, specification(channels=(channel,)))


def test_representable_pixel_area_cannot_produce_infinite_region_area():
    # Pixel calibration is finite, but the six-pixel region overflows float64.
    calibration = Calibration2D(pixel_size_x_um=1e308, pixel_size_y_um=1., confirmed=True)
    with pytest.raises(ValueError, match="calibrated_region_area_unrepresentable"):
        measured(calibration=calibration)


def test_v1_dispatch_preserves_exact_serialization_signed_values_and_required_background():
    raw = np.array([[9, 11, 13], [100, 2, 10], [100, 6, 20]], dtype=np.uint8)
    labels = np.array([[0, 0, 0], [0, 7, 7], [0, 7, 19]], dtype=np.uint32)
    background = labels == 0
    background[1:, 0] = False
    base = specification()
    old = RegionMeasurementSpec(field_id=base.field_id, analysis_revision_id=base.analysis_revision_id,
                                region_set=base.region_set, channels=base.channels,
                                backgrounds=(BackgroundSpec(channel_id="actin", roi_revision_id="bg", confirmed=True),))
    expected = measure_regions({"actin": raw}, labels, {"actin": background}, old)
    actual = measure_regions_versioned({"actin": raw}, labels, {"actin": background}, old)
    assert actual.model_dump_json() == expected.model_dump_json()
    assert actual.rows[0].mean_corrected == -5 and actual.rows[0].integrated_corrected == -15
    assert region_table_from_json(actual.model_dump_json()).model_dump_json() == expected.model_dump_json()
    with pytest.raises(ValueError, match="region_channel_or_background_mapping_mismatch"):
        measure_regions_versioned({"actin": raw}, labels, {}, old)


@pytest.mark.parametrize("field", ["mean", "median", "integrated", "mean_corrected", "median_corrected",
                                   "integrated_corrected", "storage_limit_fraction", "acquisition_saturation_fraction"])
@pytest.mark.parametrize("value", [0, False])
def test_area_table_refuses_fabricated_zero_signals(field, value):
    data = measured().model_dump(mode="json")
    data["rows"][0][field] = value
    with pytest.raises(ValidationError):
        region_table_from_json(json.dumps(data))


@pytest.mark.parametrize("field", ["mean", "intensity_missing_reason", "storage_limit_missing_reason",
                                   "acquisition_saturation_missing_reason", "measurement", "protocol_version"])
def test_measurement_mode_and_null_reasons_are_explicit_not_defaulted_on_reload(field):
    data = measured().model_dump(mode="json")
    target = data if field in ("measurement", "protocol_version") else data["rows"][0]
    target.pop(field)
    with pytest.raises(ValidationError):
        region_table_from_json(json.dumps(data))


@pytest.mark.parametrize("field,value", [("area_px", True), ("area_px", 0), ("area_px", 49),
                                         ("region_id", 0), ("field_id", "other"),
                                         ("mask_revision_id", "old"), ("channel_id", "missing"),
                                         ("area_um2", 1.0), ("area_missing_reason", None)])
def test_forged_row_cannot_pass_saved_table_validation(field, value):
    data = measured().model_dump(mode="json")
    data["rows"][0][field] = value
    with pytest.raises(ValidationError):
        region_table_from_json(json.dumps(data))


def test_duplicate_rows_status_and_calibration_are_checked_at_reload():
    table = measured(calibration=Calibration2D(pixel_size_x_um=.2, pixel_size_y_um=.3, confirmed=True))
    for change in ({"rows": [*table.model_dump(mode="json")["rows"], table.model_dump(mode="json")["rows"][0]]},
                   {"status": "no_regions"}, {"shape_yx": [2, 3]},
                   {"calibration": {"pixel_size_x_um": 1., "pixel_size_y_um": 1., "confirmed": True}}):
        with pytest.raises(ValidationError):
            region_table_from_json(json.dumps({**table.model_dump(mode="json"), **change}))
    forged = table.model_copy(update={"status": "no_regions"})
    with pytest.raises(ValidationError):
        RegionMeasurementTableV2.model_validate(forged)


def test_all_channels_cover_identical_geometry_and_storage_provenance():
    raw, labels = arrays()
    channels = (specification().channels[0], ChannelSpec(channel_id="dna", label="DNA", identity_confirmed=True))
    table = measure_regions_area({"actin": raw, "dna": raw}, labels, specification(channels=channels))
    original = table.model_dump(mode="json")
    missing = json.loads(json.dumps(original))
    missing["rows"].pop()
    wrong_area = json.loads(json.dumps(original))
    wrong_area["rows"][1]["area_px"] += 1
    wrong_storage = json.loads(json.dumps(original))
    wrong_storage["channel_provenance"][0]["storage_maximum"] = 65535
    for invalid in (missing, wrong_area, wrong_storage):
        with pytest.raises(ValidationError):
            region_table_from_json(json.dumps(invalid))


def test_supplied_background_provenance_cannot_be_hidden_in_area_table():
    data = measured().model_dump(mode="json")
    data["channel_provenance"][0]["background"]["median"] = 0
    with pytest.raises(ValidationError):
        region_table_from_json(json.dumps(data))
