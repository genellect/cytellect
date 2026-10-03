"""Versioned area requests/reports retain historical JSON and complete outcomes."""
import json

import numpy as np
import pytest
from cytellect_analysis.region_contracts import (
    RegionAnalysisRequest,
    RegionFieldMask,
    RegionImageInfo,
    RegionReport,
    RegionReportV2,
    region_report_from_json,
    region_request_config,
    scientific_specification,
    validate_region_report_policy,
)
from cytellect_analysis.region_measurement_v2 import (
    RegionMeasurementPolicy,
    RegionMeasurementSpecV2,
    measure_regions_versioned,
)
from cytellect_analysis.regions import RegionMeasurementSpec
from pydantic import ValidationError

POLICY = {"version": "1.0.0", "mode": "area_only"}
RECIPE = {"id": "region-2d", "version": "1.0.0", "region_set_id": "reviewed",
          "label": "Cell regions", "source": "imported", "defining_channel_id": None}
FILE = {"sha256": "a" * 64, "bytes": 12}


def request(*, area=True):
    return RegionAnalysisRequest.model_validate({"field_ids": ["f1"], "recipe": RECIPE,
                                                **({"measurement": POLICY} if area else {})})


def info():
    return RegionImageInfo.model_validate({"shape": [3, 4], "channels": [
        {"channel_id": "marker", "label": "実際の染色", "stain": "Phalloidin", "identity_confirmed": True},
    ], "inputs": {"ch0": FILE, "labels": FILE}, "channel_arrays": {"marker": FILE}, "labels_array": FILE})


def report(*, area=True):
    req = request(area=area)
    spec = scientific_specification(field_id="f1", revision_id="rev2", mask_revision_id="mask1",
                                    recipe=req.recipe, image_info=info(), measurement=req.measurement)
    raw = np.arange(12, dtype=np.uint8).reshape(3, 4)
    labels = np.array([[0, 0, 0, 0], [0, 7, 7, 0], [0, 0, 0, 0]], dtype=np.uint32)
    table = measure_regions_versioned({"marker": raw}, labels, {} if area else {"marker": labels == 0}, spec)
    data = dict(revision_id="rev2", recipe=req.recipe, field_tables={"f1": table},
                field_masks={"f1": RegionFieldMask(mask_revision_id="mask1", mask_sha256=table.mask_sha256,
                                                  region_set_id="reviewed", source="imported", shape=[3, 4], file=FILE)},
                field_outcomes={"f1": "measured"}, field_failures=[], excluded_failed_fields=[], exclusions=[])
    return RegionReportV2(**data, measurement=req.measurement) if area else RegionReport(**data)


def test_old_absent_or_explicit_none_policy_has_exact_historical_request_configuration():
    old = {"field_ids": ["f1"], "reuse_revision": None, "plan_resolution": None, "recipe": RECIPE,
           "backgrounds": {}, "exclusions": []}
    for payload in (old, {**old, "measurement": None}):
        result = region_request_config(RegionAnalysisRequest.model_validate(payload))
        # Preserve key order, defaults and nulls, not just semantic equality.
        assert json.dumps(result) == json.dumps(old)
        assert "measurement" not in result
    value = region_request_config(request())
    assert value["measurement"] == POLICY and value["backgrounds"] == {}


def test_v1_spec_serialization_is_unchanged_and_v2_has_no_fake_background():
    req = request(area=False)
    old = scientific_specification(field_id="f1", revision_id="rev2", mask_revision_id="mask1",
                                    recipe=req.recipe, image_info=info())
    assert isinstance(old, RegionMeasurementSpec)
    expected = {"protocol_version": "1.0.0", "field_id": "f1", "analysis_revision_id": "rev2",
                "region_set": {"region_set_id": "reviewed", "label": "Cell regions", "mask_revision_id": "mask1",
                               "source": "imported", "defining_channel_id": None},
                "channels": [{"channel_id": "marker", "label": "実際の染色", "stain": "Phalloidin",
                              "identity_confirmed": True, "acquisition_saturation_value": None,
                              "acquisition_saturation_confirmed": False}],
                "backgrounds": [{"channel_id": "marker", "roi_revision_id": "rev2", "confirmed": True}],
                "calibration": None}
    assert old.model_dump_json() == json.dumps(expected, ensure_ascii=False, separators=(",", ":"))
    new = scientific_specification(field_id="f1", revision_id="rev2", mask_revision_id="mask1",
                                    recipe=req.recipe, image_info=info(),
                                    measurement=RegionMeasurementPolicy.model_validate(POLICY))
    assert isinstance(new, RegionMeasurementSpecV2) and new.region_set == old.region_set
    assert new.channels == old.channels and "backgrounds" not in new.model_dump()


@pytest.mark.parametrize("backgrounds", [{"f1": {}}, {"f1": {"marker": {
    "polygon": [[0, 0], [1, 0], [1, 1]], "confirmed": True}}}])
def test_area_request_cannot_silently_drop_old_backgrounds(backgrounds):
    with pytest.raises(ValidationError, match="region_area_only_backgrounds_forbidden"):
        RegionAnalysisRequest.model_validate({**region_request_config(request()), "backgrounds": backgrounds})


@pytest.mark.parametrize("area", [False, True])
def test_report_roundtrip_is_strict_and_saved_masks_may_precede_analysis_revision(area):
    result = report(area=area)
    repeated = region_report_from_json(result.model_dump_json())
    assert repeated.model_dump_json() == result.model_dump_json()
    assert repeated.field_tables["f1"].region_set.mask_revision_id == "mask1"
    validate_region_report_policy(repeated, region_request_config(request(area=area)))
    assert ("measurement" in repeated.model_dump()) is area


@pytest.mark.parametrize("area,config", [(True, {}), (True, {"measurement": None}),
                                       (False, {"measurement": POLICY}),
                                       (True, {"measurement": {"version": "2.0.0", "mode": "area_only"}}),
                                       (True, {"measurement": {"version": "1.0.0", "mode": "raw"}}),
                                       (True, {"measurement": False})])
def test_report_and_saved_configuration_policy_must_agree(area, config):
    with pytest.raises(ValueError, match="region_measurement_protocol_mismatch"):
        validate_region_report_policy(report(area=area), config)


@pytest.mark.parametrize("change", [{"protocol_version": "1.0.0"}, {"protocol_version": "3.0.0"},
                                     {"measurement": None}, {"field_outcomes": {}},
                                     {"field_masks": {}}, {"revision_id": "other"},
                                     {"field_failures": [{"field_id": "f1", "reason": "region_source_invalid"}]}])
def test_report_rejects_protocol_identity_and_outcome_forgery(change):
    result = report().model_dump(mode="json")
    with pytest.raises(ValidationError):
        region_report_from_json(json.dumps({**result, **change}))


@pytest.mark.parametrize("field", ["measurement", "protocol_version"])
def test_report_union_does_not_guess_missing_protocol_or_policy(field):
    result = report().model_dump(mode="json")
    result.pop(field)
    with pytest.raises(ValidationError):
        region_report_from_json(json.dumps(result))


@pytest.mark.parametrize("area", [False, True])
def test_explicit_failed_fields_and_exclusions_survive_report_versions(area):
    result = report(area=area).model_dump(mode="json")
    result["field_outcomes"].update({"f2": "failed", "f3": "excluded_failed"})
    result["field_failures"] = [{"field_id": "f2", "reason": "region_source_invalid"}]
    result["excluded_failed_fields"] = [{"field_id": "f3", "reason": "Reviewed unreadable input",
                                         "error": "region_source_invalid"}]
    result["exclusions"] = [{"field_id": "f1", "region_id": 7, "reason": "Reviewed edge object"}]
    loaded = region_report_from_json(json.dumps(result))
    assert loaded.field_failures[0].field_id == "f2"
    assert loaded.excluded_failed_fields[0].reason == "Reviewed unreadable input"
    assert loaded.exclusions[0].region_id == 7
    result["field_outcomes"].pop("f2")
    with pytest.raises(ValidationError, match="region_report_field_coverage_invalid"):
        region_report_from_json(json.dumps(result))


def test_old_table_cannot_be_smuggled_into_v2_report():
    result = report().model_dump(mode="json")
    result["field_tables"]["f1"] = report(area=False).field_tables["f1"].model_dump(mode="json")
    with pytest.raises(ValidationError):
        region_report_from_json(json.dumps(result))
