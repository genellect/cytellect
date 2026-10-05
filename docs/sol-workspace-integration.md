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
   background/compartment workflow, explicit proposal adoption and association UI.
   Condition/unit confirmation and independent-unit comparisons are now connected
   through immutable cohorts, with saved-mask reuse, historical-result marking
   and exact-source metadata recovery. Existing NCL compartment and association
   implementations are not yet fully connected to this screen.
5. Obtain the owner's operational review before replacing the previous root
   workspace. Keep M4 private-image and M5 researcher evaluation open.

The `test_installed_region_acceptance` comparison-tampering check now selects a
comparison result by its schema instead of filesystem iteration order. All nine
local installed-harness tests passed after that fix. This is not acceptance of a
newly published Windows ZIP or Docker image.

## Regression and evaluation follow-up

PR32's first Linux Python CI completed with 1323 passed, 142 skipped and three
failures: two migration tests still expected schema0002, and a Compose secret
target assertion assumed the CLI would retain relative short syntax. The
migration tests now check schema0003 while retaining original-row preservation;
the relay secret target is explicitly `/run/secrets/proposal_device_token`.
The focused migration/upload suite passed28 tests locally. After locating the
existing user-installed Docker Desktop CLI, the actual merged-Compose test passed
locally with its required flag enabled. Python CI also passed on commit afa9af6.

The committed afa9af6 worker image was built from a Git archive (no local secrets
or in-progress edits) and tested in Docker Desktop29.6.1. The actual Fiji smoke
passed as UID10001 with a read-only root and only the loopback network interface:
9 nuclei,18 nucleolar candidates, unchanged original pixels, and private temporary
files. Its dedicated test volume did not replace the existing human-E2E services.
The fixed Fiji build stage now depends on its installer and runtime lock rather
than application code, allowing Docker to reuse it for subsequent app updates.
This does not establish a new full-stack release or human usability acceptance.

The first approved live Sol evaluation stopped at its first provider error.
After adding bounded allowlisted diagnostics, a second attempt identified
HTTP429 `insufficient_quota`. No successful proposal was received; further
requests are stopped pending the operator's billing/quota resolution. The
external cumulative ledger conservatively retains both reservations (about0.434
USD), rather than treating them as confirmed charges or resetting the cap.
The approval remains5 USD total across all attempts; paid production use remains
disabled. All43 provider/ledger/contract unit tests passed; the live evaluation
did not pass.

## Git handoff and comparison follow-up

The [Claude production handoff](claude-production-handoff-2026-10-05.md) identifies
the committed source and remaining publication gates. PR32 head ccf01f6 passed
all five required checks in run37299191396, including real Fiji/browser and
Windows3.14. Subsequent category-padding renderer1.0.1 changes passed23 focused
figure/API/export-replay tests, Ruff and mypy; old/new vector replays retain their
saved renderer version and numeric tables/Methods are unchanged. Latest-head CI
must pass separately. No PR32 main merge or new package/relay production is
claimed by this handoff. The correct COMPASS/Cytellect key has been issued and
saved to the approved ignored env-file through the secure connector. A free model
metadata request returned HTTP200; successful Responses generation and paid public
evaluation remain open. The approved budget remains5 USD cumulative evaluation only.
