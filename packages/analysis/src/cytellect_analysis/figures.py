"""Source-linked vector figures with an explicit journal-size preset."""
import hashlib
import json
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.text import Text

from .exports_csv import write_csv

FIGURE_VERSION = "1.1.3"
COLORS = ["#0072b2", "#d55e00", "#009e73", "#cc79a7", "#e69f00", "#56b4e9", "#000000"]
MARKERS = ["o", "s", "^", "v", "P", "X", "D", "<", ">"]
LABELS = {
    "ncl_log2_nucleoplasm_over_nucleoli": (
        "NCL nucleoplasm / nucleoli\n(log2 mean intensity ratio)",
        "NCL 核質 / 核小体\n（平均輝度比の log2）"),
    "ncl_legacy_release": (
        "NCL nucleus / high-intensity region\n(legacy log2 ratio)",
        "NCL 核全体 / 高輝度領域\n（互換 log2 比）"),
    "ncl_nucleus_mean_corrected": (
        "Nuclear NCL mean intensity\n(background corrected, a.u.)",
        "核内 NCL 平均輝度\n（背景補正、任意単位）"),
    "gfp_mean_corrected": (
        "Nuclear GFP mean intensity\n(background corrected, a.u.)",
        "核内 GFP 平均輝度\n（背景補正、任意単位）"),
    "nucleolar_area_fraction": ("Nucleolar area / nuclear area", "核小体面積 / 核面積"),
    "value": ("Measured value", "測定値"),
    "ncl_nucleoplasm_over_nucleoli": ("NCL nucleoplasm / nucleoli\n(mean intensity ratio)", "NCL 核質 / 核小体\n（平均輝度比）"),
    "nucleolar_count": ("Nucleolar candidates per nucleus", "核あたりの核小体候補数"),
}

for _region, _english, _japanese in (("nucleus", "Nuclear", "核全体"),
                                    ("nucleoli", "Nucleolar union", "核小体和集合"),
                                    ("nucleoplasm", "Nucleoplasmic", "核質")):
    for _stat, _stat_en, _stat_ja in (("mean", "mean", "平均"), ("median", "median", "中央値"),
                                     ("integrated", "integrated", "積算")):
        for _corrected in (False, True):
            _suffix = "_corrected" if _corrected else ""
            _correction_en = "background corrected" if _corrected else "raw"
            _correction_ja = "背景補正" if _corrected else "原値"
            _unit_en, _unit_ja = ("a.u. × pixel", "任意単位 × 画素") if _stat == "integrated" else ("a.u.", "任意単位")
            LABELS[f"ncl_{_region}_{_stat}{_suffix}"] = (
                f"{_english} NCL {_stat_en} intensity\n({_correction_en}, {_unit_en})",
                f"{_japanese} NCL {_stat_ja}輝度\n（{_correction_ja}、{_unit_ja}）")
            if _region == "nucleus":
                LABELS[f"gfp_{_stat}{_suffix}"] = (
                    f"Nuclear GFP {_stat_en} intensity\n({_correction_en}, {_unit_en})",
                    f"核全体 GFP {_stat_ja}輝度\n（{_correction_ja}、{_unit_ja}）")
for _area, _english, _japanese in (("nucleus", "Nuclear", "核全体"),
                                  ("nucleolar", "Nucleolar union", "核小体和集合"),
                                  ("nucleoplasm", "Nucleoplasmic", "核質")):
    LABELS[f"{_area}_area_px"] = (f"{_english} area (pixel²)", f"{_japanese}面積（画素²）")
    LABELS[f"{_area}_area_um2"] = (f"{_english} area (µm²)", f"{_japanese}面積（µm²）")


def metric_label(result, language):
    """Label existing values on their actual measurement grid without recalculation."""
    metric = result["spec"]["metric"]
    label = LABELS.get(metric, (metric, metric))[language == "ja"]
    legacy = any(row.get("recipe_id") == "ncl-legacy-rgb" for row in result["plot_data"])
    if legacy:
        if "_integrated" in metric:
            label = label.replace("a.u. × pixel", "a.u. × scaled pixel").replace("任意単位 × 画素", "任意単位 × 縮小画素")
        label = label.replace("Nucleolar union", "High-intensity union").replace("核小体和集合", "高輝度領域の和集合")
    return label


def export_statistical_tables(result, output):
    """Expose saved inference and scenarios; no refits or extra significance correction."""
    model = result.get("model") or {}
    if model:
        coefficients = model.get("coefficient_table") or [
            {"term": term, "estimate": estimate, "status": "estimate_only_no_saved_inference"}
            for term, estimate in model.get("coefficients", {}).items()]
        write_csv(output / "model-coefficients.csv", coefficients)
        write_csv(output / "repeat-trend.csv", [{
            "status": model.get("trend_status", "succeeded" if model.get("trend") else "not_available"),
            "reason": model.get("trend_reason"), **(model.get("trend") or {})}])
    scenarios = result.get("sensitivities") or []
    if not scenarios:
        return
    status_rows: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    counts: list[dict[str, Any]] = []
    for scenario in scenarios:
        analysis = scenario.get("result") or {}
        selection = analysis.get("selection") or {}
        label = {"scenario": scenario["scenario"], "status": scenario["status"]}
        status_rows.append({**label, "reason": scenario.get("reason"),
                            "warnings": "; ".join(analysis.get("warnings", [])),
                            **{key: selection.get(key) for key in
                               ("input_rows", "excluded", "gfp_unselected", "missing_metric_selected")}})
        comparisons.extend({**label, **row} for row in analysis.get("comparisons", []))
        for row in analysis.get("counts", []):
            group_selection: dict[str, Any] = next((s for s in selection.get("by_condition", []) if s["condition"] == row["condition"]), {})
            counts.append({**label, **row, **{f"selection_{key}": value for key, value in group_selection.items() if key != "condition"}})
    write_csv(output / "sensitivity-status.csv", status_rows)
    # Fixed downloadable tables remain present even if every scenario is not estimable.
    write_csv(output / "sensitivity-comparisons.csv", comparisons)
    write_csv(output / "sensitivity-counts.csv", counts)


FONT_FAMILIES = {
    "ja": ("Noto Sans CJK JP", "Noto Sans JP", "Yu Gothic", "Meiryo", "IPAexGothic"),
    "en": ("Arial", "Liberation Sans", "DejaVu Sans"),
}
NORMAL_WEIGHT_RANGE = (350, 500)


@dataclass(frozen=True)
class FigureFont:
    family: str
    path: Path
    weight: int
    style: str

    def metadata(self):
        # The file identity is reproducible without exporting a user's OS path.
        return {"family": self.family, "weight": self.weight, "style": self.style,
                "sha256": hashlib.sha256(self.path.read_bytes()).hexdigest()}


def _weight_number(value):
    return int(font_manager.weight_dict.get(value, 0)) if isinstance(value, str) else int(value)


def select_font(language, text=""):
    """Choose an actual normal-weight face covering every literal figure glyph."""
    required = {ord(character) for character in text + "0123456789.eE+-" if not character.isspace()}
    normal_available = False
    # Output language chooses the preferred typography, not the scripts allowed
    # in literal source labels. Every candidate still needs complete glyphs.
    fallback_language = "ja" if language == "en" else "en"
    families = tuple(dict.fromkeys((*FONT_FAMILIES[language], *FONT_FAMILIES[fallback_language])))
    for family in families:
        candidates = [entry for entry in font_manager.fontManager.ttflist
                      if entry.name == family and entry.style == "normal"
                      and NORMAL_WEIGHT_RANGE[0] <= _weight_number(entry.weight) <= NORMAL_WEIGHT_RANGE[1]]
        candidates.sort(key=lambda entry: (abs(_weight_number(entry.weight) - 400),
                        entry.stretch != "normal", str(entry.fname).casefold()))
        for entry in candidates:
            try:
                loaded = font_manager.get_font(entry.fname)
                # Inspect the file, not just a possibly stale font-cache entry.
                actual = font_manager.ttfFontProperty(loaded)
                weight = _weight_number(actual.weight)
                if actual.style != "normal" or not NORMAL_WEIGHT_RANGE[0] <= weight <= NORMAL_WEIGHT_RANGE[1]:
                    continue
                normal_available = True
                if required.issubset(loaded.get_charmap()):
                    return FigureFont(actual.name, Path(entry.fname), weight, actual.style)
            except (OSError, RuntimeError, ValueError):
                continue
    if normal_available:
        raise ValueError("figure_font_glyphs_unavailable")
    raise ValueError("japanese_font_not_installed" if language == "ja" else "sans_serif_font_not_installed")


def japanese_font():
    return select_font("ja", "測定値").family


def english_font():
    return select_font("en").family


def figure_settings(plot):
    preset = plot.get("preset", "custom")
    width = {"nature-single": 89 / 25.4, "nature-double": 183 / 25.4}.get(preset, plot["width_inches"])
    height, font_size = plot["height_inches"], plot["font_size"]
    if preset != "custom" and (height > 170 / 25.4 or not 5 <= font_size <= 7):
        raise ValueError("nature_preset_requires_height_at_most_170mm_and_font_5_to_7pt")
    return {"preset": preset, "width_inches": width, "height_inches": height,
            "width_mm": width * 25.4, "height_mm": height * 25.4, "font_size_pt": font_size,
            "line_width_pt": .6, "png_dpi": 300}


def series_color(plot, key, fallback):
    return (plot.get("style") or {}).get("series_colors", {}).get(str(key), fallback)


def apply_plot_controls(axes, plot):
    """Presentation-only controls; omitted fields preserve historical rendering."""
    display_axes = plot.get("axes") or {}
    for axis, dimension in (("x", 0), ("y", 1)):
        scale = display_axes.get(f"{axis}_scale", "linear")
        if scale != "linear":
            # Examine all plotted values, including intervals and connecting lines.
            # Log display must never silently mask non-positive observations/intervals.
            from matplotlib.collections import LineCollection, PathCollection, PolyCollection
            values = []
            for collection in axes.collections:
                if isinstance(collection, PathCollection):
                    values.extend(np.asarray(collection.get_offsets())[:, dimension].ravel())
                elif isinstance(collection, LineCollection):
                    for segment in collection.get_segments():
                        values.extend(np.asarray(segment)[:, dimension].ravel())
                elif isinstance(collection, PolyCollection):
                    for path in collection.get_paths():
                        values.extend(path.vertices[:, dimension].ravel())
            for line in axes.lines:
                values.extend(np.asarray(line.get_xdata() if axis == "x" else line.get_ydata(), dtype=float).ravel())
            values = np.asarray(values, dtype=float)
            if not len(values) or not np.isfinite(values).all() or np.any(values <= 0):
                raise ValueError("figure_log_requires_positive_values")
            getattr(axes, f"set_{axis}scale")("log", base=2 if scale == "log2" else 10)
    if plot.get("kind") != "scatter" and any(display_axes.get(key) is not None for key in ("x_min", "x_max", "x_tick_step")):
        raise ValueError("figure_numeric_x_requires_scatter")
    xlow, xhigh = axes.get_xlim()
    xlow = display_axes.get("x_min") if display_axes.get("x_min") is not None else xlow
    xhigh = display_axes.get("x_max") if display_axes.get("x_max") is not None else xhigh
    xstep = display_axes.get("x_tick_step")
    if xstep is not None or display_axes.get("x_min") is not None or display_axes.get("x_max") is not None:
        if not np.isfinite([xlow, xhigh]).all() or xlow >= xhigh:
            raise ValueError("figure_x_range_invalid")
        if xstep is not None:
            if not np.isfinite(xstep) or xstep <= 0 or (xhigh - xlow) / xstep > 99:
                raise ValueError("figure_tick_count_exceeded")
            axes.set_xticks(xlow + np.arange(int(np.floor((xhigh-xlow)/xstep))+1)*xstep)
        axes.set_xlim(xlow, xhigh)
    lower, upper = axes.get_ylim()
    lower = plot.get("y_min") if plot.get("y_min") is not None else lower
    upper = plot.get("y_max") if plot.get("y_max") is not None else upper
    if not np.isfinite([lower, upper]).all() or lower >= upper:
        raise ValueError("figure_y_range_invalid")
    step = plot.get("y_tick_step")
    if step is not None:
        if not np.isfinite(step) or step <= 0 or (upper - lower) / step > 99:
            raise ValueError("figure_tick_count_exceeded")
        # Anchor ticks at the explicit/auto lower bound. Bound work before allocation.
        ticks = lower + np.arange(int(np.floor((upper - lower) / step)) + 1) * step
        axes.set_yticks(ticks)
    if step is not None or plot.get("y_min") is not None or plot.get("y_max") is not None:
        axes.set_ylim(lower, upper)
    if plot.get("point_size") is not None:
        from matplotlib.collections import PathCollection
        for collection in axes.collections:
            if isinstance(collection, PathCollection):
                collection.set_sizes([plot["point_size"]])
    if (plot.get("style") or {}).get("show_legend") is False:
        if axes.get_legend() is not None:
            axes.get_legend().remove()
        for legend in list(axes.figure.legends):
            legend.remove()


def _validate_text_layout(figure, axes):
    """Reject demonstrably unreadable labels before publishing figure files."""
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    omitted_tick_labels = set()
    for axis in (axes.xaxis, axes.yaxis):
        lower, upper = sorted(axis.get_view_interval())
        drawn_labels = []
        for tick in axis.get_major_ticks():
            for label in (tick.label1, tick.label2):
                if not lower <= tick.get_loc() <= upper:
                    omitted_tick_labels.add(label)
                elif label.get_visible() and label.get_text():
                    drawn_labels.append(label)
        boxes = [label.get_window_extent(renderer) for label in drawn_labels]
        if any(left.overlaps(right) for index, left in enumerate(boxes) for right in boxes[index + 1:]):
            raise ValueError("figure_labels_overlap")
    canvas = figure.bbox
    for label in figure.findobj(match=Text):
        if not label.get_visible() or not label.get_text() or label in omitted_tick_labels:
            continue
        box = label.get_window_extent(renderer)
        # One display pixel tolerates backend/font rounding at the canvas edge.
        if (box.x0 < canvas.x0 - 1 or box.y0 < canvas.y0 - 1
                or box.x1 > canvas.x1 + 1 or box.y1 > canvas.y1 + 1):
            raise ValueError("figure_text_outside_canvas")


def _caption(result, note):
    lines = ["# Figure legend", "", note, "",
             "Aggregation: field median → mean of fields within sample → mean of samples within independent unit.",
             "Group diamonds show the reported mean and pointwise 95% confidence interval; these intervals are not multiplicity-adjusted.",
             "The paired-test interval describes paired differences and is reported in comparisons.csv.",
             "All tests are two-sided. Holm correction applies only to the declared comparison family, not to the plotted mean intervals.", ""]
    if not result["spec"].get("paired"):
        lines = [line for line in lines if not line.startswith("The paired-test interval")]
    if result["spec"]["plot"]["kind"] == "scatter":
        lines = [line for line in lines if not line.startswith("Group diamonds")]
    for row in result["counts"]:
        lines.append(f"- {row['condition']}: observations={row.get('cells', row.get('observations', 0))}; "
                     f"fields={row['fields']}; independent units={row['experimental_units']}.")
    for row in result["comparisons"]:
        lines.append(f"- {row['group_a']} − {row['group_b']}: {row['method']}; "
                     f"estimate={row['estimate']:.8g}; 95% CI [{row['ci_low']:.8g}, {row['ci_high']:.8g}]; "
                     f"t={row.get('statistic')}; df={row.get('degrees_of_freedom')}; "
                     f"p={row['p_value']:.8g}; Holm p={row.get('p_holm')}.")
    lines += ["", "Selection and warnings are recorded in figure-data.json and the statistics output.",
              "A journal-size preset controls formatting; it does not establish biological validity or journal acceptance."]
    lines += [f"- {warning}" for warning in result.get("warnings", [])]
    return "\n".join(lines) + "\n"


def render_figures(result, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    spec, plot = result["spec"], result["spec"]["plot"]
    metric = spec["metric"]
    cells, units = pd.DataFrame(result["plot_data"]), pd.DataFrame(result["unit_summary"])
    fields = pd.DataFrame(result["field_summary"])
    observed = list(cells.condition.unique())
    order = plot["group_order"] or observed
    if set(order) != set(observed) or len(order) != len(set(order)):
        raise ValueError("group_order_must_match_groups")
    style = figure_settings(plot)
    ja = plot["language"] == "ja"
    font = japanese_font() if ja else english_font()
    size = style["font_size_pt"]
    if plot["kind"] == "paired" and not spec.get("paired", False):
        raise ValueError("paired_plot_requires_paired_inference")
    paired = spec.get("paired", False)
    glyphs = {}
    with plt.rc_context({"font.size": size, "axes.titlesize": size, "axes.labelsize": size, "legend.fontsize": size,
          "xtick.labelsize": size, "ytick.labelsize": size, "svg.fonttype": "none", "pdf.fonttype": 42,
          "font.family": [font], "font.weight": "normal", "axes.labelweight": "normal",
          "axes.titleweight": "normal", "text.usetex": False, "text.parse_math": False,
          "axes.unicode_minus": False, "axes.linewidth": .6,
          "lines.linewidth": .6, "xtick.major.width": .6, "ytick.major.width": .6,
          "xtick.major.size": 2.5, "ytick.major.size": 2.5, "text.color": "black",
          "svg.hashsalt": "cytellect-figure-v" + FIGURE_VERSION, "savefig.facecolor": "white"}):
        fig, ax = plt.subplots(figsize=(style["width_inches"], style["height_inches"]), layout="constrained")
        rng = np.random.default_rng(0)
        try:
            if plot["kind"] == "scatter":
                if "gfp_mean_corrected" not in cells:
                    raise ValueError("gfp_scatter_requires_image_measurements")
                exploratory = spec["mode"] == "exploratory"
                predictions = pd.DataFrame((result.get("model") or {}).get("prediction_grid", []))
                if exploratory and (predictions.empty or "gfp_centered" not in cells):
                    raise ValueError("cluster_prediction_grid_required")
                x_metric = "gfp_centered" if exploratory else "gfp_mean_corrected"
                if not np.isfinite(pd.to_numeric(cells[x_metric], errors="coerce")).all():
                    raise ValueError("scatter_requires_finite_gfp_for_all_selected_rows")
                for i, group in enumerate(order):
                    d = cells[cells.condition == group]
                    x, y = d[x_metric].to_numpy(dtype=float), d[metric].to_numpy(dtype=float)
                    valid = np.isfinite(x) & np.isfinite(y)
                    ax.scatter(x[valid], y[valid], s=9, alpha=.5, linewidths=0,
                               marker=MARKERS[i % len(MARKERS)], color=series_color(plot, group, COLORS[i % len(COLORS)]), label=group)
                    if exploratory:
                        prediction = predictions[predictions.condition == group].sort_values("gfp_centered")
                        ax.plot(prediction.gfp_centered, prediction["mean"], color=series_color(plot, group, COLORS[i % len(COLORS)]))
                        ax.fill_between(prediction.gfp_centered, prediction.ci_low, prediction.ci_high,
                                        color=series_color(plot, group, COLORS[i % len(COLORS)]), alpha=.15, linewidth=0)
                ax.set_xlabel(plot["x_label"] or (
                    (("log2(max(GFP, 0) + 1)（撮影日内中心化）" if ja else "log2(max(GFP, 0) + 1)\n(centered within acquisition date)")
                     if spec.get("gfp_transform") == "legacy-log2p1" else
                     ("log2 GFP（撮影日内中央値で中心化）" if ja else "log2 GFP (centered within acquisition date)"))
                    if exploratory else LABELS["gfp_mean_corrected"][int(ja)]))
                ax.legend(frameon=False, markerscale=1.5, handletextpad=.5)
                note = ("Points are observed outcomes. Lines average the fitted mean over acquisition dates; "
                        "bands are field-clustered CRV1 pointwise 95% mean confidence intervals, with fields−1 degrees of freedom. "
                        "A common GFP slope is used by the saved model; group-specific slopes are not inferred."
                        if exploratory else "Observed GFP/outcome association only; no regression or cell-independent confidence band is inferred.")
            else:
                identities = sorted({str(r.get("pair") if paired and r.get("pair") else r["experimental_unit"])
                                     for r in result["unit_summary"]})
                glyphs = {identity: {"color": COLORS[i % len(COLORS)],
                                    "marker": MARKERS[(i // len(COLORS)) % len(MARKERS)]}
                          for i, identity in enumerate(identities)}
                for i, group in enumerate(order):
                    values = cells.loc[cells.condition == group, metric].to_numpy()
                    ax.scatter(i + rng.uniform(-.18, .18, len(values)), values,
                               s=5, color=series_color(plot, group, "#929292"), alpha=.28, linewidths=0)
                    fv = fields.loc[fields.condition == group, metric].to_numpy()
                    ax.scatter(i - .25 + np.zeros(len(fv)), fv, s=12, marker="s",
                               facecolors="none", edgecolors="#555555", linewidths=.5, alpha=.7)
                    for row in units[units.condition == group].to_dict("records"):
                        key = str(row.get("pair") if paired and row.get("pair") else row["experimental_unit"])
                        ax.scatter(i, row[metric], s=20, color=series_color(plot, group, glyphs[key]["color"]),
                                   marker=glyphs[key]["marker"], edgecolor="white", linewidth=.35, zorder=3)
                    mean = next(v for v in result["means"] if v["condition"] == group)
                    if mean["ci_low"] is not None:
                        ax.errorbar(i + .25, mean["mean"],
                                    yerr=[[max(0, mean["mean"] - mean["ci_low"])],
                                          [max(0, mean["ci_high"] - mean["mean"])]],
                                    fmt="D", markersize=3, color="black", capsize=2, capthick=.6, zorder=4)
                if paired:
                    if ("pair" not in units or units.pair.isna().any()
                            or units.duplicated(["condition", "pair"]).any()):
                        raise ValueError("paired_plot_requires_unique_pairs")
                    for _, pair in units.groupby("pair"):
                        indexed = pair.set_index("condition")
                        present = [g for g in order if g in indexed.index]
                        ax.plot([order.index(g) for g in present], [indexed.loc[g, metric] for g in present],
                                color="#aaaaaa", lw=.5, zorder=0)
                ticks = []
                for group in order:
                    count = next(c for c in result["counts"] if c["condition"] == group)
                    ticks.append(textwrap.fill(group, width=16) + f"\nn = {count['experimental_units']}")
                ax.set_xticks(range(len(order)), ticks)
                ax.set_xlim(-.6, len(order) - .4)
                ax.set_xlabel(plot["x_label"] or ("条件（n：独立実験単位）" if ja else "Condition (n: independent units)"))
                labels = (["観測値", "視野中央値", "独立単位", "平均・95% CI"] if ja else
                          ["Observation", "Field median", "Independent unit", "Mean, 95% CI"])
                fig.legend(handles=[Line2D([], [], marker=marker, linestyle="", color="#555555", label=label,
                                          markersize=marker_size, markerfacecolor="none" if marker == "s" else "#555555") for marker, marker_size, label in
                                   zip([".", "s", "o", "D"], [3, 3, 4, 3], labels, strict=True)],
                          loc="outside upper center", frameon=False, ncols=2, columnspacing=.8, handletextpad=.4)
                note = ("Diamonds are GFP/date-adjusted means; observation and unit points are unadjusted. "
                        if spec["mode"] == "exploratory" else "Diamonds are means of independent experimental units. ")
                note += ("Lines connect declared matched pairs. " if paired else "")
                note += "Unit color/shape identities are recorded in figure-data.json; jitter affects display only (seed 0)."
            ylabel = plot["y_label"] or metric_label(result, "ja" if ja else "en")
            if result.get("unit"):
                ylabel += f" ({result['unit']})"
            ax.set_ylabel(ylabel)
            ax.spines[["top", "right"]].set_visible(False)
            title = (("探索的解析", "Exploratory analysis") if spec["mode"] == "exploratory" else
                     (("対応ありの比較", "Paired comparison") if paired else ("群間比較", "Group comparison")))
            ax.set_title(title[0 if ja else 1], loc="left", pad=7)
            # Populate formatted tick labels before checking all labels; no draw
            # occurs until the selected regular face has been bound explicitly.
            ax.get_xticklabels()
            ax.get_yticklabels()
            texts = fig.findobj(match=Text)
            selected_font = select_font("ja" if ja else "en", "".join(t.get_text() for t in texts))
            font = selected_font.family
            font_metadata = selected_font.metadata()
            for item in texts:
                properties = item.get_fontproperties().copy()
                properties.set_file(str(selected_font.path))
                properties.set_family(font)
                properties.set_weight(selected_font.weight)
                item.set_fontproperties(properties)
            apply_plot_controls(ax, plot)
            _validate_text_layout(fig, ax)
            for suffix in ("svg", "pdf", "png"):
                metadata: dict[str, str | None] = {"Creator": "Cytellect " + FIGURE_VERSION}
                if suffix == "pdf":
                    metadata.update(CreationDate=None, ModDate=None)
                if suffix == "svg":
                    metadata.update(Date=None)
                fig.savefig(output / f"figure.{suffix}", dpi=style["png_dpi"], metadata=metadata)
        finally:
            plt.close(fig)
    for name, rows in (("plot-data", result["plot_data"]), ("comparisons", result["comparisons"]),
                       ("experimental-units", result["unit_summary"]), ("field-summary", result["field_summary"]),
                       ("model-predictions", (result.get("model") or {}).get("prediction_grid", []))):
        if rows:
            write_csv(output / f"{name}.csv", rows)
    export_statistical_tables(result, output)
    (output / "figure-caption.md").write_text(_caption(result, note), encoding="utf-8")
    source = {"figure_version": FIGURE_VERSION, "style": style, "spec": spec, "font": font,
              "font_metadata": font_metadata,
              "revision_id": result.get("revision_id"), "table_id": result.get("table_id"),
              "source_kind": result.get("source_kind"), "unit": result.get("unit"), "assay": result.get("assay"),
              "metric_id": metric,
              "unit_glyphs": glyphs, "counts": result["counts"], "means": result["means"],
              "selection": result.get("selection"), "statistics_version": result.get("statistics_version"),
              "warnings": result.get("warnings", []), "note": note,
              "source_hashes": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.glob("*.csv"))}}
    (output / "figure-data.json").write_text(json.dumps(source, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"figure_version": FIGURE_VERSION, "font": font, "font_metadata": font_metadata, "style": style,
            "formats": ["svg", "pdf", "png"], "svg_text": "editable",
            "scatter_band": ("field-clustered CRV1 pointwise 95% mean CI" if spec["mode"] == "exploratory"
                             else None) if plot["kind"] == "scatter" else None,
            "source_files": ["figure-caption.md", "figure-data.json", "plot-data.csv", "comparisons.csv"]}
