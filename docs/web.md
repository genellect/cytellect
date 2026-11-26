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
Images are added item by item ([#284](https://github.com/genellect/cytellect/issues/284) W1):
one image's failure never stops the others, their placement in a group, their measurement or the
comparison. The order is fixed: files that are not TIFF are 対象外; a file with the same bytes as
another image of the addition or as a registered field's input is a copy (同一内容) and becomes a
field only through 「別の撮影として追加」; the rest are grouped into fields; and only a field in which two
different images name the same channel waits (要確認), unsent, while the other fields are registered.
Before its images are sent, each field gets a row in the workspace record with its file names and,
when it was added from a group's cell, that run and group. A refused image keeps its row with the
API's reason code (a 32-bit integer label image is shown as a mask candidate, not as missing data); an
image whose answer never arrived stays 「登録未完了」. Rows keep their names after a reload.
A row is resolved by 「差し替え」 (choosing all of its files again, sent under the same row key, so no
second row or field is made) or removed with 「記録から削除」. A row whose upload was interrupted (登録未完了) is also
resolved by adding images of the same names again to where it was going (the same run and group, or none for
both); a refused row, or a row going elsewhere, is another image's record and stays. An addition that ends early
(no answer before or while sending, a changed workspace, 実行を中止) keeps nothing unsent: a later addition never
sends its images on its own, and they stay in the list of chosen files. 実行を中止 is reported in the status line
(「登録：1 視野 · 追加：中止」), not as an error, and also ends a 追加 that covers several cells. Registered fields are placed in the run
and group of their row when the addition ends and when the workspace opens again, never from the
caller's returned IDs. The researcher is never asked for a reason: the comparison counts rows without
a field in its n breakdown, by group and reason, from the selection saved with it. Every choice shows
its result in one line beside 取込, including an empty folder, a choice without TIFF and a closed dialog
(the earlier choice stays). Only an addition that cannot go on (no answer, ended session, changed
workspace) is shown as an error; what it registered stays. Images chosen before the experiment form
is chosen accumulate until they are registered. In the local build, a lost connection is shown by the
connection notice instead of that error and its 「再読み込み」, and the rows are read again once the
service answers ([Packaged local browser workspace](#packaged-local-browser-workspace)).

The AI panel ([#284](https://github.com/genellect/cytellect/issues/284) W2) first shows the selected field as the
workspace records it, without a model call and also while the AI is not enabled: its name and size, each channel with
the origin of its name and its role, and the nuclear channel. Below are the workspace's messages, each with its state
(送信中, 回答, 失敗, 設定を適用済み, 実行済み), its answer and, when its settings cannot be used, the reasons: a place the
researcher changes (画像, 染色対応, 実験デザイン, 解析設定) or a service-side failure with its code and 「再送」. The
panel shows the newest message from its first line when the message is sent, when its answer arrives and when the panel
opens, and a confirmation above the conversation comes into view when it opens: an answer of several paragraphs does
not leave the next request and its actions below the visible part. Sending
changes nothing, and the text leaves the input once the conversation holds the message (a request that never reached
the API keeps what was typed). 「設定を適用」 and 「適用して試行」 under an answer are the only ways an answer changes
settings or runs a preview, followed by 「解析設定を表示」 and 「AIによる設定変更を戻す」; when some fields fail, the
message still records what was applied and run, and the failed fields are reported. An answer that proposes a nuclear
stain the workspace has not recorded shows 「設定の適用には、核染色の指定が必要です。」 with 「核染色に … を指定」
instead: that records that channel's role as 染色対応 does (the other channels keep theirs; what the answer
proposed for them is not recorded), applies nothing, and then offers the actions. An answer is judged against the
field its message was sent for, also while a field with other channels is selected. 「再送」 is
offered for a failed message, for one left 送信中 by a session that ended, for a refusal on the service's side and,
after a reload, for an answer this session no longer holds: one with settings or with run and group suggestions
from any message, one with items to confirm as the latest message (where they are offered). It asks first, since it
may call the model, and shows what is sent when this browser has not confirmed the scope. An answer without an
analysis (only a stain's role, say) has nothing to apply and is recorded so (`applicable: null`): 「核染色に … を指定」
records what it settles, and it offers no resend after a reload. From prompt
`2026-11-26.1` (W7) the answer declares the kind of request, which only chooses these actions: a question shows its
answer and the items to confirm as buttons (a choice is sent as the next message), a settings request 「設定を適用」, and a
run request its target fields (「対象：選択した視野 · …」 or 「対象：全視野 · n 視野」, excluded fields left out) and
「適用して実行」, which applies the settings and makes detection candidates on those fields; adopting them stays with
「測定」. An answer with run and group suggestions says 「割付の案：n 視野」 with 「実験」; the suggestions appear, marked
「AI」, in the table of unassigned fields and are saved only by 「案を適用」. Applying never renames a group that has
fields or decides the control: when both groups would take a suggested name, or the only group left to name is the
control group, 「案の対照の群」 is chosen first, and what changes besides the fields is stated above the table
(「群の名前の変更：対照 → 未処理、処理 → ActD · 実験回の名前の変更：2026-11-26 → Rep1」). An empty instruction is
not sent; 「解析案を作る」 asks for a proposal from the images alone. A new workspace starts with an empty conversation and
input, and reopening a workspace shows its messages again.

An empty workspace opens on adding images ([#284](https://github.com/genellect/cytellect/issues/284) W5): a panel on
the workspace's own light surface (never an empty dark image stage, which reads as an image that failed to load)
offers 画像を選択, フォルダーを選択 and a drop, the accepted formats in one line, and three pictures of one registered
public field (BBBC007v1 A9, CC0 1.0; `apps/web/public/samples/NOTICE.json`): its DNA image as the measured
fluorescence image, its actin image as another stain of the same field, and its hand-drawn nuclear outlines, filled,
as a mask with the list's own words for one (マスクの候補 · 32-bit 整数ラベル). A window under 720 px high crops
the pictures to a band and a width up to 780 px sets them one a row, so the two links stay in view. Chosen files go to
the list first.
Each file is judged by `POST /v1/intake/inspect` (one at a time; nothing is stored) and listed with its thumbnail
and role: images grouped into the fields they will make with their channels (追加待ち, 読み込み中 while judged), a mask
candidate with the fields of its size (寸法の一致), a copy with what it copies (同一内容, 別の撮影として追加), an
unreadable file with its reason (差し替え), and a file that is not a TIFF (対象外). One line adds up the parts
(「受け取り：8 · 画像：4（2 視野） · マスクの候補：1 · …」). Choices accumulate across selections, so another stain chosen
later joins its field; 直前の選択を取り消し takes back the last choice only, and × removes one row. The list groups
the images as registration will: file names chosen again in a later selection with other content (the same names in
another condition's folder) are their own field with their stains together (「同じ名前 · 別の視野として追加」), and two
files of different content for one channel of a field are shown in that field's row (要確認, both names) with
「… を使用」 to keep one; that field waits in the list while the others are added. A field goes to one run and
group: a stain chosen without a cell joins the cell its field was chosen in, and stains of one field chosen in two
cells are two fields. An OME-TIFF with its own metadata is a field of its own, and the stains of a copy kept as a
separate acquisition stay one field. A 32-bit float or signed 16-bit
image is 読み取れない (「8/16-bit 以外の画像」), not a mask candidate, and counts as a missing image. 追加 registers
the fields (W1) and records the unreadable files as rows with stage `inspect` (at the record's limit of 100 rows the
rest gets no row and is listed with that reason, 「取り込みの記録が上限 100 件」, as an image is); with a field registered the image
shows next and what was not added waits behind 取込 n件 (the chosen files and the saved rows), so nothing that was
read stands behind a clean-up. The line beside 取込 counts the whole 追加 (「登録：3 視野 · 読み取れない：2 件」),
however many fields and cells it covered. 閉じる hides the list and keeps the chosen files. 追加して AI に質問 then opens the AI
input. The names of files not yet added are kept for this tab, with the cell each was chosen in and the file's size
and last-modified time, and come back after a reload as 「再選択」 rows (each with its cell), on which the list opens
by itself (the browser cannot keep the files). A file chosen again, by the row's 選択, by 画像を追加 or in the same
cell, takes its row's place, cell and path, so it goes where it was going and resolves the row its interrupted upload
left. With 画像を追加 or a cell the row is recognised by the file's size and time as well as its name (condition
folders hold the same file names), and rows the file cannot tell apart, going to different cells, are left to their
own 選択: a cell is never guessed from a name. Images added from a group's cell are listed with
that run and group, also in 実験. Notes on registered fields (a stain one field has and another lacks) are listed
apart (チャンネルの構成の違い) and not counted. Choosing and judging go on while images register or an analysis runs;
追加 waits for them. Development builds log the counts a choice delivered (no names or paths).

Analysis progress is counted in fields ([#284](https://github.com/genellect/cytellect/issues/284) W8). Each field in the
run has one state, shown the same way in the field list and beside the image: 準備中 (from a settings change or 測定 until
the run is accepted), 待機, 検出中, 検出候補 (candidates to review), 採用中 and 失敗; once adopted the field shows its saved count. The header reads
「視野 1/2 · BBBC007-a9：核小体を検出中」. The run continues in the API, so a lost connection while following it is retried
(「接続：確認中」) and never starts the same run again. When one field fails, the same run without it is requested
again (its finished steps are reused, not recomputed) and the fields that succeeded are adopted; the failed field keeps
「失敗」, its reason and 「再試行」. A nuclear detection asked for while no chosen field has a nuclear
stain does not start and says so (「核の検出には、核染色の指定が必要です。」, with 設定); in a run of several
fields, a field without one fails as 「核染色の指定なし」.

Statistics display cells/fields/independent units separately. The paired option is
initially selected because synthetic controls and treatments share pair IDs. Confirm
the experimental units explicitly. Matplotlib figures and source CSVs are downloaded
through authenticated API requests. Export ZIPs exclude originals unless opted in.
The panel offers only analyses the API accepts: an association needs two different region
measurements (per-nucleus nucleolar summaries cannot be an axis), and brightness of a group whose
adopted regions hold saturated or storage-limit pixels in that channel is not analysed (the API
refuses it as `region_comparison_saturated_signal`): pairs with such a group are not offered for a
comparison, and an association, which analyses every group, is withheld, each with its reason.
With a GFP nucleus filter the analysed nuclei are known only to the API, which then decides.
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
Docker, development) keep their workspace at `/` and `/workspace` and have no `/demo`. The former
review route `/workspace-review` (the workspace without its session gate) redirects to `/workspace`.

- Transport: `lib/showcase` answers visitors from recordings only, on every device and without
  waiting: the recorded GET responses (`/showcase/snapshot/`, every field, region and channel)
  paint the view, and the recorded tour (`snapshot/journal.json`) answers changes. The in-browser
  API (Pyodide) is never fetched or started for visitors; it runs only for the build-time recorder.
  No request reaches `/v1` on any server or a local service.
- An operation the recording does not hold (a hand-drawn outline correction, a measurement under
  unrecorded settings) shows an information notice at once ("公開デモに記録していません"), never
  the error banner. Unrecorded detection conditions, unrecorded AI instructions and uploads are
  notices too.
- The same as in production: several stains open as a colour merge (重ねて表示: the nuclear stain blue,
  each other used stain the colour of its channel position, so assigning the nuclear stain recolours only that channel; choosing one stain shows it alone); nucleoli and nucleoplasm
  open on the nucleolar marker with the adopted nuclei outlined faintly; side by side (2 画面) each
  pane has the outline tools of one field; focusing the AI composer opens the AI panel;
  `?step=image|statistics|figure` opens that tab; statistics and figures open on the latest saved
  result, and saved comparisons switch with one click (保存した比較); a condition chosen in the side
  panel opens its own saved result at once, and without one the demo replays its recorded calculation
  (production describes it; a test runs only on 計算), never showing another condition's
  result (genellect/cytellect#257 D-1), and グラフ follows the same choice both ways (a saved figure chosen
  there sets the side panel; SR-04); a design of two or more groups is compared (分布 is offered only
  to a design without a comparison, or when every pair holds saturated pixels), an analysis the measure
  or design cannot have is changed with its reason in one line under 解析 (SR-04), and a comparison
  opens 視野ごとの分布 (the fields behind it, group → run → field) as a check inside the result
  (owner decisions 15 and 19, 2026-11-21); a measure is named the same way on the side panel, the saved
  comparisons and the result (「核小体の平均輝度（NPM1）」, by the recorded stain); the settings panel starts
  closed and opens with 設定. In production a drop of files or folders adds images as the 画像 and
  フォルダー buttons do: the files go to the list of chosen files, and nothing is registered or placed in a
  group before the researcher adds them there (the list of chosen files, above).
- Production only, 統計 has no confirmations (owner decision 11, 2026-11-21, genellect/cytellect#257): the
  regions and fields are those adopted in 画像, the acquisition and pixel settings (群の間で撮影・画素条件を比べられる)
  and the runs' independence are declared in 実験 beside each other and shown there as status marks (撮影条件、
  独立性), pairing follows the declared layout, and nuclei without an established nucleolus are kept as missing
  under `unresolved-as-missing/1.0.0` and counted in the result's n. A request states exactly these
  declarations. While earlier work is missing, the result's place shows that one item in one line that opens its
  screen (「実験：撮影条件 未確認 →」, 「画像：未測定 3 視野 →」). The statement covers both cases of S10: the same
  settings, or a calibrated pixel size for areas in µm² (sent as `calibrated-area`; otherwise `same-settings`). A
  workspace registered without a design has no place to declare them, so it keeps one confirmation in 統計 for its
  typed groups, units and acquisition (owner decision on genellect/cytellect#273, 2026-11-21). The demo shows no such line and no
  撮影条件 mark: its recorded design states no acquisition settings and its calculations replay the tour's record.
- Demo only: the AI composer also offers the recorded instructions (`snapshot/proposal-examples.json`)
  as examples. The header shows a デモ badge with the image source and limits (`snapshot/dataset.json`)
  and a ダウンロード link. Image, folder, drag-and-drop and CSV intake open a dialog that points to the
  Windows/Docker versions. A four-step guide (画像と輪郭 → 測定値 → 統計 → グラフと書き出し) opens from
  「使い方」; it never opens by itself, so the image and results show at once.
- Controls whose results cannot be recorded are fixed to the recorded values with a short note and
  shown as locked (statistics method and design, experiment information, figure labels, axes,
  colours and sizes). The detection conditions, nuclear stain and background correction are shown
  as the recorded settings of the adopted result (text, not controls), so the demo offers no
  detection inputs; cell ROIs and GFP, absent from the dataset, are not offered. Missing optional
  demo files leave the matching controls as in production.
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

## Search engines

Only the landing page (`/`) and, on the public demo build, `/demo` are offered to search
engines; every other page is `noindex` (`app/layout.tsx`). `robots.txt` allows crawling so
that crawlers can read those `noindex` tags, and `sitemap.xml` lists the indexed pages with
canonical links (`src/lib/site.ts`).

| Build variable (hosting project) | Effect |
|---|---|
| `VERCEL_PROJECT_PRODUCTION_URL` | Set by Vercel; the public origin, e.g. `https://cytellect.app` |
| `CYTELLECT_SITE_URL` | Overrides the origin (bare `https://` origin, e.g. after moving to a custom domain) |
| `CYTELLECT_GOOGLE_SITE_VERIFICATION` | Google Search Console HTML-tag token (`google-site-verification`) on `/` |
| `CYTELLECT_BING_SITE_VERIFICATION` | Bing Webmaster Tools HTML-tag token (`msvalidate.01`) on `/` |

The tokens are public by design but belong to whoever owns the Search Console property, so
they live in the hosting project's environment, not the repository. A build without a public
origin (local package, an analysis API on this computer, other hosts without the variables)
serves `Disallow: /` and an empty sitemap.

Registration (owner): add a URL-prefix property for the origin in Google Search Console, set
the HTML-tag token, redeploy production and verify, then submit `sitemap.xml`. In Bing
Webmaster Tools, import the property from Search Console (or set the Bing token the same way).
Keep the tokens set afterwards; removing them revokes verification.

### Custom domain

The public site is served at `https://cytellect.app` (Cloudflare Registrar and DNS; the
records point to Vercel with the Cloudflare proxy off). The former address
`cytellect.vercel.app` answers every path with a permanent (308) redirect to the same path
and query on `cytellect.app` (`next.config.ts`); preview deployments are not redirected.
The redirect is kept indefinitely so links in papers, released packages and documents keep
working. `www.cytellect.app` redirects to the apex in the Vercel domain settings.

Page measurement accepts only `https://cytellect.app` (`LandingAnalytics.tsx`,
`public/lp-metrics.js`), so previews and the former address are never counted. Indexed pages
also carry Open Graph and X card metadata built from the public origin (`sharePreview` in
`src/lib/site.ts`). The domain sends no mail yet: its SPF (`v=spf1 -all`) and DMARC
(`p=reject`) records reject spoofed senders until a sending service is configured.

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

`/workspace` first asks `GET /v1/local/session`. It gives the same answer as
`GET /v1/session`, but as 200 with `authenticated: false` before the start and
after a relaunch revokes the cookie, instead of a 401 that the browser logs as an
error; a GET never issues a session. The cloud sign-in routes (`/v1/account*`)
accept only this PC's own session, not an invitation's, so local browser tests
open the workspace with `POST /v1/local/session`, as `解析を開始` does.

Connection failures (genellect/cytellect#284) are told apart in the API client
(`apps/web/src/lib/api.ts`, state in `lib/local-connection.ts`) and shown by
`ConnectionNotice` above the workspace, which then hides the general error line
and its 「再読み込み」:

| Failure | Detected as | Workspace |
|---|---|---|
| No answer (not sent, or the answer lost) | `fetch` throws; the client raises `api_unreachable` with status 0 instead of the browser's `Failed to fetch` | 「ローカルのサービス：接続なし」, 「再接続」, 「再開には、デスクトップの「Cytellect」の起動が必要です。」; `/v1/local/setup` is checked every 5 seconds |
| Ended session | 401 `session_required` on a page that has used a session | `POST /v1/local/session`, then the same request once more (one shared renewal for concurrent requests). A second 401 shows 「作業画面のセッション：終了」 and 「再接続」 |
| Wrong origin | 403 `local_origin_required`, or a non-loopback page | 「ローカルのサービス：接続の拒否」 and 「作業画面には、デスクトップの「Cytellect」から開いた画面が必要です。」 |

A request without an answer is never repeated, because the API may have
accepted it; a 401 is answered before the route runs, so its single repeat
writes nothing twice. Session routes, an explicit `DELETE /v1/session` and a
page that has not used a session yet (it starts from 「解析を開始」) are never
renewed. When the service answers again, the runtime's `reconnected` reads the
rows and fields again: a row whose upload reached the API shows as registered,
a `pending` row keeps its names for 「差し替え」 under the same row ID, and
recorded targets are placed. A new workspace with nothing saved yet has nothing
to re-read and is never replaced by the workspace that was open before it. The notice also shows the previous launcher run's
abnormal stop from `GET /v1/local/previous-stop`
(「前回の停止：計算処理の停止 · 11月23日 18:28」; codes in
[local delivery](local.md#stop-and-restart-停止と再開)) until the researcher closes it; the browser
remembers the closed stop's reason and time, so a reload does not show it again. The hosted build keeps
its session rules (no renewal, no notice); its no-answer error reads
「APIに接続できません。…」. `tests/local-connection.spec.ts` checks the notice
against the local static build with mocked routes (`CYTELLECT_LOCAL_UI_URL`).

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
`tests/local-workspace-start.spec.ts` checks, without images or Fiji, that opening
`/workspace` and starting it give no 401 and no console error.
Installer distribution is separate from this browser bundle; the public UI does
not advertise a download until a concrete release artifact is available.
