@AGENTS.md

For a new session, read `docs/claude-code-handoff.md`, then inspect Git status, open PRs and the actual deployed/published versions. Read the relevant requirement, methods and security documents before changes. The handoff records a dated checkpoint, not an override of newer repository evidence.

Keep implementation changes on a dedicated branch/worktree. Do not edit a checkout another agent is using. Preserve the existing PR -> required checks -> main -> Vercel release flow. Keep publication of Windows packages subject to their own installed-copy acceptance.
