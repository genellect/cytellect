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
on 2026-10-06. On 2026-11-17 the owner decided to raise it to **USD 50 per month**
(`MONTHLY_BUDGET_USD`), keep **USD 5 per user** (`USER_PROPOSAL_USD_MONTH`) and use
**Claude Sonnet 5.5** (`ANTHROPIC_MODEL=claude-sonnet-5-5`, tariffs 2 / 10 / 0.1 / 2.5 USD
per million tokens) for the redesigned prompt versions. These values are live since the
2026-11-17 deployment (record below). Neither budget replaces or resets the USD 5
cumulative evaluation ledger. Before each request, the Worker atomically admits its two-call maximum
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

## Order of Worker and client releases

A client that sends a newer context or prompt version needs a Worker that already accepts it. Clients from #231 on send
proposal context 1.2.0 (channel labels and field records) with prompt `2026-11-16.1`, and discussion context with the
screen's summary, n breakdown and method; a Worker deployed before #231 rejects them with HTTP 400 `request_invalid`, so
every proposal and discussion from the updated client would fail. Deploy the Worker first, check it, and only then
distribute the client. The newer Worker keeps answering installed clients (up to 0.1.0-local.23) with their own prompt
versions and OpenAI model.

### Required prompt-version check before distribution

Run `uv run python scripts/dev.py doctor --proposal-version` from the exact client commit to distribute, with `CYTELLECT_PROPOSAL_URL` and an operator-issued device token (`CYTELLECT_PROPOSAL_TOKEN` or `CYTELLECT_PROPOSAL_TOKEN_FILE`) configured privately. The proposal/discussion prompt overrides in that environment are checked too. Compose inherits the installed package's prompt defaults instead of pinning another version in YAML. For Windows distribution add `--packaged-client`: it checks the compiled prompt defaults and refuses a preflight URL different from `cloud_account.DEFAULT_CLOUD_URL`, the connection bundled in the client. This mode checks only the AI service; it does not run normal doctor checks or contact/start the GPU. It sends validated public protocol sentinels **without Idempotency-Key**. Only HTTP 400 `request_id_required` passes: version and provider selection happened, but request admission, usage count, reservation and model calls did not. Unsupported versions, invalid context, unavailable service, authentication failures and unexpected successes fail closed. There is no retry or fallback.

Both `local-release.yml` and `windows-store-release.yml` require this check at the source SHA being distributed, before packaging; scheduled Store submission also depends on a successful check (`scheduled-proposal-compatibility`, which starts only when a package is waiting to be submitted, so a schedule with nothing to submit requests no approval). Configure a `proposal-preflight` GitHub environment with `genellect` as a required reviewer and main-only deployment branches. Put `PROPOSAL_PREFLIGHT_URL` in that environment's variables and `PROPOSAL_PREFLIGHT_DEVICE_TOKEN` in its secrets for an authorized active device. Delete any old repository `PROPOSAL_PREFLIGHT_TOKEN`; the new name makes environment setup explicit and the workflow does not fall back to that old key. Remove repository-level copies; the token can spend budget if used with an idempotency key, so it belongs behind approval. It is never passed to packaging, signing, Store submission, or the bundle. Missing configuration stops release. This change provisions no credential or environment and does not invoke the live check during a PR test. Docker/manual distribution follows the same command against the running API's effective URL and prompt settings and requires both `[ok]` lines. Record the source SHA, UTC time, route, prompt version and pass/fail only; do not publish credentials, raw responses or workspace data.

Order of introduction (owner's actions; none is done by merging): (1) deploy the Worker that accepts the client's prompt versions, (2) create the `proposal-preflight` environment with the required reviewer, main-only deployment branches, `PROPOSAL_PREFLIGHT_URL` and `PROPOSAL_PREFLIGHT_DEVICE_TOKEN`, (3) merge the workflows that require the check. Merged earlier, the check fails closed: GitHub creates a referenced environment that does not exist without any protection or secret, the job then has no token, sends nothing and stops, and every push to main stops before the Store package until steps 1 and 2 are done. With the reviewer set, each push to main that builds a Store package waits for that approval.

The protocol tests share the Python client's validated sentinel payloads with the actual Worker handler and prove that supported and unsupported versions never reach claim/count/reserve/model calls. This is a compatibility gate, not evidence of model quality or an actual production generation. The separately authorized live end-to-end verification remains outstanding.

## Production deployment record

Record each production deployment here: the date, source commit, version ID,
applied migrations and sanitized probe results. Never record tokens, e-mail
addresses, research content or individual usage rows.

The production operator configuration is the git-ignored `wrangler.enabled.json`.
Generate it from the live Worker settings instead of editing an old copy: plain-text
variables, the D1 binding, compatibility date and flags, the `api.cytellect.app`
custom domain, workers.dev and preview URLs, and disabled observability. A deploy
then changes only the code. Secrets are not in the file and stay on the Worker.
After deploying, compare the live variables with the file.

Probe with `curl` or the application's user agent (`Cytellect/0.1`). Cloudflare
answers HTTP 403 to Python's default `Python-urllib` user agent before the request
reaches the Worker, so such a probe proves nothing and creates no usage. A probe
in the first seconds after a deploy can still reach the previous version.

| Date (UTC) | Source | Version | Change and checks |
|---|---|---|---|
| 2026-11-16 | `main` 735d088a | `45412097-7078-4dfc-a4bc-4fe3b8a12036`; previous `86df4702-45ab-4afe-bdfa-d94681e75fa2` (2026-11-01) | Adds the result discussion route `/v1/discussions` (#199, requirement AC-09) with the owner's permission. No new migration (`0001`–`0004` applied). Variables and secrets unchanged: `gpt-6.1-sol`, effort `medium`, USD 5 per month. Before: `pnpm check`, `pnpm test` (136 passed, 1 skipped), `node --test scripts/deployment.test.mjs` (4 passed). After: unauthenticated POST to both routes returns 401 with `no-store` on `api.cytellect.app` and workers.dev; an authenticated `{}` to `/v1/discussions` returns 400 `request_invalid` before admission. One paid call, permitted by the owner, on the public demo's nuclear-area comparison (Untreated vs Oxaliplatin 10 µM): HTTP 200 in 15.5 s, 851 input and 682 output tokens, USD 0.00895 settled; the draft passed `validate_discussion`; no outstanding reservation or budget incident afterwards. |
| 2026-11-17 | `main` 2e38c68b (#231) | `39be89ea-5291-4623-b8d5-2067d96d3722`; then `47f1eb8f` when the owner added the `ANTHROPIC_API_KEY` secret in the dashboard; previous `45412097-7078-4dfc-a4bc-4fe3b8a12036` | Claude route, proposal context 1.2.0, discussions shown as written (#231), with the owner's permission. Variables added: `ANTHROPIC_MODEL=claude-sonnet-5-5`, tariffs 2 / 10 / 0.1 / 2.5; `MONTHLY_BUDGET_USD` 5 → 50; `USER_PROPOSAL_USD_MONTH` 5. Live variables equal the operator file before and after the secret was added. No new migration. Before: `pnpm check`, `pnpm test` (155 passed, 1 skipped), `test:deployment` (4). After, on `api.cytellect.app` and workers.dev: unauthenticated POST 401 and authenticated `{}` 400 `request_invalid` on both routes. Paid checks on public/synthetic inputs: discussion `2026-11-16.1` → 200 from `claude-sonnet-5-5` (2,011 input / 1,861 output tokens, USD 0.0236 in the ledger); discussion `2026-11-12.2` → 200 from `gpt-6.1-sol` (861 / 652, USD 0.0087); proposal `2026-11-16.1` → 503 `model_unavailable` twice, Anthropic HTTP 400 `invalid_request_error`: the proposal schema's 47 union-typed fields exceed Claude's structured-output limit (16). The two failures stay in the ledger at their reserved USD 0.35167 each, as designed; no reservation or budget incident remained. The fix (format described in the prompt, not forced) follows in the next deployment. |
| 2026-11-17 | `main` 1a775ab2 (#236) | `177d9093-24c7-4c83-a8ea-e326e0225453`; previous `47f1eb8f` | Claude answers with the format described in the prompt, not forced (#236), with the owner's permission. Variables and secrets unchanged (live variables equal the operator file). Before: `pnpm check`, `pnpm test` (156 passed, 1 skipped), `test:deployment` (4). After: unauthenticated 401 and authenticated `{}` 400 on both hosts and routes. Paid checks with the owner's permission (public method scenarios and synthetic numbers only, no images): discussion `2026-11-16.1` → `claude-sonnet-5-5`; proposal `2026-11-16.1` → `claude-sonnet-5-5`; discussion `2026-11-12.2` → `gpt-6.1-sol`. Public-case evaluation of the 12 proposal scenarios: 12/12 answered by `claude-sonnet-5-5` in 6–9 s, 12/12 schema-valid with no repair call, 12/12 expected behaviour (`expectedBehavior`), 11/12 accepted by the local validation; `unsupported-frap` (recipe `none`, correctly declined) left `channels` empty and was rejected as `proposal_channels_mismatch`, so the prompt now asks for every channel also when the recipe is none (next deployment). Claude requests: 14 settlements, 14 calls, USD 0.5525 in the ledger (mean 12,641 input / 786 output tokens). No reservation or budget incident remained; 2026-11 ledger total USD 1.3072. |
| 2026-11-17 | `main` 1932f7af (#237) | `c7236078-3fa6-4238-bfca-7acc4cb9adfa`; previous `177d9093-24c7-4c83-a8ea-e326e0225453` | The proposal prompt asks for every channel also when the recipe is `none` (#237), with the owner's permission. Variables and secrets unchanged. Before: `main` tree equal to the PR head, `pnpm test` (156 passed, 1 skipped). After, on `api.cytellect.app`: unauthenticated POST 401 and authenticated `{}` 400 `request_invalid` on both routes. One paid re-run of the public `unsupported-frap` scenario: HTTP 200 from `claude-sonnet-5-5` in 7.8 s, recipe `none` with `ch1` as `unused`, accepted by the local validation, so all 12 public scenarios now pass it. Windows 0.1.0-local.24 (source 1a775ab2, published by the owner on 2026-11-17) is the first client on the Claude prompt versions. |
