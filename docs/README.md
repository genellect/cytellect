# ドキュメント / Documentation

Cytellect の文書の索引です。概要は [README](../README.md)（[English](../README.en.md)）、開発の手順は [CONTRIBUTING](../CONTRIBUTING.md) を参照してください。

## 使う / Use

- [はじめての画像解析](quickstart.ja.md)
- [Windows 版のインストールと更新](install-windows.ja.md)
- [Docker Desktop でのブラウザ操作](docker-desktop.md)
- [Local browser delivery](local.md)
- [CZI をオフラインで定量用 TIFF へ変換する](converting-czi.md)
- [クラウド GPU で Cellpose を動かす](cloud-gpu.ja.md)

## 計画と要件 / Plans and requirements

- [ロードマップ](roadmap.md) — 現在の提供状況と今後の計画
- [Accepted requirements](requirements.md)
- [Researcher workflow and continuous improvement](research-workflow.md)
- [Cytellect 解析機能（2026年10月）](implementation-overview.ja.md)

## 開発 / Development

- [チーム開発ルール / Team development rules](team-development.md)
- [Development standards](development-standards.md)
- [Runtime and API](architecture.md)
- [Web interface](web.md) · [Interface direction](interface-design.md)
- [Git-driven publication](deployment.md)
- [Analysis proposal service](proposal-service.md) · [Proposal Worker deployment](proposal-deployment.md)
- [Windows runtime composition](windows-runtime.md)
- [Local resource benchmark](resource-benchmark.md) · [解析基盤の費用と制約](hosting-costs.ja.md)

## 科学仕様 / Scientific contracts

- [Scientific contract](methods.md)
- 統計 / Statistics: [Statistical and export protocol](statistics.md) · [Statistical Methods documents](statistical-methods.md) · [Explicit common statistics and graphs](common-statistics.md)
- 測定と図 / Measurement and figures: [Descriptive measurements and figures](descriptive.md) · [Figure export contract](figures.md) · [Image display and stored pixel values](display.md)
- 検出 / Detection: [Fixed Fiji image engine](fiji.md) · [NCL candidate compartments](nucleolar-compartments.md) · [Fluorescence-positive candidate regions](positive-regions.md) · [GFP nuclear selection](gfp-exploratory-gates.md) · [Nuclear-recipe channel guidance](native-recipe-guidance.md)
- 領域と比較 / Regions and comparisons: [Generic region measurements](generic-regions.md) · [Generic region comparisons](region-comparisons.md) · [Saved-field cohorts](region-cohorts.md) · [全視野の品質一覧](region-quality-overview.md)
- 解析計画とワークスペース / Planning and workspace: [Analysis planning](analysis-planning.md) · [Source-bound workspace settings](workspace-source-settings.md) · [Single workspace](workspace-prototype.md) · [Workspace redesign](workspace-redesign.md)

## 検証 / Validation

- [Validation layers](validation.md) · [Repeatable independent review](scientific-review.md)
- 公開画像 / Public images: [BBBC039v1](public-validation.md) · [GFP](public-gfp-validation.md) · [DAPI/NCL](public-nucleolar-validation.md)
- ユーザビリティ / Usability: [Researcher workflow review](researcher-usability.md) · [Wet 研究者による操作評価課題](usability-tasks.ja.md) · [独立単位を確認する人工練習画像](usability-practice.ja.md)

## セキュリティとライセンス / Security and licensing

- [脆弱性の報告 / Reporting a vulnerability](../SECURITY.md)
- [Data protection and operations](security.md)
- [Third-party software, weights and redistribution](oss.md)

## 公開サイト / Public site

- [LP の美術方針](lp-art-direction.md) · [LP Preview のデザイン基準](lp-optical-preview.md)

## 記録 / Records

- Windows 版の受入記録 / Windows acceptance records: [0.1.0-local.19](local-release-0.1.0-local.19.md) · [0.1.0-local.17](local-release-0.1.0-local.17.md)
- [下書き / Drafts](drafts/gfp-nuclear-signal)
- [アーカイブ / Archive](archive/README.md) — MVP 期の経緯の記録です。現在の作業指示ではありません。
