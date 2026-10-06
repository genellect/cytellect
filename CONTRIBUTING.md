# Contributing

Read [AGENTS.md](AGENTS.md) and [requirements](docs/requirements.md). Keep all unpublished research data outside the checkout and CI. Public published data must have a source, accurate channel metadata and a documented use scope. Publicly redistributed assets additionally require a verified redistribution basis and SHA-256 entry.

Install Python 3.12 / Node.js 24, then `uv sync --locked --dev` and `pnpm install --frozen-lockfile`. Run `uv run pytest -m "not fiji"`, `uv run ruff check .`, `uv run mypy packages/analysis/src services`, `pnpm check`, `pnpm test`, and `pnpm build`. Engine changes also require `CYTELLECT_FIJI_EXECUTABLE` and `uv run pytest -m fiji`.

Regenerate the API contract and default recipe with `uv run cytellect openapi --output packages/contracts/openapi.json --recipe-defaults apps/web/src/lib/recipe-defaults.json` using a scratch runtime, then `pnpm contracts`. Commit OpenAPI, the default recipe JSON and generated TypeScript together.

Dependency and public-source checks use the same locked environment. Choose
private output/cache directories outside the checkout for these commands:

```sh
uv run python scripts/check_public_tree.py
uv run python scripts/check_docs.py
uv run python scripts/sbom.py --output /private/checks/dependency-inventory.json --web-notices /private/checks/THIRD_PARTY_WEB_NOTICES.txt
uv run pip-audit --local --format cyclonedx-json --output /private/checks/python.cdx.json
pnpm audit --prod --audit-level high
uv run python scripts/scan_secrets.py --repo . --cache-dir /private/security-tools --output /private/checks/secrets.json
```

The secret scanner requires full Git history, verifies its pinned tool archive,
and scans history plus the tracked working files. CI uses `fetch-depth: 0` and
retains aggregate counts/rule IDs only. Missing Python license evidence or a
missing direct Web license text fails the inventory gate; classification and
notice collection are evidence checks, not legal compatibility approval. See
[OSS management](docs/oss.md) for scope. Safe dependency/notice and scanner-summary
artifacts expire after seven days; never add raw findings, logs or research data
to artifact upload paths.

PRs describe purpose, scientific impact, checks performed and remaining limitations. Scientific behavior changes need a versioned recipe/method explanation and numerical tests. Do not replace independent experiment replication with cell counts, tune thresholds for significance, or silently omit failed fields.

## CI scope

Pull requests run only the jobs their changed paths can affect. `scripts/ci_changes.py` maps paths to four areas:

| Area | Jobs | Selected by |
|---|---|---|
| `python` | Ruff, mypy, Linux test suite, planning/proposal/asset checks, dependency audit and SBOM | analysis, API, worker, scripts, tests, engines, infra |
| `web` | contract regeneration, Next.js checks and build, proposal Worker, public-site browser tests | `apps/web`, contracts, proposal Worker, analysis/API/worker |
| `fiji` | real Fiji, API/browser workflow, containers, local web bundle | `apps/web`, contracts, analysis/API/worker, scripts, tests, Fiji engine, infra |
| `windows` | Windows setup/launcher tests and the Python 3.14 Windows suite | analysis/API/worker, scripts, tests, engines, local-export scripts |

Documentation (`docs/**`, root-level Markdown, `LICENSE`, `NOTICE`) selects no area. The public-tree check, documentation links and the full-history secret scan always run, and the packaged-documentation tests run whenever the Python suite does not. Skipped jobs report success to branch protection.

Workflows, lockfiles, package manifests, `fixtures/` and any unlisted path select every area. So do every push to `main` and every manual run, so each `main` commit keeps the complete evidence that the Windows release workflow requires. When adding a top-level directory, add it to the rules and their tests.
