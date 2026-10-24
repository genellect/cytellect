# 開発への参加

開発の進め方、Git の運用、レビュー、研究データの扱い、AI エージェントの利用は、[チーム開発ルール](docs/team-development.md)で定めています。開発に参加する前に必ず読んでください。この文書には、開発環境の起動と、PR を出すまでの最低限の手順だけをまとめます。

- [チーム開発ルール](docs/team-development.md)：開発の流れ、ブランチと PR、レビュー、研究データの区分
- [要件](docs/requirements.md)と [Development standards](docs/development-standards.md)：実装の目標と、計算・統計・UI・データなど領域ごとの技術基準
- [AGENTS.md](AGENTS.md)：AI エージェント向けの指示
- [CI の範囲と検査](docs/ci.md)：PR と `main` で実行されるジョブ、CI だけで行う検査

## 必要なもの

- Python 3.12、Node.js 24（版は `.node-version`）、pnpm 11.19.0、uv 0.12.2
- Linux x64 または Windows x64（Fiji の固定版はこの 2 つだけです）
- 日本語フォント：図の出力とテストに必要です。Linux では `fonts-noto-cjk` を導入してください。
- 非公開の研究データは checkout の外に置き、開発環境・CI・開発用 AI に渡しません（[チーム開発ルール §6](docs/team-development.md)）。

## ローカル開発

依存パッケージと Fiji を導入します。Fiji と Cellpose-SAM の導入先は、checkout の外を指定します。

```bash
python3 scripts/dev.py setup --fiji ~/cytellect-fiji
python3 scripts/dev.py setup --cellpose ~/cytellect-cellpose   # 任意：Cellpose-SAM（約 2.5 GB）
```

API、ワーカー、Web を、それぞれ別の端末で起動します。API とワーカーの端末では、最初に同じ環境変数を設定します。

```bash
export CYTELLECT_DATA_DIR=~/cytellect-data CYTELLECT_FIJI_EXECUTABLE=~/cytellect-fiji CYTELLECT_SECURE_COOKIES=false
uv run cytellect invite --hours 24   # 招待コードを表示（初回のみ）
uv run cytellect serve               # 端末 1：API（127.0.0.1:8000）
uv run cytellect-worker              # 端末 2：計算ワーカー
pnpm dev                             # 端末 3：Web（http://localhost:3000）
```

ブラウザで `http://localhost:3000/workspace` を開き、招待コードを入力します。API は Origin を完全一致で照合するため、`127.0.0.1` ではなく `localhost` で開いてください。Cellpose-SAM を導入した場合は、`setup` が最後に表示する `CYTELLECT_CELLPOSE_PYTHON` と `CYTELLECT_CELLPOSE_MODEL_DIR` も、API とワーカーの端末で設定します。

## クラウド開発（Claude Code・Codex）

クラウドの開発環境では、環境の設定にセットアップスクリプトを指定します。

| ツール | セットアップスクリプト |
|---|---|
| Claude Code | `bash .claude/cloud-setup.sh` |
| Codex | `bash .codex/setup.sh` |

- Claude Code では、作業するシェルで最初に `source "$HOME/.local/share/cytellect-cloud/env.sh"` を実行します。固定版の Node.js と、環境が用意する Chromium の場所が設定されます。
- Fiji は既定では導入しません。必要な場合は、`CYTELLECT_SETUP_FIJI=1` と、checkout の外を指す `CYTELLECT_FIJI_EXECUTABLE` を設定してからセットアップします。
- セットアップスクリプトは日本語フォントを導入しません。フォントがない環境では、図を出力するテスト（約 20 件）が `figure_font_glyphs_unavailable` で失敗します。
- 使ってよいのは公開パッケージと公開データだけです。非公開の研究データや認証情報を、クラウド環境に置かないでください。

## PR を出す前に

変更に応じて、次の検査を実行します。`check` は、PR の CI の `python` ジョブと `web` ジョブと同じコマンドを実行します。

```bash
python3 scripts/dev.py check           # すべての変更（python または web に絞れます）
python3 scripts/dev.py check --fiji    # 解析エンジンを変更した場合（実 Fiji の試験を追加）
python3 scripts/dev.py contracts       # API を変更した場合（OpenAPI・既定レシピ・TypeScript の型を一緒にコミット）
python3 scripts/dev.py audit           # 依存パッケージを変更した場合（結果は checkout の外に出力）
```

ブラウザ・コンテナ・Windows の試験は CI だけで実行します（[CI の範囲と検査](docs/ci.md)）。PR は [PR テンプレート](.github/pull_request_template.md)に沿って、変更内容、科学的な影響、検証、残る制約を書きます。計算や統計を変える場合の基準は [Development standards](docs/development-standards.md) に従います。
