# Generic region measurements — protocols 1.0.0 and 2.0.0

`cytellect_analysis.regions` supplies the typed measurement primitive for confirmed
2D fluorescence channels. The generic API and supervised worker add native
channel-TIFF input, imported/manual region masks, immutable edits and remeasurement,
source-linked descriptive figures, and private export/replay. This implementation
does not by itself establish an installed release or hosted analysis service;
delivery status is tracked in the README and roadmap. Existing NCL/GFP recipes,
scientific identifiers and measurement protocols are unchanged.

Development checkpoint (2026-10-04): protocol 2.0.0 adds explicit **area-only**
measurement in the area worktree. This increment is not yet merged, publicly
deployed or distributed in an accepted Windows package. The earlier PR #17
runtime-only candidates do not establish area acceptance. A combined `local.12`
package will be built after both increments are accepted on main, then checked
with all fifteen installed browser cases before publication.

## Inputs and biological identity

`RegionMeasurementSpec` records an analysis revision, field, region set/mask
revision, one to three channel identities, background ROI revisions, and optional
confirmed XY calibration. Each channel has an explicit ID and label, an optional
actual stain name, and required identity confirmation. Unknown chemical identity
remains unknown; actin or FITC need not become GFP/NCL to be measured.
`RegionMeasurementSpecV2` retains these identities and calibration but has no
background specification. Its required measurement policy is
`{"version":"1.0.0","mode":"area_only"}`; no raw-only or other new mode is supported.

The function `measure_regions(channels, labels, background_masks, specification)`
accepts 8/16-bit unsigned grayscale arrays and same-size, original-coordinate
integer labels. Label zero is outside measured regions, not proof of biological
background; positive, possibly sparse
IDs identify regions. A disconnected union may deliberately share one ID and is
measured over all its pixels; it does not imply one biological cell. No detection,
cell boundary, nucleolus or channel meaning is inferred by this module.

RGB/extra axes, dimension/dtype mismatches, negative/noninteger/overflowing labels,
unknown channel IDs, duplicate metadata and planes larger than 4096 pixels per
side are rejected in both protocols. Protocol 1.0.0 additionally rejects missing
or unconfirmed background ROIs. Its background masks must
be boolean, nonempty, confirmed separately for every channel and outside the
union of measured regions. Being outside a nucleus does not itself establish
biological background.

## Measurements and calibration

Both protocols emit one long-table row per nonzero region and acquired channel.
In protocol 1.0.0, it carries
region/channel/revision IDs, pixel area, raw mean/midpoint median/integral, and
the same values after subtracting that channel's background ROI median. The
shared existing `region_values` primitive computes intensities. Native negative
corrections remain signed; no clipping, epsilon or positive gate is introduced.
Integrated intensity is a pixel sum, not concentration.

Area in µm² is `pixel_count × pixel_size_x_um × pixel_size_y_um`. Both positive
finite sizes and an explicit confirmation are required. This supports anisotropic
pixels. Partial or unconfirmed calibration is rejected; absent calibration emits
missing µm² with `calibration_unknown`, never assumed square pixels. Empty label
sets emit `no_regions` and no measurement rows, rather than zero-valued objects.

Two intensity-limit diagnostics remain distinct:

- `storage_limit_fraction`: fraction equal to the dtype maximum, 255 or 65535.
- `acquisition_saturation_fraction`: fraction equal to an explicitly confirmed
  acquisition maximum. A value without confirmation or confirmation without a
  value is rejected. Values beyond the dtype or below observed source samples
  are inconsistent and rejected. If neither is provided, this diagnostic is
  missing with `acquisition_limit_unknown`.

Thus a confirmed 12-bit acquisition may detect 4095-valued pixels stored in a
16-bit TIFF, while the storage-limit fraction remains zero. These flags do not
change measurements or exclude regions automatically.

Protocol 2.0.0 counts the original mask pixels and computes calibrated area with
the same formula. No background ROI is needed, even when a region fills the
image. All six raw/corrected intensity values and both signal-limit fractions are
required nulls with `not_requested` reasons. They are not zeros, negative findings
or failed fluorescence measurements. Per-channel provenance records
`background={status:"not_measured",reason:"not_required_for_area"}` without a
fabricated background median, mask or confirmation.

The area path still validates unchanged source pixels and hashes, actual channel
identity, mask shape and acquisition metadata. A confirmed saturation limit below
an observed source value or above the dtype maximum remains invalid. Not
calculating saturation fractions does not establish unsaturated acquisition.
`area_px` and `area_um2` are the only available metric IDs; unknown calibration
remains `calibration_unknown`, while requesting intensity is rejected as
`region_metric_not_measured`.

## Traceability and scope

Table metadata stores the complete channel/region/calibration specifications,
source shape, original-pixel hashes, canonical mask hash, per-channel background
hashes/revisions, pixel counts and medians for protocol 1.0.0, or the explicit
not-measured background record for protocol 2.0.0. Hash format `cytellect-array-v1`
includes the array shape and canonical sample dtype plus little-endian samples;
these are pixel/mask hashes, not file-container hashes. API integration must
add the input file hashes and retain the same immutable revision boundary.

Hand-computed tests exercise signed correction, even-sample medians, unsigned
overflow, sparse IDs, anisotropic calibration, distinct intensity limits,
provenance and invalid inputs. The new table implementation is also compared
against all 615 saved actual ImageJ ROI references from the
[BBBC007 audit](../fixtures/public/bbbc007/README.md). This is reuse of an
independently executed ImageJ reference, not a new Fiji run or biological
segmentation validation. The two rejected RGB fields remain rejected. Background
selection in that audit is a numerical reference offset, not a certified
cell-free ROI.

## API, revisions and recovery

`region_contracts` is the JSON-native wire boundary. Channel/point collections are
lists in API/DB JSON and become tuples explicitly when constructing the strict
scientific specification. `RegionReport` response validation uses JSON mode for
nested strict scientific tables; it does not disable their validation. Unknown
condition, sample, date or experimental unit remains null. A name or field ID is
not evidence of an independent replicate.

`RegionReportType` dispatches the original report and separate `RegionReportV2`
by protocol version. The v2 report, every table and saved request must agree on
the area policy. Area requests require exactly `backgrounds={}`; supplied
backgrounds are rejected, not silently dropped. Absent/None policy keeps v1, and
`region_request_config` omits the new key in that case to preserve historical
JSON and fingerprints. The single strict policy type lives in dependency-free
`region_policy.py` so planning can share it without importing the analysis engine.

The initial generic upload accepts one to three channel TIFF files and an optional
original-coordinate integer label TIFF. This generic upload does not yet provide
multi-channel OME mapping; the existing recipe-specific OME path is unchanged.
Original filenames are not storage paths. Raw input and decoded-array files have
separate hashes and byte counts, checked by the worker. All storage stays inside
the owned private workspace.

Recipe 1.0 retains `manual` and `imported` sources and its original serialized
contract. Manual initialization creates an empty editable label plane. Recipe 1.1
adds `stardist_nuclear` with an explicitly confirmed nuclear-stain channel and the
fixed offline Fiji/StarDist fluorescent-nuclei model. The same Java bridge executes
on the actual selected plane; no GFP/NCL plane is fabricated. Nested
nucleus/nucleolus relationships retain their existing specialized recipes.

Nuclear probability, NMS and normalization percentiles are recorded. Native
coordinates and original measurement pixels are preserved. The standard-2g
automatic admission bounds remain 2048 px per side and 2,700,000 total pixels;
the worker never shrinks an image to fit. Reusing corrected labels does not rerun
Fiji. Per-field provenance distinguishes the original detector event from execution
in the current attempt, including source pixel/model hashes and correction history.

Generic edits reuse the pure label-plane operation extracted from the existing
mask implementation. The old wrapper still enforces nucleus/nucleolus containment
and dependent-child invalidation. Generic add, replace, delete, merge and split
operate on one logical region set without assigning parent/child biology.

Every edit or background/exclusion change creates an unreviewed analysis revision.
Unchanged masks preserve their mask revision ID; edited masks receive a new one.
An explicit `reuse_revision` can expand a representative-field trial into a batch:
previously analyzed selected fields retain their corrected masks, while newly
selected fields initialize from the chosen source. The recipe
and every reused field snapshot must be unchanged. Batch reuse must retain all
parent fields; omitted parent fields are rejected rather than silently dropped.
Canonical labels and their metadata are saved before background-dependent
measurement. Thus an edit that intersects a background ROI remains retrievable
after the visible measurement failure: correcting the background reuses the edited
pixels, not the original import. Previous revisions remain unchanged.

Changing measurement mode creates an unreviewed child while retaining compatible
corrected masks. The area child's empty background map is authoritative; opening
it must not restore a previous revision's background. Returning to intensity
measurement requires actual reviewed backgrounds. Planning answers do not supply
those confirmations; see [versioned adoption](analysis-planning.md).

Experimental metadata can be changed through `region-metadata`. This creates an
unreviewed child revision with explicit metadata changes, unchanged image identity
and reused masks. It does not mutate upload rows or prior scientific snapshots.
Subsequent trial-to-batch expansion retains the adopted parent metadata. The worker
independently verifies that an authorized metadata child changed no other source
properties; an altered image, recipe or unrelated source revision is rejected.

Partial failures and explicit reasons for excluding failed fields remain in the
report. Successful measurement rows are not erased by object exclusions; those
exclusions are separate statistical selection annotations. The shared supervisor
continues to own cancellation, recovery, lease fencing and final publication.
API ownership, active-parent CAS, review and retention apply to generic routes.

## Descriptive figures and reproducible exports

The first generic statistical adapter supports per-field descriptive output with
an explicit region/channel/metric selector. Area duplicated across channel rows
is checked for agreement and counted once per region. No p-value, inferential
confidence interval or independent replicate count is synthesized. A separate
[experimental-unit comparison](region-comparisons.md) explicitly records design,
acquisition comparability and the planned contrast family for generic markers.
It does not relabel another marker as GFP or enable the GFP regression implicitly.
Descriptive distributions by other groupings can be scientifically meaningful,
but are outside this initial per-field selector.

The private reproducibility bundle contains the long region CSV, field outcomes,
canonical NPY/TIFF masks, pixel-exact Fiji ROI exchange, background masks, settings,
Methods, source/environment identity and a file manifest. Background masks are
included only for protocol 1.0.0. CSV string cells are
protected against spreadsheet formula interpretation; negative numerical values
remain numerical. Raw TIFF files are included only with explicit opt-in.

Source-linked statistical figures require a reviewed revision. Before export,
the corresponding adapter recomputes the saved selector/design from the source table;
a changed plot value or source revision is rejected. Replay validates bundle and
raw-image hashes, remeasures saved masks through `measure_regions_versioned`, and regenerates
recorded SVG/PDF/PNG and source tables. It reports exact equality of
saved measurements, descriptions and experimental-unit comparisons when present.
Failed or unmeasured fields remain diagnostic
and are explicitly not reassessed by this measurement replay. No detector or model
download runs during replay.

V1 retains bundle `cytellect-region-reproducibility/1` and Methods 1.1.0. Area-only
uses bundle `/2` and Methods 1.2.0, retaining nulls and their reasons in the CSV
and report. Replay rejects a changed/missing policy, mixed protocols or added
background rasters, even if outer file hashes have been updated. It does not
retroactively convert old bundles or measurement tables.

## Validation scope

### Batch registration and retry identity

The optional `client_upload_id` is a client-generated canonical UUID scoped to the
owned workspace. Repeating it with the same normalized input specification and
original file hashes returns the accepted field. Different bytes or metadata with
that ID produce `region_upload_id_conflict`; they never overwrite a field.
Uploaded filenames are not storage paths or identity. The transaction repeats
the identity lookup, checks quotas and inserts once, so concurrent retries cannot
double-count fields or bytes. Unused temporary files are removed.

The generic upload route retains authentication, ownership, expiry, Origin/CSRF,
body/time and concurrency limits before parsing. Its workspace count/byte quota
check occurs in the registration transaction, after the retry lookup. This lets a
previously accepted upload be recovered even at quota; a new over-quota request
may consume one bounded temporary upload before rejection and cleanup. Other
upload routes retain their previous pre-parse quota checks. Schema migration0002
adds nullable identity and planning columns without rewriting existing records.
Migration is forward-only: an older package whose migration history stops at0001
cannot reopen the upgraded database. Keep a compatible package for recovery;
do not erase the database or create an automatic research-data backup to force
a rollback. Download needed results before changing the installed application.

### Evidence boundaries

The 2026-10-04 area source checkpoint passed 150 focused tests across
`test_region_measurement_v2.py`, `test_region_area_contracts.py`, `test_regions.py`
and `test_region_contracts.py`, with no failures/skips. These check 6/12-pixel
regions and anisotropic .36/.72 µm² reference areas, strict null/provenance
contracts, invalid inputs and unchanged v1 serialization/signed calculations.
This is a focused core/contract run, not full CI or installed acceptance.
After integration, the coordinator separately completed 89 cases across the
existing descriptive/comparison/export suites and `test_region_area_exports.py`.
The latter contributes nine area cases covering source-linked descriptions,
closed-form Welch/paired arithmetic, mode rejection and original-pixel
export/replay with regenerated figures. These counts describe separate focused
runs, not a total full-suite claim. Independent
source review checked these adapter/export changes; reading code is not another
test execution. Private-image M4 and human-researcher M5 remain open.

Hand-calculated and adversarial tests cover strict JSON round trips, no-Fiji
manual/imported execution, signed arithmetic, source-file tampering, mask edits,
background-collision recovery, partial failures and exclusions, exact Fiji ROI
round trips, raw opt-in, export review/source gates and replay equality. Legacy
nuclear/nucleolar mask regressions are retained.

The BBBC007 public-image integration additionally exercised actual HTTP upload,
SQLite JSON snapshots, the supervised worker and HTTP measurement retrieval for
DNA plus actin. It produced 1,230 channel rows across six fixed mask sets; the 615
actin ROI measurements agree with the saved independent ImageJ references. The
DNA rows did not receive a new independent ImageJ comparison. Both previously
rejected RGB fields remained rejected at upload. This is arithmetic and input/API
integration evidence, not a new Fiji run, biological instance-mask validation,
verified camera-native radiometry or independent biological replication.

The nuclear-only adapter was also compared against the existing fixed detector:
two real-Fiji old/new command comparisons (default and nondefault parameters),
the five fixed BBBC039 fields and the two valid BBBC007 fields had identical nuclear
label pixels. The two preselected RGB rejections and previously reported low or
ambiguous detection scores remain in the evaluation record. Adapter equivalence
is not a new claim of biological accuracy or independent model evaluation. Original
NCL/GFP/legacy/ROI and recoverable-failure Fiji regression checks were retained.
