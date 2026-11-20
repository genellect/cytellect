"""Refresh publication prose while keeping the published drawings byte for byte.

Only a result already in the old catalogue, with identical figure requests, is eligible.
The production drawing functions supply the description of marks for the legend; their
temporary canvas is never exported. This mode does not validate or replace any drawing.
"""
from __future__ import annotations

import copy
import hashlib
import json
import zipfile
from pathlib import Path


def legend(result: dict, item: dict) -> tuple[str, list[str]] | None:
    if item["figure"].get("common_statistics_figure_version") != "2.0.0":
        return None
    import matplotlib.pyplot as plt
    from cytellect_analysis.common_statistics_contracts import CommonStatisticsResult
    from cytellect_analysis.figure_images import image_channels, recorded_legend_sentence
    from cytellect_analysis.figure_legend import association_legend, comparison_legend
    from cytellect_analysis.figure_style import rc
    from cytellect_analysis.publication_figure import draw_association, draw_comparison
    from pydantic import TypeAdapter

    canonical = copy.deepcopy(result)
    canonical.pop("figure", None)
    canonical.pop("source_job_id", None)
    canonical["spec"]["plot"] = item["plot"]
    canonical = TypeAdapter(CommonStatisticsResult).validate_python(canonical).model_dump(mode="json")
    plot: dict = canonical["spec"]["plot"]
    order = plot.get("group_order") or canonical["spec"]["conditions"]
    presentation = item["figure"]["presentation"]
    style = item["figure"]["style"]
    with plt.rc_context(rc(style["font_size_pt"])):
        figure, axes = plt.subplots(figsize=(style["width_inches"], style["height_inches"]))
        try:
            if canonical["analysis_kind"] == "region-association":
                return association_legend(canonical, order, draw_association(figure, axes, canonical, plot, order))
            drawn = draw_comparison(figure, axes, canonical, plot, presentation, order)
            panels = None
            if images := item["figure"].get("images"):
                _, _, names = image_channels(canonical)
                panels = ["a, " + recorded_legend_sentence(images, names), "b,"]
            return comparison_legend(canonical, order, drawn, presentation, panels)
        finally:
            plt.close(figure)


def reuse_item(catalog, previous: Path, result: dict, item: dict) -> dict:
    """Copy content-addressed assets, replacing only the legend and its gap metadata."""
    updated = copy.deepcopy(item)
    for name in item["files"].values():
        body = (previous / name).read_bytes()
        if hashlib.sha256(body).hexdigest()[:24] != Path(name).stem:
            raise ValueError(f"published figure checksum mismatch: {name}")
        if catalog.save(body, Path(name).suffix) != name:
            raise ValueError("published figure filename mismatch")
    if prose := legend(result, updated):
        text, gaps = prose
        updated["files"]["figure-legend.md"] = catalog.save(text.encode("utf-8"), ".md")
        updated["figure"]["legend_gaps"] = gaps
    return updated


def package_root(previous: Path, document: dict, identity: str, item: dict, target: Path, out: Path) -> Path:
    """Recover the exact archived drawing/source files for a publication package."""
    entry = next((entry for entry in document["packages"]
                  if document["sources"][entry["source"]]["group"] == identity
                  and document["groups"][identity]["figures"][entry["figure"]]["plot"] == item["plot"]), None)
    if entry is None:
        raise ValueError(f"no published package drawing for {identity}")
    package = previous / entry["files"]["publication.zip"]
    with package.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest()[:24] != package.stem:
            raise ValueError("published package checksum mismatch")
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(package) as archive:
        for name in item["figure"]["source_files"]:
            if Path(name).name != name or "\\" in name:
                raise ValueError("unsafe published figure filename")
            (out / name).write_bytes(archive.read(f"edited-figure/{name}"))
    text = (target / item["files"]["figure-legend.md"]).read_text(encoding="utf-8")
    (out / "figure-legend.md").write_text(text, encoding="utf-8", newline="\n")
    methods = (out / "methods.md").read_text(encoding="utf-8")
    (out / "figure-caption.md").write_text("# Figure legend\n\n" + text + "\n" + methods, encoding="utf-8", newline="\n")
    (out / "result.json").write_text(json.dumps({"spec": {"plot": item["plot"]}}), encoding="utf-8")
    return out
