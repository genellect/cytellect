# Working on Cytellect

## 日本語

### 目的

Cytellect は、蛍光顕微鏡画像から細胞の数・面積・輝度を測り、統計解析と論文用の図の作成までを行うアプリです。研究者が画像と調べたいことを入力し、一つの画面で解析を進められることを目指します。画像ごとの設定や、別のソフトへの測定表の転記を減らします。

核小体・細胞質の検出モデルを追加学習で改良し、LLM で研究目的に合う解析設定を提案します。研究者は検出結果と設定を確認・修正でき、計算は共通の解析処理で実行します。精度、測定誤差、手修正にかかる時間を実画像で確かめます。

解析コードの OSS 公開を続け、クラウド実行・共同利用・運用支援を有料化の候補とします。現在のローカル構成や対応画像の範囲を、将来の製品の制約にしないでください。

### 作業を始める

変更前に必ず、このファイル、[CLAUDE.md](CLAUDE.md)、対象ディレクトリの指示を読んでください。作業再開時と指示更新後にも読み直します。動作を変える場合は、[要件](docs/requirements.md)・[計算仕様](docs/methods.md)・[データ保護](docs/security.md)も確認します。過去の引き継ぎは履歴として扱い、現在の依頼と実装を優先してください。

`git status` で作業場所とブランチを確認し、必ず `git fetch origin main` を実行します。新規作業は最新の `origin/main` から始め、継続中のブランチにも merge または安全な rebase で取り込みます。取得・統合に失敗したら解消してから変更し、未コミット作業や他者の変更を消さないでください。

原則として、タスク専用の `git worktree` と feature ブランチを使います。同じタスクでは既存の worktree を使い、他者が使用中の作業場所を編集しません。worktree を使えない場合は独立した checkout を用意し、理由を PR に記載します。

### 変更から PR まで

すべての変更は **feature ブランチ → PR → レビュー → マージ**で進めます。`main` に直接 push してはいけません。PR は一つの目的に絞り、無関係な変更を混ぜないでください。

共同編集者の変更は別の人がレビューします。レビューを省略できるのは `genellect` 自身の変更だけです。操作アカウントが `genellect` でも、他者の変更にはこの例外を適用しません。PR と必須 CI は誰も省略できません。

検証は [CONTRIBUTING.md](CONTRIBUTING.md#ci-scope) に従い、変更の影響範囲に合わせて行います。変更や新しい問題がなければ、記録済みの検証結果を再利用してください。PR 提出・マージ前には最新 main との差分と競合を確認し、取り込みや追加修正が影響する検証をやり直します。

PR の説明は日本語または英語で、次の内容を記載します。

- 目的・背景と、何をなぜ変えたか
- 実行した検証と結果、未実施・失敗した項目
- 本番への影響範囲と残る制約

### マージと本番公開

**main へのマージと本番デプロイは、プロダクトオーナー `genellect` のみが行えます。それぞれの操作に、オーナー本人の明示的指示が必要です。** 実装や PR 作成の依頼には含まれません。マージで本番の自動デプロイが始まる場合も、公開まで許可されていることを確認してください。保護ルールや必須チェックを無効化して通してはいけません。

### 品質とデータ

原画像と修正履歴を守り、測定は元の画素値で行います。マスク・測定値・統計・図の版を一致させ、計算方法の変更には版の更新と数値テストを伴わせてください。欠測をゼロにせず、細胞数と独立した実験の数を区別します。

非公開の研究データや認証情報は、Git・ログ・PR・CI・開発用 AI に持ち込まないでください。製品の LLM 送信は、利用者が明示的に有効にした範囲に限ります。外部送信・課金・設定変更は、現在の許可に従います。

[開発上の詳細規則](docs/development-standards.md)は、変更に関係する節を必ず読んでください。研究データ、モデルと依存関係、画面設計、配布の既存ルールを引き継いでいます。実装、CI 通過、公開、実環境での動作、科学的な検証は区別して報告し、未完了の事項は [roadmap](docs/roadmap.md) に残します。

## English

### Purpose

Cytellect measures cell counts, areas and fluorescence intensity from microscopy images, then produces statistics and publication figures. Our goal is for researchers to enter their images and research question and complete the analysis in one workspace. Reduce repeated setup for individual images and manual transfers of measurement tables between tools.

Improve nucleolar and cytoplasmic detection through model fine-tuning, and use an LLM to propose settings suited to the research question. Researchers can review and correct detections and settings; a shared analysis implementation performs the calculations. Evaluate detection accuracy, measurement error and correction time using real images.

Keep the analysis code open source. Cloud execution, collaboration and operational support are candidates for paid services. Do not turn the current local setup or supported image types into permanent product limits.

### Before starting

Before any change, read this file, [CLAUDE.md](CLAUDE.md) and instructions for the affected directories. Read them again when resuming work or after instructions change. Before changing behavior, also read the [requirements](docs/requirements.md), [scientific contract](docs/methods.md) and [data protection rules](docs/security.md). Treat dated handoffs as history; follow the current request and implementation.

Check the checkout and branch with `git status`, then always run `git fetch origin main`. Start new work from the latest `origin/main`; integrate it into an existing branch by merge or a safe rebase. Resolve fetch or integration failures before editing. Never discard uncommitted work or another contributor's changes.

Normally use a task-specific `git worktree` and feature branch. Reuse that worktree for the same task and do not edit a checkout someone else is using. If worktrees are unavailable, use an isolated checkout and explain why in the PR.

### Changes and pull requests

All changes follow **feature branch → PR → review → merge**. Never push directly to `main`. Keep each PR focused on one purpose.

Another person must review collaborator changes. Only `genellect`'s own changes may omit review; using the `genellect` account does not make someone else's changes exempt. PRs and mandatory CI apply to everyone.

Follow [CONTRIBUTING.md](CONTRIBUTING.md#ci-scope) to select checks for the affected areas. Reuse recorded results unless changes or new findings warrant rerunning them. Before submitting or merging a PR, check differences and conflicts against current main. Rerun checks affected by integration or further edits.

Write PR descriptions in Japanese or English and include:

- Purpose, background, and what changed and why.
- Checks run and their results, including unrun or failed checks.
- Production impact and remaining limitations.

### Merge and production release

**Only product owner `genellect` may merge into main or deploy to production. Each action requires the owner's explicit instruction.** Requests to implement changes or open a PR do not grant that permission. If a merge triggers automatic production deployment, confirm that publication is also authorized. Never disable protection rules or mandatory checks to get a change through.

### Quality and data

Preserve original images and edit history; measure original pixel values. Keep masks, measurements, statistics and figures tied to matching revisions. Changes to calculations require version updates and numerical tests. Missing values are not zero, and cell counts are not counts of independent experiments.

Keep private research data and credentials out of Git, logs, PRs, CI and development AI tools. Product LLM requests must stay within the user's explicit settings. Follow current authorization for external transmission, spending and settings changes.

Before editing, read the relevant sections of the [development standards](docs/development-standards.md). They retain the existing rules for research data, models and dependencies, interface design and distribution. Report implementation, CI, publication, deployed behavior and scientific validation separately. Keep unfinished work in the [roadmap](docs/roadmap.md).
