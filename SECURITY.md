# セキュリティポリシー

## 対象とする版

| 版 | セキュリティ修正 |
|---|---|
| Windows 版の最新のリリース | ✅ |
| `main`（`cytellect.app` とクラウド機能） | ✅ |
| それより前の Windows 版 | ❌ アプリ内の更新で最新版に移る |

## 脆弱性の報告

[非公開の報告フォーム](https://github.com/genellect/cytellect/security/advisories/new)から報告してほしい。Issue などの公開の場には書かないこと。合理的な報告には 3 日以内に返信し、修正版の配布後に [Security Advisories](https://github.com/genellect/cytellect/security/advisories) で公表する。再現には合成データか公開データを使い、研究データや認証情報を含めないこと。

## セキュリティの水準

| 対象 | 基準 | 現在の水準 |
|---|---|---|
| 研究データ | — | 解析は研究者の PC で行う。外部に出るのは、クラウド GPU に送る検出用の 1 プレーンと、オプトインの解析提案に送る目的とメタデータだけ。中継は本文を保存もログもしない |
| 研究者のログイン | NIST SP 800-63B（2025） | メールのワンタイムコードによる単要素の認証。同書は電子メールを帯域外認証に認めていないため、AAL1 の認証器には当たらない。試行の制限（コードごとに 5 回、アドレスごとに 1 日 20 回）は、同書の上限（連続 100 回）より厳しい |
| 管理者のログイン | NIST SP 800-63B（2025） | Cloudflare Access 経由の Google SSO。Worker でも JWT（RS256 に固定、`iss`・`aud`・`exp`・アドレス）を独立に検証し、Access を迂回する経路を閉じている。認証の強さは Google アカウントの設定による |
| 配布物 | SLSA v1.0 Build | L0（来歴の証明はない）。アプリ内の更新は Ed25519 で署名した manifest を検証してから実行し、署名鍵は承認制の GitHub Environment に隔離している |
| 解析の実行環境（Docker 版） | — | 非 root、`network_mode: none`、読み取り専用のルート、`cap_drop: ALL`、`no-new-privileges` |

仕様の詳細は[データ保護と運用](docs/security.md)にある。

## 脆弱性として扱わないもの

次は設計上の前提か既知の制約で、脆弱性としては受け付けない。

- **同じ OS アカウントの権限を持つ者による操作。** Windows 版は単一利用者のアプリで、ローカルのサーバーは `127.0.0.1` で待ち受ける。同じ OS アカウントで動くプロセスは信頼の内側にある。
- **ログインの応答から、アドレスの状態（許可・承認待ち・失効）が分かること。** PC が状態に合った画面を出すための設計で、IP ごとの回数の制限で列挙を抑えている。
- **誤ったコードを繰り返し入力して、他人のアドレスを最長 1 日ロックできること。** 総当たりを防ぐロックの副作用で、運用者は鍵の交換で解除できる。
- **Windows のインストーラーに Authenticode の署名がないこと。** 最初の導入は、署名付きの manifest で確認できる（[手順](docs/install-windows.ja.md#2-ダウンロードと確認)）。
- **Docker Desktop の所有者モードを、ループバック以外に公開した場合の問題。** このモードはループバックでの利用を前提にしており、公開は誤った設定にあたる。
- **解析提案の要求が、OpenAI の不正利用の監視のために保持されること。** 提供元のデータ方針による。

## English

### Supported versions

Security fixes go to the latest Windows release and to `main` (`cytellect.app` and the cloud features). Earlier Windows releases move to the latest one through the in-app update.

### Reporting a vulnerability

Report through the [private reporting form](https://github.com/genellect/cytellect/security/advisories/new), not in public issues. We reply to reasonable reports within three days and publish an advisory under [Security Advisories](https://github.com/genellect/cytellect/security/advisories) after the fix is released. Reproduce with synthetic or public data only, without research data or credentials.

### Security level

| Scope | Standard | Current level |
|---|---|---|
| Research data | — | Analysis runs on the researcher's PC. Only one detection plane leaves it for cloud GPU inference, and only the goal and metadata for the opt-in analysis proposal; the relay neither stores nor logs bodies |
| Researcher sign-in | NIST SP 800-63B (2025) | Single-factor e-mail one-time code. The standard does not allow e-mail for out-of-band authentication, so this is not an AAL1 authenticator. Throttling (5 attempts per code, 20 per address per day) is stricter than the standard's limit of 100 consecutive failures |
| Admin sign-in | NIST SP 800-63B (2025) | Google SSO through Cloudflare Access, with independent JWT verification at the Worker (RS256 only; `iss`, `aud`, `exp` and address) that closes routes bypassing Access. Strength depends on the Google account's settings |
| Distribution | SLSA v1.0 Build | L0 (no provenance). The in-app update runs only after verifying an Ed25519-signed manifest, and the signing key is isolated in an approval-gated GitHub Environment |
| Analysis runtime (Docker) | — | Non-root, `network_mode: none`, read-only root, `cap_drop: ALL`, `no-new-privileges` |

Specifications are in [Data protection and operations](docs/security.md).

### Not treated as vulnerabilities

- Actions by anyone with the same OS account's privileges: the Windows app is single-user and listens on `127.0.0.1`; processes of that account are trusted.
- The sign-in response revealing an address's state (allowed, pending, revoked): a design choice so the PC shows the matching screen, with per-IP limits against enumeration.
- Locking someone else's address for up to a day with wrong codes: the side effect of the brute-force lockout, which operators can clear by rotating the key.
- The Windows installer lacking an Authenticode signature: a first installation can be checked against the signed manifest.
- Exposing the Docker Desktop owner mode beyond loopback: a misconfiguration.
- OpenAI retaining analysis-proposal requests for abuse monitoring: the provider's data policy.
