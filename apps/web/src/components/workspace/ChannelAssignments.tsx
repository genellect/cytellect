"use client";
import {useId,useState} from "react";
import type {ChannelAssignment} from "../../lib/workspace/api-adapter";
import type {ChannelDefinition} from "../../lib/workspace/grouping";
import {assignmentDraft,editAssignmentStain} from "../../lib/workspace/channel-assignments";
import styles from "./channel-assignments.module.css";

export function ChannelAssignments({channels,disabled,onSave}: {channels:ChannelDefinition[];disabled:boolean;onSave:(values:ChannelAssignment[])=>Promise<void>}) {
  const [values,setValues] = useState(() => assignmentDraft(channels));
  const [dirty,setDirty] = useState(false);
  const [saving,setSaving] = useState(false);
  const [error,setError] = useState("");
  const options = useId();
  const save = async () => {
    if (!dirty || saving || disabled) return;
    setSaving(true); setError("");
    try {await onSave(values);setDirty(false);} catch {setError("保存できませんでした。もう一度お試しください。");} finally {setSaving(false);}
  };
  return <form className={styles.assignments} aria-label="チャンネルと染色" onSubmit={event=>{event.preventDefault();void save();}}>
    <strong>チャンネルと染色</strong><span className={styles.scope}>全視野に適用</span>
    <datalist id={options}>{["DAPI","Hoechst","GFP","NCL","UBF","FBL"].map(stain=><option key={stain} value={stain}/>)}</datalist>
    {values.map(value=><div className={styles.row} key={value.channel_id}>
      <label><span>{value.channel_id}</span><input list={options} aria-label={`${value.channel_id} の染色`} placeholder="未指定" maxLength={80} value={value.stain || ""} disabled={disabled || saving} onChange={event=>{setValues(current=>editAssignmentStain(current,value.channel_id,event.target.value));setDirty(true);}}/></label>
      <button type="button" className={styles.nuclear} title="核検出に使う" aria-label={`${value.channel_id} を核検出に使う`} aria-pressed={value.role === "nuclear"} disabled={disabled || saving} onClick={()=>{setValues(current=>current.map(channel=>({...channel,role:channel.channel_id===value.channel_id?"nuclear":"measure"})));setDirty(true);}}>核</button>
    </div>)}
    {dirty && <button type="submit" className={styles.save} disabled={disabled || saving}>{saving?"保存中…":"保存"}</button>}
    {error && <p role="alert">{error}</p>}
  </form>;
}
