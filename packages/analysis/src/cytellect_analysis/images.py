"""Bounded TIFF input and display-only rendering."""
import hashlib
import io
import math
from pathlib import Path

import numpy as np
import tifffile
from defusedxml import ElementTree
from PIL import Image

MAX_SIDE = 4096
MAX_PIXELS = MAX_SIDE * MAX_SIDE

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def read_tiff(path: Path, *, legacy=False, channel_indices=None) -> np.ndarray:
    # Do not follow references to other files from untrusted OME metadata.
    with tifffile.TiffFile(path, _multifile=False) as tif:
        if tif.is_ome:
            xml = tif.ome_metadata
            if not xml or len(xml) > 4 * 1024 * 1024:
                raise ValueError("invalid_ome_metadata")
            root = ElementTree.fromstring(xml)
            root_uuid = root.attrib.get("UUID", "").strip()
            for reference in root.iter():
                if reference.tag.rsplit("}", 1)[-1] != "UUID":
                    continue
                referenced_uuid = (reference.text or "").strip()
                if (reference.attrib.get("FileName") or referenced_uuid) and (
                        not root_uuid or referenced_uuid != root_uuid):
                    raise ValueError("external_ome_files_unsupported")
            # OME may name its own original file. Exact UUID identity, never
            # the user-supplied FileName, establishes this self reference.
            # _multifile=False still prohibits resolving another filesystem path.
        if len(tif.series) != 1:
            raise ValueError("single_series_required")
        series = tif.series[0]
        shape, axes = series.shape, series.axes
        if series.dtype not in (np.dtype("uint8"), np.dtype("uint16")):
            raise ValueError("uint8_or_uint16_required")
        if len(axes) != len(shape) or len(set(axes)) != len(axes) or any(n < 1 for n in shape):
            raise ValueError("invalid_dimensions")
        dims = dict(zip(axes, shape, strict=True))
        if any(dims.get(axis, 1) != 1 for axis in "ZT"):
            raise ValueError("only_2d_supported")
        if "Y" not in dims or "X" not in dims or max(dims["Y"], dims["X"]) > MAX_SIDE:
            raise ValueError("invalid_dimensions")
        if dims["Y"] * dims["X"] > MAX_PIXELS or math.prod(shape) > MAX_PIXELS * (4 if legacy else 3):
            raise ValueError("pixel_limit")
        if legacy and axes in ("YXS", "SYX") and dims["S"] in (3, 4) and series.dtype == np.uint8:
            if channel_indices is not None:
                raise ValueError("rgb_channel_mapping_unsupported")
            return np.take(series.asarray(), [0, 1, 2], axis=axes.index("S")).max(axis=axes.index("S"))
        if any(axis not in "TCZYX" for axis in axes):
            raise ValueError("grayscale_axes_required")
        if channel_indices is not None:
            count = dims.get("C", 0)
            if (not tif.is_ome or count not in (2, 3) or
                    not isinstance(channel_indices, (tuple, list)) or
                    any(type(i) is not int for i in channel_indices) or
                    sorted(channel_indices) != list(range(count))):
                raise ValueError("explicit_two_or_three_channel_ome_mapping_required")
        elif dims.get("C", 1) != 1:
            raise ValueError("explicit_channels_required")
        if "".join(axis for axis in axes if axis not in "TCZ") != "YX":
            raise ValueError("yx_required")
        array = series.asarray()
        for axis in "TZ":
            if axis in axes:
                index = axes.index(axis)
                array = np.take(array, 0, axis=index)
                axes = axes.replace(axis, "")
        if "C" in axes:
            if channel_indices is None:
                array = np.take(array, 0, axis=axes.index("C"))
                axes = axes.replace("C", "")
            else:
                return np.stack([np.take(array, i, axis=axes.index("C")) for i in channel_indices])
        if axes != "YX" or array.ndim != 2:
            raise ValueError("yx_required")
        return array


def render_preview(channels: dict[str, np.ndarray], channel="merge", low=0., high=100., gain=1.) -> bytes:
    def scale(a):
        lo, hi = np.percentile(a, [low, high])
        return np.clip((a.astype(float) - lo) / max(hi - lo, 1) * gain, 0, 1)
    if channel == "merge":
        zero = np.zeros_like(next(iter(channels.values())), dtype=float)
        rgb = np.stack([scale(channels[c]) if c in channels else zero for c in ("ncl", "gfp", "dapi")], axis=-1)
    else:
        v = scale(channels[channel])
        rgb = np.stack([v, v, v], axis=-1)
    stream = io.BytesIO()
    Image.fromarray((rgb * 255).astype(np.uint8)).save(stream, format="PNG")
    return stream.getvalue()
