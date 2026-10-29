"""Build the per-user Windows installer from an accepted setup ZIP.

The installer bundles the exact release ZIP contents plus every artifact that setup
would otherwise download: the pinned uv, the Python runtime, the hash-locked wheels,
Fiji and its plugins. Each bundled file is listed with its SHA-256 in
``offline/offline-manifest.json``, which is bound to the release manifest, so the
researcher's PC verifies everything and never downloads at installation time.

    python scripts/build_windows_installer.py build --release-zip Z --output-dir O --work-dir W --cache C
    python scripts/build_windows_installer.py install-inno --dest D --cache C
    python scripts/build_windows_installer.py scan PATH [PATH ...]

Signing (owner decision D4) is a hook: ``--sign-command`` is passed to Inno Setup's
SignTool, which signs the installer and its uninstaller. Without it the installer is
unsigned and its receipt records ``"signed": false``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

INNO_VERSION = "6.7.4"
INNO_URL = "https://github.com/jrsoftware/issrc/releases/download/is-6_7_4/innosetup-6.7.4.exe"
INNO_SHA256 = "a549929319f9120716677c685535ca4671e4b937b5fdc87e2585f32d8eb30e8c"
ISS = Path(__file__).resolve().parents[1] / "packaging/windows/cytellect.iss"
# Free space a first installation needs beside the payload (about 2.5 GB installed,
# plus room for the first workspaces), and an update that reuses Fiji and Python.
REQUIRED_INSTALL_MB = 4096
REQUIRED_UPDATE_MB = 1536
MAX_PAYLOAD_BYTES = 1900 * 1024**2  # below the 2 GiB GitHub release-asset limit
OFFLINE_SCHEMA = "cytellect-windows-offline/1"
RECEIPT_SCHEMA = "cytellect-windows-installer/1"
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[a-z0-9.]+)?")
DIGEST = re.compile(r"[0-9a-f]{64}")
WHEEL = re.compile(r"(?P<name>[A-Za-z0-9_.]+)-(?P<version>[A-Za-z0-9_.!+]+)(?:-[0-9][A-Za-z0-9_.]*)?"
                   r"-(?P<python>[A-Za-z0-9_.]+)-(?P<abi>[A-Za-z0-9_.]+)-(?P<platform>[A-Za-z0-9_.]+)\.whl")
UV_URL = re.compile(r"\$script:UvUrl = '(https://github\.com/astral-sh/uv/releases/download/[0-9.]+/"
                    r"uv-x86_64-pc-windows-msvc\.zip)'")
UV_SHA = re.compile(r"\$script:UvSha256 = '([0-9a-f]{64})'")
# Credentials that must never ship or be written by setup: OpenAI keys, Modal deploy
# and proxy tokens, GitHub tokens and private keys. Matches are counted, never printed.
SECRET_PATTERNS = {
    "openai_key": re.compile(r"\bsk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{20,}"),
    "modal_token": re.compile(r"\b(?:ak|as|wk|ws)-[A-Za-z0-9]{16,}\b"),
    "github_token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"),
    "private_key": re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"),
    # The relay's providers: AWS, Resend (mail) and Cloudflare (API tokens, Origin CA keys).
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "resend_key": re.compile(r"\bre_[A-Za-z0-9]{8,}_[A-Za-z0-9]{16,}"),
    "cloudflare_token": re.compile(r"(?i)\b(?:cloudflare|cf)_?(?:api_?)?token\b[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9_-]{40}\b"),
    "cloudflare_origin_ca_key": re.compile(r"\bv1\.0-[0-9a-f]{24}-[0-9a-f]{100,}"),
}
TEXT_SUFFIXES = {".py", ".ps1", ".cmd", ".json", ".js", ".mjs", ".html", ".css", ".txt", ".md", ".toml",
                 ".lock", ".cfg", ".ini", ".xml", ".svg", ".in", ".env", ".yaml", ".yml", ".csv"}
FORBIDDEN_NAMES = {".env", "cellpose-remote.json", "proposal-token", "cytellect.sqlite"}


class BuildError(Exception):
    """Fixed, non-sensitive failure codes."""


@dataclass(frozen=True)
class Artifact:
    role: str
    url: str
    sha256: str
    size: int | None = None


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe_member(name: str) -> bool:
    parts = PurePosixPath(name).parts
    return (bool(name) and "\\" not in name and ":" not in name and not name.startswith("/")
            and all(part not in {"", ".", ".."} for part in name.split("/")) and len(parts) > 0)


def verify_release_zip(archive: Path) -> dict:
    """The installer may only carry an accepted, exactly hash-listed setup ZIP."""
    checksum = archive.with_name(archive.name + ".sha256")
    if not archive.is_file() or archive.is_symlink() or not checksum.is_file():
        raise BuildError("release_zip_missing")
    expected = checksum.read_text(encoding="ascii").split()
    if len(expected) != 2 or expected[1] != archive.name or sha256_file(archive) != expected[0]:
        raise BuildError("release_zip_checksum_mismatch")
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        if len(names) != len(set(names)) or not all(safe_member(name) for name in names):
            raise BuildError("release_zip_paths_unsafe")
        try:
            manifest = json.loads(bundle.read("local-release.json"))
        except (KeyError, ValueError):
            raise BuildError("release_manifest_invalid") from None
        if (manifest.get("schema") != "cytellect-local-release/1" or manifest.get("platform") != "windows-x64"
                or not VERSION.fullmatch(str(manifest.get("version", "")))
                or not re.fullmatch(r"[0-9a-f]{40}", str(manifest.get("source_commit", "")))):
            raise BuildError("release_manifest_invalid")
        listed = {entry["path"]: entry for entry in manifest["files"]}
        if len(listed) != len(manifest["files"]) or set(names) != set(listed) | {"local-release.json"}:
            raise BuildError("release_zip_members_mismatch")
        for name, entry in listed.items():
            data = bundle.read(name)
            if len(data) != entry["size"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
                raise BuildError("release_zip_hash_mismatch")
    return manifest


def extract_release(archive: Path, destination: Path) -> None:
    if destination.exists():
        raise BuildError("payload_directory_exists")
    with zipfile.ZipFile(archive) as bundle:
        for name in bundle.namelist():
            target = destination.joinpath(*name.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(bundle.read(name))


def pinned_artifacts(release: Path) -> list[Artifact]:
    """Everything setup downloads, read from the release's own pins."""
    setup = (release / "scripts/local_setup.ps1").read_text(encoding="utf-8-sig")
    url, digest = UV_URL.search(setup), UV_SHA.search(setup)
    if not url or not digest:
        raise BuildError("uv_pin_missing")
    artifacts = [Artifact("uv", url.group(1), digest.group(1))]
    runtime = json.loads((release / "engines/python/windows-runtime.lock.json").read_text(encoding="utf-8"))
    python = runtime["python"]
    if (runtime.get("schema") != "cytellect-windows-runtime/1"
            or not re.fullmatch(r"https://www\.python\.org/ftp/python/[0-9.]+/python-[0-9.]+-amd64\.zip",
                                python.get("url", ""))):
        raise BuildError("python_pin_invalid")
    artifacts.append(Artifact("python", python["url"], python["sha256"], int(python["bytes"])))
    fiji = json.loads((release / "engines/fiji/runtime.lock.json").read_text(encoding="utf-8"))
    distribution = fiji["fiji"]["windows-x64"]
    artifacts.append(Artifact("fiji", distribution["url"], distribution["sha256"]))
    for plugin in fiji["plugins"]:
        artifacts.append(Artifact("fiji_plugin", plugin["url"], plugin["sha256"], plugin.get("bytes")))
    for artifact in artifacts:
        if not DIGEST.fullmatch(artifact.sha256) or not artifact.url.startswith("https://"):
            raise BuildError("artifact_pin_invalid")
    return artifacts


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


# The researcher's interpreter: CPython 3.14.8 on 64-bit Windows.
TARGET_ENVIRONMENT = {"sys_platform": "win32", "platform_system": "Windows", "os_name": "nt",
                      "platform_machine": "AMD64", "python_version": "3.14", "python_full_version": "3.14.8",
                      "implementation_name": "cpython", "platform_python_implementation": "CPython"}


def locked_requirements(text: str) -> dict[str, tuple[str, set[str]]]:
    """Third-party pins that apply on the target, with their allowed wheel hashes.

    The local project wheel line (./wheels/...) is bound separately by the release manifest.
    """
    from packaging.requirements import InvalidRequirement, Requirement

    joined = re.sub(r"\\\r?\n", " ", text)
    pins: dict[str, tuple[str, set[str]]] = {}
    for raw in joined.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("./wheels/"):
            continue
        specification, _, rest = line.partition(" --hash=")
        hashes = set(re.findall(r"--hash=sha256:([0-9a-f]{64})", line))
        try:
            requirement = Requirement(specification.strip())
        except InvalidRequirement:
            raise BuildError("requirements_not_hash_locked") from None
        pinned = [spec for spec in requirement.specifier if spec.operator == "=="]
        if not rest or not hashes or len(pinned) != 1 or requirement.url:
            raise BuildError("requirements_not_hash_locked")
        if requirement.marker is not None and not requirement.marker.evaluate(TARGET_ENVIRONMENT):
            continue
        name = normalize(requirement.name)
        if name in pins:
            raise BuildError("requirements_duplicate")
        pins[name] = (f"{requirement.name}=={pinned[0].version}", hashes)
    if not pins:
        raise BuildError("requirements_not_hash_locked")
    return pins


def requirement_hashes(text: str) -> dict[str, set[str]]:
    return {name: hashes for name, (_, hashes) in locked_requirements(text).items()}


def third_party_requirements(text: str) -> str:
    """The pip-download input: target pins with hashes, markers already evaluated."""
    return "".join(f"{pin} " + " ".join(f"--hash=sha256:{value}" for value in sorted(hashes)) + "\n"
                   for pin, hashes in locked_requirements(text).values())


def verify_wheelhouse(requirements: str, wheels: Path) -> list[dict]:
    """Exactly one Windows-compatible, hash-listed wheel per locked requirement."""
    pins = requirement_hashes(requirements)
    found: dict[str, dict] = {}
    for path in sorted(wheels.iterdir()):
        match = WHEEL.fullmatch(path.name)
        if path.is_symlink() or not path.is_file() or not match:
            raise BuildError("wheelhouse_unexpected_file")
        platform = match.group("platform")
        if not all(tag in {"any", "win_amd64"} for tag in platform.split(".")):
            raise BuildError("wheelhouse_platform_mismatch")
        name = normalize(match.group("name"))
        digest = sha256_file(path)
        if name not in pins or digest not in pins[name]:
            raise BuildError("wheelhouse_hash_not_locked")
        if name in found:
            raise BuildError("wheelhouse_duplicate")
        found[name] = {"path": "wheels/" + path.name, "sha256": digest, "bytes": path.stat().st_size}
    if set(found) != set(pins):
        raise BuildError("wheelhouse_incomplete")
    return [found[name] for name in sorted(found)]


def download_wheels(requirements_text: str, wheels: Path, scratch: Path, pip_python: Path) -> None:
    """Fetch the locked wheels for CPython 3.14 on Windows x64; pip checks every hash."""
    wheels.mkdir(parents=True)
    source = scratch / "third-party-requirements.txt"
    source.write_text(third_party_requirements(requirements_text), encoding="utf-8")
    environment = {key: value for key, value in os.environ.items() if not key.upper().startswith(("PIP_", "UV_"))}
    command = [str(pip_python), "-m", "pip", "download", "--disable-pip-version-check", "--no-deps",
               "--require-hashes", "--only-binary=:all:", "--platform", "win_amd64", "--python-version", "3.14",
               "--implementation", "cp", "--abi", "cp314", "--isolated", "--no-cache-dir",
               "-r", str(source), "-d", str(wheels)]
    try:
        subprocess.run(command, check=True, env=environment, stdout=subprocess.DEVNULL, timeout=1800)
    except (OSError, subprocess.SubprocessError):
        raise BuildError("wheel_download_failed") from None


def fetch_artifact(artifact: Artifact, cache: Path) -> Path:
    """Content-addressed cache; a cached copy is reused only when its digest matches."""
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / artifact.sha256
    if target.is_file() and sha256_file(target) == artifact.sha256:
        return target
    partial = cache / (artifact.sha256 + ".partial")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from fiji_setup import download  # resumable, retried and hash-checked

    try:
        download(artifact.url, partial, artifact.sha256)
    except Exception:
        raise BuildError("artifact_download_failed") from None
    if artifact.size is not None and partial.stat().st_size != artifact.size:
        raise BuildError("artifact_size_mismatch")
    partial.replace(target)
    return target


def write_offline_manifest(offline: Path, release_manifest: bytes, version: str, commit: str,
                           artifacts: list[Artifact], wheels: list[dict]) -> dict:
    entries = []
    for artifact in artifacts:
        path = offline / "sha256" / artifact.sha256
        if sha256_file(path) != artifact.sha256:
            raise BuildError("offline_artifact_hash_mismatch")
        entries.append({"path": "sha256/" + artifact.sha256, "sha256": artifact.sha256,
                        "bytes": path.stat().st_size, "role": artifact.role})
    for wheel in wheels:
        entries.append({**wheel, "role": "wheel"})
    paths = [entry["path"] for entry in entries]
    if len(paths) != len(set(paths)):
        # Duplicate pins (the same plugin twice) would make the manifest ambiguous.
        raise BuildError("offline_duplicate_entry")
    manifest = {"schema": OFFLINE_SCHEMA, "version": version, "source_commit": commit,
                "release_manifest_sha256": hashlib.sha256(release_manifest).hexdigest(),
                "files": sorted(entries, key=lambda entry: entry["path"])}
    (offline / "offline-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def scan_for_secrets(paths: list[Path]) -> dict[str, int]:
    """Rule counts only; file contents and matches never leave this function."""
    counts: dict[str, int] = {}
    for root in paths:
        candidates = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
        for path in candidates:
            parts = set(path.parts)
            if ".venv" in parts or "runtimes" in parts or "node_modules" in parts:
                continue
            if path.name in FORBIDDEN_NAMES or path.name.startswith(".env"):
                counts["forbidden_file"] = counts.get("forbidden_file", 0) + 1
                continue
            if path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size > 8 * 1024**2:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for rule, pattern in SECRET_PATTERNS.items():
                # Real tokens are random: require a digit to avoid prose and CSS names.
                hits = [m for m in pattern.findall(text) if any(c.isdigit() for c in m) or rule == "private_key"]
                if hits:
                    counts[rule] = counts.get(rule, 0) + len(hits)
    return counts


LICENSE_NAME = re.compile(r"(?i)^(?:licen[cs]e|copying|notice|authors?)(?:[._-].*)?$")
# Where the corresponding source of each bundled runtime is published (GPL/LGPL components
# included). The Fiji archive keeps every jar's own notices; its JDK keeps its legal/ folder.
FIJI_SOURCES = ("https://github.com/fiji/fiji", "https://github.com/imagej/ImageJ",
                "https://github.com/ome/bioformats", "https://maven.scijava.org/ (sources of every bundled jar)")


def wheel_notice(path: Path, destination: Path) -> dict:
    """Name, version, declared license and the license files shipped inside one wheel."""
    import email.parser

    with zipfile.ZipFile(path) as wheel:
        names = wheel.namelist()
        info = sorted({name.split("/", 1)[0] for name in names if name.split("/", 1)[0].endswith(".dist-info")})
        if len(info) != 1:
            raise BuildError("wheel_metadata_missing")
        metadata = email.parser.BytesParser().parsebytes(wheel.read(info[0] + "/METADATA"))
        legacy = str(metadata.get("License") or "").strip().splitlines()
        # Some packages put the whole license text in "License"; keep its first line only.
        declared = str(metadata.get("License-Expression") or "") or (legacy[0][:200] if legacy else "")
        classifiers = [str(value).split("::")[-1].strip() for value in metadata.get_all("Classifier", [])
                       if str(value).startswith("License ::")]
        files = []
        for name in names:
            inside = name[len(info[0]) + 1:] if name.startswith(info[0] + "/") else ""
            if not inside or name.endswith("/"):
                continue
            if inside.startswith("licenses/") or LICENSE_NAME.match(PurePosixPath(inside).name):
                target = destination / (metadata["Name"] + "-" + metadata["Version"]) / inside.replace("/", "__")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(wheel.read(name))
                files.append(target.relative_to(destination.parent).as_posix())
    return {"component": metadata["Name"], "version": metadata["Version"],
            "license": declared or ", ".join(classifiers) or "see the package's license files",
            "source": f"https://pypi.org/project/{metadata['Name']}/{metadata['Version']}/", "files": sorted(files)}


def write_notices(payload: Path, release: Path, artifacts: list[Artifact], wheels: list[dict]) -> dict:
    """licenses/: what the installer bundles, under which license, and where its source is."""
    directory = payload / "licenses"
    (directory / "wheels").mkdir(parents=True)
    fiji = json.loads((release / "engines/fiji/runtime.lock.json").read_text(encoding="utf-8"))
    runtime = json.loads((release / "engines/python/windows-runtime.lock.json").read_text(encoding="utf-8"))
    uv = next(artifact for artifact in artifacts if artifact.role == "uv")
    uv_version = uv.url.split("/download/")[1].split("/")[0]
    components = [
        {"component": "Fiji (archive " + fiji["fiji"]["archive_stamp"] + ", with its JDK)",
         "license": "GPL-3.0 for Fiji; every bundled component keeps its own license (Bio-Formats GPL-2.0-or-later; "
                    "the JDK GPL-2.0 WITH Classpath-exception-2.0, see java/*/legal in the installed runtime)",
         "sha256": fiji["fiji"]["windows-x64"]["sha256"], "url": fiji["fiji"]["windows-x64"]["url"],
         "source": "; ".join(FIJI_SOURCES)},
        *({"component": plugin["path"], "license": plugin["license"], "sha256": plugin["sha256"],
           "url": plugin["url"], "source": plugin["source"]} for plugin in fiji["plugins"]),
        {"component": "Python " + runtime["python"]["version"], "license": "PSF-2.0 and bundled component terms",
         "sha256": runtime["python"]["sha256"], "url": runtime["python"]["url"],
         "source": "https://www.python.org/downloads/source/"},
        *({"component": notice["path"], "license": notice["license"], "source": notice["source_url"]}
          for notice in runtime.get("notices", []) if notice.get("scope") == "scripts"),
        {"component": "uv " + uv_version, "license": "Apache-2.0 OR MIT", "sha256": uv.sha256, "url": uv.url,
         "source": f"https://github.com/astral-sh/uv/tree/{uv_version}"},
    ]
    offline = payload / "offline"
    for wheel in wheels:
        components.append(wheel_notice(offline / wheel["path"], directory / "wheels"))
    lines = ["Cytellect Windows installer: bundled third-party software", "",
             "Cytellect's own code is licensed under Apache-2.0 (LICENSE). That license does not apply to the",
             "components below; each keeps its own license. The installed copies keep every notice that the",
             "upstream archives and wheels contain (runtimes/, apps/*/.venv/Lib/site-packages/*.dist-info/).",
             "Corresponding source is published at the addresses given for each component.", ""]
    for item in components:
        lines += [f"- {item['component']}" + (f" {item['version']}" if item.get("version") else ""),
                  f"  License: {item['license']}", f"  Source: {item['source']}"]
        if item.get("sha256"):
            lines.append(f"  Bundled file SHA-256: {item['sha256']}")
        for name in item.get("files", []):
            lines.append(f"  License text: {name}")
    text = ("\n".join(lines) + "\n").encode("utf-8")
    (directory / "THIRD_PARTY_BUNDLED.txt").write_bytes(text)
    (directory / "bundled-components.json").write_text(json.dumps(components, indent=2) + "\n", encoding="utf-8")
    return {"notices_sha256": hashlib.sha256(text).hexdigest(), "components": components}


def numeric_version(version: str) -> str:
    match = re.fullmatch(r"([0-9]+)\.([0-9]+)\.([0-9]+)(?:-local\.([0-9]+))?(?:-.*)?", version)
    if not match:
        raise BuildError("version_invalid")
    return ".".join(group or "0" for group in match.groups())


def iscc_command(iscc: Path, payload: Path, output: Path, version: str, payload_mb: int,
                 sign_command: str | None) -> list[str]:
    command = [str(iscc), "/Q", f"/DAppVersion={version}", f"/DNumericVersion={numeric_version(version)}",
               f"/DPayloadDir={payload}", f"/DOutputDir={output}", f"/DRequiredInstallMB={REQUIRED_INSTALL_MB}",
               f"/DRequiredUpdateMB={REQUIRED_UPDATE_MB}", f"/DPayloadMB={payload_mb}"]
    if sign_command:
        if "$f" not in sign_command:
            raise BuildError("sign_command_requires_file_placeholder")
        command += ["/DSignToolName=cytellect", f"/Scytellect={sign_command}"]
    return [*command, str(ISS)]


def tree_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def build(release_zip: Path, output_dir: Path, work_dir: Path, cache: Path, iscc: Path,
          sign_command: str | None, pip_python: Path | None = None) -> dict:
    manifest = verify_release_zip(release_zip)
    version, commit = manifest["version"], manifest["source_commit"]
    installer = output_dir / f"Cytellect-Setup-{version}.exe"
    if installer.exists():
        raise BuildError("installer_exists")  # never replace a built version
    payload = work_dir / "payload"
    release, offline = payload / "release", payload / "offline"
    extract_release(release_zip, release)
    artifacts = pinned_artifacts(release)
    (offline / "sha256").mkdir(parents=True)
    for artifact in artifacts:
        target = offline / "sha256" / artifact.sha256
        if not target.exists():
            shutil.copyfile(fetch_artifact(artifact, cache), target)
    requirements = (release / "engines/python/windows-requirements.txt").read_text(encoding="utf-8")
    download_wheels(requirements, offline / "wheels", work_dir, pip_python or Path(sys.executable))
    wheels = verify_wheelhouse(requirements, offline / "wheels")
    unique = list({artifact.sha256: artifact for artifact in artifacts}.values())
    write_offline_manifest(offline, (release / "local-release.json").read_bytes(), version, commit, unique, wheels)
    notices = write_notices(payload, release, unique, wheels)
    findings = scan_for_secrets([release, offline / "offline-manifest.json", payload / "licenses"])
    if findings:
        raise BuildError("payload_contains_credentials:" + ",".join(sorted(findings)))
    payload_bytes = tree_bytes(payload)
    if payload_bytes > MAX_PAYLOAD_BYTES:
        raise BuildError("payload_too_large")
    output_dir.mkdir(parents=True, exist_ok=True)
    command = iscc_command(iscc, payload, output_dir, version, math.ceil(payload_bytes / 1024**2), sign_command)
    try:
        subprocess.run(command, check=True, timeout=3600)
    except (OSError, subprocess.SubprocessError):
        raise BuildError("installer_compile_failed") from None
    digest = sha256_file(installer)
    installer.with_name(installer.name + ".sha256").write_text(f"{digest}  {installer.name}\n", encoding="ascii")
    receipt = {"schema": RECEIPT_SCHEMA, "version": version, "source_commit": commit,
               "installer": installer.name, "installer_sha256": digest, "installer_bytes": installer.stat().st_size,
               "release_zip": release_zip.name, "release_zip_sha256": sha256_file(release_zip),
               "payload_bytes": payload_bytes, "bundled": {"artifacts": len(unique), "wheels": len(wheels)},
               "inno_setup": INNO_VERSION, "signed": bool(sign_command),
               "third_party_notices": {"path": "licenses/THIRD_PARTY_BUNDLED.txt",
                                       "sha256": notices["notices_sha256"]},
               "third_party": [{key: item[key] for key in ("component", "version", "license", "source", "sha256")
                                if item.get(key)} for item in notices["components"]]}
    (output_dir / f"Cytellect-Setup-{version}.json").write_text(json.dumps(receipt, indent=2) + "\n",
                                                               encoding="utf-8")
    return receipt


def install_inno(destination: Path, cache: Path) -> Path:
    """Install the pinned compiler for this user only; returns ISCC.exe."""
    compiler = destination / "ISCC.exe"
    if compiler.is_file():
        return compiler
    setup = fetch_artifact(Artifact("inno_setup", INNO_URL, INNO_SHA256), cache)
    runnable = cache / f"innosetup-{INNO_VERSION}.exe"
    shutil.copyfile(setup, runnable)
    subprocess.run([str(runnable), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER",
                    "/NOICONS", f"/DIR={destination}"], check=True, timeout=600)
    if not compiler.is_file():
        raise BuildError("inno_install_failed")
    return compiler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("build")
    make.add_argument("--release-zip", type=Path, required=True)
    make.add_argument("--output-dir", type=Path, required=True)
    make.add_argument("--work-dir", type=Path, required=True)
    make.add_argument("--cache", type=Path, required=True, help="Content-addressed download cache")
    make.add_argument("--iscc", type=Path, required=True)
    make.add_argument("--pip-python", type=Path, default=Path(sys.executable),
                      help="An interpreter with pip, used only to download the locked wheels")
    make.add_argument("--sign-command", default=os.environ.get("CYTELLECT_SIGN_COMMAND") or None,
                      help="Signing command with $f for the file; unsigned when omitted (D4)")
    inno = commands.add_parser("install-inno")
    inno.add_argument("--dest", type=Path, required=True)
    inno.add_argument("--cache", type=Path, required=True)
    scan = commands.add_parser("scan")
    scan.add_argument("paths", type=Path, nargs="+")
    args = parser.parse_args()
    try:
        if args.command == "build":
            root = Path(__file__).resolve().parents[1]
            for path in (args.output_dir, args.work_dir):
                resolved = path.resolve()
                if resolved == root or root in resolved.parents:
                    parser.error("Installer outputs must be outside the checkout")
            print(json.dumps(build(args.release_zip.resolve(), args.output_dir.resolve(), args.work_dir.resolve(),
                                   args.cache.resolve(), args.iscc.resolve(), args.sign_command,
                                   args.pip_python)))
        elif args.command == "install-inno":
            print(install_inno(args.dest.resolve(), args.cache.resolve()))
        else:
            findings = scan_for_secrets([path.resolve() for path in args.paths])
            print(json.dumps({"findings": findings}))
            if findings:
                raise SystemExit(1)
    except BuildError as error:
        print("Installer build failed: " + str(error), file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
