# Data protection and operations

This early prototype has local automated tests for invitation replay/revocation, Origin/CSRF, cross-session ownership, immutable versions, stale leases, job timeout/retry and expiry/deletion. These tests do not certify a hosted deployment. Run the acceptance checks on the actual analysis host before receiving private research data.

## Data boundaries

Unpublished research images, papers, filenames, conditions, masks, tables and plots stay outside Git, Cloud development, CI, external AI and public demos. The exceptions are the product's analysis proposal request and the operator-configured remote Cellpose inference service (both below). Public published images can be used for appropriate internal tests with recorded source and conditions. Only assets with a verified public redistribution basis belong in the public UI/repository; register hashes and attribution separately. Synthetic images remain numerical unit-test fixtures.

Browser uploads go directly to the analysis API. Disable Vercel image optimization, analytics/session recording, Service Workers and CDN caching for research content. API responses carry no-store. Every read checks the owning live session and workspace; IDs alone confer no permission. Do not log request bodies, filenames or token values. A field's display name (by default the last segment of its file name, as the workspace lists it) is stored with the field and appears in its figure labels, legends and Methods, so exported figures carry it; it is not sent to the proposal or Cellpose services.

## Analysis proposal service

The optional proposal service is off by default ([design](workspace-redesign.md#analysis-proposal-service-llm)). When the user enables it (each request carries `transmission_confirmed: true`, refused otherwise), the local API sends the stated goal and normalized metadata (channel names, dtype, dimensions, field/group counts, known pairing) to the Cytellect proposal service, which calls the OpenAI API with `store: false`. Representative previews (≤6, downscaled) are sent only after the user separately enables image transmission. Absolute paths, unneeded filenames, documents, masks and measurement tables are never sent. `store: false` does not mean zero retention: the provider may retain requests for abuse monitoring under its API data policy. The service stores invitation/device rights and usage counters only; it does not log prompt bodies or images. The operator key exists only as a service secret. Developer tools, CI and public repositories still never receive private research content.

## Remote Cellpose inference

An operator may point an installation at a remote GPU inference service
(`settings/cellpose-remote.json` on Windows; the client reads
`CYTELLECT_CELLPOSE_REMOTE_URL` and `CYTELLECT_CELLPOSE_REMOTE_TOKEN`); see
[cloud GPU](cloud-gpu.ja.md). The Docker worker keeps `network_mode: none`, so the
Docker deployment does not use remote inference until a reviewed network-enabled
worker profile exists. Only
Cellpose candidate detection is sent: the one detection plane, the adopted nuclear
labels for nucleolar protocols, and the detector parameters. Filenames, workspace
titles, conditions, paths and other channels are not sent. Binding to nuclei,
refinement, measurement and statistics remain local.

A Windows installation that signs in to the Cytellect cloud service keeps one device
token in `settings/cloud-account.json`, next to `settings/cellpose-remote.json` and
outside the research `data` directory, readable only by the OS user. The local API
never returns or logs it, sends it only to the base URL that issued it, and refuses
redirects. Signing out deletes it; explicit `CYTELLECT_CELLPOSE_REMOTE_*` settings
keep precedence over the signed-in service.

The PoC deployment (`infra/modal_cellpose.py`) is a Modal Server: per Modal, Server request and response payloads are proxied to the container and not stored, unlike Web Functions, whose inputs are kept up to 7 days. It uses no Volume or memory snapshot, requires a Modal proxy-auth token, runs at most one single-GPU container (L4 preferred, A10 as fallback) and is deployed only from `main` by a workflow whose deploy token is a repository secret. The workspace spend limit is set to zero in the Modal dashboard; deployment cannot change it. The GPU choice does not change the endpoint or token scope. The main residual risk is takeover of the Modal account or deploy token, which could replace the server with one that records inputs; the account uses GitHub sign-in with two-factor authentication and no other members.

The URL must be https (loopback http only for tests), without credentials, query or
fragment in it. The access token travels in the Authorization header and never
appears in errors. The service (`engines/cellpose/server.py`) holds request content
only in memory for the duration of the request, writes no files and logs no request
content, paths or client addresses. On Hugging Face Inference Endpoints, the provider
does not store payloads and keeps its own logs for 30 days. The client accepts a
result only when the service reports the release's runner, model and package-lock
hashes; otherwise it fails with `cellpose_remote_version_mismatch`.

## Installation and invitations

For local development set `CYTELLECT_DATA_DIR` to a private directory outside checkout, `CYTELLECT_APP_ORIGIN=http://localhost:3000` and `CYTELLECT_SECURE_COOKIES=false`. Run `uv run cytellect serve`, `uv run cytellect-worker` and `pnpm dev` in separate terminals.

For Linux containers create a dedicated private directory owned by UID 10001 with mode0700, set its absolute path in `CYTELLECT_RUNTIME_DIR`, then run `docker compose up --build -d`. The worker has `network_mode: none` and shares only the private local volume. SQLite must not live on a network share. Fiji/model acquisition happens during build, never in a job.

Use `uv run cytellect invite --hours 24` (or `docker compose exec api cytellect invite --hours 24`) from a private operator terminal. The CLI emits the one-use invitation once: do not pipe it into shared logs. Tokens are stored hashed; sessions use HttpOnly cookies. Logout revokes the session.

## Shared development environments

A development environment that other people can reach sets `CYTELLECT_UPLOAD_ALLOWLIST=fixtures/public/uploads.json`. The API then hashes every uploaded image or table after streaming it to the private volume and, unless its SHA-256 is in that list of registered public files, deletes it and answers `403 unregistered_upload`. This makes "registered public images only" a technical boundary rather than a convention. An empty or malformed list is a startup error, never "allow all". Installations leave the variable unset. The CI `fiji-browser` job checks that the prepared public inputs are still byte-identical to the list (`scripts/check_public_uploads.py`).

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

## Public-page analytics

Three public pages of the production site `https://cytellect.app` use the existing COMPASS official GA4 destination `G-EHKJ8B8N0Y` (no new tag or property): the landing page `/`, the public demo `/demo` (the workspace on registered public images, see [showcase](showcase.md)), and the analysis planning guide `/plan`. None of them accepts research images. Each page marks itself with `data-cytellect-public-page` and mounts a separate `/lp-metrics.html` document that owns the Google tag; the document checks the parent path against a fixed allowlist and is destroyed on leaving the page. The analysis workspace of an installation (`/workspace`, which the public build redirects to `/demo`), `/legacy`, the `/product` redirect, API-enabled builds, local installations, previews and development hosts do not load the tag. `/product` permanently redirects to `/`; the local package keeps its workspace at its own root. The main document CSP continues to exclude Google; only the metrics document permits the required Google script and collection hosts.

Each page sends its fixed canonical URL/title (`/` Cytellect, `/demo` Cytellect — Example analysis, `/plan` Cytellect — Analysis planning), the referring HTTPS origin (without its path/query), and allowlisted interaction names. No URL query/hash, link URL, user-entered text, filenames, study metadata, images, measurements or application state is included. The same-origin iframe separates lifecycle, not access permissions: it is not a sandbox against a compromised third-party script. Google may use analytics cookies for visitor/session measurement; advertising consent is denied and Google signals/personalization are disabled. Browser Do Not Track and Global Privacy Control suppress the tag. Blocking it never blocks the product links. There is no session recording.

Events: `page_view`, `download_click` (public Windows package link, not installation success), `download_section_click`, `example_click`, `planning_click`, `launch_help_click`, `workspace_click` (link from the LP to the analysis screen; a private workspace is never measured), `demo_step_click` (fixed `content_id`: demo_experiment/demo_image/demo_statistics/demo_figure, the demo's tab buttons), `demo_download_click` (the demo's download link), `demo_guide_click` (the demo's guide button, in the header and the phone menu), and `guide_click` (fixed `content_id`: guide/quickstart/methods/setup/figures). GA4's ordinary session/engagement events may also be produced within that isolated public document. Use Hostname = `cytellect.app` to separate these results from COMPASS; include `cytellect.vercel.app` as well when the period reaches back before the move to the custom domain on 2026-10-29. No cross-domain user stitching or shared-stream administration change is required for this addition.

Automated browser checks intercept the Google script and do not populate production reports. Production verification separately checks real tag/collection requests and absence of the tag after navigating away. A browser request is not proof that GA4 reports have processed the event; Realtime/DebugView confirmation requires access to that GA4 property.

## Docker Desktop owner access

The Desktop overlay enables `CYTELLECT_DESKTOP_OWNER` for the loopback-published
API (127.0.0.1:8001) and UI (127.0.0.1:3087). The private volume stores a stable
`local-owner` identifier across service restarts and browser session expiry.
The UI obtains a seven-day HttpOnly, SameSite=Strict session without an invitation;
opening the UI after expiry restores access as the same owner.

The bootstrap rejects foreign/missing Origin, Host, CSRF header, Fetch Metadata,
and forwarded headers. Docker's loopback port binding is part of this boundary:
never enable this adapter behind a public proxy or change its published bindings
to 0.0.0.0. Local OS users/processes are trusted, as in the Windows launcher.
Hosted invitation authentication is unchanged; this endpoint is absent by default.
Earlier invitation-owned workspaces are not silently reassigned. Research-data
expiry remains 24 hours after explicit use. Deleting the private runtime volume
also removes the persistent local owner.

### Explicit manual workspace retention

A researcher's own installation may select manual retention for all API/worker
processes: Docker Desktop through `CYTELLECT_WORKSPACE_RETENTION_MODE=manual`, the
Windows launcher through the setup choice saved as `settings/retention.json`.
Settings refuse manual mode unless the application origin is loopback, so a
hosted service keeps continuous TTL deletion. This is an explicit exception to the default workspace
24-hour expiry above, not to session/invitation expiry, ownership, lease fencing,
cancellation or deletion. Manual mode ignores workspace age for reads, queued
work, heartbeat/watchdog and final publication. Explicit DELETE still revokes
access immediately; active-lease protection still delays physical cleanup.

The database records the policy (`retention_policy`, migration 0010) and an empty
persistent marker in the private runtime volume repeats it. Either rejects a
subsequent TTL startup, and every TTL transaction rechecks the recorded policy, so a
lost marker cannot let a stale process expire retained work. On first activation,
workspaces whose TTL deadline already passed are marked deleted and removed by
cleanup; manual retention never revives them. Preserve the DB, marker and
artifacts together.
Stop all writers before changing installation policy; no live mixed-mode operation
or automatic manual-to-TTL conversion is supported. No timestamps are rewritten.
Private backups, capacity monitoring and manual deletion remain the lab's
responsibility; automatic age cleanup is not a storage-pressure fallback.
