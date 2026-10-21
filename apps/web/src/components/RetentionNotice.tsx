"use client";
import {useEffect, useState} from "react";
import {API_CONFIGURED, request} from "@/lib/api";
import {retentionText, type RetentionPolicy} from "@/lib/retention";

/** Reads the existing session only; never bootstraps auth or extends retention. */
export default function RetentionNotice({policy}: {policy?: RetentionPolicy}) {
  const [observed, setObserved] = useState<RetentionPolicy>();
  useEffect(() => {
    if (policy || !API_CONFIGURED) return;
    let active = true;
    void request<RetentionPolicy>("/v1/session").then(value => {if (active) setObserved(value);}).catch(() => {});
    return () => {active = false;};
  }, [policy]);
  return <span>{retentionText(policy ?? observed)}</span>;
}
