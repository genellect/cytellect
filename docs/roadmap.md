# Implementation and remaining gates

This is a running implementation record, not a declaration of scientific readiness. See [validation layers](validation.md).

| Stage | Implemented | Remaining acceptance |
|---|---|---|
| M0 | Public monorepo, bilingual docs, agent guidance, locked Python/Web/Fiji, actual Java21 CPU detection, Alembic, CI and container definitions | Linux Fiji/browser and actual isolated worker container passed in PR #1; complete hosted stack acceptance remains open |
| M1 | Bounded TIFF/OME, native and generalized legacy recipe, true Fiji adapter, compartment/GFP measurements, replay exports | Reference comparison on user's raw data remains M4 |
| M2 | Japanese Konva editor, immutable edits, Undo/Redo, background/exclusion/review, supervised durable jobs and retry | Local and Linux browser regression passed; actual hosted analysis acceptance remains open |
| M3 | Independent/paired/exploratory statistics, sensitivity, numerical CSV, plots, Methods, pixel-exact ROI and replay | Nature-sized vector export and independent math references tested; private scientific suitability remains M4 |
| M4 | Published real-image integration adds external examples | User-provided private raw images, field/sample-separated evaluation and legacy reconciliation |
| M5 | Invite/session/ownership/retention implementation and automated protection tests | Provisioned private analysis host, operator acceptance and researcher usability evaluation |

Public Vercel UI publication is authorized. It may expose only cleared published image samples until the private analysis API is configured and host checks pass. It must not point to localhost in production or accept research uploads without a backend.

Supabase/accounts, LLM method proposals, teams, long-term storage and payments remain later work. No paid service purchase or automatic private-data transfer is included.

Normal publication follows [PR → required CI → main → Vercel](deployment.md). [Figure formatting and statistical meaning](figures.md) are versioned separately.

## Local delivery, then hosted analysis

The next change adds automated local setup, same-origin browser operation and supervised local API/worker startup. Shared analysis, immutable revisions, statistics and export contracts remain unchanged. Installation is not complete until a fresh isolated directory can install fixed dependencies, open the browser, execute a real published-image workflow and stop cleanly. The public Vercel sample viewer remains available while the local package is validated.

Later cloud delivery must preserve the same UI and scientific contracts while replacing storage, database and job execution where necessary. Low-volume scale-to-zero hosting is under review; price alone does not satisfy 24-hour deletion and isolation. The [comparison](hosting-costs.ja.md) records costs, limits and unresolved provider conditions. No paid deployment is currently selected.
