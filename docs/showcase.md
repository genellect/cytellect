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
- 有料サービス（LLM）は呼ばない。AI の提案は、記録したモデル出力か、指示の例ごとにデモ用に用意した設定案（`showcase-authored`）だけを返す。

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
| `snapshot/journal.json` | 案内の操作を、公開した初期状態からブラウザ内の API で順に実行した記録。`{"version": 1, "entries": [{"method", "path", "body", "status", "headers", "file"}]}`。変更の要求の `body` では、来訪ごとに変わる値（`request_id`・`version`・`spec_version` と、記録中に API が作った識別子＝初期状態のスナップショットにない UUID）を `"*"` にする。保存する解析設定（`PUT analysis-spec`）は記録しない |
| `runtime/` | 自前のホイールと純 Python の依存。Pyodide 本体と同梱パッケージは、版を固定した CDN から読み込む |

`apps/web/src/lib/showcase/runtime-config.json` に、Pyodide の版と読み込み元、読み込むパッケージ、ホイールの一覧を記録します。

## 実行環境

ブラウザ内の API（②）は Pyodide 314.0.7（CPython 3.14.2、Emscripten 5.0.3）で動かします。`requires-python`（3.12・3.14、3.13 を除く）を満たし、同梱の数値計算パッケージが uv.lock に最も近い版です。0.27 系（Python 3.12）は NumPy 2.0・Matplotlib 3.8・SciPy 1.14 と古く、0.28・0.29 系は Python 3.13 です。

### 読み込みの手順

Web Worker は次の順に読み込みます。Node のハーネス（`services/showcase/pyodide/harness.mjs`）も同じ順で実行します。

1. `runtime-config.json` の `indexURL` から `loadPyodide`。`packages` を `pyodide.loadPackage` で読み込む（依存は Pyodide が解決する）。
2. `wheels` を記載順に `/showcase/runtime/<file>` から取得し、SHA-256 を照合してから `pyodide.unpackArchive(bytes, "wheel", {extractDir: <site-packages>})` で展開する。手順 1 の後に展開するため、`typing_extensions` は uv.lock の版で上書きされる。micropip は使わない。
3. `fonts` を同様に照合し、`/showcase/fonts/<file>` に書き込む。`importlib.invalidate_caches()` を呼ぶ。
4. `cytellect_showcase.runtime` の `boot(seed, location.origin)` を呼び、以後は `handle(method, url, headers, body)` を呼ぶ。`headers` は `[[name, value], ...]`、`body` は `Uint8Array` か `undefined`。戻り値は `toJs({dict_converter: Object.fromEntries})` で変換し、`destroy()` する。`body` は `Uint8Array` になる。

### `boot` と `handle` の動作

- シードの zip は、ルートがデータディレクトリです（`cytellect.sqlite`、`workspaces/`、`recordings/`、`proposals.json`、`showcase.json`）。絶対パス・`..`・1 GiB 超は拒否し、`tmp/` は展開しません。
- `boot` は展開 → `cytellect_showcase.seed.restore(data_dir)`（モジュールがあれば）→ 検出の再生 → `create_app` の順に実行します。検出関数は、まず `showcase_detection_not_recorded` で失敗する関数に置き換え、その後に `detections.install_replay(<data>/recordings)` を呼びます。実際の Fiji・Cellpose は実行されません。`showcase_detection_not_recorded` は、このプロセス内でだけ視野の失敗理由の許可リストに加えます。
- セッションは `showcase.json` の `owner`（無ければシード内のワークスペースの所有者）に対して直接作成し、Cookie は `handle` が付けます。応答の `Set-Cookie` は返しません。ログアウト後や期限切れの後は、次の要求で作り直します。`Origin` は `boot` に渡した origin、`Host` はその host に固定します。CSRF 用の `X-Cytellect-Request: 1` は呼び出し側が付けます（本番と同じ）。
- ワークスペースの保持期限は起動時に 10 年先へ更新します。
- 変更系の要求の後、応答を返してから、ワーカーと同じ手順（`cleanup`、`advance_workspace_runs`、`Store.claim`）で待機中のジョブを同じプロセスで実行します。ハンドラーは `cytellect_worker.child` と同じ許可リスト、出力先は `runs/<lease>/output`、公開は `Store.finish` です。並行の heartbeat ができないため、実行前にリースを `job_timeout_seconds` まで延長します。未知の例外は `analysis_failed` として記録し、メッセージは保存しません。要求とジョブの実行は 1 つのロックで直列化するので、次の要求（UI のジョブ確認）は完了後の状態を返します。
- 提案は `cytellect_api.proposals.request_draft` を `proposals.json` の参照に置き換えます。形式は `{"version": 1, "entries": {"<context_sha256>": {"model", "prompt_version", "draft"}}}`（提案サービスの応答そのもの）で、`{}` は記録なしです。`source` が `showcase-authored` の行（指示の例に対してデモ用に用意した案。案は指示だけで決まる）は、来訪者が先に設定を変えて文脈が一致しない場合も、同じ指示（前後の空白を除く）なら、現在の文脈で `validate_draft` に通る案を返します。モデル出力の行は、記録した文脈と完全に一致した場合だけ返します。どちらにも当たらない文脈は 409 `showcase_proposal_not_recorded` を返し、失敗した下書きの行を消すので、同じ依頼を繰り返しても同じ案内になります。返した下書きは本番と同じ `validate_draft` で検証します。設定の `proposal_url` は `https://proposals.showcase.invalid` で、接続はしません。
- Pyodide にはスレッドと子プロセスがありません。`anyio.to_thread.run_sync` は要求の間だけ同じスレッドで実行し、`psutil` が無い場合は読み込み用の空のモジュールを置きます（使用すると失敗します）。

### 本番コードの変更

`cytellect_api.config` は、モジュールから 4 階層上をチェックアウトとみなし、その中のデータディレクトリを拒否します。Pyodide の `/lib/python3.14/site-packages` では 4 階層上がファイルシステムのルートになり、すべてのパスが拒否されました。ルートに `pyproject.toml` が無い場合だけチェックアウトではないと判定します。実際のチェックアウトとルートに置いたチェックアウトの保護は変わりません（`tests/test_showcase_runtime.py`）。

### 版と uv.lock との差

Pyodide の CDN から読み込むパッケージ（再配布しない）:

| パッケージ | Pyodide 314.0.7 | uv.lock |
|---|---|---|
| numpy | 2.4.6 | 2.5.3 |
| scipy | 1.18.0 | 1.18.1 |
| pandas | 3.0.2 | 2.3.3（pyproject は `<3`） |
| scikit-image | 0.26.0 | 0.26.0 |
| statsmodels | 0.14.6 | 0.15.0 |
| matplotlib | 3.10.8 | 3.11.2 |
| pydantic / pydantic-core | 2.12.5 / 2.41.5 | 2.13.5 / 2.46.5 |
| sqlalchemy | 2.0.48 | 2.1.2 |
| pillow | 12.2.0 | 12.3.0 |
| typing-inspection, patsy, contourpy, fonttools ほか | Pyodide の版 | — |

`runtime/` に置く純 Python のホイールは、uv.lock と同じ版・同じ SHA-256 です: typing-extensions 4.16.0、idna 3.20、anyio 4.15.1、starlette 1.7.0、annotated-doc 0.0.5、opentelemetry-api 1.45.0（fastapi が読み込む）、fastapi 0.142.2、python-multipart 0.0.32、mako 1.4.3、alembic 1.20.0、tifffile 2026.9.20、roifile 2026.9.22、defusedxml 0.7.1。psutil、uvicorn、imagecodecs は含めません（画像の追加をしないため、圧縮 TIFF の読み込みはできません）。

- Matplotlib 3.10 の SVG 出力は数値の太さ（400 など）で失敗します。3.11 と同じく数値をそのまま使うよう、ブラウザ内でだけ `font_manager.weight_dict` に 0–1000 の数値を加えます。
- 日本語の図は Noto Sans JP（公式の可変フォント、SHA-256 `c2f3b4d4…fc68f`、OFL-1.1）を fontTools で太さ 400 の静的フォントにしたもの（`NotoSansJP-Regular.ttf`）を使います。サーバーは Noto Sans CJK JP なので、図の font の記録と文字の配置は異なります。英語の図はどちらも DejaVu Sans です。
- 論文用パッケージの作成時は、解析版のすべての統計結果をブラウザ内で計算し直し、保存した結果と完全に一致することを確かめます。CPython で作った初期状態の結果は、記録する `scipy_version` と、一部の浮動小数点数の最後の桁（相関係数で 1e-16 程度）がブラウザ内と異なります。この食い違いのため、以前は初期状態の解析版で ZIP を保存すると `region_export_statistics_source_mismatch` で失敗していました。そこで、ビルドの `publish` 段階では、書き出した `seed.zip` を Pyodide のハーネスで起動し、保存済みの統計と図をブラウザ内で計算し直したもの（`cytellect_showcase.rederive`）に置き換えてから、もう一度書き出します。計算し直した値が、相対誤差 1e-9（絶対誤差 1e-12）を超えて変わった場合、または版の文字列以外の項目が変わった場合は、ビルドを止めます。図の描き方の記録（`figure`。使ったフォントなど）は照合せず、描き直した図と一緒に置き換えます。ブラウザ内と CPython とで、測定値・統計・図の元データが一致することは、`tests/test_showcase_runtime.py` が同じ要求をハーネスと CPython で実行して、相対誤差 1e-9 で照合しています（公開画像 BBBC013 の切り出し 4 視野、試験用の閾値検出）。

### ビルドと検査

`uv run python scripts/build_showcase_runtime.py --cache <チェックアウト外>` が、Cytellect のホイール（`SOURCE_DATE_EPOCH` 固定で再現可能）、上記のホイール、フォント、`THIRD_PARTY_NOTICES.txt`、`runtime-config.json`、`fixtures/public/allowlist.json` の登録を書き出し、`manifest.json` の `files` のうち `runtime/` の項目と、作り直しに使ったコミット（`runtime_generated_from_commit`）を更新します。`generated_from_commit` は初期状態と記録を作ったコミットです。Python のソースを変えたら作り直します。`--check` は作り直した結果と、コミット済みのファイル・設定・登録・`manifest.json` の一覧を照合し、古い場合は失敗します。

公開デモの作り直し（`services/showcase/src/cytellect_showcase/build.py`）は、`publish` → `snapshot` → `journal` の順に実行します。`journal` は、公開ビルドと同じ `/demo` をブラウザ内の API で開き、次の操作を初期状態から 1 場面ずつ実行して記録します。警告や想定外のエラーが 1 件でも出れば失敗します。

- 案内どおりの統計・図・ZIP 保存
- 核・核小体・核質ごとの統計（指標と解析の組み合わせ、図の種類と幅）
- 視野ごとの測定と、全視野の測定
- AI の指示の例

### 測定値（Node 24、このリポジトリの開発環境）

- 取得量: Pyodide 本体 13.4 MB、パッケージ 56.3 MB、`runtime/` 7.4 MB（フォント 5.8 MB を含む）、計約 77 MB（圧縮前）。
- 時間: Pyodide の起動とパッケージの読み込み約 13 秒（キャッシュあり）、`boot` 約 20–25 秒。
- メモリ: 本番の公開デモと同じ大きさ（1536×1536 uint16 の 2 チャンネル × 6 視野、展開後のデータ約 170 MB）で、領域の削除・コホート・記述統計・共通統計・出力・図の再描画・論文用パッケージまで実行した後の WebAssembly ヒープが約 410 MB、Node のプロセス全体が約 1.6 GB。一連の操作は約 40 秒。

### 既知の制約

- ブラウザのメインスレッドではなく Web Worker で動かす前提です。ジョブの計算中は、その Worker は次の要求に応答しません。
- ジョブの取り消しは、実行中の計算を止めません（公開されないだけです）。

## 検証

- 受入テストは、画像の追加以外の全機能を自動操作し、エラー表示が 0 件であること、`/v1` やローカルへの外部通信がないことを確認する。
- ブラウザ内の計算結果（測定値・統計・図の元データ）を、同じ操作のサーバー出力と照合する。許容誤差を超えた操作は、記録の再生に切り替える。
- デモの数値は公開画像の例示であり、研究室の実画像での科学的な妥当性を示すものではない。

## ブラウザ側の実装（`apps/web/src/lib/showcase/`）

契約の節を補足する、Web 側の実装の詳細です。

- 公開ビルド（API 未設定）の `/demo` だけが `activateShowcase()` で切り替えを有効にし、`lib/api.ts` の `request`・`fetchPrivateResponse`（`download`・`fetchBlob` を含む）がこの経路を使う。API を設定したビルドとローカル版の通信は変わらない。`/workspace` は公開ビルドでは `/demo` へ転送する。
- 記録の再生：`GET <パスとクエリ>` が `snapshot/index.json` にあれば、その本文を返す。最初の変更操作より後、またはブラウザ内の API が起動した後は、すべての要求を Web Worker へ送る。記録にない GET は起動を待つ。要求は発行順に1件ずつ処理する。
- 操作の記録の再生：API を起動しない端末（スマホ、メモリが少ない PC、起動に失敗した PC）では、`snapshot/journal.json` が変更の要求に答える。まず前回答えた位置より後で、一致する記録を探す。見つからなければ先頭から探す（場面はどれも初期状態から始まるため）。答えた後の GET には、記録上でその変更の後に API が返した応答を順に返す（ジョブの進行も記録どおり）。保存する解析設定は端末側で保持し、版を 1 つ進めて返す。記録にない変更には `showcase_action_not_recorded`（409）を返す。記録を使い始めた後は、Worker の API を使わない。API を起動する PC は、記録を使わずに起動を待つ。これは、記録とその PC の API の状態が食い違わないようにするため。
- 起動：PC のブラウザ（`navigator.deviceMemory` が分かる場合は 4 以上、狭いタッチ端末を除く）では、初回表示の後に Worker を起動する。Worker は `seed.zip` を先に取得し、`runtime/` の各ファイルを `runtime-config.json` の SHA-256 と照合してから導入する（URL に `?sha256=` を付け、長期キャッシュでも別ビルドの内容を使わない）。Pyodide 本体は `indexURL` の `pyodide.mjs` から読み込む。ホイールは site-packages に展開し、フォントは `/showcase/fonts/`（`runtime.DEFAULT_FONT_DIR`、Node の検証ハーネスと同じ場所）に置き、`boot` の `font_dir` で渡す。
- 案内として表示するコード：`showcase_detection_not_recorded`、`showcase_proposal_not_recorded`、`showcase_upload_disabled`、`showcase_engine_unavailable`（端末で起動しない・起動に失敗した）、`showcase_unavailable`（記録やランタイムが公開されていない）、`showcase_action_not_recorded`（操作の記録にない設定）。`role="alert"` ではなく情報表示にし、再読み込みではなく「閉じる」で消せる。
- 任意のファイル（なければ本番と同じ表示）：`snapshot/recorded-options.json` のキーは検出器の `engine`（例 `fiji-stardist-2d`、`cytellect-nucleolar-v2`、`cellpose-sam`）、その中のキーは検出器の項目名で、核の `detection_max_side_px`（`null` は自動）も `fiji-stardist-2d` に含める。記載のある項目は記録した値の選択肢になり、記載のない項目は変更できない。記載のない検出器は選択肢として選べない。`snapshot/proposal-examples.json` は AI の指示の例、`snapshot/dataset.json`（`title`、`attribution`、`licence`、`licenceUrl`、`sourceUrl`、`caveats`）はデモ表示と案内の最後の手順に出典として表示する。
- 初回表示：読み込み中は画像追加の画面ではなく読み込み中の案内を出す。統計とグラフは、計算前でも保存済みの最新の結果（シナリオの最後の計算）を開く（本番は「保存した図」から選ぶまで空のまま）。
- HTTP ヘッダー：公開ビルドの CSP は `'wasm-unsafe-eval'`、`indexURL` のオリジン（script-src・connect-src）、`worker-src 'self' blob:` を加える。`/showcase/runtime/*` は長期・immutable、`seed.zip`・`manifest.json`・`snapshot/*` は毎回再検証、それ以外は従来どおり `no-store`。
- 開発用：`scripts/dev_showcase_backend.py` は同じ boot/handle の契約を CPython の API で提供する（検出はしきい値による代用で、結果は公開しない）。`NEXT_PUBLIC_SHOWCASE_DEV_BACKEND`（ループバックのみ）を付けたビルドでだけ使う。
- `.gitignore` は `*.zip` を除外しているため、`seed.zip` を登録する変更では除外の例外を加える。
