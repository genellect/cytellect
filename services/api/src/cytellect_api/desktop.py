"""Single-owner Docker Desktop adapter; never enable on a hosted API.

Docker publishes both ports only on 127.0.0.1. Container peers are bridge IPs,
so the network binding is enforced by Compose, not inferred from request IPs.
Local OS users/processes share this trust boundary, as in the native launcher.
"""
import secrets
import time

from fastapi import HTTPException, Request, Response

from .db import digest, sessions
from .local import _local_owner


def install_owner_session(api, settings, store):
    if settings.app_origin != "http://127.0.0.1:3087" or settings.secure_cookies:
        raise ValueError("desktop_owner_requires_loopback_configuration")
    owner = _local_owner(settings.data_dir)

    @api.post("/v1/desktop/session")
    def connect(request: Request, response: Response):
        # Exact Origin and X-Cytellect-Request are also checked by API middleware.
        if (request.headers.getlist("host") != ["127.0.0.1:8001"]
                or request.headers.get("origin") != settings.app_origin
                or request.headers.get("x-cytellect-request") != "1"
                or request.headers.get("sec-fetch-site") not in ("same-site", "same-origin")
                or any(k.lower().startswith("x-forwarded-") or k.lower() == "forwarded"
                       for k in request.headers)):
            raise HTTPException(403, "desktop_origin_required")
        now = time.time()
        token = request.cookies.get(settings.cookie_name)
        current = store.one(sessions, digest=digest(token)) if token else None
        if not (current and current["owner"] == owner and not current["revoked"]
                and current["expires"] > now):
            token = secrets.token_urlsafe(32)
            with store.transaction() as connection:
                connection.execute(sessions.insert().values(
                    digest=digest(token), owner=owner, expires=now + 7 * 86400, revoked=False,
                ))
            response.set_cookie(settings.cookie_name, token, httponly=True, secure=False,
                                samesite="strict", max_age=7 * 86400, path="/")
        return {"authenticated": True, "retention_hours": settings.retention_seconds / 3600}
