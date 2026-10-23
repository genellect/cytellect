# チーム開発ルール / Team development rules

[日本語](#日本語) · [English](#english)

## 日本語

Cytellect の開発に参加するメンバーのためのルールです。開発の進め方、Git の運用、研究データの扱いを定めます。セットアップと検証コマンドは [CONTRIBUTING.md](../CONTRIBUTING.md)、技術上の基準は [Development standards](development-standards.md) を参照してください。AI エージェント向けの指示は [AGENTS.md](../AGENTS.md) にあり、この文書と同じ内容を前提にしています。

### 1. 役割

| 役割 | 担当 | 責任 |
|---|---|---|
| プロダクトオーナー | `@genellect` | 優先順位、`main` へのマージ、本番公開と配布、外部サービスと費用の判断 |
| 開発メンバー | リポジトリの Collaborator | 担当タスクの実装、PR の作成、他のメンバーの PR のレビュー |
| AI エージェント | Claude Code、Codex など | 依頼者の指示による実装と検証。成果物の責任は依頼者が持つ |

### 2. 開発の流れ

1. **タスクを決める。** 目的と完了条件を Issue またはタスクの依頼に書きます。
2. **ブランチを作る。** 最新の `origin/main` から作成します。名前は `<種類>/<内容>` とし、種類は `feat`、`fix`、`docs`、`test`、`chore` のいずれかです（例: `fix/nucleolus-boundary`）。エージェントのツールが付ける接頭辞（`claude/`、`codex/`）も使用できます。
3. **変更する。** 1 つの PR では 1 つの目的だけを扱います。仕様・テスト・文書は、コードと同じ PR で更新します。
4. **PR を出す。** [PR テンプレート](../.github/pull_request_template.md)に沿って、変更内容、科学的な影響、検証、残る制約を書きます。作業途中の共有には Draft PR を使います。
5. **CI とレビューを通す。** 必須 CI がすべて成功し、必要なレビューを得るまでマージしません。PR の CI は、変更したファイルに関係する検査だけを実行します。Fiji・Cellpose の画像・Windows の導入の統合試験は、`main` への取り込み後に実行し、Windows 版の配布は、配布するコミットでこれらすべてが成功していることを確認してから行います（[CONTRIBUTING](../CONTRIBUTING.md#ci-scope)）。`main` で失敗した場合は、次の配布より前に修正するか取り消します。
6. **マージする。** オーナーが squash merge で `main` に取り込みます。PR のタイトルがそのままコミットの件名になるため、変更の内容が分かるタイトルにします。`main` はルールセットで更新を制限しており、PR をマージできるのはバイパス権限を持つオーナーだけです。オーナーはマージ画面でルールのバイパスを選ぶか、`gh pr merge <番号> --squash --admin` を実行します。このバイパスでも必須 CI は省略されません。

### 3. Git の運用

- `main` への直接 push、force push、ブランチ保護の変更は行いません。
- 作業を始める前と PR を出す前に `git fetch origin main` を実行し、最新の `main` を取り込みます。取り込み後は、影響する検証をやり直します。
- 他のメンバーのブランチには、本人の了承なく push しません。
- 並行作業では、タスクごとに `git worktree` または別の checkout を使います。他の人やエージェントが使用中の checkout は編集しません。
- マージ済みのブランチは削除します。

### 4. レビュー

- オーナー以外が作成した PR には、作成者とは別のメンバー 1 名以上の承認が必要です。
- オーナー自身の PR は、レビューを省略できます。PR と必須 CI は省略できません。
- エージェントが作成した変更は、作業を依頼した人の変更として扱います。オーナーのアカウントで動くエージェントが他のメンバーの依頼で作成した変更にも、レビューが必要です。
- レビューでは次の点を確認します。
  - 変更が目的に合い、無関係な修正を含まないか
  - 画素値、マスク、測定値、統計、図への影響が説明・検証されているか
  - 非公開データや認証情報が含まれていないか
  - 検証の結果が事実どおりに書かれ、未実施の項目が明示されているか

### 5. AI エージェントの利用

- エージェントへの依頼は、目的、対象範囲、完了条件を明確にします。
- 並行して動かすエージェントには、別々のブランチと worktree を割り当て、同じファイルを編集させません。
- エージェントの成果物は、依頼者が内容を確認してからレビューに出します。
- エージェントが作成したコミットには、ツールが付ける `Co-Authored-By` 行を残します。
- エージェントにマージや本番公開をさせるのは、オーナーがその PR について明示的に指示した場合に限ります。
- 作業の引き継ぎは、PR の説明と [roadmap](roadmap.md) に記録します。セッションごとの引き継ぎ文書は新たに作りません。

### 6. 研究データの扱い

研究データは、次の区分で管理します。

| 区分 | 例 | 保存場所 | Git・CI・開発用 AI |
|---|---|---|---|
| 非公開データ | 研究室の未発表画像、正解の輪郭、測定表、論文草稿、ファイル名とパス、参加者情報 | 研究室が管理するストレージ（checkout の外） | 使用不可 |
| 公開データ | 出典とライセンスを確認した公開画像 | 登録済みの fixture。出典、染色情報、再配布条件、ハッシュを記録 | 使用可（リポジトリに置くのは再配布できるものだけ） |
| 合成データ | テスト用に生成した画像・数値 | リポジトリ | 使用可 |
| 認証情報 | API キー、トークン、招待リンク | 各サービスの secret 管理 | 使用不可 |

- 非公開データは、コード、ログ、Issue、PR、スクリーンショット、CI、開発用 AI（チャットへの貼り付けを含む）に含めません。
- 製品の解析提案機能は、利用者が有効にした場合に限り、[定められた情報](security.md#analysis-proposal-service)を送信します。この機能は、開発で非公開データを扱ってよい根拠にはなりません。
- **評価データを分ける。** 検出精度の評価には、学習と条件調整に使わない実験回の画像を使います。分割は実験回の単位で行い、どの画像をどちらに使ったかを記録します。評価データを見て閾値やモデルを調整しません。
- **学習済みモデルを管理する。** 非公開データで学習した重みを公開・配布する場合は、オーナーとデータ提供元の承認を得ます。学習データ、重み、推論条件は組にしてバージョンを管理します。
- **共同研究先のデータ。** 提供元との取り決め（利用目的、保存場所、保存期間）の範囲内で使用します。
- **結果の公開。** 非公開データによる検証結果は、オーナーが承認した匿名化済みの集計だけを公開します。
- **誤って含めた場合。** 非公開データや認証情報をコミット・送信した場合は、すぐにオーナーへ連絡します。追加のコミットで削除しても履歴には残るため、単独で履歴を書き換えずに対応を相談します。認証情報は直ちに無効化して再発行します。

### 7. 本番公開と配布

- `main` へのマージは、Vercel による本番サイトの自動デプロイを起動します。
- Windows 版の配布は、`main` へのマージとは別に、配布物の導入後の受入確認を経てオーナーが行います。
- 有料サービスの契約、外部サービスの追加、費用が発生する設定は、オーナーが判断します。

### 8. このルールの変更

変更は PR で提案し、オーナーの承認を得ます。日本語と英語は同じ PR で更新し、[AGENTS.md](../AGENTS.md) と内容を一致させます。

## English

These rules apply to everyone contributing to Cytellect. They define how we work, how we use Git and how we handle research data. See [CONTRIBUTING.md](../CONTRIBUTING.md) for setup and validation commands and [Development standards](development-standards.md) for technical standards. Instructions for AI agents are in [AGENTS.md](../AGENTS.md) and are consistent with this document.

### 1. Roles

| Role | Who | Responsibilities |
|---|---|---|
| Product owner | `@genellect` | Priorities, merges into `main`, production release and distribution, external services and spending |
| Developer | Repository collaborators | Implementing assigned tasks, opening PRs, reviewing other members' PRs |
| AI agent | Claude Code, Codex and similar tools | Implementation and validation on a requester's instruction; the requester is accountable for the output |

### 2. Workflow

1. **Define the task.** State the purpose and completion criteria in an issue or task request.
2. **Create a branch** from the latest `origin/main`, named `<type>/<summary>`, where type is `feat`, `fix`, `docs`, `test` or `chore` (for example `fix/nucleolus-boundary`). Prefixes added by agent tools (`claude/`, `codex/`) are also acceptable.
3. **Make the change.** Keep each PR to one purpose. Update specifications, tests and documentation in the same PR as the code.
4. **Open a PR** following the [PR template](../.github/pull_request_template.md): change, scientific impact, validation and remaining limits. Use a draft PR to share work in progress.
5. **Pass CI and review.** Do not merge until all required checks pass and the required review is complete. Pull-request CI runs only the checks the changed files can affect. The Fiji, Cellpose-image and Windows-install integration jobs run after merge on `main`, and a Windows release proceeds only when all of them have passed on the commit it releases ([CONTRIBUTING](../CONTRIBUTING.md#ci-scope)). A failure on `main` is fixed or reverted before the next release.
6. **Merge.** The owner squash-merges into `main`. The PR title becomes the commit subject, so make it describe the change. A ruleset restricts updates to `main`, so only the owner, who holds bypass permission, can merge PRs. The owner selects the rule bypass on the merge screen or runs `gh pr merge <number> --squash --admin`. The bypass does not skip required CI.

### 3. Git

- Do not push directly to `main`, force-push, or change branch protection.
- Run `git fetch origin main` and integrate current `main` before starting work and before opening a PR. Rerun affected checks after integrating.
- Do not push to another member's branch without their agreement.
- For parallel work, use a separate `git worktree` or checkout per task. Do not edit a checkout that another person or agent is using.
- Delete branches after they are merged.

### 4. Review

- PRs authored by anyone other than the owner require approval from at least one member other than the author.
- The owner's own PRs may omit review. They still require a PR and all required checks.
- A change made by an agent belongs to the person who requested it. An agent running under the owner's account on another member's behalf still requires review.
- Reviewers check that:
  - the change matches its purpose and contains no unrelated edits;
  - effects on pixel values, masks, measurements, statistics and figures are explained and tested;
  - no private data or credentials are included;
  - validation results are reported accurately and unrun checks are stated.

### 5. Working with AI agents

- Give agents a clear purpose, scope and completion criteria.
- Assign each concurrent agent its own branch and worktree, and do not let two agents edit the same files.
- The requester reviews an agent's output before requesting review from others.
- Keep the `Co-Authored-By` lines that agent tools add to commits.
- Agents merge or publish only when the owner explicitly instructs them to for that PR.
- Record handoffs in the PR description and the [roadmap](roadmap.md). Do not create new per-session handoff documents.

### 6. Research data

Research data falls into these categories.

| Category | Examples | Storage | Git, CI and development AI |
|---|---|---|---|
| Private data | Unpublished lab images, ground-truth contours, measurement tables, manuscript drafts, file names and paths, participant information | Lab-managed storage outside the checkout | Not permitted |
| Public data | Published images with confirmed source and license | Registered fixtures with recorded source, stain metadata, redistribution terms and hashes | Permitted (only redistributable assets in the repository) |
| Synthetic data | Generated test images and values | Repository | Permitted |
| Credentials | API keys, tokens, invitation links | Each service's secret store | Not permitted |

- Keep private data out of code, logs, issues, PRs, screenshots, CI and development AI, including pasting into chat.
- The product's analysis proposal feature sends only [defined information](security.md#analysis-proposal-service), and only when the user enables it. It does not permit handling private data during development.
- **Separate evaluation data.** Evaluate detection accuracy on images from experimental runs that were not used for training or parameter tuning. Split by experimental run and record which images were used for which purpose. Do not tune thresholds or models against evaluation data.
- **Manage trained models.** Publishing or distributing weights trained on private data requires approval from the owner and the data provider. Version training data, weights and inference settings together.
- **Collaborator data.** Use data from partner labs only within the agreed purpose, storage location and retention period.
- **Publishing results.** Publish results from private-data validation only as anonymized aggregates approved by the owner.
- **Accidental exposure.** If private data or credentials are committed or sent, notify the owner immediately. A follow-up commit does not remove them from history, so agree on the remedy instead of rewriting history alone. Revoke and reissue exposed credentials at once.

### 7. Production release and distribution

- Merging into `main` triggers an automatic Vercel deployment of the production site.
- Windows distribution is separate from merging into `main`; the owner releases it after installed-copy acceptance.
- The owner decides on paid subscriptions, new external services and settings that incur costs.

### 8. Changing these rules

Propose changes in a PR and obtain the owner's approval. Update the Japanese and English sections in the same PR and keep [AGENTS.md](../AGENTS.md) consistent.
