"""Fail-closed format/contour conventions for the new public-image audit."""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("public_bbbc007", SCRIPTS / "public_bbbc007.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_strict_plane_preserves_original_unsigned_samples():
    array = np.array([[0, 65535], [1024, 7]], dtype=np.uint16)
    assert module.strict_plane(array) is array
    assert array.tolist() == [[0, 65535], [1024, 7]]


@pytest.mark.parametrize("shape", [(4, 4, 3), (1, 4, 4), (4,)])
def test_unknown_axes_and_rgb_are_not_flattened(shape):
    with pytest.raises(ValueError, match="unsupported_rgb_or_multiaxis_source"):
        module.strict_plane(np.zeros(shape, dtype=np.uint8))


def test_float_source_is_not_silently_quantized():
    with pytest.raises(ValueError, match="unsupported_source_dtype"):
        module.strict_plane(np.full((4, 4), 0.25, dtype=np.float32))


def test_closed_contour_uses_interior_not_boundary_or_exterior():
    outline = np.zeros((9, 9), dtype=bool)
    outline[2, 2:7] = outline[6, 2:7] = True
    outline[2:7, 2] = outline[2:7, 6] = True
    result = module.contour_interiors(outline)
    expected = np.zeros((9, 9), dtype=np.uint32)
    expected[3:6, 3:6] = 1
    np.testing.assert_array_equal(result, expected)


def test_open_contour_is_not_repaired():
    outline = np.zeros((9, 9), dtype=bool)
    outline[2, 2:7] = outline[6, 2:7] = True
    outline[2:7, 2] = outline[2:7, 6] = True
    outline[2, 4] = False
    assert not module.contour_interiors(outline).any()


def test_nonbinary_outline_and_repository_output_are_rejected():
    with pytest.raises(ValueError, match="unsupported_outline_encoding"):
        module.contour_interiors(np.full((4, 4), 128, dtype=np.uint8))
    with pytest.raises(ValueError, match="outside_checkout"):
        module.external_directory(SCRIPTS / "public-data")


def test_pinned_archive_identity_cannot_be_replaced(tmp_path):
    path = tmp_path / "archive.zip"
    path.write_bytes(b"changed bytes")
    with pytest.raises(ValueError, match="public_archive_identity_mismatch"):
        module.verify_archive(path, {"bytes": 13, "sha256": "0" * 64})


def test_report_gate_does_not_accept_silently_dropped_fields():
    with pytest.raises(ValueError, match="fixed_subset_changed"):
        module.check_report({"fields": []})


def test_report_gate_does_not_accept_other_execution_failures():
    fields = [{"field": name, "status": "failed", "reason": "validation_execution_error"}
              for name in ("a9", "f113", "f96_17", "f9620")]
    with pytest.raises(ValueError, match="unsupported_field_not_explicitly_rejected"):
        module.check_report({"fields": fields})
