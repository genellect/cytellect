# Researcher workflow and continuous improvement

Revision: 2026-10-04. This extends the accepted scope; it does not replace the native or compatibility recipes. Researcher needs below are literature-informed hypotheses, not results of Cytellect user interviews. The [UX review and usability tasks](researcher-usability.md) translate these hypotheses into observable acceptance tasks.

## Product goal

Let a researcher move from a **2D fluorescence measurement question to an editable, traceable figure**, with a recorded choice of regions, original-pixel measurements, reviewed exclusions and an appropriate experimental unit. A newcomer should understand the next decision; an experienced analyst should be able to inspect and reproduce it. A polished graph is not evidence that acquisition, segmentation or inference was valid.

Fiji already provides extensible image processing, measurement and scripting. Cytellect uses that capability. Our proposed value is the continuity between experimental design, representative-image trials, reviewed masks, statistical units and manuscript outputs. We must test whether that continuity saves work; we do not claim Fiji cannot perform these operations. [Fiji](https://imagej.net/software/fiji/)

A cross-community survey found demand for intuitive tools, written tutorials and segmentation guidance tailored to the use case. This supports prioritizing task-specific examples and clear decisions over a large parameter form; it does not establish Cytellect adoption or willingness to pay. [Sivagurunathan et al., community survey](https://doi.org/10.1111/jmi.13229)

## Needs translated into product behavior

| Researcher decision | Product behavior | Evidence and acceptance |
|---|---|---|
| What should I measure? | Start with the question, region and recorded stain; distinguish area, mean intensity, integrated intensity and compartment ratios. Show applicable recipes and their limits before parameters. | Quantitative imaging connects acquisition, analysis and interpretation. Test that unsupported axes/stains are not routed to a misleading recipe. [Senft et al.](https://doi.org/10.1371/journal.pbio.3002167) |
| Are these images comparable? | Explicit axes, bit depth, scale, acquisition conditions and background. Saturation is a review issue, not a display adjustment. Unknown conditions stay unknown. | Acquisition effects cannot be repaired by statistics alone. Same source above; machine checks do not establish comparability. |
| Can I trust these regions? | Representative-field trial, original-image overlay, parent/child integrity, targeted correction, reversible edits and review before batch/statistics. | Check boundary and pixel agreement separately from detector performance; report difficult fields, not only pooled scores. |
| What is my n? | Explain treatment/allocation units with examples; keep objects, fields, specimens and independent units distinct. Unknown independence permits descriptive/exploratory work, not a confirmatory claim. | Repeated measurements do not create independent replicates. [Lazic et al.](https://doi.org/10.1371/journal.pbio.2005282), [SuperPlots](https://doi.org/10.1083/jcb.202001064) |
| Can I defend the figure? | Editable vectors with source values, measurement/analysis versions, units, missingness, comparison family and a Methods draft. | Image-analysis reporting needs software, parameters and reproducible workflows. [Schmied et al.](https://doi.org/10.1038/s41592-023-01987-9) |
| Can I use this without programming? | Purpose-first choices, concise help at the decision, progressive disclosure of technical settings, recoverable failures and one clear next step. | This is a UX hypothesis to test with novice and expert researchers, not a validated time-saving claim. |

## Implementation sequence and decision gates

1. **Research workflow release:** replace marker-specific LP copy with the actual workflow; add a source-linked, no-upload analysis planning screen; independently audit numerical/statistical behavior and publish machine-readable CI evidence. Keep currently unsupported paths explicit.
2. **General 2D regions:** add named acquisition channels and a region-by-channel measurement table. Preserve legacy recipe IDs/columns and original-pixel semantics. Manual/imported masks must not require relabeling another marker as GFP or NCL. Add an independently sourced public image domain before advertising broader applicability.
3. **Guided workspace:** connect an adopted plan to immutable analysis versions; batch metadata entry; show the next unresolved action; improve trial/overlay/correction/background and statistical-unit UX. Export the adopted plan with Methods. Do not auto-adopt a proposed method.
4. **Independent re-review:** rerun relevant numerical references, real Fiji and published-image checks; review actual SVG/PDF and browser workflows at desktop/mobile sizes. Fix failures and repeat affected checks. Compare source, installed package and hosted UI identities separately.
5. **Researcher acceptance:** novice/expert task walkthroughs, correction burden, completion time, interpretation of n, missingness and re-use intent. Private image performance and researcher usability remain open until actually measured; they do not block unrelated public-data development.

Method support starts with explicit, cited decision rules. Product LLM proposals remain optional, with separate authorization for cost and research-data transmission. No new paid API or autonomous parameter search is part of this phase. Hosting remains local API/worker plus browser UI until an affordable host passes its own privacy and operational acceptance.

### Current checkpoint and next decisions

The LP/planning/scientific-review increment and the generic manual/imported-region increment are published through PRs #10 and #11, their required CI and main. The latter connects optional metadata, trial-mask reuse, source-bound descriptive figures and return-to-image links; actual public-image private-API browser workflows and canonical public-page checks have separate evidence. The immutable local.10 package retains that earlier delivery checkpoint; newer package evidence is recorded below.

The current implementation addresses two remaining breaks: (1) confirmed nuclear-stain detection through the existing pinned Fiji model, without fabricated GFP/NCL channels; (2) experiment-unit comparisons for an explicitly selected generic region/channel metric. Manual/imported 1.0 recipe serialization stays stable. General-channel comparisons require source selection, recorded experimental metadata and confirmed design; they share marker-neutral aggregation/inference rather than GFP regression. Unknown metadata continues to permit descriptive work. Independent tests cover unequal object counts, nested technical replicates, paired identities, missingness and duplicate channel-area rows. A coordinator reference check also found and corrected large-offset paired-estimate cancellation under statistics1.2.3. Public-image performance, biological applicability and human usability retain their separate limits.

Those nuclear/comparison paths passed PR #12's four required checks and are published through main c9766f8da61defe5f4fa000e03b7706678140dde. PR #13, merged as c21f9057dd130b87ba55b113d40a0396dcb79e74, connects [planning adoption](analysis-planning.md) to actual channel/metric selection and retry-safe batch registration. A selected plan is retained in immutable revisions and replay, while actual channel, background, acquisition and independence confirmations remain separate. File grouping requires an explicit mapping preview; filenames do not establish stain identity or independent replication. The [local.11 Windows package](local-release-0.1.0.md) passed installed-copy CI acceptance and was published, with its first failed browser attempt and separate local Smart App Control block retained. The next priority is [guided use with public images](quickstart.ja.md), intended-machine compatibility and [actual researcher tasks](usability-tasks.ja.md), alongside the private-data validation gate. Existing low-performing or ambiguous public detector results remain visible; adding a button does not establish new segmentation accuracy. Human usability and private-data performance remain open acceptance gates.

## Agent roles and execution loop

| Role | Owns | Independent check |
|---|---|---|
| Coordinator | requirements, API/contracts, generic region architecture, integration, Git/PR/release | reconcile all findings; never infer scientific validity from a green build |
| UX/Web | researcher task flow, LP, planning/workspace interactions, actual browser review | coordinator reviews copy, screenshots and truthful feature status |
| Image analysis | primary data provenance, fixed evaluation subset, real Fiji and ImageJ comparison | statistics reviewer/coordinator checks independence, masks and applicability |
| Statistics/figures | inference, reference arithmetic, missingness, vector/source-data consistency | coordinator checks method/version changes and actual output |

Each cycle records: question → primary source → testable expectation → independent reference → result (including failures) → correction → targeted retest → reviewer → release evidence. Do not optimize against a desired biological conclusion or use an evaluation set to tune thresholds. Published data from another task establishes a bounded integration check, not universal accuracy.

Only the coordinator commits/pushes/merges. Agents share explicit file ownership and send findings before cross-boundary edits. Reassign roles when dependencies make parallel work wasteful. CI is the reproducible test executor; it is not an autonomous scientist or a substitute for researcher review. No background paid agents are introduced.

## Completion evidence

The original MVP goal stays active. This revision broadens the scientific question and defines successive release gates; it does not mark M4/M5 complete. [Roadmap](roadmap.md) and [requirements](requirements.md) remain the status record. Code, CI, installed execution, production deployment, scientific applicability and human usability must be reported separately. Old release evidence remains immutable.

For the new workflow, success means a researcher can identify a supported measurement, inspect/correct its region, explain the independent unit, regenerate the figure and trace each point back to an accepted measurement. Number of tests, number of agents, attractive plots and agreement with a historical p-value are not product acceptance criteria.
