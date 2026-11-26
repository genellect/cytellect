# リリースの署名（アプリ内更新）

Windows 版のアプリ内更新は、オーナーの Ed25519 鍵で署名された manifest だけを信頼する。この文書は、その鍵の作成・登録・公開鍵の組み込み・配布・交換・失効の手順を、オーナーが一人で再現できる形でまとめる。仕組みと信頼の前提は[データ保護](security.md#windows-local-mode)、更新の流れは[ローカル配布](local.md)にある。

## 仕組み

パッケージ作成の前に、配布するソースと同じ SHA と、Windows に組み込む接続先で解析提案・考察の版を検査する。配布用の `PROPOSAL_PREFLIGHT_URL` と `PROPOSAL_PREFLIGHT_DEVICE_TOKEN` は、手動配布と Store ではオーナーの承認を必須にした `proposal-preflight`、EXE の自動配布では `windows-exe-preflight` に置き、検査ジョブだけで使う。repository secret、署名・パッケージのジョブへ渡さない。Store のパッケージと定期提出にも同じ検査を必須とする。未設定・不一致は配布を止める。[設定と検査の手順](proposal-deployment.md#required-prompt-version-check-before-distribution)を先に満たす。

- リリースごとに `Cytellect-update-<版>.json`（版、インストーラーのファイル名・SHA-256・大きさ、ソースのコミット、発行時刻）と、その署名 `Cytellect-update-<版>.json.sig` を添付する。
- 署名は `.github/workflows/local-release.yml` の `draft` ジョブが行う。手動配布はオーナーが承認する `release`、EXE の自動配布はオーナーが有効にした `windows-exe-publish` 環境で動く。secret `UPDATE_SIGNING_KEY` で `ssh-keygen -Y sign -n cytellect-update` を実行し、アプリと同じ検証（`scripts/update_manifest.py verify`）で確かめてから、タグと下書きのリリースを作る。secret がない場合や公開鍵と合わない場合は公開せずに止まる。自動配布では再試行に使うタグが先に作られる。
- インストール済みのアプリは、組み込んだ公開鍵（`services/api/src/cytellect_api/update_signature.py` の `UPDATE_PUBLIC_KEY`）で署名を確かめ、manifest の版と、インストーラーの SHA-256 と大きさが一致したときだけ実行する。リリースの `.sha256` と GitHub の digest は信頼の起点にしない。
- 公開鍵が空の版は、アプリ内で更新しない。新しい版があれば「cytellect.app から新しい版のインストーラーをダウンロードして開いてください」と表示する。
- 署名を確かめた後のインストーラーの失敗は、段階で区別して記録する：起動できない（`update_installer_launch_failed`）、1 時間以内に終わらない（`update_installer_timeout`）、0 以外で終了（`update_install_failed` と終了コード）。どれも今の版のまま動く。インストーラーのログ（`updates/installer.log`）は PC の中に残し、送らない。
- Microsoft Store 版はアプリ内で更新しない（Store が更新する）。作業画面に更新の案内を表示しない。
- 秘密鍵はリポジトリ・Issue・PR・チャット・CI のログに置かない。CI と試験は、実行のたびに生成する試験用の鍵を使う。

## 1. 鍵を作る（初回）

オーナーの PC で行う。Windows では PowerShell、macOS と Linux ではターミナルで実行する（Windows 10 以降には `ssh-keygen` が入っている）。

```sh
ssh-keygen -t ed25519 -N "" -C "cytellect-update" -f cytellect-update
```

- `cytellect-update` が秘密鍵、`cytellect-update.pub` が公開鍵（1 行）になる。
- 署名は CI が人の入力なしで行うため、パスフレーズは付けない（`-N ""`）。その代わり、秘密鍵のファイルはパスワード管理ソフトなど暗号化された場所に保管し、作業用のフォルダーからは削除する。鍵の交換（手順 5）で、この秘密鍵をもう一度使う。

## 2. GitHub に登録する

1. リポジトリの **Settings → Environments → New environment** で `release` を作る。**最初のリリースを実行する前に作ること**。workflow が存在しない environment を参照すると、保護のない environment が自動で作られる。
2. `release` の **Required reviewers** にオーナー（`genellect`）を加える。**Deployment branches and tags** は **Selected branches and tags** にして、`main` だけを許可する。
3. 同じ画面の **Environment secrets → Add environment secret** で、名前 `UPDATE_SIGNING_KEY`、値に秘密鍵ファイルの内容全体（`-----BEGIN OPENSSH PRIVATE KEY-----` から `-----END OPENSSH PRIVATE KEY-----` まで）を貼り付けて保存する。リポジトリ全体の secret には登録しない。

## 3. 公開鍵をアプリに組み込む

`cytellect-update.pub` の 1 行を、`services/api/src/cytellect_api/update_signature.py` の `UPDATE_PUBLIC_KEY = ""` の引用符の中に貼り付け、PR にしてマージする。

```python
UPDATE_PUBLIC_KEY = "ssh-ed25519 AAAA... cytellect-update"
```

この変更を含む版から、アプリ内で更新できるようになる。それより前の版（公開鍵が空の版）を使っている研究者は、その版をインストーラーで導入する。

現在の鍵（2026-10-30 に登録、0.1.0-local.21 から組み込み）：

| 項目 | 値 |
|---|---|
| 公開鍵 | `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKocg34zCZzyroJ93ELi0k02Hud++1pCaC2zVAjYA1Bs cytellect-update` |
| 指紋（`ssh-keygen -lf`） | `SHA256:e+/Hqvnc6NQjwkai0f8FTLXC6i+EcvnBv/V0gQ5A7YU` |

組み込んだ鍵は `update_signature.py` が正本で、この表はその写し。鍵を交換したら両方を同じ PR で更新する。

## 4. 配布する

### EXE の自動配布

オーナーが有効化すると、`main` への push の `Verify` が成功した時点で `Prepare Windows release` が起動する。直近に成功したコミットを `main` の履歴順で選び、同じ SHA の配布を再開するときは、予約済みのタグと有効期限内の検証済み成果物を使う。手動の配布と同じインストール試験と署名を通し、下書きの添付物の SHA-256 を照合して公開する。公開済み manifest の署名を `main` または直前の保護済み配布記録のソースに組み込まれた公開鍵で検証し、EXE の記録と一致したら、`windows-exe-channel` ブランチの `windows-exe.json` を更新する。公式サイトはこの記録から版を選び、アプリ内更新は GitHub Releases から選ぶ。

有効化はオーナーが行う。

1. GitHub の `windows-exe-preflight`、`windows-exe-publish`、`windows-exe-channel` environments を作成し、デプロイ元を `main` に限定する。自動経路には実行ごとの承認者を設定しない。
2. `windows-exe-preflight` に変数 `PROPOSAL_PREFLIGHT_URL` と秘密 `PROPOSAL_PREFLIGHT_DEVICE_TOKEN`、`windows-exe-publish` に秘密 `UPDATE_SIGNING_KEY` を登録する。[配布前の互換性検査](proposal-deployment.md#required-prompt-version-check-before-distribution)とこの文書の鍵の手順を使う。
3. 配布記録の更新専用に非公開の GitHub App を作成する。権限は Contents の読み書きと必須の Metadata の読み取りに絞り、`genellect/cytellect` だけにインストールする。`windows-exe-channel` の作成・更新・削除を制限する ruleset では、この App のみを例外にする。同名の environment に変数 `WINDOWS_EXE_CHANNEL_APP_CLIENT_ID` と秘密 `WINDOWS_EXE_CHANNEL_APP_PRIVATE_KEY` を設定する。自動配布を無効にした状態で Actions の `channel_only` を選び、現在の公開版を検証して記録を書き込む。通常の書き込み権限がこのブランチを更新できないことも確かめる。
4. 初回の配布候補を確認し、リポジトリ変数 `WINDOWS_EXE_AUTO_RELEASE` を `true` にする。次の `Verify` 成功時、定期実行時、または Actions の `automatic` を選んだ手動起動時に配布を進める。
5. Actions の公開ログと保護された配布記録を確認する。Vercel の Production に `WINDOWS_EXE_CHANNEL_ENABLED=true` を設定し、本番サイトに反映する。公式サイトからの取得・新規導入と、既存版からのアプリ内更新を Windows で確認する。以後、サイトの記録は GitHub とサイトのキャッシュを経て反映される。

停止時は `WINDOWS_EXE_AUTO_RELEASE` を無効にし、進行中の自動配布を Actions で取り消す。修正後は `automatic` で起動する。公開後にサイト反映だけ失敗した場合も同じ操作で再開でき、すでに公開した EXE の版・ファイルを再利用する。6時間ごとの実行も公開記録を再確認する。定期実行は、版を予約済みで検証済み成果物のない候補を作り直さない。失敗した候補は、新しいコミットの `Verify` 成功か `automatic` の起動で再試行する。新しいコミットに置き換わった候補のタグと下書き（本文に `cytellect-windows-exe-auto` の印がある未公開のもの）は残り、その版番号は使われない。不要なものはオーナーが削除する。手動配布を行うときは、先に `WINDOWS_EXE_AUTO_RELEASE` を無効にする。有効なままでは、後から起動した自動配布が、待機中の手動配布を取り消す。公開済み版の差し替えが必要な場合は、修正した `main` を新しい版として配布する。緊急の手動配布は下記の手順に従う。署名鍵を交換するときは自動配布を停止し、手順 5 の配布を済ませてから再開する。

### 手動配布

1. **Actions → Prepare Windows release** を、ブランチ `main` のまま実行する。`automatic` は選ばず、`version` に新しい版を入れ、`commit` に配布するコミットの SHA（40 文字）を入れる。`commit` を空にすると、実行した時点の `main` の先頭を配布する。
2. `package` ジョブの後、`draft` ジョブが承認待ちになる。内容を確かめて **Approve** する。
3. 下書きのリリースに `Cytellect-Setup-<版>.exe`、`Cytellect-update-<版>.json`、`Cytellect-update-<版>.json.sig` があり、本文が研究者向けの文になっている（[CI](ci.md) の配布の節）こと、実行の Summary の `Source:` が指定したコミットであることを確かめてから公開する。
4. 公開した後、サイトの「Windows版をダウンロード」をインストーラーに切り替える。公開されたインストーラーを取得して SHA-256 を確かめてから、別の PR で `apps/web/src/lib/published-release.json` の `version`、`asset`（`installer`）、`url`、`sha256`、`source_commit`、`size_bytes` を更新する（[手順](../apps/web/README.md#windows-release-link)）。公開前の版を記録しない。

手元で署名を確かめる場合は、公開鍵から `allowed_signers` というファイルを作り（1 行：`cytellect-update ssh-ed25519 AAAA...`）、ダウンロードした 2 つのファイルと同じフォルダーで実行する。

```sh
ssh-keygen -Y verify -f allowed_signers -I cytellect-update -n cytellect-update -s Cytellect-update-<版>.json.sig < Cytellect-update-<版>.json
```

### CI が通った `main` のコミットを指定する

マージが続くと、`main` の先頭の CI（約 55 分）が終わる前に次のコミットが入る。その間も、CI がすべて通った前のコミットを `commit` に指定すれば配布できる。`main` の CI は後のマージで取り消されないため、どのコミットにも完全な結果が残る（[CI の構成](ci.md#配布の条件)）。

- 指定できるのは、`main` の先頭か、その祖先のコミットで、[配布の条件](ci.md#配布の条件)の 9 つのジョブがすべて成功したものだけ。候補は **Actions → Verify** で、ブランチ `main`、イベント `push` の成功した実行から探せる（`gh run list --workflow ci.yml --branch main --event push --status success`）。
- 小文字の 16 進 40 文字以外（短い SHA、大文字、ブランチ名・タグ名）と、`main` にないコミットは、最初の `source` ジョブが何も作らずに止める。8 つのジョブの成功も、ここでそのコミットについて確かめる。
- 以後の `package` と `draft` は、そのコミットだけを checkout する。ZIP、インストーラー、対応するソース、受入のレシート、署名した manifest の `source_commit`、タグ、リリースは、すべてそのコミットを指す。`draft` は、checkout がそのコミットで `main` の祖先であることと、インストーラーのレシートの `source_commit` が一致することを、署名の前にもう一度確かめる。
- workflow 自体は常に `main` の先頭のものが動き、手動配布では、`release` environment の承認・`main` だけの許可・secret の確認・既存のタグとリリースの拒否は変わらない。署名の検証は、そのコミットに組み込まれた公開鍵か、最後に公開したリリースの鍵で行う。
- インストーラーや署名の仕組みが入る前の古いコミットは、途中のジョブで止まり、タグもリリースも作らない。

## 5. 鍵を交換する（計画的な交換）

方針：新しい公開鍵を含む版を、古い鍵で署名して配る。インストール済みのアプリは古い鍵でその版を受け入れ、以後は新しい鍵を信頼する。

1. 手順 1 で新しい鍵を作る（ファイル名は `cytellect-update-2` など）。
2. 新しい公開鍵を `UPDATE_PUBLIC_KEY` に入れる PR を作り、マージする。
3. secret は**古い鍵のまま**で、この版を手順 4 で配布する。`draft` ジョブの検証は、この版に組み込んだ新しい鍵では合わないが、最後に公開したリリースに組み込まれていた古い鍵で合うため、通る。
4. 交換の版を公開した後で、`release` と `windows-exe-publish` の両方の environment の secret `UPDATE_SIGNING_KEY` を新しい秘密鍵に置き換える（同じ名前で上書きする）。以後の版は新しい鍵で署名される。古い秘密鍵は、交換の版が行き渡るまで保管してから削除する。
5. 交換の版を飛ばして古い版から直接更新しようとしたアプリは、新しい鍵の署名を受け入れず `update_signature_wrong_key` で止まる。その研究者には、新しい版のインストーラーで導入してもらう。

## 6. 鍵が漏れた、または失ったとき（失効）

組み込んだ公開鍵をネットワーク越しに無効にする仕組みはない。漏れた鍵で署名されたリリースを悪用するには、`genellect/cytellect` にリリースを公開する権限も必要になる。

1. すぐに `WINDOWS_EXE_AUTO_RELEASE` を無効にし、`release` と `windows-exe-publish` の両方の environment の secret `UPDATE_SIGNING_KEY` を削除する。漏れた場合は、リポジトリの書き込み権限と、公開済みのリリースに不審なものがないかも確かめる。
2. 新しい鍵を作り（手順 1〜3）、新しい公開鍵を組み込んだ版を、新しい鍵で署名して配布する。
3. 古い鍵を信頼している既存のインストールは、新しい鍵の署名を受け入れない（`update_signature_wrong_key`）。漏れた鍵での交換（手順 5）は行わず、研究者には新しい版のインストーラーで導入するよう案内する。
