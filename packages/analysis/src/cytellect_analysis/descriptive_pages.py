"""Bounded, deterministic per-field pages; numerical descriptions are never pooled."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from matplotlib.lines import Line2D
from matplotlib.text import Text

from .descriptive_contracts import PagedDescriptiveRequest, parse_descriptive_request
from .descriptive_figures import _source_measurement_policy, _ylabel
from .figures import _validate_text_layout, figure_settings, plt, select_font

VERSION = "2.0.0"
PRESENTATION_ERRORS = frozenset({
    "figure_labels_overlap", "figure_text_outside_canvas", "japanese_font_not_installed",
    "sans_serif_font_not_installed", "figure_font_glyphs_unavailable",
})


class DescriptivePresentationError(ValueError):
    def __init__(self, code: str, page_index: int | None):
        super().__init__(code)
        self.code, self.page_index = code, page_index


def page_layout(result):
    """Validate full source coverage before any recoverable rendering operation."""
    request = parse_descriptive_request(result["spec"])
    if not isinstance(request, PagedDescriptiveRequest):
        raise ValueError("descriptive_page_policy_required")
    if result.get("analysis_kind") != "descriptive":
        raise ValueError("descriptive_result_required")
    if any(key in result for key in ("comparisons", "means", "unit_summary", "model")):
        raise ValueError("descriptive_inference_not_allowed")
    summaries = result["field_summary"]
    fields = [row["field_id"] for row in summaries]
    order = request.plot.group_order or fields
    rows = result["plot_data"]
    if (not fields or len(fields) != len(set(fields)) or len(order) != len(set(order))
            or set(order) != set(fields)
            or {field["field_id"] for field in result["source_fields"]} != set(fields)
            or len(result["source_fields"]) != len(fields)
            or not rows or type(result["counts"]["observations"]) is not int
            or len(rows) != result["counts"]["observations"]
            or len({row["observation_id"] for row in rows}) != len(rows)
            or any(row["field_id"] not in fields or isinstance(row["value"], bool)
                   or not isinstance(row["value"], (int, float)) or not math.isfinite(row["value"]) for row in rows)):
        raise ValueError("descriptive_figure_source_mismatch")
    values = {fid: [row["value"] for row in rows if row["field_id"] == fid] for fid in order}
    if any(type(row["selected_rows"]) is not int or len(values[row["field_id"]]) != row["selected_rows"]
           or (values[row["field_id"]] and (isinstance(row["median"], bool)
               or not isinstance(row["median"], (int, float)) or not math.isfinite(row["median"])))
           or (not values[row["field_id"]] and row["median"] is not None) for row in summaries):
        raise ValueError("descriptive_figure_source_mismatch")
    _source_measurement_policy(result)
    plot = request.plot.model_dump(mode="json")
    style, ja = figure_settings(plot), request.plot.language == "ja"
    capacity = 4 if request.plot.preset == "nature-single" else 8
    plans = [{"page_index": index // capacity + 1, "field_ids": order[index:index + capacity],
              "field_numbers": list(range(index + 1, min(index + capacity, len(order)) + 1))}
             for index in range(0, len(order), capacity)]
    if len(plans) > 999:
        raise ValueError("descriptive_page_limit_exceeded")
    labels = {fid: f"{'視野' if ja else 'Field'} {index + 1}" for index, fid in enumerate(order)}
    if result["source_kind"] == "measured-numerical-assay":
        labels = {fid: f"{'測定群' if ja else 'Set'} {index + 1}" for index, fid in enumerate(order)}
    # Ask the existing linear Matplotlib scale to expand constant values once.
    # Every page then receives exactly these limits and tick positions.
    figure, axes = plt.subplots()
    try:
        axes.scatter([0, 0], [min(row["value"] for row in rows), max(row["value"] for row in rows)])
        limits, ticks = list(map(float, axes.get_ylim())), list(map(float, axes.get_yticks()))
    finally:
        plt.close(figure)
    if any(not math.isfinite(value) for value in (*limits, *ticks)) or not limits[0] < limits[1]:
        raise ValueError("descriptive_figure_source_mismatch")
    rng = np.random.default_rng(0)
    jitter = {fid: rng.uniform(-.15, .15, len(values[fid])) for fid in order}
    return {"order": order, "page_plan": plans, "labels": labels, "y_limits": limits, "y_ticks": ticks,
            "style": style, "plot": plot, "values": values, "jitter": jitter}


def render_pages(result, output: Path, layout):
    """Only presentation failures are recoverable; write errors propagate unchanged."""
    plot, style = layout["plot"], layout["style"]
    ja, size = plot["language"] == "ja", style["font_size_pt"]
    numeric = result["source_kind"] == "measured-numerical-assay"
    ylabel = plot["y_label"] or _ylabel(result, ja)
    xlabel = plot["x_label"] or (("測定グループ" if ja else "Measurement group") if numeric else "視野" if ja else "Field")
    median_label = ("測定群中央値" if ja else "Set median") if numeric else "視野中央値" if ja else "Field median"
    observation_label = "観測値" if ja else "Observation"
    title = "測定値の分布" if ja else "Observed measurements"
    all_text = " ".join([ylabel, xlabel, median_label, observation_label, title, *layout["labels"].values(),
                         "観測" if ja else "obs.", "ページ" if ja else "Page", "·/"])
    try:
        font = select_font(plot["language"], all_text)
    except ValueError as exc:
        if str(exc) not in PRESENTATION_ERRORS:
            raise
        raise DescriptivePresentationError(str(exc), None) from None
    summaries = {row["field_id"]: row for row in result["field_summary"]}
    with plt.rc_context({"font.size": size, "axes.titlesize": size, "axes.labelsize": size,
                         "xtick.labelsize": size, "ytick.labelsize": size, "legend.fontsize": size,
                         "font.weight": "normal", "axes.labelweight": "normal", "axes.titleweight": "normal",
                         "svg.fonttype": "none", "pdf.fonttype": 42, "text.usetex": False,
                         "text.parse_math": False, "axes.unicode_minus": False, "axes.linewidth": .6,
                         "svg.hashsalt": "cytellect-descriptive-figure-" + VERSION}):
        for plan in layout["page_plan"]:
            page = plan["page_index"]
            figure, axes = plt.subplots(figsize=(style["width_inches"], style["height_inches"]), layout="constrained")
            try:
                for index, fid in enumerate(plan["field_ids"]):
                    values = layout["values"][fid]
                    if values:
                        axes.scatter(index + layout["jitter"][fid], values, s=9, color="#526b78", alpha=.65, linewidths=0)
                        axes.scatter(index + .23, summaries[fid]["median"], s=17, marker="s", facecolors="none",
                                     edgecolors="#17292f", linewidths=.7)
                ticks = [f"{layout['labels'][fid]}\n{len(layout['values'][fid])} " + ("観測" if ja else "obs.")
                         for fid in plan["field_ids"]]
                axes.set_xticks(range(len(ticks)), ticks)
                axes.set_xlim(-.5, len(ticks) - .5)
                axes.set_yticks(layout["y_ticks"])
                axes.set_ylim(layout["y_limits"])
                axes.set_xlabel(xlabel)
                axes.set_ylabel(ylabel)
                axes.set_title(f"{title} · {'ページ' if ja else 'Page'} {page}/{len(layout['page_plan'])}", loc="left", pad=7)
                axes.spines[["top", "right"]].set_visible(False)
                # Legend keys describe the common marks; they are not dummy observations.
                figure.legend(handles=[Line2D([], [], marker="o", linestyle="none", markersize=3,
                                             color="#526b78", label=observation_label),
                                       Line2D([], [], marker="s", linestyle="none", markersize=4,
                                              markerfacecolor="none", color="#17292f", label=median_label)],
                              loc="outside upper center", frameon=False, ncols=2, handletextpad=.4, columnspacing=1)
                for item in figure.findobj(match=Text):
                    properties = item.get_fontproperties().copy()
                    properties.set_file(str(font.path))
                    properties.set_family(font.family)
                    properties.set_weight(font.weight)
                    item.set_fontproperties(properties)
                try:
                    _validate_text_layout(figure, axes)
                except ValueError as exc:
                    if str(exc) not in PRESENTATION_ERRORS:
                        raise
                    raise DescriptivePresentationError(str(exc), page) from None
                for suffix in ("svg", "pdf", "png"):
                    metadata: dict[str, str | None] = {"Creator": "Cytellect descriptive figure " + VERSION}
                    if suffix == "svg":
                        metadata["Date"] = None
                    if suffix == "pdf":
                        metadata.update(CreationDate=None, ModDate=None)
                    figure.savefig(output / f"figure-{page:03d}.{suffix}", dpi=style["png_dpi"], metadata=metadata)
            finally:
                plt.close(figure)
    return font.metadata()
