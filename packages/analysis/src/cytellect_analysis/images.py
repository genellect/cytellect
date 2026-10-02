"""Bounded TIFF input and display-only rendering."""
import hashlib
import io
from pathlib import Path
import numpy as np
import tifffile
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
    with tifffile.TiffFile(path) as tif:
        if len(tif.series) != 1:
            raise ValueError("single_series_required")
        series = tif.series[0]
        shape, axes = series.shape, series.axes
        if series.dtype not in (np.dtype("uint8"), np.dtype("uint16")):
            raise ValueError("uint8_or_uint16_required")
        dims = dict(zip(axes, shape, strict=True))
        if any(dims.get(axis, 1) != 1 for axis in "ZT"):
            raise ValueError("only_2d_supported")
        if "Y" not in dims or "X" not in dims or max(dims["Y"], dims["X"]) > MAX_SIDE:
            raise ValueError("invalid_dimensions")
        if dims["Y"] * dims["X"] > MAX_PIXELS or np.prod(shape) > MAX_PIXELS * 3:
            raise ValueError("pixel_limit")
        if legacy and axes == "YXS" and shape[-1] == 3 and series.dtype == np.uint8:
            # Legacy display compatibility: per-pixel maximum of the RGB channels.
            return series.asarray().max(axis=2)
        if any(axis not in "TCZYX" for axis in axes):
            raise ValueError("grayscale_axes_required")
        if channel_indices is None and dims.get("C", 1) != 1:
            raise ValueError("explicit_channels_required")
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
                if not tif.is_ome or sorted(channel_indices) != [0, 1, 2] or dims["C"] != 3:
                    raise ValueError("three_channel_ome_mapping_required")
                return np.stack([np.take(array, i, axis=axes.index("C")) for i in channel_indices])
        if axes != "YX" or array.ndim != 2:
            raise ValueError("yx_required")
        return array

def render_preview(channels: dict[str, np.ndarray], channel="merge", low=0., high=100., gain=1.) -> bytes:
    def scale(a):
        lo, hi = np.percentile(a, [low, high])
        return np.clip((a.astype(float) - lo) / max(hi - lo, 1) * gain, 0, 1)
    if channel == "merge":
        rgb = np.stack([scale(channels["ncl"]), scale(channels["gfp"]), scale(channels["dapi"])], axis=-1)
    else:
        v = scale(channels[channel])
        rgb = np.stack([v, v, v], axis=-1)
    stream = io.BytesIO()
    Image.fromarray((rgb * 255).astype(np.uint8)).save(stream, format="PNG")
    return stream.getvalue()
