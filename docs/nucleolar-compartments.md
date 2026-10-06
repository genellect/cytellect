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

## Nucleoplasm from adopted nucleoli and parent-contained edits (2026-10-06)

Compartment recipe 1.4.0 accepts an optional `nucleolar_revision_id`, only for
`compartment=nucleoplasm`. When present, the worker does not rerun the detector:
it loads that nucleoli revision's saved labels for the field, removes its
excluded objects, and derives nucleoplasm as each eligible parent nucleus minus
the union of its adopted nucleoli (`nucleoplasm_from_adopted_nucleoli`). The
source revision must be a succeeded nucleoli revision with the same nuclear
revision, nuclear channel and defining channel. A parent with at least one
adopted nucleolus is a candidate; a parent whose candidates were all removed
becomes `no_candidate`, and other recorded detector reasons are kept, so no
whole-nucleus nucleoplasm row is invented (protocol 1.0.1 behaviour). Provenance
records the nucleolar revision, mask revision and effective mask hash. Workspace
adoption drops (or, when active, rejects with `workspace_derived_revision_stale`)
a nucleoplasm revision whose `nucleolar_revision_id` is not the adopted nucleoli
revision. Historical revisions without the field keep their original meaning.

Nucleolar edits (`region-edits` on a compartment revision) are restricted to
exactly one saved parent nucleus: an added or redrawn nucleolus that leaves its
parent or spans two nuclei is rejected (`nucleolus_outside_parent`), and a merge
across parents is rejected (`nucleoli_span_parents`). Nucleoplasm is never
edited directly (`nucleoplasm_is_derived`).

## Detector protocol 2.0.0: researcher-selected nucleolar definition (2026-10-06)

NCL leaves nucleoli under nucleolar stress, so masks defined by NCL fail where
the measurement matters. Protocol 2.0.0 (`engine: cytellect-nucleolar-v2`,
`cytellect_analysis.nucleolar_detector_v2`) defines nucleoli from a source the
researcher selects and can change; it runs in the analysis package
(NumPy/SciPy/scikit-image) and never reruns StarDist.

| `source` | Definition | Reference |
|---|---|---|
| `dapi_poor` (default) | Per parent nucleus: Gaussian-smoothed nuclear channel (`smoothing_sigma_px`, default 2), interior after eroding `rim_exclusion_px` (default 4); candidates are pixels below `relative_threshold` (default 0.7) x the interior median; 8-connected components; `minimum_area_px` (4), optional `maximum_area_px`, `minimum_solidity` (0.6). The recipe's defining channel is the nuclear channel. | Kodiha et al., BMC Cell Biol 2011, doi:10.1186/1471-2121-12-25 |
| `marker` | Stable nucleolar marker (UBF/FBL): rolling-ball background subtraction (`background_radius_px`, 10), Gaussian sigma 0.7 px, per-nucleus threshold min + `marker_fraction` (0.4) x (max - min), same filters. Reported as "FC/rDNA-defined"; masks are not dilated. The defining channel must differ from the nuclear channel. | Potapova et al., eLife 2023, doi:10.7554/eLife.88799 |

States per parent are `candidate`, `no_candidate` or `indeterminate`
(constant/empty interior); per-parent reference values, thresholds and component
counts are recorded. DAPI-defined nucleoli under-segment relative to protein
markers (Kodiha et al. report about two thirds of nucleolar signal recovered);
this biases nucleoplasm/nucleolus ratios toward 1, i.e. toward smaller group
differences. Detection uses copies only; measurement uses original pixels.
Detector 1.0.0/1.1.0 (NCL per-nucleus Otsu/manual) remain for reproducing
existing analyses and carry the NCL circularity limitation.

## Per-nucleus nucleolar/nucleoplasmic summary (compartment-summary/1.0.0)

When nucleoplasm is derived from adopted nucleoli, the worker also saves
`compartment-summary.json` per field (served by
`GET /v1/revisions/{rid}/compartment-summary?field_id=`). For every measured
channel and parent nucleus it records the nucleolar count, union area and area
fraction, the mean and integrated intensity over the nucleolar union (pixel
weighted, not a mean of object means) and over the nucleoplasm, the primary
metric log2(mean nucleoplasm / mean nucleolar union) (White et al., Mol Cell
2019), and the integrated nucleolus/nucleoplasm ratio (Potapova et al., eLife
2023). No pseudocount is added; a nucleus without a nucleolus or nucleoplasm, or
with a non-positive mean, has a missing value and a reason. The browser only
displays these values.

`channels` always holds raw values. When the nucleoplasm revision uses the
automatic background candidate (measurement protocol 4.0.0, see
`docs/methods.md`), the summary also holds `corrected_channels`: the same rows
with the channel's background median `b` subtracted once from both compartment
means (`mean − b`) and integrals (`Σ − |R|b`), with `values=background_corrected`.
A channel without an established background has no corrected rows and records
the reason (`automatic_background_insufficient_tiles` or `…_coverage`); its raw
values are not substituted. The workspace uses raw values by default; corrected
values are opt-in and displayed per nucleus. Comparisons, figures and exports
still refuse protocol 4.0.0 and use raw values until their own Methods text is
versioned.
