# Fixed Cellpose execution adapter

Protocol `cellpose-sam/4.0.0` uses official `cpsam_v2` weights. `runtime.lock.json`
records the immutable model revision, SHA-256, size, model/code licenses, and
runner/package-lock hashes. `requirements.lock` pins the complete Python 3.12
CPU environment with distribution hashes; it is separate from the API runtime.

Provision at build/install time:

```sh
python scripts/cellpose_setup.py /opt/cellpose-runtime --model-cache /opt/cellpose-models
```

The provisioning Python must be 3.12 and uv 0.12.2 must already be installed.
Model storage and the isolated environment are outside the checkout. Existing
matching weights are reused, and incorrect cached files are rejected. No image
job may invoke this script. The Docker worker includes a separate cached stage;
the API image does not include Torch or the weights.

Runtime configuration:

- `CYTELLECT_CELLPOSE_PYTHON`: isolated Python 3.12 executable.
- `CYTELLECT_CELLPOSE_MODEL_DIR`: directory containing the fixed `cpsam_v2` file.
- `CYTELLECT_CELLPOSE_ASSETS`: directory containing this adapter and manifest.

The runner verifies package versions and model bytes before deserialization.
It uses an explicit local model path and prohibits Cellpose fallback downloads
and socket connections. The scientific worker also retains its offline Docker
network boundary. This initial CPU profile cannot use CUDA; an explicit CUDA
request reports `cellpose_gpu_unavailable`, and `auto` uses the available CPU.
The model is loaded once per isolated image-job process. No persistent model
pool is claimed in this version.

The Docker provisioning stage copies only `provisioning.lock.json`, the pinned
dependency lock and the setup helper. The job runner, runtime manifest and source
assets enter the final worker layer separately. A runner or protocol update alone
therefore leaves the dependency/model stage unchanged. The public provisioning
manifest repeats the exact fixed package/model information without a runner hash;
the final runner checks its full runtime manifest, runner and dependency-lock
hashes before loading the model. Ordinary Windows setup retains that runner check.

## Windows optional installation

The setup ZIP carries the adapter, model manifest, dependency lock, license and
explicit Cellpose provisioning scripts. It does not carry model weights or add
Torch to Cytellect's normal Python 3.14 environment. First complete the ordinary
Cytellect installation, then use an already installed, signed official Python
3.12 interpreter:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<extracted release>/scripts/cellpose_setup.ps1" -Python312 "<official Python 3.12>/python.exe"
```

`-InstallRoot` selects the same Cytellect installation root when it differs from
`%LOCALAPPDATA%/Cytellect`. This explicit operation downloads packages and the
model. It creates a standard-library Python 3.12 venv in
`runtimes/cellpose-<requirements-hash>` and reuses weights in
`models/cellpose-<model-hash>`. A changed application version alone does not create
another model copy. Successful import checks precede the atomic, nonsecret
`settings/cellpose.json` configuration (`cytellect-cellpose-local/1`). Restart the
app to load it; explicit runtime environment variables take precedence.

Version-specific adapter assets are not saved in that shared configuration.
When the installed analysis wheel is outside the extracted app, the launcher’s
app working directory supplies `engines/cellpose` only after its release-manifest
hashes and the fixed runner/dependency-lock hashes pass verification.

The helper checks the source-release hashes, the already installed fixed uv ZIP
and binary, and signed Python launchers. Missing Python 3.12 is an unmet
installation prerequisite with an official Windows download link, not an
installed feature. Windows application-control rejection remains a failure;
no OS policy is weakened. This optional Windows path requires separately
recorded installed-bundle acceptance before a public Windows release.

Input is one explicitly selected native unsigned 8/16-bit plane, with two zero
channels. Percentile normalization changes only a detection copy. Diameter,
flow threshold, cell-probability threshold, minimum area, iterations and maximum
size fraction are saved. The default maximum-size fraction is 1.0, avoiding the
upstream 0.4 cap on large objects. No upper object area or trial-image exclusion
coordinate is imposed.

Protocol `4.0.0` (`cellpose-sam`) preserves its unprocessed detection input.
Protocol `4.1.0` (`cellpose-sam-ncl`) first smooths an original-coordinate float32
detection copy with Gaussian sigma 0.9 px, estimates local background with grey
opening using a circular disk of radius 10 px, then applies
`maximum(smoothed - background, 0)`. Both operations use SciPy's reflect boundary
mode. The pinned Cellpose `transforms.normalize_img(normalize=True)` with 1st/99th
percentiles follows this transform, preserving its float32 arithmetic, 1e-3 cutoff
and official percentile sampling for large images. Protocol 4.0 retains its
original manual normalization unchanged.
Preprocessing parameters and normalization source are recorded separately from
the immutable original measurement pixels. No per-nucleus crop, image-size unit
conversion or nuclear zero-padding is introduced; adopted nucleus binding still
happens after inference.

Output is an original-coordinate `uint32` mask. Nuclear binding accepts whole
objects contained inside one adopted StarDist nucleus. Candidates crossing or
touching its boundary, spanning nuclei, or outside all nuclei remain in a raw
review mask with reasons; they are not clipped into completed nucleoli. Returned
parents with such ambiguous candidates retain `review_required`. Biological
applicability requires separate real-image review; runtime/membership tests do
not establish nucleolar identity or segmentation quality.


### Parent-conditioned NCL Cellpose protocol 4.2.0

New explicit NCL Cellpose selections use `cellpose-sam-ncl-parent/4.2.0`.
The unchanged original plane is Gaussian-smoothed (0.9 original px) before any
parent restriction. For each adopted StarDist nucleus, subtract its 75th
intensity percentile, keep positive signal only within that parent, and normalize
a padded (32 px) crop using the pinned official Cellpose 1/99 percentile transform.
An explicit diameter overrides the default, which is 0.25 times that adopted
nucleus's equivalent diameter. This is an empirical, recorded model scale prior;
it is neither an image-dimension conversion nor a claim that nucleolar size is
biologically fixed. Display colour, LUT and zoom cannot change these inputs.

Original-minus-smoothed residuals in the lower nuclear intensity range provide
a robust noise estimate (1.4826 MAD, floor half an input intensity code unit).
Parent signal excess and individual candidate original-pixel enrichment must
meet the recorded minimum signal/noise ratio (5). Local background is the mean
of available pixels in an 8 px annulus inside the same parent and outside model
candidates. Insufficient parent signal is indeterminate, not zero nucleoli.
Disconnected model components receive distinct IDs and must each satisfy
minimum area. Cross-parent and boundary-touching objects are rejected whole,
never clipped. No nucleus-size, dark-hole or top-percentile mask replaces an
absent candidate.

Compartment protocol 1.1.0 retains valid individual candidates when another
object requires boundary review. That parent's nucleoplasm/complement remains
missing; it is not treated as a complete nucleolar union for ratios. Researcher
adoption resolves the candidate set explicitly. Complete eligible parents use
the union of adopted children and parent-minus-union, with original-pixel
measurements. Per-parent crop, background, diameter, normalization and signal
quality are retained alongside original and parent-mask hashes.

Protocols 3.0.0, 4.0.0 and 4.1.0 keep their historical semantics and replay.
Existing masks, including manual edits, are not silently upgraded. Private real
image validation is outside Git/CI; runtime/contract checks are not a claim of
general biological segmentation accuracy. Cellpose-SAM is not a nucleolus-specific
classifier, and NCL redistribution can change marker-defined candidates.


Protocol 4.2.1 preserves the 4.2.0 parent-conditioned inference settings and adds
whole-instance nuclear rejection after inference. A candidate covering more
than `maximum_nuclear_coverage` (default 0.5) of an adopted StarDist nucleus,
with at least 0.9 parent purity, is removed as a nuclear-scale candidate. The
original raw candidate artifact and rejection measurements are retained.
Nuclear pixels are never subtracted from nucleolar masks. A parent containing
only rejected nuclear-scale candidates is indeterminate, not a measured zero.
Stored 4.2.0 recipes skip this filter and retain their original meaning.
