# Single workspace — real adapter and explicit public prototype

`/workspace` now uses the real API adapter of the [single analysis workspace](workspace-redesign.md). The recorded public prototype is available only at `/workspace?demo=bbbc013`. The two modes do not share results or exports.

## Real API path: current integration increment

- Add separate-channel 2D TIFF files or a folder. Grouping uses filename/folder evidence and content hashes; unknown channels keep their token. An API workspace is created automatically, uploads retain retry IDs, and server metadata and previews are used after import. Duplicate channel candidates, missing channels and duplicate content remain visible rather than silently selecting a file. The public site cannot connect to a loopback API, including an accidentally configured loopback origin.
- Choose the nuclear-detection channel once when names do not decide it, then run. Region recipe 1.2.0 records `recorded_stain` or `user_selected_role`; imported channel identity records its evidence under field input 1.1.0. Neither operation fabricates the historical human-confirmed flags.
- The existing offline Fiji/StarDist worker detects nuclei and measurement protocol 3.0.0 measures their area and raw mean/median/integral in every acquired channel. Raw-intensity policy 1.1.0 has no established background: corrected measurements remain missing, never zero. No chemical identity is inferred from channel numbers. A channel labelled NCL is measured within nuclei; this increment does not claim nucleolar or nucleoplasmic measurements.
- Runs commit per field. Failed fields retain an error while successful fields keep their measurements. Interrupted polling resumes a known job without re-submitting it; an uncertain submission requires reloading and checking server state. The workspace URL retains the owned workspace ID, and reopening reads saved fields/revisions/jobs. Session storage retains revision identifiers only, including an undone revision choice, never pixels or measurements.
- Images, measurement rows and figure points are linked. Excluding or deleting a selected region uses the existing immutable reconfiguration/mask-edit routes. Undo/redo selects saved revisions. The canonical mask version accompanies edits; successful remeasurement replaces the selected field's derived output.
- Descriptive figures use `/descriptive-preview`. Both the screen and saved output identify the unreviewed detection state. Numerical points and quartiles come from the server; the interactive display does not calculate authoritative measurements or summaries. SVG/PDF/PNG, source CSV and Methods come from owned server artifacts. Style changes submit a figure job, never another Fiji detection. Exports are tied to the exact revision, metric, channel and figure settings currently displayed.
- Optional proposal advice requires an explicit workspace-level transmission choice. The browser sends only the goal and consent to `/proposal-drafts`; the server owns the metadata context. The notice identifies the external services and retention caveat. The draft is displayed as advice and is not silently applied to the analysis. Service failure does not block registered-recipe analysis.

This is a bounded real-adapter increment, not completion of the full redesign. It currently produces per-field descriptive figures. Multi-channel OME header import, nuclear/nucleolar NCL ratios, supplied masks, group/unit comparisons, arbitrary region reshaping and a complete review/adopted-proposal interface are not connected in this screen. Other existing workflows retain their separate capabilities. Detection accuracy, researcher usability, exact-package acceptance and public release remain separate gates. `workspace-api.spec.ts` uses mocked transport solely to test UI/contract behavior; `workspace-real-fiji.spec.ts` is an opt-in actual Fiji/public-image test and requires an isolated runtime and registered input paths.

## Explicit recorded prototype: what it does

- **Add images**: files or a folder (TIFF/OME-TIFF names). A workspace is created on the first addition, without a form. The start screen states the three steps and what each one does.
- **Grouping**: `apps/web/src/lib/workspace/grouping.ts` takes one channel per file. A named stain (also with a dye or wavelength number, e.g. `Hoechst33342`) wins over channel numbers, and channel numbers (`c1`, `Channel1`, `w2`, also glued as in `xy01c1`) are removed from the field key, so `A01_s1_w1_DAPI.tif` and `A01_s1_w2_GFP.tif` form field `A01-s1`. A channel folder is used when the name has neither. Two stains in one name, or two numbers without a stain, are never guessed. Index tokens never establish a stain; file order never pairs files. A name-less OME-TIFF is kept as pending: its channels are read from the header on import (API), and `omeChannels` expands one file into one field.
- **Nothing is dropped silently**: 読み込み結果 lists files → fields → channels and every file or field needing attention (unidentifiable, pending OME, duplicate slot, identical content, missing channel) with what happens to it. With no usable field the run stays unavailable.
- **Proposal**: `proposal.ts` combines registered recipes. The only channel decision is which channel detects nuclei: when a file or OME name already names a nuclear stain (DAPI, Hoechst, DRAQ), nothing is asked; otherwise the researcher clicks one channel thumbnail. All other channels are measured. Stain names are optional (解析条件) and unknown stains keep their channel name. Without groups and independent units, the proposal is descriptive (per-field distributions) and nothing more is asked.
- **Run**: field runs are queued with concurrency 1 and committed one by one. Completed fields can be inspected while others run. A failure stays on its field with 再実行.
- **Review and correction**: image outlines, table rows and figure points are cross-linked. 対象から除外 / 領域を削除 with undo/redo (Ctrl/⌘+Z, Shift for redo) affect only that field's values and figure. Figure styling (width, height, axis name, metric) never reruns analysis.
- **Export**: the saved API outputs of the registered example (area figure 178 × 76 mm, area CSV, legend) are offered only when every field of the example is analysed, nothing was corrected and, for the figure, the displayed metric and size match the saved output. Otherwise each item is disabled with its reason; files the user added never receive the example's outputs.
- **Keyboard**: every region can be selected from the measurement table (one button per row); image outlines and figure points mirror the selection. A stopped run resumes with the fields still waiting.

## Input principle

Ask only what cannot be derived, only when needed, once for the whole set, with a default already filled in. Routine use is two operations (add images, run) plus at most one click. The browser test asserts that no text field or select box is visible before running.

## Design and wording

The workspace uses the public site's visual language (`product.module.css`): midnight paper `#030916`, blue actions `#236bf1` with `#5d91ff` edges, hairline rules, 3 px corners, Inter/Noto Sans JP. Figures are shown as white exported paper, as on the site. Each state says what is happening and what to do next: the start screen lists the three steps, the proposal lists what running will do, the result view lists the next operations, and the figure view says that a point opens its image. Wording names the operation or the fact; it avoids promotional or explanatory filler.

The app icon (`apps/web/src/app/icon.svg`) is a cell outline with an offset nucleus and nucleoli in the site's blue on midnight.

## Data and boundaries

The registered example is BBBC013 wells A01, A06 and A12 (CC BY 3.0, Ilya Ravkin / Broad Bioimage Benchmark Collection). It is not offered inside the workspace UI; it opens only from a link, `/workspace?demo=bbbc013`, for the owner's review, the browser tests and a possible link from the public site. `scripts/workspace_prototype_assets.py` builds `apps/web/public/prototype/bbbc013/` from registered fixtures only: display-scaled previews (1–99.8 percentile), the recorded Fiji/StarDist measurements from `fixtures/public/bbbc013/benchmark.json`, and the A01 outlines from the public sample viewer. Region identifiers match across these sources and the exported figure table. Outlines for A06 and A12 are not recorded, so those fields show values without outlines. Run `uv run python scripts/workspace_prototype_assets.py --check` to verify the committed files.

The original BBBC013 member names (`Channel1-…`, `Channel2-…`) are used as file names, so the one-click nuclear choice is exercised: Channel2 is DRAQ (nuclear stain) and Channel1 is FKHR-EGFP, as recorded in the fixture manifest. Because the names do not state the stains, the prototype labels them channel1/channel2 unless the researcher names them.

The explicit prototype adapter (`adapter.ts`) replays recorded outputs and computes per-field quartiles of those existing values for display only. These summaries stand in for the API's saved descriptive output; they are not authoritative results. Files added while in that explicit demo mode are not uploaded or analysed; they never receive sample results. The default real path uses `api-adapter.ts` and `ApiWorkspace.tsx` instead.

## Review checklist (step 2)

1. Multiple images → proposal → adopt.
2. One click on the nuclear channel when names do not decide it; no other input before running.
3. Inspect a completed field while others run.
4. Correct a nucleus (exclude/delete) and see only that field's figure change.
5. From a figure point to its source image/region; export.

`apps/web/tests/analysis-workspace.spec.ts` automates these operations at 1366×768, 1440×900, 1024×768 and 390×844. Automated passes do not replace the owner's operational review.
