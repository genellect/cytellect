"""Corresponding source for the copyleft software that the Windows installer bundles.

The installer ships Fiji (with its JDK and plugins), Python and the locked wheels
unmodified. GPL, LGPL and the other licenses that require source with a binary
(MPL, EPL, CDDL, ...) are addressed by attaching the exact source of every such component
to the same release as ``Cytellect-<version>-gpl-sources.zip``, except the components
listed in ``engines/fiji/source-exceptions.json``, for which the upstream source location
is given instead.

Which components carry that obligation is derived from what is bundled, never from a
hand-written list:

- every jar in the Fiji archive and every pinned plugin: the licenses its embedded
  Maven POM declares, else the POM (and parents) published for its coordinates,
  else its own license files; coordinates come from ``pom.properties`` or, for a jar
  without one, from a Maven checksum search of its exact bytes;
- every native executable or library in the Fiji archive outside the JDK;
- the JDK, from its ``release`` file;
- every bundled wheel, from its metadata and the ``License:`` lines of the license
  files it carries for vendored libraries (SPDX ``OR`` alternatives and the GCC
  runtime library exception are honoured);
- the Python runtime and uv, from the licenses their pins record.

A component whose license cannot be determined is treated as needing source. A jar's
source is the most exact one published (see ``exact_source``): the -sources.jar of a
byte-identical repository jar, the GitHub archive of the commit it was built from, or
the -sources.jar of the release version it declares.

Network lookups happen only when the lock is generated, by this command, outside the
checkout's build:

    python scripts/corresponding_source.py lock --cache /outside/cache

That writes ``engines/fiji/corresponding-source.lock.json``: every bundled Fiji file
with its SHA-256, license evidence, obligation and, where needed, the exact source
file's URL, SHA-256 and size. The installer build then re-derives the obligations
from the bundled bytes, refuses a lock that does not describe them, downloads each
source by its pinned SHA-256 (retried on transient failures) and fails for any
obligation without source unless ``engines/fiji/source-exceptions.json`` lists that
component with the same bundled SHA-256, its reason and its upstream source location.
By the owner's decision of 2026-10-30 those components are bundled and only their
upstream location is given. An exception that no longer matches an obligation without
source also fails the build, so the list cannot drift from what is bundled. Wheel
sources are the sdists that ``uv.lock`` pins.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import io
import json
import re
import sys
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "engines/fiji/corresponding-source.lock.json"
LOCK_SCHEMA = "cytellect-corresponding-source/1"
EXCEPTIONS_PATH = ROOT / "engines/fiji/source-exceptions.json"
EXCEPTIONS_SCHEMA = "cytellect-source-exceptions/1"
# Why a component that needs source has none attached.
EXCEPTION_REASONS = frozenset({"no-public-source", "source-host-unreachable", "license-undetermined"})
ARCHIVE_SCHEMA = "cytellect-gpl-sources/1"
MAVEN_REPOSITORIES = ("https://maven.scijava.org/content/groups/public", "https://repo1.maven.org/maven2")
CENTRAL_SHA1_SEARCH = "https://central.sonatype.com/solrsearch/select?q=1:{sha1}&rows=5&wt=json"
SCIJAVA_SHA1_SEARCH = "https://maven.scijava.org/service/rest/v1/search/assets?sha1={sha1}&maven.extension=jar"
JDK_RELEASE = re.compile(r"^(?P<root>[^/]+/java/[^/]+/[^/]+)/release$")
NATIVE = re.compile(r"(?i)\.(?:exe|dll|so|dylib)$")
GITHUB = re.compile(r"github\.com[:/]([A-Za-z0-9_.-]+)/([A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*?)(?:\.git)?(?=[/\s<]|$)")
DIGEST = re.compile(r"[0-9a-f]{64}")

SOURCE, NONE, UNKNOWN = "source", "none", "unknown"

# Licenses that oblige a distributor of binaries to provide source.
COPYLEFT = re.compile(
    r"(?i)\b(?:a|l)?gpl|general public licen[cs]e|lesser general|library general|affero|"
    r"gnu\.org/(?:licenses|copyleft)|mozilla public|\bmpl\b|eclipse public|\bepl\b|"
    r"common development and distribution|\bcddl\b|common public licen[cs]e|\bcpl\b|"
    r"european union public|\beupl\b|\bpart of r\b")
# Exceptions under which the covered runtime may be combined and passed on without source.
NO_SOURCE_EXCEPTION = re.compile(r"(?i)gcc-exception|gcc runtime library exception|runtime library exception")
PERMISSIVE = re.compile(
    r"(?i)apache|\bmit\b|mit-|\bbsd\b|bsd-|\b0bsd\b|\bisc\b|zlib|public domain|\bcc0\b|unlicense|"
    r"\bpsf\b|python software foundation|boost|bsl-1\.0|unicode|\bw3c\b|bouncy ?castle|\bjson\b|"
    r"\bx11\b|creative commons attribution|\bcc-by\b|\bofl\b|eclipse distribution|\bedl\b|janelia farm|"
    r"cup parser generator|\bhpnd\b|wtfpl|historical permission|\bftl\b|freetype project|qhull|"
    r"bitstream|bakoma|permission is hereby granted|redistribution and use in source and binary forms")
# Headings that identify a license file's text (only the opening of each file is read).
TEXT_HEADINGS = re.compile(
    r"(?i)gnu (?:lesser |library |affero )?general public license|mozilla public license|"
    r"eclipse public license|common development and distribution license|apache license|"
    r"permission is hereby granted|redistribution and use in source and binary forms|the unlicense|"
    r"public domain|boost software license|eclipse distribution license|\bbsd license\b|\bmit license\b")
LICENSE_FILE = re.compile(r"(?i)^(?:licen[cs]e|copying|unlicense)(?:[._-].*)?$")

# Components without machine-readable license evidence, determined once by review.
# Keyed by the path inside the Fiji archive; the reason says where the license is stated.
REVIEWED_LICENSES: dict[str, tuple[str, str]] = {
    "Fiji/fiji-windows-x64.exe": ("Unlicense", "Jaunch launcher; https://github.com/apposed/jaunch (UNLICENSE)"),
    "Fiji/config/jaunch/jaunch-windows-x64.exe": (
        "Unlicense", "Jaunch launcher; https://github.com/apposed/jaunch (UNLICENSE)"),
}


class SourceError(Exception):
    """Fixed, non-sensitive failure codes (a component path may follow a colon)."""


# --- license classification -------------------------------------------------------------

def _split_top(text: str, operator: str) -> list[str]:
    parts, depth, start = [], 0, 0
    index = 0
    while index < len(text):
        char = text[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif depth == 0 and text.startswith(operator, index):
            parts.append(text[start:index])
            start = index + len(operator)
            index = start
            continue
        index += 1
    parts.append(text[start:])
    return [part.strip() for part in parts if part.strip()]


def _unwrap(text: str) -> str:
    """Remove parentheses that enclose the whole expression."""
    while text.startswith("(") and text.endswith(")"):
        depth = 0
        for index, char in enumerate(text):
            depth += char == "("
            depth -= char == ")"
            if depth == 0 and index < len(text) - 1:
                return text
        text = text[1:-1].strip()
    return text


def obligation(text: str) -> str:
    """Whether one license statement requires source: SOURCE, NONE or UNKNOWN.

    SPDX ``OR`` takes the alternative without an obligation, ``AND`` the strictest part,
    and ``WITH`` a runtime-library exception (GCC) clears the obligation.
    """
    text = _unwrap(" ".join(str(text).split()))
    alternatives = _split_top(text, " OR ")
    if len(alternatives) > 1:
        results = [obligation(item) for item in alternatives]
        return NONE if NONE in results else SOURCE if SOURCE in results else UNKNOWN
    parts = _split_top(text, " AND ")
    if len(parts) > 1:
        return combine(obligation(item) for item in parts)
    text = text.strip("() ")
    base, _, exception = text.partition(" WITH ")
    if exception and NO_SOURCE_EXCEPTION.search(exception):
        return NONE
    if COPYLEFT.search(text):
        return SOURCE
    if PERMISSIVE.search(base or text):
        return NONE
    return UNKNOWN


def combine(results: Iterable[str]) -> str:
    """Several statements about one component: any obligation wins, then any doubt."""
    values = set(results)
    if SOURCE in values:
        return SOURCE
    if UNKNOWN in values or not values:
        return UNKNOWN
    return NONE


def classify(evidence: list[str]) -> str:
    return combine(obligation(item) for item in evidence) if evidence else UNKNOWN


# --- what the bundled bytes say -----------------------------------------------------------

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pom_licenses(text: str) -> list[str]:
    """License names (or, without a name, URLs) declared in one POM's <licenses>."""
    block = re.search(r"<licenses>(.*?)</licenses>", text, re.S)
    found = []
    for license_block in re.findall(r"<license>(.*?)</license>", block.group(1), re.S) if block else []:
        match = re.search(r"<name>(.*?)</name>", license_block, re.S) or re.search(r"<url>(.*?)</url>",
                                                                                     license_block, re.S)
        value = " ".join(match.group(1).split()) if match else ""
        if value:
            found.append(value)
    return found


def pom_parent(text: str) -> tuple[str, str, str] | None:
    block = re.search(r"<parent>(.*?)</parent>", text, re.S)
    if not block:
        return None
    values = [re.search(rf"<{key}>\s*([^<\s]+)\s*</{key}>", block.group(1)) for key in ("groupId", "artifactId", "version")]
    if not all(values) or any("${" in value.group(1) for value in values if value):
        return None
    group, artifact, version = (value.group(1) for value in values if value)
    return group, artifact, version


def text_evidence(name: str, data: bytes) -> list[str]:
    """Headings found at the start of one license file, as "<file>: <heading>"."""
    head = " ".join(data[:3000].decode("utf-8", "replace").split())
    headings = sorted({match.group(0).lower() for match in TEXT_HEADINGS.finditer(head)})
    return [f"{name}: {heading}" for heading in headings]


def jar_evidence(data: bytes) -> dict:
    """Coordinates and license statements that a jar carries itself."""
    entry: dict = {"coordinates": None, "licenses": [], "licenses_from": None}
    try:
        jar = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return entry
    with jar:
        names = jar.namelist()
        properties = [name for name in names if name.startswith("META-INF/maven/") and name.endswith("/pom.properties")]
        if len(properties) == 1:
            values = dict(line.split("=", 1) for line in jar.read(properties[0]).decode("utf-8", "replace").splitlines()
                          if "=" in line and not line.startswith("#"))
            coordinates = tuple(values.get(key, "").strip() for key in ("groupId", "artifactId", "version"))
            if all(coordinates):
                entry["coordinates"] = ":".join(coordinates)
        declared, repositories = [], set()
        for name in sorted(name for name in names if name.startswith("META-INF/maven/") and name.endswith("/pom.xml")):
            text = jar.read(name).decode("utf-8", "replace")
            declared += pom_licenses(text)
            scm = re.search(r"<scm>(.*?)</scm>", text, re.S)
            repositories |= {f"{owner}/{repository}" for owner, repository in GITHUB.findall(scm.group(1) if scm else "")}
        manifest = jar.read("META-INF/MANIFEST.MF").decode("utf-8", "replace") if "META-INF/MANIFEST.MF" in names else ""
        commit = re.search(r"(?m)^Implementation-Build:\s*([0-9a-f]{40})\s*$", manifest)
        if commit and len(repositories) == 1:
            # The commit this jar was built from (SciJava builds record it), in its GitHub repository.
            entry["build"] = {"repository": repositories.pop(), "commit": commit.group(1)}
        if declared:
            entry.update(licenses=sorted(set(declared)), licenses_from="embedded-pom")
            return entry
        texts = []
        for name in sorted(names):
            inside = PurePosixPath(name)
            if not name.endswith("/") and len(inside.parts) <= 2 and LICENSE_FILE.match(inside.name):
                texts += text_evidence(name, jar.read(name))
        if texts:
            entry.update(licenses=texts, licenses_from="jar-license-file")
    return entry


def fiji_inventory(archive: Path, plugins: list[dict], plugin_bytes: Callable[[dict], bytes]) -> dict:
    """Every jar and native binary that the Fiji archive and the pinned plugins bundle, offline."""
    files: list[dict] = []
    jdk: dict | None = None
    with zipfile.ZipFile(archive) as fiji:
        infos = fiji.infolist()
        jdk_roots = {match.group("root") for info in infos if (match := JDK_RELEASE.match(info.filename))}
        notices = {PurePosixPath(info.filename).stem.lower(): info.filename for info in infos
                   if info.filename.startswith("Fiji/licenses/") and not info.filename.endswith("/")}
        for info in infos:
            name = info.filename
            if name.endswith("/"):
                continue
            if any(name.startswith(root + "/") for root in jdk_roots):
                if name.endswith("/release") and jdk is None:
                    data = fiji.read(info)
                    jdk = {"path": name, "sha256": sha256(data), **jdk_identity(data.decode("utf-8", "replace"))}
                continue
            if name.endswith(".jar"):
                data = fiji.read(info)
                files.append({"path": name, "sha256": sha256(data), "sha1": hashlib.sha1(data).hexdigest(),  # noqa: S324
                              "kind": "jar", **jar_evidence(data)})
            elif NATIVE.search(name):
                data = fiji.read(info)
                entry: dict = {"path": name, "sha256": sha256(data), "kind": "native", "coordinates": None,
                         "licenses": [], "licenses_from": None}
                stem = PurePosixPath(name).stem.lower()
                if stem in notices:
                    entry.update(licenses=text_evidence(notices[stem], fiji.read(notices[stem])),
                                 licenses_from="fiji-licenses-dir")
                files.append(entry)
    for plugin in plugins:
        data = plugin_bytes(plugin)
        if sha256(data) != plugin["sha256"]:
            raise SourceError("plugin_hash_mismatch:" + plugin["path"])
        evidence = jar_evidence(data)
        # The license reviewed in runtime.lock.json, beside anything the jar declares itself.
        evidence.update(licenses=sorted(set(evidence["licenses"]) | {plugin["license"]}),
                        licenses_from=" + ".join(filter(None, [evidence["licenses_from"], "fiji-runtime-lock"])))
        files.append({"path": "plugin:" + plugin["path"], "sha256": plugin["sha256"],
                      "sha1": hashlib.sha1(data).hexdigest(), "kind": "jar", **evidence})  # noqa: S324
    for entry in files:
        reviewed = REVIEWED_LICENSES.get(entry["path"])
        if reviewed and not entry["licenses"]:
            entry.update(licenses=[reviewed[0]], licenses_from="reviewed: " + reviewed[1])
    return {"files": sorted(files, key=lambda item: item["path"]), "jdk": jdk}


def jdk_identity(release_text: str) -> dict:
    values = {key: value.strip().strip('"') for key, _, value in
              (line.partition("=") for line in release_text.splitlines()) if key}
    return {"implementor": values.get("IMPLEMENTOR", ""), "implementor_version": values.get("IMPLEMENTOR_VERSION", ""),
            "version": values.get("JAVA_RUNTIME_VERSION") or values.get("JAVA_VERSION", ""),
            "source_revision": values.get("SOURCE", ""),
            "license": "GPL-2.0-only WITH Classpath-exception-2.0"}


def inventory_digest(inventory: dict) -> str:
    """One digest over every bundled path and SHA-256, to detect a stale lock."""
    rows = [f"{item['path']}\t{item['sha256']}" for item in inventory["files"]]
    if inventory.get("jdk"):
        rows.append(f"{inventory['jdk']['path']}\t{inventory['jdk']['sha256']}")
    return sha256("\n".join(rows).encode("utf-8"))


# --- wheels ---------------------------------------------------------------------------------

def wheel_licenses(path: Path) -> list[str]:
    """Declared license of one wheel plus the SPDX License: lines of its vendored libraries."""
    import email.parser

    with zipfile.ZipFile(path) as wheel:
        names = wheel.namelist()
        info = sorted({name.split("/", 1)[0] for name in names if name.split("/", 1)[0].endswith(".dist-info")})
        if len(info) != 1:
            raise SourceError("wheel_metadata_missing:" + path.name)
        metadata = email.parser.BytesParser().parsebytes(wheel.read(info[0] + "/METADATA"))
        statements = []
        expression = str(metadata.get("License-Expression") or "").strip()
        if expression:
            statements.append(expression)
        else:
            classifiers = [str(value).split("::")[-1].strip() for value in metadata.get_all("Classifier", [])
                           if str(value).startswith("License ::") and "OSI Approved" != str(value).split("::")[-1].strip()]
            legacy = str(metadata.get("License") or "").strip().splitlines()
            statements += classifiers or legacy[:1]
        for name in names:
            if name.endswith("/") or not (LICENSE_FILE.match(PurePosixPath(name).name) or "/licenses/" in name):
                continue
            for line in wheel.read(name).decode("utf-8", "replace").splitlines():
                match = re.match(r"^License:\s*(\S.*)$", line)
                if match:
                    statements.append(match.group(1).strip())
    return statements


def sdists(uv_lock: str) -> dict[tuple[str, str], dict]:
    """(normalized name, version) -> the sdist that uv.lock pins, with its SHA-256."""
    found = {}
    for package in tomllib.loads(uv_lock).get("package", []):
        sdist = package.get("sdist")
        if sdist and str(sdist.get("hash", "")).startswith("sha256:") and sdist.get("url"):
            name = re.sub(r"[-_.]+", "-", package["name"]).lower()
            found[(name, str(package["version"]))] = {"url": sdist["url"], "sha256": sdist["hash"][len("sha256:"):],
                                                       "bytes": sdist.get("size")}
    return found


def runtime_obligations(runtime_lock: dict, uv: dict) -> list[dict]:
    """The Python runtime and uv, from the licenses their pins record.

    Script-scope notices (the Tcl/Tk library scripts) are bundled as source text already.
    """
    python = runtime_lock["python"]
    base = [notice["license"] for notice in runtime_lock.get("notices", []) if notice.get("scope") == "base"]
    items = [{"path": "python:" + python["version"], "sha256": python["sha256"], "kind": "runtime",
              "coordinates": "CPython " + python["version"], "licenses": base},
             {"path": "uv:" + uv["version"], "sha256": uv["sha256"], "kind": "runtime",
              "coordinates": "uv " + uv["version"], "licenses": [uv["license"]]}]
    needed = []
    for item in items:
        item["obligation"] = classify(item["licenses"])
        if item["obligation"] != NONE:
            needed.append({**item, "source": None})
    return needed


def wheel_obligations(wheels: list[Path], uv_lock: str) -> list[dict]:
    pins = sdists(uv_lock)
    entries = []
    for path in sorted(wheels):
        name, version = path.name.split("-")[:2]
        normalized = re.sub(r"[-_.]+", "-", name).lower()
        licenses = wheel_licenses(path)
        result = classify(licenses)
        if result == NONE:
            continue
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        entries.append({"path": "wheel:" + path.name, "sha256": digest, "kind": "wheel",
                        "coordinates": f"{normalized}=={version}", "licenses": licenses, "obligation": result,
                        "source": pins.get((normalized, version))})
    return entries


# --- network (lock generation only; the build downloads by pinned SHA-256) -----------------

TRANSIENT_HTTP = frozenset({408, 425, 429, 500, 502, 503, 504})


def http_get(url: str, attempts: int = 10) -> bytes | None:
    """GET with retries for transient failures; None when the resource does not exist."""
    host = urllib.parse.urlsplit(url).hostname or ""
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "cytellect-corresponding-source"})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code in (403, 404, 410):
                return None
            if error.code not in TRANSIENT_HTTP:
                raise SourceError(f"lookup_failed:{host}:HTTP {error.code}") from None
            reason, wait = f"HTTP {error.code}", str(error.headers.get("Retry-After", ""))
        except (urllib.error.URLError, http.client.HTTPException, ConnectionError, TimeoutError) as error:
            reason, wait = type(error).__name__, ""
        delay = min(int(wait), 120) if wait.isdigit() else min(5 * 2 ** attempt, 120)
        print(f"Transient lookup failure at {host}: {reason}; retry in {delay} s", file=sys.stderr, flush=True)
        time.sleep(delay)
    raise SourceError("lookup_failed_after_retries:" + host)


def disk_cached(directory: Path, get: Callable[[str], bytes | None] = http_get) -> Callable[[str], bytes | None]:
    """Keep small lookups (POMs, checksums, searches) on disk, so a regeneration repeats none."""
    directory.mkdir(parents=True, exist_ok=True)

    def cached_get(url: str) -> bytes | None:
        if url.endswith(("-sources.jar", ".tar.gz", ".zip")) or "/tar.gz/" in url:
            return get(url)
        path = directory / sha256(url.encode("utf-8"))
        missing = path.with_suffix(".missing")
        if path.is_file():
            return path.read_bytes()
        if missing.is_file():
            return None
        data = get(url)
        (path if data is not None else missing).write_bytes(data or b"")
        return data

    return cached_get


def maven_path(coordinates: str, suffix: str) -> str:
    group, artifact, version = coordinates.split(":")
    return f"{group.replace('.', '/')}/{artifact}/{version}/{artifact}-{version}{suffix}"


class Resolver:
    """Maven lookups with a memo, so shared parent POMs are fetched once."""

    def __init__(self, get: Callable[[str], bytes | None] = http_get):
        self.get = get
        self.memo: dict[str, bytes | None] = {}

    def fetch(self, url: str, remember: bool = True) -> bytes | None:
        if not remember:  # source archives: hashed once, not kept in memory
            return self.get(url)
        if url not in self.memo:
            self.memo[url] = self.get(url)
        return self.memo[url]

    def first(self, path: str, remember: bool = True) -> tuple[str, bytes] | None:
        for repository in MAVEN_REPOSITORIES:
            data = self.fetch(f"{repository}/{path}", remember)
            if data is not None:
                return f"{repository}/{path}", data
        return None

    def coordinates_by_checksum(self, sha1: str) -> str | None:
        found = set()
        central = self.fetch(CENTRAL_SHA1_SEARCH.format(sha1=sha1))
        if central:
            for doc in json.loads(central).get("response", {}).get("docs", []):
                found.add(f"{doc['g']}:{doc['a']}:{doc['v']}")
        if not found:
            scijava = self.fetch(SCIJAVA_SHA1_SEARCH.format(sha1=sha1))
            for item in json.loads(scijava).get("items", []) if scijava else []:
                maven = item.get("maven2", {})
                if maven.get("extension") == "jar" and not maven.get("classifier"):
                    found.add(f"{maven['groupId']}:{maven['artifactId']}:{maven['version']}")
        return found.pop() if len(found) == 1 else None

    def published_licenses(self, coordinates: str) -> tuple[list[str], str] | None:
        """Licenses of the published POM, following parents until one declares them."""
        current: str | None = coordinates
        for _ in range(10):
            if current is None:
                return None
            found = self.first(maven_path(current, ".pom"))
            if not found:
                return None
            text = found[1].decode("utf-8", "replace")
            declared = pom_licenses(text)
            if declared:
                return sorted(set(declared)), current
            parent = pom_parent(text)
            current = ":".join(parent) if parent else None
        return None

    def binary_matches(self, coordinates: str, sha1: str) -> bool | None:
        found = self.first(maven_path(coordinates, ".jar.sha1"))
        if not found:
            return None
        return found[1].decode("ascii", "replace").split()[0].strip().lower() == sha1 if found[1].split() else None

    def github_archive(self, repository: str, commit: str) -> dict | None:
        url = f"https://codeload.github.com/{repository}/tar.gz/{commit}"
        data = self.fetch(url, remember=False)
        return {"url": url, "sha256": sha256(data), "bytes": len(data)} if data is not None else None

    def sources_jar(self, coordinates: str) -> dict | None:
        found = self.first(maven_path(coordinates, "-sources.jar"), remember=False)
        if not found:
            return None
        url, data = found
        published = self.fetch(url + ".sha1")
        if published and published.split() and published.split()[0].decode("ascii", "replace").lower() != \
                hashlib.sha1(data).hexdigest():  # noqa: S324
            raise SourceError("published_checksum_mismatch:" + coordinates)
        return {"url": url, "sha256": sha256(data), "bytes": len(data)}


def resolve_jdk(jdk: dict, resolver: Resolver) -> dict | None:
    """The JDK vendor's own source archive for this exact build, when the vendor publishes one."""
    implementor, version = jdk.get("implementor", ""), re.sub(r"-LTS$", "", jdk.get("version", ""))
    if "Eclipse Adoptium" in implementor and "+" in version:
        major = version.split(".")[0].split("+")[0]
        name = f"OpenJDK{major}U-jdk-sources_{version.replace('+', '_')}.tar.gz"
        base = f"https://github.com/adoptium/temurin{major}-binaries/releases/download/jdk-{urllib.parse.quote(version)}"
        checksum = resolver.fetch(f"{base}/{name}.sha256.txt")
        if checksum:
            data = resolver.fetch(f"{base}/{name}")
            if data is not None and sha256(data) == checksum.split()[0].decode("ascii", "replace").lower():
                return {"url": f"{base}/{name}", "sha256": sha256(data), "bytes": len(data)}
    if "Azul" in implementor:
        match = re.fullmatch(r"Zulu([0-9.]+)\+([0-9]+)-.*", jdk.get("implementor_version", ""))
        java = jdk.get("version", "").split("+")[0]
        if match:
            name = f"zsrc{match.group(1)}.{match.group(2)}-jdk{java}.zip"
            data = resolver.fetch(f"https://cdn.azul.com/zulu/src/{name}")
            if data is not None:
                return {"url": f"https://cdn.azul.com/zulu/src/{name}", "sha256": sha256(data), "bytes": len(data)}
    return None


def resolve(inventory: dict, resolver: Resolver, log: Callable[[str], None] = lambda message: None,
            workers: int = 8) -> dict:
    """Complete each bundled file's evidence from Maven and pin the sources that are needed."""
    from concurrent.futures import ThreadPoolExecutor

    done = []

    def one(item: dict) -> dict:
        entry = resolve_file(item, resolver)
        done.append(item["path"])
        if len(done) % 50 == 0:
            log(f"{len(done)}/{len(inventory['files'])} files")
        return entry

    with ThreadPoolExecutor(max_workers=workers) as pool:
        files = list(pool.map(one, inventory["files"]))
    jdk = dict(inventory["jdk"]) if inventory.get("jdk") else None
    if jdk:
        jdk["obligation"] = obligation(jdk["license"])
        jdk["source"] = resolve_jdk(jdk, resolver)
    return {"files": files, "jdk": jdk}


def resolve_file(item: dict, resolver: Resolver) -> dict:
    """One bundled file's coordinates, license evidence, obligation and pinned source."""
    entry = {key: value for key, value in item.items() if key != "sha1"}
    if item["kind"] == "jar":
        if entry["coordinates"]:
            entry["coordinates_from"] = "pom.properties"
        else:
            found = resolver.coordinates_by_checksum(item["sha1"])
            if found:
                entry.update(coordinates=found, coordinates_from="maven-checksum-search")
        if entry["coordinates"]:
            if not any(label in (entry["licenses_from"] or "") for label in ("embedded-pom", "fiji-runtime-lock")):
                published = resolver.published_licenses(entry["coordinates"])
                if published:
                    # Kept beside the jar's own license files: either may reveal an obligation.
                    entry.update(licenses=sorted(set(entry["licenses"]) | set(published[0])),
                                 licenses_from=" + ".join(filter(None, [entry["licenses_from"],
                                                                        "repository-pom " + published[1]])))
            entry["binary_matches_repository"] = resolver.binary_matches(entry["coordinates"], item["sha1"])
    entry["obligation"] = classify(entry["licenses"])
    entry["source"] = None
    if entry["obligation"] != NONE:
        entry["source"] = exact_source(entry, resolver)
    return entry


def declared_release(entry: dict) -> bool:
    """The jar names its own released version, and its file is that artifact (no classifier)."""
    if entry.get("coordinates_from") != "pom.properties":
        return False
    _, artifact, version = entry["coordinates"].split(":")
    return not version.endswith("-SNAPSHOT") and PurePosixPath(entry["path"]).name == f"{artifact}-{version}.jar"


def exact_source(entry: dict, resolver: Resolver) -> dict | None:
    """The most exact source published for one bundled jar, best first.

    1. the -sources.jar beside a repository jar that is byte-identical to the bundled one;
    2. the GitHub archive of the commit the jar records it was built from;
    3. the -sources.jar of the release version the jar declares in its own pom.properties.
    """
    coordinates = entry.get("coordinates")
    if coordinates and entry.get("binary_matches_repository"):
        found = resolver.sources_jar(coordinates)
        if found:
            return {**found, "kind": "maven-sources of the identical repository jar"}
    build = entry.get("build")
    if build:
        found = resolver.github_archive(build["repository"], build["commit"])
        if found:
            return {**found, "kind": "github archive of the commit the jar was built from"}
    if coordinates and declared_release(entry):
        found = resolver.sources_jar(coordinates)
        if found:
            return {**found, "kind": "maven-sources of the release version the jar declares"}
    return None


# --- lock --------------------------------------------------------------------------------------

def write_lock(path: Path, fiji_sha256: str, inventory: dict, resolved: dict) -> dict:
    lock = {"schema": LOCK_SCHEMA, "fiji_windows_x64_sha256": fiji_sha256,
            "inventory_sha256": inventory_digest(inventory),
            "generated_by": "python scripts/corresponding_source.py lock",
            "summary": summary(resolved), "jdk": resolved["jdk"], "files": resolved["files"]}
    rows = ",\n".join("    " + json.dumps(entry, sort_keys=True) for entry in resolved["files"])
    head = {key: lock[key] for key in lock if key != "files"}
    text = json.dumps(head, indent=2, sort_keys=False)[:-2] + ',\n  "files": [\n' + rows + "\n  ]\n}\n"
    path.write_text(text, encoding="utf-8")
    return lock


def summary(resolved: dict) -> dict:
    """Counts over the bundled files, and every obligation (the JDK included) without a pinned source."""
    files = resolved["files"]
    jdk = [resolved["jdk"]] if resolved.get("jdk") else []
    return {"files": len(files),
            "source": sum(1 for item in files if item["obligation"] == SOURCE),
            "unknown": sum(1 for item in files if item["obligation"] == UNKNOWN),
            "pinned_sources": sum(1 for item in files + jdk if item["source"]),
            "pinned_source_bytes": sum(item["source"]["bytes"] for item in files + jdk if item["source"]),
            "without_source": sorted(item["path"] for item in files + jdk
                                     if item["obligation"] != NONE and not item["source"])}


def load_lock(path: Path = LOCK_PATH) -> dict:
    lock = json.loads(path.read_text(encoding="utf-8"))
    if lock.get("schema") != LOCK_SCHEMA:
        raise SourceError("corresponding_source_lock_invalid")
    return lock


def obligations(lock: dict, inventory: dict, fiji_sha256: str) -> list[dict]:
    """The lock's obligations, after checking that it describes exactly what is bundled."""
    if lock.get("fiji_windows_x64_sha256") != fiji_sha256 or lock.get("inventory_sha256") != inventory_digest(inventory):
        raise SourceError("corresponding_source_lock_stale")
    by_path = {entry["path"]: entry for entry in lock["files"]}
    if len(by_path) != len(lock["files"]) or set(by_path) != {item["path"] for item in inventory["files"]}:
        raise SourceError("corresponding_source_lock_stale")
    needed = []
    for item in inventory["files"]:
        entry = by_path[item["path"]]
        if entry["sha256"] != item["sha256"]:
            raise SourceError("corresponding_source_lock_stale")
        # What the bundled bytes declare themselves can only tighten the lock, never loosen it.
        offline = classify(item["licenses"]) if item["licenses"] else UNKNOWN
        if entry["obligation"] == NONE and offline == SOURCE:
            raise SourceError("corresponding_source_lock_inconsistent:" + item["path"])
        if entry["obligation"] not in (SOURCE, NONE, UNKNOWN):
            raise SourceError("corresponding_source_lock_invalid")
        if entry["obligation"] != NONE:
            needed.append(entry)
    jdk = inventory.get("jdk")
    if jdk:
        locked = lock.get("jdk") or {}
        if locked.get("sha256") != jdk["sha256"]:
            raise SourceError("corresponding_source_lock_stale")
        needed.append({**locked, "kind": "jdk", "licenses": [locked.get("license", "")],
                       "coordinates": f"{locked.get('implementor')} {locked.get('version')}"})
    return needed


def load_exceptions(path: Path = EXCEPTIONS_PATH) -> dict[str, dict]:
    """The components bundled without attached source, by component path.

    Each names the bundled file's SHA-256, a reason from ``EXCEPTION_REASONS``, a detail
    and at least one https upstream source location.
    """
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise SourceError("source_exceptions_invalid") from None
    if document.get("schema") != EXCEPTIONS_SCHEMA or not isinstance(document.get("components"), list):
        raise SourceError("source_exceptions_invalid")
    listed: dict[str, dict] = {}
    for record in document["components"]:
        component = record.get("component") if isinstance(record, dict) else None
        if not isinstance(component, str) or component in listed:
            raise SourceError("source_exceptions_invalid")
        upstream = record.get("upstream")
        if (not DIGEST.fullmatch(str(record.get("bundled_sha256", "")))
                or record.get("reason") not in EXCEPTION_REASONS or not str(record.get("detail", "")).strip()
                or not isinstance(upstream, list) or not upstream
                or not all(isinstance(item, dict) and str(item.get("url", "")).startswith("https://")
                           for item in upstream)):
            raise SourceError("source_exceptions_invalid:" + component)
        listed[component] = {"reason": record["reason"], "detail": record["detail"],
                             "bundled_sha256": record["bundled_sha256"], "upstream": upstream}
    return listed


def require_sources(entries: list[dict], exceptions: dict[str, dict] | None = None) -> list[dict]:
    """Every obligation has a pinned source, or a listed exception for exactly its bundled bytes.

    An exception that matches no obligation without source (the component is gone, now has a
    pinned source, or its bytes changed) fails too, so the list stays exactly what is bundled.
    """
    exceptions = load_exceptions() if exceptions is None else exceptions
    missing, used = [], set()
    for entry in entries:
        source = entry.get("source")
        if source:
            if not DIGEST.fullmatch(str(source.get("sha256", ""))) or not str(source.get("url", "")).startswith("https://"):
                raise SourceError("corresponding_source_pin_invalid:" + entry["path"])
        elif entry["path"] in exceptions:
            if exceptions[entry["path"]]["bundled_sha256"] != entry["sha256"]:
                raise SourceError("source_exception_stale:" + entry["path"])
            entry["exception"] = exceptions[entry["path"]]
            used.add(entry["path"])
        else:
            missing.append(entry["path"])
    if missing:
        raise SourceError("corresponding_source_unavailable:" + ",".join(sorted(missing)))
    unused = sorted(set(exceptions) - used)
    if unused:
        raise SourceError("source_exception_stale:" + ",".join(unused))
    return entries


def describe_exception(exception: dict) -> str:
    """One line for the notices: why no source is attached, and where the upstream source is."""
    locations = ", ".join(
        item["url"] + (f" ({item['ref']})" if item.get("ref") else f" (version {item['version']})"
                       if item.get("version") else "")
        for item in exception["upstream"])
    return f"not attached ({exception['reason']}; owner decision of 2026-10-30). Upstream source: {locations}"


# --- the release asset ---------------------------------------------------------------------------

def asset_name(version: str) -> str:
    return f"Cytellect-{version}-gpl-sources.zip"


def member_name(entry: dict) -> str:
    label = re.sub(r"[^A-Za-z0-9._+-]+", "_", entry["path"].replace("plugin:", "plugins/").replace("wheel:", "wheels/"))
    filename = urllib.parse.unquote(entry["source"]["url"].rsplit("/", 1)[-1])
    return f"sources/{label}/{re.sub(r'[^A-Za-z0-9._+-]+', '_', filename)}"


FIXED_TIME = (2026, 1, 1, 0, 0, 0)


def write_archive(path: Path, version: str, commit: str, entries: list[dict],
                  fetch: Callable[[dict], Path]) -> dict:
    """The release asset: each pinned source as downloaded, a manifest and a README."""
    records = []
    if path.exists():
        raise SourceError("gpl_sources_exists")
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        for entry in sorted(entries, key=lambda item: item["path"]):
            record = {"component": entry["path"], "bundled_sha256": entry["sha256"],
                      "coordinates": entry.get("coordinates"), "licenses": entry.get("licenses", []),
                      "obligation": entry.get("obligation", SOURCE)}
            if entry.get("source"):
                local = fetch(entry["source"])
                with local.open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                if digest != entry["source"]["sha256"]:
                    raise SourceError("corresponding_source_hash_mismatch:" + entry["path"])
                member = member_name(entry)
                info = zipfile.ZipInfo(member, FIXED_TIME)
                with archive.open(info, "w") as target, local.open("rb") as stream:
                    while chunk := stream.read(1024 * 1024):
                        target.write(chunk)
                record.update(member=member, sha256=digest, bytes=local.stat().st_size, url=entry["source"]["url"])
            else:
                record["exception"] = entry["exception"]
            records.append(record)
        manifest = {"schema": ARCHIVE_SCHEMA, "version": version, "source_commit": commit,
                    "installer": f"Cytellect-Setup-{version}.exe", "components": records}
        archive.writestr(zipfile.ZipInfo("manifest.json", FIXED_TIME), json.dumps(manifest, indent=2) + "\n")
        readme = (f"Corresponding source for Cytellect-Setup-{version}.exe (source commit {commit}).\n\n"
                  "The installer bundles these components unmodified. Each is licensed under a license that\n"
                  "requires its source with the binary (GPL, LGPL, MPL, EPL, CDDL and similar), or its license\n"
                  "could not be determined from what it carries. sources/ holds, for each one, the source that its\n"
                  "publisher released for exactly the bundled version, as downloaded; manifest.json lists the\n"
                  "bundled file's SHA-256, its license statements, the source's URL and SHA-256.\n\n"
                  "Components that manifest.json lists with an \"exception\" are bundled, but their source is not\n"
                  "in this archive (owner decision of 2026-10-30): no source published for exactly the bundled\n"
                  "bytes was found, its host could not be reached when the release was built, or the license\n"
                  "could not be determined. For each, \"exception\" gives the reason and the upstream source\n"
                  "location, with a tag or version where one is known.\n")
        archive.writestr(zipfile.ZipInfo("README.txt", FIXED_TIME), readme)
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    path.with_name(path.name + ".sha256").write_text(f"{digest}  {path.name}\n", encoding="ascii")
    return {"asset": path.name, "sha256": digest, "bytes": path.stat().st_size, "components": records}


# --- command line --------------------------------------------------------------------------------

def cached(cache: Path, url: str, expected: str) -> Path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from fiji_setup import download  # resumable, retried and hash-checked

    cache.mkdir(parents=True, exist_ok=True)
    target = cache / expected
    if target.is_file():
        with target.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() == expected:
                return target
    partial = cache / (expected + ".partial")
    download(url, partial, expected)
    partial.replace(target)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    lock = commands.add_parser("lock", help="Regenerate the lock from the pinned Windows Fiji (network)")
    lock.add_argument("--cache", type=Path, required=True, help="Content-addressed download cache")
    lock.add_argument("--output", type=Path, default=LOCK_PATH)
    lock.add_argument("--workers", type=int, default=12, help="Concurrent repository lookups")
    lock.add_argument("--fetch-sources", action="store_true",
                      help="Also download every pinned source into the cache and report the total size")
    args = parser.parse_args()
    fiji = json.loads((ROOT / "engines/fiji/runtime.lock.json").read_text(encoding="utf-8"))
    archive = fiji["fiji"]["windows-x64"]
    path = cached(args.cache, archive["url"], archive["sha256"])
    inventory = fiji_inventory(path, fiji["plugins"],
                               lambda plugin: cached(args.cache, plugin["url"], plugin["sha256"]).read_bytes())
    resolved = resolve(inventory, Resolver(disk_cached(args.cache / "lookups")), workers=args.workers,
                       log=lambda message: print(message, file=sys.stderr, flush=True))
    written = write_lock(args.output, archive["sha256"], inventory, resolved)
    report = dict(written["summary"])
    if args.fetch_sources:
        entries = [entry for entry in resolved["files"] + ([resolved["jdk"]] if resolved["jdk"] else [])
                   if entry and entry.get("source")]
        total = 0
        for entry in entries:
            total += cached(args.cache, entry["source"]["url"], entry["source"]["sha256"]).stat().st_size
        report["pinned_source_bytes"] = total
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    try:
        main()
    except SourceError as error:
        print("Corresponding source failed: " + str(error), file=sys.stderr)
        raise SystemExit(2) from None
