"""Offline LP media derivatives: display-only motion, never scientific resampling.

Font inputs are obtained from their official distributions and retained with OFL
licenses. This script does not download or install anything at application runtime.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--font-inputs", type=Path, required=True)
    parser.add_argument("--fonts-only", action="store_true")
    parser.add_argument("--text-source", action="append", help="Repo-relative UI text source; repeat to override all UI components and labels")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    image = root / "apps/web/public/demo/4dn-ncl/demo-preview.png"
    expected = "ff7cb346f2509ed39231acf7c23a2fdc6814e88ea7428e41a1162db79cf84d6f"
    if hashlib.sha256(image.read_bytes()).hexdigest() != expected:
        raise SystemExit("Registered microscopy preview changed; review provenance first")
    target = root / "apps/web/public/marketing"
    fonts = root / "apps/web/public/fonts"
    target.mkdir(parents=True, exist_ok=True)
    fonts.mkdir(parents=True, exist_ok=True)
    # One real static field. Only the viewport moves; no cells are generated,
    # segmented, interpolated across time, removed, or independently animated.
    motion = (
        "scale=1920:-2,crop=1920:1080,"
        "zoompan=z='1.02+0.02*(1-cos(2*PI*on/288))':"
        "x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=288:s=1600x900:fps=24"
    )
    common = [str(args.ffmpeg), "-hide_banner", "-loglevel", "error", "-y", "-i", str(image)]
    if not args.fonts_only:
        subprocess.run([*common, "-vf", motion, "-frames:v", "288", "-an", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-crf", "22", "-preset", "medium",
                    "-movflags", "+faststart", str(target / "hero-microscopy.mp4")], check=True)
        subprocess.run([*common, "-vf", motion, "-frames:v", "1", "-c:v", "libwebp",
                    "-quality", "88", str(target / "hero-microscopy-poster.webp")], check=True)
    from fontTools import subset
    from fontTools.ttLib import TTFont

    expected_fonts = {
        "InterVariable.woff2": "693b77d4f32ee9b8bfc995589b5fad5e99adf2832738661f5402f9978429a8e3",
        "Inter-LICENSE.txt": "262481e844521b326f5ecd053e59b98c8b2da78c8ee1bdbb6e8174305e54935a",
        "NotoSansJP[wght].ttf": "c2f3b4d463500a2ddcd3849cded1fceeb9fd6d1c32e6cbecd568453ba50fc68f",
        "OFL.txt": "1c05c68c34f9708415aada51f17e1b0092d2cea709bf4a94cd38114f9e73d7d9",
    }
    for filename, digest in expected_fonts.items():
        if hashlib.sha256((args.font_inputs / filename).read_bytes()).hexdigest() != digest:
            raise SystemExit("Official font input changed; review provenance first")
    shutil.copyfile(args.font_inputs / "InterVariable.woff2", fonts / "InterVariable.woff2")
    shutil.copyfile(args.font_inputs / "Inter-LICENSE.txt", fonts / "Inter-LICENSE.txt")
    shutil.copyfile(args.font_inputs / "OFL.txt", fonts / "NotoSansJP-OFL.txt")
    font = TTFont(args.font_inputs / "NotoSansJP[wght].ttf")
    source_paths = ([root / name for name in args.text_source] if args.text_source else
                    sorted([*root.glob("apps/web/src/components/**/*.tsx"),
                            *root.glob("apps/web/src/app/**/*.tsx"),
                            *root.glob("apps/web/src/lib/*.ts"),
                            *root.glob("apps/web/src/lib/*catalog*.json")]))
    if any(not path.resolve().is_relative_to(root) for path in source_paths):
        raise SystemExit("Font text inputs must remain inside the checkout")
    codepoints = set(range(32, 127)) | set(range(0x2000, 0x2070))
    for path in source_paths:
        codepoints.update(map(ord, path.read_text(encoding="utf-8")))
    options = subset.Options()
    options.name_IDs = ["*"]
    options.name_legacy = True
    options.name_languages = ["*"]
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=sorted(codepoints))
    subsetter.subset(font)
    font.flavor = "woff2"
    font.save(fonts / "NotoSansJPVariable.woff2")
    (fonts / "subset-manifest.json").write_text(json.dumps({
        "source_sha256": hashlib.sha256((args.font_inputs / "NotoSansJP[wght].ttf").read_bytes()).hexdigest(),
        "license": "OFL-1.1", "weight_axis": "100-900", "fonttools_version": __import__("fontTools").version,
        "requested_codepoints": sorted(codepoints),
        "sources": {str(p.relative_to(root)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths},
        "output_sha256": hashlib.sha256((fonts / "NotoSansJPVariable.woff2").read_bytes()).hexdigest(),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    registry = root / "fixtures/public/allowlist.json"
    allowed = json.loads(registry.read_text(encoding="utf-8"))
    for path in fonts.iterdir():
        if not path.is_file():
            continue
        source = ("https://github.com/rsms/inter/releases/tag/v4.1" if path.name.startswith("Inter")
                  else "https://github.com/google/fonts/tree/main/ofl/notosansjp")
        allowed[path.relative_to(root).as_posix()] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "source": source, "license": "OFL-1.1",
        }
    registry.write_text(json.dumps(allowed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
