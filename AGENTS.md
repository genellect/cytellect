# Cytellect Development Guide

## 日本語

### プロダクト

Cytellect は、顕微鏡画像の解析から統計、論文用グラフの作成までをつなぐ、研究者のためのソフトウェアです。

画像と研究目的から解析条件を組み立て、検出・測定・統計・作図を一つのワークスペースで進める。繰り返しの設定やデータの転記を減らし、必要な箇所を確認・修正できる体験を目指します。開発では、核小体・細胞質の検出モデルの追加学習と、自然言語による解析設定の支援を進めます。

解析コードは公開を続け、クラウド実行・共同利用・運用支援を商用化の候補とします。現在のローカル構成や対応画像の範囲は、その時点の実装範囲として扱います。

### 作業の基本

この文書を、人とエージェントに共通する開発ルールの正本とします。エージェントは変更前に必ず `AGENTS.md`、[CLAUDE.md](CLAUDE.md)、対象ディレクトリの指示を読み、作業再開時・指示更新時にも確認します。

- **最新 main を取り込む。** 作業開始前に `git status` で状態を確認し、`git fetch origin main` を実行する。新規ブランチは最新 `origin/main` から作成し、継続ブランチには merge または安全な rebase で取り込む。取得・統合の失敗は変更前に解消し、既存の未コミット作業や他者の変更を保持する。
- **作業場所を分ける。** 原則、タスク専用の `git worktree` と feature ブランチを使う。同じタスクではその worktree を継続利用し、他者が使用中の checkout は編集しない。worktree を使えない場合は独立した checkout を用意し、理由を PR に記載する。
- **変更を一つの目的に絞る。** 既存の責務分担と実装を確認し、必要な範囲を変更する。関連する仕様・テストを同時に更新し、無関係な修正を混ぜない。

動作を変える前に、[要件](docs/requirements.md)・[計算仕様](docs/methods.md)・[データ保護](docs/security.md)を確認します。日付付きの引き継ぎは履歴です。現在の依頼と照合し、古い作業指示や公開許可を引き継がないでください。

### 検証とレビュー

すべての変更は **feature ブランチ → Pull Request → レビュー → マージ**を経由します。`main` への直接 push は禁止です。

ローカルでは変更に対応する検証を行い、PR では既存の必須 CI を満たします。コマンドと対象範囲は [CONTRIBUTING.md](CONTRIBUTING.md) を参照してください。変更や新しい問題がない限り、記録済みの合格結果を再利用できます。PR 提出・マージ前に最新 main との差分と競合を確認し、取り込みや追加修正が影響する検証を再実行します。

PR の説明は日本語または英語で、**目的・背景、何をなぜ変えたか、検証結果、本番への影響範囲**を記載します。実行コマンドと結果を示し、未実施・失敗・残る制約を区別してください。

共同編集者の変更には、別の人によるレビューが必要です。レビューを省略できるのは、プロダクトオーナー `genellect` 自身の変更に限ります。操作に使ったアカウントではなく、変更の主体で判断します。オーナーの変更にも PR と必須 CI は適用します。

### マージと本番公開

main へのマージと本番デプロイは、**`genellect` 本人の明示的指示を受けて、オーナー権限でのみ**行います。実装・コミット・push・PR 作成の依頼には、マージや本番公開の許可を含みません。

マージで本番デプロイが起動する場合は、公開まで含む指示であることを確認します。保護ルールを弱めたり、必須チェックを迂回したりしてマージしてはいけません。

### 設計・品質の基準

[Development standards](docs/development-standards.md) に、計算の再現性、API 契約、研究データ、モデル、UI、配布の基準を定めています。変更する領域の節を必ず読み、適用してください。

実装、CI 通過、配布・公開、実環境での動作、科学的な検証は、それぞれ確認した事実として報告します。未完了の事項は [roadmap](docs/roadmap.md) に残します。

## English

### Product

Cytellect is software for researchers that connects microscopy analysis, statistics and publication figures.

Our goal is one workspace where images and a research question lead to analysis settings, detection, measurement, statistics and figures. Reduce repeated setup and manual data transfers while keeping results open to review and correction. Development focuses on fine-tuning nucleolar and cytoplasmic detection and supporting analysis configuration through natural language.

Keep the analysis code open source. Cloud execution, collaboration and operational support are candidates for commercial services. Treat the current local setup and supported image types as the present implementation scope.

### Working principles

This document is the shared source of development rules for people and agents. Before any change, agents must read `AGENTS.md`, [CLAUDE.md](CLAUDE.md) and instructions for the affected directories. Recheck them when resuming work or when instructions change.

- **Integrate current main.** Before starting, inspect `git status` and run `git fetch origin main`. Create new branches from the latest `origin/main`; integrate it into continuing branches by merge or a safe rebase. Resolve fetch or integration failures before editing. Preserve uncommitted work and other contributors' changes.
- **Use an isolated checkout.** Normally use a task-specific `git worktree` and feature branch. Continue in that worktree for the same task; do not edit another contributor's active checkout. If worktrees are unavailable, use an isolated checkout and record the reason in the PR.
- **Keep changes focused.** Understand the existing responsibilities and implementation, then change what the task requires. Update affected specifications and tests together. Keep unrelated changes separate.

Before changing behavior, read the [requirements](docs/requirements.md), [scientific contract](docs/methods.md) and [data protection rules](docs/security.md). Dated handoffs are historical records. Check them against the current request; do not carry forward old task instructions or release permissions.

### Validation and review

All changes follow **feature branch → Pull Request → review → merge**. Direct pushes to `main` are prohibited.

Run local checks for the affected behavior and satisfy the existing mandatory CI. [CONTRIBUTING.md](CONTRIBUTING.md) defines commands and scope. Reuse recorded passing results unless changes or new findings invalidate them. Before submitting or merging a PR, check differences and conflicts against current main. Rerun checks affected by integration or additional edits.

In Japanese or English, describe the PR's **purpose and background, what changed and why, validation results, and production impact**. Include commands and outcomes, and distinguish unrun checks, failures and remaining limitations.

Collaborator changes require review by another person. Only product owner `genellect`'s own changes may omit review. The exception depends on whose change it is, not which account operates the tools. Owner changes still require a PR and mandatory CI.

### Merge and production release

Merging into main and deploying to production require **an explicit instruction from `genellect` for that action and may be performed only with the owner's authority**. Requests to implement, commit, push or open a PR do not authorize merging or production release.

If merging triggers a production deployment, confirm that publication is included in the instruction. Do not weaken protections or bypass mandatory checks to merge a change.

### Design and quality standards

[Development standards](docs/development-standards.md) defines requirements for reproducible calculations, API contracts, research data, models, UI and distribution. Read and apply the sections relevant to the change.

Report implementation, passing CI, distribution or publication, deployed behavior and scientific validation as separate verified facts. Keep unfinished work in the [roadmap](docs/roadmap.md).
