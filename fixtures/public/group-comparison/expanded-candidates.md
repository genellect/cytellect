# 群間比較の公開実画像：調査範囲の拡張（2026-10-25）

オーナーの追加指示により、核の縮小だけでなく対照・処理の比較を対象とする。
仕様参照は `31b3c22dfc24472fdf0605ba8b308dbf1ca8f81a`。この調査・登録はデモ採用の決定ではない。
既存の [evidence.md](evidence.md) の未採用候補を消さず、新しい判断をここに記録する。

## 推薦と不足

1. **DS6a：条件付きの第一候補を維持。** 取得済み2画像とチャンネルの根拠がある。離心率と平均5-EUを別指標として記述する。独立性、処理表、NPM1による領域定義の妥当性、採用は未決定。
2. **IDR0035：新規登録候補。** DMSO / taxol の3チャンネル原TIFFを公式IDR配布から18件取得・再検証した。各群先頭視野の共通核検出も実行できた。ただし論文の細胞全体のtubulin積分強度を核内平均で代用しない。核数低下や縮小を確定したデータとは扱わない。
3. **BBBC013：既存fixtureの再利用候補。** 公開画像・核領域とFKHR-EGFP測定の既存登録がある。核移行を「核内平均が上がっただけ」で証明しない。細胞質との比を使うなら指標契約の追加が必要。3視野/試料・独立実験回の条件を満たすとは確認できず、記述デモとしての採用判断が必要。
4. DNA損傷は IDR0010、Mendeley 3z3rft4hn2.1 を次候補とする。今回の契約にないfoci検出やz集約を勝手に追加しない。

## 一次資料を確認した候補比較

| 候補 | 許諾・実験・一次資料 | 比較と現在の不足 |
|---|---|---|
| IDR0035 / BBBC021 | IDR研究メタデータ原文 `CC BY 4.0`。MCF-7、DMSO/taxol、24 h、DAPI・β-tubulin・F-actin。20×、16 bit、各well4視野。[研究メタデータ](https://github.com/IDR/idr-metadata/blob/7b258ab741f2c7362ca51f76c5df4848ff2966db/idr0035-caie-drugresponse/idr0035-study.txt)、[BBBC021](https://bbbc.broadinstitute.org/BBBC021)、[Caie 2010](https://doi.org/10.1158/1535-7163.MCT-09-1148) | 新規登録は下記。独立実験日、NA、物理校正は未確定。plate/replicate/weekを独立nに読み替えない |
| IDR0010 / Doil 2009 | 研究メタデータ原文 `CC BY 4.0`。U2OS siRNA、Hoechst33258/53BP1-Alexa488、696×520、20×NA0.8、0.465 µm/px。[研究メタデータ](https://github.com/IDR/idr-metadata/blob/7b258ab741f2c7362ca51f76c5df4848ff2966db/idr0010-doil-dnadamage/idr0010-study.txt)、[原著](https://doi.org/10.1016/j.cell.2008.12.041) | 53BP1 fociの対照正規化が表現型。53BP1をNCLと呼ばない。1遺伝子2–3siRNAは独立実験日でない。公開の遺伝子hit分類と個別wellの数値を区別。今回画像未取得、特定対照/siRNAと論文図未固定 |
| IDR0017 / Breinig | [研究メタデータ](https://github.com/IDR/idr0017-breinig-drugscreen/blob/master/idr0017-study.txt) は `CC BY-NC-ND 4.0` | 今回の許諾条件外。IDR全体をCC BYとみなさない |
| BBBC013 | [公式](https://bbbc.broadinstitute.org/BBBC013)：CC BY 3.0、Ilya Ravkin。U2OS FKHR-EGFP、PI3K阻害剤1 h、DRAQ。既存fixtureのA01/A06/A12・BMP由来TIFFは画素ハッシュ登録済み | [Carpenter 2006](https://doi.org/10.1186/gb-2006-7-10-r100) 等の解析対象。核移行と核内平均は異なる。BMP 8bit配布画像でありnative FRM強度の忠実性未確認。4反復wellを4実験日としない。今回新たな検出・論文数値再現は未実施 |
| BBBC014 | [公式](https://bbbc.broadinstitute.org/BBBC014)：CC BY 3.0、MCF7/A549、TNFα、NF-κB、DAPI/FITC、10×、1360×1024、1視野/well | 公式のPublished resultsはNone。論文で報告された比較という条件を現時点で満たさない |
| BBBC018 / 020 | [BBBC018](https://bbbc.broadinstitute.org/BBBC018)、[BBBC020](https://bbbc.broadinstitute.org/BBBC020)：CC BY-NC-SA 3.0 | 許諾条件外。018はRNAi・pH3等だが表現型で選別した画像であり、結果を見ない抽出の代替にはしない |
| Mendeley 3z3rft4hn2.1 | [公式レコード](https://data.mendeley.com/datasets/3z3rft4hn2/1)：CC BY 4.0、Imaging the time course of DNA damage response at a nonrepetitive endogenous locus。Fig 2のU2OS DMSO/etoposide 1–100 µM、生ND2、z間隔0.35 µm、γH2AX等 | 図に対応するrawフォルダの説明あり。ND2一覧・ファイルハッシュ・NA・xy校正・処理時間・反復割付は未検証。z集約と領域の事前規則が必要。画像未取得 |
| BioImage Archive S-BSST227 | [原著](https://doi.org/10.1038/s41556-019-0293-6)：53BP1 nuclear bodies。公開物の説明は24bit RGB overlay / maximum projections | 単一蛍光チャンネルの元強度をこのRGBから復元しない。QIBC rawは別途提供扱いで、今回の生画像fixtureに未採用 |
| Zenodo Aitslab Galectin 12193889 | [原著データ説明](https://doi.org/10.1016/j.dib.2024.111148)、[レコード](https://zenodo.org/records/12193889) | original C01と正規化PNGを区別する。今回は対照/処理の割付と論文表現型の対応を固定できず。正規化PNGを原画像として採用しない |

追加検索範囲：IDRのdrugresponse/dnadamage/nuclear translocation、BioImage Archiveの53BP1・γH2AX、Zenodo/FigshareのCC0/CC BY raw microscopy、BBBC013/014/018/020/021、Cell Painting、Mendeley。検索語には `siRNA screen raw images CC BY`、`NF-kB translocation microscopy dataset`、`etoposide gammaH2AX raw ND2` を含む。Figshareで論文図だけの配布を原画像と取り違えない。著者への連絡、有料取得、認証が必要なデータへのアクセスはしていない。候補が見つからなかったとの結論ではなく、採用条件の不足を明示した候補群である。

## IDR0035：測定前の固定と来歴

選定先行コミット：`8c1befb`。画像のデコード・検出より前に、
`Week1_22123` の行B、DMSO **B02** / taxol **B11 0.3 µM**、各 **s1–s3**、
3チャンネルずつ18ファイルを固定した。選択根拠はソート順と既存対照配置だけであり、
核数・面積・強度・見栄えによる差し替えは禁止。s4を失敗時の代替に使わない。
1 well/条件、3視野/wellであり、n=3の生物学的推論には使えない。

[manifest](idr0035-manifest.json) は、固定したIDRメタデータコミット、study/library/screenのGit blob SHA、処理・well・field・チャンネル、原TIFFのURL・SHA-256・サイズを記録する。
ライセンスは **IDRの研究レコードとIDRが配布するファイル** に対して確認した。
BBBCページのCopyright表記だけからCC BYと推定したわけではない。
帰属：Caie et al. (2010), IDR0035, CC BY 4.0。画像変更なし。
upstream checksumは発見していない。登録SHA-256は最初の公式HTTPS取得を固定するもので、配布者のチェックサムとの一致を意味しない。

比較する一次定量報告：[Singh et al., Pipeline for illumination correction](https://doi.org/10.1111/jmi.12178)、本文 univariate readout と Fig S9–S11。
Taxolでtubulin強度が増えると報告し、各細胞の積分強度をwell内中央値に集約する。
補正前後のZ′は−0.57 / −0.40であり、これを生物学的な変化倍率と混同しない。
Cytellectの核内平均tubulin、核面積、核数は同じ指標ではない。
このfixtureで核オーバーレイを示せても、論文のtubulin定量再現や精度検証を達成したことにはならない。
当該論文の全well解析を、この6視野だけで再現したとは言わない。

[BBBC021の選定説明](https://bbbc.broadinstitute.org/BBBC021)には、低細胞数・焦点外画像の除外と、活性に基づくsubset選別がある。今回の固定選択は追加の結果依存選別を防ぐが、元配布の選別を解消しない。
核数減少の不偏推定や毒性評価にそのまま用いない。
Palma 2025のFig 2には実画像側もあるが、照明補正・crop・resizing等を経た解析であり、生成画像の効果と混ぜない。

除外：破損・ハッシュ不一致は同じURLを再取得し、解決しなければその実行を停止する。
低核数・極端な核面積・検出困難・期待と逆の結果で視野を外さない。
端の核、焦点、飽和、断片・融合は品質項目として残す。細胞/核の追加除外は測定前に別途規則を承認する。
検出パイプラインの条件をこの候補に合うよう調整しない。

D判定：D-02（研究ライセンス・帰属・取得ハッシュ）は確認。D-03/D-06は処理表とチャンネルマップの根拠あり。
D-01/D-05は原著・定量報告があるが、アプリと同じ指標・図の再現は未達。
D-04は独立性未確認、D-07はNA/校正未確認、D-08は3視野/wellを確保しただけで公開転送量未検証、
D-09は開発で参照する候補であり独立精度評価とは呼ばない。

取得・再検証：

```sh
python scripts/public_idr0035.py --output ../public-idr0035 --download
python scripts/public_idr0035.py --output ../public-idr0035
```

初回登録だけ `--download --register-hashes` を使用し、18ファイルの取得がすべて終わった時にmanifestを書き戻す。通常は固定済みハッシュを検証する。checkout外に保存し、既存不一致ファイルを上書きしない。

### 今回の取得・実行記録

18ファイル、計47,258,316 bytes、全て1024×1280・uint16・1 pageのTIFF。
取得後に上記のオフライン再検証を実行し、18件すべてのサイズ・SHA-256が一致した。
元の画素・ファイルを変えず、画像をGitに追加していない。

固定済みの各群先頭視野（B02 s1 / B11 s1）のDNAだけを、
共通 `cytellect_analysis.engine.detect_nuclei` と既定 `NuclearDetectorSpec()` で実行した。
科学コードは `31b3c22d` の試験のみの子孫 `8427663`。
FijiのStarDistモデルSHA-256は `b0eb820e455db0ec8326d3b6f456a1b2d4aff8d7dd818a71481f8041958309e3`。
確率0.5、NMS 0.3、percentile 1.0–99.8を変更していない。
入力/出力とも1024×1280、座標scaleは1。各画像の入力画素ハッシュは検出前後で一致。
所要時間は35.781秒 / 37.870秒。これは実行記録であり資源上限の測定ではない。

| well | 取得TIFF SHA-256 | 出力uint32ラベル配列 SHA-256 |
|---|---|---|
| B02 s1 | `1154dfb7671730e02c34af45211531062fd85211616a24f17fef3c66f0e2a64e` | `3288cb6ac30ac7aeea9c602f9266447cbb0fe829a1f43d59497dbee7a6ca783b` |
| B11 s1 | `d34e37884adc9246ea8dd947fa728a86706523ee73ab20d5e3937df49297ddda` | `c6156d4b428d580ef96c48f6b84f3a4b3f1ed9dec291b4567409d1bc52be27cd` |

実行コマンドは固定解析のPYTHONPATHで `python ../idr35_detection_probe.py`。
一時スクリプトのSHA-256は `13bafd54b81efa43a22b0058a0445fc05bf712469cf541f404e7b128b3b87412`、
receiptは `85e3e58b51e3a6d608db96333dc680eb992a7b4366fe8310f11ed66572d26b94`。
再現する呼出しは次のとおり（選定manifestと原ファイルのハッシュ照合後、各群s1だけ）。

```python
from cytellect_analysis.engine import detect_nuclei
from cytellect_analysis.region_contracts import NuclearDetectorSpec
# pixels = tifffile.imread(the_manifest_selected_DNA_file)
labels, provenance = detect_nuclei(
    pixels, NuclearDetectorSpec(), fresh_output_directory, locked_fiji_directory
)
```

**未検証**：検出輪郭の正確さ、視覚的な適合、表現型の方向・効果量、
全6視野の検出、論文の細胞領域tubulin定量。出力ラベルは正解ラベルではない。
取得後に都合のよい画像へ入れ替えたり、この結果で閾値を調整したりしていない。

## DS6a：平均5-EU案への指摘

平均5-EUを別指標として扱う案に賛成。ただし **5-EU/NPM1の低下から平均5-EU単独の低下は導けない**。
分母NPM1自体が変化し得るため、「Fig 5Bと方向が一致した」と主張するにも、raw 5-EUの著者報告・元表との対応が必要。
これがない場合の表現案は「この公開画像のNPM1で定めた領域における平均5-EUを比較した。論文の正規化指標とは異なる」である。
図に合うよう領域や閾値を変更しない。

核小体をNPM1で定義すると処理によるNPM1の再分布で対象領域も変わり得る。
同一ルール・校正・露光と、核小体候補なし/判定不能/処理失敗の区別を記録する。
核内全体平均、核小体内平均、総量、5-EU/NPM1を同じ「転写量」として扱わない。
Rep1–3を3実験日と推定しない。DS6aのデモ採用は引き続きオーナー判断待ち。

