# Data protection and operations

This early prototype has local automated tests for invitation replay/revocation, Origin/CSRF, cross-session ownership, immutable versions, stale leases, job timeout/retry and expiry/deletion. These tests do not certify a hosted deployment. Run the acceptance checks on the actual analysis host before receiving private research data.

## Data boundaries

Unpublished research images, papers, filenames, conditions, masks, tables and plots stay outside Git, Cloud development, CI, external AI and public demos. Public published images can be used for appropriate internal tests with recorded source and conditions. Only assets with a verified public redistribution basis belong in the public UI/repository; register hashes and attribution separately. Synthetic images remain numerical unit-test fixtures.

Browser uploads go directly to the analysis API. Disable Vercel image optimization, analytics/session recording, Service Workers and CDN caching for research content. API responses carry no-store. Every read checks the owning live session and workspace; IDs alone confer no permission. Do not log request bodies, filenames or token values.

## Installation and invitations

For local development set `CYTELLECT_DATA_DIR` to a private directory outside checkout, `CYTELLECT_APP_ORIGIN=http://localhost:3000` and `CYTELLECT_SECURE_COOKIES=false`. Run `uv run cytellect serve`, `uv run cytellect-worker` and `pnpm dev` in separate terminals.

For Linux containers create a dedicated private directory owned by UID 10001 with mode0700, set its absolute path in `CYTELLECT_RUNTIME_DIR`, then run `docker compose up --build -d`. The worker has `network_mode: none` and shares only the private local volume. SQLite must not live on a network share. Fiji/model acquisition happens during build, never in a job.

Use `uv run cytellect invite --hours 24` (or `docker compose exec api cytellect invite --hours 24`) from a private operator terminal. The CLI emits the one-use invitation once: do not pipe it into shared logs. Tokens are stored hashed; sessions use HttpOnly cookies. Logout revokes the session.

## Windows local mode

The local launcher binds only the literal `127.0.0.1` address and uses strict Host/Origin/CSRF checks, but it does not install OS firewall restrictions for its Python/Fiji worker. Fixed recipes, installed-artifact hashes and the absence of runtime downloads are application safeguards, not proof of denied network egress. See [local delivery](local.md) for the single-user trust boundary and cleanup behavior while the PC is off.

## Public host

Use an API hostname under the same registrable domain as the Vercel UI, exact `CYTELLECT_APP_ORIGIN`, HTTPS and `CYTELLECT_SECURE_COOKIES=true`. Strict same-site cookies deliberately do not support an arbitrary unrelated third-party API domain. The default Vercel domain can host the public sample viewer while an analysis domain is being provisioned.

`docker compose -f compose.yaml -f infra/compose.tls.yaml up -d` adds the Caddy TLS proxy; configure `CYTELLECT_API_HOST`. Only the proxy should face the Internet. Apply host firewall rules, storage capacity alarms and OS updates. The Compose memory limit bounds the whole worker; the supervisor also bounds children. Caddy rejects over-limit bodies before multipart parsing; temporary uploads stay in /data/tmp.

Verify browser Origin/cookie behavior, cross-session read denial for every artifact type, cancellation, server restart, cleanup, quota handling, and the worker's denied external network access on the actual host. Public UI deployment alone does not pass these gates.

## Retention and recovery

Workspaces expire24hours after explicit actions. Automatic polling/preview reads do not extend retention. Expiry and DELETE block reads immediately. Active work is protected from physical deletion until its process tree stops; cleanup then removes inputs, arrays, masks, figures, exports and attempt directories. Files are not included in ordinary PoC backups.

Workspace expiry also invalidates the parent's heartbeat, the independent child
watchdog and final result publication. An active task cannot extend its lifetime
by renewing a lease after the workspace deadline. The supervisor stops and reaps
the process tree before releasing its lease; cleanup retains active files until
then. This also applies when an operator configures a shorter retention period.

Run `cytellect cleanup` manually if the worker was offline. Durable leases recover interrupted jobs with at most two automatic attempts; old workers cannot commit. A failed retry starts a fresh attempt; it does not overwrite a previous result. Inspect sanitized job error codes, not raw engine stderr.

Alembic upgrades execute under the SQLite write lock at startup, including adoption of the initial unversioned checkpoint. Deploy code/schema changes with API and worker stopped together. Do not automatically downgrade or copy live WAL files. Before any operator-approved schema recovery, use an offline, private, short-lived metadata snapshot and follow the workspace retention policy. Research-file backups are outside this PoC.

See [SECURITY](../SECURITY.md) for private vulnerability reporting.


## Watchdog and container verification

The parent and child both require a live fenced lease. Database/monitor errors
fail closed: the supervisor terminates the scientific process tree, retains no
published result and removes the private launch descriptor; the child watchdog
also terminates computation if it cannot verify the DB or parent identity.
A process-launch failure records only a fixed error code and releases the lease.
If the database remains unavailable, finite lease recovery handles the orphaned
job after its child has stopped. Linux attempts have dedicated process groups so
Fiji descendants are terminated even if the direct Python child exits first.
No raw subprocess output is retained. Uncommitted attempt artifacts stay on the
private volume and are removed by workspace-retention cleanup.

Container CI checks the real worker image as UID10001, root-filesystem read-only,
with a writable private `/data` volume, `network none`, no Linux capabilities,
and bounded memory/process count. It verifies loopback-only interfaces and a
denied outbound socket, then runs the actual pinned Fiji detector on known
synthetic pixels. This is infrastructure evidence, not scientific performance
on user images or acceptance of an Internet-facing production host.
