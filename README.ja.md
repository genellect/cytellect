# Cytellect

蛍光画像の領域確認・定量から、実験単位の統計と編集可能な論文用図までをつなぐ画像解析アプリです。初期レシピは核・核小体・GFP・NCLを対象とします。

[English](README.md) · [要件](docs/requirements.md) · [解析法](docs/methods.md) · [検証](docs/validation.md)

[解析計画](https://cytellect.vercel.app/plan) · [公開画像のサンプル](https://cytellect.vercel.app/demo) · [ローカル版の構成](docs/local.md) · [費用と制約の比較](docs/hosting-costs.ja.md)

**研究用プロトタイプです。** Web・API・ワーカーを実装し、公開実画像と独立した数値計算で検証しています。対象実験の生画像による妥当性と、研究者によるPoC評価は未実施です。公開画面のサンプルは論文に紐づく実画像を使います。UIの公開と解析サーバーの稼働は別に確認します。

## 今回の改善方針

画像を使うWet研究者が、目的と実験設計から解析を進められる2D蛍光画像の基盤へ拡張しています。[研究者の作業と開発体制](docs/research-workflow.md)に、文献に基づく課題・担当分担・公開までの順序を記録しています。解析計画画面は、画像を送らずに既存レシピの適用条件と確認事項を整理します。現在のソースには、[任意の標識と手動・取り込み領域の面積／輝度測定](docs/generic-regions.md)、実験情報を未設定のまま利用できる[視野別の分布図](docs/descriptive.md)を追加しています。汎用領域の自動検出と任意チャンネルの群間推測統計は後続実装です。

[独立レビュー](docs/scientific-review.md)では、計算の正しさ・公開実画像の実行・生物学的妥当性・利用者評価を区別します。今回のソース修正は統計1.2.2・図1.1.2に、汎用領域1.0.0・記述図1.0.0を追加します。配布中のlocal.10 ZIPは従来のコードとプロトコルのままです。本番UIの公開で既存のインストール版が更新されることはありません。次の配布版は別途インストール検証を行います。

## できること

- DAPI核検出、NCL核小体候補抽出、手動での追加・削除・輪郭修正・結合・分割。
- 核・核小体・核質の測定、GFP選別、背景ROI、除外理由、解析版の管理。
- 実験単位の比較、探索的回帰、数値CSVの取込、図・測定表・ROI・再実行パッケージの出力。
- Fiji／StarDist／ImageJ／MorphoLibJを利用。原画像、表示調整、検出用処理を分離。
- CZIはFiji／Bio-Formatsで非公開のまま変換します。[画素を変えずに変換する手順](docs/converting-czi.md)を用意しています。

自動検出結果は利用者による確認が必要です。NCLから核小体領域を定義すると、NCLの再分布自体で検出領域も変化します。この制約を条件・出力に記録します。細胞全体の境界をDAPIだけから推定しません。

## ローカル版

操作画面はブラウザに統一し、Fijiと解析APIを同じPCで動かします。Windows向けの配布物は、自動導入・起動・終了と実画像の解析・出力を検証した版だけを[リリースページ](https://github.com/genellect/cytellect/releases)へ公開します。ZIPを展開して **Cytellect Setup.cmd** を開くと依存環境を自動導入し、その後はショートカットから起動できます。既存のPython・FijiやシステムPATHは変更しません。将来のクラウド版でも、画像処理・統計・出力の実装を共有します。

ローカル版の保存期限は最終操作から24時間です。アプリ終了中やPC停止中に期限を迎えたデータは、次回起動時に削除します。現時点で、利用者ごとの環境構築を手作業の必須手順にはしません。

[Windowsプレビュー 0.1.0-local.10 をダウンロード](https://github.com/genellect/cytellect/releases/tag/v0.1.0-local.10) · [チェックサムと受入記録](docs/local-release-0.1.0.md)

## 開発用の起動

Python3.12・Node.js24・pnpm11.19.0を使います。`uv sync --locked --dev` と `pnpm install --frozen-lockfile` で固定依存を導入します。

`CYTELLECT_DATA_DIR` にrepo外の非公開ディレクトリ、`CYTELLECT_APP_ORIGIN` に `http://localhost:3000`、ローカル開発時のみ `CYTELLECT_SECURE_COOKIES=false` を設定します。

`uv run python scripts/fiji_setup.py <repo外の新規ディレクトリ> --platform windows-x64` で固定Fijiを導入し、`CYTELLECT_FIJI_EXECUTABLE` にそのディレクトリを指定します。Linuxは `linux-x64` を選びます。

`uv run cytellect invite --hours 24` で招待を発行し、別々の端末で `uv run cytellect serve`、`uv run cytellect-worker`、`pnpm dev` を起動します。招待コードはログやIssueに記載しないでください。Fiji未設定時、実画像の解析を別エンジンで代替することはありません。

コンテナ・TLS・保存期限・削除・障害復旧は[運用](docs/security.md)、検証コマンドは[開発手順](CONTRIBUTING.md)を参照してください。

## 研究情報の保護

未公開の研究画像・資料・ファイル名・実験条件・結果・派生物を、公開repo・CI・外部AI・公開デモへ持ち込みません。元画像と派生物は非公開ボリュームに置き、明示的な利用操作から24時間を保存期限とします。

人工画像は計算の単体テストに使います。実画像での検出確認と公開デモには、出典・染色・用途を記録した公開データを使い、内部検証と公開再配布の条件を分けます。

「論文用」は、図の編集可能性、条件の明示、測定値の追跡、再実行可能性を指します。特定実験での妥当性を保証する表現ではありません。[残る検証](docs/roadmap.md)

自作コードはApache-2.0です。Fiji・プラグイン・モデル・公開画像には各々の条件が適用されます。[OSS管理](docs/oss.md)
