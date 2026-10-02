"""Private measured-assay packages and replay from the exact source CSV."""
import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

from .contracts import StatisticsRequest
from .exports import _json, environment
from .figures import render_figures
from .images import sha256
from .numerical_csv import analyze_numeric, parse_numeric_csv
from .replay import _inside

FORMAT = "cytellect-numerical-reproducibility/1"


def numeric_methods(result, source):
    spec = result["spec"]
    return "\n".join([
        "# Cytellect measured-assay Methods", "",
        "Generated from saved settings; review before publication.", "",
        f"Table ID: {source['table_id']}. Input CSV SHA-256: {source['sha256']}.",
        f"Assay: {result.get('assay', '')}; unit: {result.get('unit', '')}.",
        "UTF-8 measured values were imported without instrument normalization or image processing. "
        "Nonfinite values and inconsistent metadata are rejected, not silently removed.",
        f"Statistics protocol: {result['statistics_version']}. Aggregation: {result['aggregation']}.",
        "Observations, fields and declared independent experimental units are counted separately. "
        "Biological independence is a researcher declaration, not inferred from row count.",
        f"Paired analysis: {spec['paired']}; independent units confirmed: {spec['independent_units_confirmed']}.",
        "Paired tests use declared complete pair IDs; unpaired comparisons use Welch t tests. "
        "Tests are two-sided. Effect estimates, standard errors, degrees of freedom and p values are retained.",
        f"Baseline: {spec['baseline']}; prespecified comparisons: "
        f"{json.dumps(spec['comparisons'], ensure_ascii=False)}; Holm family: {spec['comparison_family']}.",
        "Individual 95% confidence intervals are not simultaneous multiplicity-adjusted intervals.",
        "Warnings: " + "; ".join(result.get("warnings", [])), "",
        "[source.json](source.json) records input identity; [statistics.json](statistics.json) contains "
        "the authoritative result and plot settings. [table.json](table.json) retains parsed observations. "
        "[provenance.json](provenance.json) and [environment.json](environment.json) identify code and dependencies.",
        "CSV exports escape spreadsheet formula characters in text; JSON preserves original text. "
        "The original input CSV is omitted. Follow [REPLAY.md](REPLAY.md) with its exact private original. "
        "The package itself contains confidential measurements and conditions.", "",
    ])


def build_numeric_bundle(destination: Path, *, content: bytes, table_id: str, result, provenance):
    """Called inside the table-statistics job after figures are generated."""
    parsed = parse_numeric_csv(content)
    source = {"table_id": table_id, "kind": "measured-numerical-assay",
              "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
    if result.get("table_id") != table_id:
        raise ValueError("numeric_export_source_mismatch")
    bundle = destination / "bundle"
    bundle.mkdir(exist_ok=False)
    _json(bundle / "source.json", source)
    _json(bundle / "table.json", parsed)
    _json(bundle / "statistics.json", result)
    _json(bundle / "environment.json", environment())
    _json(bundle / "provenance.json", provenance)
    for file in sorted(destination.iterdir()):
        if file.is_file() and (file.suffix == ".csv" or file.name in {
            "figure.png", "figure.svg", "figure.pdf", "figure-caption.md", "figure-data.json"
        }):
            shutil.copyfile(file, bundle / file.name)
    methods = numeric_methods(result, source)
    (bundle / "methods.md").write_text(methods, encoding="utf-8")
    (destination / "methods.md").write_text(methods, encoding="utf-8")
    (bundle / "replay.py").write_text(
        '"""Use the recorded Cytellect code and locked environment."""\n'
        'from cytellect_analysis.numeric_export import main\n'
        'if __name__ == "__main__":\n    main()\n', encoding="utf-8")
    (bundle / "REPLAY.md").write_text(
        "# Replay measured-assay statistics\n\n"
        "Restore the exact code identity and locked dependencies in provenance.json/environment.json. "
        "From this extracted private package run:\n\n"
        "    python replay.py --bundle-dir . --input-csv /private/original.csv --output-dir /private/replayed\n\n"
        "Package hashes and the original CSV byte hash are checked before analysis. "
        "The original CSV is not included. Replay parses it again, checks the normalized observations "
        "against table.json, and recalculates saved comparisons and figures without network access. "
        "Compare statistics.json, source CSVs and figures; retain the declared table identity. "
        "Keep both source and results private.\n", encoding="utf-8")
    manifest = {"format": FORMAT, "table_id": table_id, "raw_included": False,
                "replay_scope": "hash-verified measured CSV -> saved statistics and figures",
                "files": {p.name: sha256(p) for p in sorted(bundle.iterdir()) if p.is_file()}}
    _json(bundle / "manifest.json", manifest)
    with zipfile.ZipFile(destination / "analysis.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(bundle.iterdir()):
            entry = zipfile.ZipInfo(path.name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o600 << 16
            archive.writestr(entry, path.read_bytes())
    return destination / "analysis.zip"


def replay_numeric(bundle_dir: Path, input_csv: Path, output_dir: Path):
    bundle_dir, output_dir = bundle_dir.resolve(), output_dir.resolve()
    if output_dir.is_relative_to(bundle_dir) or bundle_dir.is_relative_to(output_dir):
        raise ValueError("replay_output_must_be_separate")
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != FORMAT:
        raise ValueError("numeric_replay_format_invalid")
    required = {"source.json", "table.json", "statistics.json", "environment.json", "provenance.json"}
    if not required.issubset(manifest.get("files", {})):
        raise ValueError("numeric_replay_manifest_incomplete")
    for relative, expected in manifest["files"].items():
        if sha256(_inside(bundle_dir, relative)) != expected:
            raise ValueError("replay_bundle_hash_mismatch")
    source = json.loads((bundle_dir / "source.json").read_text(encoding="utf-8"))
    if input_csv.stat().st_size != source["bytes"] or source["bytes"] > 8 * 1024**2:
        raise ValueError("replay_original_hash_mismatch")
    content = input_csv.read_bytes()
    if len(content) != source["bytes"] or hashlib.sha256(content).hexdigest() != source["sha256"]:
        raise ValueError("replay_original_hash_mismatch")
    parsed = parse_numeric_csv(content)
    if parsed != json.loads((bundle_dir / "table.json").read_text(encoding="utf-8")):
        raise ValueError("numeric_replay_observations_mismatch")
    recorded = json.loads((bundle_dir / "statistics.json").read_text(encoding="utf-8"))
    if recorded.get("table_id") != source["table_id"] or manifest.get("table_id") != source["table_id"]:
        raise ValueError("numeric_export_source_mismatch")
    fresh = analyze_numeric(parsed["rows"], StatisticsRequest.model_validate(recorded["spec"]))
    fresh["table_id"] = source["table_id"]
    output_dir.mkdir(parents=True, exist_ok=False)
    fresh["figure"] = render_figures(fresh, output_dir)
    _json(output_dir / "statistics.json", fresh)
    (output_dir / "methods.md").write_text(numeric_methods(fresh, source), encoding="utf-8")
    return fresh


def main():
    parser = argparse.ArgumentParser(description="Replay statistics from a hash-verified measured CSV")
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    replay_numeric(args.bundle_dir, args.input_csv, args.output_dir)


if __name__ == "__main__":
    main()
