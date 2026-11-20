"use client";
import {createContext, useCallback, useContext, useEffect, useState, useSyncExternalStore, type ReactNode} from "react";
import {request} from "@/lib/api";
import type {components} from "@/lib/generated";
import {AI_SCOPE, DISCUSSION_SCOPE, includePreviews, setIncludePreviews, subscribeAiSettings} from "@/lib/workspace/ai-settings";
import styles from "./ai-settings.module.css";

type Status = components["schemas"]["AiStatus"];
type Access = {available:boolean; checking:boolean; status:Status|null; failed:boolean; demo:boolean;
  accountState?:string; refresh:()=>void; login?:()=>void};
const Context=createContext<Access|null>(null);
const waiting:Access={available:false,checking:true,status:null,failed:false,demo:false,refresh:()=>{}};
export const useAi=()=>useContext(Context)??waiting;

export function AiProvider({children,demo,accountState,onLogin,onRefresh}:{children:ReactNode;demo:boolean;
  accountState?:string;onLogin?:()=>void;onRefresh?:()=>Promise<void>}){
  const [status,setStatus]=useState<Status|null>(null),[failed,setFailed]=useState(false),[checking,setChecking]=useState(!demo);
  const [revision,setRevision]=useState(0);
  const refresh=useCallback(()=>{void onRefresh?.();setRevision(value=>value+1);},[onRefresh]);
  useEffect(()=>{
    if(demo)return;
    let live=true;setChecking(true);setFailed(false);
    request<Status>("/v1/ai/status").then(value=>{if(live)setStatus(value);}).catch(()=>{if(live){setStatus(null);setFailed(true);}})
      .finally(()=>{if(live)setChecking(false);});
    return()=>{live=false;};
  },[demo,accountState,revision]);
  const accountBlocked=status?.source==="account"&&!!accountState&&accountState!=="allowed";
  return <Context.Provider value={{available:demo||(!checking&&status?.state==="available"&&!accountBlocked),
    checking:checking||(status?.source==="account"&&accountState==="checking"),status,failed,demo,accountState,refresh,login:onLogin}}>{children}</Context.Provider>;
}

export function aiStatusText(access:Pick<Access,"checking"|"failed"|"status"|"accountState">):string{
  if(access.checking)return "AI の利用状態を確認中…";
  if(access.failed||access.status?.source==="account"&&access.accountState==="offline")return "AI の利用状態を確認できません。接続状態を確認してください。";
  if(access.status?.source==="account"){
    if(access.accountState==="pending_approval")return "AI の利用は承認待ちです。承認後にログインしてください。";
    if(access.accountState==="revoked")return "AI の利用が停止されています。オーナーにお問い合わせください。";
    if(access.status.state==="sign_in_required"||access.accountState&&access.accountState!=="allowed")return "AI の利用にはログインが必要です。";
  }
  if(access.status?.state==="misconfigured")return "AI のサービス設定に問題があります。管理者が接続先と端末の認証情報を確認してください。";
  if(access.status?.state==="unconfigured")return "AI は未設定です。「AI の設定」で有効にする方法を確認できます。";
  return "解析提案・考察：設定済み";
}

export function AiAvailabilityHint({onSettings}:{onSettings?:()=>void}={}){
  const access=useAi();
  if(access.demo||access.available)return null;
  const login=access.status?.source==="account"&&!access.checking&&access.accountState!=="revoked";
  return <span className={styles.hint} role="status">{aiStatusText(access)}
    {login&&access.login?<button type="button" onClick={access.login}>ログイン</button>:
      access.failed?<button type="button" onClick={access.refresh}>接続を確認</button>:
        onSettings&&!access.checking?<button type="button" onClick={onSettings}>AI の設定</button>:null}</span>;
}

export function AiSettings(){
  const access=useAi(),previews=useSyncExternalStore(subscribeAiSettings,includePreviews,()=>true);
  return <details className={styles.settings}><summary>AI の設定</summary>
    {access.demo?<p>このデモは、用意した解析案と考察のサンプルを表示します。</p>:<>
      {access.available?<p>{aiStatusText(access)}</p>:<AiAvailabilityHint/>}
      {access.status?.source!=="account"&&access.status?.state!=="available"&&<p>
        Docker・開発環境では、管理者が提案サービスの接続先と端末の認証情報を設定します。
        <a href="https://github.com/genellect/cytellect/blob/main/docs/proposal-service.md" target="_blank" rel="noreferrer">設定方法</a>
      </p>}
      <button type="button" onClick={access.refresh}>利用状態を確認</button>
      <p>{AI_SCOPE}</p><p>{DISCUSSION_SCOPE}</p>
      <label><input type="checkbox" checked={previews} onChange={event=>setIncludePreviews(event.target.checked)}/>
        AI への相談で代表視野の縮小画像も送る（チャンネルごと、512 px 以下）</label>
    </>}
  </details>;
}
