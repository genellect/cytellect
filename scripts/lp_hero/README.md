# LP のヒーロー映像

実際の構造データから LP のヒーロー映像を描画する。方針は [LP の美術方針](../../docs/lp-art-direction.md)。

## 入力（すべて SHA-256 を照合する）

| 入力 | 取得元 | ライセンス | SHA-256 |
|---|---|---|---|
| ヒト 80S リボソーム（PDB 4V6X、Anger et al., *Nature* 2013） | https://files.rcsb.org/download/4V6X.cif.gz | CC0 1.0 | `233a11857607803ecb1b39f1f21a9e5661bcd87db607fbe8050bbbe61313ded2` |
| 照明 HDRI `white_studio_01`（2k EXR） | https://polyhaven.com/a/white_studio_01 | CC0 | `a9db42a2c140bacf417ad6fc90ad689604f54814581191b4474c664bce5aec0a` |
| Blender 5.2.3 LTS（Linux） | https://download.blender.org/release/Blender5.2/ | GPL | `78486c018b4443efe5e75ab54c290ed8c15abafd249b862c2c9ce2530a918eec` |
| Molecular Nodes 520.2.0（Linux 版） | https://extensions.blender.org/add-ons/molecularnodes/ | GPL v3 以降 | `6efade09f5b6d804d2a1f5f73bfb9a081c666b3f717af52c259e3b9407fb3b48` |

Windows・macOS では、同じ版の Blender と Molecular Nodes を使う（ハッシュはそれぞれの配布ページで確認する）。描画した映像はアドオンのライセンスに拘束されない。

## 描画

Molecular Nodes を Blender に導入した後、`4V6X.cif.gz` を展開して実行する。

```sh
# 静止画（構図の確認用）
blender -b --python scripts/lp_hero/build_hero.py -- structure=4V6X.cif hdri=white_studio_01.exr out=hero.png still=1

# ループ映像（240 フレーム、24 fps、10 秒）。GPU がある場合は Blender の設定で Cycles のデバイスを GPU にする
blender -b --python scripts/lp_hero/build_hero.py -- structure=4V6X.cif hdri=white_studio_01.exr out=frames/
```

CPU（4 コア）では 1280×720・32 サンプルで 1 フレーム約 2 分かかる。最終版は GPU で 1920×1080・64 サンプル以上で描画する。

## Web 用の書き出し

```sh
ffmpeg -framerate 24 -i frames/frame_%04d.png -c:v libx264 -pix_fmt yuv420p -crf 23 -preset slow -movflags +faststart \
  apps/web/public/marketing/hero-ribosome.mp4
ffmpeg -i frames/frame_0001.png -c:v libwebp -quality 88 apps/web/public/marketing/hero-ribosome-poster.webp
```

書き出した映像と静止画は、`apps/web/public/marketing/provenance.json` と `fixtures/public/allowlist.json` に出典・ライセンス・SHA-256 を記録する。原子座標は変更せず、色・質感・カメラは表現上の選択として記録する。
