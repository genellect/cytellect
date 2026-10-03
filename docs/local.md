# Local browser delivery

Status: Windows development preview. Each version is advertised only after its built package passes installation and browser checks; release notes record the accepted source and evidence. Local execution is an initial deployment option; the product remains a browser workspace with a future hosted backend.

The accepted [0.1.0-local.11 release](https://github.com/genellect/cytellect/releases/tag/v0.1.0-local.11) is available for Windows x86-64, with adopted planning, named-channel regions, batch registration and experimental-unit comparisons. See its [acceptance record](local-release-0.1.0.md) for exact source, checksums, failed attempts and remaining scientific/operator gates. Start with the [public-image guide](quickstart.ja.md). Earlier Methods may need review for the stain-identity correction retained from local.10.

## Researcher flow

1. Download the versioned Windows setup ZIP from the Cytellect release, verify its published SHA-256 if required by the laboratory, and extract it.
2. Open **Cytellect Setup.cmd**, review the destination and local data policy, and start setup. An unsigned early package may require Windows confirmation; do not disable operating-system security to bypass it.
3. Setup verifies its source manifest and provisions pinned Python, packages and Fiji in the user's Cytellect directory. It does not modify the system Python, PATH or an existing Fiji installation. Internet access is needed for this step only.
4. Open **Cytellect** from its shortcut. The small launcher starts the API and independent worker, then opens the browser workspace. There is no terminal command or invitation to enter for routine local use.
5. Import images, review masks, quantify, compare and export through the browser. Close the launcher to stop the local service and its worker. Closing only the browser tab does not stop the launcher.

Windows x86-64 is the first installation target. Other operating systems retain the developer/Compose setup until their installation paths are tested. The runtime may consume several gigabytes of disk; the tested installer reports its completed footprint separately from the small setup archive. No code-signing certificate or automatic-update service is assumed to exist.

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

Installation tests use an isolated directory under the task's scratch workspace. They must not overwrite a user's existing software, data or shortcuts. Acceptance includes an actual pinned-Fiji run, a browser upload/edit/export flow, hostile-origin denial, shutdown, restart and expiry. The release report records commit, archive checksum, platform, passed checks and known limitations. Publishing a ZIP is not evidence that installation succeeded.

The **Prepare Windows release** workflow is dispatched against `main` with a unique `0.1.0-local.N` version. It requires successful Python, Web, Fiji/browser, Windows lifecycle and full Windows Python3.14 compatibility checks on that exact commit, builds an immutable bundle and performs fresh and repeat Windows installation. For a release including area-only measurements, display receipts and paginated figures, all eighteen browser cases must pass against that installed copy: the published GFP path, imported/manual generic regions, one/two-channel nuclear detection with correction and batch reuse, declared independent/paired comparisons with ZIP replay, planning adoption into actual image/metric choices and a descriptive figure, strict saved-plan import, batch-registration recovery after a lost success response, historical source/mask review, shared registration metadata, saved unit/sample/field hierarchy, area-only revision/export/replay, calibrated-area comparisons, planning2.1 adoption, two exact preview/range workflows and paginated figure recovery. A skipped, failed or flaky case blocks the draft. The tests use the local session and the installed interpreter, with an explicit same-origin loopback API and separate private data directory. They do not create invitations or fall back to developer Python.

The ten required specifications contain one local-package case, two generic-region cases, three nuclear/comparison cases, three planning/batch-registration cases and one case each for source review, shared metadata and comparison hierarchy, three area-only cases, two display cases and one paginated-output case. The planning/batch specification uses registered public BBBC013 DRAQ pixels; repeated images test filename mapping and idempotent retry only, without claiming another stain or biological replication. The workflow requires exactly eighteen completed cases and retains failures instead of accepting an incomplete subset.

The additional `scripts/verify_installed_regions.py` gate runs with the installed Python, checks the complete source manifest and imported module locations, and compares the running server's exported source identity. Its module-hash receipt explicitly includes planning, plan adoption and the planning API alongside measurement, detection, comparison and replay code. Four generated regions yield signed background-corrected values A=[−3,−1], B=[2,0]. Welch and paired effect, standard error, degrees of freedom, p-value and confidence interval are checked with elementary closed-form references independently of SciPy's t-test functions. It then downloads every figure source file, verifies ZIP hashes and remeasures explicit raw originals through the saved-mask replay. The generated values verify calculation and packaging, while published microscopy verifies the image/browser paths; neither supplies biological replication or validates a private study.

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
