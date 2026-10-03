import type { DisplayReceipt } from "@/lib/preview-display";
import { formatValue } from "@/lib/types";
import styles from "./display-scale.module.css";

export default function DisplayScaleInfo({receipt,labels}:{receipt:DisplayReceipt;labels:Record<string,string>}) {
 if(receipt.status!=="verified")return <div className={styles.info} role="status">表示範囲を確認できません。{receipt.status==="missing"?"この解析サーバーは表示条件の記録に対応していません。":"画像と表示条件の対応を確認できませんでした。"}明るさの比較には測定値を使ってください。</div>;
 const display=receipt.value;
 return <section className={styles.info} aria-label="画像の表示範囲">
  <div className={styles.heading}>自動調整 <span>画像・チャンネルごと · 保存画素値</span></div>
  <div className={styles.ranges}>{display.planes.map(plane=><div key={plane.channel_id}><strong>{labels[plane.channel_id]??plane.channel_id}</strong><span>表示下限 {formatValue(plane.display_black_value)} ／ 上限 {formatValue(plane.display_white_value)}</span></div>)}</div>
  <p>画像ごとに表示範囲を調整しています。輝度の比較には測定値を使ってください。</p>
  <details><summary>表示条件</summary><p>全画素の {display.low_percentile}–{display.high_percentile} percentile ／ 表示ゲイン {display.gain}</p>
   {display.planes.map(plane=><div className={styles.plane} key={plane.channel_id}><strong>{labels[plane.channel_id]??plane.channel_id} · {plane.dtype}</strong><dl><dt>保存画素の範囲</dt><dd>{String(plane.source_min)}–{String(plane.source_max)}</dd><dt>自動調整の基準</dt><dd>{String(plane.percentile_low_value)}–{String(plane.percentile_high_value)}</dd><dt>表示下限・上限</dt><dd>{String(plane.display_black_value)}–{String(plane.display_white_value)}</dd></dl>{plane.constant_plane?<p>全画素が同じ値です。相対的な明暗はありません。</p>:plane.percentile_low_value===plane.percentile_high_value?<p>選択範囲のpercentileが同じ値のため、幅1を基準に表示しています。</p>:null}{plane.value_basis==="legacy-imported"&&<p>互換モードで取り込んだ画素値です。RGB入力の場合は、表示画像から変換した値であり、撮影時の元輝度とは限りません。</p>}</div>)}
  </details>
 </section>;
}
