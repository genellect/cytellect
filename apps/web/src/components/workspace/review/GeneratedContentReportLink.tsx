import {CONTACT_URL} from "@/lib/site";
import styles from "./discussion.module.css";

export function GeneratedContentReportLink() {
  return <a className={styles.reportLink} href={CONTACT_URL} target="_blank" rel="noopener noreferrer">
    AI の出力を報告（別のタブ）
  </a>;
}
