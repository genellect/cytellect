# 開発への参加

Cytellect の開発は、[チーム開発ルール](docs/team-development.md)に沿って進める。開発の流れ、Git とレビューの運用、研究データの扱い、AI エージェントとの協働は、まずそちらを読む。この文書は、開発環境を立ち上げて最初の PR を出すまでを扱う。

作業を始める前に、人も AI エージェントも守る[開発の原則](docs/development-principles.md)のうち、作業に関係する節を必ず読む。PR でどの CI ジョブが実行されるかは、[CI の構成](docs/ci.md)にある。

研究データと認証情報は、[チーム開発ルール §6](docs/team-development.md#6-研究データの扱い)に従って扱う。試験と動作確認には[登録済みの公開画像](fixtures/public)だけを使う。

## クラウド開発

手元に何も入れずに、道具と Fiji が揃った環境ですぐに始められる。Claude Code や Codex のクラウド環境では、環境の設定に次のセットアップスクリプトを登録する。

| ツール | セットアップスクリプト |
|---|---|
| Claude Code | `bash .claude/cloud-setup.sh` |
| Codex | `bash .codex/setup.sh` |

Claude Code のスクリプトは、固定版の Node.js、pnpm、uv と、日本語フォント、Fiji を揃え、実際の Fiji での試験まで行う（初回は約 9 分）。Codex で Fiji も使うときは、`CYTELLECT_SETUP_FIJI=1` と、checkout の外を指す `CYTELLECT_FIJI_EXECUTABLE` を設定してからセットアップする。

Claude Code の環境の設定（セッションのタイトルバーのクラウド環境のメニュー → Edit）には、[外部サービス](#外部サービス)の環境変数も登録する。登録した値は新しいセッションから読み込まれ、セットアップスクリプトからは読めない。ネットワークは、パッケージマネージャーの既定の接続先に加えて、次の接続先を許可する。

| 用途 | 接続先 |
|---|---|
| Node.js、uv | `nodejs.org`、`github.com`、`release-assets.githubusercontent.com` |
| Fiji | `downloads.imagej.net`、`sites.imagej.net`、`repo.maven.apache.org` |
| 日本語フォント | `archive.ubuntu.com`、`azure.archive.ubuntu.com`、`mirrors.edge.kernel.org` |
| 公開画像 | `bbbc.broadinstitute.org`、`cellpainting-gallery.s3.amazonaws.com`、`zenodo.org` |
| 外部サービス | `*.modal.direct`、`*.workers.dev` |

作業を始めるシェルでは、最初に `env.sh` を読み込み、準備を確かめてから起動する。`env.sh` は、固定版の道具と Fiji、試験に使う Chromium、クラウド GPU の接続キーを設定する。

```bash
source "$HOME/.local/share/cytellect-cloud/env.sh"
python3 scripts/dev.py doctor   # 道具、フォント、Fiji、外部サービスの設定を確認
python3 scripts/dev.py serve    # Web をビルドして API・計算ワーカーと起動し、招待コードを表示
```

クラウド環境の `localhost` は手元のブラウザからは開けないため、画面は環境の中の Playwright で確かめる。

## ローカル開発

手元のブラウザで画面を直接操作でき、編集もすぐに確かめられる。Python 3.12、Node.js 24（`.node-version`）、pnpm 11.19.0、uv 0.12.2 を用意する。Linux と Windows のどちらでも開発でき、Fiji はそれぞれの固定版を使う。Linux では、図の描画に使う日本語フォント `fonts-noto-cjk` も入れておく。

依存パッケージと Fiji を揃え、準備を確かめてから起動する。Fiji と作業データは checkout の外に置く。

```bash
python3 scripts/dev.py setup --fiji ~/cytellect-fiji
export CYTELLECT_FIJI_EXECUTABLE=~/cytellect-fiji
python3 scripts/dev.py doctor   # 道具、フォント、Fiji、外部サービスの設定を確認
python3 scripts/dev.py serve    # Web をビルドして API・計算ワーカーと起動し、招待コードを表示
```

ブラウザで `http://localhost:3000/workspace` を開き、招待コードを入力する。API は接続元の Origin を厳密に照合するため、`127.0.0.1` ではなく `localhost` を使う。`serve` は研究室の PC と同じ設定で動き、Ctrl-C で全体が止まる。作業データの既定の場所は `~/cytellect-data` で、Web を変えていなければ `--skip-build` でビルドを省ける。`serve` は Linux 向けで、Windows では下の 3 つの端末で起動する。

画面を編集しながら確かめるときは、変更がすぐ反映される開発サーバーを使う。API、計算ワーカー、Web を別の端末で起動し、API とワーカーの端末には同じ環境変数を設定する。

```bash
export CYTELLECT_DATA_DIR=~/cytellect-data CYTELLECT_FIJI_EXECUTABLE=~/cytellect-fiji CYTELLECT_SECURE_COOKIES=false
uv run cytellect invite --hours 24   # 招待コードを発行（初回のみ）
uv run cytellect serve               # 端末 1：API
uv run cytellect-worker              # 端末 2：計算ワーカー
pnpm dev                             # 端末 3：Web
```

## 外部サービス

核小体・細胞質の検出（Cellpose-SAM）と解析提案（LLM）は、次の設定があるときに使える。認証情報はオーナーから受け取り、チャット、コミット、ログには書かない。

| 機能 | 設定 |
|---|---|
| Cellpose-SAM（クラウド GPU） | `CYTELLECT_MODAL_PROXY_KEY` と `CYTELLECT_MODAL_PROXY_SECRET`：Modal の接続用トークンの ID（`wk-…`）と Secret（`ws-…`）（[クラウド GPU](docs/cloud-gpu.ja.md#開発環境から使う)） |
| Cellpose-SAM（CPU） | `python3 scripts/dev.py setup --cellpose ~/cytellect-cellpose`（約 2.5 GB）。最後に表示される `CYTELLECT_CELLPOSE_PYTHON` と `CYTELLECT_CELLPOSE_MODEL_DIR` を設定する |
| 解析提案 | `CYTELLECT_PROPOSAL_URL` と `CYTELLECT_PROPOSAL_TOKEN`：Worker の URL と、この環境の端末トークン（[解析提案](docs/proposal-service.md#development-environments)） |

`doctor` は、外部サービスが未設定なら `[--]`、不調なら `[!!]` を示し、どちらの場合も Fiji と画面の開発は続けられる。`doctor --live` は実際に接続して確かめる。このとき停止中の GPU が起動し、約 3 分かかって使った秒数だけ課金される。解析提案は空の依頼でトークンだけを確かめ、モデルは呼ばない。外部サービスも必須とするときは `--require-cloud` を付ける。

## PR を出す前に

`check` は、PR の CI と同じ検査を手元で再現する。変更の内容に応じて、次のコマンドを実行する。

```bash
python3 scripts/dev.py check           # すべての変更で（python や web に絞ることもできる）
python3 scripts/dev.py check --fiji    # 解析エンジンを変えたとき、実際の Fiji での試験も
python3 scripts/dev.py contracts       # API を変えたとき（OpenAPI、既定レシピ、TypeScript の型を一緒にコミット）
python3 scripts/dev.py audit           # 依存パッケージを変えたとき（結果は checkout の外に保存）
```

ブラウザ、コンテナ、Windows の統合試験は CI が担う（[CI の構成](docs/ci.md)）。ブラウザの試験を手元で行うときは、`serve` を起動したまま、CI の `fiji-browser` ジョブ（[ci.yml](.github/workflows/ci.yml)）と同じ手順で公開画像を準備して `pnpm test:e2e` を実行する。`CYTELLECT_TEST_DATA_DIR` には `serve` の作業データの場所を指定する。PR の説明は、[PR テンプレート](.github/pull_request_template.md)のすべての項目を書く。
