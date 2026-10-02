import math

import numpy as np
import pytest
from cytellect_analysis.contracts import Recipe
from cytellect_analysis.measurement import measure


def test_native_measurement_preserves_signed_corrections_and_pixel_weighted_union():
    nuclei = np.array([[0, 0, 0, 0], [0, 1, 1, 0], [0, 1, 1, 0], [0, 0, 0, 0]], dtype=np.uint32)
    nucleoli = np.zeros_like(nuclei)
    nucleoli[1, 1] = 1
    channels = {
        "dapi": np.full((4, 4), 10, dtype=np.uint16),
        "ncl": np.array([[10] * 4, [10, 30, 8, 10], [10, 12, 8, 10], [10] * 4], dtype=np.uint16),
        "gfp": np.array([[10] * 4, [10, 8, 12, 10], [10, 10, 10, 10], [10] * 4], dtype=np.uint16),
    }
    background = np.zeros((4, 4), dtype=bool)
    background[0, :] = True
    cells, objects, _ = measure(channels, nuclei, nucleoli, background, Recipe(), {}, "field")
    row = cells[0]
    assert row["ncl_nucleoli_mean_corrected"] == 20
    assert row["ncl_nucleoplasm_mean_corrected"] == pytest.approx((-2 + 2 - 2) / 3)
    assert row["gfp_mean_corrected"] == 0
    assert row["ratio_missing_reason"] == "nonpositive_signal"
    assert row["ncl_log2_nucleoplasm_over_nucleoli"] is None
    assert objects[0]["integrated_corrected"] == 20


def test_native_ratio_has_no_epsilon_or_clipping():
    nuclei = np.array([[0, 0, 0], [0, 1, 1], [0, 0, 0]], dtype=np.uint32)
    nucleoli = np.array([[0, 0, 0], [0, 1, 0], [0, 0, 0]], dtype=np.uint32)
    ncl = np.array([[10, 10, 10], [10, 50, 20], [10, 10, 10]], dtype=np.uint16)
    channels = {"dapi": ncl, "ncl": ncl, "gfp": ncl}
    background = np.zeros((3, 3), bool)
    background[0, :] = True
    row = measure(channels, nuclei, nucleoli, background, Recipe(), {}, "field")[0][0]
    assert row["ncl_nucleoplasm_over_nucleoli"] == 0.25
    assert row["ncl_log2_nucleoplasm_over_nucleoli"] == math.log2(0.25)
    assert row["legacy_epsilon"] is None
