"""Hand references for the shared inference core; no copied t-test expectations."""
import math

import numpy as np
import pandas as pd
import pytest
from cytellect_analysis.unit_inference import aggregate_unit_observations, apply_holm, compare_unit_arrays


def test_hierarchical_weights_expose_the_intermediate_sample_means():
    rows = [{"condition": "A", "experimental_unit": "unit", "sample": "s1", "field_id": "f1", "value": 2},
            *[{"condition": "A", "experimental_unit": "unit", "sample": "s1", "field_id": "f2", "value": 10}] * 100,
            {"condition": "A", "experimental_unit": "unit", "sample": "s2", "field_id": "f3", "value": 20}]
    fields, samples, units = aggregate_unit_observations(pd.DataFrame(rows), "value")
    assert fields.value.tolist() == [2, 10, 20]
    assert samples.value.tolist() == [6, 20]
    assert units.value.tolist() == [13]


@pytest.mark.parametrize("scale", [1e-18, 1, 1e18])
def test_hand_paired_reference_is_scale_invariant(scale):
    result = compare_unit_arrays([3 * scale, 8 * scale, 2 * scale],
                                 [4 * scale, 10 * scale, 5 * scale], paired=True)
    assert result["estimate"] / scale == pytest.approx(-2)
    assert result["standard_error"] / scale == pytest.approx(1 / math.sqrt(3))
    assert result["p_value"] == pytest.approx(1 - math.sqrt(6 / 7))


def test_holm_order_ties_zero_and_one_match_step_down_arithmetic():
    inputs = [("z", 0.0), ("b", .01), ("c", .01), ("d", .04), ("e", 1.0)]
    expected = {"z": 0.0, "b": .04, "c": .04, "d": .08, "e": 1.0}
    for sequence in (inputs, list(reversed(inputs)), inputs[2:] + inputs[:2]):
        output = apply_holm([{"id": key, "p_value": p} for key, p in sequence], "declared")
        assert {row["id"]: row["p_holm"] for row in output} == pytest.approx(expected)


def test_paired_estimate_uses_mean_differences_instead_of_subtracting_large_means():
    result = compare_unit_arrays([1e16 + 2, 1e16 + 4, 1e16 + 8], [1e16] * 3, paired=True)
    # Exact representable differences are 2,4,8; their mean is 14/3, not 6.
    assert result["estimate"] == pytest.approx(14 / 3)
    assert result["standard_error"] == pytest.approx(math.sqrt(28) / 3)
    assert (result["ci_low"] + result["ci_high"]) / 2 == pytest.approx(14 / 3)


def test_unsigned_paired_differences_keep_their_sign():
    result = compare_unit_arrays(np.array([1, 5, 4], dtype=np.uint8),
                                 np.array([2, 4, 7], dtype=np.uint8), paired=True)
    # Differences -1,+1,-3: mean -1; sample variance 4; SE=2/sqrt(3).
    assert result["estimate"] == -1
    assert result["standard_error"] == pytest.approx(2 / math.sqrt(3))
    assert result["statistic"] == pytest.approx(-math.sqrt(3) / 2)


@pytest.mark.parametrize("a,b,paired", [([1], [2], False), ([1, 2], [3], True),
                                       ([1, 1], [2, 2], False), ([1, 2], [2, 3], True),
                                       ([True, False], [True, True], False), ([1, float('nan')], [2, 3], False)])
def test_nonestimable_arrays_are_not_fixed_with_epsilon(a, b, paired):
    with pytest.raises(ValueError):
        compare_unit_arrays(a, b, paired=paired)
