# LP 用 Cycles カット

`docs/lp-art-direction.md` §3・§6・§9・§10 を前提に、`droplet` と `glass` の
静止画を生成する。実写との比較でオーナーが判定するまで、本描画を行わない。
現在は静止画の候補であり、採用済み素材ではない。

## 構図と来歴

- `droplet`：実験用チップの先端、膨張する透明な水、離脱した水滴。
  下方のウェルと淡い培地を浅い焦点で背景へ退け、研究の場との連続性を保つ。
- `glass`：ガラス棒がシャーレの液面に触れる部分と、濡れたガラスを主題にする。
  面積の大きい白い光源を動かし、透明な材質を通る光の変化を作る。
- SI メートルのシーン。色付き照明や独自のグレーディングは使用しない。
  中立色の AgX 静止画に、比較時だけ既存 `cuts.json` の補正を適用する。
- HDRI・画像テクスチャ・外部モデルは使用しない。全形状と照明をコードで再現する。
  `.blend`、実写原本、比較用画像は Git に含めない。

## 寸法の根拠と近似

- チップの全長 53 mm・容量クラス 200 µL は
  [Eppendorf epT.I.P.S.](https://www.eppendorf.com/us-en/Products/Lab-Consumables/Pipette-Tips/epTIPS-p-PF-243780)
  の仕様に基づく。外形の途中寸法、開口径 0.52 mm、壁厚は撮影用モデルの近似であり、
  特定製品の CAD 複製ではない。
- シャーレは [DWK KIMBLE 53061-6015](https://www.dwk.com/na/kimble-valueware-petri-dish-60-x-15-mm-53061-6015)
  の呼び径 60 mm・高さ 15 mm、ガラス棒は
  [DWK KIMAX 40500-200](https://www.dwk.com/na/kimble-kimax-stirring-rods-5-mm-od-x-200-mm-40500-200)
  の径 5 mm・長さ 200 mm に基づく。壁厚と端部の丸みは撮影用の近似。
- 屈折率は美術方針 §9 の指定値：PP 1.49、PS 1.59、ホウケイ酸ガラス 1.47、水 1.333。
- 付着液滴は水の表面張力 0.072 N/m・密度 998 kg/m³ の軸対称 Young–Laplace
  方程式を RK4 積分した準静的な輪郭。離脱後は体積一定の減衰楕円体と落下運動の近似。
  動的な分裂を検証した流体シミュレーションではなく、研究結果として使用しない。
- シャーレの液面は壁・ガラス棒近傍の毛管上昇を近似する面。
  光は Cycles の透過・屈折で計算し、シャドウコースティクスを有効にする。

## 静止画の再現

Blender 4.5 LTS、Cycles CPU、AgX。既定の出力は 1920×1080 の 16-bit PNG。
使用中の Blender の起動パスに置き換えて実行する。

```sh
blender -b -t 6 --python scripts/lp_film/blender/render.py -- --cut droplet
blender -b -t 6 --python scripts/lp_film/blender/render.py -- --cut glass
python scripts/lp_film/fetch_sources.py
python scripts/lp_film/blender/compare.py --font /path/to/japanese-font.ttf --output /path/to/review
```

`--frames`、`--samples`、`--scale`、`--output` で試写条件を指定できる。
レビュー用の静止画は `--samples 32 --scale 75`（1440×810）を使用する。
出力の settings JSON に Blender バージョンと描画条件を記録する。
比較スクリプトは Pillow と ffmpeg を使用し、原本の SHA-256 を再検証する。

## 承認後の工程

合格したカットだけを 25 fps・80 フレーム以上で本描画し、動的な形状変化、
モーションブラーとカメラの連続性を確認する。H.264 CRF 12・yuv420p・音声なしで
`scripts/lp_film/renders/<cut>.mp4` に配置し、そのファイルだけを許可リストに登録する。
最後に `python scripts/lp_film/build_film.py --preview .cache/lp_film/preview.mp4` で
前後の実写を含めて確認する。動画出力・全編確認・オーナーの採用判定はまだ完了していない。
