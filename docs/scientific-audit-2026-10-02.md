# Scientific calculation audit — 2026-10-02

This is a software correctness audit, not a claim of Nature acceptance or biological validation.

## Independently checked

- Welch differences/SE/statistic/df/two-sided p and 95% interval against closed-form t(df=2) arithmetic.
- Paired differences/SE/df/p against a separate closed-form example.
- Field-clustered CRV1 estimate, covariance, t df and p against explicit matrix algebra and numerical integration of the t density.
- Hierarchical field-median → sample-mean → unit-mean weighting does not let a field with more cells dominate.
- Exact pixel arithmetic for NCL nuclear/nucleolar/nucleoplasmic means and log2 ratio; actual GFP-only inputs retain absent NCL values as missing.
- Explicit two-/three-channel OME mapping, no channel-axis guessing, Z/T/depth rejection, mask type and uint32 ID integrity.

## Material issues corrected in this audit

GFP outcomes previously could be regressed against their own GFP covariate. Partly absent pairing metadata could survive aggregation. Exclusion counts did not expose loss of complete experimental units. Comparison outputs lacked test statistic/df/SE. Field-cluster inference could include a condition represented by only one field. Native Otsu gates included explicitly excluded objects. Unsupported integer background masks could be interpreted as array indices. Fractional masks and large sparse uint32 IDs were not safely checked. Channel mappings on a TIFF without a channel axis could be ignored.

All now have explicit validation or truthful missing/limitation reporting. Statistical protocol is version1.2.0. Methods now uses actual per-field engine provenance and nested source revision history, recorded full parameters and replay links.

## Remaining scientific limits

No private raw dataset or independent region ground truth has been evaluated here. Nuclear/nucleolar F1 targets are unmeasured. Public microscopy execution is integration evidence, not a detection-accuracy estimate. The NCL demo has a documented disagreement between portal and embedded channel metadata.

Field-cluster covariance assumes independent fields and cannot remove dependence shared by fields from one biological unit. Such data are explicitly warned and exploratory; primary comparisons aggregate to independently declared units. CRV1 can have poor small-cluster coverage; three fields is a software estimability floor, not a scientifically adequate design. Distributional assumptions, biological independence, missing-data mechanism and prospective gate/contrast selection require study-specific review. Group/GFP/date regression describes associations and is not a causal adjustment guarantee.

NCL-defined regions can change as NCL redistributes. Neither editable figure dimensions nor exact p values make that measurement definition independent of the outcome. External biostatistical review and private held-out image validation remain required before making study-specific confirmatory claims.
