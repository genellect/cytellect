"""Local launcher routes for redeeming the operator's access code and showing its status.

The researcher pastes a one-use code; the access service returns a device token,
stored by cytellect_analysis.paid_access. Only the code, the token and fixed status
fields cross the network here; no workspace, image or file name is involved.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Annotated

from cytellect_analysis import paid_access
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .proposals import _OPENER

TIMEOUT_SECONDS = 15
MAX_RESPONSE_BYTES = 16 * 1024
CODE = re.compile(r"[A-Za-z0-9_-]{20,200}")


class ActivationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: Annotated[str, Field(min_length=1, max_length=400)]


class FeatureView(BaseModel):
    enabled: bool
    used: int
    limit: int


class PaidAccessView(BaseModel):
    activated: bool
    service_configured: bool
    reachable: bool | None = None
    revoked: bool = False
    label: str | None = None
    month: str | None = None
    cellpose: FeatureView | None = None
    proposals: FeatureView | None = None


def _post(url: str, body: dict, token: str | None = None) -> dict:
    headers = {"content-type": "application/json", "user-agent": "Cytellect/0.1"}
    if token:
        headers["authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST", headers=headers)
    with _OPENER.open(request, timeout=TIMEOUT_SECONDS) as response:
        data = response.read(MAX_RESPONSE_BYTES + 1)
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("paid_access_response_invalid")
    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError("paid_access_response_invalid")
    return value


def _feature(value) -> FeatureView | None:
    try:
        return FeatureView(enabled=bool(value["enabled"]), used=int(value["used"]), limit=int(value["limit"]))
    except (KeyError, TypeError, ValueError):
        return None


def status(path: Path) -> PaidAccessView:
    try:
        configured = bool(paid_access.default_service())
    except ValueError:
        configured = False
    credential = paid_access.read(path)
    if credential is None:
        return PaidAccessView(activated=False, service_configured=configured)
    view = PaidAccessView(activated=True, service_configured=configured, label=credential.label)
    try:
        value = _post(credential.service + "/v1/status", {}, credential.token)
    except urllib.error.HTTPError as error:
        # 401: the operator stopped this PC; a new code is needed.
        return view.model_copy(update={"reachable": True, "revoked": error.code == 401})
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return view.model_copy(update={"reachable": False})
    label = value.get("label")
    return view.model_copy(update={"reachable": True, "month": str(value.get("month") or "") or None,
                                   "label": label if isinstance(label, str) else credential.label,
                                   "cellpose": _feature(value.get("cellpose")),
                                   "proposals": _feature(value.get("proposals"))})


def activate(path: Path, code: str) -> PaidAccessView:
    code = code.strip()
    if not CODE.fullmatch(code):
        raise HTTPException(400, "paid_access_code_invalid")
    try:
        service = paid_access.default_service()
    except ValueError:
        service = ""
    if not service:
        raise HTTPException(503, "paid_access_service_unconfigured")
    try:
        value = _post(service + "/v1/devices", {"invitation": code})
    except urllib.error.HTTPError as error:
        if error.code in (400, 403):
            raise HTTPException(400, "paid_access_code_invalid") from None
        raise HTTPException(503, "paid_access_service_unreachable") from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise HTTPException(503, "paid_access_service_unreachable") from None
    token, device_id = value.get("device_token"), value.get("device_id")
    if not isinstance(token, str) or not isinstance(device_id, str):
        raise HTTPException(502, "paid_access_response_invalid")
    try:
        paid_access.write(path, paid_access.Credential(service, token, device_id))
    except ValueError:
        raise HTTPException(502, "paid_access_response_invalid") from None
    except OSError:
        raise HTTPException(500, "paid_access_not_saved") from None
    return status(path)


def register(app: FastAPI, path: Path) -> None:
    @app.get("/v1/local/paid-access", response_model=PaidAccessView)
    def paid_access_status():
        return status(path)

    @app.post("/v1/local/paid-access", response_model=PaidAccessView)
    def paid_access_activate(body: ActivationRequest):
        return activate(path, body.code)

    @app.delete("/v1/local/paid-access", response_model=PaidAccessView)
    def paid_access_remove():
        # Removes only this PC's copy; the operator's revocation stops the device itself.
        paid_access.remove(path)
        return status(path)
