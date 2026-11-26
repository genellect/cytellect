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

`python3 scripts/dev.py doctor` がこれらを照合する。Linux（クラウド開発と WSL Ubuntu）では、段階的に入れる。[scripts/linux_setup.sh](scripts/linux_setup.sh) が固定版のツールと依存パッケージを入れ、Fiji と日本語フォントは、`dev.py` の `serve`・`check`・`e2e` が初めて必要になったときに入れる。

## クラウド開発

Claude Code・Codex のクラウド環境で、手元への導入なしに開発する。画面は環境内のブラウザ（Playwright）で確認する。コンテナは `dockerd` を起動すれば動かせる（外への接続には `--network host` と、環境のプロキシの CA が必要）。環境はロックファイル、Fiji の固定版、デプロイ済みの GPU サーバーと Worker から作るため、機能が増えても手順は変わらない。

1. 環境の設定にセットアップスクリプトを登録する。

   | ツール | セットアップスクリプト | 内容 |
   |---|---|---|
   | Claude Code | `bash cytellect/.claude/cloud-setup.sh` | `scripts/linux_setup.sh` で Node.js、pnpm、uv、依存パッケージを導入する。Fiji と日本語フォントは初めて使うときに入り、試験は PR の CI と `dev.py check` が担う。セットアップスクリプトは checkout の親ディレクトリで始まるため、checkout のディレクトリ名（通常はリポジトリ名）から指定する |
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
   | 運用（[オーナーの環境](#オーナーの環境)） | `api.cloudflare.com`、`api.vercel.com`、`huggingface.co` |

3. [外部サービス](#外部サービス)を使う場合は、その環境変数を環境の設定に登録する。Claude Code では、セッションのタイトルバーのクラウド環境のメニュー → Edit から設定する。環境変数は新しいセッションから読み込まれ、セットアップスクリプトからは参照できない。

4. セッションで起動する。`env.sh` は、固定版のツール、Fiji、試験用の Chromium の場所と、クラウド GPU の接続キーを設定する。Claude Code では、セッションの開始時にフック（[.claude/hooks/session-start.sh](.claude/hooks/session-start.sh)）が `env.sh` を読み込む設定をするため、各コマンドで固定版のツールが先に見つかる。ほかのシェルでは `source "$HOME/.local/share/cytellect-dev/env.sh"` を実行する。2026-11 より前のセットアップが使った `~/.local/share/cytellect-cloud` は、次のセットアップで `cytellect-dev` に移り、古い名前はリンクとして残る。

   ```bash
   python3 scripts/dev.py doctor   # ツール、フォント、Fiji、外部サービスの準備を確認
   python3 scripts/dev.py serve    # Web をビルドして API・計算ワーカーと起動し、招待コードを表示
   ```

## ローカル開発

Linux（WSL Ubuntu を含む）では、クラウドと同じスクリプトで、固定版のツール、依存パッケージ、試験用のブラウザ（Ubuntu の依存ライブラリを含む）を入れる。Fiji（約 1 分）と図のフォントは、`serve`・`check`・`e2e` を初めて使うときに入る。何度実行しても結果は変わらない。

```bash
bash scripts/linux_setup.sh
source ~/.local/share/cytellect-dev/env.sh   # 以後の端末では ~/.bashrc から読み込むとよい
python3 scripts/dev.py doctor   # ツール、フォント、Fiji、外部サービスの準備を確認
python3 scripts/dev.py serve    # Web をビルドして API・計算ワーカーと起動し、招待コードを表示
```

Linux 以外では、ツールを `必要環境` の版で入れてから、`python3 scripts/dev.py setup --fiji ~/cytellect-fiji` を実行し、`CYTELLECT_FIJI_EXECUTABLE=~/cytellect-fiji` を設定する。

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

GPU 推論（Cellpose-SAM）と解析提案（LLM）は、次の環境変数を設定すると使える。クラウド開発では環境の設定に登録する。ローカル開発では、`~/.config/cytellect/dev.env` に `名前=値` の行で書き、`chmod 600` で自分だけが読めるようにする。`env.sh` がこのファイルを読み込み、`doctor` は権限を確かめる。

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

`doctor` は、外部サービスが未設定なら `[--]`、不調なら `[!!]` を示し、どちらの場合も Fiji と画面の開発は続けられる。まだ入っていない Fiji と図のフォントも、初めて使うときに入るため `[--]` と示す。

| オプション | 動作 |
|---|---|
| `--live` | 実際に接続して確認する。停止中の GPU が起動する。GPU の空きを待つため起動にかかる時間は一定ではなく、動いた秒数に応じて課金される（[起動待ち](docs/cloud-gpu.ja.md#起動待ちと受入確認)）。解析提案は空の依頼でトークンだけを確認し、モデルは呼ばない |
| `--require-cloud` | 外部サービスも必須として確認する |
| `--owner` | [オーナーの環境](#オーナーの環境)の、各サービスの認証と CLI を確認する。読み取りの呼び出しだけで、デプロイも課金も起こさない |

### オーナーの環境

オーナー（運用者）のクラウド環境は、ネットワークを制限せず、運用の認証情報も持つ。開発から運用までを同じセッションで行える。マージ・デプロイ・有料サービスの利用は、権限があっても、オーナーが対象を指示したときだけ行う（[AGENTS.md](AGENTS.md)）。

環境のセットアップスクリプトは次のとおり。正本のセットアップのあとに、Vercel と Hugging Face の CLI を固定版で入れる（[.claude/owner-tools.sh](.claude/owner-tools.sh)）。

```bash
#!/usr/bin/env bash
set -euo pipefail
if [ -d cytellect ]; then
  bash cytellect/.claude/cloud-setup.sh
  if [ -f cytellect/.claude/owner-tools.sh ]; then bash cytellect/.claude/owner-tools.sh; fi
fi
```

| サービス | 認証情報 | クラウドセッションでの使い方 |
|---|---|---|
| GitHub | セッションの GitHub 接続（オーナーのアカウント） | REST の API と GitHub のコネクタ。GraphQL はクラウドセッションで使えないため、`gh pr list`・`gh pr merge` などは REST で行う（[マージ](docs/team-development.md#2-開発の流れ)） |
| Cloudflare（解析提案の Worker） | API トークン（`api.cloudflare.com` 宛てのネットワークシークレット）と、環境変数 `CLOUDFLARE_ACCOUNT_ID` | `pnpm --filter @cytellect/proposal-worker cf <wrangler の引数>`。wrangler はロックファイルの固定版 |
| Vercel | claude.ai の Vercel コネクタ（接続済み） | デプロイの状態・ログ・ロールバックはコネクタで行う。Vercel CLI を使う場合だけ、トークンを `api.vercel.com` 宛てのネットワークシークレットに登録する |
| Hugging Face | モデルを公開するときだけ、書き込みのトークン（`huggingface.co` 宛てのネットワークシークレット）。公開モデルの取得には要らない | `hf` CLI |
| Modal（GPU サーバー） | `MODAL_TOKEN_ID`・`MODAL_TOKEN_SECRET` は GitHub の `modal-deploy` 環境（`main` 限定）のシークレット | Actions の「Cellpose Modal deploy」を `main` から起動する。Modal の CLI は gRPC がプロキシを通らないため、クラウドセッションから接続できない |
| OpenAI、`ADMIN_TOKEN`（解析提案の Worker） | Worker の secret（`cf secret put`） | セッションに置く必要はない |

ネットワークシークレットの値はコンテナに入らず、環境のプロキシが通信に付ける。wrangler のように、鍵の値がないと動かない CLI のために、環境変数 `CLOUDFLARE_API_TOKEN` には仮の値 `placeholder-replaced-by-network-secret` を置く。プロキシがこれを本物に置き換える。AWS は現在使っていない。

`python3 scripts/dev.py doctor --owner` は、次を確かめる。

| 項目 | 確かめ方 | `[--]` の意味 |
|---|---|---|
| GitHub | `gh api` で、オーナーのアカウントと管理者の権限 | ― |
| Modal のデプロイ | `modal-deploy` 環境のシークレットの名前と、リポジトリ全体に同じ名前が残っていないこと。クラウドセッションからは読めないため、最後に成功したデプロイの日を示す | 秘密の値を、ここからは読めない |
| Cloudflare | API トークンの検証 | ― |
| Hugging Face | アカウントの照会 | 鍵がない（モデルを公開するときだけ要る） |
| Vercel | アカウントの照会 | 鍵がない（コネクタを使う） |
| Vercel CLI、Hugging Face CLI | `owner-tools.sh` の固定版と一致するか | ― |公開画像の一部は AWS Open Data にあるが、匿名の HTTPS で取得するため、アカウントも CLI も要らない。

#### 鍵の登録

鍵の作成と登録は、オーナーが Windows のブラウザ（または Claude アプリ）で行う。値はチャット・Issue・PR・ファイルに書かない。

1. Cloudflare の API トークンを作る。
   1. Cloudflare のダッシュボードで **My Profile** → **API Tokens** を開き、**Create Token** を選ぶ。
   2. テンプレートの **Edit Cloudflare Workers** を選ぶ。Workers のスクリプト・ルート・ログの権限が入る。
   3. 解析提案の Worker は D1 を使うため、権限に **D1** の編集を加える。
   4. 対象のアカウントは Cytellect のアカウントだけ、ゾーンは `cytellect.app` だけにする。
   5. **Continue to summary** → **Create Token** を選び、表示されたトークンをコピーする。トークンは一度しか表示されない。
2. モデルを公開する場合だけ、Hugging Face のトークンを作る。`https://huggingface.co/settings/tokens` で **New token** を選び、**Fine-grained** で `Genellect/Cytellect` への書き込みだけを許可する。
3. claude.ai で、オーナーの環境（`cytellect`）に登録する。次のどちらかで行う。
   - セッションで Claude に登録を頼む。Claude が出す入力欄に貼る。接続先は入力済みになる。
   - セッションのタイトルバーのクラウド環境のメニュー → **Edit** → **Network secrets** に、接続先（`api.cloudflare.com`、`huggingface.co`）と値を加える。ヘッダーは `Authorization`、接頭辞は `Bearer`。
4. 新しいセッションを開き、Claude に `doctor --owner` での確認を頼む。

#### 運用の操作

オーナーの環境のクラウドセッションで行う操作。読み取りは自由に行える。デプロイ・ロールバック・有料の操作は、オーナーが対象を指示したときだけ行い、前後の版を記録する（[AGENTS.md](AGENTS.md)）。`cf` は `pnpm --filter @cytellect/proposal-worker cf` の略。

| 対象 | 操作 | コマンド・手段 | 区分 |
|---|---|---|---|
| 解析提案の Worker | デプロイの履歴と、いまの版 | `cf deployments list --name cytellect-proposal`、`cf versions list --name cytellect-proposal` | 読み取り |
| | 版の設定（変数、D1 の結び付け、秘密の値の名前） | `cf versions view <版の ID> --name cytellect-proposal` | 読み取り |
| | ログ | `cf tail cytellect-proposal --format pretty`。依頼ごとにメソッド・URL・結果が出る。本文は出ない | 読み取り |
| | デプロイ | [解析提案のデプロイ](docs/proposal-deployment.md)の手順。運用者の `wrangler.toml` はリポジトリに入れないため、クラウドセッションでは、いまの版の設定（`cf versions view`）から checkout の外に作り直す | 指示があったとき |
| | ロールバック | `cf rollback <版の ID> --name cytellect-proposal`。戻す先の版の予算の設定を、先に `cf versions view` で確かめる | 指示があったとき |
| Vercel（Web） | 本番のデプロイの履歴と状態 | claude.ai の Vercel コネクタ（デプロイの一覧と詳細）。本番は `main` から自動で公開される | 読み取り |
| | ロールバック | コネクタのロールバック。戻したら、本番の SHA と READY を確かめる | 指示があったとき |
| Modal（GPU サーバー） | デプロイの履歴 | `gh api repos/genellect/cytellect/actions/workflows/cellpose-modal-deploy.yml/runs` | 読み取り |
| | デプロイ | `gh api -X POST repos/genellect/cytellect/actions/workflows/cellpose-modal-deploy.yml/dispatches -f ref=main` で起動し、実行の結果を同じ `runs` で確かめる | 指示があったとき（有料） |
| Hugging Face | モデルの取得 | `hf download Genellect/Cytellect <ファイル> --revision <版>`。取得したファイルの SHA-256 を、`engines/cellpose/*.lock.json` の値と照合する | 読み取り |
| | モデルの公開 | `hf upload`。書き込みのトークンが要る（[鍵の登録](#鍵の登録)） | 指示があったとき |
| GitHub | マージ | [チーム開発ルール](docs/team-development.md#2-開発の流れ)の手順 6（クラウドセッションでは REST） | 指示があったとき |

## PR を出す前に

`check` は、PR の CI と同じ検査を手元で再現する。変更の内容に応じて、次のコマンドを実行する。

```bash
python3 scripts/dev.py changed           # 変更したファイル、PR の CI が実行する対象、関係する試験を示す
python3 scripts/dev.py check --related   # 手元の短い確認：lint、型、変更したファイルを読み込む・名指しする試験だけ
python3 scripts/dev.py check --changed   # 変更に応じて python・web の全体を実行する
python3 scripts/dev.py check             # python と web のすべて（python や web に絞ることもできる）
python3 scripts/dev.py check --fiji      # 解析エンジンを変えたとき、実際の Fiji での試験も
python3 scripts/dev.py contracts         # API を変えたとき（OpenAPI、既定レシピ、TypeScript の型を一緒にコミット）
python3 scripts/dev.py audit             # 依存パッケージを変えたとき（結果は checkout の外に保存）
```

作業中は `check --related` で確かめ、全体は PR の CI に任せてよい。`--related` は、変更したファイルをほかのモジュール経由でだけ使う試験を選ばない（[scripts/related_tests.py](scripts/related_tests.py)）。Python の試験の全体は、CPU の数（最大 4）に分けて並列に実行する（[scripts/run_test_shards.py](scripts/run_test_shards.py)）。

ブラウザ、コンテナ、Windows の統合試験は CI が担う（[CI の構成](docs/ci.md)）。コンテナの試験は、クラウド環境でも `dockerd` を起動すれば手元で行える。ブラウザの試験を手元で行うときは、`python3 scripts/dev.py public-inputs` で登録済みの公開画像を準備する（既定 `~/cytellect-public-inputs/workspace-inputs`）。そのうえで `serve` を起動したまま、CI の `browser-e2e` ジョブ（[ci.yml](.github/workflows/ci.yml)）と同じ環境変数で `pnpm test:e2e` を実行する。`CYTELLECT_REAL_INPUTS` には準備した画像の場所を、`CYTELLECT_TEST_DATA_DIR` には `serve` の作業データの場所を指定する。PR の説明は、[PR テンプレート](.github/pull_request_template.md)のすべての項目を書く。

画面を手で確かめるための公開画像は、`public-inputs` にデータセットの名前を渡して取得する。出典とライセンスは [fixtures/public](fixtures/public) にある。

| 名前 | 内容 | 確かめられること |
|---|---|---|
| `bbbc007`（既定） | DNA とアクチン、1 視野 | 核の検出、測定、修正 |
| `bbbc013` | DRAQ と FKHR-EGFP、3 視野（リポジトリにあり、場所を示すだけ） | チャンネルの陽性判定と陽性率、面積だけの測定 |
| `jump-plk1` | PLK1 ノックアウトと対照、実験回 3（約 400 MB） | 群間比較 |
| `nucleolar` | DAPI と NCL の原画像 | 核小体（[公開画像での検証](docs/public-nucleolar-validation.md)） |

Claude Code 向けの手順は [.claude/skills](.claude/skills) にあり、使い分けは [CLAUDE.md](CLAUDE.md#目的別のスキル)にある。
