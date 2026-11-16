import type { Metadata } from "next";
import Link from "next/link";
import lp from "@/components/optical-landing.module.css";
import { CONTACT_URL, SITE_URL } from "@/lib/site";

export const metadata: Metadata = {
  title: "プライバシーポリシー | Cytellect",
  description: "Cytellect の Microsoft Store 版とクラウド機能で取り扱う情報について。",
  ...(SITE_URL ? { alternates: { canonical: `${SITE_URL}/privacy` } } : {}),
};

export default function PrivacyPage() {
  return (
    <div className={`${lp.page} ${lp.guidePage}`}>
      <header className={lp.guideHeader}>
        <Link href="/" className={lp.wordmark} aria-label="Cytellect ホーム">cytellect</Link>
      </header>
      <main className={lp.guideMain}>
        <h1>プライバシーポリシー</h1>
        <p className={lp.guideLead}>
          このポリシーは、genellect が運営する Cytellect の Microsoft Store 版と、
          作業画面から利用できる Cytellect のクラウド機能に適用されます。
        </p>

        <section aria-labelledby="local-data">
          <h2 id="local-data">PC 上に保存する作業データ</h2>
          <p>
            取り込んだ画像、輪郭、測定値、表や図は、利用者の Windows アカウントの作業フォルダーに保存します。
            アプリを更新・アンインストールした場合も作業フォルダーは残ります。
            作業を消すには、アプリのワークスペース一覧で対象を選んで削除してください。
            アンインストールの後にすべて消すには、作業フォルダー（<code>%LOCALAPPDATA%\Cytellect</code>）を削除してください。
            このフォルダーには、作業データのほか、設定、ログ、ログイン後の端末トークンがあります。
            別の場所に書き出したファイルは、保存先で削除できます。
          </p>
        </section>

        <section aria-labelledby="cloud-account">
          <h2 id="cloud-account">クラウドへのログイン</h2>
          <p>
            ログイン、利用承認、不正利用の防止、利用枠の管理のために、
            メールアドレス、承認状態と日時、ログインコードと端末トークンのハッシュ、GPU と AI 機能の利用量を保管します。
            メールアドレスとログインコードを、コードの送信を委託する Resend に渡します。
            ログイン後、PC は端末トークンを Windows アカウントの設定フォルダーに保存します。
            サインアウトすると端末トークンを PC から削除します。
          </p>
        </section>

        <section aria-labelledby="cloud-processing">
          <h2 id="cloud-processing">機能を使うときに送る情報</h2>
          <dl className={lp.guideList}>
            <dt>クラウド GPU による検出</dt>
            <dd>
              検出対象の画像面、検出条件、核小体の検出に必要な場合は採用済みの核ラベルを、
              Cloudflare 上の Cytellect サービスを経由して Modal に送ります。
              Cytellect サービスと推論サーバーは、処理に使った画像やラベルを保存しません。
              測定、統計と作図は PC 上で行います。
            </dd>
            <dt>AI による解析提案</dt>
            <dd>
              利用者が画面で送信を確認すると、入力した指示と画像のチャンネル名や寸法などの解析条件を、
              Cytellect サービスを経由して OpenAI API に送ります。画像、輪郭と測定表は PC に残ります。
            </dd>
            <dt>AI による考察の生成</dt>
            <dd>
              利用者が画面で送信を確認すると、保存した比較結果の集計値と入力した実験目的を、
              Cytellect サービスを経由して OpenAI API に送ります。集計値には染色名、群の名前、群ごとの値、差と信頼区間、
              実験回ごとの値、件数、検定と p 値が含まれます。画像、ファイル名とパスは PC に残ります。
              OpenAI は、解析提案と考察のリクエストを不正利用の監視に必要な期間保持する場合があります。
            </dd>
            <dt>Microsoft Store</dt>
            <dd>
              アプリの取得と更新は Microsoft Store が扱います。
              Microsoft アカウントや Store 自体で取り扱う情報については、
              <a href="https://www.microsoft.com/privacy/privacystatement">Microsoft のプライバシーに関する声明</a>
              をご覧ください。
            </dd>
          </dl>
        </section>

        <section aria-labelledby="privacy-contact">
          <h2 id="privacy-contact">利用者が選べることとお問い合わせ</h2>
          <p>
            PC 上の解析はクラウドにログインせずに使えます。クラウド機能の利用をやめる場合は、
            作業画面のアカウント設定からサインアウトしてください。
            お預かりした個人情報の確認・訂正・削除をご希望の場合は、Cytellect の窓口までご連絡ください。
          </p>
          <nav className={lp.guideMore} aria-label="関連情報">
            <a href={CONTACT_URL}>Cytellect へのお問い合わせ</a>
            <a href="https://github.com/genellect/cytellect/blob/main/docs/security.md">データ保護の詳細</a>
          </nav>
        </section>
      </main>
    </div>
  );
}
