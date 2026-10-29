# Windows 0.1.0-local.20 — acceptance record

The [release](https://github.com/genellect/cytellect/releases/tag/v0.1.0-local.20) is the first Windows package with the redesigned two-group comparison: the researcher chooses one or two screens first, enters groups and independent experimental runs, and reaches a result sentence, a figure with the run as n, and Methods. It also matches the public demo's workspace screens and records manual contour corrections in Methods. Private analysis uses the installed local API; Cellpose inference still needs an administrator-provided cloud GPU.

## Identity and acceptance

| Item | Verified value |
|---|---|
| Source | `6792628245cf3def7c7ddf84a6434cc739ef1068` |
| Archive | `Cytellect-0.1.0-local.20-windows-x64.zip` |
| Bytes | 10,204,099 |
| SHA-256 | `bcbefa59857b29c4221603045266b167fb7019311d512f1c475fbaef0608525a` |
| Manifest payload entries | 283 |
| Numerical harness SHA-256 | `4b8644f1cfc6e35a8cfd92e41bb8321f3655c2e035e1552d20a101beb8dc7e21` |
| Exact-source main CI | [40721976880](https://github.com/genellect/cytellect/actions/runs/40721976880), all seven release-gating jobs passed |
| Installed acceptance | [40728459543](https://github.com/genellect/cytellect/actions/runs/40728459543) |
| Fresh and repeat setup | Passed with pinned Python and actual Fiji |
| Workspace retention | Fresh setup recorded `manual`; the running application reported `retention_mode: manual` |
| Installed browser | 27 passed; 0 failed, skipped or flaky |
| Two-group comparison (goals C1, C11) | Passed on the installed copy: 120 registered public JUMP Cell Painting images (2 groups × 3 runs × 5 fields × 4 channels, CC0) through installed Fiji to statistics, figure and Methods |
| Numerical replay and launcher shutdown | Passed |

The draft archive was downloaded before publication: its SHA-256 and size matched the acceptance receipt and the `.sha256` file, the manifest named the exact source and version, and every one of the 283 payload hashes and sizes matched the archive.

## Delivered behavior

Changes since the published local.19 (`145df38e`):

- **Two-group comparison** (#110): the first screen asks for one or two screens. Two screens show the two groups of the same experimental run side by side with the same display transform and scale. Groups, runs and samples are entered without returning to the per-field table, missing combinations are reported, and the result sentence, the default figure (each run as a point, n = runs) and Methods come from the saved statistics. Nuclei whose nucleoli cannot be resolved are kept as missing values instead of being removed (`unresolved-as-missing/1.0.0`).
- **Workspace consistent with the public demo** (#127): images added before the form is chosen wait for that choice; the settings panel starts closed; files and folders can be dropped; composite display and the adopted nuclear outline are shown as in the demo. Rejected images are listed by name and reason, are not resent, and can be excluded with a recorded reason.
- **Methods and figures record manual corrections** (#130): the number of manually corrected regions and the researcher's field names appear in Methods, figure captions and the statistics table; region names in figures are English.
- **OME-TIFF from Fiji (Bio-Formats)** is registered as OME-TIFF (#131). Applying an analysis proposal without a metric no longer breaks the screen (#124).
- The cloud GPU server keeps an in-flight inference running while its container drains (#126). This is a server change; the package itself is unchanged by it.
- Input pixels are never modified. Measurement equations, statistics and figure calculations other than the additions above are unchanged.

## Evidence limits

The installed workflow uses registered public microscopy for Fiji integration and existing deterministic numerical fixtures for arithmetic and transport. The two-group comparison checks the workflow and the direction of the descriptive result, not detection accuracy or biological validity. Private images, results and credentials are not in Git or CI.

Real-GPU speed, agreement with the CPU and cost are not yet measured for this release: on 2026-10-28 the deployed GPU server did not start a container during acceptance. Automated acceptance does not establish setup-screen layout on a physical PC, behaviour under Smart App Control, biological segmentation accuracy, or researcher usability (goals C9 and C10). Earlier immutable releases retain their original evidence.
