"""Bounded TIFF input and display-only rendering."""
import hashlib
import io
import math
from pathlib import Path

import numpy as np
import tifffile
from defusedxml import ElementTree
from PIL import Image

from .display_contracts import PreviewDisplayMetadata, PreviewPlaneDisplay

MAX_SIDE = 4096
MAX_PIXELS = MAX_SIDE * MAX_SIDE


def _validate_ome_planes(tif, root, *, max_channels=3):
    """Reject incomplete acquisitions before tifffile can synthesize zero planes.

    This deliberately supports only one grayscale 2D image, with one IFD per
    acquired channel. OME's optional TiffData defaults are resolved explicitly.
    """
    images = [node for node in root if node.tag.rsplit("}", 1)[-1] == "Image"]
    pixels = [node for image in images for node in image if node.tag.rsplit("}", 1)[-1] == "Pixels"]
    if len(images) != 1 or len(pixels) != 1:
        raise ValueError("single_series_required")
    pixel = pixels[0]
    try:
        dims = {axis: int(pixel.attrib[f"Size{axis}"]) for axis in "XYZTC"}
    except (KeyError, ValueError) as exc:
        raise ValueError("invalid_ome_metadata") from exc
    if dims["Z"] != 1 or dims["T"] != 1:
        raise ValueError("only_2d_supported")
    if (not 1 <= dims["C"] <= max_channels or not 1 <= dims["X"] <= MAX_SIDE
            or not 1 <= dims["Y"] <= MAX_SIDE):
        raise ValueError("invalid_dimensions")
    if pixel.attrib.get("Type") not in ("uint8", "uint16"):
        raise ValueError("uint8_or_uint16_required")
    order = pixel.attrib.get("DimensionOrder", "")
    if not order.startswith("XY") or set(order) != set("XYZTC") or len(order) != 5:
        raise ValueError("invalid_ome_metadata")
    children = list(pixel)
    channels = [node for node in children if node.tag.rsplit("}", 1)[-1] == "Channel"]
    records = [node for node in children if node.tag.rsplit("}", 1)[-1] == "TiffData"]
    try:
        if len(channels) != dims["C"] or any(int(c.attrib.get("SamplesPerPixel", "1")) != 1 for c in channels):
            raise ValueError("grayscale_axes_required")
        if not records or len(tif.pages) != dims["C"]:
            raise ValueError("ome_plane_coverage_invalid")
        mapping: dict[int, int] = {}
        for record in records:
            attrs = record.attrib
            if int(attrs.get("FirstZ", "0")) != 0 or int(attrs.get("FirstT", "0")) != 0:
                raise ValueError("ome_plane_coverage_invalid")
            first = int(attrs.get("FirstC", "0"))
            ifd = int(attrs.get("IFD", "0"))
            count = int(attrs.get("PlaneCount", "1" if "IFD" in attrs else str(len(tif.pages))))
            if first < 0 or ifd < 0 or count < 1 or first + count > dims["C"] or ifd + count > len(tif.pages):
                raise ValueError("ome_plane_coverage_invalid")
            for offset in range(count):
                if first + offset in mapping or ifd + offset in mapping.values():
                    raise ValueError("ome_plane_coverage_invalid")
                mapping[first + offset] = ifd + offset
        if set(mapping) != set(range(dims["C"])):
            raise ValueError("ome_plane_coverage_invalid")
    except (TypeError, OverflowError) as exc:
        raise ValueError("invalid_ome_metadata") from exc
    for index in mapping.values():
        page = tif.pages[index]
        if (page.shape != (dims["Y"], dims["X"]) or page.dtype != np.dtype(pixel.attrib["Type"])
                or page.samplesperpixel != 1):
            raise ValueError("ome_plane_metadata_mismatch")
        # Empty or out-of-file strips may otherwise decode as missing pixels.
        if not page.dataoffsets or len(page.dataoffsets) != len(page.databytecounts):
            raise ValueError("ome_plane_data_incomplete")
        if any(offset <= 0 or size <= 0 or offset + size > tif.filehandle.size
               for offset, size in zip(page.dataoffsets, page.databytecounts, strict=True)):
            raise ValueError("ome_plane_data_incomplete")
    return mapping


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def read_tiff(path: Path, *, legacy=False, channel_indices=None, max_channels=3) -> np.ndarray:
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
            ome_mapping = _validate_ome_planes(tif, root, max_channels=max_channels)
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
        if dims["Y"] * dims["X"] > MAX_PIXELS or math.prod(shape) > MAX_PIXELS * (4 if legacy else max_channels):
            raise ValueError("pixel_limit")
        if legacy and axes in ("YXS", "SYX") and dims["S"] in (3, 4) and series.dtype == np.uint8:
            if channel_indices is not None:
                raise ValueError("rgb_channel_mapping_unsupported")
            return np.take(series.asarray(), [0, 1, 2], axis=axes.index("S")).max(axis=axes.index("S"))
        if any(axis not in "TCZYX" for axis in axes):
            raise ValueError("grayscale_axes_required")
        if channel_indices is not None:
            count = dims.get("C", 0)
            if (not tif.is_ome or count not in range(2, max_channels + 1) or
                    not isinstance(channel_indices, (tuple, list)) or
                    any(type(i) is not int for i in channel_indices) or
                    sorted(channel_indices) != list(range(count))):
                raise ValueError("explicit_two_or_three_channel_ome_mapping_required")
        elif dims.get("C", 1) != 1:
            raise ValueError("explicit_channels_required")
        if "".join(axis for axis in axes if axis not in "TCZ") != "YX":
            raise ValueError("yx_required")
        if tif.is_ome:
            # Verify the library resolved every declared plane to the exact IFD;
            # never accept its warning-and-zero-fill recovery for damaged OME.
            resolved = list(series.pages)
            if (len(resolved) != len(ome_mapping)
                    or any(page is None or page.offset != tif.pages[ome_mapping[i]].offset
                           for i, page in enumerate(resolved))):
                raise ValueError("ome_plane_coverage_invalid")
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


def render_preview_with_display(
    channels: dict[str, np.ndarray], channel="merge", low=0., high=100., gain=1.,
    *, field_id: str = "", legacy: bool = False, composite: bool | None = None,
) -> tuple[bytes, PreviewDisplayMetadata]:
    """Return pixels and their display transform together, without mutating inputs."""
    if not 0 <= low < high <= 100 or not 0.1 <= gain <= 10:
        raise ValueError("invalid_display_settings")
    merge = channel == "merge" if composite is None else composite
    ids = [c for c in ("ncl", "gfp", "dapi") if c in channels] if merge else [channel]
    if not ids or any(c not in channels for c in ids):
        raise ValueError("invalid_display_channels")
    planes: list[PreviewPlaneDisplay] = []

    def scale(c):
        a = channels[c]
        if a.ndim != 2 or not a.size or a.dtype.kind not in "uif" or not np.isfinite(a).all():
            raise ValueError("invalid_display_pixels")
        lo, hi = np.percentile(a, [low, high])
        span = max(hi - lo, 1)
        minimum, maximum = float(a.min()), float(a.max())
        planes.append(PreviewPlaneDisplay(
            channel_id=c, dtype=str(a.dtype),
            value_basis="legacy-imported" if legacy else "native-grayscale",
            source_min=minimum, source_max=maximum,
            percentile_low_value=float(lo), percentile_high_value=float(hi),
            normalization_span=float(span), display_black_value=float(lo),
            display_white_value=float(lo + span / gain), constant_plane=minimum == maximum,
        ))
        return np.clip((a.astype(float) - lo) / max(hi - lo, 1) * gain, 0, 1)
    if merge:
        zero = np.zeros_like(next(iter(channels.values())), dtype=float)
        rgb = np.stack([scale(c) if c in channels else zero for c in ("ncl", "gfp", "dapi")], axis=-1)
    else:
        v = scale(channel)
        rgb = np.stack([v, v, v], axis=-1)
    stream = io.BytesIO()
    Image.fromarray((rgb * 255).astype(np.uint8)).save(stream, format="PNG")
    return stream.getvalue(), PreviewDisplayMetadata(
        field_id=field_id, requested_channel=channel, composite=merge,
        low_percentile=low, high_percentile=high, gain=gain, planes=planes,
    )


def render_preview(channels: dict[str, np.ndarray], channel="merge", low=0., high=100., gain=1.) -> bytes:
    return render_preview_with_display(channels, channel, low, high, gain)[0]
