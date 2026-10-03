# Generic region comparisons — protocol 1.0.0

Reviewed region measurements can be compared using explicitly recorded experimental
units. This is an additional path beside descriptive figures and the original
NCL/GFP recipes. A channel keeps its actual label and stain; channel identifiers,
file names, region counts and field counts do not establish biological identity or
independent replication. Uncertain designs should use descriptive figures first.

The API is `POST /v1/revisions/{rid}/region-comparisons`. The supervised statistics
job preserves `mode="region-experimental-unit"` and the complete strict
`RegionComparisonRequest`. The worker binds the submitted request to the reviewed
source revision before calling `compare_regions(report, config, request)`.

## Required decisions

Select one logical region definition and metric. Intensity needs exactly one
acquired channel; area requires no channel selector and is counted once per region.
The adapter validates the saved mask identity, image shape, calibration, actual
channel metadata and area agreement between channel rows before selecting values.
It shares this validation with descriptive figures.

Record the independently allocated experimental unit and, for a paired design,
the matching basis and pair identifiers. Define the units from the experimental
allocation, not by simply treating all images, wells or cells as independent. The
scientific interpretation still depends on whether the actual design supports the
claimed population and treatment effect. See [Lazic et al., 2018](https://journals.plos.org/plosbiology/article?id=10.1371/journal.pbio.2005282)
and [SuperPlots, 2020](https://rupress.org/jcb/article/219/6/e202001064/151717/SuperPlots-Communicating-reproducibility-and).

The request also records the complete conditions and comparison family, acquisition
comparability and a review of omissions. Confirmations must be literal boolean
`true`; strings and numbers do not count. The interface starts with no selected
experimental design or comparison conditions. It does not select a test using a
preliminary significance or normality test and does not search thresholds for a
smaller p-value.

## Aggregation and inference

Protocol `field-median_sample-mean_unit-mean-v1` uses:

1. The median of selected region measurements within each field.
2. The arithmetic mean of those field summaries within each sample.
3. The arithmetic mean of the sample summaries within each experimental unit.

Each retained unit contributes one outcome per condition. More regions, fields or
samples within a unit do not increase independent n. Raw, background-corrected and
integrated values remain distinct metrics. Negative corrected intensities and zero
remain measurements; unavailable values are never replaced by zero. Integrated
intensity is not a concentration measurement.

Independent groups use two-sided Welch t tests. Paired groups use two-sided paired
t tests on complete matched unit differences. The reported effect is always
`group_a − group_b`. For paired data it is calculated directly as the mean of
paired differences, avoiding cancellation from subtracting two large group means.
The shared arithmetic implementation converts numeric arrays to floating point
before subtraction, avoiding unsigned-integer wraparound. Non-finite or
non-estimable results fail closed. The legacy statistics version is **1.2.3** for
this deliberate numerical correction; region comparisons and their figure protocol
start at **1.0.0**. See [statistics.md](statistics.md) for historical versions.

Standard errors and Student t quantiles supply pointwise 95% confidence intervals
for each difference and group mean. These are not simultaneous confidence
intervals. All requested contrasts must be estimable before Holm correction is
applied to the entire declared family. A failed contrast never silently shrinks
the family. Control comparisons and a complete, explicitly selected planned family
are supported; the latter may contain both control and non-control comparisons.
The original NCL/GFP family rules remain unchanged.

There must be at least two retained units per independent group, or two complete
pairs. This is a computational minimum, not sufficient power or validation of t-test
assumptions. Results with fewer than five units per condition carry a caution.
This release does not implement mixed-effects models, batch adjustment, alternative
aggregation choices, transformations or automatic outlier removal. Reference
calculations follow the [NIST t-test definitions](https://www.itl.nist.gov/div898/handbook/eda/section3/eda353.htm)
and [Holm's original procedure](https://www.ime.usp.br/~abe/lista/pdf4R8xPVzCnX.pdf).

## Input ledger and missingness

Every input field remains in the source ledger, including fields outside the
declared comparison, explicitly excluded fields, and fields without regions or
selected values. Conditions must be known so that comparison membership can be
determined. In-scope sample and unit IDs are required even when their fields are
explicitly excluded. A sample cannot map to multiple units within a condition.

Independent-group analysis rejects units shared between conditions. Paired
analysis checks the original input ledger, not only the surviving outcomes: one
unit per condition and pair, a stable pair ID for a shared unit, and all declared
conditions in each pair. A pair absent from both sides cannot disappear unnoticed.
An entire explicitly excluded pair remains in the ledger. Partially excluded or
otherwise incomplete pairs are rejected.

Unresolved field failures stop the comparison. An unexcluded unit with no outcome
also stops it. Available observations within a unit can contribute when another
field is empty or a metric is missing, with field status, missingness and counts
retained. The researcher must review this policy; it does not assert missing at
random. No field-level measurement failure is converted into a zero or an inferred
observation count. Region-level exclusions of every outcome are insufficient to
silently drop an entire unit: that decision requires explicit whole-field
exclusions and remains visible in the unit ledger.
An excluded failed field must also have the same whole-field exclusion and reason
in the saved source configuration. A failure-ledger entry alone cannot authorize
dropping that field or its unit. This integrity check also applies to the shared
generic descriptive adapter; valid measurement values remain unchanged.

## Acquisition comparability

The researcher confirms that the selected structures and measurement scales are
comparable. Matching labels, bit depth and timestamps alone cannot prove this.
Illumination, detector response, exposure/gain, labeling, background and saturation
must be considered; see [Waters, 2009](https://rupress.org/jcb/article/185/7/1135/35453/Accuracy-and-precision-in-quantitative).

- Intensities require actual acquisition dates/batches, using recorded metadata or
  an explicit batch mapping. Unknown dates remain unknown; none are manufactured.
  Different selected storage dtypes are rejected. Measured storage-limit or
  confirmed acquisition-limit saturation in a selected region is rejected. An
  unknown acquisition saturation limit remains unknown and must be considered in
  the researcher review.
- Compared conditions with no shared acquisition batch are rejected as confounded.
  Partial imbalance is flagged and not adjusted. Paired outcomes require matching
  batch sets within each pair. Shared batches do not prove absence of confounding
  or technical drift.
- Pixel area and integrated intensity require an explicit equal spatial sampling
  confirmation and consistent calibration metadata. All-unknown calibration can
  remain in pixel units only with that confirmation; micrometre units are never
  invented.
- Physical area requires calibration for eligible measured fields. Different
  known calibrations require the calibrated-area basis and a comparison of the
  biological region definition and sampling. Unknown acquisition date is allowed
  for area; this does not establish comparable region selection or resolution.

The output explicitly states that acquisition equivalence and biological
independence are researcher-reviewed, not machine-verified. No intensity
normalization or batch correction occurs.

## Figures, source files and reproducibility

`render_region_comparison(result, output_dir)` uses the existing audited vector
renderer with generic measurement labels. Observations, field medians, independent
unit summaries, group means and their pointwise confidence intervals are distinct.
Paired designs display matched pair lines. Jitter uses seed 0 and affects display
only. Actual channel/stain, unit counts, comparison direction, tests, Holm family,
pointwise intervals, source revision and limitations are retained in the caption
and Methods. Journal-width presets specify layout, not journal acceptance.

English and Japanese SVG retain text; PDF embeds a supported font. Existing exact
glyph and layout guards reject unsupported text or clipping rather than silently
dropping labels. Graph geometry, source values, SVG/PDF structure and PNG dimensions
are tested. A plot failure does not authorize changing the scientific selection.

The figure bundle contains SVG/PDF/PNG, `figure-data.json`, caption and Methods,
plus CSV files for plotted observations, all observations, source fields, field
summaries, sample summaries, experimental units, the unit ledger and comparisons.
Nonempty pair, missingness and excluded-failed-field ledgers have their own CSVs.
Source CSV hashes, original saved settings, actual channel metadata and a source
fingerprint are included. IDs and manuscript text remain private research data.

The fingerprint covers the report plus recipe, fields, immutable metadata and
image identity, backgrounds, exclusions and source review. Export recomputes the
result from that source and rejects substituted or unknown result fields. Replay
checks original file hashes and remeasures saved masks, then repeats aggregation,
inference and figures. A matching numerical replay does not validate segmentation
annotations, experimental independence or the biological conclusion. Failed and
unmeasured fields remain diagnostic and are not reassessed during replay.

## Evidence and remaining limits

### Inspecting saved aggregation

The source implementation exposes each saved unit value as an expandable sample
and field hierarchy. It joins the saved ledgers and intermediate tables by exact
condition/unit/sample/field identities. Paired results start from the saved pair
ledger. It does not compute new means, medians, observation counts or independent
n in the browser, and does not substitute current editable metadata into history.

Excluded fields and units remain visible. Missing values are shown as uncomputed;
an excluded failed field has unknown observation counts, not an observed zero.
An ambiguous or orphaned join stops the hierarchy display while preserving the
saved result and downloads. Invalid measurement-source metadata disables that
field's verified image link instead of selecting a different channel or mask.

Opening a contributing field verifies the historical revision, canonical mask
hash, mask revision, shape, source and actual channel identity. It displays the
whole field without pretending that an aggregate point is an individual region.
Area stays channel-neutral; any fluorescence layer is explicitly for viewing.
Field names match the image viewer. Pending changes to regions, settings or
experimental metadata prevent source navigation until resolved. These are source
features; the immutable local.11 package retains its documented earlier behavior.

Deterministic numeric fixtures independently check unequal nested sampling,
Welch/paired arithmetic, scale changes, large-offset paired differences, unsigned
subtraction, area deduplication, family-wide Holm, metadata conflicts, missing units,
both-sided missing pairs, explicit exclusions, saturation and acquisition
confounding. API tests additionally run known original pixels through the worker,
export and replay, and verify owner/deletion boundaries and result tampering.

Registered published images test measurement and detector integration separately.
Their source folders or image IDs are not invented experimental units. These
checks do not establish biological inference over a published dataset with unknown
replication. Nonpublic experiment validation and researcher usability assessment
remain separate acceptance gates.
