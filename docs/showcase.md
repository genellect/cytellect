# 公開デモ（サーバーレスのショーケース）

公開サイトの `/demo` は、本番と同じ解析ワークスペース（`ConnectedWorkspace`）を、解析サーバーなしで動かします。画像の追加を除く現行機能を、本番と同じ UI でエラーなく再現することが目標です。研究画像は扱わず、出典と利用条件を確認した公開画像だけを使います。

## 構成

```
本番の API とワーカー（実際の Fiji/StarDist・Cellpose）で公開画像を処理する
  └─ 検出の記録・初期状態（SQLite と全ファイル）・初期表示の GET 応答を書き出す（ビルド時、CPython）
        │
        ├─ ① 応答の再生：全視野・全領域・全チャンネルの表示（GET）と、案内の操作を②で実行した記録を返す。
        │     公開デモの訪問者に返すのはこの記録だけで、どの端末でも待たずに動く
        └─ ② ブラウザ内の API：同じ初期状態から、Pyodide 上で実際の API・ワーカー・解析パッケージを動かす（ビルド時の記録用）
              検出だけは記録を返し、測定・統計・作図・保存は同じ Python 実装が計算する
```

- 訪問者の操作には、どの端末でも①だけが答える。②は訪問者の端末では起動せず（取得もしない）、ビルド時に操作を記録するときだけ動かす。記録にない操作（輪郭の手修正、記録にない設定での測定など）には、待たせずにその場で案内を表示する。
- 検出（StarDist/Fiji、Cellpose）はブラウザで実行しない。記録した条件以外の検出は行わない。検出の設定欄は入力欄を出さず、採用した結果の記録した条件を文字で示す。
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
| `snapshot/dataset.json` | データセットの題名、出典、ライセンス、帰属表示、加工内容、注意事項（UI が表示する）。複数場面のデモでは最初の場面の内容 |
| `snapshot/scenes.json` | 場面の一覧 `{"version": 1, "scenes": [...]}`。各場面は `id`、`label`（場面の切り替えに出す名前）、`workspaceId`、`dataset.json` と同じ出典の項目、`regions`、`examples`（AI の指示の例）、`assistantScope`（記録にない指示への返答の文） |
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
- 核・核小体・核質ごとの統計：画面が選ばせる指標・染色・解析・相関の横軸のすべての組み合わせと、その図の幅（1 段・2 段）とレイアウトのすべて
- 保存した図の、幅とレイアウトのすべて
- 視野ごとの測定と、全視野の測定。続けて先頭の視野の核に戻り、測定した結果の統計（分布・群間比較）と図
- AI の指示の例（候補の採用まで）と、その後に画面が選ばせる解析のすべて
- 2 枚目以降の各視野を表示した状態での AI の指示の例（例は表示中の視野の核を検出候補として示す）
- AI の指示の例を採用した後の、核・核小体・核質それぞれの視野ごとの測定と全視野の測定（例の設定は初期状態と同じ検出・測定を別の形で書いたもので、その設定のもとで記録する）
- 順位に基づく手法（Mann–Whitney U、Spearman など）を選ぶ AI の指示の例を採用した後の、核・核小体・核質ごとの群間比較と相関のすべてと、その図（手法は続けて行う統計にも引き継がれるため。分布は手法を使わない）

場面はどれも初期状態から始まり、互いに独立しているので、3 場面ずつ並行して記録する。記録は 1 場面終わるごとに進捗を 1 行ずつ構築のログへ出す。最初のデモの場面は、訪問者と同じく `?id=` なしの `/demo` で初期状態を記録する（ワークスペースの一覧を含めるため）。記録には、再生が答えに使う取得（変更と変更の間で、パスごとの最後の取得）だけを残す。変更の本文では、訪問ごとに変わる値（要求 ID、文書の版、集合の作成時に前提とする採用中の解析版 `expected_active_revision_id`）と、記録中に API が生成した ID を `*` にする（集合の内容は、元の解析版・実験情報・採用状態で決まる）。作り直しの最後に、初期状態と今回の記録のどちらも参照しないファイル（前回の記録の残り）を公開ディレクトリから消す。図の描画結果（`GET /v1/jobs/<id>/figure-render`）は、画面が使う `source_job_id` と `figure` だけを残す（残りは統計の結果と同じ内容）。

データセットは `services/showcase/datasets/<id>.json`（`cytellect-showcase-dataset/1`）で指定します。ビルドに複数のファイルを渡すと、1 ファイルが 1 場面（同じ所有者の別のワークスペース）になり、最初のファイルの場面でデモが開きます（最後に作るので最新のワークスペースになる）。画面は `?id=<ワークスペース>` で場面を開き、ヘッダーの「場面」で切り替えます（ページを読み込み直すので、場面どうしの状態は混ざらない）。現在の公開デモは次の 2 場面です。

- `cpg0016-jump-source13-plk1.json`（核数）：JUMP Cell Painting、CC0。U2OS の PLK1 ノックアウトと non-targeting の対照、実験回 3、DNA のチャンネルだけ。JUMP が公開した CellProfiler の核との照合の表示は、2026-10-26 に外した（`presentation_amendment`）。
- `zenodo-6643470-nucleolar.json`（核小体）：Zenodo 6643470（DS6a）、U2OS の未処理と ActD 1 µM、Hoechst・NPM1・5-EU。核小体の大きさ・形と 5-EU を比べる。

視野・ウェル・チャンネル・比較の計画は、測定の前にこのファイルでコミットして固定します。群間比較デモに使う項目は次のとおりです。

- `experiment`：研究者が「実験」で入力する実験の形（群・対照・実験回・独立性の確認と根拠）。初期状態の解析設定に保存し、視野の群・独立実験単位・対応ペア・撮影日はこの形から決まる。宣言した 2 群の比較は、処理 − 対照の推定値（comparison-estimates/1.0.0）と、実験回ごとの図（superplot）で計算する。
- `scenario.nucleoli`：`false` のデータでは核小体・核質を検出せず、画面もその領域と指標を出さない（`snapshot/dataset.json` の `regions`）。
- `scenario.companions`：出典が報告し、測定の前に計画に記録した、ほかの変化の比較（DS6a では核小体の離心率）。最初の解析の前に保存し、統計の「保存した比較」で最初の比較と切り替えられる。
- `scenario.direction_checks`：場面の文が述べる、記録した各比較の向き（実験回ごとの差がすべて出典の向きか）。構築は保存した結果と照合し、文と結果が食い違えば止める（目標 C7）。
- `scenario.comparison_layouts`：群間比較で、保存した図に加える図の種類。比較を描いた種類（宣言した 2 群では実験回ごとの superplot）は最後に描き直すので、統計の画面はその図で開く。
- `scenario.opening`：最後に計算する解析。公開デモは、開いたときにこの結果（既定は分布）を表示する。群間比較を指定すると、「統計」を開いたときに結果の文と図が出る。画像の画面は、2 画面の画像・輪郭・各群の測定値だけを出す。
- `scenario.final_target`：画像の画面が開く領域（既定は核）。最初の比較が測る領域にそろえ、比べている輪郭と測定値で開く（DS6a は核小体。核の輪郭は位置の手がかりとして薄く重ねる。本番も同じ）。`snapshot/scenes.json` の `target`。統計を初めて開くと、設定欄の領域・指標・チャンネルを表示中の結果にそろえる。
- `crop_rule`：視野の切り出し位置の規則。`nuclear-window` は、核染色だけを読み、Otsu の閾値を超える画素が最も多い窓（`size`、`step` 画素の格子、同点は中央に近い窓）を選ぶ。測定するチャンネルは読まないので、切り出しが結果に合わせて動くことはない。全チャンネルで同じ窓を使い、画素値は変えない。
- `scene_label`・`assistant_scope`：場面の名前と、記録にない AI の指示への返答で、その画像で比べられることを示す文。
- `dataset.reported_change`：出典が報告している変化（比べる条件・向き・量・範囲・実験回の独立性）。画面は、デモでの測定と分けて、結果のまとめの下に向きを 1 行で示し、量・範囲・独立性は折りたたむ（`snapshot/dataset.json` の `reportedChange`）。
- Cellpose を使わないデータセット（NCL 陽性の核小体や細胞 ROI がない）では、Cellpose の実行環境は不要。

初期状態（`scenario` 段階）は次のとおり作る。

- 背景補正は自動推定で測定し、補正前・補正後のすべての指標を使えるようにする。
- 核小体を確定できない核は、核から消さずに欠測として残す（要件 Q-05、方針 `unresolved-as-missing/1.0.0`）。核小体・核質の統計では、画面と同じく、各視野の一覧（`compartment-ledger`）を読み、確定できない核があればその一覧を確認として送って計算する。結果は群・実験回ごとの核の総数と欠測の数を持つ。スナップショットは、統計の画面がどの領域でも一覧を読めるよう、表示する核小体・核質の版ごとに一覧を記録する。
- `scenario.fragment_review` を指定した場面（以前の公開デモ `zenodo-6643470.json`）だけは、以前の規則のまま、視野の核の面積の中央値の `max_area_fraction` 倍より小さい未確定の物体（核の断片）を「選択領域を削除」と同じ `region-edits` で核から削除し、核小体・核質を求め直す。ほかに未確定の核があれば作り直しを止め、削除した物体は `manifest.json`（`scenario.fragment_review`）に残す。DS6a は 2026-10-26 にこの規則をやめた（`derivation_amendment`）。

### 測定値（Node 24、このリポジトリの開発環境）

現在のデモは 2 場面（JUMP：1280×1080 uint16 の 1 チャンネル × 18 視野、DS6a：640×640 uint16 の 3 チャンネル × 18 視野）です。下の値は以前のデモ（1536×1536 の 2 チャンネル × 6 視野）で測ったもので、現在の場面では測り直していません。

- 取得量: Pyodide 本体 13.4 MB、パッケージ 56.3 MB、`runtime/` 7.4 MB（フォント 5.8 MB を含む）、計約 77 MB（圧縮前）。
- 時間: Pyodide の起動とパッケージの読み込み約 13 秒（キャッシュあり）、`boot` 約 20–25 秒。
- メモリ: 以前の公開デモ（Zenodo 6643470）と同じ大きさ（1536×1536 uint16 の 2 チャンネル × 6 視野、展開後のデータ約 170 MB）で、領域の削除・コホート・記述統計・共通統計・出力・図の再描画・論文用パッケージまで実行した後の WebAssembly ヒープが約 410 MB、Node のプロセス全体が約 1.6 GB。一連の操作は約 40 秒。

### 既知の制約

- ブラウザのメインスレッドではなく Web Worker で動かす前提です。ジョブの計算中は、その Worker は次の要求に応答しません。
- ジョブの取り消しは、実行中の計算を止めません（公開されないだけです）。

## 検証

- 受入テストは、画像の追加以外の全機能を自動操作し、エラー表示が 0 件であること、`/v1` やローカルへの外部通信がないことを確認する。
- 記録に使うブラウザ内の計算結果（測定値・統計・図の元データ）を、同じ操作のサーバー出力と照合する。
- デモの数値は公開画像の例示であり、研究室の実画像での科学的な妥当性を示すものではない。

## ブラウザ側の実装（`apps/web/src/lib/showcase/`）

契約の節を補足する、Web 側の実装の詳細です。

- 本番と同じ画面：画像・フォルダのドロップ（本番は「画像」「フォルダ」と同じ取り込み、デモは追加できない案内）、重ねて表示（チャンネルが 2 つ以上なら色の合成で開き、核染色は青、ほかの染色はそれぞれ別の色。1 つの染色を選ぶとその染色だけ）、核小体・核質で採用した核の輪郭を薄く重ねる表示と、マーカーで開く初期チャンネル、2 画面の各画像の輪郭の修正の道具、AI の入力欄を押すと AI のパネルが開く動作、`?step=image|statistics|figure` のタブ指定、統計・グラフを開いたときの最新の保存結果、統計の「保存した比較」の切り替え。デモだけのもの：関門のない入口、デモのバッジ・出典・ダウンロード、場面の切り替え、追加できない案内、AI の指示の例、記録した検出条件の文字での表示、統計・図の入力の固定（下記）。
- 公開ビルド（API 未設定）の `/demo` だけが `activateShowcase()` で切り替えを有効にし、`lib/api.ts` の `request`・`fetchPrivateResponse`（`download`・`fetchBlob` を含む）がこの経路を使う。API を設定したビルドとローカル版の通信は変わらない。`/workspace` は公開ビルドでは `/demo` へ転送する。
- 最初の表示：`index.json` が届いた時点で、ワークスペースの記録（セッション、視野一覧、解析版、採用状態、染色設定、解析設定など）と、先頭の視野のプレビュー・輪郭・測定値をまとめて並行して取得する。ワークスペースは先頭の視野を表示してから、残りの視野を読み込む（公開デモに限らず、本番の画面も同じ）。案内は自動では開かず、「使い方」から開く。スマートフォンでは、「使い方」と「ダウンロード」を「デモ」のメニューから開く。
- 記録の再生：`GET <パスとクエリ>` が `snapshot/index.json` にあれば、その本文を返す。`snapshot` 段階は、全視野 × 領域（核・核小体・核質）× チャンネルの表示と、統計・グラフ・保存した図を開いて記録する。保存した各結果について、図の点から元の視野へ戻るときに読むもの（結果の解析版の記録、各視野が固定した解析版の記録・測定値・輪郭）も記録する（結果からいつでも元の画像に戻れる）。
- 読み込みの順：2 群の設計では、解析設定から最初の実験回の各群の 1 視野目を知り、その 2 視野を同時に先に読む。残りの視野は 2 画面の表示の後に読み、読み込み済みの表示用画像は取り直さない（本番と同じ。N-03）。記録の再生は、要求の順に答えを決めるが、記録ファイルの取得は並行させる（2 枚の画像が 1 枚ずつ届かない）。ワークスペースの解析設定が読まれた時点で、そのワークスペースが最初に見せる視野（2 画面なら 2 視野、それ以外は 1 視野目）の画像・輪郭・測定値を先読みする。`snapshot/journal.json` は最初の表示の 6 秒後に読み、変更の要求が先に来ればそのときに読む。
- 操作の記録の再生：`snapshot/journal.json` が変更の要求に答える。まず前回答えた位置より後で、一致する記録を探す。見つからなければ先頭から探す（場面はどれも初期状態から始まるため）。測定の実行は、記録の直前にその場面で保存した解析設定（なければ初期状態の設定）と、要求の設定が一致するときだけ答える。統計の要求（解析版の `review`・`descriptive`・`common-statistics`）は、要求の本文が何を計算するかを表すので、パスが一致する記録がないときは、解析版 ID だけが異なる記録（同じ内容の別の解析版）で答え、その場面の答えに含まれる解析版 ID を訪問者のものに置き換えて返す。以後の要求も同じ対応で記録を探す（同じ内容の訪問者の解析版が複数あるときは、要求が名指した解析版で答える）。図の描画と論文用パッケージ、測定の受け入れは、その結果自身の記録でだけ答える。採用状態の保存（`POST selection`）は、各視野がすでに採用済みの解析版のあいだで表示を切り替えるだけの場合、端末が API と同じ規則で先に答えて保持し（次に記録の変更で答えるまで、それより前の記録の取得より優先する）、決められないときだけ記録を探す（採用状態は表示の記録で、測定値や統計ではない）。それ以外は案内を返す。答えた後の GET には、同じ場面で次の変更までに記録した最後の応答（落ち着いた状態）を返す（場面の最後の変更の後に、次の場面の最初の取得を使わない）。ただし、その変更の前後で記録上の応答が変わっていない GET には、この端末に前回返した応答を返す（変更の前の状態は、その場面の直前の取得か、文書そのものを返した書き込み）（訪問者の前の操作が別の場面の記録で答えられていても、表示がその場面の初期状態に戻らない）。書き込んだパスの GET は、その変更の後に記録した応答（次の変更までになければ、同じ場面で次に記録した応答）を返す。保存する解析設定は端末側で保持し、版を 1 つ進めて返す。ワークスペースの処理一覧（`GET /v1/workspaces/<id>/jobs`）には、この端末に以前の一覧で示した処理も残して返す（API は処理を消さず、画面は同じ解析版の集合など、以前に受け付けた処理を再利用する。別の場面の記録の一覧には、訪問者の前の場面の処理が含まれないため）。
- 記録の範囲に揃えた画面：公開デモでは、記録できない自由入力（統計の方法・対応・比較する群・独立実験単位、図の寸法・文字・凡例・ラベル・軸・色・点の大きさ、元画像を含める）と、検出条件・核染色・背景補正を記録した値に固定し、そのことを画面に示す。データにない細胞 ROI と GFP は表示しない。計算は既定の図（2 段幅・点と分布）で行い、先に別の幅を選んでいれば記録した図で描き直す。論文用パッケージを記録していない結果の「保存」は、表示している図（SVG）を保存する。
- 記録にない操作：どの端末でも、その場で `showcase_action_not_recorded`（409）を返す。ブラウザ内の API は起動しない。
- 記録用の経路：ビルド時の記録（`journal.mjs`）は `window.__cytellectShowcaseRecord` を設定してページを開く。このときだけ、初期表示の GET を記録から返し、それ以外の要求をブラウザ内の API へ送る（発行順に 1 件ずつ）。API の Worker は `seed.zip` を先に取得し、`runtime/` の各ファイルを `runtime-config.json` の SHA-256 と照合してから導入する（URL に `?sha256=` を付け、長期キャッシュでも別ビルドの内容を使わない）。Pyodide 本体は `indexURL` の `pyodide.mjs` から読み込む。ホイールは site-packages に展開し、フォントは `/showcase/fonts/`（`runtime.DEFAULT_FONT_DIR`、Node の検証ハーネスと同じ場所）に置き、`boot` の `font_dir` で渡す。
- 案内として表示するコード：`showcase_detection_not_recorded`、`showcase_proposal_not_recorded`、`showcase_upload_disabled`、`showcase_engine_unavailable`（記録用の API が起動に失敗した）、`showcase_unavailable`（記録が公開されていない）、`showcase_action_not_recorded`（操作の記録にない）。`role="alert"` ではなく情報表示にし、再読み込みではなく「閉じる」で消せる。
- 任意のファイル（なければ本番と同じ表示）：`snapshot/proposal-examples.json` は AI の指示の例、`snapshot/dataset.json`（`title`、`attribution`、`licence`、`licenceUrl`、`sourceUrl`、`caveats`）はデモ表示と案内の最後の手順に出典として表示する。`snapshot/recorded-options.json` は、ビルドが記録した検出条件の格子（キーは検出器の `engine`、その中のキーは検出器の項目名。核の `detection_max_side_px` も `fiji-stardist-2d` に含める）で、画面は読まない（検出の設定欄は、採用した結果の記録した条件を文字で示す）。
- 初回表示：読み込み中は画像追加の画面ではなく読み込み中の案内を出す。統計とグラフは、計算前でも保存済みの最新の結果（シナリオの最後の計算）を開く（本番も同じで、そのワークスペースで最後に保存した結果を開く）。
- HTTP ヘッダー：公開ビルドの CSP は `'wasm-unsafe-eval'`、`indexURL` のオリジン（script-src・connect-src）、`worker-src 'self' blob:` を加える。`/showcase/runtime/*` と、内容の SHA-256 で名付けた記録ファイル（`snapshot/<24 桁の 16 進>.<拡張子>`）は長期・immutable、`seed.zip`・`manifest.json` とそれ以外の `snapshot/*`（`index.json`・`journal.json`・`scenes.json` など）は毎回再検証、それ以外は従来どおり `no-store`。
- 開発用：`scripts/dev_showcase_backend.py` は同じ boot/handle の契約を CPython の API で提供する（検出はしきい値による代用で、結果は公開しない）。`NEXT_PUBLIC_SHOWCASE_DEV_BACKEND`（ループバックのみ）を付けたビルドでだけ使う。
- `.gitignore` は `*.zip` を除外しているため、`seed.zip` を登録する変更では除外の例外を加える。
