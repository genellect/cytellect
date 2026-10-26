# 開発への参加

Cytellect の開発は、[チーム開発ルール](docs/team-development.md)に沿って進める。開発の流れ、Git とレビューの運用、研究データの扱い、AI エージェントとの協働は、まずそちらを読む。この文書は、開発環境を立ち上げて最初の PR を出すまでを扱う。

作業を始める前に、人も AI エージェントも守る[開発の原則](docs/development-principles.md)のうち、作業に関係する節を必ず読む。PR でどの CI ジョブが実行されるかは、[CI の構成](docs/ci.md)にある。

## 必要な環境

Python 3.12、Node.js 24（`.node-version`）、pnpm 11.19.0、uv 0.12.2 を用意する。Linux と Windows のどちらでも開発でき、Fiji はそれぞれの固定版を使う。図の描画には日本語フォントを使うため、Linux では `fonts-noto-cjk` も入れておく。

研究データと認証情報は、[チーム開発ルール §6](docs/team-development.md#6-研究データの扱い)に従って扱う。

## ローカル開発

依存パッケージと Fiji は一つのコマンドで揃う。Cellpose-SAM（約 2.5 GB）も使う場合は、続けて導入する。導入先はどちらも checkout の外を指定する。

```bash
python3 scripts/dev.py setup --fiji ~/cytellect-fiji
python3 scripts/dev.py setup --cellpose ~/cytellect-cellpose
```

API、計算ワーカー、Web は、それぞれ別の端末で起動する。API とワーカーの端末では、最初に同じ環境変数を設定する。

```bash
export CYTELLECT_DATA_DIR=~/cytellect-data CYTELLECT_FIJI_EXECUTABLE=~/cytellect-fiji CYTELLECT_SECURE_COOKIES=false
uv run cytellect invite --hours 24   # 招待コードを発行（初回のみ）
uv run cytellect serve               # 端末 1：API
uv run cytellect-worker              # 端末 2：計算ワーカー
pnpm dev                             # 端末 3：Web
```

ブラウザで `http://localhost:3000/workspace` を開き、招待コードを入力するとワークスペースに入れる。API は接続元の Origin を厳密に照合するため、アドレスは `127.0.0.1` ではなく `localhost` を使う。Cellpose-SAM を導入した場合は、`setup` が最後に表示する `CYTELLECT_CELLPOSE_PYTHON` と `CYTELLECT_CELLPOSE_MODEL_DIR` も、API とワーカーの端末で設定する。

## クラウド開発

Claude Code や Codex のクラウド環境では、環境の設定にセットアップスクリプトを登録しておくと、依存パッケージが揃った状態で作業を始められる。

| ツール | セットアップスクリプト |
|---|---|
| Claude Code | `bash .claude/cloud-setup.sh` |
| Codex | `bash .codex/setup.sh` |

Claude Code では、作業を始めるシェルで `source "$HOME/.local/share/cytellect-cloud/env.sh"` を実行すると、固定版の Node.js とブラウザの試験に使う Chromium が使えるようになる。Fiji も必要なら、`CYTELLECT_SETUP_FIJI=1` と、checkout の外を指す `CYTELLECT_FIJI_EXECUTABLE` を設定してからセットアップする。図の描画に使う日本語フォント（`fonts-noto-cjk`）も、環境の設定で導入しておく。


## PR を出す前に

`check` は、PR の CI と同じ検査を手元で再現する。変更の内容に応じて、次のコマンドを実行する。

```bash
python3 scripts/dev.py check           # すべての変更で（python や web に絞ることもできる）
python3 scripts/dev.py check --fiji    # 解析エンジンを変えたとき、実際の Fiji での試験も
python3 scripts/dev.py contracts       # API を変えたとき（OpenAPI、既定レシピ、TypeScript の型を一緒にコミット）
python3 scripts/dev.py audit           # 依存パッケージを変えたとき（結果は checkout の外に保存）
```

ブラウザ、コンテナ、Windows の統合試験は CI が担う（[CI の構成](docs/ci.md)）。PR の説明は、[PR テンプレート](.github/pull_request_template.md)のすべての項目を書く。
