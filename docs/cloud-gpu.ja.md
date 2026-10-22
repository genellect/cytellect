# クラウド GPU で Cellpose を動かす

研究室の PC に GPU がなくても、Cellpose（核小体・細胞の自動検出）を実用的な速さで使うための設定です。Cellpose の推論だけを Hugging Face Inference Endpoints の GPU で行います。画像の登録、核の検出（Fiji）、測定、統計、図、保存は、これまでどおり PC で行います。

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

| 項目 | 目安 |
| --- | --- |
| GPU（NVIDIA L4） | 1 時間あたり約 0.70〜0.80 ドル。動いている間だけ、1 分単位で課金 |
| 待機中 | 自動停止（0 台）の間は 0 円 |
| 月 100〜300 視野の PoC | 数百円〜千円程度の見込み（実測後に更新） |

費用の大部分は、起動にかかる時間と、使い終わってから自動停止するまでの待ち時間です。最小の台数を 1 にすると常に課金され、月 500 ドル前後になります。必ず 0 にしてください。

## 管理者の準備（最初の 1 回）

### 1. コンテナイメージを公開する

GitHub の Actions で「Cellpose GPU image」を `main` から実行します（オーナーが行います）。完了すると、実行結果の概要に次の形式でイメージの場所が表示されます。

```
ghcr.io/genellect/cytellect-cellpose-gpu@sha256:…
```

GitHub の Packages で `cytellect-cellpose-gpu` を公開（Public）に設定します。中身は公開しているコード、公開ライブラリ、公開モデル（BSD-3-Clause）だけです。

### 2. Hugging Face で Endpoint を作る

Hugging Face の組織（Genellect）で Inference Endpoints を開き、新しい Endpoint を次の設定で作ります。

| 項目 | 設定 |
| --- | --- |
| リポジトリ | 小さな空のリポジトリ（画像やモデルは置きません。Cellpose のモデルはイメージに入っています） |
| ハードウェア | NVIDIA L4 × 1（料金表で一番安い提供元を選ぶ） |
| 台数 | 最小 0、最大 1 |
| 自動停止 | 選べる中で一番短い時間 |
| セキュリティ | Protected（Hugging Face のトークンが必要） |
| コンテナ | Custom。イメージに手順 1 の `ghcr.io/…@sha256:…` を指定。ポート `8080`、ヘルスチェックの経路 `/health` |

作成後に表示される Endpoint の URL（`https://….endpoints.huggingface.cloud`）を控えます。

### 3. トークンを作る

Hugging Face の設定で、細かく権限を選べるトークン（fine-grained）を作り、Genellect 組織の Inference Endpoints を呼び出す権限だけを付けます。トークンは研究室の PC に保存するので、ほかの権限は付けません。漏れた場合は、すぐに無効にして作り直します。

### 4. Cytellect に設定する

**Windows 版**：保存先（既定は `%LOCALAPPDATA%\Cytellect`）の `settings` フォルダーに、`cellpose-remote.json` を次の内容で保存します。

```json
{"schema": "cytellect-cellpose-remote/1", "url": "https://….endpoints.huggingface.cloud", "token": "hf_…"}
```

Cytellect を開き直すと、Cellpose の検出がクラウド GPU で行われます。

**Docker 版**：worker に環境変数 `CYTELLECT_CELLPOSE_REMOTE_URL` と `CYTELLECT_CELLPOSE_REMOTE_TOKEN` を設定します。

### 5. 動作を確かめる

公開画像で、時間と結果を確かめます。研究画像は使いません。

```sh
CYTELLECT_CELLPOSE_REMOTE_URL=https://….endpoints.huggingface.cloud \
CYTELLECT_CELLPOSE_REMOTE_TOKEN=hf_… \
uv run python scripts/cellpose_remote_check.py --image fixtures/public/bbbc013/A01-dapi.tif --crop 320 \
  --skip-local --receipt cellpose-remote-check.json
```

記録（`cellpose-remote-check.json`）には、検出数、所要時間、GPU の種類だけが残ります。画素やパスは残りません。PC に Cellpose の CPU 環境がある場合は `--skip-local` を外すと、PC の結果との一致度も記録します。

## 結果の記録

解析版の記録（`runtime`）に、次の項目が残ります。

- `device`（`cuda`）、`precision`（`float32`）、`gpu`（GPU の種類）
- `execution_backend`：クラウドで処理したこと、接続先のホスト名、検出条件で指定されていた処理装置
- `service`：クラウド側の runner・サーバー・ライブラリ・モデルのハッシュ

GPU では、TF32 を使わない float32 と、毎回同じ結果になる計算方法を使います。それでも GPU と CPU の結果が 1 画素も違わないとは限りません。初回の受入では、公開画像で CPU との一致度を記録します。

## 困ったとき

| 表示 | 対処 |
| --- | --- |
| クラウド GPU に接続できませんでした（接続キーが無効です） | トークンが無効か、権限が足りません。手順 3 で作り直し、手順 4 の設定を直します |
| クラウド GPU の起動が時間内に終わりませんでした | 停止していた GPU の起動に時間がかかっています。数分おいて、もう一度実行します |
| クラウド GPU の版がこの Cytellect と一致しません | Cytellect を更新した後は、同じ版のイメージを手順 1 で公開し、Endpoint のイメージを差し替えます |
| クラウド GPU に接続できませんでした | ネットワークの接続と、手順 4 の URL を確認します |
