# Claudeクラウド：認証・評価予算・公開作業の引継ぎ

2026-10-05。ローカルのClaude Codeを前提にしない手順です。
コードはGit、API認証はクラウド環境の保護された設定、既存の評価台帳は
非公開の移送データから引き継ぎます。PCのOAuthログインは移行しません。
[製品の引継ぎ](claude-production-handoff-2026-10-05.md)の受入条件も引き続き適用します。

## 1. Gitを取得する

Claude停止中にCodexが追加したブランチは`codex/claude-cloud-setup`です。
PR #32のheadを親としており、製品UI・解析式・統計式は変更していません。
まずこの追加PRをレビューし、#32のブランチへ統合します。mainへの統合は
最新CIと公開条件を確認してから行います。

```sh
git fetch origin
git switch codex/sol-workspace-integration
git merge --no-ff origin/codex/claude-cloud-setup
git status --short
```

まだ追加PRを統合していない環境では、setup前にそのブランチを取得してください。
クラウド設定のSetup scriptは`bash .claude/cloud-setup.sh`。
Node 24.18.0を公式配布とSHA-256で照合してrepo外へ導入し、固定依存と無課金テストを
用意します。Hosted環境ではPlaywrightのbrowser downloadを行わず、
提供済みChromiumを`CYTELLECT_CHROMIUM_EXECUTABLE`で使います。Linuxクラウドでの実行は設定後に確認し、Windows上のテストと混同しません。
次の作業コマンドの前に実行します。

```sh
source "$HOME/.local/share/cytellect-cloud/env.sh"
```

## 2. OpenAI：キーをClaudeに見せずに使う

[Anthropic公式のcloud environment説明](https://code.claude.com/docs/en/cloud-environments#add-api-credentials)
に基づき、Pro/MaxのAnthropic-hosted環境では**API credentials**を利用します。
通常の環境変数はClaudeと全コマンドから読めるため、同じ保護ではありません。
Team/Enterprise、self-hosted環境、customer-managed encryptionではこの方式を使えません。
利用中プランと設定項目の有無は実画面で確認します。

`claude.ai/code`の環境選択から環境の歯車を開き、Add credentialへ登録します。

| 設定 | 値 |
|---|---|
| Name | Cytellect evaluation |
| Credential type | Bearer |
| Allowed websites | `api.openai.com`のみ |
| Header name / prefix | `Authorization` / `Bearer` |
| Value | 発行済みCytellect専用評価キー。チャット・Git・ログへ貼らない |

使用するキーはCOMPASS組織内の独立Cytellectプロジェクトのものです。
PersonalやCOMPASS Interactiveのキーは流用しません。7日で失効するため、
実行前に有効性を確認します。新規発行や期限延長を自動で行いません。
Connect後、キーはVMへ渡らず通信後にproxyが認証を付けます。Setup script中には
この認証が利用できません。環境設定後の新規セッションで確認してください。

無料の認証確認はモデル情報のGETに限定します。レスポンス全文やヘッダーを出さず、
HTTP statusとモデルIDの一致のみを記録します。401/403/429は区別して報告し、
失敗を残高不足と決めつけません。成功してもResponses生成の合格にはしません。

今回の`evaluation-auth.ts`は評価時だけAuthorizationを除去し、外部proxyによる認証を
利用します。明示フラグ、`CLAUDE_CODE_REMOTE=true`、非CI、キー未設定を必須とし、
宛先は固定Responses URL、POST、redirect:errorのみ。本番Workerのキー契約は変更しません。

## 3. USD5の承認を移送する

承認は**全環境・全試行の合計USD5**、公開事例の評価のみです。
既存の保留予約も差し引きます。台帳の新規初期化、リセット、別枠USD5の発行は禁止です。
本番の有料API利用は未承認で、公開時もOFF・月額上限0を維持します。

Codex側で全評価プロセスを停止し、次を実行して非公開snapshotを作ります。
source/destinationはrepo外の専用ディレクトリに置きます。

```sh
node services/proposal-worker/scripts/transfer-evaluation-ledger.mjs export /private/original.sqlite /private/cloud-snapshot.sqlite
```

これは元台帳をロックして新しい予約を遮断し、SQLite snapshotを作ります。
held/settled、承認ID・上限を保持し、snapshotも初期状態は停止中です。
元台帳は再開しません。snapshotを複数環境へ複製して同時利用しないでください。
分散したコピーの同時利用を検出するサーバーはないため、一人の担当者・一つの環境で
所有を移す運用が必要です。SHA-256は転送破損の確認で、署名による真正性保証ではありません。

非公開snapshotのbase64とSHA-256をクラウド環境変数へ登録します。
この台帳はAPIキー・研究データを含まず、Claudeが読むことを意図した運用情報です。
値をGit・PR・公開ログへ転載しません。APIキーはこの環境変数欄へ入れません。

```text
CYTELLECT_EVAL_LEDGER_SNAPSHOT_B64=<private snapshot base64>
CYTELLECT_EVAL_LEDGER_SHA256=<private snapshot SHA-256>
CYTELLECT_PUBLIC_EVAL_LEDGER=/tmp/cytellect-evaluation/approved.sqlite
CYTELLECT_EVAL_SINGLE_OPERATOR=true
CYTELLECT_EVAL_PROXY_AUTH=true
CYTELLECT_PUBLIC_EVAL_BUDGET_USD=5
CYTELLECT_PUBLIC_EVAL_REPEATS=1
CYTELLECT_PUBLIC_EVAL_EFFORT=medium
```

`CYTELLECT_ALLOW_PAID_PUBLIC_EVAL`は初期設定に入れず、実評価コマンドにだけ付けます。
台帳の取り込みは一度だけ実行します。

```sh
install -d -m 700 /tmp/cytellect-evaluation
node services/proposal-worker/scripts/restore-evaluation-ledger.mjs
```

restoreはdigest、SQLite header、サイズ、repo外パスを確認し、既存ファイルを上書きせず、
引継ぎsnapshotだけを有効化します。金額の再初期化はありません。
セッションが消失した場合、最初のsnapshotをもう一度復元してはいけません。
最新台帳を非公開で回収し、同じtransfer手順で次の環境へ移します。
回収できなければ課金評価を停止し、請求記録との照合まで再開しません。
クラウドのVMは非アクティブ時に回収されます。各評価の後、Claudeは最新台帳を
`transfer-evaluation-ledger.mjs export`で非公開snapshotとして書き出し、Git以外の
非公開ファイル（ユーザーへの直接送付）で返却します。

```sh
CYTELLECT_ALLOW_PAID_PUBLIC_EVAL=true pnpm --filter @cytellect/proposal-worker eval:public
```

12事例をまず1回ずつ評価し、Python validator、用途に合う提案、欠測理由、API usageを
確認します。失敗は修正してから再評価し、回数追加も同じ台帳を使います。
原画像の測定値・統計をLLMの出力へ置き換えません。

## 4. Cloudflare・Vercelと到達性

Network accessはCustomを使い、既定パッケージリストを保持します。追加するhostは
`nodejs.org`、`api.openai.com`、`api.cloudflare.com`、`cytellect.vercel.app`、
`*.vercel.app`、`*.workers.dev`。公開Fijiを検証する場合は固定manifestの配布hostも
追加します。接続不可と認証不足は別のエラーとして扱います。

Cloudflareは既存COMPASS側と同じアカウント内の**Cytellect専用Worker/D1**を使う
ユーザー承認があります。既存COMPASSのリソースは変更しません。
PCのWrangler OAuthをクラウドへコピーせず、専用の限定トークンを設定します。
Workers Scripts:Edit、D1:Edit、Account Settings:Readを指定し、アカウントを限定します。
CloudflareのAPI credentialsは`api.cloudflare.com`へのBearer設定で使えますが、
Wranglerがトークン無しで起動する保証はありません。認証前検査を実証し、非対応なら
RESTで同じ手順を行うか、明示したsecret管理方式に切り替えます。
D1の作成・migration・確認は接続済みのCloudflareコネクタでも実行できます。dummy tokenを設定して
動いたことにしません。トークンの値をClaudeの出力へ渡す操作は禁止です。

`ADMIN_TOKEN`はWorkerの招待管理用secretです。OpenAI/Cloudflareの認証とは別であり、
CLIへ渡すために通常環境変数へ置けばClaudeから読めます。生成・登録・保管を安全な
管理側の操作で行い、値をチャット・ログへ出さないでください。
本番OpenAIキーもWorkerのsecretに設定する必要があり、ClaudeのAPI proxyに登録しただけでは
Workerへ移りません。OFFでの公開はキーなしの既存公開スクリプトに従います。

VercelはGit→mainの既存自動デプロイを利用でき、ソースレビューやCIのための再認証は
不要です。プロジェクト設定・環境変数・保護previewへアクセスする場合にだけ、必要な
yuto10のconnector権限を確認します。認証の不足を理由にコード作業全体を止めません。

## 5. 完了として報告する範囲

- ソースのレビュー、無課金テスト、最新headの必須CI、main統合を分けて報告。
- API credentialsの登録・無料認証・実課金評価はそれぞれ実施証拠を確認。
- Worker/D1の新規作成・migration・OFF確認は実hostで確認。
- Windows配布はGitHub Actionsの実ZIP検査、Dockerは実際に起動可能な環境で受入。
- canonical本番の操作と、研究用PCのSmart App Controlは未実施なら未実施と報告。
- 新ワークスペースによるroot置換はユーザーの操作確認後。本番有料APIのONは別途予算承認後。

この文書と実装はクラウド作業の準備です。設定画面に登録した証拠なしに、認証や
クラウド実行が完了したとは報告しません。
