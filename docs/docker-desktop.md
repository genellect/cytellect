# Docker Desktop で使う

Windows に Python や Fiji を入れずに、Docker Desktop の Linux コンテナで Cytellect を動かす手順。Web 画面、API、解析ワーカーの 3 つのコンテナを起動し、この PC のブラウザーから使う。

| 項目 | 内容 |
|---|---|
| 対象 | ソースから Cytellect を動かす研究者・研究室の管理者 |
| 対象版 | このリポジトリの現在のソース |
| 操作 | リポジトリの [`scripts/docker-desktop.ps1`](../scripts/docker-desktop.ps1) を PowerShell から実行する |
| Windows 版との違い | 配布版のセットアップは不要。Fiji と Cellpose はビルド中にコンテナへ自動で取得される |
| Cellpose | 解析ワーカーの CPU で実行する。ワーカーはネットワークから切り離されているため、[クラウド GPU](cloud-gpu.ja.md) は使えない |

## 1. 動作環境

| 項目 | 必要な条件 |
|---|---|
| Docker | Linux コンテナで動作している Docker Desktop（Docker Compose 2.24.4 以降） |
| メモリ | 解析ワーカーに最大 5 GiB を割り当てられること |
| 空き容量 | 数 GB 以上。解析ワーカーのイメージに Linux 版 Fiji と Cellpose の実行環境・モデル（約 1.2 GB）が入る |
| ネットワーク | 初回ビルドと更新のときに、依存関係・Fiji・Cellpose を取得する |
| ソース | このリポジトリを置いたフォルダー |

## 2. 初回の起動

1. リポジトリのフォルダーで PowerShell を開き、ビルドと起動を行う。

   ```powershell
   .\scripts\docker-desktop.ps1 Start
   ```

   初回は Fiji と Cellpose の取得を含むため時間がかかる。すべてのサービスが準備できると `Cytellect: http://127.0.0.1:3087/` と表示される。

2. ブラウザーで [http://127.0.0.1:3087/](http://127.0.0.1:3087/) を開く。招待コードやパスワードの入力は不要で、この PC の所有者として自動でワークスペースに接続する。

## 3. 起動と終了

| 操作 | コマンド | 内容 |
|---|---|---|
| 起動して開く | `.\scripts\docker-desktop.ps1 Open` | ビルド済みのイメージで起動し、ブラウザーを開く |
| 更新して起動 | `.\scripts\docker-desktop.ps1 Start` | 現在のソースからビルドし直して起動する |
| 状態の確認 | `.\scripts\docker-desktop.ps1 Status` | 各サービスの状態を表示する |
| 終了 | `.\scripts\docker-desktop.ps1 Stop` | サービスを停止する。画像・解析結果・イメージは残る |

`Stop` で止めていない場合、サービスは Docker Desktop の起動とともに自動で再開する。

- **研究データの保存**：画像と解析結果は、Docker が管理する専用ボリューム `cytellect-human-e2e_research` だけに置かれる。Git の作業フォルダーや Windows 版の保存先とは別。
  - 作業データは、最後に明示的な操作をしてから 24 時間で削除される。停止中に期限を過ぎたデータは、次に起動したときに削除される。必要な結果は期限内に書き出す。
  - 期限なしで保持したい研究室は、[研究室で作業データを手動保持する](#8-研究室で作業データを手動保持する)を参照する。
- **接続**：Web（3087）と API（8001）は `127.0.0.1` にだけ公開され、この PC からのみ接続できる。招待コードなしで接続できるのは、この公開範囲が前提。ポートを `0.0.0.0` で公開したり、外部のプロキシの背後に置いたりしない。
  - ブラウザーのログイン状態は 7 日間有効で、期限が切れても画面を開き直せば同じ所有者として再接続する。
- **通信**：解析ワーカーはネットワークなし（`network_mode: none`）、非 root ユーザー、読み取り専用のルートファイルシステム、メモリー上限 5 GiB で動作する。
  - API コンテナは Docker Desktop のポート転送のためにブリッジネットワークにも接続するため、API 自体の外向き通信が遮断される保証はない。
  - このローカル解析画面は GA4 を読み込まない。

## 4. 動作確認（初回のみ）

1. [はじめての画像解析](quickstart.ja.md)の「1. 準備する」で練習画像を入手し、「2. 測ることを決める」から進める。同ガイドの詳細画面は [http://127.0.0.1:3087/legacy](http://127.0.0.1:3087/legacy) で開く。Windows 版の起動に関する記述は読み飛ばす。
2. 公開練習画像 BBBC013 の核染色は DRAQ、蛍光標識は FKHR-EGFP。この画像の視野を、独立した実験の繰り返しとして扱わない。
3. 練習画像の結果は操作の確認用で、研究画像での検出精度を保証するものではない。

この手順での動作確認は Docker 版の確認であり、Windows ネイティブ版のインストール確認や、利用者による使いやすさの評価とは別に記録する。

## 5. 更新

1. 新しい版のソースを取得し、ビルドし直して起動する。

   ```powershell
   git pull
   .\scripts\docker-desktop.ps1 Start
   ```

2. 更新時の動作は次のとおり。
   - 研究データ（`cytellect-human-e2e_research`）は保持される。
   - 変更のない依存関係と Fiji・Cellpose のレイヤーは再利用され、変更された部分だけがビルドし直される。
3. 更新のために `docker compose down -v`、Docker の prune、Docker Desktop の初期化を行わない。保存データが失われる。

## 6. 困ったとき

| 表示・症状 | 対処 |
|---|---|
| `Install and start Docker Desktop with Linux containers first.` | Docker Desktop をインストールし、Linux コンテナで起動する |
| `Start Docker Desktop and wait until its Linux engine is running.` | Docker Desktop を起動し、Linux エンジンの準備が終わってから再実行する。Docker Desktop 自体がエラーを表示している場合は、Cytellect を入れ直しても解決しない |
| 3087 または 8001 ポートが使用中 | そのポートを使っているアプリを確認し、ポートを空ける。自動接続は `127.0.0.1:3087`（Web）と `127.0.0.1:8001`（API）に固定されているため、Compose のポートを変更すると接続できなくなる |
| 画面が「接続を確認しています」から進まない、またはエラーになる | `Status` で全サービスが起動しているか確認し、「再接続」を押す |
| Windows で `dockerInference` ソケットのエラー 1920 | 原因を確認する前に Factory Reset や WSL の削除を行わない。保存データが失われる |

## 7. アンインストール

1. 必要な結果を書き出したことを確認する。
2. リポジトリのフォルダーで次を実行し、コンテナ・イメージ・保存データのボリュームを削除する。ボリュームを削除すると、作業データと、この PC の所有者としての接続情報がすべて失われる。

   ```powershell
   $env:CYTELLECT_RUNTIME_DIR = '/unused'
   docker compose --project-name cytellect-human-e2e -f compose.yaml -f infra\compose.desktop.yaml down -v --rmi all
   ```

## 8. 研究室で作業データを手動保持する

研究室向けの任意設定 [`infra/compose.lab.yaml`](../infra/compose.lab.yaml) を使うと、作業データを 24 時間で削除せず、利用者がアプリ内で削除するまで保持できる（保存方式 `manual`）。PC の停止や再起動でも期限切れにならない。画面には手動保持であることが表示され、期限延長の操作は表示されない。ログイン状態の有効期限、所有権の確認、ジョブの停止・取消、明示的な削除は通常どおり働く。

この設定は実装済みだが、配布物としての受入確認はまだ済んでいない。固定版イメージの配布や、検証済みのバックアップ手段は含まない。

### 研究室用インストールを起動する

手動保持は、通常のインストールとは別名の、研究室用インストールにだけ適用する。通常の設定に重ねたり、稼働中のインストールを切り替えたりしない。

1. 通常のインストールを停止する。研究室用も同じポートを使うため、同時には起動できない。

   ```powershell
   .\scripts\docker-desktop.ps1 Stop
   ```

2. 研究室用インストールをビルドして起動する。データは別のボリューム `cytellect-lab_research` に保存される。

   ```powershell
   $env:CYTELLECT_RUNTIME_DIR = '/unused'
   docker compose --project-name cytellect-lab -f compose.yaml -f infra\compose.desktop.yaml -f infra\compose.lab.yaml up -d --build --wait --wait-timeout 180
   ```

   `CYTELLECT_RUNTIME_DIR` は Compose の必須変数を満たすための値で、実際の保存先は上記のボリューム。

3. ブラウザーで [http://127.0.0.1:3087/](http://127.0.0.1:3087/) を開く。停止・状態確認は、手順 2 と同じ `--project-name` と `-f` の指定で `stop`・`ps` を実行する。`docker-desktop.ps1` は通常のインストールを操作するため、研究室用には使わない。

### 保存方式の切り替えに関する制約

手動保持にしたボリュームには、空の `.manual-workspace-retention` マーカーが置かれる。

- バックアップ・復元では、データベース・成果物と一緒にマーカーも保持する。
- マーカーのあるボリュームを期限付き保存（TTL）で起動すると、データベースを開く前に停止する。稼働中にマーカーを削除したり、保存方式を切り替えたりしない。
- 手動保持から TTL への切り替えには対応していない。保存済みの期限によってデータがすぐに削除される可能性があるため。
- TTL から手動保持へ切り替えるときは、書き込みを行うすべてのサービスを先に停止する。古いプロセスで進行中の削除処理は、マーカーでは止められない。
- 手動保持に対応していない古い版で、手動保持のボリュームを開かない。戻す必要がある場合は、記録された保存方式に対応するバックアップを復元する。
- マーカーの作成時は書き込みを同期するが、停電後の復旧は検証していない。クラッシュに耐えるバックアップを保証するものではない。

### 手動保持中のデータ管理

手動保持では古いデータが自動で削除されない。研究室で空き容量を監視し、不要な作業をアプリから削除し、必要な結果を書き出す。名前付きボリュームだけではバックアップにならないため、データは別の媒体にもバックアップする。データベースと成果物をまとめたバックアップ・復元・ロールバックの検証は、配布の要件として別途残っている。

## 9. 開発者・運用者向け

### 解析結果に記録されるコミット

`docker-desktop.ps1` は、作業フォルダーに未コミットの変更がないとき、現在の Git コミット ID（40 桁）を `CYTELLECT_CODE_REVISION` として API とワーカーに渡し、解析結果の環境記録に残す。未コミットの変更がある場合は空にし、変更を含むビルドをそのコミットとして記録しない。

### 数値と再実行の受入検査

[`scripts/verify_docker_regions.py`](../scripts/verify_docker_regions.py) は、生成したテスト画像を登録し、独立・対応ありの比較、順位検定、相関、出力 ZIP のハッシュ、再計算結果との一致を確認する。研究データの入っていない受入用のインストールを、未コミットの変更がない状態で `Start` してから、[開発環境](../CONTRIBUTING.md)のリポジトリで実行する。出力先には、リポジトリの外のまだ存在しないフォルダーを指定する。

```powershell
uv run python scripts/verify_docker_regions.py --docker docker --container cytellect-human-e2e-api-1 --api-origin http://127.0.0.1:8001 --web-origin http://127.0.0.1:3087 --expected-source (git rev-parse HEAD) --output <リポジトリ外の新しいフォルダー>
```

この検査は Docker の招待認証を使い、Windows 版のインストール確認には数えない。生物学的な妥当性を確認するものでもない。

### 解析提案の中継

運用者は `-ProposalConfig` で、承認済みの解析提案の中継を有効にできる。設定ファイルの形式と制約は[ローカル版の説明](local.md#workspace-entry-and-desktop-acceptance-2026-10-06)を参照する。

### 招待コード

`.\scripts\docker-desktop.ps1 Invite` は、24 時間有効で一度だけ使える招待コードを発行する。Docker Desktop 版は招待コードなしで接続するため、通常の利用では使わない。発行する場合は自分だけが見られる端末で行い、Issue、チャット、共有ログに貼り付けない。

## 関連文書

- [はじめての画像解析](quickstart.ja.md)：公開画像を使った操作の練習
- [Windows 版のインストールと更新](install-windows.ja.md)：配布版を使う場合の手順
- [ローカル版のブラウザ配信](local.md)（英語）：作業画面の入口と解析提案の中継の詳細
- [データ保護と運用](security.md)（英語）：Docker Desktop の所有者接続と手動保持の設計
