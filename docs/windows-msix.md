# Windows 11 の Microsoft Store 版

[Issue #215](https://github.com/genellect/cytellect/issues/215) の第1段階で、現行の Windows 配布 ZIP から MSIX を作る。初回の Store 申請と配布は第2段階で行う。

## 作成

`scripts/build_windows_msix.py` は、現行の EXE と同じ ZIP、SHA-256 で固定した Windows x64 の Python、Tcl/Tk、ホイール、Fiji、JDK を使う。配布するソースの SHA を `--commit` で指定する。利用者の PC では同梱の Python を分離モード（`-I -B`）で起動し、依存ライブラリの取得や仮想環境の作成は不要。ワーカーと解析の子プロセスも同じ分離モードで起動するため、利用者の Python パッケージや `PYTHON*` 変数は読み込まれない。Fiji のブリッジはビルド時にコンパイルし、TensorFlow の JNI DLL もパッケージ内に置く。Store 版の Java プロセスでは、展開時に TurboJPEG を必要とする NDPI 読み込み器を対象外にする。Cytellect が Fiji に渡す入力は TIFF。

- 版番号は `1.0.1.0` から始め、初回の限定配布と次の更新を `1.0.1.0`、`1.0.2.0` の順にする。引き続き Store の版番号が増えるようにする。配布 ZIP の版とソースの SHA はビルドの受領書に別々に残る。
- 開発用のパッケージには `Cytellect.Development` の識別情報を使う。提出候補には Partner Center の発行者と製品の識別情報を `--identity` で設定する。JSON のキーは `name`、`publisher`、`publisher_display_name`。
- 同梱物のライセンスと [対応するソース](oss.md#gpl-などの対応するソース)はパッケージの `licenses/` にある。起動中のブラウザで `http://127.0.0.1:8765/v1/local/corresponding-source` を開くと、同梱版の対応ソース ZIP を取得できる。

## main から提出する

[Windows Store release](../.github/workflows/windows-store-release.yml) は、一般公開した後の更新を `main` から Store に提出する。[Issue #215](https://github.com/genellect/cytellect/issues/215) の第2段階（Private audience での限定配布と実機での確認）と第3段階の一般公開の申請は Partner Center で手作業で行い、このワークフローは使わない。提出ジョブは、公開済みの提出が Public になるまで何もしない。Microsoft Store 用の製品識別子は `24D2FD66.Cytellect`。3 番目の版番号にはこのワークフローの実行番号に 3 を足した値を使う。1.0.3.0 までは手動で採番した版に残す。

1. Partner Center に [Microsoft Entra テナントを関連付け](https://learn.microsoft.com/en-us/windows/apps/publish/partner-center/associate-existing-azure-ad-tenant-with-partner-center-account)、[Store 提出 API 用のアプリ](https://learn.microsoft.com/en-us/windows/uwp/monetize/create-and-manage-submissions-using-windows-store-services)を登録する。
2. GitHub のリポジトリ変数 `STORE_MSIX_PUBLISHER` に Partner Center の発行者識別子を設定する。発行者の表示名はリポジトリの Secret `STORE_MSIX_PUBLISHER_DISPLAY_NAME` に保存して CI ログでマスクする。
3. GitHub の `store-release` Environment にオーナーの承認と `main` からの実行制限を設定する。専用の Secrets に `STORE_TENANT_ID`、`STORE_CLIENT_ID`、`STORE_CLIENT_SECRET` を登録する。
4. オーナーが一般公開を許可し、最初の Public の提出が公開されてから、リポジトリ変数 `STORE_SUBMISSIONS_ENABLED` を `true` にする。この変数が `true` でない間は、ビルドも提出も行わない。

`main` の更新ごとに、次の順で進む。定期実行はない。

1. `package`：Windows ランナーで、[受入](#受入)と同じスクリプト（`packaging/windows/msix/ci-build.ps1`）を使って Store の識別情報の MSIX と受領書を作り、成果物として保存する。
2. `accept`：保存した MSIX を新しい 2 つのランナーで受け入れる。署名していない原本はそのまま残し、使い捨ての証明書（発行者は Store と同じ）で署名したコピーを導入して、[受入](#受入)の新規導入と移行を行う。Store は提出された原本に自分で署名する。
3. `select`：両方の受入に通った成果物だけを選ぶ。
4. `submit`：`store-release` Environment でオーナーが承認すると、実行時点の `main` と受領書・MSIX 内のコミットを照合して提出する。一般公開済みの提出から新しい提出を作り、掲載情報や価格などを引き継いだまま x64 パッケージを差し替える。

既存の審査が進行中なら、その実行は何もせずに終わる。審査が終わった後に新しい `main` の更新がない場合は、ワークフローを手動で実行する。手動の実行は、同じコミットで受入に通った成果物を使う。成果物の保存期間（14 日）を過ぎたときは、入力 `rebuild` を有効にして作り直す。

以前の実行がコミットの前に止まり、このワークフローが付けた名前のパッケージだけを持つ下書きが残っている場合は、その下書きの掲載情報や価格などが公開済みの提出と同じときに限り、下書きを削除して作り直す。同じ実行で作った下書きは、パッケージの付け替えかアップロードに失敗した時点で削除する。それ以外の下書き（手で作ったもの、設定を変えたもの、別の名前のパッケージを持つもの）は削除せずに止まるので、Actions に記録された提出 ID を Partner Center で確認する。Store の審査と公開後、端末は Microsoft Store の自動更新で新しい版を受け取る。

## データと更新

Windows 11 の [AppData 仮想化の除外](https://learn.microsoft.com/en-us/windows/msix/desktop/flexible-virtualization)を `%LOCALAPPDATA%\Cytellect` に限って指定する。このフォルダーで EXE 版が作った作業を Store 版から開ける。Store 版は更新と削除の際もフォルダーを保持する。保管期間は既存設定を引き継ぐ。新規導入の既定は利用者が削除するまで保持する。Store 版が新しく作るフォルダーには、EXE 版と同じ所有の印（`setup-root.json`）と保持の設定（`settings/retention.json`）を書くため、あとから EXE 版を入れても同じフォルダーを使える。EXE 版の削除時に作業データも削除する操作を選ぶと、共有している作業は削除される。

Store 版の更新には Microsoft Store を使う。ソースの検証、ローカル API、作業を操作するブラウザ画面は Windows 版と共通で、同じ作業フォルダーを同時に開くことはできない。Store 版は起動中、EXE 版と同じロック（`runtime-use.lock`）を保持するため、EXE 版のセットアップと容量の回収は Store 版の起動を検知する。

## 受入

`windows-msix` は GitHub の Windows ランナーで、新規導入と移行を一つずつ検証する。新規導入では Windows のアプリ起動経路で開き、登録済みの公開 BBBC013 画像を解析・出力する。アンインストールの後に再導入して同じ作業を開き、Code Integrity の監査でパッケージ外のネイティブファイルの読み込みを調べる。監査の記録にパッケージ内のファイルが 1 件もない場合は、パッケージのパスを識別できていないものとして失敗にする。移行では、空の端末に公開済みの EXE（`0.1.0-local.23`）を導入して公開 BBBC013 画像の解析を保存し、そのフォルダーを MSIX で開いて同じ測定を読む。続けて、EXE 版が残った状態で MSIX でも解析する。2 つの検証は別々のランナーで行う（Store に提出するパッケージも同じ 2 つの検証を通す。[main から提出する](#main-から提出する)）。新規導入の検証でパッケージを削除した後も、作業フォルダーの `data\tmp` のファイルが別のプロセスに 2 分以上開かれたままになり、同じランナーでは 2 つ目を空のフォルダーから始められないため。CI は使い捨ての証明書を使い、受領書のみを保存する。

研究者の導入と自動更新の受入は、Windows 11 の実機に Store から入れた版で行う。Smart App Control を有効にした端末を含め、Windows の設定をそのままにして検証する。
