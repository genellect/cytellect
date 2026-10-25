# 群間比較の公開データ：候補と確認できた範囲

調査日：2026-10-25。採用決定ではない。選定規則は測定前のコミット `75f02c032b69aabc02db3ab27bee298290e96fd6` で固定した。今回行ったのは出典調査、ファイルのハッシュ照合、TIFF/OME メタデータの読取りであり、表現型の検出・定量は行っていない。画像の内容や測定値で視野を選び直していない。

## 推薦

- 核の縮小：条件を満たす元画像を確保できていない。Q10 に従い、この場面は公開しない。候補論文は下表に残す。
- 核数：BMH-21 の報告は具体的だが、元画像の再配布許諾が未確認。Cell Painting の陽性対照という理由だけでは採用しない。現時点は保留。
- 核小体：DS6a の Untreated / ActD1 を条件付き候補とする。4 チャンネルの順序は下記のとおり。反復の独立性・試料の対応は不明なので、E-05/D-04 に従い記述だけとし、実験回 n=3 の検定・信頼区間には使わない。採用と公開はオーナーが決める。

## 候補比較と調査範囲

「未確認」は不適格と確定した意味ではない。検索語は `nuclear area decrease raw images dataset`, `nuclear shrinkage staurosporine dataset`, `nuclear size piperlongumine`, `cell painting nuclear count reduction`、JUMP の各陽性対照名と `cell count` / `nuclei`。論文本文・Data availability、Zenodo、BBBC、Cell Painting Gallery の公式資料を確認した。全世界の公開データを網羅した調査ではない。

| 候補・一次出典 | 図・条件・報告 | 元画像の許諾・実験構造・撮影 | 判定 |
|---|---|---|---|
| [Tollis ら 2022](https://doi.org/10.1021/acschembio.2c00004)、[著者所属機関の本文](https://www.research.ed.ac.uk/files/257301021/acschembio.2c00004.pdf) | Fig 7A の PC3、piperlongumine 等で核サイズ低下。濃度依存性あり。digitoxigenin は PC3 の縮小候補ではない。絶対核面積と N/C 比を区別する。正確な変化量は未抽出 | スクリーニングは H2B-mRFP と CellMask Deep Red、20×/NA 0.45、2 回の全ライブラリ反復。Fig 7 の元画像と対応する条件・試料の一覧、µm/px、CC0/CC BY の画像許諾を確保できず。論文の代表画像を定量用原画像として転用しない | 核の縮小の有力な文献候補だが D-02/D-05–08 未確定 |
| [Transformer-based spatial-temporal detection of apoptotic cell death](https://pmc.ncbi.nlm.nih.gov/articles/PMC10948145/) | Fig 1D は追跡した核の面積比。アポトーシスの経時変化 | H2B-miRFP703、ライブ撮影。固定した 2 処理群の比較と異なり、結果で同定した死亡細胞への条件付けがある。今回の静止画デモ用の割付・独立性・画像許諾は未確認 | 今回の比較設計には不採用 |
| [Chiaravalli ら 2017](https://doi.org/10.1177/2472555217724745) | staurosporine の viability / 核形態評価。面積の向き・量と条件を固定できていない | 生画像の取得先・CC0/CC BY・反復単位・画素寸法/NA 未確定 | 追加調査候補。採用しない |
| [Cell Painting Gallery](https://github.com/broadinstitute/cellpainting-gallery)、[JUMP 対照の公式一覧](https://github.com/jump-cellpainting/JUMP-Target#positive-control-compounds)、[JUMP 論文](https://doi.org/10.1038/s41592-024-02241-6) | AMG900、NVS-PAK1-1、dexamethasone、LY2109761、FK-866、quinidine、TC-S-7004、aloxistatin。多様な形態を示す対照の選定は、核数減少の証拠ではない | Gallery の表記は “All the data is released with CC0 1.0 Universal (CC0 1.0).”。5 チャンネル、ライセンス候補は有望。ただし各薬剤の**該当データと同じ細胞・濃度・時間**で核数低下を定量する図、実験回とプレート・ウェルの対応、採用する画像の画素寸法/NA を固定できず | 核数・縮小とも保留。別細胞系の薬効を根拠にしない |
| [BBBC022](https://bbbc.broadinstitute.org/BBBC022)、[原著](https://doi.org/10.1371/journal.pone.0080999) | U2OS、約 1,600 化合物。今回の核数低下に対応する図・化合物を特定できず | CC0、5 チャンネル、20×、0.656 µm/px、16 bit。SYTO 14 は RNA であり NCL/GFP ではない。独立実験回・NA・特定の条件の割付未確定 | 保留 |
| [BBBC039](https://bbbc.broadinstitute.org/BBBC039) | 核のラベル付き画像 | CC0。既存 fixture は検出の回帰用。核面積低下を報告する処理対照実験の代替ではない | 新しいデモには採用しない |
| [Lambert ら 2025](https://doi.org/10.1371/journal.pone.0320040)、[Zenodo 10623852](https://zenodo.org/records/10623852) | C2C12、colchicine 100 nM 等の核数変化。核面積増加を縮小の根拠にしない | 公開レコードで確認した配布物は正規化したプロファイル CSV。対応する原画像を確認できず | 原画像の fixture にできない |
| [Potapova ら、eLife 88799](https://elifesciences.org/articles/88799)、[元データ案内](https://www.stowers.org/research/publications/libpb-2415) | Fig 2C、RPE1、BMH-21 は核で数えた細胞数を約 1/2 にする。1/10 µM、24 h のスクリーニング。公開候補の正確な濃度・well と図の対応は未固定 | 40×/NA 1.1、40 視野/well、16 bit。Stowers LIBPB-2415 の生画像の CC0/CC BY 許諾・独立性・画素寸法を未確認。データページは本環境の閲覧で HTTP 403。論文の CC BY を別配布の画像へ自動適用しない | 核数の優先追加確認候補。許諾と割付が確認できるまで取得対象に登録しない |
| [Schmidt ら 2022 / DS6a](https://doi.org/10.1016/j.celrep.2022.111629)、[Zenodo 6643470](https://zenodo.org/records/6643470) | Fig 5A–B、U2OS、核小体の離心率と 5-EU | 下記参照。核面積や核数の再現の根拠ではない | 条件付き推薦 |

## 追加候補の確認

追加検索（上記と同日）：`acschembio.2c00004 data Zenodo`、`nuclear area decreased images zenodo drug`、`Reduction in Nuclear Size by DHRS7 Data Availability` でも次を確認した。

| 追加候補 | 定量の根拠 | 原画像の状況・判断 |
|---|---|---|
| [Rizzotto ら、Cells 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC10778050/)、[所属機関の本文](https://www.research.ed.ac.uk/files/404848719/cells-13-00057.pdf) | Fig 3B、PC3、10 µM/36 h、in-plate DMSO に対し6薬剤で集団平均核面積が20%以上低下。estradiol propionate 等。H2B-mRFP / CellMask Deep Red、20視野/well。Fig 4 の体積とは区別 | Data availability は原画像を大学サーバーに保管し **upon request** とする。恒久的な公開画像 URL・再配布許諾・ハッシュを取得できず。実験回別割付、画素寸法/NA の fixture としての確認も未了。今回採用しない。著者への連絡はしていない |
| [Palma ら 2025](https://www.nature.com/articles/s41467-024-55707-8) の BBBC021 再解析 | Fig 2B は Taxol 等について、実画像と生成画像の核で数えた細胞数・面積を比較する。実画像側は核数候補の追加根拠になるが、正確な効果量・濃度・視野の対応は未固定。核面積低下の記述には生成画像の補間が含まれる | **生成画像は科学的デモの原画像に採用しない**。実画像の切り出し・処理と BBBC021/Gallery の配布物の対応、画像単位のライセンス、反復の独立性、校正を固定するまで保留。実画像側の報告とモデル予測を混ぜない |

## DS6a のメタデータ証拠

原レコードの license は `{"id":"cc-by-4.0"}`。原文の名称は “Creative Commons Attribution 4.0 International”。[ライセンス本文](https://creativecommons.org/licenses/by/4.0/legalcode.en)を参照する。帰属表示案：**Schmidt, Broder; Rohatgi, Rajat; Brandman, Onn (2022), DS6a_5EU_Pulse_RawData, Zenodo 6643470, CC BY 4.0**。論文へのリンクを併記する。今回は原ファイルを変更していない。将来の表示変換・切り出しは変更内容として別途記録する。

Zenodo API は 180 ファイル（6 条件 × Rep1–3 × 各 10 視野）と各ファイルの MD5 を返す。`ds6a-manifest.json` は Untreated / ActD1、各 Rep のファイル名辞書順先頭 3 視野、計 18 ファイル（766,201,157 bytes）の URL・期待 MD5 を固定する。Rep1 の各条件先頭、計 2 ファイルをダウンロードし、サイズと MD5 を照合して SHA-256 を追加した。残り 16 ファイルは未取得・未照合で、SHA-256 は null。`ds6a-metadata-samples.json` はその 2 ファイルだけの実測メタデータであり、全 18 ファイルの検証記録ではない。

| 項目 | 2 ファイルの TIFF/OME で確認した事実 | 解釈・未確認 |
|---|---|---|
| 画素 | CYX=(4,2304,2304)、4 pages、uint16、0.1625 µm/px | 他の 16 ファイルのヘッダは未検証 |
| 対物 | 40×、NA 1.4、oil | 倍率だけから校正を推定していない |
| 配列順 0 / C0 | FITC、518 nm | 生物学的ラベル未確定。論文の FBL-sfGFP と整合するが、著者の pulse 解析コードは変数を `ubtf` と命名している。FBL と断定せず、この場面の定義・測定には使わない |
| 配列順 1 / C1 | TRITC、580 nm | 著者の pulse 解析コードが index 1 を NPM1 に対応付け、核小体を定義している |
| 配列順 2 / C2 | Cy5、670 nm | 著者の pulse 解析コードが index 2 を 5-EU に対応付ける。Methods の Alexa Fluor 647 azide と整合。OME 自体は「5-EU」と記載しない |
| 配列順 3 / C3 | DAPI、455 nm | 論文 Methods の ProLong Glass NucBlue による核染色と整合。OME のフィルタ名を染料名と断定しない |
| 露光 | 各 Plane の ExposureTime を metadata-samples に保存 | 固定した 2 ファイルの比較は可能。残りの gain/露光・撮影時点の同等性は未検証 |
| 処理 | ファイル名は Untreated / ActD1 | OME に濃度・処理時間・5-EU パルスの記載なし。Fig 5A とレコードの説明から「ActD 1 µM、1 h → 5-EU 30 min」が強く示唆されるが、ファイル単位の処理表による照合は未完了 |
| 反復・試料 | Rep1–3、ファイル名の日付は 20211201。2 ファイルの acquisition date を保存 | 別々の播種・処理・染色か、カバーガラスの識別、群間の pairing、割付・ランダム化は不明。Rep を独立実験回と自動確定しない |

本文の確認には [Europe PMC XML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9749789/fullTextXML) も使用した。本文は ActD の核小体離心率低下と転写抑制を報告する。Fig 5B の観測単位は**核小体**で、各条件 713 個以上、中央値・25–75 百分位の箱・5–95 百分位のひげである。核ごとの代表値 → 視野 → 試料 → 実験回という Cytellect の集約とは一致しない。論文の箱ひげを実験回 n=3 の図として再現してはいけない。正確な効果量はまだ転記していない。5-EU の総量と、核小体面積あたりの平均信号を区別する。

追加の一次根拠：[著者の 5EU_Pulse_Step1_Quantification.ipynb](https://github.com/RohatgiLab/2022_Schmidt_Oxaliplatin/blob/620fb6e32fb7c59c0aaf6697a851e2c627147947/5EU_Pulse_Step1_Quantification.ipynb)（コミット `620fb6e32fb7c59c0aaf6697a851e2c627147947`）。index 1 で領域を作り index 2 の平均を測る点はコードで確認できる。index 0 の `ubtf` は論文の細胞株説明との不一致が残る。著者のコードは閲覧のみで実行・移植していない。NPM1 の平滑化・閾値・境界除外を使う著者の処理と Cytellect の検出も異なるため、同じ数値になるとの保証はしない。

**5-EU の照合は追加確認が必要。** 同じコミットの [Step2_Plotting.nb](https://github.com/RohatgiLab/2022_Schmidt_Oxaliplatin/blob/620fb6e32fb7c59c0aaf6697a851e2c627147947/5EU_Pulse_Step2_Plotting.nb) は CSV の第 8 列を第 5 列で割って `NormEU` とする。Step1 の pandas 出力をそのまま読むなら、先頭の index 列を含めて「5-EU 平均 / NPM1 平均」に相当するという推定になる。これは単なる核小体内 5-EU 平均と同じ指標ではない。実際に図へ投入した CSV・列の対応は未入手で、論文の誤りと断定しない。濃度の図ラベルは 1 µM ActD を確認できるが、生ファイルへの処理表はない。採用前に、図との照合を mean 5-EU の方向確認に限るか、著者の図の正規化まで再現するかを決め、必要な出典を確保する。後者を既存の mean 指標として実装しない。

## 測定前の比較計画（X-03 / X-04 / Q-01）

| 場面 | 固定する比較 | 集約・照合 | 開始を止める不足 |
|---|---|---|---|
| 核の縮小 | 未採用。Tollis Fig 7A は文献候補のみ | 論文の絶対核面積と同じ条件を特定し、Cytellect の核中央値・試料平均との違いを明記してから測る | 元画像、許諾、条件別一覧、校正がない。測定・公開しない |
| 核数 | 未採用。Potapova Fig 2C BMH-21 は文献候補のみ | 播種・時点・観察面積・核数/well と核数/視野の差を固定する。生存率に読み替えない | 許諾と画像の割付が不明。測定・公開しない |
| 核小体 | DS6a Untreated 対 ActD1、Fig 5A–B。離心率と核小体の平均 5-EU | 核小体定義は NPM1 候補、測る信号は別チャンネル Cy5。離心率の核代表値は WP0/WP3 の承認仕様を使う。論文の核小体単位の図との**方向の照合**と、Cytellect の核単位記述を分ける。独立性不明のまま実験回推論をしない | オーナー採用、処理表/チャンネル対応の確認、共通指標・領域定義の固定が必要。数値の一致許容差を後付けしない |

共通規則：全画像を用い、今回 crop は作らない。ダウンロードの破損は同じファイルを再取得し、直らなければその実行を失敗として止める。別視野へ置換しない。画像端・飽和は品質として記録し、比較値に基づく削除はしない。核が少ない、核が小さい、核小体候補がない、断片に見えることを理由に視野を外さない。候補なし・判定不能・処理失敗は欠測として区別する。重なり・融合・過分割の修正が必要なら両群共通の規則を別コミットで測定前に固定し、前後を保存する。現行 showcase の核数による `derivation_rule` と `fragment_review` を流用しない。

## D-01–D-09 の判定（DS6a 候補）

| ID | 状態・根拠 |
|---|---|
| D-01 | 査読論文・Fig 5 の対応あり。核小体の方向は報告済み。Cytellect での再現は未測定 |
| D-02 | レコードの CC BY 4.0 と取得ファイルの MD5 照合、帰属表示案あり |
| D-03 | U2OS の対照/処理が論文にある。ファイル単位の処理表との照合は未完了 |
| D-04 | **未確認**。独立性を仮定しない。記述限定の採用判断が必要 |
| D-05 | Fig 5A–B の核小体離心率低下と平均 5-EU の低下を対象に固定。論文は核小体単位、アプリは核代表値という違いを記録。効果量の正確な転記・再現は未実施 |
| D-06 | 2 ファイルで 4 チャンネルを確認。生物学的ラベルは論文との整合による推定。全選定ファイルは未照合 |
| D-07 | 2 ファイルの画素寸法、NA、bit depth、露光を記録。全選定ファイルと小さい核小体の定量妥当性は未検証 |
| D-08 | 元ラベルごとに 10 視野、選定 3 視野。ただし独立実験回の数ではない。18 原画像は約 766 MB であり、公開デモの転送量基準を満たしたとは言えない。WP9 の派生表示物・計測が必要 |
| D-09 | この subset はメタデータ調査・デモ・回帰用。検出精度や生物学的妥当性の独立検証を主張しない。モデル訓練データとの重複も未確認 |

## 取得と再検証

```sh
python scripts/public_group_comparison.py --output ../public-ds6a --verify --metadata-samples
python scripts/public_group_comparison.py --output ../public-ds6a --download
```

1 行目は今回取得した 2 ファイルの再検証。2 行目は固定した全 18 ファイルを取得するための手順で、今回全件は実施していない。出力は checkout 外だけに許可する。既存ファイルの不一致時は停止し、上書きしない。画像のハッシュと検証 receipt を残し、科学的測定は行わない。ローカルから Zenodo への接続は初回 sandbox 内で失敗したが、許可されたネットワーク実行では成功したため、現時点でクラウド取得が必須という制約はない。
