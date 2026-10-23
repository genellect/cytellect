"""Download the adopted LP film sources into .cache/lp_film/sources/ and verify their SHA-256.

Usage: python scripts/lp_film/fetch_sources.py [--role hero hero-fallback ...]
The originals are third-party stock and are never committed; see sources.json and docs/lp-art-direction.md.
"""

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = Path(__file__).with_name("sources.json")
CACHE = ROOT / ".cache" / "lp_film" / "sources"
USER_AGENT = "Mozilla/5.0 (compatible; cytellect-lp-film; +https://github.com/genellect/cytellect)"


def source_path(source: dict) -> Path:
    return CACHE / f"{source['id']}.{'mp4' if source['kind'] == 'video' else 'jpg'}"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(source: dict) -> bool:
    path = source_path(source)
    if not (path.exists() and sha256(path) == source["sha256"]):
        request = urllib.request.Request(source["download"], headers={"User-Agent": USER_AGENT})
        partial = path.with_suffix(path.suffix + ".part")
        with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as handle:
            while block := response.read(1 << 20):
                handle.write(block)
        partial.replace(path)
    actual = sha256(path)
    if actual != source["sha256"]:
        print(f"MISMATCH {source['id']}: expected {source['sha256']}, got {actual}", file=sys.stderr)
        return False
    print(f"ok {source['id']} -> {path.relative_to(ROOT)}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--role", nargs="*", help="only these roles (hero, hero-fallback, atmosphere, reserve)"
    )
    args = parser.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    sources = json.loads(MANIFEST.read_text(encoding="utf-8"))["sources"]
    selected = [s for s in sources if not args.role or s["role"] in args.role]
    if not all([fetch(source) for source in selected]):
        raise SystemExit("Some sources did not match their recorded SHA-256; do not use them until reviewed.")


if __name__ == "__main__":
    main()
