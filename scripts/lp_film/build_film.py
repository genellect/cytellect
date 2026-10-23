"""Edit, grade and encode the LP hero film from cuts.json.

Usage:
  python scripts/lp_film/build_film.py            # write the film, poster, provenance and allowlist entries
  python scripts/lp_film/build_film.py --preview .cache/lp_film/preview.mp4   # local preview only; touches nothing tracked

Run fetch_sources.py first. A cut owned by Blender uses its committed render when the file exists and
falls back to its stock source otherwise. Requires ffmpeg with libx264 and libwebp.
"""

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CACHE = ROOT / ".cache" / "lp_film" / "sources"
ALLOWLIST = ROOT / "fixtures" / "public" / "allowlist.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cut_input(cut: dict, sources: dict) -> tuple[list[str], str, dict]:
    """Return ffmpeg input args, the per-cut filter head and the provenance record."""
    render = ROOT / cut["render"] if cut.get("render") else None
    if render and render.exists():
        args = ["-t", f"{cut['duration']:.3f}", "-i", str(render)]
        record = {"cut": cut["id"], "kind": "render", "file": cut["render"], "sha256": sha256(render)}
        return args, "setpts=PTS-STARTPTS", record
    source = sources[cut["source"]]
    path = CACHE / f"{source['id']}.{'mp4' if source['kind'] == 'video' else 'jpg'}"
    if not path.exists():
        raise SystemExit(f"Missing {path.relative_to(ROOT)}; run scripts/lp_film/fetch_sources.py first.")
    if sha256(path) != source["sha256"]:
        raise SystemExit(f"{path.relative_to(ROOT)} does not match sources.json; refetch it.")
    record = {
        "cut": cut["id"],
        "kind": source["kind"],
        "source": source["id"],
        "page": source["page"],
        "creator": source["creator"],
        "license": source["license"],
        "treatment": source["treatment"],
    }
    crop = "crop={2}:{3}:{0}:{1}".format(*cut["crop"]) if cut.get("crop") else "null"
    if source["kind"] == "video":
        speed = cut.get("speed", 1.0)
        args = ["-ss", f"{cut['start']:.3f}", "-t", f"{cut['duration'] / speed:.3f}", "-i", str(path)]
        return args, f"setpts={speed}*(PTS-STARTPTS),{crop}", record
    return ["-i", str(path)], crop, record


def build(config: dict, sources: dict, out: Path) -> tuple[list[dict], float]:
    o = config["output"]
    w, h, fps, fade = o["width"], o["height"], o["fps"], o["fade"]
    cuts = config["cuts"]
    inputs, filters, records = [], [], []
    # The first cut is appended once more so the end crossfades back onto the opening frame.
    for i, cut in enumerate([*cuts, cuts[0]]):
        args, head, record = cut_input(cut, sources)
        is_still = record["kind"] == "photo"
        if is_still:
            frames = round(cut["duration"] * fps)
            z0, z1 = cut.get("move", [1.0, 1.0])
            # Upscale before zoompan so the slow push does not step between integer pixels.
            motion = (
                f"scale={w * 2}:{h * 2}:flags=lanczos,zoompan=z='{z0}+({z1}-{z0})*on/{frames}':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}"
            )
        else:
            motion = (
                f"fps={fps},scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h}"
            )
        adjust = cut.get("adjust", "null")
        filters.append(f"[{i}:v]{head},{motion},{adjust},{config['grade']},setsar=1,format=yuv420p[s{i}]")
        inputs += args
        if i < len(cuts):
            records.append(record)
    lengths = [c["duration"] for c in cuts] + [fade]
    chain, offset = "s0", 0.0
    for i in range(1, len(lengths)):
        offset += lengths[i - 1] - fade
        filters.append(f"[{chain}][s{i}]xfade=transition=fade:duration={fade}:offset={offset:.3f}[x{i}]")
        chain = f"x{i}"
    total = sum(lengths) - fade * (len(lengths) - 1) - fade
    filters.append(f"[{chain}]trim=0:{total:.3f},setpts=PTS-STARTPTS[v]")
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            *inputs,
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[v]",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            str(o["crf"]),
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(out),
        ],
        check=True,
    )
    return records, total


def poster(config: dict, film: Path, out: Path) -> None:
    o = config["output"]
    start = 0.0
    for cut in config["cuts"]:
        if cut["id"] == o["poster_cut"]:
            break
        start += cut["duration"] - o["fade"]
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-ss",
            f"{start + o['poster_time']:.3f}",
            "-i",
            str(film),
            "-frames:v",
            "1",
            "-c:v",
            "libwebp",
            "-quality",
            "82",
            str(out),
        ],
        check=True,
    )


def register(paths: list[Path], source: str, license_text: str) -> None:
    allowed = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    for path in paths:
        allowed[path.relative_to(ROOT).as_posix()] = {
            "sha256": sha256(path),
            "source": source,
            "license": license_text,
        }
    ALLOWLIST.write_text(json.dumps(allowed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preview", type=Path, help="write only this preview file (untracked location)")
    args = parser.parse_args()
    config = json.loads((HERE / "cuts.json").read_text(encoding="utf-8"))
    manifest = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))
    sources = {s["id"]: s for s in manifest["sources"]}
    if args.preview:
        _, total = build(config, sources, args.preview.resolve())
        print(f"preview {args.preview} ({total:.2f}s)")
        return
    o = config["output"]
    film, still = ROOT / o["video"], ROOT / o["poster"]
    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp) / "film.mp4"
        records, total = build(config, sources, staged)
        film.write_bytes(staged.read_bytes())
    poster(config, film, still)
    licenses = sorted({r["license"] for r in records if "license" in r})
    provenance = {
        "schema_version": "1.0.0",
        "kind": "illustrative-stock-footage",
        "not_analysis_input": True,
        "not_product_usage_evidence": True,
        "built_by": "scripts/lp_film/build_film.py from scripts/lp_film/cuts.json",
        "duration_seconds": round(total, 2),
        "licenses": {key: manifest["licenses"][key] for key in licenses},
        "presentation_rules": [
            "Distinguish this footage from registered microscopy inputs and actual Cytellect figures.",
            "Do not imply that creators, CDC or any instrument maker use or endorse Cytellect.",
            "Do not describe this footage as the developer laboratory or product-controlled instruments.",
        ],
        "cuts": records,
        "outputs": {o["video"]: sha256(film), o["poster"]: sha256(still)},
    }
    (ROOT / o["provenance"]).write_text(
        json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    register(
        [film, still],
        "Edited by scripts/lp_film/build_film.py; sources in scripts/lp_film/sources.json",
        " AND ".join(f"{key.capitalize()} License" for key in licenses)
        + ("; Apache-2.0 (Blender renders)" if any(r["kind"] == "render" for r in records) else ""),
    )
    print(f"{o['video']} {film.stat().st_size / 1e6:.2f} MB, {total:.2f}s; poster and provenance written")


if __name__ == "__main__":
    main()
