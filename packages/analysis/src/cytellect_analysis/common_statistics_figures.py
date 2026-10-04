"""Unit-level common plots and independently versioned Methods/source exports."""
import hashlib
import json
import textwrap
from pathlib import Path
from typing import Literal

import matplotlib
import numpy as np
from pydantic import TypeAdapter

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.text import Text
from matplotlib.ticker import MaxNLocator

from .common_statistics_contracts import CommonStatisticsResult
from .exports_csv import write_csv
from .figures import COLORS, MARKERS, _validate_text_layout, figure_settings, select_font
from .regions import RegionModel

FIGURE_VERSION = "1.0.0"


class CommonStatisticsMethodsTemplate(RegionModel):
    kind: Literal["common-statistics"]
    version: Literal["1.0.0"]


CURRENT_COMMON_METHODS_TEMPLATE = CommonStatisticsMethodsTemplate(
    kind="common-statistics", version="1.0.0")


def _label(source, ja=False):
    channel = source["channel"]
    metric = source["metric"]
    labels = {"area_px": ("Region area", "領域面積"), "area_um2": ("Region area", "領域面積"),
              "mean": ("Mean intensity", "平均輝度"), "median": ("Median intensity", "輝度中央値"),
              "integrated": ("Integrated intensity", "積算輝度")}
    label = labels[metric.removesuffix("_corrected")][ja]
    if channel:
        label = f"{channel['label']}: {label}"
    correction = ("背景補正" if ja else "background corrected") if metric.endswith("_corrected") else ""
    suffix = ", ".join(s for s in (correction, source["unit"]) if s)
    return f"{label}\n({suffix})"


def _number(value):
    return "not estimated" if value is None else f"{value:.8g}"


def common_statistics_methods(result):
    spec = result["spec"]
    association = result["analysis_kind"] == "region-association"
    lines = ["# Cytellect common-statistics Methods", "", "Review this saved-settings draft before publication.",
             "Methods template: cytellect-common-statistics-methods 1.0.0.",
             f"Source revision: {result['revision_id']}; fingerprint: {result['source_fingerprint']}.",
             f"Inference core: {result['inference_version']}; request protocol: {spec['version']}.",
             f"The inferential unit was {spec['design']['unit_definition']}.",
             "Region measurements were reduced to a median within each field, an unweighted mean of fields "
             "within each sample, and an unweighted mean of samples within each independent experimental unit. "
             "Regions and fields were not treated as independent replicates.",
             "Conditions in the declared analysis: " + ", ".join(spec["conditions"]) + ".",
             "The researcher selected the method explicitly. No normality pretest or observed p-value selected a method.",
             "Reviewed original-coordinate regions and saved original-pixel measurements were used. "
             "No normalization, batch adjustment or measurement transformation was performed at this statistical stage."]
    sources = [("X", result["x_source"]), ("Y", result["y_source"])] if association else [("Outcome", result)]
    for axis, source in sources:
        lines.append(f"{axis}: {_label(source)}; region definition: {source['region']['label']}.")
        if source["channel"]:
            ch = source["channel"]
            lines.append(f"{axis} channel ID: {ch['channel_id']}; declared stain: {ch.get('stain') or 'not recorded'}.")
        if source["metric"].endswith("_corrected"):
            lines.append(f"{axis} values use the saved confirmed background ROI median; signed corrected values were retained.")
        elif source["metric"].startswith("area_"):
            lines.append(f"{axis} counts original mask pixels" +
                         (" multiplied by confirmed XY pixel area." if source["metric"] == "area_um2" else "."))
        else:
            lines.append(f"{axis} uses raw original-pixel intensity measurements.")
        lines.append(f"{axis} missing outcomes: {len(source['missingness'])}; explicitly excluded failed fields: "
                     f"{len(source['excluded_failed_fields'])}. Full field, observation and unit ledgers are exported.")
        lines.append(f"{axis} acquisition basis: {source['acquisition']['review']['basis']}; "
                     "comparability is researcher-confirmed, not established by the software.")
    if association:
        lines += [f"Association scope: {spec['scope']}. X and Y were independently aggregated and matched by the "
                  "same condition and independent-unit identity, never by observation order. "
                  "Unmatched unexcluded units were rejected. Different retained region/field counts per axis remain in the ledgers.",
                  "Holm correction covers every declared association scope in family declared-association-scopes. "
                  "The scatter contains one X/Y point per matched independent unit; no regression line or confidence band was estimated."]
        tests = result["associations"]
    else:
        if spec["design"]["kind"] == "paired":
            lines.append("Pairing basis: " + spec["design"]["pairing_basis"] +
                         ". Pairs use saved identity; incomplete pairs were rejected.")
        family = spec["comparison_family"]
        lines.append(f"Holm family {family['family_id']}: " +
                     "; ".join(f"{a} versus {b}" for a, b in family["contrasts"]) +
                     ". Every declared contrast is tested regardless of the omnibus result. "
                     "These are planned pairwise tests, not Dunn or Games–Howell tests. "
                     "Any t-test difference intervals are pointwise 95% intervals, not multiplicity-adjusted.")
        tests = result["comparisons"] + ([result["omnibus"]] if result["omnibus"] else [])
    for row in tests:
        scope = row.get("scope") or (f"{row['group_a']} versus {row['group_b']}" if "group_a" in row else "omnibus")
        lines.append(f"{scope}: {row['method']}; statistic={_number(row['statistic'])}; "
                     f"p={_number(row['p_value'])}; Holm-adjusted p={_number(row.get('p_holm'))}.")
        if row.get("estimate") is not None:
            lines.append(f"Mean difference={_number(row['estimate'])}; pointwise 95% CI "
                         f"[{_number(row['ci_low'])}, {_number(row['ci_high'])}].")
        if row.get("effect") is not None:
            lines.append(f"{row['effect_name']}={_number(row['effect'])}; no effect confidence interval estimated.")
        lines.append("Resolved test settings: " + json.dumps(row["method_settings"], ensure_ascii=False, sort_keys=True) + ".")
        if row.get("null_hypothesis"):
            lines.append("Test null: " + row["null_hypothesis"] + ".")
    lines += ["Missingness was not assumed random. All explicit exclusions remain recorded; unexcluded units "
              "without outcomes were rejected. Inferential applicability depends on the recorded design and assumptions."]
    lines.extend("Warning: " + warning + "." for warning in result["warnings"])
    return "\n\n".join(lines) + "\n"


def _tables(result):
    tables = {"experimental-units": result["unit_summary"], "unit-ledger": result["unit_ledger"],
              "counts": result["counts"], "missingness": result["missingness"]}
    sources = [("x-", result["x_source"]), ("y-", result["y_source"])] if result["analysis_kind"] == "region-association" else [("", result)]
    for prefix, source in sources:
        for filename, key in (("plot-data", "plot_data"), ("observations", "observation_ledger"),
                              ("source-fields", "source_field_ledger"), ("field-summary", "field_summary"),
                              ("sample-summary", "sample_summary"), ("unit-summary", "unit_summary"),
                              ("pair-ledger", "pair_ledger"), ("excluded-failed-fields", "excluded_failed_fields")):
            tables[prefix + filename] = source[key]
    if result["analysis_kind"] == "region-association":
        tables["associations"] = result["associations"]
    else:
        tables["comparisons"] = result["comparisons"]
        tables["omnibus"] = [result["omnibus"]] if result["omnibus"] else []
    return tables


def render_common_statistics(result, output: Path, *, methods_template=None):
    template = CommonStatisticsMethodsTemplate.model_validate(
        CURRENT_COMMON_METHODS_TEMPLATE if methods_template is None else methods_template)
    canonical = TypeAdapter(CommonStatisticsResult).validate_python(
        {k: v for k, v in result.items() if k != "figure"}).model_dump(mode="json")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    spec, rows = canonical["spec"], canonical["unit_summary"]
    plot, association = spec["plot"], canonical["analysis_kind"] == "region-association"
    order = plot["group_order"] or spec["conditions"]
    style = figure_settings(plot)
    glyphs, graphical_summary = [], []
    ja = plot["language"] == "ja"
    with plt.rc_context({"svg.fonttype": "none", "pdf.fonttype": 42, "ps.fonttype": 42,
                         "font.size": style["font_size_pt"], "axes.linewidth": .6,
                         "lines.linewidth": .6, "svg.hashsalt": "cytellect-common-statistics-1"}):
        fig, ax = plt.subplots(figsize=(style["width_inches"], style["height_inches"]), layout="constrained")
        rng = np.random.default_rng(0)
        try:
            if association:
                for i, group in enumerate(order):
                    points = [r for r in rows if r["condition"] == group]
                    ax.scatter([r["x"] for r in points], [r["y"] for r in points], s=18,
                               color=COLORS[i % len(COLORS)], marker=MARKERS[i % len(MARKERS)],
                               linewidths=.35, edgecolors="white", label=f"{group} (n={len(points)})")
                    glyphs.extend({**r, "display_x": r["x"], "display_y": r["y"]} for r in points)
                ax.set_xlabel(plot["x_label"] or _label(canonical["x_source"], ja))
                ax.set_ylabel(plot["y_label"] or _label(canonical["y_source"], ja))
                ax.legend(frameon=False)
                note = "Each point is one matched independent experimental unit; no fitted line or confidence band."
            elif plot["kind"] == "histogram":
                bins = np.linspace(min(r["value"] for r in rows), max(r["value"] for r in rows), plot["histogram_bins"] + 1)
                for i, group in enumerate(order):
                    points = [r for r in rows if r["condition"] == group]
                    values = [r["value"] for r in points]
                    counts, _ = np.histogram(values, bins=bins)
                    ax.stairs(counts, bins, color=COLORS[i % len(COLORS)], label=f"{group} (n={len(points)})")
                    ax.plot(values, np.full(len(values), -.1 - .12 * i), "|", color=COLORS[i % len(COLORS)], clip_on=False)
                    graphical_summary.extend({"condition": group, "bin_left": float(lo), "bin_right": float(hi),
                                              "count": int(n), "last_bin_includes_right": j == len(counts) - 1}
                                             for j, (lo, hi, n) in enumerate(zip(bins[:-1], bins[1:], counts, strict=True)))
                    glyphs.extend({**r, "display_x": r["value"], "display_y": -.1 - .12 * i} for r in points)
                ax.set_ylim(bottom=-.12 * len(order) - .2)
                max_count = max(r["count"] for r in graphical_summary)
                ticks = MaxNLocator(integer=True, min_n_ticks=2).tick_values(0, max_count)
                ax.set_yticks([value for value in ticks if 0 <= value <= max_count])
                ax.set_xlabel(plot["x_label"] or _label(canonical, ja))
                ax.set_ylabel(plot["y_label"] or ("独立実験単位数" if ja else "Independent-unit count"))
                ax.legend(frameon=False)
                note = "Histogram counts independent units using shared equal-width bins; rugs show every unit."
            else:
                for i, group in enumerate(order):
                    points = [r for r in rows if r["condition"] == group]
                    values = np.array([r["value"] for r in points])
                    if plot["kind"] == "box":
                        q1, median, q3 = np.quantile(values, [.25, .5, .75], method="linear")
                        lower = float(values[values >= q1 - 1.5 * (q3 - q1)].min())
                        upper = float(values[values <= q3 + 1.5 * (q3 - q1)].max())
                        summary = {"condition": group, "q1": float(q1), "median": float(median), "q3": float(q3),
                                   "whisker_low": lower, "whisker_high": upper}
                        graphical_summary.append(summary)
                        ax.bxp([{"med": median, "q1": q1, "q3": q3, "whislo": lower, "whishi": upper}],
                               positions=[i], widths=.5, showfliers=False, manage_ticks=False)
                    elif plot["kind"] == "violin":
                        if len(values) < 2 or np.ptp(values) == 0:
                            raise ValueError("common_statistics_constant_units")
                        parts = ax.violinplot(values, positions=[i], widths=.65, showextrema=False,
                                              showmedians=True, points=100, bw_method="scott")
                        for body in parts["bodies"]:
                            body.set_facecolor(COLORS[i % len(COLORS)])
                            body.set_alpha(.2)
                        graphical_summary.append({"condition": group, "kde": "Gaussian", "bandwidth": "Scott",
                                                  "grid_points": 100, "min": float(values.min()), "max": float(values.max())})
                    jitter = np.zeros(len(points)) if plot["kind"] == "paired" else rng.uniform(-.12, .12, len(points))
                    ax.scatter(i + jitter, values, s=18, color=COLORS[i % len(COLORS)],
                               marker=MARKERS[i % len(MARKERS)], edgecolor="white", linewidth=.35, zorder=3)
                    glyphs.extend({**r, "display_x": float(i + offset), "display_y": r["value"]}
                                  for r, offset in zip(points, jitter, strict=True))
                if plot["kind"] == "paired":
                    for pair in canonical["pair_ledger"]:
                        if pair["status"] != "selected":
                            continue
                        points = [next(r for r in rows if r["condition"] == c and r["experimental_unit"] == pair["units"][c]) for c in order]
                        ax.plot(range(len(order)), [r["value"] for r in points], color="#888888", linewidth=.5, zorder=0)
                ax.set_xticks(range(len(order)), [textwrap.fill(c, 16) + f"\nn={sum(r['condition'] == c for r in rows)}" for c in order])
                ax.set_xlabel(plot["x_label"] or ("条件（n：独立実験単位）" if ja else "Condition (n: independent units)"))
                ax.set_ylabel(plot["y_label"] or _label(canonical, ja))
                note = "Points are independent-unit summaries; jitter affects display only (seed 0). "
                if plot["kind"] == "box":
                    note += "Boxes show linear-interpolated quartiles and median; whiskers end at observations within 1.5 IQR. All units remain shown."
                elif plot["kind"] == "violin":
                    note += "Violins show Gaussian KDE with Scott bandwidth on 100 points, limited to the observed range; densities are descriptive, not confidence intervals."
                elif plot["kind"] == "paired":
                    note += "Lines connect saved complete pair identities."
            ax.spines[["top", "right"]].set_visible(False)
            ax.get_xticklabels()
            ax.get_yticklabels()
            texts = fig.findobj(match=Text)
            selected_font = select_font(plot["language"], "".join(t.get_text() for t in texts))
            for item in texts:
                properties = item.get_fontproperties().copy()
                properties.set_file(str(selected_font.path))
                properties.set_family(selected_font.family)
                properties.set_weight(selected_font.weight)
                item.set_fontproperties(properties)
            _validate_text_layout(fig, ax)
            for suffix in ("svg", "pdf", "png"):
                metadata = {"Creator": "Cytellect common statistics " + FIGURE_VERSION}
                if suffix == "svg":
                    metadata["Date"] = None
                if suffix == "pdf":
                    metadata.update(CreationDate=None, ModDate=None)
                fig.savefig(output / f"figure.{suffix}", dpi=300, metadata=metadata)
        finally:
            plt.close(fig)
    tables = _tables(canonical)
    tables["graphical-summary"] = graphical_summary
    csv_files = []
    for name, values in tables.items():
        if values:
            filename = f"{name}.csv"
            write_csv(output / filename, values)
            csv_files.append(filename)
    methods = common_statistics_methods(canonical)
    (output / "methods.md").write_text(methods, encoding="utf-8")
    (output / "figure-caption.md").write_text("# Figure legend\n\n" + note + "\n\n" + methods, encoding="utf-8")
    metadata = {"common_statistics_figure_version": FIGURE_VERSION,
                "common_statistics_methods": template.model_dump(mode="json"), "style": style,
                "font": selected_font.family, "font_metadata": selected_font.metadata()}
    source = {**canonical, **metadata, "unit_glyphs": glyphs, "graphical_summary": graphical_summary,
              "jitter_seed": 0, "source_hashes": {n: hashlib.sha256((output / n).read_bytes()).hexdigest() for n in csv_files}}
    (output / "figure-data.json").write_text(json.dumps(source, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return {**metadata, "figure_version": FIGURE_VERSION, "formats": ["svg", "pdf", "png"], "svg_text": "editable",
            "source_files": ["figure.svg", "figure.pdf", "figure.png", *csv_files, "figure-data.json", "figure-caption.md", "methods.md"]}
