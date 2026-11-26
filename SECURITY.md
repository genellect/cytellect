# セキュリティポリシー

Cytellect は、未発表の顕微鏡画像を研究者の PC 上で解析する。画像、輪郭、測定値、図は PC に保存し、Cytellect のクラウドには保存しない。PC の外部へ送信するのは、研究者がクラウド GPU による検出または AI の機能を実行したときの、その処理に必要な情報だけである。

中継サービスと推論サーバーは、研究データを保存せず、更新の署名鍵も持たない。アプリは、組み込んだ公開鍵で署名を検証した更新だけを実行する。このため、研究者のアカウント、中継サービス、リポジトリへの書き込み権限のいずれが攻撃者の手に渡っても、PC 上の研究データと導入済みのアプリには到達できない。

対策の実装と試験は、このリポジトリで公開している。脆弱性の報告は、[非公開の報告フォーム](https://github.com/genellect/cytellect/security/advisories/new)で受け付ける（[13. 脆弱性への対応](#13-脆弱性への対応)）。

[英語版（English）](#english)

- [1. 設計の原則](#1-設計の原則)
- [2. 構成とデータの流れ](#2-構成とデータの流れ)
- [3. 脅威と対策](#3-脅威と対策)
- [4. 研究データの保護](#4-研究データの保護)
- [5. 認証と認証情報](#5-認証と認証情報)
- [6. 中継サービス](#6-中継サービス)
- [7. 推論サーバー](#7-推論サーバー)
- [8. PC 上のアプリ](#8-pc-上のアプリ)
- [9. AI による解析支援](#9-ai-による解析支援)
- [10. 暗号方式と鍵の管理](#10-暗号方式と鍵の管理)
- [11. 配布物とサプライチェーン](#11-配布物とサプライチェーン)
- [12. 認証情報と鍵の失効](#12-認証情報と鍵の失効)
- [13. 脆弱性への対応](#13-脆弱性への対応)
- [14. 関連文書](#14-関連文書)

## 1. 設計の原則

| 原則 | 内容 | 詳細 |
|---|---|---|
| 研究データは PC に置く | 画像、輪郭、測定値、図は、研究者の PC または研究室のサーバーに保存する。検出、測定、統計、作図も同じ場所で実行する。 | [4. 研究データの保護](#4-研究データの保護) |
| 外部へ送信するのは、実行した処理に必要な情報だけ | 研究データを PC の外部へ送信するのは、研究者がクラウド GPU による検出または AI の機能を実行したときだけである。どちらの機能も、使わなければ研究データは PC の外部に出ない。 | [2.2 PC の外部へ送信する情報](#22-pc-の外部へ送信する情報) |
| クラウドは研究データを保存しない | 中継サービスと推論サーバーは、研究データを要求の処理中だけ扱い、保存もログへの記録もしない。 | [6. 中継サービス](#6-中継サービス)、[7. 推論サーバー](#7-推論サーバー) |
| 1 か所の侵害は全体に及ばない | データ、鍵、権限を構成要素ごとに分離する。研究者のアカウント、中継サービス、リポジトリへの書き込み権限のいずれを取得しても、保存された研究データと導入済みのアプリには到達できない。 | [3. 脅威と対策](#3-脅威と対策) |
| 境界を越える入力は、受け取る側が検証する | 構成要素は、境界を越えて届く入力をそれぞれ独立に検証する。 | [2.4 信頼境界](#24-信頼境界) |
| AI の出力は、研究者の採用なしに解析を変更しない | AI の出力は、コードとして実行しない。解析の提案は、PC 上で検証した設定の下書きとして扱う。 | [9. AI による解析支援](#9-ai-による解析支援) |
| 更新と依存パッケージは、署名とハッシュで検証する | PC は、署名を検証した更新だけを実行する。依存パッケージと同梱物は、ハッシュで固定する。 | [11. 配布物とサプライチェーン](#11-配布物とサプライチェーン) |
| 解析はクラウドに依存しない | 測定、統計、作図は PC 上で完結し、クラウドの機能が停止しても継続できる。 | [2.1 構成要素](#21-構成要素) |

## 2. 構成とデータの流れ

### 2.1 構成要素

提供形態は、Windows 版（Microsoft Store 版と EXE 版）と、PC または研究室のサーバーで動かす Docker 版である。研究データを保持するのは、アプリを動かすその PC またはサーバーだけである。以下では、これを PC と呼ぶ。

| 構成要素 | 役割 | 保持するデータ | 保持する鍵と認証情報 |
|---|---|---|---|
| PC（画面、PC 上のサーバー、解析ワーカー） | 検出、測定、統計、作図を実行する。 | 研究データのすべて | 端末トークン 1 つ（クラウドにログインした場合） |
| 中継サービス（Cytellect Worker。Cloudflare Workers 上で動作する） | ログイン、利用の承認、利用枠の管理を行い、クラウド GPU と AI への要求を中継する。 | アカウント情報と利用量の記録 | 外部サービスの API キー、HMAC 鍵（ログインコード、承認リンク、レート制限の識別子に、用途ごとに領域を分けて使用する） |
| 推論サーバー（Modal 上で動作する） | 細胞の検出（Cellpose）の GPU 推論を実行する。 | なし | なし |
| 配布（Microsoft Store、GitHub） | アプリを配布し、更新する。 | なし | なし（更新の署名鍵は、`main` からの実行に限定した署名環境に置く） |
| 公開サイト（`cytellect.app`） | ランディングページ、デモ、ガイドを提供する。 | なし（研究画像を受け付けない） | なし |

### 2.2 PC の外部へ送信する情報

研究データを PC の外部へ送信するのは、研究者が次の 3 つの操作を実行したときだけである。

| 操作 | 送信する情報 | 送信先 | 送信先での取り扱い |
|---|---|---|---|
| クラウド GPU による細胞の検出 | 検出対象の 1 プレーン（1 視野・1 チャンネルの原寸の画像 1 枚）と検出条件。核小体の検出では、採用済みの核のラベル（核の領域を示す画像）を加える。 | 中継サービスを経由して推論サーバー | 中継サービスは保存しない。推論サーバーはメモリ上でのみ処理し、保存しない。 |
| AI への相談 | 研究の目的、チャンネルと視野の記録、画像の寸法、現在の解析設定、代表的な 1 視野の縮小画像（内訳は下記） | 中継サービスを経由して Anthropic または OpenAI | 中継サービスは保存しない。AI の提供元は、モデルの学習に使用しない。 |
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

OpenAI には、応答を保存しない設定（`store: false`）で送信する。AI の提供元は、不正利用の監視のために、各社の API の規約が定める期間、データを保持する。

研究データを含まない通信は、次の 3 つである。導入したアプリと作業画面は、利用状況の計測情報を送信しない。

| 通信 | 送信する情報 | 送信先 |
|---|---|---|
| クラウドへのログイン | メールアドレスとログインコード | 中継サービス（ログインコードのメール送信は Resend） |
| クラウドの機能の利用 | 端末トークン | 中継サービス |
| 更新の確認（EXE 版） | なし。GitHub の公開リリース一覧を取得する。確認の間隔は 6 時間とし、取得できなかった場合は 15 分後に再確認する。 | GitHub |

### 2.3 外部サービス

| サービス | 用途 | 受け取る情報 |
|---|---|---|
| Cloudflare | 中継サービスの実行、アカウント情報と利用量の記録、管理画面の認証 | 中継中の要求（保存しない）、アカウント情報、利用量の記録 |
| Modal | 細胞の検出の GPU 推論 | 検出対象のプレーン、核のラベル、検出条件（処理中のみ） |
| Anthropic、OpenAI | 解析の提案と考察の下書きの生成 | [2.2 PC の外部へ送信する情報](#22-pc-の外部へ送信する情報) に示す、AI への送信情報 |
| Resend | ログインコードのメール送信 | メールアドレスとログインコード |
| GitHub | ソースコードの管理、CI、EXE 版の配布 | なし |
| Microsoft Store | Windows 版の配布と更新 | なし |
| Vercel | 公開サイトの提供 | なし |
| Google Analytics | 公開ページ（ランディングページ、デモ、ガイド）のアクセス解析 | 公開ページの閲覧に関する情報。広告目的の利用は無効にし、ブラウザが追跡の拒否（Do Not Track、Global Privacy Control）を示す場合は計測しない。作業画面と導入したアプリでは使用しない。 |

### 2.4 信頼境界

| 境界 | 通過するもの | 受け取る側の検証 |
|---|---|---|
| ブラウザ → PC 上のサーバー | 画面からの要求 | 接続元、Host、Origin、Fetch Metadata、CSRF 対策のヘッダー、セッション、所有者 |
| PC → 中継サービス | 検出と AI への要求 | 端末トークン、アカウントの状態、利用枠、本文のサイズと形式、要求の識別子 |
| 中継サービス → 推論サーバー | 検出の要求 | Modal のプロキシ認証、入力の形式・サイズ・項目 |
| 中継サービス → PC | 検出の結果、解析の提案、考察の下書き | バージョンを示すハッシュの照合、提案の検証、研究者の採用 |
| 配布元 → PC | 更新 | 署名、バージョン、SHA-256、サイズ |

## 3. 脅威と対策

| 脅威（攻撃者の能力） | 対策 | 影響の範囲 | 詳細 |
|---|---|---|---|
| 研究者のメールまたは端末トークンを取得した攻撃者 | 研究データをクラウドに保存しない。利用枠に、アカウントごと・月ごとの上限を設ける。アカウントの失効は、すべての端末に次の要求から及ぶ。 | 影響は、そのアカウントの当月の利用枠に限られる。研究データには到達できない。 | [5.2 認証情報の保管](#52-認証情報の保管)、[12. 認証情報と鍵の失効](#12-認証情報と鍵の失効) |
| 中継サービスを侵害した攻撃者 | 中継サービスは本文を保存しない。研究データと更新の署名鍵は、中継サービスの外にある。PC は、提案をスキーマで検証し、研究者の採用を要求する。 | 影響は、侵害の間に中継される要求と、中継サービスが保持する API キーとアカウント情報に限られる。提案は、PC 上の検証と研究者の採用を経なければ解析に使用されない。保存された研究データ、導入済みのアプリ、更新の署名鍵には到達できない。 | [6. 中継サービス](#6-中継サービス)、[9. AI による解析支援](#9-ai-による解析支援) |
| リポジトリへの書き込み権限を取得した攻撃者 | `main` への反映は、ルールセットで管理者に限定する。更新の署名鍵は、`main` からの実行に限定した署名環境に置く。PC は、この鍵で署名された更新だけを実行する。 | 影響は、ブランチとプルリクエストに限られる。`main` と導入済みの PC には到達できない。 | [11.2 リリースの検証](#112-リリースの検証)、[11.4 リポジトリと CI](#114-リポジトリと-ci) |
| 配布経路で更新を差し替える、または古いバージョンへ戻す攻撃者 | アプリは、組み込んだ公開鍵でマニフェストの署名を検証し、インストーラーの SHA-256 とサイズを照合する。現在より新しいバージョンだけを受け入れる。 | 署名とハッシュが一致しないインストーラーと、現在のバージョン以下の更新は、実行されない。 | [11.1 更新の署名と検証](#111-更新の署名と検証) |
| 依存パッケージ、同梱物、検出モデルを取得経路で差し替える攻撃者 | 依存パッケージは、ロックファイルでバージョンとハッシュを固定する。同梱物と検出モデルは、SHA-256 を照合する。 | ハッシュが一致しないものは、取り込まれない。 | [11.3 依存パッケージと同梱物](#113-依存パッケージと同梱物) |
| 悪意のあるサイトから PC 上のサーバーへ要求を送る攻撃者（CSRF、DNS リバインディング） | PC 上のサーバーは `127.0.0.1` でのみ待ち受け、要求の Host、Origin、Fetch Metadata を照合する。セッションの Cookie は、他のサイトからの要求には送信されない。 | 他のサイトからの要求は、拒否される。 | [8.1 PC 上のサーバーへのアクセス](#81-pc-上のサーバーへのアクセス) |
| 通信経路上で盗聴または改ざんする攻撃者 | PC と中継サービスが外部へ行う通信は HTTPS に限り、サーバー証明書を検証する。更新は、通信経路とは独立に署名で検証する。 | 通信の内容は読み取れない。改ざんされた更新は、実行されない。 | [10. 暗号方式と鍵の管理](#10-暗号方式と鍵の管理) |
| ログインコードを総当たりする攻撃者 | 誤入力の回数を、ログインコードごととメールアドレスごとに制限する。ログインコードの送信と検証には、レート制限を設ける。 | 試行は、1 つのメールアドレスにつき 1 日 20 回に限られる。6 桁のログインコードに対する 1 日あたりの成功確率は、2×10⁻⁵ 以下である。 | [5.1 研究者のログイン](#51-研究者のログイン) |
| 中継サービスのデータベースを取得した攻撃者 | 端末トークンは SHA-256 のハッシュだけを保存する。ログインコードは、データベースの外に置く鍵による HMAC-SHA256 だけを保存する。IP アドレスと研究データは保存しない。 | 影響は、メールアドレス、承認の状態、利用量の記録に限られる。有効な認証情報と研究データは含まれない。 | [5.2 認証情報の保管](#52-認証情報の保管)、[4.3 クラウドが保存する情報](#43-クラウドが保存する情報) |
| GPU と AI の費用を使い尽くそうとする、正規の研究者または取得されたトークン | アカウントごと・月ごとの上限と、全体の月間予算を設ける。費用は、モデルの呼び出しの前に予約する。GPU の要求は、アカウントごとに同時 1 件とする。 | 費用は、設定した月間予算を超えない。 | [6. 中継サービス](#6-中継サービス) |
| 管理画面と承認の経路を狙う攻撃者（別の入口からの到達、承認リンクの偽造、リンクの自動取得による承認） | 管理用の経路は、指定したオリジンでのみ応答する。中継サービスは、Cloudflare Access のトークンを独自に検証する。承認リンクは HMAC で署名した 1 回限りのもので、承認には画面での確認の操作を要する。 | 偽造したリンクと、開いただけのリンクでは、承認は成立しない。 | [5.3 管理画面](#53-管理画面) |
| 推論サーバーへ直接要求を送る攻撃者 | Modal のプロキシ認証を必須とする。要求は、URL、ファイルのパス、任意のモデルの指定を受け付けない。 | 認証のない要求は、受理されない。 | [7. 推論サーバー](#7-推論サーバー) |
| 誤った AI の出力と、入力に仕込まれた指示に誘導された AI の出力（プロンプトインジェクション） | AI の出力は、コードとして実行しない。提案はスキーマで検証し、研究者が採用するまで使用しない。測定と統計は、共通の実装だけが計算する。 | 解析の設定と数値は、研究者の採用なしには変わらない。 | [9. AI による解析支援](#9-ai-による解析支援) |
| 細工された入力ファイル | 入力の形式、寸法、サイズを検証する。配列は pickle を無効にして読み込む。解析のプロセスは、実行時間とメモリの上限の下で動作する。 | 形式と上限を満たさない入力は、解析の前に拒否される。Docker 版の解析は、ネットワークのない非 root・読み取り専用のコンテナの中に閉じる。 | [8.2 入力、応答、クラウドとの通信](#82-入力応答クラウドとの通信)、[8.3 解析ワーカーの隔離と監視](#83-解析ワーカーの隔離と監視) |
| 研究室のサーバーを共有する他の利用者による、ワークスペースの識別子の推測 | 要求のたびに、セッションの所有者とワークスペースの所有者を照合する。一致しない要求には、存在しない場合と同じ応答を返す。 | 他者のワークスペースは、内容も存在の有無も得られない。 | [8.1 PC 上のサーバーへのアクセス](#81-pc-上のサーバーへのアクセス) |
| フォークからのプルリクエストで CI を悪用する攻撃者 | ワークフローのトークンは、既定で読み取り専用とする。フォークに由来する実行には、書き込み権限とシークレットを与えない。リリースは、フォークに由来する実行を拒否する。 | シークレットと署名環境には到達できない。 | [11.4 リポジトリと CI](#114-リポジトリと-ci) |

## 4. 研究データの保護

### 4.1 外部への送信の範囲と同意

| 対策 | 仕組み | 実装と試験 |
|---|---|---|
| 送信の範囲 | 外部へ送信する情報は、[2.2 PC の外部へ送信する情報](#22-pc-の外部へ送信する情報) に示したものに限る。核ごとの測定値とファイルのパスは、どの操作でも送信しない。検出では、ファイル名、ワークスペースの名前、条件、ほかのチャンネルを送信しない。研究者が除外した視野は、提案にも縮小画像にも使用しない。 | [`proposals.py`](services/api/src/cytellect_api/proposals.py) [`discussions.py`](services/api/src/cytellect_api/discussions.py) [`cellpose_engine.py`](packages/analysis/src/cytellect_analysis/cellpose_engine.py) [`test_proposals.py`](tests/test_proposals.py) [`test_cellpose_remote.py`](tests/test_cellpose_remote.py) |
| 同意 | AI への送信範囲は、クラウドへのログイン時と最初の考察の生成時に画面に表示し、同意を得たうえで送信する。送信範囲は、AI の設定画面にも常に表示する。 | [`CloudAccount.tsx`](apps/web/src/components/workspace/CloudAccount.tsx) [`ConnectedWorkspace.tsx`](apps/web/src/components/workspace/review/ConnectedWorkspace.tsx) [`AiSettings.tsx`](apps/web/src/components/workspace/AiSettings.tsx) |
| 送信の確認 | PC 上のサーバーは、研究者が画面で送信を確認した要求だけを AI へ送信し、確認のない要求を拒否する。 | [`proposals.py`](services/api/src/cytellect_api/proposals.py) [`discussions.py`](services/api/src/cytellect_api/discussions.py) [`test_proposals.py`](tests/test_proposals.py) [`test_result_discussion_api.py`](tests/test_result_discussion_api.py) |

### 4.2 保存と削除

| 対策 | 仕組み | 実装と試験 |
|---|---|---|
| 保存場所 | PC 上のデータと認証情報は、OS の利用者のプロファイルの中の、その利用者だけが読み取れる領域に保存する（Windows 版は `%LOCALAPPDATA%\Cytellect`）。保存時の暗号化は、OS のディスク暗号化（BitLocker など）による。 | [`local.py`](services/api/src/cytellect_api/local.py) [`cloud_account.py`](services/api/src/cytellect_api/cloud_account.py) [`local_setup.ps1`](scripts/local_setup.ps1) |
| 原画像の完全性 | 原画像の画素値は変更しない。取り込んだ画像は、SHA-256 を照合してから解析に使用し、結果は別の領域に書き出す。 | [`worker/regions.py`](services/worker/src/cytellect_worker/regions.py) |
| 削除 | 失効または削除の時点で、読み出しをただちに遮断する。続いて、入力、配列、輪郭、図、書き出したファイルを削除する。 | [`app.py`](services/api/src/cytellect_api/app.py) [`worker/main.py`](services/worker/src/cytellect_worker/main.py) [`test_workspace_retention.py`](tests/test_workspace_retention.py) |

作業データの保持期間は、提供形態ごとに次のとおりである。

| 提供形態 | 作業データの保持 |
|---|---|
| Microsoft Store 版 | 研究者が削除するまで保持する。 |
| EXE 版 | 研究者が削除するまで保持する。導入時に、24 時間での自動削除を選択できる。 |
| Docker 版 | 最後の操作から 24 時間で失効させ、削除する。`127.0.0.1` でのみ待ち受ける構成では、削除するまでの保持を選択できる。 |

実装と試験：[`config.py`](services/api/src/cytellect_api/config.py) [`test_workspace_retention.py`](tests/test_workspace_retention.py)

### 4.3 クラウドが保存する情報

Cytellect のクラウドが保存する情報は、次の 4 区分に限る。研究データは含まない。

| 区分 | 内容 | 用途 |
|---|---|---|
| アカウント情報 | メールアドレス、承認の状態、申請・承認・失効の日時、アカウントごとの利用枠 | 承認、失効、利用枠の管理 |
| 認証の記録 | 端末トークン、ログインコード、承認リンク、招待のハッシュと、その有効期限 | 認証 |
| レート制限と再送防止の記録 | HMAC で計算した識別子と回数、要求の識別子（UUID） | 総当たりと再送の防止 |
| 利用量の記録 | 月ごとの GPU の秒数、実行中の GPU の要求の開始時刻、解析の提案ごとの費用・AI の入出力トークン数・モデル名・プロンプトのバージョン | 利用枠と費用の管理 |

実装と試験：[`migrations/`](services/proposal-worker/migrations) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`store.ts`](services/proposal-worker/src/store.ts) [`store.test.ts`](services/proposal-worker/src/store.test.ts)

## 5. 認証と認証情報

### 5.1 研究者のログイン

| 対策 | 仕組み | 実装と試験 |
|---|---|---|
| ログインコード | 研究者は、メールで受け取った 6 桁のログインコードで認証する。ログインコードは、暗号論的に安全な乱数から偏りなく生成し、管理者が許可したメールアドレスにのみ送信する。有効期間は 10 分で、1 回だけ使用できる。 | [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`mail.ts`](services/proposal-worker/src/mail.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |
| 誤入力の制限 | 5 回の誤入力でログインコードを無効にし、同じメールアドレスで 1 日 20 回の誤入力があれば 24 時間ロックする。誤入力はメールアドレス単位で数えるため、接続元の IP アドレスを変えても、試行できる回数は増えない。 | [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |
| レート制限 | ログインコードの送信は、IP アドレス単位（IPv6 は /64 単位）で 1 時間 20 回、メールアドレス単位で 1 時間 6 回かつ 1 日 10 回に制限する。検証は、IP アドレス単位で 1 時間 30 回に制限する。 | [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |

### 5.2 認証情報の保管

| 対策 | 仕組み | 実装と試験 |
|---|---|---|
| 端末トークン | クラウドへのログインで PC が保持する認証情報は、256 bit の乱数による端末トークン 1 つに限る。端末トークンは、90 日間使用しなければ失効し、ログアウト時に PC と中継サービスの双方から削除する。 | [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`http.ts`](services/proposal-worker/src/http.ts) [`cloud_account.py`](services/api/src/cytellect_api/cloud_account.py) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) [`test_cloud_account.py`](tests/test_cloud_account.py) |
| PC 上での保管と送信 | 端末トークンは、研究データとは別の設定領域に保存する。PC 上のサーバーは、端末トークンを応答にもログにも含めない。端末トークンは発行元の URL にのみ送信し、リダイレクトには従わない。 | [`cloud_account.py`](services/api/src/cytellect_api/cloud_account.py) [`test_cloud_account.py`](tests/test_cloud_account.py) |
| 中継サービスでの保管 | 端末トークンは SHA-256、ログインコードは HMAC-SHA256（用途とメールアドレスを入力に含める）によるハッシュだけを保存する。IP アドレスは保存せず、レート制限の識別子も HMAC で計算した値として保存する。トークンとログインコードの照合は、定数時間で行う。 | [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`http.ts`](services/proposal-worker/src/http.ts) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |
| 外部サービスの API キー | Anthropic、OpenAI、Modal、Resend の API キーは、中継サービスのシークレットとしてのみ保持する。PC、配布物、中継サービスの応答には含めない。配布物は、ビルド時に認証情報の混入を走査する。 | [`wrangler.toml.example`](services/proposal-worker/wrangler.toml.example) [`deployment.test.mjs`](services/proposal-worker/scripts/deployment.test.mjs) [`build_windows_installer.py`](scripts/build_windows_installer.py) |
| アカウントの失効 | 管理者がアカウントを失効させた時点で、そのアカウントでログインしたすべての端末の要求を拒否する。 | [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |

### 5.3 管理画面

| 対策 | 仕組み | 実装と試験 |
|---|---|---|
| 多要素認証 | 運用に使用する外部サービスのアカウントは、すべてパスキーまたは認証アプリによる多要素認証を必須とする。 | 運用上の設定 |
| 管理画面の認証 | 管理画面は、Cloudflare Access（Google ログイン）の背後に置く。中継サービスも、Cloudflare Access が発行した JWT について、署名（アルゴリズムは RS256 に固定）、発行者、オーディエンス、有効期限、管理者のメールアドレスを独自に検証する。 | [`access.ts`](services/proposal-worker/src/access.ts) [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`access.test.ts`](services/proposal-worker/src/access.test.ts) [`wrangler.toml.example`](services/proposal-worker/wrangler.toml.example) [`proposal-deployment.md`](docs/proposal-deployment.md) |
| 管理用の経路の限定 | 管理用の経路は、指定したオリジンでのみ応答する。`workers.dev` などの別の入口からは、有効なトークンがあっても応答しない。 | [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) [`wrangler.toml.example`](services/proposal-worker/wrangler.toml.example) |
| 利用の承認 | 新しい研究者は、HMAC で署名した 1 回限りのリンク（有効期間 7 日）で承認する。リンクを開いただけでは承認されず、承認には画面での確認の操作を要する。 | [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |
| 画面の保護 | 管理画面は、外部リソースの読み込み、フレームへの埋め込み、キャッシュを禁止する。管理の操作は、同一オリジンからの要求に限る。 | [`admin-page.ts`](services/proposal-worker/src/admin-page.ts) [`cloud.ts`](services/proposal-worker/src/cloud.ts) |

## 6. 中継サービス

| 対策 | 仕組み | 実装と試験 |
|---|---|---|
| 保存とログ | 要求と応答の本文、ログインコード、端末トークンを保存せず、ログに記録しない。Cloudflare Workers のログ収集は無効にしている。 | [`index.ts`](services/proposal-worker/src/index.ts) [`wrangler.toml.example`](services/proposal-worker/wrangler.toml.example) [`deployment.test.mjs`](services/proposal-worker/scripts/deployment.test.mjs) |
| 検出の中継 | 検出の要求と応答は、本文を解釈も保持もせずに、ストリームのまま転送する。本文のサイズは Content-Length で判定する。推論サーバーへ転送するヘッダーは、内容の種別と長さを示すものに限り、研究者の端末トークンは渡さない。 | [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |
| 要求の検証 | 本文のサイズを経路ごとに制限する（認証 4 KiB、解析の提案と考察 6 MiB、検出 256 MiB）。提案の要求はスキーマで検証し、縮小画像は PNG であることと 512 px 以下であることを、画素を復号せずに確認する。モデルとプロンプトのバージョンは、許可リストに限る。 | [`index.ts`](services/proposal-worker/src/index.ts) [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`schema.ts`](services/proposal-worker/src/schema.ts) [`discussion.ts`](services/proposal-worker/src/discussion.ts) [`index.test.ts`](services/proposal-worker/src/index.test.ts) |
| 再送（リプレイ）の防止 | 提案の要求は、端末ごとに一意の識別子（UUID）を 1 回だけ受理する。ログインコードと承認リンクは、原子的な更新で 1 回だけ消費する。 | [`index.ts`](services/proposal-worker/src/index.ts) [`store.ts`](services/proposal-worker/src/store.ts) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`index.test.ts`](services/proposal-worker/src/index.test.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |
| 外部への要求 | 外部への要求は、リダイレクトに従わない。API キーが別のホストへ送信される経路はない。外部サービスのエラーは、あらかじめ定めたエラーコードと HTTP ステータスだけを返す。 | [`openai.ts`](services/proposal-worker/src/openai.ts) [`anthropic.ts`](services/proposal-worker/src/anthropic.ts) [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`mail.ts`](services/proposal-worker/src/mail.ts) [`index.ts`](services/proposal-worker/src/index.ts) |
| 他のオリジンからの要求 | 中継サービスは、他のオリジンを許可する CORS のヘッダーを返さない。端末トークンは Authorization ヘッダーで送信するため、他のサイトのページからの要求は、ブラウザのプリフライトで遮断される。 | [`http.ts`](services/proposal-worker/src/http.ts) [`cloud.ts`](services/proposal-worker/src/cloud.ts) |
| 利用枠 | GPU の秒数と AI の費用には、アカウントごと・月ごとの上限と、全体の月間予算を設ける。上限を超える要求は、外部サービスへ転送せずに拒否する。GPU の要求は、アカウントごとに同時 1 件に限る。 | [`store.ts`](services/proposal-worker/src/store.ts) [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`store.test.ts`](services/proposal-worker/src/store.test.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |
| 費用の予約と整合性 | モデルの呼び出しの前に、その要求の最大費用を原子的に予約する。費用の記録に不整合が生じた場合は、解消するまで AI への要求を停止する。 | [`store.ts`](services/proposal-worker/src/store.ts) [`index.ts`](services/proposal-worker/src/index.ts) [`store.test.ts`](services/proposal-worker/src/store.test.ts) |
| 設定の欠落 | 必要な設定または鍵が欠けている機能は、要求を受け付けない。 | [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`index.ts`](services/proposal-worker/src/index.ts) [`deployment.test.mjs`](services/proposal-worker/scripts/deployment.test.mjs) |

## 7. 推論サーバー

| 対策 | 仕組み | 実装と試験 |
|---|---|---|
| 実行環境 | 単一のコンテナで、同時に 1 件の要求だけを処理する。永続ボリュームとメモリのスナップショットは使用しない。コンテナは非 root で動作し、イメージはダイジェストで固定する。 | [`modal_cellpose.py`](infra/modal_cellpose.py) |
| 認証 | Modal のプロキシ認証を必須とし、認証のない要求を受け付けない。 | [`modal_cellpose.py`](infra/modal_cellpose.py) [`cloud.ts`](services/proposal-worker/src/cloud.ts) |
| 要求の取り扱い | 要求の内容は、処理中のみメモリ上に保持し、ファイルに書き込まない。要求の内容、パス、接続元の IP アドレスをログに記録しない。 | [`server.py`](engines/cellpose/server.py) |
| 入力の検証 | 入力の形式、サイズ、項目を検証し、配列は pickle を無効にして読み込む。要求は、URL、ファイルのパス、任意のモデルの指定を受け付けない。 | [`server.py`](engines/cellpose/server.py) |
| モデル | 公開されている重みをリビジョンで固定して使用し、SHA-256 を照合してから読み込む。実行中は、ネットワークからの取得を無効にする。 | [`runner.py`](engines/cellpose/runner.py) [`cellpose/runtime.lock.json`](engines/cellpose/runtime.lock.json) |

## 8. PC 上のアプリ

### 8.1 PC 上のサーバーへのアクセス

| 対策 | 仕組み | 実装と試験 |
|---|---|---|
| 待ち受け | PC 上のサーバーは、`127.0.0.1` でのみ待ち受ける。Docker 版は、ポートを `127.0.0.1` にのみ公開する。 | [`local.py`](services/api/src/cytellect_api/local.py) [`compose.yaml`](compose.yaml) [`test_local.py`](tests/test_local.py) |
| 要求の検証（Windows 版） | 要求ごとに、接続元、Host、Origin、Fetch Metadata（Sec-Fetch-Site）を照合し、転送を示すヘッダー（Forwarded、X-Forwarded-*）を含む要求を拒否する。状態を変更する要求には、CSRF 対策の専用ヘッダーも要求する。 | [`local.py`](services/api/src/cytellect_api/local.py) [`app.py`](services/api/src/cytellect_api/app.py) [`test_local.py`](tests/test_local.py) |
| 要求の検証（Docker 版） | 状態を変更する要求の Origin と、CSRF 対策の専用ヘッダーを照合する。 | [`app.py`](services/api/src/cytellect_api/app.py) [`desktop.py`](services/api/src/cytellect_api/desktop.py) [`test_desktop_owner.py`](tests/test_desktop_owner.py) |
| 利用者の識別（Docker 版） | 研究室のサーバーでは、1 回限りの招待でセッションを発行する。招待は、ハッシュだけを保存する。 | [`app.py`](services/api/src/cytellect_api/app.py) [`db.py`](services/api/src/cytellect_api/db.py) |
| セッション | セッションは、HttpOnly かつ SameSite=Strict の Cookie で保持し、PC 上のサーバーにはトークンの SHA-256 だけを保存する。ログアウトでセッションを失効させる。Windows 版は、アプリの終了時にすべてのセッションを失効させる。 | [`app.py`](services/api/src/cytellect_api/app.py) [`local.py`](services/api/src/cytellect_api/local.py) [`db.py`](services/api/src/cytellect_api/db.py) [`test_local.py`](tests/test_local.py) |
| 所有者の照合 | 要求のたびに、セッションの所有者とワークスペースの所有者を照合する。一致しない要求には、存在しない場合と同じ応答を返す。識別子だけでは権限を与えない。 | [`app.py`](services/api/src/cytellect_api/app.py) [`upload_guard.py`](services/api/src/cytellect_api/upload_guard.py) [`test_upload_guard.py`](tests/test_upload_guard.py) |

### 8.2 入力、応答、クラウドとの通信

| 対策 | 仕組み | 実装と試験 |
|---|---|---|
| 入力の受け入れ | 受け入れる入力に上限を設ける（1 ワークスペースあたり 100 視野、合計 2 GiB。1 プレーンは 4096×4096 px まで）。保存には内部の識別子を使用し、アップロードされたファイル名をパスに使用しない。パスは、保存領域の内側にあることを検証する。配列は、pickle を無効にして読み込む。 | [`config.py`](services/api/src/cytellect_api/config.py) [`images.py`](packages/analysis/src/cytellect_analysis/images.py) [`region_inputs.py`](services/api/src/cytellect_api/region_inputs.py) [`upload_guard.py`](services/api/src/cytellect_api/upload_guard.py) [`db.py`](services/api/src/cytellect_api/db.py) [`test_upload_guard.py`](tests/test_upload_guard.py) |
| 応答ヘッダー | 応答には、キャッシュ、MIME タイプの推測、リファラーの送信、フレームへの埋め込みを禁止するヘッダーを付ける。画面には、外部リソースの読み込みと外部への接続を禁止する Content Security Policy を適用する。 | [`app.py`](services/api/src/cytellect_api/app.py) [`local.py`](services/api/src/cytellect_api/local.py) [`test_local.py`](tests/test_local.py) |
| ログとエラー | アクセスログは無効にしている。要求の本文、ファイル名、トークンの値をログに記録しない。エラーは、あらかじめ定めたエラーコードだけを返し、内部の例外と解析プログラムの出力は返さない。 | [`local.py`](services/api/src/cytellect_api/local.py) [`app.py`](services/api/src/cytellect_api/app.py) |
| クラウドとの通信 | クラウドとの通信は HTTPS に限る。認証情報、クエリ、フラグメントを含む URL は受け付けない。リダイレクトには従わず、応答のサイズを制限し、あらかじめ定めた項目だけを画面に渡す。 | [`cloud_account.py`](services/api/src/cytellect_api/cloud_account.py) [`proposals.py`](services/api/src/cytellect_api/proposals.py) [`cellpose_engine.py`](packages/analysis/src/cytellect_analysis/cellpose_engine.py) [`test_cloud_account.py`](tests/test_cloud_account.py) |
| 検出の応答の照合 | PC は、応答が示す実行プログラム、モデル、ロックファイルのハッシュが、導入したバージョンの値と一致する場合にのみ、検出の結果を受理する。 | [`cellpose_engine.py`](packages/analysis/src/cytellect_analysis/cellpose_engine.py) [`test_cellpose_remote.py`](tests/test_cellpose_remote.py) |

### 8.3 解析ワーカーの隔離と監視

| 対策 | 仕組み | 実装と試験 |
|---|---|---|
| コンテナの隔離（Docker 版） | 解析ワーカーは、ネットワークを持たない、非 root かつ読み取り専用のコンテナで動作する。Linux のケーパビリティをすべて削除し、権限昇格を禁止し、メモリとプロセス数を制限する。CI は、実際のコンテナで、外部への接続が拒否されることを検証する。 | [`compose.yaml`](compose.yaml) [`ci.yml`](.github/workflows/ci.yml) |
| ジョブの監視 | ジョブには、実行時間とメモリの上限を設ける。監視プロセスがジョブの状態を確認できなくなった場合は、解析のプロセスを停止し、その結果を確定しない。 | [`supervision.py`](services/worker/src/cytellect_worker/supervision.py) [`test_supervision.py`](tests/test_supervision.py) |
| 実行中のダウンロード | 解析の実行中に、コードやモデルをダウンロードしない。 | [`runner.py`](engines/cellpose/runner.py) [`fiji/runtime.lock.json`](engines/fiji/runtime.lock.json) |

## 9. AI による解析支援

AI の出力は、コードとして実行しない。解析の提案は、あらかじめ定めた項目と値だけからなる設定として PC 上で検証し、検証を通ったものだけを下書きとして研究者に示す。研究者が採用するまで、提案は解析に使用しない。採用後も、測定と統計は共通の実装が計算し、提案は数値を生成しない。

PC は、次の提案を拒否する。

- スキーマにない項目を含む提案
- 説明文に、URL またはコードに類する文字列を含む提案
- チャンネルの構成が、送信した内容と一致しない提案
- 記録された染色を変更する提案、記録のない染色を定める提案
- AI の応答を待つ間に、ワークスペースのデータが変更された、またはワークスペースが失効もしくは削除された場合の提案

考察の下書きは、形式を検証したうえで、文章として比較結果に添えて保存する。解析の設定と数値は変更しない。

実装と試験：[`proposal_validation.py`](packages/analysis/src/cytellect_analysis/proposal_validation.py) [`proposal_contracts.py`](packages/analysis/src/cytellect_analysis/proposal_contracts.py) [`discussion_validation.py`](packages/analysis/src/cytellect_analysis/discussion_validation.py) [`proposals.py`](services/api/src/cytellect_api/proposals.py) [`test_proposals.py`](tests/test_proposals.py) [`test_proposals_persistence.py`](tests/test_proposals_persistence.py) [`test_result_discussion.py`](tests/test_result_discussion.py)

## 10. 暗号方式と鍵の管理

| 用途 | 方式 | 鍵の保管 |
|---|---|---|
| 通信の保護 | TLS。サーバー証明書を、OS の信頼ストアで検証する。 | サーバー証明書の秘密鍵は、各サービスが管理する。 |
| 端末トークン | 256 bit の暗号論的に安全な乱数。中継サービスには、SHA-256 のハッシュだけを保存する。 | PC の設定領域 |
| ログインコード | HMAC-SHA256 によるハッシュだけを保存する。 | HMAC 鍵は、中継サービスのシークレットとして、データベースの外に保持する。 |
| 承認リンク | HMAC-SHA256 による署名。照合は定数時間で行う。 | 同上 |
| 管理画面の JWT | RS256 による署名を、Cloudflare Access の公開鍵で検証する。 | 秘密鍵は Cloudflare Access が保持する。 |
| 更新の署名 | Ed25519 による SSH 署名（OpenSSH の SSHSIG 形式、名前空間 `cytellect-update`、ハッシュは SHA-512）。公開鍵は、アプリに組み込む。 | 秘密鍵は、管理者の手元と、`main` からの実行に限定した署名環境にのみ保管する。 |
| 完全性の検証 | SHA-256。対象は、インストーラー、同梱物、検出モデル、依存パッケージ、取り込んだ画像である。 | 期待するハッシュは、リポジトリと署名付きのマニフェストに記録する。 |

実装と試験：[`http.ts`](services/proposal-worker/src/http.ts) [`access.ts`](services/proposal-worker/src/access.ts) [`update_signature.py`](services/api/src/cytellect_api/update_signature.py) [`test_update_signature.py`](tests/test_update_signature.py)

## 11. 配布物とサプライチェーン

### 11.1 更新の署名と検証

| 対策 | 仕組み | 実装と試験 |
|---|---|---|
| Microsoft Store 版（Windows 11） | Microsoft が署名し、導入と更新は Microsoft Store が行う。Microsoft Store への提出は、管理者が承認した `main` の最新のコミットに限る。 | [`windows-store-release.yml`](.github/workflows/windows-store-release.yml) |
| 更新の署名（EXE 版） | 各リリースには、バージョン、インストーラーの名前、SHA-256、サイズ、ソースのコミット、発行時刻を記載したマニフェストと、Ed25519 鍵による署名を付ける。 | [`local-release.yml`](.github/workflows/local-release.yml) [`update_signature.py`](services/api/src/cytellect_api/update_signature.py) [`test_update_signature.py`](tests/test_update_signature.py) |
| 更新の検証（EXE 版） | アプリは、組み込んだ公開鍵でマニフェストの署名を検証してから、インストーラーを取得する。現在より新しいバージョンであり、インストーラーの SHA-256 とサイズがマニフェストと一致する場合にのみ実行する。取得元は HTTPS の GitHub のホストに限り、リダイレクト先も照合する。配布元が示すハッシュは、信頼の根拠にしない。 | [`update_signature.py`](services/api/src/cytellect_api/update_signature.py) [`app_update.py`](services/api/src/cytellect_api/app_update.py) [`test_update_signature.py`](tests/test_update_signature.py) [`test_app_update.py`](tests/test_app_update.py) |
| 更新の切り戻し（EXE 版） | 更新の適用前に、データベースの写しを取得する。新しいバージョンが起動しない場合は、以前のバージョンとその写しに戻す。 | [`app_update.py`](services/api/src/cytellect_api/app_update.py) [`test_app_update.py`](tests/test_app_update.py) |
| 初回導入（EXE 版） | 最初に導入するインストーラーも、同じ署名付きのマニフェストで検証できる（[手順](docs/install-windows.ja.md#2-ダウンロードと確認)）。 | [`update_signature.py`](services/api/src/cytellect_api/update_signature.py) |

### 11.2 リリースの検証

| 対策 | 仕組み | 実装と試験 |
|---|---|---|
| 署名鍵の保管 | 署名鍵は、管理者の手元と、`main` からの実行に限定した GitHub Actions の署名環境にのみ保管する。鍵の作成、登録、交換、失効の手順を定めている。 | [`release-signing.md`](docs/release-signing.md) [`local-release.yml`](.github/workflows/local-release.yml) |
| 配布の条件 | 手動の配布は、管理者の承認を要する。自動の配布は、保護された `main` 上で CI と配布試験に合格したバージョンだけを公開する。 | [`local-release.yml`](.github/workflows/local-release.yml) [`windows_exe_release.cjs`](scripts/windows_exe_release.cjs) [`windows_exe_release.test.cjs`](scripts/windows_exe_release.test.cjs) |
| コミットの照合 | リリースは単一のコミットから作成し、各段階でそのコミットを照合する。`main` の履歴にないコミット、フォークに由来する実行、タグの再利用は拒否する。 | [`local-release.yml`](.github/workflows/local-release.yml) [`windows_exe_release.cjs`](scripts/windows_exe_release.cjs) [`windows_exe_release.test.cjs`](scripts/windows_exe_release.test.cjs) |
| 公開するファイルの照合 | サイズまたはハッシュが試験済みのファイルと一致しないファイルは、公開しない。 | [`windows_exe_release.cjs`](scripts/windows_exe_release.cjs) [`windows_exe_release.test.cjs`](scripts/windows_exe_release.test.cjs) |

### 11.3 依存パッケージと同梱物

| 対策 | 仕組み | 実装と試験 |
|---|---|---|
| 依存パッケージの固定 | Python と JavaScript の依存パッケージは、ロックファイルでバージョンとハッシュを固定する。 | [`uv.lock`](uv.lock) [`pnpm-lock.yaml`](pnpm-lock.yaml) |
| 同梱物の照合 | 同梱する Fiji、検出モデル、Python の実行環境は、ビルド時に SHA-256 を照合する。 | [`fiji/runtime.lock.json`](engines/fiji/runtime.lock.json) [`cellpose/runtime.lock.json`](engines/cellpose/runtime.lock.json) [`build_windows_installer.py`](scripts/build_windows_installer.py) [`test_windows_installer.py`](tests/test_windows_installer.py) |
| 配布物の検査 | 配布物は、ビルド時に認証情報の混入を走査し、検出した場合はビルドを失敗させる。 | [`build_windows_installer.py`](scripts/build_windows_installer.py) [`test_windows_installer.py`](tests/test_windows_installer.py) |
| 部品表 | CI は、依存パッケージのソフトウェア部品表（SBOM）を生成する。 | [`sbom.py`](scripts/sbom.py) [`ci.yml`](.github/workflows/ci.yml) [`test_sbom.py`](tests/test_sbom.py) |

### 11.4 リポジトリと CI

| 対策 | 仕組み | 実装と試験 |
|---|---|---|
| `main` への反映 | `main` への反映は、ルールセットで管理者に限定する。変更はプルリクエストで行い、必須の CI に合格したものを反映する。 | [`ci.yml`](.github/workflows/ci.yml) |
| 秘密情報の検出 | ハッシュを照合した gitleaks で、`main` と各プルリクエストの Git の全履歴を走査する。 | [`scan_secrets.py`](scripts/scan_secrets.py) [`security-tools.lock.json`](scripts/security-tools.lock.json) [`ci.yml`](.github/workflows/ci.yml) [`test_scan_secrets.py`](tests/test_scan_secrets.py) |
| 静的解析と脆弱性の監査 | CodeQL（ワークフロー、JavaScript/TypeScript、Python）を、プルリクエスト、`main`、週次で実行する。依存パッケージの脆弱性の監査（pip-audit、pnpm audit）を CI で実行する。 | [`codeql.yml`](.github/workflows/codeql.yml) [`ci.yml`](.github/workflows/ci.yml) |
| ワークフローの権限 | ワークフローのトークンは、既定で読み取り専用とする。フォークに由来する実行には、書き込み権限とシークレットを与えない。 | [`ci.yml`](.github/workflows/ci.yml) [`local-release.yml`](.github/workflows/local-release.yml) |
| 研究データの分離 | リポジトリと CI は、非公開の研究データを含まない。評価と公開デモには、出典、再配布条件、ハッシュを記録した公開画像を使用する。複数人が利用する開発環境は、登録済みの公開ファイル以外のアップロードを、SHA-256 の照合で拒否する。 | [`public_uploads.py`](services/api/src/cytellect_api/public_uploads.py) [`test_public_uploads.py`](tests/test_public_uploads.py) |

## 12. 認証情報と鍵の失効

| 認証情報・鍵 | 失効の手段 | 効果が及ぶ時点 |
|---|---|---|
| 端末トークン | ログアウト、アカウントの失効、90 日間の不使用 | 次の要求 |
| PC 上のセッション | ログアウト、アプリの終了（Windows 版） | ただちに |
| ログインコードと承認リンクの HMAC 鍵 | 鍵の交換 | 未使用のログインコードと承認リンクは、交換と同時に無効になる。 |
| 外部サービスの API キー | 外部サービスでの無効化と、中継サービスのシークレットの更新 | 更新と同時 |
| 更新の署名鍵 | 署名環境からの削除と、新しい鍵を組み込んだバージョンの配布（[更新の署名](docs/release-signing.md)） | 署名環境からの削除と同時に、その鍵による新しい署名は作成できなくなる。 |

実装と試験：[`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`local.py`](services/api/src/cytellect_api/local.py) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) [`release-signing.md`](docs/release-signing.md)

## 13. 脆弱性への対応

### 13.1 修正を提供するバージョン

| 対象 | セキュリティ修正 |
|---|---|
| Microsoft Store 版 | 提供する（Microsoft Store が最新のバージョンに更新する） |
| EXE 版の最新のリリース | 提供する |
| `main`（`cytellect.app`、クラウドの機能、Docker 版） | 提供する |
| 上記より前の EXE 版 | 提供しない（アプリ内の更新で最新のバージョンに移行する） |

### 13.2 対象範囲

このリポジトリのコード、Windows 版（Microsoft Store 版と EXE 版）、Docker 版、`cytellect.app`、中継サービス、推論サーバーを対象とする。Cytellect による外部サービスの設定と利用方法に起因する問題も対象に含む。同梱する第三者のコンポーネント（Fiji、Cellpose など）と、利用する外部サービス自体の脆弱性は、各開発元の窓口が扱う。

### 13.3 脆弱性の報告

脆弱性は、GitHub の非公開の報告機能で報告する。リポジトリの **Security** タブで **Report a vulnerability** を選択すると、報告者とリポジトリの管理者だけが閲覧できる形で送信できる（[報告フォーム](https://github.com/genellect/cytellect/security/advisories/new)）。Issue、プルリクエスト、ディスカッションなどの公開の場には記載しない。

報告には、次の内容を含める。

- 対象のコミット、または Windows 版のバージョン
- 再現手順
- 想定される影響

再現には、合成データまたは公開データを使用する。

### 13.4 報告後の対応

1. 合理的な報告には、3 日以内に返信する。
2. 影響範囲と深刻度を評価し、報告者と共有する。
3. 非公開のセキュリティアドバイザリで修正し、修正したバージョンを配布する。公開サイトとクラウドの機能は本番環境に反映し、Windows 版は Microsoft Store と署名付きの更新で配布する。
4. 配布後にセキュリティアドバイザリを公開し、必要に応じて CVE を取得する。報告者が希望する場合は、謝辞に氏名を記載する。

公開済みのセキュリティアドバイザリは、[一覧](https://github.com/genellect/cytellect/security/advisories)にある。

## 14. 関連文書

| 文書 | 内容 |
|---|---|
| [更新の署名](docs/release-signing.md) | 署名鍵の作成、登録、交換、失効 |
| [チーム開発ルール §6](docs/team-development.md#6-研究データの扱い) | 開発における研究データと認証情報の取り扱い |
| [プライバシーポリシー](https://cytellect.app/privacy) | Microsoft Store 版とクラウドの機能で取り扱う情報 |

## English

Cytellect analyses unpublished microscopy images on the researcher's own PC. Images, masks, measurements and figures are stored on the PC and not in the Cytellect cloud. The PC transmits only the information an operation requires, and only when the researcher invokes cloud GPU detection or an AI feature.

The relay service and the inference server store no research data and do not hold the update-signing key. The application runs only updates whose signature it has verified with its built-in public key. As a result, an attacker who obtains a researcher's account, the relay service or write access to the repository cannot reach research data on the PC or installed applications.

The implementation and tests of these measures are public in this repository. Vulnerability reports are accepted through the [private report form](https://github.com/genellect/cytellect/security/advisories/new) ([13. Vulnerability handling](#13-vulnerability-handling)).

[Japanese version (日本語)](#セキュリティポリシー)

- [1. Design principles](#1-design-principles)
- [2. Architecture and data flow](#2-architecture-and-data-flow)
- [3. Threats and mitigations](#3-threats-and-mitigations)
- [4. Protection of research data](#4-protection-of-research-data)
- [5. Authentication and credentials](#5-authentication-and-credentials)
- [6. Relay service](#6-relay-service)
- [7. Inference server](#7-inference-server)
- [8. Application on the PC](#8-application-on-the-pc)
- [9. AI assistance](#9-ai-assistance)
- [10. Cryptography and key management](#10-cryptography-and-key-management)
- [11. Releases and supply chain](#11-releases-and-supply-chain)
- [12. Revocation of credentials and keys](#12-revocation-of-credentials-and-keys)
- [13. Vulnerability handling](#13-vulnerability-handling)
- [14. Related documents](#14-related-documents)

### 1. Design principles

| Principle | Description | Details |
|---|---|---|
| Research data stays on the PC | Images, masks, measurements and figures are stored on the researcher's PC or the lab server. Detection, measurement, statistics and figure rendering run in the same place. | [4. Protection of research data](#4-protection-of-research-data) |
| Only what an invoked operation needs is transmitted | Research data leaves the PC only when the researcher invokes cloud GPU detection or an AI feature. Without these features, research data does not leave the PC. | [2.2 Information transmitted from the PC](#22-information-transmitted-from-the-pc) |
| The cloud stores no research data | The relay service and the inference server handle research data only while processing a request, and neither store nor log it. | [6. Relay service](#6-relay-service), [7. Inference server](#7-inference-server) |
| One compromise does not reach the whole | Data, keys and permissions are separated by component. Obtaining a researcher's account, the relay service or write access to the repository does not give access to stored research data or installed applications. | [3. Threats and mitigations](#3-threats-and-mitigations) |
| The receiver verifies input crossing a boundary | Each component independently verifies input that reaches it across a boundary. | [2.4 Trust boundaries](#24-trust-boundaries) |
| AI output does not change an analysis without the researcher's adoption | AI output is not executed as code. An analysis proposal is treated as a draft of settings validated on the PC. | [9. AI assistance](#9-ai-assistance) |
| Updates and dependencies are verified by signature and hash | The PC runs only updates whose signature it has verified. Dependencies and bundled components are pinned by hash. | [11. Releases and supply chain](#11-releases-and-supply-chain) |
| Analysis does not depend on the cloud | Measurement, statistics and figure rendering complete on the PC and can continue when the cloud features are unavailable. | [2.1 Components](#21-components) |

### 2. Architecture and data flow

#### 2.1 Components

Cytellect is provided as the Windows release (Microsoft Store and EXE) and as the Docker release, which runs on a PC or a lab server. Only the PC or server running the application holds research data. It is called the PC below.

| Component | Role | Data held | Keys and credentials held |
|---|---|---|---|
| PC (local web interface, the server on the PC, analysis worker) | Runs detection, measurement, statistics and figure rendering. | All research data | One device token (when signed in to the cloud) |
| Relay service (Cytellect Worker, running on Cloudflare Workers) | Handles sign-in, user approval and quotas, and relays requests to the cloud GPU and the AI. | Account information and usage records | API keys of external services; the HMAC key (used with a separate domain for sign-in codes, approval links and rate-limit identifiers) |
| Inference server (running on Modal) | Runs GPU inference for cell detection (Cellpose). | None | None |
| Distribution (Microsoft Store, GitHub) | Distributes and updates the application. | None | None (the update-signing key is kept in signing environments restricted to runs from `main`) |
| Public site (`cytellect.app`) | Serves the landing page, demo and guides. | None (accepts no research images) | None |

#### 2.2 Information transmitted from the PC

Research data leaves the PC only when the researcher performs one of the following three operations.

| Operation | Data transmitted | Destination | Handling at the destination |
|---|---|---|---|
| Cell detection on the cloud GPU | One image plane to detect (one field, one channel, at original size) and the detection parameters. For nucleolar detection, the adopted nuclear labels (an image marking the nuclear regions) are added. | The inference server, via the relay service | The relay service does not store it. The inference server processes it in memory only and does not store it. |
| Consultation with the AI | The research goal, channel and field records, image dimensions, the current analysis settings and downscaled preview images of one representative field (itemised below) | Anthropic or OpenAI, via the relay service | The relay service does not store it. The AI providers do not use it for model training. |
| Discussion draft generation by the AI | The saved comparison and the experiment purpose (itemised below) | As above | As above |

A consultation with the AI transmits the following.

- The research goal
- Channel names and recorded stains
- Field names (by default the file name) and records (condition, experimental run, pair, acquisition date)
- Image dimensions and pixel size, and field and group counts
- The current analysis settings and the previous proposal
- Per-channel downscaled preview images of one representative field (at most 512 px per side; can be disabled in settings)

Discussion draft generation transmits the following.

- The experiment purpose (it defaults to the research goal written to the AI in that workspace)
- The summary on screen (heading and points)
- The metric's name and definition, the stain name, and the region, group, experimental run and channel names
- Group values, differences and confidence intervals, per-run values, and n and its breakdown
- Aggregation and test methods, the researcher's experimental-unit definition and pairing basis, and the test and its p-value

Requests to OpenAI set `store: false` so that responses are not stored. The AI providers retain data for abuse monitoring for the period their API terms define.

The following three communications carry no research data. The installed application and the analysis screen transmit no usage telemetry.

| Communication | Data transmitted | Destination |
|---|---|---|
| Cloud sign-in | The e-mail address and the sign-in code | The relay service (the sign-in code is e-mailed through Resend) |
| Use of the cloud features | The device token | The relay service |
| Update check (EXE release) | None. GitHub's public release list is fetched. The check interval is six hours, and a failed fetch is retried after 15 minutes. | GitHub |

#### 2.3 External services

| Service | Purpose | Information received |
|---|---|---|
| Cloudflare | Running the relay service, recording account information and usage, authenticating the admin page | Requests in transit (not stored), account information and usage records |
| Modal | GPU inference for cell detection | The image plane to detect, nuclear labels and detection parameters (only while processed) |
| Anthropic, OpenAI | Generating analysis proposals and discussion drafts | The data transmitted to the AI as listed in [2.2 Information transmitted from the PC](#22-information-transmitted-from-the-pc) |
| Resend | Delivering sign-in codes by e-mail | The e-mail address and the sign-in code |
| GitHub | Source code hosting, CI and distribution of the EXE release | None |
| Microsoft Store | Distribution and updates of the Windows release | None |
| Vercel | Serving the public site | None |
| Google Analytics | Web analytics on the public pages (landing page, demo and guides) | Information about visits to the public pages. Advertising use is disabled, and no measurement takes place when the browser signals a tracking opt-out (Do Not Track, Global Privacy Control). Not used in the analysis screen or the installed application. |

#### 2.4 Trust boundaries

| Boundary | What crosses it | Verification by the receiver |
|---|---|---|
| Browser → the server on the PC | Requests from the local web interface | Peer address, Host, Origin, Fetch Metadata, the anti-CSRF header, session and ownership |
| PC → relay service | Detection and AI requests | Device token, account state, quota, body size and schema, request identifier |
| Relay service → inference server | Detection requests | Modal proxy authentication; format, size and fields of the input |
| Relay service → PC | Detection results, analysis proposals and discussion drafts | Comparison of the version hashes, proposal validation and the researcher's adoption |
| Distribution host → PC | Updates | Signature, version, SHA-256 and size |

### 3. Threats and mitigations

| Threat (attacker capability) | Mitigations | Extent of impact | Details |
|---|---|---|---|
| An attacker who has obtained a researcher's e-mail or device token | No research data is stored in the cloud. Quotas have per-account monthly limits. Revoking the account takes effect on every device from its next request. | The impact is limited to that account's quota for the month. Research data cannot be reached. | [5.2 Storage of credentials](#52-storage-of-credentials), [12. Revocation of credentials and keys](#12-revocation-of-credentials-and-keys) |
| An attacker who has compromised the relay service | The relay service stores no bodies. Research data and the update-signing key are outside the relay service. The PC validates proposals against a schema and requires the researcher's adoption. | The impact is limited to requests relayed during the compromise and to the API keys and account information the relay service holds. A proposal is not used in an analysis without validation on the PC and the researcher's adoption. Stored research data, installed applications and the update-signing key cannot be reached. | [6. Relay service](#6-relay-service), [9. AI assistance](#9-ai-assistance) |
| An attacker who has obtained write access to the repository | Merging to `main` is restricted to the maintainer by a ruleset. The update-signing key is kept in signing environments restricted to runs from `main`. The PC runs only updates signed with this key. | The impact is limited to branches and pull requests. `main` and installed PCs cannot be reached. | [11.2 Release verification](#112-release-verification), [11.4 Repository and CI](#114-repository-and-ci) |
| An attacker who replaces an update in the distribution path or rolls it back to an older version | The application verifies the manifest's signature with its built-in public key and checks the installer's SHA-256 and size. Only a version newer than the installed one is accepted. | An installer whose signature and hash do not match, and an update at or below the installed version, are not run. | [11.1 Update signing and verification](#111-update-signing-and-verification) |
| An attacker who replaces dependencies, bundled components or detection models where they are fetched | Dependencies are pinned by version and hash in lockfiles. Bundled components and detection models are checked against SHA-256. | A component whose hash does not match is not incorporated. | [11.3 Dependencies and bundled components](#113-dependencies-and-bundled-components) |
| An attacker who sends requests to the server on the PC from a malicious site (CSRF, DNS rebinding) | The server on the PC listens only on `127.0.0.1` and checks the Host, Origin and Fetch Metadata of requests. The session cookie is not sent with requests from other sites. | Requests from other sites are rejected. | [8.1 Access to the server on the PC](#81-access-to-the-server-on-the-pc) |
| An attacker who eavesdrops or tampers on the network path | External communication from the PC and the relay service uses HTTPS only, with server certificates verified. Updates are verified by signature independently of the network path. | The traffic cannot be read. A tampered update is not run. | [10. Cryptography and key management](#10-cryptography-and-key-management) |
| An attacker who brute-forces sign-in codes | Incorrect entries are limited per sign-in code and per e-mail address. Issuance and verification of sign-in codes are rate-limited. | Attempts are limited to 20 per e-mail address per day. The probability of success against a six-digit sign-in code is at most 2×10⁻⁵ per day. | [5.1 Researcher sign-in](#51-researcher-sign-in) |
| An attacker who has obtained the relay service's database | Device tokens are stored only as SHA-256 hashes. Sign-in codes are stored only as HMAC-SHA256 with a key kept outside the database. IP addresses and research data are not stored. | The impact is limited to e-mail addresses, approval states and usage records. No usable credential or research data is included. | [5.2 Storage of credentials](#52-storage-of-credentials), [4.3 Information stored in the cloud](#43-information-stored-in-the-cloud) |
| A legitimate researcher or an obtained token attempting to exhaust GPU and AI cost | There are per-account monthly limits and an overall monthly budget. Cost is reserved before the model is called. GPU requests are limited to one in flight per account. | Cost does not exceed the configured monthly budget. | [6. Relay service](#6-relay-service) |
| An attacker targeting the admin page and the approval path (reaching it through another entry point, forging an approval link, or approval by automatic link fetching) | Admin routes respond only on the designated origin. The relay service independently verifies the Cloudflare Access token. An approval link is single-use and signed with HMAC, and approval requires a confirming action on the page. | A forged link, or a link that is merely opened, does not result in approval. | [5.3 Admin page](#53-admin-page) |
| An attacker who sends requests directly to the inference server | Modal proxy authentication is required. A request cannot specify a URL, a file path or an arbitrary model. | Unauthenticated requests are not accepted. | [7. Inference server](#7-inference-server) |
| Incorrect AI output, and AI output steered by instructions planted in its input (prompt injection) | AI output is not executed as code. A proposal is validated against a schema and is not used until the researcher adopts it. Only the shared implementation computes measurements and statistics. | Analysis settings and values do not change without the researcher's adoption. | [9. AI assistance](#9-ai-assistance) |
| A crafted input file | The format, dimensions and size of input are validated. Arrays are loaded with pickle disabled. Analysis processes run under time and memory limits. | Input that does not meet the format and limits is rejected before analysis. In the Docker release, analysis is confined to a non-root, read-only container with no network. | [8.2 Input, responses and communication with the cloud](#82-input-responses-and-communication-with-the-cloud), [8.3 Isolation and supervision of the analysis worker](#83-isolation-and-supervision-of-the-analysis-worker) |
| Another user of a shared lab server guessing workspace identifiers | Every request compares the session's owner with the workspace's owner. A request that does not match receives the same response as for a workspace that does not exist. | Neither the content nor the existence of another user's workspace is obtained. | [8.1 Access to the server on the PC](#81-access-to-the-server-on-the-pc) |
| An attacker abusing CI through a pull request from a fork | The workflow token is read-only by default. Runs originating from forks receive neither write permission nor secrets. Releases refuse runs originating from forks. | Secrets and the signing environments cannot be reached. | [11.4 Repository and CI](#114-repository-and-ci) |

### 4. Protection of research data

#### 4.1 Scope of and consent to external transmission

| Measure | Mechanism | Implementation and tests |
|---|---|---|
| Scope of transmission | Data transmitted externally is limited to what [2.2 Information transmitted from the PC](#22-information-transmitted-from-the-pc) lists. Per-nucleus measurements and file paths are not transmitted by any operation. Detection does not transmit file names, workspace titles, conditions or other channels. Fields the researcher has excluded are used neither for proposals nor for preview images. | [`proposals.py`](services/api/src/cytellect_api/proposals.py) [`discussions.py`](services/api/src/cytellect_api/discussions.py) [`cellpose_engine.py`](packages/analysis/src/cytellect_analysis/cellpose_engine.py) [`test_proposals.py`](tests/test_proposals.py) [`test_cellpose_remote.py`](tests/test_cellpose_remote.py) |
| Consent | The scope transmitted to the AI is displayed, and consent obtained, at cloud sign-in and at the first discussion draft. The AI settings panel also displays the scope at all times. | [`CloudAccount.tsx`](apps/web/src/components/workspace/CloudAccount.tsx) [`ConnectedWorkspace.tsx`](apps/web/src/components/workspace/review/ConnectedWorkspace.tsx) [`AiSettings.tsx`](apps/web/src/components/workspace/AiSettings.tsx) |
| Transmission confirmation | The server on the PC sends to the AI only requests the researcher has confirmed on screen, and rejects requests without that confirmation. | [`proposals.py`](services/api/src/cytellect_api/proposals.py) [`discussions.py`](services/api/src/cytellect_api/discussions.py) [`test_proposals.py`](tests/test_proposals.py) [`test_result_discussion_api.py`](tests/test_result_discussion_api.py) |

#### 4.2 Storage and deletion

| Measure | Mechanism | Implementation and tests |
|---|---|---|
| Storage location | Data and credentials on the PC are stored in an area of the OS user's profile that only that user can read (`%LOCALAPPDATA%\Cytellect` in the Windows release). Encryption at rest relies on the OS's disk encryption (BitLocker and similar). | [`local.py`](services/api/src/cytellect_api/local.py) [`cloud_account.py`](services/api/src/cytellect_api/cloud_account.py) [`local_setup.ps1`](scripts/local_setup.ps1) |
| Integrity of original images | Original pixel values are not modified. An imported image is checked against its SHA-256 before it is used in an analysis, and results are written to a separate area. | [`worker/regions.py`](services/worker/src/cytellect_worker/regions.py) |
| Deletion | Reads are blocked immediately on expiry or deletion. Inputs, arrays, masks, figures and exported files are then removed. | [`app.py`](services/api/src/cytellect_api/app.py) [`worker/main.py`](services/worker/src/cytellect_worker/main.py) [`test_workspace_retention.py`](tests/test_workspace_retention.py) |

Work data is retained as follows in each release.

| Release | Retention of work data |
|---|---|
| Microsoft Store release | Retained until the researcher deletes it. |
| EXE release | Retained until the researcher deletes it. Automatic deletion after 24 hours can be selected at installation. |
| Docker release | Expired and deleted 24 hours after the last action. In a configuration that listens only on `127.0.0.1`, retention until deletion can be selected. |

Implementation and tests: [`config.py`](services/api/src/cytellect_api/config.py) [`test_workspace_retention.py`](tests/test_workspace_retention.py)

#### 4.3 Information stored in the cloud

The Cytellect cloud stores only the following four classes of information. Research data is not among them.

| Class | Content | Use |
|---|---|---|
| Account information | E-mail address, approval state, times of request, approval and revocation, and per-account quotas | Approval, revocation and quota management |
| Authentication records | Hashes of device tokens, sign-in codes, approval links and invitations, with their expiry times | Authentication |
| Rate-limit and replay-prevention records | Identifiers computed with HMAC and their counts, and request identifiers (UUID) | Preventing brute force and replay |
| Usage records | Monthly GPU seconds, the start time of a GPU request in flight, and per analysis proposal the cost, AI input and output token counts, model name and prompt version | Quota and cost management |

Implementation and tests: [`migrations/`](services/proposal-worker/migrations) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`store.ts`](services/proposal-worker/src/store.ts) [`store.test.ts`](services/proposal-worker/src/store.test.ts)

### 5. Authentication and credentials

#### 5.1 Researcher sign-in

| Measure | Mechanism | Implementation and tests |
|---|---|---|
| Sign-in code | A researcher authenticates with a six-digit sign-in code received by e-mail. Sign-in codes are generated without bias from a cryptographically secure random source and sent only to e-mail addresses the maintainer has allowed. A code is valid for 10 minutes and can be used once. | [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`mail.ts`](services/proposal-worker/src/mail.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |
| Limits on incorrect entries | Five incorrect entries invalidate a sign-in code, and 20 incorrect entries for one e-mail address within a day lock it for 24 hours. Incorrect entries are counted per e-mail address, so changing the source IP address yields no additional attempts. | [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |
| Rate limits | Issuance of sign-in codes is limited to 20 per hour per IP address (per /64 for IPv6), and to 6 per hour and 10 per day per e-mail address. Verification is limited to 30 per hour per IP address. | [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |

#### 5.2 Storage of credentials

| Measure | Mechanism | Implementation and tests |
|---|---|---|
| Device token | The only credential the PC holds from a cloud sign-in is a single device token of 256 random bits. The device token expires after 90 days without use and is deleted from both the PC and the relay service on sign-out. | [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`http.ts`](services/proposal-worker/src/http.ts) [`cloud_account.py`](services/api/src/cytellect_api/cloud_account.py) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) [`test_cloud_account.py`](tests/test_cloud_account.py) |
| Storage and transmission on the PC | The device token is stored in a settings area separate from research data. The server on the PC includes it in neither responses nor logs. The device token is sent only to the URL that issued it, and redirects are not followed. | [`cloud_account.py`](services/api/src/cytellect_api/cloud_account.py) [`test_cloud_account.py`](tests/test_cloud_account.py) |
| Storage in the relay service | Device tokens are stored only as SHA-256 hashes, and sign-in codes only as HMAC-SHA256 hashes (with the purpose and the e-mail address in the input). IP addresses are not stored, and rate-limit identifiers are also stored as values computed with HMAC. Tokens and sign-in codes are compared in constant time. | [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`http.ts`](services/proposal-worker/src/http.ts) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |
| API keys of external services | The Anthropic, OpenAI, Modal and Resend API keys are held only as secrets of the relay service. They are not included on the PC, in a release or in a response from the relay service. Releases are scanned for credentials at build time. | [`wrangler.toml.example`](services/proposal-worker/wrangler.toml.example) [`deployment.test.mjs`](services/proposal-worker/scripts/deployment.test.mjs) [`build_windows_installer.py`](scripts/build_windows_installer.py) |
| Account revocation | From the moment the maintainer revokes an account, requests from every device signed in with it are rejected. | [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |

#### 5.3 Admin page

| Measure | Mechanism | Implementation and tests |
|---|---|---|
| Multi-factor authentication | Every external service account used for operations requires multi-factor authentication with a passkey or an authenticator app. | Operational setting |
| Admin page authentication | The admin page is placed behind Cloudflare Access (Google sign-in). The relay service also independently verifies the JWT issued by Cloudflare Access: its signature (algorithm fixed to RS256), issuer, audience, expiry and the maintainer's e-mail address. | [`access.ts`](services/proposal-worker/src/access.ts) [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`access.test.ts`](services/proposal-worker/src/access.test.ts) [`wrangler.toml.example`](services/proposal-worker/wrangler.toml.example) [`proposal-deployment.md`](docs/proposal-deployment.md) |
| Restriction of admin routes | Admin routes respond only on the designated origin. Other entry points such as `workers.dev` do not respond even to a valid token. | [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) [`wrangler.toml.example`](services/proposal-worker/wrangler.toml.example) |
| User approval | A new researcher is approved through a single-use link signed with HMAC (valid for 7 days). Opening the link alone approves nothing; approval requires a confirming action on the page. | [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |
| Page protection | The admin page forbids loading external resources, embedding in frames and caching. Admin operations are restricted to same-origin requests. | [`admin-page.ts`](services/proposal-worker/src/admin-page.ts) [`cloud.ts`](services/proposal-worker/src/cloud.ts) |

### 6. Relay service

| Measure | Mechanism | Implementation and tests |
|---|---|---|
| Storage and logging | Request and response bodies, sign-in codes and device tokens are neither stored nor logged. Cloudflare Workers log collection is disabled. | [`index.ts`](services/proposal-worker/src/index.ts) [`wrangler.toml.example`](services/proposal-worker/wrangler.toml.example) [`deployment.test.mjs`](services/proposal-worker/scripts/deployment.test.mjs) |
| Detection relay | Detection requests and responses are forwarded as streams, without interpreting or retaining the body. Body size is judged from Content-Length. Only headers describing the content type and length are forwarded to the inference server, and the researcher's device token is not passed on. | [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |
| Request validation | Body size is limited per route (authentication 4 KiB, analysis proposals and discussions 6 MiB, detection 256 MiB). Proposal requests are validated against a schema, and preview images are confirmed to be PNG and at most 512 px without decoding pixels. Models and prompt versions are restricted to an allowlist. | [`index.ts`](services/proposal-worker/src/index.ts) [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`schema.ts`](services/proposal-worker/src/schema.ts) [`discussion.ts`](services/proposal-worker/src/discussion.ts) [`index.test.ts`](services/proposal-worker/src/index.test.ts) |
| Replay prevention | A proposal request is accepted once per device for each unique identifier (UUID). Sign-in codes and approval links are consumed exactly once by an atomic update. | [`index.ts`](services/proposal-worker/src/index.ts) [`store.ts`](services/proposal-worker/src/store.ts) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`index.test.ts`](services/proposal-worker/src/index.test.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |
| Outbound requests | Outbound requests do not follow redirects. There is no path by which an API key is sent to another host. For errors from external services, only predefined error codes and the HTTP status are returned. | [`openai.ts`](services/proposal-worker/src/openai.ts) [`anthropic.ts`](services/proposal-worker/src/anthropic.ts) [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`mail.ts`](services/proposal-worker/src/mail.ts) [`index.ts`](services/proposal-worker/src/index.ts) |
| Requests from other origins | The relay service returns no CORS headers permitting other origins. Because the device token is sent in the Authorization header, requests from pages on other sites are blocked by the browser's preflight. | [`http.ts`](services/proposal-worker/src/http.ts) [`cloud.ts`](services/proposal-worker/src/cloud.ts) |
| Quotas | GPU seconds and AI cost are subject to per-account monthly limits and an overall monthly budget. Requests exceeding a limit are rejected without being forwarded to the external service. GPU requests are limited to one in flight per account. | [`store.ts`](services/proposal-worker/src/store.ts) [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`store.test.ts`](services/proposal-worker/src/store.test.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |
| Cost reservation and integrity | The maximum cost of a request is reserved atomically before the model is called. If the cost records become inconsistent, requests to the AI are suspended until the inconsistency is resolved. | [`store.ts`](services/proposal-worker/src/store.ts) [`index.ts`](services/proposal-worker/src/index.ts) [`store.test.ts`](services/proposal-worker/src/store.test.ts) |
| Missing configuration | A feature whose required setting or key is missing accepts no requests. | [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`index.ts`](services/proposal-worker/src/index.ts) [`deployment.test.mjs`](services/proposal-worker/scripts/deployment.test.mjs) |

### 7. Inference server

| Measure | Mechanism | Implementation and tests |
|---|---|---|
| Runtime | A single container processes one request at a time. No persistent volume or memory snapshot is used. The container runs as a non-root user, and its image is pinned by digest. | [`modal_cellpose.py`](infra/modal_cellpose.py) |
| Authentication | Modal proxy authentication is required, and unauthenticated requests are not accepted. | [`modal_cellpose.py`](infra/modal_cellpose.py) [`cloud.ts`](services/proposal-worker/src/cloud.ts) |
| Request handling | Request content is held in memory only while it is processed and is not written to a file. Request content, paths and client IP addresses are not logged. | [`server.py`](engines/cellpose/server.py) |
| Input validation | The format, size and fields of the input are validated, and arrays are loaded with pickle disabled. A request cannot specify a URL, a file path or an arbitrary model. | [`server.py`](engines/cellpose/server.py) |
| Models | Public weights are used pinned to a revision and are checked against SHA-256 before loading. Fetching from the network is disabled while running. | [`runner.py`](engines/cellpose/runner.py) [`cellpose/runtime.lock.json`](engines/cellpose/runtime.lock.json) |

### 8. Application on the PC

#### 8.1 Access to the server on the PC

| Measure | Mechanism | Implementation and tests |
|---|---|---|
| Listening address | The server on the PC listens only on `127.0.0.1`. The Docker release publishes its ports only on `127.0.0.1`. | [`local.py`](services/api/src/cytellect_api/local.py) [`compose.yaml`](compose.yaml) [`test_local.py`](tests/test_local.py) |
| Request validation (Windows release) | Every request is checked for its peer address, Host, Origin and Fetch Metadata (Sec-Fetch-Site), and requests carrying forwarding headers (Forwarded, X-Forwarded-*) are rejected. State-changing requests must also carry a dedicated anti-CSRF header. | [`local.py`](services/api/src/cytellect_api/local.py) [`app.py`](services/api/src/cytellect_api/app.py) [`test_local.py`](tests/test_local.py) |
| Request validation (Docker release) | State-changing requests are checked for their Origin and the dedicated anti-CSRF header. | [`app.py`](services/api/src/cytellect_api/app.py) [`desktop.py`](services/api/src/cytellect_api/desktop.py) [`test_desktop_owner.py`](tests/test_desktop_owner.py) |
| User identification (Docker release) | On a lab server, a session is issued through a single-use invitation. Invitations are stored only as hashes. | [`app.py`](services/api/src/cytellect_api/app.py) [`db.py`](services/api/src/cytellect_api/db.py) |
| Sessions | Sessions are held in HttpOnly, SameSite=Strict cookies, and the server on the PC stores only the SHA-256 of the token. Logging out revokes the session. The Windows release revokes all sessions when the application exits. | [`app.py`](services/api/src/cytellect_api/app.py) [`local.py`](services/api/src/cytellect_api/local.py) [`db.py`](services/api/src/cytellect_api/db.py) [`test_local.py`](tests/test_local.py) |
| Ownership checks | Every request compares the session's owner with the workspace's owner. A request that does not match receives the same response as for a workspace that does not exist. An identifier alone confers no permission. | [`app.py`](services/api/src/cytellect_api/app.py) [`upload_guard.py`](services/api/src/cytellect_api/upload_guard.py) [`test_upload_guard.py`](tests/test_upload_guard.py) |

#### 8.2 Input, responses and communication with the cloud

| Measure | Mechanism | Implementation and tests |
|---|---|---|
| Input acceptance | Accepted input is bounded (100 fields and 2 GiB in total per workspace; one plane of at most 4096×4096 px). Storage uses internal identifiers, and uploaded file names are not used in paths. Paths are verified to lie inside the storage area. Arrays are loaded with pickle disabled. | [`config.py`](services/api/src/cytellect_api/config.py) [`images.py`](packages/analysis/src/cytellect_analysis/images.py) [`region_inputs.py`](services/api/src/cytellect_api/region_inputs.py) [`upload_guard.py`](services/api/src/cytellect_api/upload_guard.py) [`db.py`](services/api/src/cytellect_api/db.py) [`test_upload_guard.py`](tests/test_upload_guard.py) |
| Response headers | Responses carry headers that forbid caching, MIME type sniffing, sending the referrer and embedding in frames. The local web interface applies a Content Security Policy that forbids loading external resources and connecting to external hosts. | [`app.py`](services/api/src/cytellect_api/app.py) [`local.py`](services/api/src/cytellect_api/local.py) [`test_local.py`](tests/test_local.py) |
| Logging and errors | Access logging is disabled. Request bodies, file names and token values are not logged. Errors return predefined error codes only; internal exceptions and analysis program output are not returned. | [`local.py`](services/api/src/cytellect_api/local.py) [`app.py`](services/api/src/cytellect_api/app.py) |
| Communication with the cloud | Communication with the cloud uses HTTPS only. URLs containing credentials, a query or a fragment are not accepted. Redirects are not followed, response size is limited, and only predefined fields are passed to the local web interface. | [`cloud_account.py`](services/api/src/cytellect_api/cloud_account.py) [`proposals.py`](services/api/src/cytellect_api/proposals.py) [`cellpose_engine.py`](packages/analysis/src/cytellect_analysis/cellpose_engine.py) [`test_cloud_account.py`](tests/test_cloud_account.py) |
| Verification of detection responses | The PC accepts a detection result only when the hashes of the runner, the model and the lockfile stated in the response match those of the installed version. | [`cellpose_engine.py`](packages/analysis/src/cytellect_analysis/cellpose_engine.py) [`test_cellpose_remote.py`](tests/test_cellpose_remote.py) |

#### 8.3 Isolation and supervision of the analysis worker

| Measure | Mechanism | Implementation and tests |
|---|---|---|
| Container isolation (Docker release) | The analysis worker runs in a container with no network, as a non-root user, on a read-only root filesystem. All Linux capabilities are dropped, privilege escalation is disabled, and memory and process count are limited. CI verifies on the real container that outbound connections are denied. | [`compose.yaml`](compose.yaml) [`ci.yml`](.github/workflows/ci.yml) |
| Job supervision | Jobs are subject to time and memory limits. When the supervising process can no longer confirm a job's state, the analysis processes are terminated and their result is not committed. | [`supervision.py`](services/worker/src/cytellect_worker/supervision.py) [`test_supervision.py`](tests/test_supervision.py) |
| Downloads while running | No code or model is downloaded while an analysis runs. | [`runner.py`](engines/cellpose/runner.py) [`fiji/runtime.lock.json`](engines/fiji/runtime.lock.json) |

### 9. AI assistance

AI output is not executed as code. An analysis proposal is validated on the PC as settings consisting only of predefined fields and values, and only proposals that pass validation are shown to the researcher as drafts. A proposal is not used in an analysis until the researcher adopts it. After adoption, the shared implementation still computes measurements and statistics, and the proposal produces no values.

The PC rejects the following proposals.

- A proposal containing a field that is not in the schema
- A proposal whose explanatory text contains a URL or code-like text
- A proposal whose channel set does not match what was transmitted
- A proposal that alters a recorded stain or establishes an unrecorded one
- A proposal received after the workspace data changed, or the workspace expired or was deleted, while waiting for the AI's response

A discussion draft is validated for structure and saved as text with its comparison. It does not modify analysis settings or values.

Implementation and tests: [`proposal_validation.py`](packages/analysis/src/cytellect_analysis/proposal_validation.py) [`proposal_contracts.py`](packages/analysis/src/cytellect_analysis/proposal_contracts.py) [`discussion_validation.py`](packages/analysis/src/cytellect_analysis/discussion_validation.py) [`proposals.py`](services/api/src/cytellect_api/proposals.py) [`test_proposals.py`](tests/test_proposals.py) [`test_proposals_persistence.py`](tests/test_proposals_persistence.py) [`test_result_discussion.py`](tests/test_result_discussion.py)

### 10. Cryptography and key management

| Purpose | Method | Key custody |
|---|---|---|
| Protection in transit | TLS. Server certificates are verified against the OS trust store. | Each service manages the private key of its server certificate. |
| Device token | 256 bits from a cryptographically secure random source. The relay service stores only the SHA-256 hash. | The settings area on the PC |
| Sign-in code | Only an HMAC-SHA256 hash is stored. | The HMAC key is held as a secret of the relay service, outside the database. |
| Approval link | Signed with HMAC-SHA256. Comparison is in constant time. | As above |
| Admin page JWT | The RS256 signature is verified with Cloudflare Access's public keys. | The private key is held by Cloudflare Access. |
| Update signature | An Ed25519 SSH signature (OpenSSH SSHSIG format, namespace `cytellect-update`, SHA-512 hash). The public key is built into the application. | The private key is held only by the maintainer and in signing environments restricted to runs from `main`. |
| Integrity verification | SHA-256. Applied to the installer, bundled components, detection models, dependencies and imported images. | Expected hashes are recorded in the repository and in the signed manifest. |

Implementation and tests: [`http.ts`](services/proposal-worker/src/http.ts) [`access.ts`](services/proposal-worker/src/access.ts) [`update_signature.py`](services/api/src/cytellect_api/update_signature.py) [`test_update_signature.py`](tests/test_update_signature.py)

### 11. Releases and supply chain

#### 11.1 Update signing and verification

| Measure | Mechanism | Implementation and tests |
|---|---|---|
| Microsoft Store release (Windows 11) | Signed by Microsoft; installed and updated by the Microsoft Store. Submissions to the Microsoft Store are limited to the latest `main` commit approved by the maintainer. | [`windows-store-release.yml`](.github/workflows/windows-store-release.yml) |
| Update signature (EXE release) | Each release carries a manifest stating the version, installer name, SHA-256, size, source commit and time of issue, with a signature made with the Ed25519 key. | [`local-release.yml`](.github/workflows/local-release.yml) [`update_signature.py`](services/api/src/cytellect_api/update_signature.py) [`test_update_signature.py`](tests/test_update_signature.py) |
| Update verification (EXE release) | The application verifies the manifest's signature with its built-in public key before fetching the installer. The installer runs only when the version is newer than the installed one and its SHA-256 and size match the manifest. Downloads are restricted to GitHub hosts over HTTPS, and redirect targets are checked as well. The hash reported by the distribution host is not trusted. | [`update_signature.py`](services/api/src/cytellect_api/update_signature.py) [`app_update.py`](services/api/src/cytellect_api/app_update.py) [`test_update_signature.py`](tests/test_update_signature.py) [`test_app_update.py`](tests/test_app_update.py) |
| Update rollback (EXE release) | A copy of the database is taken before an update is applied. If the new version fails to start, the application returns to the previous version and that copy. | [`app_update.py`](services/api/src/cytellect_api/app_update.py) [`test_app_update.py`](tests/test_app_update.py) |
| First installation (EXE release) | The installer for a first installation can also be verified against the same signed manifest ([steps, in Japanese](docs/install-windows.ja.md#2-ダウンロードと確認)). | [`update_signature.py`](services/api/src/cytellect_api/update_signature.py) |

#### 11.2 Release verification

| Measure | Mechanism | Implementation and tests |
|---|---|---|
| Signing key custody | The signing key is held only by the maintainer and in GitHub Actions signing environments restricted to runs from `main`. Procedures for creating, registering, rotating and revoking the key are defined. | [`release-signing.md`](docs/release-signing.md) [`local-release.yml`](.github/workflows/local-release.yml) |
| Release conditions | A manual release requires the maintainer's approval. An automatic release publishes only versions that have passed CI and the distribution tests on protected `main`. | [`local-release.yml`](.github/workflows/local-release.yml) [`windows_exe_release.cjs`](scripts/windows_exe_release.cjs) [`windows_exe_release.test.cjs`](scripts/windows_exe_release.test.cjs) |
| Commit verification | A release is built from a single commit, which is re-checked at each stage. A commit that is not in the history of `main`, a run originating from a fork and reuse of a tag are refused. | [`local-release.yml`](.github/workflows/local-release.yml) [`windows_exe_release.cjs`](scripts/windows_exe_release.cjs) [`windows_exe_release.test.cjs`](scripts/windows_exe_release.test.cjs) |
| Verification of published files | A file whose size or hash does not match the tested file is not published. | [`windows_exe_release.cjs`](scripts/windows_exe_release.cjs) [`windows_exe_release.test.cjs`](scripts/windows_exe_release.test.cjs) |

#### 11.3 Dependencies and bundled components

| Measure | Mechanism | Implementation and tests |
|---|---|---|
| Dependency pinning | Python and JavaScript dependencies are pinned by version and hash in lockfiles. | [`uv.lock`](uv.lock) [`pnpm-lock.yaml`](pnpm-lock.yaml) |
| Verification of bundled components | The bundled Fiji, detection models and Python runtime are checked against SHA-256 at build time. | [`fiji/runtime.lock.json`](engines/fiji/runtime.lock.json) [`cellpose/runtime.lock.json`](engines/cellpose/runtime.lock.json) [`build_windows_installer.py`](scripts/build_windows_installer.py) [`test_windows_installer.py`](tests/test_windows_installer.py) |
| Inspection of releases | Releases are scanned for credentials at build time, and the build fails if any is found. | [`build_windows_installer.py`](scripts/build_windows_installer.py) [`test_windows_installer.py`](tests/test_windows_installer.py) |
| Bill of materials | CI generates a software bill of materials (SBOM) for dependencies. | [`sbom.py`](scripts/sbom.py) [`ci.yml`](.github/workflows/ci.yml) [`test_sbom.py`](tests/test_sbom.py) |

#### 11.4 Repository and CI

| Measure | Mechanism | Implementation and tests |
|---|---|---|
| Merging to `main` | Merging to `main` is restricted to the maintainer by a ruleset. Changes are made through pull requests and merged once the required CI has passed. | [`ci.yml`](.github/workflows/ci.yml) |
| Secret detection | A hash-verified gitleaks scans the full Git history of `main` and of every pull request. | [`scan_secrets.py`](scripts/scan_secrets.py) [`security-tools.lock.json`](scripts/security-tools.lock.json) [`ci.yml`](.github/workflows/ci.yml) [`test_scan_secrets.py`](tests/test_scan_secrets.py) |
| Static analysis and vulnerability audits | CodeQL (workflows, JavaScript/TypeScript, Python) runs on pull requests, on `main` and weekly. Dependency vulnerability audits (pip-audit, pnpm audit) run in CI. | [`codeql.yml`](.github/workflows/codeql.yml) [`ci.yml`](.github/workflows/ci.yml) |
| Workflow permissions | The workflow token is read-only by default. Runs originating from forks receive neither write permission nor secrets. | [`ci.yml`](.github/workflows/ci.yml) [`local-release.yml`](.github/workflows/local-release.yml) |
| Separation of research data | The repository and CI contain no private research data. Evaluation and the public demo use public images whose source, redistribution terms and hashes are recorded. Development environments used by several people reject uploads other than registered public files by checking their SHA-256. | [`public_uploads.py`](services/api/src/cytellect_api/public_uploads.py) [`test_public_uploads.py`](tests/test_public_uploads.py) |

### 12. Revocation of credentials and keys

| Credential or key | Means of revocation | When it takes effect |
|---|---|---|
| Device token | Sign-out, account revocation, or 90 days without use | The next request |
| Session on the PC | Logging out, or exiting the application (Windows release) | Immediately |
| HMAC key for sign-in codes and approval links | Key rotation | Unused sign-in codes and approval links become invalid at rotation. |
| API keys of external services | Invalidation at the external service and update of the relay service's secret | At the update |
| Update-signing key | Removal from the signing environments and distribution of a version with a new built-in key ([release signing](docs/release-signing.md), in Japanese) | From the moment it is removed from the signing environments, no new signature can be made with that key. |

Implementation and tests: [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`local.py`](services/api/src/cytellect_api/local.py) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) [`release-signing.md`](docs/release-signing.md)

### 13. Vulnerability handling

#### 13.1 Versions that receive fixes

| Target | Security fixes |
|---|---|
| The Microsoft Store release | Provided (the Microsoft Store updates it to the latest version) |
| The latest EXE release | Provided |
| `main` (`cytellect.app`, the cloud features and the Docker release) | Provided |
| Earlier EXE releases | Not provided (they move to the latest version through the in-app update) |

#### 13.2 Scope

This repository's code, the Windows release (Microsoft Store and EXE), the Docker release, `cytellect.app`, the relay service and the inference server are in scope. Issues arising from how Cytellect configures or uses an external service are also in scope. Vulnerabilities in bundled third-party components (Fiji, Cellpose and others) and in the external services themselves are handled by their upstream projects and providers.

#### 13.3 Reporting a vulnerability

Report vulnerabilities through GitHub's private reporting feature. Selecting **Report a vulnerability** under the repository's **Security** tab submits a report visible only to the reporter and the repository maintainers ([report form](https://github.com/genellect/cytellect/security/advisories/new)). Do not describe vulnerabilities in public places such as issues, pull requests or discussions.

Include the following in a report.

- The affected commit, or the version of the Windows release
- Reproduction steps
- The expected impact

Use synthetic or public data for reproduction.

#### 13.4 Response to a report

1. Reasonable reports receive a reply within three days.
2. The affected scope and severity are assessed and shared with the reporter.
3. The issue is fixed in a private security advisory and the fixed version is released. The public site and cloud features are deployed to production, and the Windows release is distributed through the Microsoft Store and a signed update.
4. After the release, the security advisory is published and a CVE is requested where appropriate. The reporter is credited by name on request.

Published security advisories are available in the [list](https://github.com/genellect/cytellect/security/advisories).

### 14. Related documents

| Document | Content |
|---|---|
| [Release signing](docs/release-signing.md) | Creating, registering, rotating and revoking the signing key (in Japanese) |
| [Team development rules, section 6](docs/team-development.md#6-research-data) | The handling of research data and credentials in development |
| [Privacy policy](https://cytellect.app/privacy) | Information handled by the Microsoft Store release and the cloud features (in Japanese) |
