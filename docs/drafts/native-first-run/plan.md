# Windows 版の初回体験（#284）：実装案

作成：2026-11-25。genellect/cytellect#284 の実装の設計・変更箇所・順序・試験を定める。状態：実装は未着手。

**役割の分担**　症状、再現手順、証拠、原因の分析、合格条件は Issue に書かれており、要求の正本は Issue とする。この文書はそれらを繰り返さず、Issue の該当箇所を名前で参照する。Issue と食い違う場合は Issue が正しく、この文書を直す。

## 1. 作業を始める前に

- [AGENTS.md](../../../AGENTS.md) と、[Issue #284](https://github.com/genellect/cytellect/issues/284) の全文を読む。担当する作業単位が参照する Issue の節（[§3](#3-issue-の項目と作業単位の対応)）は、添付の画面とログまで確かめる。
- Issue の実機は Windows インストール版 `0.1.0-local.26`（コミット `9b44ce4bed61`）。Issue が引用するソースはこのコミットに固定されている。`main`（`462c288c`）では、引用された処理は同じ内容で、行番号だけが異なる（[§4.1](#41-issue-の原因分析の確認)）。この文書は行番号を使わず、ファイルと関数・部品の名前で示す。
- Issue は実機で確かめた結果である。開発環境で追試できない項目も実装の対象とし、原因を特定できていない項目には、原因によらず症状が出ない実装と、原因を記録する実装を割り当てた（[§4.3](#43-原因を特定できていない項目)）。
- 1 つの作業単位（[§6](#6-作業単位)）を 1 本の PR にする。終わりの条件を満たせない場合は PR の「残る課題」に書き、合格として報告しない。
- `main` へのマージ、AI の中継（`services/proposal-worker`）のデプロイ、有料の API の呼び出し、Windows 版の配布は、オーナーが明示した場合だけ行う（[§10](#10-オーナーの許可が要る操作)）。
- 関連する作業：genellect/cytellect#249（AI の導線とエラー文。再送の確認は #253、AI の設定は #254 で実装済み）、genellect/cytellect#257（画面で測定対象を示す。`main` に統合済み）、genellect/cytellect#261（EXE の自動配布。W11・W12 が前提にする）。

### Issue の参照名

この文書は、Issue の節を次の名前で参照する。

| 参照名 | Issue の箇所 |
|---|---|
| 索引 | 「どの不具合から追うか」の表 |
| 入力 1〜6 | 「入力の用意と再現の約束」の 1〜6。各項の「修正後の判定」「合格条件」を含む |
| 対照 A・B・C | 「同じ画像を使って失敗の条件を切り分けた試験」の A・B・C と、各「合格条件」 |
| 巻き込み 1〜4 | 「正常画像の作業が失敗1件に巻き込まれる工程」の「何を直すとどの症状が消えるか」1〜4 |
| 巻き込みの判定 | 同節の「改修の判定」 |
| 復旧 | 同節の「復旧メッセージの切り分け」 |
| 追試 A・B | 「AI を操作の入口にした場合に起きること」の追試 A・B |
| 判定 1〜4 | 「修正を判定するテスト」の表の 1〜4 行目 |
| 測定中 | 「測定中の表示と、作業を遮る更新案内」の測定中の表示と、その「次の追試と合格条件」 |
| 更新 | 同節の更新案内と、その「次の追試と合格条件」 |
| 優先 1〜11 | 「優先して直したい操作」の 1〜11 |
| 受入 1〜6 | 「受け入れテスト」の 1〜6 |
| 画面 NN | 「Edge の操作ログとスクリーンショット」の画像（02、03、04、06、08、10、11、13〜16）と、添付の `Cytellect-284-edge-traces.zip` の画面（19、21、22、24、25） |

## 2. 決定事項

| | 決定 | 根拠 | 改める記述（改める作業単位） |
|---|---|---|---|
| 1 | 最初の操作を画像の追加にする。実験デザインは画像の登録後に決める | Issue（優先 1、入力 1） | `docs/requirements.md` の U01（2026-10-25 の改訂）、[群間比較の要件](../group-comparison/requirements.md)の E-01（2026-10-28）、`docs/workspace-redesign.md`、`docs/web.md`（W6） |
| 2 | 登録できなかった画像について、手動の除外と理由の入力を求めない。そのために比較を止めない | 2026-11-25、オーナー。Issue（優先 6、巻き込みの判定） | `docs/web.md` の「An image the API rejects…」の段落、`region_cohorts.py` の `assemble`、契約試験（W2） |
| 3 | 同じ内容の画像は 1 つの視野にまとめる。別の撮影として扱う場合だけ、研究者がその判断を記録する | Issue（対照 A の合格条件） | `docs/requirements.md` の I12（2026-10-06）（W6） |
| 4 | AI の応答の扱いを、依頼の種類（質問、設定の変更、実行）で分ける。質問では設定を変えず、解析を実行しない | Issue（追試 A、判定 1・2、優先 8） | `docs/requirements.md` の L02（2026-10-06）（W3、W8） |
| 5 | Issue の全項目を、追試の可否によらず実装案に含める。実装はオーナーの指示を待つ | 2026-11-25、オーナー | — |

補足：

- 決定 2 が廃止する規則は、`docs/web.md`、コードのコメント、契約試験にのみ記載があり、オーナーの決定の記録はない。
- 決定 3 の理由：画素が完全に一致する 2 枚は、撮像のノイズを考えると別の撮影ではなく複製とみなせる。現在の既定は視野数（観測数として読まれる）を増やす側に働く。
- 決定 4 の理由：解析の依頼に対する自動の試行（L02）は維持する価値がある。問題は、質問と設定の変更にも同じ処理を適用し、設定の検証に失敗すると文章の回答まで破棄する点にある。
- 決定 3・4 は Issue の合格条件から導いた。オーナーが異なる判断をした場合は、W3・W6・W8 を改める。

## 3. Issue の項目と作業単位の対応

作業単位の「終わりの条件」は、この表の Issue の箇所に書かれた合格条件とする。

| Issue の項目 | 作業単位 |
|---|---|
| 入力 1（空の作業で入れる場所と対象が分からない。画面 02） | W4、W6 |
| 入力 2（選択後も「視野 0」。保留の内容が見えない。画面 03、06） | W5、W6 |
| 入力 3（追加で直前の選択が消える。画面 10、11） | W1、W6 |
| 入力 4（2 群に単一の追加先。画面 15） | W7、W8 |
| 入力 5（TXT とマスクを画像に数える。画面 16） | W5、W6 |
| 入力 6（フォルダー入力） | W1、W6、W12 |
| 対照 A（複製で視野が増える。画面 19） | W5、W6 |
| 対照 B（表記違いで全件停止。画面 21、22） | W1、W6 |
| 対照 C（破損 1 枚で正常な画像が群に入らない。画面 24、25） | W1 |
| 巻き込み 1・2（部分成功の例外と群の割付） | W1 |
| 巻き込み 3・4、巻き込みの判定（失敗票の永続化、比較の停止。画面 13、14） | W2 |
| 復旧（接続断、401、403 の区別。画面 04） | W10 |
| 追試 A（質問に形式エラー。相談・条件変更・実行の境界。画面 08） | W3、W8 |
| 追試 B（指示の持ち越し、回答の消失、再送の判断） | W3 |
| 判定 1・2 | W3、W8 |
| 判定 3・4 | W3 |
| 測定中 | W9 |
| 更新 | W11 |
| 優先 1・2 | W4、W6 |
| 優先 3・4 | W1、W5、W6 |
| 優先 5 | W7、W8 |
| 優先 6 | W1、W2 |
| 優先 7 | W2、W5、W10 |
| 優先 8 | W8 |
| 優先 9 | W3 |
| 優先 10 | W9 |
| 優先 11 | W11 |
| 受入 1 | W4〜W6、W12 |
| 受入 2 | W1、W6〜W8、W12 |
| 受入 3 | W1、W2 |
| 受入 4 | W1、W5、W6 |
| 受入 5 | W3、W8 |
| 受入 6 | W9〜W11 |
| 索引の「要切り分け」（フォルダー、サービス停止、更新ボタン） | W1・W6・W12、W10、W11 |

## 4. 調査結果

### 4.1 Issue の原因分析の確認

Issue の原因分析が `main`（`462c288c`）でも成り立つことを確かめた。「再現」は、`createWorkspaceRuntime` に対する一時的な単体試験（`use-workspace-runtime.test.ts` と同じ偽の adapter。ファイル名だけで決まる経路のため 1 バイトの合成データ）で、`main` が Issue と同じ結果を返したことを指す。試験はコミットしていない。W1・W2・W6 で、修正後の期待に書き換えて追加する。

| Issue の項目 | 確認 | `main` の該当箇所 |
|---|---|---|
| 対照 A | 再現 | `use-workspace-runtime.ts` の `importFiles`（同名のファイルに別のフォルダー名を付ける）、`grouping.ts` の `groupFiles`（視野のキーにフォルダーを含める。内容のハッシュは `duplicate_content` の警告のみ） |
| 対照 B | 再現 | 同 `importFiles`（`added` に追加した後で `duplicate_channel` を検出し、全体を例外にする。`added` を戻さない） |
| 対照 C、巻き込み 1・2 | 再現 | 同 `importFiles`（拒否が 1 件あると保存後に例外を投げる）、`ConnectedWorkspace.tsx` の `addToExperiment`（戻り値の ID でのみ群を保存する） |
| 巻き込み 3 | 再現 | `use-workspace-runtime.ts` の `failedImports`（メモリー上のみ）、`refresh`、`UnfinishedImports.tsx`、`api-adapter.ts` の `registerImport`（登録票の行は `id`・`field_id`・`revision_id`・`exclusion_reason` のみ） |
| 巻き込み 4 | コード | `region_cohorts.py` の `assemble`、契約試験 `tests/test_experiment_strata.py::test_api_refuses_a_stratum_cohort_while_a_field_or_failed_upload_is_unaccounted_for` |
| 入力 1 | コード | `panel-state.ts` の `experimentSetupShown`、`ConnectedWorkspace.tsx` の開始画面の分岐 |
| 入力 2・3 | コード | `ConnectedWorkspace.tsx` の `add`（`setPending(files)` で置き換える）、`ExperimentSetup.tsx` の保留のカード（件数のみ） |
| 入力 4 | コード | `ExperimentSetup.tsx` の `pendingTarget`、`ConnectedWorkspace.tsx` の `placePending` |
| 入力 5 | コード | `grouping.ts` の `isSupportedImage`、`importFiles` の拡張子による `continue`、`api.ts` の `region_image_bit_depth_unsupported` |
| 追試 A・B | コード | `ConnectedWorkspace.tsx` の `sendInstruction`・`newWorkspace`・AI のパネル、`use-workspace-runtime.ts` の `requestProposal`、`api.ts` の `request`（`detail.reasons` を読まない）、`proposals.py` の `draft_proposal`、`db.py` の `proposal_drafts` |
| 測定中 | コード | `use-workspace-runtime.ts` の `runServer`（分母はステップ数）、`workspace_runs.py` のステップの生成（視野 × 領域の段数）、`ConnectedWorkspace.tsx` の視野の一覧（採用済みの結果のみ参照）とプレビューの 650 ms の待機 |
| 更新 | コード | `CloudAccount.tsx` の `UpdateBanner`、`cloud-account.ts` の `updateNotice`、`app_update.py` の `run_installer`・`UpdateService._run` |

### 4.2 Issue に記載のない所見

実装に影響する点を、調査で追加で確かめた。

| | 所見 | 該当箇所 | 扱う作業単位 |
|---|---|---|---|
| 1 | 256 MiB を超えるファイルが 1 つあると、`importFiles` は取り込み全体を例外で打ち切る | `use-workspace-runtime.ts` の `importFiles` | W1 |
| 2 | 視野のキーに取り込みごとのフォルダー名（`import-<UUID>`）が入るため、2 回に分けて選んだ同じ視野の別染色は、別の視野になる | 同 `importFiles`、`grouping.ts` の `groupFiles` | W6 |
| 3 | 取り込み中は `intakeDisabled` が真になり、追加の選択を受け付けない | `ConnectedWorkspace.tsx` | W6 |
| 4 | 解析案が検証で拒否されると、API は 502 を返し、解析案に含まれる文章（`rationale`、`missing_information`）も破棄する | `proposals.py` の `draft_proposal` | W3 |
| 5 | 画像の登録後に「回答のみ」を表せる有効な解析案は、`recipe: "none"`、全チャンネルの列挙、指標と図が空、の 1 通りに限られる。プロンプトは目的の文を研究の問いの記述として扱い、質問や実行の保留を指示していない | `proposal_validation.py` の `validate_draft`、`services/proposal-worker/src/openai.ts` | W8 |
| 6 | `recipe: "none"` の応答でも、`applyProposal` は解析の仕様（指標、図の提案、統計の方法）を書き換えて保存する | `use-workspace-runtime.ts` の `applyProposal`・`requestProposal` | W3 |
| 7 | 完了した解析案を読み出す API がない。画面の解析案はメモリー上のみで、`refresh` は復元しない | `proposals.py`、`use-workspace-runtime.ts` | W3 |
| 8 | 計算ワーカーが通算 3 回終了すると、ランチャーはローカルのサービス全体を停止する。再起動の回数を戻さず、停止の理由も記録しない。ほかの停止経路（ランチャーを閉じる、更新の切り替え、親プロセスの消失）も理由を記録しない | `local.py` の `WorkerSupervisor.start`、`run_local`、`_gui` | W10 |
| 9 | セッションを作り直す API（`POST /v1/local/session`）は更新の追跡だけが使い、ほかの呼び出しは 401 でページの再読み込みを求める | `cloud-account.ts` の `reconnect`・`followUpdate`、`api.ts` | W10 |
| 10 | 更新ボタンの押下後、`update_not_available` は状態を再取得するだけで、`update_unsupported` は案内を非表示にする。どちらも利用者に結果を示さない | `CloudAccount.tsx` の `applyUpdate` | W11 |
| 11 | 更新ボタンの表示は、Issue では「アップデート」、`main` では「更新」 | `cloud-account.ts` の `updateNotice` | W11 |

### 4.3 原因を特定できていない項目

| Issue の項目 | 分かっていること | 実装での扱い |
|---|---|---|
| 追試 A：形式エラーの理由コード | 検証の理由コードは 51 種類あり、今回の値はどこにも保存されていない | W3 で理由コードを保存する。文章の回答は検証の結果によらず表示する |
| 復旧：ローカルのサービスが停止した契機 | 所見 8 の経路が存在する。今回の停止がこの経路かは未確認 | W10 で全経路の停止理由を記録し、ワーカーの停止ではサービスを止めない |
| 入力 6：フォルダーで受け取れない | 観測は Edge の拡張機能を介した操作による。手動の操作での発生は未確認 | W1 で選択の結果を必ず表示し、W6 で件数のみの診断を加え、W12 で手動の操作を確かめる |
| 更新：ボタンの無反応 | 所見 10 の 2 つの分岐が該当しうる。どの分岐かは未確認 | W11 で全分岐に結果を表示する |

## 5. 設計

### 5.1 原則

1. 取り込みは項目ごとに結果を持つ。1 項目の失敗が、ほかの項目の登録、群の割付、測定、比較を妨げない。
2. 受け取ったファイルは、役割と状態を付けてすべて一覧に表示する。受け取った件数は、役割別の内訳の合計と一致する。
3. 登録できなかった理由はアプリが記録する。名前、段階、理由コードを保存し、再起動後も同じ名前で表示する。
4. AI の文章の回答は、設定の検証の結果によらず表示する。検証が止めるのは設定の適用に限る。
5. AI は依頼された範囲だけを行う。会話はワークスペースと視野に結び付けて保存し、再表示のためにモデルを呼び直さない。
6. 操作には、その場所に受付、進行、結果のいずれかを表示する。
7. サービス、更新、接続の停止では、段階と理由コードを PC 内に記録する。記録に研究データ（ファイル名、指示の文、画素）を含めない。

科学上の規則は変えない。原画像の画素値を変更しない。測定値と統計は共通実装だけが生成する。ファイル名とフォルダーから群、実験回、染色を確定しない（E-04、I11、U02。案を提示して研究者が確定する方式はこれに反しない）。失敗した視野を記録なしに除外しない。

### 5.2 受け取りの記録（`intake_items`）

受け取ったファイルを 1 行ずつ記録する API の表を新設する。登録票（`workspace_selections`）に視野のない行を作る現在の方式（`registerImport`）は廃止する。

| 列 | 内容 |
|---|---|
| `id` | UUID。登録時の `client_upload_id` に使う（同じ ID の再送は冪等。I11） |
| `workspace_id`、`batch_id` | ワークスペースと、1 回の選択またはドロップ（取り消しの単位） |
| `name` | 選択したフォルダーからの相対パス（255 文字以内） |
| `bytes`、`sha256` | 大きさと内容のハッシュ |
| `role` | `image`（測定する画像）、`label`（マスクの候補）、`other`（画像以外）、`unreadable`（読み取り不能）、`unknown`（未判定） |
| `code` | 読み取りの理由コード（例：`region_image_bit_depth_unsupported`） |
| `state` | `received`（未登録）、`registered`、`withdrawn`（研究者が取りやめた）、`interrupted`（送信が完了していない） |
| `field_id`、`channel_id` | 登録先の視野とチャンネル |
| `duplicate_of`、`separate` | 同一内容の先行する項目の ID と、「別の撮影として追加」の記録 |
| `target` | 研究者が指定した追加先 `{run_id, group_id, sample}` |
| `stored`、`shape`、`dtype` | W5 で追加する。API が内容を保存したか、読み取った寸法と型 |

- 役割は、拡張子（`other`）と、API の共通の読み取り処理の結果（`image`、`label`、`unreadable`）だけで決める。ブラウザに別の判定を持たない。
- 導入は 2 段階とする。W2 は表と記録を導入し、内容は従来どおりブラウザから登録の API へ送る。W5 は受け取り時に内容を保存し、縮小画像と確定の API を加える。
- ファイル名は研究データとして扱い、PC 内のデータベースにのみ保存する。ログ、診断、AI への送信範囲は変えない。

### 5.3 取り込みの結果（`IntakeOutcome`）

`importFiles` の戻り値を次の形にする（W1）。W5 の確定の API も同じ形で返す。

```ts
interface IntakeOutcome {
  registered: Array<{fieldId: string; names: string[]}>;
  rejected:   Array<{item: string; names: string[]; code: string}>;   // API の拒否、大きさの上限
  held:       Array<{names: string[]; reason: "duplicate_channel" | "duplicate_content"}>; // 判断待ち。未送信
  skipped:    Array<{name: string}>;                                  // 画像以外
}
```

項目単位の失敗では例外を投げない。例外（`IntakeInterrupted`）は、作業全体を継続できない場合（応答なし、セッション切れ、ワークスペースの変更、容量の上限）に限り、その時点までの `IntakeOutcome` を保持する。

### 5.4 会話の記録（`assistant_messages`）

研究者の発言を 1 行ずつ記録する API の表を新設する。`proposal_drafts`（同一の依頼に対するキャッシュ）とは分ける。

| 列 | 内容 |
|---|---|
| `id`、`workspace_id`、`field_id`、`created` | 発言と、送信時に選択していた視野 |
| `text` | 指示の原文（2,000 文字以内） |
| `state` | `pending`、`answered`、`failed` |
| `reply` | 文章の回答 |
| `applicable`、`reasons`、`stage` | 設定を適用できるか。できない場合の理由コードと、失敗した段階 |
| `request_id`、`draft_id` | 中継への依頼の ID と、適用できる解析案（`proposal_drafts`） |
| `effect` | この発言でアプリが行った処理：`none`、`settings`、`run` |

### 5.5 解析案の拡張

解析案（`ProposalDraft`）に次を加える（W8）。依頼の種類はモデルが宣言し、アプリは宣言された値に対して定めた処理だけを行う。指示の文の語句による分岐は実装しない。

| 項目 | 内容 |
|---|---|
| `intent` | `answer`（質問）、`settings`（設定の変更）、`run`（実行） |
| `answer` | 文章の回答 |
| `scope` | 実行の対象：`selected`、`all` |
| `assignments` | 群と実験回の割付の案（視野、実験回、群の組） |

| `intent` | アプリの処理 | 検証 |
|---|---|---|
| `answer` | 文章を表示する。設定を変更せず、解析を実行しない | 設定の変更を含まないこと |
| `settings` | 検証済みの設定を適用する。解析は実行しない | 現在の検証 |
| `run` | 設定を適用し、対象の視野を発言に示して候補を作成する。採用は研究者が行う | 現在の検証 |

### 5.6 状態の表示

状態の語を次に統一する。文言は UC-01〜UC-07（[結果の表現とデモの素材の要件](../results-and-demo-story/requirements.md#e-ui-の文言uc)）に従う。

| 対象 | 語 |
|---|---|
| 受け取ったファイル | 読み込み中、追加待ち、登録済み、要確認、マスクの候補、対象外、読み取れない |
| 視野の解析 | 準備中、待機、検出中、候補を確認、保存済み |
| 発言 | 送信中、回答、失敗、設定を適用、実行 |
| 接続 | 接続中、再接続中、停止 |

## 6. 作業単位

| | 内容 | 種類 | 依存 |
|---|---|---|---|
| W1 | 取り込みの結果を項目ごとに返す | fix(web) | — |
| W2 | 登録できなかった画像の記録と、比較の停止の廃止 | feat(api, web) | W1 |
| W3 | AI の会話の保存、失敗理由の表示、応答の適用の分離 | fix(web, api) | — |
| W4 | 画面の案 | docs | — |
| W5 | 受け取りの API | feat(api) | W2 |
| W6 | 画像から始める画面と取り込みの一覧 | feat(web) | W4、W5 |
| W7 | 群と実験回の割付 | feat(web, api) | W6 |
| W8 | AI の依頼の種類の区別 | feat(api, worker, web) | W3（割付の案は W7） |
| W9 | 視野ごとの進捗 | fix(web) | — |
| W10 | 接続の区別、再接続、停止理由の記録 | fix(web, api) | W1 |
| W11 | 更新案内 | fix(web, api) | — |
| W12 | Windows の実機での受入 | test | 配布 |

以下、場所の表記で `review/` は `apps/web/src/components/workspace/review/`、`lib/workspace/` は `apps/web/src/lib/workspace/`、`cytellect_api/` は `services/api/src/cytellect_api/` を指す。`ConnectedWorkspace.tsx`、`use-workspace-runtime.ts`、`api-adapter.ts` は 1 行が長いため、`grep -n` と `awk` の `substr` で該当箇所を切り出して読む。

### W1 取り込みの結果を項目ごとに返す

**Issue**　対照 B・C、巻き込み 1・2、入力 3、入力 6、受入 2〜4。

**変更**

1. `importFiles` の戻り値を `IntakeOutcome`（[§5.3](#53-取り込みの結果intakeoutcome)）にする。API の拒否（422）、名前の競合、大きさの上限（所見 1）では例外を投げず、該当する項目だけを `rejected` または `held` に入れる。
2. 名前の競合では、競合した視野だけを `held` にし、ほかの視野を登録する。`held` と `rejected` の項目を `added` と `files` から除く。
3. `addToExperiment` と `placePending` は、`IntakeOutcome` と `IntakeInterrupted` のどちらでも、`registered` の視野を群に割り付ける。
4. `pending` を追記にする。登録の完了後に解放する。
5. 選択の結果を必ず表示する。空のフォルダー、画像を含まない選択、選択の取り消し（`input` の `cancel` イベント。直前の選択を保持する）を区別する。
6. 項目単位の結果は「取込」の一覧に表示する。上部のエラー表示と「再読み込み」は `IntakeInterrupted` に限る。

**変更箇所**

| 場所 | 変える点 |
|---|---|
| `lib/workspace/use-workspace-runtime.ts` の `importFiles`、`dropImport` | 戻り値、例外の条件、`added` の後始末 |
| `review/ConnectedWorkspace.tsx` の `add`、`addToExperiment`、`placePending`、`pending` | 追記、部分成功時の割付、解放の時期 |
| `review/ExperimentSetup.tsx` の `received`、`place`、保留のカード | 結果の受け取りと表示 |

**終わりの条件**　対照 B、対照 C、入力 3 の各合格条件。入力 6 の「正常な確定、空フォルダー、全件対象外を画面で区別できる」。対照 C は再読み込み後の各群の内容まで照合する。

**試験**

- 単体：[§4.1](#41-issue-の原因分析の確認) の再現試験（対照 B・C）を修正後の期待に書き換えて追加する。`pending` の追記。大きさの上限。
- 単体：既存の `names a rejected file, keeps its ledger entry until it is excluded with a reason, and never resends it` は、例外ではなく `rejected` を確かめる形に改める。
- ブラウザ：`workspace-form-first.spec.ts` に、群のセルへの混在入力を加える。

**文書**　`docs/web.md`。　**レビュー**　`/code-review medium`。

### W2 登録できなかった画像の記録と、比較の停止の廃止

**Issue**　巻き込み 3・4、巻き込みの判定、優先 6・7、受入 3。決定 2。

**変更**

1. 表 `intake_items`（[§5.2](#52-受け取りの記録intake_items)）と、次の経路を加える。
   - `POST /v1/workspaces/{wid}/intake-items`（複数の項目の作成）
   - `GET /v1/workspaces/{wid}/intake-items`（一覧）
   - `PATCH /v1/workspaces/{wid}/intake-items/{id}`（取りやめ、追加先、`separate`）
2. 画面は送信の前に項目を作成し（名前、大きさ、ハッシュ、`batch_id`、`target`）、その ID を `client_upload_id` に使う。画像以外のファイルは `role: other` で記録し、内容は送らない。
3. `upload_region_field` と OME の登録は、結果を項目に記録する。成功時は `registered` と `field_id`、読み取りの失敗（422）時は `role` と `code` を、視野の保存と同じトランザクションで書く。
4. `assemble` から、視野も理由もない行による 409 `workspace_selection_incomplete` を削除する。比較の設定に、登録できなかった画像の件数を `target`（群、実験回）と理由コードごとに記録し、結果の「n の内訳」、Methods、書き出しに出力する。測定値と統計の計算は変更しない。
5. 群または実験回に有効な値がない比較は、既存の検査（`region_comparison_unit_without_values` など）で保留する。この検査は変更しない。
6. 「取込」の一覧を `GET …/intake-items` から描画する。読み取り不能の行は、名前、理由、「差し替え」、「追加をやめる」を持つ。次を削除する：除外理由の入力欄と「まとめて除外」（`UnfinishedImports.tsx`）、統計の画面の「登録できなかった画像：n 件。…」の表示、ランタイムの `failedImports`・`unfinishedImports`・`excludeImports`。
7. 差し替えは、同じ項目の ID で再送する。視野の作成後、項目は `registered` になり、`target` の群に入る。項目と視野は増えない。
8. 既存のワークスペースに残る「視野のない行」は読み取り専用とし、「以前の取り込みの記録（名前なし）」として表示する。処理を妨げず、新規には作成しない。

研究者が視野を対象外にする操作（`excludeField`、理由付き）は変更しない。読み取りの失敗、未対応の形式、マスクの候補、送信の中断、測定の失敗、研究者による除外は、`role`・`state`・既存の除外理由で区別する（優先 6）。

**変更箇所**

| 場所 | 変える点 |
|---|---|
| `cytellect_api/db.py`、新規 `cytellect_api/intake.py` | 表と経路 |
| `cytellect_api/regions.py` の `upload_region_field`、OME の登録 | 結果を項目に記録する |
| `cytellect_api/region_cohorts.py` の `assemble` | 検査の削除、内訳の記録 |
| `cytellect_api/workspace_selection.py` の `selection_at` | 視野のない行を読み取り専用として扱う |
| `packages/analysis` の比較の契約と書き出し | 登録できなかった画像の内訳 |
| `lib/workspace/api-adapter.ts` の `registerImport`、`upload`、`uploadOme` | 項目の作成に置き換える |
| `lib/workspace/use-workspace-runtime.ts`、`review/UnfinishedImports.tsx`、`review/ConnectedWorkspace.tsx`、`apps/web/src/lib/api.ts` の `workspace_selection_incomplete` | 一覧の描画、除外の UI と文言の削除 |

API の変更後に `python3 scripts/dev.py contracts` を実行し、OpenAPI と生成した型を同じコミットに含める。

**終わりの条件**　巻き込みの判定のうち、失敗票と比較に関する部分（①②で有効 2 視野を使える、理由の入力を求めない、再起動後に元の名前で識別できる、1 枚の差し替えで同じ票が解決する、群別の有効数と欠測を示し必要な群が空の比較だけを保留する）。受入 3。

**試験**

- API：項目の作成、状態の遷移、同じ ID での再送。
- API：上記の契約試験の前半（視野のない行が 1 つあると拒否する）を、拒否せず内訳に記録する試験に書き換える。後半（層の未定の視野による拒否）は維持する。
- 単体：[§4.1](#41-issue-の原因分析の確認) の再現試験（再読み込み後の名前）を修正後の期待に書き換えて追加する。
- ブラウザ：`workspace-unfinished-imports.spec.ts` を、再読み込み後の名前と理由、差し替え、比較の計算まで確かめる内容に書き換える。

**文書**　`docs/web.md`（該当段落）、`docs/region-comparisons.md`（Input ledger and missingness）、`docs/methods.md`、`docs/requirements.md`（S10、I11）、`docs/generic-regions.md`（`client_upload_id`）、`SECURITY.md`・`docs/security.md`（保存する項目）。

**レビュー**　`/code-review high`（比較の検査）、`/security-review`（アップロードの受け入れ）。

### W3 AI の会話の保存、失敗理由の表示、応答の適用の分離

**Issue**　追試 A・B、判定 1〜4、優先 9、受入 5。決定 4。AI の中継は変更しない。

**変更**

1. 表 `assistant_messages`（[§5.4](#54-会話の記録assistant_messages)）を加える。`draft_proposal` は受付時に発言を保存し、結果を追記する。`GET /v1/workspaces/{wid}/assistant-messages` で一覧を返す。
2. 解析案が検証で拒否された場合も、文章を返す（所見 4）。`rationale` と `missing_information` を取得でき、文章の検査（`FORBIDDEN_TEXT`）を通る場合は、200 で `reply`、`applicable: false`、`reasons` を返す。取得できない場合に限り、現在の 502 を返す。いずれの場合も、理由コード、段階、`request_id` を発言の行に保存する。ログには指示の原文とモデルの出力を書かない（判定 3）。
3. `request` は `detail.reasons` を `ApiError.reasons` に格納する。
4. ランタイムに発言の一覧を持つ。ワークスペースを開いたときに取得する。送信時に入力欄を空にする。`newWorkspace` で一覧と入力欄を初期化する。AI のパネルは一覧から描画する。
5. 失敗は該当の発言の下に表示する。理由コードを、研究者が修正できるもの（例：`proposal_one_nuclear_channel_required`）とサービス側のもの（例：`proposal_shape_invalid`）に分類し、前者には該当する設定を開く操作、後者には再送（既存の `retry_failed`）を付ける。送信中、受付済み、完了の状態を発言ごとに表示する（追試 B の再送の判断）。
6. 応答を自動で適用しない。適用できる解析案には、発言の下に「設定を適用」と「適用して試行」を表示する。操作があるまで、設定の変更（所見 6 の仕様の書き換えを含む）と解析の実行を行わない。W8 の導入後、`intent: run` の発言は操作なしで進む。
7. 空欄の送信を無効にする。画像だけから解析案を作る操作は、AI のパネルの「解析案を作る」に置く（送信内容は現在の空欄の送信と同じ）。
8. `previous_goal` に、同じワークスペースの直前の発言を送る。
9. 公開デモ（`/demo`）は記録した操作の再生であり、動作を変更しない。記録の作り直しが必要になった場合は、作業を止めてオーナーに確認する。

**変更箇所**

| 場所 | 変える点 |
|---|---|
| `cytellect_api/db.py`、`cytellect_api/proposals.py` の `draft_proposal` | 表、保存、拒否時の応答、一覧の経路 |
| `apps/web/src/lib/api.ts` の `request`、`ApiError` | `reasons` |
| `lib/workspace/api-adapter.ts` の `draft` | 応答の形、一覧の取得 |
| `lib/workspace/use-workspace-runtime.ts` の `requestProposal`、`applyProposal`、`newWorkspace`、`load` | 発言の一覧、適用の分離、復元 |
| `review/ConnectedWorkspace.tsx` の `instruction`、`send`、`sendInstruction`、AI のパネル、入力欄 | 新規 `review/AssistantPanel.tsx` に分離する |

**終わりの条件**　判定 1 のうち「測定ジョブ 0、設定変更 0」と、文章の回答が同じ会話欄に表示されること。判定 3、判定 4。追試 B の 3 項目。回答の内容（DRAQ/GFP、根拠、提案する核染色）は W8 の終わりの条件とする。

**試験**

- API：`tests/test_proposals.py` の拒否の試験を、文章を返す場合と返さない場合に拡張する。発言の保存と一覧。
- 単体：発言の状態、`newWorkspace` での初期化、復元、自動で適用しないこと。
- ブラウザ：作業 A → B → A、再読み込み、連打。

**文書**　`docs/requirements.md`（L01、L02、L05）、`docs/proposal-service.md`、`docs/web.md`、`SECURITY.md`・`docs/security.md`（指示の原文を PC 内に保存する）。

**レビュー**　`/code-review medium`、`claude-api`。

### W4 画面の案

**Issue**　入力 1、優先 1〜3。

genellect/cytellect#258 は、画面の変更が説明の文で埋まり却下された。画面を変える作業（W6〜W9、W11）は、実装の前に案を `main` の画面と並べてオーナーに示す。

**作成するもの**　次の 5 画面について、`main` の画面と案を並べた画像を `docs/drafts/native-first-run/` に置く。公開画像を使い、`frontend-design` と `design:ux-copy` を用いる。

1. 空の作業：中央の「画像を追加」（選択、フォルダー、ドロップ）、受け付ける形式の 1 行、見本 3 点（測定する蛍光画像、同じ視野の別染色、輪郭のマスク。登録済みの公開画像と出典）
2. 取り込みの一覧：内訳の 1 行、縮小画像・名前・チャンネル・状態の行、「追加」「画像を足す」、行ごとの取り消し、競合の行、同一内容の行
3. 未割り当ての視野の表（実験回と群の案）
4. AI のパネル：画像の事実、発言の一覧（状態と操作）、「解析案を作る」
5. 視野の一覧の進捗、更新案内の「後で」

次の図は検討の出発点とする。

```text
空の作業                                取り込みの一覧
┌────────────────────────────────┐    受け取り 6：画像 4（2 視野）・マスクの候補 1・対象外 1   ［追加］［画像を足す］
│           画像を追加            │    ┌──────┬────────────────┬─────────────┬──────────────┐
│ ［画像を選ぶ］［フォルダーを選ぶ］│    │ 縮小 │ BBBC007-a9      │ C01 ・ C02  │ 追加待ち      │ ×
│        ここにドロップ           │    │ 縮小 │ BBBC007-f9620   │ C01 ・ C02  │ 追加待ち      │ ×
│  TIFF・OME-TIFF（8/16-bit、2D） │    │ 縮小 │ a9-核の手動輪郭 │ マスクの候補 │ a9 と同じ寸法 │ ×
│  ［見本］ ［見本］ ［見本］      │    │  —   │ 読み方.txt      │ 対象外       │              │
│ 測定済みデータを使用・実験から始める │    └──────┴────────────────┴─────────────┴──────────────┘
└────────────────────────────────┘
```

**終わりの条件**　オーナーが各画面の案を選ぶ。選ばれた案を、この文書の W6〜W9 と W11 に反映する。

### W5 受け取りの API

**Issue**　入力 2・5、対照 A、優先 3・7、受入 4。

**変更**

1. `POST /v1/workspaces/{wid}/intake-items/{id}/content`：1 ファイルの内容を受け取り、共通の読み取り処理（`read_tiff`、OME の読み取り）で `role`、`code`、`shape`、`dtype`、OME のチャンネル名を決めて保存する。256 MiB の上限と、共有の開発環境の制限（`CYTELLECT_UPLOAD_ALLOWLIST`）をこの時点で適用する。
2. `GET …/intake-items/{id}/preview`：表示用の縮小画像を返す。原画素は変更しない。
3. `POST …/intake-items/commit`：視野の構成（項目とチャンネルの対応）と `target` を受け取り、保存済みの内容から視野を作成する。内容を再送しない。結果を `IntakeOutcome` の形で返す。
4. 受け取り時に、同じワークスペースの項目と、登録済みの視野の入力（`image_info.inputs` のハッシュ）と照合し、一致する場合に `duplicate_of` を記録する。
5. 保存した内容をワークスペースの容量に算入する。保存期限と削除は視野の入力と同じ扱いとする。取りやめた項目の内容と、視野の作成後に不要となる重複を削除する。

**変更箇所**

| 場所 | 変える点 |
|---|---|
| `cytellect_api/intake.py`、`cytellect_api/db.py` | 経路、`stored`・`shape`・`dtype` |
| `cytellect_api/regions.py` の `upload_region_field` | 読み取り、ハッシュ、容量の検査を共有し、保存済みの内容から視野を作成する経路を加える |
| `cytellect_api/local_storage.py`、保存期限の処理 | 容量と削除 |

**終わりの条件**

- 入力 5 の入力（原画像 4、32-bit のマスク 1、TXT 1）で、`image` 4、`label` 1、`other` 1 となり、合計が受け取った件数と一致する。
- 受け取り後の再読み込みで、一覧と縮小画像が保持される。
- 確定は内容を再送せず、同じ確定の再実行で視野が増えない。
- 対照 A の入力で、複製に `duplicate_of` が記録される。

**試験**　API：役割と理由コード（公開画像と、試験内で作成する破損した画像）、容量、削除、確定の冪等性、同一内容の検出。

**文書**　`docs/generic-regions.md`、`docs/architecture.md`、`SECURITY.md`・`docs/security.md`（登録前のファイルの保存と削除）、`docs/local.md`（保存期限）。

**レビュー**　`/code-review medium`、`/security-review`。

### W6 画像から始める画面と取り込みの一覧

**Issue**　入力 1〜3・5・6、対照 A・B、優先 1〜4、受入 1・2・4。決定 1・3。

**変更**

1. 視野と実験デザインのないワークスペースでは、W4 で選ばれた開始の画面を表示する。ドロップは画面全体で受ける（既存の `dropFiles`）。「実験デザインから始める」を選んだ場合は、現在の流れ（群のセルからの追加）を維持する。
2. 選択またはドロップのたびに、ファイルを受け取りの API（W5）へ送り、一覧に追加する。取り込み中も追加を受け付ける（所見 3）。行は、縮小画像、名前、チャンネル、状態（[§5.6](#56-状態の表示)）を持つ。先頭に内訳を 1 行で表示する。
3. 視野への組み分けは、未登録の `image` 全体に対して行う。視野のキーから取り込みごとのフォルダー名を除く（所見 2）。
4. 同一内容（`duplicate_of`）は 1 項目だけを使い、行に「同一内容：○○ と同じ」と「別の撮影として追加」を表示する。登録済みの視野と同一の場合は「登録済み」と表示する。
5. 名前の競合は該当の行だけを「要確認」にし、2 枚を名前と縮小画像で並べて、使用する 1 枚を選ばせる。ほかの行は追加できる。
6. マスクの候補には、寸法が一致する視野を表示する。領域として使う操作は含めない。染色と生物学的な役割を推定しない。
7. 「追加」で確定（W5）し、最初の視野を「画像」で開く。行ごとの取り消しと、直前の追加（`batch_id`）の取り消しを設ける。
8. フォルダーは、`webkitdirectory` の `input` とドロップの両方で、入れ子を含めて受ける。
9. 開発の起動時に限り、取り込みの診断をコンソールに出力する。内容は件数のみ（`change` の発火、`files.length`、相対パスの件数、受け取った件数）とし、名前と内容は出力しない（入力 6 の切り分け手順 ②）。
10. `pending`、`ExperimentSetup.tsx` の保留のカード、「受け取った画像の追加先」を削除する。

**変更箇所**

| 場所 | 変える点 |
|---|---|
| 新規 `review/EmptyStart.tsx`、`review/IntakeList.tsx` | 開始の画面、取り込みの一覧 |
| `review/panel-state.ts` の `experimentSetupShown` | 空の作業で実験デザインを表示する条件 |
| `review/ConnectedWorkspace.tsx` の `add`、開始画面の分岐、`dropFiles`、`intakeDisabled`、ファイルの `input` | 一覧への接続、`pending` の削除 |
| `review/ExperimentSetup.tsx` の実験デザインの選択、保留のカード、`pendingTarget` | 削除と整理 |
| `lib/workspace/grouping.ts` の `groupFiles`、`lib/workspace/dropped-files.ts` | 組み分けのキー、フォルダーの読み取り |

**終わりの条件**　入力 1・2・3・5 の各「修正後の判定」「合格条件」。入力 6 の合格条件。対照 A・B の合格条件。受入 1 のうち自動で確かめられる部分（研究者による評価は W12 の後に別途行う）。

**試験**

- 単体：内訳の合計、選択の回をまたぐ組み分け、同一内容、競合、取り消し。[§4.1](#41-issue-の原因分析の確認) の再現試験（対照 A）を修正後の期待に書き換えて追加する。
- ブラウザ：入れ子のフォルダーの入力、ドロップ、4 枚＋1 枚、対照 A・B、再読み込み。`workspace-form-first.spec.ts` を新しい流れに書き換える。
- `cytellect-screen-check`。

**文書**　`docs/requirements.md`（U01、I12）、[群間比較の要件](../group-comparison/requirements.md)（E-01）、`docs/workspace-redesign.md`、`docs/web.md`、`docs/quickstart.ja.md`、`docs/install-windows.ja.md`、`docs/usability-tasks.ja.md`。

**レビュー**　`frontend-design`、`design:ux-copy`、`cytellect-screen-check`、`/code-review medium`。

### W7 群と実験回の割付

**Issue**　入力 4、優先 5、受入 2。

**変更**

1. 「実験」に「未割り当ての視野」の表を置く。行は視野（縮小画像、名前、チャンネル）、列は実験回と群とする。複数の行を選択して一括で割り付けられる。
2. フォルダーの階層と名前から割付の案を作る（例：`Rep1/未処理` → 実験回 Rep1、群 未処理）。案は定めた規則だけで作り、確定前の表示とする。「案を適用」の操作まで保存しない。
3. 案を作れない行は空欄とし、その行だけ入力を求める。
4. 番号だけのチャンネル（C01、C02）から、染色と生物学的な役割を決めない。
5. 実験デザインのないワークスペースでは、案の群の数から「1 画面」「2 画面」を提示し、研究者が選ぶ。
6. 再読み込み後も案を作れるよう、視野の記録にフォルダーの相対パスを保存する（現在は `displayNameOf` が表示名の末尾だけを保存する）。

案の提示は確定ではなく、E-04、I11、U02 に反しない。

**変更箇所**

| 場所 | 変える点 |
|---|---|
| 新規 `review/UnassignedFields.tsx`、`review/ExperimentSetup.tsx` | 表と一括の割付 |
| `lib/workspace/experiment-design.ts` の `assignFields` | 複数の追加先への一括の割付 |
| `lib/workspace/grouping.ts` の `candidates` | 割付の案の規則 |
| `lib/workspace/api-adapter.ts` の `displayNameOf`、`cytellect_api/regions.py` | 相対パスの保存 |

**終わりの条件**　入力 4 の合格条件のうち、指示による割付を除く部分（6 枚を 1 回で選び、2 視野の縮小画像を確かめ、あいまいな行だけを確認し、確定時に同じ実験回・2 群各 1 視野・各 3 チャンネルが残る）。対照と処理を同じ群に入れる操作が 1 回の操作で確定しないこと。指示による割付（「未処理と ActD に分けて」）は W8 の終わりの条件とする。

**試験**　単体：案の規則（フォルダー、名前、あいまいな場合）、一括の割付。ブラウザ：DS6a の 6 枚 → 案 → 確定 → 再読み込み。

**文書**　[群間比較の要件](../group-comparison/requirements.md)（E-01、E-03、E-04）、`docs/web.md`、`docs/usability-tasks.ja.md`。

**レビュー**　`frontend-design`、`cytellect-screen-check`、`/code-review medium`。

### W8 AI の依頼の種類の区別

**Issue**　追試 A（相談・条件変更・実行の境界）、判定 1・2、入力 4（指示による割付）、優先 5・8、受入 2・5。決定 4。

**変更**

1. 解析案に `intent`、`answer`、`scope`、`assignments` を加え、[§5.5](#55-解析案の拡張) の表のとおりに処理する。
2. `assignments` は、登録済みの視野と保存した実験デザインに対して検証し、W7 の表に案として表示する。保存は研究者の「案を適用」による。
3. AI のパネルの先頭に、選択した視野の事実を常に表示する：チャンネルの名前とその由来（ファイル名、OME、研究者の入力）、寸法、ビット深度、核染色の指定の有無。モデルを呼ばずに表示する（優先 8「手元のチャンネル情報から答え」）。
4. 発言の下に、対象と状態、「解析設定を表示」、「AI による設定変更を戻す」（既存の `showSettings`、`undoProposal`）を置く。
5. プロンプトと解析案の契約の版を上げる。配布済みの版の依頼には、従来の版で応答する。

**変更箇所**

| 場所 | 変える点 |
|---|---|
| `packages/analysis/src/cytellect_analysis/proposal_contracts.py` の `ProposalDraft`、`proposal_validation.py` の `validate_draft` | 項目の追加、`intent` ごとの検証 |
| `cytellect_api/proposals.py` | 契約の版、`assignments` の検証 |
| `services/proposal-worker/src/` の `openai.ts`・`anthropic.ts`（プロンプト）、`schema.ts`・`contract.json`、`index.ts`（版の扱い） | 新しい版 |
| `lib/workspace/use-workspace-runtime.ts` の `requestProposal`、`applyProposal`、`review/AssistantPanel.tsx` | `intent` ごとの処理、画像の事実 |

**終わりの条件**　判定 1・2。入力 4 の合格条件のうち、指示による割付。受入 5 の会話（「チャンネルを教えて、まだ測らない」→「核染色は DRAQ」→「正常な全視野で核を数えて」）。

**試験**

- API：偽の提供元による `answer`、`settings`、`run`、`assignments`、形の誤り、チャンネルの不一致。
- 単体：`answer` で解析のジョブと設定の変更がともに 0 件。
- 中継：契約とプロンプトの版。
- モデルによる評価は公開画像の事例で行う（有料。オーナーの許可が要る）。

**文書**　`docs/requirements.md`（L01、L02）、`docs/proposal-service.md`、`docs/proposal-deployment.md`、[LLM による解析支援の見直し](../llm-assistant/plan.md)、送信範囲が変わる場合は `SECURITY.md`。

**レビュー**　`claude-api`、`/code-review medium`。

**配布の順序**　中継を先にデプロイし、その後に Windows 版を配布する（[順序](../../proposal-deployment.md#order-of-worker-and-client-releases)）。

対話と道具による研究アシスタント（[見直し案の段階 2](../llm-assistant/plan.md#5-進め方)）は別の計画とする。W3 の会話の表と、この作業の `intent` は、段階 2 でも使用する。

### W9 視野ごとの進捗

**Issue**　測定中、優先 10、受入 6。

**変更**

1. 実行のステップ（`field_id`、`target`、`state`）から視野ごとの状態（準備中、待機、検出中と対象の領域、候補を確認、保存済み）を導出し、視野の一覧に表示する。採用前の候補がある視野は「候補を確認」とする。
2. ヘッダーの進捗は視野を単位とする（例：「視野 1/2：核小体を検出中」）。ステップ数を表示する場合は単位を付ける。
3. 設定の変更の直後と「測定」の操作の直後から、対象の視野に「準備中」を表示する。
4. 進捗の取得中の通信の失敗では、直ちに失敗としない。解析は API 側で継続するため、間隔を空けて再取得し、回復しない場合は W10 の案内に渡す。保存済みの視野と再試行の対象を表示する。同じ依頼は既存の `request_id` により重複して起動しない。
5. 1 視野の失敗で残りを止めない。失敗した視野に「再試行」を置く。

**変更箇所**

| 場所 | 変える点 |
|---|---|
| `lib/workspace/use-workspace-runtime.ts` の `runServer`、`readCandidates`、`recoverRun` | 視野ごとの状態の公開、再取得 |
| `lib/workspace/api-adapter.ts` の `waitWorkspaceRun` | 通信の失敗の扱い |
| `review/ConnectedWorkspace.tsx` の視野の一覧、ヘッダーの状態、`queuePreview`・`previewNow` | 表示 |

**終わりの条件**　測定中の「次の追試と合格条件」。

**試験**　単体：ステップから視野の状態の導出、再取得、重複して起動しないこと。ブラウザ：2 視野の核小体の測定。`cytellect-screen-check`。

**文書**　`docs/web.md`。　**レビュー**　`/code-review medium`、`cytellect-screen-check`。

### W10 接続の区別、再接続、停止理由の記録

**Issue**　復旧、巻き込みの判定（接続断の追試）、優先 7、受入 6。索引の「サービス停止」。

**変更**

1. 失敗を 3 種類に分け、それぞれの案内を表示する。

   | 失敗 | 判定 | 表示と処理 |
   |---|---|---|
   | 応答なし | `fetch` の失敗 | 「ローカルのサービスに接続できません」と「再接続」。間隔を空けて自動でも確認する。ランチャーの開き方を 1 行で示す |
   | セッション切れ | 401 `session_required` | `POST /v1/local/session` でセッションを作り直し、同じ要求を 1 回再試行する（所見 9） |
   | 開き方の誤り | 403 `local_origin_required` | デスクトップの「Cytellect」から開く案内 |

2. 再接続の後、受け取りの記録と視野を照合する。登録済みの項目は「登録済み」、送信が完了していない項目は `interrupted` とする。内容が API にある場合（W5）は続行し、ない場合は名前を示して再選択を求める。登録は同じ ID で冪等である。
3. サービスの全停止経路（ランチャーを閉じる、更新の切り替え、ワーカーの停止、ワーカーの起動失敗、親プロセスの消失、未処理の例外）で、理由コードと時刻を PC のデータフォルダーに記録する。次の起動時、前回が異常な停止であれば 1 行で知らせる。
4. ワーカーの停止でサービス全体を止めない（所見 8）。再起動の回数は、ワーカーが一定時間正常に動作した後に 0 に戻す。再起動できない場合、API は応答を続け、解析の受付だけを `local_worker_stopped` で拒否する。画面は理由と「ワーカーを再起動」を表示する。

**変更箇所**

| 場所 | 変える点 |
|---|---|
| `apps/web/src/lib/api.ts` の `request`、`session_required` の文言 | 再接続と再試行 |
| `lib/workspace/use-workspace-runtime.ts` の `message`、`reload` | 失敗の分類、照合 |
| `review/ConnectedWorkspace.tsx` のエラー表示と「再読み込み」 | 種類ごとの案内 |
| `cytellect_api/local.py` の `WorkerSupervisor.start`、`run_local`、`_gui` | 停止理由の記録、再起動の数え方、起動時の通知 |

**終わりの条件**　巻き込みの判定の「接続断の追試は『未送信・送信後の応答消失・再接続・401・403』を分け、再接続時に既存の登録結果を照合する」。取り込みの途中でサービスを停止して再起動した後、登録済みの視野が重複せず、残りの項目を続行でき、一覧が保持される。停止理由が記録され、次の起動で表示される。記録に研究データを含まない。

**試験**

- 単体：3 種類の判定、再試行、照合。未送信、送信後の応答消失、再接続、401、403 を個別に通す。
- API：停止理由の記録、再起動の数え方（`tests/test_local.py`）。
- Windows の CI（`windows-installer`）：ワーカーの停止後も API が応答する。

**文書**　`docs/local.md`（停止と再開）、`docs/install-windows.ja.md`、`docs/web.md`。

**レビュー**　`/code-review medium`、`/security-review`（セッション）。

### W11 更新案内

**Issue**　更新、優先 11、受入 6。索引の「更新ボタン無反応」。

**変更**

1. 通常の案内に「後で」を加える。操作後は、次の起動まで表示しない。
2. 操作の直後から、同じ場所に段階を表示する：受付、ダウンロード中、インストール中、再起動中、完了。
3. 結果を表示しない 2 つの分岐（所見 10）に、1 行の結果を表示する：「新しい版はありません」、「この PC ではアプリ内から更新できません」と代替の手順。
4. 解析中の操作では「解析が終わってから更新してください」を表示し、解析を止めない（現在の動作）。二重の操作と別タブで進行中の場合は、進行中の更新の段階を表示する。更新後の再開先を表示する（優先 11）。
5. 失敗の段階を記録する。`run_installer` は段階（起動、タイムアウト、終了）と終了コードを返す。失敗コードを `update_installer_launch_failed`、`update_installer_timeout`、`update_install_failed`（終了コード付き）に分け、状態の記録に `stage` と `exit_code` を残す。インストーラーのログは PC の更新フォルダーに保存し、外部へ送らない。
6. Microsoft Store の版での案内の表示条件を、コードと試験で確かめる。Store が更新を担う版では、この案内を表示しないか、Store への案内だけを表示する。
7. ボタンの語を 1 つに統一する（所見 11）。配布版 `0.1.0-local.26` の表示を確かめたうえで決める。

**変更箇所**

| 場所 | 変える点 |
|---|---|
| `apps/web/src/components/workspace/CloudAccount.tsx` の `UpdateBanner`（`applyUpdate`） | 「後で」、全分岐の結果表示、段階の表示 |
| `apps/web/src/lib/cloud-account.ts` の `updateNotice`、文言 | 段階と語 |
| `cytellect_api/app_update.py` の `run_installer`、`UpdateService._run`、状態の記録 | 失敗の段階、終了コード、ログ |

**終わりの条件**　更新の「次の追試と合格条件」（「後で」、解析中、二重クリック、別タブで進行中、起動拒否、タイムアウト、非ゼロ終了を個別に通す）。

**試験**　単体：`updateNotice` と `UpdateBanner` の分岐、「後で」。API：`run_installer` の 3 種類の失敗、状態の記録（`tests/test_app_update.py`）。Windows の CI：`packaging/windows/smoke.ps1` の更新の試験に失敗の段階を加える。

**文書**　`docs/local.md`（更新）、`docs/install-windows.ja.md`、`docs/release-signing.md`。

**レビュー**　`/code-review medium`、`/security-review`（更新）。

### W12 Windows の実機での受入

**Issue**　受入 1〜6、入力 6（切り分け手順 ①）、更新の「次の追試と合格条件」。

開発環境の試験の合格を、実機の合格として報告しない。配布候補を Issue と同じ環境（インストール版、Edge）に導入し、Issue の「入力の用意と再現の約束」の公開画像で次を行い、画面と時刻を記録する。

1. 受入 1〜6。
2. フォルダー：Edge の通常のピッカーで、原画像のサブフォルダー（4 件）と親フォルダー（10 件）の選択、取り消し、確定。同じ 2 つのドラッグ＆ドロップ。
3. 接続：取り込みの途中でランチャーを閉じて再起動する。再起動前から開いていたタブで操作する。
4. 更新：W11 の終わりの条件の 7 場面。
5. 再起動後に、群の内容、登録できなかった画像の名前、会話が保持されることを照合する。

**終わりの条件**　受入の記録（`docs/local-release-<版>.md`）に、合格、失敗、未実施を分けて記載する。受入 1 の研究者による評価（迷って戻った箇所と支援の回数）は、未完了の受入条件として [roadmap](../../roadmap.md) で追跡する。

## 7. 順序と並行

```text
W1 ──► W2 ──► W5 ──► W6 ──► W7 ──┐
 └───► W10          ▲            ├──► W12
W4 ─────────────────┘            │
W3 ──────────────► W8 ───────────┤
W9 ──────────────────────────────┤
W11 ─────────────────────────────┘
```

- 最初に W1 と W3 に着手する。どちらも依存がなく、索引の最優先の項目に対応する。
- W1、W3、W4、W9、W11 は並行できる。
- `ConnectedWorkspace.tsx` は W1、W3、W6、W9 が変更する。並行する場合は担当を分け、W1、W3、W9、W6 の順に `main` へ取り込む。W3 は AI のパネルを、W6 は取り込みを別の部品に分離し、同じ行の変更を減らす。
- W3 と W8 は同じ配布に含めることを目標とする。W8 の中継のデプロイが遅れる場合は、W3 だけで配布できる。その場合、解析の依頼にも「適用して試行」の操作が 1 回必要になる。
- 各作業単位は、[CLAUDE.md](../../../CLAUDE.md#目的別のスキル) の表に該当するスキルを使い、`cytellect-verify`、画面を変えた場合は `cytellect-screen-check` の後に、`cytellect-pr` で PR を作成する。

## 8. 共通の検証

- 試験と画面の確認には、登録済みの公開画像（BBBC007、BBBC013、BBBC039、DS6a）を使う。Issue の入力と同じである。
- 破損した画像は、Issue と同じ方法（公開 BBBC013 の `A01-DRAQ.tif` の先頭 32 バイト）で試験内に作成する。共有の開発環境の制限（`CYTELLECT_UPLOAD_ALLOWLIST`）が有効な場合、この画像は読み取りの前に拒否されるため、この試験は制限のない設定で実行する。
- ファイル名だけで結果が決まる経路の単体試験は、既存の試験と同じ最小のバイト列を使い、試験名に「合成」と明記する（[開発の原則](../../development-principles.md#研究データと検証)の条件 1〜4 に該当する）。
- 公開デモ（`/demo`）は画像の追加を受け付けない。W1、W2、W5〜W7 はデモの動作を変えない。W3、W8、W9 は共通の部品を変更するため、各 PR でデモの記録に影響しないことを確かめる。

## 9. 残る危険

| 危険 | 対応 |
|---|---|
| W2 の変更は、比較に含まれる視野と n の内訳の表示に関わる | 測定値と統計の計算は変更しない。契約試験、Methods、要件を同じ PR で改め、`/code-review high` を行う |
| W5 は登録前のファイルを PC 内に保存し、使用する容量が増える | 容量への算入、保存期限、削除を視野の入力と同じ扱いにし、取りやめた項目と重複を削除する |
| W8 は中継の契約の版を上げる。配布済みの版との互換が要る | 版ごとに応答を分ける既存の仕組みを使う。中継を先にデプロイする |
| W3 を W8 より先に配布すると、解析の依頼に操作が 1 回増える | 同じ配布に含めることを目標とする（[§7](#7-順序と並行)） |
| 画面の変更が、#258 と同様に却下される | W4 で案を `main` と並べて示し、選ばれた案だけを実装する |
| `ConnectedWorkspace.tsx` の変更が競合する | [§7](#7-順序と並行) の取り込みの順序と、部品の分離 |
| 原因を特定できていない 4 項目（[§4.3](#43-原因を特定できていない項目)）が、実装後も実機で再発する | W12 で実機を確かめる。再発時は、W3・W10・W11 が保存する理由コードと停止理由から原因を特定する |

## 10. オーナーの許可が要る操作

| 操作 | 関係する作業単位 |
|---|---|
| `main` へのマージ | すべて（PR ごと） |
| AI の中継のデプロイ | W8 |
| 有料の API の呼び出し（モデルによる評価、形式エラーの理由コードの確認） | W3、W8 |
| Windows 版の配布、Microsoft Store への提出 | W12 の前 |
| 公開デモの記録の作り直し | W3、W8、W9 で必要になった場合 |

## 11. この調査で実施していないこと

- Windows の実機での確認。
- 有料の API の呼び出し。
- 画面の確認（画面を変更していない）。
- 別の担当による調査結果の再確認。
