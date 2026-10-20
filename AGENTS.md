# Working on Cytellect

## チーム開発ルール / Team development rules

この節は `CLAUDE.md` の同名節と同期する共通ルールです。正本は `AGENTS.md` とし、変更時は両方を更新してください。日英の記述は同じ要件です。既存の研究・セキュリティ・品質ルールは引き続き適用し、過去の引継ぎにあるブランチ・公開手順は現在の状態と照合してください。過去の作業指示を、新しい作業や公開の許可として扱わないでください。

This section contains shared rules synchronized with the section of the same name in `CLAUDE.md`. `AGENTS.md` is the source of truth; update both sections together. The Japanese and English text expresses the same requirements. Existing research, security, and quality rules remain in effect. Verify branch and release instructions in dated handoffs against current evidence; historical instructions do not authorize new work or publication.

1. **変更前の必読:** エージェントは、一切の変更の前に `AGENTS.md` と `CLAUDE.md`、対象ディレクトリの追加指示を必ず読み、適用される指示を確認してください。作業再開時や指示文の更新後にも読み直してください。

   **Read before changes:** Before making any change, agents must read `AGENTS.md`, `CLAUDE.md`, and any additional instructions for the affected directories, and identify the applicable rules. Read them again when resuming work or after the instructions change.

2. **最新 main から開始:** 作業開始前に Git の状態・作業場所・ブランチを確認し、必ず `git fetch origin main` を実行して最新の `origin/main` を取り込んでください。新規作業は最新 `origin/main` から開始し、既存の feature ブランチを継続する場合も最新 `origin/main` を merge または安全な rebase で取り込んでから変更してください。取得・統合に失敗した場合は、解消するまで変更を始めないでください。既存の未コミット作業や他者の変更を reset・削除・上書きで消してはいけません。

   **Start with current main:** Before starting work, inspect Git status, the checkout, and the branch, then always run `git fetch origin main` and incorporate the latest `origin/main`. Start new work from that revision; when continuing an existing feature branch, first integrate the latest `origin/main` by merge or a safe rebase. If fetching or integration fails, resolve it before making changes. Never discard uncommitted work or another contributor's changes through resets, deletion, or overwriting.

3. **独立した作業場所:** 修正は原則としてタスク専用の `git worktree` と feature ブランチを作成して行ってください。1タスク・1ブランチ・1作業担当を基本とし、他者や別エージェントが使用中の checkout を編集しないでください。worktree を使えない場合は理由を PR に記録し、独立した checkout と feature ブランチを使ってください。PR 経由の要件は省略できません。

   **Isolate the work:** As a rule, create a task-specific `git worktree` and feature branch for changes. Use one task, one branch, and one editing owner; do not edit a checkout used by another contributor or agent. If a worktree cannot be used, record the reason in the PR and use an isolated checkout and feature branch. The PR requirement still applies.

4. **PR とレビュー:** `main` へ直接 push しないでください。文書や設定を含むすべての変更は、feature ブランチ → Pull Request → レビュー → マージの順に進めます。レビューを省略できるのは、プロダクトオーナー `genellect` の変更だけです。共同編集者の変更を、操作アカウントが `genellect` であるという理由だけでこの例外にしてはいけません。共同編集者の変更は、別の人によるレビューを受けてください。オーナーの変更でも PR と必須チェックは省略できません。

   **Use PRs and review:** Never push directly to `main`. All changes, including documentation and configuration, follow feature branch → Pull Request → review → merge. Review may be omitted only for product owner `genellect`'s changes. Do not apply this exception to collaborator changes merely because the operating account is `genellect`. Collaborator changes require review by another person. Even owner changes still require a PR and all mandatory checks.

5. **マージ・本番公開の権限:** `main` へのマージと本番デプロイを行えるのはプロダクトオーナー `genellect` のみで、いずれにもその操作を対象としたユーザーの明示的指示が必須です。実装・コミット・push・PR 作成の依頼は、マージや本番公開の許可を含みません。エージェントは共同編集者の依頼だけでこれらを実行してはいけません。マージが本番の自動デプロイを起動する場合は、その影響も明示的指示の対象に含まれていることを確認してください。保護ルールや必須チェックを無効化・迂回してはいけません。

   **Owner-only merge and production release:** Only product owner `genellect` may merge into `main` or deploy to production, and each action requires an explicit user instruction authorizing that action. A request to implement, commit, push, or open a PR does not authorize merging or production release. Agents must not perform these actions based only on a collaborator's request. If merging triggers an automatic production deployment, ensure that effect is covered by the explicit instruction. Do not disable or circumvent protection rules or mandatory checks.

6. **PR の説明と検証:** PR の説明は日本語または英語で、目的・背景、何をなぜ変えたか、テスト結果、本番への影響範囲を明記してください。テストは実行したコマンドと結果、未実施・失敗・制約を区別し、未実施を成功と記載しないでください。変更に対応した検証と既存の必須 CI を通し、PR 提出・マージ前に最新 `main` との差分や競合を再確認してください。取り込みや追加修正で影響した検証は再実行します。1つの PR はレビュー可能な範囲に絞り、無関係な変更を混ぜないでください。

   **Describe and validate the PR:** Write the PR description in Japanese or English and state its purpose and background, what changed and why, test results, and production impact. Record commands and outcomes, distinguish unrun checks, failures, and limitations, and never report an unrun check as passed. Run validation appropriate to the change and satisfy existing mandatory CI. Recheck differences and conflicts against current `main` before submitting or merging the PR, and rerun affected validation after integration or further edits. Keep each PR focused and reviewable, without unrelated changes.

Read docs/requirements.md, docs/methods.md and docs/security.md before changing behavior.
Inspect Git status. Preserve user work and original research outputs.

## Research data boundary
- Synthetic data is for deterministic numerical tests. Published real microscopy is required for image integration and public demos; public assets need recorded source, accurate stain metadata, redistribution terms and hashes. Never substitute another stain for NCL/GFP.
- Never copy unpublished/private research images, research PDFs, source paths, study-specific results, participant identifiers, credentials, or invitation/session tokens into code, logs, issues, PRs, screenshots, or external AI services. The only exception is the product's own analysis proposal request defined in docs/workspace-redesign.md, sent by the running application under the user's explicit settings; development agents and CI never receive private research content. Registered public fixtures follow the source and redistribution requirements above.
- Keep runtime data outside the checkout. Never use production credentials for development.
- Run private validation separately; publish only an explicitly approved sanitized report.

## Scientific behavior
- Original pixel values are immutable. Detection preprocessing and display LUTs must never change measurement values.
- Label masks in original image coordinates are canonical. Changing nuclei invalidates their dependent nucleoli; changing masks or exclusions invalidates derived statistics/figures.
- Changes to thresholds, background, gating, equations or statistics require a recipe/version change, methods documentation and numerical tests.
- Missing/undefined is not zero. Never tune parameters to obtain significance or silently discard failed fields.
- Keep nuclei, nucleoli, fields, samples and independent experimental units distinct.
- The API and analysis package own numeric results; never calculate authoritative measurements in the browser.

## Development
- Conserve tokens without weakening quality: use focused reads and concise tool output, give agents non-overlapping ownership, and reuse recorded passing checks unless changed code or new evidence justifies rerunning them. Preserve required CI, exact-package numerical acceptance and canonical-browser verification.
- Keep marketing and application writing distinct. The landing page relies on photography, typography, composition and actual product output; do not add stock-photo disclaimers, development badges or defensive copy. Keep provenance and release evidence in the relevant records. Application text uses clear operation names and concise instructions, without advertising slogans. Do not invent product capabilities, endorsements or usage claims.
- Follow docs/interface-design.md for the accepted visual direction: Lila-inspired Dark and Blue, Blender-authored hero artwork rendered with Three.js, and GraphPad-style researcher-benefit hierarchy. Do not substitute charcoal-only styling or CSS perspective for those requirements. The analysis workspace follows docs/workspace-redesign.md: one workspace from image addition to figures, without per-field confirmation chains.
- Follow docs/research-workflow.md for the active product goal, agent ownership and review loop. Start from a researcher decision, not a parameter or fashionable technology. Do not claim Fiji lacks a capability without checking its actual tools.
- Distinguish literature-informed need hypotheses from observed Cytellect user needs. Independent review must report evidence scope, failures and missingness; a green build or matching p-value never establishes biological validity.
- Codex Cloud is the default code environment. Use synthetic numerical fixtures and registered public datasets only. Local execution is permitted for setup and verification, especially the private validation boundary.
- Pin dependencies and model hashes. Review licenses separately for code, weights and data.
- No runtime package/model downloads, arbitrary submitted code/macros or remote image URLs.
- Run `uv run pytest`, `uv run ruff check .`, `pnpm check`, `pnpm test`, and relevant integration tests. Do not mark skipped Fiji/private-data checks as passed.
- Record purpose, scientific impact, validation evidence and limitations in PRs.
- Distinguish source implementation, CI, deployment, hosted behavior and scientific validation.
- Follow the user's current authorization for publishing, external transmission, settings changes and deployment. Do not install paid services or Supabase dependencies to the MVP. The LLM analysis proposal service follows docs/workspace-redesign.md: off by default, structured and locally validated, never the source of measurements or statistics, and billable calls only with an operator-configured budget.
- Keep README status truthful. An unfinished requirement remains open in docs/roadmap.md.
- Local browser delivery is an execution adapter. Keep one shared measurement/statistics implementation and preserve the future hosted API boundary. Read docs/local.md before changing local bootstrap, installer, session or retention behavior.
