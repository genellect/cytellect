# BBBC007: acquired DNA/actin image validation

[BBBC007v1](https://bbbc.broadinstitute.org/BBBC007) contains Drosophila Kc167
DNA/actin images and manually drawn nuclear/cell outlines. The official source
records a CC0 copyright waiver by Anne Carpenter. Attribute images to the David
Sabatini laboratory, outlines to Chris Gang, and the analysis dataset to
[Jones, Carpenter and Golland (CVBIA 2005)](https://carpenter-singh-lab.broadinstitute.org/files/anne/files/16-Jones_Propagate_2005.pdf)
and [Ljosa et al. (2012)](https://doi.org/10.1038/nmeth.2083).

Only the manifest and numerical audit are stored here. Source archives and
intermediate pixels stay outside the checkout. No acquired channel is renamed
GFP or NCL. These archival images do not establish camera-native radiometric
calibration, independent biological replicates, or nucleolar accuracy.

## Fixed sample and observed input rejection

Before inference, select the lexicographically first DNA filename within each of
the four source folders. Retain all four fields. Do not replace a difficult or
unsupported field after seeing the result.

The provider describes grayscale 8-bit TIFF, but `f113` and `f96_17` actually
contain nonidentical RGB channels. Both are rejected by the native-format check.
No weighted RGB conversion, arbitrary component extraction or field replacement
is used. `a9` and `f9620` are accepted original-resolution 2D uint8 image pairs.

## Actual Fiji and independent ImageJ result, 2026-10-03

The fixed Fiji StarDist nuclear detector runs on DNA. The shared
`measurement.region_values` primitive then measures the separate acquired actin
pixels; actual ImageJ independently measures exactly the same ROI pixels. This
developer validation exercises generic arithmetic, not an already available
generic-channel product API.

| Field | Detected nuclear ROIs | Bounded nuclear interiors | Bounded cell interiors | Outcome |
|---|---:|---:|---:|---|
| a9 | 115 | 87 | 98 | Arithmetic agrees |
| f113 | — | — | — | RGB source rejected |
| f96_17 | — | — | — | RGB source rejected |
| f9620 | 109 | 101 | 105 | Arithmetic agrees |

Across **615 ROI comparisons on two accepted fields**, pixel counts, raw means
and midpoint medians agree exactly; the maximum integral or corrected-integral
absolute difference is 7.28e-12 intensity-pixels. These overlapping region
definitions do not represent 615 independent biological observations. A fixed
15x15 region-free block tests reference-offset arithmetic only; it is not
claimed to be biologically cell-free background. Signed corrections are retained.

## Annotation convention remains unresolved

The published outlines are strokes, not labelled object masks. The audit decodes
bounded four-connected black interiors, excludes the drawn boundary pixels and
never repairs an open contour. Small enclosed regions may not be individual
biological cells.

Exploratory nuclear IoU>=0.5 comparisons against these interiors yield F1
**0.0594 (a9)** and **0.6667 (f9620)**. Both are retained in
[benchmark.json](benchmark.json), but **neither is accepted as nuclear detector
performance**. Visual review shows that thick strokes make some interior masks
far smaller than the intended nuclear region. The boundary/fill convention has
not been validated. No detection threshold was tuned to improve these scores.
This comparison also does not reproduce the original paper's adjacent-cell
boundary-distance metric. Model training overlap is unknown.

Numerical agreement therefore passes its own limited check, while biological
segmentation accuracy remains unestablished. The two rejected RGB fields remain
visible in all summaries.

## Reproduction

```bash
uv run python scripts/public_bbbc007.py --data-dir /tmp/cytellect-bbbc007 --download
uv run python scripts/public_bbbc007.py --data-dir /tmp/cytellect-bbbc007 \
  --evaluate /tmp/cytellect-bbbc007-run --fiji /opt/fiji
uv run python scripts/public_bbbc007.py --data-dir /tmp/cytellect-bbbc007 \
  --check-report /tmp/cytellect-bbbc007-run/benchmark.json
```

On Windows, choose a short output directory because the pinned TensorFlow Java
runtime has a documented temporary-path limit. Output directories must be new.
The final check requires both RGB rejections and both numerical successes;
omitting failed fields or substituting an execution failure does not pass.

The first local attempt could not read the installed runtime under sandbox
permissions and stopped before Fiji. A permitted read allowed the second attempt
to complete. The original complete run report is retained separately from this
post-run interpretation. Eleven unit tests cover strict formats, contour
semantics, fixed input identity and report completeness; real-image results above
come from the actual Fiji/ImageJ execution.
