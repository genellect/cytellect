# Requirement coverage and remaining acceptance

This audit reconciles the [accepted requirements](requirements.md) with the implementation after Windows local.8. It does not restart M0–M3 or certify a private experiment. The current downloadable package and its exact scientific source are recorded in the [release acceptance](local-release-0.1.0.md); subsequent source corrections are included only when a new package passes that process.

## Product and image workflow

| Requirements | Implemented behavior and evidence | Remaining scope |
|---|---|---|
| P01–P02, P05 | Public Apache-2.0 source, Japanese workspace, bilingual README, invite/session API; no mandatory registration, LLM, Supabase or billing. Unsupported analyses are explicit in requirements. | Local-first delivery is the accepted initial operating environment. Researcher PoC remains M5. |
| P03, I01–I02 | Experiment hierarchy, representative trial, frozen batch recipe, review, corrections, GFP/NCL tables, statistics and exports. `workflow.spec.ts` follows actual browser/API/worker operations and retains old-version warnings. | A declared unit or channel mapping is not proof of biological independence or stain identity. |
| P04 | Original-coordinate manual ROI measurements and authoritative CSV; measured-table import supports assay/unit/pair metadata, statistics and replay. `test_numeric_export.py` and browser tests check source identity and private access. | No inferred cell boundary, automatic ROI-to-nucleus association or instrument normalization. Manual ROI comparisons require a prepared measured table. |
| I03, I07–I08 | Bounded 8/16-bit TIFF/OME reader, explicit acquired channel roles, exact single-series IFD coverage and supported Z/T; no zero-filled missing planes. Native GFP-only and NCL-without-GFP keep absent measures missing. API/input tests cover invalid axes, roles, dimensions and planes. | Automatic nuclear detection has the separately documented standard-2g admission limit. Input validation is not an exhaustive decoder fuzz audit. |
| I04 | Missing calibration gives px only; RGB is a separate compatibility recipe. [Offline CZI conversion](converting-czi.md) records Bio-Formats, channel identity and pixel/calibration checks. | Public TIFF→OME conversion preserved 5,751,808 pixels; actual proprietary CZI codec and full GUI conversion remain unverified without suitable originals. |
| I05–I06, A05–A07 | Immutable measurement pixels, original-coordinate masks, confirmed background ROI, signed corrections, weighted nucleolar union, complementary nucleoplasm and positive-only ratios. Independent ImageJ references compare 482 NCL regions and 817 GFP nuclei; analytical/replay tests cover missing values and exact pixels. | Correct masks and suitable biological backgrounds still require review. Public automatic masks are not annotation ground truth. |
| A01–A03 | Actual locked Fiji/StarDist and ImageJ/MorphoLibJ; explicit candidate states, no native whole-nucleus/top-fraction fallback. Real Fiji tests and public-image records identify versions and limitations. | Starting thresholds are not experiment-validated defaults. NCL-defined regions can change with NCL redistribution. |
| A04 | Add/delete/reshape/merge/split, strict parent containment, dependent-child invalidation, CAS revision checks and branch-aware Undo/Redo. Nuclear merge/split tests inspect exact pixels and unaffected objects; separately recorded browser checks inspect nucleolar merge/split/Undo unions. | These checks do not measure researcher correction burden. |
| A08 | Generalized, versioned RGB/downsample/background/clipping/epsilon/GFP compatibility implementation and tests. | Original private cohort, existing-code outputs and legacy differences remain M4; no preferred p value is a target. |
| A09 | Saturation/edge/candidate/containment QC, reasoned exclusions and old-result labels. Native signal QC1.0.0 adds continuous signed background-dispersion ratios, explicit missing reasons and an optional warning threshold. | No universal weak-signal threshold is supplied; warnings never automatically exclude observations. |

## Statistics and publication outputs

| Requirements | Implemented behavior and evidence | Remaining scope |
|---|---|---|
| S01, S05 | Explicit confirmed-control/manual/Otsu GFP gates, exploratory upper bounds; saved threshold/date/high-region sensitivities and reviewed compatible native alternatives. Statistics1.2.1 fixes alternative-threshold row provenance without changing selection arithmetic. Tests verify actual thresholds, exclusions, source immutability and replay. | Gates and region definitions must be chosen for scientific reasons. No search for a preferred significance result. |
| S02–S03 | Field median→sample mean→independent-unit mean, distinct n, complete pairing, Welch/paired two-sided contrasts and declared Holm families. Closed-form independent calculations test effects, SE, degrees of freedom, p values and intervals. | User metadata cannot establish genuine experimental independence or prospective analysis choice. |
| S04 | Saved GFP transform/date centering, exploratory group/GFP/date and repeat models, explicit rank/confounding/missing-control/few-cluster warnings. Independent matrix algebra and density integration test CRV1 covariance, contrasts and predictions. | Field clustering does not account for shared biological-unit dependence; these results remain exploratory. Mixed models are deferred. |
| P06, S06, S08 | Source-linked Matplotlib SVG/PDF/PNG, distinct unit/field glyphs, paired plots, adjusted means and saved pointwise confidence intervals for adjusted means using clustered covariance. Nature presets enforce 89/183mm width, ≤170mm height and editable 5–7pt text; installed rendering tests verify physical sizes, fonts and source tables. | Journal formatting is separate from scientific validity and editorial acceptance. Final labels/layout need manuscript review. |
| S07 | Measurement/statistics CSV, canonical masks, pixel-exact supported Fiji ROI exchange, template Methods, exact configuration/environment and hash-checked replay. Original images require explicit opt-in. Numeric replay exports normalized rows and the original CSV hash; the original CSV must be supplied separately. | Replay uses reviewed masks, not fresh detection. Unsupported arbitrary polygon imports are rejected. Downloaded copies remain under the user's control. |

## System, publication and operating boundaries

| Requirements | Implementation and verification | Remaining scope |
|---|---|---|
| T01, T03–T05 | Locked Web/Python monorepo, generated OpenAPI/TS/default recipe, immutable revisions separate from jobs, local SQLite/Alembic, six bounded replacement interfaces, supervised single-worker leases/fencing/retry/cancellation. API/process/browser tests exercise these boundaries. | No scaling or shared-network SQLite claim; the method-proposal interface has no required external service. |
| T02, L01, L03 | Shared browser/API/scientific implementation, automated isolated Windows setup and a separate Linux Compose/TLS configuration. Installed-copy public-image browser acceptance precedes download publication. | Initial delivery is local-first. A hosted private API is not deployed; Vercel is the public sample viewer and download entry point. |
| T06–T07, L02 | One-use invitations, hashed tokens, owner checks on every private artifact, Origin/CSRF, HttpOnly cookies and no-store. Local mode restricts literal loopback/Host/Fetch Metadata and is absent from the ordinary hosted build. Cross-session and hostile-origin tests verify rejection. | Local OS processes and the current OS user are trusted. Local HTTP cookies intentionally differ from the Secure-cookie HTTPS hosting requirement. |
| T08, T10 | Private data outside checkout; fixed recipes, no arbitrary submitted code/URLs or runtime downloads. Hashed Fiji/Java/plugins/models. Actual Linux container CI checks denied egress/read-only root/UID and CPU detection. | Windows local mode does not install an OS egress firewall. Application safeguards are not proof of OS-level network denial. |
| T09, L04 | Explicit-activity24h retention, immediate access denial, active-expiry heartbeat/watchdog/result fencing, stop-and-reap before lease release and physical cleanup. Real child/descendant lifecycle regression verifies expiry ordering. | Physical cleanup while the PC/launcher is off occurs at next launch. Future hosting needs continuous deletion acceptance. |
| T11, L05 | PR→required Python/Web/Fiji-browser/Windows CI→exact-head main merge→automatic Vercel deployment. Clean allowlisted release sources, checksums, installed-copy and canonical-browser receipts identify their exact sources separately. | A merge, hosted UI and scientific acceptance are distinct events. Older packages are immutable and do not inherit later fixes. |
| D01–D03 | README/AGENTS/design/security/operations/validation/roadmap/OSS and handoff docs; synthetic arithmetic tests plus registered published images. CI includes contract drift, real browser/Fiji/container checks, public-data hashes, fixed-version history/tracked-file secret scanning, dependency audits and retained dependency/license evidence. | Scanners cannot prove absence of confidential science or legal compatibility. License evidence is an inventory/check, not a legal certification. External documentation links are not exhaustively monitored. |
| D04–D05 | Public detector/reference reports and independent mathematical checks are recorded separately in [validation](validation.md). | **M4 open:** private originals, field/sample-separated tuning/evaluation, reviewed annotations, target detection F1 and legacy reconciliation. No private raw data or annotation has been supplied for this gate. |
| D06 | Participant/operator acceptance criteria are documented: completion, correction time, unit understanding and reuse. Automated UI and installed-package evidence is retained. | **M5 open:** actual intended-machine operator acceptance and researcher participation, preferably ≥3 across labs. Automated tests do not substitute for users. |
| D07 | Identity/DB/storage/job/image-engine/accepted-method interfaces preserve future migration boundaries. | Supabase/accounts/teams, structured LLM proposals, long-term storage, payment and further scientific recipes are intentionally deferred. |

## Corrections found by this audit

- Alternative GFP-threshold rows inherited primary gate metadata. Protocol1.2.1 records their actual manual threshold/reason and exploratory status; primary rows and numeric selection stay unchanged.
- Expired workspaces denied API reads but live jobs could renew their lease. Heartbeat, independent watchdog and final publication now reject expiry; physical deletion still waits for process shutdown.
- Positive near-background signals lacked the requested native weak-signal display. The optional, warning-only diagnostic closes this UI/metadata gap without inventing a biological cutoff.
- CZI conversion instructions and operation-specific nuclear merge/split tests were missing. The procedure and tests now record their exact verification limits.
- Default-recipe JSON was not regenerated by the contract-drift check. The CLI now explicitly generates it from Pydantic alongside OpenAPI.
- CI secret coverage and dependency inventory were narrower than the plan. Pinned history scanning and retained Python/Web/Fiji license evidence extend the actual checks; no comprehensive confidentiality or legal guarantee is inferred.
- The accepted local.9 public GFP export called its nuclei DAPI-defined although the published input used DRAQ. Methods now distinguish the historical `dapi` channel role from actual stain identity, including legacy QC and auxiliary low-intensity terminology. The display label uses the nuclear-stain term as well. This changes explanatory text, not detector parameters, masks, measurements or statistics. Earlier exports retain their original wording and need manuscript review; source corrections reach a downloadable package only after its separate release acceptance.

Each correction follows the normal PR/CI/release process. This audit is a coverage map, not permission to mark private M4, human M5 or future hosted operations complete.

## Current source checkpoint — planning and general 2D regions

This addendum describes the newer source workflow; the local.8/local.9/local.10
observations above remain historical evidence for their exact sources and
packages. They are not retrospectively renamed or counted as local.11 results.

| Requirements | New source behavior | Evidence boundary |
|---|---|---|
| P07–P10 | Version 2.0.0 planning distinguishes area, mean, integrated intensity and native compartment ratios; explicit adoption 1.0.0 resolves the actual metric/channel and retains the plan and acknowledged changes in immutable revisions, Methods and replay. | Planning answers do not confirm actual channel identity, background validity, acquisition comparability or independence. |
| I09, I11, A10–A11 | Named generic channels, manual/imported regions, confirmed nuclear-stain initialization, corrected-trial mask reuse and reviewed batch file mapping with source-bound idempotent retries. | Filenames do not establish stain identity or experimental units. New images require their own calibration confirmation. The existing fixed nuclear model has no new biological accuracy claim. |
| I10 | Experimental-metadata edits create unreviewed child revisions while retaining source images and reviewed mask pixels. | Unknown metadata stays unknown; source registration is not proof of independent replication. |
| S09 | Per-field descriptive figures preserve selected region/channel/metric identity, observations, exclusions and missingness; one valid field is sufficient. | No independent n, p value or inferential interval is fabricated. |
| S10 | Generic experimental-unit comparisons require an explicit design, full unit/pair coverage, acquisition review and declared Holm family; channel-repeated area is counted once. | No GFP regression or batch correction is inferred for other markers. Unexplained missing units, incomplete pairs and failed fields still block inference. |
| S02–S03, S06–S08 | Statistics 1.2.3 includes stable paired effects from the paired differences. Figure 1.1.3 supports verified mixed-language glyphs and portable generated log2 labels, with editable source-linked SVG/PDF. | Numeric correctness and vector formatting do not establish biological applicability or editorial acceptance. |

The adopted metric/channel is used to initialize figure selections from the saved
revision. Unavailable selections stop generation instead of silently selecting a
different metric; deliberate changes are labelled. Supplied planning JSON is
recomputed rather than trusted as an executable decision.

**Verified source and public-interface checkpoint:** [PR #13](https://github.com/genellect/cytellect/pull/13)
passed all four required checks on `f07487c12351198574ce442b400b05ca359dae51`
in [run 37139192581](https://github.com/genellect/cytellect/actions/runs/37139192581).
Merged main `c21f9057dd130b87ba55b113d40a0396dcb79e74` also passed all four checks
in [run 37140066549](https://github.com/genellect/cytellect/actions/runs/37140066549).
That source reached Vercel production READY as
`dpl_BQMM7JgbSCFKaf6CTfj36ydzrL6S`. Separate canonical browser checks of the
[landing page](https://cytellect.vercel.app/) and
[planning guide](https://cytellect.vercel.app/plan) at 1440 px and 390 px passed
six checks; four screenshots were reviewed and no browser errors
were recorded. These checks cover the public interface, not hosted private
analysis or human usability.

**Installed local.11 checkpoint: accepted second CI attempt; first failure retained.**
[Windows packaging run 37140892298](https://github.com/genellect/cytellect/actions/runs/37140892298)
passed fresh and repeat installation, then failed one of nine installed browser
cases (eight passed; zero skipped or flaky). The initial local-workspace heading
was not found. The independent numerical replay did not run; launcher shutdown
passed. The draft-release job was skipped, so this attempt did not publish a
package. Its cause remains unidentified; it is not described as fixed.

[Attempt 2](https://github.com/genellect/cytellect/actions/runs/37140892298/attempts/2)
rebuilt the same source with the unchanged acceptance harness and passed nine
browser cases (zero failed/skipped/flaky), independent numerical/replay checks
and launcher shutdown. The accepted ZIP is a new build, not the first attempt's
archive: 5,823,606 bytes, SHA-256
`ba5835dd55ed9ad6df9698c6200c715c8084ef6d3990b3764f98c6e6d440819b`.
Independent inspection verified all 138 payload files, exact-source contents
and installed module identity. The [prerelease](https://github.com/genellect/cytellect/releases/tag/v0.1.0-local.11)
was published; all six public assets were downloaded anonymously and matched
the reviewed files. The canonical site's download-button update has its own
subsequent PR/deployment check. A public UI release does not update an installed
package. See the [package record](local-release-0.1.0.md).

A separate same-source local rebuild could not finish installation because
Smart App Control blocked an unsigned virtual-environment Python launcher.
That machine is not counted as an accepted installation; no security policy was
disabled. Its operating implications are documented in [local delivery](local.md).

**Remaining acceptance is unchanged:** M4 requires the user's private originals,
reference regions and field/sample-separated evaluation, including legacy
reconciliation. M5 requires the intended operator and researcher task evaluation,
including correction time, understanding of measurement/n and reuse intent.
Published-image, agent and browser checks cannot substitute for these gates.
Future hosted private analysis retains its separate operational/privacy acceptance.
