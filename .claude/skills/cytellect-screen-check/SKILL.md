---
name: cytellect-screen-check
description: Cytellect の画面（解析ワークスペース、公開デモ /demo、LP）を変えたあと、登録済みの公開画像だけで実際の画面を起動し、Playwright でスクリーンショットを撮って、変更が意図どおりに見えて動くかを確かめる。続けて design:design-critique と design:accessibility-review で点検する。画面を実装・修正したとき、または「画面を確認して」「スクリーンショットを撮って」と頼まれたときに使う。
---

# 画面の確認

画面の変更は、試験の合格だけでなく、実際に表示して確かめる。使う画像は `fixtures/public` に登録した公開画像だけ。非公開の研究画像・ファイルパス・研究結果は、スクリーンショットにも、スキルへの入力にも含めない。

## 1. 起動の方法を選ぶ

| 確かめるもの | 起動 |
|---|---|
| LP、公開デモ（`/demo`）の表示と操作 | `pnpm build` のあと、`NEXT_PUBLIC_API_ORIGIN` を設定せずに `pnpm --filter @cytellect/web start`。CI の公開サイトの試験と同じ構成で、API・Fiji・鍵は要らない |
| 解析ワークスペース（画像の登録・検出・測定・統計・図） | `python3 scripts/dev.py doctor` で準備を確かめてから `python3 scripts/dev.py serve`。表示された招待コードで `http://localhost:3000/workspace` に入る。画像は CI の `browser-e2e` ジョブと同じ手順で公開画像を準備する（`CONTRIBUTING.md`「PR を出す前に」） |

- サーバーは `run_in_background` で起動し、`curl --fail` で応答を確かめてから操作する。
- API の Origin は `localhost` を使う（`127.0.0.1` では照合に失敗する）。
- `doctor` が `[--]` を示した外部サービス（GPU、解析提案）は使わずに確かめ、使えなかったことを報告する。`doctor --live` は GPU を起動して課金されるため、依頼がない限り実行しない。

## 2. 操作して撮る

- Chromium と Playwright は環境に入っている。`require('playwright')` を使い、`playwright install` はしない。
- 変更した画面に至る研究者の操作を、最初から順にたどる。変更前と変更後を同じ手順で撮れる場合は両方撮る。
- 幅 1440 px（`playwright.config.ts` の既定）と、スマートフォンの幅（例：`devices["iPhone 15"]`）の両方で撮る。
- 自分で見るだけのスクリーンショットは `deviceScaleFactor: 1`、PR に貼るものは `2`。保存先は scratchpad で、リポジトリには入れない。
- ブラウザのコンソールのエラーと、失敗した通信を記録する。

## 3. 点検する

撮った画面を、次のスキルで点検する。スキルが読み込めない場合は、同じ観点を自分で確かめ、読み込めなかったことを報告する。

1. `design:design-critique`：研究者が、何を対象に何を測っているかを理解し、次の操作に迷わないか。情報の優先順位、一貫性。
2. `design:accessibility-review`：色分け（陽性・陰性、核小体と核質など）を色だけに頼っていないか、コントラスト、キーボード操作、タップ領域。
3. 文言は `docs/development-principles.md` の「画面と文章」と UC-01〜UC-07 に照らす。直す場合は `design:ux-copy` を使う。LP は `docs/lp-art-direction.md` に従う。

指摘のうち、今の変更の範囲にあるものだけを直す。範囲の外のものは報告に挙げ、勝手に直さない。

## 4. 報告する

- 確かめた画面と操作、起動の方法、画面の幅
- 見つけた問題と、直したもの・直していないもの
- 確かめられなかったこと（外部サービスがない、Fiji がないなど）

「画面で確認した」と書くのは、実際に表示して確かめた範囲だけにする。
