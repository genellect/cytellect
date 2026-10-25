# Local resource benchmark

## WP7 public-image remeasurement (2026-10-25, current policy)

The owner's revised instruction supersedes synthetic-image capacity evidence.
The earlier synthetic records below are retained only as history: **they are not
accepted validation or a basis for limits or a recommended batch size**.
No detection algorithm, thresholds or model weights are tuned in this work.

Preregistered workload: the first already-registered DS6a Untreated Rep1 field,
`40x_1.4_Rep1_Untreated_20211201_01_01.tif`, SHA-256
`5b32bb25082174021ea25ecbc79fa0bd3daa2642e682ce0e828888def8f58f5d`.
Registration and source/channel evidence are in PR #99's
`fixtures/public/group-comparison/ds6a-manifest.json` and metadata samples.
Schmidt, Rohatgi and Brandman, DS6a, https://zenodo.org/records/6643470,
CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).

- Source: four 2304-square uint16 planes. Order: unresolved FITC identity,
  NPM1-mTagRFP, 5-EU, Hoechst. The unresolved FITC channel is labelled as such,
  never treated as GFP/NCL/CellMask. Only Hoechst defines the nuclear regions.
- 2048 square: top-left crop. 4096 square: repeat the source 2 by 2 and take the
  top-left 4096 square. Pixel values are copied exactly, without interpolation,
  brightness changes, padding or generated cell shapes. The source TIFF is untouched.
- Each size is measured with 1 and 3 sequential copies of the same field. These
  are repeated resource workloads, never independent fields/replicates for biology.
  Seams may influence detection; no accuracy or biological claims follow.
- Selection is fixed before inference, with no replacement after failures.
  Record failures and existing admission limits without bypassing them.
- Common analysis code is loaded from fixed review base `31b3c22d` (or its test-only
  descendant); record the exact commit in each receipt. Benchmark scripts live
  on this WP7 branch; recipe remains region-2d 1.1.0 / raw_intensity 1.1.0.
- Cellpose: first registered CC0 BBBC039 field, fixed top-left 256-square Hoechst
  crop, default locked local CPU engine. No tuning or selection by output.

The 100-field ceiling and 2 GiB upload quota **remain unchanged**. Generic
`RegionFieldInput.channels` already accepts four channels; the lead owns the
I07/I09 documentation alignment. Resource observations only inform proposals.
Input shape, actual detection shape (including the existing 1643-square resize),
and original-coordinate measurements must be reported separately.

Results: pending remeasurement; no new success is claimed at this plan commit.

## Historical WP7 synthetic benchmark (superseded; not validation)

The approved group-comparison specification is `a78a110b613684c3a352f99b625d20f94f488918`.
The measurement base is main `11eb24419f2d8af5a3eec706e23985a038cc7f1d`.
This WP owns this document and a dedicated resource-measurement script only;
it does not change admission limits, contracts, recipes or shared analysis.

Before measurements, the workload is fixed to deterministic synthetic capacity
inputs with four explicitly synthetic channels, uint16, 2048 and 4096 square
pixels, and sequential field batches. Synthetic inputs are only for resource
observations, not biological or detection-accuracy validation. Actual registration
rejections and engine admission failures must be reported without bypassing guards.
The controller will distinguish registration, detection and measurement timings,
sample child-process-tree RSS, impose a timeout and preserve failure records.
All generated images, environments and runtime results remain outside the checkout.
Pinned Fiji and Cellpose provisioning and execution are checked separately.
An input or runtime that fails is not evidence for a larger supported limit.

### Observed results

Windows 11, Python 3.12.13, 12 physical / 16 logical CPUs, 31.73 GiB RAM.
Each row is one fresh child process on the same interactive host, not repeated
trials, a cold machine, or an isolated performance laboratory. No inference jobs
were run concurrently. Documentation/tool activity continued on the host.

| Square side / fields / channels | Registration sum (s) | Detection sum (s) | Measurement sum (s) | Total wall (s) | Sampled peak summed RSS (GiB) | Outcome |
|---|---:|---:|---:|---:|---:|---|
| 2048 / 1 / 4 | 0.625 | 63.366 | 2.074 | 74.143 | 1.823 | measured, 256 rows |
| 2048 / 3 / 4 | 1.635 | 131.201 | 6.389 | 148.481 | 1.888 | all measured, 768 rows |
| 4096 / 1 / 4 | 1.866 | 50.308 | 29.699 | 91.173 | 1.934 | measured, 1024 rows |
| 4096 / 3 / 4 | 10.279 | 138.294 | 103.778 | 269.646 | 2.113 | all measured, 3072 rows |

Rows are measurement rows across four channels, **not counts of biological
cells**. The scenes are deterministic synthetic disks and foci, not real DAPI,
GFP, NCL or CellMask images. Source array hashes matched stored arrays after every
successful run. All four runs returned no field failures, with all requested fields
in the `measured` outcome. Fresh local stores were used, never an existing user store.

The script uses the real local-session/workspace/upload/enqueue HTTP handlers
through FastAPI TestClient, then directly calls the common worker
`run_region_analysis`. It does not time a browser, network transport, installer,
supervisor scheduling, nucleolar/cell-boundary detection, or statistics. Timing
wrappers forward to the original common scientific functions without changing
their inputs or numerical results. The selected recipe is region-2d 1.1.0,
`stardist_nuclear`; measurement is raw_intensity 1.1.0 on all four channels.

**Both input sizes were detected at 1643×1643**, through the existing nuclear
detection capacity resize (2,700,000 pixel ceiling). Masks were returned in
original coordinates and measurement used original-resolution arrays. These
results do not demonstrate full-resolution 4096 detection or the ability to
resolve small nucleoli. Sixteen StarDist tiles were used in every field. The
first field can include Java adapter compilation; detection timings are not
steady-state throughput estimates.

The controller samples summed RSS for the Python child and descendants including
Fiji, with a 50 ms sleep plus sampling overhead. Samples: 773, 1529, 964, 2805 in
table order. RSS access gaps: 0, 0, 0, 1. Shared pages may be double-counted and
short spikes missed. This is an observed sampled peak, not a guaranteed memory
maximum. Total time includes startup/generation/verification; stage times do not.
Each case is bounded at 600 seconds and stops below 1 GiB available host RAM.

Fiji provisioning succeeded using `scripts/fiji_setup.py` and the locked Windows
archive stamp 20260929-1417 (archive SHA-256
`8fff3fa8f202743bfd301066eb1e3611281e899e246fe9bef8fd0a30738260f0`).
The detector model SHA-256 was
`b0eb820e455db0ec8326d3b6f456a1b2d4aff8d7dd818a71481f8041958309e3`.
The benchmark script SHA-256 for the four successful runs was
`977eebe2dd90cce8d8f2a8cb96af419540dbc14366466403cff1447b57aeb39a`.

An initial harness run failed before detection because it created the output
directory that the worker itself creates. The harness was corrected to let the
worker create it. Its 72.857 seconds / 0.356 GiB is a failed harness run, excluded
from the successful table; no engine or product fix was needed.

### Proposed limits for WP0 (owner/lead decision)

1. Align I07/I09 wording to **1–4 channels per field**. At the measured main SHA,
   `RegionFieldInput` and `RegionImageInfo` already allow four channels
   in `packages/analysis/src/cytellect_analysis/region_contracts.py`; the draft's
   claim that the generic contract allows only three is stale. Check the other
   upload paths, generated contracts and UI separately before changing shared files.
2. Do not raise the existing 100-field administrative ceiling or the 2 GiB
   workspace upload quota on this evidence. **Only batches of 1 and 3 fields**
   were measured. Keep per-field 256 MiB upload guards. State that the actual
   admitted field count also depends on byte quota; 100 uncompressed 4096²×4×uint16
   fields alone would be 12.5 GiB before headers, already above the quota.
   Stored decoded arrays and analysis results consume additional disk beyond
   uploaded bytes, so the quota is not a disk-space reservation.
3. The measured CPU envelope is up to 4096² input / four channels / three sequential
   fields for this **nuclear-only recipe**, with the existing detection resize.
   This is a documented tested envelope, not a reason to silently reduce existing
   workspace field limits or promise every 4096 workflow. An initial comparison
   batch recommendation of three fields is supportable; broader supported limits
   require 5/10/100-field runs, dense real-image workloads, simultaneous imports,
   and other region recipes on the fixed integrated WP0 commit.
4. Explain input resolution and detection resolution separately in the owning UI
   and contract work. A maximum input-side setting alone is not a scientific
   resolution guarantee. No limit, recipe, shared contract or statistical code is
   changed in WP7.

### Reproduction

Run from the WP7 checkout, with each output directory new and outside the checkout:

```powershell
uv sync --locked --dev
uv run python scripts/fiji_setup.py ../runtime-fiji
uv run python scripts/benchmark_group_comparison.py --output ../benchmark-runs/2048-1-r2 --fiji ../runtime-fiji --side 2048 --fields 1
uv run python scripts/benchmark_group_comparison.py --output ../benchmark-runs/2048-3 --fiji ../runtime-fiji --side 2048 --fields 3
uv run python scripts/benchmark_group_comparison.py --output ../benchmark-runs/4096-1 --fiji ../runtime-fiji --side 4096 --fields 1
uv run python scripts/benchmark_group_comparison.py --output ../benchmark-runs/4096-3 --fiji ../runtime-fiji --side 4096 --fields 3
```

Each case writes a host record, receipt, result and local child log; raw paths in
local logs are not published. Receipt SHA-256 values in table order:

```text
abdf26d410f7f6da351f2b0b95c8831d30270f0444a74f3cd9da3e4f94e36efa
4033e89c960fb7041a9896cafe583f3bf150200a98db19d874e7c9faf7c7c6c9
66dade451bdf23ee5c620d941c670085c59457579bdcc0c7566d5bf048694630
77b9b74dace837f9f07d0ddbd36e738d5ee15965f0dc05995a326252fddd03e0
```

### Cellpose execution probe

The fixed isolated runtime was provisioned with `scripts/cellpose_setup.py`,
Python 3.12, cellpose 4.2.1.1, torch 2.8.0+cpu and model cpsam_v2. Setup verified
the model size (1,233,586,851 bytes) and locked SHA-256. The bounded CPU smoke
script uses a 128² synthetic image, a fresh child and a 300-second guard. It
clears remote-backend settings in that child and uses no paid service.
The execution result is recorded below separately from successful installation.

Execution succeeded: 102.441 s wall, 100.313 s in the common detector call,
3.066 GiB sampled peak summed RSS, uint32 labels with the original 128×128 shape,
and unchanged input pixels. One RSS access gap was recorded. This is one CPU
smoke run, not a 2048/4096 Cellpose benchmark or an accuracy result. Model SHA-256:
`0f1cc3f7ecdd8a037a57c6c48d9d8921391be4cbce3fa9f13c3e3a2e1253c667`.

```powershell
$py = (uv python find 3.12).Trim()
uv run python scripts/cellpose_setup.py ../runtime-cellpose --model-cache ../cellpose-models --python $py
uv run python scripts/benchmark_cellpose_smoke.py --output ../benchmark-runs/cellpose-128 --python ../runtime-cellpose/Scripts/python.exe --models ../cellpose-models
```

Provisioning used `UV_NO_CACHE=1` to limit disk use. Runtime/model downloads took
place during setup only; the smoke inference used the fixed local files.
Full-size Cellpose, combined nuclear/nucleolar recipes, 5+ field batches, browser
operation, installer acceptance and the integrated WP0 build remain unverified.

The earlier observations below are retained as historical evidence and are not
new WP7 measurements.

## Historical two/three-channel benchmark

Status: the representative public image completed; the production-profile maximum-size case failed. An explicitly experimental 4 GiB Java-heap run also failed. This is a capacity observation, not cloud sizing certification or a detection-accuracy validation.

The executable script is scripts/benchmark_resources.py. All source images, arrays, transient Fiji files and reports stay outside the repository. It accepts the registered 4DN source by exact SHA-256 and a deterministic capacity generator; it does not accept arbitrary image URLs or private datasets.

## Measurement method

Each case runs in a fresh Python child. The controller samples that child's RSS plus all descendants (including Java/Fiji) with a 50 ms sleep target between samples; process discovery and file reads add overhead. It records peak summed RSS, phases, wall-clock time, process count, sampling failures, source pixel hashes, dimensions, recipe, runtime/bridge/model identifiers, tile count when returned, and host CPU/OS/RAM. The controller itself is excluded. Shared pages can be counted more than once; spikes shorter than the sampling interval can be missed.

Each case has a 300-second wall-clock limit, including process startup, loading/generation, Java compilation, detection and Python compartment measurement. A host-available-memory guard stops the benchmark below 1 GiB to preserve interactive use; any such stop is recorded as a failed capacity observation. There is no container/cgroup memory limit in this local run. Runtime/measurement phases are separate; no private upload/API workload is benchmarked.

The expensive capacity observations below predate the standard-2g automatic-detection admission guard. The legacy full-frame path rejects detection images above2048px on either side or2,700,000pixels before launching Fiji. The nuclear-only recipe in the WP7 section first creates an admitted smaller detection image; its successful4096input observation must not be confused with this historical full-frame failure. No benchmark bypass is provided.

The pinned Java adapter currently requests -Xmx2g. Tile count grows through 1,4,16,... until nominal tile area is at most512². Tiling does not itself prove that full-frame prediction/output arrays fit in that heap. Default StarDist parameters and original-resolution measurement are retained.

## Measured observations

Local host: Windows11/AMD64, Python3.12.14, Java21.0.7, Intel64 Family6 Model186 Stepping2,12 physical/16 logical CPUs,31.73 GiB total RAM. These are fresh child processes, not a cold machine or an isolated cloud instance.

| Input/profile | Status | Total wall time | Sampled peak summed RSS | Tiles |
|---|---|---:|---:|---:|
| Public NCL1536×1739,2×uint16; production-Xmx2g | Completed:100 nuclei,182 candidates |52.620s|1.716GiB|16|
| Capacity4096×4096,3×uint16; production-Xmx2g | Failed: Java heap exhaustion |43.789s|2.570GiB before failure|64 requested|
| Capacity4096×4096,3×uint16; experimental-Xmx4g | Failed: Java heap exhaustion (confirmed in separate diagnostic replay) |69.038s|4.607GiB before failure|64 requested|

The public case spent43.742s in compilation/detection and6.560s in Python compartment measurement; the remainder covers startup/loading/reporting. RSS sampling had628 observations and no access-denied gaps; average spacing including overhead was about84ms. Peak RSS during the Python measurement phase was0.169GiB.

Separate diagnostic replays of both the production2GiB and experimental4GiB synthetic Java commands captured java.lang.OutOfMemoryError: Java heap space at net.imagej.tensorflow.Tensors.imgFloat:170, through DatasetTensorFlowConverter.tensorToDataset and TensorFlowNetwork.execute, while converting the TensorFlow output tensor to an ImageJ Dataset. These replays establish the error class; the table retains the original benchmark timings and sampled peaks. A later null-prediction exception is secondary. The measured2.570GiB is a failed-run observation, not proof that2.570GiB can finish the workload. The2GiB Java cap is distinct from the server's total RAM.

The first public attempt also uncovered an input compatibility error: valid single-file OME self-UUID references were rejected. That error was fixed with tests that continue to reject references to other UUIDs and disable multifile reads. Its2.1s startup failure is not included as a successful resource observation.

## Cases

- Published 4DNFI7FAWT6C: two uint16 channels,1536×1739. DAPI=index1, NCL=index0; the portal/embedded-metadata discrepancy remains documented in public-nucleolar-validation.md. GFP is absent. Source-file SHA-256: d703dfedcf3894b781d0dbf2659f7ef81b60feea8660c39844ea14e150caa775.
- Capacity workload:4096×4096, three uint16 channels, deterministic seed20261003,256 bright disks with foci. It exercises memory/runtime at the accepted size limit and is not a biological simulation or accuracy benchmark.

The arithmetic reference offset uses the first15×15 block outside detected nuclei. It is not certified cell-free background.

## Reproduction

From a checked-out Cytellect environment with the pinned Fiji already installed, run:

    python scripts/benchmark_resources.py --output /private/resource-run --fiji /opt/Fiji --public-image /private/4DNFI7FAWT6C.tiff --timeout-seconds 300

Use --case public-ncl or --case capacity-4096 to run one case. The diagnostic-only --experimental-java-heap-gib 4 flag changes only the child Java command; it does not modify the production adapter. Failure/timeout exits nonzero after writing its report. Results are JSON in the chosen private scratch directory. No model or dependency download occurs during these cases.

## Recorded capacity input hashes

These SHA-256 values hash C-order uint16 pixels; they matched between the2GiB and4GiB heap runs.

- DAPI:0d170176a17de967163c270e1aef75b0bab92f2e084618b6345d9bfdfaaf2b8a
- NCL:78eb9bf771dc76041a1fcce5e3ede81103fc537ced4d7be3e4ff8a99442f5180
- GFP:a530d1aaff110d7d15944e9d9ee203bdf73b3dcb084a215443faef88f3e3d6df

The public run records16 tiles, runtime-lock SHA-256 aee92d0139669192447a5ce50cb8fe09a6e237082ae376802a45d42a8c2d96e4 and bridge SHA-256956402423ec9b6fc865942052bbe1e2de82720fd4edbc01bff53fb33857234bc. Complete environment/provenance and failed-case details are in the scratch JSON reports.

## Interpretation

A low peak from a failed process is not evidence that the image fits that amount of RAM. A larger host does not fix an independently smaller Java heap. Successful runs on one local CPU do not establish cloud instance throughput, sustained batch behavior, all-image memory bounds, or scientific suitability. A4GiB/8GiB choice must also allow for the OS, API, browser/frontend process if hosted together, SQLite and workload variation. These measurements cannot by themselves justify a paid-server purchase.
