# Cytellect

**Get your microscopy publication-ready.**

[![Cytellect](docs/images/readme-hero.webp)](https://cytellect.vercel.app/)

[プロダクト LP](https://cytellect.vercel.app/) · [公開デモ](https://cytellect.vercel.app/demo) · [Windows](https://github.com/genellect/cytellect/releases/tag/v0.1.0-local.19) · [Docker](docs/docker-desktop.md) · [統計解析手法](docs/implementation-overview.ja.md#統計解析) · [ドキュメント](docs/README.md)

Cytellect は、顕微鏡画像の解析から統計処理、グラフ出力までを一貫して引き受ける生命科学研究者のための Web アプリケーションである。画像処理には学習済みの深層学習モデルである StarDist と Cellpose-SAM、数理計算処理には Python を採用している。

## 開発に参加する方へ

開発に参加するときは次の 3 つを順に読み、作業のたびに関係する節を確認する。AI エージェントも同じ文書に従う。

1. [チーム開発ルール](docs/team-development.md)：開発の進め方、Git とレビュー、研究データの扱い
2. [CONTRIBUTING](CONTRIBUTING.md)：開発環境の構築と起動、PR を出す前の検査
3. [開発の原則](docs/development-principles.md)：計算・統計・データ・画面・リリースで守る原則

そのほかの文書は[ドキュメント](docs/README.md)から探せる。

## アーキテクチャ

![Cytellect のシステム構成](docs/images/architecture.webp)

解析は研究室の PC で完結し、外部サービスには用途ごとに決めたデータだけを送る。

| 実行場所 | 役割 | 送受信するデータ |
|---|---|---|
| 研究室の PC（Windows 版・Docker 版） | ワークスペース、解析 API、計算ワーカー、研究データの保存 | — |
| Cloudflare Workers · D1 | LLM の中継、費用の予約と精算 | 指示文・現在の設定 → 構造化設定 |
| Modal（NVIDIA L4） | Cellpose-SAM の GPU 推論。使用後 20 秒で停止 | 検出用の 1 チャンネル・核マスク → ラベル画像 |
| Hugging Face | モデルの重みの配布 | 導入時に取得し、SHA-256 を照合 |
| Vercel | LP と公開デモ | 研究画像は扱わない |
| GitHub | CI、Windows 版のリリース、GPU イメージの公開 | GHCR に digest で固定 |

### ディレクトリ構成

| ディレクトリ | 内容 |
|---|---|
| [`apps/web`](apps/web) | Web ワークスペースと公開サイト（Next.js） |
| [`packages/analysis`](packages/analysis) | 検出・測定・統計・作図の共通実装 |
| [`packages/contracts`](packages/contracts) | API の型定義（OpenAPI） |
| [`services`](services) | 解析 API、計算ワーカー、LLM の中継 |
| [`engines`](engines) | Fiji と Cellpose-SAM の実行環境 |
| [`infra`](infra) | Docker の構成 |
| [`scripts`](scripts) | セットアップと検証 |
| [`tests`](tests) | 試験 |
| [`docs`](docs) | 仕様と運用の文書 |

## 解析パイプライン

![画像から論文の図まで](docs/images/pipeline.webp)

| 工程 | 処理 | 技術 |
|---|---|---|
| 1. 原画像 | SHA-256 で固定し、測定には原画素を使う | tifffile |
| 2. 核の検出 | StarDist で核を分割 | Fiji · TensorFlow Java |
| 3. 核小体・細胞質 | 親の核ごとに背景を正規化して Cellpose-SAM で推論し、核全体を拾った候補を除いて Multi-Otsu・Watershed で境界を補正 | PyTorch · scikit-image |
| 4. 測定 | 原画像座標の整数ラベルから面積・輝度を計算。核小体は親核の ID を保持 | NumPy |
| 5. 統計 | 細胞・視野・実験回を区別し、実験回を n として検定 | SciPy · statsmodels · pandas |
| 6. 論文の図 | SVG（文字を編集可能）・PDF（フォント埋め込み）・CSV で出力 | Matplotlib |

### 推論環境

- Fiji／TensorFlow Java と Cellpose-SAM／PyTorch を、別々の固定環境で実行
- 依存パッケージとモデルの SHA-256 を、読み込み前に照合
- 実行時のパッケージ・モデルの取得と外部通信を禁止
- GPU 推論は PC と同じ runner・モデル・ライブラリ版を使い、float32・TF32 無効・決定的アルゴリズムで実行。結果の版をハッシュで照合

### 追加学習

| 項目 | 内容 |
|---|---|
| 教師データ | 染色画像と、研究者が修正したインスタンスマスク |
| 対象 | Cellpose-SAM を核小体・細胞質ごとに追加学習 |
| 評価 | 試料・撮影バッチを分け、輪郭精度・過分割・結合誤りを評価 |
| 版管理 | 学習データ・重み・推論条件を一組で管理し、重みを [Hugging Face](https://huggingface.co/Genellect/Cytellect) で公開 |

## AI による解析設定

研究目的の一文を、LLM（GPT-6.1 Sol）が検出・測定・選別・統計・図の構造化設定に変換する。計算は検証済みの Python が担う。

| 項目 | 内容 |
|---|---|
| 送るデータ | 指示文、染色とチャンネルの対応、画像寸法、現在の設定 |
| 送らないデータ | 原画像、測定値、ファイル名 |
| 検証 | API が型・数値範囲・登録チャンネルを照合し、研究者が採用した設定だけを手動設定と同じジョブで実行 |
| 費用 | Cloudflare Workers と D1 で、呼び出し前に費用を予約し、完了後に精算。どちらも原子的に実行し、未精算の予約も上限に含める |

## 解析記録

- 設定・マスク・測定値・統計・図を版で関連付け、モデルや設定を変えた後も以前の結果と計算条件を保持
- 輪郭の描画・分割・結合・Undo／Redo は原画像の座標でマスクに保存し、依存する測定・統計・図を更新
- 図の点から、計算に使った画像と領域を開く
- グラフの色や軸の変更は再描画だけで、測定と検定はやり直さない
- 書き出しに入力ハッシュ・マスク・設定・環境・再計算スクリプトを同梱

## 信頼性とセキュリティ

| 項目 | 実装 |
|---|---|
| ジョブ | DB に永続化し、要求 ID で重複実行を防止。実行権は compare-and-swap で取得し、確定時にも検証 |
| 計算の分離 | 実行ごとの作業ディレクトリと子プロセス。キャンセル・時間・メモリ上限でその実行だけを停止 |
| 同時編集 | 設定の版を照合し、競合は `409` |
| 非同期応答 | 対象と設定の版が画面と一致する応答だけを表示 |
| 認証 | `HttpOnly`・`SameSite=Strict` Cookie。トークンはハッシュで保存し、所有権と Origin を検証 |
| SVG の取り込み | 実行可能要素と外部参照を除去し、図ごとに要素 ID を分離 |
| Docker 版 | 非 root・読み取り専用のルート・権限の削減。計算ワーカーはネットワークなし |
| Windows 版 | `127.0.0.1` で待ち受け、署名とハッシュを検証。新版の起動確認まで旧版を保持 |
| 研究データ | コードと別の領域に保存し、保存期限の管理と削除はワーカーが担当 |

脆弱性の報告方法は [SECURITY.md](SECURITY.md) にまとめている。

## 開発
### ローカル開発

Python 3.12、Node.js 24、pnpm 11.19.0、uv を使用する。Linux での起動手順は次のとおり。

```bash
python3 scripts/dev.py setup --fiji ~/cytellect-fiji

export CYTELLECT_DATA_DIR=~/cytellect-data CYTELLECT_FIJI_EXECUTABLE=~/cytellect-fiji CYTELLECT_SECURE_COOKIES=false
uv run cytellect invite --hours 24
uv run cytellect serve      # 端末 1
uv run cytellect-worker     # 端末 2（同じ環境変数を設定）
pnpm dev                    # 端末 3
```

CI の対象は、型・API 契約、数値計算、実 Fiji とブラウザの連携、Windows のセットアップ、依存パッケージの監査である。統計結果は独立した数式や全列挙による計算と照合している。Windows 版ではソースのテストに加え、配布 ZIP の導入からブラウザ操作、再計算までを確認する。

```bash
python3 scripts/dev.py check
```

### クラウド開発

Claude Code や Codex のクラウド環境では、次のセットアップスクリプトを環境の設定に登録する。Fiji の導入などの詳しい手順は [CONTRIBUTING](CONTRIBUTING.md#クラウド開発) にまとめている。

| ツール | セットアップスクリプト |
|---|---|
| Claude Code | `bash .claude/cloud-setup.sh` |
| Codex | `bash .codex/setup.sh` |

## ライセンス

コードは Apache License 2.0 で OSS として公開している。Fiji、モデルの重み、データセットには、それぞれのライセンスが適用される。
