"""Independent references: closed-form t(df=2) and explicit CRV1 matrix algebra."""
import math

import numpy as np
import pytest
from cytellect_analysis.contracts import StatisticsRequest
from cytellect_analysis.statistics import analyze
from scipy.integrate import quad


def observation(group, unit, value, **extra):
    return {"condition": group, "experimental_unit": f"{group}{unit}", "sample": f"s{group}{unit}",
            "field_id": f"f{group}{unit}", "acquisition_date": "d", "value": value,
            "excluded": False, "gfp_positive": True, **extra}


def spec(**extra):
    return StatisticsRequest(metric="value", baseline="A", comparisons=[("A", "B")],
                             independent_units_confirmed=True, **extra)


def test_welch_closed_form_df_two_reference():
    rows = [observation(g, i, value) for g, values in (("A", [0, 2]), ("B", [3, 5]))
            for i, value in enumerate(values)]
    result = analyze(rows, spec())["comparisons"][0]
    # nA=nB=2, sA²=sB²=2; Welch df=2. F_t2(t)=1/2+t/(2sqrt(t²+2)).
    critical = math.sqrt(2 * .95**2 / (1 - .95**2))
    assert result["estimate"] == -3
    assert result["degrees_of_freedom"] == 2
    assert result["standard_error"] == pytest.approx(math.sqrt(2))
    assert result["statistic"] == pytest.approx(-3 / math.sqrt(2))
    assert result["p_value"] == pytest.approx(1 - 3 / math.sqrt(13))
    assert result["ci_low"] == pytest.approx(-3 - critical * math.sqrt(2))
    assert result["ci_high"] == pytest.approx(-3 + critical * math.sqrt(2))


def test_paired_closed_form_df_two_reference():
    rows = [observation(g, i, v, pair=f"p{i}") for g, values in (("A", [3, 8, 2]), ("B", [4, 10, 5]))
            for i, v in enumerate(values)]
    result = analyze(rows, spec(paired=True))["comparisons"][0]
    # Differences -1,-2,-3: mean=-2, s=1, SE=1/sqrt(3), df=2.
    assert result["estimate"] == -2
    assert result["standard_error"] == pytest.approx(1 / math.sqrt(3))
    assert result["degrees_of_freedom"] == 2
    assert result["p_value"] == pytest.approx(1 - math.sqrt(6 / 7))


def test_field_cluster_covariance_matches_explicit_sandwich():
    rows = []
    for group in ("A", "B"):
        for field in range(4):
            for cell in range(3):
                log_gfp = cell + .17 * field
                value = 2 + (group == "B") * 1.3 + .8 * log_gfp + (field - 1.5) * .21 + (-1)**(field + cell) * .13
                rows.append(observation(group, field, value, gfp_mean_corrected=2**log_gfp))
    result = analyze(rows, spec(mode="exploratory"))
    log_gfp = np.log2([r["gfp_mean_corrected"] for r in rows])
    x = np.column_stack([np.ones(len(rows)), [r["condition"] == "B" for r in rows],
                         log_gfp - np.median(log_gfp)])
    y = np.array([r["value"] for r in rows])
    bread = np.linalg.inv(x.T @ x)
    beta = bread @ x.T @ y
    residual = y - x @ beta
    scores = [x[[r["field_id"] == f for r in rows]].T @ residual[[r["field_id"] == f for r in rows]]
              for f in sorted({r["field_id"] for r in rows})]
    g, n, k = len(scores), len(rows), x.shape[1]
    covariance = bread @ sum(np.outer(u, u) for u in scores) @ bread * g / (g - 1) * (n - 1) / (n - k)
    standard_error = math.sqrt(covariance[1, 1])
    statistic = -beta[1] / standard_error
    # Integrate t density independently; no t-test, statsmodels, or SciPy t-CDF reference.
    df = g - 1
    normalizer = math.exp(math.lgamma((df + 1)/2) - math.lgamma(df/2)) / math.sqrt(df * math.pi)
    p = 2 * quad(lambda t: normalizer * (1 + t*t/df)**(-(df + 1)/2), abs(statistic), math.inf)[0]
    comparison = result["comparisons"][0]
    assert comparison["estimate"] == pytest.approx(-beta[1])
    assert comparison["standard_error"] == pytest.approx(standard_error)
    assert comparison["degrees_of_freedom"] == df
    assert comparison["p_value"] == pytest.approx(p, rel=1e-9)
    from scipy.optimize import brentq
    critical = brentq(lambda t: quad(lambda u: normalizer * (1+u*u/df)**(-(df+1)/2), 0, t)[0] - .475, 0, 20)
    point = result["model"]["prediction_grid"][10]
    vector = np.array([1, point["condition"] == "B", point["gfp_centered"]])
    estimate = float(vector @ beta)
    half_width = critical * math.sqrt(float(vector @ covariance @ vector))
    assert point["mean"] == pytest.approx(estimate)
    assert [point["ci_low"], point["ci_high"]] == pytest.approx([estimate-half_width, estimate+half_width])



def test_missingness_and_gating_disclose_lost_units():
    rows = [observation(g, i, v, gfp_gate_exploratory=True)
            for g, values in (("A", [0, 2, None]), ("B", [3, 5, 6])) for i, v in enumerate(values)]
    result = analyze(rows, spec())
    missing = result["selection"]["by_condition"][0]
    assert missing["input_units"] == 3 and missing["selected_units"] == 2
    assert missing["missing_metric_selected"] == 1
    assert "some_experimental_units_have_no_selected_outcomes" in result["warnings"]
    assert any("independent_validation" in w for w in result["warnings"])


def test_self_covariate_and_partial_pair_metadata_are_rejected():
    rows = [observation(g, i, v, pair=f"p{i}", gfp_mean_corrected=v+1)
            for g, values in (("A", [1, 2, 3]), ("B", [3, 5, 6])) for i, v in enumerate(values)]
    with pytest.raises(ValueError, match="own_gfp_covariate"):
        analyze(rows, spec(mode="exploratory").model_copy(update={"metric": "gfp_mean_corrected"}))
    rows.append({**rows[0], "pair": None})
    with pytest.raises(ValueError, match="unique_complete_pairs"):
        analyze(rows, spec(paired=True))
