import {NUCLEOLAR_STRESS, themeRows, type ThemeRow} from "@/lib/workspace/research-themes";
import styles from "./subject-metric.module.css";

/** The 核小体ストレス measures for the registered stains (#257 NS-01): each measure with its stain, region and
 * observation unit. A measure the registered stains give is chosen here as in the selector above (Issue E-7: the
 * theme is an entry for choosing these measures); one that is not offered here (the demo holds no result for it, or
 * the stain is not registered) is listed but cannot be chosen. Closed until opened. */
export function NucleolarStressList({stains, chosen, offered, onChoose}: {stains: Array<{id: string; name: string}>;
  /** Whether a row is the condition chosen now. */
  chosen: (row: ThemeRow) => boolean;
  offered: (row: ThemeRow) => boolean;
  onChoose: (row: ThemeRow) => void}) {
  const rows = themeRows(NUCLEOLAR_STRESS, stains);
  const text = (row: ThemeRow) => <>
    <strong>{row.label}</strong>
    <span>染色：{row.stain}{row.available ? "" : "（未登録）"}</span>
    <span>領域：{row.region}</span>
    <span>観測：{row.unit}</span>
  </>;
  return <details className={styles.theme}>
    <summary>{NUCLEOLAR_STRESS.label}</summary>
    <ul aria-label={`${NUCLEOLAR_STRESS.label}の指標`}>
      {rows.map(row => <li key={`${row.metric}-${row.region}`} data-available={row.available}>
        {row.available ? <button type="button" aria-pressed={chosen(row)} disabled={!offered(row)} onClick={() => onChoose(row)}>{text(row)}</button> : text(row)}
      </li>)}
    </ul>
  </details>;
}
