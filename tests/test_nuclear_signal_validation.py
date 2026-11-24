"""The public nuclear-signal check (scripts/validate_nuclear_signal_public.py) on registered BBBC039 fields.

No DS6b value is computed here. The BBBC039 Hoechst fields and manual annotations stand in for every channel and
carry made-up condition names, only to show that the script's floor and pooling give the shared implementation's
values (rule 4) and that its statistics and verdict run and fail closed.
"""
import sys
from pathlib import Path

import numpy as np
import pytest
from cytellect_analysis import nuclear_features
from test_nuclear_features import FLOOR, features_for, public_fields, public_report

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import validate_nuclear_signal_public as check  # noqa: E402


@pytest.fixture(autouse=True)
def floor(monkeypatch):
    monkeypatch.setattr(nuclear_features, "MINIMUM_SIGNAL_TO_BACKGROUND", FLOOR)


def fields(conditions=("UntreatedWithEU", "ActD1", "UntreatedNoEU"), group="2hrs"):
    out = []
    for (name, pixels, labels), condition in zip(public_fields(len(conditions)), conditions, strict=True):
        decimated, binned = check.registered.decimate2(labels), check.registered.bin2(pixels)
        ids = np.asarray(sorted(int(value) for value in np.unique(decimated) if value), np.int64)
        field = {"name": name, "group": group, "condition": condition, "split": "tuning", "status": "ok",
                 "nuclei": int(len(np.unique(labels)) - 1), "redetected_match": {"native": ids, "redetected": ids}}
        for channel in check.CHANNELS:
            field[channel] = {"native": check._signal(labels, pixels), "binned": check._signal(decimated, binned),
                              "redetected": check._signal(decimated, binned)}
        out.append(field)
    return out


def test_floor_and_pooling_give_the_shared_implementation_values():
    measured = fields(("A", "B", "A"), group="d1")
    table = check.values_at(measured, "nuclear", "native", FLOOR)
    report, snapshot, images, labels = public_report(dates=("d1", "d1", "d1"), conditions=("A", "B", "A"))
    features = features_for(report, snapshot, images, labels, {("cv_corrected", "dna"), ("positive_area_fraction", "dna")})
    for index, field in enumerate(measured):
        fid = f"f{index}"
        values = table["fields"][field["name"]]
        for metric in ("cv_corrected", "positive_area_fraction"):
            product = features[metric, "dna"][fid]["values"]
            expected = np.asarray([np.nan if product[int(rid)]["value"] is None else product[int(rid)]["value"]
                                   for rid in values["ids"]])
            np.testing.assert_array_equal(values[metric], expected)
    assert table["thresholds"]["d1"]["value"] == features["positive_area_fraction", "dna"]["f0"]["threshold"]["value"]


def test_statistics_run_and_the_verdict_fails_closed():
    measured = fields()
    ratio = check.choose_ratio(measured)
    assert ratio["chosen"] in check.RATIO_CANDIDATES
    summary = check.summarize(measured, ratio["chosen"])
    criteria = check.criteria_from_tuning(summary["statistics"])
    assert set(criteria) == {f"{metric}/{channel}" for metric in check.METRICS for channel in check.CHANNELS}
    for value in summary["statistics"].values():
        for row in value["by_group"]["2hrs"]["conditions"].values():
            assert 0 <= row["measurable_fraction"] <= 1
    # One field per condition cannot give a contrast: tuning does not allow offering, and a missing condition fails.
    assert not any(item["tuning_allows"] for item in criteria.values())
    result = check.verdict(summary["statistics"], criteria, {"2hrs": {"UntreatedWithEU", "ActD1", "UntreatedNoEU", "Cis10"}})
    assert not any(item["passes"] for item in result.values())
    assert all("missing:2hrs/Cis10" in item["failures"] for item in result.values())
    eu5 = result["cv_corrected/eu5"]
    assert "missing:2hrs/UntreatedNoEU" not in eu5["failures"]


def test_evaluation_refuses_without_committed_tuning(tmp_path, monkeypatch):
    monkeypatch.setattr(check, "TUNING", tmp_path / "tuning.json")
    with pytest.raises(SystemExit, match="evaluation_refused"):
        check.evaluate(tmp_path / "data", tmp_path / "work", 1)
