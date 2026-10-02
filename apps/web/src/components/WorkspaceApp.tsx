"use client";
import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import Link from "next/link";
import { API, request, post, errorMessage, ApiError } from "@/lib/api";
import type { Session, Workspace } from "@/lib/types";
import Workbench from "./Workbench";
import styles from "./workspace.module.css";

function Brand(){return <div className={styles.brand}><span className={styles.brandMark} aria-hidden="true"><i/><i/><i/></span><span>cytellect<span className={styles.brandSub}>IMAGE → INSIGHT</span></span></div>;}
export default function WorkspaceApp(){
 const [client]=useState(()=>new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0,refetchOnWindowFocus:false}}}));
 return <QueryClientProvider client={client}><Application/></QueryClientProvider>;
}
function Application(){
 const client=useQueryClient();
 const [error,setError]=useState("");
 const [busy,setBusy]=useState(false);
 const [workspaceId,setWorkspaceId]=useState("");
 const [title,setTitle]=useState("");
 const [token,setToken]=useState("");
 const session=useQuery({queryKey:["session"],queryFn:()=>request<Session>("/v1/session"),enabled:!!API});
 const spaces=useQuery({queryKey:["workspaces"],queryFn:()=>request<Workspace[]>("/v1/workspaces"),enabled:!!session.data});
 const [help,setHelp]=useState(false);
 async function act(work:()=>Promise<void>){setError("");setBusy(true);try{await work();}catch(e){setError(errorMessage(e));if(e instanceof ApiError&&e.status===401){client.clear();setWorkspaceId("");}}finally{setBusy(false);}}
 function login(event:FormEvent){event.preventDefault();void act(async()=>{await post("/v1/invitations/redeem",{token});setToken("");await client.invalidateQueries({queryKey:["session"]});});}
 if(API&&session.isPending) return <div className={styles.loading}><Brand/><p>非公開ワークスペースに接続しています…</p></div>;
 if(!session.data) return <main className={styles.loginPage}>
  <section className={styles.loginIntro}><Brand/><div><span className={styles.eyebrow}>IMMUNOFLUORESCENCE ANALYSIS</span><h1>核から、<br/>定量へ。</h1><p>核・核小体の検出と修正、GFP・NCLの定量、<br/>統計と図表をひとつの作業空間で。</p><div className={styles.workflowPreview}><span>01 画像</span><b>→</b><span>02 領域</span><b>→</b><span>03 定量</span><b>→</b><span>04 図表</span></div></div><div className={styles.statusPill}>開発中の招待制PoC · 科学的妥当性は検証中</div></section>
  <section className={styles.loginForm}><span className={styles.eyebrow}>PRIVATE WORKSPACE</span><h2>ワークスペースに接続</h2><p className={styles.muted}>管理者の招待コードを入力してください。</p>
   {!API&&<div className={styles.notice}>招待アクセスは準備中です。公開画像サンプルをお試しください。</div>}
   <form onSubmit={login}><label>招待コード<input aria-label="招待コード" value={token} onChange={e=>setToken(e.target.value)} type="password" autoComplete="off" minLength={20} required placeholder="招待コードを入力"/></label><button className={styles.primary} disabled={busy||!API}>ワークスペースに接続 <span>↗</span></button></form>
   <Link href="/demo" className={styles.demoLink}>サンプルを試す <span>→</span></Link>
   {error&&<div role="alert" className={styles.error}>{error}</div>}
   {session.error && !(session.error instanceof ApiError && session.error.status===401) && <div role="alert" className={styles.error}>{errorMessage(session.error)}</div>}
   <div className={styles.privacyBox}><b>アップロード前にご確認ください</b><ul><li>画像と結果は非公開の解析サーバーに保存します。</li><li>最後の明示的な操作から24時間でアクセスが失効し、削除されます。自動更新は期限を延長しません。</li><li>結果を手元に保存してから作業を終了してください。</li><li>画像・測定値を外部AIへ送信しません。</li></ul></div>
  </section>
 </main>;
 return <div className={styles.app}>
  <header className={styles.header}><button className={styles.brandButton} onClick={()=>setWorkspaceId("")} aria-label="作業一覧"><Brand/></button><div className={styles.headerMeta}><span className={styles.statusPill}>{session.data.demo?"合成データ専用":"非公開セッション"}</span><button className={styles.linkButton} onClick={()=>setHelp(!help)}>保存とプライバシー</button><button className={styles.linkButton} onClick={()=>void act(async()=>{await request("/v1/session",{method:"DELETE"});client.clear();setWorkspaceId("");})}>接続を終了</button></div></header>
  {help&&<div className={styles.notice}>最後の明示的な操作から24時間で作業が失効します。ポーリングでは延長されません。アップロード先は非公開APIです。ZIPは原画像を既定で含みません。研究画像・結果・招待コードを公開Issueへ添付しないでください。</div>}
  {error&&<div className={styles.error} role="alert">{error}<button onClick={()=>setError("")} aria-label="メッセージを閉じる">×</button></div>}
  {workspaceId ? <Workbench key={workspaceId} id={workspaceId} session={session.data} onBack={()=>{setWorkspaceId("");void client.invalidateQueries({queryKey:["workspaces"]});}} onError={setError}/> :
  <main className={styles.home}><div className={styles.homeHero}><span className={styles.eyebrow}>YOUR RESEARCH DESK</span><h1>実験ワークスペース</h1><p>実験ごとに画像と解析条件をまとめ、修正の履歴から図表まで追跡します。</p></div>
   <div className={styles.homeGrid}><section className={styles.card}><div className={styles.sectionNumber}>01 / NEW EXPERIMENT</div><h2>新しい作業</h2><form onSubmit={e=>{e.preventDefault();void act(async()=>{const w=await post<Workspace>("/v1/workspaces",{title});await client.invalidateQueries({queryKey:["workspaces"]});setTitle("");setWorkspaceId(w.id);});}}><label>作業名<input value={title} onChange={e=>setTitle(e.target.value)} required maxLength={100} placeholder="例：NCL分布の比較"/></label><button className={styles.primary} disabled={busy}>作業を作成 <span>＋</span></button></form><p className={styles.small}>画像を使わずに試す場合は、作業内で合成データを生成できます。</p></section>
    <section className={styles.card}><div className={styles.sectionNumber}>02 / RECENT WORK</div><h2>保存中の作業</h2>{!spaces.data?.length?<p className={styles.muted}>作業はまだありません。新しく作成してはじめましょう。</p>:<div className={styles.workspaceList}>{spaces.data.map(w=><button key={w.id} onClick={()=>setWorkspaceId(w.id)}><span><b>{w.title}</b><small>有効期限 {new Date(w.expires*1000).toLocaleString("ja-JP")}</small></span><span>→</span></button>)}</div>}{spaces.error&&<p role="alert">{errorMessage(spaces.error)}</p>}</section>
   </div><p className={styles.footerNote}>Cytellect / Development preview · 実画像による検証・研究者評価は別途実施します。</p>
  </main>}
 </div>;
}
