"""Bounded original-coordinate label input for the explicit generic workflow."""

import numpy as np
import tifffile
from cytellect_analysis.masks import validate_label_array


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
