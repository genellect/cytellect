---
name: cytellect-verify
description: Cytellect でコード・設定・依存パッケージ・文書を変えたあと、コミットや PR の前に、変更に関係する検証だけを手元で実行し、合格・失敗・未実施・CI に任せるものを分けて報告する。全体の試験は PR の CI に任せる。実装を終えたとき、または「テストして」「検証して」と頼まれたときに使う。
---

# 変更に対応する検証

手元では、変更に関係する検査だけを短く実行し、全体は PR の CI に任せる。`dev.py check python` の全体は 20 分ほどかかり、CI が同じものを実行する。コマンドの正本は `CONTRIBUTING.md` の「PR を出す前に」、ジョブの選び方の正本は `scripts/ci_changes.py`（説明は `docs/ci.md`）。

## 1. 対象を確かめる

```bash
python3 scripts/dev.py changed
```

`origin/main` との差分（コミット済み、まだコミットしていない変更、追跡していないファイル）と、PR の CI が実行する対象を示す。`origin/main` が古い場合は、先に `git fetch origin main` を実行する。

## 2. 手元で実行する

| 変更 | 手元で実行するもの |
|---|---|
| Python | 変えたファイルの `uv run ruff check <ファイル>`。変えたモジュールを試す試験だけを `uv run pytest <試験のファイル>` で実行する（`grep` で、そのモジュールを読み込む試験を探す） |
| Web・Worker の TypeScript | 型と lint を `pnpm check`（Web）または `pnpm --filter @cytellect/proposal-worker check`（Worker）で確かめる。変えた部分の試験だけを `pnpm --filter <パッケージ> exec vitest run <ファイル>` で実行する |
| API | `python3 scripts/dev.py contracts`。生成した OpenAPI・既定レシピ・TypeScript の型を同じコミットに入れる |
| 依存パッケージ・lockfile | `python3 scripts/dev.py audit`。結果は checkout の外に出る。秘密情報の走査は件数だけを報告する |
| 解析エンジン | `python3 scripts/dev.py check --fiji` |
| 文書だけ | `python3 scripts/dev.py check --changed`（文書のリンクと公開ツリーの検査だけを実行する） |
| 画面 | 続けて `cytellect-screen-check` |

全体を手元で実行するのは、CI の失敗を再現するときと、依頼があったときだけ。そのときは `python3 scripts/dev.py check --changed` を使う。変更に応じて `python`・`web` の全体を選び、CI だけが実行するものを示す。

- 時間のかかる検証は `run_in_background` で実行し、完了の通知を待つ。
- 同じコミット・同じ条件で記録した合格は、その後の変更で無効にならない限り再利用してよい。再利用したことを報告に書く。

## 3. 失敗したとき

- 原因は出力・ソース・再現で特定する（`docs/development-principles.md` の「問題への対処」）。推測で直さない。
- 合格させるために、試験を消す・飛ばす・期待値を書き換える・閾値を緩めることはしない。試験の期待値が誤っていると判断した場合は、根拠を示して依頼者に確認する。
- 評価データに合わせた閾値やモデルの調整で合格させない。

## 4. 報告する

次の 4 つを分けて、日本語で報告する。

- **合格**：実行したコマンドと、対象のコミット
- **失敗**：コマンド、失敗した試験、出力の要点、特定した原因（未確定ならそう書く）
- **未実施**：実行しなかったものと理由
- **CI に任せる**：手元で実行しなかった全体の試験と、CI だけのジョブ

未実施・失敗を合格として書かない。
