@AGENTS.md

## チーム開発ルール / Team development rules

この節は `AGENTS.md` の同名節を参照する実行時の確認事項です。共通ルールの正本は `AGENTS.md` です。両ファイルを一緒に更新し、日英の要件を一致させてください。既存ルールは引き続き適用します。下記の過去の引継ぎは日付時点の記録であり、現在のチーム開発ルールや新しいユーザー指示に優先せず、新しい作業・マージ・公開の許可にもなりません。

This section is an operational checklist referencing the section of the same name in `AGENTS.md`, the source of truth for the shared rules. Update both files together and keep the Japanese and English requirements aligned. Existing rules remain in effect. The dated handoffs below are historical records; they do not override current team rules or newer user instructions, or authorize new work, merging, or publication.

- **最初に読む:** 一切の変更の前に `AGENTS.md` とこの `CLAUDE.md`、対象ディレクトリの追加指示を必ず読んでください。作業再開時・指示更新後にも読み直してください。

  **Read first:** Before any change, read `AGENTS.md`, this `CLAUDE.md`, and additional instructions for the affected directories. Read them again when resuming work or after instruction updates.

- **最新 main を取り込む:** 作業開始前に状態・checkout・ブランチを確認し、必ず `git fetch origin main` を実行してください。新規作業は最新 `origin/main` から開始し、継続ブランチにも merge または安全な rebase で取り込んでから変更します。取得・統合の失敗や競合を解消するまで変更を始めず、既存作業を reset・削除・上書きで消してはいけません。

  **Integrate current main:** Before starting work, check Git status, the checkout, and the branch, and always run `git fetch origin main`. Start new work from current `origin/main`, or integrate it into a continuing branch by merge or a safe rebase before changes. Resolve fetch or integration failures and conflicts first; never discard existing work by resetting, deleting, or overwriting it.

- **作業を分離する:** 原則としてタスク専用の `git worktree` と feature ブランチを作成します。1タスク・1ブランチ・1作業担当とし、他者の checkout を編集しないでください。worktree を使えない場合は理由を PR に記録し、独立 checkout と feature ブランチを使います。PR は必須です。

  **Isolate changes:** As a rule, create a task-specific `git worktree` and feature branch. Use one task, one branch, and one editing owner, without editing someone else's checkout. If a worktree cannot be used, document why in the PR and use an isolated checkout and feature branch. A PR is still mandatory.

- **PR・レビューを経由する:** すべての変更は feature ブランチ → Pull Request → レビュー → マージとし、`main` へ直接 push しません。レビュー省略はプロダクトオーナー `genellect` の変更だけです。共同編集者の変更を、操作アカウントが `genellect` であるという理由だけで例外にしてはいけません。共同編集者の変更は別の人がレビューし、オーナーの変更も PR・必須チェックを省略しません。

  **Use PRs and review:** All changes follow feature branch → Pull Request → review → merge; never push directly to `main`. Only product owner `genellect`'s changes may omit review. Do not apply that exception to collaborator changes merely because the operating account is `genellect`. Another person reviews collaborator changes; owner changes still require PRs and mandatory checks.

- **オーナーの明示的指示を待つ:** `main` へのマージと本番デプロイは `genellect` のみが可能で、それぞれユーザーの明示的指示が必須です。実装・コミット・push・PR 作成の依頼をマージや本番公開の許可と解釈せず、共同編集者の依頼だけでは実行しません。マージによる本番の自動デプロイも指示の対象であることを確認し、保護ルール・必須チェックは無効化・迂回しません。

  **Require explicit owner authorization:** Only `genellect` may merge into `main` or deploy to production, and each requires an explicit user instruction. Requests to implement, commit, push, or open a PR do not authorize merging or production release; collaborator requests alone are insufficient. Ensure authorization covers any automatic production deployment triggered by a merge. Never disable or circumvent protections or mandatory checks.

- **PR の説明を残す:** 日本語または英語で、目的・背景、何をなぜ変えたか、テスト結果、本番への影響範囲を記載します。実行コマンドと結果、未実施・失敗・制約を区別し、未実施を成功扱いにしません。変更に応じた検証と必須 CI を通し、PR 提出・マージ前に最新 `main` との差分・競合を再確認して、取り込みや追加修正で影響した検証を再実行します。PR は小さく、無関係な変更を混ぜないでください。

  **Document the PR:** In Japanese or English, state purpose and background, what changed and why, test results, and production impact. Distinguish commands and results from unrun checks, failures, and limitations; never call an unrun check passed. Run appropriate validation and mandatory CI, recheck current `main` differences and conflicts before PR submission or merge, and rerun checks affected by integration or later edits. Keep PRs small and free of unrelated changes.

**Current handoff (2026-10-06):** Read `docs/claude-handoff-2026-10-06.md` first. Codex stopped at the user's request to transfer work to Claude. Resume from `codex/batch-workspace-repair` / Draft PR #42 (base PR #41), not an older main-only checkpoint. The current analysis UI is explicitly not accepted by the user. The latest handoff records superseded UX proposals, remaining scientific/implementation work, tests, deployment differences, and secret/private-data boundaries. Follow it before older delivery notes.

For a new session, read `docs/claude-code-handoff.md`, then inspect Git status, open PRs and the actual deployed/published versions. Read the relevant requirement, methods and security documents before changes. The handoff records a dated checkpoint, not an override of newer repository evidence.

Keep implementation changes on a dedicated branch/worktree. Do not edit a checkout another agent is using. Preserve the existing PR -> required checks -> main -> Vercel release flow. Keep publication of Windows packages subject to their own installed-copy acceptance.
