/**
 * Owner-only admin page and short message pages. Every value from the server is
 * inserted with textContent (or escaped here), never as HTML.
 */
import { base64url, escapeHtml } from "./http";

const STYLE = `
:root{--bg:#f7f7f5;--panel:#fff;--text:#1d1f21;--muted:#5d6166;--line:#d9dbd6;--accent:#1f5f8b;--accent-text:#fff;--warn:#9a3412;--ok:#166534}
@media (prefers-color-scheme:dark){:root{--bg:#141618;--panel:#1d2023;--text:#eceeef;--muted:#a3a8ad;--line:#33373b;--accent:#6fb1df;--accent-text:#0b1620;--warn:#f0a07a;--ok:#86d19b}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.6 system-ui,-apple-system,"Hiragino Sans","Noto Sans JP",sans-serif}
main{max-width:960px;margin:0 auto;padding:32px 16px}h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 8px}
p{margin:8px 0}a{color:var(--accent)}.muted{color:var(--muted)}.panel{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:16px;margin-top:16px}
label{display:block;font-weight:600;margin:8px 0 4px}input{font:inherit;color:inherit;background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:7px 10px;min-width:0}
button{font:inherit;border:1px solid var(--accent);background:var(--accent);color:var(--accent-text);border-radius:6px;padding:7px 14px;cursor:pointer}
button.secondary{background:transparent;color:var(--accent)}button:disabled{opacity:.5;cursor:default}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.status{min-height:1.6em;margin-top:8px}.status.error{color:var(--warn)}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-weight:600;color:var(--muted)}td input{width:7em}.scroll{overflow-x:auto}.state-pending{color:var(--warn);font-weight:600}.state-allowed{color:var(--ok)}
[hidden]{display:none!important}`;

const SCRIPT = `
const $ = (id) => document.getElementById(id);
const say = (text, error) => { const s = $("status"); s.textContent = text; s.className = "status" + (error ? " error" : ""); };
async function api(path, body) {
  const init = body === undefined ? {} : { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) };
  const response = await fetch(path, { credentials: "same-origin", ...init });
  let data = null; try { data = await response.json(); } catch {}
  return { status: response.status, data };
}
const MESSAGES = {
  code_expired: "コードの期限が切れたか、まだ送っていません。もう一度送ってください。",
  too_many_attempts: "誤りが多すぎたため、このコードは無効です。もう一度送ってください。",
  mail_unavailable: "メールの送信が設定されていません。", mail_failed: "メールを送れませんでした。少し待ってからもう一度試してください。",
  email_invalid: "メールアドレスを確認してください。", owner_cannot_be_revoked: "オーナーの許可は取り消せません。",
  limits_invalid: "上限には 0 以上の数を入れてください（空欄は既定値）。", user_not_found: "この利用者は登録されていません。",
};
function explain(result) {
  const data = result.data || {};
  if (data.error === "code_invalid") return "コードが違います（残り " + data.attempts_left + " 回）。";
  if (data.error === "rate_limited") return "回数の上限に達しました。" + data.retry_after_seconds + " 秒後にもう一度試してください。";
  return MESSAGES[data.error] || "処理できませんでした（HTTP " + result.status + "）。";
}
const when = (value) => value ? new Date(value).toLocaleString("ja-JP") : "—";
const STATES = { pending: "承認待ち", allowed: "許可", revoked: "取り消し" };
function cell(row, text, className) { const td = row.insertCell(); td.textContent = text; if (className) td.className = className; return td; }
function button(label, secondary, onClick) { const b = document.createElement("button"); b.type = "button"; b.textContent = label; if (secondary) b.className = "secondary"; b.addEventListener("click", onClick); return b; }
async function change(body, done) {
  const result = await api("/v1/admin/users", body);
  if (result.status === 200) { say(done(result.data)); await load(); } else say(explain(result), true);
}
async function load() {
  const result = await api("/v1/admin/users");
  if (result.status === 401) { $("login").hidden = false; $("dashboard").hidden = true; return; }
  if (result.status !== 200) { say(explain(result), true); return; }
  const data = result.data;
  $("login").hidden = true; $("dashboard").hidden = false;
  $("owner").textContent = data.owner;
  $("summary").textContent = data.month + "（UTC）の全体の利用：GPU " + data.global.gpu_seconds + " / " + data.global.gpu_seconds_month + " 秒、解析提案 "
    + data.global.proposal_usd.toFixed(2) + " USD。既定の上限は 1 人あたり GPU " + data.defaults.gpu_seconds_month + " 秒、解析提案 "
    + data.defaults.proposal_usd_month + " USD。" + when(data.resets_at) + " にリセット。";
  const body = $("users"); body.replaceChildren();
  $("empty").hidden = data.users.length > 0;
  for (const user of data.users) {
    const row = body.insertRow();
    cell(row, user.email);
    cell(row, STATES[user.state] || user.state, "state-" + user.state);
    cell(row, user.usage.gpu_seconds + " / " + user.limits.gpu_seconds_month + " 秒");
    cell(row, user.usage.proposal_usd.toFixed(2) + " / " + user.limits.proposal_usd_month + " USD");
    cell(row, when(user.requested_at));
    const limits = row.insertCell();
    const gpu = document.createElement("input"); gpu.type = "number"; gpu.min = "0"; gpu.step = "60"; gpu.placeholder = "既定";
    gpu.setAttribute("aria-label", user.email + " の GPU 上限（秒）");
    const usd = document.createElement("input"); usd.type = "number"; usd.min = "0"; usd.step = "0.5"; usd.placeholder = "既定";
    usd.setAttribute("aria-label", user.email + " の解析提案の上限（USD）");
    if (user.limits.custom) { gpu.value = user.limits.gpu_seconds_month; usd.value = user.limits.proposal_usd_month; }
    const wrap = document.createElement("div"); wrap.className = "row";
    wrap.append(gpu, usd, button("保存", true, () => change({ email: user.email, action: "limits",
      gpu_seconds_month: gpu.value === "" ? null : Number(gpu.value), proposal_usd_month: usd.value === "" ? null : Number(usd.value) },
      () => user.email + " の上限を保存しました。")));
    limits.append(wrap);
    const actions = row.insertCell();
    if (user.state !== "allowed") actions.append(button(user.state === "pending" ? "承認" : "再び許可", false,
      () => change({ email: user.email, action: "allow" }, (d) => user.email + " を許可しました。" + (d.notified ? "メールで知らせました。" : ""))));
    else if (user.email !== data.owner) actions.append(button("取り消す", true, () => {
      if (confirm(user.email + " の許可を取り消します。この人がログインしたすべての端末で、GPU と解析提案がすぐに止まります。")) {
        change({ email: user.email, action: "revoke" }, () => user.email + " の許可を取り消しました。");
      }
    }));
  }
}
$("send").addEventListener("submit", async (event) => {
  event.preventDefault();
  const result = await api("/v1/admin/session/code", { email: $("email").value });
  if (result.status === 200) { $("verify").hidden = false; $("code").focus(); say("オーナーのアドレスであれば、コードを送りました。"); }
  else say(explain(result), true);
});
$("verify").addEventListener("submit", async (event) => {
  event.preventDefault();
  const result = await api("/v1/admin/session/verify", { email: $("email").value, code: $("code").value });
  if (result.status === 204) { $("code").value = ""; say(""); await load(); } else say(explain(result), true);
});
$("allow").addEventListener("submit", (event) => {
  event.preventDefault();
  const email = $("new-email").value;
  change({ email, action: "allow" }, (d) => email + " を許可しました。" + (d.notified ? "メールで知らせました。" : ""));
  $("new-email").value = "";
});
$("logout").addEventListener("click", async () => { await api("/v1/admin/session/logout", {}); say("ログアウトしました。"); await load(); });
load();`;

function securityHeaders(nonce: string, script: boolean): Record<string, string> {
  return {
    "content-type": "text/html; charset=utf-8", "cache-control": "no-store", "referrer-policy": "no-referrer",
    "x-content-type-options": "nosniff", "x-frame-options": "DENY",
    "content-security-policy": `default-src 'none'; style-src 'nonce-${nonce}'; ${script ? `script-src 'nonce-${nonce}'; connect-src 'self'; ` : ""}`
      + "form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
  };
}

const nonce = () => base64url(crypto.getRandomValues(new Uint8Array(16)));

function htmlDocument(title: string, body: string, nonceValue: string, script = "") {
  return `<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">`
    + `<meta name="robots" content="noindex"><title>${escapeHtml(title)}</title><style nonce="${nonceValue}">${STYLE}</style></head>`
    + `<body><main>${body}</main>${script ? `<script nonce="${nonceValue}">${script}</script>` : ""}</body></html>`;
}

export function adminPage(): Response {
  const value = nonce();
  const body = `<h1>Cytellect 管理</h1><p class="muted">クラウド機能（GPU 推論と解析提案）の利用者を管理します。</p>
<section id="login" class="panel" hidden><h2>オーナーのログイン</h2>
<form id="send"><label for="email">メールアドレス</label><div class="row"><input id="email" type="email" autocomplete="email" required><button>コードを送る</button></div></form>
<form id="verify" hidden><label for="code">メールで届いた 6 桁のコード</label><div class="row"><input id="code" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9 ]{6,8}" required><button>ログイン</button></div></form></section>
<section id="dashboard" hidden><div class="row"><p class="muted">ログイン中：<span id="owner"></span></p><button id="logout" type="button" class="secondary">ログアウト</button></div>
<p id="summary"></p>
<div class="panel"><h2>メールアドレスを許可する</h2><form id="allow" class="row"><input id="new-email" type="email" aria-label="許可するメールアドレス" required><button>許可する</button></form>
<p class="muted">許可した人には、利用できるようになったことをメールで知らせます。</p></div>
<div class="panel"><h2>利用者</h2><p class="muted">上限の空欄は既定値です。取り消すと、その人がログインしたすべての端末で GPU と解析提案がすぐに止まります。移行期間の招待トークンは利用者に結びついていないため止まりません（LEGACY_INVITATIONS="false" で止めます）。</p>
<div class="scroll"><table><thead><tr><th>メールアドレス</th><th>状態</th><th>GPU（今月）</th><th>解析提案（今月）</th><th>申請日時</th><th>上限（秒・USD）</th><th>操作</th></tr></thead><tbody id="users"></tbody></table></div>
<p id="empty" class="muted" hidden>まだ利用者はいません。</p></div></section>
<p id="status" class="status" role="status" aria-live="polite"></p>`;
  return new Response(htmlDocument("Cytellect 管理", body, value, SCRIPT), { status: 200, headers: securityHeaders(value, true) });
}

export function messagePage(status: number, title: string, text: string, form?: { action: string; token: string; label: string }): Response {
  const value = nonce();
  const action = form ? `<form method="post" action="${escapeHtml(form.action)}"><input type="hidden" name="t" value="${escapeHtml(form.token)}">`
    + `<button>${escapeHtml(form.label)}</button></form>` : "";
  const body = `<h1>${escapeHtml(title)}</h1><div class="panel"><p>${escapeHtml(text)}</p>${action}</div><p class="muted"><a href="/admin">管理ページ</a></p>`;
  return new Response(htmlDocument(title, body, value), { status, headers: securityHeaders(value, false) });
}
