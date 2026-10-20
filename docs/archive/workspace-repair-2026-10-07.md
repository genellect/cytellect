# Workspace integration repair — 2026-10-07

## Baseline and precedence

The October 6 workspace specification describes work already implemented by Claude. It is historical context, not a new backlog or authority to restore older interaction designs. This repair starts from main `00b9e3e` and the Docker Desktop runtime. Subsequent owner corrections take precedence: correct image/mask identity, useful image sizing, one integrated workspace, and AI instructions flowing into executable structured settings.

## Findings and repair scope

| Requirement | Existing implementation | Identified defect / repair |
|---|---|---|
| Original-coordinate image and mask | Fiji results and SVG overlays already exist | A new recipe could coexist with the previous result while running or after failure. Clear the displayed result during replacement and retain separate valid target history. |
| Separate nuclei, signal and nucleolar regions | Target caches and parent revisions already exist | Restore and validation assumed every nucleolar defining channel was NCL. Preserve the actual definition and reject unsupported target identities. |
| Readable image inspection | Zoom, drawing and comparison already exist | Nested sizing constraints created unused space and inner scrolling. Fit the image to its available viewport and size the single-image column using the original aspect ratio. Region numbers are optional; the selected region remains identifiable. |
| Integrated measurement and tools | Method/statistics/graph panels already exist | The measurement drawer competed with image height and AI input was hidden in one tool. Move measurements into the shared tool dock and keep AI input accessible across tools. |
| AI instructions become executable settings | Structured proposals and representative trials already exist | The closed proposal contract omitted detector settings. Extend the validated contract and carry accepted parameters into the effective execution recipe; preserve representative-trial behavior. No additional apply-confirmation step. |
| AI availability in Docker | Relay and device authentication already exist | The running API lacked the proposal Compose overlay. Restore the existing approved relay configuration without distributing the provider key. |

## Boundaries and acceptance

- No uploaded filename, stain color or channel number establishes biological stain identity.
- Uploading or navigating does not create a billable AI request. Explicit image-only submission remains supported.
- A textual proposal is not a measurement. The deterministic API/worker remain authoritative for masks, measurements and statistics.
- A representative trial does not authorize a new automatic batch. Existing user-selected batch operations remain explicit.
- The repair does not change scientific threshold defaults to conceal speckled results. A positive-pixel mask is not evidence of nuclei or nucleoli; channel/recipe/result identity must be established first.
- Preserve private volumes, existing adopted revisions and the existing monthly relay budget. Do not publish private images, file names or workspace identifiers with evidence.
- Validate stale-mask suppression during running and failure, definition-aware restoration, proposal-to-recipe parameter propagation, viewport/selection interactions, Docker availability and the Git-to-production deployment separately.
- Passing these checks does not establish biological segmentation accuracy or complete the broader researcher usability evaluation.

Deployment and test results are recorded with the associated pull request after execution; source edits alone are not a delivered fix.
