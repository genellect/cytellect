"use client";
import type {ReactNode} from "react";
import styles from "./analysis-workspace.module.css";

export type MethodStep = {
  id: string; number: number; title: string; description: string; state: string;
  tone: "done" | "current" | "todo" | "attention"; action?: {label: string; onClick: () => void; disabled?: boolean};
  details?: ReactNode;
};

/** One card per analysis: what each step does, its state, and one compact action. */
export function MethodPanel({goal, onGoal, onAi, aiBusy, aiDisabled, aiResponse, steps, onApply, applyLabel, applyDisabled, onMethodDetails}: {
  goal: string; onGoal: (value: string) => void; onAi: () => void; aiBusy: boolean; aiDisabled: boolean; aiResponse?: ReactNode;
  steps: MethodStep[]; onApply: () => void; applyLabel: string; applyDisabled: boolean; onMethodDetails: () => void;
}) {
  return <section className={styles.methodPanel} aria-label="解析方法">
    <form className={styles.goalForm} onSubmit={event => {event.preventDefault(); onAi();}}>
      <label htmlFor="analysis-goal">何を調べますか</label>
      <textarea id="analysis-goal" value={goal} maxLength={1000} rows={3}
        placeholder="例）処理群で NCL が核小体から核質へ移るかを比べたい" onChange={event => onGoal(event.target.value)}/>
      <div className={styles.goalActions}>
        <button type="submit" className={styles.primary} disabled={aiDisabled || aiBusy}>{aiBusy ? "AI が方法を選んでいます…" : "AI に方法を選ばせる"}</button>
      </div>
      {aiResponse}
    </form>
    <div className={styles.methodCard}>
      <div className={styles.methodCardHeader}><strong>解析方法</strong><button type="button" className={styles.linkButton} onClick={onMethodDetails}>手法の詳細と文献</button></div>
      <ol className={styles.methodSteps}>
        {steps.map(step => <li key={step.id} className={styles.methodStep} data-tone={step.tone}>
          <span className={styles.stepNumber} aria-hidden="true">{step.number}</span>
          <div className={styles.stepBody}>
            <span className={styles.stepTitle}>{step.title}</span>
            <span className={styles.stepDescription}>{step.description}</span>
            <span className={styles.stepState}>{step.state}</span>
            {step.details}
          </div>
          {step.action && <button type="button" className={styles.linkButton} disabled={step.action.disabled} onClick={step.action.onClick}>{step.action.label}</button>}
        </li>)}
      </ol>
      <div className={styles.methodApply}><button type="button" className={styles.primary} disabled={applyDisabled} onClick={onApply}>{applyLabel}</button></div>
    </div>
  </section>;
}
