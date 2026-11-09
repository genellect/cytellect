"""Channel gate wiring and arithmetic on minimum synthetic numeric/label fixtures.

One pixel per label fixes a hand-checkable mean; these fixtures do not evaluate
segmentation, image appearance, thresholds' biological validity or classification accuracy.
"""
import copy
import json

import pytest
from cytellect_analysis.channel_gate_contracts import ChannelGateFilter, ChannelGateRequest
from cytellect_analysis.channel_selection import apply_channel_gate, methods_sentences
from cytellect_analysis.common_statistics import analyze_region_comparison
from cytellect_analysis.common_statistics_contracts import RegionComparisonRequestV2
from cytellect_analysis.common_statistics_figures import render_common_statistics
from cytellect_analysis.descriptive import describe_regions
from cytellect_analysis.descriptive_contracts import RegionSelection
from cytellect_analysis.field_summary_source import describe_field_summary
from cytellect_analysis.gfp_selection import same_revision_nuclear_source
from cytellect_analysis.region_exports import _recompute_statistics
from pydantic import ValidationError
from test_gfp_gated_statistics import nuclear_fixture, request


def gate(**updates):
    return {"version": "1.0.0", "gate_protocol": "channel-gate/1.0.0", "channel_id": "ncl",
            "method": "manual", "threshold": 10.0, "values": "raw", "keep": "positive", **updates}


def classify(report, config, filter_):
    observations = [{"field_id": fid, "region_id": rid, "excluded": False}
                    for fid, table in report["field_tables"].items()
                    for rid in sorted({row["region_id"] for row in table["rows"]})]
    return apply_channel_gate(observations, config["field_snapshot"], filter_,
                              same_revision_nuclear_source(report, config["field_snapshot"]),
                              target_exclusions=report.get("exclusions", []))


def recorded_gate(report, config, **updates):
    filter_ = gate(**updates)
    return {**filter_, "reference_sha256": classify(report, config, filter_)[1]["decision_sha256"]}


def test_manual_boundary_raw_corrected_and_real_channel_identity_are_recorded():
    report, config = nuclear_fixture({"a": ("A", "u", None, [(1, 5), (1, 10), (1, 15)])})
    marked, record = classify(report, config, gate())
    assert [row["channel_positive"] for row in marked] == [False, False, True]
    corrected, corrected_record = classify(report, config, gate(values="corrected"))
    assert [row["channel_mean"] for row in corrected] == [0, 5, 10]
    assert [row["channel_positive"] for row in corrected] == [False, False, False]
    assert corrected_record["filter"]["values"] == "corrected"
    assert record["channel"] == {"channel_id": "ncl", "label": "NCL", "stain": "anti-nucleolin"}
    assert record["dates"]["all"]["threshold"] == 10
    assert "gfp" not in json.dumps(record).lower()
    assert "anti-nucleolin" in " ".join(methods_sentences(record))
    assert "GFP" not in " ".join(methods_sentences(record))


def test_control_percentile_is_per_date_corrected_and_minimum_is_not_bypassed():
    fields = {"c": ("control", "c", "d1", [(1, i) for i in range(20)]),
              "a": ("A", "a", "d1", [(1, 9), (1, 10)]),
              "b": ("B", "b", "d2", [(1, 100)])}
    report, config = nuclear_fixture(fields)
    _, record = classify(report, config, gate(method="negative_control", threshold=None, percentile=50.0,
                                             values="corrected", control_field_ids=["c"]))
    assert record["dates"]["d1"]["threshold"] == 4.5  # median(0..19) - background 5
    assert record["dates"]["d1"]["control_nuclei"] == 20
    assert record["dates"]["d1"]["control_field_ids"] == ["c"]
    assert record["dates"]["d2"]["threshold"] is None
    assert record["field_counts"]["a"]["negative"] == record["field_counts"]["a"]["positive"] == 1
    assert record["field_counts"]["b"]["unclassified"] == 1
    assert record["field_counts"]["c"]["control"] == 20
    assert record["field_counts"]["c"]["evaluable"] == 0


def test_otsu_uniform_unknown_dates_and_exclusions_stay_in_separate_ledgers():
    report, config = nuclear_fixture({"a": ("A", "a", "d1", [(1, 10), (1, 10)]),
                                      "b": ("B", "b", None, [(1, 0), (1, 100)])},
                                    exclusions=[{"field_id": "a", "region_id": 2, "reason": "excluded"}])
    _, record = classify(report, config, gate(method="batch_otsu", threshold=None))
    assert record["field_counts"]["a"]["excluded"] == 1
    assert record["field_counts"]["a"]["unclassified"] == 1
    assert record["field_counts"]["b"]["unclassified"] == 2
    assert record["dates"][""]["missing_reason"] == "channel_gate_acquisition_date_required"
    assert all(row["positive"] is None for row in record["nuclei"])


def test_exact_ids_source_hash_and_channel_semantics_fail_closed():
    report, config = nuclear_fixture({"a": ("A", "a", "d1", [(1, 10)])})
    source = same_revision_nuclear_source(report, config["field_snapshot"])
    source["fields"]["a"]["mask_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="channel_gate_nuclear_identity_mismatch"):
        apply_channel_gate([], config["field_snapshot"], gate(), source)
    source = same_revision_nuclear_source(report, config["field_snapshot"])
    with pytest.raises(ValueError, match="channel_gate_nuclear_identity_mismatch"):
        apply_channel_gate([{"field_id": "a", "region_id": 999, "excluded": False}], config["field_snapshot"], gate(), source)
    with pytest.raises(ValueError, match="channel_gate_channel_unknown"):
        classify(report, config, gate(channel_id="not-recorded"))


def test_positivity_denominator_is_before_subset_selection_and_reuses_decisions():
    report, config = nuclear_fixture({"a": ("A", "a", None, [(1, 10), (1, 20), (1, 30)])})
    filter_ = recorded_gate(report, config, keep="negative")
    selected = describe_regions(report, config["field_snapshot"], {"mode": "descriptive", "selection": {
        "source": "region", "region_set_id": "nuclei", "metric": "mean", "channel_id": "ncl", "channel_gate": filter_}})
    request_ = {"mode": "descriptive", "selection": {"source": "field-summary", "version": "1.0.0",
                "region_set_id": "nuclei", "metric": "positive_fraction", "positivity": filter_}}
    result = describe_field_summary(report, config["field_snapshot"], request_)
    assert [row["region_id"] for row in selected["plot_data"]] == [1]
    assert [row["value"] for row in result["plot_data"]] == [pytest.approx(2 / 3)]
    assert result["source_fields"][0]["field_summary"]["evaluable_count"] == 3
    assert result["source_fields"][0]["field_summary"]["positive_count"] == 2
    for key in ("filter", "dates", "nuclei", "nuclear_sources"):
        assert result["selection"]["channel_gate"][key] == selected["selection"]["channel_gate"][key]
    assert result["selection"]["channel_gate"]["purpose"] == "field_positivity"


def test_field_positivity_preserves_independent_units_methods_csv_and_replay(tmp_path):
    report, config = nuclear_fixture({"a1": ("A", "a1", "d1", [(1, 10), (1, 20)]),
                                      "a2": ("A", "a2", "d1", [(1, 0), (1, 30)]),
                                      "b1": ("B", "b1", "d1", [(1, 20), (1, 30)]),
                                      "b2": ("B", "b2", "d1", [(1, 40), (1, 10)])})
    raw = request(test="none").model_dump(mode="json")
    raw["selection"] = {"source": "field-summary", "version": "1.0.0", "region_set_id": "nuclei",
                        "metric": "positive_fraction", "positivity": recorded_gate(report, config, threshold=15.0)}
    result = analyze_region_comparison(report, config, RegionComparisonRequestV2.model_validate(raw))
    assert {row["experimental_unit"]: row["value"] for row in result["unit_summary"]} == {
        "a1": 0.5, "a2": 0.5, "b1": 1.0, "b2": 0.5}
    result["figure"] = render_common_statistics(result, tmp_path)
    assert "before subset selection" in (tmp_path / "methods.md").read_text(encoding="utf8")
    assert "positive_count" in (tmp_path / "observations.csv").read_text(encoding="utf8")
    assert _recompute_statistics(report, config, result) == {key: value for key, value in result.items() if key != "figure"}
    tampered = copy.deepcopy(result)
    tampered["selection"]["channel_gate"]["dates"]["all"]["threshold"] += 1
    assert _recompute_statistics(report, config, tampered) != {key: value for key, value in tampered.items() if key != "figure"}


def test_new_filter_is_opt_in_and_legacy_serialization_is_unchanged():
    old = {"source": "region", "region_set_id": "nuclei", "channel_id": "ncl", "metric": "mean"}
    assert RegionSelection.model_validate(old).model_dump(mode="json") == old
    selected = RegionSelection.model_validate({**old, "channel_gate": gate()}).model_dump(mode="json")
    assert "gfp_gate" not in selected and selected["channel_gate"]["channel_id"] == "ncl"
    from test_gfp_gated_statistics import gate as legacy_gate
    with pytest.raises(ValidationError, match="conflicting_filters"):
        RegionSelection.model_validate({**old, "channel_gate": gate(), "gfp_gate": legacy_gate()})
    for changes in ({"method": "batch_otsu"}, {"method": "negative_control", "threshold": None},
                    {"gfp_channel_id": "ncl"}, {"threshold": float("inf")}):
        with pytest.raises(ValidationError):
            ChannelGateFilter.model_validate(gate(**changes))
    with pytest.raises(ValidationError, match="duplicate_field"):
        ChannelGateRequest.model_validate({"filter": gate(), "fields": [{"field_id": "a", "revision_id": "r"}] * 2})


def test_recorded_decision_is_reused_across_cohorts_and_refuses_changed_inputs():
    report, config = nuclear_fixture({"a": ("A", "a", "d1", [(1, 10), (1, 20)])})
    _, original = classify(report, config, gate())
    recorded = gate(reference_sha256=original["decision_sha256"])
    _, replayed = classify(report, config, recorded)
    assert replayed["decision_sha256"] == original["decision_sha256"]
    renamed = copy.deepcopy(report)
    renamed["revision_id"] = "cohort"
    assert classify(renamed, config, recorded)[1]["decision_sha256"] == original["decision_sha256"]
    for table in report["field_tables"].values():
        for row in table["rows"]:
            if row["channel_id"] == "ncl":
                row["mean"] += 1
    with pytest.raises(ValueError, match="channel_gate_record_mismatch"):
        classify(report, config, recorded)


def test_formal_analysis_requires_a_record_and_missing_corrected_values_never_fall_back():
    report, config = nuclear_fixture({"a": ("A", "a", None, [(1, 100)])})
    with pytest.raises(ValueError, match="channel_gate_record_required"):
        describe_regions(report, config["field_snapshot"], {"mode": "descriptive", "selection": {
            "source": "region", "region_set_id": "nuclei", "metric": "mean", "channel_id": "ncl", "channel_gate": gate()}})
    # A non-finite legacy saved scalar is unavailable; the finite raw 100 is not a substitute.
    for row in report["field_tables"]["a"]["rows"]:
        if row["channel_id"] == "ncl":
            row["mean_corrected"] = float("nan")
    marked, record = classify(report, config, gate(values="corrected"))
    assert marked[0]["channel_mean"] is None and marked[0]["channel_positive"] is None
    assert record["field_counts"]["a"]["unclassified"] == 1
    assert record["field_counts"]["a"]["evaluable"] == 0


def test_target_exclusions_precede_thresholding_and_keep_their_reasons():
    report, config = nuclear_fixture({"a": ("A", "a", "d1", [(1, 0), (1, 100), (1, 10000)])})
    source = same_revision_nuclear_source(report, config["field_snapshot"])
    target = [{"field_id": "a", "region_id": 3, "reason": "target excluded"}]
    _, record = apply_channel_gate([], config["field_snapshot"], gate(method="batch_otsu", threshold=None), source,
                                   target_exclusions=target)
    assert record["dates"]["d1"]["threshold"] == pytest.approx(100 / 512)  # first of 256 bin centres
    assert record["field_counts"]["a"]["excluded"] == 1
    assert record["nuclei"][-1]["exclusion_reason"] == "target excluded"
    whole = [{"field_id": "a", "region_id": None, "reason": "field excluded"}]
    _, record = apply_channel_gate([], config["field_snapshot"], gate(), source, target_exclusions=whole)
    assert record["field_counts"]["a"]["excluded"] == 3
    assert {row["exclusion_reason"] for row in record["nuclei"]} == {"field excluded"}


def test_control_fields_do_not_require_or_manufacture_compared_units():
    report, config = nuclear_fixture({"c": (None, "c", "d1", [(1, i) for i in range(20)]),
                                      "a1": ("A", "a1", "d1", [(1, 10), (1, 15)]),
                                      "a2": ("A", "a2", "d1", [(1, 15), (1, 5)]),
                                      "b1": ("B", "b1", "d1", [(1, 50)]),
                                      "b2": ("B", "b2", "d1", [(1, 40)])})
    config["field_snapshot"]["c"]["metadata"].update(sample=None, experimental_unit=None)
    filter_ = recorded_gate(report, config, method="negative_control", threshold=None, percentile=50.0,
                            control_field_ids=["c"])
    raw = request(test="none").model_dump(mode="json")
    raw["selection"]["channel_gate"] = filter_
    result = analyze_region_comparison(report, config, RegionComparisonRequestV2.model_validate(raw))
    assert {row["experimental_unit"] for row in result["unit_summary"]} == {"a1", "a2", "b1", "b2"}
    control = next(row for row in result["source_field_ledger"] if row["field_id"] == "c")
    assert control["condition"] is None and control["experimental_unit"] is None
    assert control["status"] == "channel_negative_control"
