# Scientific contract

Intended semantics; see handoff.md for unimplemented/untested parts.

Original grayscale pixels are immutable. Detection normalization and display LUTs never alter measurements. Label masks use original coordinates. Each nucleolus has exactly one containing nucleus; nuclear edits invalidate dependent children.

The recorded `dapi` key is the historical nuclear-stain channel role. It does not establish that the acquired dye was DAPI: published inputs also use Hoechst or DRAQ. Methods template 1.0.0, the first explicitly versioned template, therefore describes the nuclear-stain channel and names the recorded role without inferring chemical identity. The researcher must supply the actual stain identity from acquisition records when preparing the manuscript. This wording correction does not alter channel mapping, detection parameters, measurements or statistics; previously exported Methods may still contain an unsupported DAPI claim and should be reviewed before reuse.

Background b is the median of a confirmed background ROI. Export raw values and x-b values; native negatives remain signed. Intensity integral is sum of pixels. It is not normalized concentration.

Nucleus N, nucleolar union U, nucleoplasm P=N minus U. Measure N/U/P separately; cell-level U mean is pixel-weighted, with object measurements in a separate table. Native index is log2(mean(P-b)/mean(U-b)), defined only when both means are positive. Empty/invalid compartments produce explicit missing reasons.

Measurement output protocol 1.1.1 adds explicit nucleoplasm area in original-image pixels and, only with a confirmed pixel size, square micrometres. Nucleus area equals nucleolar union area plus nucleoplasm area. The compatibility recipe also reports these original-coordinate areas while retaining its separate historical intensity measurement grid. A GFP-only recipe reports both NCL compartment areas as missing, not zero; intensity formulas are unchanged.

Per-nucleus nucleolar states retain detector evidence: `candidate`, `no_candidate`, or `indeterminate`. An empty mask without recorded detector evidence is `unclassified`. Editing a nucleus sets affected parents to `review_required`; unchanged parents keep their prior states. Explicit manual nucleolar edits yield `candidate` or `no_candidate`. The compatibility recipe retains `legacy_candidate`/`none_after_edit`, and GFP-only analysis uses `not_measured_recipe`. These states accompany the masks in provenance and reproducible measurement exports; an empty mask alone never proves a failed or negative detection.

A recoverable exception in a nucleus's candidate operation produces `processing_failed`; its nuclear NCL/GFP measurements are retained, while both unestablished NCL compartments, their areas/counts and ratio are missing. Partial candidate pixels are discarded, never reported as zero biological signal. Review, statistical analysis and replay require successful re-detection/manual correction or an explicit reasoned nucleus/field exclusion. A blanket acceptance of invalidated masks does not clear processing failures. Diagnostic measurement exports remain available and retain the failed-object count and states. Fatal input, nuclear detection, memory and JVM failures still fail the field visibly.

The accepted OME-TIFF subset is a single grayscale image with Z=T=1, one to three channels and exactly one physical TIFF IFD per channel. TiffData must cover every channel exactly once, without missing or reused IFDs; dimensions, dtype and pixel data extents must agree. Missing acquisition planes are rejected before decoding, never synthesized as zero intensity. PlaneCount defaults to the number of IFDs unless IFD is explicitly given, when it defaults to one; FirstC/Z/T default to zero. These defaults follow the [primary OME-TIFF specification](https://docs.openmicroscopy.org/ome-model/6.2.2/ome-tiff/specification.html#the-tiffdata-element). The broader format permits unused extra IFDs and multifile data, but this initial supported subset rejects them explicitly. A renamed file's self UUID is allowed without following its filename; external UUID references are rejected.

NCL-defined regions can change with NCL redistribution. Record the region definition and limitation. DAPI-low is a separate definition. Missing candidates are never substituted with the nucleus/top fraction in native mode.

Legacy RGB/resizing/background/clipping/epsilon and whole-nucleus/high-NCL ratio are a separate versioned recipe. Exact reproduction is unverified at this checkpoint.

GFP gate uses confirmed negative control or exploratory manual/batch Otsu; reference group does not automatically mean negative. Save transform, threshold/range and reasons.

GFP selection output protocol 1.1.1 also marks any manually supplied upper intensity bound as exploratory, including maximum-only filtering or an upper bound combined with a confirmed negative-control lower threshold. This metadata correction does not change inclusion arithmetic or clip negative background-corrected values.

Native signal QC protocol 1.0.0 adds a warning-only diagnostic for nuclear, nucleolar-union and nucleoplasmic NCL and nuclear GFP: corrected compartment mean divided by `1.4826 * median(abs(background_pixels - median(background_pixels)))`. The denominator is spatial background dispersion, not an estimated standard error or photon-noise model. The signed ratio is retained. A zero/invalid denominator, unavailable channel, empty compartment or failed candidate calculation produces a missing diagnostic and a fixed reason; no epsilon or infinite value is substituted. The original nonpositive compartment-ratio warning remains independent.

`Recipe.native_signal_qc_minimum_ratio` is an optional nonnegative finite threshold, initially unset. With a threshold, ratios strictly below it are labelled weak; equality is not below. Without it, finite ratios remain visible and the warning flag is missing (`threshold_not_set`). There is no validated universal cutoff. Warnings never change masks, intensities, GFP selection, exclusions or statistical inclusion; the researcher explicitly reviews any exclusion. The threshold is saved in the immutable recipe, can be updated through existing-mask remeasurement and is exported with each diagnostic/reason. This native-only metadata protocol does not change measurement protocol1.1.1, GFP selection protocol1.1.1 or the separately versioned legacy DAPI-SNR QC.

Aggregation: field median → sample mean → independent-unit mean. Predeclared Welch/paired tests use Holm families. Exploratory group/GFP/date regression uses field-clustered SE; verify rank/confounding/controls and few clusters. Cell counts are not independent replicate counts.

New opt-in generic comparison 2.0.0 and association 1.0.0 extend these methods
without rewriting historical requests. [Common statistics](common-statistics.md)
defines the rank tests, multi-group omnibus, matched-unit associations,
permutation policy and separately versioned Methods/figures. Their applicability
depends on the recorded experimental design and acquisition review.

References:
- [StarDist](https://imagej.net/plugins/stardist)
- [Nucleolar fluorescence quantification](https://link.springer.com/article/10.1186/1471-2121-12-25)
- [SuperPlots](https://pubmed.ncbi.nlm.nih.gov/32346721/)
- [CellProfiler examples](https://cellprofiler.org/examples)

## Automatic workspace: raw measurement protocol 3.0.0

The initial workspace can measure nuclear area and raw channel intensity before a
background ROI or experimental design is available. This is a separate protocol,
not a background value of zero: policy `1.1.0/raw_intensity`, report/table `3.0.0`,
bundle `/3`, measurement Methods `1.3.0`. Corrected values are null with
`background_not_established`. Existing corrected protocol 1 and area-only protocol
2 retain their definitions.

For each original-coordinate label and channel, mean and median use all original
8/16-bit pixels; integrated intensity is their sum. Storage-limit and recorded
acquisition-limit fractions remain distinct. Calibration is never inferred.
Recipe `region-2d/1.2.0` records whether the nuclear role came from recorded stain
information or a user's role selection. Filename evidence is not an acquisition
confirmation, and role adoption is not a segmentation review. NCL is measured as
an acquired channel; this generic recipe does not define nucleoli or NCL ratios.

Automatic descriptive output carries `source_review=automatic_unreviewed`,
preserves source revisions and failed-field checks, and does not mark masks as
reviewed. It contains observed points and field summaries, with no inferred
biological replicate count, p-value or inferential confidence interval. The
existing reviewed, design-aware comparison routes remain separate. Revising a
mask or exclusion creates a new measurement version; figure styling does not.

## Automatic background candidate: measurement protocol 4.0.0

Policy `1.2.0/automatic_background` measures the raw protocol 3.0.0 values and
adds corrections from an automatic background candidate (algorithm
`cytellect-automatic-background` 1.0.0). It is recorded as
`background_source=automatic_candidate`, `confirmed=false`; it is never a
human-confirmed ROI. A request cannot combine it with ROI backgrounds
(`region_automatic_background_roi_conflict`); confirmed ROIs keep protocol 1.0.0.

Per field and channel, on original pixels only:

1. Exclusion: every labelled pixel of the measured region set (for compartment
   recipes also every source nucleus, including excluded nuclei), dilated by a
   Euclidean 8 px perinuclear margin; plus bright pixels strictly above
   `median + 3 × 1.4826 × max(MAD, 1)` of the remaining pixels of that channel.
   The one-unit MAD floor keeps quantized low-signal backgrounds usable. Otsu is
   not used because it also splits unimodal noise.
2. Tiles: 32 × 32 px from the origin; partial edge tiles are dropped. A tile is
   eligible with ≥ 90 % unexcluded pixels.
3. One rejection pass on eligible tiles, using unexcluded pixels: reject a tile
   whose median m satisfies `|m − median(m)| > 3 × 1.4826 × MAD(m)` or whose MAD d
   satisfies `d > median(d) + 3 × 1.4826 × MAD(d)`.
4. At least 4 retained tiles whose centres lie in at least 3 image quadrants
   (centre at or after half the extent belongs to the lower/right quadrant).
5. B = unexcluded pixels of retained tiles; `b = median(I[B])`. Corrected mean
   `mean(I[R]) − b`, corrected median `median(I[R]) − b`, corrected integral
   `ΣI[R] − |R|b`; signed, unclipped.

Failure (`automatic_background_insufficient_tiles` or
`automatic_background_insufficient_coverage`) leaves that channel's corrected
values null with the reason; raw values and other channels are still reported
and the field does not fail. Provenance records the constants, bright threshold,
exclusion and background mask hashes, eligible/rejected/retained tile counts,
quadrants and the retained tile-median range. Synthetic counterexamples are
tested: a confluent field and one-sided background fail; a linear illumination
gradient is not removed (b is one global median, the tile-median range shows the
spread); a local diffuse blob is excluded; field-wide diffuse signal is reported
as background, which is why the candidate is never treated as confirmed. Exports
and statistical summaries refuse protocol 4.0.0 until their own Methods text is
versioned.


## Generic display-RGB input transform 1.0.0

Generic region inputs may explicitly select `input_mode=display-rgb`. Each uint8 RGB/RGBA TIFF becomes one measurement plane by `max(R,G,B)`; alpha is ignored. The original resolution and original files are retained. Unlike the historical NCL compatibility recipe, this input transform does not resize, clip corrected values, or apply a legacy epsilon. This is a display-code measurement, not recovery of acquired raw fluorescence: an acquisition LUT, gamma or clipping cannot be inverted. The input mode is retained in immutable field snapshots and replay, Methods records the transform, and measurement CSV identifies `intensity_source=display_code_max_rgb`. Native remains the default and continues to reject RGB. Generic inputs and measurement contracts accept up to four explicitly mapped planes; no plane or duplicate is silently discarded. The nuclear detector still requires an adopted or confirmed defining role, and does not infer stain identity from RGB colour.

Display-RGB input transform 1.0.0 and native acquired grayscale intensities are different measurement sources. Generic descriptive/comparison preparation rejects pooling these sources for intensity outcomes, even when channel labels and stains match. Area outcomes may combine them because canonical mask areas retain their pixel/calibration definitions. Statistical Methods explicitly identify display-RGB values as max(R,G,B) display codes; they are not acquired raw fluorescence. This admission guard does not change the underlying measured numbers.

Signal-area recipe 1.3.0 (`fiji_positive_regions`) applies the fixed Fiji/ImageJ threshold and connected-component engine to one explicitly selected acquired channel. Default Otsu is an exploratory per-field threshold, with optional explicit manual threshold; smoothing, minimum area and touching-region splitting are saved detector settings. Signal areas are independent region revisions and do not establish nuclei, whole cells, nucleoli, or biological GFP/NCL positivity. Measurements use unchanged original-resolution measurement planes; display-RGB conversion remains separately recorded. Reusing a mask requires the same source, defining channel, detector settings and input pixel hash; nucleus revisions remain available separately.

Compartment recipe 1.4.0 pins an immutable successful nuclear revision from the same workspace and field. Its canonical mask file/hash and original image identity are checked before NCL compartment detection and again during mask reuse. Previously excluded source nuclei remain excluded. NCL-enriched candidate labels retain parent nuclear IDs in detector provenance; nucleoplasm is the original nucleus minus the candidate union only for eligible parents. Every parent state and missing reason is preserved, including indeterminate/no-candidate/processing-failed parents and empty nucleoplasm after subtraction. Missing parents never become fabricated zero-valued compartment observations or whole-nucleus nucleoplasm. Compartment revisions preserve the original nuclear revision and have independently selected region-set IDs and saved detector parameters.

## Explicit nuclear detection scale

Generic nuclear recipe 1.5.0 records an explicitly selected `detection_max_side_px`
(integer 64–2048). Only the detector copy is reduced: no upsampling is performed,
the existing capacity bound still applies, and measurement pixels remain at their
original resolution. Detector protocol 1.2.0 records requested and actual shapes,
the pixel-centre transform and canonical restored-label hashes. Labels are restored
with nearest-neighbour pixel-centre mapping before original-pixel measurement.
Changing scale requires a new detector run and invalidates dependent compartments;
it cannot reuse masks produced with another scale. Omitting scale in a 1.2.0 request retains the
older capacity-based behavior; the workspace now omits it only through recipe
1.7.0 below, which sizes the detection copy from the estimated nucleus diameter.

Scale is an experimental setting, not an accuracy guarantee or a universal default.
The StarDist [FAQ](https://stardist.net/faq/#do-i-need-to-rescale-my-images-how-do-i-know-which-pixel-resolution-is-required)
describes input object-size mismatch as one possible source of oversegmentation.
Inspect boundaries on representative fields before applying a scale to a batch.

## Automatic nuclear detection scale (recipe 1.7.0, nuclear-size/1.0.0, 2026-10-07)

Without an explicit size, the workspace now requests nuclear recipe 1.7.0. Per
field, the typical nucleus diameter is estimated from the defining (nuclear)
channel's measurement plane:

1. block mean to a grid whose long side is at most 512 px (integer factor f);
2. Gaussian smoothing, sigma 2 grid px, so chromatin texture inside a nucleus merges;
3. Otsu threshold, hole filling, 4-connected components of at least 16 grid px;
4. the area-weighted median component (the component size that covers half of
   the foreground), converted to an equivalent-circle diameter D in original px.

The detection copy's long side is `round(L × 40 / D)` for an image of long side L,
bounded to 64–2048 px; when that is not smaller than L the image is not reduced
beyond the existing capacity bound and is never enlarged. Measurement pixels,
the detector, its parameters and the label restoration are those of recipe 1.5.0.
The estimate (grid factor, threshold, component count, D or a missing reason) and
the chosen size are recorded per field (`detection_scale`); a saved mask can only be
reused under the same scale protocol.

The target (40 px) was chosen from real-Fiji runs: on the public BBBC007 nuclear
image enlarged six times, target diameters of 24–40 px reproduced the
original-resolution count (115 → 116–118) while 48 px or more split nuclei; on
owner-supplied Airyscan images (validated privately, not published) 24–40 px gave
whole-nucleus masks while the capacity-only path split nuclei into hundreds of
fragments. Labels are restored from the reduced copy, so their edges are coarser by
the reduction factor; inspect and correct boundaries before measurement. Touching
nuclei that merge in the coarse estimate enlarge D and reduce the copy further;
choose an explicit size (recipe 1.5.0) when that happens. A real-Fiji regression
test (`tests/test_nuclear_scale.py`, BBBC013 enlarged six times) requires the
automatic scale to reproduce the original count within 10% and confirms that the
capacity-only path does not.

## GFP-positive nuclei from negative controls (gfp-gate/2.0.0, 2026-10-06)

`POST /v1/workspaces/{wid}/gfp-gate` labels nuclei of adopted nuclear revisions
as GFP positive when their raw GFP mean exceeds the 99th percentile (linear
interpolation; configurable 50–<100) of the GFP means of nuclei in the fields the
researcher designates as negative controls (untransfected or GFP-negative cells),
computed separately per acquisition date. A date with fewer than 20 control
nuclei has no threshold and its nuclei are unselected with a reason; missing GFP
values are never treated as positive. Pooled-population Otsu is not used because
its threshold moves with the transfected fraction. GFP is a selection or
covariate, never a denominator. The control-distribution approach follows
per-nucleus gates such as Sutton & DeRose, J Biol Chem 2021
(doi:10.1016/j.jbc.2021.100633). Comparisons and figures use it through the
separately versioned nucleus filter below.

## GFP nucleus filter 1.0.0 for comparisons and descriptions (2026-10-06)

Region selections and compartment-summary selections 1.0.0 accept an optional
`gfp_gate` in common statistics request 2.0.0
(`POST /v1/revisions/{rid}/common-statistics`) and in per-field descriptions
(`POST /v1/revisions/{rid}/descriptive`):

```json
{"version": "1.0.0", "gate_protocol": "gfp-gate/2.0.0", "gfp_channel_id": "gfp",
 "percentile": 99, "control_field_ids": ["..."], "keep": "positive"}
```

The filter changes which nuclei enter the unchanged protocols: aggregation
(field median → sample mean → independent-unit mean), tests, Holm family and
per-field summaries are not modified. Without `gfp_gate` every request, result
and figure is byte-identical to before; the absent key is omitted, not `null`.
Generic comparison 1.0.0, region association 1.0.0 and automatic descriptive
previews refuse the filter (`gfp_gate_unsupported_request`,
`gfp_gate_preview_unsupported`).

- GFP value: the raw per-nucleus arithmetic mean of the declared GFP channel in
  the adopted nuclear (`stardist_nuclear`) revision rows of the same fields. A
  nuclear revision is its own source (binding `same_revision`). A nucleoplasm
  revision (`fiji_nuclear_compartment`, `compartment="nucleoplasm"`) is bound per
  field to the nuclear revision recorded in its provenance (`nuclear_source`):
  the nuclear report must still hold that mask revision and canonical mask hash
  and the same nucleus exclusions (binding `parent_nucleus`). Nucleoplasm region
  IDs and compartment-summary rows are parent nucleus IDs and are joined by exact
  ID; a compartment-summary nucleus area must equal the nuclear area, and a
  nucleoplasm region must be strictly smaller than its nucleus. The GFP channel
  identity must equal the field's declared channel. Nucleoli regions, signal
  regions, manual or imported regions and historical revisions without a recorded
  nuclear source are refused (`gfp_gate_nuclear_source_unbound`); any
  disagreement is `gfp_gate_nuclear_identity_mismatch`.
- Threshold: `gfp-gate/2.0.0` unchanged, per acquisition date, from the
  unexcluded nuclei of the designated control fields (percentile 50–<100,
  default 99, linear interpolation, strictly greater is positive, at least 20
  control nuclei). The percentile is the researcher's recorded choice and is
  never searched; changing it is a new, recorded analysis. Every measured field
  needs an acquisition date (`gfp_gate_acquisition_date_required`). Control
  fields must be registered, measured and not excluded
  (`gfp_gate_unknown_control_field`, `gfp_gate_control_field_excluded`).
- Selection: `keep="positive"` keeps `above_control_threshold`;
  `keep="negative"` keeps `within_control_range`. Nuclei with `gfp_missing`,
  `too_few_control_nuclei` or `no_control_threshold` are never kept and never
  zero. Explicit nucleus and field exclusions take precedence and are recorded as
  `nucleus_excluded` when the nucleus is absent from the nuclear rows.
- Ledgers: control fields set thresholds only. Their observations have
  `selection_status="gfp_negative_control"` and their fields
  `status="gfp_negative_control"`; they never form compared units. Unselected
  nuclei keep `selection_status="gfp_gate_unselected"` with `gfp_mean`,
  `gfp_gate_threshold` and `gfp_gate_reason`. An unexcluded unit without kept
  nuclei (`gfp_gate_unit_without_selected_nuclei`) or a compared condition made
  only of control fields (`gfp_gate_condition_only_control_fields`) is refused,
  never dropped.
- Record: `selection.gfp_gate` stores the filter, channel identity, binding and
  per-field nuclear source (revision, mask revision, mask hash and, for a bound
  nuclear revision, the SHA-256 of its report), per-date thresholds, control
  nucleus counts and control field IDs, reason counts, kept counts per field and
  the number of nuclei with saturated GFP. Methods and figure captions state the
  filter, channel, percentile, controls and each date's threshold in English.
  Warnings: `gfp_gated_subset_selected_by_expression_level_not_randomized`
  always; `gfp_gate_dates_without_control_threshold_unselected` and
  `gfp_gate_saturated_gfp_nuclei_present` when applicable.
- Export: analysis bundles omit gated statistics with
  `region_export_gfp_gate_unsupported`, because replay would need the bound
  nuclear revision and control designation, which the bundle does not carry.
- Validation: synthetic numerical tests (hand-calculated thresholds, kept nuclei
  and unit means; tests compared with SciPy) and an owned API/worker job on
  synthetic pixels. Biological validity of a GFP threshold on real data, and an
  end-to-end nucleoplasm run through the Fiji compartment pipeline, are not
  established by these tests.

## Per-nucleus compartment-summary selection 1.0.0 (2026-10-06)

The primary NCL relocation metric, `log2_nucleoplasm_over_nucleolus` (log2 of the
mean nucleoplasm intensity over the mean intensity of the adopted nucleolar union
of the same nucleus; [nucleolar-compartments.md](nucleolar-compartments.md)), and
the channel-neutral `nucleolar_area_fraction` and `nucleolar_count` can be selected
with `selection={"source":"compartment-summary","version":"1.0.0",...}` in common
statistics (`POST /v1/revisions/{rid}/common-statistics`, request 2.0.0) and in
per-field descriptions (`POST /v1/revisions/{rid}/descriptive`). The aggregation,
tests, Holm family and descriptive summaries are the existing, unchanged protocols
(field median → sample mean → independent-unit mean; Welch/paired t,
Mann–Whitney U, Wilcoxon, Welch ANOVA, Kruskal–Wallis; per-field median and
quartiles). Only the observation source is new and separately versioned.

- Source: a reviewed nucleoplasm revision whose recipe has `nucleolar_revision_id`.
  The worker reads each field's `compartment-summary.json` from the revision that
  derived the mask (also for child or cohort revisions that reuse it) after
  checking the saved labels against the report's canonical mask hash. Nothing is
  remeasured; pixel values are raw (`compartment-summary/1.0.0` has no background
  subtraction). A summary with any other value basis is refused.
- Binding and integrity: every nucleus with nucleoplasm must be exactly a region
  of the reviewed nucleoplasm table with the same area, and no other region may
  exist. Each row must satisfy union + nucleoplasm = nucleus area for candidate
  parents, zero nucleoplasm for candidate-free parents, the recorded area
  fraction, and log2 = log2(nucleoplasm mean / nucleolar mean) exactly. Nucleus
  geometry must agree across channels. Failures are explicit error codes.
- Observations are nuclei; a nucleus keeps the nucleoplasm region ID (its parent
  nucleus ID). Region exclusions of the nucleoplasm revision and whole-field
  exclusions are honoured and remain in the ledgers. Exclusions applied in the
  nuclear and nucleolar revisions were already applied when the summary was made.
- Missingness: a summary row with a `missing_reason` is a missing observation with
  that reason (`no_nucleolus`, `no_nucleoplasm`, `nonpositive_signal`), never a
  value and never zero. For count and area fraction a candidate-free nucleus is
  missing (`no_nucleolus`): a candidate-free parent does not establish zero
  nucleoli (compartment protocol 1.0.1). Count and fraction therefore describe
  nuclei with at least one adopted nucleolus.
- Acquisition review: the ratio is treated as an intensity outcome (actual
  acquisition batches, a single storage dtype, no condition-confounded batches,
  nucleoplasm-region saturation rejected). Saturation in the nucleolar union is not
  recorded by the summary and is reported as the warning
  `nucleolar_union_saturation_not_assessed`. Count and fraction require the
  explicit equal-spatial-sampling confirmation and a single calibration, as for
  pixel area.
- Records: each source field carries the summary protocol, selection version,
  canonical SHA-256 of the summary and its nucleolar revision identity; figures,
  captions and Methods state the per-nucleus definition and channel/stain.
- Export/replay limit: the region bundle does not carry the nuclear and nucleolar
  source masks needed to regenerate the summary from original pixels. Export lists
  such results in `statistics-omitted.json` (and the export job's
  `statistics_omitted`) with `region_export_compartment_summary_unsupported`
  instead of including them; recomputation from a bundle refuses with the same
  code. Descriptive preview (unreviewed) is not available for this selection.

Numerical tests (`tests/test_compartment_observations.py`) use synthetic pixels
whose per-nucleus log2 values are exact powers of two: two conditions × three
units × two fields give unit means −1, −1.5, −0.5 versus 0.5, 1, 0; Welch's t
matches SciPy, the exact Mann–Whitney U is 0 with p = 2/20, an explicitly
excluded nucleus would change a field median and does not, and the missing nucleus
stays in the missingness ledger. These tests establish arithmetic and source
binding only, not nucleolar segmentation validity or biological interpretation.

## Explicit channel identity corrections

The workspace channel assignment ledger stores the researcher's current channel-to-stain
and analysis-role choices, including an explicitly unknown stain or unused channel.
Saving uses an ownership-checked version comparison; no channel number or display color
establishes a stain. Original upload records and measurement pixels remain unchanged.
New generic-region analyses copy the current confirmed identities and assignment ledger
into their immutable configuration. Existing revisions retain their historical identities,
and batch mask reuse rejects a changed channel identity. Further uploads compare their
identity against the current mapping. Workspace retention removes the mapping with its
other metadata. The optional proposal context uses the current explicit mapping; it does
not rename saved scientific outputs.


### Marker smoothing protocol compatibility

`cytellect-nucleolar-v2/2.0.0` marker detection continues to use Gaussian sigma 0.7 px, including historical recipes whose `smoothing_sigma_px` records another value. Those records are not rewritten or reinterpreted. Its DAPI-poor path continues to use the recorded sigma as before.

Marker-only protocol `2.1.0` uses the recorded `smoothing_sigma_px` (0–20 px), with 0.7 px as the new-request default. Rolling-ball subtraction, threshold definition, rim exclusion, component filtering, coordinates and original measurement pixels are unchanged. Opening an old result or editing an unrelated setting does not upgrade it. An explicit marker sigma edit, a new marker configuration or adoption of a 2.1.0 proposal creates the new protocol configuration; accepted masks remain unchanged until the usual preview/adoption operation. Fiji NCL protocol 1.1.0 is unaffected. This is parameter-semantic compatibility, not a claim of biological validation.
