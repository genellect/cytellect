"use client";
import RetentionNotice from "@/components/RetentionNotice";
import {useEffect, useState, type FormEvent, type ReactNode} from "react";
import Link from "next/link";
import {API_CONFIGURED, LOCAL_MODE, ApiError, errorMessage, post, request} from "@/lib/api";
import {accountApi, FIRST_RUN_KEY} from "@/lib/cloud-account";
import type {Session} from "@/lib/types";
import {CloudAccountProvider, FirstRun} from "./CloudAccount";
import styles from "./analysis-workspace.module.css";

const DESKTOP_OWNER = process.env.NEXT_PUBLIC_CYTELLECT_DESKTOP_OWNER === "true";

function firstRunDismissed() {
  try {return window.localStorage.getItem(FIRST_RUN_KEY) === "1";} catch {return false;}
}
function dismissFirstRun() {
  try {window.localStorage.setItem(FIRST_RUN_KEY, "1");} catch {}
}

/** A session gates private operations; the public example never enters this gate. */
export default function WorkspaceAccess({children}: {children: ReactNode}) {
  const [state, setState] = useState<"checking" | "login" | "ready" | "error">("checking");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  // Local mode only: the first launch of a fresh installation offers two ways to begin.
  const [firstRun, setFirstRun] = useState<boolean | null>(LOCAL_MODE ? null : false);
  const [intro, setIntro] = useState<"local" | "cloud" | null>(null);
  useEffect(() => {
    if (!API_CONFIGURED) return;
    let current = true;
    // The local build asks its own route, which answers "not yet" with 200 instead of a 401
    // that the browser would log as an error on every first visit and relaunch.
    void request<Session>(LOCAL_MODE ? "/v1/local/session" : "/v1/session").then(session => {
      if (current) setState(session.authenticated ? "ready" : "login");
    }).catch(value => {
      if (!current) return;
      if (value instanceof ApiError && value.status === 401 && DESKTOP_OWNER) {
        void post("/v1/desktop/session").then(() => {
          if (current) setState("ready");
        }).catch(failure => {
          if (current) {setError(errorMessage(failure)); setState("error");}
        });
      }
      else if (value instanceof ApiError && value.status === 401) setState("login");
      else {setError(errorMessage(value)); setState("error");}
    });
    return () => {current = false;};
  }, [attempt]);
  useEffect(() => {
    if (!LOCAL_MODE || state !== "login" || firstRun !== null) return;
    if (firstRunDismissed()) {setFirstRun(false); return;}
    let current = true;
    // An installation that already holds work (an update) opens the usual start screen.
    void accountApi.firstRun().then(value => {if (current) setFirstRun(value.first_run);}).catch(() => {if (current) setFirstRun(false);});
    return () => {current = false;};
  }, [state, firstRun]);
  async function connect(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      await post(LOCAL_MODE ? "/v1/local/session" : "/v1/invitations/redeem", LOCAL_MODE ? undefined : {token});
      setToken(""); setState("checking"); setAttempt(value => value + 1);
    } catch (value) {setError(errorMessage(value));}
    finally {setBusy(false);}
  }
  async function begin(choice: "local" | "cloud") {
    setBusy(true); setError("");
    try {
      await post("/v1/local/session");
      dismissFirstRun(); setFirstRun(false); setIntro(choice);
      setState("checking"); setAttempt(value => value + 1);
    } catch (value) {setError(errorMessage(value));}
    finally {setBusy(false);}
  }
  if (!API_CONFIGURED) return children;
  if (state === "ready") return LOCAL_MODE ? <CloudAccountProvider intro={intro}>{children}</CloudAccountProvider> : children;
  const waitingFirstRun = LOCAL_MODE && state === "login" && firstRun === null;
  return <main className={styles.shell}>
    <header className={styles.header}><Link href="/" className={styles.brand}>cytellect</Link><h1 className={styles.title}>画像解析</h1></header>
    <section className={styles.empty}>
      {state === "checking" || waitingFirstRun ? <p role="status">接続を確認しています。</p> : state === "error" ? <><p role="alert">{error}</p><button className={styles.primary} onClick={() => {setState("checking"); setAttempt(value => value + 1);}}>再接続</button></>
        : LOCAL_MODE && firstRun ? <FirstRun busy={busy} error={error} onChoose={choice => void begin(choice)}/>
        : <form onSubmit={event => void connect(event)}>
        <h2>{LOCAL_MODE ? "ワークスペース" : "ワークスペースに接続"}</h2>
        <p><RetentionNotice beforeSession/></p>
        {!LOCAL_MODE && <label>招待コード<input aria-label="招待コード" type="password" autoComplete="off" value={token} required minLength={20} onChange={event => setToken(event.target.value)}/></label>}
        <button className={styles.primary} disabled={busy}>{busy ? "接続中" : LOCAL_MODE ? "解析を開始" : "ワークスペースに接続"}</button>
        {error && <p role="alert">{error}</p>}
      </form>}
    </section>
  </main>;
}
