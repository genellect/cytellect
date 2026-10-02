# Implementation and remaining gates

This is a running implementation record, not a declaration of scientific readiness. See [validation layers](validation.md).

The [requirement coverage audit](completion-audit.md) maps the implemented workflow, regression corrections and remaining private/human/hosted acceptance. Later source fixes do not retroactively change accepted release evidence.

| Stage | Implemented | Remaining acceptance |
|---|---|---|
| M0 | Public monorepo, bilingual docs, agent guidance, locked Python/Web/Fiji, actual Java21 CPU detection, Alembic, CI and container definitions | Linux Fiji/browser and actual isolated worker container passed in PR #1; complete hosted stack acceptance remains open |
| M1 | Bounded TIFF/OME, native and generalized legacy recipe, true Fiji adapter, compartment/GFP measurements, replay exports | Reference comparison on user's raw data remains M4 |
| M2 | Japanese Konva editor, immutable edits, Undo/Redo, background/exclusion/review, supervised durable jobs and retry | Local and Linux browser regression passed; actual hosted analysis acceptance remains open |
| M3 | Independent/paired/exploratory statistics, sensitivity, numerical CSV, plots, Methods, pixel-exact ROI and replay | Nature-sized vector export and independent math references tested; private scientific suitability remains M4 |
| M4 | Published real-image integration adds external examples | User-provided private raw images, field/sample-separated evaluation and legacy reconciliation |
| M5 | Invite/session/ownership/retention implementation, automated protection tests and accepted Windows local.10 installation/browser workflow | Operator acceptance on the intended research machine and researcher usability evaluation; private hosted acceptance remains separate |

Public Vercel UI publication is authorized. It may expose only cleared published image samples until the private analysis API is configured and host checks pass. It must not point to localhost in production or accept research uploads without a backend.

Supabase/accounts, LLM method proposals, teams, long-term storage and payments remain later work. No paid service purchase or automatic private-data transfer is included.

Normal publication follows [PR → required CI → main → Vercel](deployment.md). [Figure formatting and statistical meaning](figures.md) are versioned separately.

## Local delivery, then hosted analysis

Local delivery implements automated setup, same-origin browser operation and supervised local API/worker startup. Shared analysis, immutable revisions, statistics and export contracts remain unchanged. Each package must install fixed dependencies in an isolated directory, open the browser, execute a real published-image workflow and stop cleanly before publication. The public Vercel sample viewer remains available independently of local package validation.

[Windows preview 0.1.0-local.10](local-release-0.1.0.md) passed exact-source CI, installation, the public GFP browser/export workflow and checks of corrected Methods in both actual exports. It changes only Methods wording/template identification and the auxiliary method's UI label. The first scratch runtime path exceeded the existing Windows Fiji limit; that failed attempt is retained, and the unchanged package passed with a shorter private test data directory. The [local.9 record](local-release-0.1.0-local.9.md) preserves its 114 installed scientific checks,22 figure tests and12 renderings as historical evidence for unchanged code, not new local.10 test executions. Those two suites share four cases. This completes the local package delivery gate; it does not complete M4 or the researcher evaluation in M5.

The user's local-first delivery decision changes the initial operating environment, not M4/M5 scientific and usability acceptance. A paid server is not required for the local PoC. Hosted-only acceptance (public TLS/domain routing, continuous deletion while clients are offline, operator server isolation) remains a separate gate before future cloud uploads. Windows local mode explicitly discloses its trusted OS-user boundary and cleanup on next launch.

Later cloud delivery must preserve the same UI and scientific contracts while replacing storage, database and job execution where necessary. Low-volume scale-to-zero hosting is under review; price alone does not satisfy 24-hour deletion and isolation. The [comparison](hosting-costs.ja.md) records costs, limits and unresolved provider conditions. No paid deployment is currently selected.
