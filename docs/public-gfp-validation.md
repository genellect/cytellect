# Published GFP images: quantitative reference validation

On 2026-10-02, Cytellect and actual ImageJ agreed on GFP area, raw mean, midpoint median and reference-offset median for all **817 nuclear ROIs across three fixed public fields**. Floating arithmetic differences in integrated and corrected signals were below 4e-12 intensity-pixels. This validates the fixed-mask measurement implementation on these acquired images; it does not validate the detector's biological accuracy or reproduce the paper's treatment effects.

## Source, identity and permitted use

[BBBC013v1](https://bbbc.broadinstitute.org/BBBC013) provides U2OS images of the FKHR-EGFP fusion and the DNA stain DRAQ. The collection links published analyses by [Carpenter et al., 2006](https://doi.org/10.1186/gb-2006-7-10-r100). Images are by **Ilya Ravkin**, distributed under [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/); cite the [BBBC collection](https://doi.org/10.1038/nmeth.2083). Cytellect's TIFF containers preserve the exact pixel samples of the official 8-bit BMP exports; they contain no added NCL channel. The TIFF conversion is the stated modification.

The historical API role `dapi` here means the nuclear-image input, but the actual stain is **DRAQ**, never DAPI. Channel 1 is FKHR-EGFP and channel 2 is DNA. Fixed wells A01, A06 and A12 were selected before Cytellect measurement; no field or object was removed based on agreement, signal level or significance. There is one field per well, and no nuclear ground-truth mask. These images must not be described as independent biological replicates without additional study-design evidence.

**These quantitative checks use published 8-bit exports, not verified camera-native FRM intensities.** Both official BMP and native FRM archives were acquired with recorded SHA-256. The pinned Bio-Formats `InCell3000Reader` reports only one plane from the two-plane FRM files. Its decoded first plane spatially corresponds to DNA, not GFP. A custom exploratory decoding is not accepted as a quantitative raw-GFP reference. Native conversion remains an explicitly open format-validation task. See the [upstream reader source](https://github.com/ome/bioformats/blob/develop/components/formats-gpl/src/loci/formats/in/InCell3000Reader.java).

BBBC014 was considered but excluded from this GFP validation: FITC antibody fluorescence must not be relabelled as an acquired GFP fusion channel.

## Independent reference and exact comparison

1. The pinned Fiji/StarDist CPU runtime detects nuclei from original-resolution DRAQ samples using the unchanged starting settings (1–99.8 percentiles, probability 0.5, NMS 0.3, four tiles). `gfp-nuclear-2d` disables nucleolar detection and never writes a placeholder NCL image.
2. The canonical nuclear masks are passed separately to Cytellect and the fixed Java reference bridge. Source pixel arrays remain unchanged. Each bridge mask becomes an actual ImageJ ROI through `ThresholdToSelection`, preserving all occupied pixels.
3. ImageJ `ImagePlus.getStatistics` computes pixel count, mean and histogram median. Integrated signal is its mean multiplied by its measured pixel count. This bridge never calls Cytellect/NumPy measurement code.
4. Cytellect defines even-sample medians as the midpoint of the two central sorted values. ImageJ's histogram convention differs for 59 nuclear ROIs in these fields. The bridge therefore also sorts samples obtained through the ImageJ ROI independently in Java and calculates the specified midpoint; all 817 midpoint medians agree exactly. Both median definitions are retained in the report instead of hiding the difference.
5. To exercise background arithmetic without signal-based tuning, select the first 15x15 block in row-major spatial order that does not overlap a detected nucleus. All three fields select x=0,y=0. This **reference offset ROI is not a biologically certified cell-free background**: cytoplasmic GFP may occur outside nuclear masks. A researcher must confirm real background regions before scientific use. Its odd 225-pixel count avoids median-convention ambiguity.
6. Compare raw and signed corrected values against the independent reference. A06 includes **28 negative corrected nuclear means**, all retained. No clipping or favorable-object filtering occurs.

| Fixed field | Nuclear ROIs | Reference offset median | Max absolute mean error | Max absolute integral error | Negative corrected means |
|---|---:|---:|---:|---:|---:|
| A01 | 350 | 2 | 0 | 1.82e-12 | 0 |
| A06 | 242 | 6 | 0 | 3.64e-12 | 28 |
| A12 | 225 | 1 | 0 | 1.82e-12 | 0 |

Corrected-mean error is at most 7.11e-15. Pixel count, raw midpoint median and offset median agree exactly. Tolerances fixed in the executable validator are 1e-10 for mean/count/median and 1e-8 for integrated signal. Units are pixels and exported-image intensity units; no micrometre or concentration calibration is assumed.

The committed [machine-readable benchmark](../fixtures/public/bbbc013/benchmark.json) contains every compared object, reference values, preserved median differences, fixed conditions, channel-source hashes, model/runtime/bridge hashes and field-level errors. The independent-reference Java source fingerprint normalizes line endings to LF for Windows/Linux portability; image/archive hashes remain byte-exact. The [manifest](../fixtures/public/bbbc013/manifest.json) identifies source archive/member hashes, original pixel hashes, exact channel stains and attribution. Automatic detection contours are not manual ground truth.

## Reproduce and test

```bash
uv run python scripts/public_bbbc013.py --verify
uv run python scripts/public_bbbc013.py --download
uv run python scripts/public_bbbc013.py --evaluate /private/public-gfp-validation --fiji /opt/fiji
CYTELLECT_FIJI_EXECUTABLE=/opt/fiji uv run pytest tests/test_public_bbbc013.py
```

The six TIFF fixtures are publicly licensed data, never user research uploads. Downloads happen only through the explicit preparation command. The application worker remains offline. Absent Fiji causes the actual-reference test to skip with an explicit unexecuted message; fixture checks alone never count as independent ImageJ validation.

## What remains unproven

This agreement does not establish native FRM fidelity, nuclear segmentation F1 on BBBC013, NCL/nucleolar performance, cell-boundary detection, between-treatment effects, dose-response replication, statistical independence or usefulness to researchers. Separate NCL and annotated-nuclear datasets cover their own scopes. Private representative-image validation and researcher PoC remain necessary. Full precision is preserved in CSV/JSON; display rounding is not a second measurement implementation.
