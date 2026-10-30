# Single analysis workspace and analysis proposals — 2026-10-05

This document adopts the owner's October 5 redesign decision. The October 4
acceptance of the multi-panel analysis presentation is superseded: the human
end-to-end review found that the workspace required too many settings and
confirmations before a result appeared. Scientific contracts, original-pixel
semantics, immutable revisions and experimental-unit inference are unchanged.

## Completion condition

A researcher adds many images, reviews one analysis proposal once and runs it.
Field grouping, region detection, measurement, statistics and figures follow
automatically. Results are reviewed and corrected in the same workspace, and
editable figures, tables and Methods are exported from it. Routine operation
does not require connecting jobs or repeating the same confirmation per field.

Implementation order: workspace UX → operable prototype review → connection
and automation of existing processing → proposal API/LLM → combined operational
and numerical acceptance → publication. Because the proposal service does not
depend on screen layout, its contract, validator and relay may be built in
parallel, disabled by default, and connected to the UI only after the prototype
review.

## Interaction model

Three routine operations:

1. **Add images** (files or a folder). A workspace is created automatically.
   Since 2026-10-25 a new workspace first asks for the form of the experiment
   (1 screen: describe one group; 2 screens: compare two groups) and then takes
   images per group and independent run ([group comparison](drafts/group-comparison/requirements.md),
   E-01–E-08, owner decision amending U01). The first images added before the form
   is chosen wait for it (2026-10-28 owner decision): 1 screen takes them, 2 screens ask for the
   run and group, and "形を決めずに登録" registers them without a design, with groups
   typed per field in statistics; images added to a design without a place are listed
   as unassigned fields.
2. **Review the proposal and press 解析を実行.** The analysis goal is optional
   free text; without it, a proposal is built from images and channel names.
3. **Review results**, correct where needed and export.

Layout (desktop first; tablet collapses panels; mobile prioritizes viewing):

| Area | Content |
|---|---|
| Header | Workspace name, processing status, 画像を追加, 書き出し |
| Left | Field list with group/search filters; figure list |
| Center | The selected image or figure, large |
| Right | Operations for the current selection only: channel display, region editing, figure settings, comparison conditions |
| Bottom drawer | Measurement table, opened on demand |

The image view is where researchers check what is measured, so one rule holds
for one field and for two groups side by side (owner review, 2026-10-26):
each image shows its whole field at its own aspect ratio on opening (never
cropped to fill), and that field's measurement table sits beside it, or below
it when that leaves the image larger, with a readable minimum (8 rows below,
260 px beside). Two screens draw both fields at one shared scale (V-01), and the
two fields they open on load together, before the remaining fields
([group comparison](drafts/group-comparison/requirements.md), V-01, V-04,
N-03, N-08). Hiding the tables enlarges the images; zoom shows detail.

What the image shows is the structure the metric measures, not the region set
its values are read from (Codex final review, 2026-10-26, V-04). A per-nucleus
value of the nucleoli (eccentricity, total area, count, area fraction) is read
from the nucleoplasm set but labelled 「核小体（核ごとの値）」 and checked on the
nucleoli; opening such a value from a figure shows that saved analysis's
nucleoli with its nucleus outlined. Saved tables lead with the field to open,
its run and group, the region and the value; an observation's sample, date,
selection state, versions and internal ids are folded under 「記録の詳細」
(N-06). Folded tables are drawn only once opened, since a saved table can hold
every observation.

Analysis conditions, history and retention live in a menu. There is no
"complete step 1 before step 2" page structure. Errors never reset the
workspace; successful fields keep their results.

| State | Center | User action |
|---|---|---|
| Empty | Drop area and optional goal | Add images |
| Importing | Fields appear as they arrive | Add more |
| Proposal ready | Representative image with detection preview, short summary | Run, or change one item |
| Running | Completed fields with regions and values; progress count | Inspect, stop |
| Results | Image, measurements, generated figures | Correct, compare, export |
| Partial problems | Status on affected fields only | Fix or rerun those fields |

The proposal summary shows only: field count and channel mapping, detected
regions, main measurements, comparisons and figures, and the run button.
Thresholds, smoothing, area limits and background detail are under 解析条件.
When names do not decide which channel detects nuclei, the researcher clicks one channel thumbnail once for the whole image set; every other channel is measured, and stain names are optional. Unknown
experimental units do not block image analysis or descriptive figures; the
information needed for inference is requested where the comparison is shown.

The retired step-1 prototype (`/workspace?demo=bbbc013`) is kept as a historical record in [workspace prototype](archive/workspace-prototype.md). The public demo now runs the production workspace serverless ([public demo](showcase.md)).

Corrections: selecting a figure point opens its source image and region (or
the samples/fields of an experimental-unit point); selecting a region
highlights its table row; editing a nucleus invalidates only dependent nucleoli,
measurements, statistics and figures. Earlier results stay visible and marked
「更新中」 while recalculating. Figure styling never reruns image analysis or
tests.

Wording uses operation names: 画像を追加／フォルダを追加, 解析案／解析条件,
解析を実行／中断／再実行, 領域を修正／対象から除外, 測定値／グラフ／比較条件,
書き出し／SVG／PDF／CSV. No slogans in the application. Light neutral working
surface, dark image area, blue for emphasis, Inter/Noto Sans JP, 16 px body and
13–14 px minimum for tables. The LP, its Three.js artwork and GA4 are not part of
this change and remain excluded from application routes.

## Automation rules

**Import and grouping.** Read header, axes, dtype and dimensions; extract OME
channel names, filenames and folder structure; build field candidates by
removing a delimited channel token from the filename; detect duplicates
(content hash), missing channels and contradictions. Explicit user corrections
win and are recorded with the original evidence. Two candidates for the same
field/channel remain unresolved; file order never decides. `c1`/`c2` alone never
establishes DAPI/GFP/NCL; colour or morphology never establishes a stain. Stain
name and the role "nuclear detection" are stored separately. Date, group and
sample candidates may be extracted, but folder counts never become independent
experimental units. Z/T, RGB compatibility and CZI conversion keep their
current limits; nothing is silently projected or converted. Files whose channel
is unresolved are held in an importing state.

**Proposal.** A proposal is a combination of registered recipes, never free
code: nuclear stain + measured channel; nuclear stain + NCL; nuclear stain +
NCL + GFP; supplied masks/ROIs; a registered intensity-threshold region recipe
(named "intensity-defined region", not a biological structure); measured CSV.
Representative fields are chosen deterministically from batch, channel layout
and image-quality indices, deliberately including dark, bright and dense
fields. The representative trial runs automatically; the full batch starts only
after the proposal is adopted.

**Detection.** Existing Fiji/StarDist 2D Versatile with percentiles 1–99.8,
probability 0.5 and NMS 0.3 is the stored starting setting; identical
acquisition conditions use identical settings, and a change records its scope
and reason. Nucleolar candidates keep the per-nucleus Otsu procedure and the
states candidate / no candidate / indeterminate / failed. Because NCL defines
the regions in which NCL is measured, region changes can follow signal
changes. The proposal therefore (a) recommends an independent nucleolar marker
when one was acquired, and (b) always reports per-condition no-candidate rates
and nucleolar area alongside NCL ratios so condition-dependent region
definition is visible.

**Background.** Three modes: user ROI; versioned automatic candidate; or no
established background (raw values only). The automatic candidate is a new
recipe, never recorded as human-confirmed: exclude detected regions, bright
regions per channel and a dilated perinuclear margin; tile at 32×32 px; keep
tiles with ≥90 % unexcluded pixels; reject extreme or high-dispersion tiles by
median/MAD; require ≥4 tiles in ≥3 image quadrants; report the median of the
remaining pixels. Failure leaves corrected values and ratios missing with a
reason, without stopping the analysis. Confluent fields, diffuse GFP, uneven
illumination and low signal are required counterexamples.

**Measurements** keep [methods](methods.md): `b = median(I[B])`, corrected mean
`mean(I[R]) − b`, corrected integral `ΣI − |R|b`, both raw and corrected, no
clipping, µm² only with calibration, midpoint median, union-pixel nucleolar
mean, ratios only for positive corrected means, legacy ε only in its own recipe.

**GFP selection** is not added unless requested. A confirmed negative control
yields a threshold candidate; otherwise manual or batch Otsu is proposed and
labelled exploratory. Group names never imply a negative control.

**Statistics** are proposed from goal, groups, independent units and pairing,
never from observed p-values or normality pretests: Welch t, paired t, Welch
ANOVA + planned contrasts, Mann–Whitney U, Wilcoxon, Kruskal–Wallis + planned
contrasts, Pearson, Spearman; descriptive figures when units are unknown.
Default aggregation remains field median → sample mean → unit mean, with cell,
field and unit counts shown separately and Holm over the pre-declared family.

**Figures** generated automatically: group distributions with observations,
unit-identified comparisons, paired connectors and association scatter. Each
figure states what one point is. Export SVG/PDF/300 dpi PNG, source table,
comparison results and effect sizes, units/missingness/exclusions, caption,
Methods and input/mask identities.

### Deliberate changes to the submitted plan

- **No automatic exploratory regression p-values.** The submitted plan listed
  regression lines with 95 % CI among automatic figures. A null simulation of
  the existing field-clustered exploratory model (3 units per group, 3 fields
  per unit, 30 cells per field, unit/field/cell SD 1.0/0.3/1.0, 400 runs, seed 1;
  `uv run python scripts/exploratory_model_null_simulation.py`) gave a type I
  error of 0.3225 (95 % CI 0.279–0.370) at α = 0.05, versus 0.0275
  (0.015–0.049) for the experimental-unit tests. Automatic
  proposals therefore never include that model; it stays an explicit
  specialist recipe until its clustering is corrected under a new statistics
  version.
- **Proposals send no images.** Recipe choice follows from stain names, channel
  layout and the stated goal. Requests send the goal and normalized metadata
  only; requirement L03 caps any future image transmission at six downscaled
  previews after the researcher enables it.
- **Segmentation validity is a separate gate.** Execution success on public
  images and same-mask ImageJ agreement are not detection accuracy. D04
  annotated evaluation remains required before claiming nuclear, nucleolar or
  foci accuracy.

## State, API and scale

The frontend moves from per-screen forms to one workspace state: import
(files, hashes, axes, field grouping, channel candidates), proposal (goal,
targets, recipes, metrics, statistics, outputs, unresolved items), adoption
record (proposal + input version), run (per-field state, progress, failures,
retries), results (mask/measurement/statistics/figure versions and
dependencies) and corrections (change, scope, before/after). Automatically
generated, researcher-adopted and human-corrected states stay distinct.
Adopting a proposal is not a record that every region was inspected. Existing
`confirmed: true` fields are never filled automatically; new contracts carry
the new states and stored analyses keep their original meaning.

Inputs follow one rule: ask only what cannot be derived, only when it is
needed, once for the whole set, with a default filled in. Endpoints take
identifiers and decisions, not descriptions of data the server already holds.

New `/v1` endpoints (Pydantic/OpenAPI source, generated TypeScript):
`POST /workspaces/{id}/imports`, `GET/PATCH /workspaces/{id}/imports/{import_id}`,
`POST /workspaces/{id}/proposals`, `POST /workspaces/{id}/proposal-drafts` (optional goal only; implemented),
`POST /workspaces/{id}/proposals/{proposal_id}/accept`,
`POST /workspaces/{id}/runs`, `GET /workspaces/{id}/runs/{run_id}`,
`POST /workspaces/{id}/runs/{run_id}/issues/{issue_id}/resolve`. Updates carry
an expected version; stale writes return a conflict; resubmitting the same run
request never runs twice.

Design target (an assumption, not a measured result): 1,000 fields with paged
lists, virtual scrolling, streamed or chunked upload, worker concurrency 1,
per-field result commitment, resume from unfinished fields, per-field limits
separate from batch state, Fiji bridge reuse per environment hash and capacity
checks that include masks and temporary data. The automatic-nucleus limit
(≤2,048 px per side, ≤2.7 Mpx) stays until memory and region agreement are
measured for larger images.

## Analysis proposal service (LLM)

The LLM organizes the goal and drafts a proposal. All measurements, masks,
statistics and Methods remain owned by the analysis package.

```text
Browser → local FastAPI (+ worker/Fiji/Python)
             ↓ normalized metadata; previews only when enabled
          Cytellect proposal service (Cloudflare Workers + D1)
             ↓
          OpenAI API (Structured Outputs, store: false)
```

- Input: goal text, normalized image metadata, optional ≤6 previews, groups /
  samples / pairing when known, available recipes and their conditions.
- Output (strict JSON schema): recipe ID, channel-role suggestions with
  reasons, metrics, aggregation/comparison/figure suggestions, missing
  information and registered method/literature IDs.
- Local semantic validation rejects unknown channels, metrics, recipes and
  references; absent GFP/NCL; inference without units/pairing; out-of-range
  parameters; and any code, URL or macro. A validated proposal still requires
  explicit adoption. The model never produces measurements, masks or p-values.
- The operator's API key lives only in the service secret; researchers never
  enter an API key, and the browser never receives a shared key. Access uses
  the existing invitation model; D1 stores invitation/device rights and usage
  counters, never research images or prompt bodies.
- Per-request input/image/output limits; usage is reserved before each call to
  prevent concurrent budget overrun; at most one repair retry (two calls); an
  adopted proposal for identical input is reused. A monthly limit and per-user
  quota are mandatory: without them, billable calls stay disabled. Service
  failure or exhausted quota leaves registered-recipe analysis fully usable.
- Model ID and prompt version are fixed and stored. The model is chosen from
  those passing a fixed evaluation set, then by cost.
- `store: false` is not zero data retention: the provider may retain data for
  abuse monitoring. The transmission scope is shown at first use and in
  settings, not repeated on every operation.

Source, configuration and operator deployment steps: [proposal service](proposal-service.md).

No new paid contract is approved by this document.
