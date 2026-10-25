"""Synthetic (合成) adapter edge cases use numerical records only (no generated images).

These deliberately tiny tables test zero versus missing, exclusion precedence and
serialization, not detector settings, shape accuracy or biological decisions.
Obtaining all exact invalid/absent states from real acquisitions is impractical.
The rendering/measurement test below separately uses registered BBBC039 pixels.
"""
import copy
import hashlib
import json

import pytest
from cytellect_analysis.compartment_observations import describe_compartment_summary
from cytellect_analysis.descriptive import describe_regions
from cytellect_analysis.descriptive_contracts import parse_descriptive_request
from cytellect_analysis.field_summary_source import describe_field_summary
from cytellect_analysis.region_exports import _recompute_statistics
from cytellect_analysis.regions import ChannelSpec
from pydantic import ValidationError


def numerical_records(compartment=False, calibrated=True):
    channel = ChannelSpec(channel_id="dna", label="DNA", stain="Hoechst", identity_confirmed=True).model_dump(mode="json")
    calibration = {"pixel_size_x_um": 0.5, "pixel_size_y_um": 0.25, "confirmed": True} if calibrated else None
    recipe = {"id":"region-2d", "version":"1.0.0", "region_set_id":"regions", "label":"Numerical records",
              "source":"manual", "defining_channel_id":None}
    if compartment:
        recipe.update(source="fiji_nuclear_compartment", version="1.4.0", compartment="nucleoplasm",
                      nuclear_revision_id="n", nucleolar_revision_id="nl", nuclear_channel_id="dna", defining_channel_id="dna")
    table = {"protocol_version":"1.0.0", "status":"measured", "field_id":"f", "analysis_revision_id":"r",
             "region_set":{"region_set_id":"regions", "label":"Numerical records", "mask_revision_id":"m",
                           "source":"manual", "defining_channel_id":None},
             "shape_yx":[10, 10], "mask_sha256":"0"*64, "hash_format":"cytellect-array-v1", "calibration":calibration,
             "channel_provenance":[{"channel":channel, "dtype":"uint16", "pixel_sha256":"1"*64,
                 "background_mask_sha256":"2"*64, "background_revision_id":"bg", "background_pixel_count":1,
                 "background_median":1.0, "storage_maximum":65535}],
             "rows":[{"field_id":"f", "analysis_revision_id":"r", "region_set_id":"regions", "mask_revision_id":"m",
                 "region_id":1, "channel_id":"dna", "area_px":1, "area_um2":0.125 if calibrated else None,
                 "area_missing_reason":None if calibrated else "calibration_unknown", "mean":1.0, "median":1.0,
                 "integrated":1.0, "mean_corrected":0.0, "median_corrected":0.0, "integrated_corrected":0.0,
                 "storage_limit_fraction":0.0, "acquisition_saturation_fraction":None,
                 "acquisition_saturation_missing_reason":"acquisition_limit_unknown", "touches_border":True}]}
    report = {"analysis_kind":"region-2d", "revision_id":"r", "recipe":recipe, "field_tables":{"f":table},
              "field_failures":[], "excluded_failed_fields":[], "exclusions":[]}
    snapshot = {"f":{"metadata":{}, "image_info":{"shape":[10,10], "channels":[channel], "calibration":calibration}}}
    return report, snapshot


def request(metric, compartment=False, **extra):
    return {"mode":"descriptive", "selection":{"source":"compartment-summary" if compartment else "field-summary",
            "version":"1.1.0" if compartment else "1.0.0", "region_set_id":"regions", "metric":metric}, **extra}


def summary_records():
    rows = [{"nucleus_id":1, "nucleus_area_px":3, "nucleolar_area_px":2, "nucleoplasm_area_px":1,
             "nucleolar_count":1, "nucleolar_area_fraction":2/3, "nucleoplasm_mean":1.0, "nucleolar_mean":1.0,
             "log2_nucleoplasm_over_nucleolus":0.0, "missing_reason":None, "values":"raw", "background":None},
            {"nucleus_id":2, "nucleus_area_px":1, "nucleolar_area_px":0, "nucleoplasm_area_px":0,
             "nucleolar_count":0, "nucleolar_area_fraction":0.0, "nucleoplasm_mean":None, "nucleolar_mean":None,
             "log2_nucleoplasm_over_nucleolus":None, "missing_reason":"no_nucleolus", "values":"raw", "background":None}]
    return {"f":{"nucleolar_revision":{"revision_id":"nl"}, "channels":{"dna":{"protocol":"compartment-summary/1.0.0", "rows":rows}}}}


@pytest.mark.parametrize("metric, expected", [("nucleus_count",1), ("nucleus_density_per_mm2",80000.0)])
def test_field_value_and_replay_with_no_independence_claim(metric, expected):
    report, snapshot = numerical_records()
    value = describe_field_summary(report, snapshot, request(metric))
    assert [row["value"] for row in value["plot_data"]] == [expected]
    assert value["observation_kind"] == "fields"
    assert value["field_summary"][0]["selected_rows"] == 1
    assert value["counts"]["experimental_units"] is None
    assert value["source_fields"][0]["field_summary"]["border_count"] == 1
    config = {"field_snapshot":snapshot, "review_record":{"confirmed_at":1.0}, "exclusions":[]}
    value["revision_id"] = "r"
    assert _recompute_statistics(report, config, value) == value


def test_zero_count_is_a_measured_field_not_a_missing_field():
    report, snapshot = numerical_records()
    report["field_tables"]["f"].update(rows=[], status="no_regions")
    value = describe_field_summary(report, snapshot, request("nucleus_count"))
    assert value["plot_data"][0]["value"] == 0
    assert value["selection"]["missing_metric_selected"] == 0


def test_exclusion_and_uncalibrated_density_ledger():
    report, snapshot = numerical_records()
    # Keep a second, calibrated observation so the existing all-missing guard is not bypassed.
    table = copy.deepcopy(report["field_tables"]["f"])
    table["field_id"] = "g"
    for row in table["rows"]:
        row["field_id"] = "g"
    report["field_tables"]["g"] = table
    snapshot["g"] = copy.deepcopy(snapshot["f"])
    table["calibration"] = snapshot["g"]["image_info"]["calibration"] = None
    table["rows"][0].update(area_um2=None, area_missing_reason="calibration_unknown")
    value = describe_field_summary(report, snapshot, request("nucleus_density_per_mm2"))
    assert len(value["plot_data"]) == 1
    assert value["selection"]["missing_metric_selected"] == 1
    assert value["missingness"][0]["field_id"] == "g"
    report["exclusions"] = [{"field_id":"g", "region_id":None, "reason":"explicit exclusion"}]
    value = describe_field_summary(report, snapshot, request("nucleus_count"))
    assert value["selection"]["excluded"] == 1
    assert value["counts"]["observations"] == 1
    report["exclusions"] = [{"field_id":"f", "region_id":1, "reason":"explicit exclusion"}]
    value = describe_field_summary(report, snapshot, request("nucleus_count"))
    assert {row["field_id"]:row["value"] for row in value["plot_data"]} == {"f":0, "g":1}


def test_failed_fields_require_explicit_exclusion_and_never_become_zero():
    report, snapshot = numerical_records()
    snapshot["failed"] = copy.deepcopy(snapshot["f"])
    report["field_failures"] = [{"field_id":"failed", "reason":"failed"}]
    with pytest.raises(ValueError, match="descriptive_unresolved_field_failures"):
        describe_field_summary(report, snapshot, request("nucleus_count"))
    report["field_failures"] = []
    report["excluded_failed_fields"] = [{"field_id":"failed", "reason":"explicit exclusion"}]
    report["exclusions"] = [{"field_id":"failed", "region_id":None, "reason":"explicit exclusion"}]
    value = describe_field_summary(report, snapshot, request("nucleus_count"))
    assert [row["field_id"] for row in value["plot_data"]] == ["f"]
    assert value["excluded_failed_fields"] == report["excluded_failed_fields"]


@pytest.mark.parametrize("metric, expected", [("nucleolar_area_px",2), ("nucleolar_area_um2",0.25), ("nucleolar_eccentricity",0.75)])
def test_compartment_saved_values_and_candidate_free_missingness(metric, expected):
    report, snapshot = numerical_records(compartment=True)
    summaries = summary_records()
    shapes = {"f":{1:{"nucleolar_eccentricity":0.75, "objects":1, "measured_objects":1, "missing_reason":None}}}
    value = describe_compartment_summary(report, snapshot, request(metric, True), summaries, shapes=shapes)
    assert [row["value"] for row in value["plot_data"]] == [expected]
    assert value["observation_kind"] == "nuclei"
    assert value["selection"]["missing_metric_selected"] == 1
    assert value["missingness"][0]["reason"] == "no_nucleolus"
    assert value["spec"]["selection"]["version"] == "1.1.0"
    assert summaries == summary_records()


def test_compartment_shape_and_calibration_guards():
    report, snapshot = numerical_records(compartment=True, calibrated=False)
    with pytest.raises(ValueError, match="compartment_summary_calibration_required"):
        describe_compartment_summary(report, snapshot, request("nucleolar_area_um2", True), summary_records())
    with pytest.raises(ValueError, match="compartment_summary_shape_unavailable"):
        describe_compartment_summary(report, snapshot, request("nucleolar_eccentricity", True), summary_records())


def test_historical_selection_default_and_result_bytes():
    report, snapshot = numerical_records(compartment=True)
    old = request("nucleolar_count", True)
    old["selection"].pop("version")
    parsed = parse_descriptive_request(old)
    assert parsed.selection.version == "1.0.0"
    assert "gfp_gate" not in parsed.model_dump()["selection"]
    implicit = describe_compartment_summary(report, snapshot, old, summary_records())
    old["selection"]["version"] = "1.0.0"
    assert json.dumps(implicit) == json.dumps(describe_compartment_summary(report, snapshot, old, summary_records()))
    assert implicit["descriptive_version"] == "1.0.0"
    # Byte hashes computed using the base e5514b69 implementation, not this adapter.
    def encode(value):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
    assert hashlib.sha256(encode(implicit)).hexdigest() == "c992e9bab69c108345ebf16cbdb2d0848b2f46ed40ff5455f1b2a41103b37ec5"
    for metric in ("nucleolar_area_px", "nucleolar_eccentricity"):
        old["selection"]["metric"] = metric
        with pytest.raises(ValidationError):
            parse_descriptive_request(old)
    region = {"mode":"descriptive", "selection":{"source":"region", "region_set_id":"regions", "metric":"area_px"}}
    assert hashlib.sha256(encode(describe_regions(report, snapshot, region))).hexdigest() == "947d76b0f29fda722760b8de9a2503b8415b8b974c8b85733486f071f5a78a9f"

