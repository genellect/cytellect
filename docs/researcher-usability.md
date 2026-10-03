# Researcher workflow review — 2026-10-04

Scope: coordinator review of the current public product, generic workspace code, actual desktop screenshots from `generic-workflow-production-v4`, and primary-source documentation. This is an expert heuristic review, not a user interview, novice task study or biological validation. No private research data were used.

## Evidence and product decision

The 2022 cross-community survey reported demand for intuitive interfaces, written tutorials, use-case-specific segmentation guidance and expert advice (Sivagurunathan et al., https://pubmed.ncbi.nlm.nih.gov/37727897/; checked 2026-10-04). This motivates short task examples and explanations at the decision point. It does not prove demand for Cytellect or for a particular interface.

Fiji Labkit supports image/label overlays, manual corrections, automatic pixel classification and label import/export (https://imagej.net/plugins/labkit/documentation). CellProfiler supplies reusable example pipelines with images and tutorials for counting, intensity measurements and compartment relationships (https://cellprofiler.org/examples ; https://cellprofiler.org/tutorials). Checked 2026-10-04. Cytellect must retain interoperability and build workflow continuity; do not advertise these established features as absent from Fiji or CellProfiler.

The proposed value is a small number of supported, inspectable workflows connecting experimental question, region definition, reviewed measurements, independent experimental units and editable source-linked figures. The target is less repeated setup and fewer hidden scientific decisions. Whether this saves effort must be measured with researchers.

## Prioritized friction and acceptance at the initial review

| Friction observed in current implementation | Next change | Evidence required |
|---|---|---|
| Generic entry currently begins with manual/imported masks. A novice with a nuclear stain has no generic automatic starting point. | Offer confirmed nuclear-stain detection through the existing fixed Fiji model; retain manual/import paths. Ask which channel defines the nuclei, separately from which fluorescence is measured. | Actual public-image trial → correction → batch → figure, with real channel identity and no fabricated GFP/NCL input. |
| Generic figures describe fields but cannot yet compare experimental units. | Explicit group-comparison action with a reviewed design table; describe distributions first, then require treatment units/pairing and acquisition comparability for inference. | Unequal region counts cannot increase inferential n; missing/contradictory design and omitted pairs block a misleading comparison. |
| One file chooser per channel per field is manageable for a trial, tedious for a study. | Follow the connected detection/comparison paths with batch registration: a previewable file-to-field/channel table and reusable experimental metadata. Never confirm a stain from filename alone. | Wrong/missing/duplicate files and mixed dimensions are visible before analysis; an explicit mapping can be corrected without restarting registration. |
| Planning guide and active workspace are separate. | Record explicit adoption of a supported plan as an immutable analysis input; show which proposed decisions were changed, and retain Methods provenance. | Unsupported plans cannot become executable recipes. Later edits invalidate dependent results without overwriting prior records. |
| Review controls have precise technical detail but some explanatory text repeats. | Show the next unresolved task beside the image; retain definitions and source details in expandable sections. Keep scientifically necessary decisions visible. | A researcher can identify the next action and explain mean vs integrated intensity, region definition and n without code or internal IDs. |
| Figure/source linkage was easy to lose on regeneration. | Keep the newly implemented source-revision links, pending/failed states and saved-setting labels. | New figure requests hide the old figure while pending; a source-image link opens the exact saved version; failed fields and missing measurements remain visible. |

The current desktop imported-mask and descriptive screenshots have a consistent hierarchy, legible source attribution, prominent image/graph and no obvious overlap. The mobile select-width issue was corrected and browser-verified in PR #11. This visual review is not evidence that a novice can complete the workflow.

## Task-based usability protocol to execute with researchers

Use registered public images and fixed example metadata for onboarding, followed by each participant's approved private data only in their private runtime. Prefer at least three participants including a Wet researcher unfamiliar with image-analysis scripting and an experienced imaging analyst. Do not substitute agent tests for these participants.

1. Select a supported measurement question, assign actual channels and identify why a chosen region definition applies.
2. Register a representative field, inspect the original/overlay, correct a deliberately supplied region error and explain what is being measured.
3. Specify a cell-free background, encounter an overlap error, recover without losing corrected masks, and expand to a batch.
4. Identify cells/regions, fields, samples and independent treatment units in an example with unequal object counts; choose descriptive output when independence is unknown.
5. Export a figure and its source values, return from a point/field summary to its source image version, and regenerate after a deliberate correction.

Record task completion, time, wrong turns, requests for help, correction burden, data-loss incidents, understanding of the measurement/n, and reuse intent. Compare the same bounded task with the participant's current Fiji workflow rather than a hypothetical unassisted manual baseline. Report failures and uncompleted tasks as such; no adoption/time-saving claim before evidence exists.

PRs #11–#15 are published through required CI and main. Nuclear initialization,
independent-unit comparisons, adopted plans and batch registration have scoped
source and browser evidence; the installed local.11 release has its own
acceptance record. The earlier plan/default, calibration, imported-mask input
and nuclear-area selection findings were addressed in that sequence. These are
agent findings and automated checks, not participant observations.

PR #15 addresses individual-region tracing from a saved
descriptive figure and common-information application that could erase
row-specific metadata. It also prepares the [unequal-replicate
task](usability-practice.ja.md). None of these source changes retrospectively
updates local.11 or establishes human usability.

The current source increment exposes saved unit values as an expandable
sample/field hierarchy. It uses server values and ledgers, keeps exclusions and
unknown failed-field counts visible, and verifies historical masks/channels before
opening a field. A unit point is not one cell. Source review also corrected a
display-order mismatch so that a field has the same name in the hierarchy and
image viewer. Browser and package acceptance are recorded separately; these
changes do not establish participant understanding or time savings.

The current area-only source increment implements an explicit, versioned
measurement policy without background ROIs. It preserves original-coordinate
masks and reports unmeasured intensity and signal-QC values as missing with
reasons, never as zero. Three actual-API browser cases cover mode changes and
source export, calibrated area comparisons with their saved source hierarchy,
and planning 2.1 with explicit actual-input review. Coordinator inspection of the
resulting screens is a visual review, not a participant evaluation. PR #18 has
since passed five required checks, merged as main
`d385eb0722a9df9068683fbc89a474c60b6e88af` and reached the canonical public UI.
Its source evidence does not update the installed release or the runtime-only
PR #17 candidates. The next accepted package must combine both source increments
and pass all fifteen installed browser cases.
Reducing background setup
for area measurements is an expected benefit, not an observed time saving.

Continue public-data work while human/private evidence is unavailable; keep M4
and M5 open. Actual task completion, recovery and understanding determine whether
these changes benefit researchers.
