# Windows 11 の Microsoft Store 版

[Issue #215](https://github.com/genellect/cytellect/issues/215) の第1段階で、現行の Windows 配布 ZIP から MSIX を作る。初回の Store 申請と配布は第2段階で行う。

## 作成

`scripts/build_windows_msix.py` は、現行の EXE と同じ ZIP、SHA-256 で固定した Windows x64 の Python、Tcl/Tk、ホイール、Fiji、JDK を使う。配布するソースの SHA を `--commit` で指定する。利用者の PC では同梱の Python を分離モード（`-I -B`）で起動し、依存ライブラリの取得や仮想環境の作成は不要。Fiji のブリッジはビルド時にコンパイルし、TensorFlow の JNI DLL もパッケージ内に置く。Store 版の Java プロセスでは、展開時に TurboJPEG を必要とする NDPI 読み込み器を対象外にする。Cytellect が Fiji に渡す入力は TIFF。

- 版番号は `1.0.1.0` から始め、初回の限定配布と次の更新を `1.0.1.0`、`1.0.2.0` の順にする。引き続き Store の版番号が増えるようにする。配布 ZIP の版とソースの SHA はビルドの受領書に別々に残る。
- 開発用のパッケージには `Cytellect.Development` の識別情報を使う。提出候補には Partner Center の発行者と製品の識別情報を `--identity` で設定する。JSON のキーは `name`、`publisher`、`publisher_display_name`。
- 同梱物のライセンスと [対応するソース](oss.md#gpl-などの対応するソース)はパッケージの `licenses/` にある。起動中のブラウザで `http://127.0.0.1:8765/v1/local/corresponding-source` を開くと、同梱版の対応ソース ZIP を取得できる。

## データと更新

Windows 11 の [AppData 仮想化の除外](https://learn.microsoft.com/en-us/windows/msix/desktop/flexible-virtualization)を `%LOCALAPPDATA%\Cytellect` に限って指定する。このフォルダーで EXE 版が作った作業を Store 版から開ける。Store 版は更新と削除の際もフォルダーを保持する。保管期間は既存設定を引き継ぐ。新規導入の既定は利用者が削除するまで保持する。EXE 版の削除時に作業データも削除する操作を選ぶと、共有している作業は削除される。

Store 版の更新には Microsoft Store を使う。ソースの検証、ローカル API、作業を操作するブラウザ画面は Windows 版と共通で、同じ作業フォルダーを同時に開くことはできない。

## 受入

`windows-msix` は GitHub の Windows ランナーに開発用のパッケージを入れ、Windows のアプリ起動経路を使う。登録済みの公開 BBBC013 画像で解析と出力を行い、アンインストールの後に再導入して作業を開く。Code Integrity の監査でパッケージ外のネイティブファイルの読み込みを調べる。CI は使い捨ての証明書を使い、受領書のみを保存する。

研究者の導入と自動更新の受入は、Windows 11 の実機に Store から入れた版で行う。Smart App Control を有効にした端末を含め、Windows の設定をそのままにして検証する。
