"""The bundled Noto Sans JP subset covers every character the web UI can show.

A character missing from the subset falls back to a system font and is drawn in a
different face mid-sentence. Regenerate with scripts/build_marketing_media.py --fonts-only.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps/web/src"


def test_font_subset_covers_ui_text():
    manifest = json.loads((ROOT / "apps/web/public/fonts/subset-manifest.json").read_text(encoding="utf-8"))
    covered = set(manifest["requested_codepoints"])
    sources = [*WEB.glob("components/**/*.tsx"), *WEB.glob("app/**/*.tsx"), *WEB.glob("lib/*.ts"), *WEB.glob("lib/*catalog*.json")]
    missing = {}
    for path in sources:
        for char in path.read_text(encoding="utf-8"):
            if ord(char) not in covered:
                missing.setdefault(char, path.relative_to(ROOT).as_posix())
    assert not missing, f"Regenerate the font subset; missing: {missing}"
