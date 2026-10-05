# Workspace prototype — redesign step 1

`/workspace` is the operable prototype of the [single analysis workspace](workspace-redesign.md). It exists so that the screen structure and operations can be reviewed before the analysis API and the proposal service are connected. It does not run detection or measurement.

## What it does

- **Add images**: files or a folder (TIFF/OME-TIFF names). A workspace is created on the first addition, without a form. The start screen states the three steps and what each one does.
- **Grouping**: `apps/web/src/lib/workspace/grouping.ts` pairs fields by removing one delimited channel token from the file name, or uses a channel folder. Index tokens (`c1`, `Channel1`, `w1`) never establish a stain. Duplicate candidates for one field/channel, missing channels and identical content stay visible issues; file order never pairs files.
- **Proposal**: `proposal.ts` combines registered recipes. The only channel decision is which channel detects nuclei: when a file or OME name already names a nuclear stain (DAPI, Hoechst, DRAQ), nothing is asked; otherwise the researcher clicks one channel thumbnail. All other channels are measured. Stain names are optional (解析条件) and unknown stains keep their channel name. Without groups and independent units, the proposal is descriptive (per-field distributions) and nothing more is asked.
- **Run**: field runs are queued with concurrency 1 and committed one by one. Completed fields can be inspected while others run. A failure stays on its field with 再実行.
- **Review and correction**: image outlines, table rows and figure points are cross-linked. 対象から除外 / 領域を削除 with undo/redo (Ctrl/⌘+Z, Shift for redo) affect only that field's values and figure. Figure styling (width, height, axis name, metric) never reruns analysis.
- **Export**: the existing API-produced SVG, CSV and figure legend for the same public images. After any prototype correction, export is disabled with its reason, because corrected outputs must be produced by the API.

## Input principle

Ask only what cannot be derived, only when needed, once for the whole set, with a default already filled in. Routine use is two operations (add images, run) plus at most one click. The browser test asserts that no text field or select box is visible before running.

## Design and wording

The workspace uses the public site's visual language (`product.module.css`): midnight paper `#030916`, blue actions `#236bf1` with `#5d91ff` edges, hairline rules, 3 px corners, Inter/Noto Sans JP. Figures are shown as white exported paper, as on the site. Each state says what is happening and what to do next: the start screen lists the three steps, the proposal lists what running will do, the result view lists the next operations, and the figure view says that a point opens its image. Wording names the operation or the fact; it avoids promotional or explanatory filler.

The app icon (`apps/web/src/app/icon.svg`) is a cell outline with an offset nucleus and nucleoli in the site's blue on midnight.

## Data and boundaries

The registered example is BBBC013 wells A01, A06 and A12 (CC BY 3.0, Ilya Ravkin / Broad Bioimage Benchmark Collection). It is not offered inside the workspace UI; it opens only from a link, `/workspace?demo=bbbc013`, for the owner's review, the browser tests and a possible link from the public site. `scripts/workspace_prototype_assets.py` builds `apps/web/public/prototype/bbbc013/` from registered fixtures only: display-scaled previews (1–99.8 percentile), the recorded Fiji/StarDist measurements from `fixtures/public/bbbc013/benchmark.json`, and the A01 outlines from the public sample viewer. Region identifiers match across these sources and the exported figure table. Outlines for A06 and A12 are not recorded, so those fields show values without outlines. Run `uv run python scripts/workspace_prototype_assets.py --check` to verify the committed files.

The original BBBC013 member names (`Channel1-…`, `Channel2-…`) are used as file names, so the one-click nuclear choice is exercised: Channel2 is DRAQ (nuclear stain) and Channel1 is FKHR-EGFP, as recorded in the fixture manifest. Because the names do not state the stains, the prototype labels them channel1/channel2 unless the researcher names them.

The prototype adapter (`adapter.ts`) replays recorded outputs and computes per-field quartiles of those existing values for display only. These summaries stand in for the API's saved descriptive output; they are not authoritative results. Files added by the user are grouped in the browser but not uploaded or analysed; their runs fail with an explicit message. Region reshaping, adding images after adoption, unit-level comparisons and PDF output require the API connection (step 3).

## Review checklist (step 2)

1. Multiple images → proposal → adopt.
2. One click on the nuclear channel when names do not decide it; no other input before running.
3. Inspect a completed field while others run.
4. Correct a nucleus (exclude/delete) and see only that field's figure change.
5. From a figure point to its source image/region; export.

`apps/web/tests/analysis-workspace.spec.ts` automates these operations at 1366×768, 1440×900, 1024×768 and 390×844. Automated passes do not replace the owner's operational review.
