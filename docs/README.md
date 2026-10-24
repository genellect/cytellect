# ドキュメント

Cytellect の文書の一覧です。開発に参加する方は、まず「開発メンバーが最初に読む文書」から読んでください。英語で書かれた文書には「（英語）」と付けています。

## 開発メンバーが最初に読む文書

1. [開発の原則](development-principles.md)：人も AI エージェントも守る原則。作業に関係する節を必ず読む
2. [チーム開発ルール](team-development.md)：開発の流れ、Git とレビュー、研究データの扱い
3. [CONTRIBUTING](../CONTRIBUTING.md)：開発環境の構築と起動、PR を出す前の検査
4. [CI の構成](ci.md)：PR と `main` で実行されるジョブ

## 使う

- [はじめての画像解析](quickstart.ja.md)
- [Windows 版のインストールと更新](install-windows.ja.md)
- [Docker Desktop で使う](docker-desktop.md)
- [クラウド GPU で Cellpose を動かす](cloud-gpu.ja.md)
- [CZI を定量用の TIFF に変換する](converting-czi.md)
- [全視野の品質一覧](region-quality-overview.md)
- [ローカル版のブラウザ配信](local.md)（英語）

## 計画

- [ロードマップ](roadmap.md)：現在の提供状況と今後の計画
- [解析機能の概要（2026 年 10 月）](implementation-overview.ja.md)
- [解析基盤の費用と制約](hosting-costs.ja.md)
- [要件](requirements.md)（英語）
- [研究者の作業の流れと改善の進め方](research-workflow.md)（英語）

## 設計と実装

- [実行環境と API](architecture.md)（英語）
- [公開デモの仕組み](showcase.md)
- [Web の画面](web.md)（英語）
- [画面設計の方針](interface-design.md)（英語）
- [解析提案のサービス](proposal-service.md)（英語）
- [解析提案の Worker のデプロイ](proposal-deployment.md)（英語）
- [Windows 版の実行環境の構成](windows-runtime.md)（英語）
- [Git からの公開](deployment.md)（英語）
- [ローカル版の資源の測定](resource-benchmark.md)（英語）

## 科学仕様

計算の正本は[計算仕様](methods.md)（英語）です。

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

- [セキュリティポリシー](../SECURITY.md)：脆弱性の報告
- [データ保護と運用](security.md)（英語）
- [サードパーティのソフトウェア、重み、再配布](oss.md)（英語）

## 公開サイト

- [LP の美術方針](lp-art-direction.md)
- [LP Preview のデザイン基準](lp-optical-preview.md)

## 記録

- [Windows 版 0.1.0-local.19 の受入記録](local-release-0.1.0-local.19.md)（英語）
- [Windows 版 0.1.0-local.17 の受入記録](local-release-0.1.0-local.17.md)（英語）
- [下書き](drafts/gfp-nuclear-signal)
- [アーカイブ](archive/README.md)：MVP 期の経緯の記録。現在の作業指示ではありません
