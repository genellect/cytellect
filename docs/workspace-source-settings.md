# Source-bound workspace settings

Analysis intent is stored in a versioned workspace AnalysisSpec. Saving it does not start a job, adopt a mask, confirm independent replication or send anything to an LLM. Writes use compare-and-swap against both the specification and channel-assignment versions. Figure and statistics drafts, including scatter axes, persist independently of execution.

## Channel scopes

Channel slots such as `c1` do not have a product-wide stain meaning. A mapping applies to an explicit set of acquired fields. Scoped updates require the same channel-ID configuration; new imports retain their own acquisition metadata and do not silently receive an older mapping. Migration 0008 pins existing global assignments to the fields present at migration time. Historical revision snapshots are unchanged. Comparisons must preserve source identity and must not combine incompatible stains merely because their local slot names match.

## Confirmed background ROI

Background polygons are saved separately from measured object masks, in original image coordinates and keyed by field and channel. Saving the polygon records the explicitly selected channel identities without inventing a stain name. An unknown stain can remain null. The existing corrected measurement protocol 1.0.0 requires a background for every acquired channel; raw and automatic-background policies remain available independently.

The background is its polygon's original-pixel median. Corrected mean is raw mean minus background median; corrected integral is raw integral minus area times background median. Negative values are retained. Background overlap with measured objects is rejected, not silently clipped. Changing only background or measurement policy reuses the adopted object masks and creates a new measured revision.

When switching from observed import metadata to explicitly confirmed channel identity, only the evidence fields may change. Image pixels, stain/label values, acquisition limits, coordinates and detector parameters remain checked against source provenance. Earlier result files are immutable. Background edits never become cell or nuclear mask edits.

Tests cover exact mask reuse without detector execution, negative corrected values, scope isolation, current-version conflicts and ownership. These code checks do not replace visual review of an experiment's background ROI or establish the biological suitability of automatic segmentation.
