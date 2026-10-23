"use client";
import {useEffect, useState} from "react";
import {API_CONFIGURED, LOCAL_MODE, request} from "@/lib/api";
import {retentionText, type RetentionPolicy} from "@/lib/retention";

/** Reads an existing session, or before one exists only the local launcher's public
 * setup status; never bootstraps auth or extends retention. */
export default function RetentionNotice({policy, beforeSession = false}: {policy?: RetentionPolicy; beforeSession?: boolean}) {
  const [observed, setObserved] = useState<RetentionPolicy>();
  const source = beforeSession ? (LOCAL_MODE ? "/v1/local/setup" : null) : "/v1/session";
  useEffect(() => {
    if (policy || !API_CONFIGURED || !source) return;
    let active = true;
    void request<RetentionPolicy>(source).then(value => {if (active) setObserved(value);}).catch(() => {});
    return () => {active = false;};
  }, [policy, source]);
  return <span>{retentionText(policy ?? observed)}</span>;
}
