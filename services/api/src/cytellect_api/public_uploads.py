"""Registered-public-images-only uploads for shared development environments (docs/security.md).

When CYTELLECT_UPLOAD_ALLOWLIST names a list of SHA-256 digests, every uploaded
file must match one of them; anything else is removed and refused. Installations
leave it unset, so researchers' own images are accepted as before.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DIGEST = re.compile(r"[0-9a-f]{64}")


def load_allowlist(path: str | Path) -> frozenset[str]:
    """The digests of the registered public files; an empty or malformed list is an error, not "allow all"."""
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    digests = frozenset(entry["sha256"] for entry in document["files"])
    if not digests or any(not DIGEST.fullmatch(value) for value in digests):
        raise ValueError("upload_allowlist_invalid")
    return digests


def require_registered(allowlist: frozenset[str] | None, *digests: str) -> None:
    if allowlist is not None and any(value not in allowlist for value in digests):
        from fastapi import HTTPException

        raise HTTPException(403, "unregistered_upload")
