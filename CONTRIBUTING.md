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

研究室の PC で動く版と同じ構成の解析画面を、Linux で起動して試す。構成は、解析 API、計算ワーカー、Web の本番ビルド、Fiji（核の検出）、クラウド GPU（核小体・細胞質の検出、Cellpose-SAM）、解析提案（LLM）である。試験には[登録済みの公開画像](fixtures/public)だけを使う。

```bash
python3 scripts/dev.py setup --fiji ~/cytellect-fiji
export CYTELLECT_FIJI_EXECUTABLE=~/cytellect-fiji
python3 scripts/dev.py doctor --live   # 道具、Fiji、クラウド GPU、解析提案の準備を確かめる
python3 scripts/dev.py serve           # API・ワーカー・Web の本番ビルドを起動し、招待コードを表示する
```

`doctor` は既定では外部に接続しない。`--live` を付けたときだけクラウド GPU と解析提案に問い合わせる。クラウド側の不調は警告（`[!!]`）として示し、Fiji と画面の開発は続けられる。失敗として扱うときは `--require-cloud` を付ける。`serve` は Web を本番と同じ形でビルドしてから起動し、`http://localhost:3000/workspace` と招待コードを表示する。Ctrl-C で全体が止まる。作業データは checkout の外（既定は `~/cytellect-data`）に置き、ログは一時ディレクトリに出す。

クラウド GPU と解析提案は、次の環境変数があるときだけ使える。値はオーナーから受け取り、各サービスの秘密の管理（クラウド環境では環境の設定）に置く。チャット、コミット、ログには書かない。

| 環境変数 | 内容 | 発行 |
|---|---|---|
| `CYTELLECT_MODAL_PROXY_KEY`、`CYTELLECT_MODAL_PROXY_SECRET` | Modal の接続用トークン（Proxy Auth Token）の ID（`wk-…`）と Secret（`ws-…`）。`dev.py` がつないで接続キーにし、デプロイ済みの GPU サーバーを接続先にする | オーナー（[クラウド GPU](docs/cloud-gpu.ja.md)） |
| `CYTELLECT_PROPOSAL_URL`、`CYTELLECT_PROPOSAL_TOKEN` | 解析提案の Worker の URL と、この環境の端末トークン | オーナーが招待コードから発行（[解析提案](docs/proposal-service.md#development-environments)） |

接続キーをそのまま渡す場合は `CYTELLECT_CELLPOSE_REMOTE_URL` と `CYTELLECT_CELLPOSE_REMOTE_TOKEN`（`wk-….ws-…`）を設定する。こちらが優先される。

費用に注意する。クラウド GPU は使った秒数で課金され（Modal の無料枠、支出の上限は 0 ドル）、`doctor --live` でも GPU が起動する。解析提案は月 5 ドルの予算と、端末ごとの月の回数の上限の中で動く。`doctor --live` の解析提案の確認は空の依頼だけを送り、モデルを呼ばない。Windows 版の導入と Docker 版は、この環境では再現せず CI で確かめる（[CI の構成](docs/ci.md)）。

## クラウド開発

Claude Code や Codex のクラウド環境では、環境の設定にセットアップスクリプトを登録しておくと、依存パッケージが揃った状態で作業を始められる。

| ツール | セットアップスクリプト |
|---|---|
| Claude Code | `bash .claude/cloud-setup.sh` |
| Codex | `bash .codex/setup.sh` |

Claude Code のセットアップスクリプトは、固定版の Node.js・pnpm・uv、日本語フォント（`fonts-noto-cjk`）、Fiji（checkout の外）を揃え、実際の Fiji での試験まで行う。作業を始めるシェルで `source "$HOME/.local/share/cytellect-cloud/env.sh"` を実行すると、固定版の道具、Fiji の場所、ブラウザの試験に使う Chromium、Modal の 2 つの変数から組み立てたクラウド GPU の接続キーと接続先が設定される。スクリプトは `env.sh` のうち自分が書く部分だけを差し替え、環境の設定が書いたほかの行は残す。続けて `python3 scripts/dev.py doctor` で準備を確かめ、[本番相当の環境](#本番相当の環境)を起動できる。

クラウド GPU と解析提案の環境変数は、環境の設定（セッションのタイトルバーのクラウド環境のメニュー → Edit）に登録する。登録した値は新しいセッションから読み込まれる。セットアップスクリプトはこれらの値を読めない。


## PR を出す前に

`check` は、PR の CI と同じ検査を手元で再現する。変更の内容に応じて、次のコマンドを実行する。

```bash
python3 scripts/dev.py check           # すべての変更で（python や web に絞ることもできる）
python3 scripts/dev.py check --fiji    # 解析エンジンを変えたとき、実際の Fiji での試験も
python3 scripts/dev.py contracts       # API を変えたとき（OpenAPI、既定レシピ、TypeScript の型を一緒にコミット）
python3 scripts/dev.py audit           # 依存パッケージを変えたとき（結果は checkout の外に保存）
```

ブラウザ、コンテナ、Windows の統合試験は CI が担う（[CI の構成](docs/ci.md)）。PR の説明は、[PR テンプレート](.github/pull_request_template.md)のすべての項目を書く。
