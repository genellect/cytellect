# Microsoft Store 版（MSIX）の設計と試作

研究室の Windows PC に、本番の Cytellect を「cytellect.app からダウンロード（のちに Store の「入手」）→ インストール → メールアドレスと 6 桁のコードでログイン」で入れるための、Microsoft Store 版の設計。状態は**試作**で、配布していない。インストーラー版（Inno Setup、[ローカル配布](local.md)）は当面そのまま残す。

## なぜ MSIX か

CI の Smart App Control（SAC）の監査（[CI](ci.md#smart-app-control-の監査)、PR #173 の run 41038205862）では、ISG ありでも次が止められるはずだった。PyPI のホイールの署名のない PE 122 個（scipy、scikit-image、numpy、SQLAlchemy、matplotlib、pydantic-core、Pillow など）、Inno Setup のインストーラー・ローダー・アンインストーラー、`uv.exe`、Fiji の Java プラグインが実行時に `data\runs\…` と `setup-cache\…` に展開する `tensorflow_jni.dll`。python.org の Python、Azul の JDK、Fiji のランチャーは署名があり通る。

Store で配る MSIX は、Store がパッケージ全体に署名し、SAC はその中身を信頼する。費用のかかるコード署名証明書は要らない。ただし信頼されるのは**パッケージの中のファイルだけ**なので、Python の環境とすべてのネイティブコードを、初回起動時に外に作るのではなく、パッケージに入れておく必要がある。

## パッケージの構成（読み取り専用）

`scripts/build_windows_msix.py` が、受け入れた設定 ZIP から作る。

| 場所 | 中身 |
|---|---|
| `python\` | python.org の Python 3.14.8（インストーラー版と同じく、Tcl/Tk のデータを加えて構成したもの）。`Lib\site-packages` に、ロックしたすべてのホイールと Cytellect のホイールを、python.org の配布物に入っている pip（`Lib\site-packages\pip`）で入れる：`python -m pip install --no-index --find-links <wheels> --require-hashes --only-binary=:all: --no-deps --no-compile -r engines/python/windows-requirements.txt`、続けて `pip check`。uv も仮想環境も使わない。pip が作るコンソールスクリプトの起動用 exe（署名のない PE）は消し、受領書に記す |
| `fiji\` | Fiji、その JDK、固定したプラグイン（インストーラー版と同じ検証済みの木）。`fiji\natives\tensorflow_jni.dll` は下記のとおり展開済み |
| `apps\web\out\` | 静的な作業画面 |
| ルート | リリースのソースと `local-release.json`。起動時に、`python\Lib\site-packages` の Cytellect のコードがリリースのソースと一致するかを確かめる（インストーラー版の `.venv` と同じ確認） |
| `cytellect-package.json`、`AppxManifest.xml`、`Assets\` | 版・各部の場所、マニフェスト（`packaging/windows/msix/AppxManifest.xml` から作る）、タイルの画像 |

ビルドでは、設定 ZIP を CI の機械で一度 `local_setup.ps1` で導入し、構成済みの Python と検証済みの Fiji だけを写す。その導入で uv が作る仮想環境はパッケージに入れない。最後に、パッケージの Python で、ソースの一致、Fiji のプラグインとモデルのハッシュ、展開済みのネイティブライブラリを確かめる。

## 書き込む場所

研究データ・設定・データベースは、インストーラー版と同じ `%LOCALAPPDATA%\Cytellect\`（`data\`、`settings\`、`setup-root.json`）に置く。インストーラー版で作った作業は、そのまま Store 版で開ける。

- **仮想化を外す**：MSIX は、パッケージのアプリが AppData に新しく作るファイルを、パッケージ専用の場所（`%LOCALAPPDATA%\Packages\<パッケージ>\LocalCache`）へ移し、既存のファイルの変更だけを実際の場所に書く。SQLite の WAL や新しい作業のファイルが二か所に分かれて壊れるため、マニフェストで `desktop6:FileSystemWriteVirtualization` を `disabled` にし、制限付きの機能 `unvirtualizedResources` を宣言する。レジストリの仮想化は残す（書き込まない）。
- **初回起動**（`cytellect_api.packaged`）：フォルダーがなければ、インストーラーと同じ所有の印を付けて作る。Cytellect 以外のファイルがあるフォルダーには何も書かずに止まる。新しいフォルダーでは、インストーラーの既定と同じく作業を削除操作まで保持する。既存のインストールの選択は変えない。フォルダーのアクセス権は LocalAppData から受け継ぐ（インストーラー版は利用者と SYSTEM だけに絞る）。
- **Fiji の書き込み**：Java の一時フォルダーと `user.home` は作業ごとの一時フォルダー（データの中）にする。これまでと同じ。`imagej.dir` はパッケージの `fiji\`（読み取り専用）で、imagej-tensorflow がそこに作ろうとする `.crashed` の印は作れないが、例外を捕まえて警告するだけで読み込みを続ける（1.1.9 のバイトコードで確認）。

## 実行時に展開されるネイティブコード

| DLL | 展開するもの | 必要か | 対処 |
|---|---|---|---|
| `tensorflow_jni.dll` | `jars/libtensorflow_jni-1.15.0.jar`（CSBDeep）。imagej-tensorflow 1.1.9 の `DefaultTensorFlowService.loadLibrary()` が、まず `System.loadLibrary("tensorflow_jni")`、失敗すると TensorFlow の `NativeLibrary` が `java.io.tmpdir\tensorflow_native_libraries-*` に展開して読む | 必要。核の検出（StarDist 0.3.0 → CSBDeep 0.6.0、モデル「Versatile (fluorescent nuclei)」）が使う | jar の `org/tensorflow/native/windows-x86_64/tensorflow_jni.dll` をビルドで `fiji\natives\` に取り出し、`natives.json` に jar とその中の場所、SHA-256 を記す。エンジンは `natives.json` があれば `-Djava.library.path=<fiji>\natives` を付け、最初の `System.loadLibrary` が成功するので展開されない |
| `turbojpeg.dll` | `jars/turbojpeg-8.5.0.jar`。Bio-Formats の `JPEGTurboServiceImpl` が scijava の native-lib-loader で、常に `nativelib-loader_*` に展開して読む。SCIFIO が起動時に Bio-Formats の読み込み器を一覧にするとき、`NDPIReader` のコンストラクターが呼ぶ | 不要。ブリッジは TIFF を ImageJ で開き、NDPI を読まない | `CytellectEngine` が起動の最初に、この JVM の Bio-Formats の既定の読み込み器から `NDPIReader` を外す（両方の版）。同じ Bio-Formats 8.5.0 の jar で、外さないと `nativelib-loader_*` に展開され、外すと展開されないことを Linux で確かめた |

## 起動とプロセス

- マニフェストの入口は `python\pythonw.exe -B -E -m cytellect_api.packaged`（`runFullTrust` の完全信頼のデスクトップアプリ、`uap10:Parameters` のため Windows 10 2004 以降）。スタートメニューの項目は MSIX が作る。デスクトップのショートカットは試作では作らない。
- `cytellect_api.packaged` は、パッケージの場所とデータの場所を決めて、インストーラー版と同じランチャー（`cytellect_api.local --gui`）を起動する。起動・停止の画面、`127.0.0.1:8765` のローカル API、計算ワーカー（同じパッケージの Python で `-m cytellect_api.local_worker`）、Fiji の Java はすべてパッケージの中の実行ファイル。
- 完全信頼のアプリには AppContainer のループバックの制限がかからず、ブラウザーは `127.0.0.1` に普通につながる。ポートが使用中のときの表示と「再試行」はインストーラー版と同じ。データフォルダーのロック（`data\local-launcher.lock`）で、2 つ目の起動は、どちらの版からでも、動いている作業画面を開く。

## 更新

- Store 版の更新は Store が行う。アプリ内の更新はインストーラーが管理するコピーでないため `unsupported` になり、作業画面の更新の表示は出ない。
- インストーラー版は残す。2 つの版は同じデータフォルダーを使い、次のとおり壊さない。
  - 同時に動くのは 1 つだけ（上記のロック）。
  - 新しい版が開くとデータベースを移行する。古い版は、知らない移行の版を見つけると、書き込む前に起動に失敗する（Alembic の動作。CI では未確認）。研究室では同じ版にそろえる。
  - インストーラー版を「データを残す」（既定）でアンインストールしても、Store 版はそのデータを使い続ける。「データも削除」を選ぶと Store 版の作業も消える。
  - Store 版を削除しても、仮想化を外しているため `%LOCALAPPDATA%\Cytellect` は残る。消すには手で削除する（案内は未作成）。

## Store の要件

| 項目 | 値 | 埋める人 |
|---|---|---|
| パッケージ名（Package/Identity/Name） | Partner Center の「製品 ID」の値を `packaging/windows/msix/store-identity.json` に書く（今は仮の値）。CI の試験は別の仮の識別（`ci-test-identity.json` の `Cytellect.CITest`）を使う | オーナー |
| 発行元（Package/Identity/Publisher） | Partner Center の `CN=…`。CI の試験は `CN=Cytellect CI Test Package` | オーナー |
| 発行元の表示名（PublisherDisplayName） | Partner Center の値 | オーナー |
| 機能 | `runFullTrust`、`unvirtualizedResources`（ともに制限付き。申請時に理由を書く）、`internetClient`（クラウドのログイン、クラウド GPU、解析の提案） | 理由の文案は下記 |
| プライバシーポリシーの URL | 例：`https://cytellect.app/privacy`。メールアドレスでログインするため必須。ページはまだない | オーナー |
| 年齢区分 | IARC の質問票に答える（暴力・課金・利用者間のやり取りなし） | オーナー |
| 大きさ | CI の受領書（`Cytellect-<版>-msix.json`）の `layout_bytes` と `msix_bytes`。Store の上限は 25 GB | ― |
| 対象 | Windows 10 2004（19041）以降、x64。言語は日本語（ja-JP） | ― |
| 同梱物のライセンス | インストーラー版と同じ `licenses\` と、GPL などの対応するソースの資産が必要。試作のパッケージには入っておらず、配布してはならない（`licenses\README.txt`） | 実装 |

制限付きの機能の理由の文案：「Cytellect は、研究者の PC で顕微鏡画像を解析するデスクトップアプリです。`runFullTrust`：同梱の Python と Java（Fiji）で解析を行うため。`unvirtualizedResources`：研究データとデータベースを、既存のインストーラー版と共有する `%LOCALAPPDATA%\Cytellect` に置き、アンインストールや版の切り替えで研究データを失わないようにするため。」

## オーナーが Partner Center で行うこと

1. [Partner Center](https://partner.microsoft.com/dashboard) で開発者アカウントを作る（個人または会社）。登録料と本人確認の要否は、登録画面の表示で確かめる。有料になる場合は進める前に判断する。
2. **アプリとゲーム → 新しい製品 → MSIX または PWA アプリ** で、名前「Cytellect」を予約する。
3. **製品の管理 → 製品 ID** の `Package/Identity/Name`、`Package/Identity/Publisher`、`Package/Properties/PublisherDisplayName` を写し、`packaging/windows/msix/store-identity.json` の 3 つの値を置き換え、`partner_center` を `true` にする PR を作る（公開してよい値で、秘密ではない）。CI の試験は別の仮の識別を使うので、この変更の影響を受けない。
4. 申請（Submission）の **価格と使用可能状況** で、無料、市場（日本など）、公開範囲を選ぶ。研究室で先に試すときは、公開せずに対象を絞る設定（非公開の対象ユーザー）にする。
5. **プロパティ** で、カテゴリ、プライバシーポリシーの URL、制限付きの機能の理由（上の文案）を入れる。
6. **年齢区分** で IARC の質問票に答える。
7. **パッケージ** に、配布用のワークフローが作る `.msix` をアップロードする（Store が署名するので、署名はしない）。この配布用のワークフローはまだない。
8. **ストアの掲載情報** に、説明と、登録済みの公開画像を使ったスクリーンショットを入れる。
9. 申請を送り、認定の結果を待ってから公開する。送信と公開はオーナーだけが行う。

## CI の試作（`windows-msix`）

`main` と手動実行だけで動き、配布の条件・必須のチェックではない（[CI](ci.md)）。

1. 設定 ZIP を作り、`local_setup.ps1` で一度導入して、Python と Fiji を用意する。
2. `build_windows_msix.py` でパッケージの中身を作り、Windows SDK の `makeappx` で `.msix` にする。
3. ジョブの中で作る使い捨ての自己署名証明書（有効期限 2 日。本物の鍵は使わない）で `signtool` 署名し、秘密鍵はすぐ消す。
4. `packaging/windows/sac-audit.ps1 -Msix …` が、SAC と同じ規則の監査ポリシー（ISG あり・なし）を入れ、証明書を信頼して Downloads から `Add-AppxPackage` で導入し、スタートメニューの項目から起動し、作業の作成、BBBC013 A01 の登録、Fiji による核の検出、品質確認、出力、パッケージの削除まで行う。データが `%LOCALAPPDATA%\Cytellect` に書かれ（仮想化された写しがない）、削除後も残ることを確かめる。
5. 監査の記録を、パッケージの中と外に分けて数える。**外から読み込まれた実行ファイルの数と、外に書かれた実行ファイルの数が 0 であること**が、Store 版で SAC に止められないための条件。パッケージの中のファイルも監査に出るが、それは自己署名だから。実際の SAC は Store が署名したパッケージの中身を信頼するが、Store の署名はこのジョブでは再現できない。

### 結果（2026-10-30、Windows Server 2025 build 26100、run 41049152741）

- 導入から削除まで成功した。`.msix` は 1,043 MB（展開後 1.68 GB、15,843 ファイル、PE は `python\` に 404 個、`fiji\` に 132 個）。ロックしたホイール 52 個を python.org の pip（26.2.1）で入れ、pip が作った起動用 exe 22 個を消した。`Add-AppxPackage` は 81 秒、起動の API で起動してから 22 秒でランチャーが応答し、BBBC013 A01 で 350 個の核を検出し（インストーラー版の監査と同じ数）、出力まで成功した。データは `%LOCALAPPDATA%\Cytellect` に書かれ、仮想化された写しはなく、削除後も残った。
- **パッケージの外から読み込まれた実行ファイルは、ISG なし・ありとも 0 個。外に書かれた実行ファイルも 0 個。** `tensorflow_jni.dll` はパッケージの `fiji\natives\` から読み込まれ、一時フォルダーへの展開（`tensorflow_native_libraries-*`）と `turbojpeg.dll` の展開はなかった。
- パッケージの中で監査に出たのは、ISG なしで 174 個（ホイールの PE 173 個と `tensorflow_jni.dll`）、ISG ありで 123 個。自己署名の試験パッケージなので信頼されないのは想定どおりで、Store が署名したパッケージで通るかは、この CI では確かめられない。ほかに、ランナー自身の `wsl.exe` が 2 件出た（配布物ではない）。
- 同じ変更で、インストーラー版の監査（run 41047140933 の `windows-sac-audit`）からも `turbojpeg.dll` が消え、検出した核の数は 350 個のまま変わらなかった。

## 残る作業（Store への申請の前に）

- 同梱物のライセンスの本文と、GPL などの対応するソースの資産を MSIX にも付ける（インストーラー版の `write_notices` と同じもの）。
- 配布用のワークフローで、`main` の受け入れたコミットから `.msix` を作る（署名しない。Store が署名する）。
- プライバシーポリシーのページ、Store の掲載情報、年齢区分、制限付きの機能の申請。
- 研究室の実機（Windows 11、SAC オン）で、Store から入れた版を確かめる。Store の署名による信頼はこの CI では確かめられない。
- アンインストール後のデータの削除の案内、デスクトップのショートカット（必要なら）、Store の更新中に起動していたときの扱いの確認。
- 2 つの版の併用（版の違うデータベース）を CI で確かめる。
