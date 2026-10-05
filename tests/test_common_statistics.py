import copy
import hashlib
import json

import pytest
from cytellect_analysis import common_statistics_figures
from cytellect_analysis.common_statistics import analyze_region_association, analyze_region_comparison
from cytellect_analysis.common_statistics_contracts import RegionAssociationRequest, RegionComparisonRequestV2
from cytellect_analysis.common_statistics_figures import render_common_statistics
from cytellect_analysis.region_comparison import compare_regions
from cytellect_analysis.region_comparison_contracts import RegionComparisonRequest
from pydantic import ValidationError
from test_region_comparison import comparison_fixture, comparison_request


def request_v2(*, test="mann-whitney-u", paired=False, **updates):
    raw = comparison_request(paired=paired).model_dump(mode="json")
    return RegionComparisonRequestV2.model_validate({**raw, "version": "2.0.0", "test": test, **updates})


def association_request(**updates):
    request = comparison_request().model_dump(mode="json")
    return RegionAssociationRequest.model_validate({
        "mode": "region-association", "version": "1.0.0", "x_selection": request["selection"],
        "y_selection": {**request["selection"], "channel_id": "dna"}, "design": request["design"],
        "conditions": request["conditions"], "acquisition_review": request["acquisition_review"],
        "missingness_confirmed": True, "method": "spearman", "plot": {"preset": "nature-double"}, **updates})


def test_new_version_is_explicit_and_old_result_unchanged():
    report, config = comparison_fixture()
    old = compare_regions(report, config, comparison_request())
    new = analyze_region_comparison(report, config, request_v2())
    assert new["region_comparison_version"] == "2.0.0"
    assert new["comparisons"][0]["method"] == "Mann–Whitney U"
    assert new["source_fingerprint"] == old["source_fingerprint"]
    assert old == compare_regions(report, config, comparison_request())
    with pytest.raises(ValidationError):
        RegionComparisonRequest.model_validate(request_v2().model_dump(mode="json"))
    with pytest.raises(ValidationError):
        RegionComparisonRequestV2.model_validate(comparison_request().model_dump(mode="json"))


def test_three_group_omnibus_and_full_planned_holm_family():
    report, config = comparison_fixture((("A", [1, 2, 3]), ("B", [4, 5, 6]), ("C", [7, 8, 9])))
    request = request_v2(conditions=["A", "B", "C"], omnibus="kruskal-wallis",
                         comparison_family={"family_id": "planned", "kind": "planned", "contrasts": [["A", "B"], ["A", "C"], ["B", "C"]]})
    result = analyze_region_comparison(report, config, request)
    assert result["omnibus"]["group_sizes"] == [3, 3, 3]
    assert len(result["comparisons"]) == 3
    assert {r["correction_family"] for r in result["comparisons"]} == {"planned"}


def test_association_uses_matched_units_and_separate_axis_missingness():
    report, config = comparison_fixture((("A", [1, 2, 3]), ("B", [4, 5, 6])))
    result = analyze_region_association(report, config, association_request())
    assert len(result["unit_summary"]) == 6
    assert [r["n_units"] for r in result["associations"]] == [3, 3]
    assert [r["p_value"] for r in result["associations"]] == [pytest.approx(1 / 3)] * 2
    assert result["x_source"]["channel"]["channel_id"] == "actin"
    assert result["y_source"]["channel"]["channel_id"] == "dna"
    for row in result["unit_summary"]:
        assert row["x"] == row["y"]
    bad = copy.deepcopy(report)
    for row in bad["field_tables"]["A0"]["rows"]:
        if row["channel_id"] == "dna":
            row["mean_corrected"] = None
    with pytest.raises(ValueError):
        analyze_region_association(bad, config, association_request())


@pytest.mark.parametrize("updates", [{"pooling_confirmed": "true"}, {"scope": "pooled"}, {"missingness_confirmed": 1}])
def test_association_confirmations_are_explicit(updates):
    with pytest.raises(ValidationError):
        association_request(**updates)


def test_explicit_pooling_is_recorded_and_warned():
    report, config = comparison_fixture((("A", [1, 2, 3]), ("B", [4, 5, 6])))
    result = analyze_region_association(report, config, association_request(scope="pooled", pooling_confirmed=True))
    assert len(result["associations"]) == 1
    assert result["associations"][0]["n_units"] == 6
    assert "pooled_association_may_reflect_condition_or_acquisition_batch_confounding" in result["warnings"]


def test_per_condition_association_does_not_require_cross_condition_batch_overlap():
    report, config = comparison_fixture((("A", [1, 2, 3]), ("B", [4, 5, 6])))
    for field in config["field_snapshot"].values():
        field["metadata"]["acquisition_date"] = field["metadata"]["condition"]
    result = analyze_region_association(report, config, association_request())
    assert len(result["associations"]) == 2
    with pytest.raises(ValueError, match="confounded"):
        analyze_region_association(report, config, association_request(scope="pooled", pooling_confirmed=True))


@pytest.mark.parametrize("kind", ["box", "scatter"])
def test_japanese_figure_labels_and_saved_methods_selector(tmp_path, kind):
    report, config = comparison_fixture((("A", [1, 3, 6]), ("B", [2, 5, 10])))
    plot = {"kind": kind, "preset": "nature-double", "language": "ja"}
    result = (analyze_region_association(report, config, association_request(plot=plot)) if kind == "scatter"
              else analyze_region_comparison(report, config, request_v2(plot=plot)))
    template = {"kind": "common-statistics", "version": "1.0.0"}
    manifest = render_common_statistics(result, tmp_path, methods_template=template)
    assert manifest["common_statistics_methods"] == template
    assert "平均輝度" in (tmp_path / "figure.svg").read_text(encoding="utf-8")


@pytest.mark.parametrize("kind", ["distribution", "box", "violin", "histogram", "paired", "scatter"])
def test_editable_figures_retain_exact_unit_values_tables_and_methods(tmp_path, kind):
    report, config = comparison_fixture((("A", [1, 3, 6]), ("B", [2, 5, 10])))
    if kind == "scatter":
        result = analyze_region_association(report, config, association_request())
    else:
        result = analyze_region_comparison(report, config, request_v2(
            test="wilcoxon" if kind == "paired" else "mann-whitney-u", paired=kind == "paired",
            plot={"kind": kind, "preset": "nature-double"}))
    manifest = render_common_statistics(result, tmp_path)
    assert all((tmp_path / filename).is_file() for filename in manifest["source_files"])
    assert "<text" in (tmp_path / "figure.svg").read_text(encoding="utf-8")
    assert (tmp_path / "figure.pdf").read_bytes().startswith(b"%PDF")
    source = json.loads((tmp_path / "figure-data.json").read_text(encoding="utf-8"))
    assert source["unit_summary"] == result["unit_summary"]
    assert len(source["unit_glyphs"]) == len(result["unit_summary"])
    for name, digest in source["source_hashes"].items():
        assert hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() == digest
    methods = (tmp_path / "methods.md").read_text(encoding="utf-8")
    assert "Holm" in methods and "Resolved test settings" in methods
    assert "independent experimental unit" in methods
    if kind == "histogram":
        assert sum(r["count"] for r in source["graphical_summary"]) == len(result["unit_summary"])
    if kind == "scatter":
        assert "actin" in methods and "dna" in methods
    with pytest.raises(ValidationError):
        render_common_statistics(result, tmp_path / "invalid", methods_template={"id": "cytellect-statistical-methods", "version": "1.0.0"})


@pytest.mark.parametrize("kind", ["distribution", "box", "violin", "paired"])
def test_categorical_figure_margins_do_not_depend_on_jitter(tmp_path, monkeypatch, kind):
    report, config = comparison_fixture((("A", [1, 3]), ("B", [2, 5])))
    result = analyze_region_comparison(report, config, request_v2(
        test="wilcoxon" if kind == "paired" else "mann-whitney-u", paired=kind == "paired",
        plot={"kind": kind, "preset": "nature-double"}))
    original = common_statistics_figures.plt.subplots
    axes = []

    def capture(*args, **kwargs):
        figure, axis = original(*args, **kwargs)
        axes.append(axis)
        return figure, axis

    monkeypatch.setattr(common_statistics_figures.plt, "subplots", capture)
    manifest = render_common_statistics(result, tmp_path)
    assert manifest["common_statistics_figure_version"] == "1.0.1"
    assert axes[0].get_xlim() == (-.5, 1.5)
    source = json.loads((tmp_path / "figure-data.json").read_text(encoding="utf-8"))
    assert source["unit_summary"] == result["unit_summary"]
    assert all(-.5 < row["display_x"] < 1.5 for row in source["unit_glyphs"])


def test_export_renderer_preserves_saved_figure_version(tmp_path):
    from cytellect_analysis.region_exports import _render_statistics

    report, config = comparison_fixture((("A", [1, 3]), ("B", [2, 5])))
    result = analyze_region_comparison(report, config, request_v2())
    for version in ("1.0.0", "1.0.1"):
        saved = render_common_statistics(result, tmp_path / version, figure_version=version)
        replayed = _render_statistics(result, tmp_path / (version + "-replay"),
                                      methods_template=saved["common_statistics_methods"], saved_figure=saved)
        assert replayed == saved
        for filename in saved["source_files"]:
            assert (tmp_path / version / filename).read_bytes() == (tmp_path / (version + "-replay") / filename).read_bytes()
    for filename in ("comparisons.csv", "unit-summary.csv", "methods.md"):
        assert (tmp_path / "1.0.0" / filename).read_bytes() == (tmp_path / "1.0.1" / filename).read_bytes()
    with pytest.raises(ValueError, match="figure_version_unsupported"):
        _render_statistics(result, tmp_path / "unsupported", saved_figure={"common_statistics_figure_version": "9.0.0"})
