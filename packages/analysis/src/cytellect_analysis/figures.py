"""Source-linked vector figures with an explicit journal-size preset."""
import hashlib
import json
import textwrap
from dataclasses import dataclass
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.text import Text

from .exports_csv import write_csv

FIGURE_VERSION = "1.1.1"
COLORS = ["#0072b2", "#d55e00", "#009e73", "#cc79a7", "#e69f00", "#56b4e9", "#000000"]
MARKERS = ["o", "s", "^", "v", "P", "X", "D", "<", ">"]
LABELS = {
    "ncl_log2_nucleoplasm_over_nucleoli": (
        "NCL nucleoplasm / nucleoli\n(log₂ mean intensity ratio)",
        "NCL 核質 / 核小体\n（平均輝度比の log₂）"),
    "ncl_legacy_release": (
        "NCL nucleus / high-intensity region\n(legacy log₂ ratio)",
        "NCL 核全体 / 高輝度領域\n（互換 log₂ 比）"),
    "ncl_nucleus_mean_corrected": (
        "Nuclear NCL mean intensity\n(background corrected, a.u.)",
        "核内 NCL 平均輝度\n（背景補正、任意単位）"),
    "gfp_mean_corrected": (
        "Nuclear GFP mean intensity\n(background corrected, a.u.)",
        "核内 GFP 平均輝度\n（背景補正、任意単位）"),
    "nucleolar_area_fraction": ("Nucleolar area / nuclear area", "核小体面積 / 核面積"),
    "value": ("Measured value", "測定値"),
}


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
    for family in FONT_FAMILIES[language]:
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
          "svg.hashsalt": "cytellect-figure-v1.1.1", "savefig.facecolor": "white"}):
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
                               marker=MARKERS[i % len(MARKERS)], color=COLORS[i % len(COLORS)], label=group)
                    if exploratory:
                        prediction = predictions[predictions.condition == group].sort_values("gfp_centered")
                        ax.plot(prediction.gfp_centered, prediction["mean"], color=COLORS[i % len(COLORS)])
                        ax.fill_between(prediction.gfp_centered, prediction.ci_low, prediction.ci_high,
                                        color=COLORS[i % len(COLORS)], alpha=.15, linewidth=0)
                ax.set_xlabel(plot["x_label"] or (
                    (("log₂(max(GFP, 0) + 1)（撮影日内中心化）" if ja else "log₂(max(GFP, 0) + 1)\n(centered within acquisition date)")
                     if spec.get("gfp_transform") == "legacy-log2p1" else
                     ("log₂ GFP（撮影日内中央値で中心化）" if ja else "log₂ GFP (centered within acquisition date)"))
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
                               s=5, color="#929292", alpha=.28, linewidths=0)
                    fv = fields.loc[fields.condition == group, metric].to_numpy()
                    ax.scatter(i - .25 + np.zeros(len(fv)), fv, s=12, marker="s",
                               facecolors="none", edgecolors="#555555", linewidths=.5, alpha=.7)
                    for row in units[units.condition == group].to_dict("records"):
                        key = str(row.get("pair") if paired and row.get("pair") else row["experimental_unit"])
                        ax.scatter(i, row[metric], s=20, color=glyphs[key]["color"],
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
            ylabel = plot["y_label"] or LABELS.get(metric, (metric, metric))[int(ja)]
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
