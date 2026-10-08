# Workspace repair: stage 1

The owner approved the comprehensive October 7 repair plan. Stage 1 is an operable UI review before replacing the main Docker workspace or changing scientific processing.

## Delivery boundary

- Separate local route `/workspace-review`; existing `/` and `/workspace` remain unchanged by this increment.
- Reads existing owned images, adopted biological masks and measurement values. It does not upload, run segmentation, change adoption, call the LLM, calculate statistical tests, or save scientific settings.
- Existing Desktop session bootstrap is the only authentication write; no new permissions or credentials.
- Image/Statistics/Figure navigation, channel switching, optimal-fit comparison layout, zoom/pan, region/table selection, graph-point source navigation and axis-label/range editing can be exercised.
- The SVG point view displays saved observations for UI review. It is not the final publication renderer; Matplotlib output remains the production requirement.
- Measurement, new upload, AI send and export are visibly unavailable on this review route. Draft controls do not apply scientific changes; no fabricated results are shown.

## Owner clarification

Biological objects are the unit, not disconnected positive pixels. In the intended single-nucleus assay, one adopted nucleus represents one cell for counting; GFP-positive cells are the positive subset of these cells, not necessarily all DAPI nuclei. This does not infer the whole-cell boundary or generalize the single-nucleus assumption to all specimens. Whole-cell GFP measurements use a separate cell ROI. New foci/dot recipes remain outside this increment.

## Approval sequence

1. Show the separate stage-1 route in Edge using saved local data.
2. Obtain layout/interaction feedback and approval before main-route replacement.
3. Implement shared scientific state, bindings, processing, AI, statistics and replay in the approved sequence.
4. Deliver Docker increments before cloud release. Keep source, CI, deployed runtime and biological validation evidence distinct.

No private images, paths, workspace IDs, measurements or screenshots belong in this document or repository. Existing scientific requirements and the October 7 audit remain applicable.

## Local verification, October 7

- Docker Web rebuilt and restarted without recreating API or worker containers.
- TypeScript, scoped lint, production build and eight targeted tests passed.
- Edge: saved nuclear defining channel selected initially; switching to absent nucleolar results does not retain the nuclear mask.
- Edge: image comparison, point-to-source navigation and return, and axis label editing exercised.
- At 1920 x 1080 the selected square image occupied approximately 826 x 826 pixels. At the normal 1272 x 554 viewport there was no page-level overflow; image size remains constrained by available height.
- This is not approval of scientific processing or the complete UI acceptance matrix. Synchronized comparison viewports, editing tools and scientific execution remain subsequent work.
- Source is local and uncommitted at this review checkpoint; no cloud publication was performed.
