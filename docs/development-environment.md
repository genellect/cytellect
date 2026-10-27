# 開発環境の設定

Cytellect の起動と外部サービスの利用に必要な設定をまとめる。環境を立ち上げる順序は [CONTRIBUTING](../CONTRIBUTING.md)、値を入れる雛形は [`.env.example`](../.env.example) にある。この文書では、設定の用途と、それを誰がどこで管理するかを説明する。秘密値や個人の保存場所は記載しない。

## 作業に応じて用意するもの

| 作業 | 用意するもの | オーナーへの確認 |
|---|---|---|
| Fiji・測定・統計・画面の開発 | Python・Web・Fiji の環境と、checkout の外の作業データ領域 | 外部サービスの認証情報は不要 |
| Cellpose の検出をクラウド GPU で試す | GPU の URL と開発用の接続キー | 利用する環境、期間、GPU の利用枠 |
| Cellpose をローカル CPU で試す | 固定版の Cellpose 環境とモデル | 認証情報は不要。導入と実行に時間がかかる |
| AI による解析提案を試す | 提案 Worker の URL と開発環境専用の端末トークン | 利用する環境、期間、端末の回数上限とサービス全体の予算 |
| GPU サーバー・提案 Worker の管理やデプロイ | 対象サービスの管理権限と、後述の運用者用設定 | 通常のアプリ開発とは別に、対象・権限・費用・公開の可否を確認する |

接続キーと端末トークンは、オーナーから開発用として受け取る。共同開発者全員で一つの本番用トークンを使うと、利用枠や失効の対象を分けられない。解析提案の端末トークンは開発環境ごとに発行する。外部サービスを使う試験には、登録済みの公開画像だけを使う。

## 設定の保存先

| 場所 | 保存するもの | 読み込む側 |
|---|---|---|
| リポジトリの `.env.example` | 設定名と安全な例。認証情報は空欄 | コピーして手元の設定を作るための雛形 |
| 手元の `.env` | その開発環境のパス、URL、開発用の接続キー・端末トークン | `uv run --env-file .env -- …` で起動した API・計算ワーカー・Web |
| Claude Code・Codex の開発環境の変数／secret 設定 | その環境の URL と認証情報。秘密値は secret の仕組みで保管する | 作業セッション。セットアップ時と作業時の利用範囲が異なる場合は両方を確認する |
| checkout の外の秘密ファイル | ファイルで渡す提案用端末トークン | ローカル API、または Docker Compose の secret マウント |
| GitHub Actions の repository secrets | Modal のデプロイ用 ID と Secret | GPU デプロイ workflow |
| Cloudflare Worker の secrets と設定 | OpenAI API キー、管理トークン、モデル・料金・予算、D1 の接続設定 | 提案 Worker |

`.env` は `.gitignore` の対象で、雛形だけを Git に置く。Git の除外設定はファイルを暗号化しないため、手元では本人だけが読めるアクセス権にする。値を受け渡すときは、オーナーと決めた秘密情報の共有手段を使う。Issue・PR・チャット・スクリーンショットには値を載せず、設定名と状態だけを伝える。`env`、`printenv`、HTTP ヘッダー、`.env` の全文を診断ログへ出さない。

`.env` を置くだけでは Python は読み込まない。読み込み方は [ローカル開発](../CONTRIBUTING.md#ローカル開発)を参照する。Next.js の `NEXT_PUBLIC_*` はブラウザに渡る設定なので、秘密値を入れない。Web のビルド時に使う値を変えた場合は再ビルドする。

## API・計算ワーカー・Web

以下は秘密ではない設定。パスは開発環境ごとに決め、API と計算ワーカーで同じ作業データ領域を使う。既定値は、特記しない限り [API の設定](../services/api/src/cytellect_api/config.py)の値である。

| 変数 | 用途・設定する場面 | 開発時の値・注意点 |
|---|---|---|
| `CYTELLECT_DATA_DIR` | DB、画像、測定結果などの保存先。API・計算ワーカーに必要 | checkout の外を指定する。雛形では `../cytellect-data`。`dev.py serve` は `--data-dir` を優先し、省略時は `~/cytellect-data` |
| `CYTELLECT_FIJI_EXECUTABLE` | 核の検出に使う Fiji の場所 | `setup --fiji` で導入した checkout の外の場所。雛形では `../cytellect-fiji` |
| `CYTELLECT_APP_ORIGIN` | API が許可するブラウザの接続元 | `http://localhost:3000`。スキーム・ホスト・ポートを実際の画面と一致させる |
| `NEXT_PUBLIC_API_ORIGIN` | Web が呼ぶ解析 API | `http://localhost:8000`。本番ビルドで未設定なら公開デモとして動く |
| `CYTELLECT_SECURE_COOKIES` | HTTPS 専用 Cookie を使うか | API の既定は `true`。手元の HTTP 開発では `false`。公開 TLS 環境では `true` |
| `CYTELLECT_UPLOAD_ALLOWLIST` | 受け付ける公開画像・表の SHA-256 一覧 | 共同開発の雛形は `fixtures/public/uploads.json`。他者が接続できる開発環境では必ず設定する（[データ保護](security.md#shared-development-environments)） |
| `CYTELLECT_DEMO` | API のデモ制限を有効にする | 既定 `false`。Vercel の公開デモを選ぶ設定とは別 |
| `CYTELLECT_WORKSPACE_RETENTION_MODE` | 作業データを期限で消すか、手動削除まで残すか | 既定 `ttl`。`manual` はループバックの個人利用向け。既存データの保持方針を確認せず変更しない |
| `CYTELLECT_RETENTION_SECONDS` | `ttl` の保存期間（秒） | 既定 `86400`（24 時間） |
| `CYTELLECT_JOB_TIMEOUT_SECONDS` | 解析ジョブの実行時間上限（秒） | 既定 `3600` |
| `CYTELLECT_WORKER_MEMORY_MB` | 計算ワーカーのジョブ用メモリ上限 | 既定 `4096`。OS・コンテナ側の制限も受ける |
| `CYTELLECT_MAX_UPLOAD_BYTES` | アップロードのサイズ上限 | 既定 `2147483648`（2 GiB） |
| `CYTELLECT_MAX_FIELDS` | 視野数の上限 | 既定 `100` |
| `CYTELLECT_DESKTOP_OWNER` / `NEXT_PUBLIC_CYTELLECT_DESKTOP_OWNER` | 個人用デスクトップ版の所有者モードと、その画面側の動作 | 通常の共同開発では未設定または `false`。共有サーバーの認証を省くために使わない |
| `CYTELLECT_CODE_REVISION` | 結果に記録するソースの版 | 配布・ビルド側が 40 桁のコミット SHA を設定する。未設定ならコミットは記録されず、ソースファイルのハッシュは別に記録される |
| `NEXT_TELEMETRY_DISABLED` | Next.js のテレメトリーを無効化する | `1`。`dev.py serve` も設定する |

`dev.py serve` はローカル確認用に Origin、Cookie、データ領域を設定し直す。公開 TLS サーバーの起動や、その設定の検証には使わない。公開開発環境のアップロード制限は[データ保護](security.md)に従う。

## 外部サービスの接続

### Cellpose の GPU 推論

| 変数 | 用途 | 取得・設定方法 |
|---|---|---|
| `CYTELLECT_CELLPOSE_REMOTE_URL` | Cellpose 推論サーバーの HTTPS URL。秘密ではない | オーナーが開発用として指定した接続先を設定する |
| `CYTELLECT_CELLPOSE_REMOTE_TOKEN` | GPU サーバーを呼ぶ接続キー。秘密 | Modal の接続用 ID と Secret をピリオドでつないだ値。計算ワーカーを直接起動する場合もこの形を使う |
| `CYTELLECT_MODAL_PROXY_KEY` / `CYTELLECT_MODAL_PROXY_SECRET` | 同じ接続キーを ID と Secret に分けて登録するための変数。組として秘密に扱う | `scripts/dev.py` または Claude Code の `env.sh` が結合する。明示した `CYTELLECT_CELLPOSE_REMOTE_*` が優先されるため、二つの形式を併用する場合は更新漏れに注意する |
| `CYTELLECT_CELLPOSE_REMOTE_SECRET` | 独自の推論サーバーが追加の共有秘密を要求する場合だけ使う。秘密 | サーバーの `CYTELLECT_CELLPOSE_SECRET` と対応する。通常の Modal Proxy Auth 接続では不要 |
| `CYTELLECT_CELLPOSE_PYTHON` / `CYTELLECT_CELLPOSE_MODEL_DIR` | ローカル CPU 推論に使う Python とモデルの場所。秘密ではない | `dev.py setup --cellpose` の出力に従う。クラウド GPU の代わりに使う場合は `CYTELLECT_CELLPOSE_REMOTE_URL` を設定しない |

Modal の接続用トークンと、サーバーを変更できるデプロイ用トークンは別の認証情報である。接続キーだけで通常の GPU 利用ができ、デプロイ用キーを開発環境へ渡す必要はない。詳細は[クラウド GPU](cloud-gpu.ja.md#開発環境から使う)を参照する。Docker の計算ワーカーはネットワークから切り離されており、`.env` に接続先を追加してもクラウド GPU は使えない。

### AI による解析提案

| 変数 | 用途 | 取得・設定方法 |
|---|---|---|
| `CYTELLECT_PROPOSAL_URL` | 提案 Worker の HTTPS URL。秘密ではない | オーナーが開発用として指定した接続先を設定する |
| `CYTELLECT_PROPOSAL_TOKEN` | この開発環境の端末トークン。秘密 | オーナーが Worker の招待から発行する。ローカル API に設定し、ブラウザには渡さない |
| `CYTELLECT_PROPOSAL_TOKEN_FILE` | 同じ端末トークンをファイルから読む場合のパス | checkout の外の、API の実行ユーザーだけが読めるファイルを指定する。`CYTELLECT_PROPOSAL_TOKEN` と同時に設定しない |
| `CYTELLECT_PROPOSAL_MODEL` | 応答のモデルを照合するための設定 | 既定 `gpt-6.1-sol`。Worker と一致させる。任意のモデルへ切り替えるための設定ではない |
| `CYTELLECT_PROPOSAL_PROMPT_VERSION` | 応答のプロンプト版を照合するための設定 | 既定は [proposal_contracts.py](../packages/analysis/src/cytellect_analysis/proposal_contracts.py) の `PROPOSAL_PROMPT_VERSION`。Worker と一致させる |
| `CYTELLECT_PROPOSAL_TIMEOUT_SECONDS` | 提案の応答を待つ上限（秒） | 既定 `300`。処理時間の予測値ではない |

端末トークンは OpenAI API キーではない。開発環境は Worker を呼び、Worker が自身の API キーで OpenAI を呼ぶ。開発環境ごとの回数上限に加え、全環境でサービス全体の月額予算を共有する。発行・失効は[提案サービス](proposal-service.md#development-environments)に従う。`.env` から削除するだけでは失効しない。

Docker で提案を使う場合は [infra/compose.proposal.yaml](../infra/compose.proposal.yaml) を追加し、端末トークンを secret として API にだけ渡す。ホストの `CYTELLECT_PROPOSAL_TOKEN_FILE` は秘密ファイルの絶対パスで、コンテナ内では `/run/secrets/proposal_device_token` になる。API の UID `10001` が読み取れる権限が必要である。

## 管理・デプロイの設定

以下はサービス自体を変更する担当者の設定で、共同開発用 `.env` の配布対象にはしない。作業に必要な場合は、対象サービスと作業内容をオーナーに確認する。公開・デプロイ・有料呼び出しの権限は、[チーム開発ルール](team-development.md#7-本番公開と配布)に従う。

| 設定・認証情報 | 用途 | 管理場所 |
|---|---|---|
| `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET` | GPU サーバーをデプロイする認証情報。秘密 | GitHub の Settings → Secrets and variables → Actions。接続用の Proxy Auth Token とは別（[手順](cloud-gpu.ja.md#3-github-に登録してデプロイする)） |
| `OPENAI_API_KEY` | Worker から OpenAI Responses API を呼ぶキー。秘密 | Cloudflare Worker の secret。通常の API・Web・計算ワーカーには置かない |
| `ADMIN_TOKEN` | 提案 Worker の招待を発行する管理トークン。秘密 | Cloudflare Worker の secret と、運用者の秘密情報管理。端末トークンとして配布しない |
| Cloudflare CLI の認証 / `CLOUDFLARE_ACCOUNT_ID` | Wrangler の操作権限と操作先のアカウント | 運用者が CLI でログインする。アカウント ID 自体は秘密ではなく、これだけでは認証できない |
| D1 の `database_id` と `DB` binding | 端末・利用回数・予算台帳を保存する DB の指定 | Worker の Wrangler 設定。ID は認証情報ではない |
| `OPENAI_MODEL` / `REASONING_EFFORT` / `LOW_EFFORT_EVALUATED` / `MAX_OUTPUT_TOKENS` | Worker が使うモデル、推論量、低推論量の評価済み状態、出力上限 | Worker の vars。固定モデル・評価条件に従い、未評価の値へ変更しない |
| `MONTHLY_BUDGET_USD` / `DEVICE_MONTHLY_REQUESTS` | 全体の月額予算と端末ごとの月間回数上限 | Worker の vars。オーナーが決める |
| `PRICE_INPUT_USD_PER_MTOK` / `PRICE_OUTPUT_USD_PER_MTOK` / `PRICE_CACHED_INPUT_USD_PER_MTOK` / `PRICE_CACHE_WRITE_USD_PER_MTOK` | 呼び出し前の費用予約と精算に使う単価 | Worker の vars。適用する料金を運用者が確認する。キーだけを登録しても、料金・予算が未設定なら有料呼び出しは無効 |

Worker の設定の雛形は [wrangler.toml.example](../services/proposal-worker/wrangler.toml.example)、配置・移行・無効化の手順は[デプロイ手順](proposal-deployment.md)にある。OpenAI キーを直接使う有料モデル評価も、通常の起動とは別に予算の承認が必要である（[評価設定](proposal-service.md#model-evaluation-before-enabling)）。

GitHub・Vercel などの個人用ログイン情報や CLI トークンはアプリの実行用設定ではない。各開発者の権限でログインし、オーナーの認証情報を `.env` にまとめて配布しない。Vercel の公開サイトは LP と公開デモで、GPU・提案サービスのキーを置く場所ではない。

## 実行方法に固有の設定

通常の起動で追加する必要はない。対象の作業を行う場合に、各手順に従って設定する。

| 変数 | 用途・設定場所 |
|---|---|
| `CYTELLECT_SETUP_FIJI` | Codex のセットアップで Fiji も導入・検証する場合に `1`。`CYTELLECT_FIJI_EXECUTABLE` も指定する |
| `CYTELLECT_CHROMIUM_EXECUTABLE` | クラウド環境に備わる試験用 Chromium のパス。手元で Playwright が導入する場合は不要 |
| `CYTELLECT_RUNTIME_DIR` | Docker の `/data` にマウントするホストの絶対パス。checkout の外を指定する。`CYTELLECT_DATA_DIR` はコンテナ内では `/data`（[Docker](docker-desktop.md)） |
| `CYTELLECT_API_HOST` | TLS 構成の Caddy が使う API ホスト名（[compose.tls.yaml](../infra/compose.tls.yaml)） |
| `CYTELLECT_WEB_MODE` / `NEXT_PUBLIC_CYTELLECT_WEB_MODE` | 同一 Origin で動くローカル配布版をビルドする設定と、その生成値。通常の API・Web 別起動では設定しない（[ローカル版](local.md)） |
| `CYTELLECT_WEB_DIR` | ローカル配布版が配信する Web ファイルの場所。配布物の構成に従う |
| `NEXT_PUBLIC_WINDOWS_RELEASE_URL` | 公開サイトの Windows 配布リンクの上書き。空欄はダウンロードを無効化する（[Web 設定](../apps/web/README.md)） |
| `NEXT_PUBLIC_SHOWCASE_DEV_BACKEND` / `CYTELLECT_NEXT_DIST_DIR` | 公開デモの開発用接続先と、Web のビルド出力先。公開ビルドに開発用接続先を残さない（[公開デモ](showcase.md)） |
| `CYTELLECT_ENGINE_ASSETS` / `CYTELLECT_CELLPOSE_ASSETS` | 配布環境での Fiji・Cellpose のコードや固定ファイルの場所。通常の checkout では自動解決する |
| `CYTELLECT_CELLPOSE_HOST` / `CYTELLECT_CELLPOSE_PORT` / `CYTELLECT_CELLPOSE_MODEL` / `CYTELLECT_CELLPOSE_RUNTIME_LOCK` / `CYTELLECT_REQUIRE_GPU` | GPU サーバー・runner 側の待ち受け、モデル、依存の固定、GPU 必須設定。[Modal 定義](../infra/modal_cellpose.py)と GPU イメージが設定する |
| `CYTELLECT_CELLPOSE_SECRET` | 独自の GPU サーバーに追加認証を設ける場合の秘密。クライアント側の `CYTELLECT_CELLPOSE_REMOTE_SECRET` と一致させる |
| `CYTELLECT_TEST_DATA_DIR` / `CYTELLECT_TEST_API_ORIGIN` / `CYTELLECT_WEB_URL` / `CYTELLECT_TEST_PYTHON` / `CYTELLECT_TEST_LOCAL` | ブラウザ・ローカル配布版の受入試験の接続先と実行環境。通常の起動設定とは分け、[CI](ci.md)と対象試験の手順に従う |

## 設定の確認と更新

`doctor` はツール、Fiji、外部サービスの設定の有無を確認する。外部サービスの `[--]` は未設定を示し、Fiji と画面の開発を妨げない。外部サービスも必須の作業では `--require-cloud` を使う。

`doctor --live` は実際に接続する。GPU が設定されていると停止中の GPU を起動し、稼働分の費用が発生するため、承認された利用範囲で実行する。提案サービスの確認は空の要求による認証確認で、モデルを呼ばない。これが成功しても、画像での推論や提案の品質を確認したことにはならない。

キーが無効な場合や利用枠に達した場合は、変数名、利用環境、発生時刻、秘密値を除いたエラーコードをオーナーへ伝える。キーを更新したら、その値を読むプロセスやクラウドセッションを再起動する。不要になった環境はオーナーに知らせ、サービス側で失効させてからローカルの値を削除する。誤って公開した場合は、値を再掲せず連絡し、[チーム開発ルール](team-development.md#6-研究データの扱い)に従って失効・再発行する。
