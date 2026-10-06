"""Source-linked per-field descriptive figures; no inferential renderer is called."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from matplotlib.text import Text

from .descriptive import region_report_measurement_policy
from .descriptive_contracts import DescriptiveRequest, parse_descriptive_request
from .exports_csv import write_csv
from .figures import LABELS, _validate_text_layout, apply_plot_controls, figure_settings, plt, select_font
from .statistical_methods import methods_metadata, readable_descriptive_methods

FIGURE_VERSION = "1.0.1"


def _source_measurement_policy(result):
    if result.get("source_kind") != "region-2d":
        return None
    policies = [region_report_measurement_policy({
        "protocol_version": field.get("measurement_protocol", "1.0.0"),
        "measurement": field.get("measurement"),
    }) for field in result["source_fields"]]
    if not policies or any(policy != policies[0] for policy in policies[1:]):
        raise ValueError("region_measurement_protocol_mismatch")
    return policies[0]


def _selected_channel(result):
    selection = result["spec"]["selection"]
    if selection["source"] != "region" or selection.get("channel_id") is None:
        return None
    return next(item["channel"] for item in result["source_fields"][0]["channel_provenance"]
                if item["channel"]["channel_id"] == selection["channel_id"])


def _caption(result, labels):
    ja = result["spec"]["plot"]["language"] == "ja"
    area_only = getattr(_source_measurement_policy(result), "mode", None) == "area_only"
    numeric = result["source_kind"] == "measured-numerical-assay"
    observation = {"regions": ("regions", "領域"), "nuclei": ("nuclei", "核"),
                   "observations": ("observations", "観測値")}[result["observation_kind"]][ja]
    counts, selection = result["counts"], result["selection"]
    channel = _selected_channel(result)
    selected_identity = (f"channel_id={channel['channel_id']}; label={channel['label']}; "
                         f"stain={channel.get('stain') or 'not recorded'}") if channel else None
    if ja:
        lines = ["# 図の説明", "", f"{result['metric']}（{result['unit']}）の視野別記述図。",
                 f"点は{observation}の測定値、四角は" + ("CSV の測定グループ" if numeric else "視野") + "内の中央値を示す。",
                 f"採用した {counts['observations']} 観測を表示した。",
                 "観測数・視野数は独立した実験反復数ではない。この記述解析では実験単位の独立性を判定していない。",
                 "検定、回帰、標準誤差、信頼区間は計算していない。撮影条件の比較可能性は確認していない。",
                 "四分位数は観測分布の記述であり信頼区間ではない。隣接順位間の線形補間 h=(n−1)p を使用した。",
                 f"入力 {selection['input_rows']}、明示除外 {selection['excluded']}、保存済み選別外 {selection['gate_unselected']}、"
                 f"指標欠測 {selection['missing_metric_selected']}。",
                 "点の横方向の配置にのみ固定乱数 seed=0 を使用した。値・選別は変更していない。"]
    else:
        lines = ["# Figure legend", "", f"Per-field descriptive measurements: {result['metric']} ({result['unit']}).",
                 f"Points are {observation}; squares show the median within each "
                 + ("CSV measurement group." if numeric else "field."),
                 f"{counts['observations']} selected observations are shown.",
                 "Observation and field counts do not denote independent experimental replicates. "
                 "Independent experimental units were not assessed in this descriptive analysis.",
                 "No hypothesis test, regression, standard error or confidence interval was calculated. "
                 "Acquisition comparability has not been established.",
                 "Quartiles describe the observed distribution, not uncertainty; linear interpolation uses h=(n−1)p.",
                 f"Input={selection['input_rows']}; explicitly excluded={selection['excluded']}; "
                 f"outside saved selection={selection['gate_unselected']}; missing metric={selection['missing_metric_selected']}.",
                 "Horizontal jitter affects display only (seed 0); values and selection are unchanged."]
    if selected_identity:
        lines.insert(3, ("測定チャンネル: " if ja else "Measured channel: ") + selected_identity + ".")
    if result.get("source_review") == "automatic_unreviewed":
        lines.append("領域の目視確認前に生成した記述図。" if ja else "Descriptive output generated before visual review of regions.")
    lines += ["", "Field / source mapping:"]
    for field in result["source_fields"]:
        fid = field["field_id"]
        summary = next(row for row in result["field_summary"] if row["field_id"] == fid)
        identity = "; ".join(f"{p['channel']['label']} (stain={p['channel'].get('stain') or 'unknown'})"
                             for p in field.get("channel_provenance", []))
        definition = field.get("region_set", {}).get("label", result["observation_kind"])
        lines.append(f"- {labels[fid]}: field_id={fid}; selected={summary['selected_rows']}; "
                     f"status={summary['status']}; definition={definition}; {identity}")
    for item in result.get("excluded_failed_fields", []):
        lines.append(f"- Explicitly excluded failed field: {item['field_id']}; reason={item['reason']}.")
    lines += ["", ("Selection reasons, source revisions, masks, area-only measurement policy and channel identities are recorded in "
                   if area_only else
                   "Selection reasons, source revisions, masks, backgrounds and channel identities are recorded in ") +
              "figure-data.json and source tables. Review the recorded measurement definition before publication.",
              "A journal-size preset controls formatting; it does not establish biological validity or journal acceptance."]
    lines.extend(f"- {warning}" for warning in result["warnings"])
    return "\n".join(lines) + "\n"


def descriptive_methods(result, *, methods_template=None):
    """Record the selected protocol rather than borrowing inferential Methods text."""
    if methods_metadata(methods_template):
        return readable_descriptive_methods(result)
    spec = parse_descriptive_request(result["spec"])
    policy = _source_measurement_policy(result)
    if getattr(policy, "mode", None) == "raw_intensity":
        return readable_descriptive_methods(result)
    lines = ["# Cytellect descriptive Methods", "", "Generated from saved settings; review before publication.", "",
             f"Descriptive protocol: {result['descriptive_version']}; source: {result['source_kind']}.",
             f"Selector: {json.dumps(spec.selection.model_dump(), ensure_ascii=False, sort_keys=True)}.",
             f"Measurement unit: {result['unit']}. {result['metric_definition']}.",
             "Only field-level descriptions were calculated. Individual observations were retained and field medians "
             "and linearly interpolated quartiles were computed without assigning independent experimental units.",
             "No hypothesis test, regression, standard error or confidence interval was calculated. "
             "Known sample or condition labels were retained as metadata, not evidence of independence or comparability.",
             "Saved exclusions and selection flags were preserved. Missing outcomes were counted with reasons, "
             "not replaced with zeros. " + ("Area-only measurement was requested under measurement protocol 2.0.0 "
             f"and policy {policy.version} ({policy.mode}). Region area was computed from reviewed masks in original image coordinates. "
             "Pixel areas count mask pixels; physical areas use the saved confirmed X and Y pixel sizes when available. "
             "Fluorescence intensity and signal-saturation fractions were not measured. "
             "Background estimation and correction were not performed." if policy is not None else
             "Native negative background-corrected values were retained."),
             "Generic-region area repeated across channels was checked for agreement and counted once per region. "
             "Region identity does not establish one biological cell." + ("" if policy is not None else
             " Integrated intensity is a pixel sum, not concentration."),
             "No new normalization, image processing or selection was performed by this descriptive protocol.",
             ("Input, channel, mask, calibration and area-only policy provenance is stored in figure-data.json. "
              if policy is not None else
              "Input, channel, mask and background provenance is stored in figure-data.json. ") + "Original acquisition settings "
             "and biological suitability require researcher review. Output contains research information and must remain private.", "",
             "Selection: " + json.dumps(result["selection"], ensure_ascii=False, sort_keys=True),
             "Warnings: " + "; ".join(result["warnings"]), ""]
    return "\n".join(lines)


def _ylabel(result, ja):
    metric, unit = result["metric"], result["unit"]
    if result["source_kind"] == "legacy-image-measurements":
        label = LABELS.get(metric, (metric, metric))[ja]
        if unit == "a.u. × scaled pixel":
            label = label.replace("a.u. × pixel", "a.u. × scaled pixel").replace("任意単位 × 画素", "任意単位 × 縮小画素")
        if any(field.get("recipe", {}).get("id") == "ncl-legacy-rgb" for field in result["source_fields"]):
            label = label.replace("Nucleolar union", "High-intensity union").replace("核小体和集合", "高輝度領域の和集合")
        return label
    labels = {"area_px": ("Region area", "領域面積"), "area_um2": ("Region area", "領域面積"),
              "mean": ("Region mean intensity", "領域の平均輝度"),
              "median": ("Region median intensity", "領域の輝度中央値"),
              "integrated": ("Region integrated intensity", "領域の積算輝度"),
              "value": ("Measured value", "測定値")}
    label = labels[metric.removesuffix("_corrected")][ja]
    channel = _selected_channel(result)
    if channel:
        label = label.replace("Region ", channel["label"] + " ").replace("領域の", channel["label"] + "の")
    correction = ("背景補正" if ja else "background corrected") if metric.endswith("_corrected") else ""
    suffix = ", ".join(item for item in (correction, unit) if item)
    return label + (f"\n({suffix})" if suffix else "")


def render_descriptive(result, output: Path, *, methods_template=None):
    document_metadata = methods_metadata(methods_template)
    if result.get("analysis_kind") != "descriptive":
        raise ValueError("descriptive_result_required")
    request = DescriptiveRequest.model_validate(result["spec"])
    plot = request.plot.model_dump()
    if any(key in result for key in ("comparisons", "means", "unit_summary", "model")):
        raise ValueError("descriptive_inference_not_allowed")
    fields = [row["field_id"] for row in result["field_summary"]]
    order = plot["group_order"] or fields
    if len(order) != len(set(order)) or set(order) != set(fields):
        raise ValueError("group_order_must_match_groups")
    rows = result["plot_data"]
    if (not rows or len(rows) != result["counts"]["observations"]
            or len({row["observation_id"] for row in rows}) != len(rows)
            or any(row["field_id"] not in fields or not np.isfinite(row["value"]) for row in rows)):
        raise ValueError("descriptive_figure_source_mismatch")
    style, ja = figure_settings(plot), plot["language"] == "ja"
    first_observed = next(fid for fid in order if any(row["field_id"] == fid for row in rows))
    labels = {fid: f"{'視野' if ja else 'Field'} {index + 1}" for index, fid in enumerate(order)}
    if result["source_kind"] == "measured-numerical-assay":
        labels = {fid: f"{'測定群' if ja else 'Set'} {index + 1}" for index, fid in enumerate(order)}
    size = style["font_size_pt"]
    output.mkdir(parents=True, exist_ok=True)
    with plt.rc_context({"font.size": size, "axes.titlesize": size, "axes.labelsize": size,
                         "xtick.labelsize": size, "ytick.labelsize": size, "legend.fontsize": size,
                         "font.weight": "normal", "axes.labelweight": "normal", "axes.titleweight": "normal",
                         "svg.fonttype": "none", "pdf.fonttype": 42, "text.usetex": False,
                         "text.parse_math": False, "axes.unicode_minus": False, "axes.linewidth": .6,
                         "svg.hashsalt": "cytellect-descriptive-figure-" + FIGURE_VERSION}):
        figure, axes = plt.subplots(figsize=(style["width_inches"], style["height_inches"]), layout="constrained")
        try:
            rng = np.random.default_rng(0)
            for index, fid in enumerate(order):
                values = [row["value"] for row in rows if row["field_id"] == fid]
                summary = next(row for row in result["field_summary"] if row["field_id"] == fid)
                if len(values) != summary["selected_rows"]:
                    raise ValueError("descriptive_figure_source_mismatch")
                if values:
                    axes.scatter(index + rng.uniform(-.15, .15, len(values)), values, s=9,
                                 color="#526b78", alpha=.65, linewidths=0,
                                 label=("観測値" if ja else "Observation") if fid == first_observed else None)
                    axes.scatter(index + .23, summary["median"], s=17, marker="s", facecolors="none",
                                 edgecolors="#17292f", linewidths=.7,
                                 label=(("測定群中央値" if ja else "Set median")
                                        if result["source_kind"] == "measured-numerical-assay"
                                        else "視野中央値" if ja else "Field median") if fid == first_observed else None)
            ticks = [f"{labels[fid]}\n{sum(row['field_id'] == fid for row in rows)} "
                     + ("観測" if ja else "obs.") for fid in order]
            axes.set_xticks(range(len(order)), ticks)
            axes.set_xlim(-.5, len(order) - .5)
            axes.set_xlabel(plot["x_label"] or ("測定グループ" if result["source_kind"] == "measured-numerical-assay" and ja
                                               else "Measurement group" if result["source_kind"] == "measured-numerical-assay"
                                               else "視野" if ja else "Field"))
            axes.set_ylabel(plot["y_label"] or _ylabel(result, ja))
            axes.set_title("測定値の分布" if ja else "Observed measurements", loc="left", pad=7)
            axes.spines[["top", "right"]].set_visible(False)
            handles, names = axes.get_legend_handles_labels()
            if handles:
                figure.legend(handles, names, loc="outside upper center", frameon=False, ncols=2,
                              handletextpad=.4, columnspacing=1)
            axes.get_xticklabels()
            axes.get_yticklabels()
            texts = figure.findobj(match=Text)
            selected_font = select_font(plot["language"], "".join(item.get_text() for item in texts))
            for item in texts:
                properties = item.get_fontproperties().copy()
                properties.set_file(str(selected_font.path))
                properties.set_family(selected_font.family)
                properties.set_weight(selected_font.weight)
                item.set_fontproperties(properties)
            apply_plot_controls(axes, plot)
            _validate_text_layout(figure, axes)
            for suffix in ("svg", "pdf", "png"):
                metadata: dict[str, str | None] = {"Creator": "Cytellect descriptive figure " + FIGURE_VERSION}
                if suffix == "svg":
                    metadata["Date"] = None
                if suffix == "pdf":
                    metadata.update(CreationDate=None, ModDate=None)
                figure.savefig(output / f"figure.{suffix}", dpi=style["png_dpi"], metadata=metadata)
        finally:
            plt.close(figure)
    files = ["figure.svg", "figure.pdf", "figure.png"]
    for name, items in (("plot-data", result["plot_data"]), ("field-summary", result["field_summary"]),
                        ("selection", result["selection"]["records"]), ("missingness", result["missingness"])):
        if items:
            write_csv(output / f"{name}.csv", items)
            files.append(f"{name}.csv")
    (output / "figure-caption.md").write_text(_caption(result, labels), encoding="utf-8")
    (output / "methods.md").write_text(descriptive_methods(result, methods_template=methods_template), encoding="utf-8")
    source = {key: value for key, value in result.items() if key != "figure"}
    source.update(descriptive_figure_version=FIGURE_VERSION, style=style, field_labels=labels,
                  font_metadata=selected_font.metadata(), jitter_seed=0,
                  source_hashes={name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                                 for name in files if name.endswith(".csv")})
    source.update(document_metadata)
    (output / "figure-data.json").write_text(json.dumps(source, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                                           encoding="utf-8")
    files.extend(["figure-caption.md", "figure-data.json", "methods.md"])
    return {**document_metadata, "descriptive_figure_version": FIGURE_VERSION, "style": style,
            "font": selected_font.family, "font_metadata": selected_font.metadata(),
            "formats": ["svg", "pdf", "png"], "svg_text": "editable", "source_files": files}
