# Descriptive measurements and figures — protocol 1.0.0

The descriptive path displays reviewed measurements from one or more fields
without requiring independent experimental-unit declarations. One field and
one finite observation are valid. It does not perform a hypothesis test,
regression, standard-error calculation or confidence-interval estimation.
Observation and field counts never become an independent replicate count.

This is a separate API contract:
`POST /v1/revisions/{rid}/descriptive`. The existing statistics endpoint and
`StatisticsRequest` keep their inferential requirements unchanged. A descriptive
job uses the existing supervised statistics job kind with an explicit
`payload.mode="descriptive"`; workers dispatch through that saved mode.

## Request and scope

`DescriptiveRequest` requires `mode="descriptive"` and one source selector:

- `source="legacy-cell"`, with an existing nuclear/NCL/GFP measurement ID.
- `source="region"`, with a logical `region_set_id`, metric and, for intensity,
  an exact acquired `channel_id`. Area metrics require the channel to be unset.
- `source="numerical"`, `metric="value"` exists as a library adapter for already
  imported strict numerical tables. Its product API and relaxed metadata import
  are not part of the initial descriptive image integration.

The initial grouping is per field only. Distribution plots are supported;
paired/scatter plots, comparison groups, thresholds, sensitivity searches and
independence confirmations are rejected as unsupported request fields.
Conditions, samples, dates and declared unit names remain source metadata.
Unknown metadata remains null, without invented conditions, dates or unit IDs.

An acquired channel's name does not establish comparability of exposure,
instrument settings or staining. Per-field figures do not imply that these
conditions have been verified. A generic region can be a disconnected ROI union
and does not necessarily represent one cell. Current automatic detectors and
legacy biological definitions retain their own limits.

## Arithmetic and source integrity

The adapters consume authoritative original-pixel measurements; they do not
repeat normalization, background subtraction, segmentation or gating.
Native negative corrected intensities and true zeros remain signed values.
For an intensity selector, exactly one channel supplies each region's value.
For area, the repeated per-channel area values, calibration and missing reasons
must agree, then one region contributes one observation. Channel-row count is
never reported as a region count.

Region keys include field, region set and region ID. Different fields may use
the same region ID. A field may not mix mask or analysis revisions, duplicate
an object-channel pair, omit a channel or contradict its snapshot's channel
identity. The saved target definition must agree across the selected fields;
an ordinary manual correction does not itself change that definition.
Shape and calibration must also match the immutable upload snapshot, so
changing both a saved table's calibration and its computed areas cannot supply
its own evidence. Calibration is checked against the recorded pixel area. Absent calibration
means missing square-micrometre values, not zero or an assumed pixel size.

The legacy adapter preserves saved GFP selection and explicit exclusions,
including per-object threshold/range evidence. The generic adapter uses explicit
region/field exclusions without inventing GFP selection. Input observations
partition into explicit exclusions, remaining gate exclusions, remaining
missing values and selected finite values. Selection records and missing reasons
are exported. Field failures are rejected unless they were explicitly excluded
with a reason; excluded failed fields remain in the total input-field count
and are reported separately. For generic regions, each excluded failure must
match a saved whole-field exclusion with the same reason; the failure ledger
alone cannot authorize exclusion. This source-integrity check changes no valid
measurement or summary value. A successful field with no regions is distinct
from failure and remains visible as `no_regions`.

Each field gets the selected observation count, median, minimum, maximum and
quartiles. Quartiles use linear interpolation between sorted values with
`h=(n-1)p`; they describe the distribution and are not confidence intervals.
There is no pooling across fields, sample aggregation or unit-level mean.
All-missing selections fail with `no_valid_selected_measurements` while the
source diagnostic measurements remain available.

API/worker/replay ownership, expiry, immutable revision and review gates remain
required. Switching to a descriptive metric does not bypass failed fields,
unresolved nucleolar processing failures or stale masks. The pure descriptive
functions do not authenticate sessions or authorize review acceptance; their
callers must preserve those gates.

## Outputs

The result has `analysis_kind="descriptive"`, `descriptive_version="1.0.0"`,
source selector/revisions, observation kind, unit, values, field summaries,
counts, selection, missingness and source-field provenance. Independent-unit
count is null and independence status is `not_assessed_in_descriptive_analysis`.
There are no comparison/model/unit-summary/mean-confidence-interval fields.
An absent test result is never described as nonsignificant.

The separate descriptive figure protocol is 1.0.1. It reuses the existing
Nature-size presets, normal-font-file checks, editable SVG/PDF output, 300 dpi
PNG and label-layout rejection. It does not change the existing inferential
renderer. Points show selected observations and open squares show field
medians. Horizontal jitter uses a recorded seed of zero and never changes values.
Fields receive short display labels whose actual IDs are in the source mapping.
The selected acquired channel is named on the axis, and the caption records
its exact ID, label and actual stain (or explicitly unrecorded stain).
Counts are explicitly named observations, not an unlabeled independent `n`.

Artifacts include `plot-data.csv`, `field-summary.csv`, `selection.csv`, optional
`missingness.csv`, SVG/PDF/PNG, `figure-caption.md`, `methods.md` and
`figure-data.json`. The figure-data file contains source identities, original
channel/stain labels, mask and background provenance, source-table hashes and
font identity. The returned artifact list includes only generated files;
no nonexistent `comparisons.csv` link is emitted. Derived data remain private.

The caption and Methods explicitly state the descriptive scope, absent
inference, unestablished acquisition comparability, selection and missingness.
The journal-size preset controls layout; it does not establish biological
validity or journal acceptance. Figure-generation failure still fails its job;
it does not erase source measurements or a previous successful output.

## Verification and limits

`tests/test_descriptive.py` uses hand-computed signed intensities, area,
anisotropic calibration, quartiles, unbalanced field counts and adversarial
identity/selection cases. Expected values are not produced by the descriptive
implementation. `tests/test_descriptive_figures.py` actually renders English
and Japanese SVG/PDF/PNG, inspects source values and hashes, vector text/font
embedding, one-observation and empty-field behavior, and rejects corrupted
counts, inferential payloads and clipped labels.

`tests/test_descriptive_export.py` checks a single-nucleus legacy bundle from
original TIFFs through offline remeasurement and regenerated figures. Export
and replay recompute each saved description and compare all authoritative
fields; altered values, wrong revisions, incomplete snapshots and missing
review cannot be attached as a matching result. Diagnostic measurement-only
exports retain their existing behavior.

These tests establish arithmetic, provenance and supported export behavior.
They do not establish segmentation accuracy, biological independence, image
comparability or novice usability. Public-image integration, private-image
evaluation and researcher review remain separate evidence.

The distinction between observational and experimental units follows
[Lazic et al.](https://doi.org/10.1371/journal.pbio.2005282); the importance of
showing experimental replicates separately is discussed in
[SuperPlots](https://doi.org/10.1083/jcb.202001064). This descriptive output is
not an independently replicated SuperPlot. Acquisition/background limitations
follow [Waters](https://doi.org/10.1083/jcb.200903097). Figure formatting uses the
[Nature final-artwork guide](https://research-figure-guide.nature.com/figures/building-and-exporting-figure-panels/),
without claiming scientific acceptance.
