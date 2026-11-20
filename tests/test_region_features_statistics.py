"""Region shape and pixel-signal values (region-features/1.0.0) reach statistics, Methods and the replayable bundle.

Arithmetic fixture (development principles, research data and verification): one rectangular region per field on a
flat background, so the expected solidity, axis ratio, CV and positive-area fraction follow from the pixel layout
alone. Public-image checks of the shape formulas are in tests/test_nuclear_signal_and_shape.py and
scripts/evaluate_shape_minimum_area.py.
"""
import io
import json
import math
import zipfile

import numpy as np
import pytest
from cytellect_analysis.region_exports import replay_region_bundle
from cytellect_analysis.region_features import (
    FEATURE_METRICS,
    SHAPE_METRICS,
    bind,
    field_features,
    selections_of,
)
from cytellect_worker.main import process_one
from test_api_worker import HEADERS, authenticated
from test_automatic_background_statistics import finished
from test_common_statistics_api import common_request
from test_region_api import tiff_bytes

POLICY = {"version": "1.2.0", "mode": "automatic_background"}
# (height, width, left-half value, right-half value) above a background of 10, per field.
FIELDS = [(10, 10, 2, 6), (10, 12, 2, 6), (8, 16, 4, 4), (6, 20, 1, 9)]
CONDITIONS = ["A", "A", "B", "B"]


def rectangle_axis_ratio(height, width):
    # Second moments of a uniform h × w pixel grid: (n² − 1) / 12 along each axis.
    return math.sqrt((max(height, width) ** 2 - 1) / (min(height, width) ** 2 - 1))


def feature_units(client, app, settings):
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "Feature fixture"}).json()["id"]
    fids = []
    for index, (height, width, left, right) in enumerate(FIELDS):
        pixels = np.full((128, 128), 10, np.uint16)
        labels = np.zeros((128, 128), np.uint32)
        top, start = 60, 50
        labels[top:top + height, start:start + width] = 1
        pixels[top:top + height, start:start + width // 2] = 10 + left
        pixels[top:top + height, start + width // 2:start + width] = 10 + right
        specification = {"channels": [{"channel_id": "marker", "label": "Measured marker",
                                         "stain": "Fixture fluorescence", "identity_confirmed": True}],
                         "metadata": {"condition": CONDITIONS[index], "sample": f"sample-{index}",
                                      "experimental_unit": f"culture-{index}", "acquisition_date": "batch-1"}}
        response = client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS,
                               data={"specification": json.dumps(specification)}, files={
                                   "ch0": ("image.tif", tiff_bytes(pixels), "image/tiff"),
                                   "labels": ("labels.tif", tiff_bytes(labels), "image/tiff")})
        assert response.status_code == 201, response.text
        fids.append(response.json()["id"])
    body = {"field_ids": fids, "recipe": {"region_set_id": "objects", "label": "Reviewed regions", "source": "imported"},
            "measurement": POLICY, "backgrounds": {}}
    response = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=body)
    assert response.status_code == 202, response.text
    rid = response.json()["revision_id"]
    process_one(app.state.store, settings)
    assert client.post(f"/v1/revisions/{rid}/review", headers=HEADERS, json={}).status_code == 200
    return rid, fids


def expected(metric, height, width, left, right):
    if metric == "solidity":
        return 1.0
    if metric == "axis_ratio":
        return rectangle_axis_ratio(height, width)
    if metric == "eccentricity":
        return math.sqrt(1 - 1 / rectangle_axis_ratio(height, width) ** 2)
    if metric == "positive_area_fraction":
        return 1.0 if left == right else 0.5
    offset = 0 if metric == "cv_corrected" else 10
    mean = offset + (left + right) / 2
    return abs(right - left) / 2 / mean


def selection(metric):
    return {"source": "region", "region_set_id": "objects", "metric": metric,
            "channel_id": None if metric in SHAPE_METRICS else "marker"}


@pytest.mark.parametrize("metric", FEATURE_METRICS)
def test_feature_metrics_are_described_with_their_definition(tmp_path, metric):
    client, app, settings = authenticated(tmp_path)
    rid, fids = feature_units(client, app, settings)
    value, methods = finished(client, app, settings, client.post(
        f"/v1/revisions/{rid}/descriptive", headers=HEADERS, json={"mode": "descriptive", "selection": selection(metric)}),
        "result")
    by_field = {row["field_id"]: row["value"] for row in value["plot_data"]}
    for fid, field in zip(fids, FIELDS, strict=True):
        if metric == "positive_area_fraction" and field[2] == field[3]:
            # A flat region has no split of its own; Otsu's threshold of one level is not established.
            assert by_field.get(fid) is None
            continue
        assert by_field[fid] == pytest.approx(expected(metric, *field)), fid
    assert value["unit"] == "dimensionless"
    assert all(field["region_features"]["protocol"] == "region-features/1.0.0" for field in value["source_fields"])
    assert "region-features/1.0.0" in methods
    client.close()
    app.state.store.engine.dispose()


def test_shape_comparison_association_export_and_replay(tmp_path):
    client, app, settings = authenticated(tmp_path)
    rid, _ = feature_units(client, app, settings)
    base = common_request()
    shape = {**base, "selection": selection("axis_ratio"),
             "acquisition_review": {**base["acquisition_review"], "spatial_sampling_confirmed": True}}
    value, methods = finished(client, app, settings, client.post(f"/v1/revisions/{rid}/common-statistics",
                                                                  headers=HEADERS, json=shape), "common-statistics")
    units = {row["experimental_unit"]: row["value"] for row in value["unit_summary"]}
    assert sorted(units.values()) == pytest.approx(sorted(rectangle_axis_ratio(h, w) for h, w, *_ in FIELDS))
    assert value["unit"] == "dimensionless" and value["channel"] is None
    association = common_request(association=True)
    pair = {**association, "x_selection": selection("axis_ratio"), "y_selection": selection("cv_corrected")}
    paired, _ = finished(client, app, settings, client.post(f"/v1/revisions/{rid}/common-statistics",
                                                            headers=HEADERS, json=pair), "common-statistics")
    assert paired["x_source"]["metric"] == "axis_ratio" and paired["y_source"]["metric"] == "cv_corrected"
    response = client.post(f"/v1/revisions/{rid}/export?include_raw=true", headers=HEADERS)
    assert response.status_code == 202, response.text
    export = response.json()["job_id"]
    process_one(app.state.store, settings)
    assert client.get(f"/v1/jobs/{export}").json()["state"] == "succeeded"
    archive = client.get(f"/v1/jobs/{export}/files/analysis.zip")
    bundle = tmp_path / "bundle"
    with zipfile.ZipFile(io.BytesIO(archive.content)) as opened:
        opened.extractall(bundle)
    verification = replay_region_bundle(bundle, bundle / "raw", tmp_path / "replay")
    assert verification["matched_saved_measurements"]
    assert verification["matched_saved_comparisons"] is True and verification["matched_saved_associations"] is True
    client.close()
    app.state.store.engine.dispose()


def test_shape_needs_the_minimum_area_and_signal_needs_its_channel():
    labels = np.zeros((40, 40), np.uint32)
    labels[5:13, 5:13] = 1  # 64 px: below the 96 px minimum
    labels[20:31, 20:31] = 2  # 121 px
    labels[0:3, 30:40] = 3  # touches the border
    record = field_features(labels, "solidity")
    assert record["minimum_area_px"] == 96
    assert {rid: value["missing_reason"] for rid, value in record["values"].items()} == {
        1: "below_minimum_area", 2: None, 3: "touches_border"}
    with pytest.raises(ValueError, match="region_features_unavailable"):
        field_features(labels, "cv")
    with pytest.raises(ValueError, match="region_features_unavailable"):
        field_features(labels, "circularity")
    # A corrected CV without an established background keeps that reason for every region.
    image = np.full(labels.shape, 7, np.uint16)
    missing = field_features(labels, "cv_corrected", image=image, background_reason="automatic_background_insufficient_tiles")
    assert {value["missing_reason"] for value in missing["values"].values()} == {"automatic_background_insufficient_tiles"}
    # Values bind to exactly the measured regions and areas.
    assert bind(record, "solidity", {1: 64, 2: 121, 3: 30})[2]["value"] == 1.0
    with pytest.raises(ValueError, match="region_features_mismatch"):
        bind(record, "solidity", {1: 64, 2: 120, 3: 30})
    with pytest.raises(ValueError, match="region_features_mismatch"):
        bind(record, "axis_ratio", {1: 64, 2: 121, 3: 30})


def test_feature_selections_are_found_in_saved_specs():
    spec = {"mode": "region-association", "x_selection": selection("solidity"), "y_selection": selection("mean")}
    assert selections_of(spec) == {("solidity", None)}
    assert selections_of({"selection": selection("cv")}) == {("cv", "marker")}
    assert selections_of({"selection": {"source": "compartment-summary", "metric": "nucleolar_eccentricity"}}) == set()


def test_image_table_shows_the_values_statistics_use(tmp_path):
    client, app, settings = authenticated(tmp_path)
    rid, fids = feature_units(client, app, settings)
    shape = client.get(f"/v1/revisions/{rid}/region-features", headers=HEADERS, params={"field_id": fids[2]})
    assert shape.status_code == 200, shape.text
    row = shape.json()["rows"][0]
    assert shape.json()["minimum_area_px"] == 96 and shape.json()["metrics"] == list(SHAPE_METRICS)
    assert row["values"]["axis_ratio"]["value"] == pytest.approx(rectangle_axis_ratio(8, 16))
    signal = client.get(f"/v1/revisions/{rid}/region-features", headers=HEADERS,
                        params={"field_id": fids[3], "channel_id": "marker"}).json()
    values = signal["rows"][0]["values"]
    assert values["cv_corrected"]["value"] == pytest.approx(expected("cv_corrected", *FIELDS[3]))
    assert values["positive_area_fraction"]["value"] == pytest.approx(0.5)
    assert signal["thresholds"]["positive_area_fraction"]["method"] == "field_otsu"
    described, _ = finished(client, app, settings, client.post(
        f"/v1/revisions/{rid}/descriptive", headers=HEADERS, json={"mode": "descriptive", "selection": selection("cv_corrected")}),
        "result")
    assert {row["field_id"]: row["value"] for row in described["plot_data"]}[fids[3]] == values["cv_corrected"]["value"]
    assert client.get(f"/v1/revisions/{rid}/region-features", headers=HEADERS,
                      params={"field_id": fids[0], "channel_id": "absent"}).status_code == 404
    client.close()
    app.state.store.engine.dispose()
