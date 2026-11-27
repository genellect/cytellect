"use client";
/**
 * The local build's connection notice (#284 W9): no answer, an ended session and the wrong origin each have
 * their own line, and the previous launcher run's abnormal stop is named once. When the service answers again,
 * `onReconnected` re-reads what was saved (the workspace runtime's `reconnected`).
 */
import {useEffect, useRef, useState, useSyncExternalStore} from "react";
import {LOCAL_MODE, post, request} from "@/lib/api";
import {connectionNotice, localConnection, previousStopText, RECONNECT_INTERVAL_MS, subscribeConnection, type LocalConnection, type PreviousStop} from "@/lib/local-connection";
import styles from "../cloud-account.module.css";

/** The abnormal stop whose notice the researcher closed (its reason and time); never research data. */
const STOP_SEEN = "cytellect.local.previous-stop-seen";

export function useLocalConnection(): LocalConnection {
  return useSyncExternalStore(subscribeConnection, localConnection, () => "connected");
}

export function ConnectionNotice({onReconnected}: {onReconnected: () => void}) {
  const state = useLocalConnection();
  const [checking, setChecking] = useState(false);
  const [previous, setPrevious] = useState<string | null>(null);
  const stopKey = useRef("");
  const last = useRef<LocalConnection>(state);
  const reconnected = useRef(onReconnected);
  useEffect(() => {reconnected.current = onReconnected;}, [onReconnected]);
  // Back to "connected" after any failure: re-read the rows and fields once.
  useEffect(() => {
    if (last.current !== "connected" && state === "connected") reconnected.current();
    last.current = state;
  }, [state]);
  async function check() {
    setChecking(true);
    // The setup route needs no session: an answer means the service is back. An ended session is opened again.
    try {await (state === "session" ? post("/v1/local/session") : request("/v1/local/setup"));}
    catch {/* the notice shows what the attempt met */}
    finally {setChecking(false);}
  }
  const checkRef = useRef(check);
  useEffect(() => {checkRef.current = check;});
  useEffect(() => {
    if (!LOCAL_MODE || state !== "unreachable") return;
    const timer = window.setInterval(() => void checkRef.current(), RECONNECT_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [state]);
  useEffect(() => {
    if (!LOCAL_MODE) return;
    let current = true;
    void request<PreviousStop>("/v1/local/previous-stop").then(value => {
      // A start after a normal stop forgets the closed notice: an unrecorded stop has no time, so the next one
      // would otherwise read as the stop already closed and never be shown.
      if (!value?.abnormal) {try {localStorage.removeItem(STOP_SEEN);} catch {/* storage is a convenience only */}return;}
      // Shown until it is closed, then not again for the same stop (a reload is not another stop).
      const key = `${value?.reason ?? ""}:${value?.time ?? ""}`;
      let seen = false;
      try {seen = localStorage.getItem(STOP_SEEN) === key;} catch {/* storage is a convenience only */}
      if (current && !seen) {stopKey.current = key;setPrevious(previousStopText(value));}
    }).catch(() => {});
    return () => {current = false;};
  }, []);
  if (!LOCAL_MODE) return null;
  const notice = connectionNotice(state, checking);
  if (!notice && !previous) return null;
  return <div className={styles.notices}>
    {notice && <div className={styles.notice} data-tone="problem" role={state === "origin" ? "alert" : "status"}>
      <p><b>{notice.status}</b>{notice.reason && <> {notice.reason}</>}</p>
      {notice.action && <button className={styles.secondary} disabled={checking} onClick={() => void check()}>{notice.action}</button>}
    </div>}
    {previous && <div className={styles.notice} data-tone="info" role="status">
      <p>{previous}</p>
      <button className={styles.quiet} onClick={() => {try {localStorage.setItem(STOP_SEEN, stopKey.current);} catch {/* shown again after a reload */}setPrevious(null);}}>閉じる</button>
    </div>}
  </div>;
}
