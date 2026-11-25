@AGENTS.md

# Claude Code 向けの補足

[AGENTS.md](AGENTS.md) は冒頭の `@AGENTS.md` で読み込まれる。プロダクト方針、作業手順、検証、公開権限は `AGENTS.md` と[チーム開発ルール](docs/team-development.md)に従い、この文書で上書きしない。

- クラウド環境のセットアップには [.claude/cloud-setup.sh](.claude/cloud-setup.sh) を使い、オーナーの環境では続けて [.claude/owner-tools.sh](.claude/owner-tools.sh) を実行する（[オーナーの環境](CONTRIBUTING.md#オーナーの環境)）。検証コマンドは [CONTRIBUTING.md](CONTRIBUTING.md) にある。画面は `python3 scripts/dev.py doctor` で準備を確かめてから `serve` で起動する（[ローカル開発](CONTRIBUTING.md#ローカル開発)）。
- コミットには、Claude Code が付ける `Co-Authored-By` 行を残す。
- Claude への以前の引き継ぎ文書は [docs/archive](docs/archive/README.md) にある経緯の記録。記載されたブランチや公開手順を、現在の依頼と照合せずに実行しない。

## 目的別のスキル

表の場面に当てはまるスキルは、依頼で名前を挙げられていなくても自分から使う。当てはまらない変更（小さな修正、文言、文書、設定、試験だけ）では、`cytellect-` で始まる 3 つ以外を使わない。レビューは PR ごとに 1 回で、PR を更新しても、レビューした部分のロジックが大きく変わらない限り繰り返さない。

| スキル | 使う場面 |
|---|---|
| `cytellect-verify` | コード・設定・依存パッケージ・文書を変えた |
| `cytellect-screen-check` | 画面を変えた |
| `cytellect-pr` | PR を作る・更新する（途中のコミットの push では使わない） |
| `frontend-design:frontend-design` | 新しい画面を作る、画面の構成や導線を変える。LP は先に [LP の美術方針](docs/lp-art-direction.md)を読む |
| `design:ux-copy` | 新しい画面や導線の文言をまとめて書く |
| `/code-review medium`（測定・統計・検出・作図の計算は `high`） | ロジックを変えた：解析・API・計算ワーカー・提案 Worker・開発用スクリプトの処理と、画面の状態とデータの処理 |
| `/security-review` | 認証・認可（ログイン、招待、セッション、端末トークン）、アップロードの受け入れ、更新の署名、workflow の権限とシークレットを変えた |
| `claude-api` | 解析支援の Worker、モデル、プロンプト、費用を扱う |
| `data:statistical-analysis`、`dataviz` | 新しい検定や図の種類を設計する。値は共通実装だけが作る |
| `anthropic-skills:deep-research` | 複数の情報源をまたぐ調査を頼まれた |

依頼があったときだけ使う：`design:user-research`、`design:research-synthesis`、`/simplify`、`/code-review` の `max` の水準と Workflow、Figma・Canva などのコネクタ。

`cytellect-` で始まるスキルは [.claude/skills](.claude/skills) にある。そのほかは claude.ai の組織の設定や Claude Code が配るもので、リポジトリには含まれない。読み込めない場合は、同じ目的を文書の手順で満たし、使えなかったことを報告する。
