# セキュリティポリシー

Cytellect のセキュリティ設計、サポート対象の版、脆弱性の報告手順を定める。脆弱性の報告手順は「[脆弱性の報告](#脆弱性の報告)」に、英語版は「[English](#english)」にある。

## 概要

Cytellect は、未発表の顕微鏡画像を研究者の PC 上で解析する。セキュリティ設計は、次の原則に基づく。

| 原則 | 内容 | 参照 |
|---|---|---|
| データの所在 | 画像、輪郭、測定値、図は研究者の PC または研究室のサーバーに保存し、Cytellect のクラウドには保存しない。検出、測定、統計、作図も同じ場所で実行する。 | [研究データ](#研究データ) |
| 送信の最小化 | PC の外部への送信は、利用者がクラウド GPU または AI の機能を実行した場合に限り、その処理に必要な範囲にとどめる。これらの機能は任意であり、使用しなければ研究データは PC の外部に出ない。 | [研究データ](#研究データ) |
| 影響範囲の限定 | データ、鍵、権限を構成要素ごとに分離する。クラウドまたはリポジトリが侵害されても、保存された研究データと導入済みのアプリには到達できない。 | [構成と信頼境界](#構成と信頼境界)、[侵害時の影響範囲](#侵害時の影響範囲) |
| 多層の検証 | 構成要素は互いの入出力を信頼せず、それぞれが独立に検証する。Worker は PC の要求を、推論サーバーは Worker の要求を、PC はクラウドの応答を検証する。 | [クラウドの中継](#クラウドの中継cytellect-worker)、[PC 上のアプリ](#pc-上のアプリ) |
| AI 出力の非実行 | LLM の出力はコードとして実行しない。解析の提案は検証済みの設定の下書きとして扱い、研究者が採用するまで解析に使用しない。 | [AI による解析支援](#ai-による解析支援) |
| 配布物の検証 | PC は、管理者の鍵で署名された更新だけを実行する。依存と同梱物はハッシュで固定する。 | [配布物の完全性とサプライチェーン](#配布物の完全性とサプライチェーン) |

## 構成と信頼境界

研究データを保持するのは研究者の PC だけである。クラウド側の構成要素は、処理に必要な期間と範囲でのみデータに触れる。

| 構成要素 | 役割 | 保持するデータ | 保持する鍵と資格情報 |
|---|---|---|---|
| 研究者の PC（画面、ローカル API、解析ワーカー） | 検出、測定、統計、作図を実行する。 | 研究データのすべて | 端末トークン 1 つ（クラウドにログインした場合） |
| Cytellect Worker（Cloudflare Workers） | ログイン、利用の承認、利用枠の管理を行い、クラウド GPU と AI への要求を中継する。 | アカウントと利用量の記録。研究データは保存しない。 | 送信先の API キー、ハッシュと承認リンクの署名に使用する鍵 |
| 推論サーバー（Modal） | 細胞の検出（Cellpose）の GPU 推論を実行する。 | なし。要求の内容は処理中のみメモリ上に保持する。 | なし |
| LLM の提供元（Anthropic、OpenAI） | 解析の提案と考察の下書きを生成する。 | 各社の API のデータ取り扱いによる。 | なし |
| メール送信（Resend） | ログインコードを送信する。 | メールアドレスとログインコード | なし |
| 配布（Microsoft Store、GitHub Releases） | アプリを配布し、更新する。 | 研究データを扱わない。 | 更新の署名鍵は、管理者と `main` に限定した署名環境だけが保持する。 |
| 公開サイト（`cytellect.app`） | LP、デモ、ガイドを提供する。 | 研究画像を受け付けない。 | なし |

## 現行の対策

### 研究データ

画像、輪郭（マスク）、測定表、図は、研究者の PC または研究室のサーバーの非公開領域に保存する。検出、測定、統計、作図は同じ場所で実行し、原画像の画素値は変更しない。

PC の外部へ送信するのは、利用者が次の操作を実行した場合に限る。

| 操作 | 送信する情報 | 送信先 | 送信先での取り扱い |
|---|---|---|---|
| クラウド GPU による細胞の検出 | 検出対象の 1 プレーンと検出条件。核小体の検出では、採用済みの核のラベルを加える。 | Cytellect Worker 経由で Modal | Worker は本文を読み取らずに転送し、推論サーバーはメモリ上でのみ処理する。いずれも保存せず、ログに記録しない。 |
| AI への解析の相談 | 研究の目的、チャンネル名と記録した染色、視野の名前（既定ではファイル名）と記録（条件、実験回、組、取得日）、画像の寸法と画素サイズ、視野と群の数、現在の解析設定と前回の提案、代表的な 1 視野のチャンネルごとの縮小画像（一辺 512 px 以下。設定で無効にできる）。 | Cytellect Worker 経由で Anthropic または OpenAI | Worker は本文を保存せず、ログに記録しない。OpenAI には応答を保存しない設定（`store: false`）で送信する。送信したデータはモデルの学習に使用されない。各提供元は、不正利用の監視などの目的で、データを一定期間保持する場合がある。 |
| AI による考察の生成 | 保存した比較結果と実験の目的。比較結果は、画面のまとめ（見出しと要点）、指標の名前と定義、染色名、領域・群・実験回・チャンネルの名前、群ごとの値、差と信頼区間、実験回ごとの値、n とその内訳、集計と検定の方法、研究者が記述した実験単位の定義と対応の根拠、検定と p 値からなる。目的の初期値は、そのワークスペースで AI への相談に記述した研究の目的である。 | 同上 | 同上 |
| クラウドへのログイン | メールアドレスとログインコード | Resend | ログインコードのメール送信にのみ使用する。 |

送信、保管、保持に関する取り扱いは、次のとおりである。

| 項目 | 取り扱い |
|---|---|
| 送信しない情報 | 原画像、輪郭、核ごとの測定値、ファイルのパスは、上表に記載したものを除き送信しない。利用者が除外した視野は、提案にも縮小画像にも使用しない。 |
| 同意 | AI への送信範囲は、クラウドへのログイン時と最初の考察の生成時に画面に表示し、同意を得たうえで送信する。送信範囲は AI の設定画面にも表示する（2026-11-16、オーナーの判断。2026-11-17 に、考察の生成へまとめ・n の内訳・方法・目的を追加した。経緯は [LLM による解析支援の見直し](docs/drafts/llm-assistant/plan.md)）。 |
| 送信の確認 | AI への送信は、利用者の操作による確認を伴う要求だけを受け付ける。確認を伴わない要求は、ローカル API が拒否する。 |
| 利用状況の計測 | 導入したアプリと作業画面は、利用状況（テレメトリ）を送信しない。アクセス解析を使用するのは `cytellect.app` の公開ページ（LP、デモ、ガイド）に限り、これらのページは研究画像を受け付けない。 |
| 更新の確認 | EXE 版は、GitHub の公開リリース一覧を参照して更新の有無を確認する（最大 6 時間に 1 回）。研究データとアカウント情報は送信しない。 |
| 通信の保護 | 外部との通信は、すべて TLS で暗号化する。 |
| 保存時の保護 | PC 上のデータと資格情報は、OS の利用者だけが読み取れる場所に保存する。保存時の暗号化は、OS の機能（BitLocker など）による。 |
| 原画像の完全性 | 原画像の画素値は変更しない。解析は、取り込んだ画像の SHA-256 を照合してから使用し、結果は別の領域に書き出す。 |
| 保持期間 | Windows 版は、利用者が削除するまで作業データを保持する（EXE 版は、導入時に 24 時間での自動削除を選択できる）。Docker 版は、最後の操作から 24 時間で失効させて削除する。研究者自身の PC に限り、手動での保持を選択できる。 |
| 削除 | 失効と削除は、読み出しをただちに遮断する。その後、入力、配列、マスク、図、書き出したファイルを削除する。 |
| クラウド側の保存情報 | Cytellect のクラウドは研究データを保存しない。保存するのは、アカウントの記録（メールアドレス、承認の状態と日時、トークンとコードのハッシュ）と、利用量の記録（月ごとの GPU の秒数、解析提案ごとの費用とトークン数）に限る。 |

### 侵害時の影響範囲

単一の構成要素が侵害されても被害が波及しないよう、データ、鍵、権限を分離している。

| 侵害の対象 | 到達できる範囲 | 到達できない範囲 |
|---|---|---|
| 研究者のクラウドのアカウント | その利用者の GPU と解析提案の利用枠（月ごとの上限まで） | 研究データ（クラウドに保存していない） |
| Cytellect Worker | 侵害されている間に中継されるデータの閲覧と、推論結果・提案の改ざん | 保存された研究データ、アプリの更新（署名鍵は別の場所に保管する） |
| リポジトリへの書き込み権限 | ブランチと PR | `main` への反映（管理者によるマージを要する）、導入済みの PC（更新には管理者の鍵による署名を要する） |

### 認証とアクセス制御

| 対象 | 対策 |
|---|---|
| ログインコード | 研究者は、メールで送信する 6 桁のコードで認証する。コードは暗号論的乱数で生成し、管理者が許可したアドレスにのみ送信する。コードは 10 分で失効し、1 回だけ使用できる。 |
| 試行の制限 | 5 回の誤入力でコードを無効にし、同一アドレスで 1 日 20 回の誤入力があれば 24 時間ロックする。試行回数はアドレス単位で数えるため、IP アドレスを変えても試行回数は増えない。加えて、コードの送信と検証の回数を、IP アドレス単位（IPv6 は /64 単位）とアドレス単位で制限する。 |
| 端末トークン | ログインした PC が保持するのは、256 bit の乱数による端末トークン 1 つに限る。トークンは 90 日間使用しなければ失効し、サインアウト時に PC とサーバーの双方から削除する。PC は、トークンを発行元の URL にのみ送信し、リダイレクトには従わない。 |
| サーバーが保存する認証情報 | トークンは SHA-256、コードは鍵付きの HMAC-SHA256 によるハッシュのみを保存する。IP アドレスは保存せず、回数制限の識別子も鍵付きのハッシュとして保存する。秘密値の照合は、定数時間で行う。 |
| 失効 | 管理者がアドレスを失効させると、そのアドレスでログインしたすべての端末を次の要求から拒否する。 |
| 送信先の鍵 | Anthropic、OpenAI、Modal、Resend の鍵は、Cytellect Worker のシークレットとしてのみ保持する。PC、配布物、Worker の応答には含めない。配布物は、ビルド時に資格情報のパターンを走査する。 |
| 管理者の認証 | 運用に使用するクラウドのアカウントは、すべてパスキーまたは認証アプリによる多要素認証を必須とする。管理画面は Cloudflare Access（Google ログイン）の背後に置き、Worker も JWT の署名（RS256 に固定）、発行者、対象、有効期限、管理者のアドレスを独自に検証する。管理用の経路は指定したオリジンでのみ応答し、`workers.dev` などの別の入口からは、有効なトークンがあっても応答しない。 |
| 利用者の承認 | 新規の利用者は、HMAC で署名した 1 回限りのリンク（7 日で失効）で承認する。リンクを開いただけでは承認されず、承認には画面での確認の操作を要する。 |

### クラウドの中継（Cytellect Worker）

Cytellect Worker は、認証と利用枠を検証したうえで要求を中継する。研究データを含む本文は、保存も記録もしない。

| 対策 | 内容 |
|---|---|
| 本文の非保存 | 要求と応答の本文、コード、トークンを保存せず、ログに記録しない。Workers の observability（ログの収集）は無効にしている。 |
| 検出の中継 | 検出の要求と応答は、本文を読み取らずにストリームとして転送する。送信先へ転送するヘッダーは content-type と accept に限り、利用者の端末トークンを送信先に渡さない。 |
| 要求の検証 | 本文のサイズを経路ごとに制限する（認証 4 KiB、解析の提案 6 MiB、検出 256 MiB）。提案の要求はスキーマで検証し、縮小画像は PNG であることと 512 px 以下であることを、画素を復号せずにヘッダーで確認する。モデルとプロンプトの版は、許可リストに限る。 |
| 再送の防止 | 提案の要求は、端末ごとに一意の Idempotency-Key（UUID）を 1 回だけ受理する。ログインコードと承認リンクは、原子的な更新で 1 回だけ消費する。 |
| 外部への要求 | 外部への要求はリダイレクトに従わないため、鍵が別のホストに送信されることはない。提供元のエラーは、定義済みのコードに置き換えて返す。 |
| 利用枠と費用 | GPU の秒数と AI の費用には、利用者ごと・月ごとの上限と、全体の月間予算を設ける。モデルの呼び出し前に最大費用を予約し、上限を超える要求は送信先に転送せずに拒否する。GPU の要求は、利用者ごとに同時に 1 件に限る。 |
| ブラウザからの保護 | CORS のヘッダーを返さないため、他のオリジンのブラウザからは利用できない。管理画面は、`default-src 'none'` と `frame-ancestors 'none'` を含む CSP を適用し、キャッシュを禁止する。管理の操作は、同一オリジンからの JSON の要求に限る。 |
| 設定不備時の動作 | 必要な設定または鍵が欠けている場合、該当する機能は要求を受け付けない。 |

### 推論サーバー

| 対策 | 内容 |
|---|---|
| 実行環境 | 単一のコンテナで、同時に 1 件の要求だけを処理する。永続ボリュームとメモリスナップショットは使用しない。コンテナは非 root で動作し、イメージはダイジェストで固定する。 |
| 認証 | Modal の proxy 認証を必須とし、認証のない要求を受け付けない。 |
| 要求の取り扱い | 要求の内容は処理中のみメモリ上に保持し、ファイルに書き込まない。要求の内容、パス、クライアントのアドレスをログに記録しない。 |
| 入力の検証 | 入力の形式、サイズ、項目を検証する。要求で URL、ファイルのパス、任意のモデルを指定することはできない。 |
| モデル | 公開され、リビジョンを固定した重みだけを使用し、SHA-256 を検証してから読み込む。 |
| 結果の検証 | PC は、ランナー、モデル、依存のロックのハッシュがリリースと一致する結果だけを受理する。 |

### PC 上のアプリ

| 対策 | 内容 |
|---|---|
| 待ち受け | ローカルのサーバーは `127.0.0.1` でのみ待ち受ける。Docker 版は、ポートを `127.0.0.1` にのみ公開する。 |
| 要求の検証 | Windows 版は、要求ごとに接続元、Host、Origin、Fetch Metadata を照合し、転送を示すヘッダーを含む要求を拒否する。状態を変更する要求には CSRF ヘッダーも要求し、他のサイトと DNS リバインディングによる操作を拒否する。Docker 版は、状態を変更する要求の Origin と CSRF ヘッダーを照合する。 |
| セッション | セッションは HttpOnly かつ SameSite=Strict の Cookie で保持し、サーバーにはトークンの SHA-256 だけを保存する。ログアウトでセッションを失効させる。Windows 版は、アプリの終了時にすべてのセッションを失効させる。 |
| 所有者の確認 | 読み出しのたびに所有者を確認し、他者のワークスペースについては存在の有無も返さない。識別子だけでは権限を与えない。 |
| 応答ヘッダー | 応答には `Cache-Control: no-store`、`X-Content-Type-Options: nosniff`、`Referrer-Policy: no-referrer`、`X-Frame-Options: DENY` を付与する。画面には、`frame-ancestors 'none'`、`object-src 'none'`、`connect-src 'self'` を含む CSP を適用する。 |
| ログ | アクセスログは無効にしている。要求の本文、ファイル名、トークンの値をログに記録しない。エラーは、定義済みのコードだけを返す。 |
| 入力の受け入れ | 受け入れる入力に上限を設ける（1 ワークスペースあたり 100 視野、合計 2 GiB。1 プレーンは 4096×4096 px まで）。保存には内部の識別子を使用し、アップロードされたファイル名をパスに使用しない。パスは保存領域の内側にあることを検証し、配列は pickle を無効にして読み込む。 |
| クラウドとの通信 | クラウドの URL は HTTPS に限り（試験用のループバックを除く）、資格情報、クエリ、フラグメントを含む URL を受け付けない。応答のサイズを制限し、定義済みの項目だけを画面に渡す。端末トークンは研究データとは別の設定領域に保存し、ローカル API は応答にもログにも含めない。 |
| 解析ワーカーの隔離 | Docker 版の解析ワーカーは、ネットワークを持たない、非 root かつ読み取り専用のコンテナで動作する。すべての capability を削除し、権限の昇格を禁止し、メモリとプロセス数を制限する。CI は、実際のコンテナで外部への通信が拒否されることを検証する。 |
| ジョブの監視 | ジョブには実行時間とメモリの上限を設ける。監視が状態を確認できない場合は、解析のプロセスを停止し、結果を公開しない。 |

### AI による解析支援

| 対策 | 内容 |
|---|---|
| 出力の非実行 | LLM の出力は、コードとして実行しない。 |
| 提案の検証 | 解析の提案は、定義済みの項目と値だけからなる設定として PC 上で検証する。未定義の項目を含む提案と、説明文に URL やコードに類する文字列を含む提案は拒否する。チャンネルの構成は送信した内容と一致しなければならず、記録された染色を提案が変更することも、記録のない染色を提案が定めることもできない。 |
| 採用の要否 | 提案は下書きであり、研究者が採用するまで解析に使用しない。 |
| 計算の分離 | 採用後も、測定と統計は提案の内容にかかわらず共通の実装が計算する。提案が数値を生成することはない。 |
| 状態の再確認 | 外部の呼び出しの間に、ワークスペースのデータが変更された場合と、ワークスペースが失効または削除された場合は、その提案を破棄する。 |
| 考察の下書き | 考察の下書きは、形式のみを検証し、文章として比較結果に付して保存する。解析の設定と数値は変更しない。 |

### 配布物の完全性とサプライチェーン

| 対象 | 対策 |
|---|---|
| Microsoft Store 版（Windows 11） | Microsoft が署名し、導入と更新は Microsoft Store が行う。Store への提出は、管理者が承認した `main` の最新のコミットに限る。 |
| 更新の署名 | EXE 版の各リリースには、版、インストーラーの名前、SHA-256、サイズ、ソースのコミット、発行時刻を記載した manifest と、管理者の Ed25519 鍵による OpenSSH 形式の署名（名前空間 `cytellect-update`）を付す。 |
| 更新の検証 | アプリは、組み込んだ公開鍵で manifest の署名を検証してから、インストーラーを取得する。現在より新しい版であり、インストーラーの SHA-256 とサイズが manifest と一致する場合にのみ実行する。取得元は HTTPS の GitHub のホストに限り、リダイレクト先も照合する。GitHub が示すダイジェストは、信頼の根拠にしない。 |
| 更新の切り戻し | 新しい版が起動しない場合は、切り替え前に取得したデータベースの写しと、以前の版に戻す。 |
| 初回導入 | EXE 版の最初の導入でも、同じ manifest でダウンロードを検証できる（[手順](docs/install-windows.ja.md#2-ダウンロードと確認)）。 |
| 署名鍵の保管 | 署名鍵は、管理者の手元と、`main` に限定した専用の GitHub Actions 環境にのみ保管する。手動配布は管理者の承認を要する。管理者が有効にした EXE 自動配布では、保護された `main` 上で CI と配布試験に合格した版だけを公開する。 |
| リリースの手順 | リリースは単一のコミットから作成し、各段階でそのコミットを照合する。コミットは `main` の履歴に含まれなければならず、フォークに由来する実行とタグの再利用は拒否する。公開する資産は、サイズとダイジェストが試験済みのファイルと一致しなければならない。 |
| 依存の固定 | Python と JavaScript の依存は、ハッシュ付きのロックファイルで固定する。同梱する Fiji、検出モデル、Python の実行環境は、ビルド時に SHA-256 で照合する。 |
| 実行時の取得 | 解析の実行中に、コードやモデルをダウンロードしない。 |
| リポジトリの保護 | `main` はルールセットで保護し、マージできるのは管理者に限る。workflow の `GITHUB_TOKEN` は既定で読み取り専用とし、`pull_request_target` は使用しない。 |
| 自動検査 | ハッシュを検証した gitleaks で、`main` と各 PR の Git の全履歴を走査して秘密情報を検出する。CodeQL（Actions、JavaScript/TypeScript、Python）を PR、`main`、週次で実行する。依存の脆弱性監査（pip-audit、pnpm audit）と SBOM（CycloneDX）の生成を CI で実行する。 |

## サポート対象の版

| 版 | セキュリティ修正 |
|---|---|
| Microsoft Store 版 | 提供する（Microsoft Store が最新版に更新する） |
| EXE 版の最新のリリース | 提供する |
| `main`（`cytellect.app` とクラウド機能） | 提供する |
| 上記より前の EXE 版 | 提供しない（アプリ内更新で最新版に移行する） |

## 対象範囲

このリポジトリのコード、Windows 版（Microsoft Store 版と EXE 版）、Docker 版、`cytellect.app`、Cytellect Worker、推論サーバーを対象とする。Cytellect による外部サービスの設定と利用方法に起因する問題も対象に含む。同梱する第三者の部品（Fiji、Cellpose など）と、利用する外部サービス（Cloudflare、Modal、Anthropic、OpenAI、Resend、GitHub、Vercel、Microsoft Store）自体の脆弱性は対象外とし、各開発元の窓口が扱う。

## 脆弱性の報告

脆弱性は、GitHub の非公開の報告機能で報告する。リポジトリの **Security** タブで **Report a vulnerability** を選択すると、報告者とリポジトリの管理者だけが閲覧できる形で送信できる（[報告フォーム](https://github.com/genellect/cytellect/security/advisories/new)）。Issue、PR、ディスカッションなどの公開の場には記載しない。

報告には、次の内容を含める。

- 対象のコミット、または Windows 版のバージョン
- 再現手順
- 想定される影響

再現には、合成データまたは公開データを使用する。

## 報告後の対応

1. 合理的な報告には、3 日以内に返信する。
2. 影響範囲と深刻度を評価し、報告者と共有する。
3. 非公開の Security Advisory で修正し、修正版を配布する。公開サイトとクラウド機能は本番環境に反映し、Windows 版は Microsoft Store と署名付きの更新で配布する。
4. 配布後に Security Advisory を公開し、必要に応じて CVE を取得する。報告者が希望する場合は、謝辞に氏名を記載する。

公開済みの勧告は [Security Advisories](https://github.com/genellect/cytellect/security/advisories) にある。

## 開発における研究データの取り扱い

開発の場（Git、CI、ログ、開発用 AI）における研究データと認証情報の取り扱いは、[チーム開発ルール §6](docs/team-development.md#6-研究データの扱い)で定める。データ保護の仕様と運用の詳細は、[データ保護と運用](docs/security.md)にある。

## English

This policy defines Cytellect's security design, supported versions and vulnerability reporting procedure. The reporting procedure is described in [Reporting a vulnerability](#reporting-a-vulnerability); the Japanese version is at the [top of this document](#セキュリティポリシー).

### Overview

Cytellect analyses researchers' unpublished microscopy images on the researcher's own PC. Its security design rests on the following principles.

| Principle | Description | Reference |
|---|---|---|
| Data locality | Images, masks, measurements and figures are stored on the researcher's PC or the lab server, never in the Cytellect cloud. Detection, measurement, statistics and figure rendering run in the same place. | [Research data](#research-data) |
| Minimal transmission | Data leaves the PC only when the user invokes a cloud GPU or AI feature, and only to the extent that feature requires. These features are optional; without them, research data never leaves the PC. | [Research data](#research-data) |
| Limited blast radius | Data, keys and permissions are separated by component. A compromise of the cloud or the repository cannot reach stored research data or installed applications. | [Architecture and trust boundaries](#architecture-and-trust-boundaries), [Impact of a compromise](#impact-of-a-compromise) |
| Layered verification | Components do not trust each other's input or output; each verifies independently. The Worker verifies requests from the PC, the inference server verifies requests from the Worker, and the PC verifies responses from the cloud. | [Cloud relay](#cloud-relay-cytellect-worker), [Application on the PC](#application-on-the-pc) |
| No execution of AI output | LLM output is never executed as code. An analysis proposal is treated as a validated draft of settings and is not used until the researcher adopts it. | [AI assistance](#ai-assistance) |
| Verified distribution | The PC runs only updates signed with the maintainer's key. Dependencies and bundled components are pinned by hash. | [Release integrity and supply chain](#release-integrity-and-supply-chain) |

### Architecture and trust boundaries

Only the researcher's PC holds research data. Cloud components handle data only for the duration and to the extent that processing requires.

| Component | Role | Data held | Keys and credentials held |
|---|---|---|---|
| Researcher's PC (screen, local API, analysis worker) | Runs detection, measurement, statistics and figure rendering. | All research data | One device token (when signed in to the cloud) |
| Cytellect Worker (Cloudflare Workers) | Handles sign-in, user approval and quotas, and relays requests to the cloud GPU and the AI. | Account and usage records. No research data is stored. | Provider API keys; the key used for hashes and approval-link signatures |
| Inference server (Modal) | Runs GPU inference for cell detection (Cellpose). | None. Request content is held in memory only while it is processed. | None |
| LLM providers (Anthropic, OpenAI) | Generate analysis proposals and discussion drafts. | As defined by each provider's API data terms. | None |
| E-mail delivery (Resend) | Delivers sign-in codes. | The e-mail address and the sign-in code | None |
| Distribution (Microsoft Store, GitHub Releases) | Distributes and updates the application. | Handles no research data. | The update-signing key is held only by the maintainer and the signing environments restricted to `main`. |
| Public site (`cytellect.app`) | Serves the landing page, demo and guides. | Accepts no research images. | None |

### Current measures

#### Research data

Images, masks, measurement tables and figures are stored in a private area of the researcher's PC or the lab server. Detection, measurement, statistics and figure rendering run in the same place, and original pixel values are never modified.

Data leaves the PC only when the user performs one of the following actions.

| Action | Data transmitted | Destination | Handling at the destination |
|---|---|---|---|
| Cell detection on the cloud GPU | The plane to detect and the detection parameters. For nucleolar detection, the adopted nuclear labels are added. | Modal, via the Cytellect Worker | The Worker forwards the body without reading it, and the inference server processes it in memory only. Neither stores or logs it. |
| Analysis consultation with the AI | The research goal, channel names and recorded stains, field names (by default the file name) and records (condition, experimental unit, pair, acquisition date), image dimensions and pixel size, field and group counts, the current analysis settings and the previous proposal, and per-channel display-scaled previews of one representative field (at most 512 px per side; can be disabled in settings). | Anthropic or OpenAI, via the Cytellect Worker | The Worker neither stores nor logs the body. Requests to OpenAI set `store: false` so that responses are not stored. Transmitted data is not used for model training. Each provider may retain data for a limited period for purposes such as abuse monitoring. |
| Discussion draft generation by the AI | The saved comparison and the experiment purpose. The comparison comprises the summary on screen (heading and points), the metric's name and definition, the stain name, the region, group, run and channel names, group values, differences and confidence intervals, per-experiment values, counts and their breakdown, aggregation and test settings, the researcher's experimental-unit definition and pairing basis, and the test and its p-value. The purpose defaults to the research goal written to the AI in that workspace. | As above | As above |
| Cloud sign-in | The e-mail address and the sign-in code | Resend | Used solely to deliver the sign-in code by e-mail. |

Transmission, storage and retention are handled as follows.

| Item | Handling |
|---|---|
| Data not transmitted | Original images, masks, per-object measurements and file paths are not transmitted beyond what the table above lists. Fields the user has excluded are used neither for proposals nor for previews. |
| Consent | The scope transmitted to the AI is displayed, and consent obtained, at cloud sign-in and at the first discussion draft. The AI settings panel also displays the scope (owner's decision, 2026-11-16; the summary, n breakdown, method and purpose were added to discussion drafts on 2026-11-17; background in the [LLM assistance redesign](docs/drafts/llm-assistant/plan.md)). |
| Transmission confirmation | Transmission to the AI is accepted only for requests that carry the confirmation given by the user's action. The local API rejects requests without it. |
| Usage analytics | The installed application and the workspace transmit no usage telemetry. Web analytics is used only on the public pages of `cytellect.app` (landing page, demo and guides), which accept no research images. |
| Update check | The EXE release consults GitHub's public release list for a newer version (at most once every six hours). No research data or account information is transmitted. |
| Protection in transit | All external traffic is encrypted with TLS. |
| Protection at rest | Data and credentials on the PC are stored where only the OS user can read them. Encryption at rest relies on the OS (BitLocker and similar). |
| Integrity of original images | Original pixel values are never modified. Analysis verifies the SHA-256 of an imported image before using it and writes results to a separate area. |
| Retention | The Windows release retains work data until the user deletes it (the EXE release also offers 24-hour automatic deletion at installation). The Docker release expires and deletes it 24 hours after the last action. Manual retention is available only on the researcher's own PC. |
| Deletion | Expiry and deletion block reads immediately. Inputs, arrays, masks, figures and exported files are then removed. |
| Data stored in the cloud | The Cytellect cloud stores no research data. It stores only account records (e-mail address, approval state and times, hashes of tokens and codes) and usage records (monthly GPU seconds, cost and token counts per analysis proposal). |

#### Impact of a compromise

Data, keys and permissions are separated so that the compromise of a single component does not propagate.

| Compromised component | Reachable | Not reachable |
|---|---|---|
| A researcher's cloud account | That user's GPU and analysis-proposal quota (up to the monthly limits) | Research data (none is stored in the cloud) |
| The Cytellect Worker | Data relayed during the compromise, and tampering with inference results or proposals | Stored research data and application updates (the signing key is held elsewhere) |
| Write access to the repository | Branches and pull requests | `main` (merging requires the maintainer) and installed PCs (updates require a signature made with the maintainer's key) |

#### Authentication and access control

| Subject | Measures |
|---|---|
| Sign-in code | Researchers authenticate with a six-digit code sent by e-mail. Codes are generated from a cryptographically secure random source and sent only to addresses the maintainer has allowed. A code expires after 10 minutes and can be used once. |
| Attempt limits | Five incorrect entries invalidate a code, and 20 incorrect entries for one address within a day lock that address for 24 hours. Attempts are counted per address, so changing IP addresses yields no additional attempts. In addition, code issuance and verification are rate-limited per IP address (per /64 for IPv6) and per address. |
| Device token | A signed-in PC holds a single device token of 256 random bits. The token expires after 90 days without use and is deleted from both the PC and the server on sign-out. The PC sends the token only to the URL that issued it and does not follow redirects. |
| Authentication data stored by the server | Tokens are stored only as SHA-256 hashes and codes only as keyed HMAC-SHA256 hashes. IP addresses are not stored, and rate-limit identifiers are also stored as keyed hashes. Secret values are compared in constant time. |
| Revocation | When the maintainer revokes an address, every device signed in with it is rejected from the next request. |
| Provider keys | The Anthropic, OpenAI, Modal and Resend keys are held only as secrets of the Cytellect Worker. They are never included on the PC, in a release or in a Worker response. Releases are scanned for credential patterns at build time. |
| Maintainer authentication | Every cloud account used for operations requires multi-factor authentication with a passkey or an authenticator app. The admin page is placed behind Cloudflare Access (Google sign-in), and the Worker independently verifies the JWT signature (RS256 only), issuer, audience, expiry and the maintainer's address. Admin routes respond only on the designated origin; other entry points such as `workers.dev` do not respond even to a valid token. |
| User approval | New users are approved through a single-use link signed with HMAC (expiring after 7 days). Opening the link alone approves nothing; approval requires a confirming action on the page. |

#### Cloud relay (Cytellect Worker)

The Cytellect Worker relays requests after verifying authentication and quotas. Bodies containing research data are neither stored nor logged.

| Measure | Description |
|---|---|
| No body storage | Request and response bodies, codes and tokens are neither stored nor logged. Workers observability (log collection) is disabled. |
| Detection relay | Detection requests and responses are forwarded as streams without reading the body. Only the content-type and accept headers are forwarded, so the user's device token never reaches the destination. |
| Request validation | Body size is limited per route (authentication 4 KiB, analysis proposals 6 MiB, detection 256 MiB). Proposal requests are validated against a schema, and previews are confirmed to be PNG and at most 512 px from their headers, without decoding pixels. Models and prompt versions are restricted to an allowlist. |
| Replay prevention | A proposal request is accepted once per device for each unique Idempotency-Key (UUID). Sign-in codes and approval links are consumed exactly once by an atomic update. |
| Outbound requests | Outbound requests do not follow redirects, so a key cannot be sent to another host. Provider errors are replaced with defined codes before they are returned. |
| Quotas and cost | GPU seconds and AI cost are subject to per-user monthly limits and an overall monthly budget. The maximum cost is reserved before a model call, and requests exceeding a limit are rejected without being forwarded. Each user may have one GPU request in flight at a time. |
| Browser protections | No CORS headers are returned, so browsers on other origins cannot use the service. The admin page applies a CSP including `default-src 'none'` and `frame-ancestors 'none'` and forbids caching. Admin operations are restricted to same-origin JSON requests. |
| Behaviour on incomplete configuration | When a required setting or key is missing, the affected feature accepts no requests. |

#### Inference server

| Measure | Description |
|---|---|
| Runtime | A single container processes one request at a time. No persistent volume or memory snapshot is used. The container runs as a non-root user, and its image is pinned by digest. |
| Authentication | Modal proxy authentication is required, and unauthenticated requests are not accepted. |
| Request handling | Request content is held in memory only while it is processed and is never written to a file. Request content, paths and client addresses are not logged. |
| Input validation | The format, size and fields of the input are validated. A request cannot specify a URL, a file path or an arbitrary model. |
| Models | Only public, revision-pinned weights are used, and their SHA-256 is verified before loading. |
| Result verification | The PC accepts a result only when the hashes of the runner, the model and the dependency lock match the release. |

#### Application on the PC

| Measure | Description |
|---|---|
| Listening address | The local server listens only on `127.0.0.1`. The Docker release publishes its ports only on `127.0.0.1`. |
| Request validation | The Windows release checks the peer address, Host, Origin and Fetch Metadata of every request and rejects requests carrying forwarding headers. It additionally requires a CSRF header on state-changing requests, rejecting operations from other sites and through DNS rebinding. The Docker release checks the Origin and CSRF headers of state-changing requests. |
| Sessions | Sessions are held in HttpOnly, SameSite=Strict cookies, and the server stores only the SHA-256 of the token. Logging out revokes the session. The Windows release revokes all sessions when the application exits. |
| Ownership checks | Ownership is verified on every read, and the existence of another user's workspace is not disclosed. An identifier alone confers no permission. |
| Response headers | Responses carry `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` and `X-Frame-Options: DENY`. The screen applies a CSP including `frame-ancestors 'none'`, `object-src 'none'` and `connect-src 'self'`. |
| Logging | Access logging is disabled. Request bodies, file names and token values are not logged. Errors return defined codes only. |
| Input acceptance | Accepted input is bounded (100 fields and 2 GiB in total per workspace; a plane of at most 4096×4096 px). Storage uses internal identifiers, and uploaded file names are never used in paths. Paths are verified to lie inside the storage area, and arrays are loaded with pickle disabled. |
| Communication with the cloud | Cloud URLs must use HTTPS (except loopback for tests), and URLs containing credentials, a query or a fragment are not accepted. Response size is limited, and only defined fields are passed to the screen. The device token is stored in a settings area separate from research data, and the local API includes it in neither responses nor logs. |
| Analysis worker isolation | The Docker analysis worker runs in a container with no network, as a non-root user, on a read-only root filesystem. All capabilities are dropped, privilege escalation is disabled, and memory and process count are limited. CI verifies on the real container that outbound connections are denied. |
| Job supervision | Jobs are subject to time and memory limits. When supervision cannot confirm a job's state, the analysis processes are terminated and no result is published. |

#### AI assistance

| Measure | Description |
|---|---|
| No execution of output | LLM output is never executed as code. |
| Proposal validation | An analysis proposal is validated on the PC as structured settings consisting only of defined fields and values. Proposals containing undefined fields, or URLs or code-like text in their explanations, are rejected. The channel set must match what was transmitted, and a proposal can neither alter a recorded stain nor establish an unrecorded one. |
| Adoption required | A proposal is a draft and is not used until the researcher adopts it. |
| Separation of computation | After adoption, measurements and statistics are still computed by the shared implementation, irrespective of the proposal's content. A proposal never produces values. |
| State re-check | If workspace data changes, or the workspace expires or is deleted, during the external call, the resulting proposal is discarded. |
| Discussion drafts | A discussion draft is validated for structure only and saved as text with its comparison. It does not modify analysis settings or values. |

#### Release integrity and supply chain

| Subject | Measures |
|---|---|
| Microsoft Store release (Windows 11) | Signed by Microsoft; installed and updated by the Microsoft Store. Submissions to the Store are limited to the latest `main` commit approved by the maintainer. |
| Update signature | Each EXE release carries a manifest stating the version, installer name, SHA-256, size, source commit and time of issue, with an OpenSSH signature (namespace `cytellect-update`) made with the maintainer's Ed25519 key. |
| Update verification | The application verifies the manifest's signature with its built-in public key before fetching the installer. The installer runs only when the release is newer than the installed one and its SHA-256 and size match the manifest. Downloads are restricted to GitHub hosts over HTTPS, and redirect targets are checked as well. The digest GitHub reports is not a basis of trust. |
| Update rollback | If the new version fails to start, the application restores the database copy taken before the switch and the previous version. |
| First installation | A first installation of the EXE release can also be verified against the same manifest ([steps, in Japanese](docs/install-windows.ja.md#2-ダウンロードと確認)). |
| Signing key custody | The signing key is held only by the maintainer and in dedicated GitHub Actions environments restricted to `main`. Manual releases require the maintainer's approval. When the maintainer has enabled automatic EXE distribution, only versions that have passed CI and the distribution tests on protected `main` are published. |
| Release procedure | A release is built from a single commit, which is re-checked at each stage. The commit must be in the history of `main`; runs originating from forks and reuse of a tag are refused. Published assets must match the tested files in size and digest. |
| Dependency pinning | Python and JavaScript dependencies are pinned by lockfiles with hashes. The bundled Fiji, detection models and Python runtime are verified against SHA-256 hashes at build time. |
| Runtime downloads | No code or model is downloaded while an analysis runs. |
| Repository protection | `main` is protected by a ruleset, and only the maintainer can merge. The workflows' `GITHUB_TOKEN` is read-only by default, and `pull_request_target` is not used. |
| Automated checks | A hash-verified gitleaks scans the full Git history of `main` and of every pull request for secrets. CodeQL (Actions, JavaScript/TypeScript, Python) runs on pull requests, on `main` and weekly. Dependency vulnerability audits (pip-audit, pnpm audit) and SBOM generation (CycloneDX) run in CI. |

### Supported versions

| Version | Security fixes |
|---|---|
| The Microsoft Store release | Provided (updated to the latest version by the Microsoft Store) |
| The latest EXE release | Provided |
| `main` (`cytellect.app` and the cloud features) | Provided |
| Earlier EXE releases | Not provided (move to the latest release through the in-app update) |

### Scope

This repository's code, the Windows releases (Microsoft Store and EXE), the Docker release, `cytellect.app`, the Cytellect Worker and the inference server are in scope. Issues arising from how Cytellect configures or uses an external service are also in scope. Vulnerabilities in bundled third-party components (Fiji, Cellpose and others) and in the external services themselves (Cloudflare, Modal, Anthropic, OpenAI, Resend, GitHub, Vercel, Microsoft Store) are out of scope and are handled by their respective maintainers.

### Reporting a vulnerability

Report vulnerabilities through GitHub's private reporting feature. Selecting **Report a vulnerability** under the repository's **Security** tab submits a report visible only to the reporter and the repository maintainers ([report form](https://github.com/genellect/cytellect/security/advisories/new)). Do not describe vulnerabilities in public places such as issues, pull requests or discussions.

Include the following in a report.

- The affected commit, or the version of the Windows release
- Reproduction steps
- The expected impact

Use synthetic or public data for reproduction.

### Response to a report

1. Reasonable reports receive a reply within three days.
2. The affected scope and severity are assessed and shared with the reporter.
3. The issue is fixed in a private Security Advisory and the fixed version is released. The public site and cloud features are deployed to production, and the Windows releases are distributed through the Microsoft Store and a signed update.
4. After the release, the Security Advisory is published and a CVE is requested where appropriate. The reporter is credited by name on request.

Published advisories are listed under [Security Advisories](https://github.com/genellect/cytellect/security/advisories).

### Research data in development

The handling of research data and credentials in development (Git, CI, logs, development AI) is defined in the [team development rules, section 6](docs/team-development.md#6-research-data). The data-protection specification and operating details are in [data protection and operations](docs/security.md).
