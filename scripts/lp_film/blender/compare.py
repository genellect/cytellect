"""Make review boards from actual Cycles stills and hash-verified adopted stock.

Requires Pillow and ffmpeg. Does not change cuts, sources, web assets or renders.
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
HERE = ROOT / "scripts/lp_film"
FRAMES = {"droplet": [16, 49, 65], "glass": [1, 40, 80]}


def run_frame(ffmpeg, path, output, filters, start=None):
    command = [ffmpeg, "-y", "-loglevel", "error"]
    if start is not None:
        command += ["-ss", str(start)]
    subprocess.run(command + ["-i", str(path), "-vf", filters, "-frames:v", "1", str(output)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--stills", type=Path, default=ROOT / ".cache/lp_film/blender")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--font", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads((HERE / "cuts.json").read_text(encoding="utf-8"))
    sources = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))["sources"]
    sources = {s["id"]: s for s in sources}
    cache = ROOT / ".cache/lp_film"
    processed = cache / "comparison"
    processed.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype(str(args.font), 23)
    title = ImageFont.truetype(str(args.font), 32)
    small = ImageFont.truetype(str(args.font), 19)
    references = {}
    for cut in config["cuts"]:
        source = sources[cut["source"]]
        path = cache / "sources" / (source["id"] + (".mp4" if source["kind"] == "video" else ".jpg"))
        if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError(f"Source checksum mismatch: {source['id']}")
        crop = "crop={2}:{3}:{0}:{1},".format(*cut["crop"]) if cut.get("crop") else ""
        filters = crop + "scale=640:360," + cut.get("adjust", "null") + "," + config["grade"]
        out = processed / f"stock-{cut['id']}.png"
        run_frame(args.ffmpeg, path, out, filters, cut["start"] + 1.2 if source["kind"] == "video" else None)
        references[cut["id"]] = out
    for cut_id, frames in FRAMES.items():
        cut = next(c for c in config["cuts"] if c["id"] == cut_id)
        board = Image.new("RGB", (1920, 1010), "#f5f4f0")
        draw = ImageDraw.Draw(board)
        draw.text((28, 16), f"{cut_id.upper()}  /  Cycles 静止画レビュー", font=title, fill="#233f35")
        draw.text(
            (28, 65),
            "上段：採用済みの実写　　下段：Blender 描画（各3枚）　｜　既存 cuts.json の色補正を両方に適用",
            font=font,
            fill="#233f35",
        )
        stock_ids = ["hands", "culture", cut_id]
        for col, stock_id in enumerate(stock_ids):
            x = col * 640
            source = sources[next(c for c in config["cuts"] if c["id"] == stock_id)["source"]]
            draw.text((x + 16, 108), f"実写：{stock_id} / {source['creator']}", font=small, fill="#233f35")
            board.paste(Image.open(references[stock_id]).convert("RGB"), (x, 140))
        for col, frame in enumerate(frames):
            path = args.stills / f"{cut_id}-{frame:03d}.png"
            out = args.output / f"{cut_id}-{frame:03d}-graded.png"
            run_frame(args.ffmpeg, path, out, cut.get("adjust", "null") + "," + config["grade"])
            # Preserve neutral AgX files for direct, ungraded material inspection.
            (args.output / path.name).write_bytes(path.read_bytes())
            x = col * 640
            state = (
                {16: "膨張", 49: "離脱前", 65: "離脱後"}[frame]
                if cut_id == "droplet"
                else {1: "始点", 40: "中間", 80: "終点"}[frame]
            )
            draw.text((x + 16, 519), f"Cycles：{state} / frame {frame:03d}", font=font, fill="#233f35")
            board.paste(Image.open(out).convert("RGB").resize((640, 360), Image.Resampling.LANCZOS), (x, 556))
        draw.text(
            (28, 934),
            "判定：実写級の質感 ／ 清潔感と明るさ ／ 前後の実写との連続性",
            font=font,
            fill="#233f35",
        )
        draw.text((28, 975), "静止画の承認待ち。本描画と全編プレビューは未実施。", font=small, fill="#233f35")
        board.save(args.output / f"{cut_id}-comparison.jpg", quality=96, subsampling=0)
    print(f"Review boards and six neutral/graded stills: {args.output}")


if __name__ == "__main__":
    main()
