# セキュリティポリシー

Cytellect は研究者の未発表の画像を扱う。脆弱性の報告の受け付け方、報告後の対応、プロジェクトとしての安全への取り組みを次に定める。

## 対象とする版

| 対象 | セキュリティ修正 |
|---|---|
| Windows 版の最新のリリース | 対象 |
| `main`（公開サイト `cytellect.app` とクラウド機能） | 対象 |
| それより前の Windows 版 | 対象外。アプリ内の更新か新しいインストーラーで最新版に移る |

## 脆弱性の報告

脆弱性は、GitHub の非公開の報告機能で知らせる。リポジトリの **Security** タブで **Report a vulnerability** を選ぶと、報告者とリポジトリの管理者だけが読める形で送れる（[報告フォーム](https://github.com/genellect/cytellect/security/advisories/new)）。Issue、PR、ディスカッションなどの公開の場には書かない。

報告には、次の内容を含める。

- 対象のコミット、または Windows 版のバージョン
- 再現手順
- 想定される影響

再現には合成データか公開データを使い、研究データや認証情報を含めない。

## 報告後の流れ

1. 合理的な報告には、3 日以内に返信する。
2. 影響する範囲と深刻度を評価し、報告者と共有する。
3. GitHub Security Advisory の非公開のフォークで修正し、通常と同じ CI を通す。
4. 修正版を配布する。公開サイトとクラウド機能は本番に反映し、Windows 版は署名した更新で届ける。
5. 配布の後に Security Advisory を公開し、必要に応じて CVE を取得する。報告者が望めば、謝辞に名前を載せる。

修正版の配布までは、報告の内容を公開しないよう報告者にお願いしている。公開済みの勧告は [Security Advisories](https://github.com/genellect/cytellect/security/advisories) にある。

## プロジェクトの取り組み

### 開発

- `main` への変更はすべて PR を通す。ルールセットが直接の push と force push を拒み、必須の CI、最新の `main` の取り込み、レビューでの会話の解決を求める。
- オーナー以外の PR には、別のメンバーの承認が要る。PR ごとに、コードとセキュリティの自動レビューが走る。
- GitHub Actions のトークンは、既定で読み取りだけに限る。書き込みは、リリースの作成など必要なジョブにだけ与える。PR の CI には秘密を渡さない。
- 依存はロックファイル（`uv.lock`、`pnpm-lock.yaml`）で固定し、Fiji と Cellpose の成果物は SHA-256 で固定する。既知の脆弱性は Dependabot alerts と `pip-audit` で監視し、CI が CycloneDX 形式の SBOM を出力する。
- CI は、版とハッシュを固定した gitleaks で Git の全履歴を走査し、秘密の混入を防ぐ。

### 配布

- Windows 版のアプリ内更新は、オーナーの Ed25519 鍵で署名された manifest を検証し、インストーラーのハッシュが一致したときだけ実行する。署名は、オーナーの承認が要る GitHub の `release` 環境でだけ行う。リポジトリへの書き込み権限だけでは、利用者の PC で更新を実行させられない。
- 最初の導入でも、署名付きの manifest でダウンロードしたファイルを確かめられる（[ダウンロードと確認](docs/install-windows.ja.md#2-ダウンロードと確認)）。
- 同梱した GPL などの部品のソースは、固定したハッシュで照合してからリリースに添付する。

### 製品

- 研究画像は研究者の PC で解析する。クラウドの GPU や解析提案を使うときも、送るのは処理に必要な最小限のデータだけで、ファイル名やパスは送らない。
- クラウド機能には、メールに届く 6 桁のコードでログインする。PC が持つのはデバイストークン 1 つだけで、外部サービスの鍵は Cytellect Worker だけが持つ。サーバーはトークンとコードをハッシュで保存する。
- 管理画面は Cloudflare Access の背後に置き、Worker 自身もアクセストークンの署名、発行者、対象、期限、管理者のアドレスを検証する。
- Windows 版のローカルのサーバーは `127.0.0.1` だけで待ち受け、Origin と CSRF を検証する。Docker 版の解析 worker は、ネットワークのない読み取り専用のコンテナで動く。

送るデータの範囲、認証、保存と削除の詳細は[データ保護と運用](docs/security.md)（英語）にある。研究データと認証情報の扱いは、[チーム開発ルール §6](docs/team-development.md#6-研究データの扱い)で定めている。

## English

### Supported versions

Security fixes go to the latest Windows release and to `main` (the public site `cytellect.app` and the cloud features). Earlier Windows releases move to the latest one through the in-app update or a new installer.

### Reporting a vulnerability

Report vulnerabilities privately with GitHub's **Report a vulnerability** form under the **Security** tab ([form](https://github.com/genellect/cytellect/security/advisories/new)), not in issues, pull requests or discussions. Include the affected commit or Windows release, reproduction steps and the expected impact, using only synthetic or public data and no research data or credentials.

### What happens next

1. We reply to reasonable reports within three days.
2. We assess the affected scope and severity and share the assessment with the reporter.
3. We fix the issue in a private GitHub Security Advisory fork and run the usual CI.
4. We release the fix: the public site and cloud features are deployed, and Windows installations receive a signed update.
5. After the release we publish the Security Advisory, request a CVE where appropriate and credit the reporter if they wish.

Please keep the report confidential until the fix is released. Published advisories are listed under [Security Advisories](https://github.com/genellect/cytellect/security/advisories).

### How the project stays secure

- Every change to `main` goes through a pull request. A ruleset rejects direct and force pushes and requires the required CI, an up-to-date branch and resolved review conversations. Pull requests from anyone but the owner need another member's approval, and automated code and security reviews run on every pull request.
- GitHub Actions tokens are read-only by default; write access is granted only to the jobs that need it, and pull-request CI receives no secrets.
- Dependencies are pinned by lockfiles, and the Fiji and Cellpose artifacts by SHA-256. Dependabot alerts and `pip-audit` watch for known vulnerabilities, and CI emits a CycloneDX SBOM. A version- and hash-pinned gitleaks scans the full Git history.
- The in-app update runs an installer only after verifying a manifest signed with the owner's Ed25519 key and matching the installer's hash. Signing happens only in the `release` environment, which requires the owner's approval, so repository write access alone cannot push code to users' PCs.
- Images are analysed on the researcher's PC. The cloud features send only the minimum each task needs, never file names or paths. A PC holds a single device token; only the Cytellect Worker holds the external service keys, and the server stores tokens and codes as hashes. The admin page sits behind Cloudflare Access, and the Worker verifies the access token's signature, issuer, audience, expiry and address itself.

Data handling in detail is described in [Data protection and operations](docs/security.md); research data and credentials are handled under the [team development rules](docs/team-development.md#6-research-data).
