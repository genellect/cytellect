"""Registered public BBBC039 pixels and manual annotations, not generated images.

This checks saved-value plumbing and figure output, not detector accuracy or
nucleolar identity. Calibration is unknown in this registered source.
"""
import json

import numpy as np
import pytest
import tifffile
from cytellect_analysis.descriptive_figures import descriptive_methods, render_descriptive
from cytellect_analysis.descriptive_output import render_descriptive_output
from cytellect_analysis.field_summary_source import describe_field_summary
from cytellect_analysis.region_measurement_v2 import RegionMeasurementSpecV2, measure_regions_versioned
from cytellect_analysis.statistical_methods import CURRENT_METHODS_TEMPLATE
from test_public_bbbc039 import benchmark


@pytest.fixture
def public_field():
    item = benchmark.verify()["images"][0]  # Manifest order fixed before any measurements.
    pixels = tifffile.imread(benchmark.FIXTURE / item["image"]["path"])
    labels = benchmark.decode_ground_truth(benchmark.FIXTURE / item["mask"]["path"])
    spec = RegionMeasurementSpecV2.model_validate({
        "field_id":"public", "analysis_revision_id":"r", "measurement":{"version":"1.0.0", "mode":"area_only"},
        "region_set":{"region_set_id":"nuclei", "label":"BBBC039 annotated nuclei", "source":"imported", "mask_revision_id":"m"},
        "channels":({"channel_id":"dna", "label":"DNA", "stain":"Hoechst", "identity_confirmed":True},)})
    table = measure_regions_versioned({"dna":pixels}, labels, {}, spec).model_dump(mode="json")
    report = {"revision_id":"r", "analysis_kind":"region-2d", "recipe":{"source":"imported"},
              "protocol_version":"2.0.0", "measurement":spec.measurement.model_dump(),
              "field_tables":{"public":table}, "field_failures":[], "excluded_failed_fields":[], "exclusions":[]}
    snapshot = {"public":{"metadata":{}, "image_info":{"shape":list(pixels.shape), "calibration":None,
                "channels":[channel.model_dump(mode="json") for channel in spec.channels]}}}
    return report, snapshot, len(np.unique(labels)) - 1


@pytest.mark.parametrize("paged", [False, True])
@pytest.mark.parametrize("language", ["en", "ja"])
def test_public_nuclear_count_is_one_point_and_exports_methods(public_field, tmp_path, paged, language):
    report, snapshot, count = public_field
    request = {"mode":"descriptive", "selection":{"source":"field-summary", "region_set_id":"nuclei", "metric":"nucleus_count"},
               "plot":{"preset":"nature-double", "language":language}}
    if paged:
        request["figure_policy"] = {"version":"2.0.0", "layout":"field-pages"}
    result = describe_field_summary(report, snapshot, request)
    assert result["plot_data"][0]["value"] == count == len(report["field_tables"]["public"]["rows"])
    assert result["counts"]["observations"] == 1
    render = render_descriptive_output if paged else render_descriptive
    manifest = render(result, tmp_path, methods_template=CURRENT_METHODS_TEMPLATE)
    assert manifest.get("status", "ready") == "ready"
    legend = (tmp_path / "figure-caption.md").read_text(encoding="utf8")
    assert ("1 視野 1 点" if language == "ja" else "One point per field") in legend
    svg = (tmp_path / ("figure-001.svg" if paged else "figure.svg")).read_text(encoding="utf8")
    assert "Field median" not in svg and "視野中央値" not in svg
    assert "One point per field" in (tmp_path / "methods.md").read_text(encoding="utf8")
    assert "one value per field" in descriptive_methods(result)
    assert json.loads((tmp_path / "figure-data.json").read_text(encoding="utf8"))["plot_data"] == result["plot_data"]
