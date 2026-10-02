# Public real-image validation: BBBC039v1

This benchmark uses real, published microscopy images and manual instance
annotations from [BBBC039v1](https://bbbc.broadinstitute.org/BBBC039), released
under **CC0** by the Broad Bioimage Benchmark Collection. The specimens are U2OS
cells imaged in a chemical screen. The provided channel is **DNA stained with
Hoechst**; it is not an acquired NCL or GFP channel.

## Fixed selection and reproducibility

Five filenames were selected as the lexicographically first five entries of the
official `metadata/test.txt`, before inference. No fields were replaced after
seeing results and no probability, NMS or normalization threshold was tuned.
The unchanged source TIFFs and mask PNGs, their archive/member SHA-256 values,
license and source are recorded in
[the public fixture manifest](../fixtures/public/bbbc039/manifest.json).

```bash
uv run python scripts/public_bbbc039.py --verify
# Reacquire exact public inputs if missing:
uv run python scripts/public_bbbc039.py --download
# Explicit real CPU engine, output outside the checkout:
uv run python scripts/public_bbbc039.py --evaluate /private/bbbc039 --fiji /opt/fiji
```

Images remain 520x696, uint16, at original resolution. Ground truth follows the
dataset author's first-channel/equal-colour connected-component decoding.
Matching maximizes one-to-one instance matches at IoU >=0.5, with IoU as the
tie-breaker. All annotated/predicted nuclei count, including edge instances;
failed fields cannot silently disappear.

The final evaluation used actual Fiji StarDist 2D Versatile fluorescent nuclei,
percentiles 1–99.8, probability 0.5, NMS 0.3, headless CPU execution, and four tiles
per image under the fixed memory policy. NCL zeros passed into the engine are
only an internal placeholder for this **nuclei-only** test and are never exported
as acquired NCL, GFP or nucleolar measurements.

## Observed results (2026-10-02)

| Official test field | Annotated | Predicted | TP | FP | FN | F1 |
|---|---:|---:|---:|---:|---:|---:|
| A09_s1 | 156 | 153 | 149 | 4 | 7 | 0.9644 |
| A12_s7 | 69 | 31 | 29 | 2 | 40 | 0.5800 |
| A16_s2 | 93 | 87 | 87 | 0 | 6 | 0.9667 |
| A22_s8 | 95 | 93 | 90 | 3 | 5 | 0.9574 |
| B02_s9 | 66 | 65 | 63 | 2 | 3 | 0.9618 |
| Pooled | 479 | 429 | 418 | 11 | 61 | **0.9207** |

Mean field F1 is **0.8861**. The A12 failure remains in the result and demonstrates
that manual review/correction is necessary. Pooled F1 above 0.90 does not establish
that every field meets the product's provisional target.
[Machine-readable results](../fixtures/public/bbbc039/benchmark.json) retain input,
model and bridge hashes and the field-by-field values.

During engineering validation, memory-based tiling was added for large images.
The same frozen subset was rerun with the final policy. Compared with the earlier
one-tile run, A22 gained one false-positive object; the table reports the final
run, not the better earlier aggregate. This was a runtime-memory change, not a
parameter search for accuracy.

## Limits and demo meaning

The dataset documentation states that a fraction of BBBC039 overlaps DSB2018.
The selected pretrained model was trained on DSB2018, so these numbers are
**not an independently held-out estimate of generalization**. They verify that
real input, the actual engine and a documented comparison procedure run together.

The demo uses the first predetermined field, A09, with its actual detected
outlines and raw 16-bit DNA intensity measurements. Preview contrast is display
only. Unsupported NCL/GFP operations must be visibly unavailable on this dataset.

This benchmark does not validate nucleolar segmentation, NCL partition ratios,
GFP gating, biological conclusions, or the user's private experiment. Those need
appropriate multichannel data and their own references. Synthetic arrays remain
useful for exact arithmetic edge-case tests; they are not presented as real
published microscopy.
