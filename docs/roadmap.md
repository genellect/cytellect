# Implementation and remaining gates

The active 2026-10-03 improvement sequence is recorded in [Researcher workflow](research-workflow.md): purpose-first LP/planning, generic 2D region/channel contracts, guided workspace, independent repeated review, then researcher acceptance. This work proceeds alongside the remaining private-data gates below. No historical release evidence is retrospectively relabeled.

This is a running implementation record, not a declaration of scientific readiness. See [validation layers](validation.md).

The 2026-10-05 follow-up requires common image-analysis statistics and editable
figures through the complete installed browser workflow (S15–S18). Scientific
core/reference tests and API/replay integration are under development; a final
Windows package containing these additions has not been accepted or published.
The local.13 source436 candidate is a separate baseline and does not establish
completion of the added statistics or update-storage requirements.

PR #11 added manual/imported generic regions, source-linked descriptive figures and trial-mask reuse. Its four required CI checks passed, it merged as dd64f26db0e4ea15970828aaa6dbcae3f9365696, and Vercel automatically published that source. Canonical public-page desktop/mobile/browser checks passed separately from private API execution.

PR #12 connects confirmed nuclear-stain initialization, immutable experimental-metadata edits and explicit generic-channel experimental-unit comparisons. All four required CI checks passed on 136eab8ff41af0fd0ee5d0b0936525013f6c5569. Main c9766f8da61defe5f4fa000e03b7706678140dde was automatically published as Vercel production dpl_Cx8VzAfHtPhgs3tWzaV9Uhff3Nw5; canonical desktop/mobile browser checks passed separately. Real-Fiji equivalence, corrected-mask batch reuse, comparisons, vector downloads and replay have bounded recorded evidence; this does not establish new biological accuracy.

PR #13 connects [explicit planning adoption](analysis-planning.md), reviewed file mapping and retry-safe batch registration. Main c21f9057dd130b87ba55b113d40a0396dcb79e74 passed the four required checks and reached the canonical public site. The [local.11 package](local-release-0.1.0.md) carries these source features into the installed application; its actual CI package passed nine browser cases, independent numerical/replay checks and shutdown. The initial failed browser attempt and a separate local application-control block remain recorded. [Public-image guide](quickstart.ja.md) · [Human evaluation tasks](usability-tasks.ja.md).

The [requirement coverage audit](completion-audit.md) maps the implemented workflow, regression corrections and remaining private/human/hosted acceptance. Later source fixes do not retroactively change accepted release evidence.

PR #15 passed its four required checks and merged as
`c215e70a563797d07181b6febbd5cdb04b9e39ba`. The same source reached Vercel production
READY as `dpl_FyfBb2jvarcWBFf8PEeVJjxrTguc`; canonical home/planning checks at
1440/390 px passed separately. It adds source inspection for saved individual
region measurements, preserves per-field metadata during common-field edits,
and improves installer diagnosis. These later changes are not included in the
immutable local.11 package. Comparison aggregation inspection is the next
source increment at that checkpoint; background-free area measurement was a design task.

PR #16 then added saved unit → sample → field inspection and historical source
navigation. Its four required checks passed before main
`636bbc9c73e60f26e6ae3310354f85494f84dedd` reached Vercel production
`dpl_C4voNA4qdQkWGHmGSqz1cpEUy5nP`. Canonical public home/planning checks passed
at 1440/390 px. The source-only API/browser evidence and public-page evidence are
distinct; this increment is not in local.11. The next delivery priority is the
intended-PC installation blocker. Signed-runtime candidate checks must precede
any dependency-support or public-package change; area-only was queued at that checkpoint.

### Area-only development checkpoint — not yet released

The separate area worktree now implements explicit measurement policy 1.0.0,
region measurement/report 2.0.0, bundle `/2` and Methods 1.2.0. Manual/imported or
confirmed nuclear regions can provide area without a background ROI. Fluorescence
values and saturation fractions remain unmeasured with explicit reasons. Existing
v1, GFP/NCL recipes and inference rules retain their versions and behavior.
[Protocol details and focused evidence](generic-regions.md).

Guide 2.1.0 and resolution 1.1.0 connect that choice to actual reviewed inputs;
old 2.0.0 plans remain reproducible. Canonical public planning stays 2.0.0; the
new local/API-configured source selects 2.1.0. This area increment is not yet
merged, deployed or accepted in a Windows package. PR #17 runtime-only candidates
do not include these area changes. Once both source increments are accepted on
main, build one combined `local.12` package and verify its fifteen installed
browser cases before publication. Required CI,
actual browser/figure inspection and installed acceptance are separate gates;
running checks are not recorded as passed. M4 private-image validation and M5
human researcher evaluation remain open. Reducing background gestures for area
is a usability hypothesis, not an observed reduction in researcher effort.

### Subsequent source acceptance — PR18

PR17's runtime corrections and PR18's area-only/readiness changes are now merged.
PR18 head `5ef6d41092746ac4f519bfa580fa089cdaf3b393` passed all five required
checks in [run 37159139324](https://github.com/genellect/cytellect/actions/runs/37159139324)
and merged as `d385eb0722a9df9068683fbc89a474c60b6e88af`. Canonical public
home/planning verification at 1440/390 px confirmed that exact source in Vercel
deployment `dpl_GgrBy3dVy42tUdxMm9sxBdU8rMrL`; the unchanged local.11 links and
planning2.0 remain intentional until a matching package is accepted. This
supersedes the earlier unmerged-source checkpoint above, not its retained tests
or failed attempts. The combined local.12 installation gate is still separate.

The following source increments address recorded display ranges, paginated
descriptive figures, readable versioned Methods and native recipe compatibility
guidance. They do not retroactively update local.11 or the frozen local.12 source.
Actual browser, installed-package, private-image and human acceptance retain
their own evidence.

| Stage | Implemented | Remaining acceptance |
|---|---|---|
| M0 | Public monorepo, bilingual docs, agent guidance, locked Python/Web/Fiji, actual Java21 CPU detection, Alembic, CI and container definitions | Linux Fiji/browser and actual isolated worker container passed in PR #1; complete hosted stack acceptance remains open |
| M1 | Bounded TIFF/OME, native and generalized legacy recipe, true Fiji adapter, compartment/GFP measurements, replay exports | Reference comparison on user's raw data remains M4 |
| M2 | Japanese Konva editor, immutable edits, Undo/Redo, background/exclusion/review, supervised durable jobs and retry | Local and Linux browser regression passed; actual hosted analysis acceptance remains open |
| M3 | Independent/paired/exploratory statistics, sensitivity, numerical CSV, plots, Methods, pixel-exact ROI and replay | Nature-sized vector export and independent math references tested; private scientific suitability remains M4 |
| M4 | Published real-image integration adds external examples | User-provided private raw images, field/sample-separated evaluation and legacy reconciliation |
| M5 | Invite/session/ownership/retention implementation, automated protection tests and accepted Windows local.11 CI installation/browser workflow | Operator acceptance on the intended research machine and researcher usability evaluation; private hosted acceptance remains separate |

Public Vercel UI publication is authorized. It may expose only cleared published image samples until the private analysis API is configured and host checks pass. It must not point to localhost in production or accept research uploads without a backend.

Supabase/accounts, teams, long-term storage and payments remain later work. The [single workspace and optional LLM proposal service](workspace-redesign.md) is the active 2026-10-05 increment: UX prototype, review, connection to existing processing, proposal service, then combined acceptance. No paid service purchase is included; the proposal service stays disabled until an operator configures its budget.

Normal publication follows [PR → required CI → main → Vercel](deployment.md). [Figure formatting and statistical meaning](figures.md) are versioned separately.

## Local delivery, then hosted analysis

Local delivery implements automated setup, same-origin browser operation and supervised local API/worker startup. Shared analysis, immutable revisions, statistics and export contracts remain unchanged. Each package must install fixed dependencies in an isolated directory, open the browser, execute a real published-image workflow and stop cleanly before publication. The public Vercel sample viewer remains available independently of local package validation.

[Windows preview 0.1.0-local.10](local-release-0.1.0-local.10.md) passed exact-source CI, installation, the public GFP browser/export workflow and checks of corrected Methods in both actual exports. It changes only Methods wording/template identification and the auxiliary method's UI label. The first scratch runtime path exceeded the existing Windows Fiji limit; that failed attempt is retained, and the unchanged package passed with a shorter private test data directory. The [local.9 record](local-release-0.1.0-local.9.md) preserves its 114 installed scientific checks,22 figure tests and12 renderings as historical evidence for unchanged code, not new local.10 test executions. Those two suites share four cases. This completes the local package delivery gate; it does not complete M4 or the researcher evaluation in M5.

The user's local-first delivery decision changes the initial operating environment, not M4/M5 scientific and usability acceptance. A paid server is not required for the local PoC. Hosted-only acceptance (public TLS/domain routing, continuous deletion while clients are offline, operator server isolation) remains a separate gate before future cloud uploads. Windows local mode explicitly discloses its trusted OS-user boundary and cleanup on next launch.

The local.11 package adds the reviewed planning and general-region workflow.
Its accepted CI installation does not resolve the observed Smart App Control
block on another PC. Next delivery work should investigate a policy-compatible
distribution and classify that installer failure accurately, without disabling
workstation protections or purchasing a signing service without authorization.
Researcher task completion and correction burden take priority over adding more
automatic models. The supplied guide teaches the workflow; reading it before an
unassisted usability task changes what that task measures.

Later cloud delivery must preserve the same UI and scientific contracts while replacing storage, database and job execution where necessary. Low-volume scale-to-zero hosting is under review; price alone does not satisfy 24-hour deletion and isolation. The [comparison](hosting-costs.ja.md) records costs, limits and unresolved provider conditions. No paid deployment is currently selected.
