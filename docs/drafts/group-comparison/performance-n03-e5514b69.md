# 公開デモ N-03 の性能測定（e5514b69）

## 対象と固定した手順

測定基準は `e5514b69ec874892d5b6ea989c43e3250d37f805`。この文書だけを `codex/demo-performance-n03` で変更する。製品コード・画像・記録は変更しない。N-03 の上限は未決定であり、この測定は上限を決める材料とする。

| 対象 | URL | 配備のコミット |
|---|---|---|
| 旧本番 | https://cytellect.vercel.app/demo | `11eb24419f2d8af5a3eec706e23985a038cc7f1d` |
| 新 Preview | https://cytellect-da1fexzdx-yuto10.vercel.app/demo | `e5514b69ec874892d5b6ea989c43e3250d37f805` |

GitHub の Vercel commit status と Vercel deployment metadata で対応を確認した。本番配備は `dpl_JDzD4bcHFu6aeZ1yzkFFpi4qLzn4`、Preview は `dpl_3ZdgUg35yHJUWMXwuxPBQkx8mQih`（ともに READY）。移動する branch alias は測定対象にしない。

測定前の手順：デスクトップ Chromium、1440 × 1000、毎回新しいプロファイル、ブラウザキャッシュ無効、Service Worker を迂回。CDP で下り 10 Mbps、上り 1 Mbps、遅延 40 ms を設定し、CPU は絞らない。旧本番 5 回、新 Preview の初期場面 5 回、核小体の参考測定 5 回。新の到達点は 2 画像と region「比較の結果」の文、旧の到達点は最初の画像と輪郭。異なる到達点なので速度比を回帰判定には使わない。

新の核小体場面は固定した `snapshot/scenes.json` の `id=zenodo-6643470-nucleolar` に対応する `workspaceId=a01bbc3c-8ce4-4283-bc69-face42fad2aa` を `/demo?id=...` に渡す。初期場面は `cpg0016-jump-source13-plk1`。測定値で場面・視野を選ばない。画像は登録済みの公開実画像の既存記録を再生する。

転送量は表示到達点までの CDP の encoded bytes を集計する。完了 request は `Network.loadingFinished.encodedDataLength`、未完了 request はその時点までの `response.encodedDataLength + dataReceived.encodedDataLength`。ブラウザとサーバー間の HTTP 転送の指標であり、TCP/TLS の全パケット長ではない。`seed.zip` のファイル容量を表示転送量として扱わない。

390 × 844 の追加確認ではページの request 一覧を保存し、seed・Fiji・Cellpose 等の解析 runtime を要求しないことを調べる。測定スクリプトと詳細な受信記録は checkout 外に置き、再現手順と生値をこの文書に記録する。

## 実施状況

測定前の probe で、旧本番は画像・輪郭が表示された。Preview の認証なし Chromium は Vercel ログイン画面へ転送された。既存 Vercel CLI 認証は見つからなかった。接続済み Vercel の共有リンク作成は、公開範囲の拡大に当たるとして自動承認審査に拒否され、作成していない。保護設定は変更していない。

その後、オーナーが対象 Preview に限る 23 時間の共有リンク作成を明示的に許可し、作成に成功した。認証 cookie だけを各新規プロファイルへ渡す。URL の秘密値と cookie をこの文書・PR に保存しない。認証の通信は測定外。

認証後の probe では通常の `/demo` が「視野 0」「この操作の結果は公開デモに記録していません」のまま、画像も結果の文も表示しなかった。正式試行では navigation 開始から 120 秒を打ち切り時刻とし、未到達は失敗として記録する。通常の入口を 5 回測る条件は維持する。切り分けの参考値として、JUMP の明示 workspaceId でも 5 回測る。プロトコル上の核小体 5 回は変更しない。

## 初期入口の不具合（コード・記録で確認した事実）

`apps/web/src/lib/workspace/review-preview.ts:73` は id を指定しない初期化で `GET /v1/workspaces` を要求する。固定した `snapshot/index.json` の 261 entries にはそのキーがなく、`journal.json` にも同じ GET は 0 件だった。`apps/web/src/lib/showcase/transport.ts:416` 付近は記録のない request に `showcase_action_not_recorded`（409）をメモリ内で返す。これが probe の案内文と一致する。ネットワークに HTTP 409 がなくても初期化は失敗しうる。

主担当への修正依頼は [PR #108 のコメント](https://github.com/genellect/cytellect/pull/108#issuecomment-6399055743) に記録した。この測定 PR ではコードや snapshot を修正しない。通常の入口の表示完了が成立するまで、N-03 を合格にしない。

## 環境

- Windows 11（OS build `10.0.26200`）、Intel Core i7-1360P、16 logical CPUs、RAM 31.73 GiB。
- Node.js 24.18.0、Playwright 1.63.0、Chromium 153.0.8010.12（headless、デスクトップ viewport、deviceScaleFactor 1、locale ja-JP）。
- 各試行は独立した Chromium の一時 user-data directory。キャッシュ無効、Service Worker block と CDP bypass。OS の DNS cache と CDN cache は消去していない。
- CDP の回線設定は帯域上限・追加遅延のエミュレーション。実回線・CDN・Windows の残る背景負荷の揺らぎは除去していない。CPU throttling はしない。
- 同じホストで実行中だった他作業の pytest は正式測定前に終了した。Fiji、解析、ローカル build と計測を並列実行していない。CPU 使用率は各試行の navigation 前から記録保存前までの全ホスト平均であり、到達点だけの平均ではない。
- SVG image の load event、表示領域が存在すること、必要な文・輪郭を確認し、さらに 2 回の requestAnimationFrame を待つ。時刻は navigation 起点の `performance.now()`。ネットワークの `Performance.NavigationStart + ms / 1000` までの CDP event を採用する。画面内へのスクロールはしない。
- 本番を 5 回、その後 Preview を 5 回、JUMP 直リンクを 5 回、核小体直リンクを 5 回の固定順。認証 probe は生値の 5 回に含めない。

## 旧本番の生値

到達点は最初の画像（Hoechst）と 24 個の輪郭。新の「2 画像と比較の文」とは異なる指標である。全 5 回で JavaScript の未処理例外なし、採用した受信に disk cache の使用なし。転送量には到達時に未完了の request を各 1 件含む。

| 試行 | 開始 UTC（2026-10-25） | 表示まで ms | 到達時 bytes | 全ホスト平均 CPU % |
|---|---|---:|---:|---:|
| 1 | 14:42:35 | 2498.1 | 2273920 | 16.39 |
| 2 | 14:42:43 | 2411.7 | 2275739 | 15.00 |
| 3 | 14:42:52 | 2443.6 | 2273548 | 17.77 |
| 4 | 14:43:01 | 2708.7 | 2273551 | 21.79 |
| 5 | 14:43:09 | 2405.2 | 2283795 | 11.69 |

中央値 2443.6 ms、範囲 2405.2–2708.7 ms。転送量中央値 2273920 bytes（2.169 MiB）、範囲 2273548–2283795 bytes。初期表示を測ったもので、残り全視野・全記録の受信完了ではない。

本番の Google Analytics request は試行中に `net::ERR_ABORTED` となった。アプリの初期画像・輪郭は成立したが、エラーが全くないとは記載しない。実行環境での外部 analytics の受信有無は他環境と異なりうる。
