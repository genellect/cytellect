# Cloud continuation

Use the dedicated genellect/cytellect repository and a new branch from current main. Do not reuse another project's environment or secrets. Read AGENTS.md, requirements, methods, security, and the [current roadmap](roadmap.md) before changing behavior.

The Web/API/worker, pinned Fiji engine, editor, measurements, statistics, figures and replay workflow are implemented. [Windows local.6](local-release-0.1.0.md) has passed its versioned installation and browser acceptance and is published. Do not restart M0-M3 or infer remaining implementation from the original Cloud checkpoint. Current tests establish their recorded scope, not scientific readiness for the user's experiment.

## Environment and data

Use Python3.12 and Node24. Run `bash .codex/setup.sh` with network access for provisioning. It installs the locked Python/Web dependencies and browser; actual Linux Fiji setup and tests require `CYTELLECT_SETUP_FIJI=1` and an explicit outside-checkout `CYTELLECT_FIJI_EXECUTABLE`. Verify the resulting environment before starting an offline task. A successful source change or task dispatch does not establish a configured Cloud environment or hosted analysis service.

Use synthetic fixtures for exact numerical checks and registered published microscopy for image integration. Follow the recorded licenses, stains, transformations and model-overlap limitations. Private images, research documents, filenames, conditions and results remain outside Git, CI, external AI and Cloud tasks. Runtime analysis must not download dependencies or models.

## Remaining acceptance and continuation

1. Continue from a concrete requirement or regression in the current roadmap. Preserve the shared scientific implementation and run the checks appropriate to the changed code. Record the exact source, commands, results and unverified scope.
2. M4 requires user-provided original images in a separately approved private environment. Split tuning and evaluation by field/sample; compare reviewed masks and pixel measurements with references and reconcile legacy results. Detection targets remain provisional until measured.
3. M5 requires operator acceptance and researcher evaluation on an accepted local package or approved private host. Record completion, correction time, explanation of statistical units and reuse demand. Automated browser tests do not substitute for researcher participation.
4. A future hosted backend needs its own storage, ownership, TLS/domain, continuous deletion, failure recovery and worker-isolation acceptance. The public Vercel sample viewer is not a private analysis service. No paid backend is selected by this document.

Follow the user's current authorization for merges, releases, deployments, accounts and external transmission. Do not add mandatory LLM, Supabase or payment dependencies to the initial workflow. Preserve private M4/M5 and hosted acceptance as separate gates; do not mark them complete from implementation or public-image tests.

## Historical record

[Original Cloud validation, 2026-10-02](validation-2026-10-02.ja.md) records the early narrow worker checkpoint. Its unfinished-feature list and six-test result are historical, not the current implementation status. Use the [roadmap](roadmap.md), [validation layers](validation.md) and accepted release evidence for current continuation.
