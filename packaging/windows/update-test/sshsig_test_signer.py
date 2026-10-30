"""CI and tests only: sign a generated release with a key made for this run.

The key exists only in memory; the public key is written beside the release so that the
CI update hook (cytellect_ci_update_hook.py) can supply it to the installed version under
test. A distributed copy never contains this file or a test key. The signature has the
format of ``ssh-keygen -Y sign`` (OpenSSH PROTOCOL.sshsig), which the release workflow
uses with the owner's key.

    python sshsig_test_signer.py --installer <exe> --version <v> --commit <sha> --output-dir <dir>
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import sys
import textwrap
from datetime import UTC, datetime
from pathlib import Path


def _string(value: bytes) -> bytes:
    return len(value).to_bytes(4, "big") + value


def generate():
    """A fresh Ed25519 key and its OpenSSH public key line."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    key = Ed25519PrivateKey.generate()
    raw = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    blob = _string(b"ssh-ed25519") + _string(raw)
    return key, "ssh-ed25519 " + base64.b64encode(blob).decode("ascii") + " cytellect-update-test"


def sign(key, message: bytes, namespace: str = "cytellect-update", algorithm: str = "sha512") -> bytes:
    """An armored SSH signature, as ssh-keygen -Y sign writes it."""
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    raw = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    public = _string(b"ssh-ed25519") + _string(raw)
    digest = hashlib.new(algorithm, message).digest()
    signed = b"SSHSIG" + _string(namespace.encode()) + _string(b"") + _string(algorithm.encode()) + _string(digest)
    signature = _string(b"ssh-ed25519") + _string(key.sign(signed))
    blob = (b"SSHSIG" + (1).to_bytes(4, "big") + _string(public) + _string(namespace.encode()) + _string(b"")
            + _string(algorithm.encode()) + _string(signature))
    body = "\n".join(textwrap.wrap(base64.b64encode(blob).decode("ascii"), 70))
    return f"-----BEGIN SSH SIGNATURE-----\n{body}\n-----END SSH SIGNATURE-----\n".encode("ascii")


def main(argv: list[str] | None = None) -> int:
    from cytellect_api import update_signature

    parser = argparse.ArgumentParser()
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    data = args.installer.read_bytes()
    manifest = update_signature.write_manifest(
        args.version, hashlib.sha256(data).hexdigest(), len(data), args.commit,
        datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
    key, public = generate()
    name = update_signature.manifest_name(args.version)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / name).write_bytes(manifest)
    (args.output_dir / (name + ".sig")).write_bytes(sign(key, manifest))
    (args.output_dir / "update-test-key.pub").write_text(public + "\n", encoding="ascii")
    # The installed version must accept exactly this; check it with the application's verifier.
    update_signature.verified_installer(manifest, sign(key, manifest), args.version, public)
    return 0


if __name__ == "__main__":
    sys.exit(main())
