"""Refresh publication prose while keeping the published drawings byte for byte.

Only a result already in the old catalogue, with identical figure requests, is eligible.
The production drawing functions supply the description of marks for the legend; their
temporary canvas is never exported. This mode does not validate or replace any drawing.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import zipfile
from pathlib import Path


def scientific_key(result: dict) -> str:
    """Exact recorded values and field bindings, allowing capture IDs and explicit defaults."""
    from cytellect_analysis.common_statistics_contracts import FigurePresentation

    from .figure_catalog import UUID, VERSION_RECORDS

    value = copy.deepcopy(result)
    for key in ("figure", "source_job_id", "source_fingerprint"):
        value.pop(key, None)
    plot = value.get("spec", {}).get("plot", {})
    if plot.get("presentation") in (None, FigurePresentation(version="1.0.0").model_dump(mode="json")):
        plot.pop("presentation", None)

    def canonical(item):
        if isinstance(item, dict):
            return {key: (inner if key in {"field_id", "field_ids"} else canonical(inner))
                    for key, inner in item.items() if key not in VERSION_RECORDS}
        if isinstance(item, list):
            return [canonical(inner) for inner in item]
        return UUID.sub("*", item) if isinstance(item, str) else item
    return json.dumps(canonical(value), sort_keys=True, separators=(",", ":"))


class PublishedDrawings:
    """Match scientific inputs exactly before consulting the old drawing settings and bytes."""

    def __init__(self, snapshot: Path, document: dict):
        self.document = document
        self.by_value: dict[str, set[str]] = {}
        checked: dict[str, str] = {}

        def add(job, body):
            source = document["sources"].get(job)
            if source and source["group"] in document["groups"]:
                self.by_value.setdefault(scientific_key(json.loads(body)), set()).add(source["group"])

        index = json.loads((snapshot / "index.json").read_text(encoding="utf-8"))["entries"]
        journal = json.loads((snapshot / "journal.json").read_text(encoding="utf-8"))["entries"]
        responses = [(key.removeprefix("GET "), entry) for key, entry in index.items() if key.startswith("GET ")]
        responses += [(entry["path"], entry) for entry in journal if entry["method"] == "GET"]
        for path, entry in responses:
            found = re.fullmatch(r"/v1/jobs/([^/]+)/(result|common-statistics)", path)
            if found and entry.get("file") and (source := document["sources"].get(found[1])):
                name = entry["file"]
                if name not in checked:
                    checked[name] = scientific_key(json.loads((snapshot / name).read_text(encoding="utf-8")))
                self.by_value.setdefault(checked[name], set()).add(source["group"])
        if (snapshot.parent / "seed.zip").is_file():
            with zipfile.ZipFile(snapshot.parent / "seed.zip") as archive:
                for name in archive.namelist():
                    if found := re.fullmatch(r"runs/([^/]+)/output/result.json", name):
                        add(found[1], archive.read(name))

    def choose(self, result: dict, plot: dict, images: bool) -> tuple[str, dict]:
        from .figure_catalog import _identity, variants

        known = self.by_value.get(scientific_key(result), set())
        if not known:
            raise ValueError("no identical published result; a new drawing requires a normal figures build")
        candidates = [key for key in sorted(known) if key in self.document["groups"]
                      and plot == self.document["groups"][key]["opening"]["plot"]
                      and variants(result, self.document["groups"][key]["opening"]["figure"], plot, images) ==
                      [item["plot"] for item in self.document["groups"][key]["figures"]]]
        if not candidates:
            raise ValueError("published figure settings changed")
        if _identity(result) in candidates:
            candidates = [_identity(result)]
        # Equal values may have been recorded under several capture IDs. Ambiguous drawings must not be guessed.
        def drawing(key):
            group = self.document["groups"][key]
            return json.dumps([{**item, "files": {name: file for name, file in item["files"].items()
                                                  if name != "figure-legend.md"}}
                               for item in [group["opening"], *group["figures"]]], sort_keys=True)
        if len({drawing(key) for key in candidates}) != 1:
            raise ValueError("ambiguous published drawing for identical scientific values")
        selected = candidates[0]
        return selected, self.document["groups"][selected]


def legend(result: dict, item: dict) -> tuple[str, list[str]] | None:
    if item["figure"].get("common_statistics_figure_version") != "2.0.0":
        return None
    import matplotlib

    matplotlib.use("Agg")
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
