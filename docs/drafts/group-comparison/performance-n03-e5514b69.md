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

正式測定は準備中。Preview の取得可否と、測定済み・未測定を分けて追記する。
