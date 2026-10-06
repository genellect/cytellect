"use client";
import {useEffect, useState, type FormEvent, type ReactNode} from "react";
import Link from "next/link";
import {API_CONFIGURED, LOCAL_MODE, ApiError, errorMessage, post, request} from "@/lib/api";
import type {Session} from "@/lib/types";
import styles from "./analysis-workspace.module.css";

/** A session gates private operations; the public example never enters this gate. */
export default function WorkspaceAccess({children}: {children: ReactNode}) {
  const [state, setState] = useState<"checking" | "login" | "ready" | "error">("checking");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!API_CONFIGURED) return;
    let current = true;
    void request<Session>("/v1/session").then(session => {
      if (current) setState(session.authenticated ? "ready" : "login");
    }).catch(value => {
      if (!current) return;
      if (value instanceof ApiError && value.status === 401) setState("login");
      else {setError(errorMessage(value)); setState("error");}
    });
    return () => {current = false;};
  }, [attempt]);
  async function connect(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      await post(LOCAL_MODE ? "/v1/local/session" : "/v1/invitations/redeem", LOCAL_MODE ? undefined : {token});
      setToken(""); setState("checking"); setAttempt(value => value + 1);
    } catch (value) {setError(errorMessage(value));}
    finally {setBusy(false);}
  }
  if (!API_CONFIGURED || state === "ready") return children;
  return <main className={styles.shell}>
    <header className={styles.header}><Link href="/product" className={styles.brand}>cytellect</Link><h1 className={styles.title}>画像解析</h1></header>
    <section className={styles.empty}>
      {state === "checking" ? <p role="status">接続を確認しています。</p> : state === "error" ? <><p role="alert">{error}</p><button className={styles.primary} onClick={() => {setState("checking"); setAttempt(value => value + 1);}}>再接続</button></> : <form onSubmit={event => void connect(event)}>
        <h2>{LOCAL_MODE ? "ワークスペース" : "ワークスペースに接続"}</h2>
        <p>画像と結果の保存期限は最終操作から24時間です。</p>
        {!LOCAL_MODE && <label>招待コード<input aria-label="招待コード" type="password" autoComplete="off" value={token} required minLength={20} onChange={event => setToken(event.target.value)}/></label>}
        <button className={styles.primary} disabled={busy}>{busy ? "接続中" : LOCAL_MODE ? "解析を開始" : "ワークスペースに接続"}</button>
        {error && <p role="alert">{error}</p>}
      </form>}
    </section>
  </main>;
}
