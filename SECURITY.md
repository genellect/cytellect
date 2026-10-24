# セキュリティポリシー

Cytellect は研究者の未発表の画像を扱うため、脆弱性の報告と研究データの扱いを次のとおり定めています。

## 脆弱性の報告

脆弱性は、GitHub の非公開の報告機能で知らせてください。リポジトリの **Security** タブで **Report a vulnerability** を選ぶと、報告者とリポジトリの管理者だけが読める形で送れます（[報告フォーム](https://github.com/genellect/cytellect/security/advisories/new)）。Issue、PR、ディスカッションなどの公開の場には書かないでください。

報告には、次の内容を含めてください。

- 対象のコミット、または Windows 版のバージョン
- 再現手順
- 想定される影響

再現には合成データか公開データを使い、未発表の研究画像、測定値、招待コード、セッションのトークンは添付しないでください。

## 研究データの扱い

Issue や PR には、研究画像、実験の内容、試料の識別子、招待コード、セッションのトークンを載せないでください。研究データの境界と保存期限、認証、外部サービスとの通信は、[データ保護と運用](docs/security.md)にまとめています。

## English

Report vulnerabilities privately with GitHub's **Report a vulnerability** form under the **Security** tab ([form](https://github.com/genellect/cytellect/security/advisories/new)), not in issues, pull requests or discussions. Include the affected commit or Windows release, reproduction steps and the expected impact, using only synthetic or public data. Data protection and operations are described in [docs/security.md](docs/security.md).
