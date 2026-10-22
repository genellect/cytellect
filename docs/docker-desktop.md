# Docker Desktopでのブラウザ操作

## 研究室向け固定イメージの作成（ソース準備段階）

`scripts/build-lab-release.ps1` は、固定版ランチャーが要求する3イメージを
意図的にビルドするための入口です。この変更はPR64を基点とし、manual保持対応の
PR63と、搭載するモデルを含む統合ソースに依存します。これらを自動で取り込まず、
未統合の現在のソースではmanual能力の事前検査で停止します。
実イメージのビルド・起動・研究室配布は、このソース変更では未実施です。

統合ソースとモデルのレビュー、ビルド時のRAM・ディスク容量・ネットワーク取得の確認後、
そのソースをcommitしたclean checkoutからPowerShell 7で実行します。
`$commit` はそのcheckoutの正確な40桁commit、`$newOutput` はcheckout外の
まだ存在しない専用ディレクトリの絶対パスです。親ディレクトリは事前に用意します。

```powershell
# baselineだけの版。候補の検査失敗をnoneへ置き換えて続行しないでください。
.\scripts\build-lab-release.ps1 -SourceCommit $commit -Candidate none -OutputDirectory $newOutput
# 候補を含む版ではnoneを、両lockで一致するレビュー対象の実model IDへ明示的に置き換えます。
```

`none`でもcpsam_v2を保持します。候補を指定した場合は同じbaselineに加えて1件だけを
既存の固定HF revision・SHA・サイズ検証で取得し、既定モデルを変更しません。
APIには重みを入れず、workerだけにruntime/cacheを同梱します。Webは
`http://127.0.0.1:8001` とdesktop-owner設定で別途コンパイルします。
通常のDockerfile最終target（Pythonはworker、Webはbuilder）と開発用の挙動は維持します。

Dockerへ渡すcontextは現在のディレクトリコピーではありません。固定commitのGit blobから、
Dockerfileが必要とするコード・lock・契約・公開assetだけを新しいcontextへ出力します。
ignored/untrackedファイルは読み込みません。Gitのsymlink/submodule、パスのjunction等、
研究データ・重み・DB・秘密鍵のパス、既知の秘密情報パターンは拒否します。
公開バイナリassetは既存の公開allowlistの出典・ライセンス・SHAを照合します。
コードやJSONに非公開情報がないことを自動検査だけで保証はできないため、固定commitの
プライバシーレビューも必要です。contextと検査記録の全ファイルSHAを保存します。

ビルドは指定local Docker Desktop contextのdefault builderを使い、api、worker、webの
順に実行します。外部Docker/buildx/env上書きは拒否し、pull更新は要求しません。
ただし未存在のベースイメージ、OS/package/Fiji/Cellpose/modelの取得はビルド時に必要です。
これは固定版Startの `--no-build --pull never` と別工程です。元のベースimageタグは
この変更でdigestへ置き換えておらず、完全な再現ビルドを保証しません。実配布時には
ベースdigest、依存物・license/notice、生成したimage内容を別途確認します。

新しいiid、各段階の開始・検証記録、すべて成功した時だけ `build-completed.json` を
保存します。途中で失敗・中断した出力と予約ファイルは残し、同じ出力先を再利用しません。
このコマンドは再試行、image削除、load/save/push、volume操作、アプリ起動を行いません。
エラーに生のツール出力や秘密情報を含めず、失敗段階を記録で特定します。
同じOSユーザーによる同時改変に対するセキュリティ境界ではありません。

receiptは実image IDと検査した入力の記録です。ラベルやmanual設定の能力検査だけで
科学的採用・統合機能・配布受入を証明せず、受理済みrelease manifestを自動発行しません。
実起動、offline取得済み重みのidentity、baseline復帰、実画像推論・保存修正、
研究室hardware適合、バックアップ復元は別途受入が必要です。
この研究室配布の画像受入には来歴を確認した実画像だけを使い、末尾の
`verify_docker_regions.py` による生成画素検査で代用しません。
特にactive host-VHDと物理容量のbinding未確認によるbackup/restoreの保留は解除しません。

## 固定版を使う研究室向け起動経路（配布受入前）

下記の通常開発経路とは別に、`docker-desktop.ps1` に明示的な固定版起動を
追加しています。現時点で配布可能な統合イメージ・manifest は同梱していません。
手動保持対応（PR63）と、選択モデルを含む統合ソース・イメージのレビューが必要です。
manifest のハッシュ一致やイメージのラベルだけで、そのレビューや科学的採用が
完了したとは扱いません。`main` の既存イメージに環境変数だけを追加しても使えません。

実配布物が受理された後、配布記録から manifest の SHA-256 を別途取得し、
PowerShell 7 で次の同じ3引数を毎回指定します。`$manifestPath` と
`$installationPath` は絶対パスで、後者は checkout の外にある研究室管理の専用ディレクトリです。

```powershell
.\scripts\docker-desktop.ps1 Start -ReleaseManifest $manifestPath -ManifestSha256 $publishedManifestSha256 -InstallationDirectory $installationPath
.\scripts\docker-desktop.ps1 Open -ReleaseManifest $manifestPath -ManifestSha256 $publishedManifestSha256 -InstallationDirectory $installationPath
.\scripts\docker-desktop.ps1 Status -ReleaseManifest $manifestPath -ManifestSha256 $publishedManifestSha256 -InstallationDirectory $installationPath
.\scripts\docker-desktop.ps1 Stop -ReleaseManifest $manifestPath -ManifestSha256 $publishedManifestSha256 -InstallationDirectory $installationPath
```

固定版では `Build`、`Invite`、外部提案サービス設定を受け付けません。
引数を一部だけ渡しても通常開発経路には戻りません。Start/Open は
`--no-build --pull never` を使い、取得・ビルド・モデル選定を自動で行いません。
必要なイメージが未導入なら停止します。別途配布された実 archive がある場合は、
配布記録の正確なバイト数と SHA-256 を照合してから `docker load --input $archivePath`
を明示実行し、その後ランチャーが実 image ID と指定 repo digest を再照合します。
このランチャー自体は archive をロードしません。

インストール識別子と `cytellect-lab-…-research` ボリュームはリリース版とは分離して
専用ディレクトリに記録します。既存の `cytellect-human-e2e` や所有不明のボリュームを
引き継ぎません。Docker 操作より前に予約記録を排他的に保存し、途中終了時は同じ記録と
ラベルが一致する資源だけを再利用します。破損記録や消失した既設ボリュームは自動修復せず
停止します。ディレクトリと記録は研究室内で保護し、公開配布物に含めないでください。

API/worker は両方 manual 保持です。期限による研究データ削除を無効にし、アプリ内の
明示削除・所有権・セッション期限・実行 lease は維持します。容量管理は研究室の責任です。
既存 TTL データを移行する経路ではありません。すべての writer を停止した移行・
DBとartifactの一体バックアップ・互換版への復元は別の配布単位で受け入れます。
通常 Start/Open に違う manifest を渡す更新は拒否します。古い版を既存ボリュームに
直接接続したり、`down -v`、prune、記録削除で制限を回避しないでください。

初回失敗時も研究ボリュームを残します。起動後の不一致では、この呼出しで新しく
起動した、所有権が確認できるコンテナだけを止めます。以前から動く別サービスは止めません。
ロックは同じインストールへのランチャー同士を直列化するもので、同じ OS アカウントの
外部 Docker 操作を防ぐセキュリティ境界ではありません。記録ファイルの flush は行いますが、
電源断からの自動復旧を保証しません。未完了記録は保持して調査します。

### 実リリース manifest の契約

JSON は以下のフィールドだけを受け付けます。テスト用の架空 image ID や、受理を
自己申告する `approved` 等は配布 manifest として用意しません。

| フィールド | 必要な実情報 |
|---|---|
| `schema_version` | `1` |
| `source_commit`, `platform` | 統合版の40桁 commit、現在の対応は `linux/amd64` |
| `retention`, `runtime_contract` | `manual`、`manual-v1`。PR63を含む実バイナリで確認する |
| `files` | `scripts/docker-desktop.ps1`、`scripts/docker-lab-release.ps1`、`infra/compose.release.yaml`、`engines/cellpose/runtime.lock.json` の実 SHA-256 |
| `images` | `api` / `worker` / `web` 各 `{id, repo_digest}`。`id` は実 `sha256:…`、digest 未付与のローカル archive では `repo_digest: null` |
| `baseline` | `{id, repo, revision, file, sha256, bytes}`。同梱 runtime lock の `cpsam_v2` と完全一致し、既定を維持 |
| `candidate` | 未搭載なら `null`、搭載時は `{model, status, limits}`。model は baseline と同じ identity 構造、status は `experimental`、limits は科学的制約。選択はUIで明示し既定へ昇格しない |

統合イメージのビルド・レビュー時に、3イメージへ実内容を表す
`org.opencontainers.image.revision`、`io.cytellect.lab-contract=manual-v1`、
`io.cytellect.baseline-sha256`、`io.cytellect.candidate-sha256`（非搭載は `none`）を
付与する必要があります。Web はさらに `io.cytellect.api-origin=http://127.0.0.1:8001`
と `io.cytellect.desktop-owner=true` が必要です。ラベル付与だけで機能や重みを実装した
扱いにはせず、実ファイル、モデル取得、receipt、B0への復帰を別途確認します。
この変更では Dockerfile、モデル、PR61/62/63 を取り込んでいません。

固定版定義は単独の Compose ファイルです。既存の開発用 Compose、`.env`、
`COMPOSE_*` / `CYTELLECT_*` による固定条件の上書きを持ち込まず、解決後の
イメージ・環境・ポート・mount・隔離条件を検査します。`DOCKER_*` による転送先指定も拒否し、
ローカル Docker Desktop の named pipe / Linux amd64 engine に限定します。
研究室のOS・RAM・Docker割当・空き容量の適合、実イメージ起動、ブラウザ保存・修正、
実画像での推論・測定、バックアップ復元は未受入です。メタデータ検査の成功を
これらの成功と区別してください。

worker の上限5GiBと `CYTELLECT_WORKER_MEMORY_MB=4096` は既存設定を維持しています。
対象研究室の実画像・実イメージで十分という検証結果ではありません。初回の実起動受入で
ピーク使用量と停止時の保存を確認し、不足する場合は設定変更を別途レビューします。

## 通常の開発用起動

Windows側のPythonやFijiを使わず、LinuxコンテナのWeb・API・Fijiワーカーを起動します。Docker DesktopをLinuxコンテナで起動してください。Compose 2.24.4以降が必要です。

リポジトリのPowerShellから実行します。

```powershell
.\scripts\docker-desktop.ps1 Start
```

ブラウザで **http://127.0.0.1:3087/** を開きます。初回は自分だけが見られるターミナルで次を実行し、表示された一度限りの招待コードを入力してください。コードをIssue、チャット、共有ログへ貼り付けないでください。

```powershell
.\scripts\docker-desktop.ps1 Invite
```

以後の操作はブラウザで行います。[公開画像の手順](quickstart.ja.md)の画像登録以降を利用できます。BBBC013の核染色はDRAQ、蛍光標識はFKHR-EGFPです。公開画像の視野を独立実験として扱わないでください。

```powershell
.\scripts\docker-desktop.ps1 Status
.\scripts\docker-desktop.ps1 Stop
```

`Stop`はサービスを停止し、データやFijiイメージを削除しません。`Start`は更新されたソースをビルドし、変更のない依存・Fijiレイヤーを再利用します。最初の構築にはネット接続と数GBの容量が必要です。Windows版FijiはLinuxコンテナから実行できないため、Linux版が一度別途必要です。

画像と結果は専用の`cytellect-human-e2e_research`ボリュームに保持され、GitやWindowsの既存インストールとは分離されます。初期化サービスはボリューム直下の所有者と権限だけを設定し、研究ファイルには触れません。アプリ内の削除と24時間の保存期限が適用されます。停止中の期限切れデータは再起動後に回収されます。`docker compose down -v`やDockerの初期化はデータを失うため、通常の停止に使わないでください。

Web3087/API8001は127.0.0.1にだけ公開します。APIはDocker Desktopのポート転送のため通常ブリッジにも接続します。API自体の外向き通信遮断は保証しません。Fijiワーカーは引き続き`network_mode: none`、非root、読み取り専用root、上限5GiBで実行します。このローカル解析UIはGA4を読み込みません。

## 起動時の問題

- Dockerが起動しない場合は、まずDesktop側のエラーを確認します。Cytellectの再インストールではDocker自体のエラーは直りません。
- 使用中の3087/8001がある場合、他アプリを停止せずポート競合を確認してください。変更時はComposeのWeb/API URLとポートを一緒に変更します。
- WindowsでDockerの`dockerInference`ソケットにエラー1920が発生する場合があります。実際の原因を確認せずFactory ResetやWSL削除を実行しないでください。

この手順での動作確認はDocker版の確認です。Windowsネイティブ配布物のインストール成否や、人による使いやすさの評価とは別に記録します。

## 開発者の数値・再実行検査

クリーンなソースから構築するときは、APIとWorkerに同じ
`CYTELLECT_CODE_REVISION`（40桁のGitコミット）を渡します。`compose.yaml`が
この値を解析出力の環境記録へ引き継ぎます。変更したファイルがある状態を
そのコミットの実物として扱わないでください。

`scripts/verify_docker_regions.py`は、専用の受入環境で生成画素を登録し、
独立・対応あり比較、順位検定、相関、出力ZIPのハッシュと再計算一致を確認します。
Windows配布物の検査と同じ参照式を再利用しますが、Dockerの招待認証を使い、
Windowsのインストール成功には数えません。出力先はrepo外に設定します。
