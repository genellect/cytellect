# Validation layers

| Layer | Data | What it establishes |
|---|---|---|
| Numerical unit tests | Precisely defined synthetic pixels/masks | Equations, area/intensity arithmetic, invalid states, weighting, correction and replay |
| Image integration | Published real microscopy, source/axes/stains recorded | TIFF/engine/editor behavior on actual cells; detector comparison where annotation exists |
| Public interface | Redistribution-cleared real images with attribution | Browser display, selection, layout and accurate explanation of supported channels |
| Private scientific validation | User-provided raw images outside repo/Cloud | Suitability for the actual experiment, manual/Fiji agreement and legacy reconciliation |
| Researcher PoC | Approved private host and participants | Completion, correction time, comprehensibility and reuse demand |

Public image availability does not make an RGB figure an unmodified quantitative raw input. Do not fabricate missing GFP/NCL channels or use a different stain as NCL. Label projections/crops and display conversions. Keep a fixed evaluation subset; record StarDist training-overlap uncertainty rather than claim held-out generalization.

Required software checks are in [contributing](../CONTRIBUTING.md). Browser evidence must include upload → detection → edit → explicit review → measurement → statistics → private export, plus mobile/desktop display and console errors. Public demo inspection is a separate check. A compiled UI is not proof of browser behavior.

Private acceptance remains open until raw images are supplied and evaluated. Provisional F1 goals (.90 nuclei/.80 nucleoli at IoU.5) are targets, not achieved performance. Final quantitative acceptance prioritizes agreement between reviewed masks/original pixels and reference calculations. Never force prior p-values or fixed cohort counts.
