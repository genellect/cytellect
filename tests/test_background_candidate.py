"""Automatic background candidate 1.0.0 and measurement protocol 4.0.0 on synthetic planes only."""
import json

import numpy as np
import pytest
from cytellect_analysis.background_candidate import CONSTANTS, automatic_background
from cytellect_analysis.region_contracts import RegionAnalysisRequest, region_report_from_json
from cytellect_analysis.region_measurement_v2 import (
    RegionMeasurementSpecV3,
    RegionMeasurementSpecV4,
    measure_regions_versioned,
    region_table_from_json,
    require_region_metric,
)
from cytellect_analysis.region_policy import (
    AutomaticBackgroundPolicy,
    RawIntensityPolicy,
    RegionMeasurementPolicy,
    measurement_protocol,
)
from cytellect_analysis.regions import ObservedChannelSpec, RegionSetSpec
from pydantic import ValidationError

POLICY = AutomaticBackgroundPolicy(version="1.2.0", mode="automatic_background")
RECIPE = {"version": "1.2.0", "region_set_id": "nuclei", "label": "Nuclei", "source": "stardist_nuclear",
          "defining_channel_id": "ch1", "nuclear_role_source": "recorded_stain"}


def plane(shape=(256, 256), offset=100):
    """Deterministic symmetric integer noise: offset-2 .. offset+2, median exactly offset."""
    y, x = np.indices(shape)
    return (offset + (y * 7 + x * 3) % 5 - 2).astype(np.uint16)


def disk(shape, cy, cx, radius):
    y, x = np.indices(shape)
    return (y - cy) ** 2 + (x - cx) ** 2 <= radius * radius


def nuclei_field(offset=100):
    image = plane(offset=offset)
    labels = np.zeros(image.shape, np.uint32)
    for index, (cy, cx) in enumerate([(40, 40), (40, 200), (200, 60), (180, 190), (128, 128)], 1):
        mask = disk(image.shape, cy, cx, 12)
        labels[mask] = index
        image[mask] += 900 + 10 * index
    # A dim labelled region yields a native negative correction that must stay signed.
    dim = disk(image.shape, 220, 220, 6)
    labels[dim] = 6
    image[dim] = offset - 40
    # An unlabelled bright object is excluded by the bright-pixel rule.
    image[disk(image.shape, 100, 30, 6)] = 3000
    return image, labels


def spec(*channels):
    return RegionMeasurementSpecV4(
        measurement=POLICY, field_id="f1", analysis_revision_id="r1",
        region_set=RegionSetSpec(region_set_id="nuclei", label="Nuclei", mask_revision_id="m1", source="imported"),
        channels=tuple(ObservedChannelSpec(channel_id=cid, label=cid.upper(), identity_source="unresolved")
                       for cid in channels),
    )


def test_known_offset_is_recovered_exactly_and_corrections_use_original_pixels():
    image, labels = nuclei_field()
    original, original_labels = image.copy(), labels.copy()
    mask, record = automatic_background(image, labels)
    assert mask is not None and record["reason"] is None
    assert float(np.median(image[mask])) == 100.0
    assert not np.any(mask & (labels > 0))
    assert not mask[disk(image.shape, 100, 30, 6)].any()
    assert record["quadrants"] == [0, 1, 2, 3] and record["retained_tile_count"] >= 4
    assert record["constants"] == CONSTANTS

    table = measure_regions_versioned({"ch1": image}, labels, {}, spec("ch1"))
    assert table.protocol_version == "4.0.0" and table.measurement == POLICY
    background = table.channel_provenance[0].background
    assert background.status == "established" and background.background_median == 100.0
    assert background.background_source == "automatic_candidate" and background.confirmed is False
    assert background.background_pixel_count == int(mask.sum())
    for row in table.rows:
        values = image[labels == row.region_id].astype(np.float64)
        assert row.mean == values.mean() and row.integrated == values.sum()
        assert row.mean_corrected == pytest.approx(values.mean() - 100.0, abs=1e-12)
        assert row.median_corrected == float(np.median(values)) - 100.0
        assert row.integrated_corrected == pytest.approx(values.sum() - values.size * 100.0, abs=1e-9)
        assert row.correction_missing_reason is None
    dim = next(row for row in table.rows if row.region_id == 6)
    assert dim.mean_corrected == -40.0 and dim.integrated_corrected == -40.0 * dim.area_px
    np.testing.assert_array_equal(image, original)
    np.testing.assert_array_equal(labels, original_labels)
    assert region_table_from_json(table.model_dump_json()) == table


def test_confluent_field_leaves_corrections_missing_without_failing():
    image = plane()
    labels = np.zeros(image.shape, np.uint32)
    labels[8:-8, 8:-8] = 1
    mask, record = automatic_background(image, labels)
    assert mask is None and record["reason"] == "automatic_background_insufficient_tiles"
    table = measure_regions_versioned({"ch1": image}, labels, {}, spec("ch1"))
    row = table.rows[0]
    assert row.mean == float(image[labels == 1].mean())
    assert (row.mean_corrected, row.median_corrected, row.integrated_corrected) == (None, None, None)
    assert row.correction_missing_reason == "automatic_background_insufficient_tiles"
    background = table.channel_provenance[0].background
    assert background.status == "not_established" and background.background_median is None
    assert background.confirmed is False


def test_quadrant_rule_requires_three_quadrants():
    image = plane()
    labels = np.zeros(image.shape, np.uint32)
    labels[:, 128:] = 1
    mask, record = automatic_background(image, labels)
    assert mask is None and record["reason"] == "automatic_background_insufficient_coverage"
    assert record["retained_tile_count"] >= 4 and record["quadrants"] == [0, 2]
    # Fewer than four full tiles never establishes a background.
    small = plane((63, 63))
    mask, record = automatic_background(small, np.zeros(small.shape, np.uint8))
    assert mask is None and record["reason"] == "automatic_background_insufficient_tiles"


def test_channels_fail_independently():
    image, labels = nuclei_field()
    flat = np.full(image.shape, 7, np.uint8)
    flat[:, 128:] = 200  # every tile in the right half is a shifted, rejected median
    flat[labels > 0] = 50
    table = measure_regions_versioned({"ch1": image, "ch2": flat}, labels, {}, spec("ch1", "ch2"))
    by_channel = {item.channel.channel_id: item.background for item in table.channel_provenance}
    assert by_channel["ch1"].status == "established"
    assert by_channel["ch2"].reason == "automatic_background_insufficient_coverage"
    assert all(row.mean_corrected is None for row in table.rows if row.channel_id == "ch2")
    assert all(row.mean_corrected is not None for row in table.rows if row.channel_id == "ch1")


def test_uneven_illumination_gives_one_global_median_and_records_its_spread():
    # Documented behaviour: a linear gradient is not removed. No tile is rejected,
    # b is the median of all retained pixels and the retained tile-median range
    # records the unevenness for review.
    y, x = np.indices((256, 256))
    image = (100 + x // 4).astype(np.uint16)
    mask, record = automatic_background(image, np.zeros(image.shape, np.uint8))
    assert mask is not None and mask.all()
    assert record["median_rejected_tile_count"] == 0 and record["dispersion_rejected_tile_count"] == 0
    assert float(np.median(image[mask])) == 131.5
    assert (record["retained_tile_median_min"], record["retained_tile_median_max"]) == (103.5, 159.5)


def test_diffuse_blob_is_excluded_and_rejected():
    y, x = np.indices((256, 256))
    blob = plane().astype(np.float64) + 400 * np.exp(-((y - 64) ** 2 + (x - 64) ** 2) / (2 * 25 ** 2))
    image = np.round(blob).astype(np.uint16)
    mask, record = automatic_background(image, np.zeros(image.shape, np.uint8))
    assert mask is not None and float(np.median(image[mask])) == 100.0
    assert record["median_rejected_tile_count"] > 0 and not mask[64, 64]
    assert record["quadrants"] == [1, 2, 3]


def test_field_wide_diffuse_signal_is_a_documented_limitation():
    # Diffuse signal covering most of the field cannot be distinguished from
    # background; the candidate reports that level, which is why it is never
    # recorded as human-confirmed.
    image = plane()
    image[:, 52:] += 200
    mask, record = automatic_background(image, np.zeros(image.shape, np.uint8))
    assert mask is not None and float(np.median(image[mask])) == 300.0
    assert record["median_rejected_tile_count"] > 0


def test_low_quantized_signal_is_not_excluded_by_zero_mad():
    y, x = np.indices((256, 256))
    image = (((x + 2 * y) % 7) == 0).astype(np.uint8)
    labels = np.zeros(image.shape, np.uint32)
    labels[disk(image.shape, 128, 128, 10)] = 1
    image[labels > 0] = 2
    table = measure_regions_versioned({"ch1": image}, labels, {}, spec("ch1"))
    assert table.channel_provenance[0].background.background_median == 0.0
    assert table.rows[0].mean_corrected == 2.0


def test_deterministic_and_input_validation():
    image, labels = nuclei_field()
    first_mask, first = automatic_background(image, labels)
    second_mask, second = automatic_background(image.copy(), labels.copy())
    assert first == second
    np.testing.assert_array_equal(first_mask, second_mask)
    one = measure_regions_versioned({"ch1": image}, labels, {}, spec("ch1"))
    two = measure_regions_versioned({"ch1": image}, labels, {}, spec("ch1"))
    assert one.model_dump_json() == two.model_dump_json()
    with pytest.raises(ValueError, match="protocol_unknown"):
        automatic_background(image, labels, protocol="2.0.0")
    with pytest.raises(ValueError, match="region_source_shape_or_dtype_invalid"):
        automatic_background(image.astype(np.float32), labels)
    with pytest.raises(ValueError, match="region_background_exclusion_invalid"):
        automatic_background(image, labels[:10])


def test_additional_exclusion_is_recorded_and_used():
    image, labels = nuclei_field()
    extra = np.zeros(labels.shape, np.uint32)
    extra[:, :100] = 1
    table = measure_regions_versioned({"ch1": image}, labels, {}, spec("ch1"), background_exclusion=extra)
    background = table.channel_provenance[0].background
    assert background.additional_exclusion is True
    assert background.quadrants == (1, 3) and background.reason == "automatic_background_insufficient_coverage"
    raw = RegionMeasurementSpecV3(**{**spec("ch1").model_dump(), "protocol_version": "3.0.0",
                                     "measurement": RawIntensityPolicy(version="1.1.0", mode="raw_intensity")})
    with pytest.raises(ValueError, match="region_background_exclusion_invalid"):
        measure_regions_versioned({"ch1": image}, labels, {}, raw, background_exclusion=extra)


def test_confirmed_roi_and_automatic_candidate_are_never_mixed():
    image, labels = nuclei_field()
    with pytest.raises(ValueError, match="region_automatic_background_roi_conflict"):
        measure_regions_versioned({"ch1": image}, labels, {"ch1": labels == 0}, spec("ch1"))
    roi = {"polygon": [[0, 0], [10, 0], [10, 10]], "confirmed": True}
    with pytest.raises(ValidationError, match="region_automatic_background_roi_conflict"):
        RegionAnalysisRequest.model_validate({"recipe": RECIPE, "measurement": POLICY.model_dump(),
                                              "backgrounds": {"f1": {"ch1": roi}}})
    with pytest.raises(ValidationError, match="region_area_only_backgrounds_forbidden"):
        RegionAnalysisRequest.model_validate({"recipe": RECIPE, "measurement": {"version": "1.0.0", "mode": "area_only"},
                                              "backgrounds": {"f1": {"ch1": roi}}})


def test_recorded_table_rejects_confirmation_or_correction_tampering():
    image, labels = nuclei_field()
    payload = json.loads(measure_regions_versioned({"ch1": image}, labels, {}, spec("ch1")).model_dump_json())
    confirmed = json.loads(json.dumps(payload))
    confirmed["channel_provenance"][0]["background"]["confirmed"] = True
    with pytest.raises(ValueError):
        region_table_from_json(json.dumps(confirmed))
    shifted = json.loads(json.dumps(payload))
    shifted["rows"][0]["mean_corrected"] += 1
    with pytest.raises(ValueError):
        region_table_from_json(json.dumps(shifted))
    constants = json.loads(json.dumps(payload))
    constants["channel_provenance"][0]["background"]["constants"]["tile_size_px"] = 16
    with pytest.raises(ValueError):
        region_table_from_json(json.dumps(constants))
    relabelled = json.loads(json.dumps(payload))
    relabelled["protocol_version"] = "3.0.0"
    with pytest.raises(ValueError):
        region_table_from_json(json.dumps(relabelled))


def test_existing_policy_versions_keep_their_protocols_and_metrics():
    assert measurement_protocol(None) == "1.0.0"
    assert measurement_protocol(RegionMeasurementPolicy(version="1.0.0", mode="area_only")) == "2.0.0"
    assert measurement_protocol(RawIntensityPolicy(version="1.1.0", mode="raw_intensity")) == "3.0.0"
    assert measurement_protocol(POLICY) == "4.0.0"
    with pytest.raises(ValueError, match="region_metric_not_measured"):
        require_region_metric(RawIntensityPolicy(version="1.1.0", mode="raw_intensity"), "mean_corrected")
    require_region_metric(POLICY, "mean_corrected")
    with pytest.raises(ValidationError):
        AutomaticBackgroundPolicy(version="1.1.0", mode="automatic_background")


def test_unversioned_downstream_methods_refuse_protocol_4():
    from cytellect_analysis.descriptive import region_report_measurement_policy
    from cytellect_analysis.region_exports import _request

    with pytest.raises(ValueError, match="region_measurement_protocol_mismatch"):
        region_report_measurement_policy({"protocol_version": "4.0.0", "measurement": POLICY.model_dump()})
    with pytest.raises(ValueError, match="region_export_protocol_unsupported"):
        _request({"analysis_kind": "region-2d", "field_ids": ["f1"], "recipe": RECIPE,
                   "measurement": POLICY.model_dump(), "backgrounds": {}, "exclusions": []})


def test_worker_records_automatic_unconfirmed_background(tmp_path, monkeypatch):
    from cytellect_worker.regions import run_region_analysis
    from test_api_worker import HEADERS, authenticated
    from test_region_api import tiff_bytes

    client, app, settings = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "Synthetic fixture"}).json()["id"]
    image, labels = nuclei_field()
    specification = {"version": "1.1.0", "channels": [
        {"channel_id": "ch1", "label": "DAPI", "stain": "DAPI", "identity_source": "filename"}]}
    uploaded = client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS,
                           data={"specification": json.dumps(specification)},
                           files={"ch0": ("synthetic.tif", tiff_bytes(image), "image/tiff")})
    assert uploaded.status_code == 201, uploaded.text
    fid = uploaded.json()["id"]
    monkeypatch.setattr("cytellect_worker.regions.detect_nuclei", lambda *a, **k: (labels, {"engine": "test-fixture"}))
    roi = {"polygon": [[0, 0], [10, 0], [10, 10]], "confirmed": True}
    rejected = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json={
        "field_ids": [fid], "recipe": RECIPE, "measurement": POLICY.model_dump(), "backgrounds": {fid: {"ch1": roi}}})
    assert rejected.status_code == 422
    response = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json={
        "field_ids": [fid], "recipe": RECIPE, "measurement": POLICY.model_dump(), "backgrounds": {}})
    assert response.status_code == 202, response.text
    claimed = app.state.store.claim()
    output = app.state.store.safe_path("results", claimed["id"])
    run_region_analysis(app.state.store, settings, claimed, output)
    assert app.state.store.finish(claimed, app.state.store.relative_path(output))
    measured = client.get(f"/v1/revisions/{response.json()['revision_id']}/region-measurements")
    assert measured.status_code == 200, measured.text
    report = measured.json()
    assert report["protocol_version"] == "4.0.0" and report["field_failures"] == []
    table = report["field_tables"][fid]
    background = table["channel_provenance"][0]["background"]
    assert background["background_source"] == "automatic_candidate" and background["confirmed"] is False
    assert background["background_median"] == 100.0 and background["additional_exclusion"] is False
    row = next(item for item in table["rows"] if item["region_id"] == 6)
    assert row["mean_corrected"] == -40.0
    assert region_report_from_json(json.dumps(report)).protocol_version == "4.0.0"
    assert not list(output.glob("*/background-*.npy"))
    client.close()
    app.state.store.engine.dispose()
