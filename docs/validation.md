# Validation layers

| Layer | Data | What it establishes |
|---|---|---|
| Numerical unit tests | Precisely defined synthetic pixels/masks | Equations, area/intensity arithmetic, invalid states, weighting, correction and replay |
| Image integration | Published real microscopy, source/axes/stains recorded | TIFF/engine/editor behavior on actual cells; detector comparison where annotation exists |
| Public interface | Redistribution-cleared real images with attribution | Browser display, selection, layout and accurate explanation of supported channels |
| Private scientific validation | User-provided raw images outside repo/Cloud | Suitability for the actual experiment, manual/Fiji agreement and legacy reconciliation |
| Researcher PoC | Accepted local installation or approved private host, and participants | Completion, correction time, comprehensibility and reuse demand |

Public image availability does not make an RGB figure an unmodified quantitative raw input. Do not fabricate missing GFP/NCL channels or use a different stain as NCL. Label projections/crops and display conversions. Keep a fixed evaluation subset; record StarDist training-overlap uncertainty rather than claim held-out generalization.

Required software checks are in [contributing](../CONTRIBUTING.md). Browser evidence must include upload → detection → edit → explicit review → measurement → statistics → private export, plus mobile/desktop display and console errors. Public demo inspection is a separate check. A compiled UI is not proof of browser behavior.

Private acceptance remains open until raw images are supplied and evaluated. Provisional F1 goals (.90 nuclei/.80 nucleoli at IoU.5) are targets, not achieved performance. Final quantitative acceptance prioritizes agreement between reviewed masks/original pixels and reference calculations. Never force prior p-values or fixed cohort counts.

## Recorded external and independent checks

- [BBBC039](public-validation.md): fixed published nuclear test subset; retain field-level errors and training-overlap limitations.
- [Published NCL image](public-nucleolar-validation.md): real 16-bit image and explicit channel metadata discrepancy; no nucleolar ground-truth accuracy claim.
- [BBBC013 GFP](public-gfp-validation.md): 817 ImageJ/Python object comparisons on published 8-bit exports; native FRM intensities remain unvalidated.
- [Statistical audit](scientific-audit-2026-10-02.md): closed-form t references, explicit CRV1 matrix calculation, selection/missingness/pairing checks.
- [Figures](figures.md): physical/vector/font/source checks.
- [Browser evidence](web.md), [Fiji installation evidence](fiji.md), and [release path](deployment.md).

## Completion audit regression coverage

The post-local.6 audit follows the researcher workflow against requirements, including combinations
that individual module tests did not exercise. A source fix is not evidence that an already
downloaded release contains it; see the exact release source in [local delivery](local-release-0.1.0.md).

- Incomplete OME plane mappings are rejected before tifffile can create zero-filled missing channels.
  Valid explicitly reordered channels and self-referencing UUID metadata remain covered.
- Re-segmenting only some fields cannot adopt new global detection parameters. Background ROI and
  exclusion changes travel atomically with the new immutable revision.
- Measurement tests cover nucleoplasmic area, distinct candidate states and a manual GFP upper
  bound's exploratory provenance. A recoverable nucleolar operation failure retains nucleus
  measurements and missing compartment values; it requires correction or reasoned exclusion.
- `test_export.py` recalculates a six-field comparison and its source-linked figure from original
  pixels and saved masks. Explicitly excluded failed fields remain excluded during replay.
  Native definition sensitivities carry alternate reviewed masks for independent recalculation.
- `test_numeric_export.py` verifies original CSV hashes, normalized observations, saved statistical
  conditions, Methods and replay figures, plus ownership and deletion for the downloadable package.
- Independent statistical reference tests cover the repeat-length coefficient with an explicit
  matrix/sandwich calculation, in addition to Welch, paired and group-model comparisons.

These are software regression checks. They do not establish that a selected biological unit is
independent, that an exploratory adjustment estimates a causal effect, or that the detector fits
the user's private experiment.
