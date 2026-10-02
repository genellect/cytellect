# Web interface

Japanese Next.js 16 / React 19 client, CSS Modules, Konva label editing, and TanStack Query memory-only queries.

## Development

`pnpm install --frozen-lockfile`, then `pnpm dev`. Open http://localhost:3000.
The API must allow that exact origin and run at http://localhost:8000; set
`NEXT_PUBLIC_API_ORIGIN` before building if it differs. Production must use HTTPS,
same-site controlled domains and secure cookies. No credentials belong in this variable.

`pnpm check`, `pnpm test`, `pnpm build` validate the frontend.
`pnpm contracts` regenerates Pydantic/OpenAPI-derived input types from
`packages/contracts/openapi.json`. `pnpm --filter @cytellect/web exec node scripts/contracts.mjs --check`
checks for contract drift. Server-produced measurement/result responses are currently
described by TypeScript response interfaces; scientific input schemas are generated.

## Research workflow

An administrator issues an invitation through the Python CLI. The UI exchanges it for
an HttpOnly session without persisting its token. Create an experiment, explicitly map
channels and metadata when uploading TIFFs, or generate synthetic fixtures. Confirm a
background polygon in each field, select a recipe and start a job. The viewer supports
click-defined polygons and exact coordinate entry; numerical inputs remain accessible
without relying on canvas interaction. Nucleus/nucleolus/manual ROI edits create new
immutable revisions. Undo/Redo selects earlier/later revisions through the API.
Nucleus edits require nucleolar resegmentation/review. Exclusions and background/gating
updates are remeasured on current masks. Old statistics remain visibly labelled old.

Statistics display cells/fields/independent units separately. The paired option is
initially selected because synthetic controls and treatments share pair IDs. Confirm
the experimental units explicitly. Matplotlib figures and source CSVs are downloaded
through authenticated API requests. Export ZIPs exclude originals unless opted in.
Numeric CSV import handles already measured assays; no instrument-specific processing.

## Data boundary

Research pixels go directly from browser to API. No Next.js server action, image
optimization, analytics, service worker, persistent Query cache, or localStorage is used.
Blob URLs are revoked when preview/result components change or unmount. Logout clears
in-memory queries. All API fetches use `credentials: include` and `cache: no-store`;
mutation requests add `X-Cytellect-Request: 1`. The server validates Origin.
Save outputs before the 24-hour activity-based retention expires.

## Browser verification

Use synthetic fixtures or the explicitly licensed public sample assets; never user research data. Set `CYTELLECT_TEST_INVITE_FILE` to a file outside
the checkout containing a fresh development-only invite, and
`CYTELLECT_TEST_DATA_DIR` to the same local test API data directory so the test can
issue later fresh invites through the operator CLI if configured.
Run API and worker, start the Web server, then `pnpm test:e2e`.
No invitation, cookie, or private research content is printed or recorded in test artifacts.
Browser tests cannot establish real-image scientific validity or production-host security.

## Public image explorer

The /demo route uses saved measurements and display derivatives from public microscopy datasets.
It does not run Fiji in the browser or accept uploads. Without NEXT_PUBLIC_API_ORIGIN,
production makes no local/API request and disables invitation submission. Public results
remain available without a session; the protected private API and its research data are separate.

- 4DN Sceptic DAPI/NCL: raw compartment means and recorded StarDist/ImageJ/MorphoLibJ labels.
  No GFP. The portal/OME channel-order discrepancy is visible in the inspector and retained
  in the derivative manifest; mapping is provisional and no independent detection accuracy is claimed.
- BBBC039 Hoechst DNA: raw DNA mean/integral in recorded StarDist nuclei; no NCL/GFP claims.
  Potential DSB2018 model-training overlap is retained in provenance.
- Source links, attribution, original hashes, permitted-use policy and derivative file lists
  live beside public/demo assets. These datasets are not relicensed as Cytellect source code.

UI reference: [QuPath first steps](https://qupath.readthedocs.io/en/stable/docs/starting/first_steps.html)
object selection, annotations and measurement inspection; [OMERO](https://www.openmicroscopy.org/omero/)
for image-centred browser organization. No upstream UI code or assets were copied.

## Accessible editing and browser boundary

The image viewer offers pointer polygon placement and equivalent numeric coordinate input.
Native labelled controls expose mask layer, selected IDs and parent nucleus ID.
The public explorer offers keyboard-accessible nucleus polygons, numeric ID selection,
channel previews, overlay toggle and source-table downloads at desktop/mobile widths.
Public previews are display transforms; their pixel values never replace raw measurements.
