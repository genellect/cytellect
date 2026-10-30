# ロードマップ

MVP（画像の登録から検出・修正・測定・統計・作図までの一連の機能、Windows 版、公開デモ）は完了しました。この文書は、これからの開発計画と、まだ満たしていない受入条件を管理します。MVP 期の実装記録とマイルストーン（M0–M5）は [MVP 期のロードマップ](archive/roadmap-mvp.md)に残しています。

## 現在の提供状況

| 対象 | 状況 |
|---|---|
| 公開サイト | [cytellect.app](https://cytellect.app/)。LP、`/demo`、`/plan` で構成する。`/demo` は本番と同じ解析ワークスペースを、登録済みの公開画像でサーバーレスに動かす（[公開デモ](showcase.md)）。画像の追加は Windows 版・Docker 版だけで行い、公開サイトは研究画像を受け付けない。公開サイトの `/workspace` は `/demo` へ転送する。`main` へのマージで自動デプロイ |
| Windows 版 | [0.1.0-local.20](local-release-0.1.0-local.20.md)。群間比較（2 画面、群と独立した実験回、結果の一文、実験回を n とする図）を含む最初の版で、インストールした版で公開 JUMP 画像の群間比較（C1）まで受入を通した（C11）。作業データは既定で削除操作まで保持。Cellpose はクラウド GPU（Modal）で実行する。GPU は L4 を優先し、空きがなければ A10 を使う。2026-10-29 の再デプロイ後、公開画像で A10 が CPU と同じラベルを返し（BBBC013 の 358 個、4DN NCL の切り出しの 9 個）、所要時間は BBBC013 で 22 秒、NCL の全視野（protocol 4.3.0）で 48 秒だった。L4 との比較と、画面での採用・測定は未実施（[クラウド GPU](cloud-gpu.ja.md)）。次の版に向けて、Python・依存パッケージ・Fiji を同梱した利用者単位のインストーラー（`Cytellect-Setup-<版>.exe`）と、アプリ内の更新を genellect/cytellect#155 で用意した。Windows の CI で、ネットワークなしの導入・再開・アンインストール・移行・アプリ内の更新と復帰を確かめた。2026-10-30 のオーナーの判断で、段階 0 は未署名のインストーラーで行い、Smart App Control で止められた場合は Microsoft Store での配布を先に試す（D4）。同梱物のライセンスは本文を同梱し、GPL などソースの提供が必要なものは、同梱した版ちょうどのソースを CI がリリースの資産 `Cytellect-<版>-gpl-sources.zip` として添付する（同日のオーナーの判断、[GPL などの対応するソース](oss.md#gpl-などの対応するソース)）。現在の固定では 215 個の対象のうち 173 個のソースを添付する。ソースを自動で取得できない 42 個（Azul Zulu の JDK、JavaFX・javacpp のネイティブ部品、Renjin、SNAPSHOT の `fiji` の jar、ライセンスを判定できない 25 個など）は、同日のオーナーの判断で同梱し、上流のソースの所在だけを記す（`engines/fiji/source-exceptions.json`）。研究室の実機（Smart App Control を含む）での確認は未実施（[ローカル配布](local.md)） |
| Docker 版 | [Docker Desktop での利用](docker-desktop.md) |
| 解析提案（LLM） | 既定で無効。利用者が有効にした場合に限り動作し、月額の利用上限を設定した Worker で提供 |
| 開発環境 | 研究室の PC と同じ構成を Linux で起動し、公開画像で試せる（`scripts/dev.py serve`、[CONTRIBUTING](../CONTRIBUTING.md#ローカル開発)）。共有する開発環境では、登録済みの公開画像だけを受け付けられる（`CYTELLECT_UPLOAD_ALLOWLIST`、[データ保護](security.md#shared-development-environments)）。共有の起動と研究者による評価の計画は[実装計画（案）](drafts/cloud-development/plan.md)にある |
| CI とマージ | PR では変更したファイルに関係するジョブだけを実行し、最新の `main` を取り込んだ head で成功してからマージする（[CI の構成](ci.md)）。Windows のテスト一式は 4 つに分けて並列に実行する。次の段階は、公開デモのホイールをデプロイの中で作ること（PR の競合をなくす）、`fiji-browser` の分割、必須チェックの 1 つへの集約（`ci-required`） |
| 核小体検出 | NCL の protocol 4.3.0（公式の `cpsam_v2` に、親核による条件付けと境界補正を組み合わせる）。核小体用に追加学習した `ncl-r1-step0750`・`ncl-r1-step0375` は Hugging Face で公開済みで、製品にはまだ組み込んでいない。[計算仕様](methods.md)、[モデルの構成と受入記録](segmentation-models.ja.md) |

## 今後の計画

### 1. 自研究室での実証

研究室の実画像で、検出精度・操作性・解析時間を評価し、核小体・細胞質のモデルを改良します。

- **独立したテストデータを最初に構築する。** 学習・条件調整に使わない実験回の画像を、評価専用として分けておきます。これがないと、精度の比較も実証も成り立ちません。
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

### 評価する項目

モデルの検出精度、面積・輝度の測定誤差、手補正にかかる時間。

## 未完了の受入条件

| 項目 | 内容 |
|---|---|
| 非公開データでの検証 | 研究室の実画像による、検出と測定の生物学的な妥当性の確認 |
| 研究者による評価 | 複数の研究室の研究者による、作業の完了・時間・修正の負担・理解・再利用の評価（[評価タスク](usability-tasks.ja.md)） |
| Windows 版 | Cellpose は CPU では 1 視野に数十分かかり実用にならないため、推論をクラウド GPU（[設定](cloud-gpu.ja.md)）で行う。実 GPU での所要時間・費用と CPU との一致度の受入、Windows のセットアップ画面からの設定。別の PC で起きた Smart App Control によるブロックへの対応。0.1.0-local.21 の公開後、公開されたインストーラーの SHA-256 を確かめてから、サイトのダウンロードの記録（`apps/web/src/lib/published-release.json`）を `"asset": "installer"` に切り替える（サイトは対応済み。[手順](../apps/web/README.md#windows-release-link)） |
| ホスト型の解析 | 公開 TLS とドメイン、利用者が不在の間の継続的な削除、運用サーバーの分離。研究画像をクラウドで受け付ける前に満たす |
| LP | 2026-10-23 にヒーロー映像（培養プレートから始まる実写の版）と本文（具体的な主張と解析例の実画面、「できること」4 つのタブ）をオーナーが承認した。患者へつながる将来性のカードは、既存の深緑の面に、研究から患者への 3 段階を細→太の線でつなぐ案を実装（Vercel プレビューでオーナーが線の版を選択）。PC・スマートフォンの画面でオーナーが判定することが受入条件（[美術方針](lp-art-direction.md#5-世界観と章立て)）。そのほかの残りは、ヒーロー映像の改良（Codex が担当、[美術方針](lp-art-direction.md) §9・§10）、研究室での撮影の可否、核小体の検出の前後比較の画像と研究室の利用者の声を公開してよいかの確認 |
| 今後の機能 | アカウント、チーム、長期保存、決済 |

検証の層と記録の方法は [validation.md](validation.md) に従います。CI の成功や公開した事実は、科学的な妥当性の証明にはなりません。


## Laboratory manual-retention implementation

A scoped source change adds explicit manual workspace retention with consistent
API/worker/UI behavior and a durable guard against returning the volume to TTL.
Default non-lab retention remains 24 hours. Metadata-only checks do not establish
installed browser behavior, image correctness or delivery readiness. Remaining:
independent source review, integrated PR/model selection, pinned Docker release,
quiesced DB/artifact backup/restore, hardware/resource confirmation, and fresh
real-input installation acceptance. No automatic merge/default-model switch or
production PoC is part of this change.
