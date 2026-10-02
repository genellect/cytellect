"""Source-linked Matplotlib plots; editable text in SVG/PDF."""
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from scipy import stats

from .exports_csv import write_csv


def japanese_font():
    for name in ("Noto Sans CJK JP", "Noto Sans JP", "Yu Gothic", "Meiryo", "IPAexGothic"):
        try:
            font_manager.findfont(font_manager.FontProperties(family=name), fallback_to_default=False)
            return name
        except ValueError:
            continue
    raise ValueError("japanese_font_not_installed")


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
    ja = plot["language"] == "ja"
    font = japanese_font() if ja else "DejaVu Sans"
    fonts = [font, "DejaVu Sans"]
    with plt.rc_context({"font.size": plot["font_size"], "svg.fonttype": "none", "pdf.fonttype": 42,
                         "font.family": fonts, "axes.unicode_minus": False}):
        fig, ax = plt.subplots(figsize=(plot["width_inches"], plot["height_inches"]), layout="constrained")
        colors = ["#126c67", "#ca6f36", "#6b5a9b", "#4479a8", "#b74868"]
        rng = np.random.default_rng(0)
        note = ""
        try:
            if plot["kind"] == "scatter":
                if "gfp_mean_corrected" not in cells:
                    raise ValueError("gfp_scatter_requires_image_measurements")
                for i, group in enumerate(order):
                    d = cells[cells.condition == group]
                    x, y = d.gfp_mean_corrected.to_numpy(dtype=float), d[metric].to_numpy(dtype=float)
                    valid = np.isfinite(x) & np.isfinite(y)
                    x, y = x[valid], y[valid]
                    ax.scatter(x, y, s=18, alpha=.5, color=colors[i % len(colors)], label=group)
                    if len(x) >= 3 and np.ptp(x) > 0:
                        slope, intercept, *_ = stats.linregress(x, y)
                        grid = np.linspace(x.min(), x.max(), 100)
                        predicted = intercept + slope * grid
                        residual = np.sqrt(np.sum((y-intercept-slope*x)**2)/(len(x)-2))
                        band = (stats.t.ppf(.975, len(x)-2) * residual
                                * np.sqrt(1/len(x)+(grid-x.mean())**2/np.sum((x-x.mean())**2)))
                        ax.plot(grid, predicted, color=colors[i % len(colors)])
                        ax.fill_between(grid, predicted-band, predicted+band, color=colors[i % len(colors)], alpha=.12)
                ax.set_xlabel(plot["x_label"] or ("背景補正GFP平均輝度" if ja else "GFP mean intensity (background corrected)"))
                ax.legend(frameon=False)
                note = ("線・帯：群内の単純回帰と平均の95% CI（記述用、クラスタ補正なし）" if ja else
                        "Lines/bands: descriptive within-group simple regression and 95% mean CI; not cluster-adjusted")
            else:
                for i, group in enumerate(order):
                    color = colors[i % len(colors)]
                    values = cells.loc[cells.condition == group, metric].to_numpy()
                    ax.scatter(i+rng.uniform(-.18, .18, len(values)), values, s=9, color="#909797", alpha=.35)
                    fv = fields.loc[fields.condition == group, metric].to_numpy()
                    ax.scatter(i-.28+np.zeros(len(fv)), fv, s=22, marker="s",
                               facecolors="none", edgecolors=color, alpha=.7)
                    uv = units.loc[units.condition == group, metric].to_numpy()
                    ax.scatter(np.full(len(uv), i), uv, s=42, color=color, edgecolor="white", zorder=3)
                    mean = next(v for v in result["means"] if v["condition"] == group)
                    if mean["ci_low"] is not None:
                        ax.errorbar(i+.28, mean["mean"], yerr=[[max(0, mean["mean"]-mean["ci_low"])],
                                    [max(0, mean["ci_high"]-mean["mean"])]], fmt="D", color=color, capsize=3)
                if plot["kind"] == "paired":
                    if ("pair" not in units or units.pair.isna().any()
                            or units.duplicated(["condition", "pair"]).any()):
                        raise ValueError("paired_plot_requires_unique_pairs")
                    for _, pair in units.groupby("pair"):
                        indexed = pair.set_index("condition")
                        present = [g for g in order if g in indexed.index]
                        ax.plot([order.index(g) for g in present],
                                [indexed.loc[g, metric] for g in present], color="#aaa", lw=.7, zorder=0)
                ax.set_xticks(range(len(order)), order)
                ax.set_xlabel(plot["x_label"] or ("条件" if ja else "Condition"))
                labels = (["観測値", "視野中央値", "独立実験単位", "平均・95% CI"] if ja else
                          ["Observations", "Field median", "Independent unit", "Mean and 95% CI"])
                ax.legend(handles=[Line2D([], [], marker=marker, linestyle="", color="#126c67", label=label,
                                          markersize=size) for marker, size, label in
                                   zip([".", "s", "o", "D"], [4, 4, 6, 5], labels, strict=True)],
                          loc="best", frameon=False, fontsize=max(6, plot["font_size"]-2))
                if spec["mode"] == "exploratory":
                    note = ("ひし形：GFP・撮影日で調整した平均。点：未調整値。" if ja else
                            "Diamonds: GFP/date-adjusted means. Observation and unit points are unadjusted.")
            ylabel = plot["y_label"] or metric
            if result.get("unit"):
                ylabel += f" ({result['unit']})"
            ax.set_ylabel(ylabel)
            ax.spines[["top", "right"]].set_visible(False)
            ax.set_title(("探索的解析" if ja else "Exploratory analysis") if spec["mode"] == "exploratory"
                         else ("独立実験単位に基づく比較" if ja else "Comparison of independent experimental units"),
                         loc="left", fontsize=11)
            counts = []
            for entry in result["counts"]:
                n = entry.get("cells", entry.get("observations", 0))
                counts.append(f"{entry['condition']}: observations={n}, fields={entry['fields']}, units={entry['experimental_units']}")
            caption = "\n".join(counts) + ("\n" + note if note else "")
            fig.supxlabel(caption, fontsize=max(6, plot["font_size"]-3))
            for suffix in ("svg", "pdf", "png"):
                metadata: dict[str, str | None] = {"Creator": "Cytellect"}
                if suffix == "pdf":
                    metadata.update(CreationDate=None, ModDate=None)
                if suffix == "svg":
                    metadata.update(Date=None)
                fig.savefig(output/f"figure.{suffix}", dpi=200, metadata=metadata)
        finally:
            plt.close(fig)
    for name, rows in (("plot-data", result["plot_data"]), ("comparisons", result["comparisons"]),
                       ("experimental-units", result["unit_summary"]), ("field-summary", result["field_summary"])):
        write_csv(output/f"{name}.csv", rows)
    return {"font": font, "formats": ["svg", "pdf", "png"], "svg_text": "editable",
            "scatter_band": "descriptive nonclustered mean CI" if plot["kind"] == "scatter" else None}
