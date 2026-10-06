# Fluorescence-positive candidate regions

Signal detector protocol `1.0.0` uses the locked Fiji runtime: ImageJ thresholding
and MorphoLibJ 8-connected components. It is separate from StarDist nuclear
detection and from the existing per-nucleus NCL nucleolar detector. The caller
must record the defining channel and threshold method; filenames, colours and
channel numbers do not establish the marker identity.

- `otsu`: an exploratory, per-field ImageJ Otsu rule over 256 bins between the
  detection plane minimum and maximum. Pixels whose bin is greater than the
  selected threshold bin are candidates. A uniform image is `indeterminate`,
  never automatically biological absence.
- `manual`: pixels strictly greater than the explicitly saved source-scale
  threshold are candidates. The equality boundary is excluded.
- Optional Gaussian smoothing affects detection only. The saved sigma, minimum
  component area and optional ImageJ watershed are explicit parameters. There is
  no implicit smoothing, area removal or touching-region split.

Labels use original image coordinates and resolution. Measurement uses the
original input pixels, including when a detection blur was requested. Native
input and display-RGB-derived planes retain their input mode; a display export
does not become calibrated native fluorescence because a mask was detected.

GFP-positive candidate regions may extend outside nuclei and are **not** inferred
whole cells. NCL-positive candidate regions without a parent nuclear mask are
**not** identified as nucleoli. For nuclear compartments, reuse the existing
per-nucleus NCL detector with validated nuclear labels; nucleoplasm is the nuclear
pixel set minus the union of its nucleolar candidates. Detection failures or
ambiguous nucleolar states require review and must not silently become valid
whole-nucleus nucleoplasm.

Each result records the input and mask hashes, exact parameters, threshold bin,
detection range, selection rule, fixed runtime/bridge/Java hashes and outcome.
Otsu is exploratory, and neither threshold method establishes biological GFP
positivity without experimental controls. The adapter never loads a StarDist
model for this operation, downloads a model, or evaluates submitted code.
