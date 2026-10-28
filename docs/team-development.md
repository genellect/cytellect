# チーム開発ルール / Team development rules

[日本語](#日本語) · [English](#english)

## 日本語

Cytellect の開発に参加するメンバーのためのルール。開発の進め方、Git の運用、研究データの扱いを定める。人も AI エージェントも守る原則は[開発の原則](development-principles.md)、開発環境の構築と起動は [CONTRIBUTING](../CONTRIBUTING.md) にある。AI エージェント向けの指示は [AGENTS.md](../AGENTS.md) にあり、この文書と同じ内容を前提にする。

### 1. 役割

| 役割 | 担当 | 責任 |
|---|---|---|
| プロダクトオーナー | `@genellect` | 優先順位、`main` へのマージ、本番公開と配布、外部サービスと費用の判断 |
| 開発メンバー | リポジトリの Collaborator | 担当タスクの実装、PR の作成、他のメンバーの PR のレビュー |
| AI エージェント | Claude Code、Codex など | 依頼者の指示による実装と検証。成果物の責任は依頼者が持つ |

### 2. 開発の流れ

1. **タスクを決める。** 目的と完了条件を Issue またはタスクの依頼に書く。
2. **ブランチを作る。** 最新の `origin/main` から作る。名前は `<種類>/<内容>` とし、種類は `feat`、`fix`、`docs`、`test`、`chore` のいずれか（例: `fix/nucleolus-boundary`）。エージェントのツールが付ける接頭辞（`claude/`、`codex/`）も使える。
3. **変更する。** 1 つの PR では 1 つの目的だけを扱う。仕様・テスト・文書は、コードと同じ PR で更新する。
4. **PR を出す。** [PR テンプレート](../.github/pull_request_template.md)のすべての項目を書く。作業途中の共有には Draft PR を使う。
5. **CI とレビューを通す。** 必須 CI がすべて成功し、必要なレビューを得るまでマージしない。PR の CI は、変更したファイルに関係する検査だけを実行する。Fiji・Cellpose の画像・Windows の導入の統合試験は、マージキューと `main` への取り込み後に実行し、Windows 版の配布は、配布するコミットでこれらすべての成功を確認してから行う（[CI の構成](ci.md)）。`main` で失敗した場合は、次の配布より前に修正するか取り消す。
6. **マージする。** オーナー（またはオーナーの指示を受けたエージェント）が PR をマージキューに追加する。マージ画面の「Merge when ready」か、`gh pr merge <番号>` を使う。キューは、先に並んだ PR と最新の `main` を組み合わせた状態で必須 CI と統合試験を実行し、成功したものだけを squash merge で `main` に取り込む。失敗した PR はキューから外れるので、原因を直して入れ直す。PR のタイトルがそのままコミットの件名になるため、変更の内容が分かるタイトルにする。ルールのバイパス（マージ画面のバイパス、`gh pr merge <番号> --squash --admin`）は、キューを通せない緊急の場合にオーナーが使う。

### 3. Git の運用

- `main` への直接 push、force push、ブランチ保護の変更をしない。
- 作業を始める前と PR を出す前に `git fetch origin main` を実行し、最新の `main` を取り込む。取り込み後は、影響する検証をやり直す。
- 他のメンバーのブランチには、本人の了承なく push しない。
- 並行作業では、タスクごとに `git worktree` または別の checkout を使う。他の人やエージェントが使用中の checkout は編集しない。
- マージ済みのブランチは削除する。

### 4. レビュー

- オーナー以外が作成した PR には、作成者とは別のメンバー 1 名以上の承認が要る。
- オーナー自身の PR は、レビューを省略できる。PR と必須 CI は省略できない。
- エージェントが作成した変更は、作業を依頼した人の変更として扱う。オーナーのアカウントで動くエージェントが他のメンバーの依頼で作成した変更にも、レビューが要る。
- レビューでは次の点を確認する。
  - 変更が目的に合い、無関係な修正を含まないか
  - 画素値、マスク、測定値、統計、図への影響が説明・検証されているか
  - 原因が証拠で特定され、個別の対症ではなく一般則や構造で対処しているか（[問題への対処](development-principles.md#問題への対処)）
  - 非公開データや認証情報が含まれていないか
  - 検証の結果が事実どおりに書かれ、未実施の項目が明示されているか

### 5. AI エージェントの利用

- エージェントへの依頼は、目的、対象範囲、完了条件を明確にする。
- 並行して動かすエージェントには、別々のブランチと worktree を割り当て、同じファイルを編集させない。
- エージェントの成果物は、依頼者が内容を確認してからレビューに出す。
- エージェントが作成したコミットには、ツールが付ける `Co-Authored-By` 行を残す。
- エージェントにマージや本番公開をさせるのは、オーナーがその PR について明示的に指示した場合に限る。
- 作業の引き継ぎは、PR の説明と [roadmap](roadmap.md) に記録する。セッションごとの引き継ぎ文書は新たに作らない。

### 6. 研究データの扱い

研究データは、次の区分で管理する。

| 区分 | 例 | 保存場所 | Git・CI・開発用 AI |
|---|---|---|---|
| 非公開データ | 研究室の未発表画像、正解の輪郭、測定表、論文草稿、ファイル名とパス、参加者情報 | 研究室が管理するストレージ（checkout の外） | 使用不可 |
| 公開データ | 出典とライセンスを確認した公開画像 | 登録済みの fixture。出典、染色情報、再配布条件、ハッシュを記録 | 使用可（リポジトリに置くのは再配布できるものだけ） |
| 合成データ | 計算の照合に使う最小の数値・ラベルの配列（細胞を模した画像は除く） | リポジトリ | [開発の原則](development-principles.md#研究データと検証)の条件を満たす場合に限り使用可 |
| 認証情報 | API キー、トークン、招待リンク | 各サービスの secret 管理 | 使用不可 |

- 非公開データは、コード、ログ、Issue、PR、スクリーンショット、CI、開発用 AI（チャットへの貼り付けを含む）に含めない。
- 製品の解析提案機能は、利用者が有効にした場合に限り、[定められた情報](security.md#analysis-proposal-service)を送る。この機能は、開発で非公開データを扱ってよい根拠にはならない。
- **評価データを分ける。** 検出精度の評価には、学習と条件調整に使わない実験回の画像を使う。分割は実験回の単位で行い、どの画像をどちらに使ったかを記録する。評価データを見て閾値やモデルを調整しない。
- **学習済みモデルを管理する。** 非公開データで学習した重みを公開・配布する場合は、オーナーとデータ提供元の承認を得る。学習データ、重み、推論条件は組にして版を管理する。
- **共同研究先のデータ。** 提供元との取り決め（利用目的、保存場所、保存期間）の範囲内で使う。
- **結果の公開。** 非公開データによる検証結果は、オーナーが承認した匿名化済みの集計だけを公開する。
- **誤って含めた場合。** 非公開データや認証情報をコミット・送信した場合は、すぐにオーナーへ連絡する。追加のコミットで削除しても履歴には残るため、単独で履歴を書き換えずに対応を相談する。認証情報は直ちに無効化して再発行する。

### 7. 本番公開と配布

- `main` へのマージは、Vercel による本番サイトの自動デプロイを起動する。
- Windows 版の配布は、`main` へのマージとは別に、配布物の導入後の受入確認を経てオーナーが行う。
- 有料サービスの契約、外部サービスの追加、費用が発生する設定は、オーナーが判断する。

### 8. このルールの変更

変更は PR で提案し、オーナーの承認を得る。日本語と英語は同じ PR で更新し、[AGENTS.md](../AGENTS.md) と内容を一致させる。

## English

These rules apply to everyone contributing to Cytellect. They define how we work, how we use Git and how we handle research data. The principles that people and AI agents follow are in [Development principles](development-principles.md) (Japanese), and setting up a development environment is covered in [CONTRIBUTING](../CONTRIBUTING.md) (Japanese). Instructions for AI agents are in [AGENTS.md](../AGENTS.md) and are consistent with this document.

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
4. **Open a PR** and fill in every section of the [PR template](../.github/pull_request_template.md) (Japanese). Use a draft PR to share work in progress.
5. **Pass CI and review.** Do not merge until all required checks pass and the required review is complete. Pull-request CI runs only the checks the changed files can affect. The Fiji, Cellpose-image and Windows-install integration jobs run in the merge queue and after merge on `main`, and a Windows release proceeds only when all of them have passed on the commit it releases ([CI design](ci.md)). A failure on `main` is fixed or reverted before the next release.
6. **Merge.** The owner (or an agent the owner instructs) adds the PR to the merge queue with "Merge when ready" on the merge screen or `gh pr merge <number>`. The queue runs the required checks and the integration jobs on the PR combined with current `main` and the PRs ahead of it, and squash-merges only what passes. A PR that fails leaves the queue; fix the cause and add it again. The PR title becomes the commit subject, so make it describe the change. The rule bypass (on the merge screen, or `gh pr merge <number> --squash --admin`) is for emergencies the queue cannot handle, used by the owner.

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
  - causes are identified from evidence and fixed through general rules or structure rather than case-specific patches ([Development principles](development-principles.md#問題への対処), Japanese);
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
| Synthetic data | Minimal numeric or label arrays for checking calculations (not images imitating cells) | Repository | Permitted only under the conditions in [Development principles](development-principles.md#研究データと検証) |
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
