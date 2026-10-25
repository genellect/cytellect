"""Compartment-summary selection 1.1.0 (nucleolar total area and eccentricity) through common statistics.

Uses the minimal label/pixel fixture of test_compartment_observations (synthetic numbers for
wiring and arithmetic only; not an image evaluation). Eccentricity values are supplied as
plain numbers; the shape formula itself is checked in test_group_comparison_metrics on public
BBBC039 outlines.
"""
import pytest
from cytellect_analysis.common_statistics import analyze_region_comparison
from cytellect_analysis.common_statistics_contracts import RegionComparisonRequestV2
from cytellect_analysis.common_statistics_figures import render_common_statistics
from test_compartment_observations import compartment_fixture, request

DOUBLE = {"a1f1": (0,), "b1f1": (0, 1)}


def v11(metric, **changes):
    raw = request(metric="nucleolar_count").model_dump(mode="json")
    raw["selection"] = {"source": "compartment-summary", "version": "1.1.0", "region_set_id": "nucleoplasm",
                        "metric": metric}
    return RegionComparisonRequestV2.model_validate({**raw, **changes})


def values(result):
    return {(row["field_id"], row["region_id"]): row["value"] for row in result["observation_ledger"]
            if row["value"] is not None}


def shapes_for(summaries, value=lambda fid, nid: 0.5):
    out = {}
    for fid, document in summaries.items():
        rows = next(iter(document["channels"].values()))["rows"]
        out[fid] = {row["nucleus_id"]: {"nucleolar_eccentricity": value(fid, row["nucleus_id"]) if row["nucleolar_count"] else None,
                                         "objects": row["nucleolar_count"], "measured_objects": row["nucleolar_count"],
                                         "missing_reason": None if row["nucleolar_count"] else "no_nucleolus"}
                    for row in rows}
    return out


def test_nucleolar_union_area_per_nucleus(tmp_path):
    report, config, summaries = compartment_fixture(double=DOUBLE)
    result = analyze_region_comparison(report, config, v11("nucleolar_area_px"), summaries=summaries)
    observed = values(result)
    # A doubled nucleus has a two-pixel nucleolar union; every other adopted nucleolus is one pixel.
    assert observed[("a1f1", 1)] == 2 and observed[("b1f1", 2)] == 2 and observed[("a1f2", 1)] == 1
    assert result["unit"] == "px²"
    assert result["spec"]["selection"]["version"] == "1.1.0"
    assert {item["compartment_summary"]["selection_version"] for item in result["source_fields"]} == {"1.1.0"}
    assert render_common_statistics(result, tmp_path)["source_files"]


def test_calibrated_area_needs_calibration():
    report, config, summaries = compartment_fixture()
    with pytest.raises(ValueError, match="compartment_summary_calibration_required"):
        analyze_region_comparison(report, config, v11("nucleolar_area_um2"), summaries=summaries)


def test_eccentricity_uses_bound_shapes_and_keeps_candidate_free_nuclei_missing():
    report, config, summaries = compartment_fixture()
    by_unit = {"a1": 0.2, "a2": 0.3, "a3": 0.25, "b1": 0.7, "b2": 0.8, "b3": 0.75}
    shapes = shapes_for(summaries, lambda fid, nid: by_unit[fid[:2]])
    result = analyze_region_comparison(report, config, v11("nucleolar_eccentricity", estimates="comparison-estimates/1.0.0"),
                                       summaries=summaries, shapes=shapes)
    assert set(values(result).values()) == set(by_unit.values())
    missing = [row for row in result["observation_ledger"] if row["value"] is None]
    assert missing and {row["missing_reason"] for row in missing} <= {"no_nucleolus"}
    assert result["estimates"]["scale"] == "difference"
    assert result["estimates"]["difference"]["estimate"] == pytest.approx(0.25 - 0.75)


def test_eccentricity_refuses_missing_or_unbound_shapes():
    report, config, summaries = compartment_fixture()
    with pytest.raises(ValueError, match="compartment_summary_shape_unavailable"):
        analyze_region_comparison(report, config, v11("nucleolar_eccentricity"), summaries=summaries)
    shapes = shapes_for(summaries)
    first = next(iter(shapes))
    nucleus = next(nid for nid, shape in shapes[first].items() if shape["objects"])
    shapes[first][nucleus] = {**shapes[first][nucleus], "objects": 3}
    with pytest.raises(ValueError, match="compartment_summary_shape_mismatch"):
        analyze_region_comparison(report, config, v11("nucleolar_eccentricity"), summaries=summaries, shapes=shapes)


def test_historical_selection_without_version_stays_1_0_0():
    raw = request(metric="nucleolar_count").model_dump(mode="json")
    raw["selection"].pop("version")
    parsed = RegionComparisonRequestV2.model_validate(raw)
    assert parsed.selection.version == "1.0.0"
    assert parsed.model_dump(mode="json")["selection"]["version"] == "1.0.0"
