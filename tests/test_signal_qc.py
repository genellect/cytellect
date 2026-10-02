"""Saved, optional native QC metadata must never become implicit selection."""
import copy
import json
import math

import numpy as np
import pytest
from cytellect_analysis.contracts import Recipe
from cytellect_analysis.measurement import apply_gfp_gate, measure
from cytellect_analysis.signal_qc import native_signal_quality
from cytellect_api.db import revisions
from cytellect_api.storage import read_json
from cytellect_worker.main import run_analysis
from pydantic import ValidationError
from test_api_optional_channels import metadata, tif_bytes
from test_api_worker import HEADERS, authenticated


def native_case():
    nuclei = np.zeros((6, 6), np.uint32)
    nuclei[2:4, 2:4] = 1
    nucleoli = np.zeros_like(nuclei)
    nucleoli[2, 2] = 1
    channels = {role: np.full((6, 6), 11, np.uint16) for role in ("dapi", "ncl", "gfp")}
    for image in channels.values():
        image[0, :4] = [8, 10, 12, 10]
    background = np.zeros((6, 6), bool)
    background[0, :4] = True
    return channels, nuclei, nucleoli, background


def measured(recipe=None, *, empty=False, failed=False, gfp_only=False, zero_mad=False, value=11):
    channels, nuclei, nucleoli, background = native_case()
    if empty or failed or gfp_only:
        nucleoli[:] = 0
    if gfp_only:
        del channels["ncl"]
    for image in channels.values():
        image[nuclei > 0] = value
        if zero_mad:
            image[background] = 10
    return measure(channels, nuclei, nucleoli, background, recipe or Recipe(),
                   {"acquisition_date": "day"}, "f", nucleolar_states={1: "processing_failed"} if failed else None)[0][0]


def test_positive_weak_signal_is_diagnostic_only_and_default_is_unset():
    default = measured()
    recipe = Recipe(native_signal_qc_minimum_ratio=2)
    warning = measured(recipe)
    assert Recipe().native_signal_qc_minimum_ratio is None
    for prefix in ("ncl_nucleus", "ncl_nucleoli", "ncl_nucleoplasm", "gfp"):
        assert default[f"{prefix}_signal_to_background"] == pytest.approx(1 / 1.4826)
        assert default[f"{prefix}_weak_signal"] is None
        assert default[f"{prefix}_signal_qc_reason"] == "threshold_not_set"
        assert warning[f"{prefix}_weak_signal"] is True
        assert warning[f"{prefix}_signal_qc_reason"] == "below_threshold"
    def diagnostic(key):
        return key.startswith(("signal_qc_", "native_signal_qc_")) or key.endswith(
            ("_signal_to_background", "_weak_signal", "_signal_qc_reason"))
    assert {k: v for k, v in default.items() if not diagnostic(k)} == {
        k: v for k, v in warning.items() if not diagnostic(k)}
    assert not warning["excluded"]
    assert apply_gfp_gate([warning], recipe)[0]["gfp_positive"]
    equality = measured(Recipe(native_signal_qc_minimum_ratio=1 / 1.4826))
    assert equality["gfp_weak_signal"] is False
    assert equality["gfp_signal_qc_reason"] == "at_or_above_threshold"


def test_negative_values_and_existing_nonpositive_ratio_reason_are_unchanged():
    row = measured(Recipe(native_signal_qc_minimum_ratio=2), value=8)
    assert row["ncl_nucleus_mean_corrected"] == row["gfp_mean_corrected"] == -2
    assert row["gfp_signal_to_background"] == pytest.approx(-2 / 1.4826)
    assert row["gfp_weak_signal"] is True
    assert row["ratio_missing_reason"] == "nonpositive_signal"
    assert row["ncl_nucleoplasm_over_nucleoli"] is None
    assert not row["excluded"]


def test_undefined_background_empty_missing_and_failed_compartments_remain_missing():
    recipe = Recipe(native_signal_qc_minimum_ratio=2)
    for zero_mad in (True, False):
        row = measured(recipe, failed=True, zero_mad=zero_mad)
        for prefix in ("ncl_nucleoli", "ncl_nucleoplasm"):
            assert row[f"{prefix}_signal_to_background"] is row[f"{prefix}_weak_signal"] is None
            assert row[f"{prefix}_signal_qc_reason"] == "nucleolar_processing_failed"
    zero = measured(recipe, zero_mad=True)
    assert zero["gfp_signal_to_background"] is zero["gfp_weak_signal"] is None
    assert zero["gfp_signal_qc_reason"] == "background_dispersion_zero"
    empty = measured(recipe, empty=True)
    assert empty["ncl_nucleoli_signal_to_background"] is None
    assert empty["ncl_nucleoli_signal_qc_reason"] == "compartment_empty"
    assert math.isfinite(empty["ncl_nucleoplasm_signal_to_background"])
    gfp = measured(Recipe(id="gfp-nuclear-2d", native_signal_qc_minimum_ratio=2), gfp_only=True)
    assert gfp["ncl_nucleus_signal_qc_reason"] == "channel_not_acquired"
    assert gfp["ncl_nucleus_signal_to_background"] is None
    assert math.isfinite(gfp["gfp_signal_to_background"])


@pytest.mark.parametrize("sigma", [float("nan"), float("inf"), -1, None])
def test_invalid_dispersion_is_not_converted_to_infinite_or_arbitrary_score(sigma):
    row = measured()
    row["gfp_background_sigma"] = sigma
    original = copy.deepcopy(row)
    result = native_signal_quality(row, 2)
    assert result["gfp_signal_to_background"] is result["gfp_weak_signal"] is None
    assert result["gfp_signal_qc_reason"] == "background_dispersion_invalid"
    assert row.keys() == original.keys()
    assert row["gfp_mean_corrected"] == original["gfp_mean_corrected"]


def test_native_only_threshold_rejects_invalid_values_and_legacy_scope():
    for value in (-1, float("nan"), float("inf")):
        with pytest.raises(ValidationError):
            Recipe(native_signal_qc_minimum_ratio=value)
    with pytest.raises(ValidationError, match="native_signal_qc_unavailable_in_legacy"):
        Recipe(id="ncl-legacy-rgb", native_signal_qc_minimum_ratio=2)
    channels, nuclei, nucleoli, background = native_case()
    nucleoli[:] = 0
    row = measure(channels, nuclei, nucleoli, background,
                  Recipe(id="gfp-nuclear-2d"), {}, "f")[0][0]
    assert row["ncl_nucleus_signal_qc_reason"] == "recipe_not_measured"


def test_threshold_reconfiguration_reuses_masks_and_saves_warning_without_exclusion(tmp_path, monkeypatch):
    client, app, settings = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", json={"title": "signal QC"}, headers=HEADERS).json()["id"]
    channels, nuclei, nucleoli, _ = native_case()
    uploaded = client.post(f"/v1/workspaces/{wid}/fields", data={"metadata": json.dumps(metadata())},
                           files={role: ("synthetic.tif", tif_bytes(image), "image/tiff")
                                  for role, image in channels.items()}, headers=HEADERS)
    assert uploaded.status_code == 201
    fid = uploaded.json()["id"]
    calls = []
    def fixed_detection(*args, **kwargs):
        calls.append(1)
        return nuclei.copy(), nucleoli.copy(), np.zeros_like(nuclei), {"engine": "test"}
    monkeypatch.setattr("cytellect_worker.main._initial_masks", fixed_detection)
    def finish(response):
        assert response.status_code == 202, response.text
        job = app.state.store.claim()
        assert job["id"] == response.json()["job_id"]
        output = app.state.store.safe_path("test-results", job["revision_id"])
        run_analysis(app.state.store, settings, job, output)
        assert app.state.store.finish(job, str(output.relative_to(app.state.store.root)))
        return job["revision_id"], read_json(output / "measurements.json"), output
    body = {"backgrounds": {fid: {"confirmed": True, "polygon": [[0, 0], [4, 0], [4, 1], [0, 1]]}}}
    old, before, before_path = finish(client.post(f"/v1/workspaces/{wid}/analyses", json=body, headers=HEADERS))
    body["recipe"] = Recipe(native_signal_qc_minimum_ratio=2).model_dump()
    new, after, after_path = finish(client.post(f"/v1/revisions/{old}/reconfigure", json=body, headers=HEADERS))
    assert len(calls) == 1
    assert after["field_failures"] == [] and not after["cells"][0]["excluded"]
    assert after["cells"][0]["gfp_positive"] and after["cells"][0]["gfp_weak_signal"]
    assert before["cells"][0]["gfp_weak_signal"] is None
    with np.load(before_path / fid / "masks.npz") as first, np.load(after_path / fid / "masks.npz") as second:
        for layer in ("nuclei", "nucleoli", "manual"):
            np.testing.assert_array_equal(first[layer], second[layer])
    assert app.state.store.one(revisions, id=new)["config"]["recipe"]["native_signal_qc_minimum_ratio"] == 2
