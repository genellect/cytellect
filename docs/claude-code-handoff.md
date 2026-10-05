# Developer handoff — 2026-10-05

**Latest handoff:** [PR #32 through API evaluation and production publication](claude-production-handoff-2026-10-05.md).
Start there for the current branch, committed fixes, passed baseline CI, remaining
product connections, budget boundaries and exact deployment/installation gates.
The checkpoints below are historical; they do not override the newer handoff.

## Start here

1. Read [AGENTS.md](../AGENTS.md), [requirements](requirements.md), [methods](methods.md), [security](security.md), [local delivery](local.md) and the relevant feature document. Read narrowly; do not import every document into every session.
2. Check Git status, origin/main, open PRs and current production/release identities. Use a fresh clone or a separate worktree. Existing agent worktrees and pending Windows publication drafts must not be overwritten.
3. Use the lockfiles and documented setup/CI. Do not upgrade scientific dependencies or regenerate an accepted release merely to get a test passing. Never disable OS protection to execute refused binaries.
4. Before a change, identify its acceptance evidence. Afterward distinguish source tests, CI, installed-package checks, production behavior and biological/user validation.

Claude Code can load the root CLAUDE.md, which imports the same AGENTS.md used by other agents. Confirm the loaded instructions with `/context`. Do not copy or rewrite the project rules into a second conflicting instruction set.

## Delivered source versus available download

| Item | Checkpoint and source of truth |
|---|---|
| Analysis/UI/storage source | PR [#26](https://github.com/genellect/cytellect/pull/26), merged main `f67979ae90e609b395f9536afbbbf20c7d2c37d7`. All five main checks passed in [37220187383](https://github.com/genellect/cytellect/actions/runs/37220187383). Inspect newer main before work. |
| Public LP | Canonical https://cytellect.vercel.app/; approved Dark/Blue visual direction, Blender/Three.js artwork and responsive composition. Preserve the accepted copy/layout except explicit user changes. |
| Public Windows package at this checkpoint | local.11, source `c21f9057dd130b87ba55b113d40a0396dcb79e74`; source of truth is apps/web/src/lib/published-release.json plus the actual release asset. |
| Candidate Windows package | local.14, exact f679 source; [release CI 37221773960](https://github.com/genellect/cytellect/actions/runs/37221773960) passed fresh/repeated setup, 24 installed browser cases, numerical/export/replay and supervised shutdown. It remains a draft pending intended-PC acceptance. |
| Candidate archive | 12,523,192 bytes; SHA-256 `cc33c3792d06cecbc4879cc398d1abd9e0b66ae3fe22827ef0e97308cd51da4b`. Never overwrite this asset with different bytes. |
| LP analytics/installed-user guidance | PR [#27](https://github.com/genellect/cytellect/pull/27). Read its current merge/check/deployment state; a source change or this document alone is not proof of publication. |

PR26 includes generic comparisons/associations, editable SVG/PDF figures and source data, versioned replay, and managed application retention. Read [common statistics](common-statistics.md), [figures](figures.md) and their tests before changing formulas or inference. Keep the existing nuclear/NCL/GFP recipes, original measurement pixels, region dependencies and experimental-unit distinctions.

## Remaining Windows release gate

The intended Windows PC refuses the unsigned SciPy 1.18.1 `_ufuncs_cxx.cp314-win_amd64.pyd` through Smart App Control (Code Integrity 3077, VerifiedAndReputableDesktop, status 0xc0e90002). Setup therefore stopped before intended-PC browser/numerical/update/stop acceptance. Another successful CI run alone does not resolve this gate. No policy was disabled and no refused binary was renamed or substituted. An approved test environment or an appropriate trusted binary distribution is needed. Changing the artifact requires a new immutable release and matching acceptance.

An earlier, separate runtime-integrity failure involved extra bytecode caches. Those caches were preserved outside the runtime; all pinned runtime files matched afterward. Use `-B` and PYTHONDONTWRITEBYTECODE for pinned-runtime diagnostics. Private-machine logs/paths stay outside the public repo; request only the necessary sanitized receipt or local checkpoint from the project owner.

After the environment blocker is resolved: verify the exact archive -> setup/repeat setup -> installed browser/numerical/replay/activation/retention/shutdown -> independent review -> publish accepted asset -> update release metadata/docs/planning default together -> PR/main/Vercel -> verify canonical download bytes/hash. Keep old public release history intact. Private-study scientific validation and researcher usability have not been completed.

## Installation and returning users

Downloading a ZIP does not install anything. Repeating setup into the same installation root reuses matching dedicated Fiji. Choosing a different root creates a separate environment; an unrelated pre-existing Fiji is not automatically adopted. The unpublished managed-retention improvement keeps current/previous verified applications and preserves unknown/modified/active files and research data. Do not describe it as already available in local.11.

Current local delivery starts from the Cytellect desktop shortcut. The launcher has a `ブラウザで開く` button. It rejects cross-site browser requests even at the root page, and no OS custom URI launcher is registered. Thus a public LP link to localhost is not a working one-click launch feature. LP guidance must describe the actual shortcut workflow. Any future one-click entry requires a separately reviewed launcher/protocol design; retain cross-site API/session protections.

## LP analytics boundary

Only production LP measurement uses COMPASS official `G-EHKJ8B8N0Y`. See [security](security.md#public-landing-page-analytics) for fixed events, exclusions and lifecycle. Preserve no analytics on application/local/API/preview routes. No private research content may be sent to GA4, an LLM, an error tracker, a public Issue or CI attachment. Tests must intercept production analytics rather than pollute reports.

## Working arrangement

One implementation owner per branch. Codex and Claude Code may review each other's PRs but must not concurrently edit the same checkout. GitHub checks remain the shared quality gate. Maintain a short current handoff after each meaningful checkpoint: exact commit/PR, changed behavior, checks and their scope, unresolved issues, next command or decision. Reuse unchanged passing evidence and avoid recursive rereading of old transcripts or the whole workspace.

No automatic transfer of Codex goals, quota monitors, approvals, credentials, unpublished local artifacts or chat memory occurs. The prior long-running delivery goal is blocked, not complete; its quota monitor is paused. Review permissions and the current instruction with the user before assuming unattended operation in another tool.

## 2026-10-05 redesign checkpoint

The next phase (review and minimal fixes, the GPT6.1Sol proposal API and production publication of all parts including the Worker) is assigned to Codex: start from [Codex handoff](codex-handoff-2026-10-05.md).

The owner's human end-to-end review rejected the multi-panel workspace UX. The active increment is the [single workspace and analysis proposal service](workspace-redesign.md), delivered as small PRs from `claude/cool-feynman-spwegw` (policy), `claude/cool-feynman-spwegw-ux` (operable prototype with a simulated adapter) and `claude/cool-feynman-spwegw-llm` (proposal contract, validator, relay client and Cloudflare Worker source, disabled by default). Deploying the Worker, creating its D1 database and setting its secret and budget require the operator's accounts and are not done by these PRs.

PR [#28](https://github.com/genellect/cytellect/pull/28) (Docker Desktop browser setup) is handled independently. Its recorded real-Fiji browser run had one failure: after changing conditions, the confirmation button for re-detection did not appear. The cause is not established; do not delete the test or only lengthen waits.
