"""Registered BBBC013 previews for model evaluation; no arbitrary/private inputs."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import tifffile
from PIL import Image


def prepare(output: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    output = output.resolve()
    if output.is_relative_to(root):
        raise ValueError("public_preview_output_must_be_external")
    fixture = root / "fixtures/public/bbbc013"
    manifest_bytes = (fixture / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    field = next(item for item in manifest["images"] if item["id"] == "A01")
    previews = []
    for role, token in (("dapi", "ch1"), ("gfp", "ch2")):
        item = field["channels"][role]
        raw = (fixture / item["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError("public_preview_source_hash_mismatch")
        pixels = tifffile.imread(io.BytesIO(raw))
        if pixels.ndim != 2 or pixels.dtype != np.uint8:
            raise ValueError("public_preview_source_format_mismatch")
        image = Image.fromarray(pixels)
        image.thumbnail((256, 256), Image.Resampling.LANCZOS)
        encoded = io.BytesIO()
        image.save(encoded, format="PNG")
        previews.append({"channel": token, "png_base64": base64.b64encode(encoded.getvalue()).decode("ascii")})
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump({"dataset": "BBBC013v1", "source_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                   "previews": previews}, stream)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    prepare(parser.parse_args().output)
