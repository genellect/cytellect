import math

import numpy as np
import pytest
from cytellect_analysis.compartment_summary import compartment_summary


def planes():
    nuclei = np.zeros((20, 40), np.uint32)
    nuclei[2:18, 2:18] = 1
    nuclei[2:18, 22:38] = 2
    nucleoli = np.zeros_like(nuclei)
    nucleoli[4:8, 4:8] = 1          # 16 px at 100
    nucleoli[10:12, 10:12] = 2      # 4 px at 300 (union mean is pixel-weighted: 140)
    plasm = np.where((nuclei == 1) & (nucleoli == 0), 1, 0).astype(np.uint32)
    image = np.full(nuclei.shape, 7, np.uint16)
    image[nuclei == 1] = 70
    image[4:8, 4:8] = 100
    image[10:12, 10:12] = 300
    image[nuclei == 2] = 50
    return nuclei, nucleoli, plasm, image


def test_union_mean_ratio_and_integrated_values_are_exact():
    nuclei, nucleoli, plasm, image = planes()
    rows = {row["nucleus_id"]: row for row in compartment_summary(nuclei, nucleoli, plasm, image)["rows"]}
    first = rows[1]
    assert first["nucleolar_count"] == 2 and first["nucleolar_area_px"] == 20
    assert first["nucleolar_mean"] == pytest.approx((16 * 100 + 4 * 300) / 20)
    assert first["nucleoplasm_mean"] == pytest.approx(70)
    assert first["log2_nucleoplasm_over_nucleolus"] == pytest.approx(math.log2(70 / 140))
    assert first["integrated_ratio_nucleolus_over_nucleoplasm"] == pytest.approx(2800 / (70 * (256 - 20)))
    assert rows[2]["missing_reason"] == "no_nucleolus" and rows[2]["log2_nucleoplasm_over_nucleolus"] is None


def test_background_correction_and_nonpositive_values_are_missing_not_zero():
    nuclei, nucleoli, plasm, image = planes()
    corrected = {row["nucleus_id"]: row for row in compartment_summary(nuclei, nucleoli, plasm, image, background=7)["rows"]}[1]
    assert corrected["nucleoplasm_mean"] == pytest.approx(63) and corrected["values"] == "background_corrected"
    assert corrected["log2_nucleoplasm_over_nucleolus"] == pytest.approx(math.log2(63 / 133))
    dark = {row["nucleus_id"]: row for row in compartment_summary(nuclei, nucleoli, plasm, image, background=80)["rows"]}[1]
    assert dark["missing_reason"] == "nonpositive_signal" and dark["ratio_nucleoplasm_over_nucleolus"] is None


def test_inconsistent_masks_are_rejected():
    nuclei, nucleoli, plasm, image = planes()
    plasm[4, 4] = 1
    with pytest.raises(ValueError, match="compartment_summary_masks_inconsistent"):
        compartment_summary(nuclei, nucleoli, plasm, image)
