@AGENTS.md

# Claude Code 向けの補足

[AGENTS.md](AGENTS.md) は冒頭の `@AGENTS.md` で読み込まれる。プロダクト方針、作業手順、検証、公開権限は `AGENTS.md` と[チーム開発ルール](docs/team-development.md)に従い、この文書で上書きしない。

- クラウド環境のセットアップには [.claude/cloud-setup.sh](.claude/cloud-setup.sh) を使い、オーナーの環境では続けて [.claude/owner-tools.sh](.claude/owner-tools.sh) を実行する（[オーナーの環境](CONTRIBUTING.md#オーナーの環境)）。検証コマンドは [CONTRIBUTING.md](CONTRIBUTING.md) にある。画面は `python3 scripts/dev.py doctor` で準備を確かめてから `serve` で起動する（[ローカル開発](CONTRIBUTING.md#ローカル開発)）。
- コミットには、Claude Code が付ける `Co-Authored-By` 行を残す。
- Claude への以前の引き継ぎ文書は [docs/archive](docs/archive/README.md) にある経緯の記録。記載されたブランチや公開手順を、現在の依頼と照合せずに実行しない。

## 作業の完了

- 変更を伴う依頼は、検証・コミット・push のあと、PR の作成までを標準とする（[チーム開発ルール](docs/team-development.md#2-開発の流れ)の手順 4）。依頼に「PR は不要」「調査だけ」とある場合と、コードや文書を変えない質問には作らない。作業途中で共有するときは Draft PR にする。
- PR を作ったら、URL と検証の結果を報告する。PR の作成に、マージ・デプロイ・配布・有料サービスの利用の許可は含まれない（`AGENTS.md`）。

## 目的別のスキル

目的に合うスキルは、依頼で名前を挙げられていなくても自分から使う。レビューや調査のような重いスキルは、効果のある変更に限り、PR ごとに 1 回使う。PR を更新しても、レビューした部分のロジックが大きく変わらない限り繰り返さない。

| 目的 | スキル | 使う場面 | 使わない場面 |
|---|---|---|---|
| 画面の設計 | `frontend-design:frontend-design`。LP は先に [LP の美術方針](docs/lp-art-direction.md)を読む | 新しい画面を作る、画面の構成や導線を変える | 既存の画面の小さな修正 |
| アプリの文言 | `design:ux-copy` | 新しい画面や導線の文言をまとめて書く | 数語の修正。[開発の原則](docs/development-principles.md#画面と文章)の UC-01〜UC-07 に照らすだけでよい |
| 画面の確認 | `cytellect-screen-check` | 画面を変えた | — |
| 検証 | `cytellect-verify` | コード・設定・依存パッケージを変えた | — |
| PR の作成 | `cytellect-pr` | PR を作る・更新する | 途中のコミットの push |
| コードレビュー | `/code-review medium`。測定・統計・検出・作図の計算は `high` | ロジックを変えた：解析・API・計算ワーカー・提案 Worker の処理と、画面の状態とデータの処理 | 画面の見た目・文言・文書・設定・試験だけの変更 |
| セキュリティレビュー | `/security-review` | 認証・認可（ログイン、招待、セッション、端末トークン）、アップロードの受け入れ、更新の署名、workflow の権限とシークレットを変えた | それ以外の変更 |
| Claude API と LLM の機能 | `claude-api` | 解析支援の Worker、モデル、プロンプト、費用を扱う | — |
| 統計と図の手法 | `data:statistical-analysis`、`dataviz` | 新しい検定や図の種類を設計する。値は共通実装だけが作る | 既存の図の見た目の調整 |
| 調査 | `anthropic-skills:deep-research` | 複数の情報源をまたぐ調査を頼まれた（モデルの選定、費用の比較、文献） | 1 つの事実の確認 |

次は、依頼があったときだけ使う。

- `design:user-research`、`design:research-synthesis`：研究者による評価の計画と記録のまとめ。
- `/simplify`：差分を書き換える。
- `/code-review` の `max` の水準と Workflow：多くのエージェントを起動する。
- Figma・Canva などのコネクタ：外部のサービスにファイルを作る。

`cytellect-` で始まるスキルは [.claude/skills](.claude/skills) にある。そのほかは claude.ai の組織の設定や Claude Code が配るもので、リポジトリには含まれない。読み込めない場合は、表の目的を文書の手順で満たし、使えなかったことを報告する。

## 研究データの境界

境界の正本は[チーム開発ルール §6](docs/team-development.md#6-研究データの扱い)。作業では次のように分けて考える。

- **製品の中では UX を優先する。** 研究者が自分のデータ（原画像、ファイル名、測定値、結果）を見て判断できることが製品の価値で、表示を隠す・減らす・防御的な制限を足す設計にしない。解析支援の LLM には、研究者が同意した範囲の研究データを示す（2026-11-16、オーナーの判断、[LLM による解析支援の見直し](docs/drafts/llm-assistant/plan.md)）。開発の場の規則を、製品の機能の設計に持ち込まない。
- **開発の場では公開画像を使う。** Git、PR、CI、ログ、クラウドの開発セッションで扱う画像は、[登録済みの公開画像](fixtures/public)。隔離ローカル環境では、オーナーが指定した範囲で非公開データを扱える（[ローカル研究データの利用](docs/drafts/research-measurements/local-data.md#隔離ローカル環境での-ai-の利用)）。
- **認証情報は、どこにも出さない。**
