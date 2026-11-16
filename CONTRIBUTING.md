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

### 画面の共有

`python3 scripts/dev.py serve --share` は、Web と API を 1 つのオリジン（既定は `http://localhost:8080`）にまとめて起動する。間に入るのは、ロックファイルの uvicorn と httpx で作った中継（[scripts/share_proxy.py](scripts/share_proxy.py)）で、`/v1/*` を API へ、それ以外を Web へ流す。本番と同じ Cookie（`SameSite=Strict`）と Origin の照合を保ったまま、別の場所のブラウザから画面を使える。

- 受け付けるのは、登録済みの公開画像だけ（`CYTELLECT_UPLOAD_ALLOWLIST`、[データ保護](docs/security.md#shared-development-environments)）。
- 招待コードの期限と共有は、既定で 2 時間で終わる（`--share-hours`）。
- Web は、ブラウザから見えるオリジンを埋め込んでビルドする。空のオリジンは公開版（デモ）と見なされるため。ブラウザが別のアドレスで開く場合は、`--share-origin <URL>` で指定して起動し直す。中継は、届いたアドレスを 1 回ずつ表示する。
- Web は本番と同じく、ほかのページの枠の中で表示されない（`frame-ancestors 'none'`、`X-Frame-Options: DENY`）。枠を使う表示では見えない。

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
- `serve` は Linux 向け。Windows では、次の開発サーバーで起動するか、WSL Ubuntu を使う。

### WSL Ubuntu

Windows 11 の WSL2 上の Ubuntu 24.04（x64）で、Linux と同じ手順で開発し、画面は Windows のブラウザ（Edge など）で確かめる。Fiji の固定版は x64 だけなので、ARM 版の Windows では核の検出を動かせない。

1. **WSL を用意する（Windows、一度だけ）**
   1. PowerShell を管理者として開き、`wsl --install -d Ubuntu-24.04` を実行する。再起動のあと、Ubuntu の利用者名とパスワードを決める。
   2. 必要なら `%UserProfile%\.wslconfig` に次を書き、PowerShell で `wsl --shutdown` を実行して反映する。`memory` は WSL が使えるメモリの上限（既定は PC の半分）。`networkingMode=mirrored` にすると、Windows と WSL が `localhost` を共有する。

      ```ini
      [wsl2]
      memory=8GB
      networkingMode=mirrored
      ```

   3. Docker を使う場合は、Docker Desktop の **Settings** → **Resources** → **WSL integration** で `Ubuntu-24.04` を有効にする。
2. **チェックアウトとセットアップ（WSL の端末）**。チェックアウトと作業データは WSL 側（`~/`）に置く。`/mnt/c` は遅く、権限の扱いも違う。Windows 側で clone したものは使わない。

   ```bash
   sudo apt-get update && sudo apt-get install -y git curl gh
   git clone https://github.com/genellect/cytellect.git ~/cytellect && cd ~/cytellect
   bash scripts/linux_setup.sh
   echo '. ~/.local/share/cytellect-dev/env.sh' >> ~/.bashrc && . ~/.local/share/cytellect-dev/env.sh
   python3 scripts/dev.py doctor
   ```

3. **鍵**：GPU の接続キーと解析提案の端末トークンは、[外部サービス](#外部サービス)のとおり `~/.config/cytellect/dev.env` に書く。オーナーは、各 CLI にブラウザでログインする（`gh auth login`、`vercel login`、`hf auth login`）。wrangler は `dev.env` の `CLOUDFLARE_API_TOKEN` を使う。オーナー用の CLI は `bash .claude/owner-tools.sh` で入る。
4. **起動**：`python3 scripts/dev.py serve` を実行し、Windows の Edge で `http://localhost:3000/workspace` を開く。開けない場合は、WSL の端末で `curl -s localhost:3000` が応答するかを確かめ、手順 1 の `networkingMode=mirrored` を試す。
5. **Claude Code**：WSL の端末で Claude Code を入れ、チェックアウトで起動する。セッションの開始時に [.claude/hooks/session-start.sh](.claude/hooks/session-start.sh) が `env.sh` を読み込む。

`doctor` は WSL のとき、チェックアウト・作業データ・Fiji が Windows 側のディスク（`/mnt/*`）にないか、メモリとディスクの空き、CPU の種類も確かめる。

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
| Modal（GPU サーバー） | `MODAL_TOKEN_ID`・`MODAL_TOKEN_SECRET` は GitHub の Actions の秘密の値 | Actions の「Cellpose Modal deploy」を `main` から起動する。Modal の CLI は gRPC がプロキシを通らないため、クラウドセッションから接続できない |
| OpenAI、`ADMIN_TOKEN`（解析提案の Worker） | Worker の secret（`cf secret put`） | セッションに置く必要はない |

ネットワークシークレットの値はコンテナに入らず、環境のプロキシが通信に付ける。AWS は現在使っていない。公開画像の一部は AWS Open Data にあるが、匿名の HTTPS で取得するため、アカウントも CLI も要らない。

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
4. 新しいセッションを開き、Claude に確認を頼む。CLI がトークンの指定を求める場合、Claude は形式だけ合わせた仮の値を環境変数に置き（プロキシが本物に置き換える）、`cf whoami` と `hf auth whoami` で確かめる。

## PR を出す前に

`check` は、PR の CI と同じ検査を手元で再現する。変更の内容に応じて、次のコマンドを実行する。

```bash
python3 scripts/dev.py check           # すべての変更で（python や web に絞ることもできる）
python3 scripts/dev.py check --fiji    # 解析エンジンを変えたとき、実際の Fiji での試験も
python3 scripts/dev.py contracts       # API を変えたとき（OpenAPI、既定レシピ、TypeScript の型を一緒にコミット）
python3 scripts/dev.py audit           # 依存パッケージを変えたとき（結果は checkout の外に保存）
```

ブラウザ、コンテナ、Windows の統合試験は CI が担う（[CI の構成](docs/ci.md)）。コンテナの試験は、クラウド環境でも `dockerd` を起動すれば手元で行える。ブラウザの試験は、`python3 scripts/dev.py e2e` で手元でも行える。CI の `browser-e2e` ジョブ（[ci.yml](.github/workflows/ci.yml)）と同じく、外部サービス（クラウド GPU、解析提案）を外して API・計算ワーカー・Web を自分で起動し、登録済みの公開画像と毎回新しい作業データで `pnpm test:e2e` を実行し、終われば止める。`serve` を起動している間は使えない。Playwright への引数は `--` のあとに書く（例：`-- --trace off`）。PR の説明は、[PR テンプレート](.github/pull_request_template.md)のすべての項目を書く。
