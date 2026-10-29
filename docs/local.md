# Local browser delivery

Status: Windows development preview. Each version is advertised only after its built package passes installation and browser checks; release notes record the accepted source and evidence. Local execution is an initial deployment option; the product remains a browser workspace with a future hosted backend.

The accepted [0.1.0-local.20 release](https://github.com/genellect/cytellect/releases/tag/v0.1.0-local.20) is available for Windows x86-64. It is the first package with the redesigned two-group comparison (one or two screens, groups and independent runs, a result sentence and a figure with the run as n), keeps workspaces until explicit deletion by default and sends Cellpose inference to an administrator-provided cloud GPU. See its [acceptance record](local-release-0.1.0-local.20.md) for the exact source, checksums, all 27 installed browser cases, numerical replay and evidence limits. The [local.19](local-release-0.1.0-local.19.md) and [local.17](local-release-0.1.0-local.17.md) records remain evidence for those packages. Start with the [public-image guide](quickstart.ja.md). The [local.11 record](archive/local-release-0.1.0.md) remains historical evidence for that immutable package.

## Researcher flow

Source after 0.1.0-local.20 builds two deliverables from the same accepted ZIP: the per-user installer `Cytellect-Setup-<version>.exe` (stage 1, requirements I1–I8 of the Windows access plan under owner review) and the setup ZIP, which stays available until the owner retires it. No released version contains the installer yet.

1. Download `Cytellect-Setup-<version>.exe` and open it. It installs for the current user only (`PrivilegesRequired=lowest`) into `%LOCALAPPDATA%\Cytellect`; there is no administrator prompt, command, extraction or destination choice. Whether Windows warns before it runs depends on signing and reputation (owner decision D4, [application control](#windows-application-control)).
2. Before changing anything, the installer checks Windows 10 1809 or later / Windows 11 on x64, at least 8 GB of memory (7 GiB as reported after hardware reservations) and free space (4 GB plus the unpacked payload for a first installation, 1.5 GB plus the payload for an update that reuses Fiji and Python). A failed check shows the reason and the next action in Japanese and exits without changes. A destination that holds files without Cytellect's ownership marker is also refused unchanged.
3. The installer unpacks its payload to its temporary folder and runs the same `local_setup.ps1` in offline mode. Python 3.14, the hash-locked wheels, uv and Fiji with its plugins are bundled; setup copies them only after checking each file against `offline/offline-manifest.json`, which is bound to the release manifest. Nothing is downloaded on the PC; a missing or altered file stops setup (`offline_artifact_missing`, `offline_hash_mismatch`). Cellpose is not installed on the PC; an existing cloud GPU setting is kept ([cloud GPU](cloud-gpu.ja.md)).
4. On success the workspace opens in the browser, and Desktop and Start menu shortcuts named **Cytellect** exist. The launcher window shows 「起動の準備中」 and then 「作業画面を開いています」, and its 「作業画面を開く」 button reopens the browser. A port in use or a failed start shows the reason with 「再試行」. Opening Cytellect while it already runs opens the running workspace instead of a second copy (I5).
5. Running the installer again is safe: verified files are reused, and an interrupted installation (closed, killed or powered off) finishes on the next run. Windows **Settings → Apps** lists Cytellect for uninstallation. The uninstaller refuses while the launcher runs and asks before deleting research data; by default `data/` and `settings/` stay and a later installation keeps them.
6. Import images, review masks, quantify, compare and export through the browser. Close the launcher to stop the local service and its worker. Closing only the browser tab does not stop the launcher.

With the ZIP, the researcher extracts it and opens **Cytellect Setup.cmd** instead; setup then downloads the same pinned Python, packages and Fiji. The ZIP's setup window is also, for now, where an administrator-provided cloud GPU address and key are entered. The researcher-facing steps are in [install-windows.ja.md](install-windows.ja.md).

Windows x86-64 is the first installation target. Other operating systems retain the developer/Compose setup until their installation paths are tested. The runtime may consume several gigabytes of disk; the tested installer reports its completed footprint separately from the download.

### In-app update

The local API offers `GET /v1/app/update` and `POST /v1/app/update` to the signed-in local session only; the routes are not registered in a hosted API and are not part of the published OpenAPI contract. `GET` returns `current`, `latest`, `available` and `notes_url`, plus `state` (`idle`, `downloading`, `installing`, `restarting`, `updated`, `installed`, `failed`, `rolled_back`, or `unsupported` outside an installed copy) and a fixed `error` code. `notes_url` is only ever a page under `https://github.com/genellect/cytellect/releases/`. It reads GitHub's public release list of `genellect/cytellect` at most every six hours (15 minutes after a failed check), sends no research data or identifiers, and answers offline with the last known result. A release is offered only when it is published, is newer than the running `X.Y.Z-local.N`, and carries `Cytellect-Setup-<version>.exe` with its `.sha256` file; GitHub's own asset digest, when present, must agree.

`POST` returns 202 and works in the background. It is refused with 409 `update_jobs_running` while an analysis is queued or running, because the switch stops the worker. It downloads the installer from GitHub's release hosts only, checks the published SHA-256 again immediately before running it, and runs it silently into the same folder. The installer prepares the new version beside the current one and passes all of setup's checks before the shortcuts change. If any of this fails, the current version keeps running (`failed`); the downloaded installer and partial files are removed, and a hung installer is stopped with its children after an hour. If an analysis started while the installer ran and does not finish within ten minutes, the switch waits for the next start instead (`installed`, `update_jobs_running`): the shortcut already opens the new version, which reports `updated` when it starts. From the last check for analyses until the launcher stops, other changing requests are refused with 409 `update_switching`, so no analysis can start and then be stopped. Otherwise the launcher stops and a relauncher, run with the previous version's interpreter, copies `data/cytellect.sqlite` with SQLite's backup API, starts the new version and waits up to five minutes for it to answer `/v1/local/setup` with its own version. If it does not, the relauncher stops it, restores the database copy and the previous shortcuts, and starts the previous version (`rolled_back`, `update_new_version_failed_to_start`). Every failure path still restores the shortcuts and ends with the previous version running. The relauncher waits for the stopped new version to exit and tries the restore five times; if the file stays locked, it writes `updates/rollback/pending.json`, and the previous version restores the copy at its next start, after taking its runtime lock and before opening (and migrating) the database. A start that still cannot restore it stops with the ordinary start failure instead of opening the newer database. A previous launcher that does not exit within ten minutes of its stop request is stopped and started again (`update_previous_did_not_exit`). A copy that could not be restored stays in `updates/rollback/`; otherwise none is kept. Image files are not copied. The trust in a release is described in [data protection](security.md#windows-local-mode).

The workspace banner that calls these routes ("更新があります") and the first-run screen are part of the cloud-account change (genellect/cytellect#156), and the two ship together. The banner shows each `state` above, including `installed`, `failed` and `rolled_back`, and the 409 `update_jobs_running`.

The `windows-installer` job tests the update end to end with two versions built from the same commit: a generated release list on `127.0.0.1` is offered, downloaded, verified, installed and switched to, and a second run whose new version exits at start returns to the previous version with its workspace. The redirection to the local list and the failing start come from `packaging/windows/update-test/cytellect_ci_update_hook.py`, which the test copies with a one-line `.pth` file into the previous version's site-packages. It is not in the ZIP or the installer (a test checks that nothing under `packaging/` is), so a distributed copy always reads GitHub's releases.

The shortcut, the relauncher's commands and the worker run Python with `-E`, so a researcher's own `PYTHONPATH`, `PYTHONHOME` or other `PYTHON*` variables cannot change the installed application. Cytellect needs none of them; bytecode is disabled with `-B` and the worker inherits both flags.

### Application updates and storage

Use the same installation destination for updates. The default is
`%LOCALAPPDATA%/Cytellect`; a different destination creates a separate installation.
Application versions have separate source/virtual-environment directories, but
share the pinned Fiji runtime when its lock is unchanged and the Python runtime
when its composition is unchanged. Updating the application alone does not
download another Fiji. Initial setup and changed dependencies can require network
access; analysis jobs never install dependencies.

The update-storage source increment records successfully checked installations
and retains the current and previous successful application. Only older,
recorded, byte-identical trees are eligible for removal after the replacement's
Python GUI and Fiji numerical launch checks succeed. A new setup failure before
that point leaves previous generations intact. The setup window reports retained
application count and reclaimed bytes. Research data under `data/` is never part
of this collection.

Running versions, modified files, unknown/incomplete directories and any reparse
point are preserved. Setup is serialized; managed launches and collection share
an OS-released installation lock. A native Windows process-SID inventory checks
user processes and executable interpreter candidates; an unreadable relevant
process disables collection. The retained applications keep their referenced
Fiji/Python/bootstrap runtimes. Only newly installer-created runtime trees enter
the ownership ledger; existing unregistered installations are never assumed to
be disposable. Unknown installations prevent shared-runtime collection because
their references cannot be established.

New package installations disable persistent uv caching. Known downloaded
Python/uv ZIPs are retained only while a retained app refers to them; their
recorded hash must still match before removal. Old unregistered caches, modified
archives and incomplete transfers are left in place and reported. This is a
bounded policy for managed successful updates, not permission to delete arbitrary
old files. The stable `Cytellect` shortcut is updated only if it belongs to this
installation. Historical version-specific shortcuts are not silently adopted.
New links are staged before replacement; a later setup failure restores the
prior link if it still matches this setup's write. Initial app ownership requires
the release manifest and installed wheel RECORD files; unrelated files are not
adopted by taking a whole-folder snapshot. Collection journals removal intent
before deleting and can recover a verified partially removed tree after interruption.

The collector's scratch-directory tests include three different application
versions, a failed third setup, one shared Fiji acquisition, active/modified and
unknown trees, junction rejection, referenced runtimes and archive ownership.
Those controlled-download tests do not replace actual installed-release checks.
The immutable published versions retain their original storage behavior.

### Windows application control

An observed local setup attempt was blocked by Windows Smart App Control
(`VerifiedAndReputableDesktop`, error 4551). Code Integrity events identified an
unsigned Python virtual-environment launcher created by the pinned `uv`, not
`uv` itself or the managed base interpreter. The dependency stage did not
complete and no accepted installation was recorded. This is separate from
installation on GitHub's Windows runner; successful CI cannot establish that a
laboratory's application-control policy permits the package.

Do not disable application control, unblock or relocate executables to work
around this result. Keep the failure state and ask the workstation administrator
to review the distribution under the laboratory's software policy. A signed,
policy-compatible Windows distribution is not currently provided. These events
identify a policy rejection, not a finding of malware or its cloud-reputation
cause.
See [Microsoft's policy and event-log definitions](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/test-your-app-with-smart-app-control#checking-event-logs).

The installer does not by itself satisfy requirement I1. It is unsigned unless the
owner provides a certificate (D4), and it still installs third-party wheels whose
native libraries are not all signed. Whether SmartScreen and Smart App Control allow
it can only be learned on real laboratory PCs.

### Real-machine checklist (stage 0, acceptance E1)

Record each item per PC (Windows edition and build, Smart App Control state from
Windows Security → App & browser control, signed or unsigned installer, result).
Change no security setting, and do not unblock or move files.

1. Download `Cytellect-Setup-<version>.exe` in Edge from the release page. Note any
   download warning and its exact wording.
2. Open it from the Downloads folder. Note whether a SmartScreen or Smart App
   Control dialog appears and whether the dialog offers a way to continue.
3. If it runs: install with one click, time it, and confirm that the browser opens
   the workspace and that Desktop and Start menu shortcuts exist.
4. Open the BBBC013 practice ZIP from the [public-image guide](quickstart.ja.md) and
   detect nuclei in one field.
5. Close the launcher, open **Cytellect** from the Start menu, and confirm the
   workspace returns. Run the installer again and confirm it finishes.
6. Note whether PowerShell runs in ConstrainedLanguage mode (`$ExecutionContext.SessionState.LanguageMode` in a PowerShell window) and whether Smart App Control or WDAC allows the unsigned `.ps1` scripts that the installer unpacks and the unsigned native libraries (`.pyd`, `.dll`) of the bundled wheels. A block here appears as an installer failure or as a launcher that does not start.
7. If anything is blocked: export the Code Integrity events (Event Viewer →
   Applications and Services Logs → Microsoft → Windows → CodeIntegrity →
   Operational, events 3033, 3034, 3076, 3077 and 3089) and record which file was
   blocked, without research file names or paths in shared reports.
8. Uninstall from Settings → Apps, choose to keep data, and confirm that `data/`
   remains under `%LOCALAPPDATA%\Cytellect`.

Compare the signed, unsigned and Microsoft Store candidates on the same PCs before
the owner chooses the distribution (D4). Passing CI on GitHub's runner is not this
evidence.

## What stays the same

The Web components call the same versioned API contracts. Local delivery adds a same-origin static Web build and explicit loopback startup; it does not fork segmentation, measurements, statistics, masks or exports. Standard Vercel builds retain the public sample viewer and never connect to localhost implicitly.

The local launcher uses the same pinned Fiji/Java/model and Python lockfiles. Installation downloads are separate from analysis. The worker must not fetch dependencies/models during a job. A later cloud deployment can replace database, file storage and dispatch adapters without changing scientific definitions or the browser editing workflow.

The Windows launcher does not install a firewall rule or inherit Compose's `network_mode: none`. Its worker is not isolated from the network at the operating-system level. The application accepts only registered recipes, verifies installed plugin/model hashes and invokes fixed local Java/Python entry points; it does not accept submitted code, model URLs or remote image URLs. Browser same-origin checks and a no-external-request browser test are separate evidence from OS-level egress denial. The offline Linux container remains the verified egress-isolated deployment option.

## Local security and retention

This is a single-OS-user application, not isolation between multiple people who share one operating-system account. Other processes with local loopback access are inside its trust boundary. Protect the OS account and data directory accordingly. It is not a LAN or public server.

The service binds only `127.0.0.1`, normally port8765. It validates the literal Host and Origin, rejects cross-site browser requests and forwarded host headers, and prevents framing. It does not trust DNS aliases or bind to `0.0.0.0`. A local-only same-origin POST establishes an HttpOnly, SameSite=Strict session; tokens are not placed in URLs, browser storage or logs. Cloud-mode applications do not expose this bootstrap endpoint.

Originals and derived files remain in the chosen private runtime directory, outside the source checkout and installation files. Explicit user activity controls the24-hour expiry; polling does not renew it. Access to expired work is denied. While the launcher is open, the worker performs physical cleanup; if it is closed or the PC is off, physical deletion resumes at the next launch. This limitation is disclosed before upload. Local installation does not provide remote deletion of a powered-off disk.

Closing the launcher stops computation and revokes its local-owner sessions. A subsequent launch can reopen that owner's unexpired work. Cleanup, stop/restart, quota and partial-job behavior must be verified on the installed copy, not only the development environment.

Windows virtual environments may run a redirector executable and a separate Python interpreter. The interpreter watches that redirector's PID and creation time; losing it stops the local server. The worker reports its actual process identity over a private pipe, so stopping or retrying a worker also terminates its interpreter, not just its redirector. Ordinary setup shells are not lifetime owners and may exit after opening Cytellect. Tests cover abrupt redirector termination and bounded worker recovery with a real Windows stdlib virtual environment.

Worker identity and parent monitoring start before scientific-library initialization. The15-second process handshake does not impose a15-second limit on cold font or scientific imports; jobs stay queued until initialization finishes. Matplotlib configuration and font caches use the private runtime temporary directory. Parent disappearance during initialization still stops the worker, and ordinary job/Fiji shutdown retains its supervised termination behavior.

## Build and installation evidence

Developers build a local-only Web export with `pnpm --filter @cytellect/web build:local`. For a reviewed clean commit, run:

```sh
uv sync --locked --group build
uv run --no-sync python -m hatchling build -t wheel -d /absolute/outside/checkout/wheels
uv export --locked --no-dev --no-emit-project --no-header --output-file /absolute/outside/checkout/requirements.txt
python scripts/build_local_bundle.py --version 0.1.0-local.12 --output /absolute/outside/checkout/Cytellect-0.1.0-local.12-windows-x64.zip --runtime-data /absolute/outside/checkout/windows-tcltk-9.0.4-data.zip --wheel /absolute/outside/checkout/wheels/cytellect-0.1.0-py3-none-any.whl --requirements /absolute/outside/checkout/requirements.txt
```

The required runtime data ZIP is prepared on a Windows builder by `scripts/prepare_windows_runtime_data.ps1`, with an explicit Python, cache, fresh scratch directory and exclusive output path. It uses the fixed official MSI in administrative extraction mode and verifies the fixed PSF inputs; it does not install MSI components on the researcher's computer. The release workflow contains the complete invocation. See [runtime composition and notices](windows-runtime.md).

The builder rebuilds the Web export and packages tracked allowlisted source files, static output, a normally built source-matched wheel, hash-preserving production requirements and the exact reviewed data-only Tcl/Tk asset. Every entry receives a SHA-256 in `local-release.json`; the archive receives a separate checksum. Redistribution-cleared public demo derivatives, their attribution and hash allowlist are included. No `.env`, database, virtualenv, unpublished research image, private study input, runtime output or developer cache belongs in this package. The installation bootstrap verifies this manifest before copying files. The consumer creates a signed standard-library virtual environment and installs wheels by hash; it does not run an editable project build or download an isolated build interpreter.

The installer is built on a Windows builder from that ZIP:

```sh
python scripts/build_windows_installer.py install-inno --dest /outside/inno --cache /outside/cache
python scripts/build_windows_installer.py build --release-zip /outside/Cytellect-<version>-windows-x64.zip --output-dir /outside/installer --work-dir /outside/work --cache /outside/cache --iscc /outside/inno/ISCC.exe --pip-python <python with pip>
```

The builder accepts the ZIP only when its `.sha256` file and every manifest entry match, reads the uv, Python and Fiji pins from the release itself, downloads them into a content-addressed cache and keeps only copies whose digest matches. `pip download --require-hashes` fetches the CPython 3.14 Windows wheels of the locked requirements; the builder then requires exactly one Windows-compatible wheel per requirement, with a hash listed in the lock. It scans the payload for OpenAI keys, Modal tokens, GitHub tokens, private keys and setting files that hold credentials, reporting rule counts only, and refuses a payload above 1.9 GiB. Inno Setup 6.7.4 is installed for the current user from its pinned SHA-256. The outputs are the installer, its `.sha256` file and a receipt (`Cytellect-Setup-<version>.json`) with the source, both checksums, the bundled counts and `signed`.

Code signing is a hook pending the owner's decision (D4). `--sign-command "<signing command with $f>"` (or `CYTELLECT_SIGN_COMMAND`) is passed to Inno Setup's `SignTool`, which signs the installer and its uninstaller; without it nothing is signed and the receipt records `"signed": false`. No certificate or secret exists in this repository or its workflows.

Installation tests use an isolated directory under the task's scratch workspace. They must not overwrite a user's existing software, data or shortcuts. The `windows-installer` CI job (`packaging/windows/smoke.ps1`; on `main` and manual runs, like `windows-installed`) builds the installer and, with a dead proxy so that any download would fail, checks: refusal of a foreign destination without changes, a fresh silent installation with shortcuts and the Windows Apps entry, no credential-shaped content in the installed folder, start, session, workspace and an offline update status, uninstall refusal while running, re-runs while running and after stopping, uninstall that keeps data and a reinstall that keeps the workspace, uninstall with data deletion, an installation killed at the dependency stage that the next run completes, and migration of a published 0.1.0-local.20 ZIP installation with its workspace. It does not show a dialog to a person, so the Japanese messages, the browser opening and SmartScreen behavior remain real-machine checks. Acceptance includes an actual pinned-Fiji run, a browser upload/edit/export flow, hostile-origin denial, shutdown, restart and expiry. The release report records commit, archive checksum, platform, passed checks and known limitations. Publishing a ZIP is not evidence that installation succeeded.

The **Prepare Windows release** workflow is dispatched against `main` with a unique `0.1.0-local.N` version. It requires successful Python, Web, Fiji/browser, Windows lifecycle, ZIP installation, installer and full Windows Python3.14 compatibility checks on that exact commit, builds an immutable bundle and the installer from it, and performs fresh and repeat silent installation with the installer, without network access. For a release including area-only measurements, display receipts, paginated figures and native recipe guidance, all twenty-seven browser cases must pass against that installed copy: the published GFP path, imported/manual generic regions, one/two-channel nuclear detection with correction and batch reuse, declared independent/paired comparisons with ZIP replay, planning adoption into actual image/metric choices and a descriptive figure, strict saved-plan import, batch-registration recovery after a lost success response, historical source/mask review, shared registration metadata, saved unit/sample/field hierarchy, area-only revision/export/replay, calibrated-area comparisons, planning2.1 adoption, two exact preview/range workflows, paginated figure recovery and two native recipe/channel guidance workflows saved field-quality navigation and two protected-input/stable-field workflows, plus common-statistics and association figures with edited SVG/PDF downloads. A skipped, failed or flaky case blocks the draft. The tests use the local session and the installed interpreter, with an explicit same-origin loopback API and separate private data directory. They do not create invitations or fall back to developer Python.

The fourteen required specifications contain one local-package case, two generic-region cases, three nuclear/comparison cases, three planning/batch-registration cases and one case each for source review, shared metadata and comparison hierarchy, three area-only cases, two display cases, one paginated-output case two native recipe/channel cases one field-quality case and two draft-navigation cases, plus one complete common-statistics case covering multi-group parametric/rank tests, paired Wilcoxon, Pearson/Spearman, distribution variants, vector exports and source CSV downloads. The integrated workspace additionally verifies registered BBBC007 originals through installed Fiji, a saved independent-unit comparison through graph editing and replay, and the two-screen comparison of two groups over three runs of registered public JUMP Cell Painting images (goals C1, which makes the installed run the C11 acceptance); it checks the workflow and the direction of the descriptive result, not detection accuracy. The planning/batch specification uses registered public BBBC013 DRAQ pixels; repeated images test filename mapping and idempotent retry only, without claiming another stain or biological replication. The workflow requires exactly twenty-seven completed cases and retains failures instead of accepting an incomplete subset.

The additional `scripts/verify_installed_regions.py` gate runs with the installed Python, checks the complete source manifest and imported module locations, and compares the running server's exported source identity. Its module-hash receipt explicitly includes planning, plan adoption and the planning API alongside measurement, detection, comparison and replay code. Four generated regions yield signed background-corrected values A=[−3,−1], B=[2,0]. Welch and paired effect, standard error, degrees of freedom, p-value and confidence interval are checked with elementary closed-form references independently of SciPy's t-test functions. The same installed harness checks exact Mann–Whitney U (p = 1/3) and perfect four-unit Spearman association (p = 1/12) against independent combinatorial references. It verifies editable SVG text and embedded PDF fonts, then downloads every figure source file, verifies ZIP hashes and remeasures explicit raw originals through the saved-mask replay. The generated values verify calculation and packaging, while published microscopy verifies the image/browser paths; neither supplies biological replication or validates a private study.

Only the ZIP/checksum and small, separate acceptance receipts become workflow artifacts. Receipts identify the exact source, archive and acceptance-script hashes, test counts, numerical checks, replay and clean stop. Raw browser reports, logs, session information, uploaded images, screenshots and generated workspaces are not CI artifacts. Any image of a figure that is reviewed separately must retain its own public/generated source and scope. A Japanese or mixed-script figure requires an installed font covering its literal labels; failure is retained and blocks acceptance, rather than replacing labels or silently dropping glyphs.

Passing these checks creates a **draft** GitHub prerelease; it does not automatically publish a download or certify private-image validity. Review actual installed/browser evidence and scientific limitations before publication. The local.11 release passed these gates on its recorded CI attempt; it does not retrospectively expand local.10's evidence. Existing versions must never be overwritten.

The current source distinguishes Windows application-control rejection (native
error4551, including a failed uv child launch) from an ordinary setup failure.
It emits only `windows_application_control_blocked`, displays a concise Japanese
explanation and stops repeated setup attempts in that window. Other failures and
cancellation retain the ordinary retry path. Synthetic Windows process tests
check classification and output redaction; they do not establish that a blocked
dependency can run. This correction is not part of the immutable local.11 package
and requires a separately accepted release. No OS protection is disabled.

## Later hosted execution

Preserve the browser workflow and shared analysis packages. Hosted deployment adds a suitable persistent database, private artifacts, durable dispatch and same-origin/domain routing, with access/retention checks on the actual host. Cloud spend controls must not stop required deletion jobs. See [costs and trade-offs](hosting-costs.ja.md), [deployment](deployment.md) and [remaining gates](roadmap.md).

## Workspace entry and Desktop acceptance (2026-10-06)

In local mode and with a loopback API, `/workspace` opens the single analysis
workspace. On the public site `/workspace` redirects to `/demo`, which runs the
same workspace serverless with registered public images and no image upload
([public demo](showcase.md)). On the public site `/` is the
landing page with downloads (`/product` redirects there); GA4 is limited to the
public pages listed in [security](security.md). Installations on the user's own
computer (the Windows package and Docker Desktop, whose analysis API is on a
loopback address) open the workspace at `/` as well, so their launchers are unchanged. The previous detailed
screen is retained at `/legacy` only in local mode or with a loopback API origin.
Public builds return 404 there, including future remote-API builds. An authenticated session is
required before the configured new workspace loads private data. Windows uses
its local-session exchange; Docker uses the existing one-use invitation exchange.

For Docker Desktop, run `scripts/docker-desktop.ps1 Start`. `Open` starts the
existing installation and opens `http://127.0.0.1:3087/`; `Stop` preserves its
private Docker volume. Never use volume deletion to update this installation.
Fiji is installed in the versioned worker image and reused through Docker image
layers; web/API updates do not fetch a new Fiji distribution automatically.

An operator may enable the approved proposal relay with `-ProposalConfig` pointing
to a JSON file **outside this repository**, containing `url` (the approved HTTPS
origin) and `tokenFile` (an absolute, outside-repository device-token file). Only
the API container mounts this token. The browser and analysis worker do not receive
it, and the analysis worker remains offline. This file must not contain the OpenAI
key or the Worker administrator token. Start/Open/Stop should use the same config.
The API forwards a proposal only after the user confirms the displayed transmission
scope. See [proposal deployment](proposal-deployment.md) for the separate production
budget and overrun reconciliation. A failed request is never billed again without
an explicit retry; the UI warns that retrying may incur another charge.

Public-data/browser acceptance and Windows archive acceptance are recorded against
the exact release commit. These checks do not establish private-image validity,
Windows application-control compatibility on every device, or human usability.

### Optional lab retention policy

Windows setup asks how to keep workspaces. The default choice keeps them until
explicit deletion (`settings/retention.json`); unchecking it keeps 24-hour TTL
deletion. Once manual retention has been recorded for an installation it is not
reverted, even if setup is rerun with the other choice. Docker Desktop selects it
with `CYTELLECT_WORKSPACE_RETENTION_MODE=manual`. The mode is consistently
propagated to the child worker. Its API/UI reports no age
deadline; manual deletion, session expiry and job leases are unchanged. See
[Docker Desktop retention](docker-desktop.md#8-研究室で作業データを手動保持する)
for the durable mode marker, capacity responsibility and transition restrictions.
This is source implementation, not installed-copy or Docker delivery acceptance.
