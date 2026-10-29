# クラウド GPU で Cellpose を動かす

研究室の PC に GPU がなくても、Cellpose（核小体・細胞の自動検出）を実用的な速さで使うための設定。Cellpose の推論だけを、使ったときだけ課金されるクラウドの GPU（[Modal](https://modal.com)）で行う。画像の登録、核の検出（Fiji）、測定、統計、図、保存は、これまでどおり PC で行う。

| 項目 | 内容 |
|---|---|
| 対象 | クラウド GPU を設定する研究室の管理者。研究者の操作は変わらない |
| 対応する版 | Windows 版。Docker 版は対応しない（[手順 4](#4-cytellect-に設定する)） |
| 費用 | Modal の Starter プラン（月額 0 円）と無料枠の範囲。支出の上限を 0 ドルにする |
| 管理者が行うこと | コンテナイメージの公開、Modal の登録、デプロイ、接続先と接続キーの配布 |

## 仕組み

1. 研究者が Cellpose を使う検出を実行すると、Cytellect は次のものをクラウド GPU に送る。
   - 検出に使う 1 チャンネルの画像
   - 核小体の検出では、採用済みの核のマスク
   - 検出条件
2. クラウド GPU は、PC と同じ `runner.py`・同じモデル・同じ版のライブラリで推論し、候補のラベル画像だけを返す。
3. Cytellect は返ってきた結果の版（runner・モデル・ライブラリのハッシュ）を確かめる。一致しない場合は結果を使わない。
4. 核への割り当て、境界の補正、測定は、PC で今までと同じ処理を行う。

ファイル名、作業名、実験条件、ほかのチャンネルは送らない。

## 費用の目安

Modal の Starter プラン（月額 0 円）を使う。

| 項目 | 目安 |
| --- | --- |
| 無料枠 | カードを登録すると毎月 30 ドル分（登録前は 1 ドル分）。使い残しは翌月に繰り越さない |
| GPU（NVIDIA L4） | 1 秒あたり 0.000222 ドル（1 時間で約 0.8 ドル）。CPU とメモリは別に秒単位 |
| 使い終わった後 | アイドル状態が 20 秒続くと自動停止（`infra/modal_cellpose.py` の `SCALEDOWN_SECONDS`）。処理中の要求がある場合、終了時に最大 1,800 秒の猶予を設ける。止まっている間は 0 円 |
| 1 視野あたり | 実測後に記載 |

**支出の上限（Spend limit）は必ず 0 ドルにする。** 無料枠を超える処理は止まり、請求は出ない。上限に達すると、その月は Cellpose が使えなくなる。

同時実行は L4 コンテナ 1 台・要求 1 件。`target_concurrency=1` で処理中の要求を需要として扱い、停止処理に入った場合も `exit_grace_period=1800` で、クライアントの要求期限まで完了を待てるようにする。この猶予は常時起動の設定ではないが、終了待ち中も稼働分は課金対象。1,800 秒をすべて使った場合、GPU 分は約 0.40 ドルで、CPU・メモリ分は別（[Modal Server の設定](https://modal.com/docs/sdk/py/latest/App#server)）。

## 管理者の準備（最初の 1 回）

### 1. コンテナイメージを公開する

GitHub の Actions で「Cellpose GPU image」を `main` から実行する（オーナーの指示で行う）。完了すると、実行結果の概要にイメージの場所（`ghcr.io/genellect/cytellect-cellpose-gpu@sha256:…`）が表示される。`infra/modal_cellpose.py` の `IMAGE` を、この値にする。

中身は、公開しているコード、公開ライブラリ、公開モデル（BSD-3-Clause）だけ。パッケージは公開（Public）にする。

### 2. Modal のアカウントを作る

1. GitHub アカウントの 2 段階認証を有効にしてから、[Modal](https://modal.com) に GitHub アカウントで登録する。プランは Starter。ほかのメンバーは招待しない。
2. Settings の Usage / Billing で、Spend limit を 0 ドル、Workspace budget を 30 ドルにする。
3. Settings の API Tokens でデプロイ用のトークン（`ak-…` と `as-…`）を作る。
4. Settings の Proxy Auth Tokens で接続用のトークン（`wk-…` と `ws-…`）を作る。研究室の PC は、これで GPU を呼び出す。

### 3. GitHub に登録してデプロイする

1. リポジトリの Settings → Secrets and variables → Actions に、`MODAL_TOKEN_ID` と `MODAL_TOKEN_SECRET`（手順 2 の 3）を登録する。
2. GitHub の Actions で「Cellpose Modal deploy」を `main` から実行する（オーナーの指示で行う）。サーバーの URL（`https://genellect--cytellect-cellpose-cellposeserver.us-east.modal.direct`）は、ログの `Created Server CellposeServer` の行に表示される。Server 型の URL は `*.modal.run` ではなく `*.modal.direct` で、実行結果の概要には表示されない。

デプロイ用のトークンは GitHub の秘密の値にだけ置き、研究室の PC や作業環境には置かない。この作業環境（Claude Code のクラウドセッション）からは、通信の制約で `modal deploy` を実行できない。

### 4. Cytellect に設定する

**Windows 版**：セットアップ画面の「Cellpose用クラウドGPUの接続先」に手順 3 の URL を入れる。「接続キー」には、手順 2 の 4 の接続用トークンの ID と Secret を、**ピリオド（`.`）でつないで**入れる。

```
wk-…….ws-……
```

Cytellect はこの値を `Authorization: Bearer` として送り、Modal はこの形を受け付ける（[Modal の説明](https://modal.com/docs/guide/webhook-proxy-auth)）。ID だけ、Secret だけ、または別の記号でつなぐと、すべての要求が拒否される。

**Docker 版**：現時点では使えない。Docker 版の worker は、研究画像を外へ出さないため、ネットワークから切り離している（`compose.yaml` の `network_mode: none`）。worker にクラウド GPU の接続を許す設定は、安全設計の見直しとあわせて別に用意する。

### 5. 動作を確かめる

公開画像で、時間と結果を確かめる。研究画像は使わない。

```sh
CYTELLECT_CELLPOSE_REMOTE_URL=https://genellect--cytellect-cellpose-cellposeserver.us-east.modal.direct \
CYTELLECT_CELLPOSE_REMOTE_TOKEN=wk-…….ws-…… \
uv run python scripts/cellpose_remote_check.py --image fixtures/public/bbbc013/A01-dapi.tif --crop 320 \
  --skip-local --receipt cellpose-remote-check.json
```

記録（`cellpose-remote-check.json`）には、検出数、所要時間、GPU の種類だけが残る。画素やパスは残らない。PC に Cellpose の CPU 環境がある場合は `--skip-local` を外すと、PC の結果との一致度も記録する。

### 開発環境から使う

開発環境（`python3 scripts/dev.py serve`、[CONTRIBUTING](../CONTRIBUTING.md#外部サービス)）も、同じサーバーを使う。手順 2 の 4 の接続用トークンを ID と Secret に分け、作業環境の環境変数として登録する。

| 環境変数 | 値 |
| --- | --- |
| `CYTELLECT_MODAL_PROXY_KEY` | 接続用トークンの ID（`wk-…`） |
| `CYTELLECT_MODAL_PROXY_SECRET` | 接続用トークンの Secret（`ws-…`） |

`scripts/dev.py` は 2 つをピリオドでつないで接続キーにし、上の URL を接続先にします。`python3 scripts/dev.py doctor --live` は、この接続キーで `/health` を呼び、200 が返るかを確かめます。GPU の空き待ちがあるため、起動時間は一定ではありません。起動中と使用後の 20 秒も課金されます。試験には公開画像だけを使います。

### 起動待ちと受入確認

Modal Server が停止していると、最初の要求は `503 no upstreams available` となり、起動が始まります。利用可能なコンテナができるまで要求はキューに保存されません（[Modal Servers](https://modal.com/docs/guide/servers#zero-to-one-scaling)）。`503` だけでは、割当待ち・起動失敗・予算上限のどれが原因かは分かりません。

1. 管理画面の Containers・Logs・Usage を確認します。`waiting to be scheduled on a GPU_L4 worker` は L4 の空き待ちです。Usage ではクレジット残額と使用上限の両方を確認します。
2. 公開画像と解析画面を先に準備します。起動待ちは終了時刻を決め、health の送信回数・UTC・HTTP 状態を記録します。数分で確認を止めた後に GPU が割り当てられる場合もあるため、短い確認だけで起動不能とは判定しません。
3. 現在の画面が準備できた状態で、新しい health 200 を受けた直後に推論へ進みます。古い 200 を再利用しません。起動後に要求が来ないと、アイドル 20 秒で停止するためです。
4. 推論は許可された回数だけ送信し、失敗分も数えます。終了時刻までに health 200 が出なければ、推論は未実行として記録します。自動的な推論の再送、予算上限の引き上げ、GPU 種類の変更は行いません。

コンテナの `Responses 0`・`Done` と、待受中の `KeyboardInterrupt`／`Drained` が同時に記録されている場合は、要求を受ける前の通常の停止と整合します。Traceback の表示だけで起動失敗と決めず、終了状態・処理件数・時刻を合わせて確認します。GPU の割当完了と、実推論・画面での採用・測定の成功は、別々の受入条件です。

## 送ったデータの扱い（Modal）

- Modal の Server 型で動かす。Modal の説明では、Server 型の送受信の中身は保存されず、そのままコンテナに渡される。入出力を最大 7 日間保存する Web Function 型は使わない（`tests/test_cellpose_modal.py` で固定している）。
- サーバーは画像をメモリ上でだけ扱い、ログには処理時間だけを出す。Modal のログは Starter では 1 日で消える。
- Volume（保存領域）と memory snapshot（メモリの保存）は使わない。
- 最も注意すべきなのは、Modal のアカウントやデプロイ用トークンの乗っ取り。乗っ取られると、画像を記録する偽のサーバーに置き換えられるおそれがある。2 段階認証、メンバーを増やさないこと、デプロイ用トークンを GitHub の秘密の値にだけ置くことで防ぐ。

## 別の方法：Hugging Face Inference Endpoints

同じイメージは、Hugging Face Inference Endpoints でも動く（Custom container、ポート `8080`、ヘルスチェック `/health`、NVIDIA L4 × 1、最小 0・最大 1、Protected）。ただし、自動停止までに最短 15 分かかり、その間も課金される。使うたびに最低でも 0.3 ドルほどかかるため、PoC では Modal を使う。接続キーには、Inference Endpoints を呼び出す権限だけを付けた fine-grained トークンを使う。

## 結果の記録

解析版の記録（`runtime`）に、次の項目が残る。

- `device`（`cuda`）、`precision`（`float32`）、`gpu`（GPU の種類）
- `execution_backend`：クラウドで処理したこと、接続先のホスト名、検出条件で指定されていた処理装置
- `service`：クラウド側の runner・サーバー・ライブラリ・モデルのハッシュ

GPU では、TF32 を使わない float32 と、毎回同じ結果になる計算方法を使う。それでも GPU と CPU の結果が 1 画素も違わないとは限らない。初回の受入では、公開画像で CPU との一致度を記録する。

## 困ったとき

研究者の画面に表示される文言と、管理者が行う対処。

| 表示 | 対処 |
| --- | --- |
| 「クラウドGPUに接続できませんでした（接続キーが無効です）」 | 接続用トークンが無効。手順 2 の 4 で作り直し、手順 4 の設定を直す |
| 「クラウドGPUの起動が時間内に終わりませんでした」 | 停止していた GPU の起動に時間がかかっている。数分おいて、もう一度実行する。月の無料枠を使い切った場合も起動しない（Modal の Usage を確認する） |
| 「クラウドGPUの版がこのCytellectと一致しません」 | Cytellect を更新した後は、同じ版のイメージを手順 1 で公開し、`IMAGE` を差し替えて手順 3 でデプロイし直す |
| 「クラウドGPUに接続できませんでした。ネットワーク接続を確認して…」 | ネットワークの接続と、手順 4 の URL を確認する |
| 推論中に `502` が返り、Modal に `Server has been draining for too long` が記録される | 処理中のコンテナが停止している。デプロイ済み設定の `target_concurrency=1` と `exit_grace_period=1800` を確認する。修正の反映には手順 3 の再デプロイが必要。再実行前にログで終了原因を確認し、GPU の要求回数に失敗分も含める |
| `/health` が数分以上 `503 no upstreams available` を返す | 利用可能なコンテナがない。Containers・Logs・Usage で GPU の割当待ち、起動失敗、クレジット・使用上限を区別する。[起動待ちと受入確認](#起動待ちと受入確認)の手順で確認し、health が通らなかった試行を推論失敗や推論成功として数えない |
| サーバーが起動しない（イメージを取得できない） | 手順 1 のパッケージが公開（Public）になっているか確認する |

## 関連文書

- [Windows版のインストールと更新](install-windows.ja.md)：研究者が接続先と接続キーを入力する手順
- [データ保護と運用](security.md)（英語）：研究データを外部へ送る範囲の設計
