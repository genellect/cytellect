# Windows 0.1.0-local.19 — acceptance record

The [release](https://github.com/genellect/cytellect/releases/tag/v0.1.0-local.19) keeps workspaces until explicit deletion by default, can send Cellpose inference to an administrator-provided cloud GPU, and carries the current dependency security updates. Private analysis uses the installed local API and pinned Fiji; Vercel publication does not provide a hosted private-image backend.

## Identity and acceptance

| Item | Verified value |
|---|---|
| Source | `145df38e5be1e7be8215d6a7a18fa9b9dcb8870f` |
| Archive | `Cytellect-0.1.0-local.19-windows-x64.zip` |
| Bytes | 14,652,167 |
| SHA-256 | `0e4d34553d32cb3a26ce50d369cf8a325302154cee529c95b7054d1140bb5c4a` |
| Manifest payload entries | 285 |
| Numerical harness SHA-256 | `4b8644f1cfc6e35a8cfd92e41bb8321f3655c2e035e1552d20a101beb8dc7e21` |
| Exact-source main CI | [39904832383](https://github.com/genellect/cytellect/actions/runs/39904832383), all required jobs passed |
| Installed acceptance | [39908946391](https://github.com/genellect/cytellect/actions/runs/39908946391) |
| Fresh and repeat setup | Passed with pinned Python and actual Fiji |
| Workspace retention | Fresh setup recorded `manual`; the running application reported `retention_mode: manual` |
| Installed browser | 26 passed; 0 failed, skipped or flaky |
| Numerical replay and launcher shutdown | Passed |

The draft archive was downloaded before publication: its SHA-256 and size matched the acceptance receipt and the published `.sha256` file, the manifest named the exact source and version, and every one of the 285 payload hashes and sizes matched the archive. The owner published the release as a prerelease on 2026-10-23 (06:51 UTC). After publication the archive downloaded without authentication matched SHA-256 `0e4d34553d32cb3a26ce50d369cf8a325302154cee529c95b7054d1140bb5c4a` and 14,652,167 bytes. The LP download metadata is updated separately through PR, required CI, main and automatic Vercel deployment.

## Delivered behavior

- Workspaces are kept until explicit deletion by default (#69). Setup offers 24-hour deletion instead; once a data directory has kept work, it cannot return to 24-hour deletion, and setup recognises the application's permanent marker even if its settings file was lost. Updating a local.17 installation switches it to manual retention; workspaces already past their deadline at the switch are deleted, not revived.
- Setup accepts a cloud GPU endpoint and key for Cellpose (#71, #72). Only the detection plane, adopted nuclear labels for nucleolar protocols and detector parameters are sent; results are accepted only when the remote runner, model and package hashes match this release. No endpoint is provided yet, so Cellpose remains unavailable on Windows, as in local.17. The CPU Cellpose runtime is not installed.
- Updates remove this installation's earlier versioned shortcuts after the new version is ready; Fiji and model downloads retry transient failures (#72).
- Pillow, certifi, Next.js 16.4.2 and opentelemetry-api 1.45.1 clear the dependency audit findings (#70, #73).
- Input pixels, detection, measurement, statistics and figure calculations are unchanged.

## Failed attempt and correction

[39899291693](https://github.com/genellect/cytellect/actions/runs/39899291693) was not published and created no tag or release. Six of the 26 installed browser cases failed because the tests assumed 24-hour retention: they looked for the expiry label in the workspace list and opened the database in 24-hour mode, which the application refuses once manual retention is recorded. PR #77 made the tests follow the data directory's recorded mode and added explicit acceptance checks that the installed copy runs with manual retention, so a regression of the default cannot pass. No application, detector, measurement or statistical code was changed for this correction.

## Evidence limits

The installed workflow uses registered public microscopy for Fiji integration and existing deterministic numerical fixtures for arithmetic and transport. These fixtures are not biological accuracy evidence. Private images, results and credentials are not in Git or CI.

Remote Cellpose was verified only against the CPU service in CI (identical labels); real-GPU speed, agreement and cost are not yet measured. Automated acceptance does not establish setup-screen layout on a physical PC, biological segmentation F1, independent researcher usability, or a hosted private-analysis service. Earlier immutable releases retain their original evidence.
