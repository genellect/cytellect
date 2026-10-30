# リリースの署名（アプリ内更新）

Windows 版のアプリ内更新は、オーナーの Ed25519 鍵で署名された manifest だけを信頼する。この文書は、その鍵の作成・登録・公開鍵の組み込み・配布・交換・失効の手順を、オーナーが一人で再現できる形でまとめる。仕組みと信頼の前提は[データ保護](security.md#windows-local-mode)、更新の流れは[ローカル配布](local.md)にある。

## 仕組み

- リリースごとに `Cytellect-update-<版>.json`（版、インストーラーのファイル名・SHA-256・大きさ、ソースのコミット、発行時刻）と、その署名 `Cytellect-update-<版>.json.sig` を添付する。
- 署名は `.github/workflows/local-release.yml` の `draft` ジョブが行う。このジョブは environment `release` で動き、オーナーが承認するまで始まらない。secret `UPDATE_SIGNING_KEY` で `ssh-keygen -Y sign -n cytellect-update` を実行し、アプリと同じ検証（`scripts/update_manifest.py verify`）で確かめてから、タグと下書きのリリースを作る。secret がない場合や、組み込んだ公開鍵と合わない場合は、何も作らずに止まる。
- インストール済みのアプリは、組み込んだ公開鍵（`services/api/src/cytellect_api/update_signature.py` の `UPDATE_PUBLIC_KEY`）で署名を確かめ、manifest の版と、インストーラーの SHA-256 と大きさが一致したときだけ実行する。リリースの `.sha256` と GitHub の digest は信頼の起点にしない。
- 公開鍵が空の版は、アプリ内で更新しない。新しい版があれば「新しい版のインストーラーを開いてください」と表示する。
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

1. **Actions → Prepare Windows release** を `main` で実行する。
2. `package` ジョブの後、`draft` ジョブが承認待ちになる。内容を確かめて **Approve** する。
3. 下書きのリリースに `Cytellect-Setup-<版>.exe`、`Cytellect-update-<版>.json`、`Cytellect-update-<版>.json.sig` があることを確かめてから公開する。

手元で署名を確かめる場合は、公開鍵から `allowed_signers` というファイルを作り（1 行：`cytellect-update ssh-ed25519 AAAA...`）、ダウンロードした 2 つのファイルと同じフォルダーで実行する。

```sh
ssh-keygen -Y verify -f allowed_signers -I cytellect-update -n cytellect-update -s Cytellect-update-<版>.json.sig < Cytellect-update-<版>.json
```

## 5. 鍵を交換する（計画的な交換）

方針：新しい公開鍵を含む版を、古い鍵で署名して配る。インストール済みのアプリは古い鍵でその版を受け入れ、以後は新しい鍵を信頼する。

1. 手順 1 で新しい鍵を作る（ファイル名は `cytellect-update-2` など）。
2. 新しい公開鍵を `UPDATE_PUBLIC_KEY` に入れる PR を作り、マージする。
3. secret は**古い鍵のまま**で、この版を手順 4 で配布する。`draft` ジョブの検証は、この版に組み込んだ新しい鍵では合わないが、最後に公開したリリースに組み込まれていた古い鍵で合うため、通る。
4. 交換の版を公開した後で、secret `UPDATE_SIGNING_KEY` を新しい秘密鍵に置き換える（同じ名前で上書きする）。以後の版は新しい鍵で署名される。古い秘密鍵は、交換の版が行き渡るまで保管してから削除する。
5. 交換の版を飛ばして古い版から直接更新しようとしたアプリは、新しい鍵の署名を受け入れず `update_signature_wrong_key` で止まる。その研究者には、新しい版のインストーラーで導入してもらう。

## 6. 鍵が漏れた、または失ったとき（失効）

組み込んだ公開鍵をネットワーク越しに無効にする仕組みはない。漏れた鍵で署名されたリリースを悪用するには、`genellect/cytellect` にリリースを公開する権限も必要になる。

1. すぐに `release` environment の secret `UPDATE_SIGNING_KEY` を削除する。漏れた場合は、リポジトリの書き込み権限と、公開済みのリリースに不審なものがないかも確かめる。
2. 新しい鍵を作り（手順 1〜3）、新しい公開鍵を組み込んだ版を、新しい鍵で署名して配布する。
3. 古い鍵を信頼している既存のインストールは、新しい鍵の署名を受け入れない（`update_signature_wrong_key`）。漏れた鍵での交換（手順 5）は行わず、研究者には新しい版のインストーラーで導入するよう案内する。
