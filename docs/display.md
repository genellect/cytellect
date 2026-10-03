# Image display and stored pixel values

Display protocol 1.0.0 describes the preview that is currently shown. It does not change raw images, detection, background correction, masks, measurements, review state, statistical results or exported scientific provenance.

Each acquired image plane is auto-scaled separately. The current viewer requests the 0th and 100th percentiles of the entire stored plane. For percentile values `lo` and `hi`, the existing PNG transform is retained exactly:

`uint8(255 × clip((pixel − lo) / max(hi − lo, 1) × gain, 0, 1))`

The displayed black point is `lo`; the white point is `lo + max(hi − lo, 1) / gain`. The viewer labels these in stored pixel-value units. They are not the storage datatype limits, a background ROI, detector normalization limits, or measured region intensities. The details retain the actual source minimum/maximum, exact percentile values, normalization span, datatype and gain. A constant plane is identified separately from nonconstant data whose chosen percentiles coincide. Increasing display gain does not establish that the original data are saturated.

The native composite independently scales acquired NCL (red), GFP (green) and nuclear-stain (blue) planes. An unacquired component remains black and has no fabricated range. Generic channel IDs are identifiers: even a channel named `merge` is shown as its own grayscale plane. The historical `dapi` role does not identify the actual nuclear dye.

Normal imported grayscale values use `native-grayscale` as the display basis. Compatibility imports use `legacy-imported`; this flag does not prove that the submitted TIFF was RGB. Where RGB was used, the stored plane is the existing maximum of its three RGB components, ignoring alpha. Such values do not establish camera-native intensities. Existing valid finite floating-point stored planes can be displayed; this does not broaden the accepted upload formats.

Both owned PNG endpoints return ASCII-escaped JSON in `X-Cytellect-Preview-Display`. Its `PreviewDisplayMetadata` schema is included in OpenAPI. The range and PNG are produced in one render, with field/channel identity and actual array dtype. The browser checks the identity and decodes that PNG before committing image and receipt together. A changed request immediately hides the old pair; late or cancelled responses cannot restore it. Failed requests offer a retry. Older APIs without the header can still show the image, with an explicit unavailable-range notice. Invalid metadata never supplies guessed ranges.

The header is exposed only through the existing restricted CORS policy. PNGs and metadata retain authentication, ownership, expiry and `no-store` behavior. Metadata contains no original filename, filesystem path, experiment condition or credential. Browser state is in memory only.

This stage does not add manual/common image ranges, a saved display recipe, or a new quantitative pipeline. The current gain control retains its behavior across views. Public precomputed samples have a separate display pipeline and are not assigned invented original-value ranges. Use measurement tables, with appropriate acquisition checks, for comparisons between images.
