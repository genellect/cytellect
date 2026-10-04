"use client";
import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import Link from "next/link";
import { API_CONFIGURED, LOCAL_MODE, request, post, errorMessage, ApiError } from "@/lib/api";
import type { Session, Workspace } from "@/lib/types";
import Workbench from "./Workbench";
import GenericWorkbench from "./GenericWorkbench";
import styles from "./workspace.module.css";
import { WINDOWS_RELEASE_URL } from "@/lib/release";
import WindowsDownload from "./WindowsDownload";

import PlanAdoptionCard,{type ProposedPlan} from "./PlanAdoptionCard";
import {usePlanMemory} from "./PlanMemory";
const NavigationLink=LOCAL_MODE?"a":Link;
type Workflow="regions"|"nuclear";

function WorkspaceRouter({id,session,onBack,onError,initialWorkflow}:{id:string;session:Session;onBack:()=>void;onError:(value:string)=>void;initialWorkflow?:Workflow}){
 const [choice,setChoice]=useState<Workflow|undefined>(initialWorkflow);
 const regionFields=useQuery({queryKey:["region-fields",id],queryFn:()=>request<{id:string}[]>(`/v1/workspaces/${id}/region-fields`)});
 const legacyFields=useQuery({queryKey:["fields",id],queryFn:()=>request<{id:string}[]>(`/v1/workspaces/${id}/fields`)});
 if(regionFields.isPending||legacyFields.isPending)return <main className={styles.loading}>画像の構成を確認しています…</main>;
 if(regionFields.error||legacyFields.error)return <main className={styles.home}><p role="alert">{errorMessage(regionFields.error||legacyFields.error)}</p><button className={styles.secondary} onClick={onBack}>作業一覧へ</button></main>;
 const mode=regionFields.data?.length?"regions":legacyFields.data?.length?"nuclear":choice;
 if(!mode)return <main className={styles.home}><h1>解析の種類</h1><div className={styles.homeGrid}><button className={styles.card} onClick={()=>setChoice("regions")}><h2>領域・輝度解析</h2><p>任意の標識を1〜3チャンネル登録。核染色からの自動検出、手動領域、ラベル画像を使い、面積・輝度を測定します。</p></button><button className={styles.card} onClick={()=>setChoice("nuclear")}><h2>核・核小体解析</h2><p>核染色とNCL・GFPを使い、Fijiで自動検出して修正・定量します。</p></button></div></main>;
 const Component=mode==="regions"?GenericWorkbench:Workbench;
 return <Component id={id} session={session} onBack={onBack} onError={onError}/>;
}

function Brand(){return <div className={styles.brand}><span className={styles.brandMark} aria-hidden="true"><i/><i/><i/></span><span>cytellect</span></div>;}
export default function WorkspaceApp(){
 const [client]=useState(()=>new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0,refetchOnWindowFocus:false}}}));

 return <QueryClientProvider client={client}><Application/></QueryClientProvider>;
}
function Application(){
 const client=useQueryClient();
 const planMemory=usePlanMemory();const [proposed,setProposed]=useState<ProposedPlan|null>(null);const [planBlocked,setPlanBlocked]=useState(false);
 const [error,setError]=useState("");
 const [busy,setBusy]=useState(false);
 const [workspaceId,setWorkspaceId]=useState("");
 const [workflow,setWorkflow]=useState<Workflow>("regions");
 const [initialWorkflow,setInitialWorkflow]=useState<Workflow|undefined>();
 const [title,setTitle]=useState("");
 const [token,setToken]=useState("");
 const session=useQuery({queryKey:["session"],queryFn:()=>request<Session>("/v1/session"),enabled:API_CONFIGURED});
 const localSetup=useQuery({queryKey:["local-setup"],queryFn:()=>request<{mode:"local";ready:boolean;fiji_configured:boolean;retention_hours:number}>("/v1/local/setup"),enabled:LOCAL_MODE});
 const spaces=useQuery({queryKey:["workspaces"],queryFn:()=>request<Workspace[]>("/v1/workspaces"),enabled:!!session.data});
 const [help,setHelp]=useState(false);
 async function act(work:()=>Promise<void>){setError("");setBusy(true);try{await work();}catch(e){setError(errorMessage(e));if(e instanceof ApiError&&e.status===401){client.clear();setWorkspaceId("");}}finally{setBusy(false);}}
 function login(event:FormEvent){event.preventDefault();void act(async()=>{await post("/v1/invitations/redeem",{token});setToken("");await client.invalidateQueries({queryKey:["session"]});});}
 function createWorkspace(event:FormEvent){event.preventDefault();if(planBlocked)return;void act(async()=>{const candidate=proposed?.snapshot.decision.candidates.find(item=>item.id===proposed.candidateId);const w=await post<Workspace>("/v1/workspaces",{title,...(proposed?{plan:proposed.snapshot.input,plan_candidate_id:proposed.candidateId}:{})});await client.invalidateQueries({queryKey:["workspaces"]});setTitle("");setInitialWorkflow(candidate?.workflow||workflow);setWorkspaceId(w.id);setProposed(null);planMemory.setPending(null);});}
 if(API_CONFIGURED&&session.isPending) return <div className={styles.loading}><Brand/><p>ワークスペースを開いています…</p></div>;
 if(!session.data) return <main className={styles.loginPage}>
  <section className={styles.loginIntro}><Brand/><div><h1>画像解析</h1><p>2D蛍光画像の領域編集・測定・統計解析・図の出力</p></div><div className={styles.statusPill}>{LOCAL_MODE||WINDOWS_RELEASE_URL?"開発プレビュー · 科学的妥当性は検証中":"開発中の招待制PoC · 科学的妥当性は検証中"}</div></section>
  <section className={styles.loginForm} id={WINDOWS_RELEASE_URL?"download":undefined}><h2>{LOCAL_MODE?"ワークスペース":WINDOWS_RELEASE_URL?"Windows版のセットアップ":"ワークスペースに接続"}</h2>
   {LOCAL_MODE?<><p className={styles.muted}>画像と解析結果はローカル環境に保存されます。</p><div className={styles.localReadiness} role="status"><span>ワークスペース <b>{localSetup.isPending?"確認中":localSetup.data?.ready?"起動済み":"未接続"}</b></span><span>Fiji <b>{localSetup.isPending?"確認中":localSetup.data?.fiji_configured?"設定済み":"未設定"}</b></span></div><button className={styles.primary} disabled={busy||!localSetup.data?.ready||!localSetup.data.fiji_configured} onClick={()=>void act(async()=>{await post("/v1/local/session");await client.invalidateQueries({queryKey:["session"]});})}>解析を開始</button><details className={styles.localSetupDetails}><summary>セットアップ</summary><p>Cytellectを起動すると、このワークスペースが開きます。Fijiが未設定の場合はセットアップを完了してから起動し直してください。</p><button className={styles.linkButton} onClick={()=>void localSetup.refetch()}>状態を再確認</button></details>{localSetup.error&&<div role="alert" className={styles.error}>{errorMessage(localSetup.error)}</div>}</>:WINDOWS_RELEASE_URL?<WindowsDownload url={WINDOWS_RELEASE_URL}/>:<><p className={styles.muted}>管理者の招待コードを入力してください。</p>{!API_CONFIGURED&&<div className={styles.notice}>招待アクセスは準備中です。公開画像サンプルをお試しください。</div>}<form onSubmit={login}><label>招待コード<input aria-label="招待コード" value={token} onChange={e=>setToken(e.target.value)} type="password" autoComplete="off" minLength={20} required placeholder="招待コードを入力"/></label><button className={styles.primary} disabled={busy||!API_CONFIGURED}>ワークスペースに接続</button></form></>}
   <NavigationLink href={LOCAL_MODE?"/demo/":"/demo"} className={styles.demoLink}>公開画像サンプルを開く</NavigationLink>
   {error&&<div role="alert" className={styles.error}>{error}</div>}
   {session.error && !(session.error instanceof ApiError && session.error.status===401) && <div role="alert" className={styles.error}>{errorMessage(session.error)}</div>}
   {!WINDOWS_RELEASE_URL&&<div className={styles.privacyBox}><b>アップロード前にご確認ください</b><ul><li>{LOCAL_MODE?"画像と結果はローカル環境に保存します。":"画像と結果は非公開の解析サーバーに保存します。"}</li><li>{LOCAL_MODE?"保存期限は最終操作から24時間です。終了中に期限を迎えたデータは次回起動時に削除します。":"最後の明示的な操作から24時間でアクセスが失効し、削除されます。自動更新は期限を延長しません。"}</li><li>結果を手元に保存してから作業を終了してください。</li><li>画像・測定値を外部AIへ送信しません。</li></ul></div>}
  </section>
 </main>;
 return <div className={styles.app}>
  <header className={styles.header}><button className={styles.brandButton} onClick={()=>setWorkspaceId("")} aria-label="作業一覧"><Brand/></button><div className={styles.headerMeta}><span className={styles.statusPill}>{session.data.demo?"合成データ専用":LOCAL_MODE?"ローカルワークスペース":"非公開セッション"}</span><button className={styles.linkButton} onClick={()=>setHelp(!help)}>保存とプライバシー</button><button className={styles.linkButton} onClick={()=>void act(async()=>{await request("/v1/session",{method:"DELETE"});client.clear();setWorkspaceId("");})}>接続を終了</button></div></header>
  {help&&<div className={styles.notice}>保存期限は最終操作から24時間です。自動更新では期限を延長しません。{LOCAL_MODE?"保存先はローカル環境です。終了中に期限を迎えたデータは次回起動時に削除します。":"画像は非公開の解析サーバーに保存します。"}ZIPは原画像を既定で含みません。研究画像・結果・招待コードは公開しないでください。</div>}
  {error&&<div className={styles.error} role="alert">{error}<button onClick={()=>setError("")} aria-label="メッセージを閉じる">×</button></div>}
  {workspaceId ? <WorkspaceRouter key={workspaceId} id={workspaceId} session={session.data} initialWorkflow={initialWorkflow} onBack={()=>{setWorkspaceId("");void client.invalidateQueries({queryKey:["workspaces"]});}} onError={setError}/> :
  <main className={styles.home}><div className={styles.homeHero}><h1>実験ワークスペース</h1><p>新しい作業を作成するか、保存中の作業を選択してください。</p></div>
   <div className={styles.homeGrid}><section className={styles.card}><h2>作業の新規作成</h2><form onSubmit={createWorkspace}><label>作業名<input value={title} onChange={e=>setTitle(e.target.value)} required maxLength={100} placeholder="例：処置前後の蛍光強度"/></label><label>解析の種類<select aria-label="解析の種類" disabled={!!proposed} value={workflow} onChange={e=>setWorkflow(e.target.value as Workflow)}><option value="regions">領域・輝度解析</option><option value="nuclear">核・核小体解析</option></select></label><p className={styles.small}>{workflow==="regions"?"任意の標識・1〜3チャンネル。核染色からの自動検出、手動領域、ラベルTIFFで面積・輝度を測定します。":"核染色とNCL・GFP。Fijiによる自動検出、修正、定量と群間比較を行います。"}</p><PlanAdoptionCard onChange={(value,blocked)=>{setProposed(value);setPlanBlocked(blocked);const candidate=value?.snapshot.decision.candidates.find(item=>item.id===value.candidateId);if(candidate)setWorkflow(candidate.workflow);}}/><button className={styles.primary} disabled={busy||planBlocked}>作業を作成</button></form></section>
    <section className={styles.card}><h2>保存中の作業</h2>{!spaces.data?.length?<p className={styles.muted}>保存中の作業はありません。</p>:<div className={styles.workspaceList}>{spaces.data.map(w=><button key={w.id} onClick={()=>{setInitialWorkflow(undefined);setWorkspaceId(w.id);}}><span><b>{w.title}</b><small>有効期限 {new Date(w.expires*1000).toLocaleString("ja-JP")}</small></span><span>→</span></button>)}</div>}{spaces.error&&<p role="alert">{errorMessage(spaces.error)}</p>}</section>
   </div><p className={styles.footerNote}>開発プレビュー · 解析結果は研究目的と実験条件に照らして確認してください。</p>
  </main>}
 </div>;
}
