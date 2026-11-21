import {NUCLEOLAR_STRESS, themeRows} from "@/lib/workspace/research-themes";
import styles from "./subject-metric.module.css";

/** The 核小体ストレス measures for the registered stains (#257 NS-01): each measure with its stain, region and
 * observation unit, and whether it can be measured here. Closed until opened; it chooses nothing by itself. */
export function NucleolarStressList({stains}: {stains: Array<{id: string; name: string}>}) {
  const rows = themeRows(NUCLEOLAR_STRESS, stains);
  return <details className={styles.theme}>
    <summary>{NUCLEOLAR_STRESS.label}</summary>
    <ul aria-label={`${NUCLEOLAR_STRESS.label}の指標`}>
      {rows.map(row => <li key={`${row.metric}-${row.region}`} data-available={row.available}>
        <strong>{row.label}</strong>
        <span>染色：{row.stain}{row.available ? "" : "（未登録）"}</span>
        <span>領域：{row.region}</span>
        <span>観測：{row.unit}</span>
      </li>)}
    </ul>
  </details>;
}
