"""The signed update manifest of a Windows release (docs/release-signing.md).

    python scripts/update_manifest.py write --release-dir release --version 0.1.0-local.21 --commit <sha>
    python scripts/update_manifest.py verify --release-dir release --version 0.1.0-local.21

``write`` records the installer's file name, SHA-256 and size with the source commit and the
time of issue in ``Cytellect-update-<version>.json``. The release workflow then signs it with
``ssh-keygen -Y sign -n cytellect-update``. ``verify`` checks that signature with the
application's own verifier and the public key built into this checkout, and that the
installer in the folder is the one the manifest names, so a release can only be drafted
when installed copies will accept it.

A key rotation releases the version that carries the new public key signed with the old key
(docs/release-signing.md). ``--previous-source`` names update_signature.py as it was in the
last published release; a signature by the key built in there is accepted too, because the
installed copies that update to this release trust exactly that key.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api/src"))

from cytellect_api import update_signature  # noqa: E402


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(release_dir: Path, version: str, commit: str) -> Path:
    installer = release_dir / update_signature.installer_name(version)
    manifest = update_signature.write_manifest(version, sha256_file(installer), installer.stat().st_size, commit,
                                               datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
    target = release_dir / update_signature.manifest_name(version)
    target.write_bytes(manifest)
    return target


def built_in_key(source: str) -> str:
    """UPDATE_PUBLIC_KEY as written in a copy of update_signature.py ("" when absent or empty)."""
    match = re.search(r'^UPDATE_PUBLIC_KEY = "([^"\n]*)"$', source, re.MULTILINE)
    return match.group(1) if match else ""


def verify(release_dir: Path, version: str, public_key: str | None = None, previous_key: str = "") -> dict:
    name = update_signature.manifest_name(version)
    manifest = (release_dir / name).read_bytes()
    signature = (release_dir / (name + ".sig")).read_bytes()
    try:
        installer = update_signature.verified_installer(manifest, signature, version, public_key)
    except update_signature.SignatureInvalid as refused:
        # A rotation: signed with the key that the last published release (installed copies) trusts.
        if str(refused) != "update_signature_wrong_key" or not previous_key.strip():
            raise
        installer = update_signature.verified_installer(manifest, signature, version, previous_key)
    path = release_dir / installer["name"]
    if sha256_file(path) != installer["sha256"] or path.stat().st_size != installer["bytes"]:
        raise update_signature.SignatureInvalid("update_installer_hash_mismatch")
    return installer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("write", "verify"):
        sub = commands.add_parser(command)
        sub.add_argument("--release-dir", type=Path, required=True)
        sub.add_argument("--version", required=True)
        if command == "write":
            sub.add_argument("--commit", required=True)
        else:
            sub.add_argument("--previous-source", type=Path,
                             help="update_signature.py of the last published release (key rotation)")
    args = parser.parse_args(argv)
    try:
        if args.command == "write":
            print(write(args.release_dir, args.version, args.commit).name)
        else:
            previous = built_in_key(args.previous_source.read_text(encoding="utf-8")) if args.previous_source else ""
            installer = verify(args.release_dir, args.version, previous_key=previous)
            print(f"verified {update_signature.manifest_name(args.version)} for {installer['name']}")
    except (OSError, update_signature.SignatureInvalid) as error:
        print(f"update manifest refused: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
