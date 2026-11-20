---
name: cytellect-verify
description: Cytellect でコード・設定・依存パッケージ・文書を変えたあと、コミットや PR の前に、変更したファイルに対応する検証を CONTRIBUTING.md のコマンドで選んで実行し、合格・失敗・未実施・CI に任せるものを分けて報告する。実装を終えたとき、または「テストして」「検証して」「CI を手元で確かめて」と頼まれたときに使う。
---

# 変更に対応する検証

PR の CI と同じ規則で、変更したファイルから検証を選んで実行する。コマンドの正本は `CONTRIBUTING.md` の「PR を出す前に」、ジョブの選び方の正本は `scripts/ci_changes.py`（説明は `docs/ci.md`）。この手順と食い違ったら、正本に従い、食い違いを報告する。

## 1. 対象を選ぶ

コミット済みの差分と、まだコミットしていない変更を合わせて、CI と同じ規則に通す。

```bash
{ git diff --name-only origin/main...HEAD; git diff --name-only HEAD; git ls-files --others --exclude-standard; } | sort -u | python3 -c 'import sys; sys.path.insert(0, "scripts"); from ci_changes import select; paths = [l.strip() for l in sys.stdin if l.strip()]; print(sorted(select(paths)) if paths else "no changes")'
```

空の集合 `[]` は、文書だけの変更を表す。`origin/main` が古い場合は、先に `git fetch origin main` を実行する。

## 2. 実行する

| 対象・変更 | コマンド |
|---|---|
| `python` | `python3 scripts/dev.py check python` |
| `web` | `python3 scripts/dev.py check web` |
| 解析エンジンを変えた | `python3 scripts/dev.py check --fiji` も |
| API を変えた | `python3 scripts/dev.py contracts`。生成した OpenAPI・既定レシピ・TypeScript の型を同じコミットに入れる |
| 依存パッケージ・lockfile を変えた | `python3 scripts/dev.py audit`。結果は checkout の外に出る。秘密情報の走査は件数だけを報告し、内容を貼らない |
| 文書だけ（`[]`） | `python3 scripts/check_docs.py` と `uv run python scripts/check_public_tree.py`（CI はどの変更でも実行する） |
| `fiji`、`lp`、`windows`、ブラウザの E2E、コンテナ | CI が担う。手元で再現する場合は `CONTRIBUTING.md` の手順に従う |

- 時間のかかる検証は `run_in_background` で実行し、完了の通知を待つ。
- 同じコミット・同じ条件で記録した合格は、その後の変更で無効にならない限り再利用してよい。再利用したことを報告に書く。
- 画面を変えた場合は、続けて `cytellect-screen-check` で実際の画面を確かめる。

## 3. 失敗したとき

- 原因は出力・ソース・再現で特定する（`docs/development-principles.md` の「問題への対処」）。推測で直さない。
- 合格させるために、試験を消す・飛ばす・期待値を書き換える・閾値を緩めることはしない。試験の期待値が誤っていると判断した場合は、根拠を示して依頼者に確認する。
- 公開画像以外の画像や、評価データに合わせた調整で合格させない。

## 4. 報告する

次の 4 つを分けて、日本語で報告する。

- **合格**：実行したコマンドと、対象のコミット
- **失敗**：コマンド、失敗した試験、出力の要点、特定した原因（未確定ならそう書く）
- **未実施**：実行しなかったものと理由（時間、Fiji がない、外部サービスの鍵がないなど）
- **CI に任せる**：手元で実行できないジョブ

未実施・失敗を合格として書かない。
