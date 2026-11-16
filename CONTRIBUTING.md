# 開発への参加

開発環境の構築から最初の PR までを扱う。開発の進め方は[チーム開発ルール](docs/team-development.md)、守る原則は[開発の原則](docs/development-principles.md)、PR で実行される CI のジョブは [CI の構成](docs/ci.md)にある。研究データと認証情報は[チーム開発ルール §6](docs/team-development.md#6-研究データの扱い)に従って扱い、試験と動作確認には[登録済みの公開画像](fixtures/public)だけを使う。

## 必要環境

| ツール | 版 |
|---|---|
| Python | 3.12 |
| Node.js | `.node-version` |
| pnpm | `package.json` の `packageManager` |
| uv | CI の指定 |
| Fiji | `dev.py setup` が OS ごとの固定版を導入する |
| 日本語フォント（Linux） | `fonts-noto-cjk` |

`python3 scripts/dev.py doctor` がこれらを照合する。クラウド開発では、セットアップスクリプトがすべて導入する。

## クラウド開発

Claude Code・Codex のクラウド環境で、手元への導入なしに開発する。画面は環境内のブラウザ（Playwright）で確認する。コンテナは `dockerd` を起動すれば動かせる（外への接続には `--network host` と、環境のプロキシの CA が必要）。環境はロックファイル、Fiji の固定版、デプロイ済みの GPU サーバーと Worker から作るため、機能が増えても手順は変わらない。

1. 環境の設定にセットアップスクリプトを登録する。

   | ツール | セットアップスクリプト | 内容 |
   |---|---|---|
   | Claude Code | `bash cytellect/.claude/cloud-setup.sh` | Node.js、pnpm、uv、日本語フォント、依存パッケージ、Fiji を導入し、Fiji の試験まで行う。初回は約 9 分。セットアップスクリプトは checkout の親ディレクトリで始まるため、checkout のディレクトリ名（通常はリポジトリ名）から指定する |
   | Codex | `bash .codex/setup.sh` | Fiji も使う場合は、`CYTELLECT_SETUP_FIJI=1` と checkout の外を指す `CYTELLECT_FIJI_EXECUTABLE` を設定しておく |

2. ネットワークは制限なし（すべてのホストに届く設定）にする。オーナーの環境はこの設定で動いている。制限付きのネットワークで使う場合は、パッケージマネージャーの既定の許可に加えて、次の接続先を許可する。

   | 用途 | 接続先 |
   |---|---|
   | Node.js、uv | `nodejs.org`、`github.com`、`release-assets.githubusercontent.com` |
   | Fiji | `downloads.imagej.net`、`sites.imagej.net`、`repo.maven.apache.org` |
   | 日本語フォント | `archive.ubuntu.com`、`azure.archive.ubuntu.com`、`mirrors.edge.kernel.org` |
   | 公開画像 | `bbbc.broadinstitute.org`、`cellpainting-gallery.s3.amazonaws.com`、`zenodo.org` |
   | Cellpose のモデル（`setup --cellpose`） | `huggingface.co` と、大きなファイルの転送先 |
   | 外部サービス | `*.modal.direct`、`api.cytellect.app` |
   | 運用（[オーナーの環境](#オーナーの環境)） | `api.cloudflare.com`、`api.vercel.com`、`huggingface.co`、使う AWS のエンドポイント |

3. [外部サービス](#外部サービス)を使う場合は、その環境変数を環境の設定に登録する。Claude Code では、セッションのタイトルバーのクラウド環境のメニュー → Edit から設定する。環境変数は新しいセッションから読み込まれ、セットアップスクリプトからは参照できない。

4. セッションで起動する。`env.sh` は、固定版のツール、Fiji、試験用の Chromium の場所と、クラウド GPU の接続キーを設定する。

   ```bash
   source "$HOME/.local/share/cytellect-cloud/env.sh"
   python3 scripts/dev.py doctor   # ツール、フォント、Fiji、外部サービスの準備を確認
   python3 scripts/dev.py serve    # Web をビルドして API・計算ワーカーと起動し、招待コードを表示
   ```

## ローカル開発

```bash
python3 scripts/dev.py setup --fiji ~/cytellect-fiji
export CYTELLECT_FIJI_EXECUTABLE=~/cytellect-fiji
python3 scripts/dev.py doctor   # ツール、フォント、Fiji、外部サービスの準備を確認
python3 scripts/dev.py serve    # Web をビルドして API・計算ワーカーと起動し、招待コードを表示
```

`http://localhost:3000/workspace` を開き、招待コードを入力する。

- API は接続元の Origin を厳密に照合するため、`127.0.0.1` ではなく `localhost` を使う。
- Fiji と作業データは checkout の外に置く。作業データの既定の場所は `~/cytellect-data`。
- `serve` は研究室の PC と同じ設定で動き、Ctrl-C で全体が止まる。Web を変えていなければ `--skip-build` でビルドを省ける。
- `serve` は Linux 向け。Windows では、次の開発サーバーで起動する。

### 開発サーバー

Web の変更をすぐに反映させるときは、API、計算ワーカー、Web を別の端末で起動する。API と計算ワーカーの端末には同じ環境変数を設定する。

```bash
export CYTELLECT_DATA_DIR=~/cytellect-data CYTELLECT_FIJI_EXECUTABLE=~/cytellect-fiji CYTELLECT_SECURE_COOKIES=false
uv run cytellect invite --hours 24   # 招待コードを発行（初回のみ）
uv run cytellect serve               # 端末 1：API
uv run cytellect-worker              # 端末 2：計算ワーカー
pnpm dev                             # 端末 3：Web
```

## 環境変数

| 変数 | 用途 |
|---|---|
| `CYTELLECT_DATA_DIR` | 作業データの場所。checkout の外を指定する。`serve` では `--data-dir` で指定する（既定 `~/cytellect-data`） |
| `CYTELLECT_FIJI_EXECUTABLE` | `dev.py setup --fiji` で導入した Fiji の場所 |
| `CYTELLECT_SECURE_COOKIES` | 手元の HTTP で動かすときは `false`。`serve` は自動で設定する |

画面・測定・統計・Fiji の開発に必要なのはこれだけで、認証情報は要らない。

### 外部サービス

GPU 推論（Cellpose-SAM）と解析提案（LLM）は、次の環境変数を設定すると使える。クラウド開発では環境の設定に登録し、ローカル開発では API と計算ワーカーを起動するシェルに設定する。

| 変数 | 用途 | 入手先 |
|---|---|---|
| `CYTELLECT_MODAL_PROXY_KEY` / `CYTELLECT_MODAL_PROXY_SECRET` | GPU 推論の接続キーの ID（`wk-…`）と Secret（`ws-…`）。`dev.py` と `env.sh` が 2 つを結合し、接続先も設定する（[クラウド GPU](docs/cloud-gpu.ja.md#開発環境から使う)） | オーナー |
| `CYTELLECT_CELLPOSE_REMOTE_URL` / `CYTELLECT_CELLPOSE_REMOTE_TOKEN` | 開発サーバーで計算ワーカーを起動するときの、GPU サーバーの URL と、ID と Secret をピリオドでつないだ接続キー | オーナー |
| `CYTELLECT_CELLPOSE_PYTHON` / `CYTELLECT_CELLPOSE_MODEL_DIR` | GPU の代わりに CPU で推論する。`dev.py setup --cellpose ~/cytellect-cellpose`（約 2.5 GB）が最後に値を表示する | 不要 |
| `CYTELLECT_PROPOSAL_URL` / `CYTELLECT_PROPOSAL_TOKEN` | 解析提案の Worker の URL（`https://api.cytellect.app`）と、この開発環境の端末トークン（[解析提案](docs/proposal-service.md#development-environments)） | URL は公開。端末トークンはオーナー |

- 接続キーと端末トークンは、使う機能・開発環境・期間を伝えてオーナーから受け取る。端末トークンは開発環境ごとに発行し、ほかの環境と共有しない。
- 値はチャット、Issue、PR、コミット、ログ、スクリーンショットに書かない。`env` や `printenv` の出力も貼らない。
- 運用の認証情報は、[オーナーの環境](#オーナーの環境)に置く。
- 不要になった開発環境はオーナーに伝え、サービス側で失効してもらう。環境変数を消すだけでは失効しない。

`doctor` は、外部サービスが未設定なら `[--]`、不調なら `[!!]` を示し、どちらの場合も Fiji と画面の開発は続けられる。

| オプション | 動作 |
|---|---|
| `--live` | 実際に接続して確認する。停止中の GPU が起動する。GPU の空きを待つため起動にかかる時間は一定ではなく、動いた秒数に応じて課金される（[起動待ち](docs/cloud-gpu.ja.md#起動待ちと受入確認)）。解析提案は空の依頼でトークンだけを確認し、モデルは呼ばない |
| `--require-cloud` | 外部サービスも必須として確認する |

### オーナーの環境

オーナー（運用者）のクラウド環境は、ネットワークを制限せず、運用の認証情報も持つ。開発から運用までを同じセッションで行える。マージ・デプロイ・有料サービスの利用は、権限があっても、オーナーが対象を指示したときだけ行う（[AGENTS.md](AGENTS.md)）。

| サービス | 認証情報の置き場所 | クラウドセッションでの使い方 |
|---|---|---|
| GitHub | セッションの GitHub 接続（オーナーのアカウント） | REST の API と GitHub のコネクタ。GraphQL はクラウドセッションで使えないため、`gh pr list`・`gh pr merge` などは REST で行う（[マージ](docs/team-development.md#2-開発の流れ)） |
| Cloudflare（解析提案の Worker） | API トークンは `api.cloudflare.com` 宛てのネットワークシークレット。`CLOUDFLARE_ACCOUNT_ID` は環境変数 | `pnpm --filter @cytellect/proposal-worker cf <wrangler の引数>`。wrangler はロックファイルの固定版 |
| Vercel | トークンは `api.vercel.com` 宛てのネットワークシークレット。claude.ai の Vercel コネクタも使える | Vercel CLI またはコネクタ |
| Hugging Face | トークンは `huggingface.co` 宛てのネットワークシークレット。公開モデルの取得には要らない | `hf` CLI |
| AWS | 署名方式のため、環境変数（`AWS_ACCESS_KEY_ID`・`AWS_SECRET_ACCESS_KEY`） | AWS CLI |
| Modal（GPU サーバー） | `MODAL_TOKEN_ID`・`MODAL_TOKEN_SECRET` は GitHub の Actions の秘密の値 | Actions の「Cellpose Modal deploy」を `main` から起動する。Modal の CLI は gRPC がプロキシを通らないため、クラウドセッションから接続できない |
| OpenAI、`ADMIN_TOKEN`（解析提案の Worker） | Worker の secret（`cf secret put`） | セッションに置く必要はない |

ネットワークシークレットは、環境の設定の Network secrets に登録する。値はコンテナに入らず、環境のプロキシが通信に付ける。Vercel・Hugging Face・AWS の CLI は、セットアップスクリプトではまだ入らない（[#220](https://github.com/genellect/cytellect/issues/220)）。

## PR を出す前に

`check` は、PR の CI と同じ検査を手元で再現する。変更の内容に応じて、次のコマンドを実行する。

```bash
python3 scripts/dev.py check           # すべての変更で（python や web に絞ることもできる）
python3 scripts/dev.py check --fiji    # 解析エンジンを変えたとき、実際の Fiji での試験も
python3 scripts/dev.py contracts       # API を変えたとき（OpenAPI、既定レシピ、TypeScript の型を一緒にコミット）
python3 scripts/dev.py audit           # 依存パッケージを変えたとき（結果は checkout の外に保存）
```

ブラウザ、コンテナ、Windows の統合試験は CI が担う（[CI の構成](docs/ci.md)）。コンテナの試験は、クラウド環境でも `dockerd` を起動すれば手元で行える。ブラウザの試験を手元で行うときは、`serve` を起動したまま、CI の `browser-e2e` ジョブ（[ci.yml](.github/workflows/ci.yml)）と同じ手順で公開画像を準備して `pnpm test:e2e` を実行する。`CYTELLECT_TEST_DATA_DIR` には `serve` の作業データの場所を指定する。PR の説明は、[PR テンプレート](.github/pull_request_template.md)のすべての項目を書く。
