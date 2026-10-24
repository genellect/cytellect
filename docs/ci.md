# CI scope and checks

How pull-request and `main` CI select jobs, and which checks run only in CI. Local commands are in [CONTRIBUTING](../CONTRIBUTING.md); `python3 scripts/dev.py check` runs the same commands as the `python` and `web` jobs.

## Job selection

Pull requests run only the jobs their changed paths can affect. `scripts/ci_changes.py` maps paths to four areas:

| Area | Jobs | Selected by |
|---|---|---|
| `python` | Ruff, mypy, Linux test suite, planning/proposal checks, dependency audit and SBOM | analysis, API, worker, scripts, tests, engines, infra |
| `web` | contract regeneration, Next.js checks and build, proposal Worker, public-site browser tests | `apps/web`, contracts, proposal Worker, analysis/API/worker |
| `fiji` | real Fiji, API/browser workflow, containers, local web bundle | `apps/web`, contracts, analysis/API/worker, scripts, tests, Fiji engine, infra |
| `windows` | Windows setup/launcher tests and the Python 3.14 Windows suite | analysis/API/worker, scripts, tests, engines, local-export scripts |

The public landing page is the exception within `apps/web`: its components (`PublicLanding`, `Landing*`, `HeroFilm`, `optical-landing.module.css`), `lp-metrics` and its browser tests (`marketing`, `lp-*`) select only `web`; its media (`apps/web/public/marketing/**`) and `fixtures/public/allowlist.json` select `python` and `web`, because the media ship in the Windows bundle whose boundary the Python suite checks. The offline hero-film scripts (`scripts/lp_film/**`) select no area.

Documentation (`docs/**`, root-level Markdown, `LICENSE`, `NOTICE`) selects no area. The public-tree check, documentation links and the full-history secret scan always run, and the packaged-documentation tests run whenever the Python suite does not. Skipped jobs report success to branch protection.

Workflows, lockfiles, package manifests, the rest of `fixtures/` and any unlisted path select every area. So do every merge-queue run, every push to `main` and every manual run, so each `main` commit keeps the complete evidence that the Windows release workflow requires. When adding a top-level directory, add it to the rules and their tests.

The three integration jobs — `fiji-browser` (real Fiji, API/browser workflow, containers, local web bundle), `cellpose-gpu-image` and `windows-installed` (fresh install and update of the packaged Windows release) — do not run on pull requests. They run on every push to `main`, in the merge queue and on manual runs. The Windows release workflow requires all seven jobs, these three included, to have passed on the exact `main` commit it releases, so a release is never built from a commit they did not verify. A failure on `main` is fixed or reverted before the next release.

## CI-only checks

The public-site browser tests (`pnpm --filter @cytellect/web exec playwright test …` against `pnpm build` output), the real-Fiji browser workflow, containers and the Windows jobs run only in CI.

## Dependency inventory and secret scan

The secret scanner requires full Git history, verifies its pinned tool archive,
and scans history plus the tracked working files. CI uses `fetch-depth: 0` and
retains aggregate counts/rule IDs only. Missing Python license evidence or a
missing direct Web license text fails the inventory gate; classification and
notice collection are evidence checks, not legal compatibility approval. See
[OSS management](oss.md) for scope. Safe dependency/notice and scanner-summary
artifacts expire after seven days; never add raw findings, logs or research data
to artifact upload paths.
