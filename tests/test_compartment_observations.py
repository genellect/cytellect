"""Per-nucleus compartment-summary selection 1.0.0 through the unchanged unit and descriptive protocols.

Synthetic original pixels only. Expected values are computed by hand from the
chosen intensities (powers of two give exact log2 values), not by the code under test.
"""
import copy
import json
import math

import numpy as np
import pytest
from cytellect_analysis.common_statistics import analyze_region_comparison
from cytellect_analysis.common_statistics_contracts import RegionComparisonRequestV2
from cytellect_analysis.common_statistics_figures import render_common_statistics
from cytellect_analysis.compartment_observations import describe_compartment_summary, summary_sha256
from cytellect_analysis.compartment_summary import compartment_summary
from cytellect_analysis.descriptive_contracts import CompartmentSummarySelection
from cytellect_analysis.descriptive_figures import render_descriptive
from cytellect_analysis.region_exports import _recompute_statistics
from cytellect_analysis.regions import (
    BackgroundSpec,
    ChannelSpec,
    RegionMeasurementSpec,
    RegionSetSpec,
    measure_regions,
)
from pydantic import ValidationError
from scipy import stats

# log2(nucleoplasm mean / nucleolar mean) -> (nucleoplasm pixel, nucleolus pixel)
PIXELS = {1: (32, 16), 0: (32, 32), -1: (16, 32), -2: (16, 64)}
CHANNELS = (ChannelSpec(channel_id="ncl", label="NCL", stain="anti-nucleolin", identity_confirmed=True),
            ChannelSpec(channel_id="dna", label="DNA", stain="Hoechst", identity_confirmed=True))
RECIPE = {"id": "region-2d", "version": "1.4.0", "region_set_id": "nucleoplasm", "label": "Nucleoplasm",
          "source": "fiji_nuclear_compartment", "compartment": "nucleoplasm", "nuclear_revision_id": "rev_nuclei",
          "nuclear_channel_id": "dna", "defining_channel_id": "ncl", "nucleolar_revision_id": "rev_nucleoli"}
# condition -> unit -> two fields of per-nucleus log2 values; None = nucleus without a nucleolus.
# ("x", 1) marks a nucleus that is explicitly excluded in the nucleoplasm revision.
DESIGN = {
    "A": {"a1": [[-1, -1], [-2, 0, ("x", 1)]], "a2": [[-2, -2], [-1, -1, None]], "a3": [[0, 0], [-1, -1]]},
    "B": {"b1": [[0, 0], [1, 1]], "b2": [[1, 1], [1, 1]], "b3": [[0, 0], [0, 0]]},
}
# Hand calculation: field medians -> sample (= unit, one sample of two fields) means.
UNIT_MEANS = {"a1": -1.0, "a2": -1.5, "a3": -0.5, "b1": 0.5, "b2": 1.0, "b3": 0.0}


def field_arrays(values, double=()):
    width = 4 * len(values) + 1
    nuclei = np.zeros((8, width), np.uint32)
    nucleoli = np.zeros_like(nuclei)
    ncl = np.zeros((8, width), np.uint16)
    dna = np.zeros_like(ncl)
    next_child = 1
    for index, value in enumerate(values):
        nid, col = index + 1, 4 * index
        nuclei[1:4, col:col + 3] = nid
        dna[1:4, col:col + 3] = 100
        value = value[1] if isinstance(value, tuple) else value
        if value is None:
            ncl[1:4, col:col + 3] = 40
            continue
        plasm, nucleolus = PIXELS[value]
        ncl[1:4, col:col + 3] = plasm
        nucleoli[2, col + 1] = next_child
        ncl[2, col + 1] = nucleolus
        next_child += 1
        if index in double:
            nucleoli[1, col + 1] = next_child
            ncl[1, col + 1] = nucleolus
            next_child += 1
    plasm = np.where((nuclei > 0) & (nucleoli == 0) & np.isin(nuclei, np.unique(nuclei[nucleoli > 0])), nuclei, 0)
    return nuclei, nucleoli, plasm.astype(np.uint32), {"ncl": ncl, "dna": dna}


def compartment_fixture(design=DESIGN, double=None):
    report = {"analysis_kind": "region-2d", "revision_id": "rev_np", "recipe": copy.deepcopy(RECIPE),
              "field_tables": {}, "field_failures": [], "excluded_failed_fields": [], "exclusions": []}
    snapshot, summaries = {}, {}
    for condition, units in design.items():
        for unit, fields in units.items():
            for index, values in enumerate(fields):
                fid = f"{unit}f{index + 1}"
                nuclei, nucleoli, plasm, channels = field_arrays(values, (double or {}).get(fid, ()))
                background = np.zeros(nuclei.shape, bool)
                background[6] = True
                spec = RegionMeasurementSpec(
                    field_id=fid, analysis_revision_id="rev_np",
                    region_set=RegionSetSpec(region_set_id="nucleoplasm", label="Nucleoplasm", mask_revision_id="rev_np",
                                             source="fiji_nuclear_compartment", defining_channel_id="ncl"),
                    channels=CHANNELS, backgrounds=tuple(BackgroundSpec(channel_id=c.channel_id, roi_revision_id=f"bg_{fid}",
                                                                        confirmed=True) for c in CHANNELS))
                table = measure_regions(channels, plasm, {c.channel_id: background for c in CHANNELS}, spec)
                report["field_tables"][fid] = table.model_dump(mode="json")
                summaries[fid] = json.loads(json.dumps({
                    "nucleolar_revision": {"revision_id": "rev_nucleoli"},
                    "channels": {cid: compartment_summary(nuclei, nucleoli, plasm, image) for cid, image in channels.items()}}))
                for position, value in enumerate(values):
                    if isinstance(value, tuple):
                        report["exclusions"].append({"field_id": fid, "region_id": position + 1,
                                                     "region_set_id": "nucleoplasm", "reason": "Out of focus"})
                snapshot[fid] = {"metadata": {"condition": condition, "experimental_unit": unit, "sample": f"s_{unit}",
                                              "acquisition_date": "batch-1", "pair": None},
                                 "image_info": {"shape": list(nuclei.shape), "calibration": None,
                                                "channels": [c.model_dump(mode="json") for c in CHANNELS]}}
    config = {"field_ids": list(snapshot), "field_snapshot": snapshot, "recipe": copy.deepcopy(RECIPE), "backgrounds": {},
              "exclusions": copy.deepcopy(report["exclusions"]), "review_record": {"confirmed_at": 123.0}}
    return report, config, summaries


def selection(metric="log2_nucleoplasm_over_nucleolus"):
    return {"source": "compartment-summary", "region_set_id": "nucleoplasm",
            "channel_id": "ncl" if metric.startswith("log2") else None, "metric": metric}


def request(test="welch-t", metric="log2_nucleoplasm_over_nucleolus", **changes):
    return RegionComparisonRequestV2.model_validate({
        "mode": "region-experimental-unit", "version": "2.0.0", "test": test, "selection": selection(metric),
        "design": {"kind": "independent", "confirmed": True, "unit_definition": "Independently treated cultures"},
        "conditions": ["A", "B"], "comparison_family": {"family_id": "primary", "kind": "control", "control": "A",
                                                        "contrasts": [["A", "B"]]},
        "acquisition_review": {"confirmed": True, "basis": "same-settings", "spatial_sampling_confirmed": True},
        "missingness_confirmed": True, "plot": {"preset": "nature-double"}, **changes})


def test_unit_means_and_welch_match_hand_calculation_and_scipy():
    report, config, summaries = compartment_fixture()
    result = analyze_region_comparison(report, config, request(), summaries=summaries)
    units = {row["experimental_unit"]: row["value"] for row in result["unit_summary"]}
    assert units == UNIT_MEANS
    a, b = [UNIT_MEANS[u] for u in ("a1", "a2", "a3")], [UNIT_MEANS[u] for u in ("b1", "b2", "b3")]
    contrast = result["comparisons"][0]
    assert contrast["estimate"] == -1.5
    assert contrast["standard_error"] == pytest.approx(math.sqrt(1 / 6))
    assert contrast["degrees_of_freedom"] == pytest.approx(4)
    reference = stats.ttest_ind(a, b, equal_var=False)
    assert contrast["statistic"] == pytest.approx(reference.statistic)
    assert contrast["p_value"] == pytest.approx(reference.pvalue)
    assert contrast["p_holm"] == contrast["p_value"]
    assert result["metric"] == "log2_nucleoplasm_over_nucleolus" and result["unit"] == "log2 ratio"
    assert result["channel"]["stain"] == "anti-nucleolin"
    # 26 nuclei: 1 excluded, 1 without a nucleolus (missing with reason, never zero), 24 selected.
    assert result["selection"] == {"input_rows": 26, "selected": 24, "excluded": 1, "missing": 1}
    assert result["missingness"] == [{"observation_id": '["a2f2","nucleoplasm",3]', "field_id": "a2f2",
                                      "reason": "no_nucleolus"}]
    excluded = [row for row in result["observation_ledger"] if row["selection_status"] == "excluded"]
    assert [(row["field_id"], row["nucleus_id"], row["value"]) for row in excluded] == [("a1f2", 3, 1.0)]
    assert all(row["value"] != 0 or row["selection_status"] == "selected" for row in result["observation_ledger"])
    assert "nucleolar_union_saturation_not_assessed" in result["warnings"]
    source = {field["field_id"]: field["compartment_summary"] for field in result["source_fields"]}
    assert source["a1f1"]["sha256"] == summary_sha256(summaries["a1f1"])
    assert source["a1f1"]["protocol"] == "compartment-summary/1.0.0"


def test_rank_test_and_exclusion_is_honoured():
    report, config, summaries = compartment_fixture()
    result = analyze_region_comparison(report, config, request("mann-whitney-u"), summaries=summaries)
    contrast = result["comparisons"][0]
    assert contrast["statistic"] == 0 and contrast["p_value"] == pytest.approx(2 / math.comb(6, 3))
    # Without the exclusion the excluded nucleus (log2=1) moves a1f2's median from -1 to 0.
    report["exclusions"], config["exclusions"] = [], []
    unexcluded = analyze_region_comparison(report, config, request(), summaries=summaries)
    assert {r["experimental_unit"]: r["value"] for r in unexcluded["unit_summary"]}["a1"] == -0.5


def test_paired_design_uses_matched_unit_differences():
    design = {"A": {"p1a": [[-1, -1]], "p2a": [[-2, -2]], "p3a": [[0, 0]]},
              "B": {"p1b": [[0, 0]], "p2b": [[1, 1]], "p3b": [[0, 0]]}}
    report, config, summaries = compartment_fixture(design)
    for fid, field in config["field_snapshot"].items():
        field["metadata"]["pair"] = fid[:2]
    paired = request("paired-t", design={"kind": "paired", "confirmed": True, "unit_definition": "Matched cultures",
                                          "pairing_basis": "Split before treatment"})
    result = analyze_region_comparison(report, config, paired, summaries=summaries)
    reference = stats.ttest_rel([-1, -2, 0], [0, 1, 0])
    assert result["comparisons"][0]["estimate"] == pytest.approx(-4 / 3)
    assert result["comparisons"][0]["p_value"] == pytest.approx(reference.pvalue)


def test_count_and_fraction_are_channel_neutral_and_candidate_free_nuclei_are_missing():
    report, config, summaries = compartment_fixture(double={"a1f1": (0,)})
    count = analyze_region_comparison(report, config, request("mann-whitney-u", metric="nucleolar_count"),
                                       summaries=summaries)
    by_unit = {r["experimental_unit"]: r["value"] for r in count["unit_summary"]}
    # a1f1 nuclei have 2 and 1 nucleoli -> median 1.5; a1f2 -> 1; unit mean 1.25.
    assert by_unit["a1"] == 1.25 and by_unit["b1"] == 1.0
    assert count["channel"] is None and count["unit"] == "count"
    assert [m["reason"] for m in count["missingness"]] == ["no_nucleolus"]
    fraction = analyze_region_comparison(report, config, request("mann-whitney-u", metric="nucleolar_area_fraction"),
                                          summaries=summaries)
    assert {r["experimental_unit"]: r["value"] for r in fraction["unit_summary"]}["a1"] == pytest.approx(
        ((2 / 9 + 1 / 9) / 2 + 1 / 9) / 2)
    with pytest.raises(ValueError, match="incompatible_sampling"):
        analyze_region_comparison(report, config, request(metric="nucleolar_count", acquisition_review={
            "confirmed": True, "basis": "same-settings", "spatial_sampling_confirmed": False}), summaries=summaries)


@pytest.mark.parametrize("raw,error", [
    ({**selection(), "channel_id": None}, "compartment_summary_channel_required"),
    ({**selection("nucleolar_count"), "channel_id": "ncl"}, "compartment_summary_channel_must_be_unset"),
    ({**selection(), "metric": "mean"}, "literal_error"),
])
def test_selection_contract_is_explicit(raw, error):
    with pytest.raises(ValidationError, match=error):
        CompartmentSummarySelection.model_validate(raw)


def _tamper_area(s):
    s["a1f1"]["channels"]["ncl"]["rows"][0]["nucleoplasm_area_px"] -= 1


def _tamper_ratio(s):
    s["a1f1"]["channels"]["ncl"]["rows"][0]["log2_nucleoplasm_over_nucleolus"] = 0.5


def _zero_missing(s):
    s["a2f2"]["channels"]["ncl"]["rows"][2]["log2_nucleoplasm_over_nucleolus"] = 0.0


def _background(s):
    s["a1f1"]["channels"]["ncl"]["rows"][0]["values"] = "background_corrected"


def _drop_channel(s):
    s["a1f1"]["channels"].pop("dna")


@pytest.mark.parametrize("mutate,error", [
    (lambda s: s.pop("a1f1"), "compartment_summary_coverage_mismatch"),
    (lambda s: s.clear(), "compartment_summary_unavailable"),
    (_tamper_area, "compartment_summary_inconsistent"),
    (_tamper_ratio, "compartment_summary_inconsistent"),
    (_zero_missing, "compartment_summary_inconsistent"),
    (_background, "compartment_summary_background_unsupported"),
    (_drop_channel, "compartment_summary_channel_mismatch"),
])
def test_summary_must_match_saved_source(mutate, error):
    report, config, summaries = compartment_fixture()
    mutate(summaries)
    with pytest.raises(ValueError, match=error):
        analyze_region_comparison(report, config, request(), summaries=summaries)


def test_summary_is_bound_to_the_reviewed_nucleoplasm_mask():
    report, config, summaries = compartment_fixture()
    other = compartment_fixture({"A": {"a1": [[-1, -1, -1], [-2, 0, ("x", 1)]]}})[2]["a1f1"]
    summaries["a1f1"] = other
    with pytest.raises(ValueError, match="compartment_summary_mask_mismatch"):
        analyze_region_comparison(report, config, request(), summaries=summaries)


def test_paged_descriptive_output_with_current_methods_template(tmp_path):
    from cytellect_analysis.descriptive_output import render_descriptive_output
    from cytellect_analysis.statistical_methods import CURRENT_METHODS_TEMPLATE

    report, config, summaries = compartment_fixture()
    described = describe_compartment_summary(report, config["field_snapshot"], {
        "mode": "descriptive", "selection": selection("nucleolar_area_fraction"),
        "plot": {"preset": "nature-double"}, "figure_policy": {"version": "2.0.0", "layout": "field-pages"}}, summaries)
    described["revision_id"] = "rev_np"
    figure = render_descriptive_output(described, tmp_path, methods_template=CURRENT_METHODS_TEMPLATE)
    assert figure["status"] == "ready" and len(figure["pages"]) == 2
    methods = (tmp_path / "methods.md").read_text(encoding="utf-8")
    assert "adopted nucleolar-union area / parent nucleus area" in methods
    assert "missingness.csv" in figure["files"]


def test_non_compartment_revision_is_refused():
    report, config, summaries = compartment_fixture()
    for recipe in (report["recipe"], config["recipe"]):
        recipe["nucleolar_revision_id"] = None
    with pytest.raises(ValueError, match="compartment_summary_source_required"):
        analyze_region_comparison(report, config, request(), summaries=summaries)


def test_per_field_description_figure_and_export_requires_bound_summary(tmp_path):
    report, config, summaries = compartment_fixture()
    described = describe_compartment_summary(report, config["field_snapshot"], {
        "mode": "descriptive", "selection": selection(), "plot": {"preset": "nature-double"}}, summaries)
    fields = {row["field_id"]: row for row in described["field_summary"]}
    assert fields["a1f2"]["median"] == -1 and fields["a1f2"]["excluded"] == 1
    assert fields["a2f2"]["missing_metric_selected"] == 1 and fields["a2f2"]["selected_rows"] == 2
    assert fields["b2f1"]["median"] == 1 and described["observation_kind"] == "nuclei"
    assert described["metric_definition"].startswith("log2(mean nucleoplasm intensity / mean nucleolar-union")
    described["revision_id"] = "rev_np"
    figure = render_descriptive(described, tmp_path / "descriptive")
    caption = (tmp_path / "descriptive" / "figure-caption.md").read_text(encoding="utf-8")
    assert "Per-nucleus compartment-summary value" in caption and "stain=anti-nucleolin" in caption
    assert "figure.svg" in figure["source_files"]
    compared = analyze_region_comparison(report, config, request(), summaries=summaries)
    common = render_common_statistics(compared, tmp_path / "common")
    methods = (tmp_path / "common" / "methods.md").read_text(encoding="utf-8")
    assert "compartment-summary value (selection 1.0.0)" in methods and "figure.svg" in common["source_files"]
    # Summary export is supported, but this call deliberately supplies no pinned
    # parent dependencies. Export must not infer or omit its source summaries.
    with pytest.raises(ValueError, match="compartment_summary_unavailable"):
        _recompute_statistics(report, config, {**compared, "figure": common})


def test_existing_region_selection_is_unchanged():
    from test_common_statistics import request_v2
    from test_region_comparison import comparison_fixture

    report, config = comparison_fixture()
    assert analyze_region_comparison(report, config, request_v2()) == analyze_region_comparison(
        report, config, request_v2(), summaries={"ignored": {}})



def test_worker_saved_summary_is_located_bound_and_described(tmp_path, monkeypatch):
    """Real worker output: the summary written beside the nucleoplasm mask passes the
    binding checks, also from a child revision that reuses that mask."""
    from cytellect_analysis.region_contracts import RegionCompartmentRecipe
    from cytellect_api.db import revisions
    from cytellect_worker import regions
    from cytellect_worker.compartment_sources import load_compartment_summaries
    from test_region_compartment_worker import compartment_config
    from test_region_nuclear_worker import install_detector, nuclear_fields
    from test_region_worker import execute

    store, settings, config = nuclear_fields(tmp_path)
    install_detector(monkeypatch)
    execute(store, settings, config, "nuclear")

    def detect(*, channels, nuclei, parameters, output_dir, executable, scratch_root=None):
        children = np.zeros_like(nuclei)
        children[2, 2] = 1
        return ({"nucleoli": children, "nucleoplasm": np.where(children, 0, nuclei)},
                {"nucleolar_states": {"7": "candidate", "19": "candidate"}})
    monkeypatch.setattr(regions, "detect_compartments", detect)
    execute(store, settings, compartment_config(config), "nucleoli")
    plasm = {**config, "recipe": RegionCompartmentRecipe(
        region_set_id="nucleoplasm", label="Nucleoplasm", compartment="nucleoplasm", nuclear_revision_id="nuclear",
        nuclear_channel_id="dna", defining_channel_id="actin", nucleolar_revision_id="nucleoli").model_dump(mode="json")}
    for rid, value in (("plasm", plasm), ("plasm-child", {**plasm, "reuse_revision": "plasm"})):
        report = execute(store, settings, value, rid)
        rev = store.one(revisions, id=rid)
        summaries = load_compartment_summaries(store, rev, report)
        assert report["field_masks"]["f1"]["mask_revision_id"] == "plasm"
        described = describe_compartment_summary(report, rev["config"]["field_snapshot"], {
            "mode": "descriptive", "selection": {**selection(), "channel_id": "actin"}}, summaries)
        # Nucleus 7 has the adopted nucleolus; nucleus 19 has none and stays a reasoned missing value.
        assert [row["nucleus_id"] for row in described["plot_data"]] == [7]
        assert described["missingness"] == [{"observation_id": '["f1","nucleoplasm",19]', "field_id": "f1",
                                             "reason": "no_nucleolus"}]
    np.save(store.safe_path("results", "plasm", "f1", "labels.npy"), np.zeros((8, 8), dtype=np.uint32))
    with pytest.raises(ValueError, match="compartment_summary_mask_mismatch"):
        load_compartment_summaries(store, store.one(revisions, id="plasm-child"), report)
    with pytest.raises(ValueError, match="compartment_summary_source_required"):
        load_compartment_summaries(store, store.one(revisions, id="nucleoli"), report)
