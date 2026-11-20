@AGENTS.md

# Claude Code 向けの補足

[AGENTS.md](AGENTS.md) は冒頭の `@AGENTS.md` で読み込まれる。プロダクト方針、作業手順、検証、公開権限は `AGENTS.md` と[チーム開発ルール](docs/team-development.md)に従い、この文書で上書きしない。

- クラウド環境のセットアップには [.claude/cloud-setup.sh](.claude/cloud-setup.sh) を使い、オーナーの環境では続けて [.claude/owner-tools.sh](.claude/owner-tools.sh) を実行する（[オーナーの環境](CONTRIBUTING.md#オーナーの環境)）。検証コマンドは [CONTRIBUTING.md](CONTRIBUTING.md) にある。画面は `python3 scripts/dev.py doctor` で準備を確かめてから `serve` で起動する（[ローカル開発](CONTRIBUTING.md#ローカル開発)）。
- コミットには、Claude Code が付ける `Co-Authored-By` 行を残す。
- Claude への以前の引き継ぎ文書は [docs/archive](docs/archive/README.md) にある経緯の記録。記載されたブランチや公開手順を、現在の依頼と照合せずに実行しない。

## 目的別のスキル

作業の目的に合うスキルは、依頼で名前を挙げられていなくても、その時点で読み込んで使う。スキルは手順を補うだけで、`AGENTS.md` の禁止事項や、マージ・デプロイ・配布・有料サービスの許可を変えない。

| 目的 | スキル | 使う時点 |
|---|---|---|
| 画面の設計・変更 | `frontend-design:frontend-design`。LP は先に [LP の美術方針](docs/lp-art-direction.md)を読む | 画面の実装を始める前 |
| アプリの文言 | `design:ux-copy`。規則は[開発の原則](docs/development-principles.md#画面と文章)の UC-01〜UC-07 | 見出し・ボタン・案内・エラー文を書くとき |
| 画面の確認 | `cytellect-screen-check`。中で `design:design-critique` と `design:accessibility-review` を使う | 画面の変更を実装したあと |
| 検証 | `cytellect-verify` | コード・設定・依存パッケージを変え、コミットする前 |
| PR の準備 | `cytellect-pre-pr`。中で `/code-review` と、境界に触れる変更では `/security-review` を使う | PR を作る・更新する前 |
| Claude API と LLM の機能 | `claude-api` | 解析提案・考察の Worker、モデル、プロンプト、費用を扱うとき |
| 統計と図の手法 | `data:statistical-analysis`、`dataviz` | 検定・n の取り方・図の設計を点検するとき。値は共通実装だけが作る |
| 複数の情報源の調査 | `anthropic-skills:deep-research` | モデルの選定、費用の比較、文献の調査 |

次は、依頼があったときだけ使う。

- `design:user-research`、`design:research-synthesis`：研究者による評価の記録を扱う。渡すのは匿名化した記録だけ。
- `/simplify`：差分を書き換える。
- `/code-review` の `max` の水準と Workflow：多くのエージェントを起動し、費用がかかる。
- Figma・Canva などのコネクタ：画面や画像を外部のサービスへ送る。

注意：

- `cytellect-` で始まるスキルは [.claude/skills](.claude/skills) にある。そのほかは claude.ai の組織の設定や Claude Code が配るもので、リポジトリには含まれない。読み込めない場合は、表の目的を文書の手順で満たし、使えなかったことを報告する。
- スキルに渡す画面と画像は、[登録済みの公開画像](fixtures/public)を表示したものだけにする。
