"""Build the browser (Pyodide) runtime files for the public showcase.

Writes ``apps/web/public/showcase/runtime/`` (the Cytellect wheel, exact
pure-Python dependency wheels, a static Noto Sans JP face for Japanese figure
labels, their licenses and notices) and
``apps/web/src/lib/showcase/runtime-config.json``. Compiled packages (NumPy,
SciPy, pandas, scikit-image, statsmodels, Matplotlib, pydantic, SQLAlchemy,
Pillow) come from the version-pinned Pyodide CDN and are not redistributed here.

Every dependency wheel is the exact uv.lock version and hash. The font is the
official Google Fonts variable file pinned by SHA-256 (the same input recorded
by build_marketing_media.py), instanced at weight 400 with fontTools.

``--check`` rebuilds into a scratch directory and fails if a committed file or
the configuration differs (for example, Python sources changed without
rebuilding the wheel). Downloads use ``--cache`` (outside the checkout).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "apps/web/public/showcase/runtime"
CONFIG = ROOT / "apps/web/src/lib/showcase/runtime-config.json"
ALLOWLIST = ROOT / "fixtures/public/allowlist.json"
PACKAGE_JSON = ROOT / "services/showcase/pyodide/package.json"
MANIFEST = ROOT / "apps/web/public/showcase/manifest.json"
# Inputs of the Cytellect wheel; their committed state is the runtime's source revision.
RUNTIME_SOURCES = ["packages", "services", "pyproject.toml", "uv.lock"]

PYODIDE_VERSION = "314.0.7"
INDEX_URL = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/"
# Loaded with pyodide.loadPackage; their Pyodide dependencies resolve automatically.
PYODIDE_PACKAGES = ["numpy", "scipy", "pandas", "scikit-image", "statsmodels", "matplotlib", "pydantic",
                    "sqlalchemy", "pillow", "markupsafe", "typing-inspection"]
# Pure-Python wheels at their exact uv.lock versions, unpacked in this order. The
# reviewed SPDX identifiers are checked against each wheel's own metadata.
VENDORED = {
    "typing-extensions": "PSF-2.0", "idna": "BSD-3-Clause", "anyio": "MIT", "starlette": "BSD-3-Clause", "annotated-doc": "MIT",
    "opentelemetry-api": "Apache-2.0", "fastapi": "MIT", "python-multipart": "Apache-2.0",
    "mako": "MIT", "alembic": "MIT", "tifffile": "BSD-3-Clause", "roifile": "BSD-3-Clause",
    "defusedxml": "PSF-2.0",
}
FONT_SOURCE = "https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/notosansjp/"
FONT_INPUT = ("NotoSansJP%5Bwght%5D.ttf", "c2f3b4d463500a2ddcd3849cded1fceeb9fd6d1c32e6cbecd568453ba50fc68f")
FONT_LICENSE = ("OFL.txt", "1c05c68c34f9708415aada51f17e1b0092d2cea709bf4a94cd38114f9e73d7d9")
FONT_FILE = "NotoSansJP-Regular.ttf"
FONT_LICENSE_FILE = "NotoSansJP-OFL.txt"
NOTICES = "THIRD_PARTY_NOTICES.txt"
PROVENANCE = "https://github.com/google/fonts/tree/main/ofl/notosansjp"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def locked_wheels() -> dict[str, dict]:
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    found = {}
    for package in lock["package"]:
        if package["name"] not in VENDORED:
            continue
        wheels = [w for w in package.get("wheels", []) if w["url"].endswith("-none-any.whl")]
        if len(wheels) != 1:
            raise SystemExit(f"{package['name']}: expected one pure-Python wheel in uv.lock")
        wheel = wheels[0]
        found[package["name"]] = {"version": package["version"], "url": wheel["url"],
                                  "sha256": wheel["hash"].removeprefix("sha256:"),
                                  "file": wheel["url"].rsplit("/", 1)[1]}
    missing = set(VENDORED) - set(found)
    if missing:
        raise SystemExit("Not in uv.lock: " + ", ".join(sorted(missing)))
    return found


def fetch(url: str, expected: str, cache: Path, name: str) -> bytes:
    target = cache / f"{expected}-{name}"
    if target.is_file():
        data = target.read_bytes()
    else:
        with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310 - pinned https sources
            data = response.read()
    if sha256(data) != expected:
        raise SystemExit(f"{name}: SHA-256 mismatch; review the upstream source before updating")
    target.write_bytes(data)
    return data


def build_cytellect_wheel(scratch: Path) -> tuple[str, bytes]:
    out = scratch / "wheel"
    environment = {**os.environ, "SOURCE_DATE_EPOCH": "315532800"}
    subprocess.run(["uv", "build", "--wheel", "--out-dir", str(out), str(ROOT)], check=True,
                   stdout=subprocess.DEVNULL, env=environment)
    wheels = sorted(out.glob("cytellect-*.whl"))
    if len(wheels) != 1:
        raise SystemExit("Expected exactly one Cytellect wheel")
    return wheels[0].name, wheels[0].read_bytes()


def static_font(variable: bytes) -> bytes:
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer

    font = TTFont(io.BytesIO(variable), recalcTimestamp=False)
    instance = instancer.instantiateVariableFont(font, {"wght": 400}, updateFontNames=True)
    if instance["OS/2"].usWeightClass != 400 or instance["name"].getDebugName(1) != "Noto Sans JP":
        raise SystemExit("Unexpected Noto Sans JP instance")
    buffer = io.BytesIO()
    instance.save(buffer)
    return buffer.getvalue()


def wheel_notices(name: str, data: bytes, spdx: str) -> list[tuple[str, str]]:
    from email.parser import Parser

    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        metadata_name = next(n for n in names if n.endswith(".dist-info/METADATA"))
        metadata = Parser().parsestr(archive.read(metadata_name).decode("utf-8"))
        declared = " ".join(filter(None, [metadata.get("License-Expression"), metadata.get("License"),
                                          *metadata.get_all("Classifier", [])]))
        tokens = {"MIT": "MIT", "BSD-3-Clause": "BSD", "Apache-2.0": "Apache", "PSF-2.0": "Python Software Foundation"}
        if spdx not in declared and tokens[spdx] not in declared:
            raise SystemExit(f"{name}: wheel metadata no longer declares {spdx}; review the license")
        texts = []
        for member in names:
            path = PurePosixPath(member)
            if ".dist-info" not in path.parts[0]:
                continue
            lowered = [part.lower() for part in path.parts]
            if "licenses" in lowered or path.name.upper().startswith(("LICENSE", "LICENCE", "NOTICE", "COPYING")):
                texts.append((member, archive.read(member).decode("utf-8", errors="replace")))
    if not texts:
        raise SystemExit(f"{name}: wheel has no license text")
    return texts


def build(output: Path, cache: Path, font_source: Path | None) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    wheels = locked_wheels()
    entries, allow, notices = [], {}, []
    for name, spdx in VENDORED.items():
        record = wheels[name]
        data = fetch(record["url"], record["sha256"], cache, record["file"])
        (output / record["file"]).write_bytes(data)
        entries.append({"file": record["file"], "sha256": record["sha256"]})
        allow[record["file"]] = {"sha256": record["sha256"], "source": record["url"], "license": spdx}
        for member, text in wheel_notices(name, data, spdx):
            notices.append((f"{name} {record['version']} ({spdx}) — {member}", text))
    with tempfile.TemporaryDirectory() as scratch:
        wheel_name, wheel = build_cytellect_wheel(Path(scratch))
    (output / wheel_name).write_bytes(wheel)
    entries.append({"file": wheel_name, "sha256": sha256(wheel)})
    allow[wheel_name] = {"sha256": sha256(wheel), "source": "Built from this repository by scripts/build_showcase_runtime.py",
                         "license": "Apache-2.0"}
    if font_source is not None:
        variable = (font_source / "NotoSansJP[wght].ttf").read_bytes()
        license_text = (font_source / "OFL.txt").read_bytes()
        if sha256(variable) != FONT_INPUT[1] or sha256(license_text) != FONT_LICENSE[1]:
            raise SystemExit("Font input changed; review provenance first")
    else:
        variable = fetch(FONT_SOURCE + FONT_INPUT[0], FONT_INPUT[1], cache, "NotoSansJP-wght.ttf")
        license_text = fetch(FONT_SOURCE + FONT_LICENSE[0], FONT_LICENSE[1], cache, "NotoSansJP-OFL.txt")
    font = static_font(variable)
    (output / FONT_FILE).write_bytes(font)
    (output / FONT_LICENSE_FILE).write_bytes(license_text)
    allow[FONT_FILE] = {"sha256": sha256(font), "source": PROVENANCE, "license": "OFL-1.1",
                        "derivation": f"fontTools wght=400 static instance of NotoSansJP[wght].ttf sha256 {FONT_INPUT[1]}"}
    allow[FONT_LICENSE_FILE] = {"sha256": FONT_LICENSE[1], "source": PROVENANCE, "license": "OFL-1.1"}
    notices.append((f"Noto Sans JP ({FONT_FILE}, OFL-1.1) — {FONT_LICENSE_FILE}", license_text.decode("utf-8")))
    header = [
        "Cytellect showcase browser runtime — third-party licenses and notices", "",
        "This directory redistributes the wheels and font listed below. Each wheel also",
        "contains its own license files. Cytellect's own code is Apache-2.0.", "",
        f"Pyodide {PYODIDE_VERSION} (MPL-2.0) and its packages ({', '.join(PYODIDE_PACKAGES)} and their",
        f"dependencies) are loaded from {INDEX_URL} under their own licenses;",
        "they are not redistributed here. See https://github.com/pyodide/pyodide/blob/main/LICENSE", "",
    ]
    body = []
    for title, text in notices:
        body.extend(["=" * 72, title, "-" * 72, text.replace("\r\n", "\n").replace("\r", "\n").rstrip(), ""])
    notice_bytes = ("\n".join(header + body) + "\n").encode("utf-8")
    (output / NOTICES).write_bytes(notice_bytes)
    allow[NOTICES] = {"sha256": sha256(notice_bytes), "source": "Generated by scripts/build_showcase_runtime.py",
                      "license": "Apache-2.0 AND MIT AND BSD-3-Clause AND PSF-2.0 AND OFL-1.1"}
    config = {"pyodideVersion": PYODIDE_VERSION, "indexURL": INDEX_URL, "packages": PYODIDE_PACKAGES,
              "wheels": entries, "fonts": [{"file": FONT_FILE, "sha256": sha256(font)}]}
    return {"config": config, "allow": allow}


def source_commit() -> str:
    """The commit whose tree reproduces the runtime, marked when its inputs have uncommitted changes."""
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--", *RUNTIME_SOURCES], cwd=ROOT, text=True).strip()
    return head + ("+uncommitted" if dirty else "")


def manifest_files(manifest: dict, built: dict) -> dict:
    """The demo manifest's file list with the runtime entries replaced by the built ones."""
    files = {key: value for key, value in manifest.get("files", {}).items() if not key.startswith("runtime/")}
    files.update({f"runtime/{name}": {"sha256": entry["sha256"], "bytes": (RUNTIME / name).stat().st_size if (RUNTIME / name).is_file() else None}
                  for name, entry in built["allow"].items()})
    return dict(sorted(files.items()))


def config_text(config: dict) -> str:
    return json.dumps(config, ensure_ascii=False, indent=2) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, help="Download cache outside the checkout")
    parser.add_argument("--font-source", type=Path, help="Directory with the official NotoSansJP[wght].ttf and OFL.txt")
    parser.add_argument("--check", action="store_true", help="Verify committed files instead of writing them")
    args = parser.parse_args()
    if json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))["devDependencies"]["pyodide"] != PYODIDE_VERSION:
        raise SystemExit("services/showcase/pyodide/package.json pins a different Pyodide version")
    with tempfile.TemporaryDirectory() as scratch:
        cache = args.cache or Path(scratch) / "cache"
        if cache.resolve().is_relative_to(ROOT):
            raise SystemExit("Use a cache directory outside the checkout")
        cache.mkdir(parents=True, exist_ok=True)
        output = Path(scratch) / "runtime" if args.check else RUNTIME
        if not args.check and RUNTIME.exists():
            shutil.rmtree(RUNTIME)
        built = build(output, cache, args.font_source)
        allowlist = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
        prefix = RUNTIME.relative_to(ROOT).as_posix() + "/"
        registered = {prefix + name: entry for name, entry in built["allow"].items()}
        if args.check:
            problems = []
            if not CONFIG.is_file() or CONFIG.read_text(encoding="utf-8") != config_text(built["config"]):
                problems.append("runtime-config.json")
            for name, entry in built["allow"].items():
                committed = RUNTIME / name
                if not committed.is_file() or sha256(committed.read_bytes()) != entry["sha256"]:
                    problems.append(name)
                if allowlist.get(prefix + name) != entry:
                    problems.append(f"allowlist:{name}")
            manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
            if manifest.get("files") != manifest_files(manifest, built):
                problems.append("manifest.json files")
            extra = {p.name for p in RUNTIME.iterdir()} - set(built["allow"]) if RUNTIME.is_dir() else set()
            problems.extend(sorted(f"unexpected:{name}" for name in extra))
            if problems:
                raise SystemExit("Showcase runtime is stale; run scripts/build_showcase_runtime.py: " + ", ".join(problems))
            print(json.dumps({"status": "current", "files": len(built["allow"])}))
            return
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(config_text(built["config"]), encoding="utf-8", newline="\n")
        allowlist = {key: value for key, value in allowlist.items() if not key.startswith(prefix)}
        allowlist.update(registered)
        ALLOWLIST.write_text(json.dumps(allowlist, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["files"] = manifest_files(manifest, built)
        # generated_from_commit records the seed and recordings; the runtime is rebuilt on its own.
        manifest["runtime_generated_from_commit"] = source_commit()
        MANIFEST.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        size = sum((RUNTIME / name).stat().st_size for name in built["allow"])
        print(json.dumps({"status": "written", "files": len(built["allow"]), "bytes": size}))


if __name__ == "__main__":
    sys.exit(main())
