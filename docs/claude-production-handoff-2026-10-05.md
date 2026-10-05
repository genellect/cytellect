# Claude Codeへの引継ぎ：実API評価から本番公開まで

2026-10-05。Git上の引継ぎです。開発者PCのcheckoutやチャット履歴を必要な
コードの正本にしません。秘密情報と既存の評価費用台帳は、別途安全に引き継ぎます。

## 1. 着手するGitと担当範囲

| 項目 | 現在の状態・根拠 |
|---|---|
| repo | [genellect/cytellect](https://github.com/genellect/cytellect) |
| 続けるPR | [#32](https://github.com/genellect/cytellect/pull/32)、`codex/sol-workspace-integration` → `main` |
| 最後に全必須CIが通ったhead | `ccf01f6f7d7e454298ebd7bb6b81111c69e48b63`。[Verify 37299191396](https://github.com/genellect/cytellect/actions/runs/37299191396)：python、web、fiji-browser、local-windows、python-windows-314すべて成功 |
| その後のコード修正 | `c15a414e1e16e90c6d62bdac5154da716e3d7f1c`：比較グラフのカテゴリ余白、保存描画版によるexport/replay、関連テスト。変更後のCIは最新headで確認する |
| PR #29 / #30 / #31 | 統合済み。古い[Codex引継ぎ](codex-handoff-2026-10-05.md)の未統合手順は現在の実行順序に使わない |
| Web本番 | [cytellect.vercel.app](https://cytellect.vercel.app/)はmainから配信。PR #32のpreview成功はmain・本番更新の証拠ではない |
| Windows公開版 | `apps/web/src/lib/published-release.json`はlocal.11を指す。PR #32の新しい実装が配布済みとは扱わない |
| Worker / D1 | ソース・配置用スクリプトは実装済み。この引継ぎ時点で新しい本番リソース・migration・実API接続の受入は未実施 |

新しい作業環境で、次のように取得します。mainだけをcloneして着手しないでください。

```sh
git clone https://github.com/genellect/cytellect.git
cd cytellect
git switch --track origin/codex/sol-workspace-integration
git status --short
git rev-parse HEAD
git merge-base --is-ancestor c15a414e1e16e90c6d62bdac5154da716e3d7f1c HEAD
gh pr view 32 --repo genellect/cytellect --json state,headRefOid,baseRefName,isDraft
gh pr checks 32 --repo genellect/cytellect
```

Claudeへの開始指示はユーザーが行います。Codexのゴールは現在pausedです。
以前の「週次残り40%で停止」はユーザーが解除済みです。
ClaudeへCodexのゴール状態・認証・ローカルファイルは自動移行しません。
担当者を一人にし、同じPRへの並行書き込みを避けてください。

ユーザーの追加指定：OpenAIの認証と専用キー発行はCodexが担当し、キーを
非公開の実行環境へ設定した後、評価テスト・実装・本番公開をClaudeへ引き継ぎます。
ClaudeにOpenAI dashboardへの再ログインや別キーの作成を要求する構成にしません。

## 2. 最初に読む文書と変更対象

`CLAUDE.md` → [AGENTS](../AGENTS.md) → [要件](requirements.md)、
[解析法](methods.md)、[情報保護](security.md)を読みます。その後、
[UX仕様](workspace-redesign.md)、[今回の接続](sol-workspace-integration.md)、
[API仕様](proposal-service.md)、[Workerレビュー](sol-worker-review.md)、
[公開手順](proposal-deployment.md)、[ローカル配布](local.md)を必要な箇所だけ確認します。

| 責務 | 主な実装 |
|---|---|
| 実データの新ワークスペース | `apps/web/src/components/workspace/ApiWorkspace.tsx`、`apps/web/src/lib/workspace/api-adapter.ts` |
| 比較の操作と接続 | `WorkspaceComparison.tsx`、`apps/web/src/lib/workspace/comparison-adapter.ts` |
| 不変の比較対象作成 | `services/api/src/cytellect_api/region_cohorts.py`、[cohort契約](region-cohorts.md) |
| ローカル提案・同意・保存 | `services/api/src/cytellect_api/proposals.py`、schema0003 |
| モデル呼出し・予算・評価 | `services/proposal-worker/src/openai.ts`、`index.ts`、`evaluation-ledger.ts`、`public-evaluation.test.ts` |
| 統計・図・再実行 | `packages/analysis/src/cytellect_analysis/common_statistics*.py`、`region_exports.py` |

ファイル名は検索で確認してください。CoreApiWorkspaceという名前のファイルはありません。
LLMは手法提案だけを担当し、画素測定・統計値の計算は既存の決定論的coreが担当します。

## 3. 実装済み・確認済み・未完了

実装済み：実ファイルupload → 取得stainまたは明示的選択による核チャンネル →
実Fiji核検出 → 原画像座標のmask → 原値の面積・輝度 → 分布図・SVG/PDF/CSV。
削除・除外・Undo/Redoは解析版を更新します。背景未設定は補正値欠測として保持します。

比較UIはPR #32に追加済みです。群・試料・独立単位・対応・撮影日を設定し、
保存maskを再検出せずに不変cohortを作成し、reviewと実験上の確認後に
common-statistics v2へ進みます。メタデータは同じsource cohortで復元し、
人による確認を復元時に自動承認しません。

| 証拠 | 証明した範囲と限界 |
|---|---|
| BBBC007原TIFF・実Fiji・実ブラウザ | 115核・230チャンネル行。保存maskと原画素の独立計算に最大絶対誤差0。1核除外後114、SVG/PDF/CSV出力。核検出F1は未測定 |
| 4視野の合成画像・実Fiji/API/browser | 明示した2独立単位/群の比較、視野中央値、vector出力、メタデータ復元を確認。最初の実行は待ち時間上限に達し、完了済みの同じhashのfixtureに限定して再開した。生物学的な反復・利用者評価ではない |
| 描画修正c15a414 | 23テスト成功、Ruff・mypy成功。旧/新版それぞれのSVG/PDF等の再生成バイト一致、数値CSV・Methods不変。生成図目視確認。最新full CIは別の確認 |
| Docker worker afa9af6 | Git archiveから構築。UID10001、readonly root、network noneで実Fiji smoke成功：9核・18核小体候補、原画素不変。最新full-stack配布の受入ではない |
| Solのoffline検査 | provider/ledger/contract 43テスト、配置スクリプト4テスト等に記録あり。実モデルの有用性評価は未合格 |

### 残る製品接続

1. **OME入力**：既存serverの軸・寸法・bit深度・単一series検証を再利用する。
   UIでチャンネル一覧を取得し、一括mappingを提示する。ファイル名だけでstainを
   確定しない。未対応Z/Tや欠落planeを黙って補わない。
2. **核小体・背景・編集**：既存native NCL/GFP coreへ接続する。代表画像で
   条件・背景ROIを確認し、batchへ適用する。核修正後の子核小体を再確認対象にし、
   reshape/split/mergeでも原座標maskと不変版を保持する。
3. **提案採用**：現在の新UIはrationaleとmissing_informationを表示する。
   提案を採用して確定レシピへ反映する導線は未完了。取得チャンネル・対応する
   登録レシピ・source fingerprintをAPIで再検証し、採用条件・提案版を保存する。
   採用は独立反復・背景・領域reviewの自動承認にはしない。
4. **関連解析**：既存association coreを新UIへ接続する。X/Yを条件・独立単位で
   対応付け、欠落単位を隠さず、poolingは明示的な判断を求める。細胞数を独立nにしない。

一つのworkspaceという要件を維持し、upload前の長い実験情報入力に戻さないでください。
既存root画面やcoreに機能があることだけで、新UI接続完了と判定しません。

## 4. API設定と評価：公開より先に実施

製品モデルは`gpt-6.1-sol`。開発用Claudeモデルの変更と混同しません。
課金対象はOpenAIの**COMPASS組織内の独立したCytellectプロジェクト**です。
COMPASS Interactiveのキー・設定は変更しません。Personal側の評価キーは
残高のない課金先によるHTTP429 `insufficient_quota`で失敗しました。
組織全体の支払不足や実際のOwner権限不足が証明されたわけではありません。

安全なOpenAI widgetで、ユーザーは`Cytellect-public-evaluation`、COMPASS →
Cytellect、`expires_in_seconds=604800`を選択しました。Codexが専用キーを発行し、
承認済みのignored env-fileへ保存済みです。無料のモデル情報取得がHTTP200で
`gpt-6.1-sol`への認証を確認しました。これはResponsesの実生成・課金枠・提案品質の
受入ではありません。それらはClaudeの承認済み評価で確認します。
このPCのClaude Codeへ引き継ぐため、再ログインや追加キー発行は不要です。
別の環境へ移すときは、安全なsecret入力・権限設定を使います。キーをGit・チャット・
PR・ログへ置かず、公開文書へ非公開resource IDも転記しません。

認証の引継ぎには、Gitではなく実行環境のsecretとして`OPENAI_API_KEY`を設定します。
同じPCのClaude Codeなら承認済みのignored env-fileを利用でき、別のCloud環境なら
その環境の保護されたsecret設定へ注入します。公開repoのforkやPRには渡しません。
キーを読んで表示する操作や、プロンプト本文・コマンド引数への埋込みは行いません。
評価コマンドは環境変数から読みます。`eval:public`はrepoルートの`.env.local`を
自動読込みしないため、保護されたlauncherでenvを注入するか、operator環境で
Nodeの`--env-file`を使ってテストを起動します。CIの標準検査には有料キーを設定しません。
有効期限は7日です。引継ぎに鍵の値は記載せず、設定完了・安全な環境名・期限・
接続確認結果だけを記録します。失効時の更新は同じ専用projectで行います。

承認済みは**全試行の累積評価5 USDまで**。本番の継続課金は未承認です。
既存の外部SQLite評価台帳には、未知の請求に備えたholdが合計**0.43363 USD**
残っています。これは確認済み支出ではありません。新環境には、停止中の
既存台帳を安全に移して同じapprovalを継続します。GitにはDBを含めません。
新規台帳を初期化して5 USDを復活させる操作はしません。台帳が手元にない間は
有料評価を止め、no-charge検査を続けます。同時に別環境で有料評価を実行しません。

Linuxのfresh cloneでの検査例：

```sh
uv sync --locked --dev
pnpm install --frozen-lockfile
pnpm --filter @cytellect/proposal-worker check
pnpm --filter @cytellect/proposal-worker test
pnpm --filter @cytellect/proposal-worker test:deployment
uv run python scripts/check_docs.py
uv run python scripts/check_public_tree.py
```

有料評価はCIでは実行できません。承認済みのoperator環境でキーをsecretとして
注入し、次の値を設定します。

```sh
export CYTELLECT_ALLOW_PAID_PUBLIC_EVAL=true
export CYTELLECT_PUBLIC_EVAL_BUDGET_USD=5
export CYTELLECT_PUBLIC_EVAL_REPEATS=1
export CYTELLECT_PUBLIC_EVAL_EFFORT=medium
# 保護された既存台帳の絶対パスをCYTELLECT_PUBLIC_EVAL_LEDGERへ設定する。
pnpm --filter @cytellect/proposal-worker eval:public
```

12登録シナリオ、Python意味検証、期待する用途適合、usage、遅延、拒否理由を確認する。
原値・統計値をモデルに計算させない。全rejectを成功と数えず、期待値を弱めて
合格させない。現在の評価はmetadata中心で、実画像入力能力の評価を代替しません。
公開画像入力の追加評価も同じ累積予算を使い、採用したpreviewだけで確認します。
無効な予算、同意なし、未知stain、サービス不調時もローカル解析は継続できることを確認します。

## 5. 公開する順番と合格条件

### A. PRをレビューしてmainへ統合

最新headの5必須checkを確認。未解決の失敗をskipに変更しない。
意味・数値・保護の修正には、対応版と参照テストを付ける。
PRがdraftなら準備完了後にreadyへ変更。merge時は取得した40桁headに一致させる。

```sh
gh pr checks 32 --repo genellect/cytellect
gh pr view 32 --repo genellect/cytellect --json headRefOid,isDraft
gh pr ready 32 --repo genellect/cytellect
# SHAは直前に確認した40桁の実際のheadを使う。
gh pr merge 32 --repo genellect/cytellect --squash --match-head-commit HEAD_SHA
```

### B. Vercel

main更新 → 自動production deploy。配信SHA、READY、canonical `/`、`/plan`、
`/demo`、`/workspace`、`/workspace?demo=bbbc013`をDesktop/Mobileで確認する。
標準Vercel版は画像解析serverを持たず、localhostへ暗黙接続しません。
実解析の受入はAPI設定版・Windows・Dockerで確認します。従来root workspaceの
新UI置換は、ユーザーの操作確認後に行います。LPの再設計は本引継ぎで追加しません。

### C. Worker/D1

[配置手順](proposal-deployment.md)の順で、既存Cloudflare accountを`whoami`で
確認し、専用DBを選ぶ。ログイン済みという過去の記録だけで権限を確定しない。
`0001_init.sql`と`0002_usage_integrity.sql`の両migration、invitation/device権限、
idempotency、未知請求hold、月額・端末上限を確認する。
まず月額0・端末枠0、OpenAI secretなしの構成でdeployし、無認証401・認証あり503を
確認する。モデル呼出しを有効にする前に、評価結果と具体的な月額・端末枠を
ユーザーへ提示し承認を得る。評価5 USDの承認を本番月額に読み替えない。
APIからrelayへpublic contextを送り、返却・ローカル意味検証・保存・採用・確定
レシピまで実行する。HTTP200や健康状態確認だけで連携受入完了にしない。

### D. Windows配布

最新mainの5check成功後、[local-release workflow](../.github/workflows/local-release.yml)
をuniqueな未使用`0.1.0-local.N`でdispatchする。既存版を上書きしない。
fresh/repeat install、Fiji重複保存の抑制、起動/終了、installed numerical/replay、
24既定browser casesを実物ZIPで確認する。**現在の24件だけでは新/workspaceの
全経路を証明しない**。新UIの公開原画像検出・編集・出力と比較・提案採用も
installed copyに接続し、必要な受入件数/receiptを更新してから配布する。
開発Pythonやsimulated adapterへのfallbackを認めない。

```sh
gh release list --repo genellect/cytellect
gh workflow run local-release.yml --repo genellect/cytellect --ref main -f version=UNUSED_VERSION
```

draft prereleaseの実物・checksum・source SHA・受入receiptをレビューしてから公開し、
`published-release.json`と文書をPR/main/Vercel経由で更新する。canonical download
のbytes/hashを別途確認する。既知のintended-PC Smart App Control拒否は
CI合格だけで解決済みにしない。OS保護を無効化しない。

### E. Docker

最新のclean Git sourceからbuild。Web/API/worker全体で同じ画像→修正→比較→
SVG/PDF/CSV/Methods→replay→終了を実行する。UID10001、readonly root、private
volume、offline worker、APIだけのopt-in relay secretを確認する。
旧afa9af6のworker smokeだけで最新配布の合格にしない。

## 6. 完了の報告

source commit、PR、5check、Web production SHA/URL、Worker version/DB migrations、
Windows version/hash/installed receipts、Docker source/receiptを一つの記録にまとめる。
各項目を実際の証拠からpassed/failed/not-runで記載する。
[completion audit](completion-audit.md)と[roadmap](roadmap.md)の未達要件も照合する。

公開データの測定一致は検出F1や生物学的妥当性の証明ではありません。
M4の非公開画像による参照比較、M5の研究者による操作評価は引き続き別の未完了項目。
非公開研究データ・資料をClaude/CI/Gitへ取り込まず、私的な検証はその境界内で行います。
実装・CI・デプロイ・操作受入・科学的評価をそれぞれ報告してください。
