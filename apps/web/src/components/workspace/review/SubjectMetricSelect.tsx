import {useId, type KeyboardEvent, type ReactNode} from "react";
import {SUBJECTS, SUBJECT_METRICS, UNIT_LABELS, metricChoice, metricLabel, metricSubject, subjectEntry, type MetricSubject, type SubjectMetric} from "@/lib/workspace/metric-catalog";
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

interface Radio<T extends string> {value: T; label: ReactNode; disabled?: boolean; title?: string}
/** A choice of one (WAI-ARIA radio group): a single Tab stop on the checked radio; the arrow keys move to the next
 * choosable radio and choose it. */
function RadioGroup<T extends string>({radios, value, onChoose, className, label}: {
  radios: Radio<T>[]; value: T; onChoose: (value: T) => void; className: string;
  label: {"aria-labelledby": string} | {"aria-label": string};
}) {
  const focusable = radios.some(radio => radio.value === value && !radio.disabled) ? value : radios.find(radio => !radio.disabled)?.value;
  function move(event: KeyboardEvent<HTMLButtonElement>, from: number) {
    const step = event.key === "ArrowRight" || event.key === "ArrowDown" ? 1 : event.key === "ArrowLeft" || event.key === "ArrowUp" ? -1 : 0;
    if (!step) return;
    event.preventDefault();
    for (let offset = 1; offset < radios.length; offset++) {
      const index = (from + step * offset + radios.length) % radios.length;
      if (radios[index].disabled) continue;
      event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>("[role=radio]")[index]?.focus();
      if (radios[index].value !== value) onChoose(radios[index].value);
      return;
    }
  }
  return <div className={className} role="radiogroup" {...label}>
    {radios.map((radio, index) => <button key={radio.value} type="button" role="radio" aria-checked={radio.value === value} tabIndex={radio.value === focusable ? 0 : -1}
      disabled={radio.disabled} title={radio.title} onKeyDown={event => move(event, index)} onClick={() => {if (radio.value !== value) onChoose(radio.value);}}>{radio.label}</button>)}
  </div>;
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
    <RadioGroup className={`${styles.subjects} ${subjects.length > 3 ? styles.twoColumns : ""}`} label={{"aria-labelledby": `${id}-subject`}} value={subject} onChoose={onSubject}
      radios={subjects.map(value => ({value, label: <><Pictogram subject={value}/>{SUBJECT_LABELS[value]}</>}))}/>
    <div className={styles.metric}>
      <div className={styles.caption}><span id={`${id}-metric`}>指標</span>{entry && <span className={styles.unit} id={`${id}-unit`}>{UNIT_LABELS[entry.unit]}</span>}</div>
      <select aria-labelledby={`${id}-metric`} aria-describedby={entry ? `${id}-unit` : undefined} value={entry?.metric.variants[0].id ?? metric} onChange={event => onMetric(event.target.value, subject)}>
        {/* A metric set elsewhere (a saved result) that no subject lists is shown as it is, not as the first entry. */}
        {!entry && <option value={metric} disabled>{metricLabel(metric)}</option>}
        {groups.map(group => <optgroup key={group.unit} label={UNIT_LABELS[group.unit]}>
          {group.metrics.filter(item => listed(item, subject)).map(item => {
            const base = item.variants[0].id, unavailable = needsCalibration(base);
            return <option key={base} value={base} disabled={unavailable}>{item.label}{unavailable ? "（画素の大きさが必要）" : ""}</option>;
          })}
        </optgroup>)}
      </select>
      {variants.length > 1 && <RadioGroup className={styles.variants} label={{"aria-label": variants.some(variant => variant.label === "µm²") ? "単位" : "補正"}}
        value={metric} onChoose={value => onMetric(value, subject)}
        radios={variants.map(variant => {const unavailable = needsCalibration(variant.id); return {value: variant.id, label: variant.label, disabled: unavailable, title: unavailable ? "画素の大きさが必要" : undefined};})}/>}
    </div>
    {choice && <small data-testid="metric-definition">{choice.definition}</small>}
  </>;
}
