"""Toolchain versions have one source each; every other pin in the repository must agree with it.

Node: .node-version. Python (Linux CI): the Docker base image; .python-version names its minor version.
pnpm: package.json packageManager.
uv: scripts/build_local_bundle.py UV_VERSION. Python on Windows: engines/python/windows-runtime.lock.json.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINNED_FILES = [
    *sorted((ROOT / ".github/workflows").glob("*.yml")),
    *sorted((ROOT / "infra").glob("Dockerfile*")),
    ROOT / ".claude/cloud-setup.sh",
    ROOT / ".codex/setup.sh",
    ROOT / "scripts/build_local_bundle.py",
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def found(pattern: str) -> dict[str, set[str]]:
    versions: dict[str, set[str]] = {}
    for path in PINNED_FILES:
        for version in re.findall(pattern, read(path)):
            versions.setdefault(version, set()).add(path.name)
    return versions


def test_node_has_one_version():
    expected = read(ROOT / ".node-version").strip()
    assert re.fullmatch(r"\d+\.\d+\.\d+", expected)
    assert set(found(r"\bnode:(\d+\.\d+\.\d+)")) == {expected}
    assert found(r"node-version: \"?([\d.]+)") == {}, "use node-version-file: .node-version"
    assert re.search(rf'"node": ">={expected.split(".")[0]} <', read(ROOT / "package.json"))


def test_python_has_one_linux_version_and_one_windows_version():
    linux = found(r"\bpython:(\d+\.\d+\.\d+)-")
    assert len(linux) == 1, linux
    (expected,) = linux
    # uv cannot always download the newest patch, so developers pin only the minor version.
    assert read(ROOT / ".python-version").strip() == expected.rsplit(".", 1)[0]
    windows = json.loads(read(ROOT / "engines/python/windows-runtime.lock.json"))["python"]["version"]
    assert set(found(r"python-version: \"?([\d.]+)")) == {expected, windows}


def test_pnpm_has_one_version():
    expected = json.loads(read(ROOT / "package.json"))["packageManager"].removeprefix("pnpm@")
    assert set(found(r"pnpm@(\d+\.\d+\.\d+)")) == {expected}


def test_uv_has_one_version():
    expected = re.search(r'UV_VERSION = "([\d.]+)"', read(ROOT / "scripts/build_local_bundle.py")).group(1)
    assert set(found(r"uv==(\d+\.\d+\.\d+)")) == {expected}


def test_a_disagreeing_pin_is_reported(tmp_path):
    stale = tmp_path / "Dockerfile.stale"
    stale.write_text("FROM node:24.1.0\nRUN npm install --global pnpm@10.0.0\n", encoding="utf-8")
    PINNED_FILES.append(stale)
    try:
        assert "24.1.0" in found(r"\bnode:(\d+\.\d+\.\d+)")
        assert "10.0.0" in found(r"pnpm@(\d+\.\d+\.\d+)")
    finally:
        PINNED_FILES.remove(stale)
