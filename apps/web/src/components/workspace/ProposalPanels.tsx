"use client";
import type { ReactNode } from "react";
import { channelName, type ChannelDefinition, type Grouping } from "@/lib/workspace/grouping";
import { NUCLEAR_CHOICE, type Proposal } from "@/lib/workspace/proposal";
import styles from "./analysis-workspace.module.css";

const EVIDENCE_LABEL: Record<ChannelDefinition["evidence"], string> = {
  ome: "画像情報から", filename: "ファイル名から", folder: "フォルダ名から", user: "選択済み",
};

export function channelText(channel: ChannelDefinition): string {
  return `${channelName(channel)}${channel.role === "nuclear" ? "（核検出）" : ""}`;
}

/** Short proposal summary; details and optional names stay behind 解析条件. */
export function ProposalSummary({ proposal, grouping, onRun, onName, children }: {
  proposal: Proposal;
  grouping: Grouping;
  onRun: () => void;
  onName: (token: string, stain: string) => void;
  children?: ReactNode;
}) {
  const ready = proposal.recipe !== null && proposal.unresolved.length === 0;
  const others = proposal.unresolved.filter((item) => item !== NUCLEAR_CHOICE);
  return (
    <section className={styles.proposal} aria-labelledby="proposal-title">
      <h2 id="proposal-title">解析案</h2>
      {children}
      <dl className={styles.summaryList}>
        <div><dt>対象</dt><dd>{proposal.fieldCount} 視野 · {grouping.channels.map(channelText).join("、")}</dd></div>
        <div><dt>検出する領域</dt><dd>{proposal.regions.length ? proposal.regions.join("、") : "—"}</dd></div>
        <div><dt>測定</dt><dd>{proposal.metrics.length ? proposal.metrics.map((metric) => metric.label).join("、") : "—"}</dd></div>
        <div><dt>グラフ</dt><dd>{proposal.statistics.kind === "descriptive" ? "視野ごとの分布" : "実験単位での群間比較と分布"}</dd></div>
      </dl>
      {others.length > 0 && <ul className={styles.unresolved} role="status">{others.map((item) => <li key={item}>{item}</li>)}</ul>}
      {proposal.notes.map((note) => <p key={note} className={styles.note}>{note}</p>)}
      <button type="button" className={styles.primary} disabled={!ready} onClick={onRun}>解析を実行</button>
      <details className={styles.conditions}>
        <summary>解析条件</summary>
        <dl>
          <div><dt>核検出</dt><dd>Fiji / StarDist 2D · Versatile (fluorescent nuclei) · 正規化 1–99.8 percentile · 確率 0.5 · NMS 0.3</dd></div>
          <div><dt>背景補正</dt><dd>行わない（補正前の値を出力）</dd></div>
          <div><dt>集計</dt><dd>領域 → 視野内中央値 → 試料内平均 → 独立実験単位内平均</dd></div>
        </dl>
        <fieldset className={styles.names}>
          <legend>チャンネルの染色名（任意）</legend>
          {grouping.channels.map((channel) => (
            <label key={channel.token}>{channel.token}
              <input defaultValue={channel.stain ?? ""} placeholder="未指定"
                onBlur={(event) => { if ((channel.stain ?? "") !== event.target.value.trim()) onName(channel.token, event.target.value); }} />
            </label>
          ))}
        </fieldset>
      </details>
    </section>
  );
}

/** One click: the channel used to detect nuclei. Shown only when file names do not decide it. */
export function NuclearChoice({ grouping, preview, onChoose }: {
  grouping: Grouping;
  preview: (token: string) => string | null;
  onChoose: (token: string) => void;
}) {
  const chosen = grouping.channels.find((channel) => channel.role === "nuclear");
  const decided = chosen && chosen.evidence !== "user" && grouping.channels.filter((channel) => channel.role === "nuclear").length === 1;
  if (decided) {
    return <p className={styles.note}>核検出: {channelName(chosen)}（{EVIDENCE_LABEL[chosen.evidence]}）</p>;
  }
  return (
    <fieldset className={styles.nuclearChoice}>
      <legend>{chosen ? "核検出に使うチャンネル" : "核検出に使うチャンネルを選択"}</legend>
      <div role="radiogroup" aria-label="核検出に使うチャンネル">
        {grouping.channels.map((channel) => {
          const src = preview(channel.token);
          return (
            <button key={channel.token} type="button" role="radio" aria-checked={channel.role === "nuclear"}
              aria-label={`${channelName(channel)} を核検出に使う`} onClick={() => onChoose(channel.token)}>
              {src ? <img src={src} alt="" /> : <span className={styles.thumbEmpty} />}
              <span>{channelName(channel)}</span>
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
