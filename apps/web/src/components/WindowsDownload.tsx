import styles from "./workspace.module.css";

export default function WindowsDownload({url}:{url:string}){
 return <div className={styles.windowsDownload}>
  <p className={styles.muted}>Windows版で、自分の画像を解析できます。</p>
  <a className={styles.primary} href={url} rel="noreferrer">Cytellectをダウンロード <span aria-hidden="true">↓</span></a>
  <p className={styles.downloadPlatform}>Windows · x64 <span>開発プレビュー</span></p>
  <ol className={styles.setupSteps}>
   <li><b>展開する</b><span>ZIPを展開し、Cytellect Setup.cmdを開きます。</span></li>
   <li><b>セットアップ</b><span>初回のみ、解析に必要な環境を取得します。</span></li>
   <li><b>解析を開始</b><span>ショートカットから起動し、ブラウザで画像を登録します。</span></li>
  </ol>
  <p className={styles.small}>初回セットアップにはインターネット接続が必要です。</p>
  <details className={styles.downloadPrivacy}>
   <summary>保存先と削除について</summary>
   <p>画像と解析結果は、PC内のCytellect専用フォルダーに保存します。Webサイトや外部AIには送信しません。</p>
   <p>保存期限は最後の明示的な操作から24時間です。期限後はアクセスできなくなり、削除されます。終了中に期限を迎えたデータは次回起動時に削除します。</p>
   <p>必要な結果は保存機能から書き出してください。作業の削除はワークスペース内から実行できます。</p>
  </details>
 </div>;
}
