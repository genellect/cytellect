# セキュリティポリシー

Cytellect は、研究者の未発表の顕微鏡画像を研究者の PC で解析する。研究データはクラウドに保存しないため、クラウド側が侵害されても、保存された画像と測定値には届かない。

## 現行の対策

### 研究データ

画像、マスク、測定表、図は、研究者の PC か研究室のサーバーの非公開の領域に置く。外部に送るのは次の場合に限る。

| 送り先 | 送るもの | 送り先での扱い |
|---|---|---|
| Modal（Cytellect Worker 経由） | クラウド GPU で細胞を検出するときの、検出対象の 1 プレーンと検出の条件。核小体の検出では、採用済みの核のラベルも送る | 中継も推論も本文を保存せず、ログに残さない |
| OpenAI（Cytellect Worker 経由） | 利用者が AI に解析の指示を送ったときの、研究の目的とメタデータ（チャネル名、寸法、群の数など） | `store: false` で送る |
| Resend | ログインのコードと、それを届けるメールアドレス | — |

- ファイル名、パス、実験条件、他のチャネル、測定値は送らない。
- 測定と統計は PC で行い、原画像の画素値は変えない。
- 外部との通信はすべて TLS で暗号化する。PC 上のデータと資格情報は OS の利用者だけが読める場所に置き、保存時の暗号化は OS の機能（BitLocker など）に委ねる。
- 作業データは、Windows 版では利用者が削除するまで保持する（24 時間で自動削除する設定も選べる）。Docker 版では最後の操作から 24 時間で失効して削除し、研究者自身の PC に限って手動での保持も選べる。
- Cytellect のクラウドは研究データを保存しない。保存するのは、アカウントの記録（メールアドレス、承認の状態、トークンとコードのハッシュ）と利用量の記録（月ごとの GPU の秒数、解析提案ごとの費用とトークン数）である。

### 侵害されたときの影響範囲

| 侵害されたもの | 届く範囲 | 届かないもの |
|---|---|---|
| 研究者のクラウドのアカウント | その利用者の GPU と解析提案の利用枠 | 研究データ（クラウドにない） |
| Cytellect Worker | 侵害の間に中継されるデータの閲覧と、推論結果や提案の改ざん | 保存された研究データ、アプリの更新（署名鍵は別に置く） |
| リポジトリへの書き込み権限 | ブランチと PR | `main` への反映（管理者のマージが要る）、導入済みの PC（更新には管理者の署名が要る） |

### 認証とアクセス制御

- 研究者：メールに届く 6 桁のコードでログインする。コードは管理者が許可したアドレスにだけ送り、5 回の誤りで無効、同じアドレスで 1 日 20 回の誤りで 24 時間ロックする。回数はアドレスごとに数えるので、IP を変えても試行は増えない。
- 資格情報：ログインした PC が持つのは 256 bit のデバイストークン 1 つだけで、OpenAI と Modal の鍵は Cytellect Worker だけが持つ。サーバーはトークンを SHA-256、コードを鍵付きの HMAC-SHA256 でしか保存せず、IP アドレスは保存しない。管理者がアドレスを失効させると、その利用者のすべての端末が次の要求から拒否される。
- 管理者：運用に使うクラウドのアカウントは、すべてパスキーか認証アプリによる多要素認証を必須にしている。管理画面は Cloudflare Access の Google ログインの背後に置き、Worker も JWT の署名（RS256 に固定）、発行者、対象、有効期限、管理者のアドレスを自分で検証する。管理の経路は決めたオリジンでしか応答せず、`workers.dev` のような別の入口からは、有効なトークンがあっても入れない。新しい利用者は、署名した 1 回限りのリンクで承認し、リンクを開いただけでは承認されない。
- PC 上の画面：ローカルのサーバーは `127.0.0.1` だけで待ち受け、要求ごとに Host、Origin、Fetch Metadata、CSRF のヘッダーを照合して、他のサイトや DNS リバインディングからの操作を拒む。読み出しのたびに所有者を確かめ、他人のワークスペースは存在も返さない。
- 解析の実行環境：Docker 版の解析ワーカーは、ネットワークのない、非 root で読み取り専用のコンテナで動く。

### AI による解析提案

LLM の出力はコードとして実行しない。決められた項目と値だけからなる構造化した設定として PC で検証し、URL やコードのような文字列を含むものは拒否する。測定と統計は、提案の内容にかかわらず共通の実装で計算する。

### 配布物の完全性

- Windows 版のアプリ内更新は、管理者の Ed25519 鍵で署名された manifest をアプリに組み込んだ公開鍵で検証し、インストーラーの SHA-256 とサイズが一致したときだけ実行する。
- 署名鍵は管理者の手元と、管理者の承認なしには動かないリリースの環境にだけ置く。リポジトリへの書き込み権限だけでは、利用者の PC でコードを実行させられない。
- 最初の導入でも、同じ manifest でダウンロードを確かめられる（[手順](docs/install-windows.ja.md#2-ダウンロードと確認)）。
- リポジトリでは `GITHUB_TOKEN` を既定で読み取り専用にし、依存をロックファイルとハッシュで固定し、ハッシュを検証した gitleaks で Git の全履歴の秘密を走査している。

## 対象とする版

| 版 | セキュリティ修正 |
|---|---|
| Windows 版の最新のリリース | ✅ |
| `main`（`cytellect.app` とクラウド機能） | ✅ |
| それより前の Windows 版 | ❌ アプリ内の更新で最新版に移る |

## 対象範囲

このリポジトリのコード、Windows 版、Docker 版、`cytellect.app`、Cytellect Worker を対象とする。同梱する第三者の部品（Fiji、Cellpose など）そのものの脆弱性は対象外とし、各開発元の窓口が扱う。

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
3. 非公開の Security Advisory で修正し、修正版を配布する。公開サイトとクラウド機能は本番に反映し、Windows 版は署名した更新で届ける。
4. 配布の後に Security Advisory を公開し、必要に応じて CVE を取得する。報告者が望めば、謝辞に名前を載せる。

公開済みの勧告は [Security Advisories](https://github.com/genellect/cytellect/security/advisories) にある。

## 研究データの扱い

研究データと認証情報の扱いは、[チーム開発ルール §6](docs/team-development.md#6-研究データの扱い)で定めている。

## English

### Current measures

Cytellect analyses researchers' unpublished microscopy images on the researcher's own PC. Research data is never stored in the cloud, so a compromise on the cloud side cannot reach stored images or measurements.

#### Research data

Images, masks, measurement tables and figures stay in a private area of the researcher's PC or the lab server. Data leaves it only in these cases:

| Destination | Data | Handling |
|---|---|---|
| Modal (via the Cytellect Worker) | The plane to detect and the detection parameters for cloud GPU cell detection; for nucleolar detection, also the adopted nuclear labels | Neither the relay nor inference stores or logs the body |
| OpenAI (via the Cytellect Worker) | The research goal and metadata (channel names, dimensions, group counts) when the user sends an instruction to the AI | Sent with `store: false` |
| Resend | The sign-in code and the e-mail address it is sent to | — |

- File names, paths, conditions, other channels and measurements are never sent.
- Measurements and statistics run on the PC, and original pixel values are never changed.
- All external traffic uses TLS. Data and credentials on the PC are readable only by the OS user; encryption at rest is left to the OS (BitLocker and similar).
- The Windows release keeps work data until the user deletes it (24-hour automatic deletion is optional). The Docker release deletes it 24 hours after the last action, and manual retention is available only on the researcher's own PC.
- The Cytellect cloud stores no research data, only account records (e-mail address, approval state, hashes of tokens and codes) and usage records (monthly GPU seconds, cost and token counts per analysis proposal).

#### Impact of a compromise

| Compromised | Reaches | Does not reach |
|---|---|---|
| A researcher's cloud account | That user's GPU and analysis-proposal quota | Research data (none is in the cloud) |
| The Cytellect Worker | Data relayed during the compromise, and tampering with inference results or proposals | Stored research data and app updates (the signing key is kept elsewhere) |
| Write access to the repository | Branches and pull requests | `main` (the maintainer merges) and installed PCs (updates require the maintainer's signature) |

#### Authentication and access control

- Researchers sign in with a six-digit code sent by e-mail, only to addresses the maintainer has allowed. Five wrong guesses void a code, and 20 per address per day lock the address for 24 hours, so changing IP addresses adds no attempts.
- A signed-in PC holds a single 256-bit device token; only the Cytellect Worker holds the OpenAI and Modal keys and attaches them when relaying. The server stores tokens as SHA-256 and codes as keyed HMAC-SHA256, and never stores IP addresses. Revoking an address rejects all of that user's devices from the next request.
- Every cloud account used for operations requires multi-factor authentication with a passkey or an authenticator app. The admin page sits behind Cloudflare Access with Google sign-in, and the Worker itself verifies the JWT signature (RS256 only), issuer, audience, expiry and the maintainer's address. Admin routes answer only on the designated origin; other entry points such as `workers.dev` are refused even with a valid token. New users are approved through a signed single-use link, which approves nothing merely by being opened.
- The local server listens only on `127.0.0.1` and checks the Host, Origin, Fetch Metadata and CSRF headers of every request, rejecting other sites and DNS rebinding. Every read checks ownership, and other users' workspaces are not even acknowledged.
- The Docker analysis worker runs in a container with no network, as non-root, on a read-only root.

#### AI analysis proposals

LLM output is never executed as code. It is validated on the PC as structured settings with fixed fields and values, and output containing URLs or code-like text is rejected. Measurements and statistics use the shared implementation whatever the proposal says.

#### Integrity of releases

- The in-app update of the Windows release verifies a manifest signed with the maintainer's Ed25519 key against the public key built into the app, and runs the installer only when its SHA-256 and size match.
- The signing key exists only with the maintainer and in a release environment that cannot run without the maintainer's approval, so write access to the repository alone cannot run code on users' PCs.
- A first installation can be checked against the same manifest ([steps, in Japanese](docs/install-windows.ja.md#2-ダウンロードと確認)).
- In the repository, `GITHUB_TOKEN` is read-only by default, dependencies are pinned by lockfiles and hashes, and a hash-verified gitleaks scans the full Git history for secrets.

### Supported versions

| Version | Security fixes |
|---|---|
| The latest Windows release | ✅ |
| `main` (`cytellect.app` and the cloud features) | ✅ |
| Earlier Windows releases | ❌ Move to the latest release through the in-app update |

### Scope

This repository's code, the Windows and Docker releases, `cytellect.app` and the Cytellect Worker are in scope. Vulnerabilities in bundled third-party components such as Fiji or Cellpose are out of scope and handled by their maintainers.

### Reporting a vulnerability

Report vulnerabilities privately with GitHub's **Report a vulnerability** form under the **Security** tab ([form](https://github.com/genellect/cytellect/security/advisories/new)), not in issues, pull requests or discussions. Include the affected commit or Windows release, reproduction steps and the expected impact, using only synthetic or public data.

### After a report

1. We reply to reasonable reports within three days.
2. We assess the affected scope and severity and share the assessment with the reporter.
3. We fix the issue in a private Security Advisory and release the fix: the public site and cloud features are deployed, and the Windows release receives a signed update.
4. After the release we publish the advisory, request a CVE where appropriate and credit the reporter if they wish.

Published advisories are listed under [Security Advisories](https://github.com/genellect/cytellect/security/advisories). Research data and credentials are handled under the [team development rules](docs/team-development.md#6-research-data).
