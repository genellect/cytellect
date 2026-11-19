"""Figures of the public demo, drawn from its recorded results (build stage ``figures``).

The tour (``snapshot/journal.json``) records what a visitor's operations return: images,
measurements, statistics and the discussion. A figure is presentation only, what a saved result
looks like under the figure settings, so it is not part of that record. This stage draws, with
the production API and analysis package, each recorded result's figure and the figures the
「グラフ」 settings offer one change at a time (form, size, annotation, colour, legend, and the
representative images of the opening comparison), and writes them as ``snapshot/figures.json``.

The transport (``apps/web/src/lib/showcase/transport.ts``) answers figure requests from it by the
result and the settings, not by the request's text. A change of the renderer or of the figure
controls runs this stage again; the tour is not recorded again and its answers stay as they are,
except the figures this stage replaces.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import shutil
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any

FIGURE_RENDER = re.compile(r"^/v1/jobs/([0-9a-f-]{36})/figure-render$")
STATISTICS_POST = re.compile(r"^/v1/revisions/([0-9a-f-]{36})/(common-statistics|descriptive)$")
STATISTICS_GET = re.compile(r"^/v1/jobs/([0-9a-f-]{36})/(common-statistics|result)$")
JOB_FILE = re.compile(r"^/v1/jobs/([0-9a-f-]{36})/files/(.+)$")
PACKAGE = re.compile(r"^/v1/jobs/([0-9a-f-]{36})/publication-package$")
EXPORT = re.compile(r"^/v1/revisions/([0-9a-f-]{36})/export(\?.*)?$")
WORKSPACE = re.compile(r"^/v1/workspaces/([0-9a-f-]{36})(/|$)")
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
# The keys of a figure request the 「グラフ」 view sends (ConnectedResults.tsx `plot()`).
REQUEST_KEYS = ("width_inches", "height_inches", "font_size", "x_label", "y_label", "group_order", "kind", "preset",
                "language", "axes", "y_tick_step", "point_size", "style", "y_min", "y_max")
DEFAULT_PRESENTATION = {"version": "1.0.0", "annotation": "value", "size": "panel", "composition": "quantification",
                        "outlines": True}
# Files the view reads of a figure: the drawing, the legend draft, and the PNG it copies.
SHOWN = re.compile(r"\.svg$|^figure-legend\.md$")
VERSION_RECORDS = {"scipy_version", "numpy_version", "software", "versions"}


def _concrete(value: Any) -> Any:
    """A recorded request with the values it kept as "*" written as the client sends them."""
    if isinstance(value, dict):
        return {key: ("1.0.0" if key == "version" and inner == "*" else _concrete(inner)) for key, inner in value.items()}
    if isinstance(value, list):
        return [_concrete(inner) for inner in value]
    return value


def _identity(result: dict) -> str:
    """Results that draw the same figures: the same values (to 10 significant digits) whatever the
    identifiers the recording generated (a cohort, a job) and the library versions."""
    def canonical(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: canonical(inner) for key, inner in sorted(value.items()) if key not in VERSION_RECORDS}
        if isinstance(value, list):
            return [canonical(inner) for inner in value]
        if isinstance(value, float):
            return None if math.isnan(value) else float(f"{value:.10g}")
        if isinstance(value, str):
            return UUID.sub("*", value)
        return value
    body = {key: value for key, value in result.items() if key not in ("figure", "source_job_id")}
    return hashlib.sha256(json.dumps(canonical(body), sort_keys=True).encode()).hexdigest()[:24]


def _request_plot(plot: dict, presentation: dict | None) -> dict:
    value = {key: copy.deepcopy(plot.get(key)) for key in REQUEST_KEYS}
    value["y_min"], value["y_max"] = plot.get("y_min"), plot.get("y_max")
    if presentation is not None:
        value["presentation"] = copy.deepcopy(presentation)
    return value


def _comparison(result: dict) -> bool:
    return result.get("region_comparison_version") == "2.0.0" and result.get("analysis_kind") == "region-comparison"


def variants(result: dict, figure: dict, plot: dict, images: bool) -> list[dict]:
    """The figure requests the 「グラフ」 view sends from the opening figure, one change at a time
    (plan FD-02, FD-05): index 0 is the opening figure itself."""
    if not _comparison(result):
        base = _request_plot(plot, None)
        narrow = {**copy.deepcopy(base), "width_inches": 89 / 25.4, "height_inches": min(base["height_inches"], 170 / 25.4),
                  "font_size": min(base["font_size"], 7)}
        return [base, narrow]
    presentation = {**DEFAULT_PRESENTATION, **{key: value for key, value in (plot.get("presentation") or {}).items()
                                              if key in DEFAULT_PRESENTATION}}
    base = _request_plot({**plot, "kind": "superplot"}, presentation)

    def changed(**edits: Any) -> dict:
        value = copy.deepcopy(base)
        for key, inner in edits.items():
            if key in ("kind", "style"):
                value[key] = inner
            else:
                value["presentation"][key] = inner
        return value

    shown = (figure.get("presentation") or {}).get("observations") or "points"
    found = [base]
    for form in figure.get("forms") or []:
        if form.get("kind") == "superplot" and (form.get("observations") or "points") == shown:
            continue
        edit: dict[str, Any] = {"kind": form["kind"]}
        if form.get("observations"):
            edit["observations"] = form["observations"]
        found.append(changed(**edit))
    found += [changed(size="single-column"), changed(size="double-column"), changed(annotation="none")]
    descriptive = result.get("spec", {}).get("test") == "none" or "descriptive_comparison_no_test_or_interval" in (result.get("warnings") or [])
    if not descriptive:
        found.append(changed(annotation="stars"))
    if (result.get("spec", {}).get("design") or {}).get("kind") == "paired":
        found.append(changed(color_by="group"))
    found.append(changed(style={**base["style"], "show_legend": False}))
    if images and len(figure.get("compositions") or []) > 1:
        found.append(changed(composition="images-quantification"))
    return found


class Catalog:
    """Figures drawn through the production API on a copy of the published seed."""

    def __init__(self, api, target: Path):
        from cytellect_api.db import jobs

        self.api, self.target = api, target
        self.store, self.data = api.app.state.store, api.settings.data_dir
        self.jobs = jobs
        self.files_written = 0

    def save(self, body: bytes, suffix: str) -> str:
        name = f"{hashlib.sha256(body).hexdigest()[:24]}{suffix}"
        path = self.target / name
        if not path.is_file():
            path.write_bytes(body)
            self.files_written += 1
        return name

    def save_files(self, root: Path, names: list[str], png: bool) -> dict[str, str]:
        kept = {}
        for name in names:
            if SHOWN.search(name) or (png and name == "figure.png"):
                kept[name] = self.save((root / name).read_bytes(), Path(name).suffix)
        return kept

    def inject(self, job_id: str, workspace: str, result: dict, kind: str = "statistics") -> Path:
        """A recorded job, as the API saved it, so the production figure route can draw from it."""
        relative = f"showcase-figures/{job_id}"
        root = self.data / relative
        root.mkdir(parents=True, exist_ok=True)
        (root / "result.json").write_text(json.dumps(result))
        with self.store.transaction() as conn:
            conn.execute(self.jobs.insert().values(
                id=job_id, workspace_id=workspace, revision_id=result["revision_id"], kind=kind, state="succeeded",
                payload={}, created=time.time(), lease=None, lease_until=0, attempts=1, error=None, result_dir=relative))
        return root

    def render(self, source: str, workspace: str, plot: dict) -> tuple[dict, Path]:
        from .build import drain

        accepted = self.api.post(f"/v1/jobs/{source}/figure-render", {"request_id": str(uuid.uuid4()), "plot": plot})
        drain(self.api)
        job = self.store.one(self.jobs, id=accepted["job_id"])
        if job is None or job["state"] != "succeeded":
            raise RuntimeError(f"figure render of {source} failed: {job and job['error']}")
        root = self.store.safe_path(job["result_dir"])
        return json.loads((root / "result.json").read_text()), root


def opening_figure(result: dict, plot: dict, out: Path) -> dict:
    """The figure a statistics job draws with the opening figure settings (as the worker does)."""
    from cytellect_analysis.common_statistics_figures import render_common_statistics
    from cytellect_analysis.descriptive_output import render_descriptive_output
    from cytellect_analysis.statistical_methods import saved_methods_template
    from cytellect_api.figure_render import validated_plot

    drawn = copy.deepcopy(result)
    recorded = {"figure": drawn.pop("figure", {})}
    drawn.pop("source_job_id", None)
    drawn["spec"]["plot"] = validated_plot(drawn, plot)
    out.mkdir(parents=True, exist_ok=True)
    if _comparison(drawn):
        drawn["figure"] = render_common_statistics(drawn, out)
    else:
        drawn["figure"] = render_descriptive_output(drawn, out, methods_template=saved_methods_template(recorded))
    (out / "result.json").write_text(json.dumps(drawn))
    return drawn


def build(api, target: Path, scratch: Path) -> dict:
    """Write ``figures.json`` for the tour in ``target`` and drop the tour's own figure answers."""
    from cytellect_api.db import jobs

    catalog = Catalog(api, target)
    journal = json.loads((target / "journal.json").read_text())
    entries = journal["entries"]
    read = lambda entry: json.loads((target / entry["file"]).read_text())  # noqa: E731

    # The statistics the tour calculated: job, workspace, opening figure settings and recorded result.
    scene_workspace: dict[str, str] = {}
    for entry in entries:
        found = WORKSPACE.match(entry["path"])
        if found:
            scene_workspace.setdefault(entry["scene"], found.group(1))
    calculated: dict[str, dict] = {}
    renders: dict[str, str] = {}
    exports: dict[str, str] = {}
    packages: list[dict] = []
    for position, entry in enumerate(entries):
        method, path = entry["method"], entry["path"]
        if method == "POST" and STATISTICS_POST.match(path) and entry["file"] and entry["status"] < 300:
            job = read(entry)["job_id"]
            calculated.setdefault(job, {"workspace": scene_workspace[entry["scene"]], "plot": _concrete(json.loads(entry["body"])["plot"]),
                                        "kind": STATISTICS_POST.match(path).group(2)})
        elif method == "GET" and (found := STATISTICS_GET.match(path)) and found.group(1) in calculated and entry["file"]:
            calculated[found.group(1)].setdefault("result", read(entry))
        elif method == "POST" and (found := FIGURE_RENDER.match(path)) and entry["file"] and entry["status"] < 300:
            renders[read(entry)["job_id"]] = found.group(1)
        elif method == "POST" and EXPORT.match(path) and entry["file"] and entry["status"] < 300:
            exports[entry["scene"]] = read(entry)["job_id"]
        elif method == "POST" and (found := PACKAGE.match(path)) and entry["file"] and entry["status"] < 300:
            package = read(entry)["job_id"]
            zipped = next((later for later in entries[position + 1:] if later["method"] == "GET"
                           and later["path"] == f"/v1/jobs/{package}/files/publication.zip" and later["file"]), None)
            if zipped and found.group(1) in renders:
                packages.append({"source": renders[found.group(1)], "analysis": exports[entry["scene"]],
                                 "zip": target / zipped["file"], "workspace": scene_workspace[entry["scene"]]})

    # Saved statistics of the published seed (the opening view and 「保存した図」).
    seed = {row["id"]: row for row in catalog.store.rows(jobs, kind="statistics", state="succeeded")}
    groups: dict[str, dict] = {}
    sources: dict[str, dict] = {}
    for job, row in seed.items():
        result = json.loads((catalog.store.safe_path(row["result_dir"]) / "result.json").read_text())
        if result.get("source_kind") != "region-2d" or not result.get("figure"):
            continue
        group = groups.setdefault(_identity(result), {"seed": job, "members": []})
        group["members"].append(job)
        sources[job] = {"group": _identity(result), "workspace": row["workspace_id"], "revision": result["revision_id"], "seed": True}
    for job, value in calculated.items():
        if "result" not in value:
            continue
        identity = _identity(value["result"])
        group = groups.setdefault(identity, {"seed": None, "members": []})
        group["members"].append(job)
        sources[job] = {"group": identity, "workspace": value["workspace"], "revision": value["result"]["revision_id"]}

    written: dict[str, dict] = {}
    started = time.perf_counter()
    for count, (identity, group) in enumerate(sorted(groups.items())):
        if group["seed"]:
            representative = group["seed"]
            row = seed[representative]
            root = catalog.store.safe_path(row["result_dir"])
            opening = json.loads((root / "result.json").read_text())
            workspace = row["workspace_id"]
            plot = {**opening["spec"]["plot"], **({"presentation": DEFAULT_PRESENTATION} if _comparison(opening) else {})}
        else:
            representative = group["members"][0]
            value = calculated[representative]
            # The demo calculates with the opening figure (ConnectedResults.tsx `calculate()`).
            plot = {**value["plot"], **({"kind": "superplot", "presentation": DEFAULT_PRESENTATION}
                                        if value["kind"] == "common-statistics" else {})}
            root = scratch / representative
            opening = opening_figure(value["result"], plot, root)
            workspace = value["workspace"]
            catalog.inject(representative, workspace, opening)
        images = bool(group["seed"])
        figures = []
        for request in variants(opening, opening["figure"], opening["spec"]["plot"] if group["seed"] else plot, images):
            drawn, folder = catalog.render(representative, workspace, request)
            png = images and (not figures or request.get("presentation", {}).get("composition") == "images-quantification")
            figures.append({"plot": request, "figure": drawn["figure"],
                            "files": catalog.save_files(folder, drawn["figure"]["source_files"], png),
                            "root": folder})
        written[identity] = {
            "observations": (opening["figure"].get("presentation") or {}).get("observations") or "points",
            # A calculated job reads its figure from here; a saved job of the seed keeps its snapshot.
            "opening": {"figure": opening["figure"], "plot": opening["spec"]["plot"],
                        "files": catalog.save_files(root, opening["figure"]["source_files"], images)},
            "figures": figures,
        }
        print(f"figures {count + 1}/{len(groups)} {len(figures)} drawn, {time.perf_counter() - started:.0f}s", flush=True)

    # Publication packages of the tour: the recorded analysis with the opening figure drawn anew.
    from cytellect_worker.figure_render import run_publication_package

    package_entries = []
    for index, package in enumerate(packages):
        source = sources.get(package["source"])
        if source is None:
            continue
        group = written[source["group"]]
        figure = group["figures"][0]
        result = calculated[package["source"]]["result"] if package["source"] in calculated else None
        if result is None:
            continue
        figure_job = str(uuid.uuid4())
        rendered = copy.deepcopy(result)
        rendered.pop("figure", None)
        rendered["spec"]["plot"] = json.loads((figure["root"] / "result.json").read_text())["spec"]["plot"]
        rendered["figure"], rendered["source_job_id"] = figure["figure"], package["source"]
        root = catalog.inject(figure_job, package["workspace"], rendered, kind="figure-render")
        for name in figure["figure"]["source_files"]:
            shutil.copyfile(figure["root"] / name, root / name)
        analysis_root = catalog.inject(package["analysis"] if catalog.store.one(jobs, id=package["analysis"]) is None
                                       else str(uuid.uuid4()), package["workspace"], {"revision_id": result["revision_id"]}, kind="export")
        analysis_id = analysis_root.name
        with zipfile.ZipFile(package["zip"]) as recorded:
            (analysis_root / "analysis.zip").write_bytes(recorded.read("analysis.zip"))
        out = scratch / f"package-{index}"
        shutil.rmtree(out, ignore_errors=True)
        run_publication_package(catalog.store, {"payload": {"figure_job_id": figure_job, "analysis_job_id": analysis_id},
                                                "workspace_id": package["workspace"], "revision_id": result["revision_id"]}, out)
        package_entries.append({"source": package["source"], "figure": 0, "analysis": package["analysis"],
                                "files": {"publication.zip": catalog.save((out / "publication.zip").read_bytes(), ".zip")}})

    document = {
        "version": 1,
        "groups": {identity: {"observations": value["observations"], "opening": value["opening"],
                              "figures": [{key: item[key] for key in ("plot", "figure", "files")} for item in value["figures"]]}
                   for identity, value in written.items()},
        "sources": sources,
        "packages": package_entries,
    }
    (target / "figures.json").write_text(json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n")

    # The tour's own figure answers are replaced by the catalogue: figure requests, their reads and
    # the drawings of each calculated result.
    figure_jobs = set(renders)
    package_jobs = set()
    for entry in entries:
        if entry["method"] == "POST" and PACKAGE.match(entry["path"]) and entry["file"]:
            package_jobs.add(read(entry)["job_id"])
    kept = []
    removed = 0
    for entry in entries:
        path = entry["path"]
        found = JOB_FILE.match(path)
        dropped = (
            (entry["method"] == "POST" and (FIGURE_RENDER.match(path) or PACKAGE.match(path)))
            or (entry["method"] == "GET" and FIGURE_RENDER.match(path) and FIGURE_RENDER.match(path).group(1) in figure_jobs)
            or (found is not None and (found.group(1) in figure_jobs or found.group(1) in package_jobs
                                       or (found.group(1) in sources and not sources[found.group(1)].get("seed")
                                           and SHOWN.search(found.group(2)))))
        )
        if dropped:
            removed += 1
        else:
            kept.append(entry)
    journal["entries"] = kept
    (target / "journal.json").write_text(json.dumps(journal, indent=1, ensure_ascii=False) + "\n")
    return {"groups": len(written), "sources": len(sources), "figures": sum(len(value["figures"]) for value in written.values()),
            "packages": len(package_entries), "journal_entries_removed": removed, "files_written": catalog.files_written}
