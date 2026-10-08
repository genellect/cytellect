# GFP nuclear selection: filter 1.1.0

The `gfp-gate/3.0.0` protocol adds manual and acquisition-date Otsu selection to the existing negative-control protocol. Historical filter `1.0.0` / protocol `gfp-gate/2.0.0` retains its original threshold, comparison and Methods behavior.

## Measurement and identity

The observations being classified are the saved per-nucleus arithmetic GFP means, identified by `(field_id, region_id)` in the adopted StarDist nuclear revision. Connected bright pixels are not classified as cells. These values do not represent whole-cell GFP expression. Nucleoplasmic and per-nucleus compartment-summary comparisons bind back to the recorded parent nuclear revision and mask identity.

The filter explicitly records `values: raw | corrected`. Corrected means come from the selected revision's background correction. An absent corrected mean remains missing and never falls back to the raw mean. Changes to masks or channel assignments require a new classification of the resulting revision.

The optional `unit: cell_roi` selects means from explicitly hand-drawn `manual / cell` masks instead. Object IDs then refer to these cell ROIs; neither nuclear boundaries nor generic positive-pixel masks are treated as cell boundaries. Manual and batch Otsu thresholds are supported for this unit. The historical negative-control filter remains nucleus-only. The API returns `objects` and the recorded unit; its compatibility `nuclei` array is empty for cell ROIs.

## Thresholds

- **Manual:** a finite user-specified threshold on nuclear mean intensity; acquisition date is not required. The same recorded threshold is applied to all requested nuclei.
- **Batch Otsu:** Otsu applied to finite nuclear mean intensities separately for each recorded acquisition date, using scikit-image's 256-bin implementation. The input is a distribution of nuclear means, not an image histogram. Missing acquisition dates, fewer than two finite values and constant distributions have no threshold.

A mean strictly greater than the threshold is positive. Equality is negative. Missing mean or missing threshold is unclassified and excluded from both the positive and negative selections. All decisions retain their reason and object identity. Manual and Otsu selections are exploratory; neither establishes biological negativity in the absence of a negative-control reference. Values and detector settings must not be tuned to achieve a desired significance result.

## Reproducibility

The saved filter contains its version, protocol, GFP channel, method, threshold (manual only), measurement value type and retained class. Result provenance records the actual thresholds, source revisions/masks, classifications, counts and Methods text. Existing experimental-unit aggregation is unchanged by the new selection.

`tests/test_gfp_exploratory.py` checks exact-boundary behavior, missing values, batch separation, constant distributions, corrected values, saved nucleus identity and the statistical/Methods path. `tests/test_gfp_gate_api.py` checks the actual saved-revision endpoint and prevents corrected-to-raw fallback. These synthetic checks do not establish biological classification accuracy on a particular experiment.
