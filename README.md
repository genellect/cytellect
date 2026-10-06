# Cytellect

[![Verify](https://github.com/genellect/cytellect/actions/workflows/ci.yml/badge.svg)](https://github.com/genellect/cytellect/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/genellect/cytellect?include_prereleases)](https://github.com/genellect/cytellect/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

**Cytellect は、蛍光顕微鏡画像の定量解析ソフトウェアです。** 核の検出から統計解析、論文用の図の作成までを、一つの画面で行えます。

主な機能：

- 2D 蛍光画像（TIFF / OME-TIFF）からの細胞核・核小体の検出と、検出結果の修正
- 核ごとの面積、輝度、核小体の数と面積割合の測定
- 独立した実験回を単位とした群間比較と相関解析
- 細胞・視野・実験回の値を重ねた図と、編集可能な SVG / PDF、CSV、Methods の文案の出力
- 書き出したデータからの再計算による、結果の再現

Windows 版は[最新のリリース](https://github.com/genellect/cytellect/releases/tag/v0.1.0-local.15)からダウンロードできます。インストールせずに試す場合は、[公開サイト](https://cytellect.vercel.app/workspace?demo=bbbc013)で公開画像の解析例を操作できます。

使い方と解析法は[研究者向けの説明](docs/implementation-overview.ja.md)と[解析法](docs/methods.md)に、ソースからのビルドと開発の手順は [CONTRIBUTING.md](CONTRIBUTING.md) にあります。

画像処理には Fiji と StarDist、解析サーバーには FastAPI と NumPy・SciPy・statsmodels・Matplotlib、画面には Next.js を使っています。Web、Windows 版、Docker のいずれでも同じ解析コードが動き、研究画像は利用者の PC や研究室のサーバーの外に送られません。設計の詳細は [architecture.md](docs/architecture.md) と [security.md](docs/security.md) を参照してください。

*Cytellect は研究用に開発中のソフトウェアです。ソースコードは [Apache License 2.0](LICENSE) で公開しています。Fiji、モデルの重み、公開データセットには、それぞれのライセンスが適用されます。*

![核の検出結果を重ねた Cytellect の解析画面](apps/web/public/marketing/workspace-public.png)

## 開発

Cytellect は [genellect](https://github.com/genellect) が開発しています。不具合の報告や提案は [Issue](https://github.com/genellect/cytellect/issues) で受け付けます。研究用の非公開画像や解析結果は Issue に含めないでください。脆弱性は [SECURITY.md](SECURITY.md) の窓口から報告してください。
