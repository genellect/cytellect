# ロードマップ

MVP（画像の登録から検出・修正・測定・統計・作図までの一連の機能、Windows 版、公開デモ）は完了しました。この文書は、これからの開発計画と、まだ満たしていない受入条件を管理します。MVP 期の実装記録とマイルストーン（M0–M5）は [MVP 期のロードマップ](archive/roadmap-mvp.md)に残しています。

## 現在の提供状況

| 対象 | 状況 |
|---|---|
| 公開サイト | [cytellect.app](https://cytellect.app/)。LP、`/demo`、`/plan` で構成する。`/demo` は本番と同じ解析ワークスペースを、登録済みの公開画像でサーバーレスに動かす（[公開デモ](showcase.md)）。解析エンジン（Fiji・StarDist・Cellpose）、有料 API（LLM）、画像の追加だけを止め、核ごとの表・区画への分配・陽性率を含むほかの画面は、記録した操作の結果で開く（2026-11-10、オーナーの判断）。統計・図・分類・背景補正の選択肢と、核小体の場面の核・核小体の削除は本番と同じ操作で記録から答え、自由に描いた輪郭や任意の数値・文字には案内を出す（2026-11-11、オーナーの判断）。画像の追加は Windows 版・Docker 版だけで行い、公開サイトは研究画像を受け付けない。公開サイトの `/workspace` は `/demo` へ転送する。`main` へのマージで自動デプロイ |
| Windows 版 | [0.1.0-local.20](local-release-0.1.0-local.20.md)。群間比較（2 画面、群と独立した実験回、結果の一文、実験回を n とする図）を含む最初の版で、インストールした版で公開 JUMP 画像の群間比較（C1）まで受入を通した（C11）。作業データは既定で削除操作まで保持。Cellpose はクラウド GPU（Modal）で実行する。GPU は L4 を優先し、空きがなければ A10 を使う。2026-10-29 の再デプロイ後、公開画像で A10 が CPU と同じラベルを返し（BBBC013 の 358 個、4DN NCL の切り出しの 9 個）、所要時間は BBBC013 で 22 秒、NCL の全視野（protocol 4.3.0）で 48 秒だった。L4 との比較と、画面での採用・測定は未実施（[クラウド GPU](cloud-gpu.ja.md)）。次の版に向けて、Python・依存パッケージ・Fiji を同梱した利用者単位のインストーラー（`Cytellect-Setup-<版>.exe`）と、アプリ内の更新を genellect/cytellect#155 で用意した。Windows の CI で、ネットワークなしの導入・再開・アンインストール・移行・アプリ内の更新と復帰を確かめた。2026-10-30 のオーナーの判断で、段階 0 は未署名のインストーラーで行い、Smart App Control で止められた場合は Microsoft Store での配布を先に試す（D4）。同梱物のライセンスは本文を同梱し、GPL などソースの提供が必要なものは、同梱した版ちょうどのソースを CI がリリースの資産 `Cytellect-<版>-gpl-sources.zip` として添付する（同日のオーナーの判断、[GPL などの対応するソース](oss.md#gpl-などの対応するソース)）。現在の固定では 215 個の対象のうち 173 個のソースを添付する。ソースを自動で取得できない 42 個（Azul Zulu の JDK、JavaFX・javacpp のネイティブ部品、Renjin、SNAPSHOT の `fiji` の jar、ライセンスを判定できない 25 個など）は、同日のオーナーの判断で同梱し、上流のソースの所在だけを記す（`engines/fiji/source-exceptions.json`）。研究室の実機（Smart App Control を含む）での確認は未実施（[ローカル配布](local.md)）。0.1.0-local.21 のインストール後の受入（run 41011390308）は、C1 の試験でブラウザのコンソールに 401 が記録されて失敗した。原因（招待で開いた試験のセッションを、クラウドのログインの経路が PC のセッションと認めない）と、開いたときの確認で 401 を出さない修正は `fix/jump-c1-console-401` の PR に記す。Windows での再実行は未実施 |
| Docker 版 | [Docker Desktop での利用](docker-desktop.md) |
| 解析提案（LLM） | 既定で無効。利用者が有効にした場合に限り動作し、月額の利用上限を設定した Worker で提供 |
| 開発環境 | 研究室の PC と同じ構成を Linux で起動し、公開画像で試せる（`scripts/dev.py serve`、[CONTRIBUTING](../CONTRIBUTING.md#ローカル開発)）。共有する開発環境では、登録済みの公開画像だけを受け付けられる（`CYTELLECT_UPLOAD_ALLOWLIST`、[データ保護](security.md#shared-development-environments)）。共有の起動と研究者による評価の計画は[実装計画（案）](drafts/cloud-development/plan.md)にある |
| CI とマージ | PR では変更したファイルに関係するジョブだけを実行し、最新の `main` を取り込んだ head で成功してからマージする（[CI の構成](ci.md)）。Windows のテスト一式は 4 つに分けて並列に実行する。画面の E2E は `fiji-browser` から `browser-e2e` に分け、PR でも実行し、失敗したテストのトレースを残す（必須チェックへの追加はオーナーの設定待ち）。次の段階は、公開デモのホイールをデプロイの中で作ること（PR の競合をなくす）、E2E の棚卸し（研究者の主要な道筋だけを E2E に残し、画面の関門の判定はコンポーネントのテストに移す）、必須チェックの 1 つへの集約（`ci-required`） |
| 核小体検出 | NCL の protocol 4.3.0（公式の `cpsam_v2` に、親核による条件付けと境界補正を組み合わせる）。Hugging Face の `ncl-r1-step0750`・`ncl-r1-step0375` を選択する経路を画面・CPU・GPU に追加。既定の公式モデルと既存クライアントの実行経路を保持する。[計算仕様](methods.md)、[モデルの構成と受入記録](segmentation-models.ja.md) |

## 今後の計画

Windows 実機での導入失敗への修正は genellect/cytellect#187 で進める。公開画像を使った実機試験で、Java 終了後の `tensorflow_jni.dll` の削除が共有違反32で失敗する不具合を再現した。レビューを受け、削除の保留で解析成功を取り消さず、所有記録から後で回収するよう変更した。実際の DLL を32秒間ロックした公開画像チェックは成功し、解放後の回収も確認した。回収待ちが1 GiB以上なら新たな展開を止める。旧版の失敗残骸は配布記録で所有を証明できる場合だけ回収し、別版の確認済み未登録試行と固定入力に一致する既存ランタイムを容量管理へ登録する。後片付けを項目ごとに独立させ、直近10回の診断履歴を保持する。初回の詳細ログがないため、当初の導入失敗との同一性は未確定。新しい head の Windows 導入・実機 Fiji の CI、正式版の公開と LP 更新、LP 経由の GUI 導入・起動・解析・保存の受入は未完了とする。

### 研究に必要なパラメータの拡張

[研究パラメータの拡張計画](drafts/research-measurements/plan.md)は Claude の設計レビューを反映し、2026-11-09 にオーナーが 4 方針を採用した計画。M0 で一般化した「問い→指標」、実験計画と層、新版 gate、共有契約と所有ファイルを固定する。M1 は既存 GFP ゲートを一般化した任意チャンネルの層別・陽性率、既存の比を保持する汎用分配、核面積・DNA 染色の積算・核小体形態を同じ核の行に持つ統合表を、比較・図・Methods・replay までつなぐ。4 チャンネル上限の拡張は含めない。

公開実画像での M1 と、ローカル研究者による原画像の棚卸し・独立評価集合の構築（M4a）は並行する。M1 は新しいモデルや追加学習の完成を待たず、採用済み領域から計算する。検証先は登録済みの DS6a 等の公開実画像とし、必要チャンネル・解像・対照が確認できる範囲に限る。既に開発に使ったデモを未知の final とは扱わない。

M2 は元画像での解像・対象同定・校正を開始条件とする。M3 は検証済み数値表を試料・実験回と関連付ける一機能に絞り、FRAP fit・バンド専用指標は別計画へ回す。M4b の学習・評価は原画像・対象別の完全注釈・独立 split・loader の採用条件がそろってから進める。速度と UI は必要な測定の正しさと確認・修正の負担を改善するために進め、UI への接続自体は M1 に含める。

層別の 2 群比較、新版 gate、M3 の範囲限定、M1 と M4a の並行はオーナーが採用済み。分担は機能ごとの縦割りで確定し、Claude が核ごとの統合表（核面積・核の染色の積算・各チャンネルの強度・確定した核小体の数・面積・形を同じ核の行に並べ、行から画像の核へ戻り、CSV で保存する）を genellect/cytellect#189 で実装する。Codex は任意チャンネルの陽性判定と陽性率、汎用の分配係数と、隔離ローカル環境での原画像の棚卸し（M4a）を担う。宣言した層ごとの 2 群比較（実験計画 1.1.0：1〜3 因子の水準の組み合わせによる層の宣言・各視野の所属・1 層だけの集合と、層をまたぐ合算の拒否）を genellect/cytellect#191 で実装した。新規学習・既定モデル変更は未開始。AGENTS.md の重点、既存の科学的受入条件、マージ・配布の判断は変更しない。非公開データは [ローカル専用](drafts/research-measurements/local-data.md) とし、公開 Git・CI・デモ・クラウド学習へ渡さない。開発用 AI が扱うのは、オーナーが指定した隔離ローカル環境に限る。実データの構成・配置・結果は公開文書へ記録しない。

### 1. 自研究室での実証

研究室の実画像で、検出精度・操作性・解析時間を評価し、核小体・細胞質のモデルを改良します。

- **モデル評価・学習の前に独立したテストデータを構築する。** 原画像を棚卸しし、学習・条件調整に使わない実験回の画像を評価専用に分けます。公開実画像での測定機能の開発（M1）とは並行します。独立評価集合がない状態で、モデルの精度比較や実証の合格を宣言しません。
- 正解には研究者が描いた輪郭を使い、2 名が独立に描いて正解自体の一致度も測ります。
- 指標は、再現率・適合率・F1（IoU ≥ 0.5）、融合・過分割の数、面積・輝度の誤差とし、実験回ごとに集計して信頼区間を付けます。

### 2. 北里大学の他研究室での実証

研究対象や撮影条件の異なる画像で検証します。あわせて、解析基盤をクラウド（AWS、Hugging Face、Modal）へ移し、完全な Web アプリ化を進めます。移行先の選定と費用はオーナーが判断します（[比較資料](hosting-costs.ja.md)）。

### 3. 他の研究機関への公開

解析コードはオープンソースで公開を続け、研究室単位のクラウドで収益を得ます。

### モデルと 3D・細胞内構造への展開

[解析モデルの選定と発展方針](segmentation-models.ja.md)に従い、核小体向け追加学習の成果を生かして 2D の対象・撮影条件を広げ、3D の核・細胞、細胞内構造・スポットへ展開する。

採用の判断には、実験回を分けた精度・測定誤差・修正時間の評価と、SaaS・再配布・追加学習ごとの権利記録をそろえる。ライセンスの調査結果と次の確認項目は [OSS 文書](oss.md#モデルの受入記録)に集約する。3D の受入は、原ボクセル・軸・単位の保持、断面編集、体積測定、版を指定した再現までを対象とする。

### 群間比較の UX 改善

対照と処理の群を、独立した実験回を n として、入力から図まで迷わず比べられるようにします。デモでは 2 群を並べ、出典の論文が報告する核の縮小・核数・核小体の変化を示します。目標・要件・開発体制は、Codex の独立レビューを反映し、2026-10-25 にオーナーが承認した。Claude Code（主担当）と Codex（補助）で実装し、genellect/cytellect#110 で `main` に入れた（公開サイトの `/demo` も 2 場面に替わる）。公開デモは 2 場面にする。核数の場面は JUMP Cell Painting（CC0）の PLK1 ノックアウトと対照（実験回 3）。核小体の場面は Zenodo 6643470（DS6a、CC BY 4.0）の未処理と ActD で、実験回の独立性は出典で確認できないため、検定はせずに実験回と群ごとの値を示す。核の縮小の場面は、条件を満たす公開データがないため公開しない。JUMP の実験回の独立性は出典で確認できないため、両場面の比較は検定なしの記述（共通統計の `test: "none"`）とする（2026-10-25、オーナーの判断）。2026-10-26 にオーナーが残る判断を決めた。DS6a は、論文の 2 つの報告を確かめ、合わない指標は画像に戻って定義の違いを確かめる例とする（C7）。N-03 の上限を決めた。核小体を確定できない核は、核を消さずに欠測として残す（Q-05、設計は genellect/cytellect#109）。方針 `unresolved-as-missing/1.0.0` は genellect/cytellect#111 で実装して #110 にまとめ、公開デモ（DS6a）を、断片を消さない新しい版で作り直した。同日のオーナーの見直しで、画像の画面は視野全体と測定値の表を中心にし（1 画面と同じ原則）、2 画面の 2 視野を同時に読むようにし、CellProfiler との照合の表示を外した（[要件定義書](drafts/group-comparison/requirements.md) V-01・V-04・N-08）。最終版の Codex のブラウザ試験と独立 UX レビュー（genellect/cytellect#110）を受け、核ごとの核小体の値を核小体で確かめるようにし、「n の内訳と除外」に確定できない核を数えた（V-04、Q-05）。図の選択肢・保存した表・スマートフォンの入口も直した（F-01、N-06、N-08）。Codex の再確認（d41271b5）で 5 件の解消を確かめ、残件（スマートフォンのメニューのはみ出し、保存した表の行が多いときの画面の遅さ）も直した。CI の Python のジョブが日本語フォントの取得の遅いミラーで打ち切られていたため、遅い取得を打ち切って別の公式ミラーで続けるようにした。N-03 は、プレビューでの判定ができておらず、本番サイトで測る。研究者による評価（C9・C10）と統合した Windows 版の受入（C11）は未実施（[目標定義書](drafts/group-comparison/goals.md)、[要件定義書](drafts/group-comparison/requirements.md)、[開発体制](drafts/group-comparison/development.md)）。

結果のまとめの先頭に、保存した推定値だけから作る結論の一行（向き・およその大きさ・実験回の揃い方）を置いた（2026-11-11、オーナーの指示、[要件定義書](drafts/group-comparison/requirements.md) S-01）。後続の要件（案）として、結果の生物学的な考察（何を示唆するか、既知の知見とどうつながるか、次に確かめること）を LLM に委ねる。考察は保存した結果と実験の記述だけを入力とし、計算した値とは分けて表示し、利用者が有効にした場合に限り月額の上限を設けた Worker で動かす（解析提案と同じ条件）。公開デモでは LLM を呼ばず、記録した考察だけを示す。要件・評価方法・費用の上限はオーナーの判断を待つ。

### 画像の測定ビュー

2026-11-11 のオーナーの指摘を受けた計画。本番もデモも、画像の画面から何ができるのかが分からない。核ごとの表・区画への分配・陽性率を加えても、画面はほとんど変わらなかった。画像の「色分け」（輪郭／陽性・陰性／核小体と核質）を測定の入口にし、表の見出しで何を測っているかを示し、次の一手を 1 つ置く。[要件定義書](drafts/image-measurement-view/requirements.md)と[実装案](drafts/image-measurement-view/implementation.md)は 2026-11-11 にオーナーが承認し、分配の向き（核質 ÷ 核小体）・「値の強さ」の色分けを加えない・核ごとの表を既定にする、の 3 点を決めた。ブランチ `feat/image-measurement-view` で実装した（genellect/cytellect#194・#195 を取り込んだ上に積む）。色分け、表の見出し、分配の統合、操作の整理、次の一手、判定の復元を入れ、要件 M24 に移した。研究者による評価（[操作評価課題](usability-tasks.ja.md)の課題 6、受入条件 C-09）は未実施。

### 結果の表現とデモの素材

統計の結果とデモの見せ方を見直す（2026-11-12、オーナーが方向性と 7 つの判断を承認。[要件定義書（案）](drafts/results-and-demo-story/requirements.md)、[実装案](drafts/results-and-demo-story/implementation.md)）。3 本の PR に分け、次の順でマージする。デモの記録を 1 回で済ませるため、全画面の文言（`claude/ui-copy`）は 3 に含める（2026-11-12、オーナーの判断）。

| 順 | PR・ブランチ | 内容 | 状態（2026-11-12） |
|---|---|---|---|
| 1 | genellect/cytellect#198 `claude/affectionate-knuth-vbir8l` | 結果の見出し・要点・根拠の 1 行、前提の 1 回の表示、デモを複数染色の核小体の場面から開く、UI の文言の規則（UC） | 統計画面の領域の同期を修正し、デモの記録を作り直し中 |
| 2 | genellect/cytellect#199 `claude/result-discussion` | 考察（LLM）の契約・検証・API・提案サービスの経路・画面の枠。有料の呼び出しはしない | #198 の取り込み待ち |
| 3 | `claude/demo-platinum-story` | オキサリプラチン・シスプラチンの場面、場面の概要（DM-11）、デモの考察のモック（AC-08）、全画面の文言（UC-01〜UC-07） | 4 場面でデモを作り直して PR |

1 が `main` に入ったら、2 の宛先を `main` に変え、`main` を取り込んで CI を通してからマージする。3 も同じ。取り込みで `apps/web/public/showcase/**` が衝突したら、後に積んだ側を採る。

#### 並行作業の分担

同じファイルを同時に変えないため、担当ごとに触れる範囲を決める（2026-11-12）。範囲の外を変える必要が出たら、変える前に、その範囲の担当の PR にコメントで知らせる。どの担当も、`main` へのマージ・デプロイ・有料 API の呼び出しをせず、他の担当のブランチを rebase・force-push しない。

段 1（上の 3 本を仕上げる間）：

| 担当 | ブランチ | 変えてよい範囲 | 変えない範囲 |
|---|---|---|---|
| Claude A（最初のセッション） | 1・2、`claude/ui-copy`（3 に取り込む文言の修正） | `apps/web/src/**`、`apps/web/tests/**`、`packages/analysis/src/cytellect_analysis/discussion_*`、`services/api/src/cytellect_api/discussions.py`、`services/proposal-worker/**`、`docs/requirements.md`、`docs/drafts/results-and-demo-story/**`、画面の文言を引用する文書。1・2 のブランチでは `apps/web/public/showcase/**` も（記録と実行環境の作り直し） | 3 のブランチの `services/showcase/**`・`apps/web/public/showcase/**` |
| Claude B（別のクラウドセッション） | 3 | `services/showcase/**`、`apps/web/public/showcase/**`、`apps/web/public/fonts/**`、`fixtures/public/allowlist.json`、`scripts/security-tools.lock.json`（フォントの記録の確認済みの値の追加だけ）、`docs/showcase.md` | `apps/web/src/**` と `apps/web/tests/**`（デモの作り直しで見つかった不具合は Claude A に知らせ、Claude A が `claude/ui-copy` で直す） |
| Codex | `main` から `codex/<topic>` | `.github/workflows/**`（Node.js 24 への対応、検出を手動で走らせる Actions）、`docs/drafts/gfp-scene/**`（GFP の場面の候補調査） | 上の 3 本の PR が触るすべてのファイル |

段 2（3 本が `main` に入った後。互いに重ならない 3 つを並行で進める）：

| 単位 | 担当 | 内容 | 主なファイル |
|---|---|---|---|
| 考察の画面の残り | Claude A | AC-02（有効かどうかを押す前に示す 1 行）、AC-03（設定画面での開示）、AC-06（「前の結果の考察」の表示と再生成）、試験 C-11・C-14・C-15 | `apps/web/src/components/workspace/review/DiscussionPanel.tsx`、`ProposalPanels.tsx`、`api-adapter.ts`、`services/api/src/cytellect_api/discussions.py`・`db.py` と試験 |
| 公開サイズの自動検査 | Claude A（genellect/cytellect#202、`main` から並行で作成済み） | DM-10：公開デモが 700 MiB を超えたら CI で止める（2 進で読む。2026-11-13、オーナーの判断） | `scripts/check_public_tree.py` と試験 |
| 文書の移し替え | Claude B | 要件定義書 §9 の移し替え（S-01・S-05・X-01・X-02・D-10 を群間比較の要件へ）、場面の順序の記述をそろえる、この節を完了の状態に更新する | `docs/drafts/group-comparison/requirements.md`、`docs/drafts/results-and-demo-story/requirements.md`、`docs/showcase.md`、この文書 |

段 3（オーナーの判断の後）：GFP の場面の登録（Claude B、[候補調査](https://github.com/genellect/cytellect/pull/201) の判断の後）、考察の本番での有効化（AC-09、デプロイ・有効化・有料の呼び出しの確認をそれぞれオーナーの許可を得て行う）。

### 評価する項目

モデルの検出精度、面積・輝度の測定誤差、手補正にかかる時間。

## 未完了の受入条件

| 項目 | 内容 |
|---|---|
| 非公開データでの検証 | 研究室の実画像による、検出と測定の生物学的な妥当性の確認 |
| 研究者による評価 | 複数の研究室の研究者による、作業の完了・時間・修正の負担・理解・再利用の評価（[評価タスク](usability-tasks.ja.md)） |
| Windows 版 | Cellpose は CPU では 1 視野に数十分かかり実用にならないため、推論をクラウド GPU（[設定](cloud-gpu.ja.md)）で行う。実 GPU での所要時間・費用と CPU との一致度の受入、Windows のセットアップ画面からの設定。別の PC で起きた Smart App Control によるブロックへの対応。CI の `windows-sac-audit` が、同じ規則の監査で止められるはずのファイルを一覧にする（2026-10-30 の初回は、ISG なしで 182 件、ISG ありで 129 件。Python のホイールのネイティブ部品、Fiji のプラグインが実行時に展開する DLL、Inno Setup、`uv.exe`。[CI](ci.md#smart-app-control-の監査)、[ローカル配布](local.md#ci-audit-of-smart-app-controls-rules)）。対処のうち Microsoft Store の MSIX は genellect/cytellect#174 で試作した（未マージ）。0.1.0-local.21 の公開後、公開されたインストーラーの SHA-256 を確かめてから、サイトのダウンロードの記録（`apps/web/src/lib/published-release.json`）を `"asset": "installer"` に切り替える（サイトは対応済み。[手順](../apps/web/README.md#windows-release-link)） |
| ホスト型の解析 | 公開 TLS とドメイン、利用者が不在の間の継続的な削除、運用サーバーの分離。研究画像をクラウドで受け付ける前に満たす |
| LP | 2026-10-23 にヒーロー映像（培養プレートから始まる実写の版）と本文（具体的な主張と解析例の実画面、「できること」4 つのタブ）をオーナーが承認した。患者へつながる将来性のカードは、既存の深緑の面に、研究から患者への 3 段階を細→太の線でつなぐ案を実装（Vercel プレビューでオーナーが線の版を選択）。PC・スマートフォンの画面でオーナーが判定することが受入条件（[美術方針](lp-art-direction.md#5-世界観と章立て)）。そのほかの残りは、ヒーロー映像の改良（Codex が担当、[美術方針](lp-art-direction.md) §9・§10）、研究室での撮影の可否、核小体の検出の前後比較の画像と研究室の利用者の声を公開してよいかの確認。2026-11-13 のオーナーの指摘（新機能との乖離、掲載画像が古い、デザインの水準）を受け、承認された実装方針に沿って、今のページを土台にページ全体を作り替えた版（検出と測定を最初に開くタブと、その横の Three.js の 3D 空間、実写）をブランチ `claude/festive-planck-86etrw` で実装した（[実装方針と実装](drafts/lp-renewal/implementation.md)）。プレビューでのオーナーの判定が受入条件 |
| 核ごとの表 | 保存した表（CSV・JSON）は 1 視野ごとで、列の染色名までを記録する。視野の表示名、群・実験回・条件を表に加え、複数の視野をまとめて保存できるようにする（[計画](drafts/research-measurements/plan.md) の M1「試料属性・条件・時点を保持」） |
| 今後の機能 | アカウント、チーム、長期保存、決済 |

検証の層と記録の方法は [validation.md](validation.md) に従います。CI の成功や公開した事実は、科学的な妥当性の証明にはなりません。

### 研究測定の実装と残る接続

核ごとの統合表は #189 の独立レビューで、未確定候補、核以外の入力、核小体側の視野除外、核側の視野除外理由を修正した。絶対面積と CSV を加え、登録公開 DS6a の各視野で採用ソースを解決して、原画素・保存マスクからの独立計算と照合するスクリプトを追加した。

Codex の `feat/research-m1` は、`channel-gate/1.0.0` と陽性数・陽性率を統計・図・Methods・保存の経路へ接続する。旧 GFP 経路は保持し、実験情報・核の正本・判定が変わったら digest の不一致で止める。陽性数・陽性率の比較は、判定チャンネルの輝度の結果として撮影日・dtype・群と撮影バッチの重なりを検査する。陰性対照で決めていないしきい値（手動・Otsu）では検定と信頼区間を出さず、記述だけにする。選別と測定が同じチャンネルのときは、警告と Methods に循環を記す（#190 のレビューを受けた修正）。対照の適切さと生物学的な陽性判定は、対応する公開対照と研究者による受入が残る。

同ブランチの `region-partition-table/1.0.0` は、元画素・親核・対象・参照・背景 ROI を拘束した読み取り専用の表と CSV、画像上の核への移動までを扱う。確認前の表は preview と表示し、正式統計の確認条件を緩めない。親核は採用した StarDist の核に限り、手描き・取り込みの核は受け付けない（[要件](requirements.md) M23）。分配の比較・編集可能な図・保存と replay、および区画内の飽和評価は未接続で、M1 全体の完了とはしない。層の宣言と層をまたぐ合算の拒否は genellect/cytellect#191 で、共通解析・API・worker・画面に実装した。層のない視野は、層を決めるか理由を付けて除外するまで集合を作らず、宣言した層の数を結果と Methods に残す（層の数に対する多重性は補正しない）。層の選択から結果までの画面の自動試験（ブラウザ）と、研究者による受入は未実施。

M4a の採用判定と詳しい記録は隔離ローカル領域に保持する。原画像・注釈・独立 split の採用条件を満たす前に M4b を始めない。新規学習・既定モデル変更・本番公開・配布は行っていない。


## Laboratory manual-retention implementation

A scoped source change adds explicit manual workspace retention with consistent
API/worker/UI behavior and a durable guard against returning the volume to TTL.
Default non-lab retention remains 24 hours. Metadata-only checks do not establish
installed browser behavior, image correctness or delivery readiness. Remaining:
independent source review, integrated PR/model selection, pinned Docker release,
quiesced DB/artifact backup/restore, hardware/resource confirmation, and fresh
real-input installation acceptance. No automatic merge/default-model switch or
production PoC is part of this change.


### 追加学習モデルの配布確認

- モデル選択と固定重みの照合を含む PR の必須 CI。
- GPU イメージの公開と digest の固定、Modal へのデプロイ、登録済み公開実画像での実行・モデル ID・既存クライアント互換の確認。
- Windows の新しい配布物で、モデルの選択・保存・再読込・標準モデルへの切戻しを確認。
- 独立した実験回での精度・測定誤差・修正時間の評価は、実行確認と区別して記録する。
