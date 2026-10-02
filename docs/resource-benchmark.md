# Local resource benchmark

Status: the representative public image completed; the production-profile maximum-size case failed. An explicitly experimental 4 GiB Java-heap run also failed. This is a capacity observation, not cloud sizing certification or a detection-accuracy validation.

The executable script is scripts/benchmark_resources.py. All source images, arrays, transient Fiji files and reports stay outside the repository. It accepts the registered 4DN source by exact SHA-256 and a deterministic capacity generator; it does not accept arbitrary image URLs or private datasets.

## Measurement method

Each case runs in a fresh Python child. The controller samples that child's RSS plus all descendants (including Java/Fiji) with a 50 ms sleep target between samples; process discovery and file reads add overhead. It records peak summed RSS, phases, wall-clock time, process count, sampling failures, source pixel hashes, dimensions, recipe, runtime/bridge/model identifiers, tile count when returned, and host CPU/OS/RAM. The controller itself is excluded. Shared pages can be counted more than once; spikes shorter than the sampling interval can be missed.

Each case has a 300-second wall-clock limit, including process startup, loading/generation, Java compilation, detection and Python compartment measurement. A host-available-memory guard stops the benchmark below 1 GiB to preserve interactive use; any such stop is recorded as a failed capacity observation. There is no container/cgroup memory limit in this local run. Runtime/measurement phases are separate; no private upload/API workload is benchmarked.

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
