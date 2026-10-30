"""Signed update manifests: the trust anchor of the in-app update (docs/security.md).

Each release carries ``Cytellect-update-<version>.json`` (the manifest) and its detached
signature ``.sig``, made in the release workflow with the owner's Ed25519 key::

    ssh-keygen -Y sign -f <private key> -n cytellect-update Cytellect-update-<version>.json

The signature is an SSH signature (OpenSSH PROTOCOL.sshsig). Only the public key below is
built into the application; the private key exists only on the owner's PC and in the
``release`` environment's ``UPDATE_SIGNING_KEY`` secret. While the key is empty (no key
has been created yet) the in-app update is unsupported and the workspace asks for the new
installer instead.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from typing import Any

# The owner's public key: the single line of the .pub file that ssh-keygen wrote
# ("ssh-ed25519 AAAA... comment"). Replacing it is a release decision (docs/release-signing.md).
UPDATE_PUBLIC_KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKocg34zCZzyroJ93ELi0k02Hud++1pCaC2zVAjYA1Bs cytellect-update"

NAMESPACE = "cytellect-update"
MANIFEST_SCHEMA = "cytellect-update-manifest/1"
MAX_MANIFEST_BYTES = 64 * 1024
MAX_SIGNATURE_BYTES = 16 * 1024
_ARMOR_BEGIN = "-----BEGIN SSH SIGNATURE-----"
_ARMOR_END = "-----END SSH SIGNATURE-----"
_MAGIC = b"SSHSIG"
_KEY_TYPE = "ssh-ed25519"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}")


class SignatureInvalid(Exception):
    """A fixed reason code: the manifest or its signature cannot be trusted."""


def manifest_name(version: str) -> str:
    return f"Cytellect-update-{version}.json"


def installer_name(version: str) -> str:
    return f"Cytellect-Setup-{version}.exe"


class _Reader:
    """SSH wire format (RFC 4251): uint32 lengths before every string."""

    def __init__(self, data: bytes):
        self.data, self.offset = data, 0

    def raw(self, size: int) -> bytes:
        if size < 0 or self.offset + size > len(self.data):
            raise SignatureInvalid("update_signature_invalid")
        value = self.data[self.offset:self.offset + size]
        self.offset += size
        return value

    def uint32(self) -> int:
        return int.from_bytes(self.raw(4), "big")

    def string(self) -> bytes:
        return self.raw(self.uint32())

    def done(self) -> None:
        if self.offset != len(self.data):
            raise SignatureInvalid("update_signature_invalid")


def _string(value: bytes) -> bytes:
    return len(value).to_bytes(4, "big") + value


def public_key_blob(line: str) -> bytes:
    """The wire blob of an OpenSSH ``ssh-ed25519`` public key line; anything else is refused."""
    parts = line.strip().split()
    if len(parts) < 2 or parts[0] != _KEY_TYPE:
        raise SignatureInvalid("update_signing_key_invalid")
    try:
        blob = base64.b64decode(parts[1], validate=True)
    except (binascii.Error, ValueError):
        raise SignatureInvalid("update_signing_key_invalid") from None
    reader = _Reader(blob)
    try:
        if reader.string() != _KEY_TYPE.encode() or len(reader.string()) != 32:
            raise SignatureInvalid("update_signing_key_invalid")
        reader.done()
    except SignatureInvalid:
        raise SignatureInvalid("update_signing_key_invalid") from None
    return blob


def _signature_blob(armored: bytes) -> bytes:
    try:
        text = armored.decode("ascii")
    except UnicodeDecodeError:
        raise SignatureInvalid("update_signature_invalid") from None
    lines = [line.strip() for line in text.strip().splitlines()]
    if len(lines) < 3 or lines[0] != _ARMOR_BEGIN or lines[-1] != _ARMOR_END:
        raise SignatureInvalid("update_signature_invalid")
    try:
        return base64.b64decode("".join(lines[1:-1]), validate=True)
    except (binascii.Error, ValueError):
        raise SignatureInvalid("update_signature_invalid") from None


def verify(message: bytes, armored: bytes, public_key: str, namespace: str = NAMESPACE) -> None:
    """Check an armored SSH signature of ``message`` by ``public_key`` in ``namespace``.

    PROTOCOL.sshsig: the blob is MAGIC, version 1, the signer's public key, the namespace, a
    reserved string, the hash algorithm and the signature; the signed data is MAGIC, the
    namespace, the reserved string, the hash algorithm and H(message). Only Ed25519 keys and
    SHA-512 are accepted, and the key in the blob must be exactly the built-in key.
    """
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    if len(armored) > MAX_SIGNATURE_BYTES:
        raise SignatureInvalid("update_signature_invalid")
    expected_key = public_key_blob(public_key)
    reader = _Reader(_signature_blob(armored))
    if reader.raw(6) != _MAGIC or reader.uint32() != 1:
        raise SignatureInvalid("update_signature_invalid")
    signer, signed_namespace, reserved, algorithm, signature = (reader.string() for _ in range(5))
    reader.done()
    if signer != expected_key:
        raise SignatureInvalid("update_signature_wrong_key")
    if signed_namespace != namespace.encode():
        raise SignatureInvalid("update_signature_wrong_namespace")
    if algorithm != b"sha512":
        raise SignatureInvalid("update_signature_invalid")
    inner = _Reader(signature)
    if inner.string() != _KEY_TYPE.encode():
        raise SignatureInvalid("update_signature_invalid")
    raw_signature = inner.string()
    inner.done()
    if len(raw_signature) != 64:
        raise SignatureInvalid("update_signature_invalid")
    key = _Reader(expected_key)
    key.string()
    signed = (_MAGIC + _string(namespace.encode()) + _string(reserved) + _string(algorithm)
              + _string(hashlib.sha512(message).digest()))
    try:
        Ed25519PublicKey.from_public_bytes(key.string()).verify(raw_signature, signed)
    except InvalidSignature:
        raise SignatureInvalid("update_signature_invalid") from None


def read_manifest(message: bytes, version: str) -> dict[str, Any]:
    """The signed manifest's installer for exactly this version, or a refusal."""
    try:
        manifest = json.loads(message.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise SignatureInvalid("update_manifest_invalid") from None
    installer = manifest.get("installer") if isinstance(manifest, dict) else None
    if (not isinstance(manifest, dict) or manifest.get("schema") != MANIFEST_SCHEMA
            or not isinstance(installer, dict) or not isinstance(manifest.get("issued_at"), str)
            or not isinstance(manifest.get("source_commit"), str) or not _COMMIT.fullmatch(manifest["source_commit"])):
        raise SignatureInvalid("update_manifest_invalid")
    if manifest.get("version") != version:
        raise SignatureInvalid("update_manifest_version_mismatch")
    size = installer.get("bytes")
    if (installer.get("name") != installer_name(version) or not isinstance(installer.get("sha256"), str)
            or not _SHA256.fullmatch(installer["sha256"]) or not isinstance(size, int) or isinstance(size, bool)
            or size <= 0):
        raise SignatureInvalid("update_manifest_invalid")
    return {"name": installer["name"], "sha256": installer["sha256"], "bytes": size,
            "source_commit": manifest["source_commit"]}


def verified_installer(message: bytes, armored: bytes, version: str, public_key: str | None = None) -> dict[str, Any]:
    """Verify the signature first, then read what the signed manifest says about the installer."""
    key = UPDATE_PUBLIC_KEY if public_key is None else public_key
    if not key.strip():
        raise SignatureInvalid("update_signing_key_missing")
    if len(message) > MAX_MANIFEST_BYTES:
        raise SignatureInvalid("update_manifest_invalid")
    verify(message, armored, key)
    return read_manifest(message, version)


def write_manifest(version: str, installer_sha256: str, installer_bytes: int, source_commit: str,
                   issued_at: str) -> bytes:
    """The manifest the release workflow signs (scripts/update_manifest.py)."""
    manifest = {"schema": MANIFEST_SCHEMA, "version": version,
                "installer": {"name": installer_name(version), "sha256": installer_sha256, "bytes": installer_bytes},
                "source_commit": source_commit, "issued_at": issued_at}
    data = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    read_manifest(data, version)
    return data
