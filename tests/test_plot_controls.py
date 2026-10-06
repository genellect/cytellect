"""Presentation edits preserve source values and bounded, actual Matplotlib axes."""
import copy
import json

import numpy as np
import pytest
from cytellect_analysis.contracts import PlotSpec
from cytellect_analysis.descriptive import describe_regions
from cytellect_analysis.descriptive_contracts import PagedDescriptiveRequest
from cytellect_analysis.descriptive_figures import render_descriptive
from cytellect_analysis.descriptive_pages import page_layout
from cytellect_analysis.figures import apply_plot_controls, plt
from pydantic import ValidationError
from test_descriptive import region_fixture, request


@pytest.mark.parametrize("options", [
    {"y_min": float("nan")}, {"y_max": float("inf")}, {"y_min": 1e16},
    {"y_min": 10, "y_max": 10}, {"y_min": 11, "y_max": 10},
    {"y_tick_step": 0}, {"y_tick_step": -1}, {"point_size": 0}, {"point_size": 401},
    {"y_min": 0, "y_max": 100, "y_tick_step": .001},
])
def test_invalid_axis_controls_are_rejected(options):
    with pytest.raises(ValidationError):
        PlotSpec(**options)


def test_null_and_omitted_controls_preserve_historical_serialization():
    original = PlotSpec().model_dump(mode="json")
    explicit = PlotSpec(y_min=None, y_max=None, y_tick_step=None, point_size=None).model_dump(mode="json")
    assert original == explicit
    assert not {"y_min", "y_max", "y_tick_step", "point_size"} & original.keys()


def test_actual_axes_points_and_auto_tick_allocation_guard():
    fig, ax = plt.subplots()
    try:
        points = ax.scatter([0, 1], [-5, 9], s=9)
        source = points.get_offsets().copy()
        apply_plot_controls(ax, {"y_min": -10, "y_max": 10, "y_tick_step": 5, "point_size": 25})
        np.testing.assert_array_equal(ax.get_yticks(), [-10, -5, 0, 5, 10])
        assert ax.get_ylim() == (-10, 10)
        np.testing.assert_array_equal(points.get_sizes(), [25])
        np.testing.assert_array_equal(points.get_offsets(), source)
        with pytest.raises(ValueError, match="figure_tick_count_exceeded"):
            apply_plot_controls(ax, {"y_tick_step": 1e-200})
    finally:
        plt.close(fig)


def test_render_and_paged_layout_use_requested_axes_without_recalculating_measurements(tmp_path, monkeypatch):
    report, snapshots = region_fixture()
    spec = request(plot={"language": "en", "preset": "nature-double", "y_min": -10,
                         "y_max": 10, "y_tick_step": 5, "point_size": 25})
    result = describe_regions(report, snapshots, spec)
    unchanged = copy.deepcopy(result["plot_data"])
    seen = []
    from cytellect_analysis import descriptive_figures
    original_check = descriptive_figures._validate_text_layout
    def check(figure, axes):
        seen.append((axes.get_ylim(), axes.get_yticks().tolist(), axes.collections[0].get_sizes().tolist()))
        original_check(figure, axes)
    monkeypatch.setattr(descriptive_figures, "_validate_text_layout", check)
    render_descriptive(result, tmp_path)
    assert seen == [((-10, 10), [-10, -5, 0, 5, 10], [25])]
    saved = json.loads((tmp_path / "figure-data.json").read_text())
    assert saved["plot_data"] == result["plot_data"] == unchanged
    assert saved["spec"]["plot"]["y_tick_step"] == 5
    page = PagedDescriptiveRequest.model_validate({**spec.model_dump(mode="json"),
        "figure_policy": {"version": "2.0.0", "layout": "field-pages"}})
    layout = page_layout({**result, "spec": page.model_dump(mode="json")})
    assert layout["y_limits"] == [-10, 10] and layout["y_ticks"] == [-10, -5, 0, 5, 10]
