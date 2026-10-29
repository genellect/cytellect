"""CI only (packaging/windows/smoke.ps1): exercise the in-app update against a local feed.

Loaded only when the smoke test puts this folder on PYTHONPATH. It is not part of the
setup ZIP or the installer, so a distributed copy always checks GitHub's releases.

CYTELLECT_TEST_RELEASES   URL of a generated release list on 127.0.0.1; its files may be
                          downloaded from the same origin instead of GitHub's hosts.
CYTELLECT_TEST_FAIL_VERSION
                          A launcher of exactly this installed version exits at once, so
                          the relauncher's return to the previous version can be tested.
"""
import json
import os
import sys
import urllib.parse
from pathlib import Path

_source = os.environ.get("CYTELLECT_TEST_RELEASES", "")
_fail = os.environ.get("CYTELLECT_TEST_FAIL_VERSION", "")

if _fail and "cytellect_api.local" in getattr(sys, "orig_argv", []):
    try:
        _release = json.loads((Path(sys.prefix).parent / "local-release.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _release = {}
    if _release.get("version") == _fail:
        os._exit(3)

if _source:
    _parts = urllib.parse.urlsplit(_source)
    if _parts.scheme == "http" and _parts.hostname == "127.0.0.1":
        from cytellect_api import app_update as _update

        _prefix = f"http://{_parts.netloc}/"
        _original = _update.allowed_download

        def _allowed(url: str) -> str:
            return url if url.startswith(_prefix) else _original(url)

        _update.RELEASES_URL = _source
        _update.allowed_download = _allowed
