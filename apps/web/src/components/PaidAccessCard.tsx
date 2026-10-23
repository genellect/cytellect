"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { errorMessage, post, request } from "@/lib/api";
import { featureText, type PaidAccess } from "@/lib/paid-access";
import styles from "./workspace.module.css";


/** Redeem the operator's access code on this PC and show what it allows (local version only). */
export default function PaidAccessCard() {
  const client = useQueryClient();
  const access = useQuery({ queryKey: ["paid-access"], queryFn: () => request<PaidAccess>("/v1/local/paid-access") });
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function act(work: () => Promise<PaidAccess>) {
    setBusy(true); setError("");
    try { client.setQueryData(["paid-access"], await work()); setCode(""); }
    catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  }
  function activate(event: FormEvent) {
    event.preventDefault();
    void act(() => post<PaidAccess>("/v1/local/paid-access", { code }));
  }
  function remove() {
    if (!window.confirm("このPCで有料機能を使えないようにします。もう一度使うには、新しい利用コードが必要です。よろしいですか？")) return;
    void act(() => request<PaidAccess>("/v1/local/paid-access", { method: "DELETE" }));
  }
  const data = access.data;
  const needsCode = data && (!data.activated || data.revoked);
  return <section className={styles.card} aria-labelledby="paid-access-title">
    <h2 id="paid-access-title">有料機能</h2>
    <p className={styles.muted}>クラウドGPUでの自動検出（Cellpose）と解析案の補助は、管理者から受け取る利用コードで有効にします。</p>
    {access.isPending && <p className={styles.muted}>確認しています…</p>}
    {access.error && <p role="alert" className={styles.error}>{errorMessage(access.error)}</p>}
    {data?.activated && !data.revoked && <dl className={styles.paidAccessStatus}>
      {data.label && <><dt>このPC</dt><dd>{data.label}</dd></>}
      {data.reachable === false ? <><dt>状態</dt><dd>利用状況を確認できませんでした。ネットワーク接続を確認してください。</dd></> : <>
        <dt>クラウドGPU（Cellpose）</dt><dd>{featureText(data.cellpose, "視野")}</dd>
        <dt>解析案の補助</dt><dd>{featureText(data.proposals, "回")}</dd>
      </>}
    </dl>}
    {data?.revoked && <p role="alert" className={styles.error}>このPCの利用は管理者によって停止されています。続けて使う場合は、新しい利用コードを入力してください。</p>}
    {data && !data.service_configured && !data.activated && <p className={styles.muted}>この版には有料機能の接続先が設定されていません。</p>}
    {needsCode && data.service_configured && <form onSubmit={activate}>
      <label>利用コード<input value={code} onChange={e => setCode(e.target.value)} required minLength={20} maxLength={400}
        autoComplete="off" spellCheck={false} placeholder="管理者から受け取ったコードを貼り付け" /></label>
      <button className={styles.primary} disabled={busy || code.trim().length < 20}>有効にする</button>
      <p className={styles.muted}>コードは1回だけ使えます。このPC専用の鍵に交換され、コード自体は保存しません。</p>
    </form>}
    {data?.activated && <button className={styles.secondary} disabled={busy} onClick={remove}>このPCでの利用を解除</button>}
    {error && <p role="alert" className={styles.error}>{error}</p>}
  </section>;
}
