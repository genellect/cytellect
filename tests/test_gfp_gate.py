import numpy as np
import pytest
from cytellect_analysis.gfp_gate import apply_control_gate, control_thresholds


def rows():
    rng = np.random.default_rng(0)
    controls = [{"acquisition_date": "d1", "gfp_mean": float(v), "control": True} for v in rng.normal(10, 2, 200)]
    cells = [{"acquisition_date": "d1", "gfp_mean": v, "control": False} for v in (5.0, 30.0, None)]
    other = [{"acquisition_date": "d2", "gfp_mean": 50.0, "control": False}]
    return controls + cells + other


def test_threshold_is_the_control_percentile_per_date():
    data = rows()
    thresholds = control_thresholds(data, percentile=99)
    values = [row["gfp_mean"] for row in data if row["control"]]
    assert thresholds["dates"]["d1"]["threshold"] == pytest.approx(np.percentile(values, 99))
    assert thresholds["dates"]["d2"] == {"threshold": None, "control_nuclei": 0, "missing_reason": "too_few_control_nuclei"}


def test_gate_labels_cells_and_never_treats_missing_thresholds_as_positive():
    data = rows()
    gated = apply_control_gate(data, control_thresholds(data))
    cells = [row for row in gated if not row["control"]]
    assert [row["gfp_gate_reason"] for row in cells] == ["within_control_range", "above_control_threshold", "gfp_missing", "too_few_control_nuclei"]
    assert [row["gfp_positive"] for row in cells] == [False, True, False, False]
    assert all(row["gfp_gate_reason"] == "negative_control" for row in gated if row["control"])


def test_percentile_bounds():
    with pytest.raises(ValueError, match="gfp_control_percentile_invalid"):
        control_thresholds(rows(), percentile=40)
