# Windows 0.1.0-local.17 — acceptance record

The [release](https://github.com/genellect/cytellect/releases/tag/v0.1.0-local.17) contains the connected image, statistics and graph workspace. The published archive was downloaded without authentication and matched the accepted artifact. Private analysis uses the installed local API and pinned Fiji; Vercel publication does not provide a hosted private-image backend.

## Identity and acceptance

| Item | Verified value |
|---|---|
| Source | `021081271803b80a5c92563ec253ce0d8b644081` |
| Archive | `Cytellect-0.1.0-local.17-windows-x64.zip` |
| Bytes | 14,109,111 |
| SHA-256 | `1532f1e0b32eb7f9f457f82b6a9847e85c9a919a178c766b27f835cdcc0df51c` |
| Manifest payload entries | 270 |
| Numerical harness SHA-256 | `4b8644f1cfc6e35a8cfd92e41bb8321f3655c2e035e1552d20a101beb8dc7e21` |
| Exact-source main CI | [37689312905](https://github.com/genellect/cytellect/actions/runs/37689312905), all five required jobs passed |
| Installed acceptance | [37694037264](https://github.com/genellect/cytellect/actions/runs/37694037264) |
| Fresh and repeat setup | Passed with pinned Python and actual Fiji |
| Installed browser | 26 passed; 0 failed, skipped or flaky |
| Numerical replay and launcher shutdown | Passed |

The archive manifest, every payload size and hash, exact source, acceptance receipt and harness hash were verified before publication. The LP download metadata is updated separately through PR, required CI, main and automatic Vercel deployment.

## Delivered behavior

- One workspace preserves stain roles, adopted masks, measurement selection and source references across images, statistics and figures.
- Manual nuclear/nucleolar/cell-ROI edits, server-side adoption and Undo/Redo share the saved revision; GFP selection uses nuclei or explicit cell ROIs.
- AI uses the common structured settings and selected-field preview. Upload, navigation and editing do not call the paid service. The existing monthly USD5 limit is unchanged.
- Figure editing preserves saved numerical results. Saving includes vector figures, source tables, conditions and reproducibility records; originals are included only when explicitly selected.
- New and restored workspace IDs persist in the URL without resetting live candidates. Creating a new workspace removes the previous ID.
- Repeat installation reuses compatible pinned runtimes; application updates do not download Fiji again solely because the UI changed.

## Failed attempts and corrections

[37664139870](https://github.com/genellect/cytellect/actions/runs/37664139870) was not published: the new workspace ID was absent from the URL and the comparison test requested a null destination. PR47 fixed URL binding, restored-workspace selection and reset behavior.

[37680659866](https://github.com/genellect/cytellect/actions/runs/37680659866) was not published: the test expected internal `welch-t` as visible text, although the successful saved comparison displays `Welch t-test`. PR48 checks both the visible name and stored method. Its comparison-only replay also checks only the results requested, rather than requiring an unrequested association. The separate numerical harness continues to require both comparisons and associations. No detector, measurement equation or statistical method was changed for these corrections.

The first exact-main Python attempt timed out while the Azure Ubuntu package mirror was unreachable, before scientific tests began. Only that job was rerun after the failure was identified; the four passing jobs were retained. The retry passed 1,682 Python cases (142 platform/configuration skips; 20 Fiji cases run separately). Windows Python3.14 passed 1,815 cases (9 skips; 20 Fiji cases separate). The Fiji/browser job passed 20 Fiji cases and 56 browser cases; configuration-specific skips are not counted as passes.

## Evidence limits

The installed workflow uses registered public microscopy for Fiji integration and existing deterministic numerical fixtures for arithmetic and transport. These fixtures are not biological accuracy evidence. Separate private-image Edge checks cover source pixels, adopted masks, editing, GFP object selection, figures and replay; private images, results and credentials are not in Git or CI.

Automated acceptance does not establish biological segmentation F1, ownership decisions for ambiguous nucleoli, independent researcher usability, or a hosted private-analysis service. M4/M5 evaluations remain separate. Earlier immutable releases retain their original evidence.
