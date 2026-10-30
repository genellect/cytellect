import { PUBLISHED_RELEASE, releaseSize, windowsReleaseAsset } from "@/lib/release";
import styles from "./workspace.module.css";

export default function WindowsDownload({url}:{url:string}){
 const published=PUBLISHED_RELEASE?.url===url?PUBLISHED_RELEASE:null;
 const installer=windowsReleaseAsset(url)==="installer";
 return <div className={styles.windowsDownload}>
  <p className={styles.muted}>Windows版で、自分の画像を解析できます。</p>
  <a className={styles.primary} href={url} rel="noreferrer">Cytellectをダウンロード <span aria-hidden="true">↓</span></a>
  <p className={styles.downloadPlatform}>Windows · x64 <span>開発プレビュー</span></p>
  {published&&<a className={styles.releaseInfo} href={`https://github.com/genellect/cytellect/releases/tag/v${published.version}`} target="_blank" rel="noreferrer">v{published.version} · リリース情報・SHA-256 ↗</a>}
  {installer?<>
   <p className={styles.small}>インストーラー{published&&`・${releaseSize(published.size_bytes)}`}・Windows 10／11（64ビット）・管理者権限は不要です。</p>
   <ol className={styles.setupSteps}>
    <li><b>開く</b><span>ダウンロードしたCytellect-Setupを開きます。</span></li>
    <li><b>インストール</b><span>「インストール」を押します。約5〜10分で終わり、解析画面がブラウザで開きます。</span></li>
    <li><b>ログイン</b><span>メールに届くコードでログインすると、GPUでの検出も使えます。</span></li>
   </ol>
   <p className={styles.small}>Windowsの警告画面が出たら、「詳細情報」を押してから「実行」を押します。</p>
  </>:<>
   <ol className={styles.setupSteps}>
    <li><b>展開する</b><span>ZIPを展開し、Cytellect Setup.cmdを開きます。</span></li>
    <li><b>セットアップ</b><span>初回のみ、解析に必要な環境を取得します。</span></li>
    <li><b>解析を開始</b><span>ショートカットから起動し、ブラウザで画像を登録します。</span></li>
   </ol>
   <p className={styles.small}>初回セットアップにはインターネット接続が必要です。</p>
  </>}
  <a className={styles.releaseInfo} href="https://github.com/genellect/cytellect/blob/main/docs/install-windows.ja.md" target="_blank" rel="noreferrer">インストールと更新の手順 ↗</a>
  <a className={styles.releaseInfo} href="https://github.com/genellect/cytellect/blob/main/docs/quickstart.ja.md" target="_blank" rel="noreferrer">公開画像で、はじめての解析 ↗</a>
  <details className={styles.downloadPrivacy}>
   <summary>保存先と削除について</summary>
   <p>画像と解析結果は、PC内のCytellect専用フォルダーに保存します。Webサイトには送信しません。PCの外へ画像を送るのは、次の設定をした場合だけです。</p>
   <p>管理者がCellpose用のクラウドGPUを設定した場合：Cellposeの検出に使う1チャンネルの画像（核小体の検出では核のマスクも）をそのGPUへ送ります。送った画像はクラウド側に保存しません。</p>
   <p>作業は、既定ではワークスペースで削除するまで保持します。セットアップで選択を外した場合は、最後の明示的な操作から24時間で削除します。終了中に期限を迎えたデータは次回起動時に削除します。</p>
   <p>必要な結果は保存機能から書き出し、別の媒体にもバックアップしてください。作業の削除はワークスペース内から実行できます。</p>
  </details>
 </div>;
}
