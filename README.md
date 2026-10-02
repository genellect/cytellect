# Cytellect

Reproducible immunofluorescence analysis, from nuclear and nucleolar segmentation to quantification, statistics, and publication-ready figures.

[日本語](README.ja.md)

**Development checkpoint — not a working application or validated research tool.** Python analysis and API drafts exist; Web UI, worker, locked Fiji runtime, integration tests and deployment are not implemented. Do not upload research data to this version.

Read [handoff](docs/handoff.md), [requirements](docs/requirements.md), [methods](docs/methods.md), [security](docs/security.md), [roadmap](docs/roadmap.md) and [AGENTS.md](AGENTS.md).

Python 3.12 and Node.js 24 are the targets. Install the current Python checkpoint with `uv sync --locked --dev`. Check syntax with `uv run python -m compileall -q packages services`. Lint with `uv run ruff check packages services`. These are not scientific validation. Root pnpm commands reserve a Web package that does not yet exist. No end-to-end startup is available.

Use synthetic fixtures only in GitHub/CI/Cloud. Research images and derived data belong in a separately approved private environment. The intended PoC uses invitations, ownership checks and 24h inactivity retention; these protections are incomplete. No production deployment.

Publication-ready means editable figures, explicit conditions, traceable measurements and replayable outputs, not certification of scientific validity. UBF/3D/time series/FRAP, automatic whole-cell segmentation, billing, LLM and Supabase are outside the initial runtime.

Own source: Apache-2.0. Third-party code, Fiji and weights retain their licenses; see [OSS](docs/oss.md). No Fiji/model binaries are redistributed.
