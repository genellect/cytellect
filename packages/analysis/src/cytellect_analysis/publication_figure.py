"""Publication figures of saved comparisons (common-statistics figure 2.0.0).

A comparison is drawn in four layers: every observation (nucleus, region or field), the
value of each run, the mean of runs, and the annotation of the saved effect. Every plotted
number is a saved value; nothing is estimated here except the display geometry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from matplotlib.lines import Line2D
from matplotlib.text import Text
from matplotlib.ticker import MaxNLocator

from .figure_annotations import Annotations, association_label, comparison_annotations
from .figure_forms import figure_forms
from .figure_layout import beeswarm
from .figure_sources import bind_points
from .figure_style import (
    BAR_FILL,
    DENSITY_EDGE,
    DENSITY_FILL,
    FONT_FAMILY,
    FONT_FILES,
    INK,
    MM,
    MUTED,
    OKABE_ITO,
    SIZES_MM,
    fit_axis_title,
    run_colors,
    run_marker,
    tick_locator,
    value_formatter,
    wrap_label,
)
from .group_comparison_contracts import metric_scale

REGION_ADJECTIVES = {
    "nuclei": "Nuclear", "nucleus": "Nuclear", "nucleoli": "Nucleolar", "nucleolus": "Nucleolar",
    "nucleoplasm": "Nucleoplasmic", "cytoplasm": "Cytoplasmic", "cell": "Cellular", "cells": "Cellular",
}
OBSERVATION_NOUNS = {
    "nuclei": ("nucleus", "nuclei"), "nucleus": ("nucleus", "nuclei"), "nucleoli": ("nucleolus", "nucleoli"),
    "nucleolus": ("nucleolus", "nucleoli"), "nucleoplasm": ("nucleus", "nuclei"), "cytoplasm": ("cell", "cells"),
    "cell": ("cell", "cells"), "cells": ("cell", "cells"),
}
COUNT_METRICS = {"nucleus_count", "positive_count", "nucleolar_count"}
INTENSITY = {"mean": "mean intensity", "median": "median intensity", "integrated": "integrated intensity"}


def _ascii(text: str | None) -> str | None:
    return text if text and text.isascii() and text.isprintable() else None


def stain_name(source) -> str | None:
    channel = source.get("channel") or {}
    return _ascii(channel.get("stain")) or _ascii(channel.get("label")) or channel.get("label")


def region_adjective(source) -> str | None:
    region = source.get("region") or {}
    return REGION_ADJECTIVES.get(region.get("region_set_id", "")) or _ascii(region.get("label"))


def observation_noun(source) -> tuple[str, str]:
    selection = (source.get("spec") or {}).get("selection") or source.get("selection") or {}
    if selection.get("source") == "field-summary":
        return "field", "fields"
    if str(selection.get("source", "")).startswith("compartment-summary"):
        return "nucleus", "nuclei"
    return OBSERVATION_NOUNS.get((source.get("region") or {}).get("region_set_id", ""), ("region", "regions"))


def axis_title(source) -> tuple[str, str]:
    """An English axis title (without the unit) and its unit, from the saved source."""
    metric = source["metric"]
    stain = stain_name(source)
    region = region_adjective(source)
    unit = source.get("unit") or ""
    corrected = metric.endswith("_corrected")
    base = metric.removesuffix("_corrected")
    if base in INTENSITY:
        words = " ".join(part for part in (region, stain, INTENSITY[base]) if part)
        unit = ("background-subtracted, " if corrected else "") + (unit or "a.u.")
        return words[:1].upper() + words[1:], unit
    if base in ("area_px", "area_um2"):
        return f"{region or 'Region'} area", "µm²" if base == "area_um2" else "pixel²"
    titles = {
        "nucleolar_count": ("Nucleoli per nucleus", ""),
        "nucleolar_area_px": ("Nucleolar area per nucleus", "pixel²"),
        "nucleolar_area_um2": ("Nucleolar area per nucleus", "µm²"),
        "nucleolar_area_fraction": ("Nucleolar area fraction of nucleus", ""),
        "nucleolar_eccentricity": ("Nucleolar eccentricity", ""),
        "log2_nucleoplasm_over_nucleolus": (" ".join(p for p in (stain, "nucleoplasm/nucleolus ratio") if p), "log2"),
        "nucleus_count": ("Nuclei per field", ""),
        "nucleus_density_per_mm2": ("Nuclear density", "nuclei per mm²"),
        "positive_count": (f"{stain}-positive nuclei per field" if stain else "Positive nuclei per field", ""),
        "positive_fraction": (f"{stain}-positive nuclei" if stain else "Positive nuclei", ""),
    }
    if base in titles:
        return titles[base]
    return metric.replace("_", " ").capitalize(), unit


def fit_line(line: str, width_mm: float, font_size: float) -> list[str]:
    """Put a confidence interval (or another parenthesis, such as the runs a change holds in) on its
    own line when the annotation does not fit the panel."""
    if len(line) * font_size * .52 * 25.4 / 72 <= width_mm:
        return [line]
    if " (95% CI " in line:
        head, _, tail = line.partition(" (95% CI ")
        return [head, "(95% CI " + tail]
    if " (" in line:
        head, _, tail = line.rpartition(" (")
        return [head, "(" + tail]
    return [line]


def _scale(source) -> str:
    try:
        return metric_scale(source.get("metric", ""))
    except ValueError:
        return "difference"


def _full_title(title: str, unit: str, extra: str) -> str:
    units = ", ".join(part for part in (extra, unit) if part)
    return f"{title} ({units})" if units else title


@dataclass
class Layout:
    width_mm: float
    height_mm: float
    size: str
    font_size: float
    png_dpi: int = 600

    def style(self) -> dict[str, Any]:
        return {"preset": self.size, "width_inches": self.width_mm * MM, "height_inches": self.height_mm * MM,
                "width_mm": self.width_mm, "height_mm": self.height_mm, "font_size_pt": self.font_size,
                "line_width_pt": .5, "png_dpi": self.png_dpi}


def default_size(plot) -> str:
    """A request that names no presentation (an earlier client, or a figure saved before the publication
    figure) keeps the width and height it asked for; the 「グラフ」 view names one and opens on the panel."""
    return "panel" if plot.get("presentation") else "custom"


def layout(plot, presentation, groups: int, *, legend: bool, bracket_levels: int) -> Layout:
    size = presentation.get("size", "panel")
    font = float(plot.get("font_size") or 7)
    height = 50 + 4 * max(0, bracket_levels - 1)
    if size == "custom":
        # A journal preset fixes the width, as in the earlier figures.
        width = {"nature-single": 89.0, "nature-double": 183.0}.get(plot.get("preset"), plot["width_inches"] * 25.4)
        return Layout(width, plot["height_inches"] * 25.4, size, font)
    if size in SIZES_MM:
        return Layout(SIZES_MM[size], max(height, 56 if size == "single-column" else 64), size, font)
    width = 15 + 11 * groups + (13 if legend else 3)
    return Layout(max(width, 36), height, "panel", font)


@dataclass
class Drawn:
    glyphs: list[dict[str, Any]] = field(default_factory=list)
    summary: list[dict[str, Any]] = field(default_factory=list)
    annotations: Annotations = field(default_factory=Annotations)
    description: dict[str, Any] = field(default_factory=dict)


def resolve_presentation(result, plot) -> dict[str, Any]:
    """The presentation actually drawn, with the result-dependent defaults filled in."""
    saved = dict(plot.get("presentation") or {})
    forms = figure_forms(result)
    paired = result["spec"]["design"]["kind"] == "paired"
    observations = saved.get("observations") or forms["default"].get("observations") or "points"
    return {"version": "1.0.0", "observations": observations,
            "color_by": saved.get("color_by") or ("run" if paired else "group"),
            "annotation": saved.get("annotation") or "value", "size": saved.get("size") or default_size(plot),
            "composition": saved.get("composition") or "quantification",
            "image_fields": dict(saved.get("image_fields") or {}), "outlines": saved.get("outlines", True)}


def _font_for(text: str, bold: bool):
    """The bundled face when it has every glyph, else the shared fallback (e.g. Japanese names)."""
    from matplotlib import font_manager

    from .figures import select_font

    path = FONT_FILES["bold" if bold else "regular"]
    loaded = font_manager.get_font(str(path))
    if {ord(c) for c in text if not c.isspace()}.issubset(loaded.get_charmap()):
        return FONT_FAMILY, path
    fallback = select_font("en", text)
    return fallback.family, fallback.path


def bind_fonts(figure):
    for item in figure.findobj(match=Text):
        text = item.get_text()
        if not text:
            continue
        bold = item.get_fontweight() in ("bold", 700, "heavy")
        family, path = _font_for(text, bold)
        properties = item.get_fontproperties().copy()
        properties.set_file(str(path))
        properties.set_family(family)
        item.set_fontproperties(properties)


def _observations(canonical, order):
    units = {(u["condition"], u["experimental_unit"]) for u in canonical["unit_summary"]}
    rows = [row for row in canonical.get("plot_data") or []
            if row.get("selection_status", "selected") == "selected" and row.get("value") is not None
            and row["condition"] in order and (row["condition"], row["experimental_unit"]) in units]
    return rows


def _y_range(values, scale, plot):
    values = np.asarray(values, dtype=float)
    low, high = float(values.min()), float(values.max())
    nonnegative = low >= 0
    if scale in ("ratio", "fraction") and nonnegative:
        low = 0.0
    if high == low:
        high = low + (abs(low) or 1.0)
    locator = tick_locator()
    if plot.get("y_min") is not None:
        low = float(plot["y_min"])
    if plot.get("y_max") is not None:
        high = float(plot["y_max"])
    # The same checks as the earlier figures (figures.apply_plot_controls), before any array is made.
    if not np.isfinite([low, high]).all() or low >= high:
        raise ValueError("figure_y_range_invalid")
    if plot.get("y_tick_step"):
        step = float(plot["y_tick_step"])
        if not np.isfinite(step) or step <= 0 or (high - low) / step > 99:
            raise ValueError("figure_tick_count_exceeded")
        ticks = low + np.arange(int(np.floor((high - low) / step + 1e-9)) + 1) * step
        bottom, top = low, high
    else:
        ticks = locator.tick_values(low, high)
        # The axis ends on the ticks that enclose every value: no observation or interval lies outside it.
        below = ticks[ticks <= low + 1e-12 * max(1, abs(low))]
        above = ticks[ticks >= high - 1e-12 * max(1, abs(high))]
        bottom = float(below.max()) if len(below) else float(ticks.min())
        top = float(above.min()) if len(above) else float(ticks.max())
        if plot.get("y_min") is not None:
            bottom = low
        if plot.get("y_max") is not None:
            top = high
        ticks = ticks[(ticks >= bottom - 1e-12) & (ticks <= top + 1e-12)]
        if scale == "fraction" and top > 1 and high <= 1:
            top = 1.0
            ticks = ticks[ticks <= 1 + 1e-12]
    return bottom, top, ticks


def draw_comparison(fig, ax, canonical, plot, presentation, order) -> Drawn:
    """The run hierarchy: observations, runs, mean of runs and the saved effect."""
    from scipy import stats

    drawn = Drawn()
    spec = canonical["spec"]
    units = canonical["unit_summary"]
    paired = spec["design"]["kind"] == "paired"
    descriptive = spec.get("test") == "none"
    bars = plot.get("kind") == "unit-mean-bar"
    scale = _scale(canonical)
    rows = _observations(canonical, order)
    runs = sorted({u["pair"] for u in units if u.get("pair")}) if paired else []
    overrides = (plot.get("style") or {}).get("series_colors") or {}
    by_run = presentation["color_by"] == "run" and bool(runs)
    colours = run_colors(runs, overrides) if by_run else {
        group: overrides.get(group, OKABE_ITO[index % len(OKABE_ITO)]) for index, group in enumerate(order)}
    notes = comparison_annotations(canonical, order, presentation["annotation"])
    drawn.annotations = notes
    brackets = notes.brackets if presentation["annotation"] != "none" else []
    text_size = max(5.0, (plot.get("font_size") or 7) - .5)
    room_mm = fig.get_figwidth() / MM - 8
    for bracket in brackets:
        bracket.lines = [part for line in bracket.lines for part in fit_line(line, room_mm, text_size)]

    # Group summaries: the saved two-group estimates, else the mean of the saved run values.
    saved_groups = {g["condition"]: g for g in ((canonical.get("estimates") or {}).get("groups") or [])}
    summaries = {}
    for group in order:
        values = np.array([u["value"] for u in units if u["condition"] == group], dtype=float)
        saved = saved_groups.get(group)
        mean = float(saved["mean"]) if saved and saved.get("mean") is not None else float(values.mean())
        low = high = None
        interval = "not computed (descriptive comparison)" if descriptive else "95% t interval of run values"
        if not descriptive:
            if saved and saved.get("ci_low") is not None:
                low, high = float(saved["ci_low"]), float(saved["ci_high"])
            elif len(values) >= 2:
                half = float(stats.t.ppf(.975, len(values) - 1) * values.std(ddof=1) / np.sqrt(len(values)))
                low, high = mean - half, mean + half
        summaries[group] = (mean, low, high, len(values), interval)

    candidates = [r["value"] for r in rows] + [u["value"] for u in units if u["condition"] in order]
    candidates += [v for s in summaries.values() for v in (s[0], s[1], s[2]) if v is not None]
    bottom, top, ticks = _y_range(candidates, scale, plot)
    span = top - bottom
    line_step = .085 * span
    # Adjacent contrasts sit lowest; brackets that do not overlap share a level.
    position = {group: i for i, group in enumerate(order)}
    brackets.sort(key=lambda b: (abs(position[b.left] - position[b.right]), min(position[b.left], position[b.right])))
    occupied: list[list[tuple[float, float]]] = []
    level_of = []
    for bracket in brackets:
        first, last = sorted((position[bracket.left], position[bracket.right]))
        lo, hi = first + .08, last - .08
        for k, taken in enumerate(occupied):
            if all(hi <= a or lo >= b for a, b in taken):
                taken.append((lo, hi))
                level_of.append(k)
                break
        else:
            occupied.append([(lo, hi)])
            level_of.append(len(occupied) - 1)
    heights = [max(len(b.lines) for b, k in zip(brackets, level_of, strict=True) if k == level) * line_step + .06 * span
               for level in range(len(occupied))]
    levels = [top + .05 * span + sum(heights[:k]) for k in level_of]
    headroom = (sum(heights) + .03 * span) if brackets else .02 * span
    ax.set_xlim(-.6, len(order) - .4)
    ax.set_ylim(bottom - .01 * span if bottom != 0 else bottom, top + headroom)
    if canonical.get("metric") in COUNT_METRICS and plot.get("y_tick_step") is None:
        counted = MaxNLocator(nbins=5, integer=True, min_n_ticks=3).tick_values(bottom, top)
        ticks = counted[(counted >= bottom - 1e-9) & (counted <= top + 1e-9)]
        top = max(top, float(ticks.max()))
    ax.set_yticks(ticks)
    formatter, multiplier = value_formatter(scale, ticks)
    ax.yaxis.set_major_formatter(formatter)
    ax.spines["left"].set_bounds(bottom, top)
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="x", length=0, pad=3)
    if scale in ("difference", "log2") and bottom < 0 < top:
        ax.axhline(0, color=MUTED, linewidth=.4, linestyle=(0, (2, 2)), zorder=0)

    # Freeze the layout so marker sizes can be converted to data units for the swarm.
    title, unit = axis_title(canonical)
    noun, nouns = observation_noun(canonical)
    unit_note = "%" if scale == "fraction" else unit
    if multiplier:
        unit_note = f"{multiplier} {unit}".strip()
    counts = {g: sum(r["condition"] == g for r in rows) for g in order}
    run_word = "runs" if paired else ""
    group_width = (fig.get_figwidth() / MM - 28) / max(1, len(order))
    labels = [wrap_label(group, max(9.0, group_width), plot.get("font_size") or 7)
              + f"\nn = {summaries[group][3]}" + (f" {run_word}" if run_word else "") for group in order]
    ax.set_xticks(range(len(order)), labels)
    # The title runs along the value axis: about the figure's height less the group labels.
    ax.set_ylabel(plot.get("y_label") or fit_axis_title(_full_title(title, unit_note, ""),
                                                        max(24.0, fig.get_figheight() / MM - 16), plot.get("font_size") or 7))
    # A panel takes the width of each axis-title line past the second, so the group labels keep theirs.
    extra = ax.get_ylabel().count("\n") - 1
    if extra > 0 and presentation.get("size", "panel") == "panel":
        fig.set_figwidth(fig.get_figwidth() + extra * 3.2 * MM)
    if plot.get("x_label"):
        ax.set_xlabel(plot["x_label"])
    legend = None
    if by_run and (plot.get("style") or {}).get("show_legend", True):
        handles = [Line2D([], [], marker=run_marker(i) if i >= len(OKABE_ITO) else "o", linestyle="",
                          markerfacecolor=colours[run], markeredgecolor=INK, markeredgewidth=.4, markersize=3.8,
                          label=str(run)) for i, run in enumerate(runs)]
        legend = ax.legend(handles=handles, title="Run", loc="upper left", bbox_to_anchor=(1.0, 1.0),
                           alignment="left", handlelength=.8)
        legend.get_title().set_fontsize(max(5.0, (plot.get("font_size") or 7) - .5))
    tick_height = .025 * span
    for bracket, y in zip(brackets, levels, strict=True):
        left, right = sorted((position[bracket.left], position[bracket.right]))
        ax.plot([left, left, right, right], [y - tick_height, y, y, y - tick_height], color=INK, linewidth=.5,
                clip_on=False, zorder=6)
        ax.text((left + right) / 2, y + .015 * span, "\n".join(bracket.lines), ha="center", va="bottom",
                fontsize=max(5.0, (plot.get("font_size") or 7) - .5), linespacing=1.15, zorder=6)
    bind_fonts(fig)
    fig.canvas.draw()
    fig.set_layout_engine("none")
    # A one-panel figure at column width keeps the panel's proportions, centred in the width.
    widest = (16 * len(order) + 8) * MM * fig.dpi
    current = ax.get_window_extent()
    if current.width > widest:
        x0, y0, w, h = ax.get_position().bounds
        new_w = w * widest / current.width
        ax.set_position([x0 + (w - new_w) / 2, y0, new_w, h])
        fig.canvas.draw()
    box = ax.get_window_extent()
    xspan, yspan = np.diff(ax.get_xlim())[0], np.diff(ax.get_ylim())[0]
    to_dx = lambda points: points / 72 * fig.dpi / box.width * xspan  # noqa: E731
    to_dy = lambda points: points / 72 * fig.dpi / box.height * yspan  # noqa: E731

    run_size = float(plot.get("point_size") or 26)
    total = max(counts.values() or [0])
    observation_size = 7.0 if total <= 40 else 4.5 if total <= 150 else 2.6 if total <= 600 else 1.4
    observation_size = min(observation_size, run_size / 3)
    obs_d = np.sqrt(observation_size)
    run_d = np.sqrt(run_size)

    for i, group in enumerate(order):
        mean, low, high, n_units, interval = summaries[group]
        group_rows = [r for r in rows if r["condition"] == group]
        values = np.array([r["value"] for r in group_rows], dtype=float)
        if bars:
            ax.bar(i, mean, width=.62, color=BAR_FILL, edgecolor=INK, linewidth=.5, zorder=.5)
        if presentation["observations"] == "violin" and len(values) >= 3 and np.ptp(values) > 0:
            grid = np.linspace(values.min(), values.max(), 120)
            density = stats.gaussian_kde(values, bw_method="scott")(grid)
            width = density / density.max() * .36
            ax.fill_betweenx(grid, i - width, i + width, facecolor=DENSITY_FILL, edgecolor=DENSITY_EDGE,
                             linewidth=.4, zorder=1)
            drawn.description.setdefault("density", "Gaussian kernel density, Scott bandwidth, observed range")
        elif presentation["observations"] == "box" and len(values) >= 3:
            q1, median, q3 = np.quantile(values, [.25, .5, .75], method="linear")
            inside = values[(values >= q1 - 1.5 * (q3 - q1)) & (values <= q3 + 1.5 * (q3 - q1))]
            ax.bxp([{"med": median, "q1": q1, "q3": q3, "whislo": float(inside.min()), "whishi": float(inside.max())}],
                   positions=[i], widths=.5, showfliers=False, manage_ticks=False, zorder=1,
                   boxprops={"color": DENSITY_EDGE, "linewidth": .5}, medianprops={"color": DENSITY_EDGE, "linewidth": .7},
                   whiskerprops={"color": DENSITY_EDGE, "linewidth": .5}, capprops={"linewidth": 0})
        if presentation["observations"] != "none" and len(values):
            offsets = beeswarm(values, dx=to_dx(obs_d * 1.05), dy=to_dy(obs_d * 1.05), half_width=.33)
            colour = [colours[r.get("pair")] if by_run else colours[group] for r in group_rows]
            collection = ax.scatter(i + offsets, values, s=observation_size, c=colour, alpha=.55, linewidths=0,
                                    zorder=2, rasterized=False)
            bind_points(collection, group_rows, keys=("field_id", "region_id", "nucleus_id"), focusable=False)
        group_units = [u for u in units if u["condition"] == group]
        unit_values = np.array([u["value"] for u in group_units], dtype=float)
        unit_offsets = beeswarm(unit_values, dx=to_dx(run_d), dy=to_dy(run_d), half_width=.18)
        if not bars:
            ax.hlines(mean, i - .27, i + .27, color=INK, linewidth=1.1, zorder=4.5)
        if low is not None and high is not None:
            ax.errorbar(i, mean, yerr=[[mean - low], [high - mean]], fmt="none", ecolor=INK, elinewidth=.7,
                        capsize=2.2, capthick=.7, zorder=4.4)
        for j, unit in enumerate(group_units):
            index = runs.index(unit["pair"]) if unit.get("pair") in runs else j
            colour = colours[unit["pair"]] if by_run else colours[group]
            marker = run_marker(index) if by_run else "o"
            collection = ax.scatter([i + unit_offsets[j]], [unit["value"]], s=run_size, color=colour, marker=marker,
                                    edgecolor=INK, linewidth=.5, zorder=5)
            bind_points(collection, [unit])
            drawn.glyphs.append({**unit, "display_x": float(i + unit_offsets[j]), "display_y": unit["value"]})
        drawn.summary.append({"condition": group, "mean": mean, "ci_low": low, "ci_high": high,
                              "n_units": n_units, "observations": int(len(values)), "interval": interval})
    if paired:
        positions = {(g["condition"], g["experimental_unit"]): g["display_x"] for g in drawn.glyphs}
        for pair in canonical["pair_ledger"]:
            if pair["status"] != "selected":
                continue
            members = [(positions.get((c, pair["units"][c])),
                        next((u["value"] for u in units if u["condition"] == c and u["experimental_unit"] == pair["units"][c]), None))
                       for c in order]
            if any(x is None or y is None for x, y in members):
                continue
            ax.plot([x for x, _ in members], [y for _, y in members], color=colours.get(pair["pair"], MUTED) if by_run else MUTED,
                    linewidth=.6, alpha=.9, zorder=3)
    bind_fonts(fig)
    drawn.description.update(observation=noun, observations=nouns, paired=paired, by_run=by_run, bars=bars,
                             counts=counts, runs=runs, title=title, unit=unit_note, scale=scale)
    if legend is not None:
        drawn.description["legend"] = "run colours"
    return drawn


def draw_association(fig, ax, canonical, plot, order) -> Drawn:
    drawn = Drawn()
    rows = canonical["unit_summary"]
    overrides = (plot.get("style") or {}).get("series_colors") or {}
    labels = {row.get("scope"): association_label(canonical, row) for row in canonical.get("associations") or []}
    handles = []
    for i, group in enumerate(order):
        points = [r for r in rows if r["condition"] == group]
        colour = overrides.get(group, OKABE_ITO[i % len(OKABE_ITO)])
        bind_points(ax.scatter([r["x"] for r in points], [r["y"] for r in points], s=float(plot.get("point_size") or 22),
                               color=colour, edgecolor=INK, linewidth=.4, zorder=3), points)
        drawn.glyphs.extend({**r, "display_x": r["x"], "display_y": r["y"]} for r in points)
        stat = labels.get(group) or labels.get("pooled")
        handles.append(Line2D([], [], marker="o", linestyle="", markerfacecolor=colour, markeredgecolor=INK,
                              markeredgewidth=.4, markersize=4,
                              label=f"{group} (n = {len(points)})" + (f"\n{stat}" if stat and group in labels else "")))
    if "pooled" in labels:
        ax.text(.02, .98, labels["pooled"] + " (pooled)", transform=ax.transAxes, ha="left", va="top")
    for axis, source in (("x", canonical["x_source"]), ("y", canonical["y_source"])):
        title, unit = axis_title(source)
        label = plot.get(f"{axis}_label") or _full_title(title, "%" if _scale(source) == "fraction" else unit, "")
        getattr(ax, f"set_{axis}label")(fit_axis_title(label, 34, plot.get("font_size") or 7))
        values = [r[axis] for r in rows]
        formatter, _ = value_formatter(_scale(source), values)
        getattr(ax, f"{axis}axis").set_major_formatter(formatter)
        getattr(ax, f"{axis}axis").set_major_locator(MaxNLocator(5))
    if (plot.get("style") or {}).get("show_legend", True):
        ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.0, 1.0), handlelength=.8)
    bind_fonts(fig)
    drawn.annotations.legend = [f"{scope}: {text}" for scope, text in labels.items()]
    drawn.description.update(observation="run", observations="runs")
    return drawn
