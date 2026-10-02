# Cloud 実装検証記録 — 2026-10-02

> これは初期Cloud実装時点の履歴です。以下の未実装項目・6件のテスト結果は当時の記録であり、現在の実装状況を示しません。現在の状況は[ロードマップ](roadmap.md)、[検証の区分](validation.md)、[Cloud引き継ぎ](cloud-handoff.md)と各リリースの検証記録を参照してください。非公開実画像によるM4と研究者によるM5は、現在も別途の受入条件です。

## 目的と変更範囲

公開可能な合成データだけを用い、入口の停止要因と「API で解析を投入し、独立 worker が結果を確定する」最小縦断経路を実装した。これは M0–M3 の完了報告でも、研究用途の妥当性確認でもない。

実装した範囲:

- `serve` を Uvicorn の application factory として起動するよう修正。
- 実行時データ領域 `CYTELLECT_DATA_DIR` を明示必須化し、checkout 内を引き続き拒否。
- lease/fencing 付き job claim/finish を使う単一 worker、合成 truth mask の測定、統計図生成、raw を含めない replay ZIP、期限切れ workspace のファイル削除。
- native 測定における符号付き背景補正、epsilon を使わない比、API の CSRF/Origin と workspace 所有権、worker 縦断、期限切れ削除の自動テスト。
- 合成 TIFF についても workspace 使用量を加算。

## 科学的影響

測定式、閾値、recipe version は変更していない。合成画像の初期 mask は、検出性能を装うことを避けるため `synthetic-truth` と provenance に明記する。実画像について Fiji が未設定なら `fiji_not_configured`、設定されていても adapter が未導入なら `fiji_adapter_not_installed` として field failure にする。Python detector への暗黙 fallback は行わない。

核 mask の変更は従属 nucleoli を無効化し、revision report に field を記録するため、再 segmentation/review なしでは review API を通過しない。

## 実行した検証

- `uv run ruff check .`: pass。
- `uv run pytest -q`: 6 tests pass（FastAPI TestClient の upstream deprecation warning 1 件）。

## 未検証・制約

- Fiji/Java/StarDist/CSBDeep/MorphoLibJ、model weights はこの環境に存在せず、ネットワークも無効なため、取得・hash/license 確認・headless 実行をしていない。M0 は未完了。
- Web/pnpm package は未実装のため `pnpm check`、`pnpm test`、browser E2E、スクリーンショットを実行していない。M2 は未完了。
- export は measurement JSON、revision、provenance、canonical mask を再生用 ZIP に格納する最小実装である。Fiji ROI round-trip、numeric CSV import、感度分析、完全な Methods、別環境 replay は未実装。M3 は未完了。
- process-tree の強制停止、heartbeat thread、Alembic migration、upload 中断回復、quota の全 race、実画像 partial-failure UI は未検証。
- private data、研究画像、旧法参照値、研究者評価は使用していない。M4/M5 は未着手のまま。

## セットアップ follow-up

ネットワーク利用可能な管理環境で、再配布条件を確認した固定 Fiji bundle と weights を build 時に取得し、URL、SHA-256、license を記録する。その後、合成 TIFF に対する実 Fiji integration test を追加し、runtime download を禁止した状態で clean checkout から再現すること。Web の Node 24/pnpm lock と日本語 editor は別途実装が必要。
