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
`MONTHLY_BUDGET_USD="0"`, `DEVICE_MONTHLY_REQUESTS="0"`, empty tariffs and disabled
observability. No scheduled jobs, analytics sinks or research-data storage are added.

Both `0001_init.sql` and `0002_usage_integrity.sql` must be applied. On an existing
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

## Rollback and enablement gates

- First disable billing by redeploying this reviewed zero-budget configuration.
  In-flight requests may already have reserved their maximum; preserve those holds.
- Roll back code only to a recorded version compatible with both D1 migrations:
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

References: [local Wrangler installation](https://developers.cloudflare.com/workers/wrangler/install-and-update/),
[Worker commands](https://developers.cloudflare.com/workers/wrangler/commands/workers/),
[D1 commands and migrations](https://developers.cloudflare.com/d1/wrangler-commands/).
