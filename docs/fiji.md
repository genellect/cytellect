# Fixed Fiji image engine

Cytellect executes the actual Fiji StarDist 2D implementation and its embedded
**Versatile (fluorescent nuclei)** model. There is no silent watershed, Python
StarDist, synthetic-truth, or connected-component replacement for nuclear detection.
A missing/mismatched engine fails the field explicitly.

## Install once, at setup/build time

Requirements: x86-64 Linux or Windows, Python 3.12, outbound HTTPS during setup,
and enough disk space for the Fiji/JDK archive plus extraction. The destination
must be outside the repository and must not already exist.

```bash
python scripts/fiji_setup.py /opt/fiji --platform linux-x64
export CYTELLECT_FIJI_EXECUTABLE=/opt/fiji
uv run pytest -m fiji -q
```

On Windows choose an absolute directory outside the checkout, use
`--platform windows-x64`, and set the environment variable to that directory.
An existing Fiji launcher path is also accepted; its parent must contain the
locked jars/plugins and bundled JDK. User installations are never modified.

The installer downloads the dated official Fiji archive **20260929-1417**, verifies
its published SHA-256, then verifies each additional plugin and the embedded model.
It records the installed jar/JDK inventory in `cytellect-runtime.json`. The
authoritative URLs, hashes, model member and licenses are in
[the runtime lock](../engines/fiji/runtime.lock.json). Runtime workers never invoke
the installer, Fiji updater, model URL input or an external download.

## CPU/headless compatibility and privacy

The fixed Java bridge calls Fiji's ImageJ services directly. It uses Java 21,
`java.awt.headless=true`, explicit legacy preinitialization and
`--add-opens=java.base/java.lang=ALL-UNNAMED`. It needs no display/Xvfb for the
tested operations. CPU TensorFlow 1.15 comes from its pinned JNI jar; CUDA is
disabled. The source bridge is compiled from repository-controlled Java files in
the attempt directory. Submitted macros/code/URLs are not accepted.

**Compatibility pin:** StarDist 0.3.0 / CSBDeep 0.6.0 use TensorFlow 1.15 generated
protobuf classes. Fiji's protobuf 4.28.2 caused `NoSuchMethodError` during real
model loading. The adapter explicitly puts the pinned **protobuf-java 3.25.8**
ahead of the distribution classpath. Removing this pin requires a real model
inference regression test.

ImageJ preferences are process-local memory. Temporary images, extracted models,
Java temp files and masks stay inside the private attempt directory. The adapter
suppresses third-party stdout/stderr because those streams include paths. Only
fixed error codes are exposed. The worker must enforce process-tree cancellation,
memory limits, retention cleanup, and network isolation. Java heap is bounded at
2 GiB; the surrounding worker/container limit must also account for native TF memory.

## Scientific behavior

- StarDist normalizes detection copies at configured percentiles and applies
  probability/NMS thresholds. Defaults 1–99.8, 0.5, 0.3 are starting values.
  Tile count is the smallest power of four with nominal tile area at most
  512x512 pixels; StarDist handles overlap. The exact count is saved in provenance.
- Native masks use original coordinates. Detection preprocessing never changes
  measurement pixels.
- Each nucleus gets a separate NCL histogram of **256 equal-width bins between
  its minimum and maximum**, then ImageJ `AutoThresholder.Otsu`; candidate
  membership is the histogram bin strictly above its threshold. This bin rule
  is part of recipe 1.0.0 and is not claimed numerically identical to every
  scikit-image integer-histogram implementation.
- Optional smoothing uses ImageJ GaussianBlur (sigma in pixels, accuracy 0.01).
  Optional touching-object separation uses ImageJ EDM watershed.
  MorphoLibJ labels the remaining 8-connected objects; minimum area applies
  independently within each parent nucleus.
- DAPI-low is an explicit auxiliary method: linear percentile within the nucleus,
  with pixels strictly below the percentile. Uniform signal is indeterminate.
- No-candidate, indeterminate and field failure are distinct. There is no native
  whole-nucleus/top-fraction fallback.
- Supplying edited nuclear labels preserves them exactly and regenerates
  nucleolar candidates. The API must require their review before statistics.
- The legacy recipe has a separate documented downsampling/threshold pipeline;
  its provenance must include the detection-to-original coordinate transform.

## Evidence and remaining validation

On 2026-10-02, a Windows x64 runtime with Java 21.0.7 and the pinned plugins ran
real headless CPU inference on the public synthetic generator: **9 nuclei and
18 nucleolar candidates**, unchanged source arrays and valid parent containment.
The adapter invocation took approximately 24 seconds on that local machine; this
is a single smoke measurement, not a performance guarantee.

Marked tests also exercise edited nuclei, uniform/no-candidate behavior,
DAPI-low/smoothing/watershed/size filters, and actual ImageJ ROI decoding of
pixel-run rectangles with holes, edges and large object IDs. Run the tests to
record the current result; absent runtime means skipped, never passed.

The clean Windows archive was independently downloaded, SHA-256 verified, installed
into a new runtime directory, and passed all 9 engine/BBBC039 tests in 96.45 seconds
on 2026-10-02. This includes the real CPU engine and exact ImageJ ROI exchange.
No original user Fiji installation was modified.

The GFP-only recipe runs the same DNA detector and explicitly disables nucleoli.
It never transports or measures a fabricated NCL channel.

A synthetic count is not experimental F1 or scientific validation. Private
representative-image comparison and researcher PoC remain separate acceptance
gates. Linux CPU execution is independently evidenced at commit
`f172afbf4396a8a4fb6be839435af375fc9f03bf`: the
[GitHub Linux Fiji/browser job](https://github.com/genellect/cytellect/actions/runs/37021236116/job/110884557308)
installed the hash-checked runtime and passed **6 actual Fiji tests**, with no Fiji
skips, in 42.59 seconds. Its browser flow passed 3 tests; the public-build-without-API
check was intentionally skipped because this job configures an API. The overall
workflow at that commit failed a separate Python type-check step. This evidence
is distinct from a production-host or Docker-runtime smoke. The CI now also
requires building the worker container and running actual Fiji as UID10001 with
a read-only root, private temporary volume, only loopback networking and a denied
outbound connection; that new container check awaits its own recorded result.
