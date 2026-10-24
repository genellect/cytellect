# セキュリティポリシー

Cytellect は研究者の未発表の画像を扱うため、脆弱性の報告と研究データの扱いを次のとおり定めています。

## 脆弱性の報告

脆弱性は、GitHub の非公開の報告機能で知らせてください。リポジトリの **Security** タブで **Report a vulnerability** を選ぶと、報告者とリポジトリの管理者だけが読める形で送れます（[報告フォーム](https://github.com/genellect/cytellect/security/advisories/new)）。Issue、PR、ディスカッションなどの公開の場には書かないでください。

報告には、次の内容を含めてください。

- 対象のコミット、または Windows 版のバージョン
- 再現手順
- 想定される影響

再現には合成データか公開データを使い、非公開の研究データや認証情報は添付しないでください。

## 研究データの扱い

Issue、PR、ディスカッションには、非公開の研究データ（研究室の未発表画像、正解の輪郭、測定表、論文草稿、ファイル名とパス、参加者情報）と認証情報（API キー、トークン、招待リンク）を載せないでください。誤って載せた場合は、非公開の報告フォームから知らせてください。認証情報は直ちに無効化してください。

データの区分と開発での扱いは[チーム開発ルール §6](docs/team-development.md#6-研究データの扱い)、製品が保存・送信する情報は[データ保護と運用](docs/security.md)で定めています。

## English

Report vulnerabilities privately with GitHub's **Report a vulnerability** form under the **Security** tab ([form](https://github.com/genellect/cytellect/security/advisories/new)), not in issues, pull requests or discussions. Include the affected commit or Windows release, reproduction steps and the expected impact, using only synthetic or public data. Never post private research data or credentials in issues, pull requests or discussions; the categories are defined in the [team development rules](docs/team-development.md#6-research-data), and product data handling is described in [docs/security.md](docs/security.md).
