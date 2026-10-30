# 第三者のソフトウェア・重み・データ / Third-party software, weights and data

[日本語](#日本語) · [English](#english)

## 日本語

Cytellect 独自のコードは Apache-2.0 で公開している。このライセンスは、Fiji、Java、プラグイン、モデルの重み、依存パッケージ、データセットのライセンスを置き換えない。各コンポーネントには、それぞれのライセンスが適用される。

### 配布物ごとの構成

| 配布物 | 第三者のコンポーネントの扱い |
|---|---|
| リポジトリ | 導入の手順、ロックファイル、ハッシュの記録だけを置く。第三者の実行環境と学習済みの重みは含めない |
| Windows 版（セットアップ ZIP） | ソース、ビルド済みの Web、Web の依存のライセンス本文（`THIRD_PARTY_WEB_NOTICES.txt`）、`LICENSE.cellpose.txt`、公開画像の登録簿を含む。Python・パッケージ・Fiji は導入時に公式の配布元から取得し、ハッシュを照合する。Cellpose は PC に導入せず、クラウド GPU で実行する |
| Windows 版（インストーラー `Cytellect-Setup-<版>.exe`） | ZIP の内容に加え、Python 3.14、lock の依存パッケージ（wheel）、uv、Fiji（JDK とプラグインを含む）の公式の配布物を改変せずに同梱する。`licenses/THIRD_PARTY_BUNDLED.txt` と `licenses/bundled-components.json` に、各コンポーネントのライセンス、同梱したファイルの SHA-256、ソースの所在を書き、wheel に入っているライセンス本文を `licenses/wheels/` に置く。ソースの提供が必要なコンポーネントは、同梱した版ちょうどのソースを、同じリリースの資産 `Cytellect-<版>-gpl-sources.zip` に収める。ソースを取得できない 42 個は、上流のソースの所在だけを記す（[GPL などの対応するソース](#gpl-などの対応するソース)）。インストーラー自体にソースは入れない。これらはインストール先の `licenses/` に入り、ビルドの受領記録（`Cytellect-Setup-<版>.json`）にも一覧とハッシュを記録する。Fiji・JDK・各 jar・Python のライセンス本文は、導入後の `runtimes/` にそのまま残る |
| Docker 版 | 利用者の環境でビルドする。計算ワーカーのイメージには、ビルド時に取得した Fiji、Cellpose の実行環境、`cpsam_v2` の重みが入る |
| GPU イメージ（GHCR） | Cellpose の実行環境、`cpsam_v2` の重み、`engines/cellpose`（`LICENSE.cellpose.txt` を含む） |

イメージや配布物を配る場合は、実際に組み立てた内容に対して著作権・ライセンスの表示を保持する。GPL・LGPL のコンポーネントを含む場合は、それらが求める対応するソースと再リンクの手段を用意する（Windows 版のインストーラーは次の節のとおり）。

### GPL などの対応するソース

オーナーの判断（2026-10-30）により、Windows 版のインストーラーが同梱するソフトのうち、バイナリと一緒にソースの提供を求めるライセンス（GPLv2・GPLv3・LGPL・AGPL・MPL・EPL・CDDL など）のものは、同梱した版ちょうどのソース一式を、CI がリリースの資産 `Cytellect-<版>-gpl-sources.zip` として添付する。書面による提供の申し出はせず、通知も送らない。ソースを自動で取得できない部品は、[下の表](#ソースを添付しない部品)のとおり、上流のソースの所在だけを記す。

| 段階 | 内容 |
|---|---|
| 列挙 | 同梱したバイト列から機械的に決める。手で決め打ちの一覧は作らない。Fiji のアーカイブとプラグインの各 jar は、jar に入っている Maven の POM のライセンス、なければ公開された POM（親をたどる）、なければ jar 自身のライセンス文書による。座標は `pom.properties`、なければ jar の SHA-1 による Maven の検索で決める。JDK の外にある実行ファイルとライブラリも対象にする。JDK は `release` ファイルから版を決める。wheel は、メタデータのライセンスと、同梱するライブラリのライセンス文書の `License:` 行による（SPDX の `OR` は義務のない選択肢を、`WITH GCC-exception` は義務がないものとして扱う）。ライセンスを判定できないものは、ソースが必要なものとして扱う |
| 固定 | [`engines/fiji/corresponding-source.lock.json`](../engines/fiji/corresponding-source.lock.json) に、同梱する Fiji のすべての jar・実行ファイル・プラグインと JDK について、SHA-256、ライセンスの根拠、ソースの要否、ソースの URL・SHA-256・大きさを記録する。jar のソースは、次の順に最も正確なものを固定する。(1) 同梱した jar と同じバイト列の jar が公開されている場合の、その `-sources.jar`（SciJava の Maven リポジトリ、Maven Central）。(2) jar がビルド元のコミット（`Implementation-Build`）と GitHub のリポジトリを記録している場合の、そのコミットのアーカイブ。(3) jar が自身の `pom.properties` で名乗るリリース版の `-sources.jar`（バイト列は一致しないが版は同じ）。どれによるかは lock の `source.kind` に記録する。Fiji の固定（`runtime.lock.json`）を変えたら `python scripts/corresponding_source.py lock --cache <checkout の外>` で作り直す。wheel のソースは `uv.lock` が固定する sdist を使う |
| 取得と添付 | リリースのワークフロー（`local-release.yml`）が `build_windows_installer.py build --corresponding-source` を実行する。ビルドは、同梱したバイト列から求めた一覧が lock と一致することを確かめ、各ソースを固定した SHA-256 で照合して取得する（通信の一時的な失敗は再試行する）。ソースが必要なのに固定されたソースがない部品は、[`engines/fiji/source-exceptions.json`](../engines/fiji/source-exceptions.json) に、同じ SHA-256、理由、上流のソースの所在とともに載っているものだけを通す。載っていない部品、SHA-256 が違う部品、同梱物や lock と合わなくなった例外があれば、ビルドを失敗させる |
| 記載 | インストーラーの `licenses/THIRD_PARTY_BUNDLED.txt`・`bundled-components.json`・`corresponding-source.json` に、資産の名前と SHA-256、各部品の資産の中の場所とソースの SHA-256 を書く。ソースを添付しない部品は、ライセンス（判定できないものはその旨）、理由、上流のソースの所在を書く（`corresponding-source.json` の `not_attached_components`）。資産の中の `manifest.json` には、同梱したファイルの SHA-256、ライセンスの根拠、ソースの URL と SHA-256、添付しない部品の理由と上流の所在がある |
| 配布の停止 | 資産がない、またはハッシュが受領記録と一致しない場合、ワークフローは下書きのリリースを作らない。作成後に資産が添付されていない場合は、再アップロードを試み、それでもなければ下書きを削除する |

CI でインストーラーを試すだけのビルド（`ci.yml` の `windows-installer`）はソースを集めない。その `licenses/` には「配布してはならない」と書かれる。

現在の固定（Windows 用 Fiji 2026-09-29 版）では、同梱する 676 個の jar・実行ファイル・プラグインのうち 172 個がソースを必要とし、42 個はライセンスを判定できない。これに JDK を加えた 215 個のうち 173 個のソース（合計約 102 MB）を固定し、資産に収める。

#### ソースを添付しない部品

オーナーの判断（2026-10-30）により、ソースを自動で取得できない次の 42 個も同梱し、ライセンスと上流のソースの所在だけを記す。内訳は、同梱したバイト列のソースが公開されていないもの 16 個（JDK を含む）、ソースの配布元に接続できないもの 1 個、ライセンスを判定できないもの 25 個。正本は [`engines/fiji/source-exceptions.json`](../engines/fiji/source-exceptions.json) で、各部品の SHA-256 と理由の詳細もそこにある。版の分かる上流の所在には、タグまたは版を添える。Fiji の固定を変えて部品が変わった場合は、例外の一覧も見直さないとリリースのビルドが止まる。

残るリスク：これらの 42 個は、同梱したバイト列のソースをこのリリースが持たず（25 個はライセンスの条件も確かめていない）、上流が該当する版を移したり取り下げたりすると、受け取った人が案内先からソースを得られなくなる。

| 部品 | ライセンス | 理由 | 上流のソースの所在 |
|---|---|---|---|
| `datasets-0.8.1906.jar`、`grDevices-0.8.1906.jar`、`graphics-0.8.1906.jar`、`methods-0.8.1906.jar` | Part of R 2.14.2 | 同梱したバイト列のソースが公開されていない | <https://github.com/bedatadriven/renjin/tree/v0.8.1906>（v0.8.1906） |
| `java3d-core-1.7.2.jar` | GPLv2 with Classpath exception | 同梱したバイト列のソースが公開されていない | <https://github.com/jogamp/java3d-core/tree/v1.7.2-final>（v1.7.2-final） |
| `jffi-1.3.13-native.jar` | GNU Lesser General Public License version 3; The Apache Software License, Version 2.0 | 同梱したバイト列のソースが公開されていない | <https://github.com/jnr/jffi/tree/jffi-1.3.13>（jffi-1.3.13） |
| `vecmath-1.7.2.jar` | GPLv2 with Classpath exception | 同梱したバイト列のソースが公開されていない | <https://github.com/jogamp/vecmath/tree/v1.7.2-final>（v1.7.2-final） |
| `ffmpeg-6.1.1-1.5.10-windows-x86_64.jar` | Apache License, Version 2.0; GNU General Public License (GPL) version 2, or any later version; GPLv2 with Classpath exception | 同梱したバイト列のソースが公開されていない | <https://github.com/bytedeco/javacpp-presets/tree/1.5.10>（1.5.10）、<https://github.com/FFmpeg/FFmpeg/tree/n6.1.1>（n6.1.1） |
| `javafx-base-23.0.2-win.jar`、`javafx-fxml-23.0.2-win.jar`、`javafx-graphics-23.0.2-win.jar`、`javafx-media-23.0.2-win.jar`、`javafx-web-23.0.2-win.jar` | GPLv2+CE | 同梱したバイト列のソースが公開されていない | <https://github.com/openjdk/jfx23u/tree/23.0.2-ga>（23.0.2-ga） |
| `openblas-0.3.26-1.5.10-windows-x86_64.jar` | Apache License, Version 2.0; GNU General Public License (GPL) version 2, or any later version; GPLv2 with Classpath exception | 同梱したバイト列のソースが公開されていない | <https://github.com/bytedeco/javacpp-presets/tree/1.5.10>（1.5.10）、<https://github.com/OpenMathLib/OpenBLAS/tree/v0.3.26>（v0.3.26） |
| `opencv-4.9.0-1.5.10-windows-x86_64.jar` | Apache License, Version 2.0; GNU General Public License (GPL) version 2, or any later version; GPLv2 with Classpath exception | 同梱したバイト列のソースが公開されていない | <https://github.com/bytedeco/javacpp-presets/tree/1.5.10>（1.5.10）、<https://github.com/opencv/opencv/tree/4.9.0>（4.9.0） |
| JDK（Azul Zulu 21.0.7、`zulu21.42.19-ca-jdk21.0.7-win_x64`） | GPL-2.0-only WITH Classpath-exception-2.0 | 同梱したバイト列のソースが公開されていない | <https://github.com/openjdk/jdk21u/tree/jdk-21.0.7+6>（jdk-21.0.7+6） |
| `fiji-2.18.1-SNAPSHOT.jar` | GNU General Public License v3+ | ソースの配布元に接続できない | <https://codeload.github.com/fiji/fiji/tar.gz/c691dc761719086b49a9f927e77d744ae4e5a816>（c691dc761719086b49a9f927e77d744ae4e5a816） |
| `JWlz-1.4.0.jar` | 判定できない | ライセンスを判定できない | <https://github.com/ma-tech/Woolz>（版 1.4.0） |
| `bcprov-jdk18on-1.78.1.jar` | 判定できない | ライセンスを判定できない | <https://github.com/bcgit/bc-java/tree/r1rv78v1>（r1rv78v1） |
| `blas-0.8.jar` | 判定できない | ライセンスを判定できない | <https://maven.scijava.org/content/groups/public/org/netlib/blas/0.8/>（版 0.8）、<https://www.netlib.org/java/f2j/> |
| `f2jutil-0.8.jar` | 判定できない | ライセンスを判定できない | <https://maven.scijava.org/content/groups/public/org/netlib/f2jutil/0.8/>（版 0.8）、<https://www.netlib.org/java/f2j/> |
| `grpc-grpclb-1.75.0.jar` | 判定できない | ライセンスを判定できない | <https://github.com/grpc/grpc-java/tree/v1.75.0>（v1.75.0） |
| `jhotdraw-7.6.0.jar` | 判定できない | ライセンスを判定できない | <https://maven.scijava.org/content/groups/public/org/jhotdraw/jhotdraw/7.6.0/>（版 7.6.0） |
| `jpedalSTD-2.80b11.jar` | 判定できない | ライセンスを判定できない | <https://maven.scijava.org/content/groups/public/org/jpedal/jpedalSTD/2.80b11/>（版 2.80b11） |
| `jtransforms-2.4.jar` | 判定できない | ライセンスを判定できない | <https://maven.scijava.org/content/groups/public/edu/emory/mathcs/jtransforms/2.4/>（版 2.4） |
| `lapack-0.8.jar` | 判定できない | ライセンスを判定できない | <https://maven.scijava.org/content/groups/public/org/netlib/lapack/0.8/>（版 0.8）、<https://www.netlib.org/java/f2j/> |
| `mines-jtk-20151125.jar` | 判定できない | ライセンスを判定できない | <https://github.com/dhale/jtk>（版 20151125）、<https://maven.scijava.org/content/groups/public/edu/mines/mines-jtk/20151125/>（版 20151125） |
| `netlib-java-0.9.3-renjin-patched-2.jar` | 判定できない | ライセンスを判定できない | <https://maven.scijava.org/content/groups/public/org/netlib/netlib-java/0.9.3-renjin-patched-2/>（版 0.9.3-renjin-patched-2） |
| `object-inspector-0.1.jar` | 判定できない | ライセンスを判定できない | <https://github.com/sbridges/object-inspector>（版 0.1）、<https://maven.scijava.org/content/groups/public/com/github/sbridges/object-inspector/object-inspector/0.1/>（版 0.1） |
| `perfmark-api-0.27.0.jar` | 判定できない | ライセンスを判定できない | <https://github.com/perfmark/perfmark/tree/v0.27.0>（v0.27.0） |
| `scala3-compiler_3-3.3.0.jar`、`scala3-interfaces-3.3.0.jar`、`scala3-library_3-3.3.0.jar`、`tasty-core_3-3.3.0.jar` | 判定できない | ライセンスを判定できない | <https://github.com/scala/scala3/tree/3.3.0>（3.3.0） |
| `swingx-1.6.1.jar` | 判定できない | ライセンスを判定できない | <https://github.com/ebourg/swingx>（版 1.6.1） |
| `flimlib-2.1.1-natives-windows_64.jar` | 判定できない | ライセンスを判定できない | <https://github.com/flimlib/flimlib/tree/flimlib-2.1.1>（flimlib-2.1.1） |
| `gluegen-rt-2.6.0-natives-windows-amd64.jar` | 判定できない | ライセンスを判定できない | <https://github.com/jogamp/gluegen/tree/v2.6.0>（v2.6.0） |
| `javafx-controls-23.0.2-win.jar`、`javafx-swing-23.0.2-win.jar` | 判定できない | ライセンスを判定できない | <https://github.com/openjdk/jfx23u/tree/23.0.2-ga>（23.0.2-ga） |
| `jogl-all-2.6.0-natives-windows-amd64.jar` | 判定できない | ライセンスを判定できない | <https://github.com/jogamp/jogl/tree/v2.6.0>（v2.6.0） |
| `xerbla-0.8.jar` | 判定できない | ライセンスを判定できない | <https://maven.scijava.org/content/groups/public/org/netlib/xerbla/0.8/>（版 0.8）、<https://www.netlib.org/java/f2j/> |
| `blosc1.dll` | 判定できない | ライセンスを判定できない | <https://github.com/Blosc/c-blosc/tree/v1.18.1>（v1.18.1） |

### Fiji と核の検出

[Fiji の固定記録](../engines/fiji/runtime.lock.json)に、公式の配布元の URL、版、SHA-256、ライセンス識別子、上流のソースを記録している。ZIP 版は導入時に取得し、インストーラーは同じファイルを同梱する。導入時には、入ったすべての jar と JDK のハッシュの一覧を checkout の外に書き出す。デプロイの記録と一緒に保管する。

| コンポーネント | 用途 | ライセンス |
|---|---|---|
| Fiji（2026-09-29 版） | ImageJ の実行基盤 | 複数のライセンス（Fiji 本体は GPL-3.0）。アーカイブと各 jar の表示を保持する |
| Java 21（Azul Zulu 21.0.7） | Fiji の実行（Fiji に同梱） | GPL-2.0 WITH Classpath-exception-2.0。OpenJDK の配布物の表示に従い、Apache-2.0 と表示し直さない |
| StarDist 0.3.0 | 核の 2D 分割 | BSD-3-Clause（[ソース](https://github.com/stardist/stardist-imagej/blob/master/LICENSE.txt)） |
| 学習済みモデル `dsb2018_heavy_augment` | 蛍光核用の重み（StarDist の jar に同梱） | BSD-3-Clause（[モデルのリポジトリ](https://github.com/stardist/stardist-models/blob/master/LICENSE.txt)）。ZIP の SHA-256 を固定 |
| CSBDeep 0.6.0 | ニューラルネットの実行 | BSD-2-Clause |
| ImageJ TensorFlow 1.1.9 | ImageJ と TensorFlow の連携 | BSD-2-Clause |
| TensorFlow Java 1.15.0 | CPU 推論 | Apache-2.0 |
| MorphoLibJ 1.6.5 | 連結成分の処理 | LGPL-3.0-or-later（jar の POM で確認） |
| Clipper 6.4.2（Java 版） | StarDist の多角形演算 | BSL-1.0（[上流](https://github.com/lightbringer/clipper-java)） |
| Protobuf Java 3.25.8 | TensorFlow のグラフのメタデータ | BSD-3-Clause |
| Bio-Formats | CZI の変換と画像形式の読み込み | GPL と BSD の部分を含む（[OME の方針](https://www.openmicroscopy.org/licensing/)） |

論文の Methods では、必要に応じて ImageJ/Fiji、StarDist、CSBDeep、MorphoLibJ を引用する。核のモデルの学習領域は、核小体の検出精度や個別の実験への適合を保証しない。

### Cellpose と重み

モデルは、ソフトウェア、使う重み、その基盤モデル、学習・評価データの 4 つを分けて記録する。有償の推論、再配布、追加学習も、それぞれ別に扱う。ソフトウェアのライセンスは、別に配布される重みやデータセットのライセンスを決めない。現在の構成と発展の方針は[解析モデルの選定と発展方針](segmentation-models.ja.md)にある。以下の根拠は 2026-10-29 に確認した。

| 対象 | 根拠 | 扱い |
|---|---|---|
| Cellpose 4.2.1.1 | PyPI の公式 wheel の `cellpose-4.2.1.1.dist-info/licenses/LICENSE` に、HHMI の著作権表示と BSD-3-Clause の 3 条件がある。wheel の SHA-256 は `6c5c5159fd459115bee390ffb01d94d5e1006b97c211bf3c1a7b37d5395a1a13`（[PyPI の記録](https://pypi.org/pypi/cellpose/4.2.1.1/json)と一致） | 著作権表示・条件・免責を保持し、名前を推奨に使わない条項を守る。パッケージの分類子や README のバッジより、配布物の本文を優先する |
| `cpsam_v2`（公式の重み） | 固定したリビジョンの[モデルカード](https://huggingface.co/mouseland/cellpose-sam/blob/7c61431b5fbb078f3296754bd15d9f51b320f837/README.md)が `bsd-3-clause` を宣言する。[実行環境の記録](../engines/cellpose/runtime.lock.json)でリビジョン・サイズ・SHA-256 を固定 | ソフトウェアのライセンスとは別に記録する。CPU と GPU で同じ重みを使う |
| 追加学習した NCL 用の重み | [Genellect/Cytellect のリビジョン 7670daa1](https://huggingface.co/Genellect/Cytellect/tree/7670daa1edbfcb3d4611c9e053766d91f6125e74) で、375 回・750 回更新の重み、来歴の JSON、BSD-3-Clause のモデルカード、`LICENSE.cellpose`、`NOTICE.md` を公開 | 上流の表示と、追加学習で重みを変更した旨を保持する。重みごとにハッシュ・データの許可・評価の記録を結び付ける。製品の既定の解析にはまだ組み込んでいない |
| SAM と推論の依存 | SAM ViT-L は [Cellpose のモデル文書](https://cellpose.readthedocs.io/en/latest/models.html)が示す。[CPU](../engines/cellpose/requirements.lock) と [GPU](../engines/cellpose/requirements-cuda.lock) の依存はロックファイルで固定 | Segment Anything（Apache-2.0）や PyTorch を含む依存の表示を、組み立てた実行環境ごとに保持する |
| 上流の学習データ | [Cellpose の README（コミット a54cb488）](https://github.com/MouseLand/cellpose/blob/a54cb48849b7e225a81e8e43dcb042d42427f543/README.md)が、モデルを CC BY-NC のデータで学習したと記す | 重みの宣言と並べて記録する。データの条件と重みに付与されたライセンスは別の問題として扱い、SaaS の権利確認で選んだ重みとの関係を整理する |
| Cytellect の学習・評価データ | 公開画像は[登録簿](../fixtures/public/allowlist.json)で管理する。研究室のデータは[チーム開発ルール](team-development.md#6-研究データの扱い)に従う | 評価・学習・共有・公開の許可を別々に記録する。研究画像を利用できることは、学習や公開の許可を意味しない |

`scripts/cellpose_setup.py` は、重みのサイズと SHA-256、runner と依存のロックのハッシュを照合する。依存はハッシュ必須で導入し、重みは解析の前の明示的なセットアップ・ビルドで取得する。実行環境の試験がこの固定を確かめる。これらの検査は実行を確認済みの成果物に結び付けるもので、ライセンスの解釈は採用の記録で行う。

### 候補モデルのライセンス

選定の目安で、実行環境には加えていない。採用するときに、そのリリースと重みの条件を記録する。

| 候補 | ソフトウェアの根拠 | 重みと SaaS での採用の道筋 |
|---|---|---|
| StarDist 3D | [BSD-3-Clause](https://github.com/stardist/stardist/blob/main/LICENSE.txt) | 3D の重みを選ぶか、許可されたデータで学習する。現在の 2D の `dsb2018_heavy_augment` の記録は、3D の重みの記録の代わりにならない |
| microSAM | [MIT](https://github.com/computational-cell-analytics/micro-sam/blob/master/LICENSE) | [公式のモデル一覧](https://computational-cell-analytics.github.io/micro-sam/micro_sam.html)から LM または EM の重みを選び、その条件・基盤モデルの来歴・商用の推論と配布の許可を記録する |
| nnU-Net | [Apache-2.0](https://github.com/MIC-DKFZ/nnUNet/blob/master/LICENSE) | 権利を管理したデータで学習する枠組みとして使う。できた重みの条件を記録し、外部から受け取る重みは別に確認する |
| CellposeDINO | Cellpose のライセンスと、DINO 部分の [DINOv3 License](https://github.com/facebookresearch/dinov3/blob/main/LICENSE.md) | 選んだ派生物の重みの条件を、DINOv3 の利用・再配布・帰属の条件と合わせて確認する。Cellpose のライセンスだけで全体を BSD と判断しない |
| CellSAM | [Apache-2.0](https://github.com/vanvalenlab/cellSAM/blob/master/LICENSE) | [認証付きの配布](https://github.com/vanvalenlab/cellSAM/blob/master/cellSAM/_auth.py)で別の資産を受け取る。商用で採用する前に、その版の利用条件と重みのライセンスを記録する |
| Omnipose | [NonCommercial License](https://github.com/kevinjohncutler/omnipose/blob/main/LICENSE) | 商用の SaaS で使うには、University of Washington CoMotion から商用の権利を得る必要がある。権利を得るまで、商用の既定のモデルには含めない |
| Big-FISH のスポット検出 | [BSD-3-Clause](https://github.com/fish-quant/big-fish/blob/master/LICENSE) | ソフトウェアと依存の表示を保持する。学習済みの重みではなく手法として扱い、後から加える分割の重みは別の資産として記録する |

### SaaS で採用する手順

1. **成果物を特定する。** 版、固定したソースの URL・リビジョン、SHA-256、モデルの用途、基盤の重み、依存、デプロイの形態を記録する。
2. **用途ごとに権利を確かめる。** ソフトウェア・重み・データのライセンス本文と取得日を記録し、有償の推論、再配布、改変、追加学習、公開を別々に評価する。宣言が食い違う場合や許諾が明確でない場合は、対象の成果物と用途を特定したうえで、権利者または専門家に確認する。
3. **配布物を整える。** 著作権表示と帰属を保持し、含めたライセンスが求める場合はソースと再リンクの手段を用意する。ネットワーク越しの提供に条件があるライセンスはその条件を確認する。ホスティングは、ライセンスの義務を一律に免除しない。
4. **判断を記録する。** 意図する商用利用をプロダクトオーナーが承認し、根拠と追加の契約を記録する。リリースの記録で、その判断をモデルと実行環境のハッシュに結び付ける。重みや配布の形態が変われば、改めて確認する。
5. **顧客のデータを守る。** SaaS では、サービスとしての処理、任意の学習、モデルの公開を区別する。テナントの分離、保存期間、削除、委託先、データの所在を、利用規約とデータ処理の取り決めで定める。顧客のデータで学習するのは、その目的の許可がある場合に限る。

### モデルの受入記録

根拠の不足と残りの作業を記録する。README とプロダクトの方針は機能と方向性を示し、リリースの条件と確認の状況はこの節と [roadmap](roadmap.md) が持つ。

| 項目 | 確認した根拠 | 次の判断・実装 |
|---|---|---|
| 現在の Cellpose のソフトウェアと重み | wheel のライセンスとハッシュ、固定したモデルカードの BSD-3-Clause の宣言、実行環境のハッシュの検査 | wheel のライセンスの根拠をリリースの一覧と一緒に保管する。実行環境の記録のライセンスの参照先は、現在は上流の `main` を指す |
| Cellpose の商用 SaaS での権利 | ソフトウェアと重みの BSD-3-Clause の宣言と、上流の学習データについての CC BY-NC の記述をどちらも記録済み | 有償の推論、重みの再配布、追加学習した派生物について、権利者の説明または法的な評価を得て記録する。この評価はまだ完了していない |
| 分離した Cellpose の実行環境 | CPU・CUDA の依存のロックファイルと成果物のハッシュを固定 | リリースの SBOM と表示の収集を、分離した Cellpose の環境と重みにも広げる。現在の Python の一覧は、CI で動く環境だけを対象にする |
| 拡張の候補 | 上の表の公式の機能とソフトウェアのライセンス | 重みを特定し、重み・基盤・データの条件を記録し、独立した実験回で評価してから採用を判断する |
| Cytellect の追加学習 | NCL の重みと来歴・表示のファイルを、上記のリビジョンで公開済み | 製品のリリースに組み込むときに、それらの記録と、データの利用・公開の許可、オーナーのリリースの判断を合わせて保管する。以後の追加学習も同じ構成で記録する |

### CI での確認

- `scripts/sbom.py` は、導入済みの Python 環境、Web の依存の表示、Fiji の固定記録、Windows の Python・Tcl/Tk の構成を一覧にし、ロックファイルのハッシュを添える。Python は `License-Expression`、`License` の本文、ライセンスの分類子、ライセンス表示のファイル（パス・SHA-256・サイズ）を記録する。分類子だけの宣言も根拠として扱い、あいまいな `BSD License` を特定の SPDX 識別子に置き換えない。
- 宣言も表示もない Python パッケージがあると CI は失敗する。Web は直接の依存のライセンス本文を必須とし、pnpm のストアから表示を集める。どちらも開発用の依存を含む。
- Python の脆弱性の監査（`pip-audit --local --format cyclonedx-json`）が、CycloneDX 形式の SBOM を出力する。監査が成功した場合だけ保存する。
- CI は、SBOM、依存の一覧、Web の表示、秘密情報の走査の要約を 7 日間保存する。生の検出結果、ソースの行、作者、研究データ、アプリのログはアップロードしない。
- これらは根拠がそろっていることの確認で、ライセンスの法的な適合性の判断ではない。GPL・LGPL を含む配布物の確認の代わりにもならない。

### Windows 版の実行環境

- セットアップは、Astral の uv 0.12.2（MIT OR Apache-2.0）を公式のリリースから取得する。ZIP の SHA-256 は `scripts/local_setup.ps1` で固定している。
- Python は、PSF の公式の Python 3.14.8（x64 ZIP）と、同じリリースの MSI に含まれる Tcl/Tk 9.0.4 から組み立てる。入力と派生物は[構成の記録](windows-runtime.md)と記録ファイルで特定する。PSF と Tcl/Tk のライセンス本文と、Vimix アイコンの CC BY-SA 4.0 の帰属を保持する。PSF が認証した配布物でも、Apache-2.0 だけでまとめた配布物でもない。
- プロジェクトの wheel と依存は、記録したハッシュで導入する。

### Web サイトの部品と素材

次の COMPASS の部品は、著作権者の明示的な許可を得て Cytellect 用に改変した。元は `genellect/compass` のコミット `4805fb6df9e5a0bd267aef9cfa440174ccac5fb1`。元の著作権と改変の表示はソースファイルに残している。この許可は、COMPASS のリポジトリのライセンスや、その第三者の素材の条件を変えない。

| Cytellect のファイル | COMPASS の元のファイル | 改変の内容 |
|---|---|---|
| `ProductMenu.tsx` | `founder/MobileExternalMenu.tsx` | 外側のクリック、Escape、フォーカスの復元。製品のナビゲーション |
| `OpticalHero.tsx`、`optical-scene-engine.ts` | `founder/ProductSculpture.tsx`、`founder/product-sculpture-engine.ts` | 表示時の WebGL の初期化、世代の確認、照明の環境、描画資源の明示的な解放。Cytellect の Blender の光学背景 |
| `product.module.css` | `founder/founder.module.css` | ヘッダー、ナビゲーション、本文の組版を Cytellect の構成に合わせた |

## English

Cytellect's own code is licensed under Apache-2.0. That license does not replace the licenses of Fiji, Java, plugins, model weights, dependencies or datasets; each component keeps its own license.

### Distribution contents

| Distribution | Third-party components |
|---|---|
| Repository | Installation recipes, lockfiles and hash records only. No third-party runtimes or pretrained weights |
| Windows release (setup ZIP) | Source, the built Web assets, Web dependency license texts (`THIRD_PARTY_WEB_NOTICES.txt`), `LICENSE.cellpose.txt` and the public-image register. Python, packages and Fiji are downloaded from official sources during setup and verified by hash. Cellpose is not installed on the PC; it runs on the cloud GPU |
| Windows installer (`Cytellect-Setup-<version>.exe`) | The ZIP contents plus unmodified official distributions of Python 3.14, the locked Python packages (wheels), uv and Fiji with its JDK and plugins. `licenses/THIRD_PARTY_BUNDLED.txt` and `licenses/bundled-components.json` list each component's license, the SHA-256 of the bundled file and where its source is; the license texts inside the wheels are placed in `licenses/wheels/`. For every component whose license requires source, the source of exactly the bundled version is attached to the same release as `Cytellect-<version>-gpl-sources.zip`; for the 42 whose source cannot be fetched, only the upstream source location is given ([corresponding source](#corresponding-source-for-gpl-and-similar-licenses)). The installer itself carries no source. These files are installed under `licenses/` and listed with hashes in the build receipt (`Cytellect-Setup-<version>.json`). The Fiji, JDK, jar and Python license texts stay in the installed `runtimes/` |
| Docker release | Built on the user's machine. The worker image contains Fiji, the Cellpose runtime and the `cpsam_v2` weights obtained at build time |
| GPU image (GHCR) | The Cellpose runtime, the `cpsam_v2` weights and `engines/cellpose` (including `LICENSE.cellpose.txt`) |

When distributing an image or package, retain the copyright and license notices of what was actually assembled, and provide corresponding source and relinking materials where included GPL/LGPL components require them (for the Windows installer, as in the next section).

### Corresponding source for GPL and similar licenses

By the owner's decision (2026-10-30), for every component of the Windows installer whose license requires source with the binary (GPLv2, GPLv3, LGPL, AGPL, MPL, EPL, CDDL and similar), CI attaches the complete source of exactly the bundled version to the release as `Cytellect-<version>-gpl-sources.zip`. No written offer is made and no notice is sent. For the components whose source cannot be fetched automatically, only the upstream source location is given, as in [the table below](#components-without-attached-source).

| Stage | What happens |
|---|---|
| Enumeration | Derived mechanically from the bundled bytes; there is no hand-written list. Each jar of the Fiji archive and each plugin is classified by the licenses of its embedded Maven POM, else the published POM (following parents), else its own license files. Coordinates come from `pom.properties`, else from a Maven search by the jar's SHA-1. Executables and libraries outside the JDK are included. The JDK is identified by its `release` file. Wheels are classified by their metadata and the `License:` lines of the license files of the libraries they vendor (SPDX `OR` takes the alternative without an obligation; `WITH GCC-exception` carries none). A component whose license cannot be determined is treated as requiring source |
| Pinning | [`engines/fiji/corresponding-source.lock.json`](../engines/fiji/corresponding-source.lock.json) records, for every jar, executable and plugin of the bundled Fiji and its JDK, the SHA-256, license evidence, obligation and the source's URL, SHA-256 and size. A jar's source is the most exact one available, in this order: (1) the `-sources.jar` (SciJava Maven repository, Maven Central) beside a published jar that is byte-identical to the bundled one; (2) the GitHub archive of the commit the jar records it was built from (`Implementation-Build`); (3) the `-sources.jar` of the release version the jar declares in its own `pom.properties` (same version, not byte-identical). The lock records which in `source.kind`. After a change of the Fiji pins (`runtime.lock.json`), regenerate it with `python scripts/corresponding_source.py lock --cache <outside the checkout>`. Wheel sources are the sdists that `uv.lock` pins |
| Download and attachment | The release workflow (`local-release.yml`) runs `build_windows_installer.py build --corresponding-source`. The build checks that the obligations derived from the bundled bytes match the lock and downloads each source against its pinned SHA-256, retrying transient failures. A component that requires source without a pinned one passes only when [`engines/fiji/source-exceptions.json`](../engines/fiji/source-exceptions.json) lists it with the same SHA-256, a reason and its upstream source location. An unlisted component, a different SHA-256, or an exception that no longer matches the bundle and the lock fails the build |
| Records | The installer's `licenses/THIRD_PARTY_BUNDLED.txt`, `bundled-components.json` and `corresponding-source.json` name the asset and its SHA-256, and each component's member and source SHA-256. A component without attached source is listed with its license (or that it is undetermined), the reason and the upstream source location (`not_attached_components` in `corresponding-source.json`). The asset's `manifest.json` lists the bundled file's SHA-256, the license evidence, the source's URL and SHA-256, and for the components without attached source the reason and the upstream location |
| Stopping distribution | Without the asset, or when its hash differs from the receipt, the workflow creates no draft release. If the asset is missing from the created draft, it is uploaded again, and otherwise the draft is deleted |

CI builds that only exercise the installer (`windows-installer` in `ci.yml`) collect no source; their `licenses/` say that they must not be distributed.

With the current pins (Windows Fiji archive 2026-09-29), 172 of the 676 bundled jars, executables and plugins require source and 42 have a license that cannot be determined. Of these 214 and the JDK, 173 sources (about 102 MB) are pinned and attached.

#### Components without attached source

By the owner's decision of 2026-10-30, the following 42 components, whose source cannot be fetched automatically, are bundled too, and only their license and upstream source location are given: 16 with no public source for the bundled bytes (the JDK among them), 1 whose source host is unreachable, and 25 with an undetermined license. The authoritative list is [`engines/fiji/source-exceptions.json`](../engines/fiji/source-exceptions.json), which also holds each component's SHA-256 and the detailed reason. Upstream locations carry a tag or version where one is known. When a change of the Fiji pins changes these components, the release build stops until the list is reviewed.

Remaining risk: for these 42 components the release holds no source of the bundled bytes (and for 25 the license terms have not been confirmed), so if upstream moves or withdraws that version, a recipient cannot obtain the source from the location given.

| Component | License | Reason | Upstream source location |
|---|---|---|---|
| `datasets-0.8.1906.jar`, `grDevices-0.8.1906.jar`, `graphics-0.8.1906.jar`, `methods-0.8.1906.jar` | Part of R 2.14.2 | no public source for the bundled bytes | <https://github.com/bedatadriven/renjin/tree/v0.8.1906> (v0.8.1906) |
| `java3d-core-1.7.2.jar` | GPLv2 with Classpath exception | no public source for the bundled bytes | <https://github.com/jogamp/java3d-core/tree/v1.7.2-final> (v1.7.2-final) |
| `jffi-1.3.13-native.jar` | GNU Lesser General Public License version 3; The Apache Software License, Version 2.0 | no public source for the bundled bytes | <https://github.com/jnr/jffi/tree/jffi-1.3.13> (jffi-1.3.13) |
| `vecmath-1.7.2.jar` | GPLv2 with Classpath exception | no public source for the bundled bytes | <https://github.com/jogamp/vecmath/tree/v1.7.2-final> (v1.7.2-final) |
| `ffmpeg-6.1.1-1.5.10-windows-x86_64.jar` | Apache License, Version 2.0; GNU General Public License (GPL) version 2, or any later version; GPLv2 with Classpath exception | no public source for the bundled bytes | <https://github.com/bytedeco/javacpp-presets/tree/1.5.10> (1.5.10), <https://github.com/FFmpeg/FFmpeg/tree/n6.1.1> (n6.1.1) |
| `javafx-base-23.0.2-win.jar`, `javafx-fxml-23.0.2-win.jar`, `javafx-graphics-23.0.2-win.jar`, `javafx-media-23.0.2-win.jar`, `javafx-web-23.0.2-win.jar` | GPLv2+CE | no public source for the bundled bytes | <https://github.com/openjdk/jfx23u/tree/23.0.2-ga> (23.0.2-ga) |
| `openblas-0.3.26-1.5.10-windows-x86_64.jar` | Apache License, Version 2.0; GNU General Public License (GPL) version 2, or any later version; GPLv2 with Classpath exception | no public source for the bundled bytes | <https://github.com/bytedeco/javacpp-presets/tree/1.5.10> (1.5.10), <https://github.com/OpenMathLib/OpenBLAS/tree/v0.3.26> (v0.3.26) |
| `opencv-4.9.0-1.5.10-windows-x86_64.jar` | Apache License, Version 2.0; GNU General Public License (GPL) version 2, or any later version; GPLv2 with Classpath exception | no public source for the bundled bytes | <https://github.com/bytedeco/javacpp-presets/tree/1.5.10> (1.5.10), <https://github.com/opencv/opencv/tree/4.9.0> (4.9.0) |
| JDK (Azul Zulu 21.0.7, `zulu21.42.19-ca-jdk21.0.7-win_x64`) | GPL-2.0-only WITH Classpath-exception-2.0 | no public source for the bundled bytes | <https://github.com/openjdk/jdk21u/tree/jdk-21.0.7+6> (jdk-21.0.7+6) |
| `fiji-2.18.1-SNAPSHOT.jar` | GNU General Public License v3+ | source host unreachable | <https://codeload.github.com/fiji/fiji/tar.gz/c691dc761719086b49a9f927e77d744ae4e5a816> (c691dc761719086b49a9f927e77d744ae4e5a816) |
| `JWlz-1.4.0.jar` | undetermined | license undetermined | <https://github.com/ma-tech/Woolz> (version 1.4.0) |
| `bcprov-jdk18on-1.78.1.jar` | undetermined | license undetermined | <https://github.com/bcgit/bc-java/tree/r1rv78v1> (r1rv78v1) |
| `blas-0.8.jar` | undetermined | license undetermined | <https://maven.scijava.org/content/groups/public/org/netlib/blas/0.8/> (version 0.8), <https://www.netlib.org/java/f2j/> |
| `f2jutil-0.8.jar` | undetermined | license undetermined | <https://maven.scijava.org/content/groups/public/org/netlib/f2jutil/0.8/> (version 0.8), <https://www.netlib.org/java/f2j/> |
| `grpc-grpclb-1.75.0.jar` | undetermined | license undetermined | <https://github.com/grpc/grpc-java/tree/v1.75.0> (v1.75.0) |
| `jhotdraw-7.6.0.jar` | undetermined | license undetermined | <https://maven.scijava.org/content/groups/public/org/jhotdraw/jhotdraw/7.6.0/> (version 7.6.0) |
| `jpedalSTD-2.80b11.jar` | undetermined | license undetermined | <https://maven.scijava.org/content/groups/public/org/jpedal/jpedalSTD/2.80b11/> (version 2.80b11) |
| `jtransforms-2.4.jar` | undetermined | license undetermined | <https://maven.scijava.org/content/groups/public/edu/emory/mathcs/jtransforms/2.4/> (version 2.4) |
| `lapack-0.8.jar` | undetermined | license undetermined | <https://maven.scijava.org/content/groups/public/org/netlib/lapack/0.8/> (version 0.8), <https://www.netlib.org/java/f2j/> |
| `mines-jtk-20151125.jar` | undetermined | license undetermined | <https://github.com/dhale/jtk> (version 20151125), <https://maven.scijava.org/content/groups/public/edu/mines/mines-jtk/20151125/> (version 20151125) |
| `netlib-java-0.9.3-renjin-patched-2.jar` | undetermined | license undetermined | <https://maven.scijava.org/content/groups/public/org/netlib/netlib-java/0.9.3-renjin-patched-2/> (version 0.9.3-renjin-patched-2) |
| `object-inspector-0.1.jar` | undetermined | license undetermined | <https://github.com/sbridges/object-inspector> (version 0.1), <https://maven.scijava.org/content/groups/public/com/github/sbridges/object-inspector/object-inspector/0.1/> (version 0.1) |
| `perfmark-api-0.27.0.jar` | undetermined | license undetermined | <https://github.com/perfmark/perfmark/tree/v0.27.0> (v0.27.0) |
| `scala3-compiler_3-3.3.0.jar`, `scala3-interfaces-3.3.0.jar`, `scala3-library_3-3.3.0.jar`, `tasty-core_3-3.3.0.jar` | undetermined | license undetermined | <https://github.com/scala/scala3/tree/3.3.0> (3.3.0) |
| `swingx-1.6.1.jar` | undetermined | license undetermined | <https://github.com/ebourg/swingx> (version 1.6.1) |
| `flimlib-2.1.1-natives-windows_64.jar` | undetermined | license undetermined | <https://github.com/flimlib/flimlib/tree/flimlib-2.1.1> (flimlib-2.1.1) |
| `gluegen-rt-2.6.0-natives-windows-amd64.jar` | undetermined | license undetermined | <https://github.com/jogamp/gluegen/tree/v2.6.0> (v2.6.0) |
| `javafx-controls-23.0.2-win.jar`, `javafx-swing-23.0.2-win.jar` | undetermined | license undetermined | <https://github.com/openjdk/jfx23u/tree/23.0.2-ga> (23.0.2-ga) |
| `jogl-all-2.6.0-natives-windows-amd64.jar` | undetermined | license undetermined | <https://github.com/jogamp/jogl/tree/v2.6.0> (v2.6.0) |
| `xerbla-0.8.jar` | undetermined | license undetermined | <https://maven.scijava.org/content/groups/public/org/netlib/xerbla/0.8/> (version 0.8), <https://www.netlib.org/java/f2j/> |
| `blosc1.dll` | undetermined | license undetermined | <https://github.com/Blosc/c-blosc/tree/v1.18.1> (v1.18.1) |

### Fiji and nuclear detection

The [Fiji runtime manifest](../engines/fiji/runtime.lock.json) records official URLs, versions, SHA-256, license identifiers and upstream sources. The ZIP downloads these files during setup; the installer bundles the same files. Setup writes a hash inventory of every installed jar and the JDK outside the checkout; keep it with deployment records.

| Component | Purpose | License |
|---|---|---|
| Fiji (2026-09-29 archive) | ImageJ platform | Multiple licenses (Fiji itself GPL-3.0); preserve the archive's and each jar's notices |
| Java 21 (Azul Zulu 21.0.7) | Runs Fiji (bundled with Fiji) | GPL-2.0 WITH Classpath-exception-2.0; keep the OpenJDK distribution notices and do not relabel as Apache-2.0 |
| StarDist 0.3.0 | 2D nuclear segmentation | BSD-3-Clause ([source](https://github.com/stardist/stardist-imagej/blob/master/LICENSE.txt)) |
| Pretrained model `dsb2018_heavy_augment` | Fluorescent nuclei weights (embedded in the StarDist jar) | BSD-3-Clause ([model repository](https://github.com/stardist/stardist-models/blob/master/LICENSE.txt)); ZIP SHA-256 pinned |
| CSBDeep 0.6.0 | Neural network execution | BSD-2-Clause |
| ImageJ TensorFlow 1.1.9 | ImageJ/TensorFlow integration | BSD-2-Clause |
| TensorFlow Java 1.15.0 | CPU inference | Apache-2.0 |
| MorphoLibJ 1.6.5 | Connected components | LGPL-3.0-or-later (from the artifact POM) |
| Clipper 6.4.2 (Java port) | StarDist polygon operations | BSL-1.0 ([upstream](https://github.com/lightbringer/clipper-java)) |
| Protobuf Java 3.25.8 | TensorFlow graph metadata | BSD-3-Clause |
| Bio-Formats | CZI conversion and format support | GPL and BSD components ([OME policy](https://www.openmicroscopy.org/licensing/)) |

Cite ImageJ/Fiji, StarDist, CSBDeep and MorphoLibJ in Methods as appropriate. The nuclear model's training domain does not establish nucleolar accuracy or fitness for a particular experiment.

### Cellpose and weights

Each model is recorded as four assets: software, the selected weights, the base model and the training/evaluation data. Paid inference, redistribution and fine-tuning are assessed separately. A software license does not license separately distributed weights or datasets. The current architecture and direction are in the [model strategy](segmentation-models.ja.md) (Japanese). The evidence below was checked on 2026-10-29.

| Asset | Evidence | Handling |
|---|---|---|
| Cellpose 4.2.1.1 | The official PyPI wheel's `cellpose-4.2.1.1.dist-info/licenses/LICENSE` carries the HHMI copyright and the three BSD-3-Clause conditions. Wheel SHA-256 `6c5c5159fd459115bee390ffb01d94d5e1006b97c211bf3c1a7b37d5395a1a13` matches [PyPI's record](https://pypi.org/pypi/cellpose/4.2.1.1/json) | Preserve the notice, conditions and disclaimer, and observe the non-endorsement clause. The artifact's text takes precedence over classifiers or README badges |
| `cpsam_v2` (official weights) | The [model card at the pinned revision](https://huggingface.co/mouseland/cellpose-sam/blob/7c61431b5fbb078f3296754bd15d9f51b320f837/README.md) declares `bsd-3-clause`; the [runtime manifest](../engines/cellpose/runtime.lock.json) pins revision, size and SHA-256 | Recorded separately from the software license. CPU and GPU use the same weights |
| NCL fine-tuned weights | [Genellect/Cytellect revision 7670daa1](https://huggingface.co/Genellect/Cytellect/tree/7670daa1edbfcb3d4611c9e053766d91f6125e74) publishes 375- and 750-update weights, provenance JSON, a BSD-3-Clause card, `LICENSE.cellpose` and `NOTICE.md` | Preserve upstream notices and the statement that fine-tuning modified the weights; bind each checkpoint to its hash, data permissions and evaluation record. Not yet used by the product's default analysis |
| SAM and inference dependencies | SAM ViT-L is identified by the [Cellpose model documentation](https://cellpose.readthedocs.io/en/latest/models.html); [CPU](../engines/cellpose/requirements.lock) and [GPU](../engines/cellpose/requirements-cuda.lock) dependencies are locked | Retain notices of the installed dependencies, including Segment Anything (Apache-2.0) and PyTorch, with each assembled runtime |
| Upstream training data | The [Cellpose README at commit a54cb488](https://github.com/MouseLand/cellpose/blob/a54cb48849b7e225a81e8e43dcb042d42427f543/README.md) states that its models were trained on CC-BY-NC data | Recorded next to the weights' declaration. Data terms and the license granted for weights are distinct; the SaaS rights review resolves their relationship for the selected weights |
| Cytellect training/evaluation data | Public images are managed in the [register](../fixtures/public/allowlist.json); laboratory data follows the [team rules](team-development.md#6-research-data) | Record permission for evaluation, training, sharing and publication separately. Access to a research image does not authorize training or publication |

`scripts/cellpose_setup.py` verifies the weights' size and SHA-256 and the runner/dependency lock hashes. Dependencies are installed with required hashes, and weights are obtained during explicit setup or build before analysis. Runtime tests check this identity. These checks bind execution to the reviewed artifacts; license interpretation belongs in the adoption record.

### Candidate model licensing

A selection guide; none of these is in the deployed runtime. Exact release and weight terms are recorded when a candidate is chosen.

| Candidate | Software evidence | Weights and SaaS adoption route |
|---|---|---|
| StarDist 3D | [BSD-3-Clause](https://github.com/stardist/stardist/blob/main/LICENSE.txt) | Select 3D weights or train on authorized data. The 2D `dsb2018_heavy_augment` record does not substitute for a 3D model record |
| microSAM | [MIT](https://github.com/computational-cell-analytics/micro-sam/blob/master/LICENSE) | Choose an LM or EM checkpoint from the [official catalog](https://computational-cell-analytics.github.io/micro-sam/micro_sam.html); record its terms, base-model provenance and commercial inference/distribution permissions |
| nnU-Net | [Apache-2.0](https://github.com/MIC-DKFZ/nnUNet/blob/master/LICENSE) | Use as a training framework with rights-controlled data. Record the resulting model's terms; review any external weights separately |
| CellposeDINO | Cellpose's license plus the [DINOv3 License](https://github.com/facebookresearch/dinov3/blob/main/LICENSE.md) for DINO materials | Review the derivative's weight terms together with DINOv3's use, redistribution and attribution conditions; do not classify the whole stack as BSD from Cellpose's license alone |
| CellSAM | [Apache-2.0](https://github.com/vanvalenlab/cellSAM/blob/master/LICENSE) | Its [authenticated distribution](https://github.com/vanvalenlab/cellSAM/blob/master/cellSAM/_auth.py) supplies separate assets; record their access terms and weight license before commercial adoption |
| Omnipose | [NonCommercial License](https://github.com/kevinjohncutler/omnipose/blob/main/LICENSE) | Commercial SaaS use requires rights from University of Washington CoMotion; excluded from the default commercial set until obtained |
| Big-FISH spot detection | [BSD-3-Clause](https://github.com/fish-quant/big-fish/blob/master/LICENSE) | Preserve software and dependency notices. A method, not a pretrained checkpoint; record any added segmentation weights as separate assets |

### SaaS adoption procedure

1. **Identify the deliverable.** Record version, immutable source URL/revision, SHA-256, purpose, base weights, dependencies and deployment mode.
2. **Establish rights for each use.** Record license texts and retrieval dates for software, weights and data, and assess paid inference, redistribution, modification, fine-tuning and publication separately. Resolve conflicting declarations or unclear grants with the rights holder or qualified counsel, tied to a specific artifact and use.
3. **Prepare the distribution.** Preserve notices and attribution, and provide source and relinking materials where included licenses require them. Review network-service conditions where they apply; hosting is not a blanket exemption.
4. **Record the decision.** The product owner approves the intended commercial use, citing the evidence and any additional agreement. Release records bind the decision to model and runtime hashes. A different checkpoint or distribution mode is reviewed again.
5. **Protect customer data.** Distinguish service processing from optional training and public model release. Define tenant isolation, retention, deletion, subprocessors and data location in the service terms and data-processing arrangements. Train on customer data only with permission for that purpose.

### Model adoption review record

Evidence gaps and follow-up work. README and the product strategy describe capabilities and direction; release conditions and review status live here and in the [roadmap](roadmap.md).

| Item | Verified evidence | Next decision or implementation |
|---|---|---|
| Current Cellpose software and weights | Wheel license and hash; pinned model card declaring BSD-3-Clause; enforced runtime hashes | Keep the wheel license evidence with the release inventory. The manifest's code-license source currently points to upstream `main` |
| Cellpose commercial SaaS rights | BSD-3-Clause software/weight declarations and the upstream CC-BY-NC training-data statement are both recorded | Obtain and record a rights-holder clarification or legal assessment covering paid inference, weight redistribution and fine-tuned derivatives. Not yet completed |
| Isolated Cellpose runtimes | CPU/CUDA dependency lockfiles and artifact hashes are pinned | Extend release SBOM and notice collection to the isolated Cellpose environments and weights. The current Python inventory covers only the CI interpreter |
| Expansion candidates | Official capability and software-license sources above | Select exact weights, record weight/base/data terms and evaluate on independent experiments before adoption |
| Cytellect fine-tunes | NCL weights and provenance/notice files are published at the revision above | When adopted in a release, keep those records with data-use/publication permissions and the owner's release decision; record later fine-tunes the same way |

### CI checks

- `scripts/sbom.py` inventories the installed Python environment, Web dependency notices, the Fiji manifest and the Windows Python/Tcl/Tk composition, with lockfile hashes. Python records keep `License-Expression`, `License` text, license classifiers and notice files (path, SHA-256, size). Classifier-only declarations count as evidence; an ambiguous `BSD License` classifier is not converted into a specific SPDX identifier.
- CI fails when a Python package has no declaration or notice. The Web collector requires license texts for direct dependencies and gathers notices from the pnpm store. Both include development dependencies.
- The Python vulnerability audit (`pip-audit --local --format cyclonedx-json`) emits a CycloneDX SBOM, retained only when the audit succeeds.
- CI keeps the SBOM, dependency inventory, Web notices and a secret-scan summary for seven days. Raw findings, source lines, author identifiers, research data and application logs are not uploaded.
- These checks establish that evidence is present; they are not a legal compatibility decision and do not replace review of a distribution that includes GPL/LGPL components.

### Windows runtime

- Setup downloads Astral uv 0.12.2 (MIT OR Apache-2.0) from the official release; the ZIP SHA-256 is pinned in `scripts/local_setup.ps1`.
- Python is composed from the official PSF Python 3.14.8 x64 ZIP and Tcl/Tk 9.0.4 from the same release's MSI. Inputs and derived assets are identified in the [composition record](windows-runtime.md) and its manifests. PSF and Tcl/Tk license texts and the Vimix icon CC-BY-SA-4.0 attribution are preserved. It is neither a PSF-certified distribution nor an Apache-only bundle.
- Project wheels and dependencies are installed by recorded hash.

### Website components and media

The following COMPASS components were adapted for Cytellect with the copyright owner's express permission, from `genellect/compass` commit `4805fb6df9e5a0bd267aef9cfa440174ccac5fb1`. Original copyright and adaptation notices remain in the source files. This permission does not change the license of the COMPASS repository or the terms of its third-party assets.

| Cytellect file | COMPASS source | Adaptation |
|---|---|---|
| `ProductMenu.tsx` | `founder/MobileExternalMenu.tsx` | Outside-click, Escape and focus restoration; product navigation |
| `OpticalHero.tsx`, `optical-scene-engine.ts` | `founder/ProductSculpture.tsx`, `founder/product-sculpture-engine.ts` | Visibility-triggered WebGL setup, generation guards, lighting environment and explicit resource disposal; Cytellect Blender optical background |
| `product.module.css` | `founder/founder.module.css` | Header, navigation and editorial typography adapted to Cytellect |
