"""Signed update manifests (update_signature.py): OpenSSH sshsig with the built-in Ed25519 key.

Keys are generated for each run; no private key is stored in the repository.
"""
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from cytellect_api import update_signature
from cytellect_api.update_signature import SignatureInvalid

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0-local.22"
INSTALLER = b"generated installer bytes for the signature test\n"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SIGNER = _load("sshsig_test_signer", ROOT / "packaging/windows/update-test/sshsig_test_signer.py")
KEY, PUBLIC = SIGNER.generate()


def manifest(version=VERSION, body=INSTALLER):
    return update_signature.write_manifest(version, hashlib.sha256(body).hexdigest(), len(body), "b" * 40,
                                           "2026-10-30T00:00:00Z")


def test_a_signed_manifest_names_the_installer():
    data = manifest()
    installer = update_signature.verified_installer(data, SIGNER.sign(KEY, data), VERSION, PUBLIC)
    assert installer == {"name": f"Cytellect-Setup-{VERSION}.exe", "sha256": hashlib.sha256(INSTALLER).hexdigest(),
                         "bytes": len(INSTALLER), "source_commit": "b" * 40}
    assert json.loads(data) == {"schema": "cytellect-update-manifest/1", "version": VERSION, "source_commit": "b" * 40,
                                "issued_at": "2026-10-30T00:00:00Z",
                                "installer": {"name": f"Cytellect-Setup-{VERSION}.exe",
                                              "sha256": hashlib.sha256(INSTALLER).hexdigest(), "bytes": len(INSTALLER)}}


def test_no_built_in_key_means_nothing_is_trusted(monkeypatch):
    monkeypatch.setattr(update_signature, "UPDATE_PUBLIC_KEY", "")
    data = manifest()
    with pytest.raises(SignatureInvalid, match="update_signing_key_missing"):
        update_signature.verified_installer(data, SIGNER.sign(KEY, data), VERSION)
    # The shipped source has no key yet: the in-app update stays off until the owner adds one.
    source = (ROOT / "services/api/src/cytellect_api/update_signature.py").read_text(encoding="utf-8")
    assert 'UPDATE_PUBLIC_KEY = ""' in source or 'UPDATE_PUBLIC_KEY = "ssh-ed25519 ' in source


@pytest.mark.parametrize("line", ["", "ssh-rsa AAAAB3NzaC1yc2E=", "ssh-ed25519 not-base64!",
                                  "ssh-ed25519 " + "QUFBQQ==", "ecdsa-sha2-nistp256 AAAA"])
def test_only_an_ed25519_public_key_line_is_accepted(line):
    with pytest.raises(SignatureInvalid, match="update_signing_key_invalid"):
        update_signature.public_key_blob(line)


def test_signature_details_are_all_checked():
    data = manifest()
    other, other_public = SIGNER.generate()
    cases = {
        "update_signature_invalid": [(data + b" ", SIGNER.sign(KEY, data)),      # changed after signing
                                     (data, SIGNER.sign(KEY, data, algorithm="sha256")),
                                     (data, SIGNER.sign(KEY, data)[:-40] + b"\n-----END SSH SIGNATURE-----\n"),
                                     (data, b"")],
        "update_signature_wrong_key": [(data, SIGNER.sign(other, data))],
        "update_signature_wrong_namespace": [(data, SIGNER.sign(KEY, data, namespace="file"))],
    }
    for code, pairs in cases.items():
        for message, signature in pairs:
            with pytest.raises(SignatureInvalid, match=code):
                update_signature.verify(message, signature, PUBLIC)
    update_signature.verify(data, SIGNER.sign(other, data), other_public)


def test_the_manifest_must_be_for_this_version_and_well_formed():
    for data, code in [(manifest("0.1.0-local.23"), "update_manifest_version_mismatch"),
                       (b"{", "update_manifest_invalid"),
                       (json.dumps({**json.loads(manifest()), "installer": {"name": "x.exe"}}).encode(), "update_manifest_invalid"),
                       (json.dumps({**json.loads(manifest()), "source_commit": "main"}).encode(), "update_manifest_invalid")]:
        with pytest.raises(SignatureInvalid, match=code):
            update_signature.verified_installer(data, SIGNER.sign(KEY, data), VERSION, PUBLIC)


@pytest.mark.skipif(shutil.which("ssh-keygen") is None, reason="OpenSSH ssh-keygen is not installed")
def test_signatures_agree_with_openssh(tmp_path):
    """ssh-keygen -Y sign (the release workflow) is accepted, and the test signer matches it."""
    key = tmp_path / "key"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "cytellect-update", "-f", str(key)], check=True)
    data = tmp_path / update_signature.manifest_name(VERSION)
    data.write_bytes(manifest())
    subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-f", str(key), "-n", "cytellect-update", str(data)], check=True)
    public = (tmp_path / "key.pub").read_text()
    signature = (tmp_path / (data.name + ".sig")).read_bytes()
    update_signature.verify(data.read_bytes(), signature, public)
    with pytest.raises(SignatureInvalid, match="update_signature_wrong_namespace"):
        update_signature.verify(data.read_bytes(), signature, public, namespace="file")
    # And OpenSSH accepts what the test signer writes.
    allowed = tmp_path / "allowed"
    allowed.write_text(f"cytellect {PUBLIC}\n")
    (tmp_path / "test.sig").write_bytes(SIGNER.sign(KEY, data.read_bytes()))
    with data.open("rb") as stream:
        subprocess.run(["ssh-keygen", "-q", "-Y", "verify", "-f", str(allowed), "-I", "cytellect", "-n", "cytellect-update",
                        "-s", str(tmp_path / "test.sig")], stdin=stream, check=True)


def test_release_manifest_tool_writes_and_verifies(tmp_path, monkeypatch):
    tool = _load("update_manifest", ROOT / "scripts/update_manifest.py")
    monkeypatch.setattr(update_signature, "UPDATE_PUBLIC_KEY", PUBLIC)
    (tmp_path / f"Cytellect-Setup-{VERSION}.exe").write_bytes(INSTALLER)
    written = tool.write(tmp_path, VERSION, "c" * 40)
    (tmp_path / (written.name + ".sig")).write_bytes(SIGNER.sign(KEY, written.read_bytes()))
    assert tool.verify(tmp_path, VERSION)["bytes"] == len(INSTALLER)
    assert tool.main(["verify", "--release-dir", str(tmp_path), "--version", VERSION]) == 0
    (tmp_path / f"Cytellect-Setup-{VERSION}.exe").write_bytes(INSTALLER + b"changed")
    assert tool.main(["verify", "--release-dir", str(tmp_path), "--version", VERSION]) == 1
    monkeypatch.setattr(update_signature, "UPDATE_PUBLIC_KEY", "")
    assert tool.main(["verify", "--release-dir", str(tmp_path), "--version", VERSION]) == 1  # no key: no release


def test_test_signer_cli_signs_a_generated_release(tmp_path):
    installer = tmp_path / "setup.exe"
    installer.write_bytes(INSTALLER)
    out = tmp_path / "feed"
    subprocess.run([sys.executable, str(ROOT / "packaging/windows/update-test/sshsig_test_signer.py"), "--installer",
                    str(installer), "--version", VERSION, "--commit", "d" * 40, "--output-dir", str(out)], check=True)
    name = update_signature.manifest_name(VERSION)
    public = (out / "update-test-key.pub").read_text().strip()
    update_signature.verified_installer((out / name).read_bytes(), (out / (name + ".sig")).read_bytes(), VERSION, public)
    assert sorted(path.name for path in out.iterdir()) == [name, name + ".sig", "update-test-key.pub"]


def test_the_ci_hook_supplies_its_key_only_with_the_local_release_list(tmp_path, monkeypatch):
    from cytellect_api import app_update

    monkeypatch.setattr(update_signature, "UPDATE_PUBLIC_KEY", "")
    monkeypatch.setattr(app_update, "RELEASES_URL", app_update.RELEASES_URL)
    monkeypatch.setattr(app_update, "allowed_download", app_update.allowed_download)
    monkeypatch.delenv("CYTELLECT_TEST_FAIL_VERSION", raising=False)
    monkeypatch.setenv("CYTELLECT_TEST_UPDATE_KEY", PUBLIC)
    hook = ROOT / "packaging/windows/update-test/cytellect_ci_update_hook.py"
    monkeypatch.setenv("CYTELLECT_TEST_RELEASES", "https://example.org/releases.json")
    _load("hook_remote", hook)
    assert update_signature.UPDATE_PUBLIC_KEY == ""  # not a local list: the key is ignored
    monkeypatch.setenv("CYTELLECT_TEST_RELEASES", "http://127.0.0.1:8799/releases.json")
    _load("hook_local", hook)
    assert update_signature.UPDATE_PUBLIC_KEY == PUBLIC


def test_a_key_rotation_release_signed_with_the_previous_key_is_accepted_for_drafting(tmp_path, monkeypatch):
    """The release that brings a new key is signed with the old one, which installed copies trust."""
    tool = _load("update_manifest_rotation", ROOT / "scripts/update_manifest.py")
    _, new_public = SIGNER.generate()
    monkeypatch.setattr(update_signature, "UPDATE_PUBLIC_KEY", new_public)  # built into this release
    (tmp_path / f"Cytellect-Setup-{VERSION}.exe").write_bytes(INSTALLER)
    written = tool.write(tmp_path, VERSION, "c" * 40)
    (tmp_path / (written.name + ".sig")).write_bytes(SIGNER.sign(KEY, written.read_bytes()))  # the old key
    previous = tmp_path / "previous_update_signature.py"
    previous.write_text(f'"""older copy"""\nUPDATE_PUBLIC_KEY = "{PUBLIC}"\n', encoding="utf-8")
    assert tool.built_in_key(previous.read_text()) == PUBLIC
    assert tool.built_in_key('UPDATE_PUBLIC_KEY = ""\n') == "" and tool.built_in_key("") == ""
    arguments = ["verify", "--release-dir", str(tmp_path), "--version", VERSION]
    assert tool.main(arguments) == 1  # the new key alone does not accept it
    assert tool.main([*arguments, "--previous-source", str(previous)]) == 0
    # A key that neither copy holds is still refused.
    (tmp_path / (written.name + ".sig")).write_bytes(SIGNER.sign(SIGNER.generate()[0], written.read_bytes()))
    assert tool.main([*arguments, "--previous-source", str(previous)]) == 1
