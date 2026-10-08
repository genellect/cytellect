"""GFP nucleus filter 1.0.0 through the unchanged experimental-unit and descriptive protocols.

Synthetic original pixels only (one pixel per nucleus, so every mean is the chosen
integer). Thresholds, kept nuclei, field medians and unit means are written out by
hand; test statistics are checked against SciPy on those hand-calculated unit means.
"""
import copy
import json

import numpy as np
import pytest
from cytellect_analysis.common_statistics import analyze_region_association, analyze_region_comparison
from cytellect_analysis.common_statistics_contracts import RegionAssociationRequest, RegionComparisonRequestV2
from cytellect_analysis.common_statistics_figures import render_common_statistics
from cytellect_analysis.compartment_observations import describe_compartment_summary
from cytellect_analysis.compartment_summary import compartment_summary
from cytellect_analysis.descriptive import describe_regions
from cytellect_analysis.descriptive_contracts import (
    DescriptiveRequest,
    RegionSelection,
    parse_descriptive_request,
)
from cytellect_analysis.descriptive_output import render_descriptive_output
from cytellect_analysis.gfp_selection import same_revision_nuclear_source
from cytellect_analysis.region_comparison_contracts import RegionComparisonRequest
from cytellect_analysis.region_exports import _recompute_statistics
from cytellect_analysis.regions import (
    BackgroundSpec,
    ChannelSpec,
    RegionMeasurementSpec,
    RegionSetSpec,
    measure_regions,
)
from cytellect_analysis.statistical_methods import CURRENT_METHODS_TEMPLATE
from pydantic import ValidationError
from scipy import stats

CHANNELS = (ChannelSpec(channel_id="dna", label="DNA", stain="Hoechst 33342", identity_confirmed=True),
            ChannelSpec(channel_id="gfp", label="GFP", stain="EGFP", identity_confirmed=True),
            ChannelSpec(channel_id="ncl", label="NCL", stain="anti-nucleolin", identity_confirmed=True))
RECIPE = {"id": "region-2d", "version": "1.2.0", "region_set_id": "nuclei", "label": "Nuclei",
          "source": "stardist_nuclear", "defining_channel_id": "dna", "nuclear_role_source": "recorded_stain"}
# field -> (condition, unit, date, [(gfp mean, ncl mean), ...]); one pixel per nucleus.
CONTROLS = {"c1": ("control", "cu1", "d1", [(100 + i, 1) for i in range(25)]),
            "c2": ("control", "cu2", "d2", [(200 + i, 1) for i in range(20)]),
            "c3": ("control", "cu3", "d3", [(1 + i, 1) for i in range(5)])}
MEASURED = {"a1": ("A", "a1", "d1", [(300, 10), (300, 14), (50, 100)]),
            "a1x": ("A", "a1", "d3", [(900, 999)]),
            "a2": ("A", "a2", "d1", [(400, 20), (60, 200), (60, 300)]),
            "a3": ("A", "a3", "d2", [(219, 30), (218, 400), (500, 34)]),
            "b1": ("B", "b1", "d1", [(300, 40), (300, 44), (300, 48), (70, 500)]),
            "b2": ("B", "b2", "d1", [(250, 50), (80, 600)]),
            "b3": ("B", "b3", "d2", [(300, 60), (300, 62), (100, 700)])}
# Hand calculation. d1: 100 + 0.99 * 24; d2: 200 + 0.99 * 19; d3 has 5 < 20 controls.
THRESHOLDS = {"d1": 123.76, "d2": 218.81, "d3": None}
POSITIVE_UNITS = {"a1": 12.0, "a2": 20.0, "a3": 32.0, "b1": 44.0, "b2": 50.0, "b3": 61.0}
NEGATIVE_UNITS = {"a1": 100.0, "a2": 250.0, "a3": 400.0, "b1": 500.0, "b2": 600.0, "b3": 700.0}
# Ungated field medians; a1 has two fields (a1: 14, a1x: 999) in one sample.
ALL_UNITS = {"a1": (14 + 999) / 2, "a2": 200.0, "a3": 34.0, "b1": 46.0, "b2": 325.0, "b3": 62.0}


def nuclear_fixture(fields=None, exclusions=()):
    fields = fields or {**CONTROLS, **MEASURED}
    report = {"analysis_kind": "region-2d", "revision_id": "rev_nuclei", "recipe": copy.deepcopy(RECIPE),
              "field_tables": {}, "field_failures": [], "excluded_failed_fields": [], "exclusions": list(exclusions)}
    snapshot = {}
    for fid, (condition, unit, date, nuclei) in fields.items():
        width = 2 * len(nuclei) + 1
        labels = np.zeros((3, width), np.uint32)
        planes = {c.channel_id: np.full((3, width), 5, np.uint16) for c in CHANNELS}
        for index, (gfp, ncl) in enumerate(nuclei):
            labels[1, 2 * index + 1] = index + 1
            planes["dna"][1, 2 * index + 1] = 500
            planes["gfp"][1, 2 * index + 1] = gfp
            planes["ncl"][1, 2 * index + 1] = ncl
        background = np.zeros(labels.shape, bool)
        background[0] = True
        spec = RegionMeasurementSpec(
            field_id=fid, analysis_revision_id="rev_nuclei",
            region_set=RegionSetSpec(region_set_id="nuclei", label="Nuclei", mask_revision_id="rev_nuclei",
                                     source="stardist_nuclear", defining_channel_id="dna"),
            channels=CHANNELS, backgrounds=tuple(BackgroundSpec(channel_id=c.channel_id, roi_revision_id=f"bg_{fid}",
                                                                confirmed=True) for c in CHANNELS))
        table = measure_regions(planes, labels, {c.channel_id: background for c in CHANNELS}, spec)
        report["field_tables"][fid] = table.model_dump(mode="json")
        snapshot[fid] = {"metadata": {"condition": condition, "experimental_unit": unit, "sample": f"s_{unit}",
                                      "acquisition_date": date, "pair": None},
                         "image_info": {"shape": [3, width], "calibration": None,
                                        "channels": [c.model_dump(mode="json") for c in CHANNELS]}}
    config = {"field_ids": list(snapshot), "field_snapshot": snapshot, "recipe": copy.deepcopy(RECIPE),
              "backgrounds": {}, "exclusions": list(exclusions), "review_record": {"confirmed_at": 123.0}}
    return report, config


def gate(keep="positive", **changes):
    return {"version": "1.0.0", "gate_protocol": "gfp-gate/2.0.0", "gfp_channel_id": "gfp", "percentile": 99,
            "control_field_ids": ["c1", "c2", "c3"], "keep": keep, **changes}


def request(test="welch-t", filter_=None, conditions=("A", "B"), **changes):
    selection = {"source": "region", "region_set_id": "nuclei", "channel_id": "ncl", "metric": "mean"}
    if filter_ is not None:
        selection["gfp_gate"] = filter_
    return RegionComparisonRequestV2.model_validate({
        "mode": "region-experimental-unit", "version": "2.0.0", "test": test, "selection": selection,
        "design": {"kind": "independent", "confirmed": True, "unit_definition": "Independently transfected cultures"},
        "conditions": list(conditions), "comparison_family": {"family_id": "primary", "kind": "planned", "control": None,
                                                              "contrasts": [list(conditions)]},
        "acquisition_review": {"confirmed": True, "basis": "same-settings", "spatial_sampling_confirmed": True},
        "missingness_confirmed": True, "plot": {"preset": "nature-double"}, **changes})


def units(result):
    return {row["experimental_unit"]: row["value"] for row in result["unit_summary"]}


def test_per_date_control_thresholds_and_positive_units_match_hand_calculation_and_scipy():
    report, config = nuclear_fixture()
    result = analyze_region_comparison(report, config, request(filter_=gate()))
    record = result["selection"]["gfp_gate"]
    for date, expected in THRESHOLDS.items():
        if expected is None:
            assert record["dates"][date]["threshold"] is None
        else:
            assert record["dates"][date]["threshold"] == pytest.approx(expected, abs=1e-12)
    assert record["dates"]["d1"]["threshold"] == np.percentile(range(100, 125), 99)
    assert {d: (v["control_nuclei"], v["missing_reason"], v["control_field_ids"]) for d, v in record["dates"].items()} == {
        "d1": (25, None, ["c1"]), "d2": (20, None, ["c2"]), "d3": (5, "too_few_control_nuclei", ["c3"])}
    assert record["filter"] == {**gate(), "percentile": 99.0}
    assert record["nuclear_binding"] == "same_revision" and record["values"] == "raw"
    assert record["gfp_channel"]["stain"] == "EGFP"
    assert units(result) == POSITIVE_UNITS
    a, b = [POSITIVE_UNITS[u] for u in ("a1", "a2", "a3")], [POSITIVE_UNITS[u] for u in ("b1", "b2", "b3")]
    contrast = result["comparisons"][0]
    reference = stats.ttest_ind(a, b, equal_var=False)
    assert contrast["estimate"] == pytest.approx(np.mean(a) - np.mean(b))
    assert contrast["statistic"] == pytest.approx(reference.statistic)
    assert contrast["p_value"] == pytest.approx(reference.pvalue)
    rank = analyze_region_comparison(report, config, request("mann-whitney-u", filter_=gate()))["comparisons"][0]
    assert rank["p_value"] == pytest.approx(stats.mannwhitneyu(a, b, alternative="two-sided", method="exact").pvalue)
    assert [row["observations"] for row in result["counts"]] == [5, 6]
    assert "gfp_gated_subset_selected_by_expression_level_not_randomized" in result["warnings"]
    assert "gfp_gate_dates_without_control_threshold_unselected" in result["warnings"]


def test_controls_and_unselected_nuclei_stay_in_the_ledgers_with_reasons():
    report, config = nuclear_fixture()
    result = analyze_region_comparison(report, config, request(filter_=gate()))
    statuses = {}
    for row in result["observation_ledger"]:
        statuses.setdefault(row["field_id"], []).append((row["selection_status"], row["gfp_gate_reason"]))
    assert statuses["c1"] == [("gfp_negative_control", "negative_control")] * 25
    assert statuses["a1"] == [("selected", "above_control_threshold")] * 2 + [("gfp_gate_unselected", "within_control_range")]
    assert statuses["a1x"] == [("gfp_gate_unselected", "too_few_control_nuclei")]
    # 219 > 218.81 is positive; 218 is within the control range on d2.
    assert statuses["a3"] == [("selected", "above_control_threshold"), ("gfp_gate_unselected", "within_control_range"),
                              ("selected", "above_control_threshold")]
    assert result["selection"]["gfp_negative_control"] == 50
    assert result["selection"]["gfp_gate_unselected"] == 8
    assert result["selection"]["selected"] == 11
    ledger = {row["field_id"]: row for row in result["source_field_ledger"]}
    assert {fid: ledger[fid]["status"] for fid in CONTROLS} == {fid: "gfp_negative_control" for fid in CONTROLS}
    assert ledger["a1x"]["status"] == "no_selected_values" and ledger["a1x"]["gfp_gate_unselected_observations"] == 1
    assert all(not any(fid in CONTROLS for fid in row["field_ids"]) for row in result["unit_ledger"])
    assert all(row["field_id"] not in CONTROLS for row in result["plot_data"])
    assert result["missingness"] == []
    record = result["selection"]["gfp_gate"]
    assert record["nuclei"] == {"above_control_threshold": 11, "negative_control": 50,
                                "too_few_control_nuclei": 1, "within_control_range": 7}
    assert record["observations"] == 69 and record["kept_observations"] == 11


def test_negative_selection_keeps_only_nuclei_within_the_control_range():
    report, config = nuclear_fixture()
    result = analyze_region_comparison(report, config, request(filter_=gate("negative")))
    assert units(result) == NEGATIVE_UNITS
    a, b = [NEGATIVE_UNITS[u] for u in ("a1", "a2", "a3")], [NEGATIVE_UNITS[u] for u in ("b1", "b2", "b3")]
    assert result["comparisons"][0]["p_value"] == pytest.approx(stats.ttest_ind(a, b, equal_var=False).pvalue)
    reasons = {row["gfp_gate_reason"] for row in result["plot_data"]}
    assert reasons == {"within_control_range"}


def test_without_the_filter_requests_and_results_are_unchanged():
    report, config = nuclear_fixture()
    plain = request()
    assert "gfp_gate" not in plain.model_dump(mode="json")["selection"]
    assert plain == request(filter_=None)
    result = analyze_region_comparison(report, config, plain)
    text = json.dumps(result)
    assert "gfp_gate" not in text and "gfp_negative_control" not in text and "gfp_mean" not in text
    # Without a gate, control-condition fields are simply out of scope.
    assert units(result) == ALL_UNITS
    assert result["selection"] == {"input_rows": 69, "out_of_scope": 50, "selected": 19}
    explicit_none = RegionSelection.model_validate({"source": "region", "region_set_id": "nuclei", "channel_id": "ncl",
                                                    "metric": "mean", "gfp_gate": None})
    assert explicit_none.model_dump(mode="json") == plain.selection.model_dump(mode="json")


def test_excluded_nuclei_remain_excluded_and_not_control_values():
    exclusions = [{"field_id": "b1", "region_id": 3, "region_set_id": "nuclei", "reason": "Out of focus"},
                  {"field_id": "c1", "region_id": 25, "region_set_id": "nuclei", "reason": "Debris"}]
    report, config = nuclear_fixture(exclusions=exclusions)
    result = analyze_region_comparison(report, config, request(filter_=gate()))
    record = result["selection"]["gfp_gate"]
    # 24 controls on d1 (100..123): 100 + 0.99 * 23.
    assert record["dates"]["d1"]["control_nuclei"] == 24
    assert record["dates"]["d1"]["threshold"] == pytest.approx(122.77, abs=1e-12)
    row = next(r for r in result["observation_ledger"] if r["field_id"] == "b1" and r["region_id"] == 3)
    assert row["selection_status"] == "excluded" and row["gfp_gate_reason"] == "nucleus_excluded"
    assert units(result)["b1"] == 42.0


@pytest.mark.parametrize(("change", "code"), [
    (lambda r, c, g: g.update(control_field_ids=["missing"]), "gfp_gate_unknown_control_field"),
    (lambda r, c, g: g.update(gfp_channel_id="dapi"), "gfp_gate_channel_unknown"),
    (lambda r, c, g: c["field_snapshot"]["b2"]["metadata"].update(acquisition_date=None), "gfp_gate_acquisition_date_required"),
    (lambda r, c, g: (r["recipe"].update(source="manual"), c["recipe"].update(source="manual")), "gfp_gate_nuclear_source_unbound"),
    (lambda r, c, g: [r["exclusions"].append(e) or c["exclusions"].append(e)
                      for e in [{"field_id": "c2", "region_id": None, "region_set_id": "nuclei", "reason": "Blur"}]],
     "gfp_gate_control_field_excluded"),
])
def test_refusals_have_safe_codes(change, code):
    report, config = nuclear_fixture()
    filter_ = gate()
    change(report, config, filter_)
    with pytest.raises(ValueError, match=code):
        analyze_region_comparison(report, config, request(filter_=filter_))


def test_units_without_kept_nuclei_and_control_only_conditions_are_refused():
    fields = {**CONTROLS, **MEASURED, "b2": ("B", "b2", "d1", [(80, 600)])}
    report, config = nuclear_fixture(fields)
    with pytest.raises(ValueError, match="gfp_gate_unit_without_selected_nuclei"):
        analyze_region_comparison(report, config, request(filter_=gate()))
    report, config = nuclear_fixture()
    with pytest.raises(ValueError, match="gfp_gate_condition_only_control_fields"):
        analyze_region_comparison(report, config, request(filter_=gate(), conditions=("A", "control")))


def test_tampered_or_unbound_nuclear_identity_is_refused():
    report, config = nuclear_fixture()
    nuclear = same_revision_nuclear_source(report, config["field_snapshot"])
    nuclear["fields"]["a2"]["mask_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="gfp_gate_nuclear_identity_mismatch"):
        analyze_region_comparison(report, config, request(filter_=gate()), nuclear=nuclear)
    nuclear = copy.deepcopy(same_revision_nuclear_source(report, config["field_snapshot"]))
    nuclear["fields"]["a2"]["table"]["rows"] = [row for row in nuclear["fields"]["a2"]["table"]["rows"]
                                                if row["region_id"] != 2]
    with pytest.raises(ValueError, match="gfp_gate_nuclear_identity_mismatch"):
        analyze_region_comparison(report, config, request(filter_=gate()), nuclear=nuclear)
    nuclear = same_revision_nuclear_source(report, config["field_snapshot"])
    with pytest.raises(ValueError, match="gfp_gate_nuclear_source_unbound"):
        analyze_region_comparison(report, config, request(filter_=gate()), nuclear={**nuclear, "binding": "parent_nucleus"})
    del nuclear["fields"]["b3"]
    with pytest.raises(ValueError, match="gfp_gate_nuclear_source_unbound"):
        analyze_region_comparison(report, config, request(filter_=gate()), nuclear=nuclear)


@pytest.mark.parametrize("changes", [{"percentile": 100}, {"percentile": 49.9}, {"percentile": "99"},
                                     {"control_field_ids": ["c1", "c1"]}, {"control_field_ids": []},
                                     {"version": "2.0.0"}, {"gate_protocol": "gfp-gate/1.0.0"}, {"keep": "all"},
                                     {"threshold": 5}])
def test_filter_contract_is_explicit(changes):
    with pytest.raises(ValidationError):
        request(filter_=gate(**changes))
    with pytest.raises(ValidationError):
        request(filter_={key: value for key, value in gate().items() if key != "keep"})


def test_filter_is_refused_where_it_is_not_defined():
    raw = request(filter_=gate()).model_dump(mode="json")
    v1 = {key: raw[key] for key in ("mode", "selection", "design", "conditions", "comparison_family",
                                    "acquisition_review", "missingness_confirmed")}
    with pytest.raises(ValidationError, match="gfp_gate_unsupported_request"):
        RegionComparisonRequest.model_validate(v1)
    with pytest.raises(ValidationError, match="gfp_gate_unsupported_request"):
        RegionAssociationRequest.model_validate({
            "mode": "region-association", "version": "1.0.0", "x_selection": raw["selection"],
            "y_selection": {**raw["selection"], "channel_id": "dna"}, "design": raw["design"],
            "conditions": ["A", "B"], "acquisition_review": raw["acquisition_review"],
            "missingness_confirmed": True, "method": "spearman"})


def test_gfp_association_v11_uses_identical_nuclei_for_both_axes_and_replays(tmp_path):
    report, config = nuclear_fixture()
    raw = request(filter_=gate()).model_dump(mode="json")
    association = {"mode": "region-association", "version": "1.1.0", "x_selection": {**raw["selection"], "channel_id": "gfp"},
        "y_selection": raw["selection"], "design": raw["design"], "conditions": ["A", "B"],
        "acquisition_review": raw["acquisition_review"], "missingness_confirmed": True, "method": "spearman"}
    result = analyze_region_association(report, config, association)
    assert result["region_association_version"] == "1.1.0"
    expected_gfp = {"a1": 300., "a2": 400., "a3": 359.5, "b1": 300., "b2": 250., "b3": 300.}
    assert {r["experimental_unit"]: (r["x"], r["y"]) for r in result["unit_summary"]} == {
        key: (expected_gfp[key], value) for key, value in POSITIVE_UNITS.items()}
    x_ids = {(r["field_id"], r["region_id"]) for r in result["x_source"]["plot_data"]}
    y_ids = {(r["field_id"], r["region_id"]) for r in result["y_source"]["plot_data"]}
    assert x_ids == y_ids and len(x_ids) == 11
    for row in result["associations"]:
        keys = sorted(key for key in POSITIVE_UNITS if key.startswith(row["scope"].lower()))
        expected = stats.spearmanr([expected_gfp[key] for key in keys], [POSITIVE_UNITS[key] for key in keys])
        assert row["coefficient"] == pytest.approx(expected.statistic)
        # n=3: the exact permutation two-sided p is 1 for both correlations.
        assert row["p_value"] == pytest.approx(1.0)
    result["figure"] = render_common_statistics(result, tmp_path)
    assert _recompute_statistics(report, config, result) == {key: value for key, value in result.items() if key != "figure"}
    with pytest.raises(ValidationError, match="matched_gfp_selection"):
        RegionAssociationRequest.model_validate({**association, "y_selection": {**raw["selection"], "gfp_gate": gate(keep="negative")}})
    with pytest.raises(ValidationError, match="matched_intensity_policy"):
        RegionAssociationRequest.model_validate({**association, "y_selection": {**raw["selection"], "metric": "mean_corrected"}})


def test_methods_caption_and_export_record_the_gate(tmp_path):
    report, config = nuclear_fixture()
    config = {**config, "review_record": {"confirmed_at": 1.0}}
    result = analyze_region_comparison(report, config, request(filter_=gate()))
    result["revision_id"] = report["revision_id"]
    manifest = render_common_statistics(result, tmp_path)
    methods = (tmp_path / "methods.md").read_text(encoding="utf-8")
    caption = (tmp_path / "figure-caption.md").read_text(encoding="utf-8")
    for text in (methods, caption):
        assert "GFP gate filter 1.0.0 with protocol gfp-gate/2.0.0" in text
        assert "Only GFP-positive nuclei were analysed." in text
        assert "d1: threshold 123.76 from 25 control nuclei" in text
        assert "d3: threshold not defined from 5 control nuclei (too_few_control_nuclei)" in text
        assert "99th percentile" in text and "c1, c2, c3" in text
    assert "observations.csv" in manifest["source_files"]
    assert "gfp_gate_reason" in (tmp_path / "observations.csv").read_text(encoding="utf-8")
    result["figure"] = manifest
    regenerated = _recompute_statistics(report, config, result)
    assert regenerated == {key: value for key, value in result.items() if key != "figure"}


def test_gated_per_field_description_labels_controls_and_records_thresholds(tmp_path):
    report, config = nuclear_fixture()
    spec = parse_descriptive_request({"mode": "descriptive", "selection": {
        "source": "region", "region_set_id": "nuclei", "channel_id": "ncl", "metric": "mean", "gfp_gate": gate()},
        "plot": {"preset": "nature-double"}, "figure_policy": {"version": "2.0.0", "layout": "field-pages"}})
    result = describe_regions(report, config["field_snapshot"], spec)
    summary = {row["field_id"]: row for row in result["field_summary"]}
    assert {fid: summary[fid]["status"] for fid in CONTROLS} == {fid: "gfp_negative_control" for fid in CONTROLS}
    assert summary["a1"]["median"] == 12.0 and summary["a1"]["gate_unselected"] == 1
    assert summary["b3"]["median"] == 61.0 and summary["a1x"]["status"] == "no_selected_values"
    assert result["counts"]["observations"] == 11
    assert result["selection"]["gate_unselected"] == 58
    assert result["selection"]["gfp_gate"]["dates"]["d2"]["threshold"] == pytest.approx(218.81, abs=1e-12)
    record = next(r for r in result["selection"]["records"] if r["observation_id"] == json.dumps(["a1", "nuclei", 3],
                                                                                                    separators=(",", ":")))
    assert record["gfp_gate_reason"] == "within_control_range" and record["gate_selected"] is False
    plain = describe_regions(report, config["field_snapshot"], DescriptiveRequest.model_validate(
        {"mode": "descriptive", "selection": {"source": "region", "region_set_id": "nuclei", "channel_id": "ncl", "metric": "mean"}}))
    assert all(key not in json.dumps(plain) for key in ('"gfp_gate"', "gfp_mean", "gfp_gate_reason", "gfp_negative_control"))
    result["revision_id"] = report["revision_id"]
    manifest = render_descriptive_output(result, tmp_path, methods_template=CURRENT_METHODS_TEMPLATE)
    assert manifest["status"] == "ready"
    for name in ("methods.md", "figure-caption.md"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert "GFP gate filter 1.0.0" in text and "d1: threshold 123.76 from 25 control nuclei" in text


# Nucleoplasm (compartment-summary) observations keyed by parent nucleus ID.
def compartment_fixture():
    fields = {**CONTROLS, **{key: value for key, value in MEASURED.items() if key != "a1x"}}
    recipe = {"id": "region-2d", "version": "1.4.0", "region_set_id": "nucleoplasm", "label": "Nucleoplasm",
              "source": "fiji_nuclear_compartment", "compartment": "nucleoplasm", "nuclear_revision_id": "rev_nuclei",
              "nuclear_channel_id": "dna", "defining_channel_id": "ncl", "nucleolar_revision_id": "rev_nucleoli"}
    report = {"analysis_kind": "region-2d", "revision_id": "rev_np", "recipe": copy.deepcopy(recipe), "field_tables": {},
              "field_failures": [], "excluded_failed_fields": [], "exclusions": []}
    snapshot, summaries, nuclear_fields = {}, {}, {}
    for fid, (condition, unit, date, nuclei) in fields.items():
        # Each nucleus is 1 x 3 pixels: one nucleolus pixel (NCL 2) and two nucleoplasm pixels (NCL 2 * 2**k),
        # so log2(nucleoplasm / nucleolus) = k = ncl % 5 exactly; GFP is uniform within the nucleus.
        width = 4 * len(nuclei) + 1
        nuclei_labels = np.zeros((3, width), np.uint32)
        nucleoli = np.zeros_like(nuclei_labels)
        planes = {c.channel_id: np.full((3, width), 5, np.uint16) for c in CHANNELS}
        for index, (gfp, ncl) in enumerate(nuclei):
            col = 4 * index + 1
            nuclei_labels[1, col:col + 3] = index + 1
            nucleoli[1, col] = index + 1
            planes["gfp"][1, col:col + 3] = gfp
            planes["ncl"][1, col] = 2
            planes["ncl"][1, col + 1:col + 3] = 2 * 2 ** (ncl % 5)
            planes["dna"][1, col:col + 3] = 500
        plasm = np.where((nuclei_labels > 0) & (nucleoli == 0), nuclei_labels, 0).astype(np.uint32)
        background = np.zeros(plasm.shape, bool)
        background[0] = True
        masks = {c.channel_id: background for c in CHANNELS}
        backgrounds = tuple(BackgroundSpec(channel_id=c.channel_id, roi_revision_id=f"bg_{fid}", confirmed=True)
                            for c in CHANNELS)
        spec = RegionMeasurementSpec(
            field_id=fid, analysis_revision_id="rev_np", channels=CHANNELS, backgrounds=backgrounds,
            region_set=RegionSetSpec(region_set_id="nucleoplasm", label="Nucleoplasm", mask_revision_id="rev_np",
                                     source="fiji_nuclear_compartment", defining_channel_id="ncl"))
        report["field_tables"][fid] = measure_regions(planes, plasm, masks, spec).model_dump(mode="json")
        summaries[fid] = json.loads(json.dumps({"nucleolar_revision": {"revision_id": "rev_nucleoli"}, "channels": {
            cid: compartment_summary(nuclei_labels, nucleoli, plasm, image) for cid, image in planes.items()}}))
        snapshot[fid] = {"metadata": {"condition": condition, "experimental_unit": unit, "sample": f"s_{unit}",
                                      "acquisition_date": date, "pair": None},
                         "image_info": {"shape": [3, width], "calibration": None,
                                        "channels": [c.model_dump(mode="json") for c in CHANNELS]}}
        nuclear_spec = RegionMeasurementSpec(
            field_id=fid, analysis_revision_id="rev_nuclei", channels=CHANNELS, backgrounds=backgrounds,
            region_set=RegionSetSpec(region_set_id="nuclei", label="Nuclei", mask_revision_id="rev_nuclei",
                                     source="stardist_nuclear", defining_channel_id="dna"))
        table = measure_regions(planes, nuclei_labels, masks, nuclear_spec).model_dump(mode="json")
        nuclear_fields[fid] = {"revision_id": "rev_nuclei", "table": table, "mask_revision_id": "rev_nuclei",
                               "mask_sha256": table["mask_sha256"], "exclusions": [],
                               "image_info": copy.deepcopy(snapshot[fid]["image_info"])}
    config = {"field_ids": list(snapshot), "field_snapshot": snapshot, "recipe": copy.deepcopy(recipe),
              "backgrounds": {}, "exclusions": [], "review_record": {"confirmed_at": 123.0}}
    return report, config, summaries, {"binding": "parent_nucleus", "fields": nuclear_fields}


def compartment_request(metric="nucleolar_area_fraction"):
    selection = {"source": "compartment-summary", "region_set_id": "nucleoplasm", "metric": metric,
                 "channel_id": "ncl" if metric.startswith("log2") else None, "gfp_gate": gate()}
    return request(selection=selection)


def test_nucleoplasm_summary_rows_join_their_parent_nucleus_gfp_exactly():
    report, config, summaries, nuclear = compartment_fixture()
    result = analyze_region_comparison(report, config, compartment_request("log2_nucleoplasm_over_nucleolus"),
                                       summaries=summaries, nuclear=nuclear)
    # Kept (positive) nuclei, k = ncl % 5: a1 {0, 4}, a2 {0}, a3 {0, 4}, b1 {0, 4, 3}, b2 {0}, b3 {0, 2}.
    assert units(result) == {"a1": 2.0, "a2": 0.0, "a3": 2.0, "b1": 3.0, "b2": 0.0, "b3": 1.0}
    record = result["selection"]["gfp_gate"]
    assert record["nuclear_binding"] == "parent_nucleus"
    assert record["nuclear_sources"]["a1"]["revision_id"] == "rev_nuclei"
    assert record["dates"]["d1"]["threshold"] == pytest.approx(123.76, abs=1e-12)
    description = describe_compartment_summary(report, config["field_snapshot"], DescriptiveRequest.model_validate(
        {"mode": "descriptive", "selection": compartment_request().selection.model_dump(mode="json")}), summaries, nuclear)
    assert description["counts"]["observations"] == 11
    assert {row["value"] for row in description["plot_data"]} == {1 / 3}
    region = request(selection={"source": "region", "region_set_id": "nucleoplasm", "channel_id": "ncl",
                                "metric": "mean", "gfp_gate": gate()})
    assert len(analyze_region_comparison(report, config, region, nuclear=nuclear)["plot_data"]) == 11
    with pytest.raises(ValueError, match="gfp_gate_nuclear_source_unbound"):
        analyze_region_comparison(report, config, compartment_request(), summaries=summaries)
    with pytest.raises(ValueError, match="gfp_gate_nuclear_source_unbound"):
        analyze_region_comparison(report, config, compartment_request(), summaries=summaries,
                                  nuclear={**nuclear, "binding": "same_revision"})
    bad = copy.deepcopy(nuclear)
    for row in bad["fields"]["b2"]["table"]["rows"]:
        if row["region_id"] == 1:
            row["area_px"] = 4
    with pytest.raises(ValueError, match="gfp_gate_nuclear_identity_mismatch"):
        analyze_region_comparison(report, config, compartment_request(), summaries=summaries, nuclear=bad)
    for row in bad["fields"]["b2"]["table"]["rows"]:
        if row["region_id"] == 1:
            row["area_px"] = 2  # a nucleoplasm region must lie strictly inside its parent nucleus
    with pytest.raises(ValueError, match="gfp_gate_nuclear_identity_mismatch"):
        analyze_region_comparison(report, config, region, nuclear=bad)
    bad = copy.deepcopy(nuclear)
    bad["fields"]["b2"]["image_info"]["channels"][1]["stain"] = "mCherry"
    with pytest.raises(ValueError, match="gfp_gate_nuclear_identity_mismatch"):
        analyze_region_comparison(report, config, region, nuclear=bad)


def test_missing_gfp_value_is_unselected_with_its_reason_never_positive_or_zero():
    report, config = nuclear_fixture()
    nuclear = copy.deepcopy(same_revision_nuclear_source(report, config["field_snapshot"]))
    for row in nuclear["fields"]["b1"]["table"]["rows"]:
        if row["region_id"] == 1 and row["channel_id"] == "gfp":
            row["mean"] = float("nan")
    for keep, expected in (("positive", 46.0), ("negative", 500.0)):
        result = analyze_region_comparison(report, config, request(filter_=gate(keep)), nuclear=nuclear)
        row = next(r for r in result["observation_ledger"] if r["field_id"] == "b1" and r["region_id"] == 1)
        assert (row["selection_status"], row["gfp_gate_reason"], row["gfp_mean"]) == ("gfp_gate_unselected", "gfp_missing", None)
        assert units(result)["b1"] == expected
        assert result["selection"]["gfp_gate"]["nuclei"]["gfp_missing"] == 1
