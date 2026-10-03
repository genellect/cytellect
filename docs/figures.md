# Figure export contract

Current figure protocol **1.1.3** uses Matplotlib with source-linked SVG, PDF and PNG. The Nature single/double presets fix width at 89/183 mm, require height at most 170 mm and 5–7 pt text. Custom sizing remains available. SVG retains text; PDF embeds TrueType fonts; PNG is a 300 dpi preview. Vector files are the manuscript deliverables. A preset is a formatting aid, not a claim of acceptance or biological validity. Generic experimental-unit comparisons use this shared renderer; descriptive figures use their separate protocol 1.0.1 and the same font and layout checks.

English prefers Arial, Liberation Sans, then DejaVu Sans. Japanese prefers Noto Sans CJK JP, Noto Sans JP, Yu Gothic, Meiryo, then IPAexGothic. The other language's allowed families are then considered if needed by literal source labels. Thus an English figure can preserve a Japanese marker or condition without transliteration. A candidate must provide a real normal-style face with numeric weight 350–500 (prefer 400). These weights cover regular/book/medium faces while excluding Thin, Light and bold substitutions. Both the font-cache entry and loaded file are checked. A variable Noto font exposed only as Thin/100 is skipped; an existing regular Yu Gothic or Meiryo face can be selected instead. The choice must cover all actual text, not merely the requested output language.

Generated logarithmic labels in both languages use `log2` to denote logarithm to base two. Noto Sans CJK lacks the Unicode subscript-two glyph in `log₂`; built-in labels avoid requiring an unavailable glyph when source labels contain Japanese. Numerical transformations and statistical values are unchanged. User-supplied text, including subscripts, is never rewritten and must pass the exact glyph check.

Every literal label glyph must exist in one selected regular face, including custom labels and group names. If no candidate covers the text, export fails with a fixed font-availability/glyph error before generating figure files; missing characters are not silently replaced. Labels are literal text, not TeX/mathtext. Every text artist is bound to the verified font file. figure-data.json records actual family, weight, style and file SHA-256, never its absolute OS path. The SVG remains editable and requires the recorded font on the editor's machine; PDF embeds the selected font. No system font installation or download occurs during rendering. Lines are 0.6 pt; axes and text are black; unit identities use a colorblind-oriented palette plus shapes. Exact physical dimensions are saved alongside the font metadata.

The plot always uses the adopted statistics result, never browser values. Grey observations, open field-median squares and colored independent-unit points retain the hierarchy. Diamonds show reported means with pointwise 95% CI. Paired lines use declared pair IDs. Group CIs are distinct from the paired-difference CI; exact effect, t, degrees of freedom, raw p and Holm p are in comparisons.csv and the caption. Group labels show independent-unit n; the caption separates observations, fields and units. Mean intervals and model bands are not multiplicity-adjusted.

Exploratory scatter uses log2 GFP centered by acquisition-date median and the exact saved regression model. Lines average the fitted mean over observed dates; bands use the field-clustered CRV1 covariance and t with fields−1 degrees of freedom. This common-slope model does not estimate separate group slopes. Points remain unadjusted outcomes, so the caption distinguishes points from adjusted fitted values. Experimental-unit-mode scatter shows points only and introduces no additional cell-level inferential band.

Export includes figure-caption.md, figure-data.json, plot-data.csv, experimental-units.csv, field-summary.csv, comparisons.csv, and model-predictions.csv when applicable. CSV SHA-256 hashes and plot settings link the figure to its source. Jitter uses seed 0; statistical values are unchanged.

Recorded model coefficients, repeat-length trends and declared sensitivity scenarios also have dedicated CSVs (`model-coefficients`, `repeat-trend`, `sensitivity-status`, `sensitivity-counts`, `sensitivity-comparisons`). They expose saved results without recalculation and are covered by the same source hashes. Coefficient/trend p values are explicitly unadjusted and exploratory. Selectable compartment means/medians/integrals use the same original measurements; integrated intensity labels distinguish original from legacy scaled pixels. Missing compartments/calibration do not become zero. Current statistics protocol 1.2.3 and its numerical changes are documented separately in [statistics.md](statistics.md).

Version history: 1.1.1 established actual regular-face and glyph verification;
1.1.2 added axis-label overlap/canvas checks and portable built-in Japanese
`log2` labels; 1.1.3 added mixed-script family selection and portable built-in
English `log2` labels. The latter rendering change does not alter measurements,
inference, source selection or the saved user labels. Layout checks reject the
specific overlaps and clipping they detect and do not replace visual review.

Tests inspect SVG physical dimensions/text/vector content, PDF embedded-font/CID/ToUnicode objects, PNG dimensions/DPI, source hashes, exact counts, paired titles, and reuse of saved clustered predictions. Font regressions cover Thin-only families, stale weight-cache entries, regular fallback, complete glyph coverage, actual bound file/weight in English/Japanese, and metadata without OS paths. A Japanese render test is explicitly skipped if no regular Japanese font is installed; this is not recorded as a passed Japanese rendering check. Welch/paired tests and CRV1 covariance/predictions have separate independent closed-form and matrix-algebra references in tests/test_statistics_reference.py. Scientific suitability for the user's experiment remains a separate private-data gate.

Sources checked 2026-10-02: [Nature figure guide](https://research-figure-guide.nature.com/figures/building-and-exporting-figure-panels/) and [SuperPlots](https://pubmed.ncbi.nlm.nih.gov/32346721/).

New descriptive requests may explicitly use figure policy 2.0.0, documented in
[descriptive output](descriptive.md). It divides fields into pages while retaining
one saved vertical scale and all source observations. Historical descriptive
1.0.0/1.0.1 requests keep their original rendering path. The descriptive
measurement calculation and the inferential renderer described above do not
change. An explicitly reported table-only result is usable source data, not a
successfully rendered publication figure.
