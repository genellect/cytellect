"""Corresponding source for the bundled copyleft software (scripts/corresponding_source.py).

Generated jars, wheels and archives only; every network lookup is replaced by a dictionary.
"""
import hashlib
import importlib.util
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


cs = load("corresponding_source")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()  # noqa: S324


def jar(coordinates=None, licenses=None, license_file=None, properties=True, scm=None, commit=None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        if commit:
            archive.writestr("META-INF/MANIFEST.MF", f"Manifest-Version: 1.0\nImplementation-Build: {commit}\n")
        if coordinates:
            group, artifact, version = coordinates.split(":")
            if properties:
                archive.writestr(f"META-INF/maven/{group}/{artifact}/pom.properties",
                                 f"groupId={group}\nartifactId={artifact}\nversion={version}\n")
            body = "".join(f"<license><name>{name}</name></license>" for name in licenses or [])
            source = f"<scm><url>{scm}</url></scm>" if scm else ""
            archive.writestr(f"META-INF/maven/{group}/{artifact}/pom.xml",
                             f"<project><licenses>{body}</licenses>{source}</project>" if licenses else "<project/>")
        if license_file:
            archive.writestr("META-INF/LICENSE.txt", license_file)
        archive.writestr("generated/Placeholder.class", coordinates or "generated")
    return buffer.getvalue()


GPL_JAR = jar("ome:formats-gpl:8.5.0", ["GNU General Public License v2+"])
BSD_JAR = jar("ome:formats-bsd:8.5.0", ["Simplified BSD License"])
BARE_JAR = jar("org.example:inherits:1.0")  # licenses only in its published parent POM
NO_COORDINATES_JAR = jar("org.example:shaded:2.0", ["GNU Lesser General Public License"], properties=False)
APACHE_FILE_JAR = jar(license_file="                                 Apache License\n Version 2.0, January 2004\n")
PLUGIN_JAR = jar("fr.inra.ijpb:MorphoLibJ_:1.6.5")
RELEASE = ('IMPLEMENTOR="Azul Systems, Inc."\nIMPLEMENTOR_VERSION="Zulu21.42+19-CA"\n'
           'JAVA_RUNTIME_VERSION="21.0.7+6-LTS"\nJAVA_VERSION="21.0.7"\nSOURCE=".:git:e59e98a59b70+"\n')


def fiji_archive(path: Path, extra=None) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Fiji/jars/bio-formats/formats-gpl-8.5.0.jar", GPL_JAR)
        archive.writestr("Fiji/jars/formats-bsd-8.5.0.jar", BSD_JAR)
        archive.writestr("Fiji/jars/inherits-1.0.jar", BARE_JAR)
        archive.writestr("Fiji/jars/shaded-2.0.jar", NO_COORDINATES_JAR)
        archive.writestr("Fiji/jars/apache-file.jar", APACHE_FILE_JAR)
        archive.writestr("Fiji/fiji-windows-x64.exe", b"MZ generated launcher")
        archive.writestr("Fiji/lib/win64/blosc.dll", b"MZ generated library")
        archive.writestr("Fiji/licenses/blosc.txt", "Redistribution and use in source and binary forms, with or without")
        archive.writestr("Fiji/java/win64/zulu-generated/release", RELEASE)
        archive.writestr("Fiji/java/win64/zulu-generated/lib/jrt-fs.jar", b"part of the JDK")
        archive.writestr("Fiji/java/win64/zulu-generated/bin/java.exe", b"MZ part of the JDK")
        for name, data in (extra or {}).items():
            archive.writestr(name, data)
    return path


PLUGINS = [{"path": "plugins/MorphoLibJ_-1.6.5.jar", "sha256": digest(PLUGIN_JAR), "license": "LGPL-3.0-or-later",
            "url": "https://sites.imagej.net/IJPB-plugins/plugins/MorphoLibJ_-1.6.5.jar-1",
            "source": "https://github.com/ijpb/MorphoLibJ"}]


def inventory(tmp_path, extra=None):
    return cs.fiji_inventory(fiji_archive(tmp_path / "fiji.zip", extra), PLUGINS, lambda plugin: PLUGIN_JAR)


SOURCES = {name: f"generated source of {name}".encode() for name in ("formats-gpl", "inherits", "shaded", "MorphoLibJ_")}
REPOSITORY = cs.MAVEN_REPOSITORIES[0]


def maven(coordinates: str, suffix: str) -> str:
    return f"{REPOSITORY}/{cs.maven_path(coordinates, suffix)}"


def published() -> dict[str, bytes]:
    """What the fake Maven repository and checksum search answer."""
    pages = {
        maven("org.example:inherits:1.0", ".pom"):
            b"<project><parent><groupId>org.example</groupId><artifactId>parent</artifactId>"
            b"<version>7</version></parent></project>",
        maven("org.example:parent:7", ".pom"):
            b"<project><licenses><license><name>Eclipse Public License 1.0</name></license></licenses></project>",
        cs.CENTRAL_SHA1_SEARCH.format(sha1=sha1(NO_COORDINATES_JAR)):
            json.dumps({"response": {"docs": [{"g": "org.example", "a": "shaded", "v": "2.0"}]}}).encode(),
    }
    for coordinates, data, name in (("ome:formats-gpl:8.5.0", GPL_JAR, "formats-gpl"),
                                    ("org.example:inherits:1.0", BARE_JAR, "inherits"),
                                    ("org.example:shaded:2.0", NO_COORDINATES_JAR, "shaded"),
                                    ("fr.inra.ijpb:MorphoLibJ_:1.6.5", PLUGIN_JAR, "MorphoLibJ_")):
        pages[maven(coordinates, ".jar.sha1")] = sha1(data).encode()
        pages[maven(coordinates, "-sources.jar")] = SOURCES[name]
        pages[maven(coordinates, "-sources.jar.sha1")] = sha1(SOURCES[name]).encode()
    return pages


def resolver(pages=None):
    pages = published() if pages is None else pages
    requested = []

    def get(url):
        requested.append(url)
        return pages.get(url)

    instance = cs.Resolver(get)
    instance.requested = requested
    return instance


@pytest.mark.parametrize(("statement", "expected"), [
    ("GNU General Public License v3+", cs.SOURCE),
    ("GPLv2 with Classpath exception", cs.SOURCE),
    ("GPL-2.0-only WITH Classpath-exception-2.0", cs.SOURCE),
    ("GNU Lesser General Public License Version 2.1, February 1999", cs.SOURCE),
    ("LGPL-3.0-or-later", cs.SOURCE),
    ("MPL 1.1", cs.SOURCE),
    ("Eclipse Public License - v 2.0", cs.SOURCE),
    ("CDDL + GPLv2 with classpath exception", cs.SOURCE),
    ("GNU Affero General Public License v3", cs.SOURCE),
    ("Part of R 2.14.2", cs.SOURCE),
    ("BSD-3-Clause AND LGPL-2.1-or-later", cs.SOURCE),
    ("Simplified BSD License", cs.NONE),
    ("The Apache Software License, Version 2.0", cs.NONE),
    ("MIT", cs.NONE),
    ("Public domain", cs.NONE),
    ("FTL OR GPL-2.0-or-later", cs.NONE),
    ("GPL-3.0-or-later WITH GCC-exception-3.1", cs.NONE),
    ("(MIT OR Apache-2.0) AND BSD-3-Clause", cs.NONE),
    ("BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0", cs.NONE),
    ("Janelia Farm Research Campus Software Copyright 1.1", cs.NONE),
    ("Proprietary terms of a generated vendor", cs.UNKNOWN),
    ("", cs.UNKNOWN),
])
def test_license_statements_are_classified_by_their_source_obligation(statement, expected):
    assert cs.obligation(statement) == expected


def test_several_statements_take_the_obligation_then_the_doubt():
    assert cs.classify(["Apache-2.0", "LGPL-2.1"]) == cs.SOURCE  # dual or combined: collect the source
    assert cs.classify(["Apache-2.0", "generated vendor terms"]) == cs.UNKNOWN
    assert cs.classify(["Apache-2.0", "MIT"]) == cs.NONE
    assert cs.classify([]) == cs.UNKNOWN


def test_jars_state_their_coordinates_and_licenses_themselves():
    assert cs.jar_evidence(GPL_JAR) == {"coordinates": "ome:formats-gpl:8.5.0",
                                        "licenses": ["GNU General Public License v2+"], "licenses_from": "embedded-pom"}
    assert cs.jar_evidence(BARE_JAR)["licenses"] == []
    assert cs.jar_evidence(NO_COORDINATES_JAR)["coordinates"] is None
    apache = cs.jar_evidence(APACHE_FILE_JAR)
    assert apache["licenses"] == ["META-INF/LICENSE.txt: apache license"] and apache["licenses_from"] == "jar-license-file"
    assert cs.jar_evidence(b"not a jar")["licenses"] == []


def test_inventory_lists_every_bundled_jar_binary_plugin_and_the_jdk(tmp_path):
    found = inventory(tmp_path)
    by_path = {item["path"]: item for item in found["files"]}
    # Everything outside the JDK's own directory, and the plugins under their install path.
    assert set(by_path) == {"Fiji/jars/bio-formats/formats-gpl-8.5.0.jar", "Fiji/jars/formats-bsd-8.5.0.jar",
                            "Fiji/jars/inherits-1.0.jar", "Fiji/jars/shaded-2.0.jar", "Fiji/jars/apache-file.jar",
                            "Fiji/fiji-windows-x64.exe", "Fiji/lib/win64/blosc.dll",
                            "plugin:plugins/MorphoLibJ_-1.6.5.jar"}
    assert by_path["Fiji/lib/win64/blosc.dll"]["licenses_from"] == "fiji-licenses-dir"
    assert by_path["Fiji/fiji-windows-x64.exe"]["licenses"] == ["Unlicense"]  # reviewed, with its reason
    assert by_path["Fiji/fiji-windows-x64.exe"]["licenses_from"].startswith("reviewed: Jaunch")
    assert by_path["plugin:plugins/MorphoLibJ_-1.6.5.jar"]["licenses"] == ["LGPL-3.0-or-later"]
    assert found["jdk"]["implementor"] == "Azul Systems, Inc." and found["jdk"]["version"] == "21.0.7+6-LTS"
    assert found["jdk"]["path"] == "Fiji/java/win64/zulu-generated/release"
    with pytest.raises(cs.SourceError, match="plugin_hash_mismatch"):
        cs.fiji_inventory(tmp_path / "fiji.zip", PLUGINS, lambda plugin: b"altered")


def test_lock_resolution_pins_exact_sources_for_every_obligation(tmp_path):
    lookups = resolver()
    resolved = cs.resolve(inventory(tmp_path), lookups)
    by_path = {item["path"]: item for item in resolved["files"]}
    gpl = by_path["Fiji/jars/bio-formats/formats-gpl-8.5.0.jar"]
    assert gpl["obligation"] == cs.SOURCE and gpl["binary_matches_repository"] is True
    assert gpl["source"] == {"url": maven("ome:formats-gpl:8.5.0", "-sources.jar"),
                             "sha256": digest(SOURCES["formats-gpl"]), "bytes": len(SOURCES["formats-gpl"]),
                             "kind": "maven-sources of the identical repository jar"}
    # The parent POM's EPL reaches a jar that declares nothing itself.
    inherits = by_path["Fiji/jars/inherits-1.0.jar"]
    assert inherits["licenses"] == ["Eclipse Public License 1.0"] and inherits["obligation"] == cs.SOURCE
    assert inherits["licenses_from"] == "repository-pom org.example:parent:7" and inherits["source"]
    # A jar without pom.properties is identified by the checksum of its exact bytes.
    shaded = by_path["Fiji/jars/shaded-2.0.jar"]
    assert shaded["coordinates"] == "org.example:shaded:2.0" and shaded["coordinates_from"] == "maven-checksum-search"
    assert shaded["source"]["sha256"] == digest(SOURCES["shaded"])
    assert by_path["plugin:plugins/MorphoLibJ_-1.6.5.jar"]["source"]["sha256"] == digest(SOURCES["MorphoLibJ_"])
    for permissive in ("Fiji/jars/formats-bsd-8.5.0.jar", "Fiji/jars/apache-file.jar", "Fiji/lib/win64/blosc.dll",
                       "Fiji/fiji-windows-x64.exe"):
        assert by_path[permissive]["obligation"] == cs.NONE and by_path[permissive]["source"] is None
    # No source is fetched for a component without an obligation.
    assert not any(url.endswith("formats-bsd-8.5.0-sources.jar") for url in lookups.requested)
    assert any(url.endswith("formats-gpl-8.5.0-sources.jar") for url in lookups.requested)
    assert resolved["jdk"]["obligation"] == cs.SOURCE and resolved["jdk"]["source"] is None  # not published here


def resolved_entry(found, pages, name):
    return next(item for item in cs.resolve(found, resolver(pages))["files"] if item["path"].endswith(name))


def test_a_rebuilt_jar_takes_its_build_commit_then_its_declared_release(tmp_path):
    pages = published()
    pages[maven("ome:formats-gpl:8.5.0", ".jar.sha1")] = b"0" * 40  # uploaded separately, not byte-identical
    gpl = resolved_entry(inventory(tmp_path), pages, "formats-gpl-8.5.0.jar")
    assert gpl["binary_matches_repository"] is False
    assert gpl["source"]["kind"] == "maven-sources of the release version the jar declares"
    # A jar that records the commit it was built from takes that commit's archive first.
    built = jar("sc.fiji:Cell_Counter:3.0.0", ["GNU General Public License v3+"],
                scm="https://github.com/fiji/Cell_Counter", commit="d" * 40)
    archive = "https://codeload.github.com/fiji/Cell_Counter/tar.gz/" + "d" * 40
    found = cs.fiji_inventory(fiji_archive(tmp_path / "built.zip", {"Fiji/plugins/Cell_Counter-3.0.0.jar": built}),
                              PLUGINS, lambda plugin: PLUGIN_JAR)
    pages[archive] = b"generated commit archive"
    entry = resolved_entry(found, pages, "Cell_Counter-3.0.0.jar")
    assert entry["build"] == {"repository": "fiji/Cell_Counter", "commit": "d" * 40}
    assert entry["source"] == {"url": archive, "sha256": digest(b"generated commit archive"), "bytes": 24,
                               "kind": "github archive of the commit the jar was built from"}
    # A snapshot or a platform-specific jar has no declared release to fall back on.
    snapshot = jar("sc.fiji:fiji:2.18.1-SNAPSHOT", ["GNU General Public License v3+"])
    natives = jar("org.openjfx:javafx-graphics:23.0.2", ["GPLv2+CE"])
    extra = {"Fiji/jars/fiji-2.18.1-SNAPSHOT.jar": snapshot, "Fiji/jars/win64/javafx-graphics-23.0.2-win.jar": natives}
    found = cs.fiji_inventory(fiji_archive(tmp_path / "other.zip", extra), PLUGINS, lambda plugin: PLUGIN_JAR)
    for name in ("fiji-2.18.1-SNAPSHOT.jar", "javafx-graphics-23.0.2-win.jar"):
        entry = resolved_entry(found, pages, name)
        assert entry["obligation"] == cs.SOURCE and entry["source"] is None


def test_a_published_source_that_fails_its_checksum_stops_the_lock(tmp_path):
    pages = published()
    pages[maven("ome:formats-gpl:8.5.0", "-sources.jar.sha1")] = b"0" * 40
    with pytest.raises(cs.SourceError, match="published_checksum_mismatch"):
        cs.resolve(inventory(tmp_path), resolver(pages))


def locked(tmp_path, pages=None):
    found = inventory(tmp_path)
    resolved = cs.resolve(found, resolver(pages))
    resolved["jdk"]["source"] = {"url": "https://cdn.example.org/jdk-src.zip", "sha256": digest(b"jdk source"),
                                 "bytes": 10}
    lock = cs.write_lock(tmp_path / "lock.json", "f" * 64, found, resolved)
    return found, json.loads((tmp_path / "lock.json").read_text()), lock


def test_the_build_takes_obligations_only_from_a_lock_of_the_same_bytes(tmp_path):
    found, lock, written = locked(tmp_path)
    assert written["summary"]["without_source"] == []
    needed = cs.obligations(lock, found, "f" * 64)
    assert {entry["path"] for entry in needed} == {
        "Fiji/jars/bio-formats/formats-gpl-8.5.0.jar", "Fiji/jars/inherits-1.0.jar", "Fiji/jars/shaded-2.0.jar",
        "plugin:plugins/MorphoLibJ_-1.6.5.jar", "Fiji/java/win64/zulu-generated/release"}
    assert cs.require_sources(needed, {}) == needed
    with pytest.raises(cs.SourceError, match="corresponding_source_lock_stale"):
        cs.obligations(lock, found, "e" * 64)  # another Fiji archive
    changed = cs.fiji_inventory(fiji_archive(tmp_path / "other.zip", {"Fiji/jars/new-1.0.jar": BSD_JAR}), PLUGINS,
                                lambda plugin: PLUGIN_JAR)
    with pytest.raises(cs.SourceError, match="corresponding_source_lock_stale"):
        cs.obligations(lock, changed, "f" * 64)  # a jar the lock has not classified


def test_a_lock_cannot_waive_what_a_bundled_jar_declares(tmp_path):
    found, lock, _ = locked(tmp_path)
    for entry in lock["files"]:
        if entry["path"].endswith("formats-gpl-8.5.0.jar"):
            entry["obligation"] = cs.NONE
    with pytest.raises(cs.SourceError, match="lock_inconsistent:Fiji/jars/bio-formats/formats-gpl-8.5.0.jar"):
        cs.obligations(lock, found, "f" * 64)


def test_an_obligation_without_source_fails_unless_listed_with_a_reason(tmp_path):
    found, lock, _ = locked(tmp_path)
    lock["jdk"]["source"] = None
    needed = cs.obligations(lock, found, "f" * 64)
    with pytest.raises(cs.SourceError, match="corresponding_source_unavailable:Fiji/java/win64/zulu-generated/release"):
        cs.require_sources([dict(entry) for entry in needed], {})
    excepted = cs.require_sources([dict(entry) for entry in needed],
                                  {"Fiji/java/win64/zulu-generated/release": "generated reason"})
    assert next(entry for entry in excepted if entry["kind"] == "jdk")["exception"] == "generated reason"
    # An undetermined license counts as an obligation too.
    for entry in lock["files"]:
        if entry["path"] == "Fiji/jars/formats-bsd-8.5.0.jar":
            entry.update(obligation=cs.UNKNOWN, source=None)
    with pytest.raises(cs.SourceError, match="Fiji/jars/formats-bsd-8.5.0.jar"):
        cs.require_sources(cs.obligations(lock, found, "f" * 64), {"Fiji/java/win64/zulu-generated/release": "r"})


def wheel(name: str, version: str, expression=None, classifier=None, vendored=()) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        info = f"{name}-{version}.dist-info"
        metadata = f"Metadata-Version: 2.4\nName: {name}\nVersion: {version}\n"
        metadata += f"License-Expression: {expression}\n" if expression else ""
        metadata += f"Classifier: License :: OSI Approved :: {classifier}\n" if classifier else ""
        archive.writestr(f"{info}/METADATA", metadata)
        body = "".join(f"Name: {item}\nLicense: {license}\n\n" for item, license in vendored)
        archive.writestr(f"{info}/licenses/LICENSE.txt", "Generated license text\n\n" + body)
    return buffer.getvalue()


def test_wheel_obligations_use_metadata_vendored_libraries_and_the_uv_lock_sdist(tmp_path):
    files = {
        "numpy-2.5.3-cp314-cp314-win_amd64.whl": wheel(
            "numpy", "2.5.3", "BSD-3-Clause", vendored=[("GCC runtime library", "GPL-3.0-or-later WITH GCC-exception-3.1")]),
        "matplotlib-3.11.2-cp314-cp314-win_amd64.whl": wheel(
            "matplotlib", "3.11.2", classifier="Python Software Foundation License",
            vendored=[("FreeType", "FTL OR GPL-2.0-or-later")]),
        "fastremap-1.0-cp314-cp314-win_amd64.whl": wheel(
            "fastremap", "1.0", classifier="GNU Lesser General Public License v3 (LGPLv3)"),
        "vendored-2.0-py3-none-any.whl": wheel("vendored", "2.0", "MIT", vendored=[("libgen", "LGPL-2.1-or-later")]),
    }
    paths = []
    for name, data in files.items():
        (tmp_path / name).write_bytes(data)
        paths.append(tmp_path / name)
    uv_lock = (
        '[[package]]\nname = "fastremap"\nversion = "1.0"\n'
        f'sdist = {{ url = "https://files.example.org/fastremap-1.0.tar.gz", hash = "sha256:{"a" * 64}", size = 5 }}\n'
        '[[package]]\nname = "vendored"\nversion = "2.0"\n')
    entries = {entry["path"]: entry for entry in cs.wheel_obligations(paths, uv_lock)}
    assert set(entries) == {"wheel:fastremap-1.0-cp314-cp314-win_amd64.whl", "wheel:vendored-2.0-py3-none-any.whl"}
    assert entries["wheel:fastremap-1.0-cp314-cp314-win_amd64.whl"]["source"] == {
        "url": "https://files.example.org/fastremap-1.0.tar.gz", "sha256": "a" * 64, "bytes": 5}
    with pytest.raises(cs.SourceError, match="unavailable:wheel:vendored-2.0"):
        cs.require_sources(list(entries.values()), {})


def test_the_release_asset_holds_each_source_with_a_manifest(tmp_path):
    found, lock, _ = locked(tmp_path)
    needed = cs.require_sources(cs.obligations(lock, found, "f" * 64), {})
    blobs = {digest(data): data for data in [*SOURCES.values(), b"jdk source"]}

    def fetch(source):
        path = tmp_path / "cache" / source["sha256"]
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(blobs[source["sha256"]])
        return path

    asset = tmp_path / "out" / cs.asset_name("0.1.0-local.21")
    asset.parent.mkdir()
    result = cs.write_archive(asset, "0.1.0-local.21", "a" * 40, needed, fetch)
    assert result["asset"] == "Cytellect-0.1.0-local.21-gpl-sources.zip"
    assert (tmp_path / "out/Cytellect-0.1.0-local.21-gpl-sources.zip.sha256").read_text() == (
        f"{digest(asset.read_bytes())}  {asset.name}\n")
    with zipfile.ZipFile(asset) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["installer"] == "Cytellect-Setup-0.1.0-local.21.exe"
        for record in manifest["components"]:
            assert digest(archive.read(record["member"])) == record["sha256"]
        assert "README.txt" in archive.namelist()
    assert len(manifest["components"]) == 5
    gpl = next(record for record in manifest["components"] if record["component"].endswith("formats-gpl-8.5.0.jar"))
    assert gpl["member"] == ("sources/Fiji_jars_bio-formats_formats-gpl-8.5.0.jar/formats-gpl-8.5.0-sources.jar")
    assert gpl["bundled_sha256"] == digest(GPL_JAR) and gpl["url"].startswith(REPOSITORY)
    # A download that does not match its pin never enters the asset.
    blobs[digest(b"jdk source")] = b"altered"
    with pytest.raises(cs.SourceError, match="hash_mismatch"):
        cs.write_archive(tmp_path / "out/second.zip", "0.1.0-local.21", "a" * 40, needed, fetch)


def test_the_committed_lock_describes_the_pinned_windows_fiji_and_every_plugin():
    lock = cs.load_lock()
    fiji = json.loads((ROOT / "engines/fiji/runtime.lock.json").read_text())
    assert lock["fiji_windows_x64_sha256"] == fiji["fiji"]["windows-x64"]["sha256"]
    by_path = {entry["path"]: entry for entry in lock["files"]}
    for plugin in fiji["plugins"]:
        assert by_path["plugin:" + plugin["path"]]["sha256"] == plugin["sha256"]
    assert by_path["plugin:plugins/MorphoLibJ_-1.6.5.jar"]["obligation"] == cs.SOURCE
    for entry in lock["files"]:
        assert entry["obligation"] in (cs.SOURCE, cs.NONE, cs.UNKNOWN)
        assert entry["obligation"] == cs.classify(entry["licenses"]), entry["path"]
        if entry["source"]:
            assert cs.DIGEST.fullmatch(entry["source"]["sha256"]) and entry["source"]["url"].startswith("https://")
    assert lock["summary"]["source"] == sum(1 for entry in lock["files"] if entry["obligation"] == cs.SOURCE)
    assert lock["jdk"]["obligation"] == cs.SOURCE


def test_the_python_runtime_and_uv_are_classified_from_their_pins():
    runtime = json.loads((ROOT / "engines/python/windows-runtime.lock.json").read_text())
    uv = {"version": "0.12.2", "sha256": "a" * 64, "license": "Apache-2.0 OR MIT"}
    assert cs.runtime_obligations(runtime, uv) == []  # PSF, and Apache-2.0 OR MIT: no source obligation
    runtime["notices"] = [{"scope": "base", "license": "GPL-3.0-only"}]
    needed = cs.runtime_obligations(runtime, uv)
    assert [entry["path"] for entry in needed] == ["python:" + runtime["python"]["version"]]
    with pytest.raises(cs.SourceError, match="unavailable:python:"):
        cs.require_sources(needed, {})
