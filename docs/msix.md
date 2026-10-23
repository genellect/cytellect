# Microsoft Store 配布 / Microsoft Store distribution

## 日本語

次の Windows 配布方式は x64 MSIX です。Python 3.14.8・Tcl/Tk・解析ライブラリ・
Fiji・Java・StarDist・静的 Web UI を同梱します。利用者は Store の「インストール」から
導入し、スタートメニューで起動します。起動・停止画面とブラウザは維持します。
Store 登録・署名・審査・実機受入が終わるまで、既存の [ZIP 版](local.md)を維持します。

### ビルド

`.github/workflows/msix.yml` に一連の手順があります。クリーンな対象コミットから
`scripts/build_local_bundle.py` で、通常の wheel・ハッシュ付き依存一覧・検証済み
Tcl/Tk データ・Web UI を含むソース ZIP を作ります。Windows ビルダーには
Python、uv 0.12.2、Node 24、pnpm 11.19.0、Web ビルド依存物、Windows SDK の
MakeAppx、.NET Framework の C# コンパイラーが必要です。利用者には不要です。

```powershell
./scripts/build_msix.ps1 -SourceZip <source.zip> -Python <builder-python.exe> `
  -WorkRoot <new-build-directory> -Output <Cytellect.msix> -Version 0.1.0.0
```

出力と作業場所は checkout の外です。同じ出力を上書きしません。既定は
`Cytellect.Development` / `CN=Cytellect Development` です。Store 提出時には
Partner Center の値を `-IdentityName`・`-Publisher`・`-PublisherDisplayName` に指定します。
版は 4 要素・各要素 0–65535・最後は 0。MSIX は未署名で、自動公開しません。

ソース ZIP の全ハッシュと同じクリーンなコミットであることを検証し、開発者の
既存インストール・データ・設定をコピーしません。Python を `runtime/`、通常の
wheel を `runtime/Lib/site-packages/` に置き、venv は配布しません。Tcl/Tk と Fiji の
合成画像自己診断を、空白を含む別パスへの移動前後で実行します。起動時の追加取得は
ありません。既存アプリアイコンを Store 用に変換し、測定・統計は共通実装を使います。

### データと受入

`%LOCALAPPDATA%/Cytellect/data` を ZIP 版と共有し、削除操作まで保持します。
既存ロックで二重起動を拒否し、起動 EXE はリダイレクトを拒否してルートの DACL を
本人と SYSTEM に制限します。アプリ本体は読み取り専用です。
[Microsoft の仮想化仕様](https://learn.microsoft.com/en-us/windows/msix/desktop/flexible-virtualization)
に従い、Windows 10 では AppData 書き込み仮想化を無効化、Windows 11 では Cytellect
フォルダーを除外し、アンインストール後もデータを残します。別の ZIP 保存先は自動移行
しません。`runFullTrust` と `unvirtualizedResources` は Store 審査で説明・受理が必要です。

外部 Python 設定やシェルの有料サービス設定は起動 EXE で除外します。
既存 ZIP 版で明示的に保存した GPU 設定は共通フォルダーから読みます。
Modal / OpenAI の鍵・端末トークン・招待は同梱せず、インストール自体は利用権を
付与しません。利用コード方式は別のオーナー確認と実装が必要です。

CI は使い捨ての GitHub-hosted Windows だけで仮証明書を信頼・署名し、実 MSIX の
インストール・Start アクティベーション・公開 BBBC007 画像での Fiji 検出と図出力・
合成数値の独立参照と再現・画面からの停止・アンインストール後のデータ保持・
再インストールを検証します。`scripts/verify_msix.ps1` は一般 PC / self-hosted では拒否
します。仮証明書を削除し、PR では集計 receipt だけを 7 日保持します。
バイナリーの成果物化は既定で無効です。再配布条件の確認とオーナー承認後に限り、
手動実行の `retain_package` で未署名 MSIX を保持できます。
鍵・画像・生ログは成果物にしません。Store への自動提出はありません。

公開前に Partner Center 登録・正式識別子・Microsoft 署名・制限付き機能の審査、
Fiji / Java / プラグイン / Python の再配布条件と必要な対応ソース・差し替え資料の
確認が必要です。各原本 LICENSE / NOTICE と `THIRD_PARTY_INVENTORY.json` を保持
しますが、一覧生成は法的確認の完了を意味しません。[OSS](oss.md)に従って確認します。
正式版の更新・データ保持・オフライン起動・研究室の実行ポリシー・初心者の受入も残ります。
Store URL 確定後に LP と手順を切り替えます。Store 署名は研究室独自の制限の通過を
保証しません。旧 ZIP の受入結果を、新 MSIX の受入として扱いません。

## English

The next Windows target is a fully bundled x64 Microsoft Store MSIX. The builder
verifies an exact-source ZIP, provisions pinned Python/Tcl/Tk, wheels and Fiji/Java,
then tests GUI and detection before and after relocation. No venv, user data,
settings or provider tokens are copied. The control window/browser remain.
See the workflow and command above. Defaults are development identifiers; supply
Partner Center identity parameters for submission. Output is unsigned and never
overwritten or automatically published.

Data shares the default ZIP location and remains until explicit deletion. The
launcher restricts its DACL to the user and SYSTEM, rejects redirects and uses
the existing runtime lock. Virtualization exclusions preserve data after uninstall.
Custom ZIP destinations are not migrated. Both restricted capabilities require
Store review. Installation grants no paid-service rights; entitlement changes
remain a separate owner decision.

Disposable hosted CI signs temporarily, installs/activates the actual package,
runs public-image browser and independent numerical/replay checks, closes the
control window, checks uninstall retention and reinstalls. The verifier refuses
local PCs and self-hosted runners. PRs retain aggregate receipts only. Retaining
an unsigned binary requires the manual `retain_package` input after owner
authorization and redistribution review. Never retain certificates, images,
tokens or raw logs.

Before release: complete Partner Center registration/signing, capability review,
assembled third-party redistribution/source obligations, actual Store update,
offline/lab-policy/usability acceptance, then switch LP links. Original notices
and the generated inventory are retained; an inventory is not legal clearance.
Keep the ZIP edition until acceptance. Source code and old ZIP tests do not
establish acceptance of this MSIX.
