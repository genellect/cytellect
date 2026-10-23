"""Statistics and Methods accept saved automatic-background protocol 4.0.0 values unchanged."""
import copy
import io
import json
import zipfile

import numpy as np
import pytest
from cytellect_analysis.descriptive import describe_regions
from cytellect_analysis.descriptive_figures import descriptive_methods
from cytellect_analysis.region_exports import replay_region_bundle
from cytellect_analysis.region_measurement_v2 import RegionMeasurementSpecV4, measure_regions_versioned
from cytellect_analysis.region_policy import AutomaticBackgroundPolicy
from cytellect_analysis.regions import ChannelSpec, RegionSetSpec
from cytellect_analysis.statistical_methods import CURRENT_METHODS_TEMPLATE
from cytellect_api.db import jobs, revisions
from cytellect_worker.main import process_one
from test_api_worker import HEADERS, authenticated
from test_common_statistics_api import common_request
from test_descriptive import request
from test_region_api import tiff_bytes
from test_region_comparison_api import comparison_request

POLICY = {"version": "1.2.0", "mode": "automatic_background"}


def automatic_units(client, app, settings):
    """Four fields: a flat background of 10 and one 4 x 4 region at 10 + value."""
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "Arithmetic fixture"}).json()["id"]
    fids = []
    for index, value in enumerate([2, 4, 5, 7]):
        pixels = np.full((128, 128), 10, np.uint16)
        pixels[60:64, 60:64] = 10 + value
        labels = np.zeros((128, 128), np.uint32)
        labels[60:64, 60:64] = 1
        specification = {"channels": [{"channel_id": "marker", "label": "Measured marker",
                                         "stain": "Fixture fluorescence", "identity_confirmed": True}],
                         "metadata": {"condition": "A" if index < 2 else "B", "sample": f"sample-{index}",
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
    assert app.state.store.one(revisions, id=rid)["state"] == "succeeded"
    report = client.get(f"/v1/revisions/{rid}/region-measurements").json()
    assert report["protocol_version"] == "4.0.0"
    for fid, value in zip(fids, [2, 4, 5, 7], strict=True):
        table = report["field_tables"][fid]
        assert table["channel_provenance"][0]["background"]["background_median"] == 10.0
        assert table["rows"][0]["mean_corrected"] == value
    return wid, rid, fids


def finished(client, app, settings, response, path):
    assert response.status_code == 202, response.text
    jid = response.json()["job_id"]
    process_one(app.state.store, settings)
    job = client.get(f"/v1/jobs/{jid}").json()
    assert job["state"] == "succeeded", job.get("error")
    record = app.state.store.one(jobs, id=jid)
    methods = app.state.store.safe_path(record["result_dir"], "methods.md")
    value = client.get(f"/v1/jobs/{jid}/{path}")
    assert value.status_code == 200, value.text
    return value.json(), methods.read_text(encoding="utf-8") if methods.is_file() else None


@pytest.mark.parametrize("metric", ["mean_corrected", "mean"])
def test_automatic_background_descriptive_distribution(tmp_path, metric):
    client, app, settings = authenticated(tmp_path)
    _, rid, _ = automatic_units(client, app, settings)
    body = {"mode": "descriptive", "selection": {"source": "region", "region_set_id": "objects",
                                                   "channel_id": "marker", "metric": metric}}
    assert client.post(f"/v1/revisions/{rid}/review", headers=HEADERS, json={}).status_code == 200
    reviewed, text = finished(client, app, settings,
                              client.post(f"/v1/revisions/{rid}/descriptive", headers=HEADERS, json=body), "result")
    expected = [2, 4, 5, 7] if metric == "mean_corrected" else [12, 14, 15, 17]
    assert sorted(row["value"] for row in reviewed["plot_data"]) == expected
    assert "protocol 4.0.0" in text and "cytellect-automatic-background 1.0.0" in text
    assert "not a human-confirmed" in text and "user-confirmed" not in text
    if metric == "mean_corrected":
        assert "b is the median of the automatic background candidate" in text
    else:
        assert "selected raw outcome does not subtract background" in text
    client.close()
    app.state.store.engine.dispose()


@pytest.mark.parametrize("association", [False, True])
def test_automatic_background_common_statistics(tmp_path, association):
    client, app, settings = authenticated(tmp_path)
    _, rid, _ = automatic_units(client, app, settings)
    assert client.post(f"/v1/revisions/{rid}/review", headers=HEADERS, json={}).status_code == 200
    value, _ = finished(client, app, settings, client.post(f"/v1/revisions/{rid}/common-statistics", headers=HEADERS,
                                                            json=common_request(association)), "common-statistics")
    if association:
        assert value["associations"][0]["coefficient"] == pytest.approx(1)
    else:
        assert value["comparisons"][0]["p_holm"] == pytest.approx(1 / 3)
    client.close()
    app.state.store.engine.dispose()


def test_automatic_background_welch_comparison_methods(tmp_path):
    client, app, settings = authenticated(tmp_path)
    _, rid, _ = automatic_units(client, app, settings)
    assert client.post(f"/v1/revisions/{rid}/review", headers=HEADERS, json={}).status_code == 200
    value, text = finished(client, app, settings, client.post(f"/v1/revisions/{rid}/region-comparisons", headers=HEADERS,
                                                               json=comparison_request()), "region-comparison")
    assert value["comparisons"][0]["estimate"] == pytest.approx(-3)
    assert "protocol 4.0.0" in text and "automatic background candidate" in text
    body = {"mode": "descriptive", "selection": {"source": "region", "region_set_id": "objects",
                                                   "channel_id": "marker", "metric": "mean_corrected"}}
    finished(client, app, settings, client.post(f"/v1/revisions/{rid}/descriptive", headers=HEADERS, json=body), "result")
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
    assert verification["matched_saved_measurements"] and verification["matched_saved_comparisons"]
    assert verification["matched_saved_descriptions"]
    client.close()
    app.state.store.engine.dispose()


def automatic_report(fields=("f1", "f2"), confluent=("f2",), additional_exclusion=False):
    """Analysis-level 4.0.0 source; a confluent field has no automatic background."""
    channel = ChannelSpec(channel_id="actin", label="Actin", stain="phalloidin", identity_confirmed=True)
    report = {"revision_id": "analysis_1", "protocol_version": "4.0.0", "measurement": POLICY, "field_tables": {},
              "field_failures": [], "excluded_failed_fields": [], "exclusions": []}
    snapshots = {}
    for fid in fields:
        image = np.full((128, 128), 10, np.uint8)
        image[60:64, 60:64] = 16
        labels = np.zeros(image.shape, np.uint32)
        if fid in confluent:
            labels[:] = 1
            labels[0:2, 0:2] = 0
        else:
            labels[60:64, 60:64] = 1
        extra = np.zeros(image.shape, np.uint8) if additional_exclusion else None
        table = measure_regions_versioned({"actin": image}, labels, {}, RegionMeasurementSpecV4(
            measurement=AutomaticBackgroundPolicy.model_validate(POLICY), field_id=fid, analysis_revision_id="analysis_1",
            region_set=RegionSetSpec(region_set_id="regions", label="Manual regions", mask_revision_id="mask_1",
                                     source="manual"),
            channels=(channel,)), background_exclusion=extra)
        report["field_tables"][fid] = table.model_dump(mode="json")
        snapshots[fid] = {"metadata": {"condition": None},
                          "image_info": {"channels": [channel.model_dump(mode="json")], "shape": [128, 128],
                                         "calibration": None}}
    return report, snapshots


def describe(metric="mean_corrected", **changes):
    report, snapshots = automatic_report(**changes)
    return describe_regions(report, snapshots, request(metric=metric))


def test_methods_describe_saved_values_and_missing_backgrounds_without_changing_them():
    result = describe()
    values = {row["field_id"]: row["value"] for row in result["plot_data"]}
    assert values["f1"] == 6.0
    assert result["source_fields"][1]["channel_provenance"][0]["background"]["reason"] == (
        "automatic_background_insufficient_tiles")
    before = copy.deepcopy(result)
    text = descriptive_methods(result, methods_template=CURRENT_METHODS_TEMPLATE)
    assert result == before
    assert "Measurement protocol 4.0.0 (policy 1.2.0, automatic_background)" in text
    assert "not a human-confirmed background ROI" in text and "user-confirmed" not in text
    assert "Euclidean distance of 8 px" in text and "median + 3 × 1.4826 × max(MAD, 1)" in text
    assert "32 × 32 px tiles" in text and "at least 90% unexcluded" in text
    assert "At least 4 retained tiles with centres in at least 3 image quadrants" in text
    assert "established in 1 of 2 fields" in text and "automatic_background_insufficient_tiles" in text
    assert "source nuclear revision" not in text and "corrected integral" not in text
    integrated = descriptive_methods(describe("integrated_corrected"), methods_template=CURRENT_METHODS_TEMPLATE)
    assert "ΣI − |R|b" in integrated
    raw = descriptive_methods(describe("mean"), methods_template=CURRENT_METHODS_TEMPLATE)
    assert "does not use these automatic background corrections" in raw and "Euclidean" not in raw
    nuclei = descriptive_methods(describe(additional_exclusion=True), methods_template=CURRENT_METHODS_TEMPLATE)
    assert "every nucleus of the pinned source nuclear revision, including excluded nuclei" in nuclei
    # Historical dispatch (no saved template) never borrows the area-only or confirmed-ROI prose.
    assert descriptive_methods(result) == text


@pytest.mark.parametrize("tamper", ["confirmed", "constants", "algorithm", "protocol", "policy", "mixed"])
def test_inconsistent_automatic_background_sources_are_refused(tamper):
    result = describe()
    field = result["source_fields"][0]
    background = field["channel_provenance"][0]["background"]
    if tamper == "confirmed":
        background["confirmed"] = True
    elif tamper == "constants":
        background["constants"]["tile_size_px"] = 16
    elif tamper == "algorithm":
        background["algorithm_version"] = "2.0.0"
    elif tamper == "protocol":
        field["measurement_protocol"] = "3.0.0"
    elif tamper == "policy":
        field["measurement"] = {"version": "1.1.0", "mode": "raw_intensity"}
    else:
        result["source_fields"][1].update(measurement_protocol="3.0.0",
                                          measurement={"version": "1.1.0", "mode": "raw_intensity"})
    with pytest.raises(ValueError, match="statistical_methods_source_invalid"):
        descriptive_methods(result, methods_template=CURRENT_METHODS_TEMPLATE)
