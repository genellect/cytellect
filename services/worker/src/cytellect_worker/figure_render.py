"""Presentation-only worker; never import or call statistical estimators."""
from copy import deepcopy
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from cytellect_analysis.common_statistics_figures import render_common_statistics
from cytellect_analysis.descriptive_output import render_descriptive_output
from cytellect_analysis.figures import render_figures
from cytellect_analysis.images import sha256
from cytellect_analysis.region_comparison_figures import render_region_comparison
from cytellect_api.db import jobs
from cytellect_api.figure_render import validated_plot
from cytellect_api.storage import read_json, write_json


def run_figure_render(store, job, output):
    source = store.one(jobs, id=job["payload"]["source_job_id"])
    if (source is None or source["workspace_id"] != job["workspace_id"]
            or source["revision_id"] != job["revision_id"] or source["state"] != "succeeded"):
        raise ValueError("figure_source_mismatch")
    result = deepcopy(read_json(store.safe_path(source["result_dir"], "result.json")))
    result.pop("figure", None)
    result.pop("source_job_id", None)
    result["spec"]["plot"] = validated_plot(result, job["payload"]["plot"])
    if result.get("analysis_kind") == "region-association" or result.get("region_comparison_version") == "2.0.0":
        renderer = render_common_statistics
    elif result.get("analysis_kind") == "region-comparison":
        renderer = render_region_comparison
    elif result.get("source_kind") == "measured-numerical-assay" and result.get("spec", {}).get("mode") != "descriptive":
        renderer = render_figures
    else:
        renderer = render_descriptive_output
    manifest = renderer(result, output)
    manifest["source_files"] = list(dict.fromkeys([*manifest["source_files"], *[f"figure.{suffix}" for suffix in manifest.get("formats", []) if suffix in ("svg", "pdf", "png")]]))
    result["figure"] = manifest
    result["source_job_id"] = source["id"]
    write_json(output / "result.json", result)
    if manifest.get("status", "ready") == "ready":
        names = manifest["source_files"]
        if any(Path(name).name != name or not (output / name).is_file() for name in names):
            raise ValueError("figure_artifact_mismatch")
        archive = output / "figure.zip"
        with ZipFile(archive, "w", compression=ZIP_DEFLATED) as bundle:
            for name in names:
                bundle.write(output / name, arcname=name)
        write_json(output / "figure-archive.json", {"sha256": sha256(archive), "bytes": archive.stat().st_size})
    return output


def run_publication_package(store, job, output):
    """Bundle one immutable analysis and its edited figure, preserving their identities."""
    records = [store.one(jobs, id=job["payload"][key]) for key in ("figure_job_id", "analysis_job_id")]
    if any(record is None or record["workspace_id"] != job["workspace_id"]
           or record["revision_id"] != job["revision_id"] or record["state"] != "succeeded"
           or not record["result_dir"] for record in records):
        raise ValueError("figure_source_mismatch")
    figure, analysis = records
    figure_root, analysis_root = (store.safe_path(record["result_dir"]) for record in records)
    result = read_json(figure_root / "result.json")
    source_id = result.get("table_id") if result.get("source_kind") == "measured-numerical-assay" else result.get("revision_id")
    if source_id != job["revision_id"]:
        raise ValueError("figure_source_mismatch")
    manifest = result.get("figure", {})
    names = list(dict.fromkeys([*manifest.get("source_files", []), *[f"figure.{suffix}" for suffix in manifest.get("formats", []) if suffix in ("svg", "pdf", "png")]]))
    if not names or any(Path(name).name != name or not (figure_root / name).is_file()
                        or (figure_root / name).is_symlink() for name in names):
        raise ValueError("figure_artifact_mismatch")
    original = analysis_root / "analysis.zip"
    if not original.is_file() or original.is_symlink():
        raise ValueError("publication_source_unavailable")
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "figure-result.json", result)
    receipt = {"version": "1.0.0", "revision_id": job["revision_id"],
               "figure_job_id": figure["id"], "analysis_job_id": analysis["id"],
               "files": {"analysis.zip": sha256(original), "figure-result.json": sha256(output / "figure-result.json"),
                         **{f"edited-figure/{name}": sha256(figure_root / name) for name in names}}}
    write_json(output / "manifest.json", receipt)
    (output / "README.md").write_text(
        "# Cytellect publication package\n\n"
        "`edited-figure/` contains the figure as saved in the workspace. "
        "`figure-result.json` contains its immutable measurements, statistics and plot settings.\n\n"
        "Extract `analysis.zip` and follow its replay instructions to regenerate the masks, "
        "measurements and statistics. Use that pinned Python environment to run "
        "`python replay-figure.py output` for the edited figure. "
        "Changing its appearance does not recalculate statistics. "
        "`manifest.json` records SHA-256 hashes linking these files.\n",
        encoding="utf-8")
    (output / "replay-figure.py").write_text(REPLAY_FIGURE, encoding="utf-8")
    archive = output / "publication.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as bundle:
        bundle.write(original, "analysis.zip")
        for name in names:
            bundle.write(figure_root / name, f"edited-figure/{name}")
        for name in ("figure-result.json", "manifest.json", "README.md", "replay-figure.py"):
            bundle.write(output / name, name)
    write_json(output / "publication-archive.json", {"sha256": sha256(archive), "bytes": archive.stat().st_size})
    write_json(output / "result.json", {"revision_id": job["revision_id"], "files": ["publication.zip"]})
    return output


REPLAY_FIGURE = """from pathlib import Path
import json
import hashlib
import sys
from cytellect_analysis.common_statistics_figures import render_common_statistics
from cytellect_analysis.descriptive_output import render_descriptive_output
from cytellect_analysis.figures import render_figures
from cytellect_analysis.region_comparison_figures import render_region_comparison
root = Path(__file__).resolve().parent
manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
for name, digest in manifest['files'].items():
    path = root / name
    if path.resolve().is_relative_to(root) is False or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError('source file changed')
result = json.loads((root / 'figure-result.json').read_text(encoding='utf-8'))
result.pop('figure', None)
if result.get('analysis_kind') == 'region-association' or result.get('region_comparison_version') == '2.0.0':
    renderer = render_common_statistics
elif result.get('analysis_kind') == 'region-comparison':
    renderer = render_region_comparison
elif result.get('source_kind') == 'measured-numerical-assay' and result.get('spec', {}).get('mode') != 'descriptive':
    renderer = render_figures
else:
    renderer = render_descriptive_output
renderer(result, Path(sys.argv[1]) if len(sys.argv) > 1 else root / 'regenerated-figure')
"""
