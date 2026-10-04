"use client";
import {useCallback,useEffect,useRef,useState} from "react";
import Link from "next/link";
import {errorMessage,post} from "@/lib/api";
import {parsePlan,type CandidateId,type PlanInput,type PlanSnapshot} from "@/lib/analysis-plan";
import {usePlanMemory} from "./PlanMemory";
import styles from "./workspace.module.css";
export type ProposedPlan={snapshot:PlanSnapshot;candidateId:CandidateId};
export default function PlanAdoptionCard({onChange}:{onChange:(value:ProposedPlan|null,blocked:boolean)=>void}){
 const memory=usePlanMemory();const [snapshot,setSnapshot]=useState<PlanSnapshot|null>(null);const [selected,setSelected]=useState<CandidateId|"">("");const [error,setError]=useState("");const [busy,setBusy]=useState(false);const consumed=useRef(false);const generation=useRef(0);
 const preview=useCallback(async(readInput:()=>Promise<PlanInput>,preferred:CandidateId|""="")=>{
  const version=++generation.current;setBusy(true);setError("");setSnapshot(null);setSelected("");onChange(null,true);
  let validated=false;
  try{const input=await readInput();if(generation.current!==version)return;validated=true;const value=await post<PlanSnapshot>("/v1/plans/preview",input);if(generation.current!==version)return;setSnapshot(value);const candidate=value.decision.candidates.find(item=>item.id===preferred);setSelected(candidate?.id||"");onChange(candidate?{snapshot:value,candidateId:candidate.id}:null,!candidate);}
  catch(reason){if(generation.current===version){setError(validated?errorMessage(reason):reason instanceof Error?reason.message:"計画ファイルを確認してください。");onChange(null,true);}}finally{if(generation.current===version)setBusy(false);}
 },[onChange]);
 useEffect(()=>{const pending=memory.pending;if(pending&&!consumed.current){consumed.current=true;void preview(async()=>pending.input,pending.candidateId);}},[memory.pending,preview]); // One explicit handoff; API always recomputes the guidance.
 return <section className={styles.planAdoption} aria-label="作業に引き継ぐ解析計画"><div className={styles.sectionHeader}><b>解析計画（任意）</b><Link href="/plan">解析設定を開く</Link></div><p className={styles.small}>保存した設定ファイルを読み込めます。画像の対応・背景・独立性は、実画像と実験記録で確認してください。</p>
  <label>保存した計画JSON<input aria-label="保存した計画JSON" type="file" accept=".json,application/json" disabled={busy} onChange={event=>{const file=event.target.files?.[0];if(!file)return;void preview(async()=>{if(file.size>65536)throw Error("計画JSONは64KiB以下にしてください。");return parsePlan(JSON.parse(await file.text()));});}}/></label>
  {busy&&<p role="status">計画の内容を確認しています。</p>}{error&&<p role="alert" className={styles.error}>{error}</p>}
  {snapshot&&<><label>採用する候補<select aria-label="採用する計画候補" value={selected} onChange={event=>{const id=event.target.value as CandidateId|"";setSelected(id);onChange(id?{snapshot,candidateId:id}:null,!id);}}><option value="">選択してください</option>{snapshot.decision.candidates.map(candidate=><option key={candidate.id} value={candidate.id}>{candidate.label}</option>)}</select></label>{!snapshot.decision.candidates.length&&<p className={styles.notice}>現在の条件では実行候補がありません。計画ガイドで確認事項を見直してください。</p>}
  <details><summary>確認事項と出典</summary>{[...snapshot.decision.questions,...snapshot.decision.limits].map(finding=><p className={styles.small} key={finding.id}><b>{finding.title}</b> {finding.detail}</p>)}{snapshot.decision.references.map(reference=><p className={styles.small} key={reference.id}><a href={reference.url} target="_blank" rel="noreferrer">{reference.label} ↗</a></p>)}</details></>}
  {(snapshot||error||busy)&&<button type="button" className={styles.linkButton} onClick={()=>{generation.current++;setSnapshot(null);setSelected("");setError("");setBusy(false);memory.setPending(null);onChange(null,false);}}>計画を使わずに作業を作成する</button>}
 </section>;
}
