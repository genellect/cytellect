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
The panel offers only analyses the API accepts: an association needs two different region
measurements (per-nucleus nucleolar summaries cannot be an axis), and a brightness comparison is
withheld, with its reason, when an adopted region holds saturated or storage-limit pixels in that
channel (the API refuses it as `region_comparison_saturated_signal`).
Numeric CSV import handles already measured assays; no instrument-specific processing.

## Data boundary

Research pixels go directly from browser to API. No Next.js server action, image
optimization, analytics, service worker, persistent Query cache, or localStorage is used
(the public demo stores only its guide dismissal and never handles research data).
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

## Public demo (/demo)

The public build (no `NEXT_PUBLIC_API_ORIGIN`) serves `/demo`: the production workspace
(`ConnectedWorkspace` in showcase mode) on registered public images that are already detected
and measured, with saved statistics and figures. Everything except adding images works as in
production and is computed by the same API and analysis package, serverless. The architecture,
the shared contracts and the demo files are described in [the showcase document](showcase.md).
`/workspace` on the public build redirects to `/demo`; installations with an API (local package,
Docker, development) keep their workspace at `/` and `/workspace` and have no `/demo`.

- Transport: `lib/showcase` answers visitors from recordings only, on every device and without
  waiting: the recorded GET responses (`/showcase/snapshot/`, every field, region and channel)
  paint the view, and the recorded tour (`snapshot/journal.json`) answers changes. The in-browser
  API (Pyodide) is never fetched or started for visitors; it runs only for the build-time recorder.
  No request reaches `/v1` on any server or a local service.
- An operation the recording does not hold (a hand-drawn outline correction, a measurement under
  unrecorded settings) shows an information notice at once ("公開デモに記録していません"), never
  the error banner. Unrecorded detection conditions, unrecorded AI instructions and uploads are
  notices too.
- Detection inputs offer only recorded values (`snapshot/recorded-options.json`); the AI composer
  offers the recorded instructions (`snapshot/proposal-examples.json`) as examples. The header
  shows a デモ badge with the image source and limits (`snapshot/dataset.json`) and a ダウンロード link. Image, folder, drag-and-drop and CSV intake open a dialog that
  points to the Windows/Docker versions.
- `?step=image|statistics|figure` opens that tab. A four-step guide (画像と輪郭 → 測定値 → 統計 →
  グラフと書き出し) opens from 「使い方」; it never opens by itself, so the image and results show at once.
- Controls whose results cannot be recorded are fixed to the recorded values with a short note
  (statistics method and design, figure labels, axes, colours and sizes, detection conditions,
  nuclear stain, background); cell ROIs and GFP, absent from the dataset, are not offered. Missing optional demo files leave the
  matching controls as in production.
- Development without the demo build: `scripts/dev_showcase_backend.py` serves the same
  boot/handle contract from a local CPython API with a threshold stand-in for detection, for
  builds made with `NEXT_PUBLIC_SHOWCASE_DEV_BACKEND=http://127.0.0.1:8000` (loopback only; never
  for a published build). Its numbers are not results. `tests/showcase.spec.ts` walks the
  features against either backend (`CYTELLECT_SHOWCASE_DEV_BACKEND` for the development one) and
  skips with a message when neither is available.

The demo numbers illustrate the software on public images; they establish neither detection
accuracy nor scientific validity on laboratory images. The former explorer
(`apps/web/public/demo/bbbc013`, `bbbc039`, `4dn-ncl`) and the recorded-output prototype were
removed. The landing page shows images and figures recorded from this demo (`apps/web/public/marketing/lp-*`).

UI reference: [QuPath first steps](https://qupath.readthedocs.io/en/stable/docs/starting/first_steps.html)
object selection, annotations and measurement inspection; [OMERO](https://www.openmicroscopy.org/omero/)
for image-centred browser organization. No upstream UI code or assets were copied.

## Accessible editing and browser boundary

The image viewer offers pointer polygon placement and equivalent numeric coordinate input.
Native labelled controls expose mask layer, selected IDs and parent nucleus ID.
The public demo uses the same workspace controls at desktop/mobile widths.
Public previews are display transforms; their pixel values never replace raw measurements.

## Verified checkpoint (2026-10-02)

- TypeScript and ESLint: passed without errors or warnings.
- Vitest private transport checks: 2 passed.
- Optimized Next production build: / and /demo generated successfully.
- Private Playwright workflow: 2 passed. Real Fiji processed six artificial fields;
  browser verified manual ROI editing, remeasurement, Undo/Redo, QC review, paired
  statistics, figure/ZIP retrieval, separate-session image denial, and TIFF registration.
- Public production browser checks: 2 passed. Licensed 4DN/BBBC039 object selection,
  source table download, desktop 1440 and mobile 390 layouts, no horizontal overflow
  or page errors. With no API configured, the build made no /v1 or localhost:8000 request.
- Browser localStorage and sessionStorage remained empty in the private workflow.

These checks establish the tested interactions and local integration. They do not
establish hosted private-backend operation, private-experiment scientific validity,
or successful researcher PoC evaluation.


## Optional channels and public GFP sample (2026-10-03)

The upload form distinguishes NCL analysis (nuclear stain + NCL, optional GFP)
from nuclear GFP analysis (nuclear stain + GFP). OME mappings declare both ordered
roles and channel indices. Missing channels are never replaced with another stain.
Viewer tabs, manual-ROI tables and statistical options follow stored channel roles.
GFP-only analysis omits nucleolar controls and NCL measurements; GFP cannot be
regressed on itself. Native NCL fields without GFP have no GFP selection controls.

The third public sample is BBBC013 A01, DRAQ nuclear stain and FKHR-EGFP, with no
NCL. Images are attributed to Ilya Ravkin under CC BY 3.0. Published 8-bit BMP
samples were preserved in TIFF containers; this is not a claim of validated
camera-native FRM intensities. The public page shows precomputed raw measurements
and actual Fiji contours, with the precise ImageJ comparison scope in its notes.
Its former derived assets (`apps/web/public/demo/bbbc013/manifest.json`) remain in Git history.

Figure controls offer Nature single-column (89 mm), double-column (183 mm) and
custom widths. Nature presets constrain type to 5–7 pt and height to 170 mm;
editable height remains explicit. Selecting an unpaired test disables the paired
plot. Figure data, source caption and model predictions have authenticated downloads.
A journal-size preset is a formatting option, not scientific or submission approval.

Verification at this checkpoint: three additional private browser checks passed,
including real BBBC013 two-channel upload and Fiji field trial, two-channel native
NCL OME registration, and the three-channel upload/access-isolation regression.
The production public viewer passed desktop/mobile selection, channel switching,
350-row GFP table/CSV, zero page/console errors and zero unconfigured API requests.
The first published checkpoint (f172afb) was separately tested at
https://cytellect.vercel.app on desktop/mobile; this does not establish deployment
of subsequent changes or a hosted private analysis server.

The updated full private workflow also passed (4.1 minutes): six-field actual Fiji,
manual ROI/revision navigation, review, paired statistics, Nature 89 mm figure
source/caption retrieval and reproducibility ZIP. This remains synthetic numerical
integration evidence, separate from the BBBC013 real-image field trial.


## Packaged local browser workspace

`pnpm --filter @cytellect/web build:local` builds a static browser bundle in
`apps/web/out`. It sets `CYTELLECT_WEB_MODE=local`; the default build continues to
produce the Vercel-compatible application. The local bundle uses relative `/v1`
URLs and ignores `NEXT_PUBLIC_API_ORIGIN`. It refuses API requests when opened on
a non-loopback hostname. No public page probes localhost or creates a local session.

The local API wrapper serves the static files and `/v1` on the same origin,
normally `http://127.0.0.1:8765`. The browser reads `/v1/local/setup`, displays
workspace/Fiji configuration status and, only after clicking `解析を開始`, posts
`/v1/local/session` with the CSRF header. The server issues an HttpOnly cookie;
no invitation token, URL credential, localStorage or sessionStorage is used.
Fiji configured status is not a claim of validated image-analysis accuracy.

Onboarding and the upload form state that images are saved locally. The retention
period is 24 hours after explicit activity. Data that expires while the application
is closed is deleted on the next launch; browser copy does not imply a background
service continues while the application or computer is stopped.

The real local wrapper and worker were tested with the exported bundle: session
bootstrap, forbidden external-origin bootstrap, DRAQ/FKHR-EGFP TIFF registration,
actual Fiji processing, review, ZIP download and retained work after reload passed.
No external-origin request or page exception occurred; desktop/mobile onboarding
had no horizontal overflow. Run this integration with `CYTELLECT_TEST_LOCAL=1`,
`CYTELLECT_WEB_URL=http://127.0.0.1:8765` and Playwright
`tests/local-workspace.spec.ts`. It uses the registered BBBC013 public data.
Installer distribution is separate from this browser bundle; the public UI does
not advertise a download until a concrete release artifact is available.
