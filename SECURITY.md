# セキュリティポリシー

設計原則は、データ最小化、最小権限、多層防御（前段に頼らず各層で検証）、フェイルクローズ、署名による信頼の起点の 5 つ。

## 対策

| 領域 | 実装 |
|---|---|
| データ最小化 | 解析はローカルで行う。クラウド推論に送るのは検出対象の 1 プレーンと検出条件だけで、ファイル名・パス・他チャネルは送らない。中継は本文を読まず、保存もログもしない。LLM による解析提案はオプトインで、研究の目的とメタデータだけを `store: false` で送る |
| 利用者の認証 | メールの OTP（6 桁、10 分、HMAC-SHA256 で保存）。5 回の誤りでコードを無効化し、アドレス単位で 1 日 20 回の誤りで 24 時間ロックアウトする（IP を変えても試行は増えず、/64 単位のレート制限も併用）。認証後は 256 bit のデバイストークン（SHA-256 で保存、90 日の非使用で失効、サーバー側で即時失効） |
| 管理者の認証 | Cloudflare Access（Google SSO）の背後に置き、オリジン（Worker）でも JWT を独立に検証する。RS256 に固定（alg confusion を防ぐ）、`iss`・`aud`・`exp`・`nbf`・メールを照合し、JWKS は 10 分キャッシュ、未知の `kid` での再取得は 30 秒に 1 回まで。管理経路は指定のオリジンだけで応答し、`workers.dev` などの迂回経路は有効なトークンでも拒否する |
| 承認フロー | HMAC 署名の 1 回限りのリンク（7 日）。GET では承認せず、POST で確定するので、メールのリンクスキャナーでは承認されない |
| 秘密の管理 | 認証情報の仲介。クライアントは第三者の API キーを持たず、Worker が付与して転送する。トークンとコードは保存時にハッシュ化し、ログに残さない。IP はレート制限用の鍵付きハッシュとしてだけ扱う |
| ローカル API | ループバック限定。Host・Origin・Fetch Metadata・CSRF ヘッダーを検証し、DNS リバインディングとクロスサイトの要求を拒否する。セッションは HttpOnly・SameSite=Strict の cookie |
| 認可 | 全オブジェクトでセッションの所有者を検証し、他人のリソースは存在も返さない（IDOR 対策） |
| 更新の完全性 | Ed25519 で署名した manifest を、アプリに組み込んだ公開鍵で検証し、インストーラーの SHA-256 とサイズを照合してから実行する。リリース資産のハッシュは信頼の根拠にしない。署名鍵は承認制の GitHub Environment に隔離しており、リポジトリへの書き込み権限だけでは利用者の PC でコードを実行できない |
| 実行環境の隔離 | 解析ワーカーは非 root・`network_mode: none`・読み取り専用ルート・`cap_drop: ALL`・`no-new-privileges` のコンテナで動く。プロセスの監視はリースで相互に確認し、確認できなければ停止して結果を公開しない |
| Web | 厳格な CSP（`frame-ancestors 'none'`、`object-src 'none'`）、`no-store`、`nosniff`、`no-referrer`。計測タグは分離した文書に閉じ込め、解析画面には読み込まない |
| サプライチェーン | 依存はロックファイルで、外部の成果物は SHA-256 で固定する。秘密の走査はハッシュを検証した gitleaks で Git の全履歴に行う。`GITHUB_TOKEN` は既定で読み取り専用。Dependabot alerts、`pip-audit`、CycloneDX の SBOM |

各項目の仕様は[データ保護と運用](docs/security.md)にある。

## 既知の制約

- Windows のインストーラーには Authenticode の署名がない。最初の導入では、署名付きの manifest で手動で確認できる（[手順](docs/install-windows.ja.md#2-ダウンロードと確認)）。
- Windows 版は単一利用者のモデルで、同じ OS アカウントのプロセスを信頼の内側に置く。外向きの通信は OS のファイアウォールでは制限しない。
- ログインの応答から、アドレスの状態（許可・承認待ち・失効）が分かる。

## 脆弱性の報告

[非公開の報告フォーム](https://github.com/genellect/cytellect/security/advisories/new)から報告してほしい。公開の Issue には書かないこと。合理的な報告には 3 日以内に返信する。

## English

Design principles: data minimisation, least privilege, defence in depth (every layer verifies on its own), fail-closed, and signatures as the root of trust.

| Area | Implementation |
|---|---|
| Data minimisation | Analysis runs locally. Cloud inference receives only the one detection plane and its parameters, never file names, paths or other channels; the relay neither reads, stores nor logs the body. The LLM analysis proposal is opt-in and sends only the research goal and metadata, with `store: false` |
| User authentication | E-mail OTP (6 digits, 10 minutes, stored as HMAC-SHA256). Five wrong guesses void a code; 20 per address per day lock the address for 24 hours, so rotating IPs adds no attempts (/64 rate limits apply as well). Then a 256-bit device token (stored as SHA-256, expires after 90 days unused, revocable server-side at once) |
| Admin authentication | Behind Cloudflare Access (Google SSO), with independent JWT verification at the origin Worker: RS256 only (no algorithm confusion), `iss`, `aud`, `exp`, `nbf` and e-mail checked, JWKS cached for 10 minutes and refetched for an unknown `kid` at most every 30 seconds. Admin routes answer only on the designated origin; bypass routes such as `workers.dev` are refused even with a valid token |
| Approval flow | HMAC-signed single-use links (7 days). GET never approves; a POST confirms, so mail link scanners cannot approve |
| Secrets | Credential brokering: clients hold no third-party API keys; the Worker attaches them and forwards. Tokens and codes are hashed at rest and never logged; IPs exist only as keyed hashes for rate limiting |
| Local API | Loopback only. Host, Origin, Fetch Metadata and CSRF headers are verified, rejecting DNS rebinding and cross-site requests. HttpOnly, SameSite=Strict session cookies |
| Authorisation | Ownership is checked on every object; other users' resources are not even acknowledged (IDOR protection) |
| Update integrity | An Ed25519-signed manifest is verified against the public key built into the app, and the installer's SHA-256 and size are matched before it runs. Release-asset hashes are not trusted. The signing key is isolated in an approval-gated GitHub Environment, so repository write access alone cannot run code on users' PCs |
| Isolation | The analysis worker runs non-root with `network_mode: none`, a read-only root, `cap_drop: ALL` and `no-new-privileges`. Supervision uses mutually checked leases and stops without publishing results when it cannot verify them |
| Web | Strict CSP (`frame-ancestors 'none'`, `object-src 'none'`), `no-store`, `nosniff`, `no-referrer`; analytics confined to a separate document and never loaded in the analysis workspace |
| Supply chain | Dependencies pinned by lockfiles and external artifacts by SHA-256; full-history secret scanning with a hash-verified gitleaks; read-only `GITHUB_TOKEN` by default; Dependabot alerts, `pip-audit` and a CycloneDX SBOM |

Known limitations: the Windows installer has no Authenticode signature (a first installation can be checked against the signed manifest); the Windows app follows a single-user model that trusts processes of the same OS account and does not restrict outbound traffic with the OS firewall; the login response reveals an address's state.

Report vulnerabilities through the [private reporting form](https://github.com/genellect/cytellect/security/advisories/new), not in public issues. We reply to reasonable reports within three days. Specifications are in [Data protection and operations](docs/security.md).
