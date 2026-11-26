"""Inspection of one selected file before registration, saving nothing (#284 W4, docs/generic-regions.md).

The browser sends each selected TIFF here with the route it would use to register it. The answer says
whether registration would accept it as an image, whether it is a 32-bit integer label image, or why it
cannot be read, using the same reading functions and reason codes as registration. Per-file only: channel
dimensions across files, the four-channel limit and workspace quotas stay with registration.
"""

import base64
import io
import math
import shutil
import time
from typing import Annotated, Literal

import numpy as np
import tifffile
from cytellect_analysis.images import render_preview_with_display, sha256
from fastapi import Depends, File, Form, HTTPException, UploadFile
from PIL import Image
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from .db import uid
from .public_uploads import require_registered
from .region_inputs import RegionReadError, read_label_tiff, read_region_channel
from .region_ome import read_region_ome_channels
from .upload_guard import INTAKE_ROUTE

FILE_LIMIT = 256 * 1024**2
THUMBNAIL_SIDE = 256
# Registration refuses label images in a channel slot with this code; only 32-bit integers are named labels.
LABEL_CODE = "region_image_bit_depth_unsupported"
IntakeKind = Literal["native", "display-rgb", "ome"]


class IntakeInspection(BaseModel):
    """What registration would make of one file. Nothing is stored; the file name is neither read nor returned."""

    kind: IntakeKind
    role: Literal["image", "label", "unreadable"]
    code: str | None = Field(description="Registration's reason code for a label or unreadable file; null for an image")
    sha256: str
    bytes: int
    shape: list[int] | None = Field(description="[Y, X] of a decoded image, or a label image's shape as stored in the file")
    dtype: str | None
    channel_names: list[str | None] | None = Field(description="OME channel names in order (null if unnamed); OME only")
    thumbnail_png: str | None = Field(
        description="Base64 PNG of at most 256 px per side, for display only (first channel of an OME file)"
    )


def _step(shape):
    return max(1, math.ceil(max(shape) / THUMBNAIL_SIDE))


def _thumbnail(plane):
    # Every step-th pixel, shown with the preview's default display (minimum to maximum, gain 1). Display only:
    # a thumbnail that cannot be drawn is left out and never changes the judgement.
    try:
        small = np.ascontiguousarray(plane[::_step(plane.shape), ::_step(plane.shape)])
        png, _ = render_preview_with_display({"c": small}, "c", 0, 100, 1, composite=False)
        # The preview writes equal red, green and blue; one gray plane carries the same values in a third of the size.
        stream = io.BytesIO()
        Image.open(io.BytesIO(png)).convert("L").save(stream, format="PNG")
        return stream.getvalue()
    except Exception:
        return None


def _label_thumbnail(path, shape):
    # Labelled pixels in white, read by registration's label reader; none when that reader refuses the file.
    try:
        labels = read_label_tiff(path, shape)
        small = (labels[::_step(shape), ::_step(shape)] > 0).astype(np.uint8) * 255
        stream = io.BytesIO()
        Image.fromarray(small).save(stream, format="PNG")
        return stream.getvalue()
    except Exception:
        return None


def _label_header(path):
    try:
        with tifffile.TiffFile(path, _multifile=False) as tif:
            series = tif.series[0]
            return series.dtype, tuple(int(n) for n in series.shape)
    except Exception:
        return None


def inspect_region_file(path, kind):
    """Role, reason code and display facts of one file, decided by registration's own readers."""
    if kind == "ome":
        try:
            stack, names = read_region_ome_channels(path)
        except RegionReadError as exc:
            return {"role": "unreadable", "code": exc.code}
        return {"role": "image", "code": None, "shape": list(stack.shape[1:]), "dtype": stack.dtype.name,
                "channel_names": names, "thumbnail": _thumbnail(stack[0])}
    try:
        pixels = read_region_channel(path, kind)
    except RegionReadError as exc:
        header = _label_header(path) if exc.code == LABEL_CODE else None
        # Use is never inferred from content: 8- and 16-bit masks are images, and only the 32-bit integer
        # images that registration refuses are offered as labels.
        if header is not None and header[0].kind in "iu" and header[0].itemsize == 4:
            dtype, shape = header
            return {"role": "label", "code": exc.code, "shape": list(shape), "dtype": dtype.name,
                    "thumbnail": _label_thumbnail(path, shape) if len(shape) == 2 else None}
        return {"role": "unreadable", "code": exc.code}
    return {"role": "image", "code": None, "shape": list(pixels.shape), "dtype": pixels.dtype.name,
            "thumbnail": _thumbnail(pixels)}


# An inspection takes seconds; a folder this old belongs to a process that stopped while reading it.
STALE_INTAKE_SECONDS = 3600


def remove_stale_intake(store, now: float | None = None) -> int:
    """Removes inspection copies a stopped process left behind (a crash or power loss mid-inspection).

    The copy belongs to no workspace, so neither deleting a workspace nor retention would remove it. Called
    when the API starts and by the worker's cleanup; folders in use (younger than an hour) are left.
    """
    root = store.safe_path("tmp")
    if not root.is_dir():
        return 0
    limit = (time.time() if now is None else now) - STALE_INTAKE_SECONDS
    removed = 0
    for folder in root.glob("intake-*"):
        try:
            if folder.is_dir() and not folder.is_symlink() and folder.stat().st_mtime < limit:
                shutil.rmtree(folder)
                removed += 1
        except OSError:
            continue  # Another process removed it, or it is still being written.
    return removed


def register_intake_routes(api, store, settings, owner):
    Owner = Annotated[str, Depends(owner)]
    remove_stale_intake(store)

    @api.post(INTAKE_ROUTE, response_model=IntakeInspection)
    async def inspect_intake(_owner: Owner, file: UploadFile = File(...), kind: IntakeKind = Form(...)):
        # A fixed name in a fresh private folder: the client's file name never becomes a path.
        folder = store.safe_path("tmp", f"intake-{uid()}")
        try:
            folder.mkdir(parents=True, mode=0o700)
            path = folder / "upload.tif"
            total = 0
            with path.open("wb") as stream:
                while chunk := await file.read(1024 * 1024):
                    total += len(chunk)
                    if total > FILE_LIMIT:
                        raise HTTPException(413, "field_upload_limit")
                    stream.write(chunk)
            digest = await run_in_threadpool(sha256, path)
            require_registered(settings.upload_allowlist, digest)
            found = await run_in_threadpool(inspect_region_file, path, kind)
            thumbnail = found.pop("thumbnail", None)
            return IntakeInspection(kind=kind, sha256=digest, bytes=total, shape=found.pop("shape", None),
                                    dtype=found.pop("dtype", None), channel_names=found.pop("channel_names", None),
                                    thumbnail_png=base64.b64encode(thumbnail).decode("ascii") if thumbnail else None,
                                    **found)
        finally:
            # Removed before the answer is sent, whatever the outcome; a removal that fails is an error, not ignored.
            await file.close()
            if folder.exists():
                shutil.rmtree(folder)
