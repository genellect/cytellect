"""Pixel-exact ImageJ ROI interchange using integer, half-open rectangles.

Each object is encoded as row runs rather than a traced polygon. This intentionally
supports disconnected components and holes without rounding an approximate contour.
"""
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
from roifile import ROI_OPTIONS, ROI_TYPE, ImagejRoi

FORMAT = "cytellect-pixel-runs/1"


def _digest(labels):
    return hashlib.sha256(np.asarray(labels, dtype="<u4").tobytes(order="C")).hexdigest()


def export_roi_zip(labels, destination: Path):
    labels = np.asarray(labels)
    if labels.ndim != 2 or labels.dtype.kind not in "ui" or np.any(labels < 0) or labels.max(initial=0) > 2**32-1:
        raise ValueError("roi_requires_2d_unsigned_labels")
    if max(labels.shape) > 4096:
        raise ValueError("roi_dimensions_exceeded")
    destination.parent.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for y, row in enumerate(labels):
            boundaries = np.flatnonzero(np.r_[True, row[1:] != row[:-1], True])
            for left, right in zip(boundaries[:-1], boundaries[1:], strict=True):
                label = int(row[left])
                if label == 0:
                    continue
                if len(entries) >= 1000000:
                    raise ValueError("roi_complexity_exceeded")
                name = f"object-{label:010d}-run-{len(entries):07d}"
                roi = ImagejRoi(roitype=ROI_TYPE.RECT, left=int(left), right=int(right),
                               top=y, bottom=y+1, name=name)
                archive.writestr(name + ".roi", roi.tobytes())
                entries.append({"name": name + ".roi", "label": label})
        archive.writestr("cytellect-roi.json", json.dumps({
            "format": FORMAT, "shape": list(labels.shape), "labels_sha256": _digest(labels),
            "coordinate_rule": "left <= x < right; top <= y < bottom", "entries": entries
        }, sort_keys=True, separators=(",", ":")))
    return destination


def import_roi_zip(source):
    """Accept this exact exchange format only; arbitrary Fiji polygons are unsupported."""
    with zipfile.ZipFile(io.BytesIO(source) if isinstance(source, bytes) else source) as archive:
        infos = archive.infolist()
        if sum(info.file_size for info in infos) > 256 * 1024 * 1024 or len(infos) > 1000001:
            raise ValueError("roi_archive_too_large")
        names = [info.filename for info in infos]
        if len(names) != len(set(names)) or "cytellect-roi.json" not in names:
            raise ValueError("unsupported_roi_format")
        metadata = json.loads(archive.read("cytellect-roi.json"))
        shape = metadata.get("shape", [])
        if (metadata.get("format") != FORMAT or len(shape) != 2
                or any(type(v) is not int or v < 1 or v > 4096 for v in shape)):
            raise ValueError("unsupported_roi_format")
        entries = metadata.get("entries", [])
        if set(names) != {"cytellect-roi.json", *[entry["name"] for entry in entries]}:
            raise ValueError("unsupported_roi_format")
        labels = np.zeros(shape, dtype=np.uint32)
        for entry in entries:
            name, label = entry["name"], entry["label"]
            if not re.fullmatch(r"object-[0-9]{10}-run-[0-9]{7}\.roi", name) or type(label) is not int or not 0 < label < 2**32:
                raise ValueError("unsupported_roi_format")
            roi = ImagejRoi.frombytes(archive.read(name))
            if (roi.roitype != ROI_TYPE.RECT or roi.rounded_rect_arc_size or roi.shape_roi_size
                    or roi.options & ROI_OPTIONS.SUB_PIXEL_RESOLUTION
                    or roi.subpixel_coordinates is not None
                    or not 0 <= roi.left < roi.right <= shape[1]
                    or not 0 <= roi.top < roi.bottom <= shape[0]):
                raise ValueError("unsupported_roi_geometry")
            region = labels[roi.top:roi.bottom, roi.left:roi.right]
            if (region != 0).any():
                raise ValueError("roi_overlap")
            region[:] = label
        if _digest(labels) != metadata.get("labels_sha256"):
            raise ValueError("roi_pixel_set_changed")
    return labels
