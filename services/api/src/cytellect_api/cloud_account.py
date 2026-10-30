"""Sign-in to the Cytellect cloud service from the researcher's PC (local mode only).

GPU inference (Cellpose) and analysis proposals are paid services that the
owner grants per e-mail address. The PC signs in with a one-time e-mail code
and receives a device token. That token is the only credential on the PC:

- it is stored beside the other installation settings as
  ``settings/cloud-account.json`` (next to ``settings/cellpose-remote.json``,
  outside the research ``data`` directory), readable only by this OS user, and
  is sent only to the cloud base URL that issued it;
- it never appears in a response, a log line or an error message.

Local analysis never depends on this module. A signed-out, pending or offline
account only disables the two cloud features.
"""
from __future__ import annotations

import functools
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

SCHEMA = "cytellect-cloud-account/1"
ACCOUNT_FILE = "cloud-account.json"
DEFAULT_CLOUD_URL = "https://api.cytellect.app"
RESPONSE_LIMIT = 64 * 1024
REQUEST_TIMEOUT_SECONDS = 15
# The cloud counts the start-up wait as GPU time, so a warm-up gives up after two
# minutes and the researcher decides whether to try again (「もう一度試す」).
WARM_UP_SECONDS = 120
WARM_UP_REUSE_SECONDS = 60
# A sent code is valid for 10 minutes on the service; after that, start again.
CODE_LIFETIME_SECONDS = 600
# The cloud gateway holds a health request up to 25 s while the GPU starts, then
# answers 503 gpu_starting; wait longer than that for one answer.
HEALTH_TIMEOUT_SECONDS = 40
EMAIL = re.compile(r"[^@\s]{1,64}@[^@\s.][^@\s]{0,251}\.[^@\s.]{2,63}")
TOKEN = re.compile(r"[A-Za-z0-9._~+/=-]{20,512}")
REQUEST_TOKEN = re.compile(r"[A-Za-z0-9._~+/=-]{16,512}")
CODE = re.compile(r"[0-9]{6}")
ACCOUNT_STATES = {"code_sent", "pending_approval", "allowed", "revoked", "expired"}


def validated_service_url(url: str, error: str = "cloud_url_invalid") -> str:
    """https only, except a loopback test service; no credentials, query or fragment."""
    parts = urlsplit(url.strip())
    loopback = parts.hostname in {"127.0.0.1", "localhost", "::1"}
    if (parts.scheme not in {"https", "http"} or (parts.scheme == "http" and not loopback) or not parts.hostname
            or parts.username or parts.password or parts.query or parts.fragment):
        raise ValueError(error)
    return url.strip().rstrip("/")


def cloud_base_url() -> str:
    return validated_service_url(os.environ.get("CYTELLECT_CLOUD_URL", "").strip() or DEFAULT_CLOUD_URL)


def normalized_email(value: str) -> str:
    email = value.strip().lower()
    if len(email) > 254 or EMAIL.fullmatch(email) is None:
        raise AccountError(422, "account_email_invalid")
    return email


def device_name() -> str:
    """A generic label for the owner's device list; never the host or user name."""
    system = "Windows" if sys.platform == "win32" else "macOS" if sys.platform == "darwin" else "Linux"
    return f"Cytellect ({system})"


def _service_failure(status: int, body: dict) -> "AccountError":
    """Documented cloud failures as local codes; anything else is a generic failure."""
    error = body.get("error")
    if status == 400 and error == "email_invalid":
        return AccountError(422, "account_email_invalid")
    if error in ("mail_unavailable", "mail_failed"):
        return AccountError(502, "account_mail_failed")
    if status == 503:
        return AccountError(503, "account_cloud_unavailable")
    return AccountError(502, "account_cloud_failed")


class AccountError(Exception):
    def __init__(self, status: int, code: str, **extra: Any):
        super().__init__(code)
        self.status, self.code, self.extra = status, code, extra


class CloudUnreachable(Exception):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect would resend the device token to another URL; refuse it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _LazyOpener:
    """Builds the no-redirect opener at first use.

    Python 3.14 creates an SSL context when the HTTPS handler is built. Doing that
    at import time fails in restricted environments (e.g. a Windows child process
    without its usual variables) that never make a request.
    """

    def open(self, *args, **kwargs):
        return _no_redirect_opener().open(*args, **kwargs)


@functools.cache
def _no_redirect_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_NoRedirect)


_OPENER = _LazyOpener()


def _json(raw: bytes) -> dict:
    if len(raw) > RESPONSE_LIMIT:
        return {}
    try:
        value = json.loads(raw.decode("utf-8")) if raw else {}
    except (ValueError, UnicodeDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def call_cloud(method: str, url: str, *, body: dict | None = None, token: str | None = None,
               timeout: float = REQUEST_TIMEOUT_SECONDS) -> tuple[int, dict]:
    """One request; returns the HTTP status and JSON body. Never logs or retries."""
    headers = {"Accept": "application/json", "User-Agent": "Cytellect/0.1"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            return response.status, _json(response.read(RESPONSE_LIMIT + 1))
    except urllib.error.HTTPError as error:
        try:
            raw = error.read(RESPONSE_LIMIT + 1)
        except OSError:
            raw = b""
        return error.code, _json(raw)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise CloudUnreachable() from None


def account_file(data_dir: Path) -> Path:
    """``settings/cloud-account.json`` beside the data directory (installation settings, not research data)."""
    return Path(data_dir).resolve().parent / "settings" / ACCOUNT_FILE


class AccountStore:
    """``settings/cloud-account.json``, written atomically, user-only."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.path = account_file(self.data_dir)
        self.root = self.path.parent

    def _checked(self) -> Path:
        if self.path.is_symlink() or self.path.resolve().parent != self.root.resolve():
            raise ValueError("cloud_account_path_invalid")
        return self.path

    def load(self) -> dict:
        try:
            path = self._checked()
            if not path.is_file() or path.stat().st_size > 16_384:
                return {}
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # A damaged file means signed out; local analysis is unaffected.
            return {}
        if (not isinstance(value, dict) or value.get("schema") != SCHEMA or value.get("state") not in ACCOUNT_STATES
                or not isinstance(value.get("base_url"), str)):
            return {}
        token = value.get("device_token")
        if token is not None and (not isinstance(token, str) or TOKEN.fullmatch(token) is None):
            return {}
        request = value.get("request_token")
        if request is not None and (not isinstance(request, str) or REQUEST_TOKEN.fullmatch(request) is None):
            return {}
        return value

    def save(self, value: dict) -> None:
        path = self._checked()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = path.with_name(f".{ACCOUNT_FILE}.{os.getpid()}.{threading.get_ident()}.tmp")
        temporary.unlink(missing_ok=True)
        # Created user-only (POSIX 0600). On Windows the per-user data directory's
        # inherited ACL already limits it to this account.
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(json.dumps({"schema": SCHEMA, **value}).encode("utf-8"))
            if os.name != "nt":
                temporary.chmod(0o600)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def clear(self) -> None:
        self._checked().unlink(missing_ok=True)


def _expired(record: dict, now: float) -> bool:
    value = record.get("expires_at")
    try:
        if isinstance(value, int | float):
            limit = float(value)
        elif isinstance(value, str) and value:
            limit = datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        else:
            return False
    except (ValueError, OverflowError):
        return False
    return limit <= now


# What identifies the record a request started from (see CloudAccount._commit).
_IDENTITY = ("state", "email", "base_url", "sent_at", "request_token", "device_token")


def _identity(record: dict) -> tuple:
    return tuple(record.get(key) for key in _IDENTITY)


def _current_view(record: dict) -> dict:
    """What the browser is told when another tab changed the account meanwhile."""
    return {"state": "signed_out"} if not record else {"state": record.get("state", "signed_out"), "email": record.get("email")}


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _allowance(body: dict) -> dict:
    """Only the documented numbers and dates; anything else from the service is dropped."""
    view: dict[str, Any] = {}
    for key, names in (("limits", ("gpu_seconds_month", "proposal_usd_month")), ("usage", ("gpu_seconds", "proposal_usd"))):
        source = body.get(key)
        if isinstance(source, dict):
            view[key] = {name: _number(source.get(name)) for name in names}
    if isinstance(body.get("resets_at"), str) and len(body["resets_at"]) <= 64:
        view["resets_at"] = body["resets_at"]
    return view


class CloudAccount:
    def __init__(self, data_dir: Path, *, base_url: str | None = None,
                 remote_settings: Callable[[], dict[str, str]] | None = None,
                 clock: Callable[[], float] = time.time, sleep: Callable[[float], None] = time.sleep):
        self.data_dir = Path(data_dir)
        self.store = AccountStore(data_dir)
        self._base_url = base_url
        self.remote_settings = remote_settings or (lambda: {})
        self.clock, self.sleep = clock, sleep
        self.lock = threading.Lock()
        self._gpu: dict[str, Any] = {"state": "idle"}
        self._gpu_thread: threading.Thread | None = None
        self._gpu_checked = 0.0

    @property
    def base_url(self) -> str:
        return validated_service_url(self._base_url) if self._base_url else cloud_base_url()

    def _cloud(self, record: dict | None = None) -> str:
        # A token is only ever sent to the service that issued it.
        return validated_service_url(record["base_url"]) if record and record.get("base_url") else self.base_url

    # --- account -----------------------------------------------------------------
    def view(self) -> dict:
        record = self.store.load()
        if not record:
            return {"state": "signed_out"}
        now, email = self.clock(), record.get("email")
        token = record.get("device_token")
        if token:
            if _expired(record, now):
                return self._end(record, "expired")
            try:
                status, body = call_cloud("GET", self._cloud(record) + "/v1/auth/status", token=token)
            except CloudUnreachable:
                return {"state": "offline", "email": email}
            if status == 200 and body.get("state") == "allowed":
                return {"state": "allowed", "email": email, **_allowance(body)}
            if status == 401:
                return self._end(record, "expired")
            if status == 403:
                return self._end(record, "revoked")
            return {"state": "offline", "email": email}
        if record["state"] == "pending_approval":
            pending = {"state": "pending_approval", "email": email, "requested_at": record.get("requested_at")}
            if not record.get("request_token"):
                return pending
            try:
                # The request token (never shown) identifies this PC's request without the address.
                status, body = call_cloud("POST", self._cloud(record) + "/v1/auth/request",
                                          body={"request_token": record["request_token"]})
            except CloudUnreachable:
                return pending
            if status == 200 and body.get("state") == "allowed":
                return {**pending, "approved": True}
            if status == 200 and body.get("state") == "revoked":
                return self._end(record, "revoked")
            if status == 200 and body.get("state") == "none":
                changed = self._commit(record, None)
                return {"state": "signed_out"} if changed is None else _current_view(changed)
            return pending
        if record["state"] == "code_sent":
            sent = _number(record.get("sent_at"))
            if sent is None or now - sent > CODE_LIFETIME_SECONDS:
                # The code has expired on the service; offer the address again.
                changed = self._commit(record, None)
                return {"state": "signed_out", "email": email} if changed is None else _current_view(changed)
            retry = max(0, int(round(float(record.get("retry_at", 0)) - now)))
            view = {"state": "code_sent", "email": email, "retry_after_seconds": retry}
            if isinstance(record.get("attempts_left"), int):
                view["attempts_left"] = record["attempts_left"]
            return view
        return {"state": record["state"], "email": email}

    def _commit(self, started: dict, replacement: dict | None) -> dict | None:
        """Write (or, with None, delete) the account record only if it is still ``started``.

        Every change made after waiting for the cloud service goes through here. Under
        the lock the stored record is read again and compared with the record the
        request started from (`_IDENTITY`: state, address, service, sent code, access
        request and device token). If another tab signed in, out or sent another code
        meanwhile, nothing is written and the current record is returned instead.
        """
        with self.lock:
            current = self.store.load()
            if _identity(current) != _identity(started):
                return current
            if replacement is None:
                self.store.clear()
            else:
                self.store.save(replacement)
        return None

    def _end(self, record: dict, state: str) -> dict:
        """Drop the token on expiry or revocation; keep the address so sign-in can resume."""
        changed = self._commit(record, {"state": state, "email": record.get("email"), "base_url": record["base_url"]})
        return {"state": state, "email": record.get("email")} if changed is None else _current_view(changed)

    def send_code(self, email: str) -> dict:
        email = normalized_email(email)
        record = self.store.load()
        if record.get("device_token"):
            raise AccountError(409, "account_already_signed_in")
        base = self.base_url
        try:
            status, body = call_cloud("POST", base + "/v1/auth/code", body={"email": email})
        except CloudUnreachable:
            raise AccountError(503, "account_cloud_unreachable") from None
        now = self.clock()
        if status == 429:
            retry = _number(body.get("retry_after_seconds"))
            raise AccountError(429, "account_rate_limited", retry_after_seconds=int(retry) if retry is not None else 60)
        state = body.get("state") if status == 200 else None
        if state == "code_sent":
            retry = _number(body.get("retry_after_seconds"))
            wait = int(retry) if retry is not None and 0 <= retry <= 3600 else 60
            changed = self._commit(record, {"state": "code_sent", "email": email, "base_url": base,
                                            "sent_at": now, "retry_at": now + wait})
            return {"state": "code_sent", "email": email, "retry_after_seconds": wait} if changed is None else _current_view(changed)
        if state == "pending_approval":
            requested = record.get("requested_at") if record.get("email") == email else None
            request = body.get("request_token")
            pending: dict[str, Any] = {"state": "pending_approval", "email": email, "base_url": base,
                                       "requested_at": requested or now}
            if isinstance(request, str) and REQUEST_TOKEN.fullmatch(request):
                pending["request_token"] = request
            elif record.get("email") == email and record.get("request_token"):
                pending["request_token"] = record["request_token"]
            changed = self._commit(record, pending)
            return ({"state": "pending_approval", "email": email, "requested_at": requested or now}
                    if changed is None else _current_view(changed))
        if state == "revoked":
            changed = self._commit(record, {"state": "revoked", "email": email, "base_url": base})
            return {"state": "revoked", "email": email} if changed is None else _current_view(changed)
        raise _service_failure(status, body)

    def verify(self, code: str) -> dict:
        record = self.store.load()
        if record.get("state") != "code_sent" or not record.get("email"):
            raise AccountError(409, "account_code_not_requested")
        code = code.strip()
        if CODE.fullmatch(code) is None:
            raise AccountError(422, "account_code_format_invalid")
        base = self._cloud(record)
        try:
            status, body = call_cloud("POST", base + "/v1/auth/verify",
                                      body={"email": record["email"], "code": code, "device_name": device_name()})
        except CloudUnreachable:
            raise AccountError(503, "account_cloud_unreachable") from None
        token = body.get("device_token") if status == 200 else None
        if isinstance(token, str) and TOKEN.fullmatch(token):
            email = str(body["email"] if isinstance(body.get("email"), str) else record["email"])
            expires = body.get("expires_at") if isinstance(body.get("expires_at"), str | int | float) else None
            # Save only onto the code this request checked: a logout or another sign-in
            # meanwhile must not be replaced by this late answer.
            changed = self._commit(record, {"state": "allowed", "email": email.strip().lower(), "base_url": base,
                                            "device_token": token, "expires_at": expires})
            return {"state": "allowed", "email": email.strip().lower()} if changed is None else _current_view(changed)
        error = body.get("error")
        if status == 429:
            # Too many wrong codes or sent codes; the wait can be up to a day.
            retry = _number(body.get("retry_after_seconds"))
            raise AccountError(429, "account_rate_limited", retry_after_seconds=int(retry) if retry is not None else 60)
        if status == 400 and error == "code_invalid":
            left = body.get("attempts_left")
            left = left if isinstance(left, int) and not isinstance(left, bool) and 0 <= left <= 100 else None
            self._record_attempts(record, left)
            raise AccountError(400, "account_code_invalid", attempts_left=left)
        if status == 400 and error == "code_expired":
            raise AccountError(400, "account_code_expired")
        if status == 400 and error == "too_many_attempts":
            # No attempts remain for this code; the view must not offer another.
            self._record_attempts(record, 0)
            raise AccountError(400, "account_code_attempts_exhausted")
        if status == 403 and error == "revoked":
            changed = self._commit(record, {"state": "revoked", "email": record["email"], "base_url": base})
            return {"state": "revoked", "email": record["email"]} if changed is None else _current_view(changed)
        if status == 403 and error == "pending_approval":
            now = self.clock()
            changed = self._commit(record, {"state": "pending_approval", "email": record["email"], "base_url": base,
                                            "requested_at": now})
            return ({"state": "pending_approval", "email": record["email"], "requested_at": now}
                    if changed is None else _current_view(changed))
        raise _service_failure(status, body)

    def _record_attempts(self, record: dict, left: int | None) -> None:
        """Store the remaining attempts only on the same sent code.

        A logout or a new code during the request replaces the record; the late
        answer about the old code must not bring it back.
        """
        self._commit(record, {**{k: v for k, v in record.items() if k != "schema"}, "attempts_left": left})

    def logout(self) -> dict:
        record = self.store.load()
        token = record.get("device_token")
        if token:
            try:
                call_cloud("POST", self._cloud(record) + "/v1/auth/logout", token=token)
            except CloudUnreachable:
                # The token is forgotten here either way; it expires on the service.
                pass
        changed = self._commit(record, None)
        return {"state": "signed_out"} if changed is None else _current_view(changed)

    def credentials(self) -> tuple[str, str] | None:
        """The signed-in device's base URL and token, or None."""
        record = self.store.load()
        token = record.get("device_token")
        if not token or _expired(record, self.clock()):
            return None
        return self._cloud(record), token

    # --- GPU warm-up -------------------------------------------------------------
    def _gpu_target(self) -> tuple[str, dict[str, str]] | None:
        """The same service the worker will use: explicit configuration first, then the account."""
        explicit = {**self.remote_settings(), **{key: value for key, value in os.environ.items()
                                                 if key.startswith("CYTELLECT_CELLPOSE_REMOTE_")}}
        url = explicit.get("CYTELLECT_CELLPOSE_REMOTE_URL", "").strip()
        if url:
            headers = {}
            if explicit.get("CYTELLECT_CELLPOSE_REMOTE_TOKEN"):
                headers["Authorization"] = "Bearer " + explicit["CYTELLECT_CELLPOSE_REMOTE_TOKEN"]
            if explicit.get("CYTELLECT_CELLPOSE_REMOTE_SECRET"):
                headers["X-Cytellect-Secret"] = explicit["CYTELLECT_CELLPOSE_REMOTE_SECRET"]
            return validated_service_url(url, "cellpose_remote_url_invalid") + "/health", headers
        credentials = self.credentials()
        if credentials:
            return credentials[0] + "/v1/cellpose/health", {"Authorization": "Bearer " + credentials[1]}
        return None

    def gpu(self) -> dict:
        with self.lock:
            return dict(self._gpu)

    def start_gpu(self) -> dict:
        """Ask the GPU to start once; a bounded background wait follows 503s."""
        with self.lock:
            running = self._gpu_thread is not None and self._gpu_thread.is_alive()
            recent = self._gpu.get("state") == "ready" and self.clock() - self._gpu_checked < WARM_UP_REUSE_SECONDS
            if running or recent:
                return dict(self._gpu)
            try:
                target = self._gpu_target()
            except ValueError:
                self._gpu = {"state": "failed"}
                return dict(self._gpu)
            if target is None:
                self._gpu = {"state": "unconfigured"}
                return dict(self._gpu)
            self._gpu = {"state": "starting"}
            self._gpu_thread = threading.Thread(target=self._warm, args=target, daemon=True)
            self._gpu_thread.start()
            return dict(self._gpu)

    def _warm(self, url: str, headers: dict[str, str]):
        deadline, delay = self.clock() + WARM_UP_SECONDS, 5.0
        state: dict[str, Any]
        while True:
            request = urllib.request.Request(url, method="GET", headers={"User-Agent": "Cytellect/0.1", **headers})
            try:
                with _OPENER.open(request, timeout=HEALTH_TIMEOUT_SECONDS) as response:
                    response.read(4096)
                state = {"state": "ready"}
                break
            except urllib.error.HTTPError as error:
                try:
                    body = _json(error.read(4096))
                except OSError:
                    body = {}
                if error.code == 429:
                    state = {"state": "quota_exceeded"}
                    if isinstance(body.get("resets_at"), str) and len(body["resets_at"]) <= 64:
                        state["resets_at"] = body["resets_at"]
                    if body.get("scope") in ("user", "global"):
                        state["scope"] = body["scope"]
                    break
                if error.code == 503 and body.get("error") == "gpu_service_disabled":
                    state = {"state": "disabled"}
                    break
                if error.code == 502 and body.get("error") == "gpu_upstream_invalid":
                    state = {"state": "failed"}
                    break
                # Another detection of this user holds the GPU: keep waiting, and say so.
                busy = error.code == 503 and body.get("error") == "gpu_busy"
                with self.lock:
                    self._gpu = {"state": "starting", "busy": True} if busy else {"state": "starting"}
                if error.code == 401:
                    state = {"state": "auth_required"}
                    break
                if error.code == 403:
                    state = {"state": "revoked" if body.get("error") == "revoked" else "rejected"}
                    break
                if error.code not in (502, 503, 504):
                    state = {"state": "failed"}
                    break
            except (urllib.error.URLError, TimeoutError, OSError, ValueError):
                state = {"state": "offline"}
                break
            if self.clock() + delay > deadline:
                state = {"state": "timeout"}
                break
            self.sleep(delay)
            delay = min(delay * 2, 30.0)
        with self.lock:
            self._gpu, self._gpu_checked = state, self.clock()


class EmailInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)


class CodeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=6, max_length=12)


def _failure(error: AccountError) -> JSONResponse:
    return JSONResponse({"detail": error.code, **error.extra}, status_code=error.status,
                        headers={"Cache-Control": "no-store"})


def register_account_routes(app, account: CloudAccount, session: Callable[..., None]):
    """Local-only routes; every response is built from fixed fields, never the token."""
    Session = Depends(session)

    def guarded(work: Callable[[], dict]):
        try:
            return work()
        except AccountError as error:
            return _failure(error)
        except ValueError:
            return _failure(AccountError(503, "account_cloud_misconfigured"))

    @app.get("/v1/account", dependencies=[Session])
    def account_view():
        return guarded(account.view)

    @app.post("/v1/account/code", dependencies=[Session])
    def account_code(body: EmailInput):
        return guarded(lambda: account.send_code(body.email))

    @app.post("/v1/account/verify", dependencies=[Session])
    def account_verify(body: CodeInput):
        return guarded(lambda: account.verify(body.code))

    @app.post("/v1/account/logout", dependencies=[Session])
    def account_logout():
        return guarded(account.logout)

    @app.get("/v1/account/gpu", dependencies=[Session])
    def account_gpu():
        return account.gpu()

    @app.post("/v1/account/gpu", dependencies=[Session])
    def account_gpu_start():
        return account.start_gpu()

