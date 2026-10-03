# Generic region measurements — protocol 1.0.0

`cytellect_analysis.regions` adds a separately typed analysis primitive for
confirmed 2D fluorescence channels. **It is not connected to the current Web UI,
upload API, statistics selector or installer release.** Existing NCL/GFP recipes,
scientific identifiers and measurement protocols are unchanged.

## Inputs and biological identity

`RegionMeasurementSpec` records an analysis revision, field, region set/mask
revision, one to three channel identities, background ROI revisions, and optional
confirmed XY calibration. Each channel has an explicit ID and label, an optional
actual stain name, and required identity confirmation. Unknown chemical identity
remains unknown; actin or FITC need not become GFP/NCL to be measured.

The function `measure_regions(channels, labels, background_masks, specification)`
accepts 8/16-bit unsigned grayscale arrays and same-size, original-coordinate
integer labels. Label zero is unmeasured background; positive, possibly sparse
IDs identify regions. A disconnected union may deliberately share one ID and is
measured over all its pixels; it does not imply one biological cell. No detection,
cell boundary, nucleolus or channel meaning is inferred by this module.

RGB/extra axes, dimension/dtype mismatches, negative/noninteger/overflowing labels,
unknown channel IDs, duplicate metadata, missing or unconfirmed background ROIs,
and planes larger than 4096 pixels per side are rejected. Background masks must
be boolean, nonempty, confirmed separately for every channel and outside the
union of measured regions. Being outside a nucleus does not itself establish
biological background.

## Measurements and calibration

One long-table row is emitted per nonzero region and acquired channel. It carries
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

## Traceability and scope

Table metadata stores the complete channel/region/calibration specifications,
source shape, original-pixel hashes, canonical mask hash, per-channel background
hashes/revisions, pixel counts and medians. Hash format `cytellect-array-v1`
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

Connecting this primitive to the product still requires upload/channel mapping,
mask review and revision lifecycle, long CSV export, metric selection, and a
source-linked figure path. No p-values, statistical unit assumptions or generic
automatic object detector are introduced here.
