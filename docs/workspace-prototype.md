# Workspace prototype — redesign step 1

`/workspace` is the operable prototype of the [single analysis workspace](workspace-redesign.md). It exists so that the screen structure and operations can be reviewed before the analysis API and the proposal service are connected. It does not run detection or measurement.

## What it does

- **Add images**: files or a folder (TIFF/OME-TIFF names), or 公開画像で試す. A workspace is created on the first addition, without a form.
- **Grouping**: `apps/web/src/lib/workspace/grouping.ts` pairs fields by removing one delimited channel token from the file name, or uses a channel folder. Index tokens (`c1`, `Channel1`, `w1`) never establish a stain. Duplicate candidates for one field/channel, missing channels and identical content stay visible issues; file order never pairs files.
- **Proposal**: `proposal.ts` combines registered recipes from confirmed channel roles. Unknown stains block the run until one set-wide channel table is applied. Without groups and independent units, the proposal is descriptive (per-field distributions).
- **Run**: field runs are queued with concurrency 1 and committed one by one. Completed fields can be inspected while others run. A failure stays on its field with 再実行.
- **Review and correction**: image outlines, table rows and figure points are cross-linked. 対象から除外 / 領域を削除 with undo/redo (Ctrl/⌘+Z, Shift for redo) affect only that field's values and figure. Figure styling (width, height, axis name, metric) never reruns analysis.
- **Export**: the existing API-produced SVG, CSV and figure legend for the same public images. After any prototype correction, export is disabled with its reason, because corrected outputs must be produced by the API.

## Data and boundaries

The public sample is BBBC013 wells A01, A06 and A12 (CC BY 3.0, Ilya Ravkin / Broad Bioimage Benchmark Collection). `scripts/workspace_prototype_assets.py` builds `apps/web/public/prototype/bbbc013/` from registered fixtures only: display-scaled previews (1–99.8 percentile), the recorded Fiji/StarDist measurements from `fixtures/public/bbbc013/benchmark.json`, and the A01 outlines from the public sample viewer. Region identifiers match across these sources and the exported figure table. Outlines for A06 and A12 are not recorded, so those fields show values without outlines. Run `uv run python scripts/workspace_prototype_assets.py --check` to verify the committed files.

The original BBBC013 member names (`Channel1-…`, `Channel2-…`) are used as file names, which demonstrates the set-wide mapping: Channel1 is FKHR-EGFP and Channel2 is DRAQ (nuclear stain), as recorded in the fixture manifest.

The prototype adapter (`adapter.ts`) replays recorded outputs and computes per-field quartiles of those existing values for display only. These summaries stand in for the API's saved descriptive output; they are not authoritative results. Files added by the user are grouped in the browser but not uploaded or analysed; their runs fail with an explicit message. Region reshaping, adding images after adoption, unit-level comparisons and PDF output require the API connection (step 3).

## Review checklist (step 2)

1. Multiple images → proposal → adopt.
2. Unknown channel mapping corrected once for all fields.
3. Inspect a completed field while others run.
4. Correct a nucleus (exclude/delete) and see only that field's figure change.
5. From a figure point to its source image/region; export.

`apps/web/tests/analysis-workspace.spec.ts` automates these operations at 1366×768, 1440×900, 1024×768 and 390×844. Automated passes do not replace the owner's operational review.
