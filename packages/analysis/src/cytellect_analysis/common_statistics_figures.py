"""Unit-level common plots and independently versioned Methods/source exports."""
import hashlib
import json
import textwrap
from pathlib import Path
from typing import Any, Literal, cast

import matplotlib
import numpy as np
from pydantic import TypeAdapter

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.layout_engine import ConstrainedLayoutEngine
from matplotlib.text import Text
from matplotlib.ticker import MaxNLocator

from .common_statistics_contracts import CommonStatisticsResult
from .compartment_observations import DEFINITIONS as COMPARTMENT_DEFINITIONS
from .compartment_review import compartment_missing_lines, compartment_missing_tables
from .experiment_strata import stratum_methods_lines
from .exports_csv import write_csv
from .figure_sources import attach_svg_sources, bind_points
from .figures import (
    COLORS,
    MARKERS,
    _validate_text_layout,
    apply_plot_controls,
    figure_settings,
    select_font,
    series_color,
)
from .gfp_selection import recorded_gate_lines
from .nuclear_features import LABELS as NUCLEAR_FEATURE_LABELS
from .nuclear_features import is_feature
from .nuclear_features import methods_lines as feature_methods_lines
from .regions import RegionModel

# 2.0.0: publication figures (docs/drafts/publication-figures/plan.md). 1.0.0 and 1.0.1 replay saved figures.
FIGURE_VERSION = "2.0.0"
FIGURE_VERSIONS = ("1.0.0", "1.0.1", "2.0.0")


class CommonStatisticsMethodsTemplate(RegionModel):
    kind: Literal["common-statistics"]
    version: Literal["1.0.0"]


CURRENT_COMMON_METHODS_TEMPLATE = CommonStatisticsMethodsTemplate(
    kind="common-statistics", version="1.0.0")


COMPARTMENT_LABELS = {
    "log2_nucleoplasm_over_nucleolus": ("Nucleoplasm / nucleolus mean", "核質 / 核小体 平均輝度比"),
    "nucleolar_area_fraction": ("Nucleolar area fraction of nucleus", "核に占める核小体面積比"),
    "nucleolar_count": ("Nucleoli per nucleus", "核あたりの核小体数"),
    "nucleolar_area_px": ("Nucleolar area per nucleus", "核あたりの核小体の総面積"),
    "nucleolar_area_um2": ("Nucleolar area per nucleus", "核あたりの核小体の総面積"),
    "nucleolar_eccentricity": ("Nucleolar eccentricity", "核小体の離心率"),
    "largest_nucleolus_fraction": ("Largest nucleolus / all nucleoli", "最大の核小体 / 核小体全体"),
}
FIELD_SUMMARY_LABELS = {
    "nucleus_count": ("Nucleus count", "核数"),
    "nucleus_density_per_mm2": ("Nuclear density", "核の密度"),
    "positive_count": ("Positive nuclei per field", "視野あたりの陽性核数"),
    "positive_fraction": ("Positive fraction of evaluable nuclei", "判定可能な核の陽性率"),
}


def field_summary_methods_sentence(axis, metric):
    from .field_summary_source import DEFINITIONS
    return (f"{axis} is one value per field (field-summary selection 1.0.0): {DEFINITIONS[metric]}. "
            "Fields, not nuclei, are the observations; explicitly excluded nuclei are not counted and excluded or "
            "failed fields are not observations. A nucleus count is the number of imaged nuclei, not a viability or "
            "proliferation measure, and it depends on how fields were chosen.")


def compartment_methods_sentence(axis, metric, version="1.0.0"):
    return (f"{axis} is a per-nucleus compartment-summary value (selection {version}): {COMPARTMENT_DEFINITIONS[metric]}. "
            "Nuclei, not regions, are the observations; the summary was bound to the reviewed nucleoplasm mask by "
            "exact nucleus identity and area. Missing values keep their recorded reason and were not replaced with zero.")


def _label(source, ja=False):
    channel = source["channel"]
    metric = source["metric"]
    labels = {"area_px": ("Region area", "領域面積"), "area_um2": ("Region area", "領域面積"),
              "mean": ("Mean intensity", "平均輝度"), "median": ("Median intensity", "輝度中央値"),
              "integrated": ("Integrated intensity", "積算輝度"), **COMPARTMENT_LABELS, **FIELD_SUMMARY_LABELS,
              **{key.removesuffix("_corrected"): value for key, value in NUCLEAR_FEATURE_LABELS.items()}}
    label = labels[metric.removesuffix("_corrected")][ja]
    if channel:
        label = f"{channel['label']}: {label}"
    correction = ("背景補正" if ja else "background corrected") if metric.endswith("_corrected") else ""
    suffix = ", ".join(s for s in (correction, source["unit"]) if s)
    return f"{label}\n({suffix})"


def _number(value):
    return "not estimated" if value is None else f"{value:.8g}"


def estimate_lines(estimates):
    """Methods sentences for saved treatment − control estimates (comparison-estimates/1.0.0)."""
    if not estimates:
        return []
    unit = " (percentage points)" if estimates["scale"] == "fraction" else ""
    lines = [f"Estimates ({estimates['protocol']}): {estimates['treatment']} minus {estimates['control']}; "
             f"n={estimates['n_treatment']} and {estimates['n_control']} "
             + ("recorded experimental units (independence not confirmed)" if estimates["test"] == "none" else "independent units")
             + (f", {estimates['n_pairs']} complete pairs" if estimates["n_pairs"] is not None else "") + "."]
    for name in ("difference", "ratio"):
        row = estimates[name]
        if row["estimate"] is None:
            lines.append(f"{name.capitalize()}: not estimated ({row['unavailable_reason']}).")
        else:
            lines.append(f"{name.capitalize()}{unit if name == 'difference' else ''}={_number(row['estimate'])}; "
                         f"95% CI [{_number(row['ci_low'])}, {_number(row['ci_high'])}]; basis: {row['basis']}.")
    for run in estimates["runs"]:
        lines.append(f"Run {run['pair']}: {estimates['control']}={_number(run['control'])}, "
                     f"{estimates['treatment']}={_number(run['treatment'])}, difference{unit}={_number(run['difference'])}.")
    return lines


def common_statistics_methods(result):
    spec = result["spec"]
    association = result["analysis_kind"] == "region-association"
    # A descriptive comparison (test "none") never calls its units independent.
    descriptive = not association and spec.get("test") == "none"
    unit_noun = "recorded experimental unit" if descriptive else "independent experimental unit"
    lines = ["# Cytellect common-statistics Methods", "", "Review this saved-settings draft before publication.",
             "Methods template: cytellect-common-statistics-methods 1.0.0.",
             f"Source revision: {result['revision_id']}; fingerprint: {result['source_fingerprint']}.",
             f"Inference core: {result['inference_version']}; request protocol: {spec['version']}.",
             (f"The experimental unit was {spec['design']['unit_definition']}; the researcher had not confirmed that "
              "these units were independent." if descriptive else f"The inferential unit was {spec['design']['unit_definition']}."),
             ("Each field contributed one field value, then fields were reduced to an unweighted mean within each "
              f"sample and samples to an unweighted mean within each {unit_noun}. "
              "Fields were not treated as independent replicates."
              if spec.get("selection", {}).get("source") == "field-summary" else
              "Region measurements were reduced to a median within each field, an unweighted mean of fields "
              f"within each sample, and an unweighted mean of samples within each {unit_noun}. "
              "Regions and fields were not treated as independent replicates."),
             "Conditions in the declared analysis: " + ", ".join(spec["conditions"]) + ".",
             *stratum_methods_lines(result.get("stratum")),
             "The researcher selected the method explicitly. No normality pretest or observed p-value selected a method.",
             "Reviewed original-coordinate regions and saved original-pixel measurements were used. "
             "No normalization, batch adjustment or measurement transformation was performed at this statistical stage."]
    sources = [("X", result["x_source"]), ("Y", result["y_source"])] if association else [("Outcome", result)]
    for axis, source in sources:
        lines.append(f"{axis}: {_label(source)}; region definition: {source['region']['label']}.")
        if source["channel"]:
            ch = source["channel"]
            lines.append(f"{axis} channel ID: {ch['channel_id']}; declared stain: {ch.get('stain') or 'not recorded'}.")
        if source["metric"] in COMPARTMENT_DEFINITIONS:
            lines.append(compartment_methods_sentence(axis, source["metric"],
                                                      spec.get("selection", {}).get("version", "1.0.0")))
        elif source["metric"] in FIELD_SUMMARY_LABELS:
            lines.append(field_summary_methods_sentence(axis, source["metric"]))
        elif is_feature(source["metric"]):
            lines.extend(f"{axis}: {line}" for line in feature_methods_lines(source["source_fields"], source["metric"]))
        elif source["metric"].endswith("_corrected"):
            automatic = any((item.get("measurement") or {}).get("mode") == "automatic_background" for item in source["source_fields"])
            basis = "saved automatic background candidate median" if automatic else "saved confirmed background ROI median"
            lines.append(f"{axis} values use the {basis}; signed corrected values were retained.")
        elif source["metric"].startswith("area_"):
            lines.append(f"{axis} counts original mask pixels" +
                         (" multiplied by confirmed XY pixel area." if source["metric"] == "area_um2" else "."))
        else:
            lines.append(f"{axis} uses raw original-pixel intensity measurements.")
        lines.extend(recorded_gate_lines(source.get("selection")))
        lines.append(f"{axis} missing outcomes: {len(source['missingness'])}; explicitly excluded failed fields: "
                     f"{len(source['excluded_failed_fields'])}. Full field, observation and unit ledgers are exported.")
        lines.extend(compartment_missing_lines(source))
        lines.append(f"{axis} acquisition basis: {source['acquisition']['review']['basis']}; "
                     "comparability is researcher-confirmed, not established by the software.")
    if association:
        if spec["version"] == "1.1.0":
            lines.append("Both axes used the same explicit GFP selection and identical retained region identities before independent-unit aggregation.")
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
        lines.extend(estimate_lines(result.get("estimates")))
    if not association and spec["test"] == "none":
        lines.append("Descriptive comparison: no hypothesis test, p-value or confidence interval was calculated, "
                     "because the independence of the experimental units was not confirmed by the researcher. "
                     "Unit values and per-run differences are descriptive and must not be read as inference.")
        tests = []
    elif not association:
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
        estimates = result.get("estimates")
        if estimates:
            # The saved treatment − control estimates, with their basis or the reason they are absent.
            tables["estimates"] = [{"quantity": name, "control": estimates["control"], "treatment": estimates["treatment"],
                                    "scale": estimates["scale"], "test": estimates["test"], **estimates[name]}
                                   for name in ("difference", "ratio")]
            tables["estimates-groups"] = estimates["groups"]
            tables["estimates-runs"] = estimates["runs"]
    tables.update(compartment_missing_tables(result))
    return tables


def _unit_axis(spec, ja):
    """The x-axis title naming what n counts; a descriptive comparison does not call its units independent."""
    if spec.get("test") == "none":
        # Short enough for every figure width; the legend states that independence is not confirmed.
        return "条件（n：記録した実験回）" if ja else "Condition (n: recorded runs)"
    return "条件（n：独立した実験回）" if ja else "Condition (n: independent units)"


def _unit_interval(values):
    """Mean and 95% t interval of independent-unit values (descriptive; None below two units)."""
    from scipy import stats

    values = np.asarray(values, dtype=float)
    mean = float(values.mean())
    if len(values) < 2:
        return mean, None, None
    half = float(stats.t.ppf(.975, len(values) - 1) * values.std(ddof=1) / np.sqrt(len(values)))
    return mean, mean - half, mean + half


def _hierarchy(ax, canonical, plot, order, glyphs, graphical_summary, bars):
    """Fields (small), independent units (large, one marker per run), lines joining a run's
    units, and each group's unit mean with its 95% t interval (a bar when ``bars``)."""
    rows, fields = canonical["unit_summary"], canonical["field_summary"]
    paired = canonical["spec"]["design"]["kind"] == "paired"
    # A descriptive comparison (test "none") draws the unit mean without any interval.
    descriptive = canonical["spec"]["test"] == "none"
    runs = sorted({r["pair"] for r in rows if r.get("pair")}) if paired else []
    rng = np.random.default_rng(0)
    for i, group in enumerate(order):
        color = series_color(plot, group, COLORS[i % len(COLORS)])
        points = [r for r in rows if r["condition"] == group]
        mean, low, high = _unit_interval([r["value"] for r in points])
        if descriptive:
            low = high = None
        graphical_summary.append({"condition": group, "mean": mean, "ci_low": low, "ci_high": high,
                                  "n_units": len(points),
                                  "interval": ("not computed (descriptive comparison)" if descriptive
                                               else "95% t interval of independent-unit values")})
        # The summary sits beside the points so it never hides a unit.
        summary_x = i if bars else i + .32
        if bars:
            ax.bar(i, mean, width=.55, color=color, alpha=.25, edgecolor=color, linewidth=.6, zorder=1)
        else:
            ax.hlines(mean, summary_x - .07, summary_x + .07, color="#222222", linewidth=1.1, zorder=4)
        if low is not None:
            ax.errorbar(summary_x, mean, yerr=[[mean - low], [high - mean]], fmt="none", ecolor="#222222",
                        elinewidth=.8, capsize=3, zorder=4)
        for j, unit in enumerate(points):
            marker = MARKERS[(runs.index(unit["pair"]) if unit.get("pair") in runs else j) % len(MARKERS)]
            if not bars:
                below = [f["value"] for f in fields if f["condition"] == group
                         and f["experimental_unit"] == unit["experimental_unit"]]
                ax.scatter(i + rng.uniform(-.18, .18, len(below)), below, s=7, color=color, alpha=.45,
                           marker=marker, linewidths=0, zorder=2)
            bind_points(ax.scatter([i], [unit["value"]], s=40, color=color, marker=marker, edgecolor="#222222",
                                   linewidth=.6, zorder=5), [unit])
            glyphs.append({**unit, "display_x": float(i), "display_y": unit["value"]})
    for pair in canonical["pair_ledger"] if paired else []:
        if pair["status"] != "selected":
            continue
        values = [next(r["value"] for r in rows if r["condition"] == c and r["experimental_unit"] == pair["units"][c])
                  for c in order]
        ax.plot(range(len(order)), values, color="#888888", linewidth=.5, zorder=3)


# Earlier forms that draw run values (offered at ten or more runs), and the earlier default of a comparison.
RUN_VALUE_KINDS = frozenset({"box", "violin", "histogram", "paired", "distribution"})


def render_common_statistics(result, output: Path, *, methods_template=None, figure_version=FIGURE_VERSION,
                             images=None):
    """``images``: original channel arrays and saved labels of the fields a 2.0.0 figure may show
    (``{field_id: {"channels": {...}, "labels": ...}}``), loaded by the worker."""
    if figure_version not in FIGURE_VERSIONS:
        raise ValueError("common_statistics_figure_version_unsupported")
    template = CommonStatisticsMethodsTemplate.model_validate(
        CURRENT_COMMON_METHODS_TEMPLATE if methods_template is None else methods_template)
    canonical: dict[str, Any] = TypeAdapter(CommonStatisticsResult).validate_python(
        {k: v for k, v in result.items() if k != "figure"}).model_dump(mode="json")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    spec, rows = canonical["spec"], canonical["unit_summary"]
    plot, association = spec["plot"], canonical["analysis_kind"] == "region-association"
    order = plot["group_order"] or spec["conditions"]
    style = figure_settings(plot)
    glyphs: list[dict[str, Any]] = []
    graphical_summary: list[dict[str, Any]] = []
    ja = plot["language"] == "ja"
    # The publication figure names its axes in English (plan FS); a figure asked for in Japanese keeps
    # the earlier drawing, which labels in the language requested.
    if figure_version == "2.0.0" and not ja and plot.get("presentation") and plot["kind"] in RUN_VALUE_KINDS:
        from .figure_forms import figure_forms

        # Every form the 「グラフ」 view asks for is a publication figure. A run-value form the result offers
        # (ten or more runs) is drawn as such; one it does not (a figure saved before, with fewer runs) is drawn
        # as the nearest form of the run hierarchy.
        if plot["kind"] not in {form["kind"] for form in figure_forms(canonical)["forms"]}:
            nearest = {"box": "box", "violin": "violin"}.get(plot["kind"], "points")
            plot = canonical["spec"]["plot"] = {**plot, "kind": "superplot",
                                                "presentation": {**plot["presentation"], "observations": nearest}}
        return _render_publication(canonical, output, template, order, images)
    if figure_version == "2.0.0" and not ja and (association or plot["kind"] in ("superplot", "unit-mean-bar")):
        return _render_publication(canonical, output, template, order, images)
    if figure_version == "2.0.0" and plot.get("presentation"):
        # Run-value forms keep their drawing at the chosen publication size; a request naming no
        # presentation keeps the width and height it asked for.
        size = (plot.get("presentation") or {}).get("size") or "panel"
        width_mm = {"single-column": 89.0, "double-column": 183.0}.get(size)
        if size == "panel":
            width_mm = max(60.0, 24 + 14 * len(order))
        if width_mm is not None:
            style = {**style, "preset": size, "width_inches": width_mm / 25.4, "width_mm": width_mm,
                     "height_inches": 60 / 25.4, "height_mm": 60.0}
    with plt.rc_context({"svg.fonttype": "none", "pdf.fonttype": 42, "ps.fonttype": 42,
                         "font.size": style["font_size_pt"], "axes.linewidth": .6,
                         "lines.linewidth": .6, "svg.hashsalt": "cytellect-common-statistics-1"}):
        fig, ax = plt.subplots(figsize=(style["width_inches"], style["height_inches"]), layout="constrained")
        rng = np.random.default_rng(0)
        try:
            if association:
                for i, group in enumerate(order):
                    points = [r for r in rows if r["condition"] == group]
                    bind_points(ax.scatter([r["x"] for r in points], [r["y"] for r in points], s=18,
                               color=series_color(plot, group, COLORS[i % len(COLORS)]), marker=MARKERS[i % len(MARKERS)],
                               linewidths=.35, edgecolors="white", label=f"{group} (n={len(points)})"), points)
                    glyphs.extend({**r, "display_x": r["x"], "display_y": r["y"]} for r in points)
                ax.set_xlabel(plot["x_label"] or _label(canonical["x_source"], ja))
                ax.set_ylabel(plot["y_label"] or _label(canonical["y_source"], ja))
                ax.legend(frameon=False)
                note = "Each point is one matched independent experimental unit; no fitted line or confidence band."
            elif plot["kind"] == "histogram":
                bins = np.linspace(min(r["value"] for r in rows), max(r["value"] for r in rows), plot["histogram_bins"] + 1)
                for i, group in enumerate(order):
                    points = [r for r in rows if r["condition"] == group]
                    histogram_values = [r["value"] for r in points]
                    counts, _ = np.histogram(histogram_values, bins=bins)
                    ax.stairs(counts, bins, color=series_color(plot, group, COLORS[i % len(COLORS)]), label=f"{group} (n={len(points)})")
                    ax.plot(histogram_values, np.full(len(histogram_values), -.1 - .12 * i), "|", color=series_color(plot, group, COLORS[i % len(COLORS)]), clip_on=False)
                    graphical_summary.extend({"condition": group, "bin_left": float(lo), "bin_right": float(hi),
                                              "count": int(n), "last_bin_includes_right": j == len(counts) - 1}
                                             for j, (lo, hi, n) in enumerate(zip(bins[:-1], bins[1:], counts, strict=True)))
                    glyphs.extend({**r, "display_x": r["value"], "display_y": -.1 - .12 * i} for r in points)
                ax.set_ylim(bottom=-.12 * len(order) - .2)
                max_count = max(r["count"] for r in graphical_summary)
                ticks = MaxNLocator(integer=True, min_n_ticks=2).tick_values(0, max_count)
                ax.set_yticks([value for value in ticks if 0 <= value <= max_count])
                ax.set_xlabel(plot["x_label"] or _label(canonical, ja))
                ax.set_ylabel(plot["y_label"] or ("独立した実験回の数" if ja else "Independent-unit count"))
                ax.legend(frameon=False)
                note = "Histogram counts independent units using shared equal-width bins; rugs show every unit."
            elif plot["kind"] in ("superplot", "unit-mean-bar"):
                bars = plot["kind"] == "unit-mean-bar"
                _hierarchy(ax, canonical, plot, order, glyphs, graphical_summary, bars)
                ax.set_xticks(range(len(order)), [textwrap.fill(c, 16) + f"\nn={sum(r['condition'] == c for r in rows)}" for c in order])
                ax.set_xlim(-.5, len(order) - .5)
                ax.set_xlabel(plot["x_label"] or _unit_axis(spec, ja))
                ax.set_ylabel(plot["y_label"] or _label(canonical, ja))
                per_field = spec["selection"].get("source") == "field-summary"
                units = "recorded experimental units, independence not confirmed" if spec["test"] == "none" else "independent experimental units"
                note = (f"Large points are {units} (field values → sample mean → unit mean"
                        if per_field else f"Large points are {units} (median per field → sample mean → unit mean")
                note += "); the same marker marks the same run" + (" and lines join a run's units" if spec["design"]["kind"] == "paired" else "")
                note += ". " if bars else "; small points are field values" + ("" if per_field else " (median of the field's observations)") + ". "
                note += ("Bars show the mean of unit values" if bars else "Horizontal lines show the mean of unit values")
                note += (" (descriptive: no test or interval, run independence not confirmed). n is the number of experimental units, not fields or nuclei."
                         if spec["test"] == "none" else
                         " with its 95% t interval (error bars). n is the number of independent units, not fields or nuclei.")
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
                        # Matplotlib's dictionary stub erases the list type for the bodies key.
                        for body in cast(list[PolyCollection], parts["bodies"]):
                            body.set_facecolor(series_color(plot, group, COLORS[i % len(COLORS)]))
                            body.set_alpha(.2)
                        graphical_summary.append({"condition": group, "kde": "Gaussian", "bandwidth": "Scott",
                                                  "grid_points": 100, "min": float(values.min()), "max": float(values.max())})
                    jitter = np.zeros(len(points)) if plot["kind"] == "paired" else rng.uniform(-.12, .12, len(points))
                    bind_points(ax.scatter(i + jitter, values, s=18, color=series_color(plot, group, COLORS[i % len(COLORS)]),
                               marker=MARKERS[i % len(MARKERS)], edgecolor="white", linewidth=.35, zorder=3), points)
                    glyphs.extend({**r, "display_x": float(i + offset), "display_y": r["value"]}
                                  for r, offset in zip(points, jitter, strict=True))
                if plot["kind"] == "paired":
                    for pair in canonical["pair_ledger"]:
                        if pair["status"] != "selected":
                            continue
                        points = [next(r for r in rows if r["condition"] == c and r["experimental_unit"] == pair["units"][c]) for c in order]
                        ax.plot(range(len(order)), [r["value"] for r in points], color="#888888", linewidth=.5, zorder=0)
                ax.set_xticks(range(len(order)), [textwrap.fill(c, 16) + f"\nn={sum(r['condition'] == c for r in rows)}" for c in order])
                if figure_version in ("1.0.1", "2.0.0"):
                    # Equal category margins must not depend on the random jitter,
                    # unit count, or whether a box/violin contributes to autoscaling.
                    ax.set_xlim(-.5, len(order) - .5)
                ax.set_xlabel(plot["x_label"] or _unit_axis(spec, ja))
                ax.set_ylabel(plot["y_label"] or _label(canonical, ja))
                note = ("Points are summaries of recorded experimental units (independence not confirmed); jitter affects display only (seed 0). "
                        if spec.get("test") == "none" else "Points are independent-unit summaries; jitter affects display only (seed 0). ")
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
            apply_plot_controls(ax, plot)
            _validate_text_layout(fig, ax)
            for suffix in ("svg", "pdf", "png"):
                file_metadata: dict[str, str | None] = {"Creator": "Cytellect common statistics " + figure_version}
                if suffix == "svg":
                    file_metadata["Date"] = None
                if suffix == "pdf":
                    file_metadata.update(CreationDate=None, ModDate=None)
                fig.savefig(output / f"figure.{suffix}", dpi=300, metadata=file_metadata)
                if suffix == "svg":
                    attach_svg_sources(output / f"figure.{suffix}", fig)
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
    metadata: dict[str, Any] = {"common_statistics_figure_version": figure_version,
                "common_statistics_methods": template.model_dump(mode="json"), "style": style,
                "font": selected_font.family, "font_metadata": selected_font.metadata()}
    if figure_version == "2.0.0" and not association:
        # Drawn the earlier way (in Japanese, or asked without a presentation): the screen still offers every form.
        from .figure_forms import figure_forms
        from .publication_figure import resolve_presentation

        forms = figure_forms(canonical)
        metadata.update(presentation=resolve_presentation(canonical, plot), forms=forms["forms"],
                        default_form=forms["default"], compositions=[])
    source = {**canonical, **metadata, "unit_glyphs": glyphs, "graphical_summary": graphical_summary,
              "jitter_seed": 0, "source_hashes": {n: hashlib.sha256((output / n).read_bytes()).hexdigest() for n in csv_files}}
    (output / "figure-data.json").write_text(json.dumps(source, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return {**metadata, "figure_version": figure_version, "formats": ["svg", "pdf", "png"], "svg_text": "editable",
            "source_files": ["figure.svg", "figure.pdf", "figure.png", *csv_files, "figure-data.json", "figure-caption.md", "methods.md"]}


def _write_svg_font_stack(path: Path):
    """Name Arial and Helvetica after the bundled face so editors keep the layout."""
    from .figure_style import FONT_FAMILY, SVG_FONT_STACK

    text = path.read_text(encoding="utf-8")
    text = text.replace(f"font-family: '{FONT_FAMILY}'", f"font-family: {SVG_FONT_STACK}")
    path.write_text(text, encoding="utf-8")


def _render_publication(canonical, output: Path, template, order, images=None):
    """Common-statistics figure 2.0.0: the publication layout of plan.md (FS, FQ, FA, FL)."""
    from .figure_forms import figure_forms
    from .figure_legend import association_legend, comparison_legend
    from .figure_style import PNG_DPI, rc
    from .publication_figure import (
        bind_fonts,
        default_size,
        draw_association,
        draw_comparison,
        layout,
        resolve_presentation,
    )

    spec = canonical["spec"]
    plot = spec["plot"]
    association = canonical["analysis_kind"] == "region-association"
    presentation = resolve_presentation(canonical, plot) if not association else {
        "version": "1.0.0", "size": (plot.get("presentation") or {}).get("size") or default_size(plot),
        "annotation": (plot.get("presentation") or {}).get("annotation") or "value"}
    forms = figure_forms(canonical)
    image_figure = None
    if association:
        size = layout(plot, presentation, 3, legend=True, bracket_levels=0)
        if presentation["size"] == "panel":
            size.width_mm, size.height_mm = 82.0, 56.0
    else:
        from .figure_annotations import comparison_annotations
        from .figure_images import build_panels

        levels = len(comparison_annotations(canonical, order, presentation["annotation"]).brackets)
        paired_runs = spec["design"]["kind"] == "paired" and presentation["color_by"] == "run"
        size = layout(plot, presentation, len(order), legend=paired_runs, bracket_levels=levels, names=order)
        if presentation.get("composition") == "images-quantification" and images:
            image_figure = build_panels(canonical, order, images, presentation.get("image_fields"))
        if image_figure is not None:
            columns = 2 if image_figure.counterstain else 1
            tile = 19.0 if presentation["size"] == "panel" else 22.0
            image_width = 7 + columns * tile
            if presentation["size"] == "panel":
                size.width_mm += image_width + 3
            elif presentation["size"] == "custom":
                # A custom width narrower than the images beside the panel is widened to the panel's layout.
                panel = layout(plot, {**presentation, "size": "panel"}, len(order), legend=paired_runs, names=order,
                               bracket_levels=levels)
                size.width_mm = max(size.width_mm, panel.width_mm + image_width + 3)
            size.height_mm = max(size.height_mm, len(image_figure.panels) * tile + 12)
    style = size.style()
    with plt.rc_context(rc(size.font_size)):
        if image_figure is not None:
            fig = plt.figure(figsize=(style["width_inches"], style["height_inches"]), layout="constrained")
            grid = fig.add_gridspec(1, 2, width_ratios=[image_width, size.width_mm - image_width])
        else:
            fig, ax = plt.subplots(figsize=(style["width_inches"], style["height_inches"]), layout="constrained")
        try:
            engine = fig.get_layout_engine()
            if isinstance(engine, ConstrainedLayoutEngine):
                engine.set(w_pad=1 / 72, h_pad=1 / 72, wspace=0, hspace=0)
            if image_figure is not None:
                from .figure_images import draw_images

                holder = fig.add_subplot(grid[0])
                holder.set_axis_off()
                ax = fig.add_subplot(grid[1])
                ax.set_gid("panel-b-quantification")
            drawn = (draw_association(fig, ax, canonical, plot, order) if association
                     else draw_comparison(fig, ax, canonical, plot, presentation, order))
            # The panel may have widened for a long axis title; the manifest records the drawn size.
            style = {**style, "width_inches": fig.get_figwidth(), "width_mm": fig.get_figwidth() * 25.4}
            if association:
                # The researcher's axis ranges, tick steps and log display, checked as in the earlier figures
                # (a log axis refuses non-positive values). A comparison lays out its own value axis.
                apply_plot_controls(ax, plot)
            if image_figure is not None:
                # The layout is fixed now; the tiles take the reserved space as exact squares.
                image_axes = draw_images(fig, holder, image_figure, size.font_size,
                                         bool(presentation.get("outlines", True)))
                bind_fonts(fig)
                fig.canvas.draw()
                inverse = fig.transFigure.inverted()
                first = image_axes[0].get_window_extent().transformed(inverse)
                quantified = ax.get_tightbbox()
                left = quantified.transformed(inverse).x0 if quantified is not None else ax.get_position().x0
                for letter, x in (("a", max(.004, first.x0 - .01)), ("b", max(.004, left))):
                    fig.text(x, .995, letter, fontsize=8, fontweight="bold", ha="left", va="top",
                             gid=f"panel-letter-{letter}")
            shown = ax.get_legend()
            if (plot.get("style") or {}).get("show_legend") is False and shown is not None:
                shown.remove()
            bind_fonts(fig)
            _validate_text_layout(fig, ax)
            for suffix in ("svg", "pdf", "png"):
                file_metadata: dict[str, str | None] = {"Creator": "Cytellect common statistics 2.0.0"}
                if suffix == "svg":
                    file_metadata["Date"] = None
                if suffix == "pdf":
                    file_metadata.update(CreationDate=None, ModDate=None)
                fig.savefig(output / f"figure.{suffix}", dpi=PNG_DPI, metadata=file_metadata)
                if suffix == "svg":
                    attach_svg_sources(output / "figure.svg", fig)
                    _write_svg_font_stack(output / "figure.svg")
        finally:
            plt.close(fig)
    # The fields behind a comparison, group → run → field, for checking which fields carry the result.
    fields = None
    if not association:
        from .field_check import render_field_check

        # A check that cannot be laid out is left out (with its reason); it never fails the comparison's own figure.
        try:
            fields = render_field_check(canonical, order, output, font_size=size.font_size,
                                        series_colors=(plot.get("style") or {}).get("series_colors"))
        except ValueError as error:
            if str(error) not in ("figure_labels_overlap", "figure_text_outside_canvas", "figure_font_glyphs_unavailable"):
                raise
            for name in ("fields.svg", "fields.pdf", "fields.png"):
                (output / name).unlink(missing_ok=True)
            fields = {"skipped": str(error), "files": []}
    tables = _tables(canonical)
    tables["graphical-summary"] = drawn.summary
    csv_files = []
    for name, values in tables.items():
        if values:
            filename = f"{name}.csv"
            write_csv(output / filename, values)
            csv_files.append(filename)
    methods = common_statistics_methods(canonical)
    panels = []
    if image_figure is not None:
        from .figure_images import legend_sentence

        panels = ["a, " + legend_sentence(image_figure), "b,"]
        arrays: dict[str, Any] = {f"{index}-{cid}": array for index, panel in enumerate(image_figure.panels)
                                  for cid, array in panel.channels.items()}
        arrays.update({f"{index}-labels": panel.labels for index, panel in enumerate(image_figure.panels)})
        import numpy as np

        np.savez_compressed(output / "figure-images.npz", allow_pickle=False, **arrays)
    legend, gaps = (association_legend(canonical, order, drawn) if association
                    else comparison_legend(canonical, order, drawn, presentation, panels))
    (output / "methods.md").write_text(methods, encoding="utf-8")
    (output / "figure-legend.md").write_text(legend, encoding="utf-8")
    (output / "figure-caption.md").write_text("# Figure legend\n\n" + legend + "\n" + methods, encoding="utf-8")
    from .figure_style import FONT_FAMILY, FONT_FILES

    font_metadata = {"family": FONT_FAMILY, "weight": 400, "style": "normal",
                     "sha256": hashlib.sha256(FONT_FILES["regular"].read_bytes()).hexdigest()}
    metadata: dict[str, Any] = {"common_statistics_figure_version": "2.0.0",
                                "common_statistics_methods": template.model_dump(mode="json"), "style": style,
                                "font": FONT_FAMILY, "font_metadata": font_metadata,
                                "presentation": presentation, "forms": forms["forms"], "default_form": forms["default"],
                                "legend_gaps": gaps,
                                "compositions": [] if association else ["quantification", "images-quantification"],
                                "images": image_figure.record() if image_figure is not None else None,
                                "field_check": fields}
    annotations = [{"left": b.left, "right": b.right, "lines": b.lines} for b in drawn.annotations.brackets]
    source = {**canonical, **metadata, "unit_glyphs": drawn.glyphs, "graphical_summary": drawn.summary,
              "annotations": annotations, "layout": "deterministic beeswarm",
              "source_hashes": {n: hashlib.sha256((output / n).read_bytes()).hexdigest()
                                for n in [*csv_files, *((fields or {}).get("files") or [])]}}
    (output / "figure-data.json").write_text(json.dumps(source, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return {**metadata, "figure_version": "2.0.0", "formats": ["svg", "pdf", "png"], "svg_text": "editable",
            "source_files": ["figure.svg", "figure.pdf", "figure.png", *csv_files, "figure-data.json",
                             "figure-legend.md", "figure-caption.md", "methods.md",
                             *(["figure-images.npz"] if image_figure is not None else []),
                             *((fields or {}).get("files") or [])]}
