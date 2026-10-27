# 開発への参加

Cytellect の開発は、[チーム開発ルール](docs/team-development.md)に沿って進める。開発の流れ、Git とレビューの運用、研究データの扱い、AI エージェントとの協働は、まずそちらを読む。この文書は、開発環境を立ち上げて最初の PR を出すまでを扱う。

作業を始める前に、人も AI エージェントも守る[開発の原則](docs/development-principles.md)のうち、作業に関係する節を必ず読む。PR でどの CI ジョブが実行されるかは、[CI の構成](docs/ci.md)にある。

研究データと認証情報は、[チーム開発ルール §6](docs/team-development.md#6-研究データの扱い)に従って扱う。試験と動作確認には[登録済みの公開画像](fixtures/public)だけを使う。

設定の名前・用途・保存先は[開発環境の設定](docs/development-environment.md)にまとめている。Fiji と画面の開発は外部サービスのキーなしで進められる。Cellpose の GPU 推論や AI による解析提案も確認する場合は、[外部サービス](#外部サービス)の開発用認証情報をオーナーから受け取る。

## クラウド開発

固定版の開発ツールと Fiji を備えたクラウド環境で開発する。手元の PC への導入は不要で、画面は環境内のブラウザ（Playwright）で確認する。どちらの環境も、配布版と同じ固定ファイル（ロックファイル、Fiji の固定版、デプロイ済みの GPU サーバーと Worker）から作るため、機能が増えても手順は変わらない。環境の設定には、使うツールに応じたセットアップスクリプトを登録する。

| ツール | セットアップスクリプト |
|---|---|
| Claude Code | `bash .claude/cloud-setup.sh` |
| Codex | `bash .codex/setup.sh` |

Claude Code のスクリプトは、固定版の Node.js、pnpm、uv、日本語フォント、Fiji を導入し、実際の Fiji での試験まで行う。初回は約 9 分かかる。Codex で Fiji も使うときは、`CYTELLECT_SETUP_FIJI=1` と、checkout の外を指す `CYTELLECT_FIJI_EXECUTABLE` を設定してからセットアップする。

Claude Code の環境の設定（セッションのタイトルバーのクラウド環境のメニュー → Edit）には、[外部サービス](#外部サービス)の環境変数と、次の接続先も登録する。環境変数は新しいセッションから読み込まれ、セットアップスクリプトからは参照できない。Codex でも対象の開発環境に接続先と認証情報を登録し、作業するセッションで参照できることを確かめる。URL は通常の環境変数、トークンは秘密の値として管理する（[設定の保存先](docs/development-environment.md#設定の保存先)）。接続先は、パッケージマネージャーの既定の許可に加えて設定する。

| 用途 | 接続先 |
|---|---|
| Node.js、uv | `nodejs.org`、`github.com`、`release-assets.githubusercontent.com` |
| Fiji | `downloads.imagej.net`、`sites.imagej.net`、`repo.maven.apache.org` |
| 日本語フォント | `archive.ubuntu.com`、`azure.archive.ubuntu.com`、`mirrors.edge.kernel.org` |
| 公開画像 | `bbbc.broadinstitute.org`、`cellpainting-gallery.s3.amazonaws.com`、`zenodo.org` |
| 外部サービス | `*.modal.direct`、`*.workers.dev` |

作業を始めるシェルでは、`env.sh` を読み込んでから準備を確認し、起動する。`env.sh` は、固定版のツール、Fiji、試験用の Chromium の場所と、クラウド GPU の接続キーを設定する。

```bash
source "$HOME/.local/share/cytellect-cloud/env.sh"
python3 scripts/dev.py doctor   # ツール、フォント、Fiji、外部サービスの準備を確認
python3 scripts/dev.py serve    # Web をビルドして API・計算ワーカーと起動し、招待コードを表示
```

## ローカル開発

手元の PC で開発する。画面を手元のブラウザで操作でき、開発サーバーを使うと Web の変更がすぐに反映される。Python 3.12、Node.js、pnpm、uv を用意する。版は `.node-version`、`package.json` の `packageManager`、CI の uv の指定が正本で、`doctor` がこれらと照合する。Linux と Windows のどちらでも開発でき、Fiji はそれぞれの固定版を使う。Linux では、図の描画に使う日本語フォント `fonts-noto-cjk` も導入する。

依存パッケージと Fiji を導入し、準備を確認してから起動する。Fiji と作業データは checkout の外に置く。以下は checkout のルートから実行し、どちらも checkout の隣に置く例。Windows では `python3` を `python` に読み替える。

```bash
python3 scripts/dev.py setup --fiji ../cytellect-fiji
```

[`.env.example`](.env.example) をルートの `.env` にコピーし、Fiji と作業データの場所を確認する。既に `.env` がある場合は上書きせず、足りない項目だけを追加する。外部サービスを使う場合は、受け取った開発用の URL とトークンもここに設定する。テンプレートの認証情報は空欄で、取得先と使い分けは[設定一覧](docs/development-environment.md)にある。

`.env` は Git の対象外だが、置くだけでは Python の API・計算ワーカーには反映されない。`uv run --env-file .env --` を付けて読み込む。Web を含め、別の端末から起動するときも同じファイルを使う。

```bash
uv run --env-file .env -- python scripts/dev.py doctor
uv run --env-file .env -- python scripts/dev.py serve --data-dir ../cytellect-data
```

ブラウザで `http://localhost:3000/workspace` を開き、表示された招待コードを入力する。API は接続元の Origin を厳密に照合するため、`127.0.0.1` ではなく `localhost` を使う。`serve` は API・計算ワーカーと本番ビルドの Web を起動し、Ctrl-C で全体が止まる。`--data-dir` は `.env` の `CYTELLECT_DATA_DIR` と同じ場所を指定する。このオプションを省くと `~/cytellect-data` が使われる。Web を変えていなければ `--skip-build` でビルドを省ける。`serve` は Linux 向けで、Windows では下の 3 つの端末で起動する。

Web を編集しながら確認するときは、開発サーバーを使う。API、計算ワーカー、Web を別の端末で起動し、API とワーカーの端末には同じ環境変数を設定する。

```bash
uv run --env-file .env -- cytellect invite --hours 24   # 招待コードを発行（初回のみ）
uv run --env-file .env -- cytellect serve               # 端末 1：API
uv run --env-file .env -- cytellect-worker              # 端末 2：計算ワーカー
uv run --env-file .env -- pnpm dev                      # 端末 3：Web
```

この起動方法でクラウド GPU を使うときは、`.env` に `CYTELLECT_CELLPOSE_REMOTE_URL` と `CYTELLECT_CELLPOSE_REMOTE_TOKEN` を設定する。Modal の ID と Secret から接続キーを組み立てる処理は `scripts/dev.py` にあるため、計算ワーカーを直接起動する場合には結合済みの値が必要になる。

## 外部サービス

GPU 推論（Cellpose-SAM）と解析提案（LLM）は、次の設定があるときに使える。接続先と認証情報は、利用する機能・作業環境・利用期間をオーナーに伝えて受け取る。開発用の接続キー・端末トークンを使い、本番用や管理用のキーを流用しない。値はチャット、コミット、ログには書かない。

| 機能 | 必要な設定 | 入手・設定する人 |
|---|---|---|
| GPU 推論 | `CYTELLECT_CELLPOSE_REMOTE_URL` と `CYTELLECT_CELLPOSE_REMOTE_TOKEN`。Modal の接続用 ID と Secret をピリオドでつないだ値で認証する。`scripts/dev.py` 経由では `CYTELLECT_MODAL_PROXY_KEY` と `CYTELLECT_MODAL_PROXY_SECRET` からも設定できる（[クラウド GPU](docs/cloud-gpu.ja.md#開発環境から使う)） | オーナーが開発用の接続先と接続キーを提供し、開発メンバーが作業環境に登録する |
| CPU 推論（GPU 推論の代わり） | `python3 scripts/dev.py setup --cellpose ../cytellect-cellpose`（約 2.5 GB）。表示された `CYTELLECT_CELLPOSE_PYTHON` と `CYTELLECT_CELLPOSE_MODEL_DIR` を設定する | 開発メンバーが導入する。外部サービスのキーは不要 |
| 解析提案 | `CYTELLECT_PROPOSAL_URL` と `CYTELLECT_PROPOSAL_TOKEN`。Worker の URL と、この開発環境専用の端末トークン（[解析提案](docs/proposal-service.md#development-environments)） | オーナーが環境を登録してトークンを提供し、開発メンバーが作業環境に登録する |

通常の共同開発で使うのは、既存サービスを呼び出すための認証情報である。`MODAL_TOKEN_ID`・`MODAL_TOKEN_SECRET` は GPU サーバーのデプロイ用、`OPENAI_API_KEY`・`ADMIN_TOKEN` は提案サービスの運用者用で、開発用 `.env` には入れない。サービス自体の変更・検証を担当するときは、[管理・デプロイの設定](docs/development-environment.md#管理デプロイの設定)に従い、権限と費用をオーナーに確認する。

`doctor` は、外部サービスが未設定なら `[--]`、不調なら `[!!]` を示し、どちらの場合も Fiji と画面の開発は続けられる。`doctor --live` は実際に接続して確認する。このとき停止中の GPU が起動し、起動に約 3 分かかり、使った秒数に応じて課金される。解析提案は空の依頼でトークンだけを確認し、モデルは呼ばない。外部サービスも必須とするときは `--require-cloud` を付ける。

## PR を出す前に

`check` は、PR の CI と同じ検査を手元で再現する。変更の内容に応じて、次のコマンドを実行する。

```bash
python3 scripts/dev.py check           # すべての変更で（python や web に絞ることもできる）
python3 scripts/dev.py check --fiji    # 解析エンジンを変えたとき、実際の Fiji での試験も
python3 scripts/dev.py contracts       # API を変えたとき（OpenAPI、既定レシピ、TypeScript の型を一緒にコミット）
python3 scripts/dev.py audit           # 依存パッケージを変えたとき（結果は checkout の外に保存）
```

ブラウザ、コンテナ、Windows の統合試験は CI が担う（[CI の構成](docs/ci.md)）。ブラウザの試験を手元で行うときは、`serve` を起動したまま、CI の `fiji-browser` ジョブ（[ci.yml](.github/workflows/ci.yml)）と同じ手順で公開画像を準備して `pnpm test:e2e` を実行する。`CYTELLECT_TEST_DATA_DIR` には `serve` の作業データの場所を指定する。PR の説明は、[PR テンプレート](.github/pull_request_template.md)のすべての項目を書く。
