# セキュリティポリシー

Cytellect は、研究者の未発表の顕微鏡画像を研究者の PC で解析する。クラウドの GPU や AI による解析提案を使うときも、外に出るのは処理に必要な最小限のデータだけで、外部サービスの鍵は PC に置かない。アプリの更新は、管理者の鍵で署名されたものしか実行しない。

## 研究データの扱い

画像、マスク、測定表、図は、研究者の PC か研究室のサーバーの非公開の領域に置く。外部に送るのは次の場合に限る。

| 送り先 | 送るもの | 送り先での扱い |
|---|---|---|
| Modal（Cytellect Worker 経由） | クラウド GPU で細胞を検出するときの、検出対象の 1 プレーンと検出の条件 | 中継も推論も本文を保存せず、ログに残さない |
| OpenAI（Cytellect Worker 経由） | 利用者が有効にした解析提案での、研究の目的とメタデータ（チャネル名、寸法、群の数など） | `store: false` で送る |
| Resend | ログインのコードを届けるメールアドレス | — |

ファイル名、パス、実験条件、他のチャネル、測定値は送らない。測定と統計は PC で行い、原画像の画素値は変えない。作業データは最後の操作から 24 時間で失効して削除され、研究者自身の PC では手動での保持も選べる。

## 認証とアクセス制御

研究者は、メールに届く 6 桁のコードでクラウドの機能にログインする。コードが届くのは管理者が許可したアドレスだけで、5 回間違えると無効になり、同じアドレスで 1 日に 20 回間違えると 24 時間ロックされる。回数はアドレスごとに数えるので、IP アドレスを変えても試行は増えない。ログインした PC が受け取るのは 256 bit のデバイストークン 1 つで、OpenAI や Modal の鍵は Cytellect Worker だけが持ち、要求に付けて中継する。サーバーはトークンを SHA-256、コードを鍵付きの HMAC-SHA256 でしか保存せず、IP アドレスも保存しない。管理者がアドレスを失効させると、その利用者のすべての端末が次の要求から拒否される。

管理画面は Cloudflare Access の Google ログインの背後に置いている。Worker は Access の通過を前提にせず、受け取った JWT の署名（RS256 に固定）、発行者、対象、有効期限、管理者のアドレスを自分で検証する。管理の経路は決めたオリジンでしか応答せず、`workers.dev` のような別の入口からは、有効なトークンがあっても入れない。新しい利用者の承認は、署名した 1 回限りのリンクで行い、リンクを開いただけでは承認されない。

PC 上の画面とローカルのサーバーは `127.0.0.1` だけでつながり、要求ごとに Host、Origin、Fetch Metadata、CSRF のヘッダーを照合して、他のサイトや DNS リバインディングからの操作を拒む。データの読み出しのたびに所有者を確かめ、他人のワークスペースは存在も返さない。Docker 版の解析ワーカーは、ネットワークのない、非 root で読み取り専用のコンテナで動く。

## 配布物の完全性

Windows 版のアプリ内更新は、管理者の Ed25519 鍵で署名された manifest をアプリに組み込んだ公開鍵で検証し、インストーラーの SHA-256 とサイズが一致したときだけ実行する。署名鍵は管理者の手元と、管理者の承認なしには動かないリリースの環境にだけ置いており、リポジトリへの書き込み権限だけでは、利用者の PC でコードを実行させられない。最初の導入でも、同じ manifest でダウンロードを確かめられる（[手順](docs/install-windows.ja.md#2-ダウンロードと確認)）。

リポジトリでは、`GITHUB_TOKEN` を既定で読み取り専用にし、依存をロックファイルとハッシュで固定し、ハッシュを検証した gitleaks で Git の全履歴の秘密を走査している（[CI の構成](docs/ci.md)）。

仕様の詳細は[データ保護と運用](docs/security.md)にある。

## 脆弱性の報告

脆弱性は、GitHub の非公開の報告機能で知らせる。リポジトリの **Security** タブで **Report a vulnerability** を選ぶと、報告者とリポジトリの管理者だけが読める形で送れる（[報告フォーム](https://github.com/genellect/cytellect/security/advisories/new)）。Issue、PR、ディスカッションなどの公開の場には書かない。対象のコミットか Windows 版のバージョン、再現手順、想定される影響を、合成データか公開データで示す。合理的な報告には 3 日以内に返信する。

研究データと認証情報の扱いは、[チーム開発ルール §6](docs/team-development.md#6-研究データの扱い)で定めている。

## English

Cytellect analyses researchers' unpublished microscopy images on the researcher's own PC. When the cloud GPU or the AI analysis proposal is used, only the minimum each task needs leaves the PC, and no external service keys are kept there. The app runs only updates signed with the maintainer's key.

Data sent out is limited to one detection plane and its parameters for cloud GPU detection (via the Cytellect Worker to Modal, never stored or logged), the research goal and metadata for the opt-in analysis proposal (to OpenAI with `store: false`), and the e-mail address for sign-in codes (Resend). File names, paths, conditions, other channels and measurements are never sent. Work data expires and is deleted 24 hours after the last action.

Researchers sign in with a six-digit e-mailed code, sent only to addresses the maintainer allowed. Five wrong guesses void a code and 20 per address per day lock the address for 24 hours, so rotating IPs adds no attempts. The PC then holds a single 256-bit device token; only the Worker holds the third-party keys. The server stores tokens as SHA-256 and codes as keyed HMAC-SHA256, never IP addresses, and revoking an address stops all its devices at the next request. The admin page sits behind Cloudflare Access, and the Worker verifies the JWT (RS256 only, issuer, audience, expiry, address) itself; admin routes answer only on the designated origin. The local server listens on `127.0.0.1` and checks Host, Origin, Fetch Metadata and CSRF headers on every request, and every read checks ownership. The Docker analysis worker runs without network, as non-root, on a read-only root.

The in-app update verifies an Ed25519-signed manifest against the built-in public key and runs the installer only when its SHA-256 and size match. The signing key exists only with the maintainer and in an approval-gated release environment, so repository write access alone cannot run code on users' PCs. In the repository, `GITHUB_TOKEN` is read-only by default, dependencies are pinned by lockfiles and hashes, and a hash-verified gitleaks scans the full Git history. Specifications are in [Data protection and operations](docs/security.md).

Report vulnerabilities privately with GitHub's **Report a vulnerability** form under the **Security** tab ([form](https://github.com/genellect/cytellect/security/advisories/new)), not in issues, pull requests or discussions. Include the affected commit or Windows release, reproduction steps and the expected impact, using only synthetic or public data. We reply to reasonable reports within three days. Research data and credentials are handled under the [team development rules](docs/team-development.md#6-research-data).
