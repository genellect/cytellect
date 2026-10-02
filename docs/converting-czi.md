# CZIをオフラインで定量用TIFFへ変換する

Cytellectの通常入力は8/16-bitグレースケールの2D TIFF、または対応範囲内の単一シリーズOME-TIFFです。CZIは、非公開のローカル環境でFijiのBio-Formatsを使って変換します。原CZIを上書きせず、変換後も保持してください。原画像、メタデータ、変換記録には研究情報が含まれるため、Git・公開Issue・共有ログへ置きません。

この手順はBio-Formats公式の[Importer操作](https://bio-formats.readthedocs.io/en/v8.5.0/users/imagej/load-images.html)と[Importer/Exporterの仕様](https://bio-formats.readthedocs.io/en/v8.5.0/users/imagej/features.html)に基づきます。実験由来CZIの画素忠実性を検証済みという意味ではありません。

## 固定環境を確認する

専用のFijiを使い、解析中にアップデーターを実行しません。CytellectのWindowsセットアップは既存のFijiを変更せず、専用の`runtimes/fiji-<lock hash prefix>`へ展開します。そのフォルダの`fiji-windows-x64.exe`でGUIを開けます。開発用の構築方法は[Fiji環境](fiji.md)を参照してください。変換はローカルファイルのImporterを使用し、Remote Importerや外部アップロードを使いません。

local.8の固定Fiji配布物`20260929-1417`にはBio-Formats **8.5.0**が含まれます。対象は`formats-api-8.5.0.jar`、`formats-bsd-8.5.0.jar`、`formats-gpl-8.5.0.jar`です。JAR/JDK一覧は専用環境の`cytellect-runtime.json`、配布物と追加依存のハッシュは[固定台帳](../engines/fiji/runtime.lock.json)で確認できます。任意の既存Fijiを使う場合はその実バージョンも変換記録へ保存し、同じ環境と扱わないでください。

Bio-FormatsはCZIの読み取りを提供しますが、圧縮方式・マルチシーン等の対応は入力に依存します。JPEG-XRにはOS側の追加要件もあります。読めないファイルのために画質を落として回避せず、原画像を保持して形式対応を別途確認します。[公式CZI対応情報](https://bio-formats.readthedocs.io/en/v8.5.0/formats/zeiss-czi.html)

## 1. 取り込むシリーズと取得条件を確認する

1. Git管理外の非公開フォルダに原CZIを置き、別の空の出力フォルダを用意します。必要なら原CZIのSHA-256を記録します。例：PowerShellの`Get-FileHash -LiteralPath 'D:\PrivateStudy\input.czi' -Algorithm SHA256`。表示内容を公開ログへ転記しません。
2. Fijiの`Plugins → Bio-Formats → Bio-Formats Importer`から原CZIを開きます。直前の設定を再利用するWindowless Importerを使わず、今回の選択肢を確認します。`Group files with similar names`は無効にし、近くの別視野を自動結合させません。
3. `Display metadata`と`Display OME-XML metadata`を表示し、シリーズ数、各シリーズのX/Y/C/Z/T、bit深度、チャンネル名・取得情報、PhysicalSizeX/Yと単位を確認します。必要な1シリーズだけを選び、全シリーズの連結、サムネイル、低解像度ピラミッドを選びません。取得装置の原記録と対応させ、シリーズ番号・名称を記録します。
4. **選んだ取得シリーズ自体がZ=1、T=1、uint8またはuint16のグレースケールであることを確認します。** Z/Tが複数、RGB表示画像、浮動小数、モザイクの不明な空白領域、軸や系列が不明の場合はここで停止します。最初の平面だけを黙って選んだり、最大値投影して対応形式と見なしたりしません。3D・時系列・投影等の前処理は別の解析仕様と検証が必要です。

チャンネルの役割は染色・装置設定と画像を照合して確定します。ファイル名の`c1`だけからNCL等を決めません。通常NCL解析はDAPI+NCL、必要ならGFPを追加し、GFP核解析は核染色+GFPを使います。別の核染色は実際の名称を記録してください。ImageJ画面のチャンネル位置は通常1始まりですが、CytellectのOMEマッピングは**0始まり**です。[Bio-Formatsの位置表示](https://bio-formats.readthedocs.io/en/v8.5.0/users/imagej/options.html)

## 2. 画素を変えずに出力する

1. Import Optionsで`View stack with: Hyperstack`、`Color mode: Grayscale`を選びます。`Autoscale`を無効にして表示条件を一定にします。ImporterのAutoscale自体は表示範囲の変更ですが、定量準備では表示変更と保存処理を混同しないため無効にします。画像の8-bit化、RGB Color化、Brightness/ContrastのApply、正規化、リサイズ、平滑化、背景減算、投影を実行しません。
2. 開いた画像の`Image → Properties`で幅・高さ、Channels/Slices/Frames、画素サイズを確認します。`Image → Type`は確認だけに使い、元の8-bit/16-bitを維持します。
3. 使用する2～3チャンネルだけの1シリーズであれば、`Plugins → Bio-Formats → Bio-Formats Exporter`で**新しい**`field.ome.tif`を出力します。圧縮は`Uncompressed`を選び、Z/T/channelごとの複数ファイル分割は無効にします。JPEG等の非可逆圧縮や、表示用RGBの保存は使いません。
4. UBFなど初期解析に使わないチャンネルが含まれる場合は、`Image → Color → Split Channels`で分け、採用する各グレースケール画像を新しい名前で`File → Save As → Tiff`へ保存します。各画像が同じX/Y、Z=T=1、元のbit深度であることを確認します。除外チャンネルと役割対応を記録し、原CZIはそのまま残します。Cytellectでは「チャンネル別TIFF」で該当する入力へ割り当てます。

## 3. 再読込してからCytellectへ登録する

出力を閉じ、Bio-Formats Importerで再度開きます。シリーズ数1、同じX/Y、採用C数、Z=T=1、同じ整数型、チャンネル順を再確認します。空平面、意図しないRGB、別のシリーズがないことを確かめます。元と出力の同一座標の画素値・画像統計を照合し、最初の実験では独立した読み取りとの全画素比較も行います。見た目やファイルのバイト数だけでは忠実性を判定しません。

PhysicalSizeX/Yが既知で等しい場合だけ、その値をµm/pxへ換算してCytellectの画素サイズ欄に入力します。現MVPは1つの等方的画素サイズを受け取り、OME校正を自動採用しません。値・単位が不明、またはX/Yが異なる場合は欄を空にしてpx単位で扱います。都合のよい値へ丸めたり、リサイズで等方化したりしません。

登録時にはチャンネル対応を明示して確認します。Cytellectの厳密なOME読み取りは、不完全な平面・外部ファイル参照・複数シリーズ等を拒否します。拒否を回避するためにメタデータだけを書き換えず、[対応範囲](methods.md)と変換元を確認してください。入力上限4096×4096とは別に、自動核検出は両辺2048px以下・総画素2,700,000以下です。超過画像を黙って縮小しません。

非公開の変換記録には、原CZI/出力のハッシュ、実Fiji/Bio-Formats版、シリーズ番号、X/Y/C/Z/T、bit深度、採用・除外チャンネル、実染色名、校正値と単位、変換設定、再読込照合結果を保存してください。変換後のTIFFだけでは原CZI取得条件のすべてを代替できません。

## 実施済み検証と未検証の境界

2026-10-03、上記の固定Java21/Bio-Formats8.5.0に含まれる公式`ImageReader`と`OMETiffWriter`を使い、公開TIFFから非圧縮OME-TIFFへの変換を実行しました。元と出力をCytellectの厳密なリーダーで読み、全画素を比較しています。

| 公開入力 | 型・サイズ | 比較画素数 | 差分 |
|---|---|---:|---:|
| BBBC013 A01 GFP | uint8、640×640、1ch | 409,600 | 0 |
| 4DNFI7FAWT6C | uint16、1739×1536、2ch | 5,342,208 | 0 |

Bio-Formats JARのSHA-256：`formats-api`は`5a8b0844fcad85f026f5b9bc9aaff15692d61c2dd9c9c222adc4982db70e0d8f`、`formats-bsd`は`d5587499fda886771ceccdf63d7ce0b2f5f89d1815db35e57c31d0fcb95212a2`、`formats-gpl`は`5f1fca2cb236123a03cfdefd3495afd8385894470c225c5bca350698daa83b47`。入力の出典・利用条件は[公開GFP検証](public-gfp-validation.md)と[公開NCL検証](public-nucleolar-validation.md)を参照してください。

これは**TIFF読込・OME-TIFF書込の画素保存を確認した検査**です。CZIコーデック、上記GUI全操作、未公開CZIのチャンネル同定・校正の正しさは未検証です。実験由来の原CZIが提供された時点で、非公開M4環境で確認します。独立した`bfconvert`/`showinf`コマンド群はこのFiji配布物に含まれていないため、同梱済みと仮定したコマンドは案内しません。
