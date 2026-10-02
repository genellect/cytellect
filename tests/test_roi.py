import io
import zipfile

import numpy as np
import pytest
from cytellect_analysis.roi import export_roi_zip, import_roi_zip
from roifile import ROI_TYPE, ImagejRoi


def test_roi_exact_holes_disconnected_edges_sparse_ids(tmp_path):
    labels = np.zeros((20, 24), dtype=np.uint32)
    labels[0:15, 0:12] = 41
    labels[4:9, 3:8] = 0
    labels[17, 18:24] = 41
    labels[11:16, 14:20] = 7
    path = export_roi_zip(labels, tmp_path / "rois.zip")
    np.testing.assert_array_equal(import_roi_zip(path), labels)
    with zipfile.ZipFile(path) as archive:
        assert all(ImagejRoi.frombytes(archive.read(name)).roitype == ROI_TYPE.RECT
                   for name in archive.namelist() if name.endswith(".roi"))


def test_reject_arbitrary_roi_and_tampered_geometry(tmp_path):
    with io.BytesIO() as data:
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("polygon.roi", ImagejRoi.frompoints([[0, 0], [2, 0], [2, 3]]).tobytes())
        with pytest.raises(ValueError, match="unsupported_roi_format"):
            import_roi_zip(data.getvalue())
    labels = np.ones((3, 3), dtype=np.uint32)
    path = export_roi_zip(labels, tmp_path / "rois.zip")
    with zipfile.ZipFile(path) as source, io.BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w") as target:
            for name in source.namelist():
                content = source.read(name)
                if name.endswith(".roi"):
                    roi = ImagejRoi.frombytes(content)
                    roi.right -= 1
                    content = roi.tobytes()
                target.writestr(name, content)
        with pytest.raises(ValueError, match="roi_pixel_set_changed"):
            import_roi_zip(buffer.getvalue())
