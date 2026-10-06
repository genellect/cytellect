@AGENTS.md

**Current handoff (2026-10-06):** Read `docs/claude-handoff-2026-10-06.md` first. Codex stopped at the user's request to transfer work to Claude. Resume from `codex/batch-workspace-repair` / Draft PR #42 (base PR #41), not an older main-only checkpoint. The current analysis UI is explicitly not accepted by the user. The latest handoff records superseded UX proposals, remaining scientific/implementation work, tests, deployment differences, and secret/private-data boundaries. Follow it before older delivery notes.

For a new session, read `docs/claude-code-handoff.md`, then inspect Git status, open PRs and the actual deployed/published versions. Read the relevant requirement, methods and security documents before changes. The handoff records a dated checkpoint, not an override of newer repository evidence.

Keep implementation changes on a dedicated branch/worktree. Do not edit a checkout another agent is using. Preserve the existing PR -> required checks -> main -> Vercel release flow. Keep publication of Windows packages subject to their own installed-copy acceptance.
