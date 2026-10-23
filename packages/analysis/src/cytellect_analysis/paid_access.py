"""This installation's access to the operator's paid features (Cellpose GPU, proposals).

An access code from the operator is redeemed once for a device token. The token is
kept in the installation's settings, protected with Windows DPAPI (readable only by
this Windows user on this PC); elsewhere the file is private to the user. The
operator's GPU and model-provider keys never reach the PC: requests go to the
access service, which counts and relays them.
"""
from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA = "cytellect-paid-access/1"
FILE_ENV = "CYTELLECT_PAID_ACCESS_FILE"
SERVICE_ENV = "CYTELLECT_PAID_ACCESS_URL"
TOKEN = re.compile(r"[A-Za-z0-9_-]{20,200}")
DEVICE_ID = re.compile(r"[0-9a-f]{16}")
MAX_FILE_BYTES = 16_384
_ENTROPY = SCHEMA.encode("ascii")
# The operator's access service for this release (public URL, not a secret). Empty
# until the service is deployed; the setting screen then reports it as unavailable.
SERVICE_URL = ""


@dataclass(frozen=True)
class Credential:
    service: str
    token: str
    device_id: str
    label: str | None = None


def default_service() -> str:
    """The release's access service; an explicit environment value overrides it."""
    configured = os.environ.get(SERVICE_ENV, "").strip()
    if configured:
        return validate_service(configured)
    return validate_service(SERVICE_URL) if SERVICE_URL else ""


def validate_service(url: str) -> str:
    parts = urlsplit(url)
    loopback = parts.hostname in {"127.0.0.1", "localhost", "::1"}
    if (parts.scheme not in {"https", "http"} or (parts.scheme == "http" and not loopback) or not parts.hostname
            or parts.username or parts.password or parts.query or parts.fragment or parts.path not in {"", "/"}):
        raise ValueError("paid_access_service_invalid")
    return url.rstrip("/")


def _blob(data: bytes):
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buffer = ctypes.create_string_buffer(data, len(data))
    return Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer, Blob


def _dpapi(data: bytes, protect: bool) -> bytes:
    import ctypes

    windll = ctypes.windll  # type: ignore[attr-defined]  # Windows only
    crypt32, kernel32 = windll.crypt32, windll.kernel32
    source, _keep, blob = _blob(data)
    entropy, _keep_entropy, _ = _blob(_ENTROPY)
    output = blob()
    call = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    # CRYPTPROTECT_UI_FORBIDDEN: never prompt; fail instead.
    if not call(ctypes.byref(source), None, ctypes.byref(entropy), None, None, 0x1, ctypes.byref(output)):
        raise ValueError("paid_access_unreadable")
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel32.LocalFree(output.pbData)


def _protect(token: str) -> dict:
    if os.name == "nt":
        return {"protection": "dpapi", "value": base64.b64encode(_dpapi(token.encode("ascii"), True)).decode("ascii")}
    return {"protection": "file", "value": token}


def _unprotect(value: dict) -> str:
    if value.get("protection") == "dpapi" and os.name == "nt":
        return _dpapi(base64.b64decode(value["value"], validate=True), False).decode("ascii")
    if value.get("protection") == "file" and os.name != "nt":
        return value["value"]
    raise ValueError("paid_access_unreadable")


def read(path: Path | str | None) -> Credential | None:
    """The stored credential, or None when absent or unusable (never raises for a damaged file)."""
    if not path:
        return None
    path = Path(path)
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_FILE_BYTES:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(value, dict) or value.get("schema") != SCHEMA
                or set(value) - {"schema", "service", "device_id", "label", "token"}
                or not isinstance(value.get("token"), dict) or not DEVICE_ID.fullmatch(str(value.get("device_id")))):
            return None
        token = _unprotect(value["token"])
        label = value.get("label")
        if not TOKEN.fullmatch(token) or (label is not None and not isinstance(label, str)):
            return None
        return Credential(validate_service(value["service"]), token, value["device_id"], label)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        return None


def write(path: Path, credential: Credential) -> None:
    if not TOKEN.fullmatch(credential.token) or not DEVICE_ID.fullmatch(credential.device_id):
        raise ValueError("paid_access_response_invalid")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"schema": SCHEMA, "service": validate_service(credential.service),
                          "device_id": credential.device_id, "label": credential.label,
                          "token": _protect(credential.token)}).encode("utf-8")
    temporary = path.with_name(path.name + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0), 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
    os.replace(temporary, path)


def remove(path: Path) -> None:
    path.unlink(missing_ok=True)
