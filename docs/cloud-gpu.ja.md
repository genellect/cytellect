# クラウド GPU で Cellpose を動かす

研究室の PC に GPU がなくても、Cellpose（核小体・細胞の自動検出）を実用的な速さで使うための設定です。Cellpose の推論だけを、使ったときだけ課金されるクラウドの GPU（[Modal](https://modal.com)）で行います。画像の登録、核の検出（Fiji）、測定、統計、図、保存は、これまでどおり PC で行います。

この文書は、設定を行う管理者向けです。研究者の操作は変わりません。

## 仕組み

1. 研究者が Cellpose を使う検出を実行すると、Cytellect は次のものをクラウド GPU に送ります。
   - 検出に使う 1 チャンネルの画像
   - 核小体の検出では、採用済みの核のマスク
   - 検出条件
2. クラウド GPU は、PC と同じ `runner.py`・同じモデル・同じ版のライブラリで推論し、候補のラベル画像だけを返します。
3. Cytellect は返ってきた結果の版（runner・モデル・ライブラリのハッシュ）を確かめます。一致しない場合は結果を使いません。
4. 核への割り当て、境界の補正、測定は、PC で今までと同じ処理を行います。

ファイル名、作業名、実験条件、ほかのチャンネルは送りません。

## 費用の目安

Modal の Starter プラン（月額 0 円）を使います。

| 項目 | 目安 |
| --- | --- |
| 無料枠 | カードを登録すると毎月 30 ドル分（登録前は 1 ドル分）。使い残しは翌月に繰り越さない |
| GPU（NVIDIA L4） | 1 秒あたり 0.000222 ドル（1 時間で約 0.8 ドル）。CPU とメモリは別に秒単位 |
| 使い終わった後 | 20 秒で自動停止（`infra/modal_cellpose.py` の `SCALEDOWN_SECONDS`）。止まっている間は 0 円 |
| 1 視野あたり | 起動済みなら 6〜11 秒で約 0.003 ドル。停止状態からの起動（約 3 分）を含むと 1 回約 0.06 ドル（[実測](#実測2026-10-23)） |

**支出の上限（Spend limit）を必ず 0 ドルにしてください。** 無料枠を超える処理は止まり、請求は出ません。上限に達すると、その月は Cellpose が使えなくなります。

## 管理者の準備（最初の 1 回）

### 1. コンテナイメージを公開する

GitHub の Actions で「Cellpose GPU image」を `main` から実行します（オーナーの指示で行います）。完了すると、実行結果の概要にイメージの場所（`ghcr.io/genellect/cytellect-cellpose-gpu@sha256:…`）が表示されます。`infra/modal_cellpose.py` の `IMAGE` を、この値にします。

中身は、公開しているコード、公開ライブラリ、公開モデル（BSD-3-Clause）だけです。パッケージは公開（Public）にします。

### 2. Modal のアカウントを作る

1. GitHub アカウントの 2 段階認証を有効にしてから、[Modal](https://modal.com) に GitHub アカウントで登録します。プランは Starter です。ほかのメンバーは招待しません。
2. Settings の Usage / Billing で、Spend limit を 0 ドル、Workspace budget を 30 ドルにします。
3. Settings の API Tokens でデプロイ用のトークン（`ak-…` と `as-…`）を作ります。
4. Settings の Proxy Auth Tokens で接続用のトークン（`wk-…` と `ws-…`）を作ります。研究室の PC は、これで GPU を呼び出します。

### 3. GitHub に登録してデプロイする

1. リポジトリの Settings → Secrets and variables → Actions に、`MODAL_TOKEN_ID` と `MODAL_TOKEN_SECRET`（手順 2 の 3）を登録します。
2. GitHub の Actions で「Cellpose Modal deploy」を `main` から実行します（オーナーの指示で行います）。実行結果の概要に、サーバーの URL（`https://….modal.direct`）が表示されます。

デプロイ用のトークンは GitHub の秘密の値にだけ置き、研究室の PC や作業環境には置きません。この作業環境（Claude Code のクラウドセッション）からは、通信の制約で `modal deploy` を実行できません。

### 4. Cytellect に設定する

**Windows 版**：セットアップ画面の「Cellpose用クラウドGPUの接続先」に手順 3 の URL を入れます。「接続キー」には、手順 2 の 4 の接続用トークンの ID と Secret を、**ピリオド（`.`）でつないで**入れます。

```
wk-…….ws-……
```

Cytellect はこの値を `Authorization: Bearer` として送り、Modal はこの形を受け付けます（[Modal の説明](https://modal.com/docs/guide/webhook-proxy-auth)）。ID だけ、Secret だけ、または別の記号でつなぐと、すべての要求が拒否されます。

**Docker 版**：現時点では使えません。Docker 版の worker は、研究画像を外へ出さないため、ネットワークから切り離しています（`compose.yaml` の `network_mode: none`）。worker にクラウド GPU の接続を許す設定は、安全設計の見直しとあわせて別に用意します。

### 5. 動作を確かめる

公開画像で、時間と結果を確かめます。

```sh
CYTELLECT_CELLPOSE_REMOTE_URL=https://….modal.direct \
CYTELLECT_CELLPOSE_REMOTE_TOKEN=wk-…….ws-…… \
uv run python scripts/cellpose_remote_check.py --image fixtures/public/bbbc013/A01-dapi.tif --crop 320 \
  --skip-local --receipt cellpose-remote-check.json
```

記録（`cellpose-remote-check.json`）には、検出数、所要時間、GPU の種類だけが残ります。画素やパスは残りません。PC に Cellpose の CPU 環境がある場合は `--skip-local` を外すと、PC の結果との一致度も記録します。

研究室の実画像で確かめる場合は、[実画像での確認](#実画像での確認)の手順で、画像のある PC から実行します。

## 実測（2026-10-23）

`main` の 1e39876 をデプロイした Modal Server（NVIDIA L4 × 1、最大 1 台、同時処理 1 件、20 秒で停止）を、`scripts/cellpose_remote_check.py` で測りました。比べた CPU は、Linux の作業環境の CPU で動かした同じ runner・モデル・ライブラリです。

| 画像 | 検出 | GPU | CPU | 一致度 |
| --- | --- | --- | --- | --- |
| BBBC013 A01 の DAPI（320 × 320） | Cellpose-SAM（protocol 4.0.0） | 6.4 秒 | 87.6 秒 | ラベル画像が完全に一致（74 個とも一致、画素の違い 0） |
| 4DN 4DNFI7FAWT6C の NCL（512 × 512） | NCL（protocol 4.3.0）。核は Otsu の代用（8 個） | 10.5 秒 | 127.4 秒 | ラベル画像が完全に一致（9 個とも一致、画素の違い 0） |

- 時間は、PC から要求を送って結果を受け取るまでです（転送を含み、起動済みの状態）。
- 停止状態から `/health` が応答するまでは 166 秒と 188 秒でした。Cytellect は起動中の応答（503）を最大 900 秒待ちます。
- 接続キーは `wk-…….ws-……` の `Authorization: Bearer` で受け付けられました。キーなし・誤ったキーは 401 で拒否されました。
- 2 回の測定でコンテナが動いた時間は、起動・処理・20 秒の待機を合わせて約 420 秒です。L4・CPU 2 コア・メモリ 8 GiB の単価から、費用は約 0.11 ドルと見積もりました（無料枠から差し引かれ、請求はありません）。Modal の画面の使用額で確認します。
- 核の代用は時間を測るためのもので、製品の核検出（StarDist）ではありません。公開画像には正解の輪郭がないため、検出の正確さは評価していません。

## 実画像での確認

研究室の実画像では、画像をこの作業環境や GitHub に置かず、画像のある PC から確かめます。記録に残るのは、検出数、所要時間、GPU の種類、CPU との一致度だけです。ファイル名、パス、画素は残りません。

- **Windows 版で確かめる**：手順 4 の設定をしたうえで、いつもどおり核小体の検出を実行します。製品と同じ流れ（StarDist の核 → Cellpose）で、所要時間と結果を確かめられます。Windows 版には CPU の Cellpose がないため、CPU との一致度は測れません。
- **CPU との一致度も測る**：リポジトリと `uv` のある PC で、`uv run python scripts/cellpose_setup.py <runtime の場所> --model-cache <モデルの場所> --runtime-only` で CPU の環境を用意し、手順 5 のコマンドを `--skip-local` なしで実行します。核小体では `--plane <NCL のチャンネル> --nuclei-plane <DAPI のチャンネル>` を付けます。CPU では 1 視野に数分かかります。

記録（JSON）を共有するときは、中身が数値だけであることを確かめてから渡します。画像そのもの、ファイル名、結果の画像は共有しません。

## 送ったデータの扱い（Modal）

- Modal の Server 型で動かします。Modal の説明では、Server 型の送受信の中身は保存されず、そのままコンテナに渡されます。入出力を最大 7 日間保存する Web Function 型は使いません（`tests/test_cellpose_modal.py` で固定しています）。
- サーバーは画像をメモリ上でだけ扱い、ログには処理時間だけを出します。Modal のログは Starter では 1 日で消えます。
- Volume（保存領域）と memory snapshot（メモリの保存）は使いません。
- 最も注意すべきなのは、Modal のアカウントやデプロイ用トークンの乗っ取りです。乗っ取られると、画像を記録する偽のサーバーに置き換えられるおそれがあります。2 段階認証、メンバーを増やさないこと、デプロイ用トークンを GitHub の秘密の値にだけ置くことで防ぎます。

## 別の方法：Hugging Face Inference Endpoints

同じイメージは、Hugging Face Inference Endpoints でも動きます（Custom container、ポート `8080`、ヘルスチェック `/health`、NVIDIA L4 × 1、最小 0・最大 1、Protected）。ただし、自動停止までに最短 15 分かかり、その間も課金されます。使うたびに最低でも 0.3 ドルほどかかるので、PoC では Modal を使います。接続キーには、Inference Endpoints を呼び出す権限だけを付けた fine-grained トークンを使います。

## 結果の記録

解析版の記録（`runtime`）に、次の項目が残ります。

- `device`（`cuda`）、`precision`（`float32`）、`gpu`（GPU の種類）
- `execution_backend`：クラウドで処理したこと、接続先のホスト名、検出条件で指定されていた処理装置
- `service`：クラウド側の runner・サーバー・ライブラリ・モデルのハッシュ

GPU では、TF32 を使わない float32 と、毎回同じ結果になる計算方法を使います。それでも GPU と CPU の結果が 1 画素も違わないとは限りません。公開画像の受入では、2 枚とも CPU とラベル画像が完全に一致しました（[実測](#実測2026-10-23)）。

## 困ったとき

| 表示 | 対処 |
| --- | --- |
| クラウド GPU に接続できませんでした（接続キーが無効です） | 接続用トークンが無効です。手順 2 の 4 で作り直し、手順 4 の設定を直します |
| クラウド GPU の起動が時間内に終わりませんでした | 停止していた GPU の起動に時間がかかっています。数分おいて、もう一度実行します。月の無料枠を使い切った場合も起動しません（Modal の Usage を確認します） |
| クラウド GPU の版がこの Cytellect と一致しません | Cytellect を更新した後は、同じ版のイメージを手順 1 で公開し、`IMAGE` を差し替えて手順 3 でデプロイし直します |
| クラウド GPU に接続できませんでした | ネットワークの接続と、手順 4 の URL を確認します |
| サーバーが起動しない（イメージを取得できない） | 手順 1 のパッケージが公開（Public）になっているか確認します |
