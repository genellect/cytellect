"""CI only (packaging/windows/smoke.ps1): exercise the in-app update against a local feed.

The smoke test copies this module and a one-line .pth file into the site-packages of one
installed version's virtual environment. Site .pth files load even under the launcher's
-E, unlike PYTHONPATH. Neither file is part of the setup ZIP or the installer, so a
distributed copy always checks GitHub's releases and launches versions unchanged.

CYTELLECT_TEST_RELEASES      URL of a generated release list on 127.0.0.1; its files may be
                             downloaded from the same origin instead of GitHub's hosts.
CYTELLECT_TEST_UPDATE_KEY    With CYTELLECT_TEST_RELEASES only: the public key line of the key
                             that sshsig_test_signer.py made for this run and signed the
                             generated release with. It replaces the built-in key in this
                             process; a distributed copy only ever trusts the owner's key.
CYTELLECT_TEST_FAIL_VERSION  The relauncher starts this version with a command that exits at
                             once, so the return to the previous version can be tested.
"""
import os
import urllib.parse

_source = os.environ.get("CYTELLECT_TEST_RELEASES", "")
_fail = os.environ.get("CYTELLECT_TEST_FAIL_VERSION", "")
_key = os.environ.get("CYTELLECT_TEST_UPDATE_KEY", "")

if _source or _fail:
    from cytellect_api import app_update as _update

    _parts = urllib.parse.urlsplit(_source)
    if _parts.scheme == "http" and _parts.hostname == "127.0.0.1":
        _prefix = f"http://{_parts.netloc}/"
        _original = _update.allowed_download

        def _allowed(url: str) -> str:
            return url if url.startswith(_prefix) else _original(url)

        _update.RELEASES_URL = _source
        if _key:
            from cytellect_api import update_signature as _signature

            _signature.UPDATE_PUBLIC_KEY = _key
        _update.allowed_download = _allowed

    if _fail:
        _launch = _update.Installation.launch

        def _failing_launch(self, *args, **kwargs):
            command = _launch(self, *args, **kwargs)
            return [command[0], "-E", "-c", "raise SystemExit(3)"] if self.version == _fail else command

        _update.Installation.launch = _failing_launch
