# Image display and stored pixel values

Display protocol 1.0.0 describes the preview that is currently shown. It does not change raw images, detection, background correction, masks, measurements, review state, statistical results or exported scientific provenance.

Each acquired image plane is auto-scaled separately. The current viewer requests the 0th and 100th percentiles of the entire stored plane. For percentile values `lo` and `hi`, the existing PNG transform is retained exactly:

`uint8(255 × clip((pixel − lo) / max(hi − lo, 1) × gain, 0, 1))`

The displayed black point is `lo`; the white point is `lo + max(hi − lo, 1) / gain`. The viewer labels these in stored pixel-value units. They are not the storage datatype limits, a background ROI, detector normalization limits, or measured region intensities. The details retain the actual source minimum/maximum, exact percentile values, normalization span, datatype and gain. A constant plane is identified separately from nonconstant data whose chosen percentiles coincide. Increasing display gain does not establish that the original data are saturated.

The native composite independently scales acquired NCL (red), GFP (green) and nuclear-stain (blue) planes. An unacquired component remains black and has no fabricated range. Generic channel IDs are identifiers: even a channel named `merge` is shown as its own grayscale plane. The historical `dapi` role does not identify the actual nuclear dye.

Normal imported grayscale values use `native-grayscale` as the display basis. Compatibility imports use `legacy-imported`; this flag does not prove that the submitted TIFF was RGB. Where RGB was used, the stored plane is the existing maximum of its three RGB components, ignoring alpha. Such values do not establish camera-native intensities. Existing valid finite floating-point stored planes can be displayed; this does not broaden the accepted upload formats.

Both owned PNG endpoints return ASCII-escaped JSON in `X-Cytellect-Preview-Display`. Its `PreviewDisplayMetadata` schema is included in OpenAPI. The range and PNG are produced in one render, with field/channel identity and actual array dtype. The browser checks the identity and decodes that PNG before committing image and receipt together. A changed request immediately hides the old pair; late or cancelled responses cannot restore it. Failed requests offer a retry. Older APIs without the header can still show the image, with an explicit unavailable-range notice. Invalid metadata never supplies guessed ranges.

The header is exposed only through the existing restricted CORS policy. PNGs and metadata retain authentication, ownership, expiry and `no-store` behavior. Metadata contains no original filename, filesystem path, experiment condition or credential. Browser state is in memory only.

Display protocol 1.0.0 adds no manual image range, saved display recipe or quantitative pipeline; the two-group view's shared range (below) is a separate display-only step. The current gain control retains its behavior across views. Public precomputed samples have a separate display pipeline and are not assigned invented original-value ranges. Use measurement tables, with appropriate acquisition checks, for comparisons between images.

## Shared display range 1.1.0 (two groups side by side, 2026-10-26)

When a two-group experiment design is shown side by side (the 2-screen view), both
previews of the selected channel are redrawn in the browser on one shared scale.
Each preview's 8-bit values are mapped back to stored values with its own verified
receipt (`display_black_value`, `display_white_value`) and then to the shared scale
(`apps/web/src/lib/shared-display.ts`), so equal screen brightness means equal
stored values within 8-bit quantization.

The shared black and white points are the 0.5th and 99.5th percentiles of the two
previews' stored values together, kept inside the union of their own ranges
(`percentileRange`). The brightest and darkest 0.5 % of pixels show at the limits.
1.0.0 used the union itself; one image with a few very bright objects then made
the other nearly black (a UX review found the JUMP pair hard to read, 2026-10-26).
When the percentiles are degenerate the union is used. The view states the shared
range in one line, with the rule on demand. It refuses to guess: if either preview
lacks a verified receipt or is a composite, both keep their own ranges and the
view says that brightness must not be compared. Values a preview had already
clipped stay at its own limit.

Each pane opens with its image filling the pane (the smallest zoom that leaves no
empty margin), centred. In the public demo, the nucleolar and nucleoplasm views draw the
adopted nuclei faintly as context; only the shown region's outlines can be selected.

This is display only. Original pixels, detection, masks, measurements, review
state and statistics are unchanged, and the shared scale does not correct
differences in exposure, gain or illumination between acquisitions (see the
acquisition review in S10). The two fields are different cells; zoom and position
are linked only when the researcher keeps "拡大を連動" on, and that link
implies no spatial correspondence. Zoom is matched in pixels, because the
workspace images carry no confirmed calibration.
