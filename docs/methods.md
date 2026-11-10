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
Executable workspace association proposals require both axes to name the same
explicit measurement region. Cross-region associations and implicit region
axes are unsupported; use separate descriptive analyses until a dedicated
source-matching contract is available. Saving or restoring a proposal must not
silently substitute another region for either axis.

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
as background, which is why the candidate is never treated as confirmed.
Reproducibility exports use bundle format `/4` with measurement Methods 1.4.0.
Descriptive and comparison Methods (statistical Methods templates 1.0.0 and 1.1.0) describe
protocol 4.0.0 sources from their saved provenance, as listed in
[Statistical Methods documents](statistical-methods.md); common statistics name
the automatic candidate median as the correction basis. None of these steps
recalculates or alters the measured values.


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
  fraction, and log2 = log2(nucleoplasm mean / nucleolar mean) within a relative and
  absolute 1e-12 (a few units in the last place: the browser runtime's libm can round
  log2 one bit away from the server's; the saved value is used as saved). Nucleus
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

### Measured CSV distribution and SVG source navigation

Explicit descriptive CSV import requires `field_id,value`; study metadata may remain unknown. The historical experimental-unit import remains strict. The descriptive route uses the existing per-field summaries without inferential tests or invented replicates. Comparison rejects incomplete study metadata before queuing. Numerical replay format 2 records the original CSV byte hash, normalized observations, saved descriptive settings, page artifacts and renderer Methods; replay checks the exact original CSV before recalculation.

SVG observation marks carry identities already present in saved result rows. Nuclear or ROI observations return to the saved field, object, measured channel and mask revision. Experimental-unit marks expose their saved constituent observations. These annotations do not generate observations or change measurements, aggregation or statistical tests. The pagination contract remains 2.0.0; presentation renderer 2.0.1 honors saved point size, field color and legend settings. Figure files record their renderer and code identity. Reproduction of historical presentation requires its recorded code version.

NCL object detector 3.0.0: see [the versioned compartment definition](nucleolar-compartments.md#ncl-object-protocol-300-2026-10-08). It uses local enrichment, complete compact-object envelopes and adopted-parent containment; historical recipes are not reinterpreted.

### Optional Cellpose candidates, protocol 4.0.0

The offline `cellpose-sam/4.0.0` adapter pins Cellpose 4.2.1.1 and the official
`cpsam_v2` weights by immutable revision and SHA256, separately from Fiji and the
application Python runtime. StarDist remains the nuclear detector. A researcher
explicitly chooses the defining NCL or cell stain and the Cellpose algorithm.
Changing an unrelated setting never upgrades a historical detector.

Percentile normalization and optional diameter resampling operate on a detection
copy only. Original-coordinate unsigned integer labels are authoritative;
original pixels determine area, mean and integrated intensity. A nucleolar
candidate must be wholly inside exactly one adopted nucleus. Crossing, exterior
and boundary-truncated candidates remain in review provenance and do not become
completed nucleoli by clipping. Nuclear labels and manual edits are preserved.
Nucleoplasm is derived from the adopted nucleus minus adopted nucleolar unions.

Cell recipe 1.8.0 saves separate cell ROI candidates. Optional nuclear association
records every overlap; it does not impose one cell per nucleus, infer cell
boundaries from DAPI, or establish a negative-cell denominator from GFP alone.
The existing object-level GFP selection and original-pixel measurement paths
consume these cell ROI masks. Saved masks, rather than a future model run,
provide measurement replay.

The model is a general segmentation model, not a trained nucleolus classifier.
Applicability remains an image-review question; successful execution and nuclear
containment do not prove biological identity. Local CPU jobs load the model in
their isolated process; the remote CUDA service reuses the loaded network within
its process, keyed by model path and device. Both use the official `cpsam_v2`
weights with Cellpose 4.2.1.1 in the default runtime manifest. Cytellect also
publishes NCL-specific fine-tuned checkpoints; their identities and adoption
records are documented in the [model strategy](segmentation-models.ja.md).
The NCL protocol version identifies preprocessing and refinement separately
from the model checkpoint. The runner
accepts a 2D uint8/uint16 plane and uses `do_3D=False`.
The [adapter record](../engines/cellpose/README.md) documents model,
dependency and licence provenance; the [model strategy](segmentation-models.ja.md)
defines the planned volumetric pipeline. Model and runtime acquisition occurs only in
explicit setup/build, with a reusable cache, never in image jobs.

### NCL Cellpose detection copy, protocol 4.1.0

Saved `cellpose-sam-ncl/4.1.0` selections use the same
fixed model and dependencies. The selected NCL plane is converted to float32,
Gaussian-smoothed (default sigma 0.9 original pixels), and subjected to grayscale
opening with a Euclidean disk (default radius 10 original pixels, reflect boundary
mode). The nonnegative difference from this local background is passed to the
model through its official percentile normalization (default 1 and 99). No
display LUT, color, nuclear zeroing, image-size scaling or thresholded label mask
is supplied as the detection input. Parameters are saved with the detector.

Original pixels still provide measurement values. Original-coordinate candidates
are bound to adopted StarDist nuclei by the containment policy above. This new
protocol does not reinterpret saved raw-input `cellpose-sam/4.0.0` results or the
separate cell ROI recipe. A successful segmentation still requires researcher
review; it does not independently establish nucleolar identity.


### Parent-conditioned NCL Cellpose protocol 4.2.0

The `cellpose-sam-ncl-parent/4.2.0` protocol introduced parent-conditioned inference.
The unchanged original plane is Gaussian-smoothed (0.9 original px) before any
parent restriction. For each adopted StarDist nucleus, subtract its 75th
intensity percentile, keep positive signal only within that parent, and normalize
a padded (32 px) crop using the pinned official Cellpose 1/99 percentile transform.
An explicit diameter overrides the default, which is 0.25 times that adopted
nucleus's equivalent diameter. This is an empirical, recorded model scale prior;
it is neither an image-dimension conversion nor a claim that nucleolar size is
biologically fixed. Display colour, LUT and zoom cannot change these inputs.

Original-minus-smoothed residuals in the lower nuclear intensity range provide
a robust noise estimate (1.4826 MAD, floor half an input intensity code unit).
Parent signal excess and individual candidate original-pixel enrichment must
meet the recorded minimum signal/noise ratio (5). Local background is the mean
of available pixels in an 8 px annulus inside the same parent and outside model
candidates. Insufficient parent signal is indeterminate, not zero nucleoli.
Disconnected model components receive distinct IDs and must each satisfy
minimum area. Cross-parent and boundary-touching objects are rejected whole,
never clipped. No nucleus-size, dark-hole or top-percentile mask replaces an
absent candidate.

Compartment protocol 1.1.0 retains valid individual candidates when another
object requires boundary review. That parent's nucleoplasm/complement remains
missing; it is not treated as a complete nucleolar union for ratios. Researcher
adoption resolves the candidate set explicitly. Complete eligible parents use
the union of adopted children and parent-minus-union, with original-pixel
measurements. Per-parent crop, background, diameter, normalization and signal
quality are retained alongside original and parent-mask hashes.

Protocols 3.0.0, 4.0.0 and 4.1.0 keep their historical semantics and replay.
Existing masks, including manual edits, are not silently upgraded. Private real
image validation is outside Git/CI; runtime/contract checks are not a claim of
general biological segmentation accuracy. Cellpose-SAM is not a nucleolus-specific
classifier, and NCL redistribution can change marker-defined candidates.


Protocol 4.2.1 preserves the 4.2.0
parent-conditioned inference settings and adds
whole-instance nuclear rejection after inference. A candidate covering more
than `maximum_nuclear_coverage` (default 0.5) of an adopted StarDist nucleus,
with at least 0.9 parent purity, is removed as a nuclear-scale candidate. The
original raw candidate artifact and rejection measurements are retained.
Nuclear pixels are never subtracted from nucleolar masks. A parent containing
only rejected nuclear-scale candidates is indeterminate, not a measured zero.
Stored 4.2.0 recipes skip this filter and retain their original meaning.

### Conservative NCL signal support, protocol 4.3.0

New explicit NCL Cellpose selections use 4.3.0. The pinned model, parent-conditioned
inference and whole-instance rejection from 4.2.1 are unchanged. After binding
model candidates to adopted StarDist nuclei, refinement 1.0.0 smooths the full
original NCL plane with Gaussian sigma 0.9 px before restricting to a parent.
Within each parent, the upper threshold of three-class Multi-Otsu defines signal
support; disk closing (radius 2 px) and hole filling operate within that parent.
Eight-connected components are divided by negative-distance watershed with
h-maxima markers at max(1 px, 0.15 times the component's maximum distance).

A support segment must overlap at least half of an existing model anchor, avoid
the parent boundary (four-connected erosion), occupy no more than half the parent
and have a greater original-pixel mean than the local background ring. The ring
is eight iterations of four-connected dilation, excluding support and nuclear
exterior. The parent crop has 24 px padding. These are versioned original-pixel
operations, independent of image dimensions, display zoom or LUT.

Matching segments join/extend the original anchors conservatively. Unmatched
anchors retain their original pixels; support alone cannot introduce a new object.
Connected supported fragments share one object, while disconnected final pieces
receive separate IDs. Raw model labels, bound anchors, support labels, parent
identity and source-object lineage are retained with hashes. Parent review,
no-candidate and indeterminate evidence is preserved. Unsupported parents are
not made into whole-nucleus nucleolar masks or measured zeros.

Measurements use unchanged original pixels and the final integer labels. Existing
4.0.0, 4.1.0, 4.2.0 and 4.2.1 recipes replay unchanged; new candidates do not
replace researcher-adopted or corrected masks. Local private real-image acceptance
compares complete label regions with the approved trial, independently checks
original-pixel measurements, and is distinct from general biological validation.

## Group comparison contracts (2026-10-25)

The group-comparison workflow ([goals](drafts/group-comparison/goals.md),
[requirements](drafts/group-comparison/requirements.md)) adds the contracts below.
They are additive: existing selections retain their request/result serialization
and measurement/figure definitions. Saved workspaces, statistics, figures and
public-demo recordings replay under their original versions. The new observation sources and estimates are
accepted by the common-statistics comparison endpoint (two-screen comparisons).
Field-summary 1.0.0 and compartment-summary 1.1.0 are also accepted by the
descriptive endpoint (one-screen descriptions); comparison estimates remain comparison-only.

### Version and compatibility table

| Contract | Version | Status | Compatibility |
|---|---|---|---|
| Analysis spec `experiment` (experiment design, declared strata) | 1.1.0 | Accepted by `PUT /v1/workspaces/{wid}/analysis-spec`; cohorts, descriptions and comparisons read one declared stratum | 1.0.0 documents and their bytes unchanged; results gain `stratum` only for stratified cohorts |
| Analysis spec `experiment` (experiment design) | 1.0.0 | Accepted by `PUT /v1/workspaces/{wid}/analysis-spec` | Optional key; specs saved without it read back with `experiment: null` |
| Field-summary selection (`source: "field-summary"`) | 1.0.0 | Comparisons and per-field descriptions: `nucleus_count`, `nucleus_density_per_mm2` (`field_summary_source.py`). Positivity metrics refused (`field_summary_positivity_not_connected`) | New source; existing sources unchanged |
| Compartment-summary selection | 1.1.0 | Comparisons and per-field descriptions (`compartment_observations.py`; eccentricity from the adopted masks, `nucleolar_shape.py`) | 1.0.0 requests (with or without `version`) and results unchanged |
| Nucleus table | `nucleus-table/1.0.0` | Read-only `GET /v1/revisions/{rid}/nucleus-table` and its CSV/JSON ZIP, shown beside the adopted nuclei | New endpoint; saved measurements, masks and results unchanged |
| Comparison estimates | `comparison-estimates/1.0.0` | Opt-in `estimates` on common-statistics 2.0.0 comparisons with one contrast | Absent from historical requests and results |
| Unresolved-nucleoli policy | `unresolved-as-missing/1.0.0` | Opt-in `compartment_missing` on cohorts and reviews of nucleolar/nucleoplasm revisions; comparisons and descriptions | Absent from historical requests, review records and results; without it every parent must be a candidate |
| Region comparison 1.0.0, common statistics 2.0.0, statistics 1.2.3, figure policies | unchanged | Implemented | Replayed with their original definitions |

### Descriptive observation-source extension

Descriptive 1.0.0 retains its existing per-field medians, linearly interpolated
quartiles, exclusion and missingness ledger, without inference or an independence
claim. Only its independently versioned observation sources are extended; existing
requests and result bytes retain their previous serialization and definitions.
Field-summary 1.0.0 uses `prepare_field_summary_observations`: one value and one
plotted point per measured field, including a measured zero-nucleus field.
Uncalibrated density is missing; explicitly excluded and failed fields follow the
same source rules as comparisons. The redundant within-field median marker is
omitted for this new source. Compartment-summary 1.1.0 uses the shared compartment
adapter and the adopted-mask shape loader: one value per nucleus, with nuclei
without an adopted nucleolus missing, never zero. These selections require reviewed
sources and do not enable automatic previews. The 1.1.0 API/worker uses the same
`assert_complete_compartments` admission check as comparisons: unresolved nuclear
compartments must be resolved or explicitly excluded before queuing; the shared
observation adapter still preserves missingness reasons. Historical 1.0.0
admission behavior is unchanged. The existing figure versions retain
their historical output for previously supported selections.

### Experiment design 1.0.0

A design records what the researcher declared: `layout` (`single`: one group
described; `pair`: two groups compared), the groups (1 or 2), the control group
(required before a pair comparison), the independent runs, each field's group,
run and optional sample (coverslip or well), and whether the researcher confirmed
that the runs were performed independently. Group, run and sample labels are at
most 24 characters, without leading or trailing spaces, control characters or the
separator `·`. Dates are ISO `YYYY-MM-DD`. Nothing is inferred from file names,
folders, dates or plate labels.

Derived per-field metadata (`experiment_design.field_metadata`), used unchanged by
the existing ledgers and the field → sample → unit aggregation (S02):

- condition = group label;
- experimental unit = `run · group` (one unit per run and group, so independent and
  paired designs both validate);
- sample = `run · sample`, or the unit when the run has one sample per group;
- pair = run label for `pair` designs, otherwise none;
- acquisition date = the field's own imaging date, else the run's, else unknown.

`experiment_design.readiness` lists issues to resolve before inference: unassigned
or unknown fields, no runs, no control, a run missing a group, fields without an
imaging date (needed for intensity comparisons, not for areas or counts), and
unconfirmed independence. Descriptions never wait for these issues (S09). The default pair
comparison is paired by run with contrast `[treatment, control]`, so the reported
effect is treatment − control; the researcher still confirms the design (S10).

### Experiment design 1.1.0: declared strata (2026-11-09)

Version 1.1.0 keeps groups (at most two), runs, samples, independence and the derived
metadata of 1.0.0, and adds what the researcher declares to keep comparisons within
one condition (for example one cell line or one time point):

- `factors`: 1–3 named factors, each with its levels;
- `strata`: each stratum is exactly one level of every factor, with a label; the
  same combination is never declared twice. The list may be empty while the researcher
  is still declaring factors (`experiment_design_no_strata`); no cohort can be made then;
- each field's `stratum_id`, chosen by the researcher. A field without one belongs to
  no stratum (`experiment_design_unstratified_fields`); nothing is inferred from file
  names, dates, folders or values.

1.0.0 documents keep their model and bytes (a document without `version` is 1.0.0).
`experiment_design.readiness` checks a stratified design within each stratum: a run that
appears in a stratum needs both groups there, and an empty stratum is named.

In the workspace, 実験 declares factors, levels and strata (one level of every factor
per stratum) and the stratum of each field. Adding a factor removes the existing strata,
because they no longer name a level of every factor; removing a level, factor or stratum
removes the strata that named it. In each case the affected fields keep their group and
run, become unassigned, and the researcher confirms first, with the number of fields
named. Nothing is reassigned automatically. The 2-screen view pairs only fields of the
selected field's stratum within a run, and an unassigned field is not paired.

Strata are read one at a time (`experiment_strata.py`). A cohort of a stratified design
names one declared stratum and the hash of the saved design
(`stratum: {design_version, design_sha256, stratum_id}`; the API returns
`experiment_sha256` with the saved analysis spec). The API checks it against the saved
design and refuses:

- no stratum (`cohort_stratum_required`);
- a field of another stratum (`cohort_stratum_mixed`);
- a stratum field neither included nor excluded (`cohort_stratum_incomplete`);
- a registered field that has no stratum (unassigned, or absent from the design) and no
  recorded exclusion reason (`cohort_stratum_unassigned`): as in 1.0.0, every registered
  field is either analysed or excluded with a reason before a cohort is made, so leaving
  a field out of every stratum is never a silent exclusion. The workspace does not start
  the calculation until each such field is assigned or excluded;
- metadata other than the design derives, i.e. condition, unit, sample, pair or date
  (`cohort_stratum_metadata_mismatch`);
- a design changed since (`cohort_stratum_design_changed`).

A stratified design always uses such a cohort, even when one field is adopted. The
cohort records the stratum (`stratum-selection/1.0.0`): label, factor levels, design
hash, `declared_stratum_count` (how many strata the saved design declared),
`field_ids` (every field assigned to the stratum), `analysed_field_ids` (the fields
the cohort holds) and `excluded_fields` (assigned fields excluded before analysis, with
the researcher's reason).

Unlike 1.0.0, where descriptions never wait for design issues, a formal (reviewed)
description of a stratified design also needs a stratum cohort: it is refused until the
researcher selects a stratum and every field has a stratum or a recorded exclusion. Only
the automatic preview below is exempt.

For a stratified design, descriptions, common statistics and region comparisons (API
and worker) re-check the source against the saved design and refuse:

- a source without a stratum record (`comparison_stratum_required`);
- unassigned fields (`comparison_stratum_unassigned`);
- fields of more than one stratum, or other than the analysed fields
  (`comparison_stratum_mixed`);
- a changed design (`comparison_stratum_design_changed`);
- field metadata other than the design derives, including a metadata edit of a child
  revision (`comparison_stratum_metadata_mismatch`).

Region comparison 1.0.0 predates strata and is refused for a stratified design
(`comparison_stratum_legacy_unsupported`); common statistics 2.0.0 is used instead.
An automatic (unreviewed) description preview of a stratified design describes one
field or fields of one declared stratum; a source holding fields of several strata or
unassigned fields is refused at the API and in the worker (`comparison_stratum_mixed`,
`comparison_stratum_unassigned`). A preview records no stratum and is not a formal result.
Labels containing control characters or a lone surrogate are refused when the design is
parsed, before its hash is computed.

Results, Methods and replay keep the record. Methods state the stratum, its levels and
the design hash, and the counts of assigned, analysed and excluded fields: "The
researcher assigned N fields to this declared stratum; M were analysed and K were
excluded before analysis with recorded reasons. Only fields of this stratum were used.
Other strata were neither pooled with it nor compared, and the stratum was not modelled
as a factor. The saved design declared S strata. Each stratum is analysed separately:
multiplicity is controlled within this stratum's comparison family only, and p-values
are not adjusted for analyses of the other declared strata."

Each stratum's comparisons form their own Holm family. Nothing adjusts for the number of
declared strata, so the count is recorded with every result and shown beside the stratum
choice: a reader can see how many per-stratum analyses were possible, and a stratum
reported alone is not evidence that the other strata were examined and agreed.

Strata are never pooled, compared with each other or modelled as a factor. The
workspace binds the selected stratum and the design hash into the identities of channel
classifications, cohorts and results, so changing either makes them stale instead of
reusing them; a channel gate's digest recomputed over another stratum's fields does not
match. Unstratified designs and earlier results are unchanged.

### Field-summary selection 1.0.0

One observation per field, computed from the adopted, non-excluded regions of the
selected nuclear region set (`field_summary.field_summary_values`):

- `nucleus_count`: the number of adopted nuclei, including nuclei touching the
  image border; `border_count` reports how many touch it. A measured field with no
  regions is an observed zero, not a missing value.
- `nucleus_density_per_mm2`: `nucleus_count / (rows × columns × s² × 10⁻⁶)` with
  the confirmed square pixel size `s` in µm; missing (`calibration_unknown`)
  without calibration.
- `positive_count` and `positive_fraction`: nuclei classified positive by the
  recorded nucleus gate on the judged channel: `gfp-gate/2.0.0` negative-control or
  `gfp-gate/3.0.0` manual/batch Otsu (`keep: "positive"` only), or the channel-neutral
  gate below (either `keep`; the fraction is read before the subset is selected). The
  denominator of the fraction is the number of nuclei with a gate value
  (`evaluable_count`); the total and the non-evaluable count are reported. No
  evaluable nucleus → both the fraction and the positive count are missing
  (`no_evaluable_nuclei`), never zero (owner's decision, 2026-11-10).
- Failed and explicitly excluded fields are not observations (`field_failed`,
  `field_excluded`) and stay in the comparison ledger; their counts are unknown
  (`null`), not zero.
- `evaluable_count` and `positive_count` are reported only for `positive_*`
  selections (otherwise `null`). `excluded_region_count` is the number of the
  field's explicitly excluded regions, which are never counted as nuclei.
- `field_area_mm2` is reported whenever the pixel size is known.
- Aggregation is unchanged: the single field value is the field summary, then the
  sample mean and the unit mean. The count is a count of imaged nuclei, not a
  viability or proliferation measure, and it depends on field selection.
- Only nuclear region sets are counted: StarDist nuclei or researcher-supplied
  (manual/imported) regions. Positive regions, nuclear compartments and Cellpose
  cells are refused (`field_summary_nuclear_source_required`).
- Acquisition review follows pixel area: equal spatial sampling must be confirmed
  and all compared fields must share one calibration, because the count depends on
  the imaged area and resolution.
- Field positivity review: `positive_count` and `positive_fraction` are decided by an
  intensity threshold, so they are reviewed as intensity outcomes of the judged
  channel as well: every compared field needs an acquisition date, the judged
  channel has one dtype, and a contrast whose groups share no acquisition batch is
  refused (`region_comparison_condition_batch_confounded`), exactly as for a mean
  intensity. A per-date threshold does not remove this confound.
- A threshold that no designated negative control fixed (manual, Otsu; legacy
  `gfp-gate/3.0.0`) is exploratory and can be moved after the values are seen. With
  such a gate the positive count and fraction are described only: a comparison
  must use `test: "none"` (unit values and differences, no test, p-value or
  interval); any test is refused
  (`field_positivity_exploratory_threshold_descriptive_only`). Tests require the
  negative-control gate. Whether the control is biologically suitable remains the
  researcher's judgement.

### Compartment-summary selection 1.1.0

Adds to the 1.0.0 metrics, for nuclei with at least one adopted nucleolus
(candidate-free nuclei are missing with `no_nucleolus`, never zero):

- `nucleolar_area_px`, `nucleolar_area_um2`: pixel area of the nucleolar union of
  the nucleus (calibration required for µm²).
- `nucleolar_eccentricity` (`nucleolar_shape.nucleolar_eccentricity`): for each
  nucleolar object of the nucleus, `e = sqrt(1 − λmin / λmax)`, where λ are the
  eigenvalues of the population covariance of the object's pixel-centre
  coordinates (equal to scikit-image `regionprops` eccentricity). A one-pixel
  object (`λmax = 0`) is not measured; a one-pixel-wide line has `e = 1`. The nucleus value is the area-weighted mean of its measured objects;
  if none is measurable it is missing (`degenerate_objects`). Larger values mean
  more elongated nucleoli; rounder nucleoli have smaller values.
- Eccentricity is computed when the comparison runs, from each field's adopted
  nuclear mask (with its exclusions) and adopted nucleolar mask, the same inputs as
  the saved summary. Every summarized nucleus must have the same nuclear and
  nucleolar-union pixel areas and nucleolus count in these masks, otherwise the
  comparison is refused (`compartment_summary_shape_mismatch`).
- `nucleolar_area_um2` needs a confirmed calibration (`compartment_summary_calibration_required`);
  area and eccentricity follow the pixel-area acquisition review (equal sampling,
  one calibration), µm² the calibrated-area review.

### Nucleus table 1.0.0 (2026-11-09)

`GET /v1/revisions/{rid}/nucleus-table?field_id=…[&nucleolar_revision_id=…]`
(`nucleus_table.py`) returns one row per nucleus of a nuclear revision, so a
researcher reads each nucleus's size, nuclear-stain signal, every stain's signal
and its nucleoli together, and opens the nucleus on the image from its row.
`GET /v1/revisions/{rid}/nucleus-table.zip` returns the same table as
`nucleus-table.csv` (one row per nucleus), `columns.csv` (unit and definition of
every column) and the authoritative `nucleus-table.json`. Text cells that a
spreadsheet would read as a formula are prefixed with an apostrophe in the CSV.
The saved files name the stain of every channel column on their own: the table
records each channel's ID, recorded label, stain and role (`channels`), the CSV
repeats them as `<channel>__label` and `<channel>__stain`, and `columns.csv` gives
`channel_id`, `channel_label` and `stain` beside each channel column's definition.
A stain that was not recorded stays empty, never guessed. The table covers one
field; it does not carry the field's display name or its group, run and condition.

- Nuclei are only a revision detected with the nuclear-stain recipe
  (`source: "stardist_nuclear"` with a defining channel); any other region set is
  refused (`nucleus_table_nuclear_source_required`) and never returned as nuclei or
  DNA signal. Rows are bound to the saved nuclear labels by nucleus label
  (`region_id`), never by order or position. The labels must match the saved mask
  hash (`nucleus_table_mask_mismatch`) and every label must have saved rows
  (`nucleus_table_region_mismatch`).
- Nucleus area, raw and background-corrected mean and integrated intensity,
  saturation fractions and their missing reasons are the nuclear revision's saved
  measurement rows (any region protocol), copied unchanged; pixels are not read
  again. The defining channel is marked `nuclear_stain`: its integrated signal is a
  relative DNA-stain signal, comparable only under the same stain, linear range and
  acquisition, not a DNA amount or ploidy. Values are not divided by nuclear area or
  DNA signal. Each channel's background is recorded with the table and in the CSV
  (`background_source`: `confirmed_roi`, `automatic_candidate` (protocol 4.0.0, not
  confirmed by a person) or `not_established`; `background_confirmed`; the subtracted
  `background_median`), so corrected values from an unconfirmed automatic background are
  never read as ROI-corrected.
- A nucleolar revision must be built on this nuclear revision (`compartment:
  "nucleoli"`, the same `nuclear_revision_id`, otherwise
  `nucleus_table_nucleolar_source_invalid`) and its provenance must pin these saved
  nuclei and their mask hash (`nucleus_table_nucleolar_source_mismatch`).
- A nucleus's nucleoli are **confirmed** (`measured`) when the nucleolar revision is
  the field's adopted one and the nucleus has at least one adopted nucleolus that
  remains after the researcher's object exclusions. This is the rule comparisons and
  descriptions use (`compartment_engine.adopted_nucleolar_states`): a nucleolus the
  researcher added, kept or edited counts, whatever the detector recorded. Then the
  table adds object count, union area (px, µm² with a confirmed calibration), union
  area / nuclear area, largest object area / union area, the area-weighted
  eccentricity of compartment-summary 1.1.0 and the number of excluded objects.
- Every other nucleus is `missing`, never zero, with its reason: the detector's
  recorded reason for a nucleus without an adopted nucleolus (`no_candidate` when the
  detector found one but every one was removed or none was recorded, `review_required`,
  `indeterminate`, `processing_failed`, …), `no_adopted_nucleolus` (every adopted
  object excluded),
  `nucleolar_revision_not_adopted` or `nucleolar_field_excluded` (the field is
  excluded in the nucleolar revision). Nucleolar µm² also needs the nucleolar
  revision's calibration to equal the nuclear one; when µm² is absent for confirmed
  nucleoli, `union_area_um2_missing_reason` says why (`calibration_unknown` or
  `calibration_mismatch`). When this field's nucleoli cannot be
  read (not measured, or a damaged mask), the nuclei are still shown and their nucleolar
  values are `not_measured` (`nucleolar_revision_unavailable`). An excluded nucleus, or
  every nucleus of a field excluded in the nuclear revision or on the workspace's
  selection screen, stays in the table with
  `exclusion_scope` (`nucleus` or `field`) and the reason (the nucleus's own, else
  the field's, whole at the selection screen's limit of 300 characters); its nucleolar values are `not_measured` (`nucleus_excluded`), which
  comes before every nucleolar reason. Without a nucleolar revision they are
  `not_measured` (`nucleolar_revision_not_selected`).
- The table records whether the nuclei and the nucleoli are the field's adopted
  revisions (`nuclear_adopted`, `nucleolar_source.adopted`). It is read-only and
  versioned; it adds no comparison or statistics. The workspace shows it beside the
  image of the adopted nuclei with the nucleus ledger (nuclei, excluded, confirmed,
  missing by reason, nuclei with pixels at the detector's saturation value or, when that
  value is unknown, at the file's maximum, per stain; channels corrected with an
  unconfirmed automatic background), both the absolute
  nucleolar area and its fraction of the nucleus, and saves it as the ZIP above.

Label validation (`masks.validate_labels`) and eccentricity
(`nucleolar_shape.nucleolar_eccentricity`) read each object once from its bounding
box instead of scanning the whole image per object; their definitions, results and
error codes are unchanged (`tests/test_nucleus_table.py` compares the eccentricity
with the per-object full-image definition).

### Comparison estimates 1.0.0

Computed from the independent-unit values of a saved two-group comparison
(`comparison_estimates.comparison_estimates`), always as treatment − control. The
metric's scale (`group_comparison_contracts.metric_scale`) decides what is shown:

| Scale | Metrics | Difference | Ratio |
|---|---|---|---|
| ratio | areas, counts, density, raw mean/median/integrated, nucleolar count and area | in the metric's unit | when every unit value is positive |
| difference | background-corrected intensities, nucleolar eccentricity | in the metric's unit | not shown (`ratio_not_applicable`) |
| fraction | positive fraction, nucleolar area fraction | in percentage points (×100) | not shown |
| log2 | log2 nucleoplasm/nucleolus | in log2 units | not shown |

- Paired t test: difference = mean of per-run differences, 95% t interval with
  n_pairs − 1 degrees of freedom; ratio = `exp(mean(log(t_i / c_i)))` with the 95%
  t interval of the mean log ratio, exponentiated. Fewer than two pairs →
  `too_few_pairs`; zero variance → `zero_variance`.
- Welch t test: difference of group means with the Welch–Satterthwaite interval;
  ratio of geometric means, `exp(mean(log t) − mean(log c))`, with the Welch interval
  on log values. A group with fewer than two units → `too_few_units`.
- Rank tests (Mann–Whitney U, Wilcoxon): no difference or ratio interval
  (`rank_test`); the result keeps the existing rank effect sizes, and paired
  designs list the per-run values and differences descriptively.
- Descriptive comparison (`test: "none"`, used while the researcher has not confirmed
  that the runs are independent, requirements E-05): no difference, ratio or interval
  (`inference_not_requested`); group summaries keep n, mean and SD without an interval;
  paired designs list each run's values and difference. No test or p value exists.
- Any non-positive unit value → ratio missing (`nonpositive_values`).
- Group summaries: n, mean, sample SD and the 95% t interval of each group's unit
  values (`too_few_units` below two units).
- Paired designs list each run's control, treatment, difference and (for the ratio
  scale with positive values) ratio, in the saved pair order.
- For the fraction scale, the saved difference, its interval and each run's
  difference are in percentage points (the fraction difference × 100); unit values
  and group summaries stay fractions. The declared test's own estimate in the
  comparison table keeps the fraction unit.

These are pointwise intervals for one declared contrast. The p value remains the
declared test's; estimates never select or replace a test.

The saved estimates are exported with the common-statistics figure as
`estimates.csv` (difference and ratio with basis or reason), `estimates-groups.csv`
and `estimates-runs.csv`, and stated in its Methods.

### Unresolved-nucleoli policy 1.0.0 (2026-10-26)

Requirements Q-05; design and options in
[genellect/cytellect#109](https://github.com/genellect/cytellect/pull/109).
Without the policy, statistics on a nucleolar or nucleoplasm revision still require
every parent nucleus to be a `candidate` (and, for nucleoplasm, a non-empty
nucleoplasm). With it, a nucleus whose nucleolus was not established stays in the
ledger as missing instead of being removed (`compartment_review.py`).

- Kept as missing: parents recorded as `no_candidate` or `indeterminate`, and
  candidate parents whose nucleoplasm is empty after subtraction
  (`empty_after_subtraction`, nucleoplasm revisions only). Their nuclear masks,
  measurements and IDs are unchanged.
- Still stopped: `processing_failed`, `unclassified`, `review_required` (saved
  candidates of a truncated parent await the researcher's review; whether to count
  them individually needs its own rule), `not_measured_recipe`, `legacy_candidate`,
  `none_after_edit` (`compartment_state_not_missing`), and a state table that does not
  list every missing parent (`compartment_ledger_invalid`). An unexcluded
  experimental unit without any value still stops the comparison
  ([region comparisons](region-comparisons.md#input-ledger-and-missingness)).
- Ledger per field: all parent nuclei; resolved (with an established compartment);
  missing by reason; explicitly excluded (nucleoplasm region exclusions, which are
  parent nuclei; part of resolved). nuclei = resolved + missing.
- Confirmation: a cohort request names the policy (`compartment_missing`) and the
  review sends, per field, the missing count by reason. The API rebuilds the ledger
  from the revision's provenance and accepts the review only when the confirmation
  equals it exactly (`compartment_missing_confirmation_mismatch`); the review record
  keeps the policy and the ledger. `GET /v1/revisions/{rid}/compartment-ledger`
  returns the ledger before the review. Statistics stop when the ledger no longer
  equals the reviewed one (`compartment_missing_ledger_changed`).
- Results (common-statistics 2.0.0 comparisons and descriptive results) carry
  `compartment_missing`: per condition and experimental unit, fields, nuclei,
  resolved, missing (with reasons) and excluded. The missing fraction is
  missing / all nuclei; exclusions never shrink the denominator.
- Warning (`compartment_missing_rate_differs`): within one run (the field's `pair`;
  fields without a run form one run), the groups' missing fractions (missing / all
  nuclei, summed over the run's units of each group) differ by at least 10
  percentage points, decided with exact fractions. Groups without nuclei have no
  fraction. Runs whose differences cancel out are each warned. The threshold was
  fixed before it was applied to any data; no warning is not evidence that no
  selection related to the treatment remains.
- Values describe the nuclei whose nucleolus was established, not all nuclei, and
  are not a bias-corrected estimate of the treatment effect.
- Associations refuse a revision reviewed under the policy
  (`compartment_missing_association_unsupported`): their result has no place for the
  ledger.
- The comparison figure exports `compartment-missing.csv`; comparison and
  descriptive Methods state the policy, every group and unit's missing / all nuclei
  and the warning. Descriptive exports keep the ledger in `figure-data.json`.
  Export replay and the in-browser runtime recompute the same ledger from the saved
  review record.


### Selecting a fine-tuned nucleolar checkpoint

Parent-conditioned protocol 4.3.0 accepts `cpsam_v2`, `ncl-r1-step0375` and
`ncl-r1-step0750` with the exact model/SHA pairs in the runtime manifests.
Model selection changes the weights; it does not change input pixels, parent
nuclei, preprocessing, nuclear-scale rejection, signal-support refinement or
measurement arithmetic. The selected ID, SHA-256, model metadata and actual
runner hash accompany the result. Saved recipes retain their selection and
the standard model remains the default. AI proposals preserve manual selection.

Local CPU execution verifies the selected file before loading. The GPU image
contains all checkpoints; the server verifies them before accepting requests.
For the standard model, the server retains the exact previously deployed runner
to serve installed clients. New clients accept that pinned runner only for
`cpsam_v2`; fine-tuned models require the current runner identity. See the
[adapter record](../engines/cellpose/README.md#cytellect-nucleolar-checkpoints).

## Channel-neutral nuclear gate 1.0.0

`channel-gate/1.0.0` classifies the saved arithmetic mean of one explicitly
identified channel inside each exact parent nucleus. It does not infer a stain
from its channel number or rename a stain as GFP. Raw and corrected means are
separate choices; an absent corrected value is unclassified, never replaced by
its raw value. The legacy GFP contracts and saved recipes keep their meaning.

The new filter supports a manual threshold, a negative-control percentile per
acquisition date, and exploratory Otsu per acquisition date. Percentile and Otsu
arithmetic are shared with the existing gate. Negative controls require at least
20 evaluable control nuclei per date; a missing date or insufficient control
population leaves the corresponding classifications missing. A mean strictly
greater than the threshold is positive; equality is negative. Control, excluded,
failed and unclassified observations retain their separate statuses and reasons.
Manual and Otsu thresholds are exploratory and do not establish biological
positivity without a suitable experimental control.

Classification returns a digest of the channel meaning, saved nuclear means,
canonical mask identities, metadata, exclusions, thresholds and full per-nucleus
decisions. Formal descriptions and comparisons require the digest and recompute
it against their frozen cohort. A changed source or experiment record requires
explicit reclassification; the browser never silently substitutes a new gate.
Preview classification does not review or adopt the source. The existing review
and experimental-unit requirements still apply to formal statistics.

For field positive count and positive fraction, the same decision record supplies
the numerator and denominator. Positive fraction is positive / (positive +
negative), before the requested positive/negative subset is selected. Missing,
control and excluded nuclei are reported separately. A zero denominator is
missing, not zero. Choosing the negative subset cannot turn its positive fraction
into zero. These are nuclear positivity summaries, not a cell-count or DNA-ploidy
assay.

When a positive or negative subset is selected by a channel and the intensity of
that same channel is then described or compared, the selected values are bounded
by the threshold by construction. The result carries
`channel_gate_selection_and_outcome_share_channel`, the gate record states it and
Methods say that a difference in that channel between the subsets is not an
independent finding. Other channels and area metrics are not marked.

## Explicit region partition table 1.0.0

`region-partition/1.0.0` measures two explicitly selected memberships in one
native measurement channel inside each exact parent nucleus.
`region-partition-table/1.0.0` binds this calculation to owned, succeeded, frozen
source revisions, original pixel/file hashes, canonical label hashes, confirmed
calibration and saved exclusions. A target or reference can be a saved manual or
imported membership or an exactly bound nuclear compartment. Nonzero membership
labels need not be parent IDs. Both memberships must lie inside the selected
nuclei and be disjoint; they need not cover the whole nucleus. The reference is
never inferred from the remaining pixels.

For each membership, area is its pixel count, mean is the arithmetic mean of its
original pixels and integrated intensity is their sum. Confirmed XY calibration
also gives area in µm². With background median `b` from that nuclear revision's
saved, confirmed measurement-channel ROI, corrected mean is `mean - b` and
corrected integrated intensity is `sum - area * b`. Automatic background
candidates do not establish this ROI. Without it, corrected values are missing.

`K = target mean / reference mean` and `log2K = log2(K)` are computed separately
for raw and corrected values, only when both means are positive and the result
is finite and representable. There is no epsilon, clipping or raw fallback.
An empty region, unresolved compartment, exclusion, nonpositive mean or
out-of-range ratio retains its reason; an unresolved structure never becomes a
zero-valued measurement. Excluded parent IDs and reasons remain in the table.
The historical `log2_nucleoplasm_over_nucleolus` metric is unchanged: selecting
nucleoli as target and nucleoplasm as reference in the new table uses the
opposite ratio direction.

The JSON and CSV use the same server builder. Actual `reviewed` and current
`adopted` flags accompany all three sources; the server resolves adoption from
the saved field selection. The read-only table is a `preview` until every source
is reviewed. Viewing or exporting it never changes review/adoption decisions.
The CSV includes raw/corrected values, missing/exclusion reasons, units, source
provenance and Methods. This table is not yet a common-statistics, figure or replay
source. It reports an apparent intensity partition ratio: linearity, bleaching,
compartment-level saturation and concentration interpretation need experimental
validation before a physical partition coefficient can be claimed. Saturation within the
target and reference regions is not evaluated by this table (its screen, CSV Methods
and this section say so); saturated pixels can bias K.

The registered public DS6a consistency check is reproducible with
`python scripts/verify_research_measurements.py --out <new-directory-outside-checkout>`.
It verifies the seed hash, byte-exact restoration, per-field adopted sources,
native pixel arithmetic and JSON/CSV agreement without running a model or
changing scientific review decisions. It is not an independent detector benchmark
or evidence of biological validity, experimental independence or researcher task
completion time.
