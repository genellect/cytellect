"use client";
import type {ReactNode} from "react";
import styles from "./analysis-workspace.module.css";

export type MethodStep = {
  id: string; number: number; title: string; description: string; state: string;
  tone: "done" | "current" | "todo" | "attention"; action?: {label: string; onClick: () => void; disabled?: boolean};
  details?: ReactNode;
};

/** One card per analysis: only the steps of the chosen measurement, each with its state and one compact action. */
export function MethodPanel({steps, onApply, applyLabel, applyDisabled, onMethodDetails}: {
  steps: MethodStep[]; onApply: () => void; applyLabel: string; applyDisabled: boolean; onMethodDetails: () => void;
}) {
  const choice = steps.find(step => step.id === "measure");
  const primary = steps.filter(step => ["nuclei", "positive", "nucleoli", "nucleoplasm", "drawn"].includes(step.id));
  const conditions = steps.filter(step => ["background", "gfp", "values"].includes(step.id));
  const renderStep = (step: MethodStep) => <li key={step.id} className={styles.methodStep} data-tone={step.tone}>
    <div className={styles.stepBody}>
      <span className={styles.stepTitle}>{step.title}</span>
      <span className={styles.stepDescription}>{step.description}</span>
      {step.state && step.state !== "—" && <span className={styles.stepState}>{step.state}</span>}
      {step.id === "nuclei" && step.details && step.tone !== "attention"
        ? <details className={styles.detectorOptions}><summary>検出設定</summary>{step.details}</details> : step.details}
    </div>
    {step.action && <button type="button" className={styles.linkButton} disabled={step.action.disabled} onClick={step.action.onClick}>{step.action.label}</button>}
  </li>;
  return <section className={styles.methodPanel} aria-label="解析方法">
    <div className={styles.methodCard}>
      <div className={styles.methodCardHeader}><strong>解析対象</strong><button type="button" className={styles.linkButton} onClick={onMethodDetails}>手法・条件</button></div>
      <div className={styles.analysisChoice}>{choice?.details}</div>
      <ul className={styles.methodSteps}>{primary.map(renderStep)}</ul>
      <details className={styles.measurementConditions}><summary>測定条件</summary><ul className={styles.methodSteps}>{conditions.map(renderStep)}</ul></details>
      <div className={styles.methodApply}><button type="button" className={styles.primary} disabled={applyDisabled} onClick={onApply}>{applyLabel}</button></div>
    </div>
  </section>;
}
