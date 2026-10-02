# Figure export contract

Figure protocol 1.1.0 uses Matplotlib with source-linked SVG, PDF and PNG. The Nature single/double presets fix width at 89/183 mm, require height at most 170 mm and 5–7 pt text. Custom sizing remains available. SVG retains text; PDF embeds TrueType fonts; PNG is a 300 dpi preview. Vector files are the manuscript deliverables. A preset is a formatting aid, not a claim of acceptance or biological validity.

English uses Arial where available, otherwise Liberation Sans or DejaVu Sans; the actual font is recorded. Japanese requires an installed Japanese sans-serif font and fails explicitly if unavailable. Fonts are not downloaded at runtime. Lines are 0.6 pt; axes and text are black; unit identities use a colorblind-oriented palette plus shapes. The installed font and exact physical dimensions are saved in figure-data.json.

The plot always uses the adopted statistics result, never browser values. Grey observations, open field-median squares and colored independent-unit points retain the hierarchy. Diamonds show reported means with pointwise 95% CI. Paired lines use declared pair IDs. Group CIs are distinct from the paired-difference CI; exact effect, t, degrees of freedom, raw p and Holm p are in comparisons.csv and the caption. Group labels show independent-unit n; the caption separates observations, fields and units. Mean intervals and model bands are not multiplicity-adjusted.

Exploratory scatter uses log2 GFP centered by acquisition-date median and the exact saved regression model. Lines average the fitted mean over observed dates; bands use the field-clustered CRV1 covariance and t with fields−1 degrees of freedom. This common-slope model does not estimate separate group slopes. Points remain unadjusted outcomes, so the caption distinguishes points from adjusted fitted values. Experimental-unit-mode scatter shows points only and introduces no additional cell-level inferential band.

Export includes figure-caption.md, figure-data.json, plot-data.csv, experimental-units.csv, field-summary.csv, comparisons.csv, and model-predictions.csv when applicable. CSV SHA-256 hashes and plot settings link the figure to its source. Jitter uses seed 0; statistical values are unchanged.

Tests inspect SVG physical dimensions/text/vector content, PDF embedded-font objects, PNG dimensions/DPI, source hashes, exact counts, paired titles, and reuse of saved clustered predictions. Welch/paired tests and CRV1 covariance/predictions have separate independent closed-form and matrix-algebra references in tests/test_statistics_reference.py. Scientific suitability for the user's experiment remains a separate private-data gate.

Sources checked 2026-10-02: [Nature figure guide](https://research-figure-guide.nature.com/figures/building-and-exporting-figure-panels/) and [SuperPlots](https://pubmed.ncbi.nlm.nih.gov/32346721/).
