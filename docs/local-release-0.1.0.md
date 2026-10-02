# Windows preview 0.1.0-local.9 — acceptance record

The [published Windows preview](https://github.com/genellect/cytellect/releases/tag/v0.1.0-local.9) passed exact-source main CI, installation, installed scientific/figure checks and public-image browser acceptance. The [local.8 record](local-release-0.1.0-local.8.md) remains unchanged for its own immutable package.

The Windows x86-64 package provides the browser workspace, private local API and pinned Fiji worker. Its scientific and export contracts are shared with the future hosted edition. Software acceptance does not validate a private experiment, establish biological segmentation accuracy or guarantee journal acceptance.

## Release identity

| Item | Value |
|---|---|
| Source | `d810a0f82ee0e76aa2e264e9477b6f805c2c6157` |
| Archive | `Cytellect-0.1.0-local.9-windows-x64.zip` |
| Archive bytes | 5,704,533 |
| SHA-256 | `bdb202b1b85b91f6d1a67aa6d4da1149b5f87d591fb91189945b718dfe5fd720` |
| Package manifest entries | 107 |
| Source PR | [#6](https://github.com/genellect/cytellect/pull/6) |
| PR CI | [Run 37057562660](https://github.com/genellect/cytellect/actions/runs/37057562660), all four required checks passed |
| Exact-source main CI | [Run 37058439039](https://github.com/genellect/cytellect/actions/runs/37058439039), all four required checks passed |
| Installed Python | 3.12.15 |

Source merge, CI, installation, scientific verification, release publication and the actual hosted download are separate checks. The public website remains a sample viewer and download entry point; private analysis runs locally. No hosted private analysis service is claimed here.

At scientific-source publication, Vercel deployment `dpl_CfxbffudbF1qhyuq1VaivbMWh5pQ` reached READY on the same source. Its immutable host is `cytellect-4j2x1o1lu-yuto10.vercel.app`. The download metadata follows in a separate PR; canonical browser/download verification is recorded separately after that merge. GitHub's published asset digest and size match the candidate above.

## Changes since local.8

- **Optional native signal quality display, protocol 1.0.0.** Nuclear GFP and nuclear/nucleolar/nucleoplasmic NCL can show signed corrected mean divided by robust background dispersion. The warning threshold is initially unset. Zero or invalid background dispersion and unavailable compartments retain explicit missing reasons. Changing the threshold remeasures existing masks and never changes measured intensities, GFP selection or exclusions automatically. This is a spatial background diagnostic, not a validated universal signal-to-noise cutoff.
- **Corrected GFP-threshold sensitivity metadata, statistics protocol 1.2.1.** Each alternative now records the threshold and manual/exploratory selection actually used. Primary rows, numerical selection and statistical formulas are unchanged. Recompute older 1.2.0 scenarios before relying on their per-row gate provenance; their scenario identity already recorded the alternative threshold.
- **Expiry enforced during execution.** An expired workspace can no longer keep a task alive through lease renewal. Heartbeat, independent watchdog and final result publication reject expiry. The process tree is stopped and reaped before the lease is released and private files are physically deleted. Cleanup while the launcher or PC is off still resumes at next launch.
- **Reproducible preparation and stronger regressions.** Offline Bio-Formats CZI conversion instructions record series, axes, bit depth, channel identity and calibration without implicit projection/RGB conversion. Exact nuclear merge/split invariants are tested. Default-recipe generation is included in contract drift checks, and CI retains fixed-version secret-scanning and dependency/license evidence. These checks are not an exhaustive confidentiality or legal certification.

Measurement protocol 1.1.1, GFP selection protocol 1.1.1 and figure rendering protocol 1.1.1 remain separate from the new signal-QC and statistics metadata versions. No detection model or measurement formula is changed by the optional QC display.

## Confirmed checks on this installed candidate

- All **107 package manifest entries** and installed application source hashes verified. Setup completed in **133.986 seconds** as a new application version in an existing isolated installation root, reusing cached dedicated Python/dependencies and the unchanged versioned Fiji runtime. This is a cached upgrade observation, not a fresh-download benchmark. Shortcut creation was disabled.
- The real pinned-Fiji installation check passed. Its synthetic installation fixture checks numerical/runtime readiness, not biological detection quality.
- The actual installed BBBC013 A01 GFP workflow completed upload, Fiji detection, review, export and reload. It yielded **350 nuclei**, no field failures and missing NCL measurements. Published 8-bit GFP fixtures test the recorded image pipeline; this does not validate native instrument intensities or private NCL biology.
- The visible optional QC control submitted a threshold of **100000** to the API. This intentionally large test value exercises the warning path and is not a recommended scientific threshold. The second analysis reused existing labels. Every original JSON and CSV measurement/selection value and all three canonical 640×640 mask layers were identical before and after the change.
- Both exports matched the exact source above. Each contained **17 verified manifest file hashes**, and both excluded original images. Installed Python and scientific imports were used for the comparison; development scientific libraries were not substituted.
- Actual 1440px/390px browser checks verified rendered imagery, all 350 table rows, table scrolling and sticky headers. The narrow table scrolled within its container without document overflow. Strict CSP passed; no off-origin requests, application errors or CSP violations were recorded. Browser local/session storage remained empty.
- Stopping the owned launcher left **zero owned processes and zero listeners** on its test port. Native Windows execution still does not provide an OS-enforced worker egress block.

## Installed scientific and figure verification

- **114 scientific tests passed**, with zero failures/skips. One HTTP-only reconfiguration case was explicitly deselected from this installed-science scope and is covered by source CI and actual browser checks. Original test bytes, selected/deselected IDs and hashes are recorded. Imports before/after execution were verified against the installed application; the overlay contained pytest tooling only.
- **22 figure tests passed**, with zero failures/skips. Twelve English/Japanese, 89/183mm distribution/paired/scatter cases were generated using installed Matplotlib and rasterized from the actual PDFs. Physical dimensions, editable vector text, regular embedded fonts, source-table hashes and mean/count correspondence passed. All twelve rendered PDFs were visually checked for axes, labels, legends, confidence bands, paired lines and clipping.
- Two named figure test functions expand to **four cases shared with the scientific suite**. Do not add114 and22 as a unique test total; the twelve renderings are also a separate verification activity.
- The first scratch verification harness selected the unsuitable HTTP test and incorrectly allowed its passed-count integer to overwrite a boolean status. That attempt is retained as failed. The corrected harness passed five subprocess self-checks proving failure/skip/wrong exclusion cannot return success, then reran both suites into new evidence directories. No product or package source was changed to obtain a pass.

## Historical evidence and remaining acceptance

Preserve the [local.8 acceptance record](local-release-0.1.0-local.8.md) without rewriting its results. Public NCL/ImageJ and GFP reference comparisons remain separately documented in [validation](validation.md); earlier reference measurements do not become a new installed-copy acceptance result merely because the engine is unchanged.

- **M4:** user-provided original images and reviewed annotations in a private environment, field/sample-separated tuning and evaluation, corrected-mask reference measurements and legacy reconciliation.
- **M5:** operator acceptance on the intended machine and researcher evaluation of completion, correction time, experimental-unit understanding and reuse. Automated browser tests do not substitute for participant evaluation.
- **Future cloud service:** actual private hosting, TLS/domain/session acceptance, continuous deletion while clients are offline, durable recovery and host-enforced worker isolation.

Native automatic nuclear detection retains the standard-2g admission limit: each edge at most 2048 px and no more than 2,700,000 pixels. Excess inputs fail explicitly without silently rescaling measurement pixels. NCL-defined candidates still require biological review because redistribution of NCL can change their boundaries.

The documented Bio-Formats conversion mechanics preserved 5,751,808 pixels in public grayscale TIFF→OME-TIFF roundtrips. This does not validate proprietary CZI decoding or the complete GUI procedure without suitable originals. See [offline conversion](converting-czi.md), [signal semantics](methods.md), [statistics](statistics.md), [data protection](security.md) and [local operation](local.md). Private research data must not be attached to public issues or release evidence.
