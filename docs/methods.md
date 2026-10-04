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
