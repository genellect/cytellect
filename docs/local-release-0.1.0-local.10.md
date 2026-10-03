# Windows preview 0.1.0-local.10 — acceptance record

The [published Windows preview](https://github.com/genellect/cytellect/releases/tag/v0.1.0-local.10) corrects exported Methods that could misidentify a nuclear stain. The [local.9 record](local-release-0.1.0-local.9.md) is preserved unchanged for its immutable package.

This is a browser workspace with a private local API and fixed Fiji worker. Scientific contracts remain shared with the future hosted edition. Software acceptance does not validate a private experiment, establish biological segmentation accuracy or guarantee journal acceptance.

## Release identity

| Item | Value |
|---|---|
| Source | `f8a5a16080d94634fb708de5e11cf054a4618a7d` |
| Archive | `Cytellect-0.1.0-local.10-windows-x64.zip` |
| Archive bytes | 5,704,801 |
| SHA-256 | `d94e64386500a7d51b11e58db69ef60ecbab469c7a745a13f06e14783c79437e` |
| Package manifest entries | 107 |
| Source PR | [#8](https://github.com/genellect/cytellect/pull/8) |
| PR CI | [Run 37065898370](https://github.com/genellect/cytellect/actions/runs/37065898370), all four required checks passed |
| Exact-source main CI | [Run 37066600921](https://github.com/genellect/cytellect/actions/runs/37066600921), all four required checks passed |
| Installed Python | 3.12.15 |

Source merge, CI, installation, scientific verification, release publication and the hosted download are separate checks. The public website serves published samples and the download; private analysis runs locally.

The source merge reached Vercel production READY as `dpl_7iS3bsUwn5ewjroHnyjFqd6HEQtD`, at `cytellect-36y1yhcdc-yuto10.vercel.app`. Download metadata follows in a separate PR. Canonical browser/download acceptance is recorded separately after its deployment.

## Correction and unchanged behavior

An actual local.9 export from the published BBBC013 GFP sample described nuclei as DAPI-defined, although its nuclear stain was DRAQ. The historical `dapi` role cannot establish chemical identity. Methods template **1.0.0**, the first explicitly versioned template, now describes the nuclear-stain channel, the recorded role and saved manual corrections. It asks researchers to confirm the acquired stain from acquisition records. The native auxiliary method label is also stain-neutral; its `dapi-low` identifier is unchanged.

Previously exported Methods are not rewritten: review them before manuscript reuse. No automatic DRAQ or Hoechst name is substituted for an unknown acquisition stain.

Source review found no changes to detection parameters/models, masks, numerical measurement, GFP selection, statistics, figure rendering or pinned dependencies. The Methods text, its manifest hash, ZIP hash and source identity change. Measurement1.1.1, GFP selection1.1.1, statistics1.2.1, figure rendering1.1.1 and native signal-QC1.0.0 remain unchanged.

## Checks on this installed package

- All **107 manifest entries** and installed source/import locations verified. Installation completed in **140.218 seconds**, using an existing task-owned installation root with cached dedicated Python/dependencies and unchanged versioned Fiji. This is a cached upgrade observation, not a fresh-download benchmark; shortcut creation was disabled.
- The pinned Fiji installation check passed. Its synthetic fixture establishes runtime readiness, not biological accuracy.
- The installed published BBBC013 A01 browser workflow passed upload, Fiji detection, review, export and reload in **45.2 seconds**. It yielded **350 nuclei**, no field failures and explicit missing NCL measurements.
- The visible optional QC threshold100000 exercised the warning path. This test value is not a scientific recommendation. Remeasurement reused existing labels; all original JSON/CSV measurement and selection values and three canonical640×640 mask layers were identical before and after.
- Both actual export ZIPs identified this exact source, verified17 internal manifest hashes and excluded original images. Their Methods contained template1.0.0, the role-versus-dye explanation and saved-correction description, with no unsupported named-stain claim.
- Actual1440px/390px browser checks passed strict CSP, zero off-origin requests/errors, empty browser local/session storage,350 table rows and scrolling/sticky headers. All five accepted screenshots were visually reviewed; mobile table columns scroll inside their container without page overflow.
- Shutdown left zero owned processes and zero listeners on the test port. Windows native execution still does not provide an OS-enforced worker egress block.

### Retained failed first attempt

The first scratch data directory made the legacy Windows TensorFlow model path's worst-case length241 characters, exceeding the existing240-character guard. The application reported `fiji_temporary_path_too_long`, retained the failed field and prevented quality approval; the browser test failed and shutdown succeeded.

That attempt remains failed in the evidence. A new evidence directory and a shorter private scratch data directory were used for the accepted run above. The archive, installed code and tests were unchanged. This is an environment correction, not a relaxed acceptance threshold or silent image resizing.

## Prior evidence and remaining gates

The [local.9 record](local-release-0.1.0-local.9.md) retains114 installed scientific tests,22 figure tests and12 inspected PDF renderings. Four test cases overlap between those suites. They support unchanged numerical/rendering code historically and were **not rerun or counted as new local.10 tests**. This wording-only release adds targeted Methods regressions in source CI and direct checks of the installed export.

[Public-image comparisons and independent statistical references](validation.md) remain separate evidence. Original-image validation for the user's experiment (M4) and human operator/researcher evaluation (M5) are open. A future hosted private service also requires actual domain/TLS, access, retention, recovery and worker-isolation acceptance.

Native automatic nuclear detection retains the standard-2g limit: each edge at most2048px and at most2,700,000pixels. Larger inputs fail explicitly without rescaling measurement pixels. NCL-defined candidates require biological review because NCL redistribution can change their boundaries.

See [methods](methods.md), [statistics](statistics.md), [local operation](local.md), [data protection](security.md) and [offline CZI conversion](converting-czi.md). Private images or research details must not be attached to public issues or release evidence.
