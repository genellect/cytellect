# セキュリティポリシー

Cytellect は、研究者の未発表の顕微鏡画像を扱う。画像は研究者の手元で解析し、クラウドを使う機能でも、外に出すのは処理に必要な最小限に限る。

## 方針

- 研究データは研究者の管理下に置く。外部に送る機能は利用者が有効にしたときだけ動き、送る内容は機能ごとに決めておく。
- 鍵は、それを使う場所にだけ置く。研究者の PC は外部サービスの鍵を持たず、サーバーはトークンとコードをハッシュでしか持たない。
- 信頼は検証で決める。認証は手前の防御に頼らず各層で確かめ、配布物は署名で確かめる。
- 確かめられないときは止める。設定の不備や障害で、処理や要求を通すことはしない。

## 現行の対策

### 研究データ

画像、マスク、測定表、図は、研究者の PC（または研究室のサーバー）の非公開のディレクトリに置く。外に送るのは次の場合だけである。

| 機能 | 送るもの | 送らないもの |
|---|---|---|
| クラウド GPU での細胞検出 | 検出に使う 1 平面と検出の条件 | ファイル名、ワークスペース名、実験条件、パス、他のチャネル |
| AI による解析提案（既定で無効） | 研究の目的と、チャネル名や寸法などのメタデータ | パス、マスク、測定表、文書 |
| ログイン | メールアドレス | — |

推論の中継は本文を読まず、保存も記録もしない。測定と統計は PC で行い、原画像の画素値は変えない。作業データは最後の操作から 24 時間で失効して削除される。研究者自身の PC では、手動での保持も選べる。

### 認証

| 利用者 | 認証の方法 | 守り |
|---|---|---|
| 研究者（クラウド機能） | メールに届く 6 桁のコードでログインし、PC にデバイストークンを 1 つ受け取る | コードは許可したアドレスにだけ送る。5 回の誤りで無効、1 日 20 回の誤りでアドレスごとロックするため、IP を変えても試行は増えず、1 日に当たる確率は 5 万分の 1。トークンは発行元にだけ送り、90 日使わなければ失効する。管理者が失効させると、全端末が次の要求から拒否される |
| 管理者 | Cloudflare Access の Google ログイン | Worker 自身が、アクセストークンの RS256 の署名、発行者、対象、期限、管理者のアドレスを検証する。別の入口（`workers.dev` など）は、正しいトークンがあっても閉じている |
| PC 上の画面 | `127.0.0.1` だけで待ち受けるローカルのサーバー | 要求ごとに Host、Origin、Fetch Metadata、CSRF のヘッダーを照合し、他のサイトや DNS リバインディングからの操作を拒む。他人のワークスペースは存在も分からない |

トークンは 32 バイトの乱数で作り、SHA-256 のハッシュだけを保存する。ログインコードは鍵付きの HMAC で保存するため、データベースが漏れても総当たりできない。IP アドレスは保存しない。新しい利用者の承認は、署名した 1 回限りのリンクで行い、リンクを開いただけでは承認されない。

### 更新

Windows 版のアプリ内更新は、管理者の Ed25519 鍵で署名された manifest を検証し、インストーラーのハッシュが一致したときだけ実行する。署名鍵は、管理者の手元と、管理者の承認なしには動かないリリースの環境にだけ置いている。リポジトリへの書き込み権限を奪われても、利用者の PC で更新を実行させることはできない。最初の導入でも、同じ manifest でダウンロードしたファイルを確かめられる（[手順](docs/install-windows.ja.md#2-ダウンロードと確認)）。

### 実行環境

解析エンジンは、ネットワークのない、読み取り専用で権限のないコンテナで動く（Docker 版）。親子のプロセスが互いの状態を確かめられなくなったときは、計算を止めて結果を公開しない。

各対策の詳細は[データ保護と運用](docs/security.md)にある。

## 脆弱性の報告

脆弱性は、Issue などの公開の場ではなく、[非公開の報告フォーム](https://github.com/genellect/cytellect/security/advisories/new)で知らせてほしい。対象の版、再現手順、想定される影響を、合成データか公開データで示してもらえると助かる。合理的な報告には 3 日以内に返信する。

## English

Cytellect handles researchers' unpublished microscopy images. Images are analysed on the researcher's own PC; the cloud features send only the minimum each task needs (one detection plane and its parameters for cloud GPU detection; the research goal and metadata for the optional AI analysis proposal), never file names or paths. A PC holds a single device token from an e-mailed six-digit code and no external service keys; the server stores tokens and codes only as hashes, and per-address limits keep a code from being guessed. The admin page sits behind Cloudflare Access, and the Worker verifies the access token's signature, issuer, audience, expiry and address itself. In-app updates run only after a manifest signed with the maintainer's Ed25519 key is verified, so repository write access alone cannot run code on users' PCs. Details are in [Data protection and operations](docs/security.md).

Report vulnerabilities through the [private reporting form](https://github.com/genellect/cytellect/security/advisories/new), not in public issues. We reply to reasonable reports within three days.
