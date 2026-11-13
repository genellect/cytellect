# ドキュメント

Cytellect の文書の一覧。利用者は「利用ガイド」から、開発に参加するメンバーは「開発メンバーが最初に読む文書」から読む。英語で書かれた文書には「（英語）」と付けている。

## 開発メンバーが最初に読む文書

1. [チーム開発ルール](team-development.md)：開発の流れ、Git とレビュー、研究データの扱い
2. [CONTRIBUTING](../CONTRIBUTING.md)：開発環境の構築と起動、PR を出す前の検査
3. [開発の原則](development-principles.md)：人も AI エージェントも守る原則。作業に関係する節を必ず読む
4. [CI の構成](ci.md)：PR と `main` で実行されるジョブ

## 利用ガイド

### 導入する

| 文書 | 対象 | 内容 |
|---|---|---|
| [Windows 版のインストールと更新](install-windows.ja.md) | 研究者 | 配布版の導入・起動・更新・アンインストール |
| [Docker Desktop で使う](docker-desktop.md) | 研究者・研究室の管理者 | ソースから Docker で起動・更新・データ保持 |
| [クラウド GPU で Cellpose を動かす](cloud-gpu.ja.md) | 研究室の管理者 | Cellpose の推論をクラウド GPU で行う設定 |

### 解析する

| 文書 | 対象 | 内容 |
|---|---|---|
| [はじめての画像解析](quickstart.ja.md) | 研究者 | 公開画像を使った、登録から図の保存までの練習 |
| [CZI をオフラインで定量用の TIFF に変換する](converting-czi.md) | 研究者 | Fiji で CZI を画素値を変えずに TIFF へ変換する |
| [全視野の品質一覧](region-quality-overview.md) | 研究者 | 保存済みの診断を視野ごとに一覧する画面の読み方 |

## 計画

- [ロードマップ](roadmap.md)：現在の提供状況と今後の計画
- [解析機能の概要（2026 年 10 月）](implementation-overview.ja.md)
- [解析モデルの選定と発展方針](segmentation-models.ja.md)：採用モデル、3D・細胞内構造への展開、SaaS の設計方針
- [解析基盤の費用と制約](hosting-costs.ja.md)
- [要件](requirements.md)（英語）
- [研究者の作業の流れと改善の進め方](research-workflow.md)（英語）
- [研究パラメータの拡張計画](drafts/research-measurements/plan.md)：設計レビューを反映した共通測定・層別・受入・並行作業の計画。4 方針は採用済み、具体的な契約は M0 で確定
- [ローカル研究データの利用](drafts/research-measurements/local-data.md)：非公開の教師・評価データを公開開発から分離する境界
- [群間比較の UX 改善：目標定義書（案）](drafts/group-comparison/goals.md)、[要件定義書（案）](drafts/group-comparison/requirements.md)、[開発体制（案）](drafts/group-comparison/development.md)：レビュー中の下書き
- [画像の測定ビュー：要件定義書（案）](drafts/image-measurement-view/requirements.md)、[実装案](drafts/image-measurement-view/implementation.md)：画像の色分けを測定の入口にし、何を測っているかと次の一手を画面で示す。2026-11-11 承認、実装中
- [結果の表現とデモの素材：要件定義書（案）](drafts/results-and-demo-story/requirements.md)、[実装案](drafts/results-and-demo-story/implementation.md)：統計の結果を見出しと箇条書きにし、前提の表示を 1 か所にまとめ、考察を LLM に分け、デモの素材を物語で選ぶ。2026-11-12 に方向性を承認、個々の判断は未決
- [LP の刷新：実装方針と実装](drafts/lp-renewal/implementation.md)：2026-11-13 に承認された実装方針と、今のページを土台にページ全体を作り替えた実装（3D の空間、書体、実写）。オーナーの判定待ち
- [クラウド開発環境：実装計画（案）](drafts/cloud-development/plan.md)：オーナーの承認待ち
- [本番構成での動作確認と研究者 UX 評価：実施計画（案）](drafts/cloud-development/verification.md)：オーナーの承認待ち
- [エージェントによる画面の評価：2026-10-27](drafts/cloud-development/agent-evaluation-2026-10-27.md)：研究者による評価ではない

## 設計と実装

- [実行環境と API](architecture.md)（英語）
- [ローカル版のブラウザ配信](local.md)（英語）
- [公開デモの仕組み](showcase.md)
- [Web の画面](web.md)（英語）
- [画面設計の方針](interface-design.md)（英語）
- [解析提案のサービス](proposal-service.md)（英語）
- [解析提案の Worker のデプロイ](proposal-deployment.md)（英語）
- [Windows 版の実行環境の構成](windows-runtime.md)（英語）
- [Git からの公開](deployment.md)（英語）
- [ローカル版の資源の測定](resource-benchmark.md)（英語）

## 科学仕様

計算の正本は[計算仕様](methods.md)（英語）。

- [統計と書き出しの仕様](statistics.md)（英語）
- [統計手法の説明文書](statistical-methods.md)（英語）
- [共通の統計とグラフ](common-statistics.md)（英語）
- [記述的な測定と図](descriptive.md)（英語）
- [図の書き出し](figures.md)（英語）
- [画像の表示と保存する画素値](display.md)（英語）
- [固定版の Fiji エンジン](fiji.md)（英語）
- [核の中の NCL 候補領域](nucleolar-compartments.md)（英語）
- [蛍光陽性の候補領域](positive-regions.md)（英語）
- [GFP による核の選別](gfp-exploratory-gates.md)（英語）
- [核のレシピとチャンネルの案内](native-recipe-guidance.md)（英語）
- [汎用の領域測定](generic-regions.md)（英語）
- [汎用の領域比較](region-comparisons.md)（英語）
- [保存した視野の群](region-cohorts.md)（英語）
- [解析計画](analysis-planning.md)（英語）
- [画像に結びつくワークスペースの設定](workspace-source-settings.md)（英語）
- [ワークスペースの再設計](workspace-redesign.md)（英語）

## 検証

- [検証の階層](validation.md)（英語）
- [独立した再現レビュー](scientific-review.md)（英語）
- [公開画像での検証：BBBC039v1](public-validation.md)（英語）
- [公開画像での検証：GFP](public-gfp-validation.md)（英語）
- [公開画像での検証：DAPI と NCL](public-nucleolar-validation.md)（英語）

## 使いやすさの評価

- [Wet 研究者による操作評価課題](usability-tasks.ja.md)
- [独立単位を確認する練習画像](usability-practice.ja.md)
- [研究者の作業の見直し](researcher-usability.md)（英語）

## セキュリティとライセンス

- [セキュリティポリシー](../SECURITY.md)：現行の対策と脆弱性の報告。セキュリティの正本
- [データ保護と運用](security.md)（英語）：運用者向けの詳細
- [第三者のソフトウェア・重み・データ](oss.md)
- [リリースの署名](release-signing.md)：アプリ内更新の署名鍵の作成・登録・交換・失効

## 公開サイト

- [LP の美術方針](lp-art-direction.md)
- [LP Preview のデザイン基準](lp-optical-preview.md)

## 記録

- [Windows 版 0.1.0-local.20 の受入記録](local-release-0.1.0-local.20.md)（英語）
- [Windows 版 0.1.0-local.19 の受入記録](local-release-0.1.0-local.19.md)（英語）
- [Windows 版 0.1.0-local.17 の受入記録](local-release-0.1.0-local.17.md)（英語）
- [下書き](drafts/gfp-nuclear-signal)
- [アーカイブ](archive/README.md)：MVP 期の経緯の記録。現在の作業指示ではない
