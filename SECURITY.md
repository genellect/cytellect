# セキュリティポリシー

Cytellect は、未発表の顕微鏡画像を研究者の PC 上で解析する。画像、輪郭、測定値、図を Cytellect のクラウドに保存しないため、クラウドやリポジトリが侵害されても、保存された研究データには到達できない。

対策の実装と試験は、このリポジトリで公開している。各節の末尾に、対応するコードを示す。

脆弱性は、[非公開の報告フォーム](https://github.com/genellect/cytellect/security/advisories/new)で受け付ける（[12.3 脆弱性の報告](#123-脆弱性の報告)）。英語版は、この文書の[後半](#english)にある。

- [1. セキュリティ上の性質](#1-セキュリティ上の性質)
- [2. 構成とデータの流れ](#2-構成とデータの流れ)
- [3. 脅威と対策](#3-脅威と対策)
- [4. 研究データの保護](#4-研究データの保護)
- [5. 認証とアクセス制御](#5-認証とアクセス制御)
- [6. クラウドの構成要素](#6-クラウドの構成要素)
- [7. PC 上のアプリ](#7-pc-上のアプリ)
- [8. AI による解析支援](#8-ai-による解析支援)
- [9. 暗号](#9-暗号)
- [10. 配布物とサプライチェーン](#10-配布物とサプライチェーン)
- [11. 運用](#11-運用)
- [12. 脆弱性への対応](#12-脆弱性への対応)
- [13. 関連文書](#13-関連文書)

## 1. セキュリティ上の性質

| 性質 | 内容 | 詳細 |
|---|---|---|
| 研究データは PC にとどまる | 画像、輪郭、測定値、図は、研究者の PC または研究室のサーバーに保存する。検出、測定、統計、作図も同じ場所で実行し、原画像の画素値は変更しない。 | [4. 研究データの保護](#4-研究データの保護) |
| 外部への送信は最小限である | PC の外部へ送信するのは、利用者がクラウド GPU または AI の機能を実行したときに、その処理に必要な情報だけである。これらの機能は任意であり、使用しなければ研究データは PC の外部に出ない。 | [2.2 PC の外部へ送信する情報](#22-pc-の外部へ送信する情報) |
| クラウドは研究データを保存しない | 中継サービスと推論サーバーは、研究データを処理中にのみ扱い、保存もログへの記録もしない。 | [6. クラウドの構成要素](#6-クラウドの構成要素) |
| 単一の侵害は波及しない | データ、鍵、権限を構成要素ごとに分離している。クラウドのアカウント、中継サービス、リポジトリのいずれが侵害されても、保存された研究データと導入済みのアプリには到達できない。 | [3. 脅威と対策](#3-脅威と対策) |
| 構成要素は互いを検証する | 構成要素は互いの入出力を信頼しない。中継サービスは PC の要求を、推論サーバーは中継サービスの要求を、PC はクラウドの応答を、それぞれ独立に検証する。 | [6. クラウドの構成要素](#6-クラウドの構成要素)、[7. PC 上のアプリ](#7-pc-上のアプリ) |
| AI の出力は解析を変更しない | AI の出力は、コードとして実行しない。解析の提案は検証済みの設定の下書きであり、研究者が採用するまで解析に使用しない。測定と統計は、共通の実装だけが計算する。 | [8. AI による解析支援](#8-ai-による解析支援) |
| 更新は署名で検証する | PC は、管理者の鍵で署名された更新だけを実行する。依存と同梱物は、ハッシュで固定する。 | [10. 配布物とサプライチェーン](#10-配布物とサプライチェーン) |
| 解析はクラウドに依存しない | 測定、統計、作図は PC 上で完結する。クラウドの機能が停止しても、解析は継続できる。 | [2. 構成とデータの流れ](#2-構成とデータの流れ) |

## 2. 構成とデータの流れ

### 2.1 構成要素

研究データを保持するのは、研究者の PC だけである。クラウド側の構成要素は、処理に必要な期間と範囲でのみデータを扱う。

| 構成要素 | 役割 | 保持するデータ | 保持する鍵と資格情報 |
|---|---|---|---|
| 研究者の PC（画面、PC 上のサーバー、解析ワーカー） | 検出、測定、統計、作図を実行する。 | 研究データのすべて | 端末トークン 1 つ（クラウドにログインした場合） |
| 中継サービス（Cytellect Worker。Cloudflare 上で動作する） | ログイン、利用の承認、利用枠の管理を行い、クラウド GPU と AI への要求を中継する。 | アカウント情報と利用量の記録。研究データは保存しない。 | 送信先の API キー、ハッシュと承認リンクの署名に使用する鍵 |
| 推論サーバー（Modal 上で動作する） | 細胞の検出（Cellpose）の GPU 推論を実行する。 | なし。要求の内容は、処理中のみメモリ上に保持する。 | なし |
| 配布（Microsoft Store、GitHub） | アプリを配布し、更新する。 | 研究データを扱わない。 | 更新の署名鍵は、管理者と、`main` に限定した署名環境だけが保持する。 |
| 公開サイト（`cytellect.app`） | ランディングページ、デモ、ガイドを提供する。 | 研究画像を受け付けない。 | なし |

### 2.2 PC の外部へ送信する情報

PC の外部へ送信するのは、利用者が次の操作を実行したときだけである。外部へ送信する情報は、この表がすべてである。

| 操作 | 送信する情報 | 送信先 | 送信先での取り扱い |
|---|---|---|---|
| クラウド GPU による細胞の検出 | 検出対象の 1 プレーンと検出条件。核小体の検出では、採用済みの核のラベルを加える。 | 中継サービスを経由して推論サーバー | 中継サービスは本文を読み取らずに転送し、推論サーバーはメモリ上でのみ処理する。いずれも保存せず、ログに記録しない。 |
| AI への解析の相談 | 研究の目的、チャンネル名と記録した染色、視野の名前（既定ではファイル名）と記録（条件、実験回、組、取得日）、画像の寸法と画素サイズ、視野と群の数、現在の解析設定と前回の提案、代表的な 1 視野のチャンネルごとの縮小画像（一辺 512 px 以下。設定で無効にできる） | 中継サービスを経由して Anthropic または OpenAI | 中継サービスは本文を保存せず、ログに記録しない。OpenAI には、応答を保存しない設定（`store: false`）で送信する。送信したデータは、モデルの学習に使用されない。各提供元は、不正利用の監視のために、各社の API の規約が定める期間、データを保持する。 |
| AI による考察の生成 | 保存した比較結果と実験の目的。比較結果は、画面のまとめ（見出しと要点）、指標の名前と定義、染色名、領域・群・実験回・チャンネルの名前、群ごとの値、差と信頼区間、実験回ごとの値、n とその内訳、集計と検定の方法、研究者が記述した実験単位の定義と対応の根拠、検定と p 値からなる。目的の初期値は、そのワークスペースで AI への相談に記述した研究の目的である。 | 同上 | 同上 |
| クラウドへのログイン | メールアドレスとログインコード | Resend | ログインコードのメール送信にのみ使用する。 |

### 2.3 外部サービス

| サービス | 用途 | 受け取る情報 |
|---|---|---|
| Cloudflare | 中継サービスの実行、アカウント情報と利用量の記録、管理画面の認証 | 中継中の要求（保存しない）、アカウント情報、利用量の記録 |
| Modal | 細胞の検出の GPU 推論 | 検出対象のプレーン、ラベル、検出条件（処理中のみ） |
| Anthropic、OpenAI | 解析の提案と考察の下書きの生成 | [2.2 PC の外部へ送信する情報](#22-pc-の外部へ送信する情報) に示す AI への送信情報 |
| Resend | ログインコードのメール送信 | メールアドレスとログインコード |
| GitHub | ソースコードの管理、CI、EXE 版の配布 | 研究データを受け取らない。 |
| Microsoft Store | Windows 版の配布と更新 | 研究データを受け取らない。 |
| Vercel | 公開サイトの提供 | 研究画像を受け取らない。 |
| Google Analytics | 公開ページのアクセス解析 | 公開ページの閲覧に関する情報。作業画面と導入したアプリでは使用しない。 |

## 3. 脅威と対策

想定する脅威ごとに、対策と、その結果を示す。

| 脅威 | 対策 | 結果 |
|---|---|---|
| 研究者のクラウドのアカウントの乗っ取り | 研究データをクラウドに保存しない。利用枠に月ごとの上限を設ける。管理者がアドレスを失効させると、すべての端末を次の要求から拒否する。 | その利用者の GPU と解析提案の利用枠（月ごとの上限まで）。研究データには到達できない。 |
| 中継サービスの侵害 | 中継サービスは本文を保存しない。更新の署名鍵は中継サービスの外に保管する。PC は、提案を定義済みの設定として検証し、研究者の採用を要求する。 | 侵害されている間に中継されるデータの閲覧と、推論結果・提案の改ざん。保存された研究データとアプリの更新には到達できない。 |
| リポジトリへの書き込み権限の取得 | `main` の更新をルールセットで制限し、反映できるのは管理者に限る。更新には、管理者の鍵による署名を要する。 | ブランチとプルリクエスト。`main` と導入済みの PC には到達できない。 |
| 配布経路での更新の差し替え | アプリは、組み込んだ公開鍵でマニフェストの署名を検証し、インストーラーのハッシュとサイズを照合する。現在より新しい版だけを受け入れる。 | 署名とハッシュが一致しないインストーラーは、実行されない。 |
| 依存パッケージと同梱物の改ざん | 依存は、ハッシュ付きの固定ファイルで固定する。同梱物と検出モデルは、ビルド時と読み込み時に SHA-256 で照合する。 | ハッシュが一致しないものは、取り込まれない。 |
| 他のサイトから PC 上の画面への操作（CSRF、DNS リバインディング） | PC 上のサーバーは `127.0.0.1` でのみ待ち受ける。要求の宛先、オリジン、発生元を照合し、状態を変更する要求には CSRF 対策のヘッダーを要求する。セッションの Cookie は、他のサイトからの要求に送信されない。 | 他のサイトからの要求は、拒否される。 |
| 通信経路上の盗聴と改ざん | 外部との通信は、すべて TLS で暗号化する。端末トークンは発行元の URL にのみ送信し、リダイレクトには従わない。更新は、通信経路とは独立に署名で検証する。 | 通信の内容は読み取れない。改ざんされた更新は、実行されない。 |
| ログインコードの総当たり | 5 回の誤入力でコードを無効にし、同一アドレスで 1 日 20 回の誤入力があれば 24 時間ロックする。送信と検証の回数を、IP アドレス単位とアドレス単位で制限する。 | 試行は、1 つのコードにつき 5 回、1 つのアドレスにつき 1 日 20 回までに限られる。 |
| 中継サービスのデータベースの漏えい | トークンとコードは、ハッシュだけを保存する。IP アドレスと研究データは保存しない。 | メールアドレス、承認の状態、利用量の記録。有効な資格情報と研究データは得られない。 |
| 誤った、または操作された AI の出力 | AI の出力は、コードとして実行しない。提案は定義済みの項目と値だけからなる設定として検証し、研究者が採用するまで使用しない。測定と統計は、共通の実装だけが計算する。 | 解析の設定と数値は、研究者の採用なしには変わらない。 |
| 不正な入力ファイル | 入力の形式、寸法、サイズを検証する。保存には内部の識別子を使用し、配列はコードの実行を伴わない形式でのみ読み込む。Docker 版の解析ワーカーは、ネットワークを持たない隔離したコンテナで動作する。 | 形式と上限を満たさない入力は、解析の前に拒否される。 |
| 同じ環境の他の利用者による読み出し | 読み出しのたびに所有者を確認する。他者のワークスペースについては、存在の有無も返さない。 | 他者のワークスペースは、内容も存在の有無も得られない。 |

## 4. 研究データの保護

### 4.1 送信の統制

| 項目 | 内容 |
|---|---|
| 送信する情報の範囲 | 外部へ送信する情報は、[2.2 PC の外部へ送信する情報](#22-pc-の外部へ送信する情報) に示したものに限る。核ごとの測定値とファイルのパスは、いずれの操作でも送信しない。利用者が除外した視野は、提案にも縮小画像にも使用しない。 |
| 同意 | AI への送信範囲は、クラウドへのログイン時と最初の考察の生成時に画面に表示し、同意を得たうえで送信する。送信範囲は、AI の設定画面にも表示する（2026-11-16 に決定し、2026-11-17 に考察の生成へまとめ・n の内訳・方法・目的を追加した。経緯は [AI による解析支援の見直し](docs/drafts/llm-assistant/plan.md)）。 |
| 送信の確認 | AI への送信は、利用者の操作による確認を伴う要求だけを受け付ける。確認を伴わない要求は、PC 上のサーバーが拒否する。 |
| 検出の送信内容 | 検出では、検出対象の 1 プレーン、検出条件、核小体の検出に必要な核のラベルだけを送信する。ファイル名、ワークスペースの名前、条件、ほかのチャンネルは送信しない。 |

実装：[`proposals.py`](services/api/src/cytellect_api/proposals.py)、[`discussions.py`](services/api/src/cytellect_api/discussions.py)、[`cellpose_engine.py`](packages/analysis/src/cytellect_analysis/cellpose_engine.py)。試験：[`test_proposals.py`](tests/test_proposals.py)、[`test_result_discussion_api.py`](tests/test_result_discussion_api.py)、[`test_cellpose_remote.py`](tests/test_cellpose_remote.py)

### 4.2 保管、保持、削除

| 項目 | 内容 |
|---|---|
| 保存時の保護 | PC 上のデータと資格情報は、OS の利用者だけが読み取れる場所に保存する。保存時の暗号化は、OS の機能（BitLocker など）による。 |
| 原画像の完全性 | 原画像の画素値は変更しない。解析は、取り込んだ画像のハッシュ（SHA-256）を照合してから使用し、結果は別の領域に書き出す。 |
| 保持期間 | Windows 版は、利用者が削除するまで作業データを保持する（EXE 版は、導入時に 24 時間での自動削除を選択できる）。Docker 版は、最後の操作から 24 時間で失効させて削除する。研究者自身の PC に限り、手動での保持を選択できる。 |
| 削除 | 失効と削除は、読み出しをただちに遮断する。その後、入力、配列、マスク、図、書き出したファイルを削除する。 |

実装：[`config.py`](services/api/src/cytellect_api/config.py)、[`db.py`](services/api/src/cytellect_api/db.py)、[`regions.py`](services/worker/src/cytellect_worker/regions.py)。試験：[`test_workspace_retention.py`](tests/test_workspace_retention.py)

### 4.3 クラウドが保存する情報

Cytellect のクラウドは、研究データを保存しない。保存するのは、次の情報に限る。

| 区分 | 内容 | 用途 |
|---|---|---|
| アカウント情報 | メールアドレス、承認の状態と日時、トークンとコードのハッシュ | 認証、承認、失効 |
| 利用量の記録 | 月ごとの GPU の秒数、解析提案ごとの費用とトークン数 | 利用枠と費用の管理 |

実装：[`0004_cloud_access.sql`](services/proposal-worker/migrations/0004_cloud_access.sql)、[`auth-store.ts`](services/proposal-worker/src/auth-store.ts)、[`store.ts`](services/proposal-worker/src/store.ts)

### 4.4 利用状況の計測

| 項目 | 内容 |
|---|---|
| アプリの計測 | 導入したアプリと作業画面は、利用状況の計測情報を送信しない。 |
| 公開サイトのアクセス解析 | アクセス解析を使用するのは、`cytellect.app` の公開ページ（ランディングページ、デモ、ガイド）に限る。これらのページは研究画像を受け付けない。広告目的の利用は無効にし、ブラウザの追跡拒否の設定（Do Not Track、Global Privacy Control）がある場合は計測しない。 |
| 更新の確認 | EXE 版は、GitHub の公開リリース一覧を参照して更新の有無を確認する（最大 6 時間に 1 回）。研究データとアカウント情報は送信しない。 |

実装：[`LandingAnalytics.tsx`](apps/web/src/components/LandingAnalytics.tsx)、[`app_update.py`](services/api/src/cytellect_api/app_update.py)

## 5. 認証とアクセス制御

### 5.1 研究者のログイン

| 項目 | 内容 |
|---|---|
| ログインコード | 研究者は、メールで送信する 6 桁のコードで認証する。コードは暗号論的乱数で生成し、管理者が許可したアドレスにのみ送信する。コードは 10 分で失効し、1 回だけ使用できる。 |
| 試行の制限 | 5 回の誤入力でコードを無効にし、同一アドレスで 1 日 20 回の誤入力があれば 24 時間ロックする。試行回数はアドレス単位で数えるため、IP アドレスを変えても試行回数は増えない。 |
| 回数制限 | コードの送信と検証の回数を、IP アドレス単位（IPv6 は /64 単位）とアドレス単位で制限する。 |

実装：[`cloud.ts`](services/proposal-worker/src/cloud.ts)、[`auth-store.ts`](services/proposal-worker/src/auth-store.ts)、[`mail.ts`](services/proposal-worker/src/mail.ts)。試験：[`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts)

### 5.2 資格情報

| 項目 | 内容 |
|---|---|
| 端末トークン | ログインした PC が保持する資格情報は、256 bit の乱数による端末トークン 1 つに限る。トークンは 90 日間使用しなければ失効し、サインアウト時に PC とサーバーの双方から削除する。 |
| 端末トークンの保管と送信 | 端末トークンは、研究データとは別の設定領域に保存する。PC 上のサーバーは、トークンを応答にもログにも含めない。トークンは発行元の URL にのみ送信し、リダイレクトには従わない。 |
| サーバーが保存する認証情報 | トークンは SHA-256、コードは鍵付きの HMAC-SHA256 によるハッシュのみを保存する。IP アドレスは保存せず、回数制限の識別子も鍵付きのハッシュとして保存する。秘密値の照合は、定数時間で行う。 |
| 送信先の鍵 | Anthropic、OpenAI、Modal、Resend の鍵は、中継サービスのシークレットとしてのみ保持する。PC、配布物、中継サービスの応答には含めない。 |
| 失効 | 管理者がアドレスを失効させると、そのアドレスでログインしたすべての端末を、次の要求から拒否する。 |

実装：[`cloud.ts`](services/proposal-worker/src/cloud.ts)、[`http.ts`](services/proposal-worker/src/http.ts)、[`cloud_account.py`](services/api/src/cytellect_api/cloud_account.py)。試験：[`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts)、[`test_cloud_account.py`](tests/test_cloud_account.py)

### 5.3 管理者

| 項目 | 内容 |
|---|---|
| 多要素認証 | 運用に使用するクラウドのアカウントは、すべてパスキーまたは認証アプリによる多要素認証を必須とする。 |
| 管理画面の認証 | 管理画面は、Cloudflare Access（Google ログイン）の背後に置く。中継サービスも、アクセストークン（JWT）の署名（RS256 に固定）、発行者、対象、有効期限、管理者のアドレスを独自に検証する。 |
| 管理用の経路の限定 | 管理用の経路は、指定したオリジンでのみ応答する。`workers.dev` などの別の入口からは、有効なトークンがあっても応答しない。 |
| 利用者の承認 | 新規の利用者は、HMAC で署名した 1 回限りのリンク（7 日で失効）で承認する。リンクを開いただけでは承認されず、承認には画面での確認の操作を要する。 |
| 管理画面の保護 | 管理画面は、外部の資源の読み込み、他のサイトへの埋め込み、キャッシュを禁止する。管理の操作は、同一オリジンからの要求に限る。 |

実装：[`access.ts`](services/proposal-worker/src/access.ts)、[`cloud.ts`](services/proposal-worker/src/cloud.ts)、[`admin-page.ts`](services/proposal-worker/src/admin-page.ts)。試験：[`access.test.ts`](services/proposal-worker/src/access.test.ts)、[`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts)

### 5.4 PC 上の画面

| 項目 | 内容 |
|---|---|
| 待ち受け | PC 上のサーバーは、`127.0.0.1` でのみ待ち受ける。Docker 版は、ポートを `127.0.0.1` にのみ公開する。 |
| 要求の検証 | Windows 版は、要求ごとに接続元、宛先のホスト名、オリジン、要求の発生元を示すブラウザの情報（Fetch Metadata）を照合し、転送を示すヘッダーを含む要求を拒否する。状態を変更する要求には CSRF 対策のヘッダーも要求し、他のサイトと DNS リバインディングによる操作を拒否する。Docker 版は、状態を変更する要求のオリジンと CSRF 対策のヘッダーを照合する。 |
| セッション | セッションは、スクリプトから読み取れず、他のサイトからの要求には送信されない Cookie（HttpOnly、SameSite=Strict）で保持する。サーバーには、トークンの SHA-256 だけを保存する。ログアウトでセッションを失効させ、Windows 版はアプリの終了時にすべてのセッションを失効させる。 |
| 所有者の確認 | 読み出しのたびに所有者を確認し、他者のワークスペースについては存在の有無も返さない。識別子だけでは権限を与えない。 |

実装：[`local.py`](services/api/src/cytellect_api/local.py)、[`app.py`](services/api/src/cytellect_api/app.py)、[`desktop.py`](services/api/src/cytellect_api/desktop.py)。試験：[`test_local.py`](tests/test_local.py)、[`test_desktop_owner.py`](tests/test_desktop_owner.py)

### 5.5 解析の実行環境

Docker 版の解析ワーカーは、ネットワークを持たない、非 root かつ読み取り専用のコンテナで動作する。すべての特権（ケーパビリティ）を削除し、権限の昇格を禁止し、メモリとプロセス数を制限する。CI は、実際のコンテナで、外部への通信が拒否されることを検証する。

実装：[`compose.yaml`](compose.yaml)、[`Dockerfile.python`](infra/Dockerfile.python)、[`ci.yml`](.github/workflows/ci.yml)

## 6. クラウドの構成要素

### 6.1 中継サービス

| 項目 | 内容 |
|---|---|
| 本文の非保存 | 要求と応答の本文、コード、トークンを保存せず、ログに記録しない。実行基盤のログ収集機能は無効にしている。 |
| 検出の中継 | 検出の要求と応答は、本文を読み取らずに逐次転送する。送信先へ転送するヘッダーは内容の種別を示すものに限り、利用者の端末トークンを送信先に渡さない。 |
| 要求の検証 | 本文のサイズを経路ごとに制限する（認証 4 KiB、解析の提案 6 MiB、検出 256 MiB）。提案の要求は定義済みの形式に照らして検証し、縮小画像は PNG であることと 512 px 以下であることを、画素を復号せずに確認する。モデルと指示文の版は、許可した一覧に限る。 |
| 再送の防止 | 提案の要求は、端末ごとに一意の識別子（UUID）を 1 回だけ受理する。ログインコードと承認リンクは、原子的な更新で 1 回だけ消費する。 |
| 外部への要求 | 外部への要求はリダイレクトに従わないため、鍵が別のホストに送信されることはない。提供元のエラーは、定義済みのコードに置き換えて返す。 |
| 他のオリジンからの利用 | 他のオリジンからの利用を許可する設定（CORS）を持たないため、他のサイトのブラウザからは利用できない。 |
| 設定不備時の動作 | 必要な設定または鍵が欠けている場合、該当する機能は要求を受け付けない。 |

実装：[`index.ts`](services/proposal-worker/src/index.ts)、[`cloud.ts`](services/proposal-worker/src/cloud.ts)、[`http.ts`](services/proposal-worker/src/http.ts)、[`openai.ts`](services/proposal-worker/src/openai.ts)、[`anthropic.ts`](services/proposal-worker/src/anthropic.ts)。試験：[`index.test.ts`](services/proposal-worker/src/index.test.ts)、[`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts)、[`deployment.test.mjs`](services/proposal-worker/scripts/deployment.test.mjs)

### 6.2 利用枠と費用

| 項目 | 内容 |
|---|---|
| 利用枠 | GPU の秒数と AI の費用には、利用者ごと・月ごとの上限と、全体の月間予算を設ける。上限を超える要求は、送信先に転送せずに拒否する。 |
| 費用の予約 | モデルの呼び出し前に、その要求の最大費用を予約する。予約は原子的に行う。 |
| 費用の整合性 | 費用の記録に不整合が生じた場合は、解消するまで AI への要求を停止する。 |
| 同時実行 | GPU の要求は、利用者ごとに同時に 1 件に限る。 |

実装：[`store.ts`](services/proposal-worker/src/store.ts)、[`cloud.ts`](services/proposal-worker/src/cloud.ts)。試験：[`store.test.ts`](services/proposal-worker/src/store.test.ts)

### 6.3 推論サーバー

| 項目 | 内容 |
|---|---|
| 実行環境 | 単一のコンテナで、同時に 1 件の要求だけを処理する。永続的な記憶領域とメモリの保存機能は使用しない。コンテナは非 root で動作し、イメージはダイジェストで固定する。 |
| 認証 | Modal のプロキシ認証を必須とし、認証のない要求を受け付けない。 |
| 要求の取り扱い | 要求の内容は、処理中のみメモリ上に保持し、ファイルに書き込まない。要求の内容、パス、接続元のアドレスをログに記録しない。 |
| 入力の検証 | 入力の形式、サイズ、項目を検証する。要求で URL、ファイルのパス、任意のモデルを指定することはできない。 |
| モデル | 公開され、版を固定した重みだけを使用し、SHA-256 を検証してから読み込む。 |
| 結果の検証 | PC は、実行プログラム、モデル、依存の固定情報のハッシュが、導入した版と一致する結果だけを受理する。 |

実装：[`modal_cellpose.py`](infra/modal_cellpose.py)、[`server.py`](engines/cellpose/server.py)、[`runner.py`](engines/cellpose/runner.py)、[`runtime.lock.json`](engines/cellpose/runtime.lock.json)、[`cellpose_engine.py`](packages/analysis/src/cytellect_analysis/cellpose_engine.py)。試験：[`test_cellpose_remote.py`](tests/test_cellpose_remote.py)

## 7. PC 上のアプリ

| 項目 | 内容 |
|---|---|
| 応答の保護 | 応答には、キャッシュの禁止、内容の種別の推測の禁止、参照元の送信の禁止、他のサイトへの埋め込みの禁止を指定する。画面には、外部の資源の読み込みと外部への接続を禁止するコンテンツセキュリティポリシーを適用する。 |
| 入力の受け入れ | 受け入れる入力に上限を設ける（1 ワークスペースあたり 100 視野、合計 2 GiB。1 プレーンは 4096×4096 px まで）。保存には内部の識別子を使用し、アップロードされたファイル名をパスに使用しない。パスは保存領域の内側にあることを検証し、配列はコードの実行を伴わない形式でのみ読み込む。 |
| クラウドとの通信 | クラウドとの通信は HTTPS に限る。資格情報、クエリ、フラグメントを含む URL は受け付けない。リダイレクトには従わず、応答のサイズを制限し、定義済みの項目だけを画面に渡す。 |
| ログ | アクセスログは無効にしている。要求の本文、ファイル名、トークンの値をログに記録しない。 |
| エラーの取り扱い | エラーは、定義済みのコードだけを返す。内部の例外と解析プログラムの出力を、そのまま返すことはない。 |
| ジョブの監視 | ジョブには、実行時間とメモリの上限を設ける。監視が状態を確認できない場合は、解析のプロセスを停止し、結果を公開しない。中断したジョブは自動で再試行し（自動の試行は最大 2 回）、再試行は以前の結果を上書きしない。 |
| 実行時の取得 | 解析の実行中に、コードやモデルをダウンロードしない。 |

実装：[`local.py`](services/api/src/cytellect_api/local.py)、[`app.py`](services/api/src/cytellect_api/app.py)、[`upload_guard.py`](services/api/src/cytellect_api/upload_guard.py)、[`db.py`](services/api/src/cytellect_api/db.py)、[`cloud_account.py`](services/api/src/cytellect_api/cloud_account.py)、[`supervision.py`](services/worker/src/cytellect_worker/supervision.py)。試験：[`test_local.py`](tests/test_local.py)、[`test_upload_guard.py`](tests/test_upload_guard.py)、[`test_supervision.py`](tests/test_supervision.py)

## 8. AI による解析支援

| 項目 | 内容 |
|---|---|
| 出力の非実行 | AI の出力は、コードとして実行しない。 |
| 提案の検証 | 解析の提案は、定義済みの項目と値だけからなる設定として、PC 上で検証する。未定義の項目を含む提案と、説明文に URL やコードに類する文字列を含む提案は拒否する。チャンネルの構成は送信した内容と一致しなければならず、記録された染色を提案が変更することも、記録のない染色を提案が定めることもできない。 |
| 採用 | 提案は下書きであり、研究者が採用するまで解析に使用しない。 |
| 計算の分離 | 採用後も、測定と統計は、提案の内容にかかわらず共通の実装が計算する。提案が数値を生成することはない。 |
| 状態の再確認 | 外部の呼び出しの間に、ワークスペースのデータが変更された場合と、ワークスペースが失効または削除された場合は、その提案を破棄する。 |
| 考察の下書き | 考察の下書きは、形式のみを検証し、文章として比較結果に付して保存する。解析の設定と数値は変更しない。 |

実装：[`proposal_validation.py`](packages/analysis/src/cytellect_analysis/proposal_validation.py)、[`proposal_contracts.py`](packages/analysis/src/cytellect_analysis/proposal_contracts.py)、[`discussion_validation.py`](packages/analysis/src/cytellect_analysis/discussion_validation.py)、[`proposals.py`](services/api/src/cytellect_api/proposals.py)。試験：[`test_proposals.py`](tests/test_proposals.py)、[`test_result_discussion.py`](tests/test_result_discussion.py)

## 9. 暗号

| 用途 | 方式 | 鍵と秘密値の保管 |
|---|---|---|
| 通信の保護 | TLS | 各サービスの証明書による。 |
| 端末トークン | 256 bit の暗号論的乱数。サーバーには SHA-256 のハッシュだけを保存する。 | PC の設定領域 |
| ログインコード | 鍵付きの HMAC-SHA256 によるハッシュだけを保存する。 | ハッシュ用の鍵は、中継サービスのシークレットとして保持する。 |
| 承認リンク | HMAC-SHA256 による署名。照合は定数時間で行う。 | 同上 |
| 管理者のアクセストークン | RS256 による署名を、Cloudflare Access の公開鍵で検証する。 | 秘密鍵は Cloudflare Access が保持する。 |
| 更新の署名 | Ed25519 による OpenSSH 形式の署名（SHA-512）。公開鍵はアプリに組み込む。 | 秘密鍵は、管理者の手元と、`main` に限定した署名環境にのみ保管する。 |
| 完全性の検証 | SHA-256。対象は、インストーラー、同梱物、検出モデル、依存パッケージ、取り込んだ画像である。 | 期待するハッシュは、リポジトリと署名付きのマニフェストに記録する。 |
| 保存時の暗号化 | OS の機能（BitLocker など） | 利用者の OS が管理する。 |

## 10. 配布物とサプライチェーン

### 10.1 更新の署名と検証

| 項目 | 内容 |
|---|---|
| Microsoft Store 版（Windows 11） | Microsoft が署名し、導入と更新は Microsoft Store が行う。Store への提出は、管理者が承認した `main` の最新のコミットに限る。 |
| 更新の署名 | EXE 版の各リリースには、版、インストーラーの名前、SHA-256、サイズ、ソースのコミット、発行時刻を記載したマニフェストと、管理者の Ed25519 鍵による署名を付す。 |
| 更新の検証 | アプリは、組み込んだ公開鍵でマニフェストの署名を検証してから、インストーラーを取得する。現在より新しい版であり、インストーラーの SHA-256 とサイズがマニフェストと一致する場合にのみ実行する。取得元は HTTPS の GitHub のホストに限り、リダイレクト先も照合する。配布元が示すハッシュは、信頼の根拠にしない。 |
| 更新の切り戻し | 新しい版が起動しない場合は、切り替え前に取得したデータベースの写しと、以前の版に戻す。 |
| 初回導入 | EXE 版の最初の導入でも、同じマニフェストでダウンロードを検証できる（[手順](docs/install-windows.ja.md#2-ダウンロードと確認)）。 |

実装：[`update_signature.py`](services/api/src/cytellect_api/update_signature.py)、[`app_update.py`](services/api/src/cytellect_api/app_update.py)。試験：[`test_update_signature.py`](tests/test_update_signature.py)、[`test_app_update.py`](tests/test_app_update.py)

### 10.2 リリースの手順

| 項目 | 内容 |
|---|---|
| 署名鍵の保管 | 署名鍵は、管理者の手元と、`main` に限定した専用の署名環境にのみ保管する。鍵の作成、登録、交換、失効の手順は、[更新の署名](docs/release-signing.md)に定める。 |
| 配布の承認 | 手動配布は、管理者の承認を要する。管理者が有効にした EXE の自動配布では、保護された `main` 上で CI と配布試験に合格した版だけを公開する。 |
| コミットの照合 | リリースは単一のコミットから作成し、各段階でそのコミットを照合する。コミットは `main` の履歴に含まれなければならず、フォークに由来する実行とタグの再利用は拒否する。 |
| 公開するファイルの照合 | 公開するファイルは、サイズとハッシュが試験済みのファイルと一致しなければならない。 |

実装：[`local-release.yml`](.github/workflows/local-release.yml)、[`windows-store-release.yml`](.github/workflows/windows-store-release.yml)、[`windows_exe_release.cjs`](scripts/windows_exe_release.cjs)。試験：[`windows_exe_release.test.cjs`](scripts/windows_exe_release.test.cjs)

### 10.3 依存と同梱物

| 項目 | 内容 |
|---|---|
| 依存の固定 | Python と JavaScript の依存は、ハッシュ付きの固定ファイルで固定する。 |
| 同梱物の照合 | 同梱する Fiji、検出モデル、Python の実行環境は、ビルド時に SHA-256 で照合する。 |
| 配布物の検査 | 配布物は、ビルド時に認証情報の混入を走査し、検出した場合はビルドを失敗させる。 |
| 部品表とライセンス | CI は、依存のソフトウェア部品表（SBOM）を生成する。ソースの提供を求めるライセンスの部品については、対応するソースをリリースに添付する（[ライセンスと配布](docs/oss.md)）。 |

実装：[`uv.lock`](uv.lock)、[`pnpm-lock.yaml`](pnpm-lock.yaml)、[`runtime.lock.json`](engines/fiji/runtime.lock.json)、[`runtime.lock.json`](engines/cellpose/runtime.lock.json)、[`build_windows_installer.py`](scripts/build_windows_installer.py)、[`sbom.py`](scripts/sbom.py)

### 10.4 リポジトリと CI

| 項目 | 内容 |
|---|---|
| 変更の反映 | すべての変更はプルリクエストで行い、必須の CI の成功とレビューを経て、管理者が `main` に反映する。`main` の更新はルールセットで制限し、反映できるのは管理者に限る。 |
| レビュー | 管理者以外が作成した変更は、作成者以外の 1 名以上の承認を要する。レビューでは、本番への影響、画素値・測定値・統計・図への影響、非公開データと認証情報の混入の有無を確認する。 |
| 秘密情報の検出 | ハッシュを検証した gitleaks で、`main` と各プルリクエストの Git の全履歴を走査する。 |
| 静的解析と依存の監査 | CodeQL（ワークフロー、JavaScript/TypeScript、Python）を、プルリクエスト、`main`、週次で実行する。依存の脆弱性監査（pip-audit、pnpm audit）を CI で実行する。 |
| ワークフローの権限 | ワークフローに与えるトークンは、既定で読み取り専用とする。フォークに由来する実行には、書き込み権限とシークレットを与えない。 |
| 環境の分離 | 開発に本番の認証情報を使用しない。実行時のデータは、ソースコードの外に保存する。複数人が利用する開発環境は、登録済みの公開ファイル以外のアップロードを、ハッシュ（SHA-256）の照合で拒否する。 |
| 試験データ | 試験、評価、公開デモには、出典、再配布条件、ハッシュを記録した公開画像を使用する。非公開の研究データは、Git、CI、公開の場に含めない。 |

実装：[`ci.yml`](.github/workflows/ci.yml)、[`codeql.yml`](.github/workflows/codeql.yml)、[`scan_secrets.py`](scripts/scan_secrets.py)、[`security-tools.lock.json`](scripts/security-tools.lock.json)、[`public_uploads.py`](services/api/src/cytellect_api/public_uploads.py)。試験：[`test_scan_secrets.py`](tests/test_scan_secrets.py)、[`test_public_uploads.py`](tests/test_public_uploads.py)

## 11. 運用

### 11.1 権限

| 役割 | 権限 |
|---|---|
| 管理者 | `main` への反映、本番への公開と配布、外部サービスの契約と設定、利用者の承認と失効、脆弱性への対応を行う。 |
| 開発メンバー | 担当する変更を実装し、プルリクエストを作成し、他のメンバーの変更をレビューする。`main` への反映と配布の権限は持たない。 |
| AI エージェント | 依頼者の指示の範囲で実装と検証を行う。`main` への反映と本番への公開は、管理者が対象を明示して指示した場合に限る。 |

### 11.2 失効と復旧

| 事象 | 対応 |
|---|---|
| 利用者のアカウントの不正利用 | 管理者が該当するアドレスを失効させる。そのアドレスでログインしたすべての端末を、次の要求から拒否する。 |
| 認証情報の漏えい | 該当する認証情報を、ただちに無効化して再発行する。 |
| ハッシュと署名に使用する鍵の漏えい | 鍵を交換する。交換により、未使用のログインコードと承認リンクは無効になる。 |
| 更新の署名鍵の漏えいまたは紛失 | [更新の署名](docs/release-signing.md)に定める失効と交換の手順に従う。 |
| 中継サービスの不具合 | 以前の版に切り戻す。 |
| 非公開データまたは認証情報の混入 | ただちに管理者に連絡する。履歴の書き換えは単独で行わず、対応を協議する。 |

### 11.3 利用者が管理する範囲

| 領域 | Cytellect が行うこと | 利用者が行うこと |
|---|---|---|
| 研究データの保管 | アプリは、研究データを OS の利用者だけが読み取れる場所に保存する。 | PC と OS アカウントの管理、ディスクの暗号化、バックアップ |
| クラウドの機能 | 認証、中継、利用枠の管理、送信範囲の表示 | 機能の使用の判断、送信範囲への同意 |
| アプリの更新 | 署名付きの更新の提供 | 更新の適用 |
| アカウント | 承認、失効、認証情報の保護 | メールアドレスの管理、使用しなくなった端末のサインアウト |

## 12. 脆弱性への対応

### 12.1 サポート対象の版

| 版 | セキュリティ修正 |
|---|---|
| Microsoft Store 版 | 提供する（Microsoft Store が最新版に更新する） |
| EXE 版の最新のリリース | 提供する |
| `main`（`cytellect.app` とクラウドの機能） | 提供する |
| 上記より前の EXE 版 | 提供しない（アプリ内の更新で最新版に移行する） |

### 12.2 対象範囲

このリポジトリのコード、Windows 版（Microsoft Store 版と EXE 版）、Docker 版、`cytellect.app`、中継サービス、推論サーバーを対象とする。Cytellect による外部サービスの設定と利用方法に起因する問題も対象に含む。同梱する第三者の部品（Fiji、Cellpose など）と、利用する外部サービス自体の脆弱性は、各開発元の窓口が扱う。

### 12.3 脆弱性の報告

脆弱性は、GitHub の非公開の報告機能で報告する。リポジトリの **Security** タブで **Report a vulnerability** を選択すると、報告者とリポジトリの管理者だけが閲覧できる形で送信できる（[報告フォーム](https://github.com/genellect/cytellect/security/advisories/new)）。Issue、プルリクエスト、ディスカッションなどの公開の場には記載しない。

報告には、次の内容を含める。

- 対象のコミット、または Windows 版のバージョン
- 再現手順
- 想定される影響

再現には、合成データまたは公開データを使用する。

### 12.4 報告後の対応

1. 合理的な報告には、3 日以内に返信する。
2. 影響範囲と深刻度を評価し、報告者と共有する。
3. 非公開のセキュリティアドバイザリで修正し、修正版を配布する。公開サイトとクラウドの機能は本番環境に反映し、Windows 版は Microsoft Store と署名付きの更新で配布する。
4. 配布後にセキュリティアドバイザリを公開し、必要に応じて CVE を取得する。報告者が希望する場合は、謝辞に氏名を記載する。

公開済みのセキュリティアドバイザリは、[一覧](https://github.com/genellect/cytellect/security/advisories)にある。

## 13. 関連文書

| 文書 | 内容 |
|---|---|
| [データ保護と運用](docs/security.md) | データ保護の仕様と運用の詳細 |
| [チーム開発ルール §6](docs/team-development.md#6-研究データの扱い) | 開発の場（Git、CI、ログ、開発用 AI）での研究データと認証情報の取り扱い |
| [更新の署名](docs/release-signing.md) | 署名鍵の作成、登録、交換、失効 |
| [CI の構成](docs/ci.md) | CI のジョブと必須の検査 |
| [プライバシーポリシー](https://cytellect.app/privacy) | 利用者の情報の取り扱い |

## English

Cytellect analyses researchers' unpublished microscopy images on the researcher's own PC. Images, masks, measurements and figures are never stored in the Cytellect cloud, so a compromise of the cloud or the repository cannot reach stored research data.

The implementation and tests of these measures are public in this repository. Each section ends with the corresponding code.

Vulnerabilities are accepted through the [private report form](https://github.com/genellect/cytellect/security/advisories/new) ([12.3 Reporting a vulnerability](#123-reporting-a-vulnerability)).

- [1. Security properties](#1-security-properties)
- [2. Architecture and data flow](#2-architecture-and-data-flow)
- [3. Threats and mitigations](#3-threats-and-mitigations)
- [4. Protection of research data](#4-protection-of-research-data)
- [5. Authentication and access control](#5-authentication-and-access-control)
- [6. Cloud components](#6-cloud-components)
- [7. Application on the PC](#7-application-on-the-pc)
- [8. AI assistance](#8-ai-assistance)
- [9. Cryptography](#9-cryptography)
- [10. Releases and supply chain](#10-releases-and-supply-chain)
- [11. Operations](#11-operations)
- [12. Vulnerability handling](#12-vulnerability-handling)
- [13. Related documents](#13-related-documents)

### 1. Security properties

| Property | Description | Details |
|---|---|---|
| Research data stays on the PC | Images, masks, measurements and figures are stored on the researcher's PC or the lab server. Detection, measurement, statistics and figure rendering run in the same place, and original pixel values are never modified. | [4. Protection of research data](#4-protection-of-research-data) |
| External transmission is minimal | The PC transmits only the information a cloud GPU or AI feature requires, and only when the user invokes that feature. These features are optional; without them, research data never leaves the PC. | [2.2 Information transmitted from the PC](#22-information-transmitted-from-the-pc) |
| The cloud stores no research data | The relay service and the inference server handle research data only while processing it, and neither store nor log it. | [6. Cloud components](#6-cloud-components) |
| A single compromise does not propagate | Data, keys and permissions are separated by component. A compromise of a cloud account, the relay service or the repository cannot reach stored research data or installed applications. | [3. Threats and mitigations](#3-threats-and-mitigations) |
| Components verify each other | Components do not trust each other's input or output. The relay service verifies requests from the PC, the inference server verifies requests from the relay service, and the PC verifies responses from the cloud, each independently. | [6. Cloud components](#6-cloud-components), [7. Application on the PC](#7-application-on-the-pc) |
| AI output does not change an analysis | AI output is never executed as code. An analysis proposal is a validated draft of settings and is not used until the researcher adopts it. Only the shared implementation computes measurements and statistics. | [8. AI assistance](#8-ai-assistance) |
| Updates are verified by signature | The PC runs only updates signed with the maintainer's key. Dependencies and bundled components are pinned by hash. | [10. Releases and supply chain](#10-releases-and-supply-chain) |
| Analysis does not depend on the cloud | Measurement, statistics and figure rendering complete on the PC. Analysis continues when the cloud features are unavailable. | [2. Architecture and data flow](#2-architecture-and-data-flow) |

### 2. Architecture and data flow

#### 2.1 Components

Only the researcher's PC holds research data. Cloud components handle data only for the duration and to the extent that processing requires.

| Component | Role | Data held | Keys and credentials held |
|---|---|---|---|
| Researcher's PC (screen, the server on the PC, analysis worker) | Runs detection, measurement, statistics and figure rendering. | All research data | One device token (when signed in to the cloud) |
| Relay service (Cytellect Worker, running on Cloudflare) | Handles sign-in, user approval and quotas, and relays requests to the cloud GPU and the AI. | Account information and usage records. No research data is stored. | Provider API keys; the key used for hashes and approval-link signatures |
| Inference server (running on Modal) | Runs GPU inference for cell detection (Cellpose). | None. Request content is held in memory only while it is processed. | None |
| Distribution (Microsoft Store, GitHub) | Distributes and updates the application. | Handles no research data. | The update-signing key is held only by the maintainer and the signing environments restricted to `main`. |
| Public site (`cytellect.app`) | Serves the landing page, demo and guides. | Accepts no research images. | None |

#### 2.2 Information transmitted from the PC

The PC transmits data externally only when the user performs one of the following actions. This table lists everything that is transmitted.

| Action | Data transmitted | Destination | Handling at the destination |
|---|---|---|---|
| Cell detection on the cloud GPU | The plane to detect and the detection parameters. For nucleolar detection, the adopted nuclear labels are added. | The inference server, via the relay service | The relay service forwards the body without reading it, and the inference server processes it in memory only. Neither stores or logs it. |
| Analysis consultation with the AI | The research goal, channel names and recorded stains, field names (by default the file name) and records (condition, experimental unit, pair, acquisition date), image dimensions and pixel size, field and group counts, the current analysis settings and the previous proposal, and per-channel display-scaled previews of one representative field (at most 512 px per side; can be disabled in settings) | Anthropic or OpenAI, via the relay service | The relay service neither stores nor logs the body. Requests to OpenAI set `store: false` so that responses are not stored. Transmitted data is not used for model training. Each provider retains data for abuse monitoring for the period its API terms define. |
| Discussion draft generation by the AI | The saved comparison and the experiment purpose. The comparison comprises the summary on screen (heading and points), the metric's name and definition, the stain name, the region, group, run and channel names, group values, differences and confidence intervals, per-experiment values, counts and their breakdown, aggregation and test settings, the researcher's experimental-unit definition and pairing basis, and the test and its p-value. The purpose defaults to the research goal written to the AI in that workspace. | As above | As above |
| Cloud sign-in | The e-mail address and the sign-in code | Resend | Used solely to deliver the sign-in code by e-mail. |

#### 2.3 External services

| Service | Purpose | Information received |
|---|---|---|
| Cloudflare | Running the relay service, recording account information and usage, authenticating the admin page | Requests in transit (not stored), account information and usage records |
| Modal | GPU inference for cell detection | The plane to detect, labels and detection parameters (only while processed) |
| Anthropic, OpenAI | Generating analysis proposals and discussion drafts | The data transmitted to the AI as listed in [2.2 Information transmitted from the PC](#22-information-transmitted-from-the-pc) |
| Resend | Delivering sign-in codes by e-mail | The e-mail address and the sign-in code |
| GitHub | Source code hosting, CI and distribution of the EXE release | Receives no research data. |
| Microsoft Store | Distribution and updates of the Windows release | Receives no research data. |
| Vercel | Serving the public site | Receives no research images. |
| Google Analytics | Web analytics on the public pages | Information about visits to the public pages. Not used in the workspace or the installed application. |

### 3. Threats and mitigations

For each threat considered, the mitigations and the resulting outcome.

| Threat | Mitigations | Outcome |
|---|---|---|
| Takeover of a researcher's cloud account | No research data is stored in the cloud. Quotas have monthly limits. When the maintainer revokes the address, every device is rejected from the next request. | That user's GPU and analysis-proposal quota (up to the monthly limits). Research data cannot be reached. |
| Compromise of the relay service | The relay service stores no bodies. The update-signing key is held outside the relay service. The PC validates proposals as defined settings and requires the researcher's adoption. | Data relayed during the compromise, and tampering with inference results or proposals. Stored research data and application updates cannot be reached. |
| Acquisition of write access to the repository | Updates to `main` are restricted by a ruleset, and only the maintainer can merge. Updates require a signature made with the maintainer's key. | Branches and pull requests. `main` and installed PCs cannot be reached. |
| Replacement of an update in the distribution path | The application verifies the manifest's signature with its built-in public key and checks the installer's hash and size. Only a release newer than the installed one is accepted. | An installer whose signature and hash do not match is not run. |
| Tampering with dependencies and bundled components | Dependencies are pinned by lockfiles with hashes. Bundled components and detection models are verified against SHA-256 at build time and at load time. | A component whose hash does not match is not incorporated. |
| Operations on the screen on the PC from other sites (CSRF, DNS rebinding) | The server on the PC listens only on `127.0.0.1`. It checks the destination, origin and initiator of requests and requires an anti-CSRF header on state-changing requests. The session cookie is not sent with requests from other sites. | Requests from other sites are rejected. |
| Eavesdropping and tampering on the network path | All external traffic is encrypted with TLS. The device token is sent only to the URL that issued it, and redirects are not followed. Updates are verified by signature independently of the network path. | The traffic cannot be read. A tampered update is not run. |
| Brute-forcing sign-in codes | Five incorrect entries invalidate a code, and 20 incorrect entries for one address within a day lock that address for 24 hours. Issuance and verification are rate-limited per IP address and per address. | Attempts are limited to five per code and 20 per address per day. |
| Leak of the relay service's database | Tokens and codes are stored only as hashes. IP addresses and research data are not stored. | E-mail addresses, approval states and usage records. No usable credential or research data is obtained. |
| Incorrect or manipulated AI output | AI output is never executed as code. A proposal is validated as settings consisting only of defined fields and values and is not used until the researcher adopts it. Only the shared implementation computes measurements and statistics. | Analysis settings and values do not change without the researcher's adoption. |
| Malformed or malicious input files | The format, dimensions and size of input are validated. Storage uses internal identifiers, and arrays are loaded only in a form that cannot execute code. The Docker analysis worker runs in an isolated container with no network. | Input that does not meet the format and limits is rejected before analysis. |
| Reads by other users of the same installation | Ownership is verified on every read. The existence of another user's workspace is not disclosed. | Neither the content nor the existence of another user's workspace is obtained. |

### 4. Protection of research data

#### 4.1 Control of transmission

| Item | Description |
|---|---|
| Scope of transmitted data | Data transmitted externally is limited to what [2.2 Information transmitted from the PC](#22-information-transmitted-from-the-pc) lists. Per-object measurements and file paths are not transmitted by any action. Fields the user has excluded are used neither for proposals nor for previews. |
| Consent | The scope transmitted to the AI is displayed, and consent obtained, at cloud sign-in and at the first discussion draft. The AI settings panel also displays the scope (decided on 2026-11-16; the summary, n breakdown, method and purpose were added to discussion drafts on 2026-11-17; background in the [AI assistance redesign](docs/drafts/llm-assistant/plan.md)). |
| Transmission confirmation | Transmission to the AI is accepted only for requests that carry the confirmation given by the user's action. The server on the PC rejects requests without it. |
| Content of detection requests | Detection transmits only the plane to detect, the detection parameters and, for nucleolar detection, the nuclear labels. File names, workspace titles, conditions and other channels are not transmitted. |

Implementation: [`proposals.py`](services/api/src/cytellect_api/proposals.py), [`discussions.py`](services/api/src/cytellect_api/discussions.py), [`cellpose_engine.py`](packages/analysis/src/cytellect_analysis/cellpose_engine.py). Tests: [`test_proposals.py`](tests/test_proposals.py), [`test_result_discussion_api.py`](tests/test_result_discussion_api.py), [`test_cellpose_remote.py`](tests/test_cellpose_remote.py)

#### 4.2 Storage, retention and deletion

| Item | Description |
|---|---|
| Protection at rest | Data and credentials on the PC are stored where only the OS user can read them. Encryption at rest relies on the OS (BitLocker and similar). |
| Integrity of original images | Original pixel values are never modified. Analysis verifies the hash (SHA-256) of an imported image before using it and writes results to a separate area. |
| Retention | The Windows release retains work data until the user deletes it (the EXE release also offers 24-hour automatic deletion at installation). The Docker release expires and deletes it 24 hours after the last action. Manual retention is available only on the researcher's own PC. |
| Deletion | Expiry and deletion block reads immediately. Inputs, arrays, masks, figures and exported files are then removed. |

Implementation: [`config.py`](services/api/src/cytellect_api/config.py), [`db.py`](services/api/src/cytellect_api/db.py), [`regions.py`](services/worker/src/cytellect_worker/regions.py). Tests: [`test_workspace_retention.py`](tests/test_workspace_retention.py)

#### 4.3 Information stored in the cloud

The Cytellect cloud stores no research data. It stores only the following.

| Class | Content | Use |
|---|---|---|
| Account information | E-mail address, approval state and times, hashes of tokens and codes | Authentication, approval and revocation |
| Usage records | Monthly GPU seconds; cost and token counts per analysis proposal | Quota and cost management |

Implementation: [`0004_cloud_access.sql`](services/proposal-worker/migrations/0004_cloud_access.sql), [`auth-store.ts`](services/proposal-worker/src/auth-store.ts), [`store.ts`](services/proposal-worker/src/store.ts)

#### 4.4 Usage measurement

| Item | Description |
|---|---|
| Application telemetry | The installed application and the workspace transmit no usage telemetry. |
| Web analytics on the public site | Web analytics is used only on the public pages of `cytellect.app` (landing page, demo and guides). These pages accept no research images. Advertising use is disabled, and no measurement takes place when the browser signals a tracking opt-out (Do Not Track, Global Privacy Control). |
| Update check | The EXE release consults GitHub's public release list for a newer version (at most once every six hours). No research data or account information is transmitted. |

Implementation: [`LandingAnalytics.tsx`](apps/web/src/components/LandingAnalytics.tsx), [`app_update.py`](services/api/src/cytellect_api/app_update.py)

### 5. Authentication and access control

#### 5.1 Researcher sign-in

| Item | Description |
|---|---|
| Sign-in code | Researchers authenticate with a six-digit code sent by e-mail. Codes are generated from a cryptographically secure random source and sent only to addresses the maintainer has allowed. A code expires after 10 minutes and can be used once. |
| Attempt limits | Five incorrect entries invalidate a code, and 20 incorrect entries for one address within a day lock that address for 24 hours. Attempts are counted per address, so changing IP addresses yields no additional attempts. |
| Rate limits | Code issuance and verification are rate-limited per IP address (per /64 for IPv6) and per address. |

Implementation: [`cloud.ts`](services/proposal-worker/src/cloud.ts), [`auth-store.ts`](services/proposal-worker/src/auth-store.ts), [`mail.ts`](services/proposal-worker/src/mail.ts). Tests: [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts)

#### 5.2 Credentials

| Item | Description |
|---|---|
| Device token | The only credential a signed-in PC holds is a single device token of 256 random bits. The token expires after 90 days without use and is deleted from both the PC and the server on sign-out. |
| Storage and transmission of the device token | The device token is stored in a settings area separate from research data. The server on the PC includes it in neither responses nor logs. The token is sent only to the URL that issued it, and redirects are not followed. |
| Authentication data stored by the server | Tokens are stored only as SHA-256 hashes and codes only as keyed HMAC-SHA256 hashes. IP addresses are not stored, and rate-limit identifiers are also stored as keyed hashes. Secret values are compared in constant time. |
| Provider keys | The Anthropic, OpenAI, Modal and Resend keys are held only as secrets of the relay service. They are never included on the PC, in a release or in a response from the relay service. |
| Revocation | When the maintainer revokes an address, every device signed in with it is rejected from the next request. |

Implementation: [`cloud.ts`](services/proposal-worker/src/cloud.ts), [`http.ts`](services/proposal-worker/src/http.ts), [`cloud_account.py`](services/api/src/cytellect_api/cloud_account.py). Tests: [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts), [`test_cloud_account.py`](tests/test_cloud_account.py)

#### 5.3 Maintainer

| Item | Description |
|---|---|
| Multi-factor authentication | Every cloud account used for operations requires multi-factor authentication with a passkey or an authenticator app. |
| Admin page authentication | The admin page is placed behind Cloudflare Access (Google sign-in). The relay service also independently verifies the access token (JWT): its signature (RS256 only), issuer, audience, expiry and the maintainer's address. |
| Restriction of admin routes | Admin routes respond only on the designated origin. Other entry points such as `workers.dev` do not respond even to a valid token. |
| User approval | New users are approved through a single-use link signed with HMAC (expiring after 7 days). Opening the link alone approves nothing; approval requires a confirming action on the page. |
| Admin page protection | The admin page forbids loading external resources, embedding in other sites and caching. Admin operations are restricted to same-origin requests. |

Implementation: [`access.ts`](services/proposal-worker/src/access.ts), [`cloud.ts`](services/proposal-worker/src/cloud.ts), [`admin-page.ts`](services/proposal-worker/src/admin-page.ts). Tests: [`access.test.ts`](services/proposal-worker/src/access.test.ts), [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts)

#### 5.4 The screen on the PC

| Item | Description |
|---|---|
| Listening address | The server on the PC listens only on `127.0.0.1`. The Docker release publishes its ports only on `127.0.0.1`. |
| Request validation | The Windows release checks the peer address, host name, origin and the browser's request-initiator information (Fetch Metadata) of every request and rejects requests carrying forwarding headers. It additionally requires an anti-CSRF header on state-changing requests, rejecting operations from other sites and through DNS rebinding. The Docker release checks the origin and the anti-CSRF header of state-changing requests. |
| Sessions | Sessions are held in cookies that scripts cannot read and that are not sent with requests from other sites (HttpOnly, SameSite=Strict). The server stores only the SHA-256 of the token. Logging out revokes the session, and the Windows release revokes all sessions when the application exits. |
| Ownership checks | Ownership is verified on every read, and the existence of another user's workspace is not disclosed. An identifier alone confers no permission. |

Implementation: [`local.py`](services/api/src/cytellect_api/local.py), [`app.py`](services/api/src/cytellect_api/app.py), [`desktop.py`](services/api/src/cytellect_api/desktop.py). Tests: [`test_local.py`](tests/test_local.py), [`test_desktop_owner.py`](tests/test_desktop_owner.py)

#### 5.5 Analysis runtime

The Docker analysis worker runs in a container with no network, as a non-root user, on a read-only root filesystem. All privileges (capabilities) are dropped, privilege escalation is disabled, and memory and process count are limited. CI verifies on the real container that outbound connections are denied.

Implementation: [`compose.yaml`](compose.yaml), [`Dockerfile.python`](infra/Dockerfile.python), [`ci.yml`](.github/workflows/ci.yml)

### 6. Cloud components

#### 6.1 Relay service

| Item | Description |
|---|---|
| No body storage | Request and response bodies, codes and tokens are neither stored nor logged. The platform's log collection is disabled. |
| Detection relay | Detection requests and responses are forwarded as streams without reading the body. Only headers describing the content type are forwarded, so the user's device token never reaches the destination. |
| Request validation | Body size is limited per route (authentication 4 KiB, analysis proposals 6 MiB, detection 256 MiB). Proposal requests are validated against a defined schema, and previews are confirmed to be PNG and at most 512 px without decoding pixels. Models and prompt versions are restricted to an allowlist. |
| Replay prevention | A proposal request is accepted once per device for each unique identifier (UUID). Sign-in codes and approval links are consumed exactly once by an atomic update. |
| Outbound requests | Outbound requests do not follow redirects, so a key cannot be sent to another host. Provider errors are replaced with defined codes before they are returned. |
| Use from other origins | There is no setting (CORS) that permits use from other origins, so browsers on other sites cannot use the service. |
| Behaviour on incomplete configuration | When a required setting or key is missing, the affected feature accepts no requests. |

Implementation: [`index.ts`](services/proposal-worker/src/index.ts), [`cloud.ts`](services/proposal-worker/src/cloud.ts), [`http.ts`](services/proposal-worker/src/http.ts), [`openai.ts`](services/proposal-worker/src/openai.ts), [`anthropic.ts`](services/proposal-worker/src/anthropic.ts). Tests: [`index.test.ts`](services/proposal-worker/src/index.test.ts), [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts), [`deployment.test.mjs`](services/proposal-worker/scripts/deployment.test.mjs)

#### 6.2 Quotas and cost

| Item | Description |
|---|---|
| Quotas | GPU seconds and AI cost are subject to per-user monthly limits and an overall monthly budget. Requests exceeding a limit are rejected without being forwarded. |
| Cost reservation | The maximum cost of a request is reserved before the model is called. Reservation is atomic. |
| Cost integrity | If the cost records become inconsistent, requests to the AI are suspended until the inconsistency is resolved. |
| Concurrency | Each user is limited to one GPU request in flight at a time. |

Implementation: [`store.ts`](services/proposal-worker/src/store.ts), [`cloud.ts`](services/proposal-worker/src/cloud.ts). Tests: [`store.test.ts`](services/proposal-worker/src/store.test.ts)

#### 6.3 Inference server

| Item | Description |
|---|---|
| Runtime | A single container processes one request at a time. No persistent storage or memory snapshot is used. The container runs as a non-root user, and its image is pinned by digest. |
| Authentication | Modal proxy authentication is required, and unauthenticated requests are not accepted. |
| Request handling | Request content is held in memory only while it is processed and is never written to a file. Request content, paths and client addresses are not logged. |
| Input validation | The format, size and fields of the input are validated. A request cannot specify a URL, a file path or an arbitrary model. |
| Models | Only public, revision-pinned weights are used, and their SHA-256 is verified before loading. |
| Result verification | The PC accepts a result only when the hashes of the runner, the model and the dependency lock match the installed release. |

Implementation: [`modal_cellpose.py`](infra/modal_cellpose.py), [`server.py`](engines/cellpose/server.py), [`runner.py`](engines/cellpose/runner.py), [`runtime.lock.json`](engines/cellpose/runtime.lock.json), [`cellpose_engine.py`](packages/analysis/src/cytellect_analysis/cellpose_engine.py). Tests: [`test_cellpose_remote.py`](tests/test_cellpose_remote.py)

### 7. Application on the PC

| Item | Description |
|---|---|
| Response protection | Responses forbid caching, content-type sniffing, sending the referrer and embedding in other sites. The screen applies a content security policy that forbids loading external resources and connecting to external hosts. |
| Input acceptance | Accepted input is bounded (100 fields and 2 GiB in total per workspace; a plane of at most 4096×4096 px). Storage uses internal identifiers, and uploaded file names are never used in paths. Paths are verified to lie inside the storage area, and arrays are loaded only in a form that cannot execute code. |
| Communication with the cloud | Communication with the cloud uses HTTPS only. URLs containing credentials, a query or a fragment are not accepted. Redirects are not followed, response size is limited, and only defined fields are passed to the screen. |
| Logging | Access logging is disabled. Request bodies, file names and token values are not logged. |
| Error handling | Errors return defined codes only. Internal exceptions and analysis program output are never returned as they are. |
| Job supervision | Jobs are subject to time and memory limits. When supervision cannot confirm a job's state, the analysis processes are terminated and no result is published. An interrupted job is retried automatically (at most two automatic attempts), and a retry does not overwrite a previous result. |
| Runtime downloads | No code or model is downloaded while an analysis runs. |

Implementation: [`local.py`](services/api/src/cytellect_api/local.py), [`app.py`](services/api/src/cytellect_api/app.py), [`upload_guard.py`](services/api/src/cytellect_api/upload_guard.py), [`db.py`](services/api/src/cytellect_api/db.py), [`cloud_account.py`](services/api/src/cytellect_api/cloud_account.py), [`supervision.py`](services/worker/src/cytellect_worker/supervision.py). Tests: [`test_local.py`](tests/test_local.py), [`test_upload_guard.py`](tests/test_upload_guard.py), [`test_supervision.py`](tests/test_supervision.py)

### 8. AI assistance

| Item | Description |
|---|---|
| No execution of output | AI output is never executed as code. |
| Proposal validation | An analysis proposal is validated on the PC as structured settings consisting only of defined fields and values. Proposals containing undefined fields, or URLs or code-like text in their explanations, are rejected. The channel set must match what was transmitted, and a proposal can neither alter a recorded stain nor establish an unrecorded one. |
| Adoption | A proposal is a draft and is not used until the researcher adopts it. |
| Separation of computation | After adoption, measurements and statistics are still computed by the shared implementation, irrespective of the proposal's content. A proposal never produces values. |
| State re-check | If workspace data changes, or the workspace expires or is deleted, during the external call, the resulting proposal is discarded. |
| Discussion drafts | A discussion draft is validated for structure only and saved as text with its comparison. It does not modify analysis settings or values. |

Implementation: [`proposal_validation.py`](packages/analysis/src/cytellect_analysis/proposal_validation.py), [`proposal_contracts.py`](packages/analysis/src/cytellect_analysis/proposal_contracts.py), [`discussion_validation.py`](packages/analysis/src/cytellect_analysis/discussion_validation.py), [`proposals.py`](services/api/src/cytellect_api/proposals.py). Tests: [`test_proposals.py`](tests/test_proposals.py), [`test_result_discussion.py`](tests/test_result_discussion.py)

### 9. Cryptography

| Purpose | Method | Custody of keys and secrets |
|---|---|---|
| Protection in transit | TLS | Each service's certificates. |
| Device token | 256 bits from a cryptographically secure random source. The server stores only the SHA-256 hash. | The settings area on the PC |
| Sign-in code | Only a keyed HMAC-SHA256 hash is stored. | The hashing key is held as a secret of the relay service. |
| Approval link | Signed with HMAC-SHA256. Comparison is in constant time. | As above |
| Maintainer's access token | The RS256 signature is verified with Cloudflare Access's public keys. | The private key is held by Cloudflare Access. |
| Update signature | An OpenSSH-format Ed25519 signature (SHA-512). The public key is built into the application. | The private key is held only by the maintainer and in the signing environments restricted to `main`. |
| Integrity verification | SHA-256. Applied to the installer, bundled components, detection models, dependency packages and imported images. | Expected hashes are recorded in the repository and in the signed manifest. |
| Encryption at rest | OS facilities (BitLocker and similar) | Managed by the user's OS. |

### 10. Releases and supply chain

#### 10.1 Update signing and verification

| Item | Description |
|---|---|
| Microsoft Store release (Windows 11) | Signed by Microsoft; installed and updated by the Microsoft Store. Submissions to the Store are limited to the latest `main` commit approved by the maintainer. |
| Update signature | Each EXE release carries a manifest stating the version, installer name, SHA-256, size, source commit and time of issue, with a signature made with the maintainer's Ed25519 key. |
| Update verification | The application verifies the manifest's signature with its built-in public key before fetching the installer. The installer runs only when the release is newer than the installed one and its SHA-256 and size match the manifest. Downloads are restricted to GitHub hosts over HTTPS, and redirect targets are checked as well. The hash reported by the distribution host is not a basis of trust. |
| Update rollback | If the new version fails to start, the application restores the database copy taken before the switch and the previous version. |
| First installation | A first installation of the EXE release can also be verified against the same manifest ([steps, in Japanese](docs/install-windows.ja.md#2-ダウンロードと確認)). |

Implementation: [`update_signature.py`](services/api/src/cytellect_api/update_signature.py), [`app_update.py`](services/api/src/cytellect_api/app_update.py). Tests: [`test_update_signature.py`](tests/test_update_signature.py), [`test_app_update.py`](tests/test_app_update.py)

#### 10.2 Release procedure

| Item | Description |
|---|---|
| Signing key custody | The signing key is held only by the maintainer and in dedicated signing environments restricted to `main`. Procedures for creating, registering, rotating and revoking the key are defined in [release signing](docs/release-signing.md) (in Japanese). |
| Release approval | Manual releases require the maintainer's approval. When the maintainer has enabled automatic EXE distribution, only versions that have passed CI and the distribution tests on protected `main` are published. |
| Commit verification | A release is built from a single commit, which is re-checked at each stage. The commit must be in the history of `main`; runs originating from forks and reuse of a tag are refused. |
| Verification of published files | Published files must match the tested files in size and hash. |

Implementation: [`local-release.yml`](.github/workflows/local-release.yml), [`windows-store-release.yml`](.github/workflows/windows-store-release.yml), [`windows_exe_release.cjs`](scripts/windows_exe_release.cjs). Tests: [`windows_exe_release.test.cjs`](scripts/windows_exe_release.test.cjs)

#### 10.3 Dependencies and bundled components

| Item | Description |
|---|---|
| Dependency pinning | Python and JavaScript dependencies are pinned by lockfiles with hashes. |
| Verification of bundled components | The bundled Fiji, detection models and Python runtime are verified against SHA-256 hashes at build time. |
| Inspection of releases | Releases are scanned for credentials at build time, and the build fails if any is found. |
| Bill of materials and licences | CI generates a software bill of materials (SBOM) for dependencies. For components whose licences require source to be provided, the corresponding source is attached to the release ([licensing and distribution](docs/oss.md), in Japanese). |

Implementation: [`uv.lock`](uv.lock), [`pnpm-lock.yaml`](pnpm-lock.yaml), [`runtime.lock.json`](engines/fiji/runtime.lock.json), [`runtime.lock.json`](engines/cellpose/runtime.lock.json), [`build_windows_installer.py`](scripts/build_windows_installer.py), [`sbom.py`](scripts/sbom.py)

#### 10.4 Repository and CI

| Item | Description |
|---|---|
| Merging changes | Every change is made through a pull request and is merged to `main` by the maintainer after the required CI succeeds and the change is reviewed. Updates to `main` are restricted by a ruleset, and only the maintainer can merge. |
| Review | A change authored by anyone other than the maintainer requires approval by at least one member other than its author. Review confirms the impact on production, the impact on pixel values, measurements, statistics and figures, and the absence of private data and credentials. |
| Secret detection | A hash-verified gitleaks scans the full Git history of `main` and of every pull request. |
| Static analysis and dependency audits | CodeQL (workflows, JavaScript/TypeScript, Python) runs on pull requests, on `main` and weekly. Dependency vulnerability audits (pip-audit, pnpm audit) run in CI. |
| Workflow permissions | The token granted to workflows is read-only by default. Runs originating from forks receive neither write permission nor secrets. |
| Separation of environments | Production credentials are not used in development. Runtime data is stored outside the source tree. Development environments used by several people reject uploads other than registered public files by checking their hash (SHA-256). |
| Test data | Tests, evaluation and the public demo use public images whose source, redistribution terms and hashes are recorded. Private research data is never included in Git, CI or public places. |

Implementation: [`ci.yml`](.github/workflows/ci.yml), [`codeql.yml`](.github/workflows/codeql.yml), [`scan_secrets.py`](scripts/scan_secrets.py), [`security-tools.lock.json`](scripts/security-tools.lock.json), [`public_uploads.py`](services/api/src/cytellect_api/public_uploads.py). Tests: [`test_scan_secrets.py`](tests/test_scan_secrets.py), [`test_public_uploads.py`](tests/test_public_uploads.py)

### 11. Operations

#### 11.1 Authority

| Role | Authority |
|---|---|
| Maintainer | Merges to `main`, production releases and distribution, contracts and settings of external services, approval and revocation of users, and vulnerability handling. |
| Development members | Implement assigned changes, open pull requests and review other members' changes. They hold no authority to merge to `main` or to distribute. |
| AI agents | Implement and verify within the requester's instructions. Merging to `main` and production release are limited to cases the maintainer has explicitly instructed for the specific target. |

#### 11.2 Revocation and recovery

| Event | Response |
|---|---|
| Misuse of a user account | The maintainer revokes the address. Every device signed in with it is rejected from the next request. |
| Leak of a credential | The credential is invalidated and reissued immediately. |
| Leak of the key used for hashes and signatures | The key is rotated. Rotation invalidates unused sign-in codes and approval links. |
| Leak or loss of the update-signing key | The revocation and rotation procedures defined in [release signing](docs/release-signing.md) are followed. |
| Fault in the relay service | The service is rolled back to a previous version. |
| Inclusion of private data or credentials | The maintainer is notified immediately. History is not rewritten unilaterally; the response is agreed first. |

#### 11.3 What the user manages

| Area | What Cytellect does | What the user does |
|---|---|---|
| Storage of research data | The application stores research data where only the OS user can read it. | Management of the PC and OS accounts, disk encryption and backup |
| Cloud features | Authentication, relay, quota management and display of the transmission scope | The decision to use a feature and consent to the transmission scope |
| Application updates | Provision of signed updates | Applying updates |
| Accounts | Approval, revocation and protection of authentication data | Management of the e-mail address and signing out of devices no longer in use |

### 12. Vulnerability handling

#### 12.1 Supported versions

| Version | Security fixes |
|---|---|
| The Microsoft Store release | Provided (updated to the latest version by the Microsoft Store) |
| The latest EXE release | Provided |
| `main` (`cytellect.app` and the cloud features) | Provided |
| Earlier EXE releases | Not provided (move to the latest release through the in-app update) |

#### 12.2 Scope

This repository's code, the Windows releases (Microsoft Store and EXE), the Docker release, `cytellect.app`, the relay service and the inference server are in scope. Issues arising from how Cytellect configures or uses an external service are also in scope. Vulnerabilities in bundled third-party components (Fiji, Cellpose and others) and in the external services themselves are handled by their respective maintainers.

#### 12.3 Reporting a vulnerability

Report vulnerabilities through GitHub's private reporting feature. Selecting **Report a vulnerability** under the repository's **Security** tab submits a report visible only to the reporter and the repository maintainers ([report form](https://github.com/genellect/cytellect/security/advisories/new)). Do not describe vulnerabilities in public places such as issues, pull requests or discussions.

Include the following in a report.

- The affected commit, or the version of the Windows release
- Reproduction steps
- The expected impact

Use synthetic or public data for reproduction.

#### 12.4 Response to a report

1. Reasonable reports receive a reply within three days.
2. The affected scope and severity are assessed and shared with the reporter.
3. The issue is fixed in a private security advisory and the fixed version is released. The public site and cloud features are deployed to production, and the Windows releases are distributed through the Microsoft Store and a signed update.
4. After the release, the security advisory is published and a CVE is requested where appropriate. The reporter is credited by name on request.

Published security advisories are available in the [list](https://github.com/genellect/cytellect/security/advisories).

### 13. Related documents

| Document | Content |
|---|---|
| [Data protection and operations](docs/security.md) | The data-protection specification and operating details |
| [Team development rules, section 6](docs/team-development.md#6-research-data) | The handling of research data and credentials in development (Git, CI, logs, development AI) |
| [Release signing](docs/release-signing.md) | Creating, registering, rotating and revoking the signing key (in Japanese) |
| [CI configuration](docs/ci.md) | CI jobs and required checks (in Japanese) |
| [Privacy policy](https://cytellect.app/privacy) | The handling of user information (in Japanese) |
