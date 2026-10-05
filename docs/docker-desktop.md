# Docker Desktopでのブラウザ操作

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
