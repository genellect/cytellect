# Analysis proposal service

Source for the optional LLM proposal described in [workspace redesign](workspace-redesign.md#analysis-proposal-service-llm). It is **disabled by default** and is not deployed by CI.

Use the [disabled deployment runbook](proposal-deployment.md) for pinned tooling,
remote D1 migrations, no-paid-call acceptance and rollback conditions.

```text
Browser → local API POST /v1/workspaces/{id}/proposal-drafts   {"goal": "…"} (optional)
            local API derives ProposalContext from the workspace
          → proposal service POST /v1/proposals   (Cloudflare Worker + D1)
            → Anthropic Messages API (redesigned prompt versions; the JSON Schema is described in the prompt, not forced)
              or OpenAI Responses API (installed clients' versions; Structured Outputs, store: false)
          ← draft → local semantic validation → ValidatedProposal (requires adoption)
```

## Components

| Part | Location | Responsibility |
|---|---|---|
| Contract | `packages/analysis/src/cytellect_analysis/proposal_contracts.py` | `ProposalContext` (what leaves the PC), `ProposalDraft` (what the model may return), strict output schema. Recipes, metrics, tests and references are closed enumerations; the exploratory clustered regression is not representable. |
| Validation | `proposal_validation.py` | For prompt `2026-11-26.1` ([#284](https://github.com/genellect/cytellect/issues/284) W7), an answer of `intent: answer` is valid whatever the workspace lacks, as long as it has text. A question's answer has no way to apply a setting, so validation leaves out any setting it carries instead of refusing the answer: the recipe becomes `none`; metrics, figures, analyses, processing, background, gate and figure presentation are emptied; each channel it lists keeps only the stain and role the workspace records (`unused` without a recorded role), and a channel the workspace does not have is dropped. Its text, `choices` and `assignments` are kept and checked as for any answer, and the text check reads the answer as the model wrote it. `run` needs a `scope` and an analysis; `choices` are at most 4 items of a question (≤200 characters) and 2–6 distinct one-line options (≤80); `assignments` name the context's field identifiers once each, with run and group names valid as design labels (1–24 characters, no `·`, no surrounding spaces or control characters) and at most as many groups as the design has (two without one). Otherwise it rejects unknown or unacquired channels, stains asserted for index-only tokens, changed stains, NCL metrics without NCL, corrected intensity without background, inference without independent units, paired tests without pairing, missing omnibus for ≥3 independent conditions, figures of unproposed metrics, duplicate references and any URL/code/macro text. The explanation (`rationale`, channel `reason`, `missing_information`) has no length or count limit since 2026-11-17 ([redesign §8](drafts/llm-assistant/plan.md)). Lists tokens whose suggested role still needs the researcher's confirmation. |
| Local route | `services/api/src/cytellect_api/proposals.py` | Owner-checked `POST /v1/workspaces/{id}/proposal-drafts`. Inputs are an optional goal sentence and `transmission_confirmed`, which must be `true` (428 otherwise): the UI shows what is sent and asks once, and the API refuses to send anything without it. Redirects from the service are refused so the device credential is never re-sent elsewhere; channel tokens, recorded stains, field and condition counts and the unit/pairing/region/table/background flags are derived from the workspace. Returns the validated draft and the token → channel mapping; 409 without images; 503 `proposal_service_disabled` unless configured; reuses an identical validated draft (durable, private, per workspace) without another call; returns rejection codes only. |
| Service | `services/proposal-worker/` | E-mail login → user-bound device token ([cloud access](#cloud-access-e-mail-login-approval-and-gpu-gateway)), invitation tokens during migration, per-device monthly request quota, per-user and monthly budget reservation before every call, one repair call at most, `store: false`, no logging of bodies. The same Worker relays GPU inference to Modal. |
| Result discussion | `discussion_contracts.py`, `discussion_context.py`, `discussion_validation.py`, `services/api/src/cytellect_api/discussions.py` | Protocol `result-discussion/1.1.0`, prompt `2026-11-16.1` (protocol 1.0.0 from installed clients keeps its prompt `2026-11-12.2`) ([requirements AC-01–AC-09](drafts/results-and-demo-story/requirements.md#c-考察ac), L07, L08). Owner-checked `POST /v1/jobs/{job}/discussion` on one saved two-group comparison with estimates, and `GET` of the stored discussion. Sends the context the discussion needs, as the workspace shows it: the summary's heading and points (`summary`, sent by the page), the metric with its name and definition, the region and its name, stain and channel label, the researcher's group and run names, values, intervals, n with its breakdown (`counts`), the recorded method (`method`), test, p value, warning codes, and the researcher's purpose (by default the goal last written to the AI in the workspace), cells and stain names. Images, file names and paths are not sent. `transmission_confirmed` is required (428). The draft is shown as written once it has the three headings; its numbers, wording, references and length are not checked and no note is added (2026-11-17, [redesign §8](drafts/llm-assistant/plan.md)). It is stored with the result job, model and prompt version. Same service, credential, reuse, explicit retry and failure codes as proposals. The service route `POST /v1/discussions` (`services/proposal-worker/src/discussion.ts`) uses the same device token, per-device and per-user quotas, budget reservation, one repair call at most and `store: false`; its schema is generated into `contract.json` (strict output for OpenAI; described in the prompt for Claude). The public demo never calls it: it shows mock discussions marked as examples (AC-08). Production calls the model since 2026-11-16 (AC-09), when the owner permitted deploying and enabling it; since 2026-11-17 the 2026-11-16.1 prompt is answered by Claude Sonnet 5.5 ([deployment record](proposal-deployment.md#production-deployment-record)). |
| Shared schema | `services/proposal-worker/src/contract.json` | Generated by `uv run python scripts/proposal_schema.py`; CI fails when stale. |

The researcher is never asked to fill in this context. The local API builds the `ProposalContext` (1.3.0 for prompt `2026-11-26.1`, 1.2.0 for any earlier prompt an operator pins; [LLM assistance redesign](drafts/llm-assistant/plan.md)) sent to the service from the workspace: goal (≤2,000 characters), channel tokens with their labels and recorded stains (roles only where a recipe records them), every field's name and records (condition, experimental unit, pair, acquisition date; up to 200 fields), from 1.3.0 each field's opaque identifier (`f1`, `f2`…; the response's `fields` maps them to the workspace's fields), the names its files were added with (at most four, from the selection row's `intake.names`, as paths that start at the chosen folder's own name; a name that looks absolute, or that starts at a users' folder (`Users/…`, `home/…`), is reduced to its file name) and its run and group, and the experiment design's layout and run and group names, field count, condition count and whether units, pairing, supplied regions, a measured table and an established background exist. Locations on the PC (the path above the chosen folder), measurements and masks are not part of the contract (extra fields are rejected). With each request it also sends up to six display-scaled PNG previews (`previews`, ≤512 px, one per channel) of the selected or first native field, unless the researcher turned previews off in the account settings (`include_previews`). A label suggests a stain only; a stain is established by the recorded stain. Prompt `2026-11-16.1` keeps the latest rules and schema and adds how to read these records and previews; prompt `2026-11-19.1` (the local API's default since 2026-11-19) adds `figure_presentation`, the main figure's composition and the legend facts the workspace does not record (cell line, treatment, stains), with its own schema (`figure_draft_schema`); the workspace offers them for adoption and never takes a number from them ([publication figures](drafts/publication-figures/plan.md) FM). The service must be deployed with `2026-11-19.1` before a release that sends it; the service sends it to Claude when Claude is configured (`CLAUDE_PROMPT_VERSIONS`) and to the OpenAI model otherwise. Prompt `2026-11-26.1` (the local API's default from #284 W7) adds the kind of request with its own schema (`intent_draft_schema`): `intent` (`answer` for a question, a request to wait, or a request to split fields into runs or groups, answered from the context with what needs confirming; `settings` for a change of analysis conditions; `run` only when the researcher asks to measure or run now), `answer`, `scope` (`selected`, `all`), `choices` (question and options, each option written as the researcher's next message) and `assignments` (field identifier, run, group). The text the researcher reads (`answer`, `rationale`, each missing item and channel reason, and the questions and options of `choices`) uses the workspace's words: a channel by its label (or its recorded stain without one), a field, a run and a group by their names, 視野, 実験回 and 群, and a recipe or a measurement described in words; tokens, identifiers, context key names and schema words stay in the JSON fields that require them. `answer` describes what `assignments` holds, and says so when a run is a provisional name because nothing names the runs. 「まだ測定しないで」 does not decide the kind: with a question it is an `answer`, with a change of conditions it is `settings` (applying settings measures nothing), and it is never `run`. A request to split fields is an `answer` whose suggestions go in `assignments`, with no analysis drafted. A stain or a role proposed in reply to a question is written in `answer` with its reason and offered in `choices`, never in the settings fields. `intent` only chooses the actions the workspace shows; the answer never changes settings or runs anything (decision 4 of the #284 plan). Reply text is `answer`, then `rationale`, then each missing item. Context 1.3.0 is accepted only with `2026-11-26.1`; the Worker must be deployed before the client ([order of releases](proposal-deployment.md#order-of-worker-and-client-releases)). Installed clients' prompt versions stay on the OpenAI model, and the local API accepts any model in `PROPOSAL_MODELS` and stores the one that answered.

## Availability and settings in the workspace

The authenticated `GET /v1/ai/status` reads only local configuration and the installed account credential. It returns `state` (`available`, `sign_in_required`, `unconfigured`, or `misconfigured`) and `source` (`operator`, `account`, or `none`), never a token or service URL. It makes no service or model request and does not verify provider uptime, quotas, or prompt compatibility. Explicit operator configuration takes precedence over an installed account. The Windows account's sign-in/approval state also controls whether the screen enables sending.

The AI panel's **AI の設定** is available in Windows, Docker, and development. It repeats both transmission scopes and offers the representative-preview setting. Windows users follow sign-in. Docker operators first obtain an owner-issued invitation and redeem it once for a device token (steps 6–7 under [operator deployment](#operator-deployment-not-performed-by-these-prs)); they keep the token in a file outside the repository and use `docker-desktop.ps1 Start -ProposalConfig` ([Docker setup](docker-desktop.md#解析提案と考察の有効化)). Compose passes it as `CYTELLECT_PROPOSAL_TOKEN_FILE=/run/secrets/proposal_device_token`, not as a plaintext token environment variable. Development operators use their private environment's URL and token/token-file settings. After restart, refresh local availability. Credentials are not entered into browser settings; this does not add e-mail login to Docker.

The optional **サービスの対応を確認** action calls authenticated `POST /v1/ai/check`. It sends public protocol sentinels to the configured service without Idempotency-Key and accepts only the stop before request admission. It checks both the configured prompt versions, distinguishes incompatible requests and authentication from unavailable service, and returns only a fixed state. It sends no workspace data and never runs from a status read or page load. The same implementation is used by the distribution check. A failed explicit check disables sending until the setting is refreshed or the check succeeds; refresh clears a stale check. It does not test model output quality or guarantee later service uptime.

Discussion scope and optional purpose are shown before the single **考察を生成** action, including first use. Opening a result never generates automatically. The authenticated `GET /v1/jobs/{job}/discussion-history` returns `current` separately from the most recent earlier stored discussion of the same workspace, measure/channel, groups and stratum. Recalculation shows **前の結果の考察** and offers generation for the new result. A redrawn figure uses its source comparison. These reads work with AI disabled and make no model request.

## Protocol 1.1 and durable local reuse

The Sol integration uses protocol `1.1.0`, model `gpt-6.1-sol` and prompt
`2026-10-06.1`. Area and intensity selections identify their measurement region;
association proposals identify both axes, and figures reference the corresponding
analysis index. A proposal can include one primary and up to three additional
analyses. These remain drafts, not executable statistical confirmations. Native
NCL compartment ratios require a confirmed background; the measurement engine
still separately checks positive corrected means. Multi-condition paired designs
are rejected until an explicit supported contrast is selected. No equation changes.

A service that does not accept the client's prompt version is reported as
`proposal_service_version_mismatch`. A failed or timed-out instruction is not sent again automatically:
an older service rejecting the current request schema reports `proposal_service_request_incompatible`,
with the same service-update guidance. Known rejections before a model call (disabled or invalid local
configuration, authentication, quota admission, unsupported prompt, invalid request schema) are stored
as `unbilled`; a later user-initiated send after the cause is fixed does not require a paid retry.
An unknown failure, timeout, malformed answer, or mismatched answer version remains potentially billed:
the researcher may send the same instruction, read the cost notice, and explicitly choose to resend it
with `retry_failed: true`. Cancelling sends nothing. The confirmation appears once, without a second copy
in the workspace error banner. Error messages cover both proposals and discussions and do not name a
particular model provider. These behaviours implement LP-02–LP-04 of [#249](https://github.com/genellect/cytellect/issues/249).

The context uses opaque channel tokens rather than research-defined IDs, includes
anonymous independent-unit counts per condition and complete-pair counts, and
checks the whole image cohort. Unknown stain identity does not prevent generic
raw measurements; only a new detector-defining nuclear role needs confirmation.
Backgrounds and metadata come from the active saved snapshot, never any historical
revision. Mixed input modes or incomplete channel coverage require cohort correction.
The minimum unit counts are computational prerequisites, not a claim of adequate
statistical power or confirmed biological independence.

Each message the researcher sends is kept (#284 W2, migration `0013`, `assistant_messages`): its text,
the selected field, its state (`pending`, `answered`, `failed`), the answer, whether it can be applied,
the reason codes and the stage that stopped it (`context`, `service`, `validation`), and what the
researcher did with it (`effect`: `none`, `settings`, `run`). `GET /v1/workspaces/{wid}/assistant-messages`
lists them in order and `PATCH /v1/workspaces/{wid}/assistant-messages/{id}` records the effect (only for
an applicable answer). A message is made for every request that reaches the model or the cache, and for one
the workspace context refuses; none is made without the transmission confirmation, for a request already in
progress or for one that needs an explicit resend. A resend names its message (`message_id`) and reuses it.
When the model's draft is well formed and its text passes the text check but its settings are refused, the
route answers 200 with `proposal: null` and the message carries the answer (`rationale` and
`missing_information`), `applicable: false` and the reasons; a malformed draft or a refused text keeps only
the reasons and the route answers 502 as before. The workspace shows the answer, and the reason codes in two
kinds: something the researcher changes, with the place to change it, or a service-side failure, with 「再送」.
Sending never changes settings or runs anything; applying is the researcher's action (requirement L02). After a
reload the messages and answers are shown again without a model call; applying a reloaded answer resends its
message, which the cache answers without the model when the context is unchanged. A question's answer
(`intent: answer`) has no settings, and neither has an answer without an analysis (recipe `none`, no processing:
it only names a stain or a role, which the researcher records in the workspace): its message carries
`applicable: null` and offers no application.
The listing carries the text of an answer, not its items to confirm or its run and group suggestions. Each
message therefore says whether the proposal recorded for it holds any (`restorable`, read from the draft the
message points to; false without one). For such a message the workspace offers 「再送」 after a reload: for
items to confirm as the latest message, where they are offered, and for run and group suggestions
(`suggests_assignments`) from any message, since the experiment table shows them. The resend is answered from the record when the request is the same as
the one recorded; a message that continued an earlier proposal, or a workspace whose context has changed since,
is another request and calls the model, so the workspace asks before any resend.
The text of messages and answers stays in the workspace database and is never logged.

Private SQLite migration `0003` stores validated drafts and atomic request claims
under the workspace. Reuse survives restart and is invalidated by local input/design,
recipe, protocol, model, prompt, or service changes. Presentation changes alone do
not trigger a new proposal. Cached responses still require live workspace ownership
and transmission permission; deletion/expiry blocks access and retention cleanup
removes the stored proposal. Drafts never imply adoption or overwrite confirmations.

Concurrent requests return `proposal_request_in_progress` rather than incur another
call. A timed-out or interrupted request requires explicit `retry_failed: true`;
that new user action receives a new UUID. Transport resends must not invent new
UUIDs. Worker idempotency prevents duplicate charges for an already submitted UUID.
Response model/prompt provenance must exactly match the local configuration.

### Reporting generated content

The workspace links to the developer's contact form from an AI analysis proposal and from a model-generated discussion shown with a saved result. Opening the form sends no prompt, generated text, images or workspace identifiers. The user decides what to submit in the form. The product owner reviews incoming reports and takes action on confirmed inappropriate output.

## Cloud access: e-mail login, approval and GPU gateway

Status: implemented, tested locally and deployed to the production Worker (in
production at least since 2026-10-30, [deployment record](proposal-deployment.md#production-deployment-record));
the unverified paths are listed under [status and limits](#status-and-limits). It follows the draft plan
for one-click Windows access (requirements A1–A6, C1–C3, C5). The owner's
decisions below are **provisional** until the plan is approved:
mail is sent with Resend from `MAIL_FROM`; per-user monthly defaults are GPU
3,600 seconds and proposals USD 5; a device login expires after 90 days unused;
the owner can both pre-register addresses and approve requests.

An installation signs in once with an e-mail address and a 6-digit code. Only
addresses the owner allowed receive a code; any other address becomes an access
request, and the owner receives one approval link. The device token from the
login is the only credential the PC holds. The Worker alone holds the Anthropic,
OpenAI and Modal keys.

JSON bodies; addresses are trimmed and lowercased. Errors are `{"error": "…"}`.

| Route | Result |
|---|---|
| `POST /v1/auth/code {email}` | `{"state":"code_sent","retry_after_seconds":60}` for an allowed address (code valid 10 minutes, stored only as a keyed hash); `{"state":"pending_approval","request_token":"…"}` otherwise (request recorded, no code sent; the token is random, stored only as a hash, valid 14 days and good only for the next route); `{"state":"revoked"}`. 429 `rate_limited` with `retry_after_seconds` (see [limits](#login-limits)). 503 `mail_unavailable` without a mail sender; 502 `mail_failed` if sending fails |
| `POST /v1/auth/verify {email, code, device_name?}` | `{"device_token","email","expires_at"}`. 400 `code_invalid` with `attempts_left`, `code_expired` (also when no code is active) or `too_many_attempts` (the 5th wrong code voids it). 429 `rate_limited` while the address is locked. `device_name` is accepted but not stored |
| `GET /v1/auth/status` (Bearer) | `{"state":"allowed","email","limits":{"gpu_seconds_month","proposal_usd_month"},"usage":{"gpu_seconds","proposal_usd"},"resets_at"}`. 401 `auth_required` (missing, unknown, expired or logged-out token); 403 `revoked` |
| `POST /v1/auth/request {request_token}` | `{"state":"pending_approval"\|"allowed"\|"revoked"\|"none"}` for the request the token was issued for, so the PC can show that it was approved without a login. Unknown, malformed or expired tokens return `none`. The address never appears in a URL, and no other address's state can be read. Rate-limited per IP (/64) |
| `POST /v1/auth/logout` (Bearer) | 204; the token is deleted |
| `GET /v1/cellpose/health`, `POST /v1/cellpose/` and `POST /v1/cellpose/v1/cellpose` | GPU gateway: the Modal server's routes (`GET /health`, `POST /`, `POST /v1/cellpose`) under the `/v1/cellpose` prefix, so the PC can use `<base>/v1/cellpose` as its Cellpose service URL unchanged |
| `POST /v1/proposals` | Unchanged request and response; also accepts login tokens (below) |

The gateway requires an allowed user's device token and remaining GPU time, then
forwards to the `MODAL_URL` secret with `Authorization: Bearer <MODAL_PROXY_TOKEN>`.
Request and response bodies are streamed unchanged; only `Content-Type`, `Accept`
and `Content-Length` go upstream, and only `Content-Type`, `Content-Length` and
`Retry-After` come back. Upstream statuses, including 503 while the GPU starts,
are returned unchanged for the client to retry. Elapsed wall time from forwarding
to the upstream response (rounded up to whole seconds, health checks included)
is added to the user's monthly GPU usage. The Modal server runs one container
that serves one request at a time, so this time also includes waiting behind
other users' requests and the container's start-up.

Every GPU request, an inference (`POST`) or a health check (`GET /v1/cellpose/health`),
is admitted in one D1 statement and takes the user's single slot, so each user has
at most one GPU request in flight. A request while the user's slot is taken is
answered at once, without the upstream, with `Retry-After: 5`, which the client
retries like a starting GPU:

| The user's request in flight | Answer to another request of the same user |
|---|---|
| An inference | 503 `{"error":"gpu_busy","retry_after_seconds":5}` |
| A health check | 503 `{"error":"gpu_starting","retry_after_seconds":5}` |

Admission needs user time left, and room for one inference (300 seconds) after the
global total and the holds of every other request in flight; otherwise both kinds
get the same 429 with `scope` and `resets_at`. An admitted inference then holds
300 seconds, a health check 30 seconds (its 25-second deadline plus rounding; its
counted time is capped at 30 seconds). So an inference needs at least 300 seconds
of the global cap left; a personal limit is exceeded by at most the one request
that started before it was reached; and the global cap only by an inference that
runs longer than 300 seconds. A health check waits at most 25 seconds; during a
longer cold start it returns 503 `{"error":"gpu_starting","retry_after_seconds":5}`
and the client asks again. Its slot is released when it ends, or expires after
60 seconds.

When a request ends (an inference with an answer, or any health check), its elapsed
time is added and its slot released in one D1 transaction. If that transaction fails, both are kept as they
were: the slot stays and counts as a hold until it expires (35 minutes after the start
for an inference, 60 seconds for a health check), and the Worker logs only the fixed text `gpu_usage_record_failed`. The
answer is still returned.

The Worker runs with the `enable_request_signal` compatibility flag, so a client
that disconnects aborts the upstream call at once. The Modal server still finishes
an inference it has accepted, so a disconnected inference is counted as 300 seconds
(or its elapsed time, if longer), and its slot stays until 300 seconds after the
start (or the disconnect, if later): meanwhile that user's next inference gets
`gpu_busy`. Sending long inferences and disconnecting therefore cannot use the GPU
for less than it is charged, unless one inference runs beyond 300 seconds after
its client left. The Worker does not wait for the upstream answer after a
disconnect (`waitUntil` allows only 30 seconds); it uses `waitUntil` only to finish
this accounting step. A health check that ends by a disconnect
counts its elapsed time. Only a Worker stopped without the signal (for example a
runtime restart) leaves a slot behind; it stops blocking after 35 minutes, and that
request's GPU time is not counted.

Errors: 401 `auth_required`, 403 `revoked`, 429
`{"error":"quota_exceeded","resets_at","scope":"user"|"global"}`, 503 `gpu_busy` or `gpu_starting`,
411/413 for a missing or excessive `Content-Length`, 502
`gpu_upstream_unreachable`/`gpu_upstream_invalid` (a redirect is never followed),
503 `gpu_service_disabled` unless the secrets and a positive `GPU_MONTHLY_SECONDS`
are set. Invitation tokens are not accepted by the gateway.

For proposals, a login token is checked first: 401 `{"code":"unauthorized"}` when
expired, 403 `{"code":"revoked"}` when revoked. The worst-case reservation must fit
both the monthly budget and the user's monthly limit (settled cost plus the user's
outstanding reservations); otherwise 429 `{"code":"quota_exceeded","resets_at"}`.
Settlement adds the accounted cost to the user's usage in the same transaction.
Invitation tokens keep working while `LEGACY_INVITATIONS` is not `"false"`;
they are bound to no user and count only against the global budget.

Months are UTC calendar months. Revocation takes effect on the next request of
every device that logged in with that address; re-allowing a user requires a new
login. Invitation tokens are bound to no user, so revocation cannot reach them:
while `LEGACY_INVITATIONS` is on, a person who also holds one can still request
proposals with it. Set `LEGACY_INVITATIONS="false"` for a hard stop (or set
`revoked_at` on that device record). The owner's address is always allowed and
cannot be revoked.

<a id="login-limits"></a>**Login limits.** Counters are keyed hashes of the
address or the client IP; an IPv6 client counts by its /64 prefix. Each counter is a fixed
window that starts at its first hit and resets when it ends; it is not a sliding
window.

| Limit | Value |
|---|---|
| Code requests (`/v1/auth/code`) | 20 per hour per IP; 6 per hour per address; 60 s between codes. A request during those 60 s gets `retry_after_seconds`: it counts against the IP but not against the address |
| Device codes sent | 10 per day per address, whatever the requesting IP |
| Admin codes sent to the owner (only while Cloudflare Access is not configured) | 5 per hour and 10 per day; 10 admin code requests per hour per IP, counting requests during the owner's 60-second resend interval (those get `retry_after_seconds` and send nothing) |
| Code checks | 30 per hour per IP (admin: 20); at most 5 candidates are compared against one code. Each check claims its attempt before the comparison, so requests that arrive together cannot exceed the 5; the fifth wrong guess voids the code |
| Invitation redemption (`/v1/devices`, while `LEGACY_INVITATIONS` is on) | 10 per hour per IP. The counters are keyed hashes like the login's: with `ADMIN_SIGNING_KEY` when the e-mail login is configured, otherwise with `ADMIN_TOKEN`, so an installation that only uses invitations (steps 1–7 below) keeps working. They live in the `rate_limits` table of migration `0004` (step 2 applies every migration). Without the database or either key the route answers 503 `auth_unavailable` |
| Wrong codes per address | 20 within a day lock that address for 24 hours (device and admin separately). The lock also voids the current code and stops new codes |
| Access requests | 240 request-state checks per hour per IP; 20 owner notices per day in total |

`/v1/auth/code` answers with the address's state (`code_sent`, `pending_approval`
or `revoked`), because the PC shows the matching screen. This is an accepted risk:
anyone can learn whether an address is allowed, waiting or revoked, at most 20
addresses per hour per IP (/64) and 6 requests per hour per address
([data protection](security.md#analysis-proposal-service)).

Rotating IP addresses therefore adds neither codes nor guesses for one address: an
attacker gets at most 20 wrong guesses per address per day (a one-in-50,000 chance). The limits can be used against a person, without any code: anyone can lock an
address for a day by guessing wrong, or use up its daily codes (10 requests for
the owner's admin login without Cloudflare Access, or for a researcher's address) so that no code reaches it until
that window ends, up to about a day. Rotating `ADMIN_SIGNING_KEY` ends every lock and
counter at once, and also voids pending codes and approval links.

**Owner operations.** When `ADMIN_ORIGIN` is set, `/admin` and `/v1/admin/*` answer
only on that origin (404 elsewhere, 503 `admin_origin_invalid` if it is malformed), and
approval e-mails link there. When `ACCESS_TEAM_DOMAIN` and `ACCESS_AUD` are set
(production), the owner signs in with Google through Cloudflare Access, and the Worker
itself verifies the `Cf-Access-Jwt-Assertion` token on every admin path, the approval
link and the legacy invitation route included: signature, issuer, audience, expiry and
the owner's address. Without a valid token those paths are refused, however the request
reached the Worker; the e-mail code login for `/admin` is then off and
`/v1/admin/session/*` answers 404. A half-set or malformed Access configuration, or
Access without `ADMIN_ORIGIN`, answers 503 `access_config_invalid` there
([deployment](proposal-deployment.md#owner-sign-in-through-cloudflare-access)).
While Access is not configured, the owner opens `/admin`, enters `OWNER_EMAIL` and the
code sent there (a 12-hour session cookie; codes for other addresses are never sent).
The page lists users with state, monthly usage and limits; it approves requests,
pre-registers addresses, revokes, and sets per-user limits (blank = default).
An approval e-mail links to `GET /v1/admin/approve?t=…`: a signed (HMAC with
`ADMIN_SIGNING_KEY`), single-use token valid for 7 days. Opening the link shows
the address and one **承認する** button, so mail scanners that follow links cannot
approve. Approval e-mails the requester that the cloud features are available. At
most 20 request notices per day reach the owner; further requests remain listed on
the page.

**Stored data.** Migration `0004_cloud_access.sql` adds `users` (address, state,
optional limits, request/notice/approval/revocation times), `login_codes` (keyed
hash, expiry, attempts), `user_devices` and `admin_sessions` (token hashes and
times; admin sessions only from the e-mail code login), `approval_links` (hash, expiry, use time), `request_tokens` (hash, address, expiry), `rate_limits` (keyed hashes of
addresses and IPs with counters and lock times), `gpu_slots` (address, kind,
held seconds, start and expiry time of a GPU request in flight) and `user_usage` (GPU seconds and proposal cost
per user and month). Images, goals, prompts, outputs, device names and request
bodies are not stored or logged.

## Operator deployment (not performed by these PRs)

Requires the operator's Cloudflare account and a model-provider account (Anthropic, and OpenAI while installed clients use it). No paid contract is implied by this source.

1. `cd services/proposal-worker && cp wrangler.toml.example wrangler.toml`.
2. `wrangler d1 create cytellect-proposal`; put its ID in `wrangler.toml`; `wrangler d1 migrations apply cytellect-proposal --remote`.
3. `wrangler secret put OPENAI_API_KEY`, `wrangler secret put ANTHROPIC_API_KEY` (for redesigned prompt versions) and `wrangler secret put ADMIN_TOKEN` (random, ≥20 URL-safe characters).
4. Keep `OPENAI_MODEL=gpt-6.1-sol` and `REASONING_EFFORT=medium`. For Claude, set `ANTHROPIC_MODEL` (`claude-opus-5-5` or `claude-sonnet-5-5`) and its four tariffs (`ANTHROPIC_PRICE_INPUT_USD_PER_MTOK`, `ANTHROPIC_PRICE_OUTPUT_USD_PER_MTOK`, `ANTHROPIC_PRICE_CACHED_INPUT_USD_PER_MTOK`, `ANTHROPIC_PRICE_CACHE_WRITE_USD_PER_MTOK`), each at least the model's standard tariff; without them redesigned versions also use the OpenAI model. `ANTHROPIC_MAX_OUTPUT_TOKENS` (1,024–16,000) sets Claude's own output ceiling, which includes its thinking; empty uses `MAX_OUTPUT_TOKENS`. Each model call times out after 120 seconds, so an initial and a repair call fit the local API's 300-second request. After explicit operator budget approval, set all four tariffs (`PRICE_INPUT_USD_PER_MTOK`, `PRICE_OUTPUT_USD_PER_MTOK`, `PRICE_CACHED_INPUT_USD_PER_MTOK`, `PRICE_CACHE_WRITE_USD_PER_MTOK`), `MONTHLY_BUDGET_USD` and `DEVICE_MONTHLY_REQUESTS`. Missing values keep billable calls disabled (503). `low` requires `LOW_EFFORT_EVALUATED=true` after equivalent evaluation; it is not the default. The example output ceiling is 8,000 tokens including reasoning and visible JSON, subject to public-case evaluation rather than a quality guarantee.
5. `wrangler deploy`. Keep Workers observability/log persistence off for request bodies.
6. Issue an invitation: `POST /v1/admin/invitations?hours=24` with `Authorization: Bearer <ADMIN_TOKEN>`. Give it privately to the installation owner, who redeems it once with `POST /v1/devices {"invitation": "…"}` to obtain a device token.
7. On the PC, set `CYTELLECT_PROPOSAL_URL=https://…` and `CYTELLECT_PROPOSAL_TOKEN=<device token>` for the local API. HTTPS is required except for `127.0.0.1`/`localhost` testing.
8. Cloud access (e-mail login, approval, GPU gateway) needs migration `0004` and the secrets and variables in the [deployment runbook](proposal-deployment.md#cloud-access-login-approval-and-gpu-gateway). Until then, steps 6–7 remain the way to authorize an installation.

Local `CYTELLECT_PROPOSAL_MODEL` and `CYTELLECT_PROPOSAL_PROMPT_VERSION` default
to the selected Sol model and `PROPOSAL_PROMPT_VERSION` in `proposal_contracts.py`
(`2026-11-26.1`), and must match the deployed Worker.
`CYTELLECT_PROPOSAL_TIMEOUT_SECONDS` defaults to 300: this is an upper deadline,
not a predicted wait, and covers at most two 120-second provider requests. An
incomplete model answer is classified separately and never automatically repeated
with the same exhausted output ceiling. Provider refusal and invalid output also
remain distinct from service unavailability.

Budget control reserves a conservative input/output ceiling for up to two calls
only if `spent + unsettled reservations + reservation ≤ budget` in one statement.
Usage settlement records model, prompt version, input/cached-input/output tokens
and calls. Noncached input is provisionally priced at the higher cache-write tariff
until its actual billing breakdown is confirmed: this ledger is conservative and
is not an invoice. Failures or absent usage are retained at the reserved amount.
Unsettled reservations continue counting after interruption and require reconciliation
with provider billing; do not routinely delete them to restore quota. D1 migration
`0002_usage_integrity.sql` adds request idempotency and usage evidence. The same
device/request UUID returns 409 rather than initiate another paid request; no research
prompt or answer is stored remotely. D1 SQL is tested locally using `node:sqlite`;
remote D1 execution remains a separate deployment check.

## Development environments

A development environment that runs the installation's stack
(`python3 scripts/dev.py serve`, see [CONTRIBUTING](../CONTRIBUTING.md#外部サービス))
is enrolled like any installation, with its own device token:

1. The operator issues an invitation from their own machine or the owner's cloud
   environment ([CONTRIBUTING](../CONTRIBUTING.md#オーナーの環境), step 6 above) and redeems it
   once with `POST /v1/devices`. Neither the admin token nor the device token is pasted
   into chat, commits, issues or logs.
2. The operator stores `CYTELLECT_PROPOSAL_URL` and `CYTELLECT_PROPOSAL_TOKEN` in the
   environment's secret settings (for Claude Code cloud sessions: the environment's
   variables, read by new sessions). `serve` passes them to the local API unchanged.
3. Open **AI の設定** and choose **サービスの対応を確認**. This checks the device and
   the actual prompt/request format without model admission or a reservation.
   The normal status refresh checks configuration only. `doctor --live` remains
   an authenticated empty-request check; `400 request_invalid` there does not prove
   prompt compatibility.

Each development environment counts against the same monthly budget and its own
`DEVICE_MONTHLY_REQUESTS`. Test proposals use registered public images only. To
stop an environment, the operator sets `revoked_at` on its device record in D1
(there is no revocation endpoint for invitation tokens; login tokens are revoked on
`/admin`); deleting the environment variable alone leaves the token valid.

## Model evaluation before enabling

The fixed public scenarios in `src/public-cases.ts` cover BBBC013 DRAQ/FKHR-EGFP,
4DN DAPI/NCL, BBBC039 Hoechst, unknown channels/units, paired and multigroup designs,
and unsupported requests. `pnpm --dir services/proposal-worker eval:public` normally
skips billable calls. An operator-approved run needs `CYTELLECT_ALLOW_PAID_PUBLIC_EVAL=true`,
`CYTELLECT_PUBLIC_EVAL_BUDGET_USD` (positive, at most $20), and the private API key;
`CYTELLECT_PUBLIC_EVAL_REPEATS` is 1–3 (default 3), effort defaults to `medium`.
The harness uses the actual adapter and Python semantic validator. Evaluate useful
correct proposals as well as refusal: rejecting everything cannot pass. Record latency,
tokens and correct usable recipes/axes/figures. No live evaluation is implied by a
passing offline test. Never invent stains or biological independence. Re-evaluate
after prompt/model changes before enabling a lower effort setting.

## Input principle

Ask only what cannot be derived, only when it is needed, once for the whole set, with a default already filled in. The goal sentence is optional. The next step lets the model turn the goal (for example, "three independent experiments comparing treated and control") into a suggested condition/unit assignment from folder and file-name candidates, shown on one confirmation screen; without the service the same screen is filled from those candidates alone. Units are never adopted without that single confirmation.

## Status and limits

- Implemented and tested locally: contract, validation, durable local route, Worker logic, offline public-case checks and actual D1 SQL via SQLite. Live Sol evaluation and remote Worker/D1 checks remain release gates.
- The owner's Cloudflare Access sign-in is tested with RSA keys generated in the test and a fake certs endpoint; sign-in through a real Access application and Google remains unverified.
- Cloud access (login, approval, admin page, quotas, GPU gateway) is tested with fake mail and a fake Modal server. Delivery through Resend, forwarding of an actual ~5 MB Cellpose request to Modal, and the PC's login screen remain unverified.
- The workspace connects explicit AI requests to validated processing settings and a representative-field trial. Preview transmission and device-token registration from the application remain separate work; the configured local service currently sends metadata and the bounded continuation described below.
- Draft reuse is persisted privately across restarts. Only an executed recipe produces a scientific revision; reading a stored draft does not restart analysis.
- `store: false` is not zero data retention; see [security](security.md#analysis-proposal-service).
- Result discussions: the contract, the structure check, local route, Worker route, prompt and workspace panel (`DiscussionPanel.tsx`: 「考察を生成」, what is sent, the purpose starting from the AI goal, the screen's summary, the frame naming the model and day) are implemented and tested with a stand-in model. Not implemented yet (requirements L07, L08): the one line on how to enable the service for users without it (the panel shows the service's failure message after the request), the scope in the settings, and marking a recalculated result's earlier discussion as 「前の結果の考察」 (a recalculated result shows none). A stored discussion with `origin: "example"` is shown as the demo's example, not a model's output; the demo's examples are added with the demo scenes. With the owner's permission, the route was deployed and enabled in production on 2026-11-16 (AC-09) and checked with one paid call on a public comparison ([deployment record](proposal-deployment.md#production-deployment-record)). Up to 0.1.0-local.23 the context accepted a unit of at most 20 characters, so comparisons with longer units, such as positivity rates, got no discussion; protocol 1.1.0 accepts any unit.
# Structured execution settings (2026-10-07)

Prompt `2026-10-07.1` adds optional `processing` version `1.0.0` to the
validated draft. This is a settings contract, not a new segmentation algorithm.
It uses the actual registered StarDist, nucleolar and positive-pixel detector
models and their bounds. The local validator checks channels, roles, nuclear
parent requirements and marker identity. Unknown channel numbers do not establish
DAPI, GFP, NCL or a nucleolar marker.

Following an explicit AI request, the UI applies validated settings and runs one
representative-field trial, retaining the existing workspace behavior. Unknown
nuclear channel roles wait for the researcher to select the channel. The trial
resolves the adopted parent nucleus and stores the exact detector settings in
the immutable recipe. Applying the method to all fields remains an explicit action. Visible manual thresholds take
precedence; changing the nucleolar source or pixel calibration drops incompatible
hidden detector overrides. Image-only explicit requests remain supported; image
registration itself does not invoke the paid provider.

The worker accepts old prompt versions `2026-10-06.1` and `2026-10-06.2` with
their old output schema. Stored drafts lacking `processing` remain readable;
they do not acquire fabricated detector settings. Deploy the worker before
enabling the new local API prompt version.

The ordinary local proposal route transmits metadata, the stated goal, current
structured detector settings and at most one previous goal/proposal, **not image
previews**. The local API maps channel IDs back to opaque service tokens and
validates the closed settings contract before transmission. The browser maps
every channel reference in the response back to the acquired image IDs, including
detector settings, statistics axes, figures and pending nuclear-role selections.
A follow-up continues from the previous proposal's settings: the local API leaves out
its items to confirm (`choices`) and its run and group suggestions (`assignments`)
before it checks the contract, so a proposal with one suggestion per field does not
stop the messages after it, and neither is sent to the model again.
The provider request-size reservation includes this entire bounded continuation.
Suggested thresholds are starting settings, not
image-validated segmentation. Positive-pixel segmentation is not classification
of GFP-positive nuclei. Nuclear selection from GFP still uses the separate
registered gate and its control/threshold requirements.
