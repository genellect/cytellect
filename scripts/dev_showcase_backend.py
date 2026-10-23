"""DEVELOPMENT ONLY: serve the public-demo boot/handle contract from a local CPython API.

The public demo (docs/showcase.md) runs the real API inside the browser with Pyodide and
replays recorded detections. Until those artefacts exist, this script lets the web
transport be exercised end to end:

    uv run python scripts/dev_showcase_backend.py seed --out /scratch/showcase-seed
    uv run python scripts/dev_showcase_backend.py serve --seed /scratch/showcase-seed \
        --work /scratch/showcase-work --origin http://127.0.0.1:3000 --record-snapshot --sample-extras
    NEXT_PUBLIC_SHOWCASE_DEV_BACKEND=http://127.0.0.1:8000 pnpm --filter @cytellect/web build

`POST /boot` restores the seed (as `cytellect_showcase.runtime.boot` does), `POST /handle`
forwards one request to the in-process API and then runs queued jobs inline, and
`GET /snapshot/<file>` serves the GET responses recorded before the first change.

Detection here is a deterministic threshold stand-in for StarDist/Cellpose. Its masks
and every number derived from them are NOT scientific results: never publish them,
never ship this script or its output to the browser bundle, and never use it to build
`apps/web/public/showcase/`. All data directories must be outside the checkout.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import re
import shutil
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/public/bbbc013"
ORIGIN = "http://127.0.0.1:3000"
RETENTION = 30 * 86400
CHANNELS = [("dapi", "DRAQ (DNA)", "nuclear"), ("gfp", "FKHR-EGFP", "measure")]
# Dev-only layout: each published well is cropped (pixels unchanged) into three parts so
# that group comparisons can be exercised; the halves are not independent experiments.
# The rows avoid the few 8-bit-saturated pixels so intensity statistics are not refused.
WELLS = [("A01", "control"), ("A06", "treatment"), ("A12", "treatment-high")]
ROWS = slice(160, 430)


def outside_checkout(path: Path) -> Path:
    path = path.resolve()
    if path == ROOT or ROOT in path.parents:
        raise SystemExit("Development data directories must be outside the checkout")
    return path


def settings_for(data_dir: Path, origin: str):
    from cytellect_api.config import Settings

    return Settings(data_dir, app_origin=origin.rstrip("/"), secure_cookies=False, retention_seconds=RETENTION)


# --- Deterministic detection stand-ins (development only) -------------------------------------

def _threshold_labels(image: np.ndarray, factor: float = 1.0, minimum: int = 30) -> np.ndarray:
    from skimage.filters import gaussian, threshold_otsu
    from skimage.measure import label
    from skimage.morphology import remove_small_objects

    smooth = gaussian(image.astype(np.float64), sigma=2, preserve_range=True)
    if float(smooth.max()) == float(smooth.min()):
        return np.zeros(image.shape, np.uint32)
    foreground = smooth > threshold_otsu(smooth) * factor
    foreground = remove_small_objects(foreground, max_size=minimum)
    return label(foreground, connectivity=1).astype(np.uint32)


def install_fake_detection() -> None:
    import cytellect_worker.regions as regions
    from skimage.segmentation import expand_labels

    info = {"engine": "dev-threshold-stand-in", "development_only": True}

    def detect_nuclei(image, parameters, output_dir, executable, scratch_root=None, *, detection_max_side=None):
        probability = float(getattr(parameters, "probability", 0.5) or 0.5)
        return _threshold_labels(image, 0.6 + 0.8 * probability), dict(info)

    def detect_cellpose(image, detector, output_dir, nuclei=None):
        labels = _threshold_labels(image, 0.8)
        return expand_labels(labels, 6).astype(np.uint32), dict(info)

    def detect_positive_regions(image, parameters, output_dir, executable, scratch_root=None):
        return _threshold_labels(image, 1.0, 4), {**info, "status": "ok"}

    regions.detect_nuclei = detect_nuclei
    regions.detect_cellpose = detect_cellpose
    regions.detect_positive_regions = detect_positive_regions


def run_pending(store, settings) -> None:
    """Run queued jobs inline, as the in-browser runtime does after a change."""
    from cytellect_api.workspace_runs import advance_workspace_runs
    from cytellect_worker.child import ERROR_CODES
    from cytellect_worker.errors import SAFE_ERRORS
    from cytellect_worker.figure_render import run_figure_render, run_publication_package
    from cytellect_worker.main import run_analysis, run_export, run_statistics, run_table_statistics

    for _ in range(500):
        advanced = advance_workspace_runs(store, settings)
        job = store.claim()
        if job is None:
            if not advanced:
                return
            continue
        output = store.safe_path("runs", job["lease"]) / "output"
        output.parent.mkdir(parents=True, exist_ok=True)
        handlers = {
            "figure-render": lambda: run_figure_render(store, job, output),
            "publication-package": lambda: run_publication_package(store, job, output),
            "analysis": lambda: run_analysis(store, settings, job, output),
            "statistics": lambda: run_statistics(store, job, output),
            "export": lambda: run_export(store, job, output),
            "table-statistics": lambda: run_table_statistics(store, job, output),
        }
        try:
            if job["kind"] not in handlers:
                raise ValueError("job_kind_not_allowlisted")
            handlers[job["kind"]]()
            store.finish(job, store.relative_path(output))
        except Exception as exc:  # noqa: BLE001 - mirror the child's sanitized error codes
            message = str(exc)
            if message not in ERROR_CODES | SAFE_ERRORS:
                sys.stderr.write(f"job {job['kind']} failed: {type(exc).__name__}: {message[:1200]!r}\n")
            store.finish(job, None, message if message in ERROR_CODES | SAFE_ERRORS else "analysis_failed")


class Api:
    def __init__(self, data_dir: Path, origin: str, cookie: tuple[str, str] | None = None):
        from cytellect_api.app import create_app
        from fastapi.testclient import TestClient

        self.settings = settings_for(data_dir, origin)
        self.app = create_app(self.settings)
        self.store = self.app.state.store
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.headers = {"origin": self.settings.app_origin, "x-cytellect-request": "1"}
        if cookie:
            self.client.cookies.set(*cookie)
        else:
            response = self.client.post("/v1/invitations/redeem", json={"token": self.store.invite(RETENTION)}, headers=self.headers)
            response.raise_for_status()

    def cookie(self) -> tuple[str, str]:
        name = self.settings.cookie_name
        return name, self.client.cookies.get(name)

    def call(self, method: str, url: str, headers=None, content: bytes | None = None, **kwargs):
        merged = {**(headers or {}), "origin": self.settings.app_origin}
        response = self.client.request(method, url, headers=merged, content=content, **kwargs)
        if method.upper() not in ("GET", "HEAD"):
            run_pending(self.store, self.settings)
        return response

    def close(self):
        self.client.close()
        self.store.engine.dispose()


def _json(response, status=(200, 201, 202)):
    if response.status_code not in status:
        raise SystemExit(f"seed request failed: {response.status_code} {response.text[:300]}")
    return response.json()


def seed(out: Path, origin: str) -> None:
    import tifffile

    install_fake_detection()
    out = outside_checkout(out)
    if out.exists():
        shutil.rmtree(out)
    data_dir = out / "data"
    data_dir.mkdir(parents=True)
    api = Api(data_dir, origin)
    try:
        h = {**api.headers, "content-type": "application/json"}
        workspace = _json(api.call("POST", "/v1/workspaces", h, json.dumps({"title": "画像解析"}).encode()))
        wid = workspace["id"]
        selection = _json(api.call("GET", f"/v1/workspaces/{wid}/selection"))
        fields = []
        for well, condition in WELLS:
            planes = {name: tifffile.imread(FIXTURES / f"{well}-{name}.tif") for name, _, _ in CHANNELS}
            width = planes["dapi"].shape[1] // 3
            for half, columns in ((str(part + 1), slice(part * width, (part + 1) * width)) for part in range(3)):
                entry = str(uuid.uuid4())
                selection = _json(api.call("POST", f"/v1/workspaces/{wid}/selection", h, json.dumps({
                    "version": selection["version"], "entries": [*selection["entries"], {"id": entry, "field_id": None, "revision_id": None, "exclusion_reason": None}]}).encode()))
                unit = f"{well}-{half}"
                specification = {"version": "1.1.0", "client_upload_id": entry, "input_mode": "native", "calibration": None,
                                 "metadata": {"condition": condition, "sample": unit, "experimental_unit": unit, "acquisition_date": "dev-batch"},
                                 "channels": [{"channel_id": cid, "label": stain, "stain": stain, "identity_source": "user_entered",
                                               "acquisition_saturation_value": None, "acquisition_saturation_confirmed": False} for cid, stain, _ in CHANNELS]}
                files = {}
                for index, (cid, _, _) in enumerate(CHANNELS):
                    buffer = io.BytesIO()
                    tifffile.imwrite(buffer, np.ascontiguousarray(planes[cid][ROWS, columns]))
                    files[f"ch{index}"] = (f"{unit}-{cid}.tif", buffer.getvalue(), "image/tiff")
                uploaded = api.client.post(f"/v1/workspaces/{wid}/region-fields", headers=api.headers,
                                           data={"specification": json.dumps(specification)}, files=files)
                fid = _json(uploaded)["id"]
                fields.append(fid)
                selection = _json(api.call("POST", f"/v1/workspaces/{wid}/selection", h, json.dumps({
                    "version": selection["version"], "entries": [{**item, "field_id": fid} if item["id"] == entry else item for item in selection["entries"]]}).encode()))
        assignments = _json(api.call("PUT", f"/v1/workspaces/{wid}/channel-assignments", h, json.dumps({
            "version": 0, "assignments": [{"channel_id": cid, "stain": stain, "role": role} for cid, stain, role in CHANNELS]}).encode()))
        spec = {"channel_assignment_version": assignments["version"], "target": "nuclei", "processing": None,
                "measurement": {"version": "1.1.0", "mode": "raw_intensity"}}
        saved = _json(api.call("PUT", f"/v1/workspaces/{wid}/analysis-spec", h, json.dumps({"version": 0, "spec": spec}).encode()))
        run = _json(api.call("POST", f"/v1/workspaces/{wid}/runs", h, json.dumps({
            "request_id": str(uuid.uuid4()), "spec_version": saved["version"], "target": "nuclei", "field_ids": fields, "purpose": "measurement"}).encode()))
        run = _json(api.call("GET", f"/v1/workspaces/{wid}/runs/{run['id']}"))
        if run["state"] != "succeeded":
            raise SystemExit(f"seed detection did not succeed: {run['state']}")
        _json(api.call("POST", f"/v1/workspaces/{wid}/runs/{run['id']}/accept", h, b"{}"))
        (out / "session.json").write_text(json.dumps({"cookie": list(api.cookie()), "workspace": wid}), encoding="utf-8")
    finally:
        api.close()
    print(f"Seeded {len(fields)} development fields (threshold stand-in detection, not scientific results).")


class Backend:
    def __init__(self, seed_dir: Path, work: Path, origin: str, record: bool, sample_extras: bool = False):
        self.seed_dir, self.work, self.origin, self.record = outside_checkout(seed_dir), outside_checkout(work), origin, record
        self.sample_extras = sample_extras
        self.snapshot = self.work / "snapshot"
        self.api: Api | None = None
        self.recording = False

    def boot(self):
        if self.api:
            self.api.close()
        data_dir = self.work / "data"
        if data_dir.exists():
            shutil.rmtree(data_dir)
        shutil.copytree(self.seed_dir / "data", data_dir)
        session = json.loads((self.seed_dir / "session.json").read_text(encoding="utf-8"))
        self.api = Api(data_dir, self.origin, tuple(session["cookie"]))
        # Record the initial reads of the first session only, as the build records them.
        self.recording = self.record and not (self.snapshot / "index.json").exists()
        if self.recording:
            self.snapshot.mkdir(parents=True, exist_ok=True)
            self._index = {"version": 1, "entries": {}}
            if self.sample_extras:
                self.write_sample_extras()

    def write_sample_extras(self):
        """Development stand-ins for the demo build's optional files, to exercise their UI."""
        files = {
            "recorded-options.json": {"fiji-stardist-2d": {"probability": [0.5, 0.6], "nms": [0.3], "detection_max_side_px": [None]},
                                      "cytellect-nucleolar-v2": {"relative_threshold": [0.7]}},
            "proposal-examples.json": [{"label": "核の面積を比較", "instruction": "条件ごとに核の面積を比較したい"}],
            "dataset.json": {"title": "BBBC013v1 (development stand-in)", "attribution": "Images by Ilya Ravkin, Broad Bioimage Benchmark Collection",
                             "licence": "CC BY 3.0", "licenceUrl": "https://creativecommons.org/licenses/by/3.0/",
                             "sourceUrl": "https://bbbc.broadinstitute.org/BBBC013",
                             "caveats": ["Development layout: crops of one field per well are not independent experiments.",
                                         "Threshold stand-in detection; not a scientific result."]},
        }
        for name, value in files.items():
            (self.snapshot / name).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def handle(self, request: dict) -> dict:
        if self.api is None:
            self.boot()
        method, url = request["method"].upper(), request["url"]
        if not url.startswith("/v1/"):
            return {"status": 404, "headers": [["content-type", "application/json"]], "body": base64.b64encode(b'{"detail":"not_found"}').decode()}
        if method == "POST" and re.fullmatch(r"/v1/workspaces/[^/]+/proposal-drafts", url):
            # No model is called: like a demo without recorded proposals for this instruction.
            return {"status": 409, "headers": [["content-type", "application/json"]],
                    "body": base64.b64encode(b'{"detail":"showcase_proposal_not_recorded"}').decode()}
        body = base64.b64decode(request["body"]) if request.get("body") else None
        headers = {name: value for name, value in request.get("headers", []) if name.lower() not in ("origin", "cookie", "host", "content-length")}
        response = self.api.call(method, url, headers, body)
        drop = {"content-length", "transfer-encoding", "set-cookie", "connection"}
        pairs = [[name, value] for name, value in response.headers.items() if name.lower() not in drop]
        if self.recording:
            if method == "GET" and response.status_code == 200:
                key = f"GET {url}"
                name = hashlib.sha256(key.encode()).hexdigest()[:24] + ".bin"
                (self.snapshot / name).write_bytes(response.content)
                self._index["entries"][key] = {"status": 200, "headers": pairs, "file": name}
            elif method != "GET":
                (self.snapshot / "index.json").write_text(json.dumps(self._index, ensure_ascii=False), encoding="utf-8")
                self.recording = False
        return {"status": response.status_code, "headers": pairs, "body": base64.b64encode(response.content).decode()}


def serve(backend: Backend, port: int) -> None:
    install_fake_detection()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: bytes, content_type="application/json"):
            self.send_response(status)
            self.send_header("content-type", content_type)
            self.send_header("access-control-allow-origin", "*")
            self.send_header("cache-control", "no-store")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):  # noqa: N802
            self.send_response(204)
            self.send_header("access-control-allow-origin", "*")
            self.send_header("access-control-allow-methods", "GET, POST")
            self.send_header("access-control-allow-headers", "content-type")
            self.end_headers()

        def do_GET(self):  # noqa: N802
            name = self.path.split("?", 1)[0].removeprefix("/snapshot/")
            path = backend.snapshot / name
            if self.path.startswith("/snapshot/") and "/" not in name and path.is_file():
                self._send(200, path.read_bytes(), "application/json" if name.endswith(".json") else "application/octet-stream")
            else:
                self._send(404, b'{"detail":"not_found"}')

        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("content-length") or 0)
            payload = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/boot":
                backend.boot()
                self._send(200, b'{"booted":true}')
            elif self.path == "/handle":
                started = time.monotonic()
                result = backend.handle(payload)
                sys.stderr.write(f"{payload['method']} {payload['url'].split('?')[0]} -> {result['status']} ({time.monotonic() - started:.2f}s)\n")
                self._send(200, json.dumps(result).encode())
            else:
                self._send(404, b'{"detail":"not_found"}')

        def log_message(self, *args):
            return

    print(f"Development showcase backend on http://127.0.0.1:{port} (not for published results)")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    seeding = sub.add_parser("seed")
    seeding.add_argument("--out", type=Path, required=True)
    seeding.add_argument("--origin", default=ORIGIN)
    serving = sub.add_parser("serve")
    serving.add_argument("--seed", type=Path, required=True)
    serving.add_argument("--work", type=Path, required=True)
    serving.add_argument("--origin", default=ORIGIN)
    serving.add_argument("--port", type=int, default=8000)
    serving.add_argument("--record-snapshot", action="store_true")
    serving.add_argument("--sample-extras", action="store_true", help="also write stand-in recorded-options, proposal examples and dataset notes")
    args = parser.parse_args()
    if args.command == "seed":
        seed(args.out, args.origin)
    else:
        serve(Backend(args.seed, args.work, args.origin, args.record_snapshot, args.sample_extras), args.port)


if __name__ == "__main__":
    main()
