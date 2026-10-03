"""Versioned descriptive artifacts, with bounded presentation-only recovery."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from .descriptive_contracts import PagedDescriptiveOutput, PagedDescriptiveRequest, parse_descriptive_request
from .descriptive_figures import _caption, descriptive_methods, render_descriptive
from .descriptive_pages import VERSION, DescriptivePresentationError, page_layout, render_pages
from .exports_csv import csv_sha256, write_csv
from .images import sha256
from .statistical_methods import methods_metadata

TABLES = ("plot-data.csv", "field-summary.csv", "selection.csv", "missingness.csv")
DOCUMENTS = ("figure-caption.md", "methods.md", "figure-data.json")
PAGE_NAME = re.compile(r"figure-[0-9]{3}\.(svg|pdf|png)\Z")
INDEX_MAX_BYTES = 1024 * 1024


def _source(result):
    return {key: value for key, value in result.items() if key != "figure"}


def source_result_sha256(result):
    data = json.dumps(_source(result), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def _columns(rows):
    # v2 fixes CSV column order independently of JSON dict insertion order.
    return sorted({key for row in rows for key in row})


def _parse_manifest(value):
    manifest = PagedDescriptiveOutput.model_validate(value)
    pages = {name for page in manifest.pages for name in page.files.model_dump().values()}
    expected = pages | set(DOCUMENTS) | set(TABLES[:3])
    if "missingness.csv" in manifest.files:
        expected.add("missingness.csv")
    if set(manifest.source_files) != expected:
        raise ValueError("descriptive_output_manifest_mismatch")
    return manifest


def _manifest(result):
    if not isinstance(parse_descriptive_request(result["spec"]), PagedDescriptiveRequest):
        raise ValueError("descriptive_page_policy_required")
    manifest = _parse_manifest(result["figure"])
    if bool(result.get("missingness")) != ("missingness.csv" in manifest.files):
        raise ValueError("descriptive_output_manifest_mismatch")
    return manifest


def descriptive_output_file(manifest_data, name):
    """Cheap API boundary: validate the saved manifest, never recalculate science."""
    if name not in (*TABLES, *DOCUMENTS) and not PAGE_NAME.fullmatch(name):
        raise ValueError("descriptive_output_artifact_not_found")
    manifest = _parse_manifest(manifest_data)
    if name not in manifest.files:
        raise ValueError("descriptive_output_artifact_not_found")
    return manifest.files[name]


def read_descriptive_output_index(path: Path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > INDEX_MAX_BYTES:
        raise ValueError("descriptive_output_manifest_mismatch")
    with path.open("rb") as stream:
        content = stream.read(INDEX_MAX_BYTES + 1)
    if len(content) > INDEX_MAX_BYTES:
        raise ValueError("descriptive_output_manifest_mismatch")
    return _parse_manifest(json.loads(content.decode("utf-8"))).model_dump(mode="json")


def _source_document(result, layout, font_metadata, csv_hashes, methods_template=None):
    return {**_source(result), **methods_metadata(methods_template), "descriptive_figure_version": VERSION, "style": layout["style"],
            "field_labels": layout["labels"], "page_plan": layout["page_plan"],
            "y_limits": layout["y_limits"], "y_ticks": layout["y_ticks"],
            "font_metadata": font_metadata, "jitter_seed": 0, "source_hashes": csv_hashes}


def _output_caption(result, layout, status):
    text = _caption(result, layout["labels"])
    count, pages = result["counts"]["observations"], len(layout["page_plan"])
    if result["spec"]["plot"]["language"] == "ja":
        statement = (f"全{pages}ページに合計{count}観測を表示した。" if status == "ready" else
                     f"合計{count}観測を全件の表に保存した。図は作成できなかった。")
        text = text.replace(f"採用した {count} 観測を表示した。", statement)
    else:
        statement = (f"{count} selected observations are shown across all {pages} pages." if status == "ready" else
                     f"All {count} selected observations are retained in the source tables. No figure was produced.")
        text = text.replace(f"{count} selected observations are shown.", statement)
    text += "\nPage / saved field mapping (field numbers are global; all pages share one Y scale):\n"
    for page in layout["page_plan"]:
        text += f"- Page {page['page_index']}: " + "; ".join(
            f"{layout['labels'][fid]}: field_id={fid}" for fid in page["field_ids"]) + "\n"
    if status != "ready":
        text += "The mapping describes the planned pages; no partially rendered page is published.\n"
    return text


def _methods_text(result, status, methods_template):
    return descriptive_methods(result, methods_template=methods_template) + (
        f"\nDescriptive figure policy: {VERSION} (field-pages); output status: {status}. "
        "Pages preserve the complete field order, global field labels and common Y limits/ticks. "
        "Pagination does not select observations or change any numerical summary.\n")


def render_descriptive_output(result, output: Path, *, methods_template=None):
    document_metadata = methods_metadata(methods_template)
    request = parse_descriptive_request(result["spec"])
    if not isinstance(request, PagedDescriptiveRequest):
        return render_descriptive(result, output, methods_template=methods_template)
    layout = page_layout(result)
    output.mkdir(parents=True, exist_ok=True)
    data_files = []
    for name, rows in (("plot-data.csv", result["plot_data"]), ("field-summary.csv", result["field_summary"]),
                       ("selection.csv", result["selection"]["records"]), ("missingness.csv", result["missingness"])):
        if rows:
            if (output / name).exists():
                raise FileExistsError("descriptive_output_destination_not_empty")
            write_csv(output / name, rows, columns=_columns(rows))
            data_files.append(name)
    error, font_metadata, pages = None, None, []
    with TemporaryDirectory(prefix=".descriptive-pages-", dir=output) as temporary:
        staging = Path(temporary)
        try:
            font_metadata = render_pages(result, staging, layout)
        except DescriptivePresentationError as exc:
            error = {"code": exc.code, "page_index": exc.page_index}
        else:
            for plan in layout["page_plan"]:
                page_files = {suffix: f"figure-{plan['page_index']:03d}.{suffix}" for suffix in ("svg", "pdf", "png")}
                for name in page_files.values():
                    if (output / name).exists():
                        raise FileExistsError("descriptive_output_destination_not_empty")
                    shutil.move(str(staging / name), str(output / name))
                pages.append({"page_index": plan["page_index"], "files": page_files})
    status = "ready" if error is None else "tables_only"
    (output / "figure-caption.md").write_text(_output_caption(result, layout, status), encoding="utf-8")
    methods = _methods_text(result, status, methods_template)
    (output / "methods.md").write_text(methods, encoding="utf-8")
    csv_hashes = {name: sha256(output / name) for name in data_files}
    _json(output / "figure-data.json", _source_document(result, layout, font_metadata, csv_hashes, methods_template))
    files = [*data_files, *DOCUMENTS, *(name for page in pages for name in page["files"].values())]
    manifest = PagedDescriptiveOutput.model_validate({
        **document_metadata,
        "descriptive_figure_version": VERSION, "status": status, "error": error,
        "field_order": layout["order"], "page_plan": layout["page_plan"], "pages": pages,
        "y_limits": layout["y_limits"], "y_ticks": layout["y_ticks"], "style": layout["style"],
        "font_metadata": font_metadata, "source_result_sha256": source_result_sha256(result),
        "source_files": files, "files": {name: {"sha256": sha256(output / name), "bytes": (output / name).stat().st_size}
                                         for name in files},
    })
    saved = manifest.model_dump(mode="json")
    # Private small index for per-file downloads; not a self-hashed artifact.
    _json(output / "descriptive-output.json", saved)
    return saved


def validate_descriptive_output(result, source_root: Path, *, require_index=False):
    """Bind the saved page plan and private artifact bytes to the full numerical result."""
    manifest = _manifest(result)
    index = source_root / "descriptive-output.json"
    if (require_index or index.exists()) and read_descriptive_output_index(index) != manifest.model_dump(mode="json"):
        raise ValueError("descriptive_output_manifest_mismatch")
    layout = page_layout(result)
    if (manifest.source_result_sha256 != source_result_sha256(result)
            or manifest.field_order != layout["order"]
            or [page.model_dump(mode="json") for page in manifest.page_plan] != layout["page_plan"]
            or manifest.y_limits != layout["y_limits"] or manifest.y_ticks != layout["y_ticks"]
            or manifest.style != layout["style"]):
        raise ValueError("descriptive_output_source_mismatch")
    for name, record in manifest.files.items():
        path = source_root / name
        if (path.is_symlink() or not path.is_file() or path.stat().st_size != record.bytes or sha256(path) != record.sha256):
            raise ValueError("descriptive_output_artifact_mismatch")
    source = json.loads((source_root / "figure-data.json").read_text(encoding="utf-8"))
    csv_hashes = {name: manifest.files[name].sha256 for name in TABLES if name in manifest.files}
    if source != _source_document(result, layout, manifest.font_metadata, csv_hashes, manifest.methods_template):
        raise ValueError("descriptive_output_source_mismatch")
    if manifest.methods_template is not None and (source_root / "methods.md").read_text(encoding="utf-8") != _methods_text(
            result, manifest.status, manifest.methods_template):
        raise ValueError("descriptive_output_source_mismatch")
    # Rehashed CSVs must still match the canonical rows. Stream through the same
    # serializer in memory, never through unmanaged OS temporary storage.
    for name, rows in (("plot-data.csv", result["plot_data"]), ("field-summary.csv", result["field_summary"]),
                       ("selection.csv", result["selection"]["records"]), ("missingness.csv", result["missingness"])):
        if rows and csv_sha256(rows, columns=_columns(rows)) != manifest.files[name].sha256:
            raise ValueError("descriptive_output_source_mismatch")
    return manifest


def copy_descriptive_output(result, source_root: Path, destination: Path):
    manifest = validate_descriptive_output(result, source_root, require_index=True)
    destination.mkdir(parents=True, exist_ok=True)
    for name in manifest.source_files:
        target = destination / name
        if target.exists():
            raise FileExistsError("descriptive_output_destination_not_empty")
        shutil.copyfile(source_root / name, target)
    return manifest.model_dump(mode="json")


def replay_descriptive_output(recorded, fresh, source_root: Path, destination: Path):
    saved = validate_descriptive_output(recorded, source_root)
    manifest = render_descriptive_output(fresh, destination, methods_template=saved.methods_template)
    _json(destination / "descriptive-output-verification.json", {
        "descriptive_figure_version": VERSION,
        "matched_saved_description": _source(recorded) == _source(fresh),
        "matched_page_mapping": manifest["page_plan"] == [page.model_dump(mode="json") for page in saved.page_plan],
        "saved_figure_status": saved.status, "replayed_figure_status": manifest["status"],
        "saved_font_metadata": saved.font_metadata, "replayed_font_metadata": manifest["font_metadata"],
        "original_artifacts_unchanged": True,
    })
    return manifest
