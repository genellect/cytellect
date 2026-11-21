import {useId} from "react";
import {SUBJECTS, SUBJECT_METRICS, UNIT_LABELS, metricChoice, metricSubject, subjectEntry, type MetricSubject, type SubjectMetric} from "@/lib/workspace/metric-catalog";
import type {ReviewTarget} from "@/lib/workspace/review-preview";
import styles from "./subject-metric.module.css";

const SUBJECT_LABELS: Record<MetricSubject, string> = {nuclei: "核", nucleoli: "核小体", nucleoplasm: "核質", cell: "細胞ROI"};
const fill = "#93c5fd", line = "#1e3a8a";
/** The nucleus outline with the measured part filled. */
function Pictogram({subject}: {subject: MetricSubject}) {
  return <svg width="30" height="22" viewBox="0 0 30 22" aria-hidden="true">
    {subject === "cell" ? <>
      <rect x="1.5" y="1.5" width="27" height="19" rx="7" fill={fill} stroke={line} strokeWidth="1.5"/>
      <ellipse cx="15" cy="11" rx="7" ry="5" fill="#fff" stroke={line} strokeWidth="1"/>
    </> : <>
      <ellipse cx="15" cy="11" rx="13" ry="9" fill={subject === "nucleoli" ? "#fff" : fill} stroke={line} strokeWidth="1.5"/>
      {subject !== "nuclei" && [[11, 9, 3.2], [19, 13, 2.4]].map(([cx, cy, r]) => subject === "nucleoli"
        ? <circle key={cx} cx={cx} cy={cy} r={r} fill="#16a34a"/>
        : <circle key={cx} cx={cx} cy={cy} r={r} fill="#fff" stroke={line} strokeWidth="1"/>)}
    </>}
  </svg>;
}

/** The statistics side panel's choice of what to measure: the subject first (a pictogram of the nucleus), then that
 * subject's metrics grouped by what one observation is, then a switch between a metric's variants (requirements M-01).
 * Metrics in physical units need a confirmed pixel size and cannot be chosen without one (M-02). */
export function SubjectMetricSelect({metric, target, calibrated, offered, onSubject, onMetric}: {
  metric: string; target: ReviewTarget; calibrated: boolean;
  /** Whether a metric can be chosen when its subject is the chosen region (the demo offers what it holds). */
  offered: (metric: string, subject: MetricSubject) => boolean;
  onSubject: (subject: MetricSubject) => void;
  onMetric: (metric: string, subject: MetricSubject) => void;
}) {
  const id = useId();
  const subject = metricSubject(metric, target), entry = subjectEntry(subject, metric);
  const listed = (item: SubjectMetric, shown: MetricSubject) => offered(item.variants[0].id, shown);
  const subjects = SUBJECTS.filter(value => SUBJECT_METRICS[value].some(group => group.metrics.some(item => listed(item, value))));
  const groups = SUBJECT_METRICS[subject].filter(group => group.metrics.some(item => listed(item, subject)));
  const variants = entry?.metric.variants.filter(variant => offered(variant.id, subject)) ?? [];
  const needsCalibration = (value: string) => !!metricChoice(value)?.calibrated && !calibrated;
  const choice = metricChoice(metric);
  return <>
    <div className={styles.caption} id={`${id}-subject`}>対象</div>
    <div className={styles.subjects} role="group" aria-labelledby={`${id}-subject`}>
      {subjects.map(value => <button key={value} type="button" aria-pressed={value === subject} onClick={() => {if (value !== subject) onSubject(value);}}><Pictogram subject={value}/>{SUBJECT_LABELS[value]}</button>)}
    </div>
    <div className={styles.metric}>
      <div className={styles.caption}><span id={`${id}-metric`}>指標</span>{entry && <span className={styles.unit} id={`${id}-unit`}>{UNIT_LABELS[entry.unit]}</span>}</div>
      <select aria-labelledby={`${id}-metric`} aria-describedby={entry ? `${id}-unit` : undefined} value={entry?.metric.variants[0].id ?? ""} onChange={event => onMetric(event.target.value, subject)}>
        {groups.map(group => <optgroup key={group.unit} label={UNIT_LABELS[group.unit]}>
          {group.metrics.filter(item => listed(item, subject)).map(item => {
            const base = item.variants[0].id, unavailable = needsCalibration(base);
            return <option key={base} value={base} disabled={unavailable}>{item.label}{unavailable ? "（画素の大きさが必要）" : ""}</option>;
          })}
        </optgroup>)}
      </select>
      {variants.length > 1 && <div className={styles.variants} role="group" aria-label={variants.some(variant => variant.label === "µm²") ? "単位" : "補正"}>
        {variants.map(variant => {
          const unavailable = needsCalibration(variant.id);
          return <button key={variant.id} type="button" aria-pressed={variant.id === metric} disabled={unavailable} title={unavailable ? "画素の大きさが必要" : undefined} onClick={() => onMetric(variant.id, subject)}>{variant.label}</button>;
        })}
      </div>}
    </div>
    {choice && <small data-testid="metric-definition">{choice.definition}</small>}
  </>;
}
