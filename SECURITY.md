# セキュリティポリシー

[English](SECURITY.en.md)

Cytellect は、未発表の顕微鏡画像を研究者の PC 上で解析する。画像、輪郭、測定値、図は PC に保存し、Cytellect のクラウドには保存しない。中継サービスと推論サーバーは、研究データを保存せず、更新の署名鍵も持たない。このため、研究者のアカウント、中継サービス、リポジトリへの書き込み権限のいずれが攻撃者の手に渡っても、PC 上の研究データと導入済みのアプリには到達できない。

対策の実装と試験は、このリポジトリで公開している。運営者は genellect であり、中継サービスの運用、認証情報と鍵の管理、インシデントへの対応に責任を負う。

脆弱性の報告は、[非公開の報告フォーム](https://github.com/genellect/cytellect/security/advisories/new)で受け付ける（[7. 脆弱性への対応](#7-脆弱性への対応)）。

- [1. 設計の原則](#1-設計の原則)
- [2. 構成と信頼境界](#2-構成と信頼境界)
- [3. 攻撃への対策](#3-攻撃への対策)
- [4. 認証情報、鍵、アカウントの保護](#4-認証情報鍵アカウントの保護)
- [5. 研究データの保護](#5-研究データの保護)
- [6. 監視とインシデント対応](#6-監視とインシデント対応)
- [7. 脆弱性への対応](#7-脆弱性への対応)
- [8. 関連文書](#8-関連文書)

## 1. 設計の原則

| 原則 | 内容 |
|---|---|
| 研究データは PC に置く | 画像、輪郭、測定値、図は PC に保存し、Cytellect のクラウドには保存しない。検出、測定、統計、作図も PC で実行する。 |
| クラウドが持つ情報と権限を最小にする | 中継サービスは、研究データを保存せず、更新の署名鍵を持たない。保存するのは、アカウント情報と利用量の記録だけである。 |
| 1 か所の侵害が全体に及ばないようにする | データ、鍵、権限を構成要素ごとに分離する。研究者のアカウント、中継サービス、リポジトリへの書き込み権限のいずれを取得しても、PC 上の研究データと導入済みのアプリには到達できない。 |
| 境界を越える入力は、受け取る側が検証する | PC 上のサーバー、中継サービス、推論サーバーは、境界を越えて届く入力をそれぞれ独立に検証する。 |
| 認証情報は、平文で保存せず、権限を絞る | トークンとログインコードは、ハッシュだけを保存する。API キーと署名鍵は、使用する構成要素だけが保持する。 |
| AI の出力は実行しない | AI の出力は、コードとして実行しない。解析の提案は、PC 上で検証した設定の下書きであり、研究者が採用するまで解析に使用しない。 |
| 配布物は、署名とハッシュで検証する | PC は、署名を検証した更新だけを実行する。依存パッケージと同梱物は、ハッシュで固定する。 |

## 2. 構成と信頼境界

### 2.1 構成要素

提供形態は、Windows 版（Microsoft Store 版と EXE 版）と、PC または研究室のサーバーで動かす Docker 版である。以下では、アプリを動かすその PC またはサーバーを PC と呼ぶ。

| 構成要素 | 役割 | 保持するデータ | 保持する鍵と認証情報 |
|---|---|---|---|
| PC（画面、PC 上のサーバー、解析ワーカー） | 検出、測定、統計、作図を実行する。 | 研究データのすべて | 端末トークン 1 つ（クラウドにログインした場合） |
| 中継サービス（Cytellect Worker。Cloudflare Workers 上で動作する） | ログイン、利用の承認、利用枠の管理を行い、クラウド GPU と AI への要求を中継する。 | アカウント情報と利用量の記録 | 外部サービスの API キー、HMAC 鍵 |
| 推論サーバー（Modal 上で動作する） | 細胞の検出（Cellpose）の GPU 推論を実行する。 | なし | なし |
| 配布（Microsoft Store、GitHub） | アプリを配布し、更新する。 | なし | なし（更新の署名鍵は、`main` からの実行に限定した署名環境に置く） |
| 公開サイト（`cytellect.app`） | ランディングページ、デモ、ガイドを提供する。 | なし（研究画像を受け付けない） | なし |

### 2.2 信頼境界

| 境界 | 内容 | 受け取る側の検証 |
|---|---|---|
| ブラウザ → PC 上のサーバー | 画面からの要求 | 接続元、Host、Origin、Fetch Metadata、CSRF 対策のヘッダー、セッション、所有者 |
| PC → 中継サービス | 検出と AI への要求 | 端末トークン、アカウントの状態、利用枠、本文のサイズとスキーマ、要求の識別子 |
| 中継サービス → 推論サーバー | 検出の要求 | Modal のプロキシ認証、入力の形式・サイズ・項目 |
| 中継サービス → PC | 検出の結果、解析の提案、考察の下書き | バージョンを示すハッシュの照合、提案のスキーマ検証、研究者の採用 |
| 配布元 → PC | 更新 | 署名、バージョン、SHA-256、サイズ |

### 2.3 外部サービス

| サービス | 用途 | 受け取る情報 |
|---|---|---|
| Cloudflare | 中継サービスの実行、アカウント情報と利用量の記録、管理画面の認証 | 中継中の要求（保存しない）、アカウント情報、利用量の記録 |
| Modal | 細胞の検出の GPU 推論 | 検出対象のプレーン、核のラベル、検出条件（処理中のみ） |
| Anthropic、OpenAI | 解析の提案と考察の下書きの生成 | [5.1 PC の外部へ送信する情報](#51-pc-の外部へ送信する情報) に示す、AI への送信情報 |
| Resend | ログインコードのメール送信 | メールアドレスとログインコード |
| GitHub | ソースコードの管理、CI、EXE 版の配布 | なし |
| Microsoft Store | Windows 版の配布と更新 | なし |
| Vercel | 公開サイトの提供 | なし |
| Google Analytics | 公開ページ（ランディングページ、デモ、ガイド）のアクセス解析 | 公開ページの閲覧に関する情報。広告目的の利用は無効にし、ブラウザが追跡の拒否（Do Not Track、Global Privacy Control）を示す場合は計測しない。作業画面と導入したアプリでは使用しない。 |

## 3. 攻撃への対策

### 3.1 不正アクセス

| 攻撃 | 対策 | 実装と試験 |
|---|---|---|
| ログインコードの総当たり | 5 回の誤入力でログインコードを無効にし、同じメールアドレスで 1 日 20 回の誤入力があれば 24 時間ロックする。誤入力はメールアドレス単位で数えるため、接続元の IP アドレスを変えても試行できる回数は増えない。ログインコードの送信は、IP アドレス単位（IPv6 は /64 単位）で 1 時間 20 回、メールアドレス単位で 1 時間 6 回かつ 1 日 10 回に制限し、検証は IP アドレス単位で 1 時間 30 回に制限する。6 桁のログインコードに対する 1 日あたりの成功確率は、1 つのメールアドレスにつき 2×10⁻⁵ 以下である。 | [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |
| パスワードリスト攻撃 | パスワードを使用しない。認証は、メールで受け取る 1 回限りのログインコード（有効期間 10 分。暗号論的に安全な乱数から偏りなく生成する）と、端末ごとに発行する 256 bit のトークンで行う。ログインコードは、Cytellect の管理者が許可したメールアドレスにのみ送信する。 | [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`http.ts`](services/proposal-worker/src/http.ts) [`mail.ts`](services/proposal-worker/src/mail.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |
| トークンの窃取 | 端末トークンは、256 bit の乱数である。中継サービスには SHA-256 のハッシュだけを保存する。PC では、研究データとは別の設定領域に保存し、PC 上のサーバーは応答にもログにも含めない。端末トークンは発行元の URL にのみ送信し、リダイレクトには従わない。90 日間使用しなければ失効し、ログアウトで PC と中継サービスの双方から削除する。 | [`cloud_account.py`](services/api/src/cytellect_api/cloud_account.py) [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`http.ts`](services/proposal-worker/src/http.ts) [`test_cloud_account.py`](tests/test_cloud_account.py) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |
| セッションの固定と乗っ取り | ログインのたびに、サーバーが新しいトークンを発行する。クライアントが指定したセッションは採用しない。セッションは HttpOnly かつ SameSite=Strict の Cookie で保持し、サーバーにはトークンの SHA-256 だけを保存する。ログアウトでセッションを失効させ、Windows 版はアプリの終了時にすべてのセッションを失効させる。 | [`app.py`](services/api/src/cytellect_api/app.py) [`local.py`](services/api/src/cytellect_api/local.py) [`db.py`](services/api/src/cytellect_api/db.py) [`test_local.py`](tests/test_local.py) |
| クロスサイトリクエストフォージェリ（CSRF） | 状態を変更する要求には、Origin の完全一致と、CSRF 対策の専用ヘッダーを要求する。CORS は、アプリ自身のオリジンだけを許可する。セッションの Cookie は、他のサイトからの要求には送信されない。 | [`app.py`](services/api/src/cytellect_api/app.py) [`local.py`](services/api/src/cytellect_api/local.py) [`desktop.py`](services/api/src/cytellect_api/desktop.py) [`test_local.py`](tests/test_local.py) [`test_desktop_owner.py`](tests/test_desktop_owner.py) |
| DNS リバインディング | PC 上のサーバーは、`127.0.0.1` でのみ待ち受ける。Windows 版は、要求ごとに接続元、Host の完全一致、Fetch Metadata（Sec-Fetch-Site）を照合し、転送を示すヘッダー（Forwarded、X-Forwarded-*）を含む要求を拒否する。 | [`local.py`](services/api/src/cytellect_api/local.py) [`test_local.py`](tests/test_local.py) |
| 権限のない読み出しと書き込み（アクセス制御の不備） | ワークスペース、視野、ジョブ、結果の識別子を受け取るすべての経路で、セッションの所有者と対象の所有者を照合する。一致しない要求には、存在しない場合と同じ応答を返す。識別子はサーバーが生成する UUID v4 であり、識別子だけでは権限を与えない。 | [`app.py`](services/api/src/cytellect_api/app.py) [`regions.py`](services/api/src/cytellect_api/regions.py) [`db.py`](services/api/src/cytellect_api/db.py) [`test_upload_guard.py`](tests/test_upload_guard.py) |
| 管理機能への不正な到達 | 管理画面は、Cloudflare Access（Google ログイン）の背後に置く。中継サービスも、Cloudflare Access が発行した JWT について、署名（アルゴリズムは RS256 に固定）、発行者、オーディエンス、有効期限、管理者のメールアドレスを独自に検証する。管理用の経路は指定したオリジンでのみ応答し、`workers.dev` などの別の入口からは、有効なトークンがあっても応答しない。 | [`access.ts`](services/proposal-worker/src/access.ts) [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`access.test.ts`](services/proposal-worker/src/access.test.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) [`wrangler.toml.example`](services/proposal-worker/wrangler.toml.example) |
| 承認の偽造 | 新しい研究者は、HMAC で署名した 1 回限りのリンク（有効期間 7 日）で承認する。リンクを開いただけでは承認されず、承認には画面での確認の操作を要する。 | [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`admin-page.ts`](services/proposal-worker/src/admin-page.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |
| 推論サーバーへの直接の要求 | Modal のプロキシ認証を必須とし、認証のない要求を受け付けない。 | [`modal_cellpose.py`](infra/modal_cellpose.py) [`cloud.ts`](services/proposal-worker/src/cloud.ts) |

### 3.2 インジェクション

| 攻撃 | 対策 | 実装と試験 |
|---|---|---|
| SQL インジェクション | PC 上のサーバーは、SQLAlchemy の式で問い合わせを組み立て、値をすべてバインドする。中継サービスは、すべての文をプリペアドステートメントで実行し、値をバインドする。要求の値を SQL の文字列に連結する箇所はない。 | [`db.py`](services/api/src/cytellect_api/db.py) [`app.py`](services/api/src/cytellect_api/app.py) [`store.ts`](services/proposal-worker/src/store.ts) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) |
| コマンドインジェクション | 外部のプロセスは、引数の配列で起動し、シェルを経由しない。Fiji には型の決まったパラメーターだけを渡し、マクロの文字列を実行しない。検出モデルの名前は固定で、要求から指定できない。 | [`supervision.py`](services/worker/src/cytellect_worker/supervision.py) [`engine.py`](packages/analysis/src/cytellect_analysis/engine.py) [`CytellectEngine.java`](engines/fiji/CytellectEngine.java) [`region_contracts.py`](packages/analysis/src/cytellect_analysis/region_contracts.py) |
| プロンプトインジェクション | AI には、ツールの呼び出しを与えない。AI の出力は JSON スキーマに限定し、コードとして実行しない。解析の提案は、PC 上でスキーマに照らして検証し、未定義の項目を含むものを拒否する。スキーマには、ファイルのパス、URL、コマンドを表す項目がない。提案は、研究者が採用するまで解析に使用しない。測定と統計は、提案の内容にかかわらず共通の実装が計算する。考察の下書きは、文字列として表示し、解析の設定と数値を変更しない。 | [`proposal_validation.py`](packages/analysis/src/cytellect_analysis/proposal_validation.py) [`proposal_contracts.py`](packages/analysis/src/cytellect_analysis/proposal_contracts.py) [`proposals.py`](services/api/src/cytellect_api/proposals.py) [`openai.ts`](services/proposal-worker/src/openai.ts) [`anthropic.ts`](services/proposal-worker/src/anthropic.ts) [`test_proposals.py`](tests/test_proposals.py) [`test_proposals_persistence.py`](tests/test_proposals_persistence.py) |
| クロスサイトスクリプティング（XSS） | 画面は、React のエスケープを通して描画する。研究者の入力と AI の出力は文字列として表示し、HTML として解釈しない。HTML として挿入するのは、解析が生成した SVG の図だけであり、要素と属性の許可リストで無害化してから挿入する。管理画面は、値を文字列として設定し、nonce を指定した Content Security Policy を適用する。 | [`EditableFigure.tsx`](apps/web/src/components/workspace/review/EditableFigure.tsx) [`DiscussionPanel.tsx`](apps/web/src/components/workspace/review/DiscussionPanel.tsx) [`admin-page.ts`](services/proposal-worker/src/admin-page.ts) [`http.ts`](services/proposal-worker/src/http.ts) |
| パストラバーサル | 保存には、サーバーが生成する UUID と固定の名前を使用し、アップロードされたファイル名をパスに使用しない。パスは、保存領域の内側にあることを検証する。設定ファイルと作業領域は、シンボリックリンクを拒否する。アーカイブは、ディスクに展開しない。 | [`db.py`](services/api/src/cytellect_api/db.py) [`config.py`](services/api/src/cytellect_api/config.py) [`local.py`](services/api/src/cytellect_api/local.py) [`app.py`](services/api/src/cytellect_api/app.py) |
| 安全でないデシリアライズ | pickle を使用しない。配列は、すべて pickle を無効にして読み込む。モデルの重みは、SHA-256 を照合したうえで、重みだけを読み込む方式で読み込む。外部から届く JSON は、未定義の項目を拒否するスキーマで検証する。 | [`server.py`](engines/cellpose/server.py) [`runner.py`](engines/cellpose/runner.py) [`cellpose_engine.py`](packages/analysis/src/cytellect_analysis/cellpose_engine.py) [`contracts.py`](packages/analysis/src/cytellect_analysis/contracts.py) [`proposal_contracts.py`](packages/analysis/src/cytellect_analysis/proposal_contracts.py) [`schema.ts`](services/proposal-worker/src/schema.ts) |
| サーバーサイドリクエストフォージェリ（SSRF） | 外部への接続先は、設定だけで決まる。要求と AI の出力は、接続先を指定できない。接続先の URL は HTTPS に限り、認証情報、クエリ、フラグメントを含むものを拒否する。外部への要求は、リダイレクトに従わない。更新の取得元は、ホストの許可リストに限り、リダイレクト先も照合する。推論の要求は、URL、ファイルのパス、任意のモデルの指定を受け付けない。 | [`cloud_account.py`](services/api/src/cytellect_api/cloud_account.py) [`cellpose_engine.py`](packages/analysis/src/cytellect_analysis/cellpose_engine.py) [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`openai.ts`](services/proposal-worker/src/openai.ts) [`anthropic.ts`](services/proposal-worker/src/anthropic.ts) [`app_update.py`](services/api/src/cytellect_api/app_update.py) [`server.py`](engines/cellpose/server.py) [`runner.py`](engines/cellpose/runner.py) |

### 3.3 入力とリソース

| 攻撃 | 対策 | 実装と試験 |
|---|---|---|
| 細工されたファイルのアップロード | 画像は、8 bit または 16 bit の 2 次元の TIFF で、1 シリーズに限る。1 辺は 4096 px までとし、ヘッダーから求めた画素数が上限内であることを確認してから展開する。外部のファイルを参照する OME は拒否する。表は 8 MiB、10 万行までとし、列の構成を固定する。1 ワークスペースは、100 視野、合計 2 GiB までとする。 | [`images.py`](packages/analysis/src/cytellect_analysis/images.py) [`numerical_csv.py`](packages/analysis/src/cytellect_analysis/numerical_csv.py) [`app.py`](services/api/src/cytellect_api/app.py) [`upload_guard.py`](services/api/src/cytellect_api/upload_guard.py) [`test_upload_guard.py`](tests/test_upload_guard.py) |
| サービス拒否と資源の枯渇 | 中継サービスは、本文のサイズを経路ごとに制限する（認証 4 KiB、解析の提案と考察 6 MiB、検出 256 MiB）。PC 上のサーバーは、待機中と実行中のジョブを合計 10 件までとし、ジョブに実行時間（3600 秒）とメモリ（4096 MB）の上限を設ける。推論サーバーは、単一のコンテナで同時に 1 件の要求だけを処理する。 | [`index.ts`](services/proposal-worker/src/index.ts) [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`app.py`](services/api/src/cytellect_api/app.py) [`supervision.py`](services/worker/src/cytellect_worker/supervision.py) [`modal_cellpose.py`](infra/modal_cellpose.py) [`test_supervision.py`](tests/test_supervision.py) |
| 費用の使い尽くし | GPU の秒数と AI の費用には、アカウントごと・月ごとの上限と、全体の月間予算を設ける。モデルの呼び出しの前に、その要求の最大費用を原子的に予約し、上限を超える要求は外部サービスへ転送せずに拒否する。GPU の要求は、アカウントごとに同時 1 件に限る。費用の記録に不整合が生じた場合は、解消するまで AI への要求を停止する。 | [`store.ts`](services/proposal-worker/src/store.ts) [`index.ts`](services/proposal-worker/src/index.ts) [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`store.test.ts`](services/proposal-worker/src/store.test.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |
| 要求の再送（リプレイ） | 提案の要求は、端末ごとに一意の識別子（UUID）を 1 回だけ受理する。ログインコード、承認リンク、招待は、1 回だけ消費する。 | [`index.ts`](services/proposal-worker/src/index.ts) [`store.ts`](services/proposal-worker/src/store.ts) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`index.test.ts`](services/proposal-worker/src/index.test.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |
| 競合状態の悪用 | 1 回限りの消費、予算の予約、レート制限の加算は、それぞれ単一の文で原子的に実行する。PC 上のデータベースは書き込みを直列化し、ジョブの実行権は比較交換で検証する。 | [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`store.ts`](services/proposal-worker/src/store.ts) [`db.py`](services/api/src/cytellect_api/db.py) |
| 解析の環境からの逸脱 | Docker 版の解析ワーカーは、ネットワークを持たない、非 root かつ読み取り専用のコンテナで動作する。Linux のケーパビリティをすべて削除し、権限昇格を禁止し、メモリとプロセス数を制限する。CI は、実際のコンテナで、外部への接続が拒否されることを検証する。解析の実行中に、コードやモデルをダウンロードしない。 | [`compose.yaml`](compose.yaml) [`ci.yml`](.github/workflows/ci.yml) [`runner.py`](engines/cellpose/runner.py) |

### 3.4 通信と表示

| 攻撃 | 対策 | 実装と試験 |
|---|---|---|
| 盗聴と改ざん（中間者攻撃） | PC と中継サービスが外部へ行う通信は HTTPS に限り、サーバー証明書を OS の信頼ストアで検証する。証明書の検証を無効にする経路はない。平文の HTTP を使用するのは、PC の内部（ループバック）だけである。更新は、通信経路とは独立に署名で検証する。 | [`cloud_account.py`](services/api/src/cytellect_api/cloud_account.py) [`cellpose_engine.py`](packages/analysis/src/cytellect_analysis/cellpose_engine.py) [`proposals.py`](services/api/src/cytellect_api/proposals.py) [`app_update.py`](services/api/src/cytellect_api/app_update.py) |
| 他のオリジンからの API の呼び出し | 中継サービスは、他のオリジンを許可する CORS のヘッダーを返さない。端末トークンは Authorization ヘッダーで送信するため、他のサイトのページからの要求は、ブラウザのプリフライトで遮断される。 | [`http.ts`](services/proposal-worker/src/http.ts) [`cloud.ts`](services/proposal-worker/src/cloud.ts) |
| クリックジャッキング | PC 上の画面、公開サイト、管理画面のすべてで、フレームへの埋め込みを禁止する。 | [`app.py`](services/api/src/cytellect_api/app.py) [`local.py`](services/api/src/cytellect_api/local.py) [`next.config.ts`](apps/web/next.config.ts) [`admin-page.ts`](services/proposal-worker/src/admin-page.ts) |
| 情報の漏えい | エラーは、あらかじめ定めたエラーコードだけを返し、内部の例外、スタックトレース、解析プログラムの出力を返さない。応答には、キャッシュ、MIME タイプの推測、リファラーの送信を禁止するヘッダーを付ける。アクセスログは無効にし、要求の本文、ファイル名、トークンの値をログに記録しない。中継サービスは、Cloudflare Workers のログ収集を無効にし、外部サービスのエラーを、あらかじめ定めたエラーコードと HTTP ステータスだけに置き換えて返す。 | [`app.py`](services/api/src/cytellect_api/app.py) [`local.py`](services/api/src/cytellect_api/local.py) [`index.ts`](services/proposal-worker/src/index.ts) [`wrangler.toml.example`](services/proposal-worker/wrangler.toml.example) [`deployment.test.mjs`](services/proposal-worker/scripts/deployment.test.mjs) |

### 3.5 配布とサプライチェーン

| 攻撃 | 対策 | 実装と試験 |
|---|---|---|
| 更新の差し替えと、古いバージョンへの差し戻し | EXE 版の各リリースには、バージョン、インストーラーの名前、SHA-256、サイズ、ソースのコミット、発行時刻を記載したマニフェストと、Ed25519 鍵による署名を付ける。アプリは、組み込んだ公開鍵でマニフェストの署名を検証してから、インストーラーを取得する。現在より新しいバージョンであり、インストーラーの SHA-256 とサイズがマニフェストと一致する場合にのみ実行する。配布元が示すハッシュは、信頼の根拠にしない。Microsoft Store 版は、Microsoft が署名し、Microsoft Store が更新する。 | [`update_signature.py`](services/api/src/cytellect_api/update_signature.py) [`app_update.py`](services/api/src/cytellect_api/app_update.py) [`local-release.yml`](.github/workflows/local-release.yml) [`test_update_signature.py`](tests/test_update_signature.py) [`test_app_update.py`](tests/test_app_update.py) |
| 初回のダウンロードの差し替え | 最初に導入するインストーラーも、同じ署名付きのマニフェストで検証できる（[手順](docs/install-windows.ja.md#2-ダウンロードと確認)）。 | [`update_signature.py`](services/api/src/cytellect_api/update_signature.py) |
| 依存パッケージ、同梱物、検出モデルの差し替え | Python と JavaScript の依存パッケージは、ロックファイルでバージョンとハッシュを固定する。同梱する Fiji、検出モデル、Python の実行環境は、ビルド時に SHA-256 を照合する。検出モデルは、読み込みの前にも SHA-256 を照合する。 | [`uv.lock`](uv.lock) [`pnpm-lock.yaml`](pnpm-lock.yaml) [`fiji/runtime.lock.json`](engines/fiji/runtime.lock.json) [`cellpose/runtime.lock.json`](engines/cellpose/runtime.lock.json) [`build_windows_installer.py`](scripts/build_windows_installer.py) [`runner.py`](engines/cellpose/runner.py) [`test_windows_installer.py`](tests/test_windows_installer.py) |
| リポジトリへの不正な変更 | `main` への反映は、ルールセットで管理者に限定する。変更はプルリクエストで行い、必須の CI に合格したものを反映する。リリースは単一のコミットから作成し、各段階でそのコミットを照合する。`main` の履歴にないコミットとタグの再利用は拒否する。サイズまたはハッシュが試験済みのファイルと一致しないファイルは、公開しない。 | [`local-release.yml`](.github/workflows/local-release.yml) [`windows_exe_release.cjs`](scripts/windows_exe_release.cjs) [`windows_exe_release.test.cjs`](scripts/windows_exe_release.test.cjs) |
| CI の悪用 | ワークフローのトークンは、既定で読み取り専用とする。フォークに由来する実行には、書き込み権限とシークレットを与えない。リリースは、フォークに由来する実行を拒否する。 | [`ci.yml`](.github/workflows/ci.yml) [`local-release.yml`](.github/workflows/local-release.yml) [`windows_exe_release.cjs`](scripts/windows_exe_release.cjs) |
| 既知の脆弱性の悪用 | CodeQL（ワークフロー、JavaScript/TypeScript、Python）を、プルリクエスト、`main`、週次で実行する。依存パッケージの脆弱性の監査（pip-audit、pnpm audit）と、ソフトウェア部品表（SBOM）の生成を CI で実行する。 | [`codeql.yml`](.github/workflows/codeql.yml) [`ci.yml`](.github/workflows/ci.yml) [`sbom.py`](scripts/sbom.py) [`test_sbom.py`](tests/test_sbom.py) |

### 3.6 侵害時の影響範囲

攻撃者が次のいずれかを取得した場合の、影響の範囲を示す。

| 攻撃者が取得したもの | 影響の範囲 | 到達できないもの |
|---|---|---|
| 研究者のメールまたは端末トークン | そのアカウントの当月の利用枠 | 研究データ（クラウドに保存していない） |
| 中継サービス | 侵害の間に中継される要求と、中継サービスが保持する API キーとアカウント情報。提案は、PC 上の検証と研究者の採用を経なければ解析に使用されない。 | PC 上の研究データ、導入済みのアプリ、更新の署名鍵 |
| 中継サービスのデータベース | メールアドレス、承認の状態、利用量の記録 | 有効な認証情報（ハッシュだけを保存している）、研究データ |
| リポジトリへの書き込み権限 | ブランチとプルリクエスト | `main`、導入済みの PC（更新には、署名環境にある鍵による署名を要する） |

## 4. 認証情報、鍵、アカウントの保護

### 4.1 認証情報と鍵の一覧

| 認証情報・鍵 | 保管場所 | 権限の範囲 | 有効期間と失効 |
|---|---|---|---|
| 端末トークン | PC の設定領域（OS の利用者だけが読み取れる）。中継サービスには SHA-256 のハッシュだけ。 | そのアカウントの利用枠の範囲での、検出と AI の要求 | 90 日間の不使用、ログアウト、アカウントの失効で無効になる。失効は、次の要求から及ぶ。 |
| PC 上のセッション | ブラウザの Cookie（HttpOnly、SameSite=Strict）。PC 上のサーバーには SHA-256 のハッシュだけ。 | その PC 上のワークスペースの操作 | 7 日。ログアウトと、アプリの終了（Windows 版）で、ただちに無効になる。 |
| ログインコード | 中継サービスに、HMAC-SHA256 のハッシュだけ。 | 1 回のログイン | 10 分。1 回の使用、または 5 回の誤入力で無効になる。 |
| 承認リンク | 中継サービスに、SHA-256 のハッシュだけ。リンクは HMAC で署名する。 | 1 つのメールアドレスの承認 | 7 日。1 回の使用で無効になる。 |
| HMAC 鍵 | 中継サービスのシークレット（データベースの外）。32 文字未満の鍵では、ログインと管理の機能が起動しない。 | ログインコードのハッシュ、承認リンクの署名、レート制限の識別子の計算（用途ごとに領域を分ける） | 交換と同時に、未使用のログインコードと承認リンクが無効になる。 |
| 外部サービスの API キー（Anthropic、OpenAI、Resend） | 中継サービスのシークレットにのみ保管する。PC、配布物、中継サービスの応答には含めない。 | AI の呼び出しとメールの送信。費用は、月間予算の範囲に限られる。 | 外部サービスでの無効化と、シークレットの更新で交換する。 |
| 推論サーバーの認証情報（Modal のプロキシ認証） | 中継サービスのシークレットに保管する。クラウドにログインした PC は保持しない。 | 推論サーバーへの検出の要求 | Modal での再発行と、シークレットの更新で交換する。 |
| 更新の署名鍵（Ed25519） | 管理者のパスワードマネージャーと、`main` からの実行に限定した GitHub Actions の署名環境にのみ保管する。リポジトリ全体のシークレットには置かない。 | EXE 版の更新のマニフェストへの署名。署名のジョブだけが使用する。 | 交換と失効の手順を定めている（[更新の署名](docs/release-signing.md)）。 |
| 更新の公開鍵 | アプリに組み込む。 | マニフェストの署名の検証 | 鍵の交換の手順でのみ変更する。 |
| Microsoft Store への提出の認証情報 | 管理者の承認を要する、`main` に限定した GitHub Actions の環境に保管する。 | Microsoft Store への提出 | 提出のジョブだけが使用する。 |
| Cloudflare の API トークン | 管理者の運用環境にのみ置く。 | Cytellect のアカウントと `cytellect.app` のゾーンに限定した、Workers と D1 の編集 | Cloudflare での無効化で失効する。 |
| ワークフローのトークン（`GITHUB_TOKEN`） | GitHub Actions が実行ごとに発行する。 | 既定は読み取り専用。書き込みは、それを要するジョブにだけ与える。 | 実行の終了で無効になる。 |

実装と試験：[`cloud.ts`](services/proposal-worker/src/cloud.ts) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`http.ts`](services/proposal-worker/src/http.ts) [`cloud_account.py`](services/api/src/cytellect_api/cloud_account.py) [`local.py`](services/api/src/cytellect_api/local.py) [`update_signature.py`](services/api/src/cytellect_api/update_signature.py) [`wrangler.toml.example`](services/proposal-worker/wrangler.toml.example) [`local-release.yml`](.github/workflows/local-release.yml) [`windows-store-release.yml`](.github/workflows/windows-store-release.yml) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) [`test_cloud_account.py`](tests/test_cloud_account.py) [`deployment.test.mjs`](services/proposal-worker/scripts/deployment.test.mjs)

### 4.2 漏えいの防止と検出

| 対策 | 仕組み | 実装と試験 |
|---|---|---|
| 平文で保存しない | トークン、ログインコード、承認リンク、招待は、ハッシュだけを保存する。IP アドレスは保存せず、レート制限の識別子も HMAC で計算した値として保存する。トークンとログインコードの照合は、定数時間で行う。 | [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`http.ts`](services/proposal-worker/src/http.ts) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`db.py`](services/api/src/cytellect_api/db.py) |
| リポジトリの走査 | ハッシュを照合した gitleaks で、`main` と各プルリクエストの Git の全履歴と、追跡しているファイルを走査する。走査の結果は、件数と規則の識別子だけを出力する。 | [`scan_secrets.py`](scripts/scan_secrets.py) [`security-tools.lock.json`](scripts/security-tools.lock.json) [`ci.yml`](.github/workflows/ci.yml) [`test_scan_secrets.py`](tests/test_scan_secrets.py) |
| 配布物の走査 | インストーラーと Microsoft Store 版のパッケージは、ビルド時に認証情報の混入を走査し、検出した場合はビルドを失敗させる。 | [`build_windows_installer.py`](scripts/build_windows_installer.py) [`test_windows_installer.py`](tests/test_windows_installer.py) |
| 外部への送信の限定 | 中継サービスは、API キーを各外部サービスの固定の HTTPS の宛先にだけ送信し、リダイレクトには従わない。推論サーバーへ転送するヘッダーは、内容の種別と長さを示すものに限り、研究者の端末トークンは渡さない。 | [`openai.ts`](services/proposal-worker/src/openai.ts) [`anthropic.ts`](services/proposal-worker/src/anthropic.ts) [`mail.ts`](services/proposal-worker/src/mail.ts) [`cloud.ts`](services/proposal-worker/src/cloud.ts) |
| 開発との分離 | 開発環境には、環境ごとに発行した端末トークンだけを置く。API キーと署名鍵は、開発環境に置かない。リポジトリと CI は、非公開の研究データを含まない。複数人が利用する開発環境は、登録済みの公開ファイル以外のアップロードを、SHA-256 の照合で拒否する。 | [`public_uploads.py`](services/api/src/cytellect_api/public_uploads.py) [`test_public_uploads.py`](tests/test_public_uploads.py) |

### 4.3 運用アカウントの保護

| 対策 | 仕組み | 実装と試験 |
|---|---|---|
| 多要素認証 | 運用に使用する外部サービスのアカウントは、すべてパスキーまたは認証アプリによる多要素認証を必須とする。 | 運用上の設定 |
| 運用の権限 | 中継サービス、推論サーバー、配布の運用は、genellect だけが行う。推論サーバーのアカウントに、ほかの利用者を招待しない。 | 運用上の設定 |
| 配布の承認 | 手動の配布と Microsoft Store への提出は、管理者の承認を要する GitHub Actions の環境で実行する。自動の配布は、保護された `main` 上で CI と配布試験に合格したバージョンだけを公開する。 | [`local-release.yml`](.github/workflows/local-release.yml) [`windows-store-release.yml`](.github/workflows/windows-store-release.yml) [`windows_exe_release.cjs`](scripts/windows_exe_release.cjs) [`windows_exe_release.test.cjs`](scripts/windows_exe_release.test.cjs) |
| 支出の上限 | 中継サービスの月間予算とアカウントごとの上限に加えて、推論サーバーの事業者側にも支出の上限を設定する。 | [`store.ts`](services/proposal-worker/src/store.ts) [`wrangler.toml.example`](services/proposal-worker/wrangler.toml.example) |

### 4.4 暗号方式

| 用途 | 方式 |
|---|---|
| 通信の保護 | TLS。サーバー証明書を、OS の信頼ストアで検証する。 |
| トークンの生成 | 256 bit の暗号論的に安全な乱数 |
| トークンの保存 | SHA-256 のハッシュ |
| ログインコードの保存と承認リンクの署名 | HMAC-SHA256（用途ごとに領域を分ける） |
| 管理画面の JWT | RS256 による署名を、Cloudflare Access の公開鍵で検証する。 |
| 更新の署名 | Ed25519 による SSH 署名（OpenSSH の SSHSIG 形式、名前空間 `cytellect-update`、ハッシュは SHA-512） |
| 完全性の検証 | SHA-256。対象は、インストーラー、同梱物、検出モデル、依存パッケージ、取り込んだ画像である。 |
| 保存時の暗号化 | OS のディスク暗号化（BitLocker など） |

実装と試験：[`http.ts`](services/proposal-worker/src/http.ts) [`access.ts`](services/proposal-worker/src/access.ts) [`update_signature.py`](services/api/src/cytellect_api/update_signature.py) [`test_update_signature.py`](tests/test_update_signature.py) [`access.test.ts`](services/proposal-worker/src/access.test.ts)

## 5. 研究データの保護

### 5.1 PC の外部へ送信する情報

研究データを PC の外部へ送信するのは、研究者が次の 3 つの操作を実行したときだけである。どの操作も、使わなければ研究データは PC の外部に出ない。

| 操作 | 送信する情報 | 送信先 | 送信先での取り扱い |
|---|---|---|---|
| クラウド GPU による細胞の検出 | 検出対象の 1 プレーン（1 視野・1 チャンネルの原寸の画像 1 枚）と検出条件。核小体の検出では、採用済みの核のラベル（核の領域を示す画像）を加える。 | 中継サービスを経由して推論サーバー | 中継サービスは、本文を解釈も保持もせずに、ストリームのまま転送する。推論サーバーは、メモリ上でのみ処理し、ファイルに書き込まない。いずれも保存せず、ログに記録しない。 |
| AI への相談 | 研究の目的、チャンネルと視野の記録、画像の寸法、現在の解析設定、代表的な 1 視野の縮小画像（内訳は下記） | 中継サービスを経由して Anthropic または OpenAI | 中継サービスは保存せず、ログに記録しない。AI の提供元は、モデルの学習に使用しない。 |
| AI による考察の生成 | 保存した比較結果と実験の目的（内訳は下記） | 同上 | 同上 |

AI への相談で送信する情報は、次のとおりである。

- 研究の目的
- チャンネル名と、記録した染色
- 視野の名前（既定ではファイル名）と記録（条件、実験回、組、取得日）
- 画像の寸法と画素サイズ、視野と群の数
- 現在の解析設定と、前回の提案
- 代表的な 1 視野の、チャンネルごとの縮小画像（一辺 512 px 以下。設定で無効にできる）

考察の生成で送信する情報は、次のとおりである。

- 実験の目的（初期値は、そのワークスペースで AI への相談に記述した研究の目的）
- 画面のまとめ（見出しと要点）
- 指標の名前と定義、染色名、領域・群・実験回・チャンネルの名前
- 群ごとの値、差と信頼区間、実験回ごとの値、n とその内訳
- 集計と検定の方法、研究者が記述した実験単位の定義と対応の根拠、検定と p 値

核ごとの測定値とファイルのパスは、どの操作でも送信しない。研究者が除外した視野は、提案にも縮小画像にも使用しない。OpenAI には、応答を保存しない設定（`store: false`）で送信する。AI の提供元は、不正利用の監視のために、各社の API の規約が定める期間、データを保持する。

研究データを含まない通信は、クラウドへのログイン（メールアドレスとログインコード）、クラウドの機能の利用（端末トークン）、EXE 版の更新の確認（GitHub の公開リリース一覧の取得）の 3 つである。導入したアプリと作業画面は、利用状況の計測情報を送信しない。

実装と試験：[`proposals.py`](services/api/src/cytellect_api/proposals.py) [`discussions.py`](services/api/src/cytellect_api/discussions.py) [`cellpose_engine.py`](packages/analysis/src/cytellect_analysis/cellpose_engine.py) [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`server.py`](engines/cellpose/server.py) [`app_update.py`](services/api/src/cytellect_api/app_update.py) [`test_proposals.py`](tests/test_proposals.py) [`test_result_discussion_api.py`](tests/test_result_discussion_api.py) [`test_cellpose_remote.py`](tests/test_cellpose_remote.py)

### 5.2 同意と送信の確認

| 対策 | 仕組み | 実装と試験 |
|---|---|---|
| 同意 | AI への送信範囲は、クラウドへのログイン時と最初の考察の生成時に画面に表示し、同意を得たうえで送信する。送信範囲は、AI の設定画面にも常に表示する。 | [`CloudAccount.tsx`](apps/web/src/components/workspace/CloudAccount.tsx) [`ConnectedWorkspace.tsx`](apps/web/src/components/workspace/review/ConnectedWorkspace.tsx) [`AiSettings.tsx`](apps/web/src/components/workspace/AiSettings.tsx) |
| 送信の確認 | PC 上のサーバーは、研究者が画面で送信を確認した要求だけを AI へ送信し、確認のない要求を拒否する。 | [`proposals.py`](services/api/src/cytellect_api/proposals.py) [`discussions.py`](services/api/src/cytellect_api/discussions.py) [`test_proposals.py`](tests/test_proposals.py) [`test_result_discussion_api.py`](tests/test_result_discussion_api.py) |

### 5.3 保存と削除

| 対策 | 仕組み | 実装と試験 |
|---|---|---|
| 保存場所 | PC 上のデータと認証情報は、OS の利用者のプロファイルの中の、その利用者だけが読み取れる領域に保存する（Windows 版は `%LOCALAPPDATA%\Cytellect`）。 | [`local.py`](services/api/src/cytellect_api/local.py) [`cloud_account.py`](services/api/src/cytellect_api/cloud_account.py) [`local_setup.ps1`](scripts/local_setup.ps1) |
| 原画像の完全性 | 原画像の画素値は変更しない。取り込んだ画像は、SHA-256 を照合してから解析に使用し、結果は別の領域に書き出す。 | [`worker/regions.py`](services/worker/src/cytellect_worker/regions.py) |
| 保持期間 | Windows 版は、研究者が削除するまで作業データを保持する（EXE 版は、導入時に 24 時間での自動削除を選択できる）。Docker 版は、最後の操作から 24 時間で失効させ、削除する。`127.0.0.1` でのみ待ち受ける構成では、削除するまでの保持を選択できる。 | [`config.py`](services/api/src/cytellect_api/config.py) [`test_workspace_retention.py`](tests/test_workspace_retention.py) |
| 削除 | 失効または削除の時点で、読み出しをただちに遮断する。続いて、入力、配列、輪郭、図、書き出したファイルを削除する。 | [`app.py`](services/api/src/cytellect_api/app.py) [`worker/main.py`](services/worker/src/cytellect_worker/main.py) [`test_workspace_retention.py`](tests/test_workspace_retention.py) |

### 5.4 クラウドが保存する情報

Cytellect のクラウドが保存する情報は、次の 4 区分に限る。研究データは含まない。

| 区分 | 内容 | 用途 |
|---|---|---|
| アカウント情報 | メールアドレス、承認の状態、申請・承認・失効の日時、アカウントごとの利用枠 | 承認、失効、利用枠の管理 |
| 認証の記録 | 端末トークン、ログインコード、承認リンク、招待のハッシュと、その有効期限 | 認証 |
| レート制限と再送防止の記録 | HMAC で計算した識別子と回数、要求の識別子（UUID） | 総当たりと再送の防止 |
| 利用量の記録 | 月ごとの GPU の秒数、実行中の GPU の要求の開始時刻、解析の提案ごとの費用・AI の入出力トークン数・モデル名・プロンプトのバージョン | 利用枠と費用の管理 |

実装と試験：[`migrations/`](services/proposal-worker/migrations) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`store.ts`](services/proposal-worker/src/store.ts) [`store.test.ts`](services/proposal-worker/src/store.test.ts)

## 6. 監視とインシデント対応

### 6.1 運営者の責務

Cytellect は、genellect が運営する。genellect は、次の責務を負う。

- 中継サービスと推論サーバーの運用と、その設定の管理
- 認証情報と鍵の保管、交換、失効
- 研究者の利用の承認と失効
- 配布物への署名と、修正したバージョンの配布
- 脆弱性の報告への対応と、セキュリティアドバイザリの公開
- インシデントの封じ込め、影響の評価、影響を受けた研究者への通知、復旧

### 6.2 検知

| 対策 | 仕組み | 実装と試験 |
|---|---|---|
| 認証の異常 | 誤入力とレート制限の回数を記録し、上限に達したメールアドレスを自動でロックする。新しい利用の申請は、管理者にメールで通知する。 | [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |
| 利用量と費用の異常 | アカウントごとの利用量を記録し、管理画面に表示する。費用の記録に不整合が生じた場合は、AI への要求を自動で停止する。 | [`store.ts`](services/proposal-worker/src/store.ts) [`admin-page.ts`](services/proposal-worker/src/admin-page.ts) [`index.ts`](services/proposal-worker/src/index.ts) [`store.test.ts`](services/proposal-worker/src/store.test.ts) |
| 認証情報の混入 | CI が、Git の全履歴と配布物を走査する（[4.2 漏えいの防止と検出](#42-漏えいの防止と検出)）。 | [`scan_secrets.py`](scripts/scan_secrets.py) [`build_windows_installer.py`](scripts/build_windows_installer.py) [`ci.yml`](.github/workflows/ci.yml) |
| 脆弱性 | CodeQL と依存パッケージの監査を CI で実行し、外部からの報告を非公開の報告フォームで受け付ける（[7. 脆弱性への対応](#7-脆弱性への対応)）。 | [`codeql.yml`](.github/workflows/codeql.yml) [`ci.yml`](.github/workflows/ci.yml) |
| 配布物の改ざん | リリースの作成時に署名を検証し、公開後のファイルを再度検証する。アプリは、署名またはハッシュが一致しない更新を拒否し、エラーとして表示する。 | [`local-release.yml`](.github/workflows/local-release.yml) [`windows_exe_release.cjs`](scripts/windows_exe_release.cjs) [`app_update.py`](services/api/src/cytellect_api/app_update.py) [`test_app_update.py`](tests/test_app_update.py) |

### 6.3 インシデントへの対応

1. 封じ込め。影響を受ける機能を停止し、関係する認証情報と鍵を失効させる（[6.4 停止と失効の手段](#64-停止と失効の手段)）。
2. 影響の評価。影響を受けたアカウント、データ、バージョンの範囲を特定する。
3. 通知。研究者のアカウント情報、または中継中のデータに影響が及んだ場合は、影響を確認ししだい、登録されたメールアドレスに通知する。
4. 復旧。鍵を交換し、修正したバージョンを配布する。公開サイトとクラウドの機能は本番環境に反映し、Windows 版は Microsoft Store と署名付きの更新で配布する。
5. 公開。セキュリティアドバイザリを公開し、原因、影響の範囲、修正したバージョンを示す。
6. 再発の防止。原因を証拠で特定し、個別の対症ではなく、構造で対処する。

### 6.4 停止と失効の手段

| 対象 | 手段 | 効果 |
|---|---|---|
| 研究者のアカウント | 管理画面でアカウントを失効させる。 | そのアカウントでログインしたすべての端末の要求を、次の要求から拒否する。 |
| AI の機能 | 中継サービスの予算の設定を 0 にする。 | 解析の提案と考察の要求を、外部サービスへ転送せずに拒否する。 |
| クラウド GPU | 中継サービスの GPU の月間の上限を 0 にする。 | 検出の要求を、推論サーバーへ転送せずに拒否する。 |
| ログインと管理 | 中継サービスの HMAC 鍵を交換する。 | 未使用のログインコードと承認リンクが、交換と同時に無効になる。 |
| 外部サービスの API キー | 外部サービスで無効化し、中継サービスのシークレットを更新する。 | 無効化と同時に、古い API キーは使用できなくなる。 |
| EXE 版の自動の配布 | 自動の配布を無効にし、実行中のワークフローを取り消す。 | 新しいリリースが公開されなくなる。 |
| 更新の署名鍵 | 署名環境から鍵を削除し、新しい鍵を組み込んだバージョンを配布する（[更新の署名](docs/release-signing.md)）。 | 削除と同時に、署名環境はその鍵で署名できなくなる。以後のバージョンは新しい鍵で署名し、研究者には、新しいインストーラーでの導入を案内する。 |
| 中継サービスの版 | 以前のバージョンに切り戻す。 | 切り戻しと同時に、以前のバージョンが要求を処理する。 |

実装と試験：[`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`index.ts`](services/proposal-worker/src/index.ts) [`wrangler.toml.example`](services/proposal-worker/wrangler.toml.example) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) [`deployment.test.mjs`](services/proposal-worker/scripts/deployment.test.mjs) [`proposal-deployment.md`](docs/proposal-deployment.md) [`release-signing.md`](docs/release-signing.md)

## 7. 脆弱性への対応

### 7.1 修正を提供するバージョン

| 対象 | セキュリティ修正 |
|---|---|
| Microsoft Store 版 | 提供する（Microsoft Store が最新のバージョンに更新する） |
| EXE 版の最新のリリース | 提供する |
| `main`（`cytellect.app`、クラウドの機能、Docker 版） | 提供する |
| 上記より前の EXE 版 | 提供しない（アプリ内の更新で最新のバージョンに移行する） |

### 7.2 対象範囲

このリポジトリのコード、Windows 版（Microsoft Store 版と EXE 版）、Docker 版、`cytellect.app`、中継サービス、推論サーバーを対象とする。Cytellect による外部サービスの設定と利用方法に起因する問題も対象に含む。同梱する第三者のコンポーネント（Fiji、Cellpose など）と、利用する外部サービス自体の脆弱性は、各開発元の窓口が扱う。

### 7.3 脆弱性の報告

脆弱性は、GitHub の非公開の報告機能で報告する。リポジトリの **Security** タブで **Report a vulnerability** を選択すると、報告者とリポジトリの管理者だけが閲覧できる形で送信できる（[報告フォーム](https://github.com/genellect/cytellect/security/advisories/new)）。Issue、プルリクエスト、ディスカッションなどの公開の場には記載しない。

報告には、次の内容を含める。

- 対象のコミット、または Windows 版のバージョン
- 再現手順
- 想定される影響

### 7.4 試験の範囲

- 試験は、自分のアカウントと、合成データまたは公開データで行う。
- 他の研究者のデータとアカウントに触れない。
- サービスを止める試験を行わない。
- 修正したバージョンが配布されるまで（最大 90 日間）、脆弱性を公開しない。

### 7.5 報告後の対応

1. 合理的な報告には、3 日以内に返信する。
2. 影響範囲を特定し、深刻度を CVSS で評価して、報告者と共有する。
3. 非公開のセキュリティアドバイザリで修正し、修正したバージョンを配布する。報告者には、配布まで、最大 90 日間、公開を控えるよう求める。
4. 配布後にセキュリティアドバイザリを公開し、必要に応じて CVE を取得する。報告者が希望する場合は、謝辞に氏名を記載する。

公開済みのセキュリティアドバイザリは、[一覧](https://github.com/genellect/cytellect/security/advisories)にある。

## 8. 関連文書

| 文書 | 内容 |
|---|---|
| [更新の署名](docs/release-signing.md) | 署名鍵の作成、登録、交換、失効 |
| [チーム開発ルール §6](docs/team-development.md#6-研究データの扱い) | 開発における研究データと認証情報の取り扱い |
| [プライバシーポリシー](https://cytellect.app/privacy) | Microsoft Store 版とクラウドの機能で取り扱う情報 |
