# 開発への参加

Cytellect の開発は、[チーム開発ルール](docs/team-development.md)に沿って進めます。開発の流れ、Git とレビューの運用、研究データの扱い、AI エージェントとの協働まで、まずはこちらに目を通してください。この文書では、開発環境を立ち上げて最初の PR を出すまでを案内します。

作業を始める前に、人も AI エージェントも守る[開発の原則](docs/development-principles.md)のうち、作業に関係する節を必ず読んでください。PR でどの CI ジョブが実行されるかは、[CI の構成](docs/ci.md)にまとめています。

## 必要な環境

Python 3.12、Node.js 24（`.node-version`）、pnpm 11.19.0、uv 0.12.2 を用意します。Linux と Windows のどちらでも開発でき、Fiji はそれぞれの固定版を使います。図の描画には日本語フォントを使うため、Linux では `fonts-noto-cjk` も入れておきます。

研究データと認証情報は、[チーム開発ルール §6](docs/team-development.md#6-研究データの扱い)に従って扱います。

## ローカル開発

依存パッケージと Fiji は一つのコマンドで揃います。Cellpose-SAM（約 2.5 GB）も使う場合は、続けて導入します。導入先はどちらも checkout の外を指定します。

```bash
python3 scripts/dev.py setup --fiji ~/cytellect-fiji
python3 scripts/dev.py setup --cellpose ~/cytellect-cellpose
```

API、計算ワーカー、Web は、それぞれ別の端末で起動します。API とワーカーの端末では、最初に同じ環境変数を設定してください。

```bash
export CYTELLECT_DATA_DIR=~/cytellect-data CYTELLECT_FIJI_EXECUTABLE=~/cytellect-fiji CYTELLECT_SECURE_COOKIES=false
uv run cytellect invite --hours 24   # 招待コードを発行（初回のみ）
uv run cytellect serve               # 端末 1：API
uv run cytellect-worker              # 端末 2：計算ワーカー
pnpm dev                             # 端末 3：Web
```

ブラウザで `http://localhost:3000/workspace` を開き、招待コードを入力すればワークスペースに入れます。API は接続元の Origin を厳密に照合するため、アドレスは `127.0.0.1` ではなく `localhost` を使います。Cellpose-SAM を導入した場合は、`setup` が最後に表示する `CYTELLECT_CELLPOSE_PYTHON` と `CYTELLECT_CELLPOSE_MODEL_DIR` も、API とワーカーの端末で設定します。

## クラウド開発

Claude Code や Codex のクラウド環境では、環境の設定にセットアップスクリプトを登録しておくと、依存パッケージが揃った状態で作業を始められます。

| ツール | セットアップスクリプト |
|---|---|
| Claude Code | `bash .claude/cloud-setup.sh` |
| Codex | `bash .codex/setup.sh` |

Claude Code では、作業を始めるシェルで `source "$HOME/.local/share/cytellect-cloud/env.sh"` を実行すると、固定版の Node.js とブラウザの試験に使う Chromium が使えるようになります。Fiji も必要なら、`CYTELLECT_SETUP_FIJI=1` と、checkout の外を指す `CYTELLECT_FIJI_EXECUTABLE` を設定してからセットアップします。図の描画に使う日本語フォント（`fonts-noto-cjk`）も、環境の設定で導入しておきます。


## PR を出す前に

`check` は、PR の CI と同じ検査を手元で再現します。変更の内容に応じて、次のコマンドを実行してください。

```bash
python3 scripts/dev.py check           # すべての変更で（python や web に絞ることもできます）
python3 scripts/dev.py check --fiji    # 解析エンジンを変えたとき、実際の Fiji での試験も
python3 scripts/dev.py contracts       # API を変えたとき（OpenAPI、既定レシピ、TypeScript の型を一緒にコミット）
python3 scripts/dev.py audit           # 依存パッケージを変えたとき（結果は checkout の外に保存）
```

ブラウザ、コンテナ、Windows の統合試験は CI が担います（[CI の構成](docs/ci.md)）。PR の説明は[テンプレート](.github/pull_request_template.md)に沿って、変更の内容、科学的な影響、検証、残る課題を書きます。
