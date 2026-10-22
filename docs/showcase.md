# 公開デモ（サーバーレスのショーケース）

公開サイトの `/demo` は、本番と同じ解析ワークスペース（`ConnectedWorkspace`）を、解析サーバーなしで動かします。画像の追加を除く現行機能を、本番と同じ UI でエラーなく再現することが目標です。研究画像は扱わず、出典と利用条件を確認した公開画像だけを使います。

## 構成

```
本番の API とワーカー（実際の Fiji/StarDist・Cellpose）で公開画像を処理する
  └─ 検出の記録・初期状態（SQLite と全ファイル）・初期表示の GET 応答を書き出す（ビルド時、CPython）
        │
        ├─ ① 応答の再生：初期表示の GET を記録から返す。すぐ開き、スマートフォンでも動く
        └─ ② ブラウザ内の API：同じ初期状態から、Pyodide 上で実際の API・ワーカー・解析パッケージを動かす
              検出だけは記録を返し、測定・統計・作図・保存は同じ Python 実装が計算する
```

- 最初の変更操作から先は、すべて②が処理する。②が使えない環境（スマートフォン、メモリ不足）では、変更操作の代わりに案内を表示する。
- 検出（StarDist/Fiji、Cellpose）はブラウザで実行しない。記録した条件以外の検出は行わず、入力欄は記録した値の範囲に揃える。
- 測定値と統計は、API と解析パッケージの共通実装だけが生成する。ブラウザ内の計算結果は、同じ操作のサーバー出力と CI で照合する。
- 有料サービス（LLM）は呼ばない。AI の提案は、実際のモデル出力として記録したものだけを再生する。

## 共有する契約

並行して実装する部品の境界です。変更する場合は、この文書と両側の実装を同じ PR で更新します。

### Python パッケージ `cytellect_showcase`

場所は `services/showcase/src/cytellect_showcase/`。`__init__.py` の内容は次の1行に固定します。

```python
"""Serverless public showcase for Cytellect."""
```

| モジュール | 役割 |
|---|---|
| `runtime.py` | `async boot(seed_zip: bytes, origin: str) -> None`、`async handle(method: str, url: str, headers: list[list[str]], body: bytes \| None) -> dict`（`{"status": int, "headers": [[name, value], ...], "body": bytes}`）。セッションは内部で作成・保持し、呼び出し側は Cookie を扱わない。変更系の要求の後、待機中のジョブをその場で実行する |
| `detections.py` | 検出の記録と再生。`install_recorder(out_dir: Path)`、`install_replay(recordings_dir: Path)`、`record_key(...)` |
| `build.py` | ビルド時に CPython で実行する。公開画像の取り込み、記録付きの実検出、シナリオの実行、初期状態と GET 応答の書き出し |
| `seed.py` | `restore(data_dir: Path) -> int`。`seed.zip` を展開した直後、API を開く前に `boot()` が呼ぶ。`showcase.json` の `regenerate` に列挙した重複ファイル（元 TIFF から復号する `channel-*.npy`、その複製）をバイト単位で再生成し、SHA-256 を照合する。不一致は `showcase_seed_restore_mismatch` |

### 検出の記録キー

`cytellect_worker.regions` が呼ぶ検出関数 `detect_nuclei`、`detect_cellpose`、`detect_compartments`、`detect_positive_regions` を、同じ名前で差し替えて記録・再生します。

- キーは、次の JSON を `sort_keys=True`、`separators=(",", ":")` で直列化した UTF-8 の SHA-256 とする。

  ```json
  {"fn": "<関数名>", "arrays": {"<引数名>": "<配列ダイジェスト>"}, "detector": <detector.model_dump(mode="json")>, "options": {"detection_max_side": <int|null>}}
  ```

- 配列ダイジェストは、`dtype.str`、`shape`、C 順のバイト列を連結した SHA-256。`detect_compartments` の `channels` は `channels.dapi`、`channels.ncl` として、`nuclei` も含める。
- 出力先・実行ファイル・一時ディレクトリなど、実行ごとに変わる引数はキーに含めない。
- 記録は `recordings/index.json`（キー → `fn`、出力配列のファイル名、`engine_info`、出力ディレクトリに書かれたファイルの一覧）と `.npy`・付随ファイルで構成する。再生時は出力ディレクトリのファイルも復元する。
- 記録にないキーは、エラーコード `showcase_detection_not_recorded` で失敗させる。UI はこれをエラーではなく案内として表示する。

### 配信するファイル

`apps/web/public/showcase/` に置き、`manifest.json` に全ファイルの SHA-256、データセットの出典・ライセンス、生成したコミットと実行環境を記録します。

| パス | 内容 |
|---|---|
| `seed.zip` | データディレクトリ（`cytellect.sqlite`、`workspaces/` ほか。`tmp/` と再生成できる重複を除く）、`recordings/`、`proposals.json`、`showcase.json`（`workspace_id`、所有者 `owner`、`regenerate`。ビルド時のセッションは削除済みで、実行時はこの `owner` のセッションを作成する） |
| `snapshot/dataset.json` | データセットの題名、出典、ライセンス、帰属表示、加工内容、注意事項（UI が表示する） |
| `snapshot/index.json` | `{"version": 1, "entries": {"GET <パスとクエリ>": {"status": 200, "headers": [[...]], "file": "<ファイル名>"}}}` |
| `runtime/` | 自前のホイールと純 Python の依存。Pyodide 本体と同梱パッケージは、版を固定した CDN から読み込む |

`apps/web/src/lib/showcase/runtime-config.json` に、Pyodide の版と読み込み元、読み込むパッケージ、ホイールの一覧を記録します。

## 検証

- 受入テストは、画像の追加以外の全機能を自動操作し、エラー表示が 0 件であること、`/v1` やローカルへの外部通信がないことを確認する。
- ブラウザ内の計算結果（測定値・統計・図の元データ）を、同じ操作のサーバー出力と照合する。許容誤差を超えた操作は、記録の再生に切り替える。
- デモの数値は公開画像の例示であり、研究室の実画像での科学的な妥当性を示すものではない。
