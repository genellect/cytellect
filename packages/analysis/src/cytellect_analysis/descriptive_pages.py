"""Bounded, deterministic per-field pages; numerical descriptions are never pooled."""
from __future__ import annotations

import math
import unicodedata
from collections import Counter
from pathlib import Path

import numpy as np
from matplotlib.lines import Line2D
from matplotlib.text import Text

from .descriptive_contracts import PagedDescriptiveRequest, parse_descriptive_request
from .descriptive_figures import _source_measurement_policy, _ylabel
from .figure_sources import attach_svg_sources, bind_points
from .figures import _validate_text_layout, apply_plot_controls, figure_settings, plt, select_font

VERSION = "2.0.0"  # Saved pagination contract; independent of presentation fixes.
RENDER_VERSION = "2.1.0"
PRESENTATION_ERRORS = frozenset({
    "figure_labels_overlap", "figure_text_outside_canvas", "japanese_font_not_installed",
    "sans_serif_font_not_installed", "figure_font_glyphs_unavailable",
})


class DescriptivePresentationError(ValueError):
    def __init__(self, code: str, page_index: int | None):
        super().__init__(code)
        self.code, self.page_index = code, page_index


def _page_capacity(style):
    if style["preset"] == "nature-single":
        return 4
    if style["preset"] == "nature-double":
        return 8
    # Custom pages reserve nine font-size units per field's two-line tick label.
    # Keep the manifest's eight-field bound; rendering still validates text fit.
    return max(1, min(8, math.floor(style["width_inches"] * 72 / (9 * style["font_size_pt"]))))


TICK_NAME_COLUMNS = 12  # Two half-width columns per wide character; fits the reserved tick width.


def _tick_name(name, ja):
    """A registered name fits a tick when short and, in English figures, printable ASCII."""
    if not isinstance(name, str) or not name.isprintable() or (not ja and not name.isascii()):
        return None
    columns = sum(2 if unicodedata.east_asian_width(char) in "WF" else 1 for char in name)
    return name if columns <= TICK_NAME_COLUMNS else None


def field_labels(result, order, ja):
    """Global labels: the registered name when unique and short, otherwise the field number."""
    numbered = {fid: f"{'視野' if ja else 'Field'} {index + 1}" for index, fid in enumerate(order)}
    names = {field["field_id"]: _tick_name(field.get("display_name"), ja) for field in result["source_fields"]}
    counts = Counter(name for name in names.values() if name)
    return {fid: name if (name := names.get(fid)) and counts[name] == 1 and name not in numbered.values()
            else numbered[fid] for fid in order}


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
    capacity = _page_capacity(style)
    plans = [{"page_index": index // capacity + 1, "field_ids": order[index:index + capacity],
              "field_numbers": list(range(index + 1, min(index + capacity, len(order)) + 1))}
             for index in range(0, len(order), capacity)]
    if len(plans) > 999:
        raise ValueError("descriptive_page_limit_exceeded")
    labels = field_labels(result, order, ja)
    if result["source_kind"] == "measured-numerical-assay":
        labels = {fid: f"{'測定群' if ja else 'Set'} {index + 1}" for index, fid in enumerate(order)}
    # Ask the existing linear Matplotlib scale to expand constant values once.
    # Every page then receives exactly these limits and tick positions.
    figure, axes = plt.subplots()
    try:
        axes.scatter([0, 0], [min(row["value"] for row in rows), max(row["value"] for row in rows)])
        apply_plot_controls(axes, plot)
        limits, ticks = list(map(float, axes.get_ylim())), list(map(float, axes.get_yticks()))
    finally:
        plt.close(figure)
    if any(not math.isfinite(value) for value in (*limits, *ticks)) or not limits[0] < limits[1]:
        raise ValueError("descriptive_figure_source_mismatch")
    rng = np.random.default_rng(0)
    jitter = {fid: rng.uniform(-.15, .15, len(values[fid])) for fid in order}
    return {"order": order, "page_plan": plans, "labels": labels, "y_limits": limits, "y_ticks": ticks,
            "style": style, "plot": plot, "values": values, "jitter": jitter}


def tick_label(value: float, ticks) -> str:
    """A value-axis label: thousands separated, with as many decimals as the axis's ticks need (1,000.5 is not 1,001)."""
    if abs(value) < 1000:
        return f"{value:g}"
    large = [float(tick) for tick in ticks if abs(tick) >= 1000] or [float(value)]
    decimals = next((d for d in range(7) if all(abs(round(tick, d) - tick) <= 1e-9 * abs(tick) for tick in large)), 6)
    return f"{value:,.{decimals}f}"


def render_pages(result, output: Path, layout):
    """Only presentation failures are recoverable; write errors propagate unchanged.

    Pages are drawn as publication figures (2026-11-19): the bundled typeface, each field's observations
    placed by a deterministic beeswarm and coloured by the field's condition, the field median as a line,
    and one value axis shared by every page."""
    from matplotlib.ticker import FuncFormatter

    from .figure_layout import beeswarm
    from .figure_style import INK, OKABE_ITO, fit_axis_title, rc

    plot, style = layout["plot"], layout["style"]
    ja, size = plot["language"] == "ja", style["font_size_pt"]
    numeric = result["source_kind"] == "measured-numerical-assay"
    ylabel = plot["y_label"] or _ylabel(result, ja)
    xlabel = plot["x_label"] or (("測定グループ" if ja else "Measurement group") if numeric else "視野" if ja else "Field")
    median_label = ("測定群中央値" if ja else "Set median") if numeric else "視野中央値" if ja else "Field median"
    observation_label = "観測値" if ja else "Observation"
    summaries = {row["field_id"]: row for row in result["field_summary"]}
    # The experiment's groups colour the fields, in the order the fields are shown.
    condition_of = {fid: summaries[fid].get("condition") for fid in layout["order"]}
    conditions = list(dict.fromkeys(value for value in condition_of.values() if value))
    palette = {condition: OKABE_ITO[index % len(OKABE_ITO)] for index, condition in enumerate(conditions)}
    overrides = plot.get("style", {}).get("series_colors", {})
    colour_of = lambda fid: overrides.get(fid) or palette.get(condition_of.get(fid)) or "#526b78"  # noqa: E731
    all_text = " ".join([ylabel, xlabel, median_label, observation_label, *conditions, *layout["labels"].values(),
                         "観測" if ja else "obs.", "·/,"])
    try:
        font = select_font(plot["language"], all_text)
    except ValueError as exc:
        if str(exc) not in PRESENTATION_ERRORS:
            raise
        raise DescriptivePresentationError(str(exc), None) from None
    point_size = float(plot.get("point_size") or 9)
    point_d = math.sqrt(point_size)
    fields_only = result["observation_kind"] == "fields"

    def bind_font(item):
        properties = item.get_fontproperties().copy()
        properties.set_file(str(font.path))
        properties.set_family(font.family)
        properties.set_weight(font.weight)
        item.set_fontproperties(properties)
    with plt.rc_context({**rc(size), "text.usetex": False, "text.parse_math": False, "axes.unicode_minus": False,
                         "svg.hashsalt": "cytellect-descriptive-figure-" + RENDER_VERSION}):
        for plan in layout["page_plan"]:
            page = plan["page_index"]
            figure, axes = plt.subplots(figsize=(style["width_inches"], style["height_inches"]), layout="constrained")
            try:
                ticks = [f"{layout['labels'][fid]}\n{len(layout['values'][fid])} " + ("観測" if ja else "obs.")
                         for fid in plan["field_ids"]]
                axes.set_xticks(range(len(ticks)), ticks)
                axes.set_xlim(-.6, len(ticks) - .4)
                axes.set_yticks(layout["y_ticks"])
                axes.set_ylim(layout["y_limits"])
                axes.set_xlabel(xlabel)
                axes.set_ylabel(fit_axis_title(ylabel, max(24.0, style["height_inches"] * 25.4 - 22), size))
                axes.tick_params(axis="x", length=0, pad=3)
                for item in figure.findobj(match=Text):
                    bind_font(item)
                # Legend keys describe the common marks; they are not dummy observations.
                if plot.get("style", {}).get("show_legend", True):
                    # A key per colour the points have (a field colour chosen by the researcher included); when one
                    # condition is shown in several colours, each key names the fields it marks.
                    keyed: dict[tuple[str | None, str], list[str]] = {}
                    for fid in sorted(plan["field_ids"], key=lambda fid: (conditions.index(condition_of[fid])
                                                                        if condition_of.get(fid) in conditions else -1)):
                        keyed.setdefault((condition_of.get(fid) if len(conditions) > 1 else None, colour_of(fid)), []).append(fid)
                    split = len(keyed) > len({condition for condition, _ in keyed})
                    handles = [Line2D([], [], marker="o", linestyle="none", markersize=3.2, markeredgewidth=0, color=colour,
                                      label=(condition or observation_label)
                                      + (f" ({', '.join(layout['labels'][fid] for fid in fids)})" if split else ""))
                               for (condition, colour), fids in keyed.items()]
                    if not fields_only:
                        handles.append(Line2D([], [], color=INK, linewidth=1.1, label=median_label))
                    # As many keys on a row as the page is wide: a narrow column wraps them.
                    for columns in range(len(handles), 0, -1):
                        legend = figure.legend(handles=handles, loc="outside upper center", frameon=False, ncols=columns,
                                               handlelength=1.1, handletextpad=.4, columnspacing=1.2)
                        for item in legend.get_texts():
                            bind_font(item)
                        figure.canvas.draw()
                        if columns == 1 or legend.get_window_extent().width <= figure.bbox.width - 2:
                            break
                        legend.remove()
                for item in figure.findobj(match=Text):
                    bind_font(item)
                # The observations are on the axis before its controls check them (a log axis needs positive values);
                # they are spread side by side once the layout is fixed.
                marks = {}
                for index, fid in enumerate(plan["field_ids"]):
                    values = np.asarray(layout["values"][fid], dtype=float)
                    if len(values):
                        marks[index] = values, axes.scatter(np.full(len(values), float(index)), values, s=point_size,
                                                            color=colour_of(fid), alpha=.75, linewidths=0, zorder=2)
                apply_plot_controls(axes, plot)
                if plot.get("axes", {}).get("y_scale", "linear") == "linear":
                    axes.yaxis.set_major_formatter(FuncFormatter(lambda value, _, axes=axes: tick_label(value, axes.get_yticks())))
                # The layout is fixed before the marks are placed, so a point's printed size is known in data units.
                figure.canvas.draw()
                figure.set_layout_engine("none")
                box = axes.get_window_extent()
                xspan, yspan = np.diff(axes.get_xlim())[0], np.diff(axes.get_ylim())[0]
                to_dx = lambda points: points / 72 * figure.dpi / box.width * xspan  # noqa: E731
                to_dy = lambda points: points / 72 * figure.dpi / box.height * yspan  # noqa: E731
                half_median = min(.3, to_dx(5 / 25.4 * 72))
                log_y = axes.get_yscale() == "log"
                for index, fid in enumerate(plan["field_ids"]):
                    if index not in marks:
                        continue
                    values, collection = marks[index]
                    # On a log axis the points are spread where they are drawn (display units), not in data units.
                    heights = axes.transData.transform(np.column_stack([np.zeros(len(values)), values]))[:, 1] if log_y else values
                    offsets = beeswarm(heights, dx=to_dx(point_d * 1.05),
                                       dy=point_d * 1.05 / 72 * figure.dpi if log_y else to_dy(point_d * 1.05),
                                       half_width=min(.32, to_dx(9 / 25.4 * 72)))
                    collection.set_offsets(np.column_stack([index + offsets, values]))
                    bind_points(collection, [row for row in result["plot_data"] if row["field_id"] == fid])
                    if not fields_only:
                        median = summaries[fid]["median"]
                        axes.hlines(median, index - half_median, index + half_median, color=INK, linewidth=1.1, zorder=3)
                        bind_points(axes.scatter([index], [median], s=0, marker="_", color=INK, zorder=3), [{"field_id": fid}])
                try:
                    _validate_text_layout(figure, axes)
                except ValueError as exc:
                    if str(exc) not in PRESENTATION_ERRORS:
                        raise
                    raise DescriptivePresentationError(str(exc), page) from None
                for suffix in ("svg", "pdf", "png"):
                    metadata: dict[str, str | None] = {"Creator": "Cytellect descriptive figure " + RENDER_VERSION}
                    if suffix == "svg":
                        metadata["Date"] = None
                    if suffix == "pdf":
                        metadata.update(CreationDate=None, ModDate=None)
                    figure.savefig(output / f"figure-{page:03d}.{suffix}", dpi=style["png_dpi"], metadata=metadata)
                    if suffix == "svg":
                        attach_svg_sources(output / f"figure-{page:03d}.{suffix}", figure)
            finally:
                plt.close(figure)
    return font.metadata()
