# Production delivery — 2026-10-06

Claude's cloud work has stopped. The existing local evaluation ledger is the
single active authority again; the cloud environment bundle is retired. No keys,
device tokens, account IDs, ledger database or private research inputs are tracked.

## Completed evidence

- PRs #32–#34 are integrated. PR #34 adds two real-Fiji `/workspace` acceptance
  cases to the Windows archive workflow, requiring 26 passing cases without skips.
- Sol prompt `2026-10-06.1` passed all 14 live evaluation scenarios: 12 metadata
  scenarios and two previews from registered BBBC013 originals. Both Python
  semantic validation and usefulness assertions passed. Unknown stain metadata
  was retained rather than inferred as GFP. Source: `38e16a780baf39b292172d337329b2ac646e0c64`.
- The ledger's cumulative settled costs plus unresolved upper-bound holds are
  **USD 0.828806905**, within the **USD 5 evaluation-only** authorization. This is
  conservative accounting, not an invoice. Earlier failed attempts and the
  unknown-usage request remain accounted for; they were not cleared for retries.
- Dedicated Worker: <https://cytellect-proposal.my270yuto0413.workers.dev>.
  D1 migrations `0001_init.sql` and `0002_usage_integrity.sql` applied. No COMPASS
  resources changed. Worker source matches the commit above. No OpenAI key is
  installed; zero monthly budget and quota keep model calls disabled.
- Deployed smoke checks returned unauthenticated **401**, authenticated **503**,
  both `Cache-Control: no-store`. Before/after reservation, settlement and request
  counts were all zero. Provisioning tokens remain private.

## Delivery checks still in progress

- PR #35 exact-head CI and integration, canonical Vercel verification, fresh
  Windows archive acceptance/release, and current-source Docker full workflow.
- Docker Desktop's startup failure was isolated to stale temporary Unix socket
  directories. They were reversibly moved aside; volumes, settings and credentials
  were preserved. Docker Engine 29.6.1 and the existing containers resumed.
- Full Compose build exposed missing planning JSON fixtures in the web image.
  The Dockerfile now includes that public fixture directory; CI also builds the
  web container to prevent a host-only build from hiding this failure.
- A Windows CI attempt passed 1472 Python tests but timed out on `docker compose
  version`. Its failed job was retried without weakening assertions.

## Owner decisions held

Production paid model calls remain disabled. The landing page at `/` is retained;
`/workspace` does not replace it. Either change requires the owner's decision.

These results verify proposal contracts and execution. They do not establish
biological validity, detector accuracy on private experiments, or researcher
usability acceptance; those remain separate gates in the roadmap.
