# Workspace activation — 2026-10-06

This increment follows the [previous delivery](production-delivery-2026-10-06.md).
Its source, deployment and archive acceptance are separate gates.

## Changes and scientific scope

- `/` and `/workspace` use the same workspace. `/product` holds the LP and its
  analytics; `/legacy` is available only for local installations and is 404 on
  public builds, including a future remote-API configuration.
- Adopted field revisions, Undo and reasoned failed-input exclusions are stored
  on the server with version checks. Comparison submission, calculation and
  publication reject changed adoption. Completed old results remain available.
- Descriptive plots follow their accepted job directly and recover from a failed
  status read. A held stale job list reproduced the former liveness failure;
  the corrected case passed with real Fiji/API and vector/data exports.
- Accounting incidents block later production model calls across devices and
  months. A valid paid draft is retained; unknown costs and other reservations
  are not cleared. See [budget reconciliation](proposal-deployment.md).
- Measurement equations, recipes and statistical methods are unchanged.

## Live proposal service

Production model calls are enabled under the separately approved USD 5 monthly
limit. The cumulative evaluation ledger remains separate and unchanged. Provider
and device secrets are outside Git; only the local API receives its device token.

Two integration problems were identified and corrected. Cloudflare rejected the
default Python urllib user agent before the request reached the Worker; the API
now identifies itself as `Cytellect/0.1`. More importantly, the edge runtime
rejects `redirect: "error"` before sending a request. A real workerd reproduction
established the latter cause. The adapter uses `manual` and rejects non-success
responses, with real-runtime tests proving that 302/307 never forward credentials.
No diagnostic endpoint or new dependency was added.

Worker version `a4b3adaf-6a06-4176-a642-4ebc6ed7d866` contains the adapter fixed in
commit `69a842b`. A real browser request using registered BBBC007 metadata reached
Sol and passed the local semantic validator. The returned proposal described
nuclear area and raw intranuclear intensity, retained unknown stain identities,
and did not invent independent replication or a group test. The successful call
recorded USD 0.01418. Earlier conservative failure settlements remain in the
ledger; the aggregate USD 0.45519 is an upper-bound accounting total, not a
provider invoice. Outstanding reservations and reconciliation incidents were zero.
Repeating the same browser request returned the cached proposal; the settlement
count and aggregate cost did not increase. All 70 offline Worker checks passed,
with the separately billable public evaluation explicitly skipped.

## Docker and release gates

Docker with the updated workspace passed a registered BBBC007 workflow: 115
nuclei, 230 channel rows, zero maximum absolute error against same-mask raw-pixel
references, correction and SVG/PDF/CSV/Methods exports. A separate generated-image
case passed independent-unit comparison and editable export acceptance. These
checks establish arithmetic and workflow behavior, not detector accuracy or
biological validity. The human E2E installation preserves its private volume and
reuses the pinned Fiji image layer.

The next Windows archive must pass exact-source main CI, fresh/repeat setup,
26 installed browser cases, independent numerical/replay checks and shutdown.
The [storage-test investigation](windows-storage-investigation-2026-10-06.md)
retains an unexplained earlier failure and its strengthened diagnostics. Neither
a passing retry nor Linux acceptance establishes native acceptance on this PC.
Private-image scientific suitability and researcher usability remain open.
