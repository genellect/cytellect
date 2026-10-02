# Windows preview 0.1.0-local.6 — acceptance record

The [published Windows x86-64 preview](https://github.com/genellect/cytellect/releases/tag/v0.1.0-local.6) provides the browser workspace with a local API and pinned Fiji worker. It supports nuclear/nucleolar review and correction, GFP/NCL measurements, statistics, editable figures and reproducibility exports. This is acceptance of the recorded software package, not validation of a private experiment or journal acceptance.

## Release identity

| Item | Value |
|---|---|
| Source | `81047dc8001d4ecb456eab1aceafec278d9533e8` |
| Archive | `Cytellect-0.1.0-local.6-windows-x64.zip` |
| Archive bytes | 5,683,514 |
| SHA-256 | `2cb9fbf64a5ad91931e39a20c8ee2df6d9cc62a118a76f1d938d75f580780668` |
| Exact-source CI | [Run 37039980341](https://github.com/genellect/cytellect/actions/runs/37039980341) |
| Installed Python | 3.12.15 |

Required Python, Web, Windows lifecycle and actual Fiji/browser checks passed on that source. Source merge, package installation, published release and public-site behavior are distinct checks. The public site remains a sample viewer; this release does not provide a hosted private analysis backend.

The setup archive includes redistribution-cleared public demo derivatives, attribution and a hash allowlist alongside source and static UI. It excludes private research data, raw study inputs, credentials and developer runtimes.

## Installed local.6 checks

- The manifest and archive checksum verified. Setup completed in **107.587 seconds using an existing owned installation root and cached dependencies**. This was an upgrade acceptance run, not a fresh-download benchmark. Shortcut creation was disabled in this isolated run.
- Actual installed Tk and pinned Fiji passed their installation checks. The known-pixel Fiji check produced 9 nuclei and 18 nucleolar candidates. These counts check installation and arithmetic, not biological detection accuracy.
- The installed public BBBC013 GFP workflow completed analysis, review and export with **350 nuclei**, no field failures and absent NCL values preserved as missing. It uses the registered public 8-bit image export; it does not establish quantitative equivalence with native FRM data or the user's images. See [public GFP validation](public-gfp-validation.md).
- The exported reproducibility package recorded the release source, verified **17 manifest file hashes** and excluded original images. The GFP-only table displayed NCL as outside the recipe's scope while preserving the underlying quality flags.
- Desktop and mobile browser checks found no application errors, failed requests, CSP violations or external requests during the tested local workflow. The 350-row table scrolled to its end with its header retained; mobile table scrolling did not cause page overflow. Browser local/session storage contained no entries.
- Shutdown left no matching installed application processes or listener. This is lifecycle evidence for the tested installed run, not OS-level network isolation.

## Earlier installed checks on unchanged code

The local.6 manifest comparison found all **56 non-Web package files byte-identical** to local.5, source `f1af4aba215c4b0524e49598d976a1f59290a5b8`. The intervening source changes affected Web QC presentation only. The following checks were actually run on local.5, not rerun on local.6:

- **22 figure tests and 12 rendering cases**, using the installed scientific dependencies and a pytest-only tooling overlay. English/Japanese distribution, paired and exploratory scatter figures covered 89/183 mm presets, 7 pt text, editable SVG text and embedded TrueType PDF fonts. All 12 rendered PDFs were visually checked. The selected regular-weight fonts were Arial, DejaVu Sans or Yu Gothic according to glyph coverage; no missing-glyph warning was accepted. These synthetic figures establish formatting and source correspondence, not biological validity.
- **Two real Pythonw/Tk launcher cases**, invoking the Stop button and window-close callback in test-owned windows. Both verified local session creation, the browser-open callback, session revocation, child-process shutdown and port release. Browser navigation was verified separately.

The independent installed numerical/reference suite of **27 tests** was run on local.3, source `0419b55a821ef1f5a16b23d9f7cc1b843623d704`, with installed scientific packages and a pytest-only tooling overlay. Measurement, statistics, legacy and ROI implementation files remained unchanged through local.6; `figures.py` was the only analysis-package change and received the later figure checks above. This is an evidence chain, not a claim that all historical tests were re-executed on the release source. See [validation layers](validation.md) and [figure semantics](figures.md).

## Remaining acceptance

- **M4:** user-provided original images in a separately approved private environment; field/sample-separated tuning and evaluation; corrected-mask reference measurements, legacy reconciliation and measured detection quality. Provisional detection targets remain unconfirmed for the user's experiment.
- **M5:** operator acceptance on the intended research machine and researcher evaluation of completion, correction time, understanding of independent units and reuse demand. Automated browser checks do not replace participant evaluation.
- **Future cloud service:** private storage and ownership, actual TLS/domain/session behavior, continuous deletion while clients are offline, durable recovery and host-enforced worker isolation. No hosted private backend is claimed here.

Native automatic nuclear detection currently requires both image sides at most 2048 px and at most 2,700,000 pixels under the standard-2g profile; excess inputs are rejected without silently resizing measurement pixels. NCL-defined nucleolar candidates need biological review because NCL redistribution can change the segmented region.

Local work expires 24 hours after explicit activity. Physical cleanup while the launcher or PC is off resumes at the next launch. Native Windows execution trusts the OS user and does not install an OS-enforced worker egress block. Read [local operation](local.md), [data protection](security.md) and the [roadmap](roadmap.md) before using private images. Private research material does not belong in GitHub issues or public verification artifacts.
