# Proposal Worker deployment

This runbook deploys the relay with **model calls disabled**. The approved public
evaluation allowance is not a production operating budget. OpenAI quota resolution,
successful public-case evaluation and separate production-budget approval remain
required before enabling paid proposals. No OpenAI key is needed for this deployment.

## Reproducible local preparation

Node.js 24 and the repository's pinned pnpm are required. Wrangler **4.135.0** is a
development dependency of `services/proposal-worker` (MIT OR Apache-2.0); the root
lockfile records its CLI, bundler and runtime dependencies. Application/runtime
dependencies have not been changed. Installer scripts for esbuild/workerd are
disabled; supported-platform binaries come from locked optional packages. Do not
install with `--no-optional`. The CLI is not bundled in the Windows application.
The scoped `miniflare>undici` override pins 7.29.1 to avoid the 7.29.0 high-severity
advisories in Wrangler's development runtime. The remaining high-severity audit
finding is the existing web ESLint chain's `braces` dependency; it is outside this
deployment-tool change. Do not describe the full development tree as audit-clean.
Wrangler's npm archive declares its dual license but does not ship license text;
the upstream [Workers SDK licenses](https://github.com/cloudflare/workers-sdk) apply.
This CLI pin is build tooling, not authorization to redistribute its binaries
without the corresponding third-party notices.

From the repository root, run `pnpm install --frozen-lockfile`, then:

```sh
cd services/proposal-worker
pnpm check
pnpm test
pnpm test:deployment
pnpm cf --version
```

For restricted machines, `WRANGLER_LOG_PATH` may point to a writable directory
outside the checkout. Set `WRANGLER_SEND_METRICS=false` for these commands. Never
attach Wrangler debug logs to public issues: authenticated CLI logs are private.

## Account and database preparation

An operator must confirm the intended existing Cloudflare account and its free
Workers/D1 limits before creating resources. These commands do not subscribe to
a paid plan. Capacity beyond a free plan is not promised. Cloudflare limits and
provider billing are separate from the relay's budget ledger.

```sh
pnpm cf whoami
# Only if the existing account is not authenticated:
pnpm cf login
```

Set `CLOUDFLARE_ACCOUNT_ID` in the operator's shell to the selected account ID,
then inspect `pnpm cf d1 list`. Reuse only a database intentionally dedicated to
this relay. If absent, create `pnpm cf d1 create cytellect-proposal`. Do not reuse
another project's database merely because its name resembles this one.

```sh
pnpm deploy:prepare-disabled ACCOUNT_ID D1_DATABASE_ID
pnpm cf deploy --config wrangler.disabled.json --dry-run --outdir .deploy-dry-run
pnpm cf d1 migrations list cytellect-proposal --remote --config wrangler.disabled.json
pnpm cf d1 migrations apply cytellect-proposal --remote --config wrangler.disabled.json
pnpm cf d1 migrations list cytellect-proposal --remote --config wrangler.disabled.json
```

Replace the two uppercase IDs with confirmed identifiers, never credentials.
The generator refuses to overwrite `wrangler.disabled.json`; inspect an existing
file rather than silently replacing it. Check `account_id`, Worker name, D1 ID,
`MONTHLY_BUDGET_USD="0"`, `DEVICE_MONTHLY_REQUESTS="0"`, empty tariffs, empty
`OWNER_EMAIL` and `MAIL_FROM`, `GPU_MONTHLY_SECONDS="0"`,
`compatibility_flags = ["enable_request_signal"]` (the GPU gateway relies on it to
release a disconnected client's slot) and disabled observability. No scheduled jobs, analytics sinks or research-data storage are added.

All of `0001_init.sql`, `0002_usage_integrity.sql`,
`0003_budget_reconciliation.sql` and `0004_cloud_access.sql` must be applied before
enabling calls. Apply `0004` **before** deploying code that includes cloud access:
that code looks up login tokens and records the user on every reservation and
settlement. Deployed first, every `/v1/proposals` request fails with HTTP 500
(`no such table: user_devices`) for every installation, including invitation
tokens, until the migration is applied. Immediately before `pnpm cf deploy`, run
`pnpm cf d1 migrations list cytellect-proposal --remote --config wrangler.disabled.json`
and deploy only when it reports no unapplied migration. Code without cloud access
keeps working on a database with `0004`. On an existing
database, retain a private D1 export before migration (`d1 export --remote` with
an output path outside the checkout). It contains access/usage records; do not
publish it. Never clear reservations to make a budget check pass.

## Deploy and verify without paid requests

Record the source commit and existing deployment version before deploying:

```sh
pnpm cf deployments list --config wrangler.disabled.json
pnpm cf deploy --config wrangler.disabled.json
pnpm cf deployments list --config wrangler.disabled.json
```

The initial deployment is closed to installations until an operator sets
`ADMIN_TOKEN` through `pnpm cf secret put ADMIN_TOKEN --config wrangler.disabled.json`.
Use a securely generated URL-safe token of at least 20 characters, entered via
the CLI's protected prompt; never a command argument, chat or tracked file. This
secret does not enable model calls. **Do not set `OPENAI_API_KEY` at this stage.**
Existing OpenAI secrets, if present on an older Worker, still cannot bypass the
zero budget and quota in this configuration.

Use the existing invitation/device endpoints described in
[proposal service](proposal-service.md) to provision one authorized installation.
Handle their returned tokens privately. This exercises the D1 access records;
it must not be mistaken for successful model evaluation. In a private shell,
set `CYTELLECT_PROPOSAL_TOKEN` to that installation's token, then run:

```sh
pnpm deploy:verify-disabled https://WORKER.SUBDOMAIN.workers.dev
```

The probe expects unauthenticated HTTP 401 and authenticated HTTP 503, both
`Cache-Control: no-store`. It sends only `{}`, no analysis context or request ID,
and refuses redirects. Even an accidentally enabled service rejects that body
before a model call. The CLI prints only fixed results; it never prints a token.
A 401 on the authenticated request does not prove that paid requests are disabled.

Verify migrations and compare aggregate `COUNT(*)` values for `reservations`,
`settlements` and `proposal_requests` before/after: this probe must not add any.
Do not select or print individual device/invitation hashes. Keep deployment ID,
commit, migration names and sanitized probe results in the release record.

## Cloud access (login, approval and GPU gateway)

Provisional owner decisions (2026-10-29, pending approval of the Windows access
plan): Resend sends mail; per-user monthly defaults are GPU 3,600 seconds and
proposals USD 5; device logins expire after 90 days unused. The routes and stored
data are described in [proposal service](proposal-service.md#cloud-access-e-mail-login-approval-and-gpu-gateway).
Resend and Modal are external services: enabling them is the owner's decision, and
Modal's own spend limit stays in place as the outer bound.

| Name | Kind | Purpose |
|---|---|---|
| `OWNER_EMAIL` | variable | The only address that can open `/admin` (through Cloudflare Access, or with the e-mail code while Access is not configured); always allowed |
| `ADMIN_ORIGIN` | variable | The only origin that serves `/admin` and `/v1/admin/*`, including the legacy `/v1/admin/invitations` (production: `https://api.cytellect.app`); other origins of the Worker, such as `workers.dev`, answer 404 there and approval links point to this origin. Empty serves them on every origin; required when the Access values below are set |
| `ACCESS_TEAM_DOMAIN` | variable | Cloudflare Access team domain, `<team>.cloudflareaccess.com`. Set together with `ACCESS_AUD` and `ADMIN_ORIGIN`: the Worker then verifies the owner's Access token on every admin path and turns off the e-mail code login for `/admin`. Both empty keeps the e-mail code login |
| `ACCESS_AUD` | variable | Application Audience (AUD) tag of the Access application for the admin paths (`<AUD tag>`) |
| `ADMIN_SIGNING_KEY` | secret | At least 32 random characters. Keys the hashes of login codes and rate-limit entries and signs approval links. Rotating it voids pending codes, links, rate-limit counters and address locks, not device tokens |
| `RESEND_API_KEY` | secret | Resend API key. Without it, code requests fail with `mail_unavailable`; nothing is sent |
| `MAIL_FROM` | variable | Sender, for example `Cytellect <noreply@…>` on a domain verified in Resend (SPF/DKIM) |
| `MODAL_URL` | secret | HTTPS origin of the Modal Cellpose server |
| `MODAL_PROXY_TOKEN` | secret | Modal proxy-auth token, ID and secret joined by `.` ([cloud GPU](cloud-gpu.ja.md)) |
| `GPU_MONTHLY_SECONDS` | variable | Global monthly GPU seconds; `0` or empty closes the gateway |
| `USER_GPU_SECONDS_MONTH`, `USER_PROPOSAL_USD_MONTH` | variables | Per-user monthly defaults (3600 and 5 when empty). A malformed value means 0 |
| `LEGACY_INVITATIONS` | variable | `"false"` closes `/v1/admin/invitations`, `/v1/devices` and invitation tokens after installations have moved to login |

Until `OWNER_EMAIL` and `ADMIN_SIGNING_KEY` are set, the login and admin APIs
return JSON 503 `auth_unavailable` and `/admin` returns an HTML 503 page. Enter secrets with `pnpm cf secret put NAME` at the
CLI's protected prompt, never as arguments or in tracked files. The global
proposal budget remains `MONTHLY_BUDGET_USD`.

<a id="owner-sign-in-through-cloudflare-access"></a>**Owner sign-in through Cloudflare Access.**
The owner signs in to the admin page with Google through Cloudflare Access (Zero Trust,
free plan). The Worker does not rely on Access sitting in front of it: when
`ACCESS_TEAM_DOMAIN` and `ACCESS_AUD` are set, it accepts `/admin`, every `/v1/admin/*`
route (the approval link included) and the legacy `/v1/admin/invitations` only with a
`Cf-Access-Jwt-Assertion` token that it verifies itself:

- RS256 signature by a key published at `https://<team>.cloudflareaccess.com/cdn-cgi/access/certs`
  (cached for 10 minutes; an unknown key id refetches the keys, at most every 30 seconds);
- issuer `https://<team>.cloudflareaccess.com` and the application's AUD tag in `aud`;
- expiry and not-before, with 60 seconds' allowance for clock difference;
- an `email` claim equal to `OWNER_EMAIL`, ignoring case. Service tokens carry no
  e-mail and are refused.

A request that reaches the Worker without passing Access (through `workers.dev`,
another route, or a path the application does not cover) therefore has no valid token
and is refused: HTML 403 for `/admin` and the approval link, JSON 401 `auth_required`
for the admin APIs, 401 `unauthorized` for invitations. `ADMIN_ORIGIN` still answers 404
on every other origin before any token is read. Access needs `ADMIN_ORIGIN`, so that the
approval links in the owner's mail point to the host the application covers. Only one
of the two Access values, a malformed value, or Access without `ADMIN_ORIGIN` closes every
admin path with 503 `access_config_invalid`; the researcher routes keep working.

With Access configured, the e-mail code login for the admin page is off (the owner
does not enter a code after Google): `/v1/admin/session/*` answers 404, admin session
cookies issued earlier no longer open anything, and **ログアウト** ends the Access
session (`/cdn-cgi/access/logout`). While both Access values are empty, the e-mail
code login works exactly as before. The researcher routes (`/v1/auth/*`,
`/v1/cellpose/*`, `/v1/proposals`, `/v1/devices`) stay outside Access. Issuing a legacy
invitation then needs the owner's Access sign-in as well as `ADMIN_TOKEN`; new
researchers use e-mail login instead. Signing in for researchers (Google, Microsoft,
passkeys) is a separate, later design and does not use this application.

Owner steps (in the Cloudflare dashboard; only the owner changes these settings):

1. **Zero Trust**. On first use, choose a team name and the Free plan. The team domain
   is `<team>.cloudflareaccess.com`; it is shown under **Settings → Custom pages**
   (Team domain).
2. **Settings → Authentication → Login methods → Add new → Google**. Create an OAuth
   client in Google Cloud Console with the redirect URL Cloudflare shows
   (`https://<team>.cloudflareaccess.com/cdn-cgi/access/callback`), enter its client ID
   and secret, and use **Test**.
3. **Access → Applications → Add an application → Self-hosted**. Name `Cytellect admin`;
   destinations `api.cytellect.app` with path `admin` and `api.cytellect.app` with path
   `v1/admin/*`; login method Google only; session duration 24 hours.
4. Policy: **Allow**, include **Emails** = the owner's address. Optionally, where the
   dashboard offers it, also require Cloudflare's independent MFA, so that a second
   factor such as Windows Hello (a passkey) or a security key is asked after Google,
   whatever the Google account's own settings. Save.
5. Open the application's **Overview** and copy the **Application Audience (AUD) tag**.
6. Set `ACCESS_TEAM_DOMAIN = "<team>.cloudflareaccess.com"`, `ACCESS_AUD = "<AUD tag>"`
   and `ADMIN_ORIGIN = "https://api.cytellect.app"` in the operator's `wrangler.toml`
   (not in tracked files or records) and deploy, which is the owner's decision.
7. In a private window, `https://api.cytellect.app/admin` must show the Google sign-in
   first, then the Cytellect page without a code form; `https://api.cytellect.app/v1/auth/status`
   must still answer JSON without any sign-in; the `workers.dev` address of the Worker
   must answer 404 for `/admin`.

To go back to the e-mail code login, empty both Access values and deploy.

Owner operations, all on `https://<ADMIN_ORIGIN>/admin`:

- **Sign in** with Google through Cloudflare Access as `OWNER_EMAIL`. While Access is
  not configured, sign in instead with `OWNER_EMAIL` and the 6-digit code sent there.
- **Approve** a request from the e-mail link (one button on the opened page; with
  Access, the link passes the same sign-in) or with **承認** on the page. The requester receives an e-mail.
- **Pre-register** an address with **許可する**; that person can log in at once.
- **Revoke** with **取り消す**. Every device that logged in with that address stops
  at its next GPU or proposal request. Re-allowing requires a new login.
  Invitation tokens are not bound to a user and keep working for proposals while
  `LEGACY_INVITATIONS` is on: for a hard stop, deploy `LEGACY_INVITATIONS="false"`
  (or set `revoked_at` on the device record in D1).
- **Locked out**: 20 wrong codes within a day lock an address for 24 hours, and
  10 code requests use up an address's codes until that day's window ends. Anyone
  who knows an address can do either, also to the owner's admin login while Access is
  not configured (with Access, the owner's sign-in uses no code). Wait, or
  rotate `ADMIN_SIGNING_KEY` (`pnpm cf secret put ADMIN_SIGNING_KEY`), which clears
  every lock and counter and also voids pending codes and approval links. Device
  tokens and admin sessions stay valid.
- **Limits**: set per-user GPU seconds and proposal USD; blank uses the defaults.

Before enabling, check without paid calls: `/v1/auth/code` for an unlisted
address returns `pending_approval` and e-mails only the owner; the owner can sign
in to `/admin`; `GET /v1/cellpose/health` without a token returns 401. A health
call with a token starts a GPU container and counts as GPU time.

## Rollback and enablement gates

- First disable billing by redeploying this reviewed zero-budget configuration.
  In-flight requests may already have reserved their maximum; preserve those holds.
- Roll back code only to a recorded version compatible with the applied D1 migrations:
  `pnpm cf rollback VERSION_ID --config wrangler.disabled.json`. Verify its budget
  configuration; rollback must not restore an earlier enabled version. Repeat the
  disabled smoke check. Do not downgrade or restore D1 casually: that can revive
  revoked credentials or erase paid-usage accounting. Prefer a forward code fix.
- For actual model enablement, require the live public-case report, confirmed model
  access, production monthly budget, per-device allowance, current pricing, secret
  provisioning and reviewed nonzero configuration. Use a separately reviewed
  operator configuration; do not mutate this disabled baseline. The current
  $5 evaluation approval covers none of these production charges.
- Vercel UI deployment, Docker/Windows compatibility and scientific evaluation
  remain separate checks. A deployed disabled Worker is infrastructure readiness,
  not functioning LLM-assisted analysis.

## Production budget and reconciliation

The owner approved a separate **USD 5 per UTC calendar month** production budget
on 2026-10-06. This does not replace or reset the USD 5 cumulative evaluation
ledger. Before each request, the Worker atomically admits its two-call maximum
only if settled costs plus all outstanding reservations fit the monthly budget.
Unknown or interrupted billing retains its conservative reservation amount.

Migration `0003_budget_reconciliation.sql` creates an operator-reconciliation
hold when observed per-call token usage exceeds its admitted bound, or when a
settlement exceeds its reservation. Recording the incident, accounting the cost
and removing the corresponding reservation are one SQLite transaction. Other
outstanding reservations remain intact. Every installation and every later month
is blocked while any incident remains unresolved; increasing the budget or
restarting the Worker does not clear it. The Worker also checks the hold directly
before each initial or repair call. Requests already sent to OpenAI cannot be
recalled: the admission limit cannot guarantee an exact provider invoice when
the provider reports usage beyond the assumed maximum.

A completed, schema-valid billed draft can still be returned after the incident
is committed. Local semantic validation and researcher adoption remain required.
Malformed, refused or incomplete output is not returned, and an exceeded bound
never triggers a repair call. The response body is not stored with the incident
or serialized into error diagnostics. Later requests receive HTTP 503 with
`budget_reconciliation_required` without another model call.

To reconcile, first deploy the zero-budget configuration and let in-flight calls
finish. Inspect accounting-only `budget_incidents`, `settlements` and outstanding
`reservations` privately; compare provider usage and the configured tariff/token
bound. Correct the cause, test admission again and retain all historical costs
and reservations. Only then mark the specific reviewed incident with
`resolved_at` (UTC epoch milliseconds) and a short operator `resolution_note`
containing no research information. There is no public endpoint or automatic
monthly reset for this action. Never delete incidents, clear reservations or
reduce recorded spending to unblock calls. Re-enable only within the approved
budget, then confirm that settled plus outstanding costs still permit admission.

References: [local Wrangler installation](https://developers.cloudflare.com/workers/wrangler/install-and-update/),
[Worker commands](https://developers.cloudflare.com/workers/wrangler/commands/workers/),
[D1 commands and migrations](https://developers.cloudflare.com/d1/wrangler-commands/).
