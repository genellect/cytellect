"use client";
import {NUCLEOLAR_STRESS, themeRow} from "@/lib/workspace/research-themes";
import type {ReviewTarget} from "@/lib/workspace/review-preview";
import styles from "./experiment-setup.module.css";

/** The 核小体ストレス theme (#257 E-7, NS-01): each question with the measure that answers it, the stain it reads, the
 * region and what one observation is, before any comparison. 「画像で見る」 opens the region on the original image;
 * 「主要指標にする」 declares it (RP-04). */
export function ResearchTheme({stains, readOnly, busy, onView, onDeclare}: {stains: Array<{id: string; name: string}>; readOnly: boolean; busy: boolean;
  onView: (subject: ReviewTarget, channel: string | null) => void;
  onDeclare: (metric: string, subject: ReviewTarget, channel: string | null) => void}) {
  const rows = NUCLEOLAR_STRESS.questions.map(question => themeRow(question, stains));
  return <details className={styles.theme}>
    <summary>研究テーマから指標を選ぶ：{NUCLEOLAR_STRESS.label}</summary>
    <p>{NUCLEOLAR_STRESS.summary}</p>
    <div className={styles.themeScroll}><table aria-label={`${NUCLEOLAR_STRESS.label}の指標`}>
      <thead><tr><th scope="col">問い</th><th scope="col">指標</th><th scope="col">染色</th><th scope="col">測定する領域</th><th scope="col">観測の単位</th><th scope="col"><span className={styles.hidden}>操作</span></th></tr></thead>
      <tbody>{rows.map(row => <tr key={row.question} data-available={row.available}>
        <th scope="row">{row.question}</th>
        <td title={row.definition}>{row.label}<small>{row.limit}</small></td>
        <td>{row.stain}</td><td>{row.region}</td><td>{row.unit}</td>
        <td><button className={styles.link} disabled={!row.available} onClick={() => onView(row.subject, row.channel)}>画像で見る</button>
          {!readOnly && <button className={styles.link} disabled={busy || !row.available} onClick={() => onDeclare(row.metric, row.subject, row.channel)}>主要指標にする</button>}</td>
      </tr>)}</tbody>
    </table></div>
    {rows.some(row => !row.available) && <p>「未登録」の指標には、その染色の画像が必要です。染色名は画像の「染色対応」で登録します。</p>}
  </details>;
}
