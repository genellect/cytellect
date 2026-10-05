# Runtime and API

The Next.js UI renders images locally in a Konva canvas. It requests private previews directly from FastAPI with credentials, never through Next image optimization. FastAPI validates ownership before every image/mask/result read. SQLite contains workspace metadata, immutable scientific revisions, separate execution jobs and attempt leases. Files live outside the checkout in a private local volume. A separate worker claims one job and starts a supervised child process; Fiji Java runs only inside that process tree.

A revision snapshots input SHA-256, channel mapping, metadata, recipe, masks, exclusions and backgrounds. Edits create child revisions with an active-revision compare-and-swap. Reconfiguring gates/background/exclusions remeasures existing masks; changing nucleolar detection requires explicit resegmentation. Nuclear edits remove children of affected nuclei and require explicit review or redetection. Undo/Redo selects previous immutable revisions; previous statistics stay tied to their original revision.

The worker persists attempts under short internal IDs, renews a lease, enforces process-tree time/memory limits, rejects stale publication and records sanitized codes. A child watchdog terminates if its parent, lease or workspace is lost. Partial field failures remain visible and prevent statistics until explicitly resolved or excluded in a new revision. Retry retains scientific inputs and uses a distinct attempt directory.

## Replacement boundaries

| Boundary | Current implementation | Possible later replacement |
|---|---|---|
| Identity | Invite exchange and hashed sessions; owner ID | Account provider with verified guest transfer |
| Database | SQLAlchemy Store and Alembic schema, local SQLite WAL | PostgreSQL adapter/migrations |
| Artifacts | storage helpers and contained private filesystem | Private object storage, permission-checked retrieval |
| Jobs | Store leases + supervised worker | Durable queue with the same fencing semantics |
| Image engine | `engine.detect` and fixed recipe contracts | Separately validated detector recipe |
| Method proposal | No runtime dependency; validated Recipe is the accepted execution contract | Structured proposals requiring explicit adoption |

These boundaries do not authorize arbitrary plugin code or remote URLs.

## API groups

The generated [OpenAPI document](../packages/contracts/openapi.json) is the contract source for TypeScript input and response types.

- `/v1/invitations/redeem`, `/v1/session`: one-use invitation, cookie session and revocation.
- `/v1/workspaces`, `/fields`, `/tables`: metadata, bounded TIFF/CSV registration, private previews.
- `/analyses`, `/v1/revisions/{id}`: automatic detection and immutable measurements.
- Revision `/edits`, `/reconfigure`, `/resegment`, `/review`: masks, gates/background, nucleolar redetection and explicit review.
- `/statistics`, `/export`, `/v1/jobs`: asynchronous processing, cancellation/retry and permission-checked files.
- Workspace `/region-fields`, `/region-analyses`: named 2D channels, optional metadata and manual/imported masks through the same upload guard, ownership, quotas and job lifecycle. Native nuclear recipe endpoints retain their existing contracts.
- Revision `/region-measurements`, `/region-masks`, `/region-edits`, `/region-reconfigure`: typed region results, canonical labels and immutable corrections. Reusing the current revision explicitly preserves trial masks when adding fields; stale mask/revision writes are rejected.
- Revision `/descriptive`: reviewed per-field distributions for either image workflow. Explicit source/region/channel/metric selection; no inferred experimental units. A statistics job carries `analysis_mode` so clients distinguish these results from inferential models.
- Workspace DELETE blocks access immediately; worker cleanup removes original/derived/temporary data after execution stops.

No registration, analytics or billing endpoint is installed. The optional analysis proposal relay is specified in [workspace redesign](workspace-redesign.md) and is disabled unless configured.
