# セキュリティポリシー

[脆弱性を報告する](#脆弱性の報告) ｜ [English](#english)

Cytellect は、未発表の顕微鏡画像を研究者の PC の中で解析する。画像、輪郭、測定値、図を Cytellect のクラウドに保存しないので、クラウドやリポジトリが侵害されても、保存された研究データには届かない。クラウド GPU と AI の機能は任意で、使わなければ研究データは PC の外に出ない。

| 知りたいこと | 答え | 詳細 |
|---|---|---|
| 研究データはどこにあるか | 研究者の PC か研究室のサーバー。検出、測定、統計、作図もそこで行う | [研究データ](#研究データ) |
| 何が PC の外に出るか | 利用者がクラウド GPU か AI の機能を使ったときに、その処理に要るものだけ。表にすべて挙げている | [研究データ](#研究データ) |
| クラウドが侵害されたらどうなるか | 届くのは中継中のデータまでで、保存された研究データと PC のアプリには届かない | [侵害されたときの影響範囲](#侵害されたときの影響範囲) |
| AI の出力が解析を変えないか | 提案は検証済みの設定の下書きで、研究者が採用するまで使わない。測定と統計は共通の実装が計算する | [AI による解析支援](#ai-による解析支援) |
| 更新は本物か | 管理者の鍵で署名された版だけを PC が実行する。Store 版は Microsoft が署名する | [配布物の完全性](#配布物の完全性) |

## 現行の対策

### 研究データ

画像、輪郭（マスク）、測定表、図は、研究者の PC か研究室のサーバーの非公開の領域に置く。検出、測定、統計、作図はそこで行い、原画像の画素値は変えない。

PC の外に送るのは、利用者が次の操作をしたときだけである。Cytellect Worker は Cloudflare 上で動く Cytellect の中継サービスで、ログインと利用枠を確かめ、送り先の鍵を付けて転送する。

| 利用者の操作 | 送るもの | 送り先 | 送り先での扱い |
|---|---|---|---|
| クラウド GPU で細胞を検出する | 検出対象の 1 プレーンと検出の条件。核小体の検出では、採用済みの核のラベルも送る | Cytellect Worker を経て Modal | Worker は本文を読まずに転送し、推論サーバーはメモリの上だけで処理する。どちらも保存せず、ログに残さない |
| AI に解析を相談する | 研究の目的、チャンネル名と記録した染色、視野の名前（既定ではファイル名）と記録（条件、実験回、組、取得日）、画像の寸法と画素サイズ、視野と群の数、現在の解析の設定と前回の提案、代表的な 1 視野のチャンネルごとの縮小画像（一辺 512 px 以下。設定で止められる） | Cytellect Worker を経て Anthropic または OpenAI | Worker は本文を保存せず、ログに残さない。OpenAI には応答を保存しない設定（`store: false`）で送る。送ったデータはモデルの学習に使われない。提供元は、不正利用の監視などのために一定期間保持する場合がある |
| AI に考察の生成を依頼する | 保存した比較結果と実験の目的。比較結果は、画面のまとめ（見出しと要点）、指標の名前と定義、染色名、領域・群・実験回・チャンネルの名前、群ごとの値、差と信頼区間、実験回ごとの値、n とその内訳、集計と検定の方法、研究者が書いた実験単位の定義と対応の根拠、検定と p 値。目的の初期値は、そのワークスペースで AI への相談に書いた研究の目的 | 同上 | 同上 |
| クラウドにログインする | メールアドレスとログインのコード | Resend | コードをメールで届けるために使う |

- **送らないもの。** 原画像、輪郭、核ごとの測定値、ファイルのパスは、上の表にあるものを除いて送らない。
- **同意。** AI に送る範囲は、クラウドへのログインと最初の考察の生成のときに画面で示し、同意を得てから送る。範囲は AI の設定の画面でいつでも確かめられる（2026-11-16 のオーナーの判断。2026-11-17 に、考察の生成へまとめ・n の内訳・方法・目的を加えた。経緯は [LLM による解析支援の見直し](docs/drafts/llm-assistant/plan.md)）。
- **計測。** 導入したアプリと作業画面は、利用状況の計測（テレメトリ）を送らない。アクセス解析を使うのは `cytellect.app` の公開ページ（LP、デモ、ガイド）だけで、そこでは研究画像を受け付けない。EXE 版は、更新の有無を GitHub の公開リリース一覧で確かめる（多くても 6 時間に 1 回。研究データもアカウントの情報も送らない）。
- **通信と保管。** 外部との通信はすべて TLS で暗号化する。PC 上のデータと資格情報は OS の利用者だけが読める場所に置き、保存時の暗号化は OS の機能（BitLocker など）に委ねる。
- **保持期間。** Windows 版は、利用者が削除するまで作業データを保持する（EXE 版は、導入のときに 24 時間での自動削除も選べる）。Docker 版は最後の操作から 24 時間で失効して削除し、研究者自身の PC に限って手動での保持も選べる。
- **クラウドが保存するもの。** Cytellect のクラウドは研究データを保存しない。保存するのは、アカウントの記録（メールアドレス、承認の状態と日時、トークンとコードのハッシュ）と、利用量の記録（月ごとの GPU の秒数、解析提案ごとの費用とトークン数）だけである。

### 侵害されたときの影響範囲

1 か所が侵害されても被害が広がらないように、データ、鍵、権限を分けて置いている。

| 侵害されたもの | 届く範囲 | 届かないもの |
|---|---|---|
| 研究者のクラウドのアカウント | その利用者の GPU と解析提案の利用枠（月ごとの上限まで） | 研究データ（クラウドにない） |
| Cytellect Worker | 侵害の間に中継されるデータの閲覧と、推論結果や提案の改ざん | 保存された研究データ、アプリの更新（署名鍵は別に置く） |
| リポジトリへの書き込み権限 | ブランチと PR | `main` への反映（管理者のマージが要る）、導入済みの PC（更新には管理者の鍵による署名が要る） |

この設計は、PC の OS のアカウントと、その権限で動くプログラムを信頼している。PC を複数人で使うときは OS のアカウントを分け、ディスクの暗号化を有効にする。

### 認証とアクセス制御

- **研究者のログイン。** メールに届く 6 桁のコードでログインする。コードは管理者が許可したアドレスにだけ送り、10 分で失効する。5 回の誤りで無効、同じアドレスで 1 日 20 回の誤りで 24 時間ロックする。回数はアドレスごとに数えるので、IP を変えても試行は増えない。
- **PC が持つ資格情報。** ログインした PC が持つのは 256 bit の端末トークン 1 つだけで、90 日使わなければ失効し、サインアウトで消える。Anthropic、OpenAI、Modal の鍵は Cytellect Worker だけが持ち、PC にも配布物にも入れない。
- **サーバーが保存する情報。** トークンは SHA-256、コードは鍵付きの HMAC-SHA256 のハッシュでしか保存せず、IP アドレスは保存しない。管理者がアドレスを失効させると、そのアドレスでログインしたすべての端末が次の要求から拒否される。
- **管理者。** 運用に使うクラウドのアカウントは、すべてパスキーか認証アプリによる多要素認証を必須にしている。管理画面は Cloudflare Access の Google ログインの背後に置き、Worker も JWT の署名（RS256 に固定）、発行者、対象、有効期限、管理者のアドレスを自分で検証する。管理の経路は決めたオリジンでしか応答せず、`workers.dev` のような別の入口からは、有効なトークンがあっても入れない。新しい利用者は、署名した 1 回限りのリンクで承認し、リンクを開いただけでは承認されない。
- **PC 上の画面。** ローカルのサーバーは `127.0.0.1` だけで待ち受ける。Windows 版は、要求ごとに Host、Origin、Fetch Metadata を照合し、状態を変える要求には CSRF のヘッダーも求めて、他のサイトや DNS リバインディングからの操作を拒む。Docker 版は、状態を変える要求の Origin と CSRF のヘッダーを照合する。どちらも読み出しのたびに所有者を確かめ、他人のワークスペースは存在も返さない。
- **解析の実行環境。** Docker 版の解析ワーカーは、ネットワークのない、非 root で読み取り専用のコンテナで動く。

### AI による解析支援

- LLM の出力は、コードとして実行しない。
- 解析の提案は、決められた項目と値だけからなる設定として PC で検証する。決められていない項目があるものと、説明文に URL やコードのような文字列を含むものは拒否する。
- 提案は下書きで、研究者が採用するまで解析に使わない。採用しても、測定と統計は提案の内容にかかわらず共通の実装が計算する。
- 考察の下書きは、形式だけを確かめ、文章として比較結果に添えて保存する。解析の設定と数値は変えない。
- GPU の秒数と AI の費用には、利用者ごと・月ごとの上限がある。上限を超える要求は、送り先に渡さずに断る。

### 配布物の完全性

| 経路 | 確かめ方 |
|---|---|
| Microsoft Store 版（Windows 11） | Microsoft が署名し、導入と更新は Microsoft Store が行う |
| EXE 版のアプリ内更新 | 管理者の Ed25519 鍵で署名された manifest を、アプリに組み込んだ公開鍵で検証する。いまより新しい版で、インストーラーの SHA-256 とサイズが manifest と一致したときだけ実行する |
| EXE 版の最初の導入 | 同じ manifest でダウンロードを確かめられる（[手順](docs/install-windows.ja.md#2-ダウンロードと確認)）。インストーラー自体のコード署名（Authenticode）は、まだない |

- 署名鍵は、管理者の手元と、`main` に限定した専用の GitHub Actions 環境だけに置く。手動配布は管理者の承認を要する。管理者が有効にした EXE 自動配布では、保護された `main` 上で CI と配布試験を通過した版だけを公開する。
- 同梱する Fiji、検出モデル、Python の実行環境は、ビルドのときに SHA-256 で照合する。解析の実行中に、コードやモデルをダウンロードしない。
- リポジトリでは、`GITHUB_TOKEN` を既定で読み取り専用にし、依存をロックファイルとハッシュで固定している。ハッシュを検証した gitleaks で `main` と各 PR の Git の全履歴の秘密を走査し、CodeQL と依存の脆弱性の監査（pip-audit、pnpm audit）を CI で実行する。

## 対象とする版

| 版 | セキュリティ修正 |
|---|---|
| Microsoft Store 版 | ✅ Microsoft Store が最新版に更新する |
| EXE 版の最新のリリース | ✅ |
| `main`（`cytellect.app` とクラウド機能） | ✅ |
| それより前の EXE 版 | ❌ アプリ内の更新で最新版に移る |

## 対象範囲

このリポジトリのコード、Windows 版（Microsoft Store 版と EXE 版）、Docker 版、`cytellect.app`、Cytellect Worker、クラウド GPU の推論サーバーを対象とする。Cytellect による設定や使い方に起因する問題も対象に含む。同梱する第三者の部品（Fiji、Cellpose など）と、利用する外部サービス（Cloudflare、Modal、Anthropic、OpenAI、Resend、GitHub、Vercel、Microsoft Store）そのものの脆弱性は対象外とし、各開発元の窓口が扱う。

## 脆弱性の報告

脆弱性は、GitHub の非公開の報告機能で知らせる。リポジトリの **Security** タブで **Report a vulnerability** を選ぶと、報告者とリポジトリの管理者だけが読める形で送れる（[報告フォーム](https://github.com/genellect/cytellect/security/advisories/new)）。Issue、PR、ディスカッションなどの公開の場には書かない。

報告には、次の内容を含める。

- 対象のコミット、または Windows 版のバージョン
- 再現手順
- 想定される影響

再現には合成データか公開データを使う。

## 報告後の流れ

1. 合理的な報告には、3 日以内に返信する。
2. 影響する範囲と深刻度を評価し、報告者と共有する。
3. 非公開の Security Advisory で修正し、修正版を配布する。公開サイトとクラウド機能は本番に反映し、Windows 版は Microsoft Store と署名した更新で届ける。
4. 配布の後に Security Advisory を公開し、必要に応じて CVE を取得する。報告者が望めば、謝辞に名前を載せる。

公開済みの勧告は [Security Advisories](https://github.com/genellect/cytellect/security/advisories) にある。

## 開発での研究データの扱い

開発の場（Git、CI、ログ、開発用 AI）での研究データと認証情報の扱いは、[チーム開発ルール §6](docs/team-development.md#6-研究データの扱い)で定めている。データ保護の仕様と運用の詳細は、[データ保護と運用](docs/security.md)にある。

## English

[Report a vulnerability](#reporting-a-vulnerability)

Cytellect analyses researchers' unpublished microscopy images on the researcher's own PC. Images, masks, measurements and figures are never stored in the Cytellect cloud, so a compromise of the cloud or the repository cannot reach stored research data. Cloud GPU and AI features are optional; without them, research data never leaves the PC.

| Question | Answer | Details |
|---|---|---|
| Where is research data kept? | On the researcher's PC or the lab server, where detection, measurement, statistics and figures also run | [Research data](#research-data) |
| What leaves the PC? | Only what a cloud GPU or AI feature needs, when the user invokes it. The table lists everything | [Research data](#research-data) |
| What if the cloud is compromised? | Data in transit during the compromise is exposed; stored research data and the app on the PC are not | [Impact of a compromise](#impact-of-a-compromise) |
| Can AI output change an analysis? | A proposal is a validated draft of settings that is unused until the researcher adopts it. The shared implementation computes measurements and statistics | [AI assistance](#ai-assistance) |
| Is an update genuine? | The PC runs only releases signed with the maintainer's key. Microsoft signs the Store release | [Integrity of releases](#integrity-of-releases) |

### Current measures

#### Research data

Images, masks, measurement tables and figures stay in a private area of the researcher's PC or the lab server. Detection, measurement, statistics and figures run there, and original pixel values are never changed.

Data leaves the PC only when the user takes one of the actions below. The Cytellect Worker is Cytellect's relay on Cloudflare: it checks the sign-in and the quota, attaches the provider's key and forwards the request.

| User action | Data sent | Destination | Handling |
|---|---|---|---|
| Detecting cells on the cloud GPU | The plane to detect and the detection parameters; for nucleolar detection, also the adopted nuclear labels | Modal, through the Cytellect Worker | The Worker forwards the body without reading it and the inference server processes it in memory only. Neither stores or logs it |
| Asking the AI about an analysis | The research goal, channel names and recorded stains, field names (by default the file name) and records (condition, experimental unit, pair, acquisition date), image dimensions and pixel size, field and group counts, the current analysis settings and the previous proposal, and per-channel display-scaled previews (512 px or less per side) of one representative field, which the user can turn off in settings | Anthropic or OpenAI, through the Cytellect Worker | The Worker neither stores nor logs the body. Requests to OpenAI set `store: false`. The data is not used for model training. Each provider may retain it for a period, for example for abuse monitoring |
| Requesting a discussion draft from the AI | The saved comparison and the experiment purpose. The comparison holds the summary's heading and points on screen, the metric's name and definition, the stain name, the region, group, run and channel names, group values, differences and intervals, per-experiment values, counts and their breakdown, aggregation and test settings, the researcher's experimental-unit definition and pairing basis, and the test and its p-value. The purpose starts from the goal last written to the AI in the workspace | As above | As above |
| Signing in to the cloud | The e-mail address and the sign-in code | Resend | Used to deliver the code by e-mail |

- **Not sent.** Original images, masks, per-object measurements and file paths are not sent beyond what the table lists.
- **Consent.** The scope sent to the AI is shown on screen, and consent obtained, at cloud sign-in and at the first discussion draft. The AI settings panel shows the scope at any time (owner's decision, 2026-11-16; the summary, breakdown, method and purpose were added to discussion drafts on 2026-11-17; background in the [LLM assistance redesign](docs/drafts/llm-assistant/plan.md)).
- **Analytics.** The installed app and the workspace send no usage telemetry. Only the public pages of `cytellect.app` (landing page, demo and guides) use web analytics, and they accept no research images. The EXE release checks GitHub's public release list for a newer version, at most every six hours, sending no research data or account information.
- **Transport and storage.** All external traffic uses TLS. Data and credentials on the PC are readable only by the OS user; encryption at rest is left to the OS (BitLocker and similar).
- **Retention.** The Windows release keeps work data until the user deletes it (the EXE release also offers 24-hour automatic deletion at installation). The Docker release deletes it 24 hours after the last action, and manual retention is available only on the researcher's own PC.
- **What the cloud stores.** The Cytellect cloud stores no research data, only account records (e-mail address, approval state and times, hashes of tokens and codes) and usage records (monthly GPU seconds, cost and token counts per analysis proposal).

#### Impact of a compromise

Data, keys and permissions are kept apart so that one compromise does not spread.

| Compromised | Reaches | Does not reach |
|---|---|---|
| A researcher's cloud account | That user's GPU and analysis-proposal quota, up to the monthly limits | Research data (none is in the cloud) |
| The Cytellect Worker | Data relayed during the compromise, and tampering with inference results or proposals | Stored research data and app updates (the signing key is kept elsewhere) |
| Write access to the repository | Branches and pull requests | `main` (the maintainer merges) and installed PCs (updates require a signature made with the maintainer's key) |

This design trusts the PC's OS account and the programs running with its rights. On a shared PC, use separate OS accounts and enable disk encryption.

#### Authentication and access control

- **Researcher sign-in.** Researchers sign in with a six-digit code sent by e-mail, only to addresses the maintainer has allowed; a code expires after 10 minutes. Five wrong guesses void a code, and 20 per address per day lock the address for 24 hours. Attempts are counted per address, so changing IP addresses adds none.
- **Credentials on the PC.** A signed-in PC holds a single 256-bit device token, which expires after 90 days without use and is deleted on sign-out. Only the Cytellect Worker holds the Anthropic, OpenAI and Modal keys; they are never on the PC or in a release.
- **What the server stores.** Tokens are stored only as SHA-256 and codes only as keyed HMAC-SHA256; IP addresses are never stored. Revoking an address rejects every device signed in with it from the next request.
- **Maintainer.** Every cloud account used for operations requires multi-factor authentication with a passkey or an authenticator app. The admin page sits behind Cloudflare Access with Google sign-in, and the Worker itself verifies the JWT signature (RS256 only), issuer, audience, expiry and the maintainer's address. Admin routes answer only on the designated origin; other entry points such as `workers.dev` are refused even with a valid token. New users are approved through a signed single-use link, which approves nothing merely by being opened.
- **The screen on the PC.** The local server listens only on `127.0.0.1`. The Windows release checks the Host, Origin and Fetch Metadata headers of every request and also requires a CSRF header on state-changing requests, rejecting other sites and DNS rebinding. The Docker release checks the Origin and CSRF headers of state-changing requests. In both, every read checks ownership, and other users' workspaces are not even acknowledged.
- **Analysis runtime.** The Docker analysis worker runs in a container with no network, as non-root, on a read-only root.

#### AI assistance

- LLM output is never executed as code.
- An analysis proposal is validated on the PC as structured settings with fixed fields and values. Proposals with unknown fields, or with URLs or code-like text in their explanations, are rejected.
- A proposal is a draft and is not used until the researcher adopts it. Even then, measurements and statistics use the shared implementation whatever the proposal says.
- A discussion draft is checked for structure only and saved as text with its comparison. It changes no settings or values.
- GPU seconds and AI cost have per-user monthly limits. Requests over a limit are refused before they reach the provider.

#### Integrity of releases

| Channel | Verification |
|---|---|
| Microsoft Store release (Windows 11) | Signed by Microsoft; the Microsoft Store installs and updates it |
| In-app update of the EXE release | Verifies a manifest signed with the maintainer's Ed25519 key against the public key built into the app, and runs the installer only when the release is newer and its SHA-256 and size match the manifest |
| First installation of the EXE release | The download can be checked against the same manifest ([steps, in Japanese](docs/install-windows.ja.md#2-ダウンロードと確認)). The installer itself is not yet code-signed (Authenticode) |

- The signing key exists only with the maintainer and in dedicated GitHub Actions environments restricted to `main`. Manual releases require the maintainer's approval. When the maintainer has enabled automatic EXE distribution, only versions that passed CI and the distribution tests on protected `main` are published.
- The bundled Fiji, detection models and Python runtime are checked against SHA-256 hashes at build time. Nothing downloads code or models while an analysis runs.
- In the repository, `GITHUB_TOKEN` is read-only by default and dependencies are pinned by lockfiles and hashes. A hash-verified gitleaks scans the full Git history of `main` and of every pull request for secrets, and CodeQL and dependency vulnerability audits (pip-audit, pnpm audit) run in CI.

### Supported versions

| Version | Security fixes |
|---|---|
| The Microsoft Store release | ✅ Updated to the latest version by the Microsoft Store |
| The latest EXE release | ✅ |
| `main` (`cytellect.app` and the cloud features) | ✅ |
| Earlier EXE releases | ❌ Move to the latest release through the in-app update |

### Scope

This repository's code, the Windows releases (Microsoft Store and EXE), the Docker release, `cytellect.app`, the Cytellect Worker and the cloud GPU inference server are in scope, including problems caused by how Cytellect configures or uses a service. Vulnerabilities in bundled third-party components (Fiji, Cellpose and others) and in the external services themselves (Cloudflare, Modal, Anthropic, OpenAI, Resend, GitHub, Vercel, Microsoft Store) are out of scope and handled by their maintainers.

### Reporting a vulnerability

Report vulnerabilities privately with GitHub's **Report a vulnerability** form under the **Security** tab ([form](https://github.com/genellect/cytellect/security/advisories/new)), not in issues, pull requests or discussions. Include the affected commit or Windows release, reproduction steps and the expected impact, using only synthetic or public data.

### After a report

1. We reply to reasonable reports within three days.
2. We assess the affected scope and severity and share the assessment with the reporter.
3. We fix the issue in a private Security Advisory and release the fix: the public site and cloud features are deployed, and the Windows releases receive it through the Microsoft Store and a signed update.
4. After the release we publish the advisory, request a CVE where appropriate and credit the reporter if they wish.

Published advisories are listed under [Security Advisories](https://github.com/genellect/cytellect/security/advisories).

### Research data in development

Research data and credentials in development (Git, CI, logs, development AI) are handled under the [team development rules](docs/team-development.md#6-research-data). The data-protection specification and operating details are in [data protection and operations](docs/security.md).
