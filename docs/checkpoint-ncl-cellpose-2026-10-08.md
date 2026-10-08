# Cytellect NCL / Cellpose checkpoint — 2026-10-08

## Stop condition and scope

The owner requested that the current implementation be installed in Docker and
all repository changes saved to GitHub, then work and the active goal be paused.
This is a resumable checkpoint, not a declaration that nucleolar segmentation
accuracy is complete. The owner accepted the present implementation as the
temporary baseline. Do not resume parameter exploration, publish production
changes, merge this branch, or replace masks without renewed instructions.

Checkpoint branch: `codex/ncl-cellpose-checkpoint-20261008`.
Base main commit: `aadc2b47914d54ca83d7c26739ec5b581bf7cc19`.
The branch contains all previously uncommitted repository source changes,
including NCL detection, Cellpose provisioning/contracts, parent binding,
workspace state, AI panel restoration and proposal compatibility.

Private microscopy inputs, validation outputs, screenshots, model weights,
runtime data and credentials remain outside the checkout and must not be copied
into Git, CI, external AI requests or a public report. This document deliberately
does not publish specimen-specific results or private workspace identifiers.

## Current detection contract

- Nuclei remain adopted StarDist masks. Cellpose does not replace nuclear
  detection. NCL product detection requires the adopted parent mask.
- Explicit new NCL Cellpose selections use `cellpose-sam-ncl-parent/4.2.1`.
  Parent-conditioned inference retains the recorded 4.2.0 settings.
- After inference, split disconnected instances and reject an entire candidate
  if it covers more than the recorded `maximum_nuclear_coverage` (default 0.5)
  of a parent nucleus with parent purity at least 0.9.
- Never subtract nuclear pixels from an intranuclear nucleolar mask. Retain raw
  labels and exclusion measurements. Nuclear-scale rejection does not recover
  a nucleolus the model never detected.
- A parent with only rejected nuclear-scale candidates is indeterminate, not a
  measured zero. Candidate adoption remains a researcher action.
- Stored older protocols retain their historical semantics; existing results
  and manual edits are not silently upgraded. Original-coordinate labels and
  original input pixels remain authoritative for measurements.
- Pin Cellpose 4.2.1.1, CPU Torch 2.8.0 and the `cpsam_v2` model according to
  `engines/cellpose/runtime.lock.json`. Downloads are setup-time only, never
  inference-time. Existing classical NCL recipes remain replayable.

## Docker receipt

The `cytellect-human-e2e` API, worker and web images were rebuilt and restarted.
The existing research volume, owner access, retention and proposal budget were
preserved. The local workspace route returned HTTP 200. A current real-image
preview completed under protocol 4.2.1, reusing its adopted StarDist nuclear
revision, and the browser displayed the resulting NCL candidate set.

The running image identity is `aadc2b4+local-ncl421`: it explicitly identifies a
working-tree build made before this checkpoint commit, not a clean-main build.
Its application source is included in this branch. The final checkpoint document
does not change runtime behavior.

Image configuration IDs at this checkpoint:

| Image | Configuration SHA-256 |
| --- | --- |
| API | `1aca4ff5a112a78617dbf45040800f1b5ef08d5540bf380ff28e6a80935af103` |
| Worker | `806a9659d48360f28a804c40ce1b8e7375222787171594f2f8f2e1647fee5460` |
| Web | `3ea139a4daa6d7de46770804b2684b7195c0ffef98e27285e794c5c15fee5ae4` |

The local offline build reused the already provisioned runtime/model through a
wheel overlay. This is not evidence that a fresh Windows installer or a fresh
networked Docker build has passed. Follow the pinned setup/build scripts for a
new installation; do not substitute an unpinned runtime.

## Recorded verification

| Check | Result |
| --- | --- |
| Changed Python paths: Cellpose runtime, workspace runs, proposals | 60 passed |
| Web tests | 53 files, 484 passed |
| Web type/lint check | Passed; two pre-existing warnings remain |
| Proposal Worker check/tests | Passed; 75 passed, one skipped |
| Ruff | Passed |
| Git whitespace check | Passed |
| Local real-image preview and browser display | Completed; private evidence retained locally |

The earlier complete Python suite under the 4.2 implementation finished with
exit status zero. The repeated full-suite run after 4.2.1 was intentionally
interrupted to finish the requested checkpoint; do not report that repeat as
passed. The changed 4.2.1 paths passed the focused suite above. Skipped Fiji or
private-data checks are not passes. Runtime, contract and numerical checks do
not establish biological segmentation accuracy.

## Remaining work and resume order

1. Ask the owner to assess the current real-image candidate boundaries. Some
   large or weakly separated NCL structures can remain incomplete or fragmented;
   complete biological accuracy has not been established.
2. Continue from the exact saved protocol and result lineage. Inspect the input,
   adopted parent, raw model output and filtering separately before changing an
   algorithm. Do not tune to a desired object count or use generated microscopy
   as private-image acceptance evidence.
3. Confirm candidate adoption, manual correction and downstream compartment
   measurements on the owner's actual data before declaring the research flow
   complete. Avoid overwriting existing adopted masks.
4. Review the checkpoint branch and run applicable CI/release checks when work
   is authorized to resume. No PR merge or production release was performed by
   this checkpoint operation.
5. Deploy the proposal Worker compatibility changes only as a separate verified
   release. Source prompt `2026-10-08.5` supports protocol 4.2.1 and preserves
   older prompt replay, but the deployed relay was not updated in this step.
   The existing local relay prompt configuration remains `2026-10-08.1`.
6. Windows packaging, public hosted confirmation and any further API evaluation
   remain separate release tasks. No billable API evaluation was performed for
   this checkpoint; the existing monthly five-dollar limit is unchanged.

Docker remains running for the owner's local review while agent work and the
goal are paused. Read this record and inspect the Git branch before restarting
implementation; do not infer completion from the presence of an API or button.

## Owner-requested resumption, 2026-10-08

The owner subsequently requested resumption. PR #50 was checked at its saved
head: Web and local Windows checks passed; Python, Windows 3.14 and Fiji/browser
checks failed. The failures were traced to missing optional-array type narrowing,
an obsolete proposal-response prompt constant, an obsolete browser control
name, and metadata-only hash caching missing same-size model rewrites on Windows.

The repair preserves protocol 4.2.1 detection parameters and stored-mask meaning.
Model/adapter integrity now hashes actual file bytes before use rather than
reusing a size/timestamp cache. The mutation test preserves the original mtime
explicitly so that the regression is deterministic. Proposal persistence mocks
follow the declared current prompt version; real mismatches remain rejected.
The browser regression selects the existing `核小体の定義` control.

Local repair verification: 78 focused Python tests passed; mypy reported no
issues in 116 files; Ruff and documentation links passed. The first local test
attempt used an excessively long Windows scratch path and failed image intake;
the same tests passed from a short isolated scratch root without changing image
handling. These checks do not resolve the remaining biological acceptance gate.
CI must be checked on the repair commit; the previously failed run is not a pass.

### Resumed Docker verification

The first offline rebuild reused an older base whose model file had the expected
size but a different SHA-256. The byte-level integrity check rejected it.
The recorded expected hash was not changed or bypassed: the already provisioned,
verified pinned model was copied into the rebuilt Worker, and its build-time and
running-container capability probes passed. The research volume and existing
ownership/retention settings were preserved.

A fresh protocol 4.2.1 preview on the owner's previously supplied paired real
input completed with its adopted StarDist parent reused. Saved labels matched
the accepted trial, every candidate had one parent, no candidate pixels lay
outside the adopted parent, and NCL area/mean/median/integrated measurements
matched an independent calculation from unchanged original pixels. The adopted
selection ledger remained unchanged. Private specimens, labels, numerical
results and browser evidence remain outside Git and CI. This verifies the
accepted baseline and data path, not the still-open general biological accuracy
gate. Edge was refreshed to the new candidate result.

The exported Methods now states protocol 4.2.1 whole-instance nuclear rejection,
and the current default in the requirements/roadmap was corrected without
reinterpreting historical 4.1.0/4.2.0 recipes. Documentation links passed and
21 export regression tests passed. CI on `cad0b607` had passed Python, Web,
Fiji/browser and local Windows; the Windows 3.14 job was still running at the
time of this record. Check the latest PR head independently.

### Channel annotation reuse repair

Correcting stain names in the real-input workspace exposed a separate reuse
defect: unchanged detection parameters could still start fresh StarDist
detection because the reuse gate compared the entire channel assignment record.
The gate now distinguishes channel annotations from physical image identity.
An annotation-only update creates a new measurement revision with the current
stain information while retaining the saved labels, mask revision, exclusions
and original detector provenance. A versioned annotation record is validated
against the source revision. Changes to pixels, channel IDs, acquisition facts
or detector settings still fail the reuse checks. Child edits clear the source
revision's annotation operation rather than replaying it against another parent.

On the owner's paired real input after stain correction, the rebuilt Docker
Worker recorded no StarDist execution. Nuclear labels were identical to the
adopted parent, NCL labels matched the accepted trial, parent containment and
original-pixel measurements passed again, and the adopted selection ledger was
unchanged. Current source annotations and measurement metadata agree. No masks
were automatically adopted. Private inputs and result evidence remain local.
Detection parameters and protocol 4.2.1 were not changed by this repair.

The focused metadata/run/compartment/cohort suite passed 27 tests; mypy passed
116 source files; Ruff, documentation links and whitespace checks passed. The
initial restricted local test invocation stalled and was stopped; it is not
reported as a pass. The explicitly authorized local invocation completed.

The preceding Python CI job completed all test steps (1704 passed) but reached
its twenty-minute overall limit after font provisioning consumed almost twelve
minutes. The job limit is now thirty minutes; this does not skip checks or turn
the cancelled job into a pass. New CI must be assessed on the latest PR head.
The Docker application revision for this verified repair is `22c60eb`.
