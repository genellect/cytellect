# Windows preview 0.1.0-local.8 — acceptance record

The [published Windows x86-64 preview](https://github.com/genellect/cytellect/releases/tag/v0.1.0-local.8) provides the browser workspace, local API and pinned Fiji worker. It supports nuclear/nucleolar correction, GFP/NCL measurements, independent-unit comparisons, exploratory models, editable figures and reproducibility exports. This is acceptance of the recorded software package, not validation of a private experiment or journal acceptance.

## Release identity

| Item | Value |
|---|---|
| Source | `8b87f21ae9ce5449b2a327c368477249983c7a9d` |
| Archive | `Cytellect-0.1.0-local.8-windows-x64.zip` |
| Archive bytes | 5,701,069 |
| SHA-256 | `5c49c0b64eac78ce6a89a9aa8db5cf529c132044315ed0eb306a3c6e86ac5cc5` |
| Source PR | [#4](https://github.com/genellect/cytellect/pull/4) |
| Exact-source main CI | [Run 37050026779](https://github.com/genellect/cytellect/actions/runs/37050026779) |
| Installed Python | 3.12.15 |

Required Python, Web, Windows lifecycle and actual Fiji/browser checks passed on that source. The immutable bundle was built from the clean merged main commit and verified on Windows before publication. Source merge, installation, release publication and hosted download behavior are separate checks. The public site remains a sample viewer; private analysis runs locally.

The setup archive includes redistribution-cleared public demo derivatives, attribution and a hash allowlist alongside source and static UI. It excludes private research data, raw study inputs, credentials and developer runtimes. The earlier [local.6 acceptance record](local-release-0.1.0-local.6.md) remains available; local.7 was an unpublished release-automation draft and is superseded by this version.

## Changes since local.6

- Incomplete OME channel/IFD mappings are rejected before decoding. Explicitly reordered channels remain supported.
- Nucleoplasmic area and nucleolar detection states are explicit. Recoverable nucleolar failures preserve nuclear measurements while leaving unresolved compartments missing; review and statistics require correction or a reasoned exclusion.
- Re-detection saves background/exclusion settings atomically and prevents inconsistent partial adoption of global conditions. Revision navigation retains the chosen edit branch.
- Reviewed native nucleolar definitions can be compared using saved alternative masks. Reproducibility exports recalculate these alternatives from supplied original pixels.
- Model coefficients, repeat trends and sensitivity results have source-linked CSVs. Numerical-table imports now export their data, conditions, Methods and a hash-verified replay package.

## Checks on this installed package

- All **106 package manifest entries** verified. Setup completed in **415.963 seconds** in an existing task-owned installation root. Dedicated Python/dependency caches were reused and a new pinned Fiji runtime was downloaded. This is neither a fresh-download benchmark nor a fully cached upgrade. Shortcut creation was disabled in this isolated run.
- Actual installed Tk and Fiji passed. The known-pixel installation check produced 9 nuclei and 18 nucleolar candidates; these are installation checks, not biological accuracy estimates.
- **97 numerical/input/ROI/statistics/replay tests passed with zero skips** using scientific modules loaded from the installed application. A separate pytest-only tooling overlay and fixed test definitions were used; development scientific libraries were not substituted.
- **22 figure tests passed with zero skips**, followed by 12 English/Japanese distribution, paired and exploratory scatter renderings at 89/183 mm. All actual PDFs were rendered and visually inspected. Regular-weight Arial/DejaVu Sans/Yu Gothic, editable SVG text, embedded TrueType PDF fonts, Unicode mappings, physical dimensions and source correspondence passed. Synthetic plotting data establishes formatting, not biological validity.
- The installed public BBBC013 GFP workflow completed image registration, detection, explicit review, export and reload in **48.7 seconds** for the tested browser run. It yielded 350 nuclei, no field failures and missing NCL metrics. This is a single acceptance run, not a general performance benchmark or validation of native FRM intensities.
- Export identity matched this release source; all **17 manifest file hashes** verified and original images were excluded. Desktop/mobile checks verified the actual preview image, all 350 table rows, scrolling, no page overflow, no application/CSP errors and no external requests. Browser local/session storage remained empty.
- Stopping the launcher left no local application listener or local launcher/worker processes. Native Windows execution still does not provide an OS-enforced worker egress block.

The updated public 16-bit NCL reference comparison is recorded in [published NCL validation](public-nucleolar-validation.md): 100 nuclei and 182 candidates, pixel-identical masks to the prior reference, and ImageJ comparisons for 482 compartment/object measurements. That comparison was run on the scientific source in PR #4 before packaging; its engine bridge/model match this installation. It is distinct from the installed numerical tests above and does not establish nucleolar ground-truth accuracy.

## Remaining acceptance

- **M4:** user-provided original images in a private environment; field/sample-separated tuning and evaluation, corrected-mask reference measurements, legacy reconciliation and measured detection quality.
- **M5:** operator acceptance on the intended research machine and researcher evaluation of completion, correction time, independent-unit understanding and reuse demand. Automated browser checks do not replace participant evaluation.
- **Future cloud service:** actual private hosting, TLS/domain/session behavior, continuous deletion while clients are offline, durable recovery and host-enforced worker isolation.

Native automatic nuclear detection currently requires both image sides at most 2048 px and at most 2,700,000 pixels under the standard-2g profile. Excess inputs are rejected without silently resizing measurement pixels. NCL-defined candidates need biological review because NCL redistribution can change the segmented region.

Local work expires 24 hours after explicit activity; cleanup while the launcher or PC is off resumes at next launch. Read [local operation](local.md), [data protection](security.md), [figure semantics](figures.md) and the [roadmap](roadmap.md). Private research material does not belong in GitHub issues or public verification artifacts.
