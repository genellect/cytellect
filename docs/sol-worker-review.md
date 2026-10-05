# Sol proposal Worker: implementation and release checks

This increment implements GPT-6.1 Sol request handling and mock-tested accounting.
It does not establish deployed service operation, scientific proposal quality,
actual billed cost, or private-image validity. No paid calls were made during implementation.

## Model and execution

`gpt-6.1-sol` is the only accepted model. Requests use Responses, strict generated
JSON Schema, `store: false`, standard `service_tier`, and medium reasoning.
Low reasoning requires explicit operator `LOW_EFFORT_EVALUATED=true` after the
same evaluation passes. No automatic model fallback, arbitrary tools, web search,
user code, previous-response state, or response storage is requested.

The provisional output ceiling is 8,000 tokens including reasoning and JSON.
Operator overrides must be integers between 1,024 and 16,000. This is a cost
control, not a measured optimum. Incomplete responses return
`model_output_incomplete` without repeating the same budget. Refusals and transport
failures also stop. Structurally malformed output receives at most one repair;
the two-call cap applies to the complete proposal. Scientific semantic validation
remains in the local API and never silently executes a rejected proposal.

Official sources checked 2026-10-05:
[model and pricing](https://developers.openai.com/api/docs/models/gpt-6.1-sol),
[reasoning and token limits](https://developers.openai.com/api/docs/guides/reasoning).
The published standard short-context rates per million tokens are input $2,
cached input $0.10, cache writes $2.50, and output $10. The adapter fixes standard
tier and rejects configuration below these rates; review pricing again before activation.

## Data and accounting review

- Context and drafts are structurally validated against the generated closed
  schemas without coercion. Unknown nested fields, malformed counts, duplicate
  channels and unregistered preview channels fail before a billable request.
- Request streams are bounded by UTF-8 bytes even without trustworthy length
  headers. Preview PNG headers are limited to 512 by 512; no pixel measurement
  occurs in the relay. Only embedded previews are accepted, never remote URLs.
- OpenAI redirects are disabled. Each request has a 120-second abort signal and
  a bounded response body. Provider bodies and exception text are never logged.
- Reservations include the actual instruction, generated schema, context, UTF-8
  expansion, repair allowance and preview token allowance for both possible calls.
  Non-cached tokens are conservatively priced as cache writes until a validated
  usage breakdown distinguishes them. Missing/invalid usage and failures retain
  the full reservation. This is an upper accounting estimate, not an invoice.
  Known input/cache/output token counts, call count and model/prompt versions are
  saved as accounting metadata for reconciliation; unknown usage stays null.
  Zero or contradictory usage cannot release a reservation. Calendar periods
  use UTC request-start months; provider invoicing around a month boundary must
  be reconciled separately. The configured cap applies to this relay, not other
  API clients using the same operator account.
- Migration `0002_usage_integrity.sql` makes settlement atomic and idempotent.
  Its SQLite trigger adds spending and removes a reservation in one transaction;
  retries do not double count. Unsettled reservations never expire automatically.
  Do not delete unresolved holds based on age: settle them with verified provider
  cost through the same atomic accounting operation, retaining the hold if cost
  remains unknown.
- `Idempotency-Key` must be a version-4 UUID, scoped to the installation/device.
  Repeating an action returns `409 duplicate_request` before another quota debit
  or model call. The relay stores only this opaque action right and accounting,
  not goals, response JSON or research fingerprints. Completed proposals belong
  in local persistent storage. A lost response is not replayable from the relay;
  creating a new action after that failure requires an explicit local retry.
- Keep operator key, budget, device quota and every tariff unset until configured.
  The example configuration cannot produce paid calls. D1 must receive both
  migrations before the updated Worker is enabled.

## Public evaluation command (requires separate paid-call authorization)

Install Python and pnpm dependencies first. Run `pnpm --filter
@cytellect/proposal-worker eval:public` normally to verify the harness without
calling a model: its live test is skipped.

After operator authorization, privately supply `OPENAI_API_KEY`, set
`CYTELLECT_ALLOW_PAID_PUBLIC_EVAL=true` and an explicit
`CYTELLECT_PUBLIC_EVAL_BUDGET_USD=5`. The user's 2026-10-05 approval is a **total
$5 evaluation allowance**, not $5 per run and not production spending approval.
Set
`CYTELLECT_PUBLIC_EVAL_EFFORT` to `medium` or `low`; repeats default to three and
may be one through three. `CYTELLECT_EVAL_PYTHON` can identify the prepared Python
interpreter; otherwise the repository `.venv` is used. Never paste a key into
chat, shell command history, a tracked file, or a CI artifact.
Paid evaluation explicitly refuses CI environments. Its Python oracle receives
only OS/runtime environment variables, not the OpenAI key, and has a 15-second
subprocess timeout.

Before the first run, choose one persistent, absolute `CYTELLECT_PUBLIC_EVAL_LEDGER`
path outside the repository, with an existing local parent directory, and run
`pnpm --filter @cytellect/proposal-worker eval:init-ledger`. Initialization makes
no API call and reads no credential. Reuse this exact SQLite file for every
subsequent attempt, repetition and medium/low comparison under this approval.
Do not place it in an ephemeral directory, network share or cloud-sync folder.
The evaluator refuses a missing ledger; it cannot silently recreate it. Never
delete/reinitialize it or choose another file to renew the allowance. If it is
lost or corrupt, stop and reconcile previous usage before seeking a new approval.

SQLite file locking (`BEGIN IMMEDIATE`) and synchronous commits reserve both
possible calls before any request. Settled cost plus all unresolved holds is
checked against the persisted approval and the hard $5 limit, including across
concurrent processes and restarts. Reservations have no automatic expiry. A
failed/interrupted call keeps its full hold until its provider cost can be
confirmed. Settlement is idempotent; an impossible cost above the reserved
ceiling blocks subsequent admission for reconciliation. Integer nanodollars
avoid floating-point admission drift. The file records only an approval marker,
opaque reservation ID, public case ID and accounting/token totals—no key,
prompt, model response, image or research information.

The harness uses 12 fixed public-method scenarios, the actual Worker adapter and
the local Python semantic validator. It accepts no custom prompt, image path or
research file. It bounds cost before each proposal using the same reservation
logic and emits only case IDs, fixed validation codes, usefulness, latency,
call/token counts and estimated cost. All selected cases/repeats must complete;
a budget stop is an incomplete evaluation, not a pass. Blanket rejection and
always-descriptive answers cannot satisfy the positive comparison case.

These are transport and method-selection scenarios informed by registered public
references, not a public microscopy image benchmark. They do not replace actual
published-image integration, independent scientific review or statistical power
assessment. No live scores are available at this checkpoint.

## Remaining release gates

1. Public evaluation of medium; investigate failed case IDs without merely
   weakening expectations. Evaluate low on identical cases before allowing it.
2. Compare reservation estimates with provider usage/invoices, including cache
   writes, missing usage and failures. Validate low-detail preview cost if enabled.
3. Apply and exercise migrations on real D1; SQLite tests are not remote D1 proof.
4. Verify owned device/invitation, revocation, quota and lost-response behavior
   through the actual local API and deployed relay. Keep research data unlogged.
5. Verify all scientific proposals through image-to-table-to-figure acceptance.
   Do not equate valid JSON, green CI, or a helpful explanation with correctness.

## Optional Docker relay connection

The base `compose.yaml` leaves the API on its internal network and the analysis
worker on `network_mode: none`. It does not forward proposal credentials. To
connect an already deployed, budget-configured relay, use the explicit override:

```sh
docker compose -f compose.yaml -f infra/compose.proposal.yaml config --quiet
docker compose -f compose.yaml -f infra/compose.proposal.yaml up -d --build
```

Set these operator values privately before the command:

- `CYTELLECT_RUNTIME_DIR`: the existing private image/analysis volume outside Git.
- `CYTELLECT_PROPOSAL_URL`: the approved HTTPS relay origin.
- `CYTELLECT_PROPOSAL_TOKEN_FILE`: an absolute private file outside Git containing
  the installation's invitation-issued device token. This is never an OpenAI key.
- `CYTELLECT_PROPOSAL_TIMEOUT_SECONDS`: normally 300, covering two bounded
  120-second provider calls plus relay overhead.

The secret file must be readable by container UID 10001. On Linux, restrict the
file to that owner with mode 0400; on Windows, restrict its host ACL and confirm
Docker can mount/read it. Do not put the token in a Compose environment value,
command argument, build argument, image, or shared log. The rendered configuration
contains only its file path. Docker administrators retain access to container
secrets; this is not isolation from the host administrator.

Only the API receives this file at `/run/secrets/proposal_device_token`. The
Python API reads it with a small byte limit and fixed errors; simultaneous direct
token and file settings are rejected. The analysis worker receives neither the
secret nor an outbound network, and the web service is unchanged. The operator's
OpenAI key remains solely at the remote relay.

The override grants outbound networking to the API; it is not a destination
firewall. The application calls only its operator-configured relay and refuses
redirects. If deployment requires a network-enforced endpoint allowlist, configure
the host's outbound firewall/proxy separately before activation. Base Compose is
unchanged when this override is omitted. To remove access after opting in,
recreate the API with the base files only and verify the outbound network/secret
attachment is gone. Existing local analysis remains available without the relay.

`tests/test_proposal_compose.py` exercises actual Compose merging with a dummy
device token, verifies that the token is absent from the rendered configuration,
and checks unchanged offline-worker/web boundaries. It requires the Compose CLI
but starts no containers and does not contact the relay. A skip means the merged
deployment has not been verified in that environment; run it in Docker CI or on
the deployment host before publishing the package. Set
`CYTELLECT_REQUIRE_COMPOSE_TEST=1` in that required check to fail rather than skip
if its Compose CLI is unavailable.
