# Sol and real-workspace integration — 2026-10-05

This increment connects `/workspace` to the existing private API. It does not
replace `/`, redesign the LP, update an installed release, or establish biological
validity. The explicit BBBC013 demonstration retains its separate adapter.

## Implemented

- Real file upload, original-coordinate Fiji nuclear masks, raw channel area and
  intensity, server-owned measurements, revision-based exclusion/deletion and
  Undo/Redo, saved descriptive SVG/PDF/CSV and source-linked figure points.
- Raw measurement protocol 3.0.0 preserves missing background corrections. Nuclear
  role selection and observed channel identity do not fabricate human confirmation.
- Sol `gpt-6.1-sol`, medium reasoning, strict proposal contract 1.1, local scientific
  validation, durable private draft reuse, request idempotency, atomic D1 usage
  settlement and conservative budget reservation. Proposal failure does not block
  registered analysis. Proposals are advice until explicitly adopted.
- Optional API-only Docker egress and a mounted device-token secret; the analysis
  worker remains offline. Default Compose has no proposal connection.

## Evidence obtained

- Web type/lint checks and 329 unit tests passed.
- Raw API tests save actual child-worker descriptive figures without marking the
  analysis reviewed. Separate raw bundle tests reproduce measurements, descriptions,
  comparisons and vector outputs, and reject forged protocol/background states.
- A real browser run used hash-verified BBBC007 original DNA/actin TIFFs, with
  index-only filenames and explicit nuclear-channel selection. Fiji detected
  115 nuclei; 230 channel rows matched independent arithmetic over the original
  TIFFs and saved label mask with maximum absolute error 0. Excluding one region
  changed the descriptive count from 115 to 114. Editable-text SVG, PDF, CSV and
  Methods were saved. No private images or mock detector were used in this run.
- The first live-browser attempt exposed a wrong result endpoint in the new
  adapter. It was corrected to the existing `/v1/jobs/{id}/result` endpoint and the
  workflow rerun. Mocked transport checks alone had not caught this error.

These are implementation observations, not evidence of detection F1, statistical
power, independent biological replication or researcher usability. Full required
CI and installed-package acceptance remain separate from the focused checks.

## Remaining delivery and product work

1. Finish full regression, real-Fiji CI, exact installed-copy and Docker acceptance;
   merge reviewed changes through protected main and inspect canonical Vercel routes.
2. Run the approved public Sol evaluation within **5 USD total**, using a dedicated
   key on the owner's existing OpenAI account. Production paid calls are not approved.
   Record actual usefulness, semantic rejections, latency, usage and failure cases.
3. Verify remote Worker/D1 migrations and rights independently; do not enable paid
   production service merely because source tests pass.
4. Complete the new workspace's multichannel OME intake, full mask corrections,
   background/compartment workflow, explicit proposal adoption, condition/unit
   confirmation, independent-unit statistics and combined figures. The current new
   screen exposes per-field nuclear raw measurements; existing NCL compartment and
   common-statistics implementations are not yet fully connected to this screen.
5. Obtain the owner's operational review before replacing the previous root
   workspace. Keep M4 private-image and M5 researcher evaluation open.

The `test_installed_region_acceptance` comparison-tampering check now selects a
comparison result by its schema instead of filesystem iteration order. The full
installed harness must still confirm this fix. Older results with the same count
or p-value are not substituted for a rerun on the accepted source.
