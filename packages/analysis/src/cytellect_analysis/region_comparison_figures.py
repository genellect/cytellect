"""Generic comparison figures reusing the audited unit/paired vector renderer."""
import hashlib
import json
from pathlib import Path

from .descriptive_figures import _source_measurement_policy, _ylabel
from .exports_csv import write_csv
from .figures import render_figures
from .region_comparison_contracts import RegionComparisonResult
from .statistical_methods import methods_metadata, readable_comparison_methods

FIGURE_VERSION = "1.0.0"


def _caption(result):
    ja = result["spec"]["plot"]["language"] == "ja"
    channel = result["channel"]
    identity = (f"{channel['label']}; channel_id={channel['channel_id']}; stain={channel.get('stain') or 'not recorded'}"
                if channel else "area; no intensity channel")
    lines = ["# 図の説明" if ja else "# Figure legend", "",
             f"{result['region']['label']}; {identity}; {result['metric']} ({result['unit']}).",
             ("小さい点は領域測定値、四角は視野中央値、色付きの点は独立実験単位の要約値。"
              "黒い菱形は独立実験単位の平均と点ごとの95%信頼区間を示す。" if ja else
              "Small points are region observations, squares are field medians, and colored points are independent-unit summaries. "
              "Black diamonds show independent-unit means and pointwise 95% confidence intervals."),
             ("視野内中央値 → 試料内の視野平均 → 独立実験単位内の試料平均。領域数を独立nに数えない。" if ja else
              "Aggregation: field median → mean of fields within sample → mean of samples within independent unit. "
              "Region observations do not increase independent n."),
             ("検定は両側。Holm補正は事前指定の比較集合全体に適用し、平均や差の95%信頼区間は同時信頼区間ではない。" if ja else
              "Tests are two-sided. Holm correction covers the complete declared contrast family; "
              "mean and difference 95% intervals are pointwise, not simultaneous intervals."),
             f"Family: {result['spec']['comparison_family']['family_id']}; source revision: {result['revision_id']}.",
             f"Source fingerprint: {result['source_fingerprint']}."]
    if result["spec"]["design"]["kind"] == "paired":
        lines.append("線は宣言された対応ペアを結ぶ。検定と差の区間はペア差から計算する。" if ja else
                     "Lines connect declared matched pairs. Tests and difference intervals use paired differences.")
    for row in result["counts"]:
        lines.append(f"- {row['condition']}: regions={row['observations']}; fields={row['selected_fields']}/{row['input_fields']}; "
                     f"samples={row['samples']}; independent units={row['experimental_units']}/{row['input_units']}; "
                     f"excluded units={row['explicitly_excluded_units']}; complete pairs={row['complete_pairs']}.")
    for row in result["comparisons"]:
        lines.append(f"- {row['group_a']} − {row['group_b']}: {row['method']}; estimate={row['estimate']:.8g}; "
                     f"95% CI [{row['ci_low']:.8g}, {row['ci_high']:.8g}]; t={row['statistic']:.8g}; "
                     f"df={row['degrees_of_freedom']:.8g}; p={row['p_value']:.8g}; Holm p={row['p_holm']:.8g}.")
    lines += ["", ("取得条件の比較可能性と独立性は利用者が記録した設計に基づく。自動的に確認された生物学的妥当性ではない。" if ja else
                   "Acquisition comparability and independence rely on the recorded researcher-reviewed design; "
                   "they are not machine-established biological validity."),
              "No normalization or batch adjustment. Jitter affects display only (seed 0). "
              "Omissions, source fields, units and pairs are recorded in the accompanying CSV files.",
              "A journal-size preset controls formatting, not journal acceptance or scientific validity."]
    lines.extend(f"- {item}" for item in result["warnings"])
    lines.extend(f"- Excluded failed field: {item['field_id']}; reason={item['reason']}."
                 for item in result["excluded_failed_fields"])
    return "\n".join(lines) + "\n"


def region_comparison_methods(result, *, methods_template=None):
    if methods_metadata(methods_template):
        return readable_comparison_methods(result)
    policy = _source_measurement_policy(result)
    if getattr(policy, "mode", None) == "raw_intensity":
        return readable_comparison_methods(result)
    return "\n".join([
        "# Cytellect generic-region comparison Methods", "", "Generated from saved settings; review before publication.",
        f"Region comparison protocol: {result['region_comparison_version']}; inference core: {result['inference_version']}.",
        f"Measurement: {result['metric']} ({result['unit']}); region: {result['region']['label']}.",
        "Channel: " + json.dumps(result["channel"], ensure_ascii=False, sort_keys=True),
        "Design: " + json.dumps(result["spec"]["design"], ensure_ascii=False, sort_keys=True),
        (f"Area-only measurement used measurement protocol 2.0.0 and policy {policy.version} ({policy.mode}). "
         "Region area was computed from reviewed masks in original image coordinates. "
         "Pixel areas count mask pixels; physical areas use the saved confirmed X and Y pixel sizes when available. "
         "Fluorescence intensity and signal-saturation fractions were not measured. "
         "Background estimation and correction were not performed. No normalization or additional gating was applied."
         if policy is not None else
         "Original-pixel measurements and reviewed masks/backgrounds were used without normalization or additional gating."),
        "Field medians were averaged within sample; sample summaries were averaged within experimental unit. "
        "Each retained independent unit contributed one value per condition. Unequal numbers of regions did not weight units.",
        "Independent groups used Welch t tests; declared paired designs used paired differences. All tests were two-sided. "
        "Holm correction covered the complete specified comparison family. Confidence intervals are pointwise 95%, not multiplicity-adjusted.",
        "Comparison family: " + json.dumps(result["spec"]["comparison_family"], ensure_ascii=False, sort_keys=True),
        "Acquisition review: " + json.dumps(result["acquisition"], ensure_ascii=False, sort_keys=True),
        "Missingness policy: " + result["spec"]["missingness_policy"],
        "Unresolved failures were not omitted. Explicit exclusions and unavailable outcomes remain in source and unit ledgers; "
        "unexcluded units without selected outcomes and incomplete pairs were rejected. Missingness was not assumed random.",
        "Source fingerprint: " + result["source_fingerprint"], "Warnings: " + "; ".join(result["warnings"]), "",
    ])


def render_region_comparison(result, output: Path, *, methods_template=None):
    document_metadata = methods_metadata(methods_template)
    canonical = RegionComparisonResult.model_validate({key: value for key, value in result.items() if key != "figure"}).model_dump(mode="json")
    counts = canonical["counts"]
    if (sum(row["observations"] for row in counts) != len(canonical["plot_data"])
            or sum(row["experimental_units"] for row in counts) != len(canonical["unit_summary"])):
        raise ValueError("region_comparison_result_required")
    plot = dict(canonical["spec"]["plot"])
    # This presentation adapter does not pretend that the selected marker is GFP/NCL.
    # The existing renderer's neutral value column and generic source-kind are used.
    plot["y_label"] = plot["y_label"] or _ylabel({**canonical, "unit": ""}, plot["language"] == "ja")
    presentation = {**canonical,
                    "spec": {"metric": "value", "mode": "experimental-unit",
                             "paired": canonical["spec"]["design"]["kind"] == "paired", "plot": plot},
                    "counts": [{**row, "fields": row["selected_fields"]} for row in counts]}
    manifest = render_figures(presentation, output)
    rendered = json.loads((output / "figure-data.json").read_text(encoding="utf-8"))
    tables = {"plot-data": canonical["plot_data"], "observations": canonical["observation_ledger"],
              "source-fields": canonical["source_field_ledger"], "field-summary": canonical["field_summary"],
              "sample-summary": canonical["sample_summary"], "experimental-units": canonical["unit_summary"],
              "unit-ledger": canonical["unit_ledger"], "pair-ledger": canonical["pair_ledger"],
              "comparisons": canonical["comparisons"], "missingness": canonical["missingness"],
              "excluded-failed-fields": canonical["excluded_failed_fields"]}
    for name, rows in tables.items():
        if rows:
            write_csv(output / f"{name}.csv", rows)
    (output / "figure-caption.md").write_text(_caption(canonical), encoding="utf-8")
    (output / "methods.md").write_text(region_comparison_methods(canonical, methods_template=methods_template), encoding="utf-8")
    csv_files = [f"{name}.csv" for name, rows in tables.items() if rows]
    source = {**canonical, "region_comparison_figure_version": FIGURE_VERSION,
              "renderer_version": manifest["figure_version"], "style": manifest["style"],
              "font_metadata": manifest["font_metadata"], "unit_glyphs": rendered["unit_glyphs"],
              "jitter_seed": 0, "source_hashes": {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                                                  for name in csv_files}}
    source.update(document_metadata)
    (output / "figure-data.json").write_text(json.dumps(source, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    manifest.update(region_comparison_figure_version=FIGURE_VERSION,
                    source_files=["figure.svg", "figure.pdf", "figure.png", *csv_files,
                                  "figure-caption.md", "figure-data.json", "methods.md"])
    manifest.update(document_metadata)
    return manifest
