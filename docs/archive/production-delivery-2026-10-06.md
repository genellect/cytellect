# Production delivery — 2026-10-06

For the later root-workspace switch, production API enablement and review fixes,
see the [workspace activation record](workspace-activation-2026-10-06.md).
The disabled-service and held-root states below describe the earlier delivery.

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
  Active Worker version: `5e579cd9-1536-429d-b66a-475f7574a0dc`.
- Deployed smoke checks returned unauthenticated **401**, authenticated **503**,
  both `Cache-Control: no-store`. Before/after reservation, settlement and request
  counts were all zero. Provisioning tokens remain private.
- Final Docker full-stack acceptance passed both real browser cases in 5.9
  minutes: 115 BBBC007 nuclei, 230 channel rows, maximum absolute pixel-reference
  error zero, one region excluded, and SVG/PDF/CSV/Methods exports; plus four
  generated fields with two explicit software units per group and editable
  independent-unit comparisons. Source: `7f65970cfb38b962f6b962355e3e30cfc9b80298`.
  Its Git tree is identical to merged main `9c35a730cfcc7b0e811a81bfe36c51398a99358f`.
- Independent Docker references passed signed background-corrected pixel checks,
  closed-form independent and paired t comparisons, exact small-sample
  Mann–Whitney and Spearman checks, editable SVG/embedded-font PDF, every bundle
  hash, and replay equality for measurements, descriptions, comparisons and
  associations. The first replay stopped on a Windows-working-copy/Git-archive
  source-byte mismatch; using the same clean archive as the container resolved
  that identity mismatch without weakening the assertion.
- Docker API/worker ran as UID 10001 with read-only roots and dropped capabilities;
  the worker had no network and no provider key. Research/runtime mounts stayed
  outside Git. All three isolated acceptance containers stopped. Existing human
  E2E containers and data were preserved.
- The registered BBBC013 example now retains the source's DRAQ/FKHR-EGFP channel
  correspondence. A live-browser check exposed an empty intensity plot after a
  filename-only nuclear choice; recorded masks can no longer be reinterpreted by
  that choice. Ten public-example browser checks passed, including GFP counts,
  correction/undo, source navigation and four viewport sizes. Two unrelated real
  upload cases were explicitly skipped in the unconfigured-site test environment.

## Integration and operating checks

- PR [#35](https://github.com/genellect/cytellect/pull/35) passed all five checks
  on its exact head in [run 37339191648](https://github.com/genellect/cytellect/actions/runs/37339191648)
  and merged as `9c35a730cfcc7b0e811a81bfe36c51398a99358f`. The first Fiji/browser
  attempt failed one saved-area-result display assertion. That exact browser
  case passed against the same-source Docker API; the unchanged CI retry passed.
  The initial failure is retained; its underlying cause was not established.
- Merged main passed all five checks in
  [run 37346079235](https://github.com/genellect/cytellect/actions/runs/37346079235)
  before dispatching Windows `0.1.0-local.15` on that same immutable source in
  [run 37349387343](https://github.com/genellect/cytellect/actions/runs/37349387343).
- The equivalent Docker Desktop assets from PR #28 are included in #35; #28 is
  closed as superseded and its branch was preserved.
- Initial post-integration Vercel publication reached READY on `9c35a730cfcc7b0e811a81bfe36c51398a99358f`,
  deployment `dpl_8s1nwgtCEGRqmLy6BRYUpTG559ss`. Canonical `/`, `/plan`, `/demo`,
  `/workspace` and `/workspace?demo=bbbc013` were checked on desktop and mobile.
  The recorded GFP example shows 350/242/225 regions with the registered stain
  correspondence, without a page overflow or browser error. This example replays
  registered public results; it is not a hosted private-image Fiji service.
  The unconfigured production workspace correctly disables private uploads.
- Windows [local.15](https://github.com/genellect/cytellect/releases/tag/v0.1.0-local.15)
  is published. Exact source: `9c35a730cfcc7b0e811a81bfe36c51398a99358f`.
  [Release run 37349387343](https://github.com/genellect/cytellect/actions/runs/37349387343)
  passed fresh/repeat setup, 26 installed browser cases with zero failed/skipped/
  flaky cases, independent numerical/replay verification and launcher shutdown.
  The archive is 13,775,657 bytes, SHA-256
  `2484d2eaf067ecbc986cdf7251e413c184ea7f50db709d429d5498894df72b44`.
  Independent inspection verified all 217 payload files, manifest identity,
  acceptance-harness identity and the exact source tag. An unauthenticated public
  download matched the same bytes and SHA-256.
- This is a Windows CI-accepted prerelease. The intended PC's Smart App Control
  refusal of an unsigned SciPy extension remains unresolved; publication does
  not claim native acceptance on that PC. The release notes retain this limit.
  No OS protection was disabled and no refused binary was renamed/substituted.
  Docker acceptance is a separate, passed execution path.
- The website's release pointer and these records ship together through a
  PR/main deployment. Final website acceptance requires its canonical download
  link, displayed version and SHA-256 to match the accepted local.15 artifact above.
- Docker Desktop's startup failure was isolated to stale temporary Unix socket
  directories. They were reversibly moved aside; volumes, settings and credentials
  were preserved. Docker Engine 29.6.1 and the existing containers resumed.
- Full Compose build exposed missing planning JSON fixtures in the web image.
  The Dockerfile now includes that public fixture directory; CI also builds the
  web container to prevent a host-only build from hiding this failure.
- A Windows CI attempt passed 1472 Python tests but timed out on `docker compose
  version`. Its failed job was retried. Optional CLI availability now records an
  explicit skip for an unresponsive CLI; the required Linux deployment check
  still fails in that situation. The actual required Compose check passed here.
- Python API defaults and its contract now match evaluated prompt `2026-10-06.1`.
  Twenty-nine affected API/persistence/oracle tests passed.

## Owner decisions held

Production paid model calls remain disabled. The landing page at `/` is retained;
`/workspace` does not replace it. Either change requires the owner's decision.

These results verify proposal contracts and execution. They do not establish
biological validity, detector accuracy on private experiments, or researcher
usability acceptance; those remain separate gates in the roadmap.
