"use client";
import type { ReactNode } from "react";
import { channelName, type ChannelDefinition, type Grouping, type GroupingIssue } from "@/lib/workspace/grouping";
import { NUCLEAR_CHOICE, type Proposal } from "@/lib/workspace/proposal";
import styles from "./analysis-workspace.module.css";

const EVIDENCE_LABEL: Record<ChannelDefinition["evidence"], string> = {
  ome: "画像情報", filename: "ファイル名", folder: "フォルダ名", user: "選択",
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
      <ol className={styles.flow} aria-label="実行すると行う処理">
        <li>{proposal.regions.length ? `${proposal.regions.join("・")}を検出` : "領域を検出"}</li>
        <li>{proposal.metrics.length ? `${proposal.metrics.map((metric) => metric.label).join("、")}を測定` : "面積と輝度を測定"}</li>
        <li>{proposal.statistics.kind === "descriptive" ? "視野別の分布グラフを作成" : "実験単位で群間比較"}</li>
      </ol>
      <p className={styles.target}>{proposal.fieldCount} 視野 · {grouping.channels.map(channelText).join("、")}</p>
      {others.length > 0 && <ul className={styles.unresolved} role="status">{others.map((item) => <li key={item}>{item}</li>)}</ul>}
      {proposal.notes.map((note) => <p key={note} className={styles.note}>{note}</p>)}
      <button type="button" className={styles.primary} disabled={!ready} onClick={onRun}>解析を実行</button>
      <details className={styles.conditions}>
        <summary>解析条件</summary>
        <dl>
          <div><dt>核検出</dt><dd>Fiji / StarDist 2D Versatile　正規化 1–99.8%　確率 0.5　NMS 0.3</dd></div>
          <div><dt>背景補正</dt><dd>なし（補正前の値）</dd></div>
          <div><dt>集計</dt><dd>視野内中央値 → 試料平均 → 実験単位平均</dd></div>
        </dl>
        <fieldset className={styles.names}>
          <legend>染色名（任意）</legend>
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
    return <p className={styles.note}>核検出：{channelName(chosen)}（{EVIDENCE_LABEL[chosen.evidence]}）</p>;
  }
  return (
    <fieldset className={styles.nuclearChoice}>
      <legend>{chosen ? "核検出に使うチャンネル" : "核検出に使うチャンネルを選択"}</legend>
      <p className={styles.hint}>ファイル名から染色を判別できませんでした。核を染めた画像（DAPI・Hoechst・DRAQ など）を選んでください。</p>
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

const ISSUE_TEXT: Record<GroupingIssue["kind"], { title: string; detail: string }> = {
  channel_unidentified: {
    title: "チャンネルを判別できないファイル",
    detail: "ファイル名に染色名（DAPI、GFP など）もチャンネル番号（c1、w2 など）もないため、追加していません。名前を変えて追加し直してください。",
  },
  channels_pending: {
    title: "チャンネルを取り込み時に読み取るファイル",
    detail: "複数のチャンネルを含む OME-TIFF です。チャンネル名はファイル内の情報から読み取ります（解析APIの接続後に対応）。",
  },
  duplicate_channel: {
    title: "同じ視野・チャンネルに複数あるファイル",
    detail: "どれを使うか判断できないため、いずれも使っていません。不要なファイルを外して追加し直してください。",
  },
  duplicate_content: { title: "内容が同じファイル", detail: "同じ画像が複数回追加されています。" },
  missing_channel: { title: "チャンネルが不足している視野", detail: "不足したチャンネルの測定値は欠測として扱います。" },
};

function issueLine(issue: GroupingIssue): string {
  switch (issue.kind) {
    case "channel_unidentified":
    case "channels_pending":
      return issue.path;
    case "duplicate_channel":
      return `${issue.field} · ${issue.token}：${issue.paths.join("、")}`;
    case "duplicate_content":
      return issue.paths.join("、");
    case "missing_channel":
      return `${issue.field}（${issue.token} なし）`;
  }
}

/** What was read from the added files, and every file or field that needs attention. */
export function ImportSummary({ grouping, files }: { grouping: Grouping; files: number }) {
  const kinds = (Object.keys(ISSUE_TEXT) as GroupingIssue["kind"][])
    .map((kind) => ({ kind, items: grouping.issues.filter((issue) => issue.kind === kind) }))
    .filter((group) => group.items.length);
  const count = kinds.reduce((sum, group) => sum + group.items.length, 0);
  return (
    <section className={styles.importSummary} aria-labelledby="import-title">
      <h3 id="import-title">読み込み結果</h3>
      <p>{files} ファイル → {grouping.fields.length} 視野 · {grouping.channels.length} チャンネル</p>
      {count > 0 && <p className={styles.issueCount}>確認が必要な項目 {count} 件</p>}
      {kinds.map(({ kind, items }) => (
        <details key={kind} className={styles.issue} open={kind !== "missing_channel"}>
          <summary>{ISSUE_TEXT[kind].title}（{items.length}）</summary>
          <p>{ISSUE_TEXT[kind].detail}</p>
          <ul>
            {items.slice(0, 6).map((issue, index) => <li key={index}>{issueLine(issue)}</li>)}
            {items.length > 6 && <li>ほか {items.length - 6} 件</li>}
          </ul>
        </details>
      ))}
    </section>
  );
}
