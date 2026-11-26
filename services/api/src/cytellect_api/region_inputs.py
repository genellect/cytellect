"""Bounded reading of region inputs, shared by registration and the intake inspection (#284 W4)."""

import numpy as np
import tifffile
from cytellect_analysis.images import read_tiff
from cytellect_analysis.masks import validate_label_array

GENERIC_IMAGE_CODE = "unsupported_or_invalid_region_image"
GENERIC_OME_CODE = "unsupported_or_invalid_region_ome"
# Reader causes a researcher can act on, by the slot being read; other causes keep the generic code.
REGION_IMAGE_ERRORS = {
    "uint8_or_uint16_required": "region_image_bit_depth_unsupported",
    "only_2d_supported": "region_image_not_2d",
    "grayscale_axes_required": "region_image_not_grayscale",
    "explicit_channels_required": "region_image_multichannel_requires_ome",
    "channel_dimensions_mismatch": "region_channel_dimensions_mismatch",
    "pixel_limit": "region_image_pixel_limit",
}
REGION_LABEL_ERRORS = {
    "single_label_plane_required": "region_labels_single_plane_required",
    "original_coordinate_integer_labels_required": "region_labels_shape_or_type_mismatch",
    "label_plane_incomplete": "region_labels_incomplete",
}


class RegionReadError(Exception):
    """A file the registration reader refuses, carrying the API reason code (never the reader's own text)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def read_region_channel(path, input_mode):
    """Decode one channel file exactly as registration does, or raise its reason code.

    Only known reader causes are named; never the exception text, which can carry paths or bytes.
    """
    try:
        return read_tiff(path, legacy=input_mode == "display-rgb")
    except ValueError as exc:
        raise RegionReadError(REGION_IMAGE_ERRORS.get(str(exc), GENERIC_IMAGE_CODE)) from None
    except Exception:
        raise RegionReadError(GENERIC_IMAGE_CODE) from None


def read_label_tiff(path, shape):
    with tifffile.TiffFile(path, _multifile=False) as tif:
        if tif.is_ome or len(tif.series) != 1 or len(tif.pages) != 1:
            raise ValueError("single_label_plane_required")
        series, page = tif.series[0], tif.pages[0]
        if not isinstance(page, tifffile.TiffPage):
            raise ValueError("single_label_plane_required")
        if (series.axes != "YX" or series.shape != tuple(shape)
                or series.dtype not in (np.dtype("uint8"), np.dtype("uint16"), np.dtype("uint32"))
                or page.samplesperpixel != 1 or max(shape) > 4096):
            raise ValueError("original_coordinate_integer_labels_required")
        if (not page.dataoffsets or len(page.dataoffsets) != len(page.databytecounts)
                or any(offset <= 0 or size <= 0 or offset + size > tif.filehandle.size
                       for offset, size in zip(page.dataoffsets, page.databytecounts, strict=True))):
            raise ValueError("label_plane_incomplete")
        labels = series.asarray()
    validate_label_array(labels)
    return labels.astype(np.uint32, copy=False)
