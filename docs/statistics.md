# Statistical and export protocol

Protocol version **1.2.0** records changes to validation, reference coding and sample selection relative to the initial draft. This is a software protocol, not a claim of validation on private images.

## Unit comparisons

A field contributes its median selected measurement. Fields are averaged within each sample; samples are averaged within an independent experimental unit. Cell count cannot increase the weight of a field. Users must confirm independent experimental units.

Unpaired comparisons use Welch's t test and require at least two units per group. The same unit ID in two compared groups requires an explicitly paired design. Paired t tests require one complete, unique pair mapping per unit, with at least two pairs. Zero-variance paired differences or wholly constant unpaired data are reported as not estimable. No epsilon is added to create a p value.

Planned differences are group A minus group B. Holm correction applies to the explicit comparison list. Baseline comparisons and repeat-group comparisons must be separate jobs/families; reversed duplicates are rejected. Individual 95% confidence intervals are not simultaneous family-wise intervals. All tests are two-sided. Outputs include the exact statistic, degrees of freedom, standard error, confidence level and raw/adjusted p values. Groupwise missingness shows whether selection removes entire fields or units.

## Exploratory model

The response is the selected metric. The design includes condition, GFP and acquisition date (when multiple dates exist). The declared baseline is the actual categorical reference. Native GFP uses log2 of positive background-corrected values. A separately recorded legacy transform uses log2(max(GFP, 0)+1). Rows excluded by the transform are counted; all displayed counts and summaries use the final model rows.

GFP is median-centered within acquisition date on those rows. OLS uses field-clustered CRV1 covariance, finite-sample correction and t inference with number of fields minus one degrees of freedom. At least three fields in total and at least two fields in each condition are required. Fewer than 20 fields produces a prominent exploratory warning, not a guarantee that 20 is sufficient. Missing controls, incomplete dates and rank deficiency are distinguished. Fields and cells are not biological replicates. When multiple fields belong to one independent unit, a warning explicitly states that field clustering does not account for between-field correlation inside that unit. This limitation is not repaired by a larger cell count; experimental-unit comparisons remain the primary inferential route. GFP cannot be both outcome and its own covariate.

Adjusted means use GFP centered at zero and equal weight across observed acquisition dates. A repeat-length slope excludes the baseline; repeat length zero is never invented. Non-estimable trends have an explicit reason. No p-value-based model selection is performed.

See [statsmodels covariance documentation](https://www.statsmodels.org/stable/generated/statsmodels.regression.linear_model.RegressionResults.get_robustcov_results.html) for correction and degrees-of-freedom semantics.

## Sensitivity analyses

Users predeclare GFP thresholds and an optional restriction to dates containing all comparison groups plus the baseline. Each scenario retains its specification, counts, contrasts and warnings, or a not-estimable reason. The main result is not replaced by the scenario with the smallest p value.

Alternative NCL region definitions require separately measured, reviewed revisions sharing the same source images. The helper accepts alternate revision row tables; callers must enforce ownership, input identity and review. Changing a column name does not constitute remasking. The API must explicitly connect this helper before claiming this sensitivity UI available.

## Measured assay CSV

UTF-8 CSV required columns: condition, experimental_unit, sample, field_id, acquisition_date, value. Optional columns: pair, repeat_length, unit, assay. A file must contain a single assay and unit. Values must be finite; missing/invalid rows are rejected, not silently dropped. RNA/DNA instrument normalization is outside this importer's scope.

Maximum size is 8 MiB and 100,000 rows. The experimental hierarchy has the same declared aggregation as image measurements. Plots label the input rows observations, not cells. Numeric tables cannot invoke a fabricated GFP regression.

## Figures

Matplotlib writes PNG plus SVG with editable text and PDF with embedded TrueType text. A Japanese-capable font is required for Japanese labels; missing fonts are a clear error. Linux runtime must install fonts-noto-cjk. Plot-data, field-summary, experimental-unit and comparison CSVs accompany each figure.

Distribution plots distinguish observations, field medians, independent units, and mean/95% CI. Exploratory adjusted means are labeled separately from unadjusted unit points. Exploratory scatter lines and pointwise 95% mean intervals use the exact fitted group/GFP/date model and field-clustered CRV1 covariance, evaluated at equal weights across acquisition dates. The x axis is within-date median-centered log2 GFP; observed y values remain unadjusted and the prediction is explicitly date-adjusted. Experimental-unit-mode scatter shows points without an inferential line or interval. Counts show observations, fields and independent units.

## Bundles and Fiji exchange

Private bundles include measurement CSV/JSON, TIFF/NPZ labels, configuration, environment versions, provenance, template Methods, supported Fiji ROI ZIPs, optional recorded statistics/figures and a SHA-256 manifest. They omit original images unless explicitly requested. Derived data remain confidential.

ROI exchange encodes each object's pixel set as integer rectangular row runs. This preserves holes, disconnected components, edge pixels and sparse IDs exactly. Fiji opens the rectangles as individual ROIs; the manifest preserves object grouping. Cytellect import accepts this format only and verifies the full pixel-set hash. Arbitrary polygons, subpixel or rounded rectangles, overlap and approximate contour conversion are rejected. This is exact pixel exchange, not a general-purpose Fiji ROI importer.

Measurement replay verifies source TIFF hashes and package hashes, loads the approved masks, and recalculates measurements and recorded statistics. It does not download models or rerun detection. Original files must be placed under the recorded internal field IDs; the package gives instructions. The declared code commit and locked dependency environment must be restored for comparable results.

CSV text starting with spreadsheet formula characters is prefixed by an apostrophe; numbers remain numeric. JSON preserves authoritative unmodified labels and metadata. Neither package nor figures may be published by default.


## Compatibility recipe implementation

The legacy recipe has a separate versioned parameter object. Its defaults use long-axis 320 pixels without upsampling, anti-aliased bilinear resize, and rounded source-dtype DAPI only for detection. Measurement channels retain resized floating-point values. RGB conversion is max(R,G,B); RGBA alpha is ignored, and planar RGB is supported explicitly. Native input rules remain separate.

Canonical masks are restored to original coordinates; legacy measurements transform them back to the saved measurement grid. Losing a whole nucleus during this transformation is an explicit failure. A restored nucleolar pixel must retain its original parent nucleus, including after edits.

Compatibility-only background is the median outside all nuclear labels, or zero when no outside pixel exists. Negative corrections are clipped at zero; epsilon is max(1, robust background sigma), where sigma is 1.4826 times MAD. Within-nucleus Otsu uses strictly greater values; a uniform nucleus marks all pixels high. Fewer than max(3, ceil(1 percent of nuclear pixels)) high pixels triggers the historical top10-percent percentile rule including ties. These fallback flags are explicit and do not apply to the native recipe.

The primary compatibility index is log2((whole-nucleus corrected mean+epsilon)/(saved high-region corrected mean+epsilon)). Manual changes to the high-region mask are identified. Additional top5/top10/top20-percent region definitions have separate sensitivity scenarios and metrics; they are never silently substituted for the primary index.

Default independent nuclear QC requires non-edge objects, 300..6000 scaled pixels, DAPI signal-to-noise at least2, DAPI saturation fraction at most0.25, and at least20 nuclear pixels. Parameters are editable and recorded. GFP Otsu is estimated per acquisition batch from independent-QC nuclei; constant distributions use their median. The compatibility regression transform is log2(max(GFP,0)+1). Histories, masks and chosen parameters determine counts; there are no hardcoded study groups, dates or cohort sizes.

Only the arithmetic and transformations have been checked against synthetic analytical cases. Reproduction of a private experiment remains unverified until its raw data, original masks and selected cohort are compared in the private validation stage.

## Audit references and limits

The independent reference tests in tests/test_statistics_reference.py use the closed-form Student t distribution with two degrees of freedom for Welch and paired examples. The cluster test builds the design matrix, residual cluster scores and CRV1 sandwich directly with NumPy, then integrates the Student t density. It does not call the same t-test or covariance implementation to manufacture the expected result.

Manually chosen or data-derived GFP gates carry an explicit warning; estimate or confirm gates independently of the intended NCL group result. Neither software nor a negative-control flag can establish that a threshold was specified prospectively. The Holm family must be specified before reviewing the results; running many separate families does not control error across all exploratory analyses.

Unit labels and pairing are declarations by the researcher. The software rejects incomplete or inconsistent metadata, duplicate contrasts, zero-variance comparisons, confounded designs and unsupported self-covariates. It cannot verify biological independence, random sampling, absence of batch confounding outside recorded metadata, missing-at-random assumptions, suitable distributional approximations for two-unit t tests, or the causal meaning of GFP-adjusted comparisons. Small-cluster CRV1 coverage and real-image segmentation accuracy remain unvalidated.

Native NCL analysis permits a genuinely absent GFP channel only with no GFP selection. The separate gfp-nuclear-2d recipe measures DAPI-defined nuclear GFP and reports NCL and nucleolar metrics as missing. A disabled gate means selection is not applied; it is not an experimentally established GFP-positive classification.

Measurement and native GFP selection protocol1.1.0 also record the optional-channel semantics and exclude explicitly excluded objects when fitting a native batch Otsu gate. Recipe parameters and exact per-cell thresholds remain saved independently.
