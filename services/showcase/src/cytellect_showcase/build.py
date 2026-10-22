"""Build the public showcase with the real API, worker and detectors (CPython).

Stages (each writes only outside the checkout until ``publish``):

1. ``prepare``  download sources with SHA-256 verification into a cache, apply the
   dataset manifest's pre-registered plane/crop rule and write 2D TIFFs.
2. ``scenario`` run the real API (``create_app``) and the worker's job handlers
   in this process with the detection recorder installed, driving the HTTP
   endpoints with the same requests the workspace UI sends.
3. ``grid``     on a copy of the seeded data directory, run preview runs for a
   small grid of detector settings the UI exposes, recording each detection.
4. ``publish``  export ``seed.zip`` (deterministic), ``recorded-options.json``,
   proposals and the manifest into ``apps/web/public/showcase``.
5. ``snapshot`` serve the seeded copy with uvicorn and record every GET response
   the real web UI makes (``snapshot.mjs``, Playwright/Chromium).

Measurements, statistics and figures come only from the shared API/worker
implementation. No value is computed or edited here.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import io
import itertools
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
PUBLIC = REPO / "apps" / "web" / "public" / "showcase"
HEADERS = {"x-cytellect-request": "1"}
RETENTION_SECONDS = 10 * 365 * 86400
NAMESPACE = uuid.UUID("6f1c2b8e-8d0e-4f43-9a55-0d6c5f6a2f11")
ZIP_DATE = (1980, 1, 1, 0, 0, 0)


def log(*values: object) -> None:
    print(time.strftime("%H:%M:%S"), *values, flush=True)


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def outside_checkout(path: Path) -> Path:
    resolved = path.resolve()
    if resolved == REPO or REPO in resolved.parents:
        raise SystemExit(f"{path} must be outside the checkout")
    return resolved


def stable_uuid(*parts: str) -> str:
    return str(uuid.uuid5(NAMESPACE, "/".join(parts)))


# ---------------------------------------------------------------------------
# 1. Dataset preparation
# ---------------------------------------------------------------------------

def _md5_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "md5").hexdigest()


def download(source: dict, cache: Path) -> Path:
    """Fetch a pinned public file once; every use re-verifies size and digests.

    A source pinned only by the publisher's MD5 (e.g. a Zenodo record) is
    verified against it and gains a SHA-256 in ``source`` for the manifest.
    """
    cache.mkdir(parents=True, exist_ok=True)
    name = ("md5-" + source["md5"]) if source.get("md5") else source["sha256"]
    target = cache / name
    if not target.exists():
        partial = cache / (name + ".partial")
        for attempt in range(4):
            try:
                log("download", source["url"])
                request = urllib.request.Request(source["url"], headers={"User-Agent": "cytellect-showcase-build"})
                with urllib.request.urlopen(request, timeout=300) as response, partial.open("wb") as stream:
                    shutil.copyfileobj(response, stream, 1024 * 1024)
                break
            except OSError:
                if attempt == 3:
                    raise
                time.sleep(10 * (attempt + 1))
        os.replace(partial, target)
    if (("bytes" in source and target.stat().st_size != source["bytes"])
            or ("md5" in source and _md5_file(target) != source["md5"])
            or ("sha256" in source and sha256_file(target) != source["sha256"])):
        target.unlink()
        raise SystemExit(f"source integrity mismatch: {source['url']}")
    source.setdefault("sha256", sha256_file(target))
    source.setdefault("bytes", target.stat().st_size)
    return target


def read_source(path: Path, source: dict):
    """Return (array, axes) for a TIFF, a TIFF/PNG member of a ZIP, or a PNG."""
    import numpy as np
    import tifffile

    data: bytes | None = None
    if source.get("member"):
        with zipfile.ZipFile(path) as archive:
            data = archive.read(source["member"])
            digest = source.get("member_sha256")
            if digest and hashlib.sha256(data).hexdigest() != digest:
                raise SystemExit(f"member integrity mismatch: {source['member']}")
    name = source.get("member") or source.get("filename") or source["url"]
    if name.lower().endswith((".tif", ".tiff")):
        with tifffile.TiffFile(io.BytesIO(data) if data is not None else path) as tif:
            series = tif.series[int(source.get("series", 0))]
            return series.asarray(), series.axes
    from PIL import Image

    with Image.open(io.BytesIO(data) if data is not None else path) as image:
        array = np.asarray(image)
    if array.ndim != 2:
        raise SystemExit(f"unsupported non-grayscale source: {name}")
    return array, "YX"


def select_plane(array, axes: str, selector: dict):
    """Apply a recorded plane rule: {axis: index} or {axis: "max"} per non-YX axis."""
    import numpy as np

    current, names = array, list(axes)
    for axis in [name for name in names if name not in "YX"]:
        rule = selector.get(axis, 0 if current.shape[names.index(axis)] == 1 else None)
        position = names.index(axis)
        if rule is None:
            raise SystemExit(f"plane rule missing axis {axis}")
        current = (current.max(axis=position) if rule == "max" else np.take(current, int(rule), axis=position))
        names.pop(position)
    if names == ["X", "Y"]:
        current = current.T
    if current.ndim != 2 or current.dtype not in (np.uint8, np.uint16):
        raise SystemExit("prepared plane must be 2D uint8/uint16")
    return np.ascontiguousarray(current)


def tile_fields(manifest: dict) -> list[dict]:
    """Expand a pre-registered grid rule into explicit fields (row-major)."""
    fields = list(manifest.get("fields", []))
    for rule in manifest.get("tiles", []):
        height, width = rule["shape"]
        rows, cols = rule["rows"], rule["cols"]
        tile_h, tile_w = height // rows, width // cols
        for row, col in itertools.product(range(rows), range(cols)):
            index = row * cols + col
            metadata = {key: value.format(row=row + 1, col=col + 1, index=index + 1) if isinstance(value, str) else value
                        for key, value in rule.get("metadata", {}).items()}
            for override in rule.get("metadata_by_index", []):
                if index in override["indices"]:
                    metadata.update(override["metadata"])
            fields.append({"id": rule["id"].format(row=row + 1, col=col + 1, index=index + 1),
                           "planes": rule["planes"], "crop": [row * tile_h, col * tile_w, tile_h, tile_w],
                           "metadata": metadata})
    return fields


def centre_crop(shape: tuple[int, int], size: list[int]) -> list[int]:
    height, width = size
    if height > shape[0] or width > shape[1]:
        raise SystemExit("crop larger than source")
    return [(shape[0] - height) // 2, (shape[1] - width) // 2, height, width]


def count_whole_nuclei(image, fiji: str, scratch: Path) -> dict:
    """Default nuclear recipe (1.7.0, nuclear-size/1.0.0, StarDist defaults) on one plane;
    nuclei touching the image border are not counted."""
    import numpy as np
    from cytellect_analysis.engine import detect_nuclei
    from cytellect_analysis.nuclear_scale import automatic_detection_max_side, estimate_nuclear_diameter
    from cytellect_analysis.region_contracts import NuclearDetectorSpec

    detector = NuclearDetectorSpec.model_validate({"engine": "fiji-stardist-2d", "model": "Versatile (fluorescent nuclei)",
                                                   "percentile_low": 1, "percentile_high": 99.8,
                                                   "probability": 0.5, "nms": 0.3})
    scale = estimate_nuclear_diameter(image)
    side = automatic_detection_max_side(image.shape, scale["diameter_px"])
    if scratch.exists():
        shutil.rmtree(scratch)
    labels, _ = detect_nuclei(image, detector, scratch / "engine", fiji, scratch_root=scratch, detection_max_side=side)
    border = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))) - {0}
    ids = set(np.unique(labels)) - {0}
    return {"whole_nuclei": len(ids - border), "border_nuclei": len(ids & border), "detection_max_side_px": side,
            "estimated_diameter_px": scale.get("diameter_px")}


def select_fields(manifest: dict, cache: Path, work: Path, fiji: str) -> dict:
    """Apply the manifest's pre-registered field rule; only the counting channel is read."""
    import numpy as np

    rule = manifest["selection"]
    counting = next(channel for channel in manifest["channels"] if channel["channel_id"] == rule["count_channel"])
    results, fields, sources = [], [], {}
    for cell in rule["cells"]:
        kept = []
        for name in cell["candidates"]:
            source = {"url": rule["url_pattern"].format(name=name), "filename": name, **rule["checksums"][name]}
            path = download(source, cache)
            array, axes = read_source(path, source)
            plane = select_plane(array, axes, counting["select"])
            crop = centre_crop(plane.shape, rule["crop_size"])
            y, x, h, w = crop
            image = np.ascontiguousarray(plane[y:y + h, x:x + w])
            counted = count_whole_nuclei(image, fiji, work / "selection-scratch")
            maximum = int(np.iinfo(image.dtype).max)
            record = {"file": name, **counted, "saturated_pixels": int((image == maximum).sum()),
                      "qualifies": rule["minimum"] <= counted["whole_nuclei"] <= rule["maximum"]}
            results.append({**cell["metadata"], **record})
            log("select", name, record)
            if record["qualifies"]:
                key = Path(name).stem
                sources[key] = source
                kept.append(name)
                fields.append({"id": key, "crop": crop, "metadata": cell["metadata"],
                               "planes": {channel["channel_id"]: {"source": key, "select": channel["select"]}
                                          for channel in manifest["channels"]}})
            if len(kept) == rule["per_cell"]:
                break
        if len(kept) < rule["per_cell"]:
            log("selection shortfall", cell["metadata"], len(kept))
    return {**manifest, "sources": sources, "fields": fields, "selection": {**rule, "results": results}}


def prepare(manifest: dict, cache: Path, destination: Path) -> list[dict]:
    import numpy as np
    import tifffile

    destination.mkdir(parents=True, exist_ok=True)
    loaded: dict[str, Any] = {}
    prepared = []
    for item in tile_fields(manifest):
        files, derivation = {}, {}
        for channel in manifest["channels"]:
            plane = item["planes"][channel["channel_id"]]
            source_id = plane["source"]
            source = manifest["sources"][source_id]
            if source_id not in loaded:
                loaded[source_id] = read_source(download(source, cache), source)
            array, axes = loaded[source_id]
            image = select_plane(array, axes, plane.get("select", {}))
            y, x, h, w = item.get("crop") or [0, 0, image.shape[0], image.shape[1]]
            if y < 0 or x < 0 or y + h > image.shape[0] or x + w > image.shape[1]:
                raise SystemExit(f"crop outside source for {item['id']}")
            crop = np.ascontiguousarray(image[y:y + h, x:x + w])
            path = destination / f"{item['id']}-{channel['channel_id']}.tif"
            tifffile.imwrite(path, crop, photometric="minisblack")
            files[channel["channel_id"]] = path
            derivation[channel["channel_id"]] = {
                "source": source_id, "source_sha256": source["sha256"], "member": source.get("member"),
                "select": plane.get("select", {}), "crop_yxhw": [y, x, h, w], "dtype": crop.dtype.name,
                "shape": list(crop.shape), "tiff_sha256": sha256_file(path),
                "pixel_sha256": hashlib.sha256(crop.tobytes()).hexdigest(),
            }
        prepared.append({"id": item["id"], "files": files, "metadata": item.get("metadata", {}),
                         "derivation": derivation})
    return prepared


# ---------------------------------------------------------------------------
# 2. Real API + in-process worker
# ---------------------------------------------------------------------------

class ApiError(RuntimeError):
    pass


@dataclass
class Api:
    client: Any
    app: Any
    settings: Any
    origin: str

    def _check(self, response, expected=(200, 201, 202)):
        if response.status_code not in expected:
            raise ApiError(f"{response.request.method} {response.request.url.path}: {response.status_code} {response.text[:400]}")
        return response.json()

    def get(self, path: str):
        return self._check(self.client.get(path))

    def post(self, path: str, body: Any = None, **kwargs):
        headers = {**HEADERS, "origin": self.origin}
        if body is None and not kwargs:
            return self._check(self.client.post(path, headers=headers))
        if kwargs:
            return self._check(self.client.post(path, headers=headers, **kwargs))
        return self._check(self.client.post(path, headers=headers, json=body))

    def put(self, path: str, body: Any):
        return self._check(self.client.put(path, headers={**HEADERS, "origin": self.origin}, json=body))


def open_api(data_dir: Path, origin: str, fiji: str, owner: str | None = None) -> Api:
    from cytellect_api.app import create_app
    from cytellect_api.config import Settings
    from fastapi.testclient import TestClient

    settings = Settings(data_dir, app_origin=origin, secure_cookies=False, fiji_executable=fiji,
                        retention_seconds=RETENTION_SECONDS, job_timeout_seconds=7200, worker_memory_mb=12288)
    app = create_app(settings)
    client = TestClient(app, base_url="http://127.0.0.1")
    api = Api(client, app, settings, origin)
    if owner is None:
        token = app.state.store.invite()
        api.post("/v1/invitations/redeem", {"token": token})
    else:
        # Continue as the owner of an existing workspace (a fresh build-time session).
        import secrets

        from cytellect_api.db import digest, sessions

        token = secrets.token_urlsafe(32)
        with app.state.store.transaction() as conn:
            conn.execute(sessions.insert().values(digest=digest(token), owner=owner, expires=time.time() + 86400,
                                                  revoked=False))
        client.cookies.set(settings.cookie_name, token)
    return api


def execute_job(store, settings, job) -> None:
    """The child's handlers, in this process, with the supervisor's lease fencing."""
    from cytellect_api.db import attempts, jobs
    from cytellect_worker.child import ERROR_CODES
    from cytellect_worker.errors import SAFE_ERRORS
    from cytellect_worker.figure_render import run_figure_render, run_publication_package
    from cytellect_worker.main import run_analysis, run_export, run_statistics, run_table_statistics
    from sqlalchemy import update

    attempt = store.safe_path("runs", job["lease"])
    with store.transaction() as conn:
        conn.execute(attempts.insert().values(id=job["lease"], workspace_id=job["workspace_id"],
                                              job_id=job["id"], created=time.time()))
    attempt.mkdir(parents=True, exist_ok=False)
    output = attempt / "output"
    handlers = {
        "figure-render": lambda: run_figure_render(store, job, output),
        "publication-package": lambda: run_publication_package(store, job, output),
        "analysis": lambda: run_analysis(store, settings, job, output),
        "statistics": lambda: run_statistics(store, job, output),
        "export": lambda: run_export(store, job, output),
        "table-statistics": lambda: run_table_statistics(store, job, output),
    }
    stop = threading.Event()

    def heartbeat():
        while not stop.wait(5):
            store.heartbeat(job)

    beat = threading.Thread(target=heartbeat, daemon=True)
    beat.start()
    error = None
    try:
        if job["kind"] not in handlers:
            raise ValueError("job_kind_not_allowlisted")
        handlers[job["kind"]]()
    except Exception as exc:  # noqa: BLE001 - mirror the child's allowlisted status
        message = str(exc)
        error = message if message in ERROR_CODES | SAFE_ERRORS else "analysis_failed"
        log("job failed", job["kind"], error, type(exc).__name__, message[:200])
    finally:
        stop.set()
        beat.join()
    store.heartbeat(job)
    relative = store.relative_path(output) if error is None and output.is_dir() else None
    if error is None and relative is None:
        error = "worker_process_failed"
    if not store.finish(job, relative, error):
        raise RuntimeError("job publication refused")
    with store.transaction() as conn:
        conn.execute(update(jobs).where(jobs.c.id == job["id"], jobs.c.lease == job["lease"]).values(lease_until=0))


def drain(api: Api) -> int:
    from cytellect_api.workspace_runs import advance_workspace_runs

    store, count = api.app.state.store, 0
    while True:
        progressed = advance_workspace_runs(store, api.settings)
        job = store.claim()
        if job is None:
            if not progressed:
                return count
            continue
        started = time.perf_counter()
        execute_job(store, api.settings, job)
        count += 1
        log(f"job {job['kind']} {time.perf_counter() - started:.1f}s")


def wait_job(api: Api, wid: str, job_id: str) -> dict:
    drain(api)
    job = next(item for item in api.get(f"/v1/workspaces/{wid}/jobs") if item["id"] == job_id)
    if job["state"] != "succeeded":
        raise ApiError(f"job {job['kind']} {job['state']} {job.get('error')}")
    return job


# ---------------------------------------------------------------------------
# UI request mirrors (apps/web/src/lib/workspace/*.ts, ConnectedResults.tsx)
# ---------------------------------------------------------------------------

RAW = {"version": "1.1.0", "mode": "raw_intensity"}
AUTOMATIC = {"version": "1.2.0", "mode": "automatic_background"}


def default_settings() -> dict:
    """defaultRuntimeSettings() in use-workspace-runtime.ts."""
    return {"nuclearMaxSide": None, "nuclearProbability": 0.5, "nuclearNms": 0.3,
            "nucleolarDefinition": {"source": "dapi_poor", "marker": "", "pixelUm": None, "relative": 0.7,
                                    "algorithm": None},
            "cellDefinition": {"source": "manual", "channel": ""}, "nucleolarSigma": None,
            "nucleolarRim": None, "nucleolarMinimumArea": None, "nucleolarMaximumArea": None,
            "background": "raw"}


def cellpose_detector() -> dict:
    return {"engine": "cellpose-sam", "protocol_version": "4.0.0", "model": "cpsam_v2",
            "model_sha256": "0f1cc3f7ecdd8a037a57c6c48d9d8921391be4cbce3fa9f13c3e3a2e1253c667",
            "diameter_px": None, "normalization_percentile_low": 1, "normalization_percentile_high": 99,
            "flow_threshold": 0.4, "cellprob_threshold": 0, "minimum_area_px": 15, "maximum_size_fraction": 1,
            "iterations": None, "batch_size": 1, "compute_device": "cpu"}


def ncl_cellpose_detector() -> dict:
    return {**cellpose_detector(), "engine": "cellpose-sam-ncl-parent", "protocol_version": "4.3.0",
            "smoothing_sigma_px": 0.9, "parent_background_percentile": 75, "nuclear_diameter_fraction": 0.25,
            "crop_padding_px": 32, "minimum_contrast_snr": 5, "local_background_radius_px": 8,
            "maximum_nuclear_coverage": 0.5}


def legacy_ncl_detector() -> dict:
    return {"engine": "fiji-nucleolar-compartments", "protocol_version": "1.1.0", "threshold_method": "otsu",
            "threshold": None, "smoothing_sigma_px": 0, "minimum_area_px": 1, "maximum_area_px": None,
            "split_touching": False}


def empty_processing() -> dict:
    return {"version": "1.0.0", "nuclei": None, "nucleoli": None, "signal": None}


def plot(operation: str, kind: str = "distribution") -> dict:
    """plot() in ConnectedResults with the default editor state."""
    return {"width_inches": 183 / 25.4, "height_inches": 100 / 25.4, "font_size": 7, "x_label": "", "y_label": "",
            "group_order": [], "kind": kind, "preset": "custom", "language": "en",
            "axes": {"version": "1.0.0", "x_scale": "linear", "y_scale": "linear", "x_min": None, "x_max": None,
                     "x_tick_step": None},
            "y_tick_step": None, "point_size": 18,
            "style": {"version": "1.0.0", "series_colors": {}, "show_legend": True}}


COMPARTMENT_METRICS = ("log2_nucleoplasm_over_nucleolus", "nucleolar_area_fraction", "nucleolar_count")


def selection_for(region_set: str, metric: str, channel: str | None) -> dict:
    """resultSelection/comparisonSelection without a GFP decision."""
    if metric in COMPARTMENT_METRICS:
        return {"source": "compartment-summary", "version": "1.0.0", "region_set_id": region_set, "metric": metric,
                "channel_id": channel if metric == "log2_nucleoplasm_over_nucleolus" else None}
    neutral = metric.startswith("area_") or metric in ("nucleolar_count", "nucleolar_area_fraction")
    return {"source": "region", "region_set_id": region_set, "metric": metric, "channel_id": None if neutral else channel}


@dataclass
class Workspace:
    api: Api
    wid: str
    fields: list[dict] = field(default_factory=list)  # [{"id", "key", "metadata"}]
    spec: dict = field(default_factory=lambda: {"version": 0, "spec": None})
    assignments_version: int = 0
    processing: dict | None = None
    settings: dict = field(default_factory=default_settings)

    # -- analysis specification -------------------------------------------------
    def current_spec(self, target: str) -> dict:
        processing = ({**self.processing, "cells": self.processing.get("cells")} if self.processing else None)
        measurement = None if self.settings["background"] == "confirmed_roi" else (
            AUTOMATIC if self.settings["background"] == "automatic" else RAW)
        return {**(self.spec["spec"] or {}), "channel_assignment_version": self.assignments_version,
                "target": target, "settings": copy.deepcopy(self.settings),
                "processing": copy.deepcopy(processing), "measurement": measurement}

    def persist(self, target: str, extra: dict | None = None) -> None:
        spec = {**self.current_spec(target), **(extra or {})}
        if self.spec["spec"] is not None and json.dumps(self.spec["spec"], sort_keys=True) == json.dumps(spec, sort_keys=True):
            return
        self.spec = self.api.put(f"/v1/workspaces/{self.wid}/analysis-spec",
                                 {"version": self.spec["version"], "spec": spec})

    # -- runs -------------------------------------------------------------------
    def run(self, target: str, field_ids: list[str] | None = None, purpose: str = "measurement") -> dict:
        self.persist(target)
        ids = field_ids or [item["id"] for item in self.fields]
        body = {"request_id": str(uuid.uuid4()), "spec_version": self.spec["version"], "target": target,
                "field_ids": ids, "purpose": purpose}
        created = self.api.post(f"/v1/workspaces/{self.wid}/runs", body)
        drain(self.api)
        run = self.api.get(f"/v1/workspaces/{self.wid}/runs/{created['id']}")
        if run["state"] != "succeeded":
            errors = sorted({str(step.get("error")) for step in run["steps"] if step.get("error")})
            raise ApiError(f"run {target} {run['state']}: {errors}")
        if purpose == "measurement":
            self.api.post(f"/v1/workspaces/{self.wid}/runs/{created['id']}/accept", {})
        return run

    def selection(self) -> dict:
        return self.api.get(f"/v1/workspaces/{self.wid}/selection")

    def adopted(self, target: str) -> dict[str, str]:
        entries = self.selection()["entries"]
        return {entry["field_id"]: (entry.get("target_revisions") or {}).get(target)
                for entry in entries if entry.get("field_id") and not entry.get("exclusion_reason")
                and (entry.get("target_revisions") or {}).get(target)}

    # -- statistics and figures (ConnectedResults.calculate/render) -------------
    def metadata(self) -> dict[str, dict]:
        empty = {"condition": None, "sample": None, "experimental_unit": None, "pair": None,
                 "acquisition_date": None, "repeat_length": None}
        return {item["id"]: {**empty, **{key: item["metadata"].get(key) for key in empty}} for item in self.fields}

    def calculate(self, operation: str, target: str, metric: str, channel: str | None, unit: str,
                  x_metric: str = "area_px", x_channel: str | None = None, paired: bool = False,
                  pairing: str = "") -> dict:
        api, wid = self.api, self.wid
        adopted = self.adopted(target)
        sources = [(item["id"], adopted[item["id"]]) for item in self.fields if item["id"] in adopted]
        if len(sources) != len(self.fields):
            raise ApiError(f"{target}: {len(self.fields) - len(sources)} fields without adopted result")
        fields = {fid: self.metadata()[fid] for fid, _ in sources}
        conditions = list(dict.fromkeys(value["condition"].strip() for value in fields.values() if value["condition"]))
        contrasts = [[a, b] for index, a in enumerate(conditions) for b in conditions[index + 1:]]
        region_set = target
        channel = None if metric.startswith("area_") else channel
        x_channel = x_channel if x_channel is not None else channel
        display = plot(operation)
        canonical = "ncl_log2_nucleoplasm_over_nucleoli" if metric == "log2_nucleoplasm_over_nucleolus" else metric
        region = "nucleus" if region_set == "nuclei" else "supplied" if region_set == "cell" else region_set
        method = {"kind": "descriptive" if operation == "distribution" else operation,
                  "test": ("paired-t" if paired else "welch-t") if operation == "comparison" else None,
                  "omnibus": "welch-anova" if operation == "comparison" and not paired and len(conditions) >= 3 else None,
                  "association": "pearson" if operation == "association" else None,
                  "x": {"metric": x_metric, "channel": x_channel, "region": region} if operation == "association" else None,
                  "y": {"metric": canonical, "channel": channel, "region": region} if operation == "association" else None}
        draft = {"statistics": {"method": method, "metric": canonical, "channel_id": channel,
                                "design": "paired" if paired else "independent",
                                "unit_definition": unit, "pairing_basis": pairing if paired else "", "conditions": conditions,
                                "comparisons": contrasts, "field_metadata": fields, "x_metric": x_metric,
                                "x_channel_id": x_channel},
                 "figure": {"metric": canonical, "channel_id": channel,
                            "plot": {**display, "kind": "scatter" if operation == "association" else "distribution"}}}
        self.persist(self.spec["spec"]["target"] if self.spec["spec"] else target, draft)
        selection = selection_for(region_set, metric, channel)
        if operation == "distribution":
            request = {"mode": "descriptive", "selection": selection, "group_by": "field",
                       "figure_policy": {"version": "2.0.0", "layout": "field-pages"},
                       "plot": {**display, "kind": "distribution"}}
        elif operation == "comparison":
            request = {"mode": "region-experimental-unit", "version": "2.0.0",
                       "test": "paired-t" if paired else "welch-t",
                       "omnibus": "welch-anova" if len(conditions) >= 3 and not paired else None, "selection": selection,
                       "design": {"kind": "paired" if paired else "independent", "confirmed": True,
                                  "unit_definition": unit, "pairing_basis": pairing if paired else None},
                       "conditions": list(dict.fromkeys(itertools.chain.from_iterable(contrasts))),
                       "comparison_family": {"family_id": "workspace-planned", "kind": "planned", "control": None,
                                             "contrasts": contrasts},
                       "acquisition_review": {"confirmed": True,
                                              "basis": "calibrated-area" if metric == "area_um2" else "same-settings",
                                              "field_batches": {}, "spatial_sampling_confirmed": True},
                       "missingness_confirmed": True, "aggregation": "field-median_sample-mean_unit-mean-v1",
                       "missingness_policy": "available-observations_require-unexcluded-units-v1",
                       "plot": {"histogram_bins": 10, **display, "kind": "distribution"}}
        else:
            request = {"mode": "region-association", "version": "1.0.0",
                       "x_selection": selection_for(region_set, x_metric, x_channel), "y_selection": selection,
                       "design": {"kind": "independent", "confirmed": True, "unit_definition": unit,
                                  "pairing_basis": None},
                       "conditions": conditions,
                       "acquisition_review": {"confirmed": True, "basis": "same-settings", "field_batches": {},
                                              "spatial_sampling_confirmed": True},
                       "missingness_confirmed": True, "method": "pearson", "scope": "per-condition",
                       "pooling_confirmed": False, "aggregation": "field-median_sample-mean_unit-mean-v1",
                       "missingness_policy": "require-matched-unexcluded-units-v1",
                       "plot": {**display, "kind": "scatter"}}
        # adapter.selectRevision for every source (adopt sets the entry's revision_id).
        current = self.selection()
        entries = [{**entry, "revision_id": dict(sources).get(entry.get("field_id"), entry.get("revision_id"))}
                   for entry in current["entries"]]
        if entries != current["entries"]:
            current = api.post(f"/v1/workspaces/{wid}/selection", {"version": current["version"], "entries": entries})
        if len(sources) == 1:
            revision = sources[0][1]
        else:
            active = api.get(f"/v1/workspaces/{wid}")["active_revision"]
            cohort = api.post(f"/v1/workspaces/{wid}/region-cohorts", {
                "expected_active_revision_id": active, "workspace_selection": current,
                "sources": [{"field_id": fid, "revision_id": rid} for fid, rid in sources], "metadata": fields})
            wait_job(api, wid, cohort["job_id"])
            revision = cohort["revision_id"]
        api.post(f"/v1/revisions/{revision}/review", {"accept_invalidated_fields": []})
        path = "descriptive" if operation == "distribution" else "common-statistics"
        accepted = api.post(f"/v1/revisions/{revision}/{path}", request)
        wait_job(api, wid, accepted["job_id"])
        result = api.get(f"/v1/jobs/{accepted['job_id']}/{'result' if operation == 'distribution' else 'common-statistics'}")
        if result["revision_id"] != revision:
            raise ApiError("result revision mismatch")
        return {"job": accepted["job_id"], "revision": revision, "operation": operation, "draft": draft,
                "plot": request["plot"], "result": result}

    def render(self, saved: dict, kind: str) -> dict:
        """ConnectedResults.render for a changed layout (persists the figure kind first)."""
        draft = copy.deepcopy(saved["draft"])
        draft["figure"]["plot"]["kind"] = kind
        self.persist(self.spec["spec"]["target"], draft)
        display = {**plot(saved["operation"]), "kind": kind}
        accepted = self.api.post(f"/v1/jobs/{saved['job']}/figure-render", {
            "request_id": str(uuid.uuid4()), "plot": {**display, "y_min": None, "y_max": None}})
        wait_job(self.api, self.wid, accepted["job_id"])
        output = self.api.get(f"/v1/jobs/{accepted['job_id']}/figure-render")
        if output["source_job_id"] != saved["job"]:
            raise ApiError("figure source mismatch")
        return {"job": accepted["job_id"], "kind": kind, "files": output["figure"].get("source_files", [])}


def channel_specification(channel: dict) -> dict:
    """channelSpecification() for a user-entered stain name."""
    return {"channel_id": channel["channel_id"], "label": channel.get("stain") or channel["channel_id"],
            "stain": channel.get("stain"), "identity_source": "user_entered",
            "acquisition_saturation_value": None, "acquisition_saturation_confirmed": False}


def import_fields(space: Workspace, manifest: dict, prepared: list[dict]) -> None:
    """registerImport + upload + selection mapping (api-adapter.ts)."""
    api, wid = space.api, space.wid
    calibration = manifest.get("calibration")
    for item in prepared:
        entry = stable_uuid(manifest["id"], item["id"])
        selection = space.selection()
        if not any(value["id"] == entry for value in selection["entries"]):
            selection = api.post(f"/v1/workspaces/{wid}/selection", {"version": selection["version"], "entries": [
                *selection["entries"], {"id": entry, "field_id": None, "revision_id": None, "exclusion_reason": None}]})
        spec = {"version": "1.1.0", "client_upload_id": entry,
                "channels": [channel_specification(channel) for channel in manifest["channels"]],
                "input_mode": "native", "metadata": item["metadata"],
                "calibration": {**calibration, "confirmed": True} if calibration else None}
        files = {f"ch{index}": (f"{item['id']}-{channel['channel_id']}.tif", item["files"][channel["channel_id"]].read_bytes(),
                                "image/tiff") for index, channel in enumerate(manifest["channels"])}
        uploaded = api.post(f"/v1/workspaces/{wid}/region-fields", data={"specification": json.dumps(spec)}, files=files)
        selection = space.selection()
        existing = next((value for value in selection["entries"] if value["field_id"] == uploaded["id"] and value["id"] != entry), None)
        entries = ([value for value in selection["entries"] if value["id"] != entry] if existing else
                   [{**value, "field_id": uploaded["id"]} if value["id"] == entry else value for value in selection["entries"]])
        if entries != selection["entries"]:
            api.post(f"/v1/workspaces/{wid}/selection", {"version": selection["version"], "entries": entries})
        space.fields.append({"id": uploaded["id"], "key": item["id"], "metadata": item["metadata"]})
        log("uploaded", item["id"], uploaded["image_info"]["shape"])


# ---------------------------------------------------------------------------
# Scenario
# ---------------------------------------------------------------------------

def scenario(api: Api, manifest: dict, prepared: list[dict]) -> dict:
    plan = manifest["scenario"]
    created = api.post("/v1/workspaces", {"title": manifest.get("workspace_title", "画像解析")})
    space = Workspace(api, created["id"])
    api.get(f"/v1/workspaces/{space.wid}/selection")
    import_fields(space, manifest, prepared)
    assignments = api.put(f"/v1/workspaces/{space.wid}/channel-assignments", {"version": 0, "assignments": [
        {"channel_id": channel["channel_id"], "stain": channel.get("stain"), "role": channel["role"]}
        for channel in manifest["channels"]]})
    space.assignments_version = assignments["version"]
    timings: dict[str, float] = {}

    def timed(name, action):
        started = time.perf_counter()
        value = action()
        timings[name] = round(time.perf_counter() - started, 1)
        log(name, timings[name], "s")
        return value

    timed("nuclei", lambda: space.run("nuclei"))
    marker = plan.get("nucleolar_marker")
    if marker:
        space.settings = {**space.settings, "nucleolarDefinition": {**space.settings["nucleolarDefinition"],
                          "source": "ncl", "marker": marker, "algorithm": "cellpose"},
                          "nucleolarSigma": None, "nucleolarRim": None, "nucleolarMinimumArea": None,
                          "nucleolarMaximumArea": None}
        space.processing = {**empty_processing(), "nucleoli": {"channel": marker, "detector": ncl_cellpose_detector()}}
    timed("nucleoli", lambda: space.run("nucleoli"))
    timed("nucleoplasm", lambda: space.run("nucleoplasm"))
    saved = {}
    for name in ("distribution", "association", "comparison"):
        analysis = plan["statistics"].get(name)
        if not analysis:
            continue
        saved[name] = timed(f"statistics-{name}", lambda analysis=analysis, name=name: space.calculate(
            name, analysis["target"], analysis["metric"], analysis.get("channel"), plan["unit_definition"],
            analysis.get("x_metric", "area_px"), analysis.get("x_channel"), analysis.get("design") == "paired",
            plan.get("pairing_basis", "")))
    renders = []
    if "comparison" in saved:
        for kind in plan.get("comparison_layouts", ["box", "violin", "histogram"]):
            renders.append(timed(f"render-{kind}", lambda kind=kind: space.render(saved["comparison"], kind)))
    drain(api)
    from cytellect_api.db import workspaces

    owner = api.app.state.store.one(workspaces, id=space.wid)["owner"]
    return {"workspace_id": space.wid, "owner": owner, "fields": space.fields, "timings": timings,
            "statistics": {name: {"job": value["job"], "revision": value["revision"]} for name, value in saved.items()},
            "renders": renders, "spec_version": space.spec["version"], "space": space}


# ---------------------------------------------------------------------------
# 3. Detection grid (preview runs on a copy of the seeded data directory)
# ---------------------------------------------------------------------------

def grid(api: Api, manifest: dict, state: dict) -> dict:
    """Preview runs over the recorded parameter grid; returns recorded-options."""
    plan = manifest["scenario"].get("grid", {})
    base: Workspace = state["space"]
    space = Workspace(api, base.wid, base.fields, api.get(f"/v1/workspaces/{base.wid}/analysis-spec"),
                      base.assignments_version, copy.deepcopy(base.processing), copy.deepcopy(base.settings))
    options: dict[str, dict[str, list]] = {}
    timings: dict[str, float] = {}
    default_settings_value = copy.deepcopy(space.settings)
    default_processing = copy.deepcopy(space.processing)

    def preview(name: str, target: str):
        started = time.perf_counter()
        try:
            space.run(target, purpose="preview")
        except ApiError as error:
            log("grid preview failed", name, error)
            raise
        timings[name] = round(time.perf_counter() - started, 1)
        log("grid", name, timings[name], "s")

    nuclei = plan.get("nuclei")
    if nuclei:
        values = {"probability": nuclei["probability"], "nms": nuclei["nms"],
                  "detection_max_side_px": nuclei["detection_max_side_px"]}
        options["fiji-stardist-2d"] = values
        for probability, nms, side in itertools.product(*values.values()):
            space.settings = {**default_settings_value, "nuclearProbability": probability, "nuclearNms": nms,
                              "nuclearMaxSide": side}
            space.processing = copy.deepcopy(default_processing)
            if (probability, nms, side) == (0.5, 0.3, None):
                continue  # recorded by the scenario's measurement run
            preview(f"nuclei p={probability} nms={nms} side={side}", "nuclei")
    space.settings = copy.deepcopy(default_settings_value)
    marker = manifest["scenario"].get("nucleolar_marker")
    for kind, detector_default, algorithm in (("cellpose-sam-ncl-parent", ncl_cellpose_detector(), "cellpose"),
                                              ("fiji-nucleolar-compartments", legacy_ncl_detector(), "legacy")):
        values = plan.get(kind)
        if values is None or not marker:
            continue
        options[kind] = values
        keys = list(values)
        for combination in itertools.product(*values.values()):
            detector = {**detector_default, **dict(zip(keys, combination, strict=True))}
            settings = {**default_settings_value, "nucleolarDefinition": {
                **default_settings_value["nucleolarDefinition"], "source": "ncl", "marker": marker,
                "algorithm": algorithm}, "nucleolarSigma": None, "nucleolarMinimumArea": None,
                "nucleolarMaximumArea": None}
            if kind == "fiji-nucleolar-compartments":
                # selectNucleolarSource(..., "legacy") clears processing.nucleoli; the visible
                # sigma/minimum-area inputs then override the default legacy detector.
                settings.update(nucleolarSigma=detector["smoothing_sigma_px"],
                                nucleolarMinimumArea=detector["minimum_area_px"])
                processing = {**(copy.deepcopy(default_processing) or empty_processing()), "nucleoli": None}
            else:
                if detector == detector_default:
                    continue  # recorded by the scenario's measurement run
                processing = {**empty_processing(), "nucleoli": {"channel": marker, "detector": detector}}
            space.settings = settings
            space.processing = processing
            preview(f"{kind} {dict(zip(keys, combination, strict=True))}", "nucleoli")
    cells = plan.get("cellpose-sam")
    if cells:
        options["cellpose-sam"] = {key: value for key, value in cells.items() if key != "channel"}
        keys = [key for key in cells if key != "channel"]
        for combination in itertools.product(*(cells[key] for key in keys)):
            space.settings = {**default_settings_value, "cellDefinition": {"source": "cellpose", "channel": cells["channel"]}}
            space.processing = {**(copy.deepcopy(default_processing) or empty_processing()),
                                "cells": {"channel": cells["channel"],
                                          "detector": {**cellpose_detector(), **dict(zip(keys, combination, strict=True))}}}
            preview(f"cellpose-sam {dict(zip(keys, combination, strict=True))}", "cell")
    return {"options": options, "timings": timings}


# ---------------------------------------------------------------------------
# 4. Export
# ---------------------------------------------------------------------------

def sqlite_copy(source: Path, target: Path) -> None:
    """Consistent single-file copy without build-time sessions/invitations."""
    target.unlink(missing_ok=True)
    with contextlib.closing(sqlite3.connect(source)) as origin, contextlib.closing(sqlite3.connect(target)) as copy_:
        origin.backup(copy_)
        copy_.execute("DELETE FROM sessions")
        copy_.execute("DELETE FROM invitations")
        copy_.commit()
        copy_.execute("VACUUM")
    with contextlib.closing(sqlite3.connect(target)) as conn:
        conn.execute("PRAGMA journal_mode=DELETE")


def deterministic_zip(target: Path, entries: dict[str, Path | bytes]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".partial")
    with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, date_time=ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            value = entries[name]
            archive.writestr(info, value if isinstance(value, bytes) else value.read_bytes(), compresslevel=9)
    os.replace(partial, target)


ENGINE_FILE_LIMIT = 1024 * 1024


def export_seed(data_dir: Path, recordings: Path, proposals: dict, showcase: dict, target: Path) -> dict:
    staging = data_dir.parent / "seed-db.sqlite"
    sqlite_copy(data_dir / "cytellect.sqlite", staging)
    entries: dict[str, Path | bytes] = {"cytellect.sqlite": staging}
    omitted = []
    for path in sorted(data_dir.rglob("*")):
        relative = path.relative_to(data_dir)
        if not path.is_file() or relative.parts[0] == "tmp" or relative.name.startswith("cytellect.sqlite"):
            continue
        if "engine" in relative.parts and path.stat().st_size > ENGINE_FILE_LIMIT:
            # Detector diagnostics (label/plane copies) that no API route reads.
            omitted.append({"path": relative.as_posix(), "sha256": sha256_file(path), "bytes": path.stat().st_size})
            continue
        entries[relative.as_posix()] = path
    index = json.loads((recordings / "index.json").read_text())
    used = set()
    import numpy as np

    for entry in index["entries"].values():
        # Label arrays are published compressed (.npz) so unpacking the seed stays small.
        for name, relative in list(entry["outputs"].items()):
            if relative.endswith(".npy"):
                packed = relative[:-4] + ".npz"
                if f"recordings/{packed}" not in entries:
                    buffer = io.BytesIO()
                    np.savez_compressed(buffer, array=np.load(recordings / relative, allow_pickle=False))
                    entries[f"recordings/{packed}"] = buffer.getvalue()
                entry["outputs"][name] = packed
        for item in entry["files"]:
            if item.get("omitted") or item["bytes"] > ENGINE_FILE_LIMIT:
                item.pop("file", None)
                item["omitted"] = True
            else:
                used.add(item["file"])
    entries["recordings/index.json"] = (json.dumps(index, sort_keys=True, indent=1) + "\n").encode()
    for relative in sorted(used):
        entries[f"recordings/{relative}"] = recordings / relative
    from cytellect_api.db import Store, fields

    from .seed import plan

    channel_arrays = {}
    for row in Store(data_dir).rows(fields):
        folder = f"workspaces/{row['workspace_id']}/fields/{row['id']}"
        for index, channel in enumerate(row["image_info"]["channels"]):
            channel_arrays[f"{folder}/channel-{channel['channel_id']}.npy"] = f"{folder}/ch{index}.tif"
    regenerate = plan({name: value for name, value in entries.items() if isinstance(value, Path)}, channel_arrays)
    for item in regenerate:
        entries.pop(item["path"])
    showcase = {**showcase, "regenerate": regenerate, "omitted_engine_files": omitted,
                "omitted_engine_file_policy": f"engine-directory files larger than {ENGINE_FILE_LIMIT} bytes "
                                              "(detector diagnostics no route reads) are not published; "
                                              "their SHA-256 is listed here and in recordings/index.json"}
    entries["proposals.json"] = (json.dumps(proposals, sort_keys=True, ensure_ascii=False) + "\n").encode()
    entries["showcase.json"] = (json.dumps(showcase, sort_keys=True, ensure_ascii=False, indent=1) + "\n").encode()
    deterministic_zip(target, entries)
    sizes = {"entries": len(entries), "bytes": target.stat().st_size, "regenerated_on_boot": len(regenerate),
             "regenerated_bytes": sum(item["bytes"] for item in regenerate)}
    staging.unlink()
    return sizes


def runtime_versions(fiji: str) -> dict:
    lock = json.loads((REPO / "engines/fiji/runtime.lock.json").read_text())
    cellpose = json.loads((REPO / "engines/cellpose/runtime.lock.json").read_text())
    installed = Path(fiji) / "cytellect-runtime.json"
    receipt = json.loads(installed.read_text()) if installed.is_file() else {}
    return {
        "fiji": {"distribution": lock["fiji"]["linux-x64"], "plugins": [
            {key: item[key] for key in ("path", "sha256")} for item in lock["plugins"]],
            "model": lock["model"], "installed_lock_sha256": receipt.get("lock_sha256")},
        "cellpose": {"packages": cellpose["packages"], "model": {key: cellpose["model"][key] for key in (
            "id", "revision", "url", "sha256", "size", "license")}, "runner_sha256": cellpose["runner_sha256"],
            "requirements_sha256": cellpose["requirements_sha256"]},
        "python": sys.version.split()[0],
    }


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


# ---------------------------------------------------------------------------
# 5. Snapshot
# ---------------------------------------------------------------------------

def serve(data_dir: Path, origin: str, fiji: str, port: int):
    """Real API under uvicorn plus the in-process worker (records only GETs later)."""
    import uvicorn
    from cytellect_api.app import create_app
    from cytellect_api.config import Settings

    settings = Settings(data_dir, app_origin=origin, secure_cookies=False, fiji_executable=fiji,
                        retention_seconds=RETENTION_SECONDS)
    app = create_app(settings)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="off"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(200):
        if server.started:
            break
        time.sleep(0.05)
    return app, settings, server, thread


def snapshot(seed_data: Path, work: Path, origin_port: int, api_port: int, fiji: str, out: Path,
             fields: list[dict], workspace_id: str) -> dict:
    data = work / "snapshot-data"
    if data.exists():
        shutil.rmtree(data)
    shutil.copytree(seed_data, data, ignore=shutil.ignore_patterns("tmp"))
    origin = f"http://127.0.0.1:{origin_port}"
    api_origin = f"http://127.0.0.1:{api_port}"
    app, settings, server, thread = serve(data, origin, fiji, api_port)
    # A session for the workspace owner, as the showcase runtime creates one.
    import secrets

    from cytellect_api.db import digest, sessions, workspaces

    token = secrets.token_urlsafe(32)
    owner = app.state.store.one(workspaces, id=workspace_id)["owner"]
    with app.state.store.transaction() as conn:
        conn.execute(sessions.insert().values(digest=digest(token), owner=owner, expires=time.time() + 3600,
                                              revoked=False))
    web = REPO / "apps" / "web"
    # `next dev` rewrites these for a custom distDir; restore them afterwards.
    preserved = {name: (web / name).read_bytes() for name in ("next-env.d.ts", "tsconfig.json")}
    env = {**os.environ, "NEXT_PUBLIC_API_ORIGIN": api_origin, "CYTELLECT_NEXT_DIST_DIR": ".next-showcase",
           "NEXT_TELEMETRY_DISABLED": "1", "PORT": str(origin_port)}
    nextjs = subprocess.Popen(["pnpm", "exec", "next", "dev", "--hostname", "127.0.0.1", "--port", str(origin_port)],
                              cwd=web, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              start_new_session=True)
    try:
        for _ in range(240):
            try:
                urllib.request.urlopen(f"{origin}/", timeout=5)
                break
            except OSError:
                time.sleep(1)
        destination = work / "snapshot-out"
        if destination.exists():
            shutil.rmtree(destination)
        config = {"origin": origin, "api": api_origin, "token": token, "cookie": settings.cookie_name,
                  "workspace": workspace_id,
                  "out": str(destination), "chromium": os.environ.get("CYTELLECT_CHROMIUM_EXECUTABLE",
                                                                       "/opt/pw-browsers/chromium"),
                  "web": str(web), "fields": len(fields)}
        script = Path(__file__).with_name("snapshot.mjs")
        result = subprocess.run(["node", str(script)], input=json.dumps(config), text=True, cwd=work,
                                capture_output=True, timeout=1800)
        sys.stdout.write(result.stdout[-4000:])
        if result.returncode:
            sys.stderr.write(result.stderr[-4000:])
            raise SystemExit("snapshot walk failed")
        report = json.loads((destination / "report.json").read_text())
    finally:
        os.killpg(nextjs.pid, 15)
        nextjs.wait(30)
        server.should_exit = True
        thread.join(10)
        for name, content in preserved.items():
            (web / name).write_bytes(content)
        shutil.rmtree(web / ".next-showcase", ignore_errors=True)
    target = out / "snapshot"
    keep = {"index.json", "recorded-options.json", "proposal-examples.json", "dataset.json"}
    if target.exists():
        for path in target.iterdir():
            if path.name not in keep:
                path.unlink()
    target.mkdir(parents=True, exist_ok=True)
    for path in (destination / "files").iterdir():
        shutil.copyfile(path, target / path.name)
    shutil.copyfile(destination / "index.json", target / "index.json")
    return report


# ---------------------------------------------------------------------------
# 6. Visual QA (outside the checkout)
# ---------------------------------------------------------------------------

def overlays(data_dir: Path, qa: Path, fields: list[dict], limit: int | None = None) -> list[Path]:
    """Contours of every adopted/preview label mask over its defining channel."""
    import numpy as np
    from cytellect_api.db import Store, revisions
    from PIL import Image
    from skimage.segmentation import find_boundaries

    store = Store(data_dir)
    qa.mkdir(parents=True, exist_ok=True)
    names = {item["id"]: item["key"] for item in fields}
    written = []
    rows = [row for row in store.rows(revisions) if row["state"] == "succeeded" and row["result_dir"]
            and row["config"].get("analysis_kind") == "region-2d" and not row["config"].get("cohort_sources")]
    for row in rows:
        recipe = row["config"]["recipe"]
        for fid in row["config"]["field_ids"]:
            labels_path = store.safe_path(row["result_dir"], fid, "labels.npy")
            if not labels_path.is_file():
                continue
            labels = np.load(labels_path)
            channel = recipe.get("defining_channel_id")
            plane = np.load(store.safe_path("workspaces", row["workspace_id"], "fields", fid, f"channel-{channel}.npy"))
            low, high = np.percentile(plane, [1, 99.8])
            gray = np.uint8(np.clip((plane.astype(float) - low) / max(high - low, 1), 0, 1) * 255)
            rgb = np.stack([gray] * 3, axis=-1)
            rgb[find_boundaries(labels, mode="inner")] = (255, 200, 0)
            detector = recipe.get("detector", {}) or {}
            tag = "-".join(str(part) for part in (recipe.get("region_set_id"), detector.get("engine", recipe.get("source")),
                                                   detector.get("probability", ""), detector.get("nms", ""),
                                                   recipe.get("detection_max_side_px", ""), row["id"][:6]))
            path = qa / f"{names.get(fid, fid)}-{tag}.png"
            Image.fromarray(rgb).save(path)
            written.append(path)
    return written[:limit] if limit else written


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("manifest", type=Path, help="dataset manifest JSON")
    parser.add_argument("--work", type=Path, required=True, help="scratch directory outside the checkout")
    parser.add_argument("--cache", type=Path, required=True, help="download cache outside the checkout")
    parser.add_argument("--fiji", required=True, help="pinned Fiji installation (scripts/fiji_setup.py)")
    parser.add_argument("--out", type=Path, default=PUBLIC)
    parser.add_argument("--stages", default="prepare,scenario,grid,publish,snapshot,qa")
    parser.add_argument("--web-port", type=int, default=3217)
    parser.add_argument("--api-port", type=int, default=8217)
    args = parser.parse_args(argv)
    work, cache = outside_checkout(args.work), outside_checkout(args.cache)
    for name in ("CYTELLECT_CELLPOSE_PYTHON", "CYTELLECT_CELLPOSE_MODEL_DIR"):
        if not os.environ.get(name):
            raise SystemExit(f"{name} must name the pinned Cellpose runtime")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("schema") != "cytellect-showcase-dataset/1":
        raise SystemExit("unknown dataset manifest schema")
    stages = set(args.stages.split(","))
    work.mkdir(parents=True, exist_ok=True)
    state_path = work / "state.json"
    origin = f"http://127.0.0.1:{args.web_port}"
    from cytellect_showcase.detections import install_recorder, uninstall

    started = time.perf_counter()
    state: dict = json.loads(state_path.read_text()) if state_path.is_file() else {}
    if "select" in stages:
        manifest = select_fields(manifest, cache, work, args.fiji)
        args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        log("selected", [item["id"] for item in manifest["fields"]])
    if "prepare" in stages:
        prepared = prepare(manifest, cache, work / "prepared")
        state["prepared"] = [{**item, "files": {key: str(value) for key, value in item["files"].items()}}
                             for item in prepared]
        state_path.write_text(json.dumps(state, indent=1))
    prepared = [{**item, "files": {key: Path(value) for key, value in item["files"].items()}}
                for item in state.get("prepared", [])]
    seed_data, recordings = work / "data", work / "recordings"
    if "scenario" in stages:
        for path in (seed_data, work / "grid-data"):
            if path.exists():
                shutil.rmtree(path)
        recorder = install_recorder(recordings, reuse=True)
        api = open_api(seed_data, origin, args.fiji)
        result = scenario(api, manifest, prepared)
        uninstall()
        result.pop("space")
        state["scenario"] = {**result, "recorded_calls": recorder.calls}
        state_path.write_text(json.dumps(state, indent=1))
        api.client.close()
    if "grid" in stages:
        grid_data = work / "grid-data"
        if grid_data.exists():
            shutil.rmtree(grid_data)
        shutil.copytree(seed_data, grid_data, ignore=shutil.ignore_patterns("tmp"))
        recorder = install_recorder(recordings, reuse=True)
        api = open_api(grid_data, origin, args.fiji, state["scenario"]["owner"])
        scenario_state = state["scenario"]
        space = Workspace(api, scenario_state["workspace_id"], scenario_state["fields"],
                          api.get(f"/v1/workspaces/{scenario_state['workspace_id']}/analysis-spec"),
                          api.get(f"/v1/workspaces/{scenario_state['workspace_id']}/channel-assignments")["version"])
        saved_spec = space.spec["spec"]
        space.settings = saved_spec["settings"]
        space.processing = saved_spec["processing"]
        result = grid(api, manifest, {"space": space})
        uninstall()
        state["grid"] = {**result, "recorded_calls": recorder.calls}
        state_path.write_text(json.dumps(state, indent=1))
        api.client.close()
    if "publish" in stages:
        publish(args, manifest, state, seed_data, recordings, started)
    if "snapshot" in stages:
        report = snapshot(seed_data, work, args.web_port, args.api_port, args.fiji, args.out,
                          state["scenario"]["fields"], state["scenario"]["workspace_id"])
        state["snapshot"] = report
        state_path.write_text(json.dumps(state, indent=1))
        write_manifest(args, manifest, state)
    if "qa" in stages:
        written = overlays(work / "grid-data" if (work / "grid-data").exists() else seed_data, work / "qa",
                           state["scenario"]["fields"])
        log("qa overlays", len(written), work / "qa")
    log("done", round(time.perf_counter() - started, 1), "s")


def publish(args, manifest: dict, state: dict, seed_data: Path, recordings: Path, started: float) -> None:
    out = args.out
    (out / "snapshot").mkdir(parents=True, exist_ok=True)
    # Python-only nucleolar definitions run in the browser and need no recording; they are
    # listed without adjustable fields (docs/showcase.md: unlisted fields stay fixed).
    options = {**{engine: {} for engine in ("cytellect-nucleolar-v2", "cytellect-ncl-objects")},
               **state.get("grid", {}).get("options", {})}
    (out / "snapshot" / "recorded-options.json").write_text(json.dumps(options, sort_keys=True, indent=1) + "\n")
    proposals: dict = {}
    (out / "snapshot" / "proposal-examples.json").write_text("[]\n")
    dataset = manifest.get("dataset", {})
    note = {"version": 1, "title": dataset.get("name"), "attribution": dataset.get("attribution"),
            "licence": dataset.get("license"), "licenceUrl": dataset.get("license_url"),
            "sourceUrl": dataset.get("source"), "doi": dataset.get("doi"), "citation": dataset.get("citation"),
            "description": dataset.get("scope"), "modifications": dataset.get("modifications"),
            "caveats": dataset.get("caveats", []),
            "fields": [{"field": f"視野 {index + 1}", "source_file": item["id"], **item["metadata"]}
                       for index, item in enumerate(state.get("prepared", []))]}
    (out / "snapshot" / "dataset.json").write_text(json.dumps(note, ensure_ascii=False, indent=1) + "\n")
    scenario_state = state["scenario"]
    showcase = {"version": 1, "workspace_id": scenario_state["workspace_id"], "owner": scenario_state["owner"],
                "dataset": manifest["id"], "retention_seconds": RETENTION_SECONDS}
    state["seed"] = export_seed(seed_data, recordings, proposals, showcase, out / "seed.zip")
    write_manifest(args, manifest, state)


def write_manifest(args, manifest: dict, state: dict) -> None:
    out = args.out
    files = {}
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            files[path.relative_to(out).as_posix()] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
    record = {
        "schema": "cytellect-showcase-manifest/1",
        "dataset": {key: manifest.get("dataset", {}).get(key) for key in (
            "name", "source", "license", "license_url", "attribution", "citation", "scope")},
        "derivation_rule": manifest.get("derivation_rule"),
        "sources": {key: {name: value.get(name) for name in ("url", "sha256", "bytes", "member", "member_sha256")}
                    for key, value in manifest["sources"].items()},
        "fields": [{"id": item["id"], "metadata": item["metadata"], "derivation": item["derivation"]}
                   for item in state.get("prepared", [])],
        "generated_from_commit": git_commit(),
        "runtime": runtime_versions(args.fiji),
        "scenario": {key: state["scenario"].get(key) for key in ("timings", "statistics", "renders")},
        "grid": {"options": state.get("grid", {}).get("options"), "timings": state.get("grid", {}).get("timings")},
        "detections_recorded": len(json.loads((args.work / "recordings" / "index.json").read_text())["entries"])
        if (args.work / "recordings" / "index.json").is_file() else 0,
        "files": files,
        "limitations": "Public example images; numbers illustrate the software and do not establish scientific "
                       "validity for any laboratory's images.",
    }
    (out / "manifest.json").write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n")
    if out.resolve() == PUBLIC.resolve():
        register_public_files(out, manifest)


SENSITIVE = {".tif", ".tiff", ".png", ".jpg", ".jpeg", ".webp", ".pdf", ".zip", ".npy", ".npz", ".sqlite", ".db"}


def register_public_files(out: Path, manifest: dict) -> None:
    """Allowlist entries (source, licence, SHA-256) for scripts/check_public_tree.py."""
    registry = REPO / "fixtures" / "public" / "allowlist.json"
    allowed = json.loads(registry.read_text(encoding="utf-8"))
    prefix = out.resolve().relative_to(REPO).as_posix() + "/"
    allowed = {key: value for key, value in allowed.items() if not key.startswith(prefix)}
    dataset = manifest["dataset"]
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.suffix.lower() in SENSITIVE:
            allowed[prefix + path.relative_to(out).as_posix()] = {
                "sha256": sha256_file(path), "source": dataset["source"], "license": dataset["license"],
                "note": "Cytellect showcase output derived from the public dataset; see apps/web/public/showcase/manifest.json"}
    registry.write_text(json.dumps(allowed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
