"""Independent finite enumerations/closed forms; no SciPy call as oracle."""
import itertools
import math

import numpy as np
import pytest
from cytellect_analysis.common_unit_inference import (
    compare_common_units,
    correlate_common_units,
    omnibus_common_units,
)
from cytellect_analysis.unit_inference import apply_holm


def ranks(values):
    return [1 + sum(other < value for other in values) + (sum(other == value for other in values) - 1) / 2
            for value in values]


def test_mann_whitney_exact_and_tied_permutation_against_all_allocations():
    for a, b in (([1, 2, 3], [4, 5, 6]), ([1, 2, 2], [2, 4, 5]), ([1, 1, 1], [2, 2, 2])):
        pooled = a + b
        rr = ranks(pooled)
        observed = sum(rr[:len(a)]) - len(a) * (len(a) + 1) / 2
        possible = [sum(rr[i] for i in indices) - len(a) * (len(a) + 1) / 2
                    for indices in itertools.combinations(range(len(pooled)), len(a))]
        expected = min(1, 2 * min(sum(u <= observed for u in possible), sum(u >= observed for u in possible)) / len(possible))
        actual = compare_common_units(a, b, "mann-whitney-u")
        assert actual["statistic"] == observed
        assert actual["p_value"] == pytest.approx(expected)
        assert actual["effect"] == observed / (len(a) * len(b))
        assert actual["estimate"] is None  # Never relabel U as a mean/median difference.


def test_wilcoxon_ties_and_zeros_against_sign_enumeration():
    a, b = [1, 3, 5, 8, 9], [1, 2, 7, 6, 6]
    differences = [x - y for x, y in zip(a, b, strict=True) if x != y]
    rr = ranks([abs(d) for d in differences])
    positive = sum(rank for rank, difference in zip(rr, differences, strict=True) if difference > 0)
    possible = [sum(rank for rank, sign in zip(rr, signs, strict=True) if sign > 0)
                for signs in itertools.product((-1, 1), repeat=len(rr))]
    p = min(1, 2 * min(sum(w <= positive for w in possible), sum(w >= positive for w in possible)) / len(possible))
    result = compare_common_units(a, b, "wilcoxon")
    assert result["statistic"] == min(positive, sum(rr) - positive)
    assert result["p_value"] == p
    assert result["method_settings"]["zero_pairs"] == 1
    assert result["method_settings"]["ties"] is True
    assert result["method_settings"]["resamples"] == 16


def test_welch_anova_closed_form_f_and_survival_with_numerator_df_two():
    # Three groups of n=3, variance=1. Welch F=(27)/(7/6)=162/7;
    # df=(2,4). For F(2,v), survival=(v/(v+2F))**(v/2).
    result = omnibus_common_units([[1, 2, 3], [4, 5, 6], [7, 8, 9]], "welch-anova")
    assert result["statistic"] == pytest.approx(162 / 7)
    assert result["method_settings"]["degrees_of_freedom_denominator"] == pytest.approx(4)
    assert result["p_value"] == pytest.approx((7 / 88) ** 2)


def test_kruskal_small_sample_exact_against_all_partitions():
    values = [1, 2, 3, 4, 5, 6]
    def h(groups):
        return 12 / (6 * 7) * sum(sum(group) ** 2 / len(group) for group in groups) - 3 * 7
    observed = h(([1, 2], [3, 4], [5, 6]))
    null = []
    for a in itertools.combinations(values, 2):
        rest = [v for v in values if v not in a]
        for b in itertools.combinations(rest, 2):
            null.append(h((a, b, [v for v in rest if v not in b])))
    expected = sum(v >= observed - 1e-12 for v in null) / len(null)
    result = omnibus_common_units([[1, 2], [3, 4], [5, 6]], "kruskal-wallis")
    assert len(null) == 90
    assert result["statistic"] == pytest.approx(observed)
    assert result["p_value"] == expected == 6 / 90


def test_spearman_tied_exact_against_all_pairings():
    x, y = [1, 2, 2, 4], [3, 1, 2, 4]
    rx, ry = ranks(x), ranks(y)
    def correlation(a, b):
        aa, bb = [v - sum(a) / len(a) for v in a], [v - sum(b) / len(b) for v in b]
        return sum(u * v for u, v in zip(aa, bb, strict=True)) / math.sqrt(sum(u * u for u in aa) * sum(v * v for v in bb))
    observed = correlation(rx, ry)
    possible = [correlation(p, ry) for p in itertools.permutations(rx)]
    expected = min(1, 2 * min(sum(v <= observed + 1e-12 for v in possible),
                             sum(v >= observed - 1e-12 for v in possible)) / len(possible))
    result = correlate_common_units(x, y, "spearman")
    assert result["coefficient"] == pytest.approx(observed)
    assert result["p_value"] == expected
    assert result["method_settings"]["ties_x"]


def test_pearson_n_four_uniform_beta_null_closed_form():
    # Orthogonal centered vectors x and z with equal norms; y=.8*x+.6*z.
    # Under rho=0, n=4 Pearson r is uniform on [-1,1], hence p=1-|r|.
    result = correlate_common_units([-1, -1, 1, 1], [-1.4, -.2, .2, 1.4], "pearson")
    assert result["coefficient"] == pytest.approx(.8)
    assert result["p_value"] == pytest.approx(.2)


def test_permutation_budget_seed_and_positive_p_are_reproducible():
    x, y = np.arange(9), np.array([0, 2, 1, 4, 3, 6, 5, 8, 7])
    a, b = correlate_common_units(x, y, "spearman"), correlate_common_units(x, y, "spearman")
    assert a == b
    settings = a["method_settings"]
    assert settings["seed"] == 0 and settings["resamples"] == 9999
    assert settings["monte_carlo_plus_one"] is True
    assert a["p_value"] >= 2 / 10000


def test_holm_declared_family_closed_form():
    results = [{"p_value": p} for p in (.04, .01, .03)]
    apply_holm(results, "planned")
    assert [row["p_holm"] for row in results] == [.06, .03, .06]


@pytest.mark.parametrize("bad", [[1], [1, np.nan], [1, np.inf], [True, False], [[1, 2]]])
def test_invalid_units_never_silently_filtered(bad):
    with pytest.raises(ValueError):
        compare_common_units(bad, [1, 3], "mann-whitney-u")


def test_degenerate_pair_and_group_designs_rejected():
    with pytest.raises(ValueError, match="nonzero"):
        compare_common_units([1, 2, 3], [1, 2, 3], "wilcoxon")
    with pytest.raises(ValueError, match="constant"):
        omnibus_common_units([[1, 2], [3, 4], [5, 5]], "welch-anova")
    with pytest.raises(ValueError, match="three_groups"):
        omnibus_common_units([[1, 2], [3, 4]], "kruskal-wallis")


@pytest.mark.parametrize("n", [3, 20])
def test_all_tied_mann_whitney_has_defined_degenerate_null(n):
    result = compare_common_units([2] * n, [2] * n, "mann-whitney-u")
    # All allocations put average rank n+.5 on every observation, hence U=n*n/2.
    assert result["statistic"] == n * n / 2
    assert result["p_value"] == 1
    assert result["effect"] == .5
    assert result["method_settings"]["p_value_method"] == "exact degenerate U null"


def test_wilcoxon_constant_axis_and_single_nonzero_difference_are_defined():
    # Differences [1,-1,-2], ranks [1.5,1.5,3]: 3/8 in the smaller inclusive tail.
    result = compare_common_units([2, 2, 2], [1, 3, 4], "wilcoxon")
    assert result["statistic"] == 1.5
    assert result["p_value"] == .75
    # A single nonzero rank has exactly two possible signs; two-sided p=1.
    single = compare_common_units([1, 1], [1, 2], "wilcoxon")
    assert single["statistic"] == 0 and single["p_value"] == 1
    assert single["method_settings"]["nonzero_pairs"] == 1
    assert single["method_settings"]["zero_pairs"] == 1
    assert single["method_settings"]["resamples"] == 2


def test_constant_groups_kruskal_tie_corrected_reference():
    # Ranks [1.5,1.5,3.5,3.5,5.5,5.5]. Tie correction=1-18/210;
    # H=5, with 6 maximally segregated allocations of 90 possible allocations.
    result = omnibus_common_units([[1, 1], [2, 2], [3, 3]], "kruskal-wallis")
    assert result["statistic"] == pytest.approx(5)
    assert result["p_value"] == pytest.approx(6 / 90)
    # n=5 per group resolves to chi-square df2, whose survival is exp(-H/2).
    large = omnibus_common_units([[1] * 5, [2] * 5, [3] * 5], "kruskal-wallis")
    assert large["statistic"] == pytest.approx(14)
    assert large["p_value"] == pytest.approx(math.exp(-7))
    with pytest.raises(ValueError, match="constant"):
        omnibus_common_units([[1, 1], [1, 1], [1, 1]], "kruskal-wallis")


@pytest.mark.parametrize("method", ["pearson", "spearman"])
def test_constant_correlation_axis_remains_undefined(method):
    with pytest.raises(ValueError, match="constant"):
        correlate_common_units([1, 1, 1], [1, 2, 3], method)
    with pytest.raises(ValueError, match="constant"):
        correlate_common_units([1, 2, 3], [1, 1, 1], method)


@pytest.mark.parametrize("method", ["welch-t", "paired-t"])
def test_one_constant_t_test_axis_has_positive_sampling_variance(method):
    result = compare_common_units([1, 1, 1], [2, 3, 4], method)
    assert result["estimate"] == -2
    assert result["statistic"] == pytest.approx(-2 * math.sqrt(3))
    assert result["degrees_of_freedom"] == pytest.approx(2)
    with pytest.raises(ValueError, match="not_estimable"):
        compare_common_units([1, 1, 1], [2, 2, 2], method)
