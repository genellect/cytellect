# Accepted requirements — implementation targets

This contract summarizes the user-approved plan. Implementation status and remaining verification gates are tracked in roadmap.md and validation.md.

## Product

P01: Public genellect/cytellect; own code Apache-2.0; Japanese UI and bilingual README. Clearly separate planned, implemented, tested and scientifically validated.
P02: Free invite-only PoC; no registration, LLM, Supabase, billing or paid contracts as initial requirements.
P03: DAPI nuclei + NCL nucleolar candidates, manual correction, GFP selection, NCL quantification, group comparisons, GFP association, figures. Group labels are configuration, never private study constants.
P04: Manual ROIs for extranuclear/whole-cell GFP. DAPI does not define cell boundaries. Numeric CSV import supports previously measured RNA/DNA assays.
P05: UBF, RNA FISH, FRAP, 3D/time series, generic spots, automatic cell boundaries and instrument-specific quantification are later recipes.
P06: Publication-ready means editable figures, explicit conditions, traceable measurements, reproducible outputs. Not p-value matching.
P07: The 2026-10-03 extension centers general 2D fluorescence region detection, area/intensity measurement, statistics and figures. Preserve existing nuclear/NCL/GFP recipes and their limits; never transport another stain as GFP/NCL merely to bypass a contract. See [researcher workflow](research-workflow.md) for needs, sequencing and agent responsibilities.
P08: Method support must explain applicability, needed controls, limitations and primary sources. Begin with a no-upload, rule-based planning guide. Unsupported methods are not executable suggestions. No product LLM or additional paid service is required for this phase.
P09: Novice usability means task-oriented choices and a clear next action, with inspectable settings for specialists. Evaluate this through researcher tasks; visual polish and automated browser tests alone do not prove usability.

## Workflow and input

I01: Experiment setup → registration → representative trial → edit/review → freeze conditions → batch → QC/selection → statistics/plots → save/delete.
I02: Record group/control, independent unit, sample, field, acquisition date, pairing and optional repeat length; dates and units are distinct.
I03: Native 8/16-bit grayscale channel TIFF and verified single-series OME-TIFF Z=1/T=1; explicit DAPI/NCL/GFP mapping. Reject unknown axes, missing channels, dimension mismatch, corruption and over-limit decompressed pixels.
I04: Missing pixel size means px only. CZI initially converted with Bio-Formats. RGB TIFF is separate compatibility mode.
I05: Immutable original measurement pixels; display LUT and detection preprocessing separate. Native masks canonical at original resolution; store detection coordinate transform.
I06: User-confirmed background ROI median. Extranuclear pixels not automatically background. Save raw/corrected values and preserve native negative corrections.
I07: Configurable input-security limits 100 fields/workspace, 4096x4096 plane, 3 channels, 2 GiB total. The input ceiling does not promise automatic detection at that size. The provisional standard-2g automatic-nucleus admission profile requires both sides ≤2048 px and total area ≤2,700,000 pixels; reject excess before Fiji without resizing. Reusing supplied nuclear masks bypasses automatic-nucleus admission, while input/worker limits still apply. Internal IDs for paths, not uploaded filenames.
I09: Generic region entry accepts 1–3 explicitly named 2D grayscale channels with optional metadata and confirmed XY calibration. Missing unit/sample/date remains null. Reusing a channel ID with a different label/stain in the same workspace is rejected. Imported unsigned integer labels retain exact original-coordinate pixel membership. Do not claim automatic generic detection in the manual/imported slice.

## Segmentation, editing and metrics

A01: Real Fiji StarDist2D Versatile fluorescent nuclei. Initial percentiles 1–99.8, probability .5, NMS .3 are starting values requiring validation.
A02: Per-nucleus NCL Otsu + components via ImageJ/MorphoLibJ. Explicit smoothing/size/splitting parameters; DAPI-low auxiliary recipe. No-candidate, ambiguous, failed distinct; nucleus retained.
A03: No whole-nucleus or arbitrary top-fraction substitution for absent native nucleoli. Record circularity limitation of defining NCL regions using NCL itself.
A04: Nucleus/nucleolus IDs and exact containment/parent. Add/delete/reshape/merge/split, Undo/Redo; background and manual ROI. Nuclear changes invalidate affected children and require review.
A05: Native nucleus N, nucleolar union U, nucleoplasm N minus U. Cell nucleolar mean from union pixels, not mean of object means. Separate object table.
A06: NCL area/mean/median/integral for three compartments; nucleolar count/area/fraction; GFP raw/corrected mean/integral and gate reasons.
A07: Native positive corrected values allow nucleoplasm/nucleolus ratio and log2 ratio. Invalid denominator → missing reason, no arbitrary epsilon.
A08: Legacy whole-nucleus/high-NCL log2((nucleus+epsilon)/(high+epsilon)) is distinct metric/recipe. Explicit RGB conversion, resizing, background, clipping, epsilon, gate and version.
A09: Saturation/edge/weak signal/detection/region QC, explicit exclusions. No hardcoded study counts, dates, paths or private results. Revision changes mark existing tables/statistics/figures old.
A10: Expanding a representative trial to a batch explicitly reuses the current reviewed/corrected masks under the unchanged recipe; newly added fields are initialized separately. Reject stale sources, omitted source fields and implicit definition changes. Background or exclusion changes trigger new measurement revisions without discarding corrected masks.

## Statistics and deliverables

S01: Confirmed negative-control GFP gate, otherwise manual or batch Otsu labelled exploratory. Never assume a named control is GFP-negative.
S02: Separate cell/field/independent-unit n. Default aggregation field median → sample mean of fields → independent-unit mean of samples. Save method/pairing.
S03: Welch/paired t tests; planned contrast families with Holm correction. Reference and repeat-group families separate. No implicit repeat length zero for reference.
S04: Exploratory group/GFP/date regression, field-clustered SE, GFP association and repeat-length trend. Save transform, date centering, formula, baseline, contrasts and correction family. Detect missing controls, confounding, rank failure, few clusters. Unknown independent replication prevents confirmatory labels.
S05: Sensitivities for GFP gate, NCL high-region definition and complete-comparison dates. Do not silently drop failed fields.
S06: Matplotlib scatter/regression/95% CI, distributions with unit points, field summaries, adjusted means, paired plots; editable SVG/PDF plus PNG; Japanese/English labels. Figure values correspond to source table and adopted revision.
S07: Measurement/statistics CSV, masks, supported pixel-exact Fiji ROI round-trip, template Methods, environment/config/provenance and replay package. Raw images excluded by default; explicit opt-in only.
S09: First offer a reviewed per-field distribution with observation count, median, quartiles, explicit selection and missingness. One field/one valid observation is sufficient. Independent-unit count stays unknown and no tests/CI/regression are fabricated. Group comparison is a separate explicit action retaining S02–S05. Region/channel/metric identity and source revision must match before export and replay. See [descriptive protocol](descriptive.md).

## System

T01: Node24/Next16/React19/TS/pnpm; CSS Modules, Konva/react-konva, TanStack Query. Python3.12 FastAPI/Pydantic/Uvicorn, SQLAlchemy/Alembic/SQLite local disk, independent worker and private volume.
T02: Single Linux x86-64 CPU analysis server, Compose Web/API/worker and TLS. Browser uploads directly to private API; Vercel serves UI without image optimization/research caching.
T03: Pydantic/OpenAPI source contract → generated TS, /v1 endpoints. Job execution state distinct from immutable scientific revision: input/channel/recipe/metric/mask versions, exclusions/statistics/seed/code/environment.
T04: Six replacement boundaries: identity, DB, storage, jobs, image engine, method proposal. No generic workflow marketplace/editor.
T05: Initial concurrency1, field-by-field memory. Atomic claims, leases/heartbeat, recovery/retry, fencing, idempotency, partial-failure reporting, child time/memory limits and tree cancellation.
T06: CLI one-use expiring invite, hashed tokens, Secure HttpOnly cookie; no URL/localStorage secrets. Exact CORS, Origin/CSRF mutation checks.
T07: Ownership on image/preview/mask/table/figure/ZIP; immediate revocation/expiry/deletion applies to every path.
T08: Research content and names/conditions never in Git/CI/logs/issues/PR/analytics/external AI. no-store, no CDN/service-worker caches. Worker egress denied, allowlisted recipes, no arbitrary macros/code/URLs.
T09: 24h from explicit activity, polling excluded. On expiry/delete block access, stop execution, remove raw/derived/temp files. Protect active execution and exclude research files from general PoC backups.
T10: Lock actual Python/pnpm/Fiji/Java/plugins/weights versions/URLs/SHA256/licenses. No runtime downloads/updates. Verify CPU/headless support or include Xvfb.

## Quality and future gates

D01: Documentation: README/AGENTS/requirements/methods/design/API/security/operations/validation/roadmap/OSS+SBOM/contributing/private vulnerability reporting and CI/setup.
D02: Synthetic fixtures test exact numerical behavior. Published real microscopy containing nuclei/nucleoli is prioritized for image integration and the public demo. Internal testing and public redistribution have separate documented use scopes. Public assets require source, stain metadata, redistribution provenance and hash allowlisting; unpublished research remains prohibited.
D03: CI Web lint/type/build, Python lint/type/tests, contract drift, analytical masks/measurements, browser invite→upload→edit→remeasure→export, real Fiji integration on engine changes, secrets/data/vulnerability/license/link/startup checks.
D04: M4 representative private images split by field/sample into tuning and evaluation, not threshold optimization on evaluation images. Provisional targets nucleus F1>=.90, nucleolar F1>=.80 at IoU.5, neither achieved nor literature guarantee. Ambiguous cases separate; near-background errors not judged only relatively.
D05: Corrected-mask measurement agreement with reference pixels essential; explain counts/legacy differences rather than force old significance.
D06: M5 preferably >=3 researchers across labs evaluate completion/time/edit burden/understanding/reuse. Record operational metrics without research content.
D07: Future Supabase identity/Postgres/private Storage adapters preserve owner IDs with verified guest transfer and RLS. Optional structured LLM method proposals require adoption before recipe execution; no arbitrary code/significance search. Mixed models/R/other segmentation/spots/3D later recipes. Teams/retention/billing depend on PoC evidence.
D08: Independent scientific reviews record the source, scientific question, reference calculation, applicable data, failures, change/version, reviewer and rerun evidence. CI must distinguish passed numerical checks from missing/skipped checks and from unmeasured biological applicability. Private-data or human-evaluation gates do not stop independent public-data or UX improvement.

## Published-image and figure extensions

I08: Native NCL analysis accepts confirmed DAPI+NCL with optional GFP only when no GFP gate/range is requested. GFP-nuclear recipe requires DAPI+GFP, keeps NCL metrics missing, and never fabricates absent channels. Two-channel OME uses an explicit role/index mapping. Published DNA stains such as DRAQ are labelled by their actual stain, even when transported through the historical dapi role.
S08: Nature presets set 89/183 mm widths, height≤170 mm, editable vector text, 5–7 pt labels, embedded PDF fonts and source-linked metadata/caption. Publication formatting is distinct from scientific acceptance. Exploratory regression bands use the saved clustered covariance; no additional cell-independent band is introduced.
T11: Normal source publication follows PR → required CI → main merge → automatic Vercel deployment. The initial CLI bootstrap is recorded separately in deployment.md.

## Local delivery and later cloud execution

L01: Initial low-cost delivery uses the existing browser UI with API/worker on the same PC. Windows setup automates pinned dependencies without modifying system Python or an existing Fiji. Routine startup requires no command or invitation. Installation/browser acceptance precedes an advertised download.
L02: Bind only literal loopback; local session bootstrap is absent from cloud mode. Exact Host/Origin, browser Fetch Metadata, CSRF, HttpOnly cookies and frame restrictions protect browser access. Local OS processes are trusted; this is not shared-account isolation.
L03: The same analysis, revision, measurement, statistics and export contracts serve local and future cloud modes. No local-only scientific fork. Standard Vercel builds do not silently connect to localhost.
L04: Local expiry blocks access after24h; physical deletion while the launcher/PC is off resumes at next launch, disclosed before upload. A future cloud host must satisfy its own continuous deletion and isolation acceptance.
L05: Versioned release bundles contain tracked allowlisted sources and static UI, per-file hashes and a package checksum; no unpublished/private research data, credentials or developer runtime. Registered public demonstration assets retain their redistribution evidence. Git/PR checkpoints record implementation and remaining gates.
