# セキュリティポリシー

Cytellect は研究者の未発表の画像を扱うため、脆弱性の報告と研究データの扱いを次のとおり定める。

## 脆弱性の報告

脆弱性は、GitHub の非公開の報告機能で知らせる。リポジトリの **Security** タブで **Report a vulnerability** を選ぶと、報告者とリポジトリの管理者だけが読める形で送れる（[報告フォーム](https://github.com/genellect/cytellect/security/advisories/new)）。Issue、PR、ディスカッションなどの公開の場には書かない。

報告には、次の内容を含める。

- 対象のコミット、または Windows 版のバージョン
- 再現手順
- 想定される影響

再現には合成データか公開データを使う。

合理的な報告には、3 日以内に返信する。評価から修正版の配布、公表までの流れは[セキュリティ体制 §6](docs/security.md#6-脆弱性への対応)にある。

## 研究データの扱いと体制

研究データと認証情報の扱いは、[チーム開発ルール §6](docs/team-development.md#6-研究データの扱い)で定めている。方針、現在の管理策、残るリスクは[セキュリティ体制](docs/security.md)にまとめている。

## English

Report vulnerabilities privately with GitHub's **Report a vulnerability** form under the **Security** tab ([form](https://github.com/genellect/cytellect/security/advisories/new)), not in issues, pull requests or discussions. Include the affected commit or Windows release, reproduction steps and the expected impact, using only synthetic or public data. We reply to reasonable reports within three days. Research data and credentials are handled under the [team development rules](docs/team-development.md#6-research-data); the security policy, current controls and accepted risks are described in [docs/security.md](docs/security.md) (Japanese).
