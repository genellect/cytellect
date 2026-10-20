# Development standards

## 日本語

[AGENTS.md](../AGENTS.md) の開発ルールに加え、変更する領域に以下の基準を適用します。セットアップと検証コマンドは [CONTRIBUTING.md](../CONTRIBUTING.md) を参照してください。

### 計算とデータの整合性

測定値の正本は API と解析パッケージが生成します。ブラウザ側や配布形態ごとに、別の測定・統計処理を持たせません。API を変更した場合は、OpenAPI、既定レシピ、生成した TypeScript 型を一緒に更新します。

原画像の画素値は変更せず、検出用の前処理と表示用の色・明るさを測定から分離します。マスクは原画像座標のラベル画像を正本とします。核を編集した場合は依存する核小体を、マスクや除外を変更した場合は派生する統計・図を無効化し、古い結果を混在させません。

閾値、背景補正、対象選別、計算式、統計手法の変更には、レシピ・処理の版更新、[Methods](methods.md) の更新、数値テストを伴わせます。欠測とゼロ、核・核小体・視野・試料・独立した実験単位を区別し、有意差を得るための調整や、失敗した視野の無断除外は行いません。

### 研究データと検証

非公開の画像・論文・ファイルパス・研究結果・参加者情報と、認証情報・トークンは、コード、ログ、Issue、PR、スクリーンショット、CI、外部 AI に含めません。実行時のデータは checkout の外に保存し、開発に本番の認証情報を使用しません。非公開データの検証は別に行い、公開するのは明示的に承認された匿名化済みの報告に限ります。

合成データは再現可能な数値テストに使用します。画像の結合テストと公開デモには公開された実画像を使い、出典、染色情報、再配布条件、ハッシュを記録します。別の染色を NCL や GFP として扱ってはいけません。

検出精度と使いやすさは実画像と研究者の操作で評価します。文献から得た仮説と、利用者から確認した要望を区別してください。CI の成功や p 値の一致は、生物学的な妥当性の証明にはなりません。評価は失敗・欠測・未検証の範囲も含めて報告します。

### モデル・依存関係・外部サービス

依存バージョンとモデルのハッシュを固定し、コード・重み・データのライセンスをそれぞれ確認します。解析実行時のパッケージ・モデル取得、任意コード・マクロの実行、外部 URL からの画像取得は認めません。

LLM の解析提案は既定で無効とし、利用者が有効にした場合に限り、[定義された範囲](workspace-redesign.md#analysis-proposal-service-llm)の情報を送信します。これは製品の機能であり、開発用 AI や CI に研究データを渡す例外ではありません。提案は構造化した設定としてローカルで検証し、測定・統計には共通の計算処理を使います。有料呼び出しには運用者が設定した予算が必要です。詳細は [security.md](security.md) に従います。

外部送信・設定変更・公開・課金は、ユーザーの現在の許可に従います。初期 MVP に有料サービスや Supabase を必須依存として追加しません。将来のサービス選定は別の判断として扱います。

### 画面と文章

LP は研究者にとっての価値を伝え、アプリは操作と判断を支えます。LP の基準は [現在の採用文](../apps/web/src/components/PublicLanding.tsx)と [interface-design.md](interface-design.md) です。写真、文字、構図、実際の出力を中心に据え、開発バッジや防御的な注釈、素材写真の断り書きを追加しません。出典と検証記録は関連文書に残し、機能・実績・推薦を創作しないでください。

Lila を参照した Dark and Blue、Blender の造形と Three.js の描画、GraphPad を参照した情報の順序を維持します。チャコール一色や CSS の遠近表現で代替しません。アプリでは明確な操作名と短い説明を使い、[一つのワークスペース](workspace-redesign.md)で画像から図まで進めます。視野ごとの確認手順を増やさず、研究者の目的から必要な操作を設計します。Fiji との比較は実際の機能を確認して記述します。

### 開発環境とリリース

通常の開発は Codex Cloud を使い、合成の数値データと登録済みの公開データで検証します。環境構築や実機確認、非公開データの検証は、データの境界を守ってローカルで行えます。調査は対象を絞り、複数人・複数エージェントで作業する場合は編集範囲を分けます。影響のない検証を繰り返さず、必須 CI は維持します。

ローカル版は共通の解析基盤を動かす実行環境です。起動、インストーラー、セッション、保存期限の変更では [local.md](local.md) を確認し、将来のホスト型 API との境界を保ちます。配布には対象パッケージの数値検証と導入後の受入確認、公開には正規 URL 上での動作確認が必要です。Fiji や非公開データの検証を省略した場合は、未実施と記録します。

README は確認済みの状態を記載し、未完了の要件は [roadmap](roadmap.md) に残します。[research-workflow.md](research-workflow.md) は研究者の操作と評価の背景として参照し、日付付きの記録は現在の方針・実装と照合します。

## English

Apply these standards to the affected areas alongside [AGENTS.md](../AGENTS.md). [CONTRIBUTING.md](../CONTRIBUTING.md) defines setup and validation commands.

### Calculation and data integrity

The API and analysis package produce authoritative measurements. Keep one measurement and statistics implementation across browser, local and hosted delivery. When changing an API, update OpenAPI, the default recipe and generated TypeScript types together.

Preserve original pixel values. Detection preprocessing and display colors or brightness must not change measurements. Label images in original coordinates are the canonical masks. Nuclear edits invalidate dependent nucleoli; mask or exclusion changes invalidate derived statistics and figures. Never mix stale and current results.

Changes to thresholds, background correction, selection, equations or statistics require recipe or protocol versioning, updated [Methods](methods.md) and numerical tests. Distinguish missing values from zero, and nuclei, nucleoli, fields, specimens and independent experimental units from one another. Never tune for significance or silently discard failed fields.

### Research data and evaluation

Keep private images, papers, paths, study results, participant information, credentials and tokens out of code, logs, issues, PRs, screenshots, CI and external AI. Store runtime data outside the checkout and never use production credentials for development. Validate private data separately; publish only an explicitly approved, sanitized report.

Use synthetic data for deterministic numerical tests. Image integration tests and public demos require published real images with recorded sources, stain metadata, redistribution terms and hashes. Never substitute another stain for NCL or GFP.

Evaluate detection and usability with real images and researcher tasks. Distinguish literature-informed hypotheses from observed user needs. Passing CI or matching a p-value does not establish biological validity. Report failures, missingness and unverified conditions as part of the evidence.

### Models, dependencies and external services

Pin dependency versions and model hashes. Review licenses for code, weights and data separately. Do not download packages or models during analysis, execute arbitrary submitted code or macros, or fetch images from remote URLs.

LLM proposals are off by default. Send only the [defined information](workspace-redesign.md#analysis-proposal-service-llm) when the user enables the feature. This product capability does not permit development AI or CI to receive research data. Validate structured proposals locally and use the shared implementation for measurements and statistics. Billable requests require an operator-configured budget. Follow [security.md](security.md) for the full boundary.

External transmission, settings changes, publication and spending require current user authorization. Do not add paid services or Supabase as mandatory dependencies of the initial MVP. Future service selection is a separate decision.

### Interface and writing

The landing page communicates researcher value; the application supports actions and decisions. Follow the [adopted copy](../apps/web/src/components/PublicLanding.tsx) and [interface-design.md](interface-design.md). Let photography, typography, composition and actual outputs carry the page. Do not add development badges, defensive copy or stock-photo disclaimers. Keep provenance and validation records in their documentation; never invent capabilities, results or endorsements.

Preserve the Lila-inspired Dark and Blue direction, Blender-authored forms, Three.js rendering and GraphPad-inspired information order. Charcoal-only styling or CSS perspective is not a substitute. Use clear operation names and concise instructions in the application. Keep image-to-figure work in [one workspace](workspace-redesign.md), without per-field confirmation chains. Design around the researcher's task. Verify Fiji's actual capabilities before making comparisons.

### Development environments and releases

Codex Cloud is the default development environment. Use synthetic numerical fixtures and registered public data. Local setup, installed-copy checks and private validation are permitted within the data boundary. Keep investigations focused and assign separate editing scopes when people or agents work concurrently. Reuse unaffected validation evidence while retaining mandatory CI.

Local delivery runs the shared analysis implementation. Read [local.md](local.md) before changing startup, installers, sessions or retention, and preserve the future hosted API boundary. Distribution requires numerical checks on the exact package and installed-copy acceptance; publication requires verification at the canonical URL. Record skipped Fiji or private-data checks as unrun.

Keep README status factual and unfinished requirements in the [roadmap](roadmap.md). Use [research-workflow.md](research-workflow.md) for researcher workflow and evaluation context, and check dated records against current direction and implementation.
