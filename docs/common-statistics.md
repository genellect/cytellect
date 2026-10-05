# Explicit common statistics and graphs

This opt-in analysis increment adds generic comparison protocol **2.0.0** and
generic association protocol **1.0.0**, with common inference/figure/Methods
protocols **1.0.0**. Historical generic comparison 1.0.0, its serialized
fingerprints, old Methods and replay behavior remain unchanged. New requests
must carry their explicit version. Source implementation and synthetic
reference checks are bounded evidence, not scientific, browser, package or
researcher acceptance.

## Research decision and inferential unit

Choose the scientific question and test before examining its p-value. No
Shapiro pretest, significance optimization or automatic choice from outcomes is
performed. Every test uses field median → sample mean of fields → independent
experimental-unit mean of samples. Region and field counts do not inflate n.
Saved identity, acquisition review, source revision, missing/excluded observations,
all input units and complete pairs use the existing generic comparison ledger.
Nonfinite values, undefined test-specific variation, insufficient groups/units, ambiguous
units and incomplete pairs fail explicitly. An unexcluded unit without values
must be repaired or explicitly excluded at the source, never silently dropped.

| Question | Explicit test | Minimum and interpretation |
|---|---|---|
| Two independent groups, mean difference | Welch t | At least two units per group and positive total sampling variance; heteroscedastic t reference |
| Two matched conditions, mean difference | Paired t | At least two complete pairs; nondegenerate differences |
| Two independent distributions | Mann–Whitney U | At least two units per group, allowing within-group constants; equality of distributions, not a general median test |
| Two matched distributions | Wilcoxon signed-rank | At least two complete pairs and one nonzero difference; differences symmetric about zero under the null |
| Three or more independent groups, means | Welch ANOVA | At least two units and positive finite variance per group |
| Three or more independent distributions | Kruskal–Wallis | At least two units per group and variation in the pooled values; rank-distribution omnibus |
| Linear association between two outcomes | Pearson | At least three matched independent units; beta null under independent normal samples |
| Monotonic association between two outcomes | Spearman | At least three matched independent units; pairing permutation null |

Constant inputs are handled by the selected method, not a universal prefilter.
Pearson/Spearman reject either constant axis; Welch ANOVA requires positive finite
variance in every group. Welch/paired t retain their original estimability guards
and allow a constant axis when the relevant standard error remains positive.
Mann–Whitney permits constant groups, including the all-pooled-tied degenerate
null (U = nA*nB/2, p = 1, superiority = 0.5). Kruskal–Wallis permits constant
groups with different values but rejects all-pooled-tied values because its tie
correction is zero. Wilcoxon rejects all-zero differences; one nonzero difference
among at least two complete pairs has two possible signs and exact p = 1.
These cases remain explicitly described in the saved resolved-method settings.

For three or more independent groups an omnibus method is required. Welch ANOVA
uses planned Welch t contrasts; Kruskal–Wallis uses planned Mann–Whitney contrasts.
All contrasts run regardless of the omnibus p-value. Holm correction covers
exactly the complete declared contrast family; the one declared omnibus is
reported separately. These comparisons are **not Dunn or Games–Howell tests**.
T-test mean-difference intervals are pointwise 95%, never Holm-adjusted or
simultaneous. Rank tests report a probability of superiority (Mann–Whitney,
ties half) or matched rank-biserial coefficient (Wilcoxon), without fabricated
mean/median estimates or confidence intervals.

## Deterministic computational policy

The lock and verified runtime contain SciPy 1.18.1 and statsmodels 0.15.0;
no new dependency is introduced. Actual SciPy version is saved per test.

- Mann–Whitney uses the exact U distribution if the smaller group has at most
  eight units and pooled values have no ties. Otherwise a group smaller than
  twenty uses an independent-label permutation; both groups at least twenty
  use the tie-corrected normal approximation with continuity correction.
- Wilcoxon removes zero differences (`wilcox` policy), assigns average ranks
  to equal absolute differences, and sign-permutes those ranks. This remains
  a conditional signed-rank randomization test when ties are present. It does
  not mislabel SciPy's untied exact distribution as exact for tied differences.
  Differences are not rounded; exact floating-point subtraction is recorded.
- Kruskal–Wallis uses pooled average ranks and the H tie correction. If any
  group has fewer than five units, an independent-label permutation replaces
  the chi-square approximation. Otherwise the chi-square reference is used.
- Spearman assigns average marginal ranks and permutes only X's pairing with
  the fixed Y rank vector. No small-sample asymptotic Spearman p-value is used.
- Permutation spaces up to 40,320 arrangements are fully enumerated. Larger
  spaces use 9,999 random draws, NumPy `default_rng(0)`, batch size 128 and the
  conservative plus-one numerator/denominator. The saved result records exact
  versus Monte Carlo, seed, budget, space size, ties, zeros and the resolution
  floor. The minimum attainable p is computed from the complete conditional
  distribution only for exact tests; Monte Carlo leaves it unknown.
- Two-sided permutation p is twice the smaller inclusive tail, capped at one.
  Kruskal–Wallis uses the inclusive upper tail. Monte Carlo p-values have
  simulation uncertainty; the saved seed makes a replay deterministic, not
  more precise. No result is retried to obtain a smaller p-value.

## Generic two-outcome associations

Both axis selections name the region set, actual channel (or channel-free area)
and metric. Identical selections or different region sets are rejected. The
outcomes are separately aggregated, then joined on `(condition,
experimental_unit)`, not row order or cell correspondence. Each point is one
matched independent unit. Axis-specific source/field/sample/unit tables and
missingness remain available; different retained region counts on the axes are
reported. Any unmatched unexcluded unit blocks the calculation.

The default computes one association per declared condition, applying Holm to
the declared set of association scopes. Pooling requires a separate explicit
acknowledgment and records a condition/acquisition-confounding warning. Groups
and acquisition-date/batch ledgers are preserved. No regression, intensity
normalization, batch adjustment, confidence band or causal conclusion is added.

## Graph and Methods contracts

Comparison plots support unit points, declared pair connectors, boxplots,
violin plots and histograms. All use the same experimental-unit values as the
tests. Boxes use NumPy linear quartiles and observed whisker endpoints within
1.5 IQR, retaining every unit as a point. Violins use a Gaussian KDE with Scott
bandwidth and a 100-point grid limited to the observed range; their width is a
descriptive density, not a confidence interval. Histograms share equal-width
bins across conditions, with saved endpoints/counts and individual-unit rugs.
The final bin includes its right endpoint. Distribution/box/violin points use
display-only jitter seed 0; paired connectors use saved pair identities.

Figure renderer 1.0.1 fixes categorical X limits at half a category outside each
end group. This keeps edge groups and their labels away from the plot boundary,
independently of jitter and group size. Numeric values, tests, summaries and
Methods are unchanged. Export and replay retain the saved renderer version;
1.0.0 figures keep their original autoscaling. Unknown versions are rejected.

Association scatter shows one matched independent-unit X/Y point, with no
fitted line. All figures export editable SVG, font-embedded PDF, 300 dpi PNG,
complete saved-value CSV tables and figure-data JSON with file hashes and exact
display coordinates. Regular font glyph coverage and label layout are checked.
Journal-size formatting does not imply journal acceptance.

`figure.common_statistics_methods = {kind: "common-statistics", version:
"1.0.0"}` selects the independent Methods path. It records the actual methods,
source identities, units, missingness, explicit design and Holm families,
resolved numerical settings and warnings. Historical
`cytellect-statistical-methods` templates cannot select this path.

## Independent evidence and primary sources

Focused tests independently enumerate Mann–Whitney allocations, tied/zero
Wilcoxon signs, small Kruskal partitions and tied Spearman pairings. Welch F
and Pearson p are checked against closed forms, and declared Holm correction
against manual arithmetic. These do not use the same SciPy function as an
oracle. Adapter tests cover version isolation, actual synthetic pixel-derived
unit matching, explicit pooling and omissions; renderer tests inspect editable
vectors, saved unit values, source hashes and histogram counts.

- [SciPy Mann–Whitney](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.mannwhitneyu.html)
- [SciPy Wilcoxon](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wilcoxon.html)
- [SciPy Welch ANOVA](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.f_oneway.html)
- [SciPy Kruskal–Wallis](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.kruskal.html)
- [SciPy Pearson](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.pearsonr.html)
- [SciPy Spearman](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html)
- [SciPy permutation conventions](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html)
