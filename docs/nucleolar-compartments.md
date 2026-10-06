# NCL candidate compartments in preserved nuclei

The compartment adapter reuses the saved, original-coordinate nuclear labels. It
does not rerun StarDist. A candidate must lie wholly inside one parent nucleus.
Nucleoplasm is the parent nucleus minus the union of its accepted candidate
pixels; original measurement pixels are never blurred or resized.

## Saved detector versions

`NucleolarDetectorSpec` 1.0.0 retains its existing per-nucleus Otsu computation
and default parameters. The opt-in 1.1.0 detector adds a choice of `otsu` or
`manual`, an explicit manual `threshold`, and an optional `maximum_area_px`.
Both versions remain distinguished by `protocol_version` inside compartment
recipe 1.4.0. Missing historical detector versions resolve to 1.0.0; introducing
new settings into an old version is rejected.

| Setting | Definition |
|---|---|
| `threshold_method=otsu` | ImageJ Otsu on the 256-bin histogram of that nucleus's detection values; no manual threshold is accepted. |
| `threshold_method=manual` | Select nuclear pixels strictly greater than the saved source-scale threshold. Equality is excluded. |
| `threshold` | Required only for manual mode; 0–255 for uint8 or 0–65535 for uint16. It is not a percentile or background-corrected value. |
| `smoothing_sigma_px` | Gaussian sigma, 0–10 original-image pixels; 0 disables smoothing. |
| `minimum_area_px` | Inclusive minimum connected-component area, 1–100000 original-image pixels. |
| `maximum_area_px` | Optional inclusive maximum, at least the minimum and at most 16777216 pixels; null adds no upper filter. |
| `split_touching` | Optional ImageJ EDM watershed before the area filter; MorphoLibJ uses 8-connectivity. |

The optional Gaussian blur operates on a detection copy of the full defining
plane, so nearby non-nuclear signal can influence detection values near nuclear
edges. Histogram samples, threshold selection, connected components, and final
labels are restricted to the parent nucleus. This scope is recorded; it does not
claim a nucleus-isolated convolution. Area filters are applied after watershed.
Intensity measurements always use unchanged input pixels.

For Otsu, binning follows `min(255, floor((value-min)*256/(max-min)))` and selects
bins strictly above the returned Otsu bin. Detector 1.1.0 records each parent's
observed detection range, Otsu bin, source-unit bin boundary, and exact rule.
Manual mode records the actual threshold and `signal > threshold`. These are
computed detection settings, not estimates of nucleolar identity or confidence.
Display-RGB source conversion retains its separately recorded compatibility
meaning; these intensity units must not be described as native detector counts.

## Missing compartments and correction

A uniform Otsu input is `indeterminate`. Manual mode can classify a uniform input
against an explicit threshold: below/equal produces `no_candidate`; above can
fill the nucleus. A filtered-away candidate is `no_candidate`, and a recoverable
per-nucleus processing exception is `processing_failed`. All parent states and
omitted-parent reasons remain available. A parent without an established
candidate does not become a fabricated zero-valued nucleolus or an automatically
valid whole-nucleus nucleoplasm.

If candidates occupy the entire nucleus, nucleoplasm is empty and remains
missing. Compartment derivation protocol 1.0.1 corrects the aggregate status to
`incomplete` in this case; it changes no mask or intensity arithmetic. Parent
IDs, containment, and the nucleus-minus-candidate relationship must be preserved
when edited masks are accepted, and derived compartments/statistics must be
updated. A blanket review cannot substitute for resolving missing parents.

## Interpretation under stress

NCL-based candidates depend on the same signal subsequently measured. A diffuse
or redistributed signal may give a different Otsu partition even when that
partition does not identify a nucleolus. Manual thresholding preserves an
explicit rule but does not remove this circularity. Fix settings after checking
representative images and controls; retain uncertain nuclei for review rather
than changing thresholds to obtain a preferred comparison.

The published analysis by [Kodiha et al.](https://link.springer.com/article/10.1186/1471-2121-12-25)
describes the difficulty of compartment markers that redistribute under stress
and distinguishes marker-based from nuclear-marker-based approaches. This
motivates recording the region definition and inspecting alternatives; it does
not validate Cytellect's candidate masks or a universal threshold. The existing
specialized DAPI-low auxiliary recipe is distinct and is not silently selected
by this NCL compartment adapter. ImageJ provides the fixed
[Otsu implementation](https://imagej.net/ij/developer/api/ij/ij/process/AutoThresholder.html).

The focused checks in `tests/test_compartment_engine.py` use known synthetic
pixels to verify the old/new Otsu agreement, manual equality boundary, inclusive
area limits, nucleus containment, missing-state handling, and exact original
pixel measurements. These checks do not establish biological performance on
stress images. No private image is part of these fixtures.
