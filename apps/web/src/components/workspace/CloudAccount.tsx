"use client";
/**
 * Cloud features of a local installation: sign-in, the pending-approval banner, GPU start-up
 * and the update notice. Rendered only inside CloudAccountProvider (local mode); elsewhere
 * every component here renders nothing, so the hosted workspace and the demo are unchanged.
 */
import {createContext, useCallback, useContext, useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent as ReactKeyboardEvent, type ReactNode} from "react";
import {
  AccountRequestError, accountApi, accountErrorText, accountLabel, gpuQuotaReached, gpuQuotaText, accountNotice, errorDetail, formatDate, gpuNotice, inferencePhase,
  followUpdate, normalizeEmail, pendingNotice, plausibleCode, plausibleEmail, resendWait, safeNotesUrl, updateNotice, usageText,
  UPDATE_IN_PROGRESS, UPDATE_JOBS_RUNNING, UPDATE_JOBS_RUNNING_TEXT, UPDATE_NOT_AVAILABLE, UPDATE_REMEMBERED, UPDATE_SEEN_KEY, UPDATE_SETTLED,
  UPDATE_TIMEOUT_TEXT, UPDATE_UNSUPPORTED, updateSignature,
  GPU_POLL_MS, GPU_TIME_NOTE, PENDING_POLL_MS, type Account, type GpuState, type Notice, type UpdateInfo,
} from "@/lib/cloud-account";
import styles from "./cloud-account.module.css";

export const PRACTICE_IMAGES_URL = "https://github.com/genellect/cytellect/releases/download/v0.1.0-local.11/Cytellect-BBBC013-practice-v1.zip";

type Intro = "local" | "cloud" | null;
type CloudContext = {
  account: Account | null; checking: boolean; setAccount: (value: Account) => void; refresh: () => Promise<void>;
  /** When 「コードを再送」 becomes available (epoch ms), kept across reopening the dialog. */
  resendAt: number;
  loginOpen: boolean; openLogin: () => void; closeLogin: () => void;
  gpu: GpuState | null; startGpu: () => void; warmUpOnce: () => void; intro: Intro; dismissIntro: () => void;
};
const Context = createContext<CloudContext | null>(null);
export const useCloudAccount = () => useContext(Context);

export function CloudAccountProvider({children, intro: initialIntro = null}: {children: ReactNode; intro?: Intro}) {
  const [account, setAccountState] = useState<Account | null>(null);
  const [checking, setChecking] = useState(true);
  const [resendAt, setResendAt] = useState(0);
  const [loginOpen, setLoginOpen] = useState(initialIntro === "cloud");
  const [gpu, setGpu] = useState<GpuState | null>(null);
  const [intro, setIntro] = useState<Intro>(initialIntro);
  const warmed = useRef(false);
  const opener = useRef<HTMLElement | null>(null);
  const setAccount = useCallback((value: Account) => {
    setAccountState(value);
    if (value.state === "code_sent" && typeof value.retry_after_seconds === "number") setResendAt(Date.now() + value.retry_after_seconds * 1000);
  }, []);
  const refresh = useCallback(async () => {
    // A failed check leaves the last state; local analysis never waits on the cloud.
    try {setAccount(await accountApi.get());} catch {}
    finally {setChecking(false);}
  }, [setAccount]);
  const startGpu = useCallback(() => {warmed.current = true; void accountApi.startGpu().then(setGpu).catch(() => {});}, []);
  // The cloud counts the start-up wait as GPU time: start it by itself once per session,
  // afterwards only when the researcher asks (「もう一度試す」) or a detection runs.
  const warmUpOnce = useCallback(() => {if (!warmed.current) startGpu();}, [startGpu]);
  useEffect(() => {void refresh();}, [refresh]);
  const waiting = account?.state === "pending_approval" && !account.approved;
  useEffect(() => {
    if (!waiting) return;
    const timer = setInterval(() => void refresh(), PENDING_POLL_MS);
    return () => clearInterval(timer);
  }, [waiting, refresh]);
  useEffect(() => {
    if (gpu?.state !== "starting") return;
    const timer = setInterval(() => {void accountApi.gpu().then(setGpu).catch(() => {});}, GPU_POLL_MS);
    return () => clearInterval(timer);
  }, [gpu?.state]);
  // The GPU check learns of an ended login before the account view does.
  useEffect(() => {if (gpu?.state === "auth_required" || gpu?.state === "revoked") void refresh();}, [gpu?.state, refresh]);
  // After signing in, a Cellpose choice that waited for the login starts the GPU.
  const allowed = account?.state === "allowed";
  const gpuState = gpu?.state;
  useEffect(() => {if (allowed && (gpuState === "unconfigured" || gpuState === "auth_required")) startGpu();}, [allowed, gpuState, startGpu]);
  const value: CloudContext = {
    account, checking, setAccount, refresh, resendAt, loginOpen,
    openLogin: () => {opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null; setLoginOpen(true);},
    // Focus returns to the control that opened the dialog.
    closeLogin: () => {setLoginOpen(false); const target = opener.current; opener.current = null; setTimeout(() => target?.focus(), 0);},
    gpu, startGpu, warmUpOnce, intro, dismissIntro: () => setIntro(null),
  };
  return <Context.Provider value={value}>{children}{loginOpen && <LoginDialog/>}</Context.Provider>;
}

function Details({error}: {error: unknown}) {
  const code = errorDetail(error);
  return code ? <details className={styles.details}><summary>詳細</summary><code>{code}</code></details> : null;
}

function NoticeLine({notice, onAction, onClose, closeLabel}: {notice: Notice; onAction?: () => void; onClose?: () => void; closeLabel?: string}) {
  return <div className={styles.notice} data-tone={notice.tone} role={notice.tone === "problem" ? "alert" : "status"}>
    <p>{notice.text}</p>
    {notice.action && onAction && <button className={notice.tone === "ready" ? styles.primary : styles.secondary} onClick={onAction}>{notice.action.label}</button>}
    {onClose && <button className={styles.quiet} onClick={onClose}>{closeLabel || "閉じる"}</button>}
  </div>;
}

/** The header's account control: 「ログイン」, or the address with what is available. */
export function AccountIndicator() {
  const cloud = useCloudAccount();
  const [logoutError, setLogoutError] = useState<unknown>(null);
  if (!cloud) return null;
  // The first check can wait for the network; do not offer a sign-in that may already exist.
  if (cloud.checking && !cloud.account) return <button className={styles.accountButton} disabled><span>確認しています</span></button>;
  const {label, detail} = accountLabel(cloud.account);
  const account = cloud.account;
  if (account?.state === "allowed" || account?.state === "offline") {
    const usage = usageText(account);
    const resets = formatDate(account.resets_at);
    async function logout() {
      setLogoutError(null);
      try {cloud?.setAccount(await accountApi.logout());} catch (error) {setLogoutError(error);}
    }
    return <details className={styles.account} data-dismissible>
      <summary><span>{label}</span>{detail && <small>{detail}</small>}</summary>
      <div className={styles.accountPanel}>
        <p className={styles.accountEmail}>{account.email}</p>
        <p>{account.state === "allowed" ? "GPU による検出と解析提案が使えます。" : "クラウドに接続できません。ネットワークを確認してください。このPCでの解析は使えます。"}</p>
        {gpuQuotaReached(account) && <p role="status">{gpuQuotaText(account)}</p>}
        {usage && <p className={styles.small}>今月の利用：{usage}{resets ? `（${resets}にリセット）` : ""}</p>}
        <p className={styles.small}>{GPU_TIME_NOTE}</p>
        <button className={styles.secondary} onClick={() => void logout()}>ログアウト</button>
        {logoutError !== null && <div role="alert" className={styles.error}><p>ログアウトできませんでした。{accountErrorText(logoutError)}</p><Details error={logoutError}/></div>}
      </div>
    </details>;
  }
  return <button className={styles.accountButton} data-state={account?.state || "signed_out"} onClick={cloud.openLogin}>
    <span>{label}</span>{detail && <small>{detail}</small>}
  </button>;
}

/** Banners above the work area: approval, ended access, update, the practice images. */
export function CloudNotices() {
  const cloud = useCloudAccount();
  const [collapsed, setCollapsed] = useState(false);
  const [continueError, setContinueError] = useState<unknown>(null);
  if (!cloud) return null;
  const pending = pendingNotice(cloud.account);
  const ended = accountNotice(cloud.account);
  async function continueLogin() {
    const email = cloud?.account?.email;
    if (!cloud || !email) return;
    setContinueError(null);
    try {cloud.setAccount(await accountApi.sendCode(email)); cloud.openLogin();}
    catch (error) {setContinueError(error);}
  }
  return <div className={styles.notices}>
    {/* The request stays visible at the top; it can be folded to one line, not dismissed. */}
    {pending && (pending.action || !collapsed) && <NoticeLine notice={pending} onAction={() => void continueLogin()}
      onClose={pending.action ? undefined : () => setCollapsed(true)} closeLabel="ローカルの解析を続ける"/>}
    {pending && !pending.action && collapsed && <div className={styles.notice} data-tone="info" role="status">
      <p>承認待ち。このPCでの解析は使えます。</p>
      <button className={styles.quiet} onClick={() => setCollapsed(false)}>詳しく</button>
    </div>}
    {continueError !== null && <div className={styles.notice} data-tone="problem" role="alert">
      <p>{accountErrorText(continueError)}</p><Details error={continueError}/>
    </div>}
    {ended && <NoticeLine notice={ended} onAction={cloud.openLogin}/>}
    <UpdateBanner/>
    {cloud.intro === "local" && <div className={styles.notice} data-tone="info" role="status">
      <p>公開の練習画像（BBBC013）で、核の検出から図までを試せます。ZIP を展開し、画像をこの画面にドラッグしてください。</p>
      <a className={styles.secondary} href={PRACTICE_IMAGES_URL} rel="noreferrer">練習画像をダウンロード</a>
      <button className={styles.quiet} onClick={cloud.dismissIntro}>閉じる</button>
    </div>}
  </div>;
}

/**
 * 「更新があります」 and the state of an update (#155's /v1/app/update). After 「更新する」 the
 * banner re-reads the state every 3 s until it settles (at most 20 min); a settled state that
 * the installer keeps (updated, installed, failed, rolled_back) is shown once.
 */
function UpdateBanner() {
  const [update, setUpdate] = useState<UpdateInfo | null>(null);
  const [following, setFollowing] = useState(false);
  const [timedOut, setTimedOut] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [hidden, setHidden] = useState(false);
  const [waitsForJobs, setWaitsForJobs] = useState(false);
  const run = useRef<AbortController | null>(null);
  const busy = useRef(false);
  // A settled state the installer keeps is remembered once it has been shown, wherever it came from.
  const show = useCallback((value: UpdateInfo | null) => {
    if (value && UPDATE_REMEMBERED.has(value.state ?? "")) {
      try {window.localStorage.setItem(UPDATE_SEEN_KEY, updateSignature(value));} catch {}
    }
    setUpdate(value);
  }, []);
  const live = useRef(true);
  const follow = useCallback(async () => {
    run.current?.abort();
    const controller = new AbortController();
    run.current = controller;
    setFollowing(true);
    const result = await followUpdate(accountApi.update, {signal: controller.signal});
    if (result === "cancelled" || run.current !== controller || !live.current) return;
    setFollowing(false);
    if (result === "timeout") setTimedOut(true); else show(result);
  }, [show]);
  useEffect(() => {
    live.current = true;
    void accountApi.update().then(value => {
      if (!live.current || !value) return;
      if (UPDATE_REMEMBERED.has(value.state ?? "")) {
        const signature = updateSignature(value);
        let seen = false;
        try {seen = window.localStorage.getItem(UPDATE_SEEN_KEY) === signature;} catch {}
        if (seen) {setUpdate({...value, state: "idle", error: null}); return;}
      }
      show(value);
      // An update already under way (the page was reopened): keep following it.
      if (value.state && !UPDATE_SETTLED.has(value.state)) void follow();
    }).catch(() => {});
    return () => {live.current = false; run.current?.abort();};
  }, [follow, show]);
  async function applyUpdate() {
    if (busy.current) return; // A second press while one is being sent does nothing.
    busy.current = true;
    setFollowing(true); setTimedOut(false); setError(null); setHidden(false); setWaitsForJobs(false);
    try {
      const started = await accountApi.applyUpdate();
      if (!live.current) return;
      if (started) show(started);
      if (started && UPDATE_SETTLED.has(started.state ?? "") && started.state !== "idle") setFollowing(false);
      else await follow();
    } catch (failure) {
      if (!live.current) return;
      const code = failure instanceof AccountRequestError ? failure.code : "";
      if (code === UPDATE_IN_PROGRESS) {await follow(); return;} // Started from another tab: follow that one.
      setFollowing(false);
      if (code === UPDATE_JOBS_RUNNING) setWaitsForJobs(true); // Not a failure; the button stays available.
      else if (code === UPDATE_NOT_AVAILABLE) {try {const current = await accountApi.update(); if (live.current) show(current);} catch {}}
      else if (code === UPDATE_UNSUPPORTED) setHidden(true);
      else {setError(failure); setUpdate(current => current ? {...current, state: "failed"} : current);}
    } finally {busy.current = false;}
  }
  const offered = updateNotice(update, following);
  const line = timedOut ? {text: UPDATE_TIMEOUT_TEXT, tone: "problem" as const}
    : waitsForJobs && offered ? {...offered, text: `${UPDATE_JOBS_RUNNING_TEXT}${offered.text}`} : offered;
  if (!line || hidden) return null;
  const notesUrl = safeNotesUrl(update?.notes_url);
  const detail = "error" in line && line.error ? line.error : errorDetail(error);
  return <div className={styles.notice} data-tone={line.tone} role={line.tone === "problem" ? "alert" : "status"}>
    <p>{line.text}</p>
    {notesUrl && line.tone === "info" && <a className={styles.quiet} href={notesUrl} target="_blank" rel="noreferrer">変更内容</a>}
    {"action" in line && line.action && !following && <button className={styles.primary} onClick={() => void applyUpdate()}>{line.action.label}</button>}
    {detail && <details className={styles.details}><summary>詳細</summary><code>{detail}</code></details>}
    {(line.tone === "problem" || line.tone === "ready") && <button className={styles.quiet} onClick={() => setHidden(true)}>閉じる</button>}
  </div>;
}

/** Starts the GPU when a Cellpose detector is chosen and shows its state beside the settings. */
export function GpuStatus() {
  const cloud = useCloudAccount();
  const warmUpOnce = cloud?.warmUpOnce;
  useEffect(() => {warmUpOnce?.();}, [warmUpOnce]);
  if (!cloud) return null;
  const notice = gpuNotice(cloud.gpu);
  if (!notice || notice.tone === "ready") return null;
  return <div className={styles.inspectorNotice}><NoticeLine notice={notice} onAction={notice.action?.kind === "login" ? cloud.openLogin : cloud.startGpu}/></div>;
}

/** 「GPU を起動しています」→「検出しています」 while a Cellpose detection runs. */
export function CloudPhase({running}: {running: boolean}) {
  const cloud = useCloudAccount();
  if (!cloud || !cloud.gpu || cloud.gpu.state === "unconfigured" || cloud.gpu.state === "idle") return null;
  const phase = inferencePhase(cloud.gpu, running);
  return phase ? <span className={styles.phase} role="status">{phase}</span> : null;
}

type Step = "email" | "code" | "pending" | "revoked" | "done";
function initialStep(account: Account | null): Step {
  if (account?.state === "code_sent") return "code";
  if (account?.state === "pending_approval" && !account.approved) return "pending";
  if (account?.state === "allowed") return "done";
  return "email";
}

const FOCUSABLE = "input:not([disabled]), button:not([disabled]), a[href], summary, [tabindex]:not([tabindex='-1'])";

function LoginDialog() {
  const cloud = useCloudAccount()!;
  const title = useId();
  const [step, setStep] = useState<Step>(() => initialStep(cloud.account));
  const [email, setEmail] = useState(cloud.account?.email || "");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [now, setNow] = useState(() => Date.now());
  const first = useRef<HTMLInputElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const dialog = useRef<HTMLElement>(null);
  // Each step moves focus to its field, or to the heading when it has none.
  useEffect(() => {(first.current ?? heading.current)?.focus();}, [step]);
  function trapFocus(event: ReactKeyboardEvent<HTMLElement>) {
    if (event.key !== "Tab" || !dialog.current) return;
    const items = [...dialog.current.querySelectorAll<HTMLElement>(FOCUSABLE)];
    if (!items.length) return;
    const [start, end] = [items[0], items[items.length - 1]];
    if (event.shiftKey && (document.activeElement === start || document.activeElement === heading.current)) {event.preventDefault(); end.focus();}
    else if (!event.shiftKey && document.activeElement === end) {event.preventDefault(); start.focus();}
  }
  useEffect(() => {
    if (step !== "code") return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [step]);
  useEffect(() => {
    const escape = (event: KeyboardEvent) => {if (event.key === "Escape") cloud.closeLogin();};
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [cloud]);
  async function requestCode(address: string) {
    setBusy(true); setError(null);
    try {
      const result = await accountApi.sendCode(address);
      cloud.setAccount(result);
      setEmail(result.email || address);
      if (result.state === "code_sent") {setNow(Date.now()); setCode(""); setStep("code");}
      else if (result.state === "pending_approval") setStep("pending");
      else if (result.state === "revoked") setStep("revoked");
    } catch (value) {setError(value);}
    finally {setBusy(false);}
  }
  function submitEmail(event: FormEvent) {
    event.preventDefault();
    if (!plausibleEmail(email)) {setError(new Error("format")); return;}
    void requestCode(normalizeEmail(email));
  }
  async function submitCode(event: FormEvent) {
    event.preventDefault();
    if (!plausibleCode(code)) return;
    setBusy(true); setError(null);
    try {
      const result = await accountApi.verify(code.trim());
      cloud.setAccount(result);
      // The owner may have revoked or not yet approved the address since the code was sent.
      if (result.state === "revoked") setStep("revoked");
      else if (result.state === "pending_approval") setStep("pending");
      else {await cloud.refresh(); setStep("done");}
    }
    catch (value) {setError(value);}
    finally {setBusy(false);}
  }
  const wait = resendWait(cloud.resendAt, now);
  // No attempts left on this code (also after reopening): offer only a new code.
  const exhausted = (cloud.account?.state === "code_sent" && cloud.account.attempts_left === 0)
    || (error instanceof AccountRequestError && (error.code === "account_code_attempts_exhausted"
      || (error.code === "account_code_invalid" && error.attemptsLeft === 0)));
  const approved = step === "pending" && cloud.account?.state === "pending_approval" && !!cloud.account.approved;
  const invalidEmail = error instanceof Error && error.message === "format";
  return <div className={styles.backdrop} onMouseDown={event => {if (event.target === event.currentTarget) cloud.closeLogin();}}>
    <section ref={dialog} className={styles.dialog} role="dialog" aria-modal="true" aria-labelledby={title} onKeyDown={trapFocus}>
      <h2 id={title} ref={heading} tabIndex={-1}>{step === "done" ? "クラウド機能が使えます" : approved ? "承認されました" : step === "pending" ? "承認を待っています" : step === "revoked" ? "利用が停止されています" : "クラウド機能を有効にする"}</h2>
      {step === "email" && <form onSubmit={submitEmail} noValidate>
        <p>オーナーが許可したメールアドレスに、6 桁のコードを送ります。パスワードは使いません。</p>
        <label>メールアドレス<input ref={first} type="email" autoComplete="email" inputMode="email" value={email}
          onChange={event => setEmail(event.target.value)} required maxLength={254} placeholder="name@example.ac.jp"/></label>
        <p className={styles.small}>ログインすると、核小体・細胞の検出（Cellpose）では、検出に使う 1 チャンネルの画像（核小体では核の輪郭も）をクラウドの GPU に送ります。解析提案には画像を送りません。ほかの解析はこれまでどおりこのPCだけで行います。</p>
        <button className={styles.primary} disabled={busy || !email.trim()}>{busy ? "送信しています" : "コードを送る"}</button>
      </form>}
      {step === "code" && <form onSubmit={event => void submitCode(event)}>
        <p role="status">{email} にコードを送りました。</p>
        {exhausted ? <p>このコードで入力できる回数を使い切りました。「コードを再送」を押して、新しいコードを受け取ってください。</p> : <>
        <label>6 桁のコード<input ref={first} value={code} onChange={event => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
          inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required/></label>
        <button className={styles.primary} disabled={busy || !plausibleCode(code)}>{busy ? "確認しています" : "ログイン"}</button>
        </>}
        <p className={styles.small}>届かない場合は、迷惑メールのフォルダーを確認してください。コードの有効期限は 10 分です。</p>
        <div className={styles.row}>
          <button type="button" className={styles.secondary} disabled={busy || wait > 0} onClick={() => void requestCode(email)}>{wait > 0 ? `コードを再送（${wait} 秒後）` : "コードを再送"}</button>
          <button type="button" className={styles.quiet} disabled={busy} onClick={() => {setError(null); setCode(""); setStep("email");}}>メールアドレスを修正</button>
        </div>
      </form>}
      {step === "pending" && (approved ? <>
        <p>{email} の利用が承認されました。ログインを続けると、6 桁のコードをメールで送ります。</p>
        <button className={styles.primary} disabled={busy} onClick={() => void requestCode(email)}>ログインを続ける</button>
      </> : <>
        <p>オーナーに利用を申請しました（{email}）。承認されるとメールでお知らせします。それまでも、このPCでの解析は使えます。</p>
        <button className={styles.quiet} onClick={() => {setError(null); setStep("email");}}>メールアドレスを修正</button>
      </>)}
      {step === "revoked" && <p>このメールアドレスのクラウド機能は停止されています。オーナーにお問い合わせください。このPCでの解析は続けて使えます。</p>}
      {step === "done" && <>
        <p>{cloud.account?.email || email} でログインしました。GPU による検出と解析提案が使えます。</p>
        {cloud.account && usageText(cloud.account) && <p className={styles.small}>今月の利用：{usageText(cloud.account)}</p>}
      </>}
      {error !== null && <div role="alert" className={styles.error}><p>{invalidEmail ? "メールアドレスの形式を確認してください。" : accountErrorText(error)}</p><Details error={error}/></div>}
      <div className={styles.footer}>
        {step === "done" ? <button className={styles.primary} onClick={cloud.closeLogin}>作業に戻る</button>
          : <button className={styles.quiet} onClick={cloud.closeLogin}>ローカルの解析を続ける</button>}
      </div>
    </section>
  </div>;
}

/** The first screen after installation: work on this PC, or turn on the cloud features. */
export function FirstRun({busy, error, onChoose}: {busy: boolean; error: string; onChoose: (choice: "local" | "cloud") => void}) {
  return <section className={styles.firstRun} aria-labelledby="first-run-title">
    <h2 id="first-run-title">インストールが完了しました</h2>
    <p>画像の登録・検出・測定・統計・図は、このPCだけで使えます。どちらから始めるかを選んでください。</p>
    <div className={styles.choices}>
      <button className={styles.choice} disabled={busy} onClick={() => onChoose("local")}>
        <b>このPCで解析を始める</b><span>公開の練習画像で、核の検出から図までを試せます。ログインは不要です。</span>
      </button>
      <button className={styles.choice} disabled={busy} onClick={() => onChoose("cloud")}>
        <b>クラウド機能を有効にする</b><span>メールアドレスでログインし、GPU による核小体・細胞の検出と、解析提案を使えるようにします。</span>
      </button>
    </div>
    {error && <p role="alert" className={styles.error}>{error}</p>}
  </section>;
}
