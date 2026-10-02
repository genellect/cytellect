# Contributing

Read [AGENTS.md](AGENTS.md) and [requirements](docs/requirements.md). Keep all unpublished research data outside the checkout and CI. Public published data must have a source, accurate channel metadata and a documented use scope. Publicly redistributed assets additionally require a verified redistribution basis and SHA-256 entry.

Install Python 3.12 / Node.js 24, then `uv sync --locked --dev` and `pnpm install --frozen-lockfile`. Run `uv run pytest -m "not fiji"`, `uv run ruff check .`, `uv run mypy packages/analysis/src services`, `pnpm check`, `pnpm test`, and `pnpm build`. Engine changes also require `CYTELLECT_FIJI_EXECUTABLE` and `uv run pytest -m fiji`.

Regenerate the API contract with `cytellect openapi --output packages/contracts/openapi.json` using a scratch runtime, then `pnpm contracts`. Commit both generated contracts.

PRs describe purpose, scientific impact, checks performed and remaining limitations. Scientific behavior changes need a versioned recipe/method explanation and numerical tests. Do not replace independent experiment replication with cell counts, tune thresholds for significance, or silently omit failed fields.
