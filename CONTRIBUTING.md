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

## 本番相当の環境

研究室の PC と同じ構成の解析画面を、Linux で起動して試す。構成は、Web の本番ビルド、API、計算ワーカー、Fiji（核の検出）、クラウド GPU（Cellpose-SAM による核小体・細胞質の検出）、解析提案（LLM）である。試験には[登録済みの公開画像](fixtures/public)だけを使う。

```bash
python3 scripts/dev.py setup --fiji ~/cytellect-fiji
export CYTELLECT_FIJI_EXECUTABLE=~/cytellect-fiji
python3 scripts/dev.py doctor          # 準備の確認（外部には接続しない）
python3 scripts/dev.py doctor --live   # クラウド GPU と解析提案への接続も確認
python3 scripts/dev.py serve           # 本番ビルドで起動し、招待コードを表示（Ctrl-C で停止）
```

クラウド GPU と解析提案は、次の環境変数があるときに使われる。値はオーナーから受け取り、チャット、コミット、ログには書かない。

| 環境変数 | 内容 |
|---|---|
| `CYTELLECT_MODAL_PROXY_KEY`、`CYTELLECT_MODAL_PROXY_SECRET` | Modal の接続用トークンの ID（`wk-…`）と Secret（`ws-…`）（[クラウド GPU](docs/cloud-gpu.ja.md#開発環境から使う)） |
| `CYTELLECT_PROPOSAL_URL`、`CYTELLECT_PROPOSAL_TOKEN` | 解析提案の Worker の URL と、この環境の端末トークン（[解析提案](docs/proposal-service.md#development-environments)） |

`doctor` は、クラウド GPU と解析提案が未設定なら `[--]`、不調なら警告（`[!!]`）を示す。この間も Fiji と画面の開発は続けられる。どちらも失敗として扱うときは `--require-cloud` を付ける。`--live` は停止中の GPU を起動するため、約 3 分かかり、使った秒数だけ課金される。解析提案は空の依頼でトークンだけを確かめ、モデルは呼ばない。

`serve` は作業データを checkout の外（既定は `~/cytellect-data`）に置く。Web を変えていなければ、`--skip-build` でビルドを省ける。ブラウザの通しの試験は、`serve` を起動したまま、CI の `fiji-browser` ジョブ（[ci.yml](.github/workflows/ci.yml)）と同じく公開画像を準備して `pnpm test:e2e` を実行する。このとき `CYTELLECT_TEST_DATA_DIR` には `serve` の作業データの場所を指定する。Windows 版と Docker 版はこの環境では再現せず、CI で確かめる（[CI の構成](docs/ci.md)）。

## クラウド開発

Claude Code や Codex のクラウド環境では、環境の設定にセットアップスクリプトを登録しておくと、依存パッケージが揃った状態で作業を始められる。

| ツール | セットアップスクリプト |
|---|---|
| Claude Code | `bash .claude/cloud-setup.sh` |
| Codex | `bash .codex/setup.sh` |

Claude Code のスクリプトは、固定版の Node.js、pnpm、uv と、日本語フォント、Fiji（checkout の外）を揃え、実際の Fiji での試験まで行う。初回は約 9 分かかる。Codex で Fiji も使うときは、`CYTELLECT_SETUP_FIJI=1` と、checkout の外を指す `CYTELLECT_FIJI_EXECUTABLE` を設定してからセットアップする。

Claude Code の環境の設定（セッションのタイトルバーのクラウド環境のメニュー → Edit）には、[本番相当の環境](#本番相当の環境)の 4 つの環境変数も登録する。登録した値は新しいセッションから読み込まれ、セットアップスクリプトからは読めない。ネットワークは、パッケージマネージャーの既定の接続先に加えて、次の接続先を許可する。

| 用途 | 接続先 |
|---|---|
| Node.js、uv | `nodejs.org`、`github.com`、`release-assets.githubusercontent.com` |
| Fiji | `downloads.imagej.net`、`sites.imagej.net`、`repo.maven.apache.org` |
| 日本語フォント | `archive.ubuntu.com`、`azure.archive.ubuntu.com`、`mirrors.edge.kernel.org` |
| 公開画像 | `bbbc.broadinstitute.org`、`cellpainting-gallery.s3.amazonaws.com`、`zenodo.org` |
| クラウド GPU、解析提案 | `*.modal.direct`、`*.workers.dev` |

作業を始めるシェルでは、最初に `env.sh` を読み込む。固定版の Node.js、pnpm、uv、Fiji とブラウザの試験に使う Chromium の場所、クラウド GPU の接続キーが設定される。

```bash
source "$HOME/.local/share/cytellect-cloud/env.sh"
python3 scripts/dev.py doctor
python3 scripts/dev.py serve
```

クラウド環境の `localhost` は、手元のブラウザからは開けない。画面は、環境の中の Playwright（Chromium）で確かめる。

## PR を出す前に

`check` は、PR の CI と同じ検査を手元で再現する。変更の内容に応じて、次のコマンドを実行する。

```bash
python3 scripts/dev.py check           # すべての変更で（python や web に絞ることもできる）
python3 scripts/dev.py check --fiji    # 解析エンジンを変えたとき、実際の Fiji での試験も
python3 scripts/dev.py contracts       # API を変えたとき（OpenAPI、既定レシピ、TypeScript の型を一緒にコミット）
python3 scripts/dev.py audit           # 依存パッケージを変えたとき（結果は checkout の外に保存）
```

ブラウザ、コンテナ、Windows の統合試験は CI が担う（[CI の構成](docs/ci.md)）。PR の説明は、[PR テンプレート](.github/pull_request_template.md)のすべての項目を書く。
