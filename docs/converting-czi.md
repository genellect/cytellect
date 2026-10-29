# CZI をオフラインで定量用の TIFF に変換する

Zeiss の CZI を、Fiji の Bio-Formats で画素値を変えずに TIFF / OME-TIFF へ変換し、Cytellect に登録する手順。

| 項目 | 内容 |
|---|---|
| 対象 | CZI で撮影した画像を Cytellect で解析する研究者 |
| 入力の条件 | 選んだ 1 シリーズが Z=1、T=1、uint8 または uint16 のグレースケール |
| 出力 | 8/16-bit グレースケールの 2D TIFF、または対応範囲内の単一シリーズ OME-TIFF（Cytellect の通常入力） |
| 作業する場所 | 非公開のローカル環境。原画像、メタデータ、変換記録には研究情報が含まれるため、Git・公開 Issue・共有ログへ置かない |

原 CZI は上書きせず、変換後も保持する。この手順は Bio-Formats 公式の [Importer の操作](https://bio-formats.readthedocs.io/en/v8.5.0/users/imagej/load-images.html)と [Importer/Exporter の仕様](https://bio-formats.readthedocs.io/en/v8.5.0/users/imagej/features.html)に基づく。実験由来の CZI の画素忠実性を検証済みという意味ではない（[検証済みの範囲](#検証済みの範囲)）。

## 1. 変換環境を確認する

- 専用の Fiji を使い、解析中にアップデーターを実行しない。Cytellect の Windows セットアップは既存の Fiji を変更せず、専用の `runtimes/fiji-<lock hash prefix>` へ展開する。そのフォルダーの `fiji-windows-x64.exe` で GUI を開ける。開発用の構築方法は [Fiji 環境](fiji.md)を参照する。
- 変換にはローカルファイルの Importer を使い、Remote Importer や外部アップロードは使わない。
- 現在の固定 Fiji 配布物 `20260929-1417` には Bio-Formats **8.5.0**（`formats-api-8.5.0.jar`、`formats-bsd-8.5.0.jar`、`formats-gpl-8.5.0.jar`）が含まれる。JAR/JDK の一覧は専用環境の `cytellect-runtime.json`、配布物と追加依存のハッシュは[固定台帳](../engines/fiji/runtime.lock.json)で確認できる。
- 任意の既存 Fiji を使う場合は、その実バージョンも変換記録へ保存し、同じ環境として扱わない。

Bio-Formats は CZI の読み取りを提供するが、圧縮方式・マルチシーンなどの対応は入力に依存する。JPEG-XR には OS 側の追加要件もある。読めないファイルを画質を落として回避せず、原画像を保持して形式の対応を別途確認する（[公式の CZI 対応情報](https://bio-formats.readthedocs.io/en/v8.5.0/formats/zeiss-czi.html)）。

## 2. 取り込むシリーズと取得条件を確認する

1. Git 管理外の非公開フォルダーに原 CZI を置き、別の空の出力フォルダーを用意する。必要なら原 CZI の SHA-256 を記録する（例：PowerShell の `Get-FileHash -LiteralPath 'D:\PrivateStudy\input.czi' -Algorithm SHA256`）。表示内容は公開ログへ転記しない。
2. Fiji の `Plugins → Bio-Formats → Bio-Formats Importer` から原 CZI を開く。直前の設定を再利用する Windowless Importer は使わず、今回の選択肢を確認する。`Group files with similar names` は無効にし、近くの別視野を自動結合させない。
3. `Display metadata` と `Display OME-XML metadata` を表示し、シリーズ数、各シリーズの X/Y/C/Z/T、bit 深度、チャンネル名・取得情報、PhysicalSizeX/Y と単位を確認する。必要な 1 シリーズだけを選び、全シリーズの連結、サムネイル、低解像度ピラミッドは選ばない。取得装置の原記録と対応させ、シリーズ番号・名称を記録する。
4. **選んだ取得シリーズ自体が Z=1、T=1、uint8 または uint16 のグレースケールであることを確認する。** Z/T が複数、RGB 表示画像、浮動小数、モザイクの不明な空白領域、軸や系列が不明の場合はここで停止する。最初の平面だけを黙って選んだり、最大値投影して対応形式と見なしたりしない。3D・時系列・投影などの前処理は、別の解析仕様と検証が必要。

チャンネルの役割は、染色・装置設定と画像を照合して確定する。ファイル名の `c1` だけから NCL などを決めない。通常の NCL 解析は DAPI + NCL（必要なら GFP を追加）、GFP 核解析は核染色 + GFP を使う。別の核染色は実際の名称を記録する。ImageJ 画面のチャンネル位置は通常 1 始まりだが、Cytellect の OME マッピングは **0 始まり**（[Bio-Formats の位置表示](https://bio-formats.readthedocs.io/en/v8.5.0/users/imagej/options.html)）。

## 3. 画素を変えずに出力する

1. Import Options で `View stack with: Hyperstack`、`Color mode: Grayscale` を選び、`Autoscale` を無効にする。Importer の Autoscale 自体は表示範囲の変更だが、表示の変更と保存処理を混同しないため無効にする。画像の 8-bit 化、RGB Color 化、Brightness/Contrast の Apply、正規化、リサイズ、平滑化、背景減算、投影は実行しない。
2. 開いた画像の `Image → Properties` で幅・高さ、Channels/Slices/Frames、画素サイズを確認する。`Image → Type` は確認だけに使い、元の 8-bit/16-bit を維持する。
3. 使用する 2〜3 チャンネルだけの 1 シリーズであれば、`Plugins → Bio-Formats → Bio-Formats Exporter` で**新しい** `field.ome.tif` を出力する。圧縮は `Uncompressed` を選び、Z/T/channel ごとの複数ファイル分割は無効にする。JPEG などの非可逆圧縮や、表示用 RGB の保存は使わない。
4. UBF など初期解析に使わないチャンネルが含まれる場合は、`Image → Color → Split Channels` で分け、採用する各グレースケール画像を新しい名前で `File → Save As → Tiff` へ保存する。各画像が同じ X/Y、Z=T=1、元の bit 深度であることを確認する。除外したチャンネルと役割の対応を記録し、原 CZI はそのまま残す。Cytellect では「チャンネル別TIFF」で該当する入力へ割り当てる。

## 4. 再読込してから Cytellect へ登録する

1. 出力を閉じ、Bio-Formats Importer で再度開く。シリーズ数 1、同じ X/Y、採用した C の数、Z=T=1、同じ整数型、チャンネル順を確認する。空の平面、意図しない RGB、別のシリーズがないことを確かめる。
2. 元と出力の同一座標の画素値・画像統計を照合する。最初の実験では、独立した読み取りとの全画素比較も行う。見た目やファイルのバイト数だけで忠実性を判定しない。
3. PhysicalSizeX/Y が既知で等しい場合だけ、その値を µm/px へ換算して Cytellect の画素サイズ欄に入力する。現在の実装は 1 つの等方的な画素サイズを受け取り、OME の校正を自動では採用しない。値・単位が不明、または X/Y が異なる場合は欄を空にして px 単位で扱う。都合のよい値へ丸めたり、リサイズで等方化したりしない。
4. 登録時にはチャンネルの対応を明示して確認する。Cytellect の厳密な OME 読み取りは、不完全な平面・外部ファイル参照・複数シリーズなどを拒否する。拒否を回避するためにメタデータだけを書き換えず、[対応範囲](methods.md)と変換元を確認する。

入力の上限 4096×4096 とは別に、自動の核検出は両辺 2048 px 以下・総画素 2,700,000 以下。超過した画像を黙って縮小しない。

## 5. 変換記録を残す

非公開の変換記録に、次を保存する。変換後の TIFF だけでは、原 CZI の取得条件のすべてを代替できない。

- 原 CZI と出力のハッシュ
- 実際の Fiji / Bio-Formats の版
- シリーズ番号、X/Y/C/Z/T、bit 深度
- 採用・除外したチャンネルと実際の染色名
- 校正値と単位
- 変換設定と再読込の照合結果

## 検証済みの範囲

2026-10-03、上記の固定 Java 21 / Bio-Formats 8.5.0 に含まれる公式の `ImageReader` と `OMETiffWriter` で、公開 TIFF から非圧縮 OME-TIFF への変換を実行した。元と出力を Cytellect の厳密なリーダーで読み、全画素を比較している。

| 公開入力 | 型・サイズ | 比較画素数 | 差分 |
|---|---|---:|---:|
| BBBC013 A01 GFP | uint8、640×640、1ch | 409,600 | 0 |
| 4DNFI7FAWT6C | uint16、1739×1536、2ch | 5,342,208 | 0 |

Bio-Formats JAR の SHA-256：`formats-api` は `5a8b0844fcad85f026f5b9bc9aaff15692d61c2dd9c9c222adc4982db70e0d8f`、`formats-bsd` は `d5587499fda886771ceccdf63d7ce0b2f5f89d1815db35e57c31d0fcb95212a2`、`formats-gpl` は `5f1fca2cb236123a03cfdefd3495afd8385894470c225c5bca350698daa83b47`。入力の出典・利用条件は[公開 GFP 検証](public-gfp-validation.md)と[公開 NCL 検証](public-nucleolar-validation.md)にある。

これは **TIFF 読込・OME-TIFF 書込の画素保存を確認した検査**。CZI コーデック、上記の GUI 操作のすべて、未公開 CZI のチャンネル同定・校正の正しさは未検証で、実験由来の原 CZI が提供された時点で、非公開の M4 環境で確認する。独立した `bfconvert` / `showinf` コマンド群はこの Fiji 配布物に含まれていないため、同梱を前提にしたコマンドは案内しない。

## 関連文書

- [Fiji 環境](fiji.md)（英語）：固定版 Fiji の構築
- [計算仕様](methods.md)（英語）：入力の対応範囲
- [はじめての画像解析](quickstart.ja.md)：変換後の画像の登録手順
