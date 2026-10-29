# 解析モデルの選定と発展方針

Cytellect は、対象の生物学的な特徴に合うモデルを選び、検出・修正・測定を一つの解析履歴でつなぐ。研究室単位の SaaS への展開では、モデルの精度と操作性に加え、商用利用の権利、計算費用、再現性を選定基準にする。

この文書は採用モデルと今後の設計方針を扱う。計算の正本は[計算仕様](methods.md)、権利の根拠と採用時の確認項目は[ライセンス文書](oss.md#segmentation-models-and-commercial-service-policy)、開発の受入条件は[ロードマップ](roadmap.md)に置く。一次資料の確認日は 2026-10-29。

## 解析基盤と追加学習モデル

核の検出に StarDist、核小体・細胞領域の検出に Cellpose-SAM を用いる。核小体向けには Cellpose-SAM を追加学習し、`ncl-r1-step0750` と `ncl-r1-step0375` を [Genellect/Cytellect](https://huggingface.co/Genellect/Cytellect/tree/7670daa1edbfcb3d4611c9e053766d91f6125e74) で公開している。ただし製品の既定の解析は、まだ公式の `cpsam_v2` を使う（[モデルの受入記録](#モデルの受入記録)）。基盤モデル、追加学習した重み、解析プロトコルは、それぞれ別に版管理する。

次の表は、リポジトリの `main` に固定されている実行構成を示す。

| 用途 | 構成 | Cytellect での使い方 |
|---|---|---|
| 核の検出 | StarDist ImageJ 0.3.0、`dsb2018_heavy_augment`（Versatile fluorescent nuclei） | Fiji 内で 2D 核インスタンスを検出する。プラグインと内蔵モデルのハッシュを固定 |
| 核小体候補・細胞領域の検出 | Cellpose 4.2.1.1、公式 `cpsam_v2`、SAM ViT-L | 対象チャンネルから 2D インスタンスを検出。NCL では親核の条件付けと境界補正を適用 |
| 実行基盤 | Python 3.12、PyTorch 2.8.0、torchvision 0.23.0 | CPU 版と CUDA 12.6 版で同じ重み・runner を共有。CUDA は float32、TF32 無効で実行 |

構成の正本は [Fiji manifest](../engines/fiji/runtime.lock.json)、[Cellpose CPU manifest](../engines/cellpose/runtime.lock.json)、[GPU manifest](../engines/cellpose/gpu.lock.json)にある。Cellpose の公式モデル一覧は `cpsam_v2` を SAM ViT-L ベースとして説明している（[公式資料](https://cellpose.readthedocs.io/en/latest/models.html)）。

### Cellpose の重みの識別

| 項目 | 固定値 |
|---|---|
| 配布元 | `mouseland/cellpose-sam` |
| ファイル | `cpsam_v2` |
| revision | `7c61431b5fbb078f3296754bd15d9f51b320f837` |
| SHA-256 | `0f1cc3f7ecdd8a037a57c6c48d9d8921391be4cbce3fa9f13c3e3a2e1253c667` |
| サイズ | 1,233,586,851 bytes |
| ライセンス表示 | 固定 revision のモデルカードに `bsd-3-clause` |

Cytellect の `cellpose-sam-ncl-parent/4.3.0` は、親核による条件付け、核全体を拾う候補の除去、Multi-Otsu・Watershed による境界補正を含む解析プロトコルの版である。Cellpose パッケージ、基盤モデル、追加学習モデルの識別子と区別して記録する。

現在の入力は 2D の uint8/uint16 検出面で、runner は `do_3D=False` を指定する。検出用の正規化はコピーに適用し、測定は原画素から行う。採用した整数ラベルと研究者の修正を保存し、モデルの再実行に依存せず測定を再現する。細胞領域と核の関連付けは重なりを記録し、1 細胞 1 核を一律に仮定しない。

### 公開している追加学習モデル

| 項目 | 内容 |
|---|---|
| 対象 | NCL 染色による核小体のインスタンス分割 |
| 基盤 | 上記の固定版 `cpsam_v2` |
| 公開 revision | `7670daa1edbfcb3d4611c9e053766d91f6125e74` |
| モデル | `ncl/r1-step0750.pt`（750 更新）、`ncl/r1-step0375.pt`（375 更新） |
| 750 更新版 SHA-256 | `9d2c2ec06aa1aa71f36695b49b0828f82fd3cb633da2832c99a9f194d0bd4099` |
| 375 更新版 SHA-256 | `bc5ea7f25ce9a9f96e9ff510cee20587e1328ac834a0f7f82aee0bc06156d906` |
| 来歴 | モデル別 JSON に学習条件、基盤・学習コード・データ manifest のハッシュと評価記録を保存 |
| 権利表示 | モデルカードの BSD-3-Clause、上流の `LICENSE.cellpose`、追加学習による変更を記した `NOTICE.md` |

根拠は固定版の[モデルカード](https://huggingface.co/Genellect/Cytellect/blob/7670daa1edbfcb3d4611c9e053766d91f6125e74/README.md)、[750 更新版の記録](https://huggingface.co/Genellect/Cytellect/blob/7670daa1edbfcb3d4611c9e053766d91f6125e74/ncl/r1-step0750.json)、[NOTICE](https://huggingface.co/Genellect/Cytellect/blob/7670daa1edbfcb3d4611c9e053766d91f6125e74/NOTICE.md)。評価条件と製品への組み込み状況は、[モデルの受入記録](#モデルの受入記録)で管理する。

## 拡張先とモデルの選び方

次の表は開発候補を示す。用途への適合と導入順は Cytellect の設計判断であり、各モデルの機能・ライセンスはリンク先の一次資料に基づく。

| 展開先 | 候補 | 選定の理由と設計上の要点 |
|---|---|---|
| 核小体・細胞領域の精度向上 | Cellpose-SAM の追加学習を継続・展開 | 核小体用の追加学習と現在の推論経路を生かし、対象・染色・撮影条件を広げる。独立した実験回で検出精度と手補正時間を比較する（[Cellpose の学習済みモデルと追加学習](https://cellpose.readthedocs.io/en/latest/models.html)） |
| 3D の核・細胞 | Cellpose の 2.5D 推論、StarDist 3D | Cellpose は直交 3 面の流れ場を組み合わせて 3D で領域を構成する。StarDist 3D は星凸形状のインスタンス分割として比較する。StarDist は Python の 3D 実装と対象に合う重みを別途選定する（[Cellpose 3D](https://cellpose.readthedocs.io/en/latest/do3d.html)、[StarDist](https://github.com/stardist/stardist)） |
| 2D・3D の輪郭修正と教師データ作成 | microSAM（`vit_b_lm` / `vit_l_lm`） | 光学顕微鏡の細胞・核向けモデルと対話的な領域指定を、修正操作に組み込む。EM 用の `vit_b_em_organelles` 等は電子顕微鏡の用途として区別する（[公式モデル・操作仕様](https://computational-cell-analytics.github.io/micro-sam/micro_sam.html)） |
| ミトコンドリア・ER・Golgi などの 3D 構造 | nnU-Net による対象別モデル | 構造の教師ラベルから学習する枠組み。領域クラス、個体、枝分かれを区別し、面積・体積・形態の測定目的に合う出力を設計する（[公式資料](https://github.com/MIC-DKFZ/nnUNet)） |
| 大きい・細長い細胞、計算量の最適化 | CellposeDINO `cpdino` / `cpdino-vitb` | 可変タイルと大小のバックボーンを、精度・VRAM・処理時間で比較する。DINOv3 由来の条件をモデル採用記録に含める（[モデル仕様](https://cellpose.readthedocs.io/en/latest/models.html)、[DINOv3 条項](https://github.com/facebookresearch/dinov3/blob/main/LICENSE.md)） |
| 多様な撮影法での細胞全体 | CellSAM | Cellpose-SAM とは別プロジェクト。`cellsam_general` 等を比較対象にし、認証配布される重みの条件を取得版に結びつける（[公式資料](https://github.com/vanvalenlab/cellSAM)、[配布実装](https://github.com/vanvalenlab/cellSAM/blob/master/cellSAM/_auth.py)） |
| 細菌・非凸形状 | Omnipose | 形態に適した比較候補。商用サービスでは提供元との商用ライセンス契約を採用経路とする（[公式資料](https://omnipose.readthedocs.io/)、[NonCommercial License](https://github.com/kevinjohncutler/omnipose/blob/main/LICENSE)） |
| RNA・蛍光スポット | Big-FISH のスポット検出 | インスタンスマスクとは別の点座標・強度・密度の解析経路を設ける。これは学習済み重みの置換ではなく、検出・定量手法の拡張である（[公式資料](https://big-fish.readthedocs.io/en/stable/)） |

核・細胞のように個体を数える対象と、ER のようにつながった構造、RNA のような点状信号では、正解と測定単位が異なる。細胞向けモデルをすべてに当てはめず、インスタンス、構造の領域クラス、点座標を共通の解析履歴に接続する。

## 3D 対応の設計方針

3D 対応は、モデルの呼び出しだけでなく、画像の確認・修正・定量・書き出しまでを一つの機能として設計する。

| 層 | 設計方針 |
|---|---|
| 入力 | OME の軸、チャンネル、Z 間隔、XY の画素寸法を明示し、異方性を推論条件として保存する。時間軸は Z 軸と分け、追跡は別の機能として扱う |
| 推論 | Cellpose の 2.5D と StarDist 3D を同じ評価画像で比較。3D 固有の閾値・最小体積を定義する。例えば Cellpose の `flow_threshold` は 3D では適用されない |
| 保存 | 原画像座標の 3D 整数ラベル、対象 ID、核・細胞・細胞内構造の関連、検出・採用・修正の版を保持する |
| 操作 | XY・XZ・YZ の断面を対応付け、立体内の結合・分割を確認して修正できるようにする。投影像は全体像の表示に使い、定量は原ボクセルから行う |
| 測定 | 体積、表面積、強度、空間的位置を物理単位で定義する。撮影範囲の端で切れた対象を記録し、面積と体積、細胞数と実験回の n を区別する |
| 資源 | タイルの重なりと境界での ID 統合を設計し、代表的な体積・異方性でピーク VRAM、待ち時間、費用を測る。利用者単位の実行枠・費用上限・キャンセルを保つ |

軸・異方性・3D 固有パラメータの根拠は [Cellpose 3D の公式仕様](https://cellpose.readthedocs.io/en/latest/do3d.html)。現行の 2D レシピを保存済みの版で再現しながら、3D の入出力を新しい契約として追加する。

## 研究室向け SaaS の開発順序

1. **既存の 2D 解析を磨く。** 研究者の修正を教師データへ結びつけ、対象・染色・撮影条件ごとの精度と手補正時間を評価する。モデルの権利記録を、既存のバージョン・ハッシュ管理に結びつける。
2. **3D の核・細胞を一連の操作にする。** 入力、直交断面での編集、体積測定、結果の再現をそろえ、Cellpose と StarDist の比較から採用モデルを決める。
3. **細胞内構造とスポットへ展開する。** 対象別の教師ラベルと測定定義を作り、nnU-Net、microSAM、スポット検出を用途に応じて接続する。

モデルは、試料・実験回・撮影バッチを分離した評価で選ぶ。領域の一致度に加え、結合・過分割、面積・体積・強度の誤差、研究者の修正時間を測る。GPU の速さや試験の件数だけで科学的な品質を判断しない。

SaaS のモデル更新では、利用者が採用した版を保持し、新版の評価結果と費用を提示して移行する。研究画像を用いた学習、共同研究先への共有、重みの公開は別々の利用目的として管理し、データ提供元との取り決めに結びつける。商用運用・配布・追加学習の権利判断は、[採用手順](oss.md#segmentation-models-and-commercial-service-policy)に従って記録する。

## モデルの受入記録

開発・リリース判断に用いる記録。2026-10-29 に公開モデルの metadata、`main` の runtime manifest、関連 PR を照合した。

| 対象 | 確認した状態 | 次の受入条件 |
|---|---|---|
| 追加学習と公開 | 核小体用 375・750 更新版の重み、学習条件、評価 metadata、ライセンス表示を公開済み | 追加の対象・撮影条件にも同じ来歴管理を適用 |
| 製品との接続 | `main` の既定 manifest は公式 `cpsam_v2` を固定。候補選択の [PR #61](https://github.com/genellect/cytellect/pull/61) は closed・未マージ | 採用する重みを版とハッシュで指定し、製品経路での再現結果を記録 |
| 評価範囲 | 学習は 1 実験の 8 個、評価は別に培養・処理した実験の 4 個の核小体。750 更新版は製品の後処理込みで、IoU ≥ 0.5 の F1 が 1.0、union Dice が 0.8951。IoU ≥ 0.7 では F1 0.75 で、1 個は面積が 40.8% 小さい。評価に使った 4 個は候補の選択にも使ったため、独立した最終試験ではない | 独立した実験回で輪郭・測定誤差・修正時間を評価。個々の境界誤差と IoU 閾値別の結果も含める |

更新回数や単一の一致率を製品全体の精度に置き換えず、モデルカードの対象・処理条件・評価単位とともに判断する。
