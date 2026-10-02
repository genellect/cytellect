# Implementation handoff — 2026-10-02

The user requested Cloud continuation while away. This is incomplete work, not M0–M3 completion. Use only public source and synthetic data.

Read AGENTS.md, requirements.md, methods.md, security.md and roadmap.md. Inspect Git status. Continue on a feature branch; preserve this checkpoint. Leave reviewable changes and accurate evidence. Do not merge or deploy automatically.

## Existing drafts

- packages/analysis: Pydantic contracts, TIFF validation, synthetic fields, mask editing, numerical measurements, GFP gating, statistics, Matplotlib exports.
- services/api: FastAPI invite/session/ownership, upload/preview, immutable revision requests, review/statistics/export requests and private downloads.
- db.py: SQLite tables, atomic claim, heartbeat, leased/fenced finish, expired-lease recovery draft.
- services/worker: package marker only; no pipeline, cleanup or process supervisor.
- uv.lock installed locally with Python 3.12. No Web implementation/pnpm lock, real Fiji runtime, tests, CI or Compose yet.

## Known blockers

1. CLI serve references cytellect_api.app:app although only create_app exists. Use factory mode. Worker and cleanup entry points target absent cytellect_worker.main.
2. Settings defaults to a home directory. Require explicit private data volume in deployment, temporary outside-checkout directory in tests.
3. Schema uses create_all, not Alembic. Synthetic insertion misses workspace-byte updates and some deletion/quota race checks.
4. Analysis/statistics/export routes only queue work; nothing executes.
5. Nucleolar detection is currently a Python/scikit-image reference. Production Fiji/ImageJ/MorphoLibJ is absent; never label Python results Fiji.
6. Pin and test actual Fiji/Java/StarDist/CSBDeep/MorphoLibJ/weights; record URLs, SHA-256 and licenses; no runtime downloads.
7. Legacy is not verified reproduction. RGB conversion, resizing, extranuclear background, clipping, epsilon, fallback and GFP gate/transform need explicit versioned implementation and an approved sanitized reference. Private legacy files are not available in Cloud.
8. Exploratory regression uses positive GFP then log2. Verify recipe-specific transforms/centering, interaction/trend needs and field-summary consistency.
9. Sensitivities and numeric CSV import are absent.
10. Nuclear edits remove affected nucleoli. Implement affected-parent review/recomputation and prohibit stale child measurements.
11. Retry endpoint, cancellation/process-tree kill, retention/cleanup, partial failures, interrupted-upload recovery and export are absent.
12. API responses mostly dictionaries; introduce response schemas then generated TypeScript.
13. Matplotlib outputs/fonts, editable SVG/PDF, pixel-exact Fiji ROI exchange are untested.
14. Cross-session/expiry/revocation/deletion/CSRF/quota/concurrency protections are draft, untested. Do not deploy.

## Checkpoint verification

uv dependencies installed. Python compileall passed. Ruff found 16 import-order/unused-import findings, not fixed. No unit tests, mypy, browser, Docker, Fiji, hosted or private-data checks passed.

## Continue

Write meaningful synthetic numerical/security tests and fix entry-point blockers. Build a real worker vertical slice and pinned Fiji integration. Implement Japanese Next.js region editor, revision lifecycle, batch analysis, statistics, exports. Complete CI/Compose/privacy/dependency/license checks. Track actual milestone gates. M4/M5 require private raw images and researcher evaluation; never claim them completed from synthetic tests.
