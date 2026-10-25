# 公開デモ N-03 の性能測定（e5514b69）

## 対象と固定した手順

測定基準は `e5514b69ec874892d5b6ea989c43e3250d37f805`。この文書だけを `codex/demo-performance-n03` で変更する。製品コード・画像・記録は変更しない。N-03 の上限は未決定であり、この測定は上限を決める材料とする。

**結論：新しい通常入口は 5 回とも 120 秒で未到達だった。N-03 は合格としない。** 直リンクの参考測定では JUMP が中央値 26.650 秒・21760168 bytes、核小体場面の初期「核・Hoechst」が 28.786 秒・15622214 bytes で到達した。旧本番の最初の画像と輪郭は 2.444 秒・2273920 bytes。到達点が異なるため、これらの差を同じ処理の回帰と断定しない。

正式測定は 2026-10-25 14:42:35–15:03:41 UTC（JST 10 月 25 日 23:42:35–26 日 00:03:41）。本番配備の SHA は測定後も同じと確認した。以下は「画像 load と layout 可視状態の文まで」の計測で、到達瞬間の viewport 内全文を保証する計測ではない。

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

測定前の probe で、旧本番は画像・輪郭が表示された。Preview の認証なし Chromium は Vercel ログイン画面へ転送された。既存 Vercel CLI 認証は見つからなかった。接続済み Vercel の共有リンク作成は、公開範囲の拡大に当たるとして自動承認審査に拒否され、その時点では作成されなかった。プロジェクトの保護を無効化していない。

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

<!-- measurement-results -->

## 新 Preview の通常入口

成功 0/5、未到達 5/5。未到達行の bytes は観測打ち切り時までの受信量であり、表示完了時の量ではない。

| 試行 | 開始 UTC（2026-10-25） | 表示まで ms | 打ち切り観測 ms | bytes | 全ホスト平均 CPU % |
|---|---|---:|---:|---:|---:|
| 1 | 14:44:21 | 未到達 | 120,020.3 | 1951804 | 12.60 |
| 2 | 14:46:27 | 未到達 | 120,016.7 | 1951773 | 7.07 |
| 3 | 14:48:33 | 未到達 | 120,009.4 | 1951945 | 4.87 |
| 4 | 14:50:39 | 未到達 | 120,010.6 | 1951797 | 6.91 |
| 5 | 14:52:45 | 未到達 | 120,006.1 | 1951797 | 5.85 |

表示完了の時間・転送量の中央値と範囲は算出不能。120 秒を成功時間として扱わない。

試行中の全ホスト平均 CPU は 4.9–12.6%。disk cache 由来の受信 0 件、JavaScript の未処理例外 0 件。

## 参考：新 JUMP の明示 id

成功 5/5、未到達 0/5。未到達行の bytes は観測打ち切り時までの受信量であり、表示完了時の量ではない。

| 試行 | 開始 UTC（2026-10-25） | 表示まで ms | 打ち切り観測 ms | bytes | 全ホスト平均 CPU % |
|---|---|---:|---:|---:|---:|
| 1 | 14:54:51 | 52,042.9 | — | 21760898 | 9.45 |
| 2 | 14:55:49 | 28,255.3 | — | 21760110 | 8.50 |
| 3 | 14:56:24 | 26,116.2 | — | 21760153 | 13.73 |
| 4 | 14:56:57 | 26,649.6 | — | 21760419 | 11.55 |
| 5 | 14:57:30 | 25,921.4 | — | 21760168 | 11.43 |

成功試行の時間中央値 26,649.6 ms、範囲 25921.4–52042.9 ms。転送中央値 21,760,168 bytes（20.752 MiB）、範囲 21760110–21760898 bytes。

表示された文：視野あたりの核数をNon-targetingとPLK1 KOで比べました（実験単位の平均：Non-targeting 418、PLK1 KO 74.4 nuclei per field）。

試行中の全ホスト平均 CPU は 8.5–13.7%。disk cache 由来の受信 0 件、JavaScript の未処理例外 0 件。

## 参考：核小体場面の明示 id（初期表示は核・Hoechst）

成功 5/5、未到達 0/5。未到達行の bytes は観測打ち切り時までの受信量であり、表示完了時の量ではない。

| 試行 | 開始 UTC（2026-10-25） | 表示まで ms | 打ち切り観測 ms | bytes | 全ホスト平均 CPU % |
|---|---|---:|---:|---:|---:|
| 1 | 14:58:02 | 79,715.4 | — | 15617803 | 6.84 |
| 2 | 14:59:28 | 28,387.5 | — | 15622241 | 9.87 |
| 3 | 15:00:03 | 29,584 | — | 15622214 | 10.58 |
| 4 | 15:00:38 | 27,892 | — | 15622061 | 10.00 |
| 5 | 15:01:13 | 28,786.4 | — | 15622565 | 12.92 |

成功試行の時間中央値 28,786.4 ms、範囲 27892.0–79715.4 ms。転送中央値 15,622,214 bytes（14.899 MiB）、範囲 15617803–15622565 bytes。

表示された文：平均輝度をUntreatedとActD 1 µMで比べました（実験単位の平均：Untreated 3450、ActD 1 µM 3070 a.u.）。

「核小体」は scenes.json の場面名である。初期画面は領域セレクタが「核」、画像チャンネルが Hoechst で、上記の平均輝度の文を表示した。核小体や 5-EU へ手動切り替えはしていない。その切り替え後の表示速度とは区別する。

試行中の全ホスト平均 CPU は 6.8–12.9%。disk cache 由来の受信 0 件、JavaScript の未処理例外 0 件。

## 比較と上限を決める材料

旧本番は 1 画像と輪郭、新は 2 画像と結果の文なので、以下の差は処理の回帰率ではない。初期場面・画素数・記録数・表示内容・第三者スクリプトも異なる。

| 比較（中央値） | 時間差 ms | 転送差 bytes | 解釈 |
|---|---:|---:|---|
| 新 Preview の通常入口 − 旧本番 | 算出不能 | 算出不能 | 入口が未到達 |
| 参考：新 JUMP の明示 id − 旧本番 | 24,206 | 19,486,248 | 異なる到達点の参考差 |
| 参考：核小体場面の明示 id（初期表示は核・Hoechst） − 旧本番 | 26,342.8 | 13,348,294 | 異なる到達点の参考差 |

通常入口の失敗を先に修正し、同じ配備・場面・到達点で測り直す必要がある。直リンクは入口の代替として N-03 の合格にはしない。5 試行だけでは遅い利用者の p95 や保証上限は決められない。帯域・遅延・端末を固定した今回の中央値と最大値を暫定値の材料にし、許容する余裕をオーナーが決める。上限の仕様・コードは変更しない。

## 到達時の転送内訳（参考、各対象の第 1 試行）

同一 URL の再取得も実際の転送として数える。途中受信はその時点の量。第三者スクリプトも合計から除外しない。

| 対象 | snapshot の PNG | snapshot の JSON（journal以外） | journal | HTML・JS・CSS・font 等 | 第三者 origin | 合計 bytes |
|---|---:|---:|---:|---:|---:|---:|
| production | 1158947 | 102746 | 0 | 829877 | 182350 | 2273920 |
| preview（打ち切り） | 962125 | 152237 | 0 | 837442 | 0 | 1951804 |
| jump-direct | 18153858 | 2384383 | 379794 | 842863 | 0 | 21760898 |
| nucleolar | 13547667 | 848396 | 379899 | 841841 | 0 | 15617803 |

転送量を下り 1250000 bytes/s で割った値は帯域だけの所要時間の目安になる。JUMP の約 21.76 MB は転送だけで約 17.4 秒に相当する。仮に表示 10 秒を目標にするなら、描画前の転送量削減が必要になるが、10 秒を合意した上限として採用したわけではない。実際には追加遅延、request の依存、描画、実回線の揺らぎを含むため、この目安を表示時間の保証には使えない。静的 snapshot は複数場面の初期メタデータと先頭視野を先読みする。今回の通常入口が空でも約 1.95 MB を受信する点は、この先読みと整合する。遅い試行の原因は、この測定だけでは特定していない。

## 390 × 844 の参考確認

各対象は新規プロファイルで開き、ページのブランド表示後 30 秒まで観測した（デスクトップの N-03 到達点ではない）。スクロール・解析・再測定はしない。取得中の request を含む一覧を調べた。

| 対象 | 開始 UTC | 観測終了 UTC | HTTP request 数 | seed/runtime request | 画像 SVG 数（終了時） |
|---|---|---|---:|---:|---:|
| production | 14:43:18 | 14:43:49 | 91 | 0 | 1 |
| preview | 15:01:48 | 15:02:19 | 46 | 0 | 0 |
| jump-direct | 15:03:10 | 15:03:41 | 113 | 0 | 2 |
| nucleolar | 15:02:19 | 15:02:50 | 207 | 0 | 2 |

`seed.zip`、Pyodide、Fiji、Cellpose、wasm、wheel、モデルの取得は観測されなかった。さらに保存済みの正式 24 記録（desktop 20 + mobile 4）の requestsAfter を pathname に `/runtime/` を含む条件で再検索し、該当 0 件と確認した（再測定はしていない）。これは上記の初期閲覧区間の確認であり、全操作・全端末・将来のコードについての証明ではない。通常入口は空画面なので、正常表示の参考は明示 id の場面で行った。

## 未実施・制約・判断事項

- 到達点の visible 判定は DOM の寸法・visibility・display による layout 上の可視状態であり、viewport との交差や文全体が入ることは判定していない。画像 load と文の layout 成立までの時刻として読む。
- JUMP と核小体場面の第 1 試行では、到達約 5 秒後の screenshot（jump-direct-1.png、nucleolar-1.png）を目視し、スクロールなしの 1440×1000 に 2 画像と結果文が入っていることを確認した。ただし到達の瞬間の viewport 内全文は未検証で、後の screenshot をその瞬間の証拠にはしない。
- 本番の変更前から新の 2 画面と結果の文が出る設計ではないため、同一到達点の変更前後比較は未実施。
- headless Chromium のデスクトップ寸法で測定。実スマートフォン、GPU や Safari/Firefox、低性能端末、回線混雑時、OS/CDN の cold cache は未測定。
- 認証を終えて cookie のみを渡した Preview を測定。共有リンクの認証・ログイン所要時間は含めない。Vercel Preview と本番の配信条件が完全に同一とは保証しない。
- Preview では `vercel.live` の feedback script に `Network.loadingFailed`（errorText は空）が記録された。ページ機能の失敗と、外部スクリプトの失敗を分ける。
- [PR #107 の Web CI](https://github.com/genellect/cytellect/actions/runs/40203138473/job/121198423359) は一時 merge `7694f8da7e2ec9399b62e886c979b5a6d5724905`（d0c19fbf の変更を e5514b69 に結合）で初画像待ち 240000 ms が失敗。ログを直接確認した。これは別試験の裏付けであり、今回の 5 試行には含めない。
- オーナー判断：通常入口修正後の再測定を受け、N-03 の時間・転送量の上限と対象端末を決める。科学的な検出精度や画像採用の妥当性はこの性能測定の評価範囲外。

## 再現手順

1. 固定した 2 配備の SHA が上表に一致することを Vercel metadata で確認する。本番 alias が変わった場合、この旧基準とは分ける。
2. checkout 外の作業ディレクトリに以下を `n03-measure.cjs` として保存する。Node 24、`@playwright/test@1.63.0` と対応 Chromium を用意する。共有依存を使う場合は `N03_PLAYWRIGHT_MODULE` にそのモジュールを指定する。
3. 承認された対象限定の短期認証 URL を環境変数 `N03_ACCESS_URL` としてプロセスに渡す。値をシェル履歴・標準出力・PR に書かない。認証 bootstrap の cookie はメモリ内だけで引き継ぎ、各試行の一時プロファイルは終了時に削除する。
4. 他の重い作業を止め、`node n03-measure.cjs production`、`node n03-measure.cjs preview`、`node n03-measure.cjs mobile-jump` を順に実行する。`production` は認証変数なしで実行できる。
5. `n03-results` の各 JSON の milestone.ms・bytes・error を集計する。認証前/事前 probe は数えない。実行環境・時刻・外部通信失敗も保存される。画像は公開画像のみのスクリーンショット。

初期表示判定は `svg[role="img"] image` の load、必要な画像数、旧は `path[data-region]`、新は `section[aria-label="比較の結果"] p` の非空文。CDP event は時刻で切り、リソース受信完了を待って転送量を増やさない。未到達は観測終了時点の bytes として別に集計する。

再現用スクリプト本文の SHA-256（UTF-8、LF）：`624961417f9c0691f0f869745ffec6bcd8082551ab9957122a277554de5dc2b6`。モジュール取得元だけを環境変数化した。

<details>
<summary>測定スクリプト（checkout 外に保存）</summary>

```javascript
const {chromium}=require(process.env.N03_PLAYWRIGHT_MODULE || '@playwright/test');
const fs=require('fs'),os=require('os'),path=require('path');
const OUT=path.join(__dirname,'n03-results');fs.mkdirSync(OUT,{recursive:true});
const prod='https://cytellect.vercel.app/demo',preview='https://cytellect-da1fexzdx-yuto10.vercel.app/demo';
const nucleolar=preview+'?id=a01bbc3c-8ce4-4283-bc69-face42fad2aa';
function safeUrl(u){const v=new URL(u);v.searchParams.delete('_vercel_share');return v.href}
async function auth(){const b=await chromium.launch({headless:true}),c=await b.newContext();try{const r=await c.request.get(process.env.N03_ACCESS_URL);if(!r.ok())throw Error('Auth HTTP '+r.status());return (await c.cookies()).filter(x=>x.domain.includes('cytellect-da1fexzdx-yuto10.vercel.app'));}finally{await b.close()}}
async function run(label,url,index,cookies,mobile=false,probe=false){
 const profile=fs.mkdtempSync(path.join(OUT,'profile-'));
 const c=await chromium.launchPersistentContext(profile,{headless:true,viewport:{width:mobile?390:1440,height:mobile?844:1000},deviceScaleFactor:1,locale:'ja-JP',timezoneId:'Asia/Tokyo',serviceWorkers:'block'});
 const page=c.pages()[0]; if(label!=='production')await c.addCookies(cookies);
 const browserVersion=c.browser()?.version()||'Chromium persistent';
 const cdp=await c.newCDPSession(page),req=new Map(),failures=[],errors=[],history=[];let eventsActive=true;
 const save=(e)=>{const r=req.get(e.requestId);if(r)history.push({id:e.requestId,t:e.timestamp,value:{...r}})};
 cdp.on('Network.requestWillBeSent',e=>{if(!eventsActive)return;if(/^https?:/.test(e.request.url))req.set(e.requestId,{url:safeUrl(e.request.url),type:e.type,bytes:0,status:null,finished:false})});
 cdp.on('Network.responseReceived',e=>{const r=req.get(e.requestId);if(eventsActive&&r){r.bytes=e.response.encodedDataLength||0;r.status=e.response.status;r.cache=!!e.response.fromDiskCache;r.protocol=e.response.protocol;save(e);}});
 cdp.on('Network.dataReceived',e=>{const r=req.get(e.requestId);if(eventsActive&&r){r.bytes+=e.encodedDataLength;save(e)}});
 cdp.on('Network.loadingFinished',e=>{const r=req.get(e.requestId);if(eventsActive&&r){r.bytes=e.encodedDataLength;r.finished=true;save(e)}});
 cdp.on('Network.loadingFailed',e=>{const r=req.get(e.requestId);if(eventsActive)failures.push({url:r?.url,error:e.errorText});});
 page.on('pageerror',e=>errors.push(e.message));
 await cdp.send('Network.enable');await cdp.send('Performance.enable');await cdp.send('Network.setCacheDisabled',{cacheDisabled:true});await cdp.send('Network.setBypassServiceWorker',{bypass:true});
 await cdp.send('Network.emulateNetworkConditions',{offline:false,latency:40,downloadThroughput:1250000,uploadThroughput:125000,connectionType:'wifi'});
 await page.addInitScript(({isNew,mobile})=>{
   const loaded=new WeakSet();window.__n03={};document.addEventListener('load',e=>{if(e.target instanceof SVGImageElement||e.target instanceof HTMLImageElement)loaded.add(e.target)},true);
   function visible(e){const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'}
   function poll(){const svgs=[...document.querySelectorAll('svg[role="img"]')].filter(visible);
     const imgs=svgs.filter(s=>[...s.querySelectorAll('image')].some(i=>Number(i.getAttribute('width'))>0&&loaded.has(i)));
     const result=document.querySelector('section[aria-label="比較の結果"]');
     const outline=imgs[0]?.querySelectorAll('path[data-region]').length||0;
     const ready=mobile?document.body?.innerText.includes('cytellect'):isNew?imgs.length>=2&&result&&visible(result)&&result.querySelector('p')?.textContent.trim():imgs.length>=1&&outline>0;
     if(ready&&!window.__n03.pending){window.__n03.pending=true;requestAnimationFrame(()=>requestAnimationFrame(()=>{window.__n03.milestone={ms:performance.now(),images:imgs.map(s=>s.getAttribute('aria-label')),outline,headline:result?.querySelector('p')?.textContent||null,viewport:{w:innerWidth,h:innerHeight}};}));}else if(!ready)requestAnimationFrame(poll);
   }requestAnimationFrame(poll);
 },{isNew:label!=='production',mobile});
 const started=new Date().toISOString(); const cpuBefore=os.cpus().map(x=>x.times);
 let milestone=null,error=null;
 try{await page.goto(url,{waitUntil:'domcontentloaded',timeout:120000});const elapsed=await page.evaluate(()=>performance.now());await page.waitForFunction(()=>window.__n03?.milestone,null,{timeout:Math.max(1,(probe?20000:120000)-elapsed)});milestone=await page.evaluate(()=>window.__n03.milestone)}catch(e){error=e.message.split('\n')[0]}
 const observedMs=await page.evaluate(()=>performance.now());
 const metrics=(await cdp.send('Performance.getMetrics')).metrics;
 const navigationStart=metrics.find(x=>x.name==='NavigationStart')?.value;
 const cutoff=milestone&&navigationStart?navigationStart+milestone.ms/1000:Infinity;
 const atTime=new Map();history.filter(x=>x.t<=cutoff).forEach(x=>atTime.set(x.id,x.value));
 const atMilestone=[...atTime.values()];
 const bytes=atMilestone.reduce((n,r)=>n+r.bytes,0);
 await page.waitForTimeout(mobile?30000:probe?15000:5000);
 const body=(await page.locator('body').innerText()).slice(0,22000);
 await page.screenshot({path:path.join(OUT,`${label}-${index}${mobile?'-mobile':''}.png`),fullPage:true});
 const images=await page.locator('svg[role="img"]').evaluateAll(xs=>xs.map(x=>({label:x.getAttribute('aria-label'),images:[...x.querySelectorAll('image')].map(i=>({href:i.getAttribute('href')?.split(':')[0],width:i.getAttribute('width')})),regions:x.querySelectorAll('path[data-region]').length,rect:{width:x.getBoundingClientRect().width,height:x.getBoundingClientRect().height}})));
 const after=[...req.values()].map(x=>({...x}));eventsActive=false;
 const cpuAfter=os.cpus().map(x=>x.times);let total=0,idle=0;cpuBefore.forEach((a,i)=>{for(const k in a)total+=cpuAfter[i][k]-a[k];idle+=cpuAfter[i].idle-a.idle});
 const record={label,index,mobile,probe,url,finalUrl:safeUrl(page.url()),started,ended:new Date().toISOString(),browserVersion,os:os.release(),cpu:os.cpus()[0].model,logicalCpu:os.cpus().length,memoryGiB:os.totalmem()/2**30,cpuBusyPercent:100*(total-idle)/total,milestone,observedMs,bytes,requestsAtMilestone:atMilestone,requestsAfter:after,seedOrRuntime:after.filter(x=>/seed\.zip|fiji|cellpose|pyodide|\.onnx|\.wasm|\.jar|\.whl/i.test(new URL(x.url).pathname)),failures,errors,error,images,body};
 fs.writeFileSync(path.join(OUT,`${label}-${index}${mobile?'-mobile':''}.json`),JSON.stringify(record,null,2));
 console.log(JSON.stringify({label,index,mobile,ms:milestone?.ms,bytes,requests:atMilestone.length,seedOrRuntime:record.seedOrRuntime.length,error,finalUrl:record.finalUrl}));
 await c.close();if(!path.resolve(profile).startsWith(path.resolve(OUT)+path.sep))throw Error('Profile path escaped output directory');fs.rmSync(profile,{recursive:true,force:true});return record;
}
(async()=>{
const mode=process.argv[2]||'all',cookies=process.env.N03_ACCESS_URL?await auth():[];delete process.env.N03_ACCESS_URL;
if(mode==='probe'){await run('preview',preview,'probe',cookies,false,true);return}
if(mode==='mobile-jump'){await run('jump-direct',preview+'?id=bdb1e2fa-86cb-46c5-9be0-6cb43039bb9a',1,cookies,true);return}
if(mode==='production'){for(let i=1;i<=5;i++)await run('production',prod,i,[]);await run('production',prod,1,[],true);return}
if(mode==='preview'){for(let i=1;i<=5;i++)await run('preview',preview,i,cookies);for(let i=1;i<=5;i++)await run('jump-direct',preview+'?id=bdb1e2fa-86cb-46c5-9be0-6cb43039bb9a',i,cookies);for(let i=1;i<=5;i++)await run('nucleolar',nucleolar,i,cookies);await run('preview',preview,1,cookies,true);await run('nucleolar',nucleolar,1,cookies,true);return}
for(let i=1;i<=5;i++){await run('production',prod,i,[]);await run('preview',preview,i,cookies)}
for(let i=1;i<=5;i++)await run('nucleolar',nucleolar,i,cookies);
for(const [label,url] of [['production',prod],['preview',preview],['nucleolar',nucleolar]])await run(label,url,1,cookies,true);
})().catch(e=>{console.error(e.name+': '+e.message.replace(/_vercel_share=[^&\s]+/g,'_vercel_share=[REDACTED]'));process.exit(1)});

```

</details>
