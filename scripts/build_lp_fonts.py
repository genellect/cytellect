"""Display typefaces of the landing page, subset to the characters the page uses.

The LP sets its statements in Noto Serif JP, the English headline in Instrument Serif, and its
chapter labels in IBM Plex Mono (docs/lp-art-direction.md). All three are OFL-1.1 fonts from the
Google Fonts repository. The script downloads the official files once into .cache/lp_fonts,
checks their SHA-256, subsets them to the characters in the LP components, and writes
apps/web/public/fonts/lp/ with the licenses, a manifest, and the public allowlist entries.

    python3 scripts/build_lp_fonts.py

Rerun it whenever the LP text changes; tests/test_web_font_subset.py fails until then.
"""
from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache/lp_fonts"
OUT = ROOT / "apps/web/public/fonts/lp"
REPO = "https://raw.githubusercontent.com/google/fonts/main/"

# file in the Google Fonts repository -> SHA-256 of the version this LP was built from
INPUTS = {
    "ofl/notoserifjp/NotoSerifJP[wght].ttf": "2fd527ba12b6a44ec30d796d633360da0aeba6c5d4af1304ce12bb4dc15a7dfc",
    "ofl/notoserifjp/OFL.txt": "5e0da210fb04058a8c0087985d2d456b931c2579811a49655721d3cf0c36b6d6",
    "ofl/instrumentserif/InstrumentSerif-Regular.ttf": "498efd461f6ddfcb7a111bf9a565709d2085d48201d501ead960d93e84ffbb88",
    "ofl/instrumentserif/InstrumentSerif-Italic.ttf": "08939b8bdf534afec24ae0ef5e03f948940cd9a8fe08e7fecbad040e62327385",
    "ofl/instrumentserif/OFL.txt": "129ed7618959716959f2941fdd5b49e0ad6e6c1d78726761786a00253d865521",
    "ofl/ibmplexmono/IBMPlexMono-Regular.ttf": "6a3412f058c7d8dfd9170c41e85ade48e5156ecb89356110ca57a0a27734af46",
    "ofl/ibmplexmono/OFL.txt": "7e6b2818edbd8f6a01ae80641cc8f16a51080d08fb4e532be3a0b6f74adb07da",
}

# The LP text lives in these components; every character in them is kept.
SOURCES = sorted([
    *ROOT.glob("apps/web/src/components/Landing*.tsx"),
    ROOT / "apps/web/src/components/PublicLanding.tsx",
])
ASCII = set(range(0x20, 0x7F))
PUNCTUATION = {ord(c) for c in "、。・「」『』（）〜—…→←↓↑↗％＋：／　"}

# output file -> (input, unicode set, keep the weight axis)
OUTPUTS = {
    "NotoSerifJP-LP.woff2": ("ofl/notoserifjp/NotoSerifJP[wght].ttf", "text", True),
    "InstrumentSerif-Regular.woff2": ("ofl/instrumentserif/InstrumentSerif-Regular.ttf", "latin", False),
    "InstrumentSerif-Italic.woff2": ("ofl/instrumentserif/InstrumentSerif-Italic.ttf", "latin", False),
    "IBMPlexMono-LP.woff2": ("ofl/ibmplexmono/IBMPlexMono-Regular.ttf", "latin", False),
}
LICENSES = {
    "NotoSerifJP-OFL.txt": "ofl/notoserifjp/OFL.txt",
    "InstrumentSerif-OFL.txt": "ofl/instrumentserif/OFL.txt",
    "IBMPlexMono-OFL.txt": "ofl/ibmplexmono/OFL.txt",
}


def fetch(name: str) -> Path:
    path = CACHE / name.replace("/", "_")
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(REPO + name.replace("[", "%5B").replace("]", "%5D")) as response:
            path.write_bytes(response.read())
    if hashlib.sha256(path.read_bytes()).hexdigest() != INPUTS[name]:
        raise SystemExit(f"{name} differs from the reviewed version; review its provenance first")
    return path


def main() -> None:
    from fontTools import subset
    from fontTools.ttLib import TTFont

    text = {ord(c) for path in SOURCES for c in path.read_text(encoding="utf-8")} | ASCII | PUNCTUATION
    sets = {"text": sorted(text), "latin": sorted(ASCII | {ord(c) for c in "’“”–—…→↓↗"})}
    OUT.mkdir(parents=True, exist_ok=True)
    for output, (source, unicodes, variable) in OUTPUTS.items():
        font = TTFont(fetch(source))
        options = subset.Options()
        options.layout_features = ["*"]
        options.name_IDs = ["*"]
        options.notdef_outline = True
        subsetter = subset.Subsetter(options=options)
        subsetter.populate(unicodes=sets[unicodes])
        subsetter.subset(font)
        if not variable and "fvar" in font:
            raise SystemExit(f"{source} is unexpectedly variable")
        font.flavor = "woff2"
        font.save(OUT / output)
    for output, source in LICENSES.items():
        (OUT / output).write_bytes(fetch(source).read_bytes())
    (OUT / "manifest.json").write_text(json.dumps({
        "license": "OFL-1.1",
        "fonttools_version": __import__("fontTools").version,
        "inputs": {REPO + name: digest for name, digest in INPUTS.items()},
        "sources": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCES},
        "requested_codepoints": sets["text"],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    registry = ROOT / "fixtures/public/allowlist.json"
    allowed = json.loads(registry.read_text(encoding="utf-8"))
    families = {"NotoSerifJP": "notoserifjp", "InstrumentSerif": "instrumentserif", "IBMPlexMono": "ibmplexmono"}
    for path in sorted(OUT.iterdir()):
        family = next((slug for prefix, slug in families.items() if path.name.startswith(prefix)), None)
        allowed[path.relative_to(ROOT).as_posix()] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "source": "https://github.com/google/fonts/tree/main/ofl/" + family if family
            else "https://github.com/google/fonts (subset by scripts/build_lp_fonts.py)",
            "license": "OFL-1.1",
        }
    registry.write_text(json.dumps(allowed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    for path in sorted(OUT.iterdir()):
        print(f"{path.relative_to(ROOT)} {path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
