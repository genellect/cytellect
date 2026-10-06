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
it cannot reuse masks produced with another scale. Omitting scale retains the
older capacity-based behavior and recipe version.

Scale is an experimental setting, not an accuracy guarantee or a universal default.
The StarDist [FAQ](https://stardist.net/faq/#do-i-need-to-rescale-my-images-how-do-i-know-which-pixel-resolution-is-required)
describes input object-size mismatch as one possible source of oversegmentation.
Inspect boundaries on representative fields before applying a scale to a batch.
