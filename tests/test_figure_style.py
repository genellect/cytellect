"""Presentation controls change real vector output without recomputing inference."""
import copy

import pytest
from cytellect_analysis.common_statistics import analyze_region_comparison
from cytellect_analysis.common_statistics_figures import render_common_statistics
from cytellect_analysis.contracts import PlotSpec
from pydantic import ValidationError
from test_gfp_gated_statistics import nuclear_fixture, request


def test_style_is_opt_in_and_rejects_unregistered_versions_or_external_colors():
    assert "style" not in PlotSpec().model_dump(mode="json")
    assert "axes" not in PlotSpec().model_dump(mode="json")
    for style in ({"version": "2.0.0"}, {"version": "1.0.0", "series_colors": {"A": "url(https://example.com)"}}):
        with pytest.raises(ValidationError):
            PlotSpec(style=style)


def test_axes_reject_category_numeric_bounds_and_nonpositive_log_limits():
    with pytest.raises(ValidationError, match="numeric_x_requires_scatter"):
        PlotSpec(axes={"version": "1.0.0", "x_min": 0})
    with pytest.raises(ValidationError, match="log_requires_positive"):
        PlotSpec(y_min=0, axes={"version": "1.0.0", "y_scale": "log10"})
    with pytest.raises(ValidationError, match="tick_count"):
        PlotSpec(kind="scatter", axes={"version": "1.0.0", "x_min": 1, "x_max": 1000, "x_tick_step": 1})


def test_actual_matplotlib_scatter_axis_scale_range_and_ticks_preserve_statistics(tmp_path, monkeypatch):
    from cytellect_analysis import common_statistics_figures
    from cytellect_analysis.common_statistics import analyze_region_association
    from test_common_statistics import association_request
    from test_region_comparison import comparison_fixture

    report, config = comparison_fixture((("A", [1, 2, 3]), ("B", [4, 5, 6])))
    result = analyze_region_association(report, config, association_request())
    before = copy.deepcopy(result)
    result["spec"]["plot"].update(y_min=0.5, y_max=20, y_tick_step=5,
        axes={"version": "1.0.0", "x_min": 0.5, "x_max": 20, "x_tick_step": 5, "x_scale": "log2", "y_scale": "log10"})
    apply = common_statistics_figures.apply_plot_controls
    captured = {}
    def observe(ax, plot):
        apply(ax, plot)
        captured.update(x_scale=ax.get_xscale(), y_scale=ax.get_yscale(), x=ax.get_xlim(), y=ax.get_ylim(), ticks=ax.get_xticks().tolist())
    monkeypatch.setattr(common_statistics_figures, "apply_plot_controls", observe)
    render_common_statistics(result, tmp_path)
    assert captured == {"x_scale": "log", "y_scale": "log", "x": (0.5, 20), "y": (0.5, 20), "ticks": [0.5+5*i for i in range(4)]}
    assert (tmp_path / "figure.svg").is_file() and (tmp_path / "figure.pdf").is_file()
    assert result["unit_summary"] == before["unit_summary"] and result["associations"] == before["associations"]


def test_log_axis_refuses_negative_background_corrected_measurements(tmp_path):
    fields = {f"{group}{i}": (group, f"{group}{i}", "d1", [(300, value)])
              for group, values in (("A", [1, 2, 3]), ("B", [10, 12, 14])) for i, value in enumerate(values)}
    report, config = nuclear_fixture(fields=fields)
    spec = request().model_dump(mode="json")
    spec["selection"]["metric"] = "mean_corrected"
    result = analyze_region_comparison(report, config, spec)
    assert any(row["value"] < 0 for row in result["unit_summary"])
    result["spec"]["plot"]["axes"] = {"version": "1.0.0", "y_scale": "log10"}
    with pytest.raises(ValueError, match="figure_log_requires_positive_values"):
        render_common_statistics(result, tmp_path)
    assert not (tmp_path / "figure.svg").exists()


def test_actual_svg_honors_series_color_size_and_preserves_source_statistics(tmp_path):
    report, config = nuclear_fixture()
    result = analyze_region_comparison(report, config, request())
    result["revision_id"] = report["revision_id"]
    expected = copy.deepcopy(result)
    result["spec"]["plot"].update(point_size=40, style={"version": "1.0.0", "series_colors": {"A": "#123456"}, "show_legend": False})
    render_common_statistics(result, tmp_path)
    assert "#123456" in (tmp_path / "figure.svg").read_text(encoding="utf-8")
    assert result["comparisons"] == expected["comparisons"]
    assert result["unit_summary"] == expected["unit_summary"]
