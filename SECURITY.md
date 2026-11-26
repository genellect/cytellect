# セキュリティポリシー

本書は、Cytellect の情報セキュリティに関する方針、管理策、脆弱性の報告手順を定める。脆弱性の報告手順は「[14.2 脆弱性の報告](#142-脆弱性の報告)」に、英語版は本書の後半（[English](#english)）にある。

**目次**

- [1. 目的と適用範囲](#1-目的と適用範囲)
- [2. 基本方針](#2-基本方針)
- [3. 体制と責任](#3-体制と責任)
- [4. システム構成と信頼境界](#4-システム構成と信頼境界)
- [5. 情報の分類と取り扱い](#5-情報の分類と取り扱い)
- [6. 研究データの保護](#6-研究データの保護)
- [7. アクセス制御と認証](#7-アクセス制御と認証)
- [8. 暗号と鍵の管理](#8-暗号と鍵の管理)
- [9. 通信とネットワークのセキュリティ](#9-通信とネットワークのセキュリティ)
- [10. アプリケーションのセキュリティ](#10-アプリケーションのセキュリティ)
- [11. ログ、監視、容量の管理](#11-ログ監視容量の管理)
- [12. 開発と変更の管理](#12-開発と変更の管理)
- [13. 外部サービスとサプライチェーン](#13-外部サービスとサプライチェーン)
- [14. 脆弱性の管理](#14-脆弱性の管理)
- [15. インシデントへの対応](#15-インシデントへの対応)
- [16. 事業継続](#16-事業継続)
- [17. 法令、契約、ライセンス](#17-法令契約ライセンス)
- [18. 文書の管理](#18-文書の管理)

## 1. 目的と適用範囲

本書の目的は、Cytellect が研究データと利用者の情報をどのように保護しているかを、利用者、導入を審査する組織、脆弱性の報告者に示すことである。

| 区分 | 内容 |
|---|---|
| 対象とする製品とサービス | このリポジトリのコード、Windows 版（Microsoft Store 版と EXE 版）、Docker 版、公開サイト（`cytellect.app`）、中継サービス（Cytellect Worker）、推論サーバー |
| 対象とする情報 | 研究データ、認証情報、アカウント情報、利用量の記録 |
| 対象とする活動 | 設計、開発、配布、運用、脆弱性への対応 |
| 対象外 | 同梱する第三者の部品（Fiji、Cellpose など）と、利用する外部サービス自体の脆弱性。これらは各開発元の窓口が扱う。Cytellect による外部サービスの設定と利用方法に起因する問題は、対象に含む。 |

## 2. 基本方針

Cytellect は、未発表の顕微鏡画像を研究者の PC 上で解析する。セキュリティ設計は、次の方針に基づく。

| 方針 | 内容 | 参照 |
|---|---|---|
| データの所在 | 画像、輪郭、測定値、図は研究者の PC または研究室のサーバーに保存し、Cytellect のクラウドには保存しない。検出、測定、統計、作図も同じ場所で実行する。 | [6. 研究データの保護](#6-研究データの保護) |
| 送信の最小化 | PC の外部への送信は、利用者がクラウド GPU または AI の機能を実行した場合に限り、その処理に必要な範囲にとどめる。これらの機能は任意であり、使用しなければ研究データは PC の外部に出ない。 | [6. 研究データの保護](#6-研究データの保護) |
| 最小権限と分離 | データ、鍵、権限を構成要素ごとに分離する。クラウドまたはリポジトリが侵害されても、保存された研究データと導入済みのアプリには到達できない。 | [4. システム構成と信頼境界](#4-システム構成と信頼境界)、[15. インシデントへの対応](#15-インシデントへの対応) |
| 多層の検証 | 構成要素は互いの入出力を信頼せず、それぞれが独立に検証する。中継サービスは PC の要求を、推論サーバーは中継サービスの要求を、PC はクラウドの応答を検証する。 | [10. アプリケーションのセキュリティ](#10-アプリケーションのセキュリティ) |
| AI 出力の非実行 | AI の出力はコードとして実行しない。解析の提案は検証済みの設定の下書きとして扱い、研究者が採用するまで解析に使用しない。 | [10.4 AI による解析支援](#104-ai-による解析支援) |
| 配布物の検証 | PC は、管理者の鍵で署名された更新だけを実行する。依存と同梱物はハッシュで固定する。 | [13. 外部サービスとサプライチェーン](#13-外部サービスとサプライチェーン) |

## 3. 体制と責任

### 3.1 役割

| 役割 | 責任と権限 |
|---|---|
| 管理者（プロダクトオーナー） | `main` への反映、本番への公開と配布、外部サービスの契約と設定、利用者の承認と失効、脆弱性への対応を判断し、実行する。 |
| 開発メンバー | 担当する変更を実装し、プルリクエストを作成し、他のメンバーの変更をレビューする。`main` への反映と配布の権限は持たない。 |
| AI エージェント | 依頼者の指示の範囲で実装と検証を行う。成果物の責任は依頼者が負う。`main` への反映と本番への公開は、管理者が対象を明示して指示した場合に限る。 |
| 利用者（研究者、研究室） | 研究データを、自らの PC またはサーバーで管理する。 |

### 3.2 責任分界

研究データは利用者の管理下にあるため、責任を次のとおり分担する。

| 領域 | Cytellect の責任 | 利用者の責任 |
|---|---|---|
| 研究データの保管 | アプリは、研究データを OS の利用者だけが読み取れる場所に保存する。 | PC と OS アカウントの管理、ディスクの暗号化、バックアップ |
| クラウドの機能 | 認証、中継、利用枠の管理、送信範囲の表示 | 機能の使用の判断、送信範囲への同意 |
| アプリの更新 | 署名付きの更新の提供 | 更新の適用 |
| アカウント | 承認、失効、認証情報の保護 | メールアドレスの管理、使用しなくなった端末のサインアウト |

## 4. システム構成と信頼境界

研究データを保持するのは研究者の PC だけである。クラウド側の構成要素は、処理に必要な期間と範囲でのみデータに触れる。

| 構成要素 | 役割 | 保持するデータ | 保持する鍵と資格情報 |
|---|---|---|---|
| 研究者の PC（画面、ローカルのサーバー、解析ワーカー） | 検出、測定、統計、作図を実行する。 | 研究データのすべて | 端末トークン 1 つ（クラウドにログインした場合） |
| 中継サービス（Cytellect Worker。Cloudflare 上で動作する） | ログイン、利用の承認、利用枠の管理を行い、クラウド GPU と AI への要求を中継する。 | アカウント情報と利用量の記録。研究データは保存しない。 | 送信先の API キー、ハッシュと承認リンクの署名に使用する鍵 |
| 推論サーバー（Modal 上で動作する） | 細胞の検出（Cellpose）の GPU 推論を実行する。 | なし。要求の内容は、処理中のみメモリ上に保持する。 | なし |
| AI の提供元（Anthropic、OpenAI） | 解析の提案と考察の下書きを生成する。 | 各社の API のデータの取り扱いによる。 | なし |
| メール送信（Resend） | ログインコードを送信する。 | メールアドレスとログインコード | なし |
| 配布（Microsoft Store、GitHub） | アプリを配布し、更新する。 | 研究データを扱わない。 | 更新の署名鍵は、管理者と、`main` に限定した署名環境だけが保持する。 |
| 公開サイト（`cytellect.app`） | ランディングページ、デモ、ガイドを提供する。 | 研究画像を受け付けない。 | なし |

## 5. 情報の分類と取り扱い

| 区分 | 例 | 保存場所 | 取り扱い |
|---|---|---|---|
| 研究データ（非公開） | 未発表の画像、輪郭、測定表、図、ファイル名とパス | 研究者の PC または研究室のサーバー | クラウドに保存しない。外部への送信は [6. 研究データの保護](#6-研究データの保護) に定める範囲に限る。Git、CI、ログ、公開の場に含めない。 |
| 認証情報 | API キー、端末トークン、署名鍵 | 各サービスのシークレット管理、PC の設定領域、管理者の手元 | ソースコード、ログ、配布物に含めない。サーバーにはハッシュだけを保存する。 |
| アカウント情報 | メールアドレス、承認の状態と日時 | 中継サービスのデータベース | 認証、承認、利用枠の管理にのみ使用する。 |
| 利用量の記録 | 月ごとの GPU の秒数、解析提案ごとの費用とトークン数 | 中継サービスのデータベース | 利用枠と費用の管理にのみ使用する。 |
| 公開データ | 出典とライセンスを確認した公開画像 | リポジトリの登録済みの領域 | 出典、再配布条件、ハッシュを記録し、試験と公開デモに使用する。 |

## 6. 研究データの保護

### 6.1 所在と処理

画像、輪郭（マスク）、測定表、図は、研究者の PC または研究室のサーバーの非公開領域に保存する。検出、測定、統計、作図は同じ場所で実行し、原画像の画素値は変更しない。

### 6.2 外部への送信

PC の外部へ送信するのは、利用者が次の操作を実行した場合に限る。

| 操作 | 送信する情報 | 送信先 | 送信先での取り扱い |
|---|---|---|---|
| クラウド GPU による細胞の検出 | 検出対象の 1 プレーンと検出条件。核小体の検出では、採用済みの核のラベルを加える。 | 中継サービスを経由して推論サーバー（Modal） | 中継サービスは本文を読み取らずに転送し、推論サーバーはメモリ上でのみ処理する。いずれも保存せず、ログに記録しない。 |
| AI への解析の相談 | 研究の目的、チャンネル名と記録した染色、視野の名前（既定ではファイル名）と記録（条件、実験回、組、取得日）、画像の寸法と画素サイズ、視野と群の数、現在の解析設定と前回の提案、代表的な 1 視野のチャンネルごとの縮小画像（一辺 512 px 以下。設定で無効にできる） | 中継サービスを経由して Anthropic または OpenAI | 中継サービスは本文を保存せず、ログに記録しない。OpenAI には、応答を保存しない設定（`store: false`）で送信する。送信したデータは、モデルの学習に使用されない。各提供元は、不正利用の監視のために、各社の API の規約が定める期間、データを保持する。 |
| AI による考察の生成 | 保存した比較結果と実験の目的。比較結果は、画面のまとめ（見出しと要点）、指標の名前と定義、染色名、領域・群・実験回・チャンネルの名前、群ごとの値、差と信頼区間、実験回ごとの値、n とその内訳、集計と検定の方法、研究者が記述した実験単位の定義と対応の根拠、検定と p 値からなる。目的の初期値は、そのワークスペースで AI への相談に記述した研究の目的である。 | 同上 | 同上 |
| クラウドへのログイン | メールアドレスとログインコード | Resend | ログインコードのメール送信にのみ使用する。 |

### 6.3 送信の統制

| 管理策 | 実装 |
|---|---|
| 送信しない情報 | 外部へ送信する情報は、6.2 に記載したものに限る。核ごとの測定値とファイルのパスは、いずれの操作でも送信しない。利用者が除外した視野は、提案にも縮小画像にも使用しない。 |
| 同意 | AI への送信範囲は、クラウドへのログイン時と最初の考察の生成時に画面に表示し、同意を得たうえで送信する。送信範囲は、AI の設定画面にも表示する（2026-11-16 に決定し、2026-11-17 に考察の生成へまとめ・n の内訳・方法・目的を追加した。経緯は [AI による解析支援の見直し](docs/drafts/llm-assistant/plan.md)）。 |
| 送信の確認 | AI への送信は、利用者の操作による確認を伴う要求だけを受け付ける。確認を伴わない要求は、PC 上のサーバーが拒否する。 |
| 通信の保護 | 外部との通信は、すべて TLS で暗号化する。 |

### 6.4 保管、保持、削除

| 管理策 | 実装 |
|---|---|
| 保存時の保護 | PC 上のデータと資格情報は、OS の利用者だけが読み取れる場所に保存する。保存時の暗号化は、OS の機能（BitLocker など）による。 |
| 原画像の完全性 | 原画像の画素値は変更しない。解析は、取り込んだ画像のハッシュ（SHA-256）を照合してから使用し、結果は別の領域に書き出す。 |
| 保持期間 | Windows 版は、利用者が削除するまで作業データを保持する（EXE 版は、導入時に 24 時間での自動削除を選択できる）。Docker 版は、最後の操作から 24 時間で失効させて削除する。研究者自身の PC に限り、手動での保持を選択できる。 |
| 削除 | 失効と削除は、読み出しをただちに遮断する。その後、入力、配列、マスク、図、書き出したファイルを削除する。 |
| クラウド側の保存情報 | Cytellect のクラウドは研究データを保存しない。保存するのは、アカウント情報（メールアドレス、承認の状態と日時、トークンとコードのハッシュ）と、利用量の記録（月ごとの GPU の秒数、解析提案ごとの費用とトークン数）に限る。 |

### 6.5 利用状況の計測

| 管理策 | 実装 |
|---|---|
| アプリの計測 | 導入したアプリと作業画面は、利用状況の計測情報を送信しない。 |
| 公開サイトのアクセス解析 | アクセス解析を使用するのは、`cytellect.app` の公開ページ（ランディングページ、デモ、ガイド）に限る。これらのページは研究画像を受け付けない。広告目的の利用は無効にし、ブラウザの追跡拒否の設定（Do Not Track、Global Privacy Control）がある場合は計測しない。 |
| 更新の確認 | EXE 版は、GitHub の公開リリース一覧を参照して更新の有無を確認する（最大 6 時間に 1 回）。研究データとアカウント情報は送信しない。 |

## 7. アクセス制御と認証

### 7.1 研究者の認証

| 管理策 | 実装 |
|---|---|
| ログインコード | 研究者は、メールで送信する 6 桁のコードで認証する。コードは暗号論的乱数で生成し、管理者が許可したアドレスにのみ送信する。コードは 10 分で失効し、1 回だけ使用できる。 |
| 試行の制限 | 5 回の誤入力でコードを無効にし、同一アドレスで 1 日 20 回の誤入力があれば 24 時間ロックする。試行回数はアドレス単位で数えるため、IP アドレスを変えても試行回数は増えない。 |
| 送信と検証の回数制限 | コードの送信と検証の回数を、IP アドレス単位（IPv6 は /64 単位）とアドレス単位で制限する。 |

### 7.2 資格情報の管理

| 管理策 | 実装 |
|---|---|
| 端末トークン | ログインした PC が保持する資格情報は、256 bit の乱数による端末トークン 1 つに限る。トークンは 90 日間使用しなければ失効し、サインアウト時に PC とサーバーの双方から削除する。 |
| 端末トークンの保管と送信 | 端末トークンは、研究データとは別の設定領域に保存する。PC 上のサーバーは、トークンを応答にもログにも含めない。トークンは発行元の URL にのみ送信し、転送の指示（リダイレクト）には従わない。 |
| サーバーが保存する認証情報 | トークンは SHA-256、コードは鍵付きの HMAC-SHA256 によるハッシュのみを保存する。IP アドレスは保存せず、回数制限の識別子も鍵付きのハッシュとして保存する。秘密値の照合は、定数時間で行う。 |
| 送信先の鍵 | Anthropic、OpenAI、Modal、Resend の鍵は、中継サービスのシークレットとしてのみ保持する。PC、配布物、中継サービスの応答には含めない。 |
| 失効 | 管理者がアドレスを失効させると、そのアドレスでログインしたすべての端末を、次の要求から拒否する。 |

### 7.3 管理者の認証と特権アクセス

| 管理策 | 実装 |
|---|---|
| 多要素認証 | 運用に使用するクラウドのアカウントは、すべてパスキーまたは認証アプリによる多要素認証を必須とする。 |
| 管理画面の認証 | 管理画面は、Cloudflare Access（Google ログイン）の背後に置く。中継サービスも、アクセストークン（JWT）の署名（RS256 に固定）、発行者、対象、有効期限、管理者のアドレスを独自に検証する。 |
| 管理用の経路の限定 | 管理用の経路は、指定したオリジンでのみ応答する。`workers.dev` などの別の入口からは、有効なトークンがあっても応答しない。 |
| 利用者の承認 | 新規の利用者は、HMAC で署名した 1 回限りのリンク（7 日で失効）で承認する。リンクを開いただけでは承認されず、承認には画面での確認の操作を要する。 |
| ソースコードと配布の権限 | `main` への反映と配布物への署名は、管理者だけが行える。詳細は [12. 開発と変更の管理](#12-開発と変更の管理) と [13.3 配布物の署名と検証](#133-配布物の署名と検証) に示す。 |

### 7.4 PC 上の画面

| 管理策 | 実装 |
|---|---|
| 待ち受け | PC 上のサーバーは、`127.0.0.1` でのみ待ち受ける。Docker 版は、ポートを `127.0.0.1` にのみ公開する。 |
| 要求の検証 | Windows 版は、要求ごとに接続元、宛先のホスト名、オリジン、要求の発生元を示すブラウザの情報（Fetch Metadata）を照合し、転送を示すヘッダーを含む要求を拒否する。状態を変更する要求には CSRF 対策のヘッダーも要求し、他のサイトと DNS リバインディングによる操作を拒否する。Docker 版は、状態を変更する要求のオリジンと CSRF 対策のヘッダーを照合する。 |
| セッション | セッションは、スクリプトから読み取れず、他のサイトからの要求には送信されない Cookie（HttpOnly、SameSite=Strict）で保持する。サーバーには、トークンの SHA-256 だけを保存する。ログアウトでセッションを失効させ、Windows 版はアプリの終了時にすべてのセッションを失効させる。 |
| 所有者の確認 | 読み出しのたびに所有者を確認し、他者のワークスペースについては存在の有無も返さない。識別子だけでは権限を与えない。 |

### 7.5 解析の実行環境

Docker 版の解析ワーカーは、ネットワークを持たない、非 root かつ読み取り専用のコンテナで動作する。すべての特権（ケーパビリティ）を削除し、権限の昇格を禁止する。

## 8. 暗号と鍵の管理

| 用途 | 方式 | 鍵と秘密値の保管 |
|---|---|---|
| 通信の保護 | TLS | 各サービスの証明書による。 |
| 端末トークン | 256 bit の暗号論的乱数。サーバーには SHA-256 のハッシュだけを保存する。 | PC の設定領域 |
| ログインコード | 鍵付きの HMAC-SHA256 によるハッシュだけを保存する。 | ハッシュ用の鍵は、中継サービスのシークレットとして保持する。 |
| 承認リンク | HMAC-SHA256 による署名。照合は定数時間で行う。 | 同上 |
| 管理者のアクセストークン | RS256 による署名を、Cloudflare Access の公開鍵で検証する。 | 秘密鍵は Cloudflare Access が保持する。 |
| 更新の署名 | Ed25519 による OpenSSH 形式の署名（SHA-512）。公開鍵はアプリに組み込む。 | 秘密鍵は、管理者の手元と、`main` に限定した署名環境にのみ保管する。 |
| 完全性の検証 | SHA-256。対象は、インストーラー、同梱物、検出モデル、依存パッケージ、取り込んだ画像である。 | 期待するハッシュは、リポジトリと署名付きのマニフェストに記録する。 |
| 送信先の API キー | — | 中継サービスのシークレットとしてのみ保持する。 |
| 保存時の暗号化 | OS の機能（BitLocker など） | 利用者の OS が管理する。 |
| 鍵の交換と失効 | 更新の署名鍵は、交換と失効の手順を[更新の署名](docs/release-signing.md)に定める。ハッシュ用の鍵を交換すると、未使用のコードと承認リンクは無効になる。 | — |

## 9. 通信とネットワークのセキュリティ

| 経路 | 管理策 |
|---|---|
| PC 内（画面と PC 上のサーバー） | `127.0.0.1` でのみ待ち受け、他の機器からは接続できない。 |
| 解析ワーカー | Docker 版の解析ワーカーは、ネットワークを持たない。CI は、実際のコンテナで外部への通信が拒否されることを検証する。 |
| PC から中継サービス | クラウドとの通信は HTTPS に限る。資格情報、クエリ、フラグメントを含む URL は受け付けない。リダイレクトには従わず、応答のサイズを制限し、定義済みの項目だけを画面に渡す。 |
| 中継サービスから送信先 | 外部への要求はリダイレクトに従わないため、鍵が別のホストに送信されることはない。送信先へ転送するヘッダーは内容の種別を示すものに限り、利用者の端末トークンを送信先に渡さない。 |
| 推論サーバー | Modal のプロキシ認証を必須とし、認証のない要求を受け付けない。 |
| 更新の取得 | 取得元は HTTPS の GitHub のホストに限り、リダイレクト先も照合する。 |
| ブラウザからの利用 | 中継サービスは、他のオリジンからの利用を許可する設定（CORS）を持たないため、他のサイトのブラウザからは利用できない。 |

## 10. アプリケーションのセキュリティ

### 10.1 中継サービス

| 管理策 | 実装 |
|---|---|
| 本文の非保存 | 要求と応答の本文、コード、トークンを保存せず、ログに記録しない。実行基盤のログ収集機能は無効にしている。 |
| 検出の中継 | 検出の要求と応答は、本文を読み取らずに、逐次転送する。 |
| 要求の検証 | 本文のサイズを経路ごとに制限する（認証 4 KiB、解析の提案 6 MiB、検出 256 MiB）。提案の要求は定義済みの形式に照らして検証し、縮小画像は PNG であることと 512 px 以下であることを、画素を復号せずに確認する。モデルと指示文の版は、許可した一覧に限る。 |
| 再送の防止 | 提案の要求は、端末ごとに一意の識別子（UUID）を 1 回だけ受理する。ログインコードと承認リンクは、原子的な更新で 1 回だけ消費する。 |
| エラーの取り扱い | 提供元のエラーは、定義済みのコードに置き換えて返す。提供元の応答の内容や鍵が、エラーを通じて PC に渡ることはない。 |
| 管理画面の保護 | 管理画面は、外部の資源の読み込みと他のサイトへの埋め込みを禁止し、キャッシュを禁止する。管理の操作は、同一オリジンからの要求に限る。 |
| 設定不備時の動作 | 必要な設定または鍵が欠けている場合、該当する機能は要求を受け付けない。 |

### 10.2 推論サーバー

| 管理策 | 実装 |
|---|---|
| 実行環境 | 単一のコンテナで、同時に 1 件の要求だけを処理する。永続的な記憶領域とメモリの保存機能は使用しない。コンテナは非 root で動作し、イメージはダイジェストで固定する。 |
| 要求の取り扱い | 要求の内容は、処理中のみメモリ上に保持し、ファイルに書き込まない。要求の内容、パス、接続元のアドレスをログに記録しない。 |
| 入力の検証 | 入力の形式、サイズ、項目を検証する。要求で URL、ファイルのパス、任意のモデルを指定することはできない。 |
| モデル | 公開され、版を固定した重みだけを使用し、SHA-256 を検証してから読み込む。 |
| 結果の検証 | PC は、実行プログラム、モデル、依存の固定情報のハッシュが、導入した版と一致する結果だけを受理する。 |

### 10.3 PC 上のアプリ

| 管理策 | 実装 |
|---|---|
| 応答の保護 | 応答には、キャッシュの禁止、内容の種別の推測の禁止、参照元の送信の禁止、他のサイトへの埋め込みの禁止を指定する。画面には、外部の資源の読み込みと外部への接続を禁止するコンテンツセキュリティポリシーを適用する。 |
| 入力の受け入れ | 受け入れる入力に上限を設ける（1 ワークスペースあたり 100 視野、合計 2 GiB。1 プレーンは 4096×4096 px まで）。保存には内部の識別子を使用し、アップロードされたファイル名をパスに使用しない。パスは保存領域の内側にあることを検証し、配列はコードの実行を伴わない形式でのみ読み込む。 |
| エラーの取り扱い | エラーは、定義済みのコードだけを返す。内部の例外や解析プログラムの出力を、そのまま返すことはない。 |
| ジョブの監視 | ジョブには、実行時間とメモリの上限を設ける。監視が状態を確認できない場合は、解析のプロセスを停止し、結果を公開しない。 |
| 実行時の取得 | 解析の実行中に、コードやモデルをダウンロードしない。 |

### 10.4 AI による解析支援

| 管理策 | 実装 |
|---|---|
| 出力の非実行 | AI の出力は、コードとして実行しない。 |
| 提案の検証 | 解析の提案は、定義済みの項目と値だけからなる設定として、PC 上で検証する。未定義の項目を含む提案と、説明文に URL やコードに類する文字列を含む提案は拒否する。チャンネルの構成は送信した内容と一致しなければならず、記録された染色を提案が変更することも、記録のない染色を提案が定めることもできない。 |
| 採用の要否 | 提案は下書きであり、研究者が採用するまで解析に使用しない。 |
| 計算の分離 | 採用後も、測定と統計は、提案の内容にかかわらず共通の実装が計算する。提案が数値を生成することはない。 |
| 状態の再確認 | 外部の呼び出しの間に、ワークスペースのデータが変更された場合と、ワークスペースが失効または削除された場合は、その提案を破棄する。 |
| 考察の下書き | 考察の下書きは、形式のみを検証し、文章として比較結果に付して保存する。解析の設定と数値は変更しない。 |

## 11. ログ、監視、容量の管理

| 管理策 | 実装 |
|---|---|
| ログに記録しない情報 | 中継サービスは、要求と応答の本文、コード、トークンを記録しない。PC 上のサーバーは、アクセスログを無効にし、要求の本文、ファイル名、トークンの値を記録しない。推論サーバーは、要求の内容、パス、接続元のアドレスを記録しない。 |
| 記録する情報 | 中継サービスは、アカウント情報と利用量（月ごとの GPU の秒数、解析提案ごとの費用とトークン数）を記録する。 |
| 利用枠 | GPU の秒数と AI の費用には、利用者ごと・月ごとの上限と、全体の月間予算を設ける。モデルの呼び出し前に最大費用を予約し、上限を超える要求は、送信先に転送せずに拒否する。 |
| 費用の監視 | 費用の記録に不整合が生じた場合は、解消するまで AI への要求を停止する。 |
| 同時実行の制限 | GPU の要求は、利用者ごとに同時に 1 件に限る。推論サーバーは、同時に 1 件の要求だけを処理する。 |
| 入力とジョブの上限 | 入力の件数とサイズ、ジョブの実行時間とメモリに上限を設ける（[10.3 PC 上のアプリ](#103-pc-上のアプリ)）。 |

## 12. 開発と変更の管理

| 管理策 | 実装 |
|---|---|
| 変更管理 | すべての変更はプルリクエストで行い、必須の CI の成功とレビューを経て、管理者が `main` に反映する。`main` の更新はルールセットで制限し、反映できるのは管理者に限る。 |
| レビュー | 管理者以外が作成した変更は、作成者以外の 1 名以上の承認を要する。レビューでは、本番への影響、画素値・測定値・統計・図への影響、非公開データと認証情報の混入の有無を確認する。 |
| 環境の分離 | 開発に本番の認証情報を使用しない。実行時のデータは、ソースコードの外に保存する。複数人が利用する開発環境は、登録済みの公開ファイル以外のアップロードを、ハッシュ（SHA-256）の照合で拒否する。 |
| 試験データ | 試験、評価、公開デモには、出典、再配布条件、ハッシュを記録した公開画像を使用する。非公開の研究データは、Git、CI、公開の場に含めない。 |
| セキュリティ試験 | 招待の再利用と失効、オリジンと CSRF の検証、所有者の確認、失効と削除を、自動試験で検証する。CI は、解析ワーカーの実際のコンテナで隔離の設定を検証する。中継サービスの設定は、鍵が設定値に含まれないことと、ログ収集が無効であることを、試験で検証する。 |
| 自動検査 | ハッシュを検証した gitleaks で、`main` と各プルリクエストの Git の全履歴を走査し、秘密情報を検出する。CodeQL（ワークフロー、JavaScript/TypeScript、Python）を、プルリクエスト、`main`、週次で実行する。依存の脆弱性監査（pip-audit、pnpm audit）と、ソフトウェア部品表（SBOM）の生成を CI で実行する。 |
| ワークフローの権限 | ワークフローに与えるトークンは、既定で読み取り専用とする。フォークに由来する実行には、書き込み権限とシークレットを与えない。 |
| AI エージェントの利用 | AI エージェントの成果物は、依頼者が内容を確認してからレビューに出す。`main` への反映と本番への公開は、管理者が対象を明示して指示した場合に限る。 |

## 13. 外部サービスとサプライチェーン

### 13.1 外部サービス

| サービス | 用途 | 受け取る情報 |
|---|---|---|
| Cloudflare | 中継サービスの実行、アカウント情報と利用量の記録、管理画面の認証 | 中継中の要求（保存しない）、アカウント情報、利用量の記録 |
| Modal | 細胞の検出の GPU 推論 | 検出対象のプレーン、ラベル、検出条件（処理中のみ） |
| Anthropic、OpenAI | 解析の提案と考察の下書きの生成 | [6.2 外部への送信](#62-外部への送信) に定める AI への送信情報 |
| Resend | ログインコードのメール送信 | メールアドレスとログインコード |
| GitHub | ソースコードの管理、CI、EXE 版の配布 | 研究データを受け取らない。 |
| Microsoft Store | Windows 版の配布と更新 | 研究データを受け取らない。 |
| Vercel | 公開サイトの提供 | 研究画像を受け取らない。 |
| Google Analytics | 公開ページのアクセス解析 | 公開ページの閲覧に関する情報。作業画面と導入したアプリでは使用しない。 |

外部サービスの追加と、費用が発生する設定は、管理者が判断する。

### 13.2 依存と同梱物

| 管理策 | 実装 |
|---|---|
| 依存の固定 | Python と JavaScript の依存は、ハッシュ付きの固定ファイルで固定する。 |
| 同梱物の照合 | 同梱する Fiji、検出モデル、Python の実行環境は、ビルド時に SHA-256 で照合する。 |
| 配布物の検査 | 配布物は、ビルド時に認証情報の混入を走査し、検出した場合はビルドを失敗させる。 |

### 13.3 配布物の署名と検証

| 対象 | 管理策 |
|---|---|
| Microsoft Store 版（Windows 11） | Microsoft が署名し、導入と更新は Microsoft Store が行う。Store への提出は、管理者が承認した `main` の最新のコミットに限る。 |
| 更新の署名 | EXE 版の各リリースには、版、インストーラーの名前、SHA-256、サイズ、ソースのコミット、発行時刻を記載したマニフェストと、管理者の Ed25519 鍵による署名を付す。 |
| 更新の検証 | アプリは、組み込んだ公開鍵でマニフェストの署名を検証してから、インストーラーを取得する。現在より新しい版であり、インストーラーの SHA-256 とサイズがマニフェストと一致する場合にのみ実行する。配布元が示すハッシュは、信頼の根拠にしない。 |
| 初回導入 | EXE 版の最初の導入でも、同じマニフェストでダウンロードを検証できる（[手順](docs/install-windows.ja.md#2-ダウンロードと確認)）。 |
| 署名鍵の保管 | 署名鍵は、管理者の手元と、`main` に限定した専用の署名環境にのみ保管する。手動配布は、管理者の承認を要する。管理者が有効にした EXE の自動配布では、保護された `main` 上で CI と配布試験に合格した版だけを公開する。 |
| リリースの手順 | リリースは単一のコミットから作成し、各段階でそのコミットを照合する。コミットは `main` の履歴に含まれなければならず、フォークに由来する実行とタグの再利用は拒否する。公開するファイルは、サイズとハッシュが試験済みのファイルと一致しなければならない。 |

## 14. 脆弱性の管理

### 14.1 サポート対象の版

| 版 | セキュリティ修正 |
|---|---|
| Microsoft Store 版 | 提供する（Microsoft Store が最新版に更新する） |
| EXE 版の最新のリリース | 提供する |
| `main`（`cytellect.app` とクラウドの機能） | 提供する |
| 上記より前の EXE 版 | 提供しない（アプリ内の更新で最新版に移行する） |

### 14.2 脆弱性の報告

脆弱性は、GitHub の非公開の報告機能で報告する。リポジトリの **Security** タブで **Report a vulnerability** を選択すると、報告者とリポジトリの管理者だけが閲覧できる形で送信できる（[報告フォーム](https://github.com/genellect/cytellect/security/advisories/new)）。Issue、プルリクエスト、ディスカッションなどの公開の場には記載しない。

報告には、次の内容を含める。

- 対象のコミット、または Windows 版のバージョン
- 再現手順
- 想定される影響

再現には、合成データまたは公開データを使用する。

### 14.3 報告後の対応

1. 合理的な報告には、3 日以内に返信する。
2. 影響範囲と深刻度を評価し、報告者と共有する。
3. 非公開のセキュリティアドバイザリで修正し、修正版を配布する。公開サイトとクラウドの機能は本番環境に反映し、Windows 版は Microsoft Store と署名付きの更新で配布する。
4. 配布後にセキュリティアドバイザリを公開し、必要に応じて CVE を取得する。報告者が希望する場合は、謝辞に氏名を記載する。

公開済みのセキュリティアドバイザリは、[一覧](https://github.com/genellect/cytellect/security/advisories)にある。

## 15. インシデントへの対応

### 15.1 侵害時の影響範囲

単一の構成要素が侵害されても被害が波及しないよう、データ、鍵、権限を分離している。

| 侵害の対象 | 到達できる範囲 | 到達できない範囲 |
|---|---|---|
| 研究者のクラウドのアカウント | その利用者の GPU と解析提案の利用枠（月ごとの上限まで） | 研究データ（クラウドに保存していない） |
| 中継サービス | 侵害されている間に中継されるデータの閲覧と、推論結果・提案の改ざん | 保存された研究データ、アプリの更新（署名鍵は別の場所に保管する） |
| リポジトリへの書き込み権限 | ブランチとプルリクエスト | `main` への反映（管理者による反映を要する）、導入済みの PC（更新には管理者の鍵による署名を要する） |

### 15.2 封じ込めと復旧

| 事象 | 対応 |
|---|---|
| 利用者のアカウントの不正利用 | 管理者が該当するアドレスを失効させる。そのアドレスでログインしたすべての端末を、次の要求から拒否する。 |
| 認証情報の漏えい | 該当する認証情報を、ただちに無効化して再発行する。 |
| ハッシュと署名に使用する鍵の漏えい | 鍵を交換する。交換により、未使用のログインコードと承認リンクは無効になる。 |
| 更新の署名鍵の漏えいまたは紛失 | [更新の署名](docs/release-signing.md)に定める失効と交換の手順に従う。 |
| 中継サービスの不具合 | 以前の版に切り戻す。 |
| 非公開データまたは認証情報の混入 | ただちに管理者に連絡する。履歴の書き換えは単独で行わず、対応を協議する。 |

## 16. 事業継続

| 事象 | 対応 |
|---|---|
| クラウドの機能の停止 | 研究データは PC にあり、測定、統計、作図はクラウドに依存しない。クラウドの機能が停止しても、PC 上の解析は継続できる。 |
| 研究データのバックアップ | 研究データのバックアップは、データを保持する研究室が、自らの方針に従って行う。Cytellect のクラウドは、研究データを保持しない。 |
| 更新の失敗 | 新しい版が起動しない場合は、切り替え前に取得したデータベースの写しと、以前の版に戻す。 |
| 中断したジョブ | 中断したジョブは、自動で再試行する（自動の試行は最大 2 回）。再試行は、以前の結果を上書きしない。 |

## 17. 法令、契約、ライセンス

| 項目 | 内容 |
|---|---|
| プライバシー | 利用者の情報の取り扱いは、[プライバシーポリシー](https://cytellect.app/privacy)に定める。 |
| 送信先でのデータの取り扱い | AI の提供元と推論サーバーでのデータの取り扱いは、[6.2 外部への送信](#62-外部への送信) に示す。 |
| ライセンス | Cytellect 独自のコードは、Apache-2.0 で公開する。配布物には、第三者の部品のライセンス表示を含める。ソースの提供を求めるライセンスの部品については、対応するソースをリリースに添付する（[ライセンスと配布](docs/oss.md)）。 |
| 用途 | Cytellect は研究用のソフトウェアであり、診断、予後、治療の選択を出力しない。 |

## 18. 文書の管理

本書は、Cytellect のセキュリティに関する正本である。方針、仕様、手順を変更するときは、関連する文書を同じ変更で更新する。本書の変更は、プルリクエストと管理者の承認を要する。

| 文書 | 内容 |
|---|---|
| [データ保護と運用](docs/security.md) | データ保護の仕様と運用の詳細 |
| [チーム開発ルール](docs/team-development.md) | 役割、レビュー、研究データと認証情報の取り扱い（§6） |
| [開発の原則](docs/development-principles.md) | 研究データと検証に関する原則 |
| [更新の署名](docs/release-signing.md) | 署名鍵の作成、登録、交換、失効 |
| [CI の構成](docs/ci.md) | CI のジョブと必須の検査 |

## English

This document defines Cytellect's information security principles, controls and vulnerability reporting procedure. The reporting procedure is described in [14.2 Reporting a vulnerability](#142-reporting-a-vulnerability); the Japanese version is in the first half of this document.

**Contents**

- [1. Purpose and scope](#1-purpose-and-scope)
- [2. Security principles](#2-security-principles)
- [3. Organization and responsibilities](#3-organization-and-responsibilities)
- [4. Architecture and trust boundaries](#4-architecture-and-trust-boundaries)
- [5. Information classification and handling](#5-information-classification-and-handling)
- [6. Protection of research data](#6-protection-of-research-data)
- [7. Access control and authentication](#7-access-control-and-authentication)
- [8. Cryptography and key management](#8-cryptography-and-key-management)
- [9. Communications and network security](#9-communications-and-network-security)
- [10. Application security](#10-application-security)
- [11. Logging, monitoring and capacity management](#11-logging-monitoring-and-capacity-management)
- [12. Development and change management](#12-development-and-change-management)
- [13. External services and supply chain](#13-external-services-and-supply-chain)
- [14. Vulnerability management](#14-vulnerability-management)
- [15. Incident response](#15-incident-response)
- [16. Business continuity](#16-business-continuity)
- [17. Legal, contractual and licensing matters](#17-legal-contractual-and-licensing-matters)
- [18. Document control](#18-document-control)

### 1. Purpose and scope

The purpose of this document is to show users, organizations assessing adoption and vulnerability reporters how Cytellect protects research data and user information.

| Category | Content |
|---|---|
| Products and services in scope | This repository's code, the Windows releases (Microsoft Store and EXE), the Docker release, the public site (`cytellect.app`), the relay service (Cytellect Worker) and the inference server |
| Information in scope | Research data, credentials, account information and usage records |
| Activities in scope | Design, development, distribution, operation and vulnerability handling |
| Out of scope | Vulnerabilities in bundled third-party components (Fiji, Cellpose and others) and in the external services themselves. These are handled by their respective maintainers. Issues arising from how Cytellect configures or uses an external service are in scope. |

### 2. Security principles

Cytellect analyses researchers' unpublished microscopy images on the researcher's own PC. Its security design rests on the following principles.

| Principle | Description | Reference |
|---|---|---|
| Data locality | Images, masks, measurements and figures are stored on the researcher's PC or the lab server, never in the Cytellect cloud. Detection, measurement, statistics and figure rendering run in the same place. | [6. Protection of research data](#6-protection-of-research-data) |
| Minimal transmission | Data leaves the PC only when the user invokes a cloud GPU or AI feature, and only to the extent that feature requires. These features are optional; without them, research data never leaves the PC. | [6. Protection of research data](#6-protection-of-research-data) |
| Least privilege and separation | Data, keys and permissions are separated by component. A compromise of the cloud or the repository cannot reach stored research data or installed applications. | [4. Architecture and trust boundaries](#4-architecture-and-trust-boundaries), [15. Incident response](#15-incident-response) |
| Layered verification | Components do not trust each other's input or output; each verifies independently. The relay service verifies requests from the PC, the inference server verifies requests from the relay service, and the PC verifies responses from the cloud. | [10. Application security](#10-application-security) |
| No execution of AI output | AI output is never executed as code. An analysis proposal is treated as a validated draft of settings and is not used until the researcher adopts it. | [10.4 AI assistance](#104-ai-assistance) |
| Verified distribution | The PC runs only updates signed with the maintainer's key. Dependencies and bundled components are pinned by hash. | [13. External services and supply chain](#13-external-services-and-supply-chain) |

### 3. Organization and responsibilities

#### 3.1 Roles

| Role | Responsibilities and authority |
|---|---|
| Maintainer (product owner) | Decides and carries out merges to `main`, production releases and distribution, contracts and settings of external services, approval and revocation of users, and vulnerability handling. |
| Development members | Implement assigned changes, open pull requests and review other members' changes. They hold no authority to merge to `main` or to distribute. |
| AI agents | Implement and verify within the requester's instructions. The requester is responsible for the output. Merging to `main` and production release are limited to cases the maintainer has explicitly instructed for the specific target. |
| Users (researchers, laboratories) | Manage research data on their own PCs or servers. |

#### 3.2 Shared responsibility

Because research data remains under the user's control, responsibilities are divided as follows.

| Area | Cytellect's responsibility | User's responsibility |
|---|---|---|
| Storage of research data | The application stores research data where only the OS user can read it. | Management of the PC and OS accounts, disk encryption and backup |
| Cloud features | Authentication, relay, quota management and display of the transmission scope | The decision to use a feature and consent to the transmission scope |
| Application updates | Provision of signed updates | Applying updates |
| Accounts | Approval, revocation and protection of authentication data | Management of the e-mail address and signing out of devices no longer in use |

### 4. Architecture and trust boundaries

Only the researcher's PC holds research data. Cloud components handle data only for the duration and to the extent that processing requires.

| Component | Role | Data held | Keys and credentials held |
|---|---|---|---|
| Researcher's PC (screen, local server, analysis worker) | Runs detection, measurement, statistics and figure rendering. | All research data | One device token (when signed in to the cloud) |
| Relay service (Cytellect Worker, running on Cloudflare) | Handles sign-in, user approval and quotas, and relays requests to the cloud GPU and the AI. | Account information and usage records. No research data is stored. | Provider API keys; the key used for hashes and approval-link signatures |
| Inference server (running on Modal) | Runs GPU inference for cell detection (Cellpose). | None. Request content is held in memory only while it is processed. | None |
| AI providers (Anthropic, OpenAI) | Generate analysis proposals and discussion drafts. | As defined by each provider's API data terms. | None |
| E-mail delivery (Resend) | Delivers sign-in codes. | The e-mail address and the sign-in code | None |
| Distribution (Microsoft Store, GitHub) | Distributes and updates the application. | Handles no research data. | The update-signing key is held only by the maintainer and the signing environments restricted to `main`. |
| Public site (`cytellect.app`) | Serves the landing page, demo and guides. | Accepts no research images. | None |

### 5. Information classification and handling

| Class | Examples | Location | Handling |
|---|---|---|---|
| Research data (private) | Unpublished images, masks, measurement tables, figures, file names and paths | The researcher's PC or the lab server | Never stored in the cloud. External transmission is limited to the scope defined in [6. Protection of research data](#6-protection-of-research-data). Never included in Git, CI, logs or public places. |
| Credentials | API keys, device tokens and signing keys | Each service's secret store, the settings area on the PC, and the maintainer | Never included in source code, logs or releases. The server stores only hashes. |
| Account information | E-mail address, approval state and times | The relay service's database | Used solely for authentication, approval and quota management. |
| Usage records | Monthly GPU seconds; cost and token counts per analysis proposal | The relay service's database | Used solely for quota and cost management. |
| Public data | Public images whose source and licence have been confirmed | The registered area of the repository | Source, redistribution terms and hashes are recorded; used for tests and the public demo. |

### 6. Protection of research data

#### 6.1 Location and processing

Images, masks, measurement tables and figures are stored in a private area of the researcher's PC or the lab server. Detection, measurement, statistics and figure rendering run in the same place, and original pixel values are never modified.

#### 6.2 External transmission

Data leaves the PC only when the user performs one of the following actions.

| Action | Data transmitted | Destination | Handling at the destination |
|---|---|---|---|
| Cell detection on the cloud GPU | The plane to detect and the detection parameters. For nucleolar detection, the adopted nuclear labels are added. | The inference server (Modal), via the relay service | The relay service forwards the body without reading it, and the inference server processes it in memory only. Neither stores or logs it. |
| Analysis consultation with the AI | The research goal, channel names and recorded stains, field names (by default the file name) and records (condition, experimental unit, pair, acquisition date), image dimensions and pixel size, field and group counts, the current analysis settings and the previous proposal, and per-channel display-scaled previews of one representative field (at most 512 px per side; can be disabled in settings) | Anthropic or OpenAI, via the relay service | The relay service neither stores nor logs the body. Requests to OpenAI set `store: false` so that responses are not stored. Transmitted data is not used for model training. Each provider retains data for abuse monitoring for the period its API terms define. |
| Discussion draft generation by the AI | The saved comparison and the experiment purpose. The comparison comprises the summary on screen (heading and points), the metric's name and definition, the stain name, the region, group, run and channel names, group values, differences and confidence intervals, per-experiment values, counts and their breakdown, aggregation and test settings, the researcher's experimental-unit definition and pairing basis, and the test and its p-value. The purpose defaults to the research goal written to the AI in that workspace. | As above | As above |
| Cloud sign-in | The e-mail address and the sign-in code | Resend | Used solely to deliver the sign-in code by e-mail. |

#### 6.3 Control of transmission

| Control | Implementation |
|---|---|
| Data not transmitted | Data transmitted externally is limited to what 6.2 lists. Per-object measurements and file paths are not transmitted by any action. Fields the user has excluded are used neither for proposals nor for previews. |
| Consent | The scope transmitted to the AI is displayed, and consent obtained, at cloud sign-in and at the first discussion draft. The AI settings panel also displays the scope (decided on 2026-11-16; the summary, n breakdown, method and purpose were added to discussion drafts on 2026-11-17; background in the [AI assistance redesign](docs/drafts/llm-assistant/plan.md)). |
| Transmission confirmation | Transmission to the AI is accepted only for requests that carry the confirmation given by the user's action. The server on the PC rejects requests without it. |
| Protection in transit | All external traffic is encrypted with TLS. |

#### 6.4 Storage, retention and deletion

| Control | Implementation |
|---|---|
| Protection at rest | Data and credentials on the PC are stored where only the OS user can read them. Encryption at rest relies on the OS (BitLocker and similar). |
| Integrity of original images | Original pixel values are never modified. Analysis verifies the hash (SHA-256) of an imported image before using it and writes results to a separate area. |
| Retention | The Windows release retains work data until the user deletes it (the EXE release also offers 24-hour automatic deletion at installation). The Docker release expires and deletes it 24 hours after the last action. Manual retention is available only on the researcher's own PC. |
| Deletion | Expiry and deletion block reads immediately. Inputs, arrays, masks, figures and exported files are then removed. |
| Data stored in the cloud | The Cytellect cloud stores no research data. It stores only account information (e-mail address, approval state and times, hashes of tokens and codes) and usage records (monthly GPU seconds; cost and token counts per analysis proposal). |

#### 6.5 Usage measurement

| Control | Implementation |
|---|---|
| Application telemetry | The installed application and the workspace transmit no usage telemetry. |
| Web analytics on the public site | Web analytics is used only on the public pages of `cytellect.app` (landing page, demo and guides). These pages accept no research images. Advertising use is disabled, and no measurement takes place when the browser signals a tracking opt-out (Do Not Track, Global Privacy Control). |
| Update check | The EXE release consults GitHub's public release list for a newer version (at most once every six hours). No research data or account information is transmitted. |

### 7. Access control and authentication

#### 7.1 Researcher authentication

| Control | Implementation |
|---|---|
| Sign-in code | Researchers authenticate with a six-digit code sent by e-mail. Codes are generated from a cryptographically secure random source and sent only to addresses the maintainer has allowed. A code expires after 10 minutes and can be used once. |
| Attempt limits | Five incorrect entries invalidate a code, and 20 incorrect entries for one address within a day lock that address for 24 hours. Attempts are counted per address, so changing IP addresses yields no additional attempts. |
| Rate limits | Code issuance and verification are rate-limited per IP address (per /64 for IPv6) and per address. |

#### 7.2 Credential management

| Control | Implementation |
|---|---|
| Device token | The only credential a signed-in PC holds is a single device token of 256 random bits. The token expires after 90 days without use and is deleted from both the PC and the server on sign-out. |
| Storage and transmission of the device token | The device token is stored in a settings area separate from research data. The server on the PC includes it in neither responses nor logs. The token is sent only to the URL that issued it, and redirects are not followed. |
| Authentication data stored by the server | Tokens are stored only as SHA-256 hashes and codes only as keyed HMAC-SHA256 hashes. IP addresses are not stored, and rate-limit identifiers are also stored as keyed hashes. Secret values are compared in constant time. |
| Provider keys | The Anthropic, OpenAI, Modal and Resend keys are held only as secrets of the relay service. They are never included on the PC, in a release or in a response from the relay service. |
| Revocation | When the maintainer revokes an address, every device signed in with it is rejected from the next request. |

#### 7.3 Maintainer authentication and privileged access

| Control | Implementation |
|---|---|
| Multi-factor authentication | Every cloud account used for operations requires multi-factor authentication with a passkey or an authenticator app. |
| Admin page authentication | The admin page is placed behind Cloudflare Access (Google sign-in). The relay service also independently verifies the access token (JWT): its signature (RS256 only), issuer, audience, expiry and the maintainer's address. |
| Restriction of admin routes | Admin routes respond only on the designated origin. Other entry points such as `workers.dev` do not respond even to a valid token. |
| User approval | New users are approved through a single-use link signed with HMAC (expiring after 7 days). Opening the link alone approves nothing; approval requires a confirming action on the page. |
| Authority over source code and distribution | Only the maintainer can merge to `main` and sign releases. Details are given in [12. Development and change management](#12-development-and-change-management) and [13.3 Release signing and verification](#133-release-signing-and-verification). |

#### 7.4 The screen on the PC

| Control | Implementation |
|---|---|
| Listening address | The server on the PC listens only on `127.0.0.1`. The Docker release publishes its ports only on `127.0.0.1`. |
| Request validation | The Windows release checks the peer address, host name, origin and the browser's request-origin information (Fetch Metadata) of every request and rejects requests carrying forwarding headers. It additionally requires an anti-CSRF header on state-changing requests, rejecting operations from other sites and through DNS rebinding. The Docker release checks the origin and the anti-CSRF header of state-changing requests. |
| Sessions | Sessions are held in cookies that scripts cannot read and that are not sent with requests from other sites (HttpOnly, SameSite=Strict). The server stores only the SHA-256 of the token. Logging out revokes the session, and the Windows release revokes all sessions when the application exits. |
| Ownership checks | Ownership is verified on every read, and the existence of another user's workspace is not disclosed. An identifier alone confers no permission. |

#### 7.5 Analysis runtime

The Docker analysis worker runs in a container with no network, as a non-root user, on a read-only root filesystem. All privileges (capabilities) are dropped, and privilege escalation is disabled.

### 8. Cryptography and key management

| Purpose | Method | Custody of keys and secrets |
|---|---|---|
| Protection in transit | TLS | Each service's certificates. |
| Device token | 256 bits from a cryptographically secure random source. The server stores only the SHA-256 hash. | The settings area on the PC |
| Sign-in code | Only a keyed HMAC-SHA256 hash is stored. | The hashing key is held as a secret of the relay service. |
| Approval link | Signed with HMAC-SHA256. Comparison is in constant time. | As above |
| Maintainer's access token | The RS256 signature is verified with Cloudflare Access's public keys. | The private key is held by Cloudflare Access. |
| Update signature | An OpenSSH-format Ed25519 signature (SHA-512). The public key is built into the application. | The private key is held only by the maintainer and in the signing environments restricted to `main`. |
| Integrity verification | SHA-256. Applied to the installer, bundled components, detection models, dependency packages and imported images. | Expected hashes are recorded in the repository and in the signed manifest. |
| Provider API keys | — | Held only as secrets of the relay service. |
| Encryption at rest | OS facilities (BitLocker and similar) | Managed by the user's OS. |
| Key rotation and revocation | Rotation and revocation procedures for the update-signing key are defined in [release signing](docs/release-signing.md). Rotating the hashing key invalidates unused codes and approval links. | — |

### 9. Communications and network security

| Path | Controls |
|---|---|
| Within the PC (screen and the server on the PC) | Listens only on `127.0.0.1`; other machines cannot connect. |
| Analysis worker | The Docker analysis worker has no network. CI verifies on the real container that outbound connections are denied. |
| PC to the relay service | Communication with the cloud uses HTTPS only. URLs containing credentials, a query or a fragment are not accepted. Redirects are not followed, response size is limited, and only defined fields are passed to the screen. |
| Relay service to providers | Outbound requests do not follow redirects, so a key cannot be sent to another host. Only headers describing the content type are forwarded, so the user's device token never reaches the destination. |
| Inference server | Modal proxy authentication is required, and unauthenticated requests are not accepted. |
| Update download | Downloads are restricted to GitHub hosts over HTTPS, and redirect targets are checked as well. |
| Use from browsers | The relay service has no setting (CORS) that permits use from other origins, so browsers on other sites cannot use it. |

### 10. Application security

#### 10.1 Relay service

| Control | Implementation |
|---|---|
| No body storage | Request and response bodies, codes and tokens are neither stored nor logged. The platform's log collection is disabled. |
| Detection relay | Detection requests and responses are forwarded as streams without reading the body. |
| Request validation | Body size is limited per route (authentication 4 KiB, analysis proposals 6 MiB, detection 256 MiB). Proposal requests are validated against a defined schema, and previews are confirmed to be PNG and at most 512 px without decoding pixels. Models and prompt versions are restricted to an allowlist. |
| Replay prevention | A proposal request is accepted once per device for each unique identifier (UUID). Sign-in codes and approval links are consumed exactly once by an atomic update. |
| Error handling | Provider errors are replaced with defined codes before they are returned. Neither provider response content nor keys reach the PC through errors. |
| Admin page protection | The admin page forbids loading external resources, embedding in other sites and caching. Admin operations are restricted to same-origin requests. |
| Behaviour on incomplete configuration | When a required setting or key is missing, the affected feature accepts no requests. |

#### 10.2 Inference server

| Control | Implementation |
|---|---|
| Runtime | A single container processes one request at a time. No persistent storage or memory snapshot is used. The container runs as a non-root user, and its image is pinned by digest. |
| Request handling | Request content is held in memory only while it is processed and is never written to a file. Request content, paths and client addresses are not logged. |
| Input validation | The format, size and fields of the input are validated. A request cannot specify a URL, a file path or an arbitrary model. |
| Models | Only public, revision-pinned weights are used, and their SHA-256 is verified before loading. |
| Result verification | The PC accepts a result only when the hashes of the runner, the model and the dependency lock match the installed release. |

#### 10.3 Application on the PC

| Control | Implementation |
|---|---|
| Response protection | Responses forbid caching, content-type sniffing, sending the referrer and embedding in other sites. The screen applies a content security policy that forbids loading external resources and connecting to external hosts. |
| Input acceptance | Accepted input is bounded (100 fields and 2 GiB in total per workspace; a plane of at most 4096×4096 px). Storage uses internal identifiers, and uploaded file names are never used in paths. Paths are verified to lie inside the storage area, and arrays are loaded only in a form that cannot execute code. |
| Error handling | Errors return defined codes only. Internal exceptions and analysis program output are never returned as they are. |
| Job supervision | Jobs are subject to time and memory limits. When supervision cannot confirm a job's state, the analysis processes are terminated and no result is published. |
| Runtime downloads | No code or model is downloaded while an analysis runs. |

#### 10.4 AI assistance

| Control | Implementation |
|---|---|
| No execution of output | AI output is never executed as code. |
| Proposal validation | An analysis proposal is validated on the PC as structured settings consisting only of defined fields and values. Proposals containing undefined fields, or URLs or code-like text in their explanations, are rejected. The channel set must match what was transmitted, and a proposal can neither alter a recorded stain nor establish an unrecorded one. |
| Adoption required | A proposal is a draft and is not used until the researcher adopts it. |
| Separation of computation | After adoption, measurements and statistics are still computed by the shared implementation, irrespective of the proposal's content. A proposal never produces values. |
| State re-check | If workspace data changes, or the workspace expires or is deleted, during the external call, the resulting proposal is discarded. |
| Discussion drafts | A discussion draft is validated for structure only and saved as text with its comparison. It does not modify analysis settings or values. |

### 11. Logging, monitoring and capacity management

| Control | Implementation |
|---|---|
| Information not logged | The relay service does not log request or response bodies, codes or tokens. The server on the PC disables access logging and does not log request bodies, file names or token values. The inference server does not log request content, paths or client addresses. |
| Information recorded | The relay service records account information and usage (monthly GPU seconds; cost and token counts per analysis proposal). |
| Quotas | GPU seconds and AI cost are subject to per-user monthly limits and an overall monthly budget. The maximum cost is reserved before a model call, and requests exceeding a limit are rejected without being forwarded. |
| Cost monitoring | If the cost records become inconsistent, requests to the AI are suspended until the inconsistency is resolved. |
| Concurrency limits | Each user is limited to one GPU request in flight at a time. The inference server processes one request at a time. |
| Input and job limits | The number and size of inputs and the run time and memory of jobs are bounded ([10.3 Application on the PC](#103-application-on-the-pc)). |

### 12. Development and change management

| Control | Implementation |
|---|---|
| Change management | Every change is made through a pull request and is merged to `main` by the maintainer after the required CI succeeds and the change is reviewed. Updates to `main` are restricted by a ruleset, and only the maintainer can merge. |
| Review | A change authored by anyone other than the maintainer requires approval by at least one member other than its author. Review confirms the impact on production, the impact on pixel values, measurements, statistics and figures, and the absence of private data and credentials. |
| Separation of environments | Production credentials are not used in development. Runtime data is stored outside the source tree. Development environments used by several people reject uploads other than registered public files by checking their hash (SHA-256). |
| Test data | Tests, evaluation and the public demo use public images whose source, redistribution terms and hashes are recorded. Private research data is never included in Git, CI or public places. |
| Security testing | Automated tests verify invitation replay and revocation, origin and CSRF validation, ownership checks, and expiry and deletion. CI verifies the isolation settings on the real analysis worker container. Tests verify that the relay service's configuration contains no keys among its plain settings and that log collection is disabled. |
| Automated checks | A hash-verified gitleaks scans the full Git history of `main` and of every pull request for secrets. CodeQL (workflows, JavaScript/TypeScript, Python) runs on pull requests, on `main` and weekly. Dependency vulnerability audits (pip-audit, pnpm audit) and generation of a software bill of materials (SBOM) run in CI. |
| Workflow permissions | The token granted to workflows is read-only by default. Runs originating from forks receive neither write permission nor secrets. |
| Use of AI agents | The requester reviews an AI agent's output before submitting it for review. Merging to `main` and production release are limited to cases the maintainer has explicitly instructed for the specific target. |

### 13. External services and supply chain

#### 13.1 External services

| Service | Purpose | Information received |
|---|---|---|
| Cloudflare | Running the relay service, recording account information and usage, authenticating the admin page | Requests in transit (not stored), account information and usage records |
| Modal | GPU inference for cell detection | The plane to detect, labels and detection parameters (only while processed) |
| Anthropic, OpenAI | Generating analysis proposals and discussion drafts | The data transmitted to the AI as defined in [6.2 External transmission](#62-external-transmission) |
| Resend | Delivering sign-in codes by e-mail | The e-mail address and the sign-in code |
| GitHub | Source code hosting, CI and distribution of the EXE release | Receives no research data. |
| Microsoft Store | Distribution and updates of the Windows release | Receives no research data. |
| Vercel | Serving the public site | Receives no research images. |
| Google Analytics | Web analytics on the public pages | Information about visits to the public pages. Not used in the workspace or the installed application. |

Adding an external service and any setting that incurs cost are decided by the maintainer.

#### 13.2 Dependencies and bundled components

| Control | Implementation |
|---|---|
| Dependency pinning | Python and JavaScript dependencies are pinned by lockfiles with hashes. |
| Verification of bundled components | The bundled Fiji, detection models and Python runtime are verified against SHA-256 hashes at build time. |
| Inspection of releases | Releases are scanned for credentials at build time, and the build fails if any is found. |

#### 13.3 Release signing and verification

| Subject | Controls |
|---|---|
| Microsoft Store release (Windows 11) | Signed by Microsoft; installed and updated by the Microsoft Store. Submissions to the Store are limited to the latest `main` commit approved by the maintainer. |
| Update signature | Each EXE release carries a manifest stating the version, installer name, SHA-256, size, source commit and time of issue, with a signature made with the maintainer's Ed25519 key. |
| Update verification | The application verifies the manifest's signature with its built-in public key before fetching the installer. The installer runs only when the release is newer than the installed one and its SHA-256 and size match the manifest. The hash reported by the distribution host is not a basis of trust. |
| First installation | A first installation of the EXE release can also be verified against the same manifest ([steps, in Japanese](docs/install-windows.ja.md#2-ダウンロードと確認)). |
| Signing key custody | The signing key is held only by the maintainer and in dedicated signing environments restricted to `main`. Manual releases require the maintainer's approval. When the maintainer has enabled automatic EXE distribution, only versions that have passed CI and the distribution tests on protected `main` are published. |
| Release procedure | A release is built from a single commit, which is re-checked at each stage. The commit must be in the history of `main`; runs originating from forks and reuse of a tag are refused. Published files must match the tested files in size and hash. |

### 14. Vulnerability management

#### 14.1 Supported versions

| Version | Security fixes |
|---|---|
| The Microsoft Store release | Provided (updated to the latest version by the Microsoft Store) |
| The latest EXE release | Provided |
| `main` (`cytellect.app` and the cloud features) | Provided |
| Earlier EXE releases | Not provided (move to the latest release through the in-app update) |

#### 14.2 Reporting a vulnerability

Report vulnerabilities through GitHub's private reporting feature. Selecting **Report a vulnerability** under the repository's **Security** tab submits a report visible only to the reporter and the repository maintainers ([report form](https://github.com/genellect/cytellect/security/advisories/new)). Do not describe vulnerabilities in public places such as issues, pull requests or discussions.

Include the following in a report.

- The affected commit, or the version of the Windows release
- Reproduction steps
- The expected impact

Use synthetic or public data for reproduction.

#### 14.3 Response to a report

1. Reasonable reports receive a reply within three days.
2. The affected scope and severity are assessed and shared with the reporter.
3. The issue is fixed in a private security advisory and the fixed version is released. The public site and cloud features are deployed to production, and the Windows releases are distributed through the Microsoft Store and a signed update.
4. After the release, the security advisory is published and a CVE is requested where appropriate. The reporter is credited by name on request.

Published security advisories are available in the [list](https://github.com/genellect/cytellect/security/advisories).

### 15. Incident response

#### 15.1 Impact of a compromise

Data, keys and permissions are separated so that the compromise of a single component does not propagate.

| Compromised component | Reachable | Not reachable |
|---|---|---|
| A researcher's cloud account | That user's GPU and analysis-proposal quota (up to the monthly limits) | Research data (none is stored in the cloud) |
| The relay service | Data relayed during the compromise, and tampering with inference results or proposals | Stored research data and application updates (the signing key is held elsewhere) |
| Write access to the repository | Branches and pull requests | `main` (merging requires the maintainer) and installed PCs (updates require a signature made with the maintainer's key) |

#### 15.2 Containment and recovery

| Event | Response |
|---|---|
| Misuse of a user account | The maintainer revokes the address. Every device signed in with it is rejected from the next request. |
| Leak of a credential | The credential is invalidated and reissued immediately. |
| Leak of the key used for hashes and signatures | The key is rotated. Rotation invalidates unused sign-in codes and approval links. |
| Leak or loss of the update-signing key | The revocation and rotation procedures defined in [release signing](docs/release-signing.md) are followed. |
| Fault in the relay service | The service is rolled back to a previous version. |
| Inclusion of private data or credentials | The maintainer is notified immediately. History is not rewritten unilaterally; the response is agreed first. |

### 16. Business continuity

| Event | Response |
|---|---|
| Outage of the cloud features | Research data is on the PC, and measurement, statistics and figure rendering do not depend on the cloud. Analysis on the PC continues when the cloud features are unavailable. |
| Backup of research data | The laboratory holding the data backs it up under its own policy. The Cytellect cloud holds no research data. |
| Failed update | If the new version fails to start, the application restores the database copy taken before the switch and the previous version. |
| Interrupted jobs | An interrupted job is retried automatically (at most two automatic attempts). A retry does not overwrite a previous result. |

### 17. Legal, contractual and licensing matters

| Item | Content |
|---|---|
| Privacy | The handling of user information is defined in the [privacy policy](https://cytellect.app/privacy) (in Japanese). |
| Data handling at destinations | Data handling at the AI providers and the inference server is described in [6.2 External transmission](#62-external-transmission). |
| Licensing | Cytellect's own code is published under Apache-2.0. Releases include the licence notices of third-party components. For components whose licences require source to be provided, the corresponding source is attached to the release ([licensing and distribution](docs/oss.md), in Japanese). |
| Intended use | Cytellect is research software and does not output a diagnosis, prognosis or treatment choice. |

### 18. Document control

This document is the authoritative statement of Cytellect's security. When a policy, specification or procedure changes, the related documents are updated in the same change. Changes to this document require a pull request and the maintainer's approval.

| Document | Content |
|---|---|
| [Data protection and operations](docs/security.md) | The data-protection specification and operating details |
| [Team development rules](docs/team-development.md) | Roles, review, and the handling of research data and credentials (section 6) |
| [Development principles](docs/development-principles.md) | Principles on research data and verification (in Japanese) |
| [Release signing](docs/release-signing.md) | Creating, registering, rotating and revoking the signing key (in Japanese) |
| [CI configuration](docs/ci.md) | CI jobs and required checks (in Japanese) |
