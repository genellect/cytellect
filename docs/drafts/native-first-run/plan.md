# Windows 版の初回体験（#284）：実装案

作成：2026-11-25。genellect/cytellect#284 の実装の設計・変更箇所・順序・試験を定める。状態：実装は未着手。改訂の経緯は [§12](#12-改訂の記録) にある。

**役割の分担**　症状、再現手順、証拠、原因の分析、合格条件は Issue に書かれており、要求の正本は Issue とする。この文書はそれらを繰り返さず、Issue の該当箇所を名前で参照する。Issue と食い違う場合は Issue が正しく、この文書を直す。Issue の記述だけでは実装が一意に決まらない点は、[§11](#11-issue-の解釈) にこの文書の解釈を定めた。実装はその解釈に従う。

## 1. 作業を始める前に

- [AGENTS.md](../../../AGENTS.md) と、[Issue #284](https://github.com/genellect/cytellect/issues/284) の全文を読む。担当する作業単位が参照する Issue の節（[§3](#3-issue-の項目と作業単位の分担)）は、添付の画面とログまで確かめる。
- Issue の実機は Windows インストール版 `0.1.0-local.26`（コミット `9b44ce4bed61`）で、#257 の統合（genellect/cytellect#291、2026-11-24）より前の版である。この文書は、統合後の `main`（`462c288c`）のコードと照合して書いた（[§4.4](#44-257-の統合との整合)）。行番号は使わず、ファイルと関数・部品の名前で示す。
- Issue は実機で確かめた結果である。開発環境で追試できない項目も実装の対象とする（[§4.3](#43-原因を特定できていない項目)）。
- 1 つの作業単位（[§6](#6-作業単位)）を 1 本の PR にする。各作業単位の「変更」は、番号の順に実装する。終わりの条件は、[§3](#3-issue-の項目と作業単位の分担) で作業単位に割り当てた範囲とする。満たせない場合は PR の「残る課題」に書き、合格として報告しない。
- 各作業単位は、単独で `main` に入れても配布できる状態を保つ（[§7](#7-順序と配布)）。`main` へのマージ、AI の中継（`services/proposal-worker`）のデプロイ、有料の API の呼び出し、Windows 版の配布、公開デモのホイールと記録の作り直しは、オーナーが明示した場合だけ行う（[§10](#10-オーナーの許可が要る操作)）。
- 実装の判断に迷う場合は、Issue の「達成したい体験」と [§5.1](#51-原則) に沿う方を選んで進める。オーナーに確認するのは、Issue の目的に反する仕様を見つけた場合に限る。
- 関連する作業：genellect/cytellect#249（AI の導線とエラー文。再送の確認は #253、AI の設定は #254 で実装済み）、genellect/cytellect#257（`main` に統合済み。画面の作り直しの原則の出どころ）、genellect/cytellect#261（EXE の自動配布）、genellect/cytellect#286（Microsoft Store を主導線にする）。

### 用語

| 語 | 意味 |
|---|---|
| 票 | ワークスペースの登録票の全体（`workspace_selections` の 1 件。`entries` と `version` を持つ） |
| 行 | 票の `entries` の 1 件。視野 1 つ、または登録を試みた視野 1 つに対応する |
| 選択 | 研究者がファイルやフォルダーを選ぶ、またはドロップする操作 |
| 追加 | 選択した画像を視野として登録する操作（「追加」ボタン） |
| 取り込みの一覧 | 選択したファイルと、登録できなかった行を表示する一覧。W1 では画面下端の「取込」、W5 以降は `IntakeList` |

### Issue の参照名

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

| | 決定 | 根拠 | 改める要件 |
|---|---|---|---|
| 1 | 最初の操作を画像の追加にする。実験デザインは画像の登録後に決める | Issue（優先 1、入力 1） | `docs/requirements.md` の U01（2026-10-25 の改訂）、[群間比較の要件](../group-comparison/requirements.md)の E-01（2026-10-28） |
| 2 | 登録できなかった画像について、手動の除外と理由の入力を求めない。そのために比較を止めない | オーナー（2026-11-25）。Issue（優先 6、巻き込みの判定） | `docs/requirements.md` の S10 のうち、登録できなかった画像に関する部分 |
| 3 | 同じ内容の画像は 1 つの視野にまとめる。別の撮影として扱う場合だけ、研究者がその判断を記録する | Issue（対照 A の合格条件） | `docs/requirements.md` の I12（2026-10-06） |
| 4 | AI の応答によって、設定の変更と解析の実行を自動で行わない。どちらも研究者の操作で行う | Issue（追試 A、判定 1）。解釈は [§11](#11-issue-の解釈) の 7 | `docs/requirements.md` の「LLM」の節の L02（2026-10-06） |
| 5 | Issue の全項目を、追試の可否によらず実装する | オーナー（2026-11-25） | — |

補足：

- 決定 2 が廃止する規則（登録できなかった画像を理由付きで除外するまで比較を止める）に、オーナーの決定の記録はない。記載は `docs/web.md`、`docs/region-comparisons.md`、コードのコメント、契約試験にある。
- 決定 3 と 4 は、以前の決定（I12、L02）が Issue の目的に反するために改める。I12 は複製を視野として数え、観測数を増やす側に働く。画素が完全に一致する 2 枚は、撮像のノイズを考えると別の撮影ではなく複製とみなせる。L02 は、質問に対しても設定を変えて解析を実行し、「まだ測らない」を守れない。
- 決定 4 の方式：「まだ測らない」（判定 1）は不変条件であり、[開発の原則](../../development-principles.md#問題への対処)は不変条件を決定論的な検査で守ると定める。依頼の種類をモデルに宣言させて自動で実行する方式は、モデルの誤った宣言で破れる。したがって、宣言は表示する操作の選択にだけ使い、適用と実行は研究者の操作を条件とする。
- `docs/requirements.md` は L01〜L05 の ID が「LLM」と「ローカル配布」の節で重複する。この文書は節の名前を付けて参照する。
- 各作業単位が改める文書の全体は、その作業単位の「文書」に挙げる。

## 3. Issue の項目と作業単位の分担

1 つの合格条件を複数の作業単位が満たす場合は、各単位が満たす範囲を書く。作業単位の「終わりの条件」は、この表の自分の範囲とする。

| Issue の項目 | 分担 |
|---|---|
| 入力 1（画面 02） | W3：画面の案。W5：中央の追加、選ぶ前の見本、追加に続けて AI へ進む操作 |
| 入力 2（画面 03、06） | W4：役割と縮小画像の判定。W5：選択した時点の一覧（視野、チャンネル、読み込み中、読めなかった項目） |
| 入力 3（画面 10、11） | W1：選択の追記、成功分を二重に登録しない、登録できなかった行だけの再試行（行の全ファイルを選び直す）。W5：一覧に全件を残す、その回の選択だけを戻す、ファイル単位の再試行 |
| 入力 4（画面 15） | W6：表による割付と、フォルダーと名前からの案。W7：指示（「未処理と ActD に分けて」）による案 |
| 入力 5（画面 16） | W1：32-bit のマスクを欠測に数えない。W4：役割の判定。W5：内訳の表示、マスクの候補と対象外を一覧に残す |
| 入力 6 | W1：正常な確定・空のフォルダー・全件対象外・取り消しの区別。W5：入れ子とドロップの試験、件数の診断。W11：手動の操作 |
| 対照 A（画面 19） | W1：複製を視野にしない、複製と対応先を「取込」に示す、「別の撮影として追加」とその記録。W5：同じ内容を縮小画像つきの一覧で示す |
| 対照 B（画面 21、22） | W1：無関係な視野を登録する、選択し直したときに以前の競合を再検出しない、競合した 2 枚を名前で示す。W5：競合した 2 枚を縮小画像と対応先つきで示し、行で差し替える |
| 対照 C（画面 24、25） | W1 |
| 巻き込み 1〜4 | W1 |
| 巻き込みの判定（画面 13、14） | W1：有効な視野を使える、理由の入力を求めない、再起動後に元の名前で識別する、差し替えで同じ行が解決する、比較を止めず群別の有効数と欠測を示す。W4・W5：マスクと TXT の別集計。W9：接続断の追試 |
| 復旧（画面 04） | W9 |
| 追試 A（画面 08） | W2：文章の回答の表示、理由コードの保存と表示、設定と実行を自動で行わない、空欄の送信の廃止、直前の発言の引き継ぎ、画像の事実。W7：依頼の種類に応じた回答と操作 |
| 追試 B | W2 |
| 判定 1 | W2：測定ジョブ 0・設定変更 0、文章の回答が同じ会話欄に出る。W7：回答の内容（DRAQ/GFP、根拠、核染色の提案） |
| 判定 2 | W7：設定の変更と実行の依頼に、対象と状態を付けた操作を示す。適用と実行は研究者の操作による（[§11](#11-issue-の解釈) の 7） |
| 判定 3・4 | W2 |
| 測定中 | W8 |
| 更新 | W10 |
| 優先 1・2 | W3、W5 |
| 優先 3 | W4、W5 |
| 優先 4 | W1、W5 |
| 優先 5 | W6、W7 |
| 優先 6 | W1：読み取りの失敗、未対応の形式、マスク、送信の中断、研究者による除外の区別。W8：測定の失敗 |
| 優先 7 | W1：行に名前・追加先・段階を記録する。W5：追加の前の一覧の名前を保持する。W9：再接続 |
| 優先 8 | W2：画像の事実、設定の表示と取り消し。W7：依頼の種類、確認が要る項目の選択肢 |
| 優先 9 | W2 |
| 優先 10 | W8 |
| 優先 11 | W10 |
| 受入 1 | W3〜W5。研究者による評価は別に追跡する |
| 受入 2 | W1（4 枚＋1 枚）、W5（一覧、フォルダー）、W6（表による割付）、W7（対話による割付） |
| 受入 3 | W1 |
| 受入 4 | W1（重複、上限、中断）、W4・W5（内訳） |
| 受入 5 | W2（会話の保存と復元、測らない）、W7（3 つの発言の流れ） |
| 受入 6 | W8〜W10 |

## 4. 調査結果

### 4.1 Issue の原因分析の確認

Issue の原因分析が、#257 の統合後の `main`（`462c288c`）でも成り立つことを確かめた。「再現」は、`createWorkspaceRuntime` に対する一時的な単体試験（`use-workspace-runtime.test.ts` と同じ偽の adapter。ファイル名だけで決まる経路のため 1 バイトの合成データ）で、`main` が Issue と同じ結果を返したことを指す。試験はコミットしていない。W1 で、修正後の期待に書き換えて追加する。

| Issue の項目 | 確認 | `main` の該当箇所 |
|---|---|---|
| 対照 A | 再現 | `use-workspace-runtime.ts` の `importFiles`（同名のファイルに別のフォルダー名を付ける）、`grouping.ts` の `groupFiles`（視野のキーにフォルダーを含める。内容のハッシュは `duplicate_content` の警告のみ） |
| 対照 B | 再現 | 同 `importFiles`（`added` に追加した後で `duplicate_channel` を検出し、全体を例外にする。`added` を戻さない） |
| 対照 C、巻き込み 1・2 | 再現 | 同 `importFiles`（拒否が 1 件あると保存後に例外を投げる）、`ConnectedWorkspace.tsx` の `addToExperiment`（戻り値の ID でのみ群を保存する） |
| 巻き込み 3 | 再現 | `use-workspace-runtime.ts` の `failedImports`（メモリー上のみ）、`refresh`、`UnfinishedImports.tsx`、`api-adapter.ts` の `registerImport`（行は `id`・`field_id`・`revision_id`・`exclusion_reason` のみ） |
| 巻き込み 4 | コード | `region_cohorts.py` の `assemble`、契約試験 `tests/test_experiment_strata.py::test_api_refuses_a_stratum_cohort_while_a_field_or_failed_upload_is_unaccounted_for` |
| 入力 1 | コード | `panel-state.ts` の `experimentSetupShown`、`ConnectedWorkspace.tsx` の開始画面の分岐 |
| 入力 2・3 | コード | `ConnectedWorkspace.tsx` の `add`（`setPending(files)` で置き換える）、`ExperimentSetup.tsx` の保留のカード（件数のみ） |
| 入力 4 | コード | `ExperimentSetup.tsx` の `pendingTarget`、`ConnectedWorkspace.tsx` の `placePending` |
| 入力 5 | コード | `grouping.ts` の `isSupportedImage`、`importFiles` の拡張子による `continue`、`api.ts` の `region_image_bit_depth_unsupported` |
| 追試 A・B | コード | `ConnectedWorkspace.tsx` の `sendInstruction`・`newWorkspace`・AI のパネル、`use-workspace-runtime.ts` の `requestProposal`、`api.ts` の `request`（`detail.reasons` を読まない）、`proposals.py` の `draft_proposal`、`db.py` の `proposal_drafts` |
| 測定中 | コード | `use-workspace-runtime.ts` の `runServer`（分母はステップ数）、`workspace_runs.py` のステップの生成（視野 × 領域の段数）、`ConnectedWorkspace.tsx` の視野の一覧（採用済みの結果のみ参照）とプレビューの 650 ms の待機 |
| 更新 | コード | `CloudAccount.tsx` の `UpdateBanner`、`cloud-account.ts` の `updateNotice`、`app_update.py` の `run_installer`・`UpdateService._run` |

### 4.2 Issue に記載のない所見

| | 所見 | 該当箇所 | 扱う作業単位 |
|---|---|---|---|
| 1 | 256 MiB を超えるファイルが 1 つあると、`importFiles` は取り込み全体を例外で打ち切る。API の上限は視野の合計に対して掛かる | `use-workspace-runtime.ts` の `importFiles`、`regions.py` の `upload_region_field` | W1 |
| 2 | 登録の冪等キー（`client_upload_id`）と行は視野単位で、1 視野の複数チャンネルを 1 回の要求で送る。422 は原因のファイルを返さない。行の ID と視野の対応（`uploadKeys`）はメモリー上にしかない | `importFiles`、`upload_region_field` | W1、W4 |
| 3 | `save_selection` は行の削除を受け付けない（`workspace_entries_cannot_disappear`）。票は 100 行までで、視野のない行も数に入る。行のモデルは未知の項目を拒否する（`RegionModel` の `extra="forbid"`） | `workspace_selection.py` の `save_selection`・`WorkspaceSelection`・`WorkspaceSelectionEntry` | W1 |
| 4 | `importFiles` は、行の保存（`registerImport`）の後に画像を送る。作業の上限（413 `workspace_limit`）は、画像を送った応答で分かる | `importFiles`、`upload_region_field` | W1 |
| 5 | 比較の設定は、その時点の票の全体を保存する（`config["workspace_selection"]`）。保存した票は `GET /v1/revisions/{rid}/workspace-selection` で読める。書き出しは、この票を Methods にそのまま出力する | `region_cohorts.py` の `assemble`・`saved_selection`、`region_exports.py` | W1 |
| 6 | 統計の画面の「n の内訳」は、保存済みの比較の結果（`counts`、`source_field_ledger`）から描画する | `ConnectedResults.tsx` | W1 |
| 7 | ワークスペースの上限は 100 視野・2 GiB | `config.py` の `max_fields`・`max_upload_bytes` | W1 |
| 8 | 視野のキーに取り込みごとのフォルダー名（`import-<UUID>`）が入るため、2 回に分けて選択した同じ視野の別染色は別の視野になる。既存の試験 `retains separate file identities when later images have the same filename` は、後から選択した同名のファイルを別の視野として扱うことを確かめている | `importFiles`、`grouping.ts` の `groupFiles` | W5 |
| 9 | ワークスペースは `importFiles` の中で初めて作られる。`importFiles` と `ensureWorkspace` は `exclusive` を通り、処理中の呼び出しは例外になる。取り込み中は `intakeDisabled` が真になる | `use-workspace-runtime.ts`、`ConnectedWorkspace.tsx` | W4、W5 |
| 10 | 登録の読み取りは、クライアントの振り分けに依存する。OME のメタデータがあれば `/region-fields/ome`、RGB の表示用画像は `input_mode: display-rgb` で読む。チャンネル間の寸法の一致と上限は視野単位で判定する | `tiff-intake.ts`、`importFiles`、`upload_region_field` | W4 |
| 11 | マスクと判定できるのは、API が `region_image_bit_depth_unsupported` で拒否する 32-bit 整数の画像だけである。8-bit・16-bit のマスクは画像として視野になる | `regions.py`、`api.ts` | W1、W4、W5 |
| 12 | フォルダーからの相対パスは、フォルダーの入力とドロップでだけ得られる。ファイルの選択では名前だけになる | `dropped-files.ts` の `intakePath` | W6 |
| 13 | 解析案が検証で拒否されると、API は 502 を返し、解析案に含まれる文章（`rationale`、`missing_information`）も破棄する。`validate_draft` は理由コードだけを外へ返す。形が不正な場合は解析案そのものが得られない。拒否された依頼のキャッシュの行は `failed` になり、同じ依頼の再送は 409 `proposal_explicit_retry_required` になる | `proposal_validation.py` の `validate_draft`、`proposals.py` の `draft_proposal` | W2 |
| 14 | 画像の登録後に「回答のみ」を表せる有効な解析案は、`recipe: "none"`、全チャンネルの列挙、指標と図が空、の 1 通りに限られる。プロンプトは目的の文を研究の問いの記述として扱い、質問や実行の保留を指示していない | `validate_draft`、`services/proposal-worker/src/openai.ts` | W7 |
| 15 | `recipe: "none"` の応答でも、`applyProposal` は解析の仕様（指標、図の提案、統計の方法）を書き換えて保存する | `use-workspace-runtime.ts` の `applyProposal`・`requestProposal` | W2 |
| 16 | 完了した解析案を読み出す API がない。画面の解析案はメモリー上のみで、`refresh` は復元しない。同じ文脈の同じ依頼は、キャッシュからモデルを呼ばずに返る | `proposals.py`、`use-workspace-runtime.ts` | W2 |
| 17 | AI の入力欄は、AI が使える状態（クラウドへのログインと有効化、互換性の確認）でなければ無効になる | `AiSettings.tsx` の `useAi`、`ConnectedWorkspace.tsx` の `sendInstruction` | W2 |
| 18 | 解析案の文脈は、視野ごとに名前・条件・実験回など 5 項目だけを持つ。視野の ID、フォルダー、実験デザインの群の名前は持たない。中継は未知の文脈を拒否する | `proposal_contracts.py` の `ContextField`、[中継のデプロイ](../../proposal-deployment.md) | W7 |
| 19 | 実行の採用（`accept_run`）は、実行の全ステップが成功していないと 409 `analysis_run_not_complete` になる。1 視野の失敗で、成功した視野も採用できない。同じ仕様・同じ票の実行では、成功済みのステップが再利用される | `workspace_runs.py`、`use-workspace-runtime.ts` の `runServer` | W8 |
| 20 | 計算ワーカーは終了すると 2 回まで再起動され、通算 3 回目の終了でランチャーがサービス全体を停止する。この上限は[ローカル配布の文書](../../local.md)に記載があり、試験もある。停止の理由は記録されない。この経路では、`run_local` が例外を返し、ランチャーが「Cytellectを起動できないか、実行が停止しました。」と「再試行」を表示する。Issue にその表示の記述はない | `local.py` の `WorkerSupervisor.start`、`run_local`、`main`、`_gui_failure_message` | W9 |
| 21 | セッションを作り直す API（`POST /v1/local/session`）は、接続の画面（`WorkspaceAccess.tsx`）と更新の追跡が使う。解析の画面の API 呼び出し（`request`）は、401 でページの再読み込みを求める | `api.ts`、`cloud-account.ts` の `reconnect` | W9 |
| 22 | 更新ボタンの押下後、`update_not_available` は状態を再取得するだけで、`update_unsupported` は案内を非表示にする。どちらも利用者に結果を示さない | `CloudAccount.tsx` の `applyUpdate` | W10 |
| 23 | データベースの構成は Alembic で管理する（`migrations/versions` の 0001〜0012。`Store` が開くたびに `upgrade head`）。アプリ内更新の復帰（`restore_pending_database`）は、更新直後の失敗だけを戻す | `db.py`、`app_update.py` | W2 |
| 24 | 公開デモは、開いたときに行う GET を正規表現 `OPENING` で限定し、それ以外の要求を 409 `showcase_action_not_recorded` にする。デモは API と解析パッケージをホイールにして Pyodide で動かす。ホイールが古い場合、CI は警告を出す（失敗にはしない） | `apps/web/src/lib/showcase/transport.ts`、[公開デモ](../../showcase.md)、`ci.yml` | [§8](#8-公開デモへの影響) |
| 25 | Windows の統合試験（`windows-installer` など）は、`main` への push と手動の起動（`workflow_dispatch`）でだけ走り、PR では走らない。配布の workflow は `main` のコミットだけを受け付ける。`main` への push は、設定が有効な場合に EXE の自動配布と Microsoft Store への提出を起動する | `.github/workflows/ci.yml`・`local-release.yml`・`windows-store-release.yml` | [§7](#7-順序と配布) |

### 4.3 原因を特定できていない項目

原因の証拠がない項目には、症状を消す実装と原因を記録する実装だけを割り当てる。原因を仮定した構造の変更は、記録から原因が分かった後に、別の変更として行う。

| Issue の項目 | 分かっていること | 実装での扱い |
|---|---|---|
| 追試 A：形式エラーの理由コード | 検証の理由コードは 51 種類あり、今回の値はどこにも保存されていない | W2 で理由コードを保存する。文章の回答は検証の結果によらず表示する |
| 復旧・測定中：`Failed to fetch` | Issue は 2 回を記録している（11 月 22 日の全体測定中、11 月 23 日の画像の登録中）。後者では 8765 番に待受がなかった。所見 20 の経路は候補として弱い | W9 で全経路の停止理由を記録し、接続の案内と再接続を入れる。停止の経路そのものは変えない |
| 入力 6：フォルダーで受け取れない | 観測は Edge の拡張機能を介した操作による。手動の操作での発生は未確認 | W1 で選択の結果を必ず表示し、W5 で件数のみの診断を加え、W11 で手動の操作を確かめる |
| 更新：ボタンの無反応 | 所見 22 の 2 つの分岐が該当しうる。どの分岐かは未確認 | W10 で全分岐に結果を表示する |
| 更新：`.27` への更新の失敗 | 記録は `update_install_failed` のみで、原因は分からない | W10 で段階と終了コードを記録する。W11 で実機の更新を確かめ、失敗する場合はインストーラーまたは Store からの導入を案内する |

### 4.4 #257 の統合との整合

Issue の点検は #257 の統合（genellect/cytellect#291）より前の版で行われた。統合で変わった点と、この文書での扱いは次のとおり。Issue が挙げる症状の原因箇所（[§4.1](#41-issue-の原因分析の確認)）は、統合で変わっていない。

| #257 の統合で変わった点 | この文書での扱い |
|---|---|
| 統計の画面から確認欄がなくなった（#257 の決定 11）。前の画面の作業が残る場合だけ、結果の場所に 1 つを示す（`statistics-readiness.ts` の `remainingWork`：「実験：撮影条件 未確認」「画像：未測定 n 視野」）。欠測は結果の「n の内訳」で扱う | W1 は、登録できなかった画像を「残る作業」に加えず、「n の内訳」に示す。統計の画面の「登録できなかった画像：n 件。比較の前に…」の表示は、決定 11 と同じ方向で削除する |
| 実験デザインのないワークスペースは、統計の画面で群と実験回を入力して確認する（#273 の判断） | 決定 1 により、新しいワークスペースは実験デザインのない状態で始まる。この経路をそのまま使い、W6 で後から実験デザインを作って割り付ける。新しい状態は増えない |
| 「実験」の画面が、状態の印（実験回、群、視野の割付済み／全体、撮影条件、独立性）、実数の図、見出しの右の「統計で比べる →」になった（#257 の決定 13、`experiment-summary.ts`）。「群・実験回が未割り当ての視野」の節は、視野ごとの選択欄を持つ | W6 は、既存の「群・実験回が未割り当ての視野」の節を、複数選択と割付の案を持つ表に改める。印、図、次の一手は変えない |
| 統計は、開始時と完了時に、票が比較の作成時と同じであることを確かめる（`assert_selection`）。保存済みの結果が今の結果かどうかの判定が加わった（NS-04） | W1 の票の変更（行の追加、削除、状態の変更）は、この規則のとおり、保存済みの比較を前の結果にする。新しい判定は加えない |
| 候補は、検出した時点の仕様の内容で照合する（`candidateSignature`、`workspace_runs.py` の `same_detection_spec`）。主要指標の宣言（`primary_outcome`）が仕様に加わった | W2 の適用の分離と W8 の進捗は、この照合を変えない。解析案の適用は `primary_outcome` を保持する（現在の `applyProposal` と同じ） |
| 「独立実験単位」の呼び名が「実験回」になった（genellect/cytellect#280） | この文書と画面の文言は「実験回」を使う。Issue の画面の文言（統合前）とは、この点が異なる |
| 画面の作り直しの原則が定められた（[#257 の実装案 §3](../nucleolar-measurement/implementation.md#3-作り直しの原則)）：`main` の画面が基準、文章で説明しない、画面の案を先に示す、変更前後を並べて確かめる | 画面を変える作業単位（W1、W2、W5、W6、W8〜W10）はこの原則に従う |

## 5. 設計

### 5.1 原則

1. 取り込みは項目ごとに結果を持つ。1 項目の失敗が、ほかの項目の登録、群の割付、測定、比較を妨げない。
2. 選択したファイルは、役割と状態を付けてすべて一覧に表示する。受け取った件数は、役割別の内訳の合計と一致する。
3. 登録できなかった理由はアプリが記録する。名前、段階、理由コードを保存し、再起動後も同じ名前で表示する。
4. AI の文章の回答は、設定の検証の結果によらず表示する。検証が止めるのは設定の適用に限る。
5. 設定の変更と解析の実行は、研究者の操作でだけ行う。AI の応答はこれらを自動で起こさない。
6. 会話はワークスペースと視野に結び付けて保存し、再表示のためにモデルを呼び直さない。
7. 操作には、その場所に受付、進行、結果のいずれかを表示する。
8. サービス、更新、接続の停止では、段階と理由コードを PC 内に記録する。この記録に研究データ（ファイル名、指示の文、画素）を含めない。
9. 画像の登録の経路は 1 つとする。画面のどこから追加しても、同じ判定、同じ重複の規則、同じ結果の形を通る。

科学上の規則は変えない。原画像の画素値を変更しない。測定値と統計は共通実装だけが生成する。ファイル名とフォルダーから群、実験回、染色を確定しない（E-04、I11、U02。案を提示して研究者が確定する方式はこれに反しない）。失敗した視野を記録なしに除外しない。

### 5.2 取り込みの判定の順序

選択したファイルは、次の順で判定する。対照 A と対照 B は同じ入力に異なる扱いを求めうるため、順序を固定する（[§11](#11-issue-の解釈) の 1）。

1. **拡張子**：TIFF でなければ「対象外」。
2. **読み取り**（W4 以降）：TIFF を API の共通の読み取り処理で判定し、画像・マスクの候補・読み取れない、に分ける。W4 より前は、この判定は登録の時点で行われる。
3. **同一内容**：SHA-256 が、同じ選択のほかのファイル、または登録済みの視野の入力（`image_info.inputs`）と一致するファイルは、複製として視野にしない。
4. **組み分け**：残った画像を視野とチャンネルにまとめる（既存の `groupFiles`）。
5. **名前の競合**：内容の異なる 2 枚が同じ視野・同じチャンネルに当たる場合に限り、その視野を判断待ちにする。

この順序では、対照 B の入力（a9-C01 と同じ内容の改名コピー）は 3 で複製として扱われ、競合にならない。名前の競合の試験には、内容の異なる競合（例：f9620-C01 を `BBBC007-a9_c01.tif` に改名したもの）を使う。

### 5.3 取り込みの記録

新しい表は作らない。票の行を拡張する。行は現在と同じく視野単位で、`id` を `client_upload_id` に使う（所見 2）。`entries` は JSON の列のため、データベースの移行は不要である。

```text
intake: { names: [1〜4 件、各 255 文字以内],   // 視野を構成するファイルの名前（フォルダーからの相対パス。なければファイル名）
          state: "pending" | "rejected" | "registered",
          stage: "inspect" | "register" | null,   // 失敗した段階。"inspect" は W5 以降
          code:  理由コード | null,
          target: {run_id, group_id, sample} | null,   // 研究者が指定した追加先
          separate: true }                        // 「別の撮影として追加」の記録。該当しなければ省く
```

**行の規則**

- `intake` は省略できる。値のない項目は出力しない（既存の票と、票の全体を比べる `isSelectionCurrent` を変えないため）。
- `state: registered` は視野（`field_id`）のある行にだけ、`pending`・`rejected` は視野のない行にだけ許す。
- `save_selection` は、視野のない行に限って削除を受け付ける（所見 3）。

**書き込みの順序**（`importFiles`。所見 4）

1. 票が 100 行に達している場合は、行を作らず、結果に `ledger_full` として返す。
2. 行を作る（`names`、`target`、`state: pending`）。
3. 画像を送る。成功した場合は `state: registered` とする。拒否された場合（422、413）は `state: rejected`、`stage: register`、応答の理由コードを書く。256 MiB を超えるファイルを含む視野は、送らずに `rejected`（`field_upload_limit`）とする。
4. 応答を受け取れなかった行は `pending` のまま残る。

**追加先の適用**　`target` を持つ `registered` の行のうち、実験デザインに割付のない視野は、取り込みの完了時と `refresh` 時に、`target` の群と実験回へ割り付ける。割付を、呼び出し元が受け取る戻り値に依存させない（対照 C の原因。中断の後にも適用される）。

**差し替えと取りやめ**

- 差し替えは、同じ行の `id` を `client_upload_id` にして再送する。視野の作成後、既存の `selection_at` が行と視野を結び付ける。行と視野は増えない。行の ID を指定して送る関数（`replaceImport(entryId, files)`）をランタイムに加える（所見 2）。
- W1 の差し替えは、行の全ファイルを選択し直す（422 は原因のファイルを返さないため）。ファイル単位の差し替えは W5 で加える。
- 「追加をやめる」は行を削除する。

**欠測の数え方**

- 視野がなく、`state` が `rejected` または `pending` の行を「登録できなかった画像」とし、`target` の群と実験回ごとに数える。`target` のない行は「群の指定なし」に数える。削除した行は数えない。
- 理由コードが `region_image_bit_depth_unsupported` の行は、マスクの候補として表示し、欠測に数えない（所見 11）。W4 以降、マスクの候補は行を作らない。
- 画面の「n の内訳」は、比較の設定に保存された票（`GET /v1/revisions/{rid}/workspace-selection`）の `intake` から数える（所見 5・6）。比較の結果の契約は変更しない。

**行を持たない結果**　`held`（名前の競合）、`duplicates`（同一内容）、`skipped`（対象外）、`ledger_full` は行を持たない。取り込みの一覧には、その回の `IntakeOutcome` から表示し、再読み込みで消える。

**保存の範囲**　ファイル名は研究データである。保存先は、PC 内のデータベース、研究者自身の書き出し（Methods は票をそのまま出力する。所見 5）、追加の前の一覧を保持するブラウザの記憶（W5）に限る。ログ、診断、AI への送信範囲には加えない。

### 5.4 取り込みの結果（`IntakeOutcome`）

`importFiles` の戻り値を次の形にする（W1）。

```ts
interface IntakeOutcome {
  registered: Array<{fieldId: string; names: string[]}>;
  rejected:   Array<{entry: string | null; names: string[]; code: string}>;  // entry が null なら行なし（ledger_full）
  held:       Array<{names: string[]; reason: "duplicate_channel"}>;         // 内容の異なる名前の競合。未送信
  duplicates: Array<{name: string; sameAs: string}>;                         // 同一内容。視野にしない
  skipped:    Array<{name: string}>;                                         // 画像以外
}
```

項目単位の失敗では例外を投げない。例外（`IntakeInterrupted`）は、作業全体を継続できない場合（応答なし、セッション切れ、ワークスペースの変更）に限り、その時点までの `IntakeOutcome` を保持する。

### 5.5 会話の記録（`assistant_messages`）

研究者の発言を 1 行ずつ記録する API の表を新設する（W2。Alembic の revision を 1 つ追加する）。`proposal_drafts`（同一の依頼に対するキャッシュ）とは分ける。

| 列 | 内容 |
|---|---|
| `id`、`workspace_id`、`field_id`、`created` | 発言と、送信時に選択していた視野 |
| `text` | 指示の原文（2,000 文字以内） |
| `state` | `pending`、`answered`、`failed` |
| `reply` | 文章の回答 |
| `applicable`、`reasons`、`stage` | 設定を適用できるか。できない場合の理由コードと、失敗した段階 |
| `request_id`、`draft_id` | 中継への依頼の ID と、適用できる解析案（`proposal_drafts`） |
| `effect` | この発言に対して研究者が行った操作：`none`、`settings`、`run` |

**発言を作る時点**（`draft_proposal`）

| 分岐 | 発言の行 |
|---|---|
| 送信の確認がない（428）、ワークスペースがない（404）、同じ依頼が進行中（409 `proposal_request_in_progress`） | 作らない |
| キャッシュに完了した解析案がある | 作る。`answered`。モデルは呼ばない |
| モデルを呼び、解析案が検証を通る | 作る。`answered`、`applicable: true` |
| モデルを呼び、検証で拒否され、文章を取り出せる | 作る。`answered`、`applicable: false`、`reasons` |
| モデルを呼び、形が不正で文章を取り出せない、または中継が失敗 | 作る。`failed`、`reasons`、`stage` |
| 明示の再送が要る（409 `proposal_explicit_retry_required`） | 作らない。元の発言の「再送」で送り直す |

**経路**

- `GET /v1/workspaces/{wid}/assistant-messages`：`{messages: [{id, field_id, created, text, state, reply, applicable, reasons, stage, effect}]}` を、作成の順に返す。
- `PATCH /v1/workspaces/{wid}/assistant-messages/{id}`：`{effect}` を更新する。

**復元**　再読み込みの後は、発言、回答、状態を表示する。適用の操作は、同じセッションで受け取った応答に表示する。再読み込みの後に適用する場合は、発言の「再送」で応答を取り直す。文脈が変わっていなければ、キャッシュから返り、モデルは呼ばれない（所見 16）。

### 5.6 AI の応答と操作

決定 4 に従い、応答はどの場合も設定と解析を変えない。

**W2 の時点**

| 応答 | 発言の下に表示するもの |
|---|---|
| 設定を適用できない（`applicable: false`） | 回答、適用できない理由 |
| 適用できる解析案で、`recipe` が `none` | 回答 |
| 適用できる解析案で、`recipe` が `none` 以外 | 回答、「設定を適用」、「適用して試行」（選択視野の候補を作る） |

**W7 以降**　解析案に加える `intent` は、表示する操作を選ぶためだけに使う。モデルが誤って宣言しても、研究者が操作しない限り何も起きない。

| `intent` | 発言の下に表示するもの |
|---|---|
| `answer` | 回答、確認が要る項目の選択肢（ある場合） |
| `settings` | 回答、「設定を適用」 |
| `run` | 回答、対象の視野、「適用して実行」 |

適用した発言には、「解析設定を表示」と「AI による設定変更を戻す」（既存の `showSettings`、`undoProposal`）を表示する。

### 5.7 状態の表示

状態の語を次に統一する。文言は UC-01〜UC-07（[結果の表現とデモの素材の要件](../results-and-demo-story/requirements.md#e-ui-の文言uc)）に従う。

| 対象 | 語（対応する値） |
|---|---|
| 選択したファイルと行 | 読み込み中、追加待ち、登録済み（`registered`）、要確認（`held`）、同一内容（`duplicates`）、マスクの候補、対象外（`skipped`）、読み取れない（`rejected`）、再選択（`pending`） |
| 視野の解析 | 準備中、待機、検出中、候補を確認、採用中、保存済み、失敗 |
| 発言 | 送信中（`pending`）、回答（`answered`）、失敗（`failed`）、設定を適用済み（`effect: settings`）、実行済み（`effect: run`） |
| 接続 | 接続中、再接続中、停止 |

## 6. 作業単位

| | 内容 | 種類 | 依存 |
|---|---|---|---|
| W1 | 取り込みの最初の修正（部分成功、競合、複製、記録、比較の停止の廃止） | fix(web, api) | — |
| W2 | AI の最初の修正（会話の保存、失敗理由、文章の表示、操作の明示、画像の事実） | fix(web, api, analysis) | — |
| W3 | 画面の案（新しい画面） | docs | — |
| W4 | 取り込みの判定の API | feat(api) | — |
| W5 | 画像から始める画面と取り込みの一覧 | feat(web) | W1、W3、W4 |
| W6 | 群と実験回の割付 | feat(web) | W3、W5 |
| W7 | AI の依頼の種類と割付の案 | feat(api, analysis, worker, web) | W2、W6 |
| W8 | 視野ごとの進捗 | fix(web) | — |
| W9 | 接続の区別、再接続、停止理由の記録 | fix(web, api) | W1 |
| W10 | 更新案内 | fix(web, api) | — |
| W11 | Windows の実機での受入 | test | 各作業単位の配布 |

**画面の扱い**　画面を変える作業単位は、[#257 の実装案 §3](../nucleolar-measurement/implementation.md#3-作り直しの原則) の原則に従う。新しい画面と導線（W5、W6）は、W3 が `main` に入った後に、その案を実装する。W3 の `main` へのマージが、案への合意にあたる。既存の画面の中の表示の修正（W1、W2、W8〜W10）は、W3 を待たず、PR に `main` と並べた変更前後の画像を付ける（`cytellect-screen-check`）。

**API の変更**　API を変える作業単位（W1、W2、W4、W7、W9、W10）は、`python3 scripts/dev.py contracts` を実行し、OpenAPI と生成した型を同じコミットに含める。

以下、場所の表記で `review/` は `apps/web/src/components/workspace/review/`、`lib/workspace/` は `apps/web/src/lib/workspace/`、`cytellect_api/` は `services/api/src/cytellect_api/` を指す。`ConnectedWorkspace.tsx`、`use-workspace-runtime.ts`、`api-adapter.ts` は 1 行が長いため、`grep -n` と `awk` の `substr` で該当箇所を切り出して読む。

### W1 取り込みの最初の修正

索引の最優先のうち、取り込みに関する 4 行を、画面の構成を変えずに止める。

**変更**（API、ランタイム、画面の順）

*API*

1. 行に `intake`（[§5.3](#53-取り込みの記録) の形と行の規則）を加える。`save_selection` は、視野のない行に限って削除を受け付ける。
2. `assemble` から、視野も理由もない行による 409 `workspace_selection_incomplete` を削除する。測定値と統計の計算は変更しない。群または実験回に有効な値がない比較は、既存の検査（`region_comparison_unit_without_values` など）で保留する。

*ランタイム*

3. `importFiles` の戻り値を `IntakeOutcome`（[§5.4](#54-取り込みの結果intakeoutcome)）にする。API の拒否、名前の競合、大きさの上限、作業の上限、票の上限では例外を投げず、該当する項目だけを結果に入れる。
4. 判定を [§5.2](#52-取り込みの判定の順序) の 1・3・4・5 の順にする。同一内容のファイルは `duplicates` に入れ、視野にしない。OME のファイルも同じ判定を通す。登録済みの視野との照合のため、Web の `ImportedField` の型に `image_info.inputs` を加える。名前の競合は、競合した視野だけを `held` にし、ほかの視野を登録する。`held`・`rejected`・`duplicates` の項目を `added` と `files` から除く。
5. 行の書き込みを [§5.3](#53-取り込みの記録) の「書き込みの順序」にする（`registerImport`、`upload`、`uploadOme`）。
6. 追加先の適用（[§5.3](#53-取り込みの記録)）を、取り込みの完了時と `refresh` 時に行う。`addToExperiment` と `placePending` は、追加先を `importFiles` に渡すだけにし、戻り値の ID による割付をやめる。
7. `replaceImport(entryId, files)` を加える。`duplicates` の項目を「別の撮影として追加」する関数を加える（行に `separate` を書く）。`failedImports`・`excludeImports` を削除する。

*画面*

8. `pending` を追記にし、登録の完了後に解放する。
9. 「取込」の一覧を、票の行（視野のない行）と、その回の `IntakeOutcome`（行を持たない結果）から描画する。

   | 項目 | 表示 | 操作 |
   |---|---|---|
   | `rejected` の行 | 名前：理由 | 「差し替え」、「追加をやめる」 |
   | `pending` の行 | 名前：登録が完了していません | 「差し替え」、「追加をやめる」 |
   | マスクの候補の行（[§5.3](#53-取り込みの記録)） | 名前：マスクの候補 | 「追加をやめる」 |
   | `intake` のない既存の行 | 以前の取り込みの記録（名前なし） | 「追加をやめる」 |
   | `held` | 競合した 2 枚の名前：要確認 | 使う 1 枚を選択し直す |
   | `duplicates` | 名前：同一内容（対応先の名前） | 「別の撮影として追加」 |
   | `skipped`、`ledger_full` | 名前：対象外／上限 | — |

   除外理由の入力欄と「まとめて除外」（`UnfinishedImports.tsx`）、統計の画面の「登録できなかった画像：n 件。比較の前に…」の表示を削除する。
10. 統計の画面の「n の内訳」に、登録できなかった画像の件数を群・実験回・理由ごとに表示する（数え方と源は [§5.3](#53-取り込みの記録)）。「残る作業」（`remainingWork`）には加えない。
11. 選択の結果を必ず表示する。空のフォルダー、画像を含まない選択、選択の取り消し（`input` の `cancel` イベント。直前の選択を保持する）を区別する。
12. 上部のエラー表示と「再読み込み」は `IntakeInterrupted` に限る。

研究者が視野を対象外にする操作（`excludeField`、理由付き）は変更しない。票の行の追加、削除、状態の変更は、既存の規則（`assert_selection`、NS-04）のとおり、保存済みの比較を前の結果にする。

**変更箇所**

| 場所 | 変える点 |
|---|---|
| `cytellect_api/workspace_selection.py` の `WorkspaceSelectionEntry`、`save_selection` | 変更 1 |
| `cytellect_api/region_cohorts.py` の `assemble` | 変更 2 |
| `lib/workspace/use-workspace-runtime.ts` の `importFiles`、`dropImport`、`refresh` | 変更 3〜7 |
| `lib/workspace/api-adapter.ts` の `registerImport`、`upload`、`uploadOme`、`ImportedField` | 変更 4・5・7 |
| `review/ConnectedWorkspace.tsx` の `add`、`addToExperiment`、`placePending`、`pending`、「取込」の一覧、ファイルの `input`、エラー表示 | 変更 6・8・9・11・12 |
| `review/ExperimentSetup.tsx` の `received`、`place`、保留のカード | 変更 6・8 |
| `review/UnfinishedImports.tsx` | 変更 9 |
| `review/ConnectedResults.tsx` の「n の内訳」、統計の画面の通知 | 変更 9・10 |
| `apps/web/src/lib/api.ts` の `workspace_selection_incomplete` | 文言 |

**終わりの条件**　[§3](#3-issue-の項目と作業単位の分担) の W1 の範囲。対照 C は再読み込み後の各群の内容まで照合する。

**試験**

- API：`intake` の検証、視野のない行の削除。契約試験 `test_api_refuses_a_stratum_cohort_while_a_field_or_failed_upload_is_unaccounted_for` の前半（視野のない行が 1 つあると拒否する）を、拒否しない試験に書き換える。後半（層の未定の視野による拒否）は維持する。
- 単体：[§4.1](#41-issue-の原因分析の確認) の再現試験 4 件を、修正後の期待に書き換えて追加する。判定の順序（同一内容が競合より先）、内容の異なる競合、OME の複製、`pending` の追記、大きさ・作業・票の上限、追加先の適用（中断の後を含む）、差し替え、マスクの候補を欠測に数えないこと。
- 単体：既存の `names a rejected file, keeps its ledger entry until it is excluded with a reason, and never resends it` は、例外と除外ではなく `rejected` と行の内容を確かめる形に改める。
- ブラウザ：`workspace-form-first.spec.ts` に群のセルへの混在入力を加える。`workspace-unfinished-imports.spec.ts` を、再読み込み後の名前と理由、差し替え、比較の計算、「n の内訳」まで確かめる内容に書き換える。

**文書**　`docs/web.md`（取り込みと、登録できなかった画像の段落）、`docs/region-comparisons.md`（Input ledger and missingness）、`docs/requirements.md`（I12、S10）、`docs/generic-regions.md`（`client_upload_id`）、`SECURITY.md`・`docs/security.md`（保存する項目にファイル名を加える）。

**レビュー**　`/code-review high`（比較の検査）、`/security-review`（アップロードの受け入れ）。

### W2 AI の最初の修正

追試 A・B を、AI の中継を変えずに止める。

**変更**（解析パッケージと API、ランタイム、画面の順）

*解析パッケージと API*

1. `validate_draft` が拒否する場合に、文章を呼び出し元へ渡す。解析案の形が正しく（`ProposalDraft` として読める）、文章の検査（`FORBIDDEN_TEXT`）を通る場合に限り、`ProposalRejected` に `rationale` と `missing_information` を持たせる。形が不正な場合と、文章の検査に通らない場合は、文章を持たせない（所見 13）。理由コードを 1 つの定数に列挙する。
2. 表 `assistant_messages` と 2 つの経路（[§5.5](#55-会話の記録assistant_messages)）を加える。`draft_proposal` は、[§5.5](#55-会話の記録assistant_messages) の「発言を作る時点」のとおりに行を作り、結果を書く。
3. `draft_proposal` は、拒否で文章がある場合に、200 で `reply`、`applicable: false`、`reasons` を返す。文章がない場合は現在の 502 を返す。どちらの場合も、理由コード、段階、`request_id` を発言の行に保存する。ログには指示の原文とモデルの出力を書かない（判定 3）。キャッシュの行（`proposal_drafts`）の扱いは変えない。

*ランタイム*

4. `request` は `detail.reasons` を `ApiError.reasons` に格納する。
5. 発言の一覧を持つ。ワークスペースを開いたときに取得する。`newWorkspace` で一覧を初期化する。
6. `requestProposal` を、応答の取得と、適用・試行に分ける（決定 4、[§5.6](#56-ai-の応答と操作) の「W2 の時点」）。応答の取得は、設定、解析の仕様（所見 15）、解析を変えない。適用と試行は、研究者の操作から呼び、`effect` を更新する。適用は `primary_outcome` を保持する。
7. `previous_goal` に、`previous_proposal`（直前の適用できる解析案）を生んだ発言の文を送る。

*画面*

8. AI のパネルを `AssistantPanel.tsx` に分け、発言の一覧から描画する。送信時に入力欄を空にする。`newWorkspace` で入力欄を初期化する。発言ごとに状態（[§5.7](#57-状態の表示)）を表示する。
9. 失敗と、適用できない理由は、該当の発言の下に表示する。理由コードを、研究者が修正できるもの（例：`proposal_one_nuclear_channel_required`）とサービス側のもの（例：`proposal_shape_invalid`）に分ける対応表を 1 か所に置く。前者には該当する設定を開く操作、後者には再送（既存の `retry_failed`）を付ける。
10. 適用した発言に、「解析設定を表示」と「AI による設定変更を戻す」を表示する（優先 8）。
11. 空欄の送信を無効にする。画像だけから解析案を作る操作は、AI のパネルの「解析案を作る」に置く（送信内容は現在の空欄の送信と同じ）。
12. AI のパネルの先頭に、選択した視野の事実を常に表示する：チャンネルの名前とその由来（記録がある場合）、寸法、核染色の指定の有無。モデルを呼ばずに表示する（優先 8）。AI が使えない状態（所見 17）でも表示し、既存の `AiAvailabilityHint` で有効にする方法を示す。
13. 公開デモ：発言の一覧の GET を呼ばない（所見 24）。例を選ぶ操作は、研究者の操作として、応答の取得に続けて適用と試行を行う（現在と同じ要求の列）。記録済みの応答（現在の形）を読めるようにし、記録は変えない。

送信の連打は、既存の `exclusive`（処理中の呼び出しを拒否する）と 409 `proposal_request_in_progress` が防ぐ。変更は加えず、試験で確かめる（判定 4）。

**変更箇所**

| 場所 | 変える点 |
|---|---|
| `packages/analysis/src/cytellect_analysis/proposal_validation.py` の `validate_draft`、`ProposalRejected` | 変更 1 |
| `cytellect_api/db.py`、`cytellect_api/migrations/versions/`（新しい revision） | 変更 2 |
| `cytellect_api/proposals.py` の `draft_proposal`、`ProposalDraftResponse` | 変更 2・3 |
| `apps/web/src/lib/api.ts` の `request`、`ApiError` | 変更 4 |
| `lib/workspace/api-adapter.ts` の `draft` | 応答の形（現在の形も読む）、一覧の取得、`effect` の更新 |
| `lib/workspace/use-workspace-runtime.ts` の `requestProposal`、`applyProposal`、`newWorkspace`、`load` | 変更 5〜7 |
| `review/ConnectedWorkspace.tsx` の `instruction`、`send`、`sendInstruction`、AI のパネル、入力欄。新規 `review/AssistantPanel.tsx` | 変更 8〜13 |

**終わりの条件**　[§3](#3-issue-の項目と作業単位の分担) の W2 の範囲。AI が使える状態（ログイン済み、有効）で確かめる。

**試験**

- 解析と API：`tests/test_proposals.py` の拒否の試験を、文章を返す場合と返さない場合（形の不正、文章の検査）に拡張する。[§5.5](#55-会話の記録assistant_messages) の「発言を作る時点」の全分岐。新しい revision の適用と、古い版のデータベースからの移行。
- 単体：発言の状態、`newWorkspace` での初期化、復元、応答の取得だけでは設定・仕様・解析が変わらないこと、理由コードの対応表が定数の全コードを網羅すること。
- ブラウザ：作業 A → B → A、再読み込み、連打。公開デモの例の選択が現在と同じ結果になること（`showcase.spec.ts`）。

**文書**　`docs/requirements.md`（「LLM」の節の L02）、`docs/proposal-service.md`、`docs/web.md`、`SECURITY.md`・`docs/security.md`（指示の原文を PC 内に保存する）、`docs/local.md`（古い版のアプリが新しい revision のデータベースを開いた場合の動作。試験で確かめて記す）。

**レビュー**　`/code-review medium`、`claude-api`。

### W3 画面の案

genellect/cytellect#258 は、画面の変更が説明の文で埋まり却下された。新しい画面（W5、W6）は、[#257 の実装案 §3](../nucleolar-measurement/implementation.md#3-作り直しの原則) の原則 4 に従い、実装の前に案を画像で示す。

**作成するもの**　次の 3 画面について、`main` の同じ場面と並べた案の画像を `docs/drafts/native-first-run/` に置く。画面ごとに案は 1 つとし、公開画像を使い、`frontend-design` と `design:ux-copy` を用いる。

1. 空の作業：中央の「画像を追加」（選択、フォルダー、ドロップ）、受け付ける形式の 1 行、見本 3 点（測定する蛍光画像、同じ視野の別染色、輪郭のマスク。登録済みの公開画像と出典）
2. 取り込みの一覧：内訳の 1 行、縮小画像・名前・チャンネル・状態の行、「追加」、「追加して AI に聞く」、「画像を足す」、行ごとの取り消し、競合の行、同一内容の行、登録できなかった行
3. 「実験」の未割り当ての視野の表（実験回と群の案）。状態の印、実数の図、「統計で比べる →」は現在のまま

案は次の条件を満たす：`main` の配置と密度を保つ。常に表示する説明の段落を足さない。状態は「項目：値」で示す。最初の表示域で、次の操作が 1 つに見える。

次の図は配置の説明で、見た目の案ではない。

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

**終わりの条件**　3 画面の案の画像が、`main` の画面と並べて PR に置かれている。案への指摘は、この PR で受けて案を直す。

### W4 取り込みの判定の API

登録の前に、ファイルの役割と縮小画像を返す。何も保存しない。

**設計の選択**　登録前のファイルを API に保存する方式（受け取りの表、内容の保存、確定の API）は採らない。その方式は登録の経路が 2 つになり、2 GiB の上限に登録前の内容が加わり、表の移行と削除の処理が要る。Issue は再読み込み後の再選択を認めている（優先 7「ブラウザーがファイル再選択を必要とする場合は、その対象名を示す」）。内容は判定と登録で 2 回送ることになる（PC 内の通信）。

**変更**

1. `POST /v1/intake/inspect`：1 ファイルと、クライアントの振り分け（`kind`：`native`、`display-rgb`、`ome`。所見 10）を受け取る。ワークスペースに依存しない（所見 9）。登録と同じ読み取りの関数で判定し、次を返す：役割（`image`、`label`、`unreadable`）、理由コード、寸法、型、OME のチャンネル名、SHA-256、表示用の縮小画像。一時ファイルは応答の前に削除する。256 MiB の上限と、共有の開発環境の制限（`CYTELLECT_UPLOAD_ALLOWLIST`）を適用する。認証と要求の検査は、ほかのローカルの経路と同じにする。
2. `label` は、32-bit 整数の画像（登録が `region_image_bit_depth_unsupported` で拒否するもの）に限る。8-bit・16-bit の画像は内容から用途を推定せず、`image` とする（所見 11）。
3. ファイル単位で判定できるのは、読み取りの可否、型、寸法である。チャンネル間の寸法の一致、4 チャンネルの上限、視野の合計の大きさは、登録だけが判定する（`stage: register`）。
4. 読み取りと理由コードの対応を、`upload_region_field` と共有する関数に切り出す。判定と登録で結果が分かれないことを試験で確かめる。

**変更箇所**

| 場所 | 変える点 |
|---|---|
| 新規 `cytellect_api/intake.py`、`cytellect_api/app.py`（経路の登録） | 変更 1〜3 |
| `cytellect_api/regions.py` の `upload_region_field` | 変更 4 |

**終わりの条件**　[§3](#3-issue-の項目と作業単位の分担) の W4 の範囲。入力 5 の入力（原画像 4、32-bit のマスク 1）で、`image` 4、`label` 1 を返す。判定の後、ワークスペースとファイルが増えていない。

**試験**　API：役割と理由コード（公開画像と、試験内で作成する破損した画像）、3 種類の振り分け、判定と登録の結果の一致、何も保存しないこと、上限と制限。

**文書**　`docs/generic-regions.md`、`docs/architecture.md`、`docs/security.md`。

**レビュー**　`/code-review medium`、`/security-review`（アップロードの受け入れ）。

### W5 画像から始める画面と取り込みの一覧

**変更**

1. 取り込みの一覧の状態（選択したファイル、判定の結果、縮小画像）を、ランタイムの `exclusive` の外に持つ（所見 9）。選択と判定は、登録や解析の処理中も受け付ける。登録（「追加」）は処理中は無効にする。
2. 視野と実験デザインのないワークスペースでは、W3 の案の開始の画面を表示する。ドロップは画面全体で受ける（既存の `dropFiles`）。
3. 選択のたびに、ファイルを判定の API（W4）へ送り、一覧に加える。行は、縮小画像、名前、チャンネル、状態（[§5.7](#57-状態の表示)）を持つ。先頭に内訳を 1 行で表示する（画像以外は拡張子で「対象外」）。
4. 組み分けは、一覧にある未登録の画像の全体に対して [§5.2](#52-取り込みの判定の順序) の順で行う。選択の回が異なっても、同じ視野の別染色は 1 つの視野にまとまる。登録済みの視野と同じ名前で内容の異なるファイルは、現在と同じく別の視野とし、行にその旨を表示する（所見 8）。登録済みの視野へのチャンネルの追加は扱わない（[§9](#9-残る制約と危険)）。
5. 「追加」は、ランタイムの `importFiles`（W1）で登録し、最初の視野を「画像」で開く。「追加して AI に聞く」は、追加に続けて AI の入力欄に移る（優先 3）。読み取れないファイルは、追加の時点で `rejected`（`stage: inspect`）の行として記録する。
6. W1 の「取込」の一覧をこの一覧に置き換える。登録できなかった行、`held`、`duplicates` も同じ一覧に表示する。画面下端の「取込 n 件」は、この一覧を開く。
7. 同一内容の行は、対応先を縮小画像つきで示す。名前の競合は、2 枚を名前と縮小画像で並べ、使用する 1 枚を選ばせる。ほかの行は追加できる。
8. 差し替えを、ファイル単位にする。判定の結果から、読み取れないファイルが分かるため、そのファイルだけを選択し直して行を再送する。
9. マスクの候補には、寸法が一致する視野を表示する。領域として使う操作は含めない。画像として登録された 8-bit・16-bit のマスクは、既存の「補助画像」の指定（`saveFieldLink`）で測定の対象から外せる。染色と生物学的な役割を推定しない。
10. 行ごとの取り消しと、直前の選択の取り消しを設ける。
11. 群のセルからの追加（実験デザインを先に作った場合）も同じ一覧を通し、追加先をあらかじめ入れる（原則 9）。
12. 追加の前の一覧の名前を、ワークスペースごとにブラウザの `sessionStorage` に保持する。再読み込み後は「再選択」の行として表示する（優先 7）。
13. フォルダーは、`webkitdirectory` の `input` とドロップの両方で、入れ子を含めて受ける。開発の起動時に限り、取り込みの診断をコンソールに出力する。内容は件数のみ（`change` の発火、`files.length`、相対パスの件数、一覧の件数）とする（入力 6 の切り分け手順 ②）。
14. `pending`、`ExperimentSetup.tsx` の保留のカード、「受け取った画像の追加先」を削除する。

**変更箇所**

| 場所 | 変える点 |
|---|---|
| 新規 `lib/workspace/intake-list.ts`（一覧の状態と判定の呼び出し）、新規 `review/EmptyStart.tsx`、`review/IntakeList.tsx` | 変更 1〜3、6〜10、12 |
| `review/panel-state.ts` の `experimentSetupShown` | 変更 2 |
| `review/ConnectedWorkspace.tsx` の `add`、開始画面の分岐、`dropFiles`、`intakeDisabled`、ファイルの `input`、「取込」の一覧 | 変更 2・5・6・13・14 |
| `review/ExperimentSetup.tsx` の実験デザインの選択、保留のカード、`pendingTarget`、`received` | 変更 11・14 |
| `lib/workspace/grouping.ts` の `groupFiles`、`lib/workspace/dropped-files.ts` | 変更 4・13 |

**終わりの条件**　[§3](#3-issue-の項目と作業単位の分担) の W5 の範囲。

**試験**

- 単体：内訳の合計、選択の回をまたぐ組み分け、同一内容と「別の撮影」、内容の異なる競合、取り消し、再読み込み後の「再選択」、処理中の選択。既存の `retains separate file identities…` は維持する。
- ブラウザ：入れ子のフォルダーの入力、ドロップ、4 枚＋1 枚、対照 A、内容の異なる競合、再読み込み。`workspace-form-first.spec.ts` を新しい流れに書き換える。
- `cytellect-screen-check`。

**文書**　`docs/requirements.md`（U01）、[群間比較の要件](../group-comparison/requirements.md)（E-01）、`docs/workspace-redesign.md`、`docs/web.md`、`docs/quickstart.ja.md`、`docs/install-windows.ja.md`、`docs/usability-tasks.ja.md`、`docs/security.md`（ブラウザに保持する名前）。

**レビュー**　`frontend-design`、`design:ux-copy`、`cytellect-screen-check`、`/code-review medium`。

### W6 群と実験回の割付

**変更**

1. 「実験」の既存の節「群・実験回が未割り当ての視野」（視野ごとの選択欄）を、表に改める。行は視野（縮小画像、名前、チャンネル）、列は実験回と群とする。複数の行を選択し、割付先を選んで一括で割り付けられる。状態の印、実数の図、「統計で比べる →」は変えない。
2. 割付の案を、定めた規則だけで作る。案は「視野、実験回の名前、群の名前」の組とし、W7 の指示による案と同じ形にする。
   - フォルダーの相対パスがある場合（フォルダーの入力とドロップ。所見 12）：階層から作る（例：`Rep1/未処理` → 実験回 Rep1、群 未処理）。相対パスは行の `intake.names` から読む。
   - ファイルの選択で名前だけの場合：名前のトークン（既存の `candidates`）から作れる範囲に限る。
3. 案は確定前の表示とし、「案を適用」の操作まで保存しない。適用は、案にある実験回と群がなければ作り、視野を割り付ける。実験デザインがない場合は、案の群の数から「1 画面」「2 画面」を提示し、研究者が選んでから適用する。
4. 案を作れない行は空欄とし、その行だけ入力を求める。
5. 番号だけのチャンネル（C01、C02）から、染色と生物学的な役割を決めない。

案の提示は確定ではなく、E-04、I11、U02 に反しない。

**変更箇所**

| 場所 | 変える点 |
|---|---|
| 新規 `review/UnassignedFields.tsx`、`review/ExperimentSetup.tsx` | 変更 1・3・4 |
| `lib/workspace/experiment-design.ts` の `assignFields` | 変更 1・3 |
| `lib/workspace/grouping.ts` の `candidates` | 変更 2 |

**終わりの条件**　[§3](#3-issue-の項目と作業単位の分担) の W6 の範囲。DS6a の `Rep1` のフォルダーをドロップした場合に、2 視野の案が「同じ実験回、未処理と ActD」になり、適用後に同じ実験回・2 群各 1 視野・各 3 チャンネルが残る。割付先を選ばずに、複数の視野が 1 つの群に入る経路がない。

**試験**　単体：案の規則（フォルダー、名前、案を作れない場合）、一括の割付、実験デザインのない場合の適用。ブラウザ：DS6a のフォルダー → 案 → 適用 → 再読み込み。

**文書**　[群間比較の要件](../group-comparison/requirements.md)（E-01、E-03）、`docs/web.md`、`docs/usability-tasks.ja.md`。

**レビュー**　`frontend-design`、`cytellect-screen-check`、`/code-review medium`。

### W7 AI の依頼の種類と割付の案

**変更**

1. 解析案に次を加える：`intent`（`answer`、`settings`、`run`）、`answer`（文章）、`scope`（`selected`、`all`）、`choices`（確認が要る項目と選択肢。核染色のチャンネル、群など）、`assignments`（割付の案。W6 と同じ「視野、実験回の名前、群の名前」の組）。
2. 表示は [§5.6](#56-ai-の応答と操作) の「W7 以降」のとおりにする。`choices` の選択肢を選ぶと、その内容を次の発言として送る（優先 8）。
3. `intent: answer` の検証は、設定の変更を含まないことを確かめる。質問への回答が検証で落ちない形を契約に定める（所見 14）。
4. `intent: run` の発言には、対象の視野（`scope`。対象外にした視野と登録できなかった行を除く）を示し、「適用して実行」を置く。実行は候補の作成までで、採用は研究者が行う。
5. `assignments` は、登録済みの視野に対して検証し、W6 の表に案として表示する。保存は研究者の「案を適用」による。
6. 割付の案に要る文脈を加える：視野を指す識別子、フォルダーの相対パス、実験デザインの実験回と群の名前（所見 18）。文脈の契約の版を上げる。送信範囲が広がるため、`SECURITY.md` とプライバシーポリシーの送信範囲を改め、送信の同意の全文を 1 回示し直す（既存の仕組み）。
7. プロンプトと解析案の契約の版を上げる。配布済みの版の依頼には、従来の版で応答する。

**変更箇所**

| 場所 | 変える点 |
|---|---|
| `packages/analysis/src/cytellect_analysis/proposal_contracts.py` の `ProposalDraft`・`ContextField`、`proposal_validation.py` の `validate_draft` | 変更 1・3・5・6 |
| `cytellect_api/proposals.py` | 文脈の組み立て、契約の版 |
| `services/proposal-worker/src/` の `openai.ts`・`anthropic.ts`（プロンプト）、`schema.ts`・`contract.json`、`index.ts`（版の扱い） | 変更 6・7 |
| `lib/workspace/use-workspace-runtime.ts`、`review/AssistantPanel.tsx`、`review/UnassignedFields.tsx`、`lib/workspace/ai-settings.ts`（送信範囲の文） | 変更 2・4・5・6 |

**終わりの条件**　[§3](#3-issue-の項目と作業単位の分担) の W7 の範囲。どの `intent` でも、研究者が操作するまで解析のジョブと設定の変更が 0 件である。

**試験**

- 解析と API：偽の提供元による `answer`、`settings`、`run`、`choices`、`assignments`、形の誤り、チャンネルの不一致。
- 単体：すべての `intent` で、応答だけでは解析のジョブと設定の変更が 0 件。
- 中継：契約とプロンプトの版、新しい文脈。
- モデルによる評価は公開画像の事例で行う（有料。オーナーの許可が要る）。観点は、質問に `answer` で答える割合と、回答の内容（チャンネル、根拠、必要な確認）。

**文書**　`docs/requirements.md`（「LLM」の節の L01、L02、L03）、`docs/proposal-service.md`、`docs/proposal-deployment.md`、[LLM による解析支援の見直し](../llm-assistant/plan.md)、`SECURITY.md`、プライバシーポリシー。

**レビュー**　`claude-api`、`/code-review medium`、`/security-review`（送信範囲）。

**順序**　中継のデプロイが、この作業単位の `main` へのマージより先である（[§7](#7-順序と配布)）。

対話と道具による研究アシスタント（[見直し案の段階 2](../llm-assistant/plan.md#5-進め方)）は別の計画とする。W2 の会話の表と、この作業の `intent` は、段階 2 でも使用する。

### W8 視野ごとの進捗

**変更**

1. 実行のステップ（`field_id`、`target`、`state`）から視野ごとの状態（[§5.7](#57-状態の表示)）を導出し、視野の一覧に表示する。採用前の候補がある視野は「候補を確認」、採用の処理中は「採用中」とする。一覧と画像の表示を同じ状態から描画する。
2. ヘッダーの進捗は視野を単位とする（例：「視野 1/2：核小体を検出中」）。ステップ数を表示する場合は単位を付ける。
3. 設定の変更の直後と「測定」の操作の直後から、対象の視野に「準備中」を表示する。
4. 進捗の取得中の通信の失敗では、直ちに失敗としない。解析は API 側で継続するため、間隔を空けて再取得する。その間は、ヘッダーに「接続を確認中」と、保存済みの視野、再試行の対象を表示する。同じ依頼は既存の `request_id` により重複して起動しない。
5. 1 視野の失敗で残りを止めない。実行に失敗した視野がある場合は、失敗した視野を除いた同じ実行を出し直し、成功した視野を採用する。成功済みのステップは再利用され、再計算されない（所見 19）。失敗した視野には「失敗」と「再試行」を表示する。

**変更箇所**

| 場所 | 変える点 |
|---|---|
| `lib/workspace/use-workspace-runtime.ts` の `runServer`、`readCandidates`、`recoverRun` | 変更 1・4・5 |
| `lib/workspace/api-adapter.ts` の `waitWorkspaceRun` | 変更 4 |
| `review/ConnectedWorkspace.tsx` の視野の一覧、ヘッダーの状態、`queuePreview`・`previewNow` | 変更 1〜3 |

**終わりの条件**　測定中の「次の追試と合格条件」。

**試験**　単体：ステップから視野の状態の導出（`reused`、`blocked`、`background_pending` を含む）、再取得、重複して起動しないこと、失敗した視野を除いた採用。ブラウザ：2 視野の核小体の測定。`cytellect-screen-check`。

**文書**　`docs/web.md`。　**レビュー**　`/code-review medium`、`cytellect-screen-check`。

### W9 接続の区別、再接続、停止理由の記録

**変更**

1. 失敗を 3 種類に分け、それぞれの案内を表示する。

   | 失敗 | 判定 | 表示と処理 |
   |---|---|---|
   | 応答なし | `fetch` の失敗 | 「ローカルのサービスに接続できません」と「再接続」。間隔を空けて自動でも確認する。ランチャーの開き方を 1 行で示す |
   | セッション切れ | 401 `session_required` | `POST /v1/local/session` でセッションを作り直し、同じ要求を 1 回再試行する（所見 21） |
   | 開き方の誤り | 403 `local_origin_required` | デスクトップの「Cytellect」から開く案内 |

2. 再接続の後、`refresh` で票と視野を読み直す。視野のある行は「登録済み」、`pending` のままの行は「再選択」として名前を表示する（W1 の表示と同じ）。追加先の適用（W1）がここでも働く。登録は同じ `id` で冪等である。
3. W8 の「接続を確認中」を、1 の案内に置き換える（W8 が先に入っている場合）。
4. サービスの停止経路（ランチャーを閉じる、更新の切り替え、ワーカーの停止、ワーカーの起動失敗、親プロセスの消失、未処理の例外）で、理由コードと時刻を PC のデータフォルダーに記録する。プロセスが強制的に終了された場合は記録を書けないため、起動時に「前回の正常な終了の記録がない」ことを異常な停止として扱う。次の起動時、前回が異常な停止であれば、ランチャーと解析の画面に 1 行で知らせる。
5. 停止の経路そのもの（ワーカーの再起動の上限など）は変えない（[§4.3](#43-原因を特定できていない項目)）。

**変更箇所**

| 場所 | 変える点 |
|---|---|
| `apps/web/src/lib/api.ts` の `request`、`session_required` の文言 | 変更 1 |
| `lib/workspace/use-workspace-runtime.ts` の `message`、`reload` | 変更 1〜3 |
| `review/ConnectedWorkspace.tsx` のエラー表示と「再読み込み」 | 変更 1〜3 |
| `cytellect_api/local.py` の `WorkerSupervisor.start`、`run_local`、`_gui`、`main` | 変更 4 |

**終わりの条件**　巻き込みの判定の「接続断の追試は『未送信・送信後の応答消失・再接続・401・403』を分け、再接続時に既存の登録結果を照合する」。取り込みの途中でサービスを停止して再起動した後、登録済みの視野が重複せず、残りの行が名前つきで表示される。停止理由が記録され、次の起動で表示される。記録に研究データを含まない。

**試験**

- 単体：3 種類の判定、再試行、読み直し。未送信、送信後の応答消失、再接続、401、403 を個別に通す。
- API：停止経路ごとの理由の記録と、記録のない終了の扱い（`tests/test_local.py`）。
- Windows の統合試験（`windows-installer`）は PR では走らない（所見 25）。マージの前に `ci.yml` を手動で起動して確かめる。

**文書**　`docs/local.md`（停止と再開）、`docs/install-windows.ja.md`、`docs/web.md`。

**レビュー**　`/code-review medium`、`/security-review`（セッション）。

### W10 更新案内

**変更**

1. API の更新の状態（`GET /v1/app/update`）に、ランチャーの起動ごとに変わる識別子を加える。
2. 通常の案内に「後で」を加える。操作後は、同じ起動の間は表示しない（1 の識別子で判定する）。
3. 操作の直後から、同じ場所に段階を表示する：受付、ダウンロード中、インストール中、再起動中、完了。
4. 結果を表示しない 2 つの分岐（所見 22）に、1 行の結果を表示する：「新しい版はありません」、「この PC ではアプリ内から更新できません」と代替の手順。
5. 解析中の操作では「解析が終わってから更新してください」を表示し、解析を止めない（現在の動作）。二重の操作と別タブで進行中の場合は、進行中の更新の段階を表示する。更新後の再開先を表示する（優先 11）。
6. 失敗の段階を記録する。`run_installer` は段階（起動、タイムアウト、終了）と終了コードを返す。失敗コードを `update_installer_launch_failed`、`update_installer_timeout`、`update_install_failed`（終了コード付き）に分け、状態の記録に `stage` と `exit_code` を残す。インストーラーのログは PC の更新フォルダーに保存し、外部へ送らない。
7. Microsoft Store の版での案内の表示条件を、コードと試験で確かめる。Store が更新を担う版では、この案内を表示しないか、Store への案内だけを表示する。

**変更箇所**

| 場所 | 変える点 |
|---|---|
| `cytellect_api/app_update.py` の `UpdateService.status`、`run_installer`、`UpdateService._run`、状態の記録 | 変更 1・6 |
| `apps/web/src/components/workspace/CloudAccount.tsx` の `UpdateBanner`（`applyUpdate`） | 変更 2〜5・7 |
| `apps/web/src/lib/cloud-account.ts` の `updateNotice`、文言 | 変更 3・4 |

**終わりの条件**　更新の「次の追試と合格条件」（「後で」、解析中、二重クリック、別タブで進行中、起動拒否、タイムアウト、非ゼロ終了を個別に通す）。

**試験**　単体：`updateNotice` と `UpdateBanner` の分岐、「後で」。API：`run_installer` の 3 種類の失敗、状態の記録（`tests/test_app_update.py`）。Windows の統合試験（`packaging/windows/smoke.ps1`）に失敗の段階を加え、マージの前に `ci.yml` を手動で起動して確かめる（所見 25）。

**文書**　`docs/local.md`（更新）、`docs/install-windows.ja.md`、`docs/release-signing.md`。

**レビュー**　`/code-review medium`、`/security-review`（更新）。

### W11 Windows の実機での受入

開発環境の試験の合格を、実機の合格として報告しない。配布の workflow は `main` のコミットだけを受け付ける（所見 25）ため、実機での受入は、作業単位を含む版の配布の後に行う。配布のたびに、その版に含まれる作業単位の項目を、Issue と同じ環境（インストール版、Edge）で確かめる。主導線である Microsoft Store の版（#286）でも同じ項目を確かめる。入力は Issue の「入力の用意と再現の約束」の公開画像とする。

| 作業単位 | 実機で確かめる項目 |
|---|---|
| W1 | 対照 A・B・C、巻き込みの判定、受入 3（いずれも [§3](#3-issue-の項目と作業単位の分担) の W1 の範囲）。再起動後に、群の内容と、登録できなかった画像の名前が保持されること |
| W2 | 追試 A・B、判定 1（測定ジョブ 0・設定変更 0）、判定 3・4。再起動後に会話が保持されること |
| W4、W5 | 入力 1・2・3・5、受入 1・4。フォルダー：Edge の通常のピッカーで、原画像のサブフォルダー（4 件）と親フォルダー（10 件）の選択、取り消し、確定。同じ 2 つのドラッグ＆ドロップ |
| W6 | 入力 4（表による割付と、フォルダーからの案） |
| W7 | 判定 1 の回答の内容、判定 2、受入 5、指示による割付（受入 2） |
| W8 | 測定中 |
| W9 | 復旧。取り込みの途中でランチャーを閉じて再起動する。再起動前から開いていたタブで操作する |
| W10 | 更新の 7 場面。アプリ内更新が成功すること |

**終わりの条件**　受入の記録（`docs/local-release-<版>.md`）に、合格、失敗、未実施を分けて記載する。失敗した項目は、原因を特定して該当する作業単位の修正として扱う。受入 1 の研究者による評価（迷って戻った箇所と支援の回数）は、未完了の受入条件として [roadmap](../../roadmap.md) で追跡する。

## 7. 順序と配布

### 順序

```text
W1 ──┬──────────────► W5 ──► W6 ──┐
     └──► W9          ▲           ├──► W7
W3 ───────────────────┤           │
W4 ───────────────────┘           │
W2 ───────────────────────────────┘
W8、W10（依存なし）
```

| 段 | 作業単位 | 止まる症状 |
|---|---|---|
| 1 | W1、W2 | 索引の最優先 5 行。5 行目（質問に形式エラー）は、回答が失われる症状と理由の不明を W2 で止める。回答の内容の改善は W7 |
| 2 | W3、W4、W5、W6、W8、W9、W10 | 入力 1〜6、測定中、復旧、更新 |
| 3 | W7 | 判定 1・2 の回答の内容、確認が要る項目の選択肢、指示による割付 |

- 最初に W1 と W2 に着手する。W3、W4、W8、W10 も依存がなく、並行できる。
- 段は着手の優先順位を示す。`main` へのマージは作業単位ごとに行い、段の完了を待たない。
- `ConnectedWorkspace.tsx` は W1、W2、W5、W6、W8、W9 が変更する。並行する場合は担当を分け、後から取り込む側が `main` を取り込んで合わせる。W2 は AI のパネルを、W5 は取り込みを別の部品に分離し、同じ行の変更を減らす。

### 配布との関係

`main` への push は、設定が有効な場合に、EXE の自動配布と Microsoft Store への提出を起動する（所見 25）。そのため、次を守る。

- 各作業単位は、単独で `main` に入れても配布できる状態にする。途中の状態を `main` に入れない。
- 依存する作業単位は、依存先が `main` に入った後にマージする（依存の表）。
- W7 は、中継のデプロイの後に `main` へマージする（[順序](../../proposal-deployment.md#order-of-worker-and-client-releases)）。
- Windows の統合試験は PR では走らない。Windows に関わる作業単位（W9、W10）は、マージの前に `ci.yml` を手動で起動して確かめる。ほかの作業単位は、既存の規則どおり、`main` への取り込み後の統合試験の成功を確かめる（[CI の構成](../../ci.md)）。
- 実機での受入（W11）は配布の後に行う。

各作業単位は、[CLAUDE.md](../../../CLAUDE.md#目的別のスキル) の表に該当するスキルを使い、`cytellect-verify`、画面を変えた場合は `cytellect-screen-check` の後に、`cytellect-pr` で PR を作成する。

## 8. 公開デモへの影響

公開デモは、API と解析パッケージをホイールにして Pyodide で動かし、開いたときの GET を限定する（所見 24）。API または解析パッケージを変える作業単位（W1、W2、W4、W7）は、ホイールを古くする。CI は警告を出すが、失敗にはしない。ホイールと記録の作り直しは、オーナーの許可が要る。

| 作業単位 | 開いたときの要求 | デモでの扱い |
|---|---|---|
| W1 | 増えない（票の GET は既存） | デモは画像を追加しないため、動作は変わらない。「n の内訳」の源（`GET …/workspace-selection`）は、記録にない場合は表示を省く |
| W2 | 発言の一覧の GET が増える | デモでは呼ばない。例の選択は現在と同じ要求の列にし、記録済みの応答（現在の形）を読む。記録は変えない |
| W4、W5、W6 | 増えない | デモは画像の追加を受け付けないため、開始の画面と取り込みの一覧は表示しない |
| W7 | 増えない | 記録済みの解析案は従来の版として読む。新しい版の例を加える場合は、記録の作り直しが要る |
| W8 | 増えない | 記録した実行の進捗の表示が変わる。`showcase.spec.ts` で確かめる |

W9、W10 はローカルの配布だけに関わり、デモには影響しない。

## 9. 残る制約と危険

| 制約・危険 | 対応 |
|---|---|
| 登録済みの視野へ、後からチャンネルを追加できない（視野は作成後に構成を変えない）。入力 3 が挙げる「2 回目のファイルが同じ視野の追加染色」は、追加の前に限って 1 つの視野にまとまる | W5 の一覧で、登録済みの視野と同じ名前のファイルにその旨を表示する。視野の作り直しは範囲外とする |
| マスクと判定できるのは 32-bit 整数の画像だけである | 8-bit・16-bit のマスクは画像として登録される。既存の「補助画像」の指定で対象から外す（W5） |
| 再読み込みで、追加の前のファイルの内容は失われる | 名前を保持し、「再選択」として示す（W5）。Issue の優先 7 が認める範囲 |
| 判定と登録で、内容を 2 回送る | PC 内の通信のため許容する（W4） |
| フォルダーからの割付の案は、フォルダーの入力とドロップでだけ作れる | ファイルの選択では、名前から作れる範囲と、表での割付になる（W6） |
| 票は 100 行までで、登録できなかった行も数に入る | 上限に達した項目は結果に返す。「追加をやめる」で行を削除できる（W1） |
| W1 の変更は、比較に含まれる視野と「n の内訳」に関わる。書き出しの Methods に、行の `intake`（ファイル名を含む）が出力される | 測定値と統計の計算は変更しない。契約試験と要件を同じ PR で改め、`/code-review high` を行う。ファイル名の出力は研究者自身の書き出しに限る |
| 決定 4 により、解析の依頼にも操作が 1 回要る | Issue の判定 1 を決定論的に守るための選択（[§2](#2-決定事項)） |
| W7 は送信範囲を広げ、中継の契約の版を上げる | 送信の同意を示し直す。版ごとに応答を分ける既存の仕組みを使い、中継を先にデプロイする |
| 画面の変更が、#258 と同様に却下される | #257 の作り直しの原則に従う。新しい画面は W3 で案を先に示し、既存の画面の修正は PR に変更前後の画像を付ける |
| 実機での受入が配布の後になる | 作業単位を単独で配布できる状態に保ち、失敗した項目は次の修正で扱う（W11）。Windows に関わる作業単位は、マージの前に統合試験を手動で起動する |
| 原因を特定できていない項目（[§4.3](#43-原因を特定できていない項目)）が、実装後も実機で再発する | 再発時は、W2・W9・W10 が保存する理由コードと停止理由から原因を特定する |
| 実機のアプリ内更新が失敗する場合、修正が届かない | W11 で更新を確かめる。失敗する場合はインストーラーまたは Store からの導入を案内する |

## 10. オーナーの許可が要る操作

[AGENTS.md](../../../AGENTS.md) の規則による。作業単位の実装と PR の作成には含まれない。

| 操作 | 関係する作業単位 |
|---|---|
| `main` へのマージ | 作業単位ごと |
| AI の中継のデプロイ | W7 |
| 有料の API の呼び出し（モデルによる評価、形式エラーの理由コードの確認） | W2、W7 |
| Windows 版の配布、Microsoft Store への提出 | W11 の前 |
| 公開デモのホイールと記録の作り直し | W1・W2・W4・W7 のホイールの更新 |

## 11. Issue の解釈

Issue の記述だけでは実装が一意に決まらない点について、この文書の解釈を定める。実装と試験はこの解釈に従う。いずれも Issue の「達成したい体験」に沿う側を選んだ。

| | Issue の点 | この文書の解釈 |
|---|---|---|
| 1 | 対照 B の競合ファイルは、a9-C01 と同じ内容の改名コピーである。対照 A の合格条件（同じ内容は 1 つにまとめる）を先に適用すると、対照 B の「競合 2 枚を提示する」場面は起きない | 同一内容を先に判定する（[§5.2](#52-取り込みの判定の順序)）。対照 B の入力は 2 視野になり、復旧の手順を要しない。競合の提示は、内容の異なる競合の入力で試験する |
| 2 | 追試 A・B と受入 5 は、AI が使える状態（ログイン済み、有効）で行われた。初めて開いた研究者は、AI を有効にしていない場合がある | AI が使える状態を、追試 A・B と受入 5 の前提とする。AI が使えない場合も、画像の事実を表示し、有効にする方法を示す（W2） |
| 3 | 優先順位の記述が 3 つある（冒頭の「最初に追う 3 件」、索引の最優先 5 行、「優先して直したい操作」1〜11） | 実装の順序は索引に従う（段 1 が最優先 5 行）。「優先して直したい操作」は、目指す操作の一覧として [§3](#3-issue-の項目と作業単位の分担) で作業単位に割り当てた |
| 4 | 入力のファイル名（`BBBC007-a9-C01.tif` など）は、リポジトリの登録名（`a9-dna.tif` など）と異なる | 試験は、登録済みの公開画像を Issue の名前で複製して使う（下の表）。名前が組み分けを決めるため、Issue の名前を保つ |
| 5 | 人による判定を含む合格条件がある（入力 1・受入 1「説明書なしで進める」、受入 6「状態と次の操作を指させる」） | 作業単位の終わりの条件は、自動の試験と画面の確認で確かめられる範囲とする。研究者による評価は、未完了の受入条件として [roadmap](../../roadmap.md) で追跡する |
| 6 | 判定 3 の「利用者が直せる項目とサービス側の修復を区別」は、区別の基準を示していない | 理由コードの対応表を W2 で作り、それを基準とする |
| 7 | 判定 1 は「測定ジョブ 0、設定変更 0…『まだ測らない』を守る」、判定 2 は「条件だけを変更した発言と、実行を依頼した発言…後者で正常視野を実行」、優先 8 は「対象と役割を短く示して実行へつなげる」と書く。モデルの判断で自動に実行すると、判定 1 を保証できない | 判定 1 を優先する。設定の変更と実行は、対象を示した 1 回の操作で行う（決定 4）。判定 2 と優先 8 は、依頼の種類に応じた操作を発言の下に示すことで満たす |
| 8 | 入力 4 は、6 枚を「一度だけ選び」、指示で割付の案を出すと書く。ファイルの選択ではフォルダーの情報が得られない（所見 12） | フォルダーからの案は、フォルダーの入力とドロップを対象とする。ファイルの選択では、名前からの案、表での割付、指示による案（W7）を使う |

**試験の入力**

| Issue の名前 | 作り方 |
|---|---|
| `BBBC007-a9-C01.tif`、`-C02.tif` | `scripts/prepare_workspace_bbbc007.py` が作る `a9-dna.tif`、`a9-actin.tif`（`a9-dna.tif` の SHA-256 は Issue の記載と一致する） |
| `BBBC007-f9620-C01.tif`、`-C02.tif` | `fixtures/public/bbbc007/manifest.json` の `f9620` の `dna`、`actin` を同じ手順で用意する |
| `BBBC007-a9-核の手動輪郭.tif` | `a9-dna.tif` と同じ寸法の 32-bit 整数のラベルの配列を、試験の中で TIFF に書き出す。判定は型と寸法だけで決まるため、合成の配列とし、試験名に明記する |
| `A01-DRAQ.tif`、`A01-GFP.tif` | `fixtures/public/bbbc013/A01-dapi.tif`、`A01-gfp.tif`（`A01-dapi.tif` の先頭 32 バイトの SHA-256 は、Issue の破損試料の記載と一致する） |
| `test-truncated-DRAQ.tif` | `A01-dapi.tif` の先頭 32 バイト。共有の開発環境の制限（`CYTELLECT_UPLOAD_ALLOWLIST`）が有効な場合は読み取りの前に拒否されるため、制限のない設定で試験する |
| `BBBC039-B02-視野09-Hoechst.tif`、DS6a の「視野01」の 6 枚 | `fixtures/public/bbbc039`、`fixtures/public/nucleolar` の登録済みの画像 |

ファイル名だけで結果が決まる経路の単体試験は、既存の試験と同じ最小のバイト列を使い、試験名に「合成」と明記する（[開発の原則](../../development-principles.md#研究データと検証)の条件 1〜4 に該当する）。

Issue の追試 A の画面のリンクは、本文（`…/9c0e7da0-…`）と末尾の画像（`…/9c79d0a0-…`）で異なる。画面 08 は末尾の画像を参照する。

## 12. 改訂の記録

すべて 2026-11-25。

| 改訂 | 内容 |
|---|---|
| 独立レビュー（1 回目） | 適用と実行を研究者の操作に限った（決定 4）。取り込みの記録を票の行の拡張にし、新しい表をやめた。判定の順序を定めた。受け取りの保存をやめ、保存しない判定の API にした。合格条件を作業単位ごとに分けた。調査の誤り（更新ボタンの語、セッションの作り直しの利用箇所）を訂正した |
| オーナーの指示 | #257 の統合後の `main` と照合した（[§4.4](#44-257-の統合との整合)）。確認待ちの事項をなくし、Issue の解釈（[§11](#11-issue-の解釈)）と試験の入力を確定した |
| 独立レビュー（2 回目。実装の順序） | 統合ブランチをやめ、作業単位ごとに `main` へ入れる進め方にした（Windows の統合試験と配布が `main` に限られるため。所見 25）。実機での受入を配布の後とし、項目を作業単位ごとにした（W11）。各作業単位の「変更」を実装の順に並べ替えた。W1：行の書き込みの順序と上限、行を持たない結果の表示、差し替えの関数、追加先の適用、「n の内訳」の源、マスクの候補の数え方を定めた。W2：文章を取り出す条件、発言を作る時点、一覧と更新の経路、復元の範囲、W2 の時点の操作を定めた。W4：ワークスペースに依存しない経路にし、振り分けを入力に取る。W5：一覧の状態を `exclusive` の外に置く。W6：案の形と、フォルダーの情報がある場合の範囲を定めた。W7：割付の案に要る文脈と送信範囲の変更を加えた。W8：失敗した視野を除いた採用を定め、W9 への依存をなくした。Methods と書き出しの作業単位（旧 W11）は、票がそのまま出力されるため不要とした |

この調査で実施していないこと：Windows の実機での確認、有料の API の呼び出し、画面の確認（画面を変更していない）、添付の ZIP の中身の確認。
