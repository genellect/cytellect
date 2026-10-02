# Current implementation handoff

The original Cloud task ended after a narrow worker checkpoint. It was not continuous development and did not complete the MVP. Local work has resumed in parallel across Web, Fiji, analysis/statistics and API/operations.

The current working implementation includes Web/API/worker, masks and measurements, statistics/exports, real Fiji CPU integration, source/recipe/environment tracking and protection tests. Published real images now supplement numerical synthetic tests. Follow [roadmap](roadmap.md) for open verification gates; do not infer completion from files existing or a task being dispatched.

Before resuming, inspect Git status and read requirements/methods/security. Preserve private data boundaries. Run fixed-dependency installation and appropriate checks. Do not treat another project's Cloud setup as Cytellect setup. The setup script must finish Node24, Python, browser and optionally Fiji provisioning before network access is disabled.

When handing off, record the actual running task, latest successful command, pending tests, branch/commit and what requires input. Verify the destination starts and reaches the next acceptance result. A completed narrow task requires a new explicit continuation, not an assumption that the open window keeps working.

Private scientific validation and the hosted analysis server remain distinct from public UI publication.
