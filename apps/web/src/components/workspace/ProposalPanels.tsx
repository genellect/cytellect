"use client";
import { useState, type ReactNode } from "react";
import type { ChannelDefinition, ChannelRole, Grouping } from "@/lib/workspace/grouping";
import type { Proposal } from "@/lib/workspace/proposal";
import styles from "./analysis-workspace.module.css";

const ROLE_LABEL: Record<ChannelRole, string> = { nuclear: "核検出", measure: "測定" };
const EVIDENCE_LABEL: Record<ChannelDefinition["evidence"], string> = {
  ome: "画像情報", filename: "ファイル名", folder: "フォルダ名", user: "指定済み",
};

export function channelText(channel: ChannelDefinition): string {
  return `${channel.stain ?? "染色未指定"}${channel.role ? `（${ROLE_LABEL[channel.role]}）` : ""}`;
}

/** Short proposal summary; details stay behind 解析条件. */
export function ProposalSummary({ proposal, grouping, onRun, children }: { proposal: Proposal; grouping: Grouping; onRun: () => void; children?: ReactNode }) {
  const ready = proposal.recipe !== null && proposal.unresolved.length === 0;
  return (
    <section className={styles.proposal} aria-labelledby="proposal-title">
      <h2 id="proposal-title">解析案</h2>
      <dl className={styles.summaryList}>
        <div><dt>対象</dt><dd>{proposal.fieldCount} 視野 · {grouping.channels.map((channel) => `${channel.token} → ${channelText(channel)}`).join("、")}</dd></div>
        <div><dt>検出する領域</dt><dd>{proposal.regions.length ? proposal.regions.join("、") : "—"}</dd></div>
        <div><dt>測定</dt><dd>{proposal.metrics.length ? proposal.metrics.map((metric) => metric.label).join("、") : "—"}</dd></div>
        <div><dt>グラフ</dt><dd>{proposal.statistics.kind === "descriptive" ? "視野ごとの分布" : "実験単位での群間比較と分布"}</dd></div>
      </dl>
      {proposal.unresolved.length > 0 && (
        <div className={styles.unresolved} role="status">
          <strong>実行前に指定が必要です</strong>
          <ul>{proposal.unresolved.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
      )}
      {children}
      {proposal.notes.map((note) => <p key={note} className={styles.note}>{note}</p>)}
      <details className={styles.conditions}>
        <summary>解析条件</summary>
        <dl>
          <div><dt>核検出</dt><dd>Fiji / StarDist 2D · Versatile (fluorescent nuclei) · 正規化 1–99.8 percentile · 確率 0.5 · NMS 0.3</dd></div>
          <div><dt>背景補正</dt><dd>行わない（補正前の値を出力）</dd></div>
          <div><dt>集計</dt><dd>領域 → 視野内中央値 → 試料内平均 → 独立実験単位内平均</dd></div>
        </dl>
      </details>
      <button type="button" className={styles.primary} disabled={!ready} onClick={onRun}>解析を実行</button>
    </section>
  );
}

/** One set-wide channel table; never a per-field confirmation. */
export function ChannelMapping({ grouping, disabled, onApply }: {
  grouping: Grouping;
  disabled: boolean;
  onApply: (mapping: Record<string, { stain: string; role: ChannelRole }>) => void;
}) {
  const [draft, setDraft] = useState<Record<string, { stain: string; role: ChannelRole | "" }>>(() =>
    Object.fromEntries(grouping.channels.map((channel) => [channel.token, { stain: channel.stain ?? "", role: channel.role ?? "" }])));
  const complete = grouping.channels.every((channel) => draft[channel.token]?.stain.trim() && draft[channel.token]?.role);
  const changed = grouping.channels.some((channel) => draft[channel.token]?.stain !== (channel.stain ?? "") || draft[channel.token]?.role !== (channel.role ?? ""));
  return (
    <section className={styles.mapping} aria-labelledby="mapping-title">
      <h3 id="mapping-title">チャンネル対応（全視野）</h3>
      <table className={styles.mappingTable}>
        <thead><tr><th scope="col">チャンネル</th><th scope="col">染色名</th><th scope="col">役割</th></tr></thead>
        <tbody>
          {grouping.channels.map((channel) => (
            <tr key={channel.token}>
              <th scope="row">{channel.token}<small>{EVIDENCE_LABEL[channel.evidence]}</small></th>
              <td><input aria-label={`${channel.token} の染色名`} value={draft[channel.token]?.stain ?? ""} disabled={disabled}
                onChange={(event) => setDraft({ ...draft, [channel.token]: { ...draft[channel.token], stain: event.target.value } })} /></td>
              <td><select aria-label={`${channel.token} の役割`} value={draft[channel.token]?.role ?? ""} disabled={disabled}
                onChange={(event) => setDraft({ ...draft, [channel.token]: { ...draft[channel.token], role: event.target.value as ChannelRole | "" } })}>
                <option value="">未指定</option><option value="nuclear">核検出</option><option value="measure">測定</option>
              </select></td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className={styles.hint}>c1・Channel1などの番号だけでは染色名を決めません。</p>
      <button type="button" className={styles.secondary} disabled={disabled || !complete || !changed}
        onClick={() => onApply(Object.fromEntries(Object.entries(draft).map(([token, value]) => [token, { stain: value.stain.trim(), role: value.role as ChannelRole }])))}>
        対応を全視野に適用
      </button>
    </section>
  );
}
