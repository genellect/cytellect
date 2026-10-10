# NCL 4.3.0 deployment checkpoint, 2026-10-09

The owner resumed delivery on 2026-10-10. The accepted detector and scientific
settings are fixed; resumption is delivery verification, not another detector
redesign. The following checkpoint retains the state of the 2026-10-09 pause.

## Resumption

The immutable ZIP hash was rechecked and is unchanged. The intervening main
update (#52) changes the landing page only; its changes were preserved. The
short-location ordinary Windows setup resumed and completed with the exact
bundled script. Optional model/package provisioning completed, but Windows
application control rejected the dependency `fill_voids.cp312-win_amd64.pyd`
during its final import check. The isolated reproduction and Code Integrity
event 3077 identify the same DLL. The remaining optional-runtime gates and public
asset are blocked; no later gate is counted as passed. The existing native
package and tag remain immutable. See the updated
[acceptance record](local-release-0.1.0-local.18.md).

Docker Desktop failed to start because of stale IPC sockets. Only its stopped
temporary socket directories were retired before restarting Desktop. The existing
Web/API/worker containers resumed, the loopback Web returned HTTP 200, and the
research volume and offline scientific worker were retained. No factory reset,
data-volume deletion or OS-policy change was performed. Edge opened the local
workspace.

## Completed delivery at the original pause

- PR50 and PR53 are merged. Scientific code was tested at
  `7aa3cb7201cf651447a5457cf7a9b26032becf91`; the delivery source is
  `e28fec581ebecacd0265a6e97c05c9ed8103b332`, with all five main CI checks passed
  in run `37909113488`.
- Docker API/worker use the tested scientific source. Web includes intake repair
  `11e13b0acda590390c7544f4c9f6168297b02fe2`, matching delivery application source.
  The existing research volume, offline worker and loopback bindings are retained.
- Canonical Vercel deployment `dpl_G3335ZEx4aBgUwpt8sPTPCQm4qZ6` is READY at the
  delivery source. Scientific image execution remains local, not hosted on Vercel.
- Dedicated production proposal Worker version
  `951ec487-55a7-4698-a5f8-dedc799c7c7c` uses prompt `2026-10-09.1`, supports the
  accepted 4.3.0 contract and preserves the monthly USD 5 budget.
- The reviewed private real-image partition and immutable-original measurement
  path passed package/Docker checks. Private specimens and results stay outside
  Git/CI; reproduction is not general biological accuracy evidence.

## Windows delivery: verified draft, not published

Run `37911671684` passed fresh/repeat ordinary setup, 26 installed browser cases
with zero failures/skips/flakes, independent numerical replay and launcher
shutdown. The `v0.1.0-local.18` tag points exactly to the delivery source.

The ZIP is `Cytellect-0.1.0-local.18-windows-x64.zip`, 14,544,843 bytes, SHA-256
`a1a5315193f9536de06b1b8007a2ef71e1ea9fdf6ac6810f1eb4a8afc0725048`.
All 280 manifest payload hashes and sizes, source/tag, acceptance receipt and
numerical harness hash were independently verified. The release remains a draft;
public download metadata remains local.17.

The first PC validation location was too deep for an atomic Python extraction
temporary filename under Windows PowerShell 5.1. Its concrete exception, valid
launcher signatures and retained failure are recorded in
[the acceptance record](local-release-0.1.0-local.18.md). The identical archive
was verified/extracted in a shorter dedicated location. Python runtime extraction
passed there; ordinary setup was stopped in `install_dependencies` at the owner's
pause request, before optional-runtime acceptance.
Task-owned setup/child processes have stopped; caches and partial files remain.
Docker, existing research data, credentials and OS policies were not changed.

The original and short-location local acceptance drivers/checkpoints are retained
in task-private storage on this PC. They are intentionally not published, because
their input references and resulting evidence include private research material.

## Original resume procedure and current gate

Step 1 completed on 2026-10-10. Step 2 failed at the actual Windows import gate.
Do not repeat it unchanged, weaken OS protections, or publish the pending package.
A Windows compatibility change must preserve the accepted detector/model/conditions
and pass full-region real-image verification in a new immutable release. The owner
has been asked whether to continue that separate compatibility/release work or
use the already running Docker delivery for the current operational boundary.

The original verification order remains below for traceability.

1. Verify the preserved ZIP/source/hashes and task-owned process state. Continue
   ordinary setup at the short dedicated location using the exact ZIP's script;
   retain cached validated downloads and partial installation rather than deleting
   them. Record successful setup before starting optional work.
2. Run the exact installed archive's optional Cellpose setup with the existing
   signed official Python 3.12. Verify lock/model/runner hashes and installed module
   identity; no source-checkout imports, OS-policy weakening or runtime downloads
   during image jobs.
3. Use the same supplied private paired originals, saved adopted StarDist parent
   mask and researcher-reviewed expected partition in the preserved local harness.
   Verify complete regions, original-pixel measurements and parent/review states.
   Do not redetect/tune nuclei, regenerate expected labels, substitute synthetic
   images, or publish private evidence.
4. Check repeat setup reuses the fixed runtime/model and check the owned local
   launcher starts/stops. These gates are currently unstarted, not passed.
5. After all gates pass, publish local.18, download the public asset without
   authentication and verify its exact size/hash/manifest. Only then update
   `apps/web/src/lib/published-release.json`, README/local guidance and acceptance
   records through PR, required CI, main and canonical Vercel verification.
6. Keep the archive's source as `e28fec581ebecacd0265a6e97c05c9ed8103b332` even if
   documentation/download metadata later has a different main commit. Do not
   overwrite the existing tag or silently replace an immutable archive.

No additional paid API evaluation is needed for this checkpoint. No new keys,
scope changes, detector tuning, COMPASS edits or research-volume resets are part
of resumption.
