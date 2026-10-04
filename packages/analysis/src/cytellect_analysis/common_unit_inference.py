"""Explicit common tests on already aggregated independent experimental units.

Protocol 1.0.0. Deterministic resolution depends on sample size and ties, never p.
The caller owns independence, source matching, selection and Holm family scope.
"""
import math
from types import SimpleNamespace

import numpy as np
import scipy
from scipy import stats

from .unit_inference import compare_unit_arrays

VERSION = "1.0.0"
SEED = 0
RESAMPLES = 9999
EXACT_LIMIT = 40320


def _array(value, minimum=2):
    raw = np.asarray(value)
    if raw.ndim != 1 or raw.dtype.kind not in "iuf" or not np.isfinite(raw).all():
        raise ValueError("common_statistics_finite_units_required")
    data = raw.astype(float)
    if len(data) < minimum:
        raise ValueError("common_statistics_insufficient_units")
    return data


def _settings(**kwargs):
    return {"inference_version": VERSION, "scipy_version": scipy.__version__,
            "inferential_unit": "independent experimental unit", "alternative": "two-sided",
            "selection": "explicit researcher choice; no normality pretest or p-based selection",
            "seed": None, "resamples": None, **kwargs}


def _finite(result):
    if not np.isfinite([result["statistic"], result["p_value"]]).all():
        raise ValueError("common_statistics_not_estimable")
    return result


def _permutation(data, statistic, arrangements, *, kind="independent", alternative="two-sided"):
    exact = arrangements <= EXACT_LIMIT
    budget = arrangements if exact else RESAMPLES
    result = stats.permutation_test(data, statistic, permutation_type=kind, vectorized=True,
                                    n_resamples=budget, batch=128, alternative=alternative,
                                    rng=np.random.default_rng(SEED))
    attainable = None
    if exact:
        null = result.null_distribution
        tail_count = (min(np.count_nonzero(np.isclose(null, null.min(), rtol=1e-14, atol=0)),
                          np.count_nonzero(np.isclose(null, null.max(), rtol=1e-14, atol=0)))
                      if alternative == "two-sided" else np.count_nonzero(np.isclose(null, null.max(), rtol=1e-14, atol=0)))
        attainable = min(1.0, (2 if alternative == "two-sided" else 1) * int(tail_count) / budget)
    settings = _settings(p_value_method="exact permutation" if exact else "Monte Carlo permutation",
                         permutation_type=kind, alternative=alternative,
                         seed=None if exact else SEED, resamples=budget,
                         possible_arrangements=arrangements, exact_enumeration_limit=EXACT_LIMIT,
                         monte_carlo_budget=RESAMPLES,
                         minimum_attainable_p=attainable,
                         p_resolution_floor=(2 if alternative == "two-sided" else 1) / (budget if exact else budget + 1),
                         p_convention="twice smaller inclusive tail, capped at one" if alternative == "two-sided"
                         else "inclusive upper tail", monte_carlo_plus_one=not exact)
    return result, settings


def compare_common_units(a, b, method):
    a, b = _array(a), _array(b)
    if method in ("welch-t", "paired-t"):
        result = compare_unit_arrays(a, b, paired=method == "paired-t")
        result["method_settings"] = _settings(p_value_method="Student t reference distribution")
        return result
    base = {"n_a": len(a), "n_b": len(b), "n_unit": "independent experimental units",
            "estimate": None, "ci_low": None, "ci_high": None,
            "degrees_of_freedom": None, "standard_error": None, "confidence_level": None,
            "alternative": "two-sided"}
    if method == "mann-whitney-u":
        tied = len(np.unique(np.r_[a, b])) != len(a) + len(b)
        if np.all(np.r_[a, b] == a[0]):
            # Every allocation has U=n_a*n_b/2: the null is degenerate but
            # defined, with both inclusive tails equal to one.
            test = SimpleNamespace(statistic=len(a) * len(b) / 2, pvalue=1.0)
            settings = _settings(p_value_method="exact degenerate U null", ties=True,
                                 tie_policy="all pooled values tied; every allocation has identical U",
                                 continuity_correction=False, minimum_attainable_p=1.0)
        elif not tied and min(len(a), len(b)) <= 8:
            test = stats.mannwhitneyu(a, b, alternative="two-sided", method="exact", use_continuity=False)
            settings = _settings(p_value_method="exact U distribution", ties=False, continuity_correction=False,
                                 minimum_attainable_p=2 / math.comb(len(a) + len(b), len(a)))
        elif min(len(a), len(b)) < 20:
            def u_statistic(x, y, axis):
                ranks = stats.rankdata(np.concatenate((x, y), axis=axis), axis=axis)
                return ranks[..., :x.shape[axis]].sum(axis=axis) - x.shape[axis] * (x.shape[axis] + 1) / 2
            test, settings = _permutation((a, b), u_statistic, math.comb(len(a) + len(b), len(a)))
            settings.update(ties=tied, tie_policy="average pooled ranks", continuity_correction=False)
        else:
            test = stats.mannwhitneyu(a, b, alternative="two-sided", method="asymptotic", use_continuity=True)
            settings = _settings(p_value_method="asymptotic normal", ties=tied,
                                 tie_policy="average ranks and tie-corrected variance", continuity_correction=True)
        base.update(method="Mann–Whitney U", statistic_name="U for group A",
                    effect_name="probability of superiority A over B (ties half)",
                    effect=float(test.statistic / (len(a) * len(b))),
                    null_hypothesis="equal distributions; not a general test of medians")
    elif method == "wilcoxon":
        if len(a) != len(b):
            raise ValueError("incomplete_pairs")
        differences = a - b
        if not np.isfinite(differences).all():
            raise ValueError("common_statistics_not_estimable")
        zeros = int(np.count_nonzero(differences == 0))
        nonzero = differences[differences != 0]
        if not len(nonzero):
            raise ValueError("common_statistics_insufficient_nonzero_pairs")
        # Permute signed ranks themselves. This is the signed-rank randomization
        # distribution conditional on observed absolute differences, including ties.
        ranks = stats.rankdata(np.abs(nonzero))
        signed = ranks * np.sign(nonzero)
        def signed_rank_statistic(x, axis):
            return np.maximum(x, 0).sum(axis=axis)
        if len(nonzero) == 1:
            # SciPy permutation_test requires sample length >=2, but the
            # two-sign conditional distribution is defined without simulation.
            test = SimpleNamespace(statistic=float(max(signed[0], 0)), pvalue=1.0)
            settings = _settings(p_value_method="exact permutation", permutation_type="samples",
                                 resamples=2, possible_arrangements=2, minimum_attainable_p=1.0,
                                 p_resolution_floor=1.0, monte_carlo_plus_one=False,
                                 p_convention="twice smaller inclusive tail, capped at one")
        else:
            test, settings = _permutation((signed,), signed_rank_statistic, 2 ** len(nonzero), kind="samples")
        w_plus = float(test.statistic)
        base.update(method="Wilcoxon signed-rank", statistic_name="minimum signed-rank sum",
                    effect_name="matched rank-biserial correlation A minus B",
                    effect=float(2 * w_plus / ranks.sum() - 1), complete_pairs=len(a),
                    null_hypothesis="paired differences symmetric about zero")
        base["statistic"] = min(w_plus, float(ranks.sum()) - w_plus)
        settings.update(zero_method="wilcox: remove zero differences before ranking", zero_pairs=zeros,
                        nonzero_pairs=len(nonzero), ties=len(np.unique(np.abs(nonzero))) != len(nonzero),
                        tie_policy="average absolute-difference ranks", continuity_correction=False,
                        difference_rounding="none; exact floating-point differences")
    else:
        raise ValueError("common_statistics_unknown_method")
    base.update(p_value=float(test.pvalue), method_settings=settings)
    base.setdefault("statistic", float(test.statistic))
    return _finite(base)


def omnibus_common_units(groups, method):
    arrays = [_array(values) for values in groups]
    if len(arrays) < 3:
        raise ValueError("common_statistics_three_groups_required")
    if method == "welch-anova":
        variance = np.array([np.var(a, ddof=1) for a in arrays])
        if np.any(variance == 0):
            raise ValueError("common_statistics_constant_units")
        if not np.isfinite(variance).all() or np.any(variance < 0):
            raise ValueError("common_statistics_not_estimable")
        test = stats.f_oneway(*arrays, equal_var=False, nan_policy="raise")
        # Welch (1951) denominator df; exposed alongside the SciPy F statistic.
        n = np.array([len(a) for a in arrays], dtype=float)
        weight = n / variance
        term = np.sum((1 - weight / weight.sum()) ** 2 / (n - 1))
        df_num, df_den = len(arrays) - 1, (len(arrays) ** 2 - 1) / (3 * term)
        settings = _settings(p_value_method="Welch F approximation", alternative="omnibus",
                             equal_variance=False, degrees_of_freedom_numerator=df_num,
                             degrees_of_freedom_denominator=float(df_den))
        name = "Welch ANOVA"
    elif method == "kruskal-wallis":
        pooled = np.concatenate(arrays)
        if np.all(pooled == pooled[0]):
            # Only pooled constants make the Kruskal tie-correction zero.
            raise ValueError("common_statistics_constant_units")
        if min(map(len, arrays)) >= 5:
            test = stats.kruskal(*arrays, nan_policy="raise")
            settings = _settings(p_value_method="asymptotic chi-square", alternative="omnibus",
                                 degrees_of_freedom=len(arrays) - 1)
        else:
            arrangements, remaining = 1, sum(map(len, arrays))
            for a in arrays[:-1]:
                arrangements *= math.comb(remaining, len(a))
                remaining -= len(a)
            def statistic(*values, axis):
                return stats.kruskal(*values, axis=axis, nan_policy="raise").statistic
            test, settings = _permutation(tuple(arrays), statistic, arrangements, alternative="greater")
        settings.update(tie_policy="pooled average ranks; tie correction to H",
                        ties=len(np.unique(np.concatenate(arrays))) != sum(map(len, arrays)))
        name = "Kruskal–Wallis"
    else:
        raise ValueError("common_statistics_unknown_method")
    return _finite({"method": name, "statistic": float(test.statistic), "p_value": float(test.pvalue),
                    "group_sizes": list(map(len, arrays)), "method_settings": settings,
                    "correction_family": None, "multiplicity": "one declared omnibus test; separate from planned contrast family"})


def correlate_common_units(x, y, method):
    x, y = _array(x, 3), _array(y, 3)
    if len(x) != len(y):
        raise ValueError("common_statistics_unmatched_units")
    if np.all(x == x[0]) or np.all(y == y[0]):
        raise ValueError("common_statistics_constant_units")
    if method == "pearson":
        test = stats.pearsonr(x, y, alternative="two-sided")
        settings = _settings(p_value_method="exact beta null distribution under independent normal samples",
                             null_hypothesis="zero population Pearson correlation")
    elif method == "spearman":
        # Ranking once permits a vectorized pairing permutation without refits.
        rx, ry = stats.rankdata(x), stats.rankdata(y)
        rx, ry = rx - rx.mean(), ry - ry.mean()
        denom = np.linalg.norm(rx) * np.linalg.norm(ry)
        def statistic(permuted, axis):
            return np.sum(permuted * ry, axis=axis) / denom
        test, settings = _permutation((rx,), statistic, math.factorial(len(x)), kind="pairings")
        settings.update(tie_policy="average marginal ranks", ties_x=len(np.unique(x)) != len(x),
                        ties_y=len(np.unique(y)) != len(y), null_hypothesis="random pairings / independence")
    else:
        raise ValueError("common_statistics_unknown_method")
    return _finite({"method": "Pearson correlation" if method == "pearson" else "Spearman rank correlation",
                    "statistic": float(test.statistic), "p_value": float(test.pvalue), "n_units": len(x),
                    "coefficient": float(test.statistic), "method_settings": settings,
                    "confidence_interval": None, "fit": "none; association is not causation"})
