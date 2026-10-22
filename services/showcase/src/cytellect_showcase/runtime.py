"""Browser host for the real Cytellect API, job handlers and analysis package.

``boot`` unpacks a seed (data directory, detection recordings, proposal
recordings) into the in-memory file system and creates the production FastAPI
application on it. ``handle`` passes one HTTP request through that application
over ASGI and returns the response. The private session is created and kept
here; callers never see or send cookies. After a mutating request, queued jobs
and workspace runs are executed in-process by the same handlers the worker
uses, so the next request (normally the UI's job poll) observes the result.

Only detection and the paid proposal service are replaced, both by replaying
recorded outputs. Measurements, statistics, figures and exports are computed
by the shared implementation. Nothing in the production API or worker imports
this module.
"""

from __future__ import annotations

import asyncio
import json
import secrets
import shutil
import time
import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit

from . import _compat

DEFAULT_ROOT = Path("/showcase")
DEFAULT_FONT_DIR = DEFAULT_ROOT / "fonts"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# The seed is created at build time; keep its workspaces alive for any visit.
RETENTION_SECONDS = 10 * 365 * 86400
SEED_DESCRIPTION = "showcase.json"
SESSION_SECONDS = 7 * 86400
MAX_SEED_BYTES = 1024**3
MAX_SEED_MEMBERS = 20000
# Never contacted: request_draft is replaced by the recorded-response replay.
PROPOSAL_URL = "https://proposals.showcase.invalid"
PROPOSAL_TOKEN = "showcase-recorded-replay"
DETECTION_FUNCTIONS = ("detect_nuclei", "detect_cellpose", "detect_compartments", "detect_positive_regions")
DETECTION_NOT_RECORDED = "showcase_detection_not_recorded"
DROPPED_REQUEST_HEADERS = frozenset({"cookie", "origin", "host", "content-length"})
DROPPED_RESPONSE_HEADERS = frozenset({"set-cookie"})


@dataclass
class _Runtime:
    app: Any
    store: Any
    settings: Any
    token: str
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    drain_task: asyncio.Task | None = None
    drain_requested: bool = False
    restore: list = field(default_factory=list)

    def ensure_session(self) -> None:
        """Re-create the private session after logout or expiry."""
        from cytellect_api.db import digest, sessions

        current = self.store.one(sessions, digest=digest(self.token))
        if current and not current["revoked"] and current["expires"] > time.time() + 60:
            return
        self.token = _create_session(self.store, _seed_owner(self.store))

    def schedule_drain(self) -> None:
        self.drain_requested = True
        if self.drain_task is None or self.drain_task.done():
            self.drain_task = asyncio.ensure_future(self._drain_loop())

    async def _drain_loop(self) -> None:
        from ._executor import drain

        while self.drain_requested:
            # Yield first so the mutating request's response reaches the caller.
            await asyncio.sleep(0)
            async with self.lock:
                self.drain_requested = False
                try:
                    drain(self.store, self.settings)
                except Exception:
                    # Never log job contents. Committed state stays consistent;
                    # leases recover any job left running on a later drain.
                    pass

    async def settle(self) -> None:
        while self.drain_task is not None and not self.drain_task.done():
            await asyncio.shield(self.drain_task)

    def close(self) -> None:
        if self.drain_task is not None and not self.drain_task.done():
            self.drain_task.cancel()
        for undo in reversed(self.restore):
            undo()
        self.restore.clear()
        self.store.engine.dispose()


_runtime: _Runtime | None = None


def _is_null(value: Any) -> bool:
    # Pyodide maps JS undefined to None and JS null to pyodide.ffi.jsnull.
    return value is None or type(value).__name__ == "JsNull"


def _as_bytes(value: Any) -> bytes | None:
    """Accept Python bytes or a Pyodide proxy of a JS Uint8Array/ArrayBuffer."""
    if _is_null(value):
        return None
    if hasattr(value, "to_bytes"):
        return value.to_bytes()
    return bytes(value)


def _as_headers(value: Any) -> list[tuple[str, str]]:
    """Accept ``[[name, value], ...]`` from Python or as a Pyodide proxy of a JS array."""
    if _is_null(value):
        return []
    if hasattr(value, "to_py"):
        value = value.to_py()
    return [(str(item[0]), str(item[1])) for item in value]


def _member_path(name: str) -> PurePosixPath | None:
    path = PurePosixPath(name)
    if (not name or "\\" in name or ":" in name or path.is_absolute()
            or any(part in ("", ".", "..") for part in path.parts)):
        raise ValueError("showcase_seed_invalid")
    if path.parts[0] == "tmp":
        return None
    return path


def _extract_seed(seed_zip: bytes, data_dir: Path) -> None:
    with zipfile.ZipFile(BytesIO(seed_zip)) as archive:
        members = archive.infolist()
        if len(members) > MAX_SEED_MEMBERS or sum(m.file_size for m in members) > MAX_SEED_BYTES:
            raise ValueError("showcase_seed_too_large")
        names = {m.filename.rstrip("/") for m in members}
        if "cytellect.sqlite" not in names:
            raise ValueError("showcase_seed_database_missing")
        for member in members:
            relative = _member_path(member.filename.rstrip("/"))
            if relative is None:
                continue
            target = data_dir.joinpath(*relative.parts)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)


def _seed_description(data_dir: Path) -> dict:
    path = data_dir / SEED_DESCRIPTION
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("showcase_seed_invalid")
    return value


def _restore_seed(data_dir: Path) -> None:
    """Regenerate files the seed omits (D's ``seed.restore``), when that module exists."""
    try:
        from . import seed  # type: ignore[attr-defined]
    except ImportError:
        return
    seed.restore(data_dir)


def _seed_owner(store) -> str:
    from cytellect_api.db import uid, workspaces

    recorded = _seed_description(store.root).get("owner")
    if isinstance(recorded, str) and recorded:
        return recorded
    owners = {row["owner"] for row in store.rows(workspaces) if not row["deleted"]}
    if len(owners) > 1:
        raise ValueError("showcase_seed_multiple_owners")
    return next(iter(owners)) if owners else uid()


def _create_session(store, owner: str) -> str:
    """The same session row that invitation redemption creates."""
    from cytellect_api.db import digest, sessions

    token = secrets.token_urlsafe(32)
    with store.transaction() as conn:
        conn.execute(sessions.insert().values(
            digest=digest(token), owner=owner, expires=time.time() + SESSION_SECONDS, revoked=False))
    return token


def _refresh_expiry(store, settings) -> None:
    from cytellect_api.db import workspaces
    from sqlalchemy import update

    with store.transaction() as conn:
        conn.execute(update(workspaces).where(workspaces.c.deleted.is_(False)).values(
            expires=time.time() + settings.retention_seconds))


def _patch(restore: list, target: Any, name: str, value: Any) -> None:
    original = getattr(target, name)
    setattr(target, name, value)
    restore.append(lambda: setattr(target, name, original))


def _detections_unavailable(*_args, **_kwargs):
    raise ValueError(DETECTION_NOT_RECORDED)


def _install_detection_replay(restore: list, recordings: Path) -> None:
    import cytellect_worker.regions as regions

    originals = {name: getattr(regions, name) for name in DETECTION_FUNCTIONS}

    def undo():
        for name, value in originals.items():
            setattr(regions, name, value)

    restore.append(undo)
    if DETECTION_NOT_RECORDED not in regions.REGION_FIELD_ERRORS:
        # Field-level reason the UI shows as a notice, local to this process.
        regions.REGION_FIELD_ERRORS.add(DETECTION_NOT_RECORDED)
        restore.append(lambda: regions.REGION_FIELD_ERRORS.discard(DETECTION_NOT_RECORDED))
    # Real detectors (Fiji/StarDist, Cellpose) never run here: fail closed first.
    for name in DETECTION_FUNCTIONS:
        setattr(regions, name, _detections_unavailable)
    try:
        from . import detections  # type: ignore[attr-defined]
    except ImportError:
        return
    detections.install_replay(recordings)


def _register_fonts(restore: list, font_dir: Path) -> list[str]:
    from matplotlib import font_manager

    files = sorted(p for p in font_dir.glob("*") if p.suffix.lower() in (".ttf", ".otf")) if font_dir.is_dir() else []
    if not files:
        return []
    original = list(font_manager.fontManager.ttflist)

    def undo():
        font_manager.fontManager.ttflist = original
        getattr(font_manager.fontManager, "_findfont_cached").cache_clear()

    restore.append(undo)
    for path in files:
        font_manager.fontManager.addfont(str(path))
    return [path.name for path in files]


async def boot(seed_zip: bytes, origin: str, *, root: str | Path | None = None,
               font_dir: str | Path | None = None) -> None:
    """Unpack the seed and start the API. Calling it again starts over from the seed."""
    global _runtime
    if _runtime is not None:
        shutdown()
    parts = urlsplit(origin)
    if parts.scheme not in ("http", "https") or not parts.netloc or parts.path not in ("", "/"):
        raise ValueError("showcase_origin_invalid")
    origin = f"{parts.scheme}://{parts.netloc}"
    base = Path(root) if root is not None else DEFAULT_ROOT
    data_dir = base / "data"
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True)
    _extract_seed(_as_bytes(seed_zip) or b"", data_dir)
    _restore_seed(data_dir)
    _compat.ensure_psutil_importable()

    from cytellect_api.app import create_app
    from cytellect_api.config import Settings

    from ._proposals import Recordings

    recordings = Recordings.load(data_dir / "proposals.json")
    identity = recordings.identity
    settings = Settings(
        data_dir=data_dir, app_origin=origin, secure_cookies=False, retention_seconds=RETENTION_SECONDS,
        proposal_url=PROPOSAL_URL, proposal_token=PROPOSAL_TOKEN,
        **({"proposal_model": identity[0], "proposal_prompt_version": identity[1]} if identity else {}),
    )
    restore: list = []
    try:
        import cytellect_api.proposals as proposals

        _install_detection_replay(restore, data_dir / "recordings")
        _patch(restore, proposals, "request_draft", recordings.request_draft)
        app = create_app(settings)
        store = app.state.store
        _refresh_expiry(store, settings)
        undo_weights = _compat.numeric_font_weights()
        if undo_weights is not None:
            restore.append(undo_weights)
        _register_fonts(restore,Path(font_dir) if font_dir is not None else DEFAULT_FONT_DIR)
        token = _create_session(store, _seed_owner(store))
    except BaseException:
        for undo in reversed(restore):
            undo()
        raise
    _runtime = _Runtime(app=app, store=store, settings=settings, token=token, restore=restore)
    # A seed should hold no pending work; finish any so nothing stays queued.
    _runtime.schedule_drain()
    await _runtime.settle()


def _require() -> _Runtime:
    if _runtime is None:
        raise RuntimeError("showcase_not_booted")
    return _runtime


async def _call(runtime: _Runtime, method: str, url: str, headers: list[tuple[str, str]],
                body: bytes | None) -> dict:
    parts = urlsplit(url)
    path = parts.path if parts.path.startswith("/") else "/" + parts.path
    origin = urlsplit(runtime.settings.app_origin)
    request_headers = [(name.lower(), value) for name, value in headers
                       if name.lower() not in DROPPED_REQUEST_HEADERS]
    content = body or b""
    request_headers += [("host", origin.netloc), ("origin", runtime.settings.app_origin),
                        ("cookie", f"{runtime.settings.cookie_name}={runtime.token}")]
    if content or method.upper() not in SAFE_METHODS:
        request_headers.append(("content-length", str(len(content))))
    port = origin.port or (443 if origin.scheme == "https" else 80)
    scope = {
        "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"}, "http_version": "1.1",
        "method": method.upper(), "scheme": origin.scheme, "path": unquote(path),
        "raw_path": path.encode("utf-8"), "root_path": "", "query_string": parts.query.encode("latin-1"),
        "headers": [(name.encode("latin-1"), value.encode("latin-1")) for name, value in request_headers],
        "client": ("127.0.0.1", 0), "server": (origin.hostname or "localhost", port), "state": {},
    }
    finished = asyncio.Event()
    delivered = False
    status = 500
    response_headers: list[list[str]] = []
    chunks: list[bytes] = []

    async def receive():
        nonlocal delivered
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": content, "more_body": False}
        await finished.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        nonlocal status, response_headers
        if message["type"] == "http.response.start":
            status = int(message["status"])
            response_headers = [[name.decode("latin-1"), value.decode("latin-1")]
                                for name, value in message.get("headers", [])
                                if name.decode("latin-1").lower() not in DROPPED_RESPONSE_HEADERS]
        elif message["type"] == "http.response.body":
            chunks.append(bytes(message.get("body", b"")))
            if not message.get("more_body", False):
                finished.set()

    try:
        with _compat.inline_threads():
            await runtime.app(scope, receive, send)
    except Exception:
        return {"status": 500, "headers": [["content-type", "application/json"], ["cache-control", "no-store"]],
                "body": b'{"detail":"internal_error"}'}
    finally:
        finished.set()
    return {"status": status, "headers": response_headers, "body": b"".join(chunks)}


def _forget_unrecorded_proposal(runtime: _Runtime, url: str, response: dict) -> None:
    """A replay miss sent nothing and cost nothing; do not demand an explicit retry.

    Production keeps a failed draft so a possibly billed request is never
    silently repeated. Here every failure is a lookup miss, so the failed rows
    are removed and asking again returns the same "not recorded" notice.
    """
    from cytellect_api.db import proposal_drafts
    from sqlalchemy import delete

    from ._proposals import NOT_RECORDED

    parts = urlsplit(url).path.strip("/").split("/")
    if (len(parts) != 4 or parts[:2] != ["v1", "workspaces"] or parts[3] != "proposal-drafts"
            or response["status"] != 409 or NOT_RECORDED.encode() not in response["body"]):
        return
    with runtime.store.transaction() as conn:
        conn.execute(delete(proposal_drafts).where(
            proposal_drafts.c.workspace_id == parts[2], proposal_drafts.c.state == "failed"))


async def handle(method: str, url: str, headers: list[list[str]], body: bytes | None) -> dict:
    """One HTTP request through the API: ``{"status", "headers", "body"}``.

    ``headers`` and ``body`` may also be Pyodide proxies of a JS array and a
    Uint8Array (``undefined``/``null`` for no body).
    """
    runtime = _require()
    verb, target = str(method).upper(), str(url)
    pairs, content = _as_headers(headers), _as_bytes(body)
    async with runtime.lock:
        runtime.ensure_session()
        response = await _call(runtime, verb, target, pairs, content)
        _forget_unrecorded_proposal(runtime, target, response)
    if verb not in SAFE_METHODS:
        runtime.schedule_drain()
    return response


async def settle() -> None:
    """Wait until jobs queued by earlier requests have been executed (tests, harness)."""
    await _require().settle()


def shutdown() -> None:
    """Stop the runtime and undo its process-local replacements."""
    global _runtime
    if _runtime is not None:
        _runtime.close()
        _runtime = None
