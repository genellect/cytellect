# Cytellect Development Guide

日本語版と英語版は同じ内容です。変更する場合は、同じ PR で両方を更新してください。
The Japanese and English sections are equivalent. Update both in the same PR.

## 日本語

### プロダクト

Cytellect は、顕微鏡画像の解析から統計、論文用グラフの作成までをつなぐ、研究者のためのソフトウェアです。

目指すのは、画像と研究目的から解析条件を組み立て、検出・測定・統計・作図までを一つのワークスペースで進められる体験です。繰り返しの設定やデータの転記を減らしながら、結果はいつでも確認・修正できるようにします。現在は、核小体・細胞質の検出モデルの追加学習と、自然言語による解析設定の支援に取り組んでいます。

解析コードは Apache-2.0 で公開を続けます。クラウド実行・共同利用・運用支援を商用提供の候補としているため、測定・統計の実装を一つに保ち、ローカル版と将来のホスト型 API の境界を崩さない設計にします。現在のローカル構成や対応画像は現時点の実装範囲であり、製品の上限ではありません。

### 常に守ること

次の事項は、変更の領域や作業の種類にかかわらず適用します。詳細は [Development standards](docs/development-standards.md) と [データ保護](docs/security.md) に従います。

- 非公開の研究画像・論文・ファイルパス・研究結果・参加者情報と、認証情報・トークンを、コード・ログ・Issue・PR・スクリーンショット・CI・外部 AI に含めない。
- 原画像の画素値を変更しない。測定値と統計は、API と解析パッケージの共通実装だけが生成する。
- 有意差を得るための調整や、失敗した視野の無断除外を行わない。
- 未実施・失敗した検証を、合格として報告しない。

### 作業の基本

この文書を、人とエージェントに共通する開発ルールの正本とします。エージェントは変更前に、この文書、使用するツール固有の指示（Claude Code の場合は [CLAUDE.md](CLAUDE.md)）、対象ディレクトリの指示を読み、作業再開時・指示更新時にも確認します。

- **最新 main を取り込む。** 作業開始前に `git status` で状態を確認し、`git fetch origin main` を実行する。新規ブランチは最新の `origin/main` から作成し、継続中のブランチには merge または安全な rebase で取り込む。取得・統合の失敗は変更前に解消し、未コミットの作業や他者の変更を保持する。
- **作業場所を分ける。** 並行して作業する場合は、タスクごとの `git worktree` または独立した checkout と feature ブランチを使う。他者やほかのエージェントが使用中の checkout は編集しない。
- **変更を一つの目的に絞る。** 既存の責務分担と実装を確認し、必要な範囲を変更する。関連する仕様・テストを同時に更新し、無関係な修正を混ぜない。

動作を変える前に、[要件](docs/requirements.md)・[計算仕様](docs/methods.md)・[データ保護](docs/security.md)を確認します。日付付きの引き継ぎは履歴です。現在の依頼と照合し、古い作業指示や公開許可を引き継がないでください。

### 検証とレビュー

すべての変更は **feature ブランチ → Pull Request → 必須 CI → マージ** を経由し、オーナー以外の変更にはレビューが加わります。`main` への直接 push は禁止です。

ローカルでは変更に対応する検証を行い、PR ではブランチ保護の必須 CI を満たします。コマンドと CI の対象範囲は [CONTRIBUTING.md](CONTRIBUTING.md) を参照してください。同じコミット・同じ条件で記録した合格結果は、その後の変更や新しい問題で無効にならない限り再利用できます。PR 提出・マージ前に最新 main との差分と競合を確認し、取り込みや追加修正が影響する検証を再実行します。

PR の説明は日本語または英語で、[PR テンプレート](.github/pull_request_template.md)の項目（変更内容、科学的な影響、検証、残る制約）に沿って記載し、本番への影響も明記します。実行したコマンドと結果を示し、未実施・失敗・残る制約を区別してください。

プロダクトオーナー（`genellect`）以外の変更には、作成者とは別の人によるレビューが必要です。オーナー自身の変更に限り、レビューを省略できます。この例外は、操作したアカウントではなく、変更を依頼・作成した人で判断します。オーナーのアカウントで動くエージェントが共同編集者の依頼で作成した変更にも、レビューが必要です。オーナーの変更にも PR と必須 CI は適用します。

### マージと本番公開

`main` へのマージは Vercel の本番デプロイを起動します。そのため、マージと本番公開はオーナーが判断します。エージェントがマージ・公開を行うのは、オーナーがその PR について明示的に指示した場合に限ります。実装・コミット・push・PR 作成の依頼には、マージや本番公開の許可は含まれません。

ブランチ保護を弱めたり、必須チェックを迂回したりしてマージしてはいけません。Windows 版の配布は、`main` へのマージとは別に、導入後の受入確認を経て行います。

### 設計・品質の基準

[Development standards](docs/development-standards.md) に、計算の再現性、API 契約、研究データ、モデル、UI、配布の基準を定めています。変更する領域の節を読み、適用してください。

実装、CI 通過、配布・公開、実環境での動作、科学的な検証は、それぞれ確認した事実として分けて報告します。未完了の事項は [roadmap](docs/roadmap.md) に残します。

## English

### Product

Cytellect is software for researchers that connects microscopy analysis, statistics and publication figures.

Our goal is one workspace where images and a research question lead to analysis settings, detection, measurement, statistics and figures. We reduce repeated setup and manual data transfers while keeping every result open to review and correction. Current work focuses on fine-tuning nucleolar and cytoplasmic detection and on supporting analysis configuration through natural language.

The analysis code remains open source under Apache-2.0. Cloud execution, collaboration and operational support are candidate commercial offerings, so keep one measurement and statistics implementation and preserve the boundary between local delivery and a future hosted API. The current local setup and supported image types describe today's implementation, not the product's limits.

### Always

These rules apply to every change and every kind of task. [Development standards](docs/development-standards.md) and [data protection rules](docs/security.md) give the details.

- Keep private research images, papers, file paths, study results, participant information, credentials and tokens out of code, logs, issues, PRs, screenshots, CI and external AI.
- Never modify original pixel values. Only the shared API and analysis package implementation produces measurements and statistics.
- Never tune for significance or silently discard failed fields.
- Never report unrun or failed checks as passed.

### Working principles

This document is the shared source of development rules for people and agents. Before any change, agents read this document, their tool-specific instructions ([CLAUDE.md](CLAUDE.md) for Claude Code) and instructions for the affected directories. Recheck them when resuming work or when instructions change.

- **Integrate current main.** Before starting, inspect `git status` and run `git fetch origin main`. Create new branches from the latest `origin/main`; integrate it into continuing branches by merge or a safe rebase. Resolve fetch or integration failures before editing. Preserve uncommitted work and other contributors' changes.
- **Separate working copies.** When working in parallel, use a task-specific `git worktree` or isolated checkout with a feature branch. Do not edit a checkout that another person or agent is using.
- **Keep changes focused.** Understand the existing responsibilities and implementation, then change what the task requires. Update affected specifications and tests together. Keep unrelated changes separate.

Before changing behavior, read the [requirements](docs/requirements.md), [scientific contract](docs/methods.md) and [data protection rules](docs/security.md). Dated handoffs are historical records. Check them against the current request; do not carry forward old task instructions or release permissions.

### Validation and review

All changes follow **feature branch → Pull Request → required CI → merge**, with review added for changes not made by the owner. Direct pushes to `main` are prohibited.

Run local checks for the affected behavior and satisfy the required CI in branch protection. [CONTRIBUTING.md](CONTRIBUTING.md) defines the commands and CI scope. A passing result recorded for the same commit and conditions may be reused unless later changes or new findings invalidate it. Before submitting or merging a PR, check differences and conflicts against current main, and rerun checks affected by integration or additional edits.

Write the PR description in Japanese or English, following the [PR template](.github/pull_request_template.md) (change, scientific impact, validation, remaining limits), and state the production impact. Include commands and outcomes, and distinguish unrun checks, failures and remaining limitations.

Changes by anyone other than the product owner (`genellect`) require review by someone other than the author. Only the owner's own changes may omit review. The exception depends on who requested or authored the change, not which account operated the tools: an agent running under the owner's account on a collaborator's behalf still requires review. Owner changes still require a PR and required CI.

### Merge and production release

Merging into `main` triggers a Vercel production deployment, so the owner decides merges and production releases. Agents merge or publish only when the owner explicitly instructs them to for that PR. Requests to implement, commit, push or open a PR do not authorize merging or production release.

Do not weaken branch protection or bypass required checks to merge a change. Windows distribution is separate from merging into `main` and requires installed-copy acceptance.

### Design and quality standards

[Development standards](docs/development-standards.md) defines requirements for reproducible calculations, API contracts, research data, models, UI and distribution. Read and apply the sections relevant to the change.

Report implementation, passing CI, distribution or publication, deployed behavior and scientific validation as separate verified facts. Keep unfinished work in the [roadmap](docs/roadmap.md).
