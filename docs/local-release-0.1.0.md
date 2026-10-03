# Windows preview 0.1.0-local.11 — acceptance record

The [published Windows preview](https://github.com/genellect/cytellect/releases/tag/v0.1.0-local.11) passed installed acceptance on Windows CI. Its public release assets were downloaded anonymously and verified. This record covers the package; canonical-site download verification is a separate metadata-deployment check, recorded in the release notes after it completes. The [local.10 record](local-release-0.1.0-local.10.md) is preserved unchanged.

This version connects analysis planning, named 2D fluorescence channels, region review, batch registration and source-linked figures in the installed browser workspace. Private analysis runs in the local API and fixed Fiji worker. A public website deployment does not update an installed copy or provide hosted private analysis.

## Release identity

| Item | Verified value |
|---|---|
| Source | `c21f9057dd130b87ba55b113d40a0396dcb79e74` |
| Archive | `Cytellect-0.1.0-local.11-windows-x64.zip` |
| Archive bytes | 5,823,606 |
| SHA-256 | `ba5835dd55ed9ad6df9698c6200c715c8084ef6d3990b3764f98c6e6d440819b` |
| Package manifest entries | 138 |
| Installed Python | 3.12.15 |
| Source PR | [#13](https://github.com/genellect/cytellect/pull/13), head `f07487c12351198574ce442b400b05ca359dae51` |
| PR CI | [Run 37139192581](https://github.com/genellect/cytellect/actions/runs/37139192581), all four required checks passed |
| Exact-source main CI | [Run 37140066549](https://github.com/genellect/cytellect/actions/runs/37140066549), all four required checks passed |
| Installed acceptance | [Windows run 37140892298, attempt 2](https://github.com/genellect/cytellect/actions/runs/37140892298/attempts/2) |
| Acceptance harness SHA-256 | `b2d15adfa76f568a07e5da5f60d9c207d91948dcfabd1cb329a028c9fa5adee8` |
| Public release | Prerelease `v0.1.0-local.11`, targeting the source above; six assets verified |
| Canonical download | Separate metadata-deployment check; consult the linked release notes for its recorded outcome |

The accepted archive's size, checksum and all 138 payload hashes were also checked after downloading the CI artifact. Source merge, CI, installation, publication and researcher acceptance are separate checks.

## Changes since local.10

- **Planning and explicit adoption:** planning 2.0.0 separates area, mean, integrated intensity and existing NCL compartment ratios. The API recomputes candidates; adoption 1.0.0 saves the chosen candidate, actual metric/channel and acknowledged changes in immutable revisions, Methods and replay. Plan answers do not confirm staining, backgrounds, acquisition comparability or independence. Old 1.0.x notes require review rather than a guessed conversion. Handoff uses memory within the same runtime or a user-selected JSON file across runtimes.
- **General 2D region measurements:** actual channel labels, manual/imported masks and confirmed nuclear-stain detection support area and intensity measurements without substituting markers for GFP or NCL. Unknown metadata remains unknown. Corrected trial regions can be retained when adding fields; metadata changes create separately reviewable revisions.
- **Batch registration:** an explicit file/channel correspondence table and source-bound retry identities avoid duplicate registration after a lost response. Filenames do not establish stain or experimental-unit identity. New image batches require renewed calibration confirmation.
- **Separate descriptive and inferential outputs:** per-field distributions work without known independent replication. Experimental-unit comparisons require the design, units/pairs, acquisition review, full coverage and a declared Holm family. Exclusions and missingness remain visible; repeated channel rows do not multiply area observations.
- **Calculation and figure corrections:** shared statistics 1.2.3 calculates paired effects from paired differences, improving numerical stability with large offsets. Common figure rendering 1.1.3 checks actual font glyphs for mixed-language labels and uses portable generated `log2` labels without changing values. Figure selections start from the saved adopted metric/channel; unavailable selections do not silently fall back to another measure.

Existing native NCL/GFP and compatibility workflows remain separate recipes. The fixed Fiji nuclear model is reused; this release does not establish a new segmentation-accuracy claim. See [planning](analysis-planning.md), [generic regions](generic-regions.md), [descriptive outputs](descriptive.md) and [region comparisons](region-comparisons.md).

## Accepted installed checks

Windows CI performed fresh setup with pinned Python and actual Fiji, followed by repeat setup in the same installation. It used console setup with shortcut creation disabled; this is not a human onboarding or shortcut test.

- Installed browser acceptance completed **9 passed, 0 failed, 0 skipped and 0 flaky** cases. The cases cover the native published-image route, generic manual/imported regions and nuclear detection, saved corrections, descriptive output, unit comparisons, plan handoff/import and batch retry. These are automated workflows, not researcher observations.
- Independent installed checks verified source/import identities and signed measurements from four generated regions: corrected values A = [−3, −1], B = [2, 0], area 4 px² and integrated values four times the means. Unknown calibration remained unknown.
- Independent closed-form references checked the effect, standard error, statistic, degrees of freedom, two-sided p value, unadjusted 95% interval and single-contrast Holm result. Welch and paired effects both equalled −3; their standard errors were √2 and 2, with degrees of freedom 2 and 1. These artificial units verify arithmetic, not biological replication.
- Figure source downloads succeeded. A raw-opt-in analysis ZIP verified **64 internal file hashes**; replay matched saved measurements and comparisons for all four generated fields. Reconfirming review did not invalidate export, and the generated workspace was deleted.
- Shutdown passed the harness's launcher-stop and test-listener-absence check. No comprehensive Windows process or egress-isolation claim is inferred.

The published [installed acceptance receipt](https://github.com/genellect/cytellect/releases/download/v0.1.0-local.11/Cytellect-0.1.0-local.11-acceptance.json) and [independent numerical/replay receipt](https://github.com/genellect/cytellect/releases/download/v0.1.0-local.11/Cytellect-0.1.0-local.11-numerical-replay.json) identify the exact source and harness; the first also binds the archive hash. Earlier development counts and previous-release screenshots are not counted as new installed results.

### Retained first-attempt failure

Attempt 1 passed fresh/repeat setup but recorded **8 passed, 1 failed, 0 skipped and 0 flaky** installed browser cases. A test did not find the initial local-workspace heading. Independent numerical replay did not run; shutdown passed and the release job was skipped. **The cause remains unresolved.** A successful rerun does not prove that the original failure was fixed or harmless.

Attempt 2 reran the same source and acceptance harness without relaxing checks. It rebuilt the archive: the failed attempt's SHA-256 was `07ba6fc7af6abe169e47759f884256f7c9e0169af399287f0ac44a6099f61a3a`; the accepted archive is the one identified above. This is not a claim that the same ZIP bytes were retested.

### Separate block on the development PC

A separate local rebuild of the same source did not complete installation on the development PC. Windows Application Control returned OS error **4551** when querying a uv-created virtual-environment Python launcher; the diagnostic record identifies a Smart App Control block. The setup-complete marker was absent. No security policy was bypassed, and this attempt is **not an accepted installation**.

That local rebuild had SHA-256 `b17242d637174c637854dd9fdd3996b080c24fd02c374cfa60a1dbdf3df96c25`; it was not either CI archive. CI acceptance does not establish installation on this PC or every Windows configuration. Separate source-runtime reproduction is not installed-package evidence.

## Public release and website

The prerelease targets the source above. All six public assets were downloaded without authentication and matched the prepared bytes: the Windows ZIP and checksum, two scoped acceptance receipts, and the optional BBBC013 practice ZIP and checksum. Practice images retain DRAQ and FKHR-EGFP identities and do not provide NCL, reference masks, confirmed background ROIs or biological replication.

Source `c21f9057dd130b87ba55b113d40a0396dcb79e74` reached Vercel production READY as `dpl_BQMM7JgbSCFKaf6CTfj36ydzrL6S`. Separate canonical checks of the [landing page](https://cytellect.vercel.app/) and [planning guide](https://cytellect.vercel.app/plan) at 1440 px and 390 px passed six checks, with four screenshots reviewed and no recorded browser errors. These checks establish the public interface, not private cloud analysis or the site's local.11 download.

Verify the canonical site's local.11 version, download button and downloaded archive identity after the metadata deployment, and append its exact source and outcome to the linked release notes. A published GitHub asset does not establish that the website points to it.

## Scientific and operating limits

- **M4 remains open:** the user's original images, reference regions, field/sample-separated tuning/evaluation and reconciliation with private legacy analysis have not been validated. Public images and fixed-pixel/ImageJ agreement cannot establish applicability to that experiment. NCL-defined candidate boundaries can change with NCL redistribution; automatic nuclear masks still require review.
- **M5 remains open:** intended-operator acceptance and researcher task evaluation have not been completed. Time savings, correction burden, understanding of measurements/independent n and reuse demand require actual participants.
- Descriptive plots show individual region values and per-field summaries. They do not pool fields into biological replicates or supply p values or inferential intervals. Unit comparisons require confirmed independent allocation or justified complete pairing. Each declared family uses Holm correction; displayed confidence intervals are not multiplicity-adjusted. Generic markers do not acquire GFP regression, automatic batch correction or mixed models.
- Editable, traceable and reproducible figures do not guarantee biological validity or journal acceptance. Final labels and layout need review. The native standard-2g nuclear admission limit remains: each edge at most 2048 px and at most 2,700,000 pixels. Larger inputs fail rather than resizing measurement pixels. Arbitrary whole-cell detection, 3D and time series remain outside scope.
- Private originals and results stay outside source/CI/public assets. Retention is 24 hours after explicit activity; physical deletion while the PC or launcher is off resumes at next launch. Windows local mode trusts the local OS user/process boundary and does not install an OS-enforced worker egress firewall. Future hosted private analysis still requires separate TLS/domain, isolation, retention and recovery acceptance.

See [validation](validation.md), [statistics](statistics.md), [figure conventions](figures.md), [local operation](local.md) and [data protection](security.md). Do not attach private images or research details to public issues or release evidence.
