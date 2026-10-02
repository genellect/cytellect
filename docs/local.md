# Local browser delivery

Status: implementation and installation acceptance are in progress. Do not advertise a download until the built package passes installation and browser checks. Local execution is an initial deployment option; the product remains a browser workspace with a future hosted backend.

## Researcher flow

1. Download the versioned Windows setup ZIP from the Cytellect release, verify its published SHA-256 if required by the laboratory, and extract it.
2. Open **Cytellect Setup.cmd**, review the destination and local data policy, and start setup. An unsigned early package may require Windows confirmation; do not disable operating-system security to bypass it.
3. Setup verifies its source manifest and provisions pinned Python, packages and Fiji in the user's Cytellect directory. It does not modify the system Python, PATH or an existing Fiji installation. Internet access is needed for this step only.
4. Open **Cytellect** from its shortcut. The small launcher starts the API and independent worker, then opens the browser workspace. There is no terminal command or invitation to enter for routine local use.
5. Import images, review masks, quantify, compare and export through the browser. Close the launcher to stop the local service and its worker. Closing only the browser tab does not stop the launcher.

Windows x86-64 is the first installation target. Other operating systems retain the developer/Compose setup until their installation paths are tested. The runtime may consume several gigabytes of disk; the tested installer reports its completed footprint separately from the small setup archive. No code-signing certificate or automatic-update service is assumed to exist.

## What stays the same

The Web components call the same versioned API contracts. Local delivery adds a same-origin static Web build and explicit loopback startup; it does not fork segmentation, measurements, statistics, masks or exports. Standard Vercel builds retain the public sample viewer and never connect to localhost implicitly.

The local launcher uses the same pinned Fiji/Java/model and Python lockfiles. Installation downloads are separate from analysis. The worker must not fetch dependencies/models during a job. A later cloud deployment can replace database, file storage and dispatch adapters without changing scientific definitions or the browser editing workflow.

The Windows launcher does not install a firewall rule or inherit Compose's `network_mode: none`. Its worker is not isolated from the network at the operating-system level. The application accepts only registered recipes, verifies installed plugin/model hashes and invokes fixed local Java/Python entry points; it does not accept submitted code, model URLs or remote image URLs. Browser same-origin checks and a no-external-request browser test are separate evidence from OS-level egress denial. The offline Linux container remains the verified egress-isolated deployment option.

## Local security and retention

This is a single-OS-user application, not isolation between multiple people who share one operating-system account. Other processes with local loopback access are inside its trust boundary. Protect the OS account and data directory accordingly. It is not a LAN or public server.

The service binds only `127.0.0.1`, normally port8765. It validates the literal Host and Origin, rejects cross-site browser requests and forwarded host headers, and prevents framing. It does not trust DNS aliases or bind to `0.0.0.0`. A local-only same-origin POST establishes an HttpOnly, SameSite=Strict session; tokens are not placed in URLs, browser storage or logs. Cloud-mode applications do not expose this bootstrap endpoint.

Originals and derived files remain in the chosen private runtime directory, outside the source checkout and installation files. Explicit user activity controls the24-hour expiry; polling does not renew it. Access to expired work is denied. While the launcher is open, the worker performs physical cleanup; if it is closed or the PC is off, physical deletion resumes at the next launch. This limitation is disclosed before upload. Local installation does not provide remote deletion of a powered-off disk.

Closing the launcher stops computation and revokes its local-owner sessions. A subsequent launch can reopen that owner's unexpired work. Cleanup, stop/restart, quota and partial-job behavior must be verified on the installed copy, not only the development environment.

## Build and installation evidence

Developers build a local-only Web export with `pnpm --filter @cytellect/web build:local`. For a reviewed clean commit, run:

```sh
python scripts/build_local_bundle.py --version 0.1.0-local.1 --output /absolute/outside/checkout/Cytellect-0.1.0-local.1-windows-x64.zip
```

The builder rebuilds the Web export and packages only tracked allowlisted source files plus the static output. Every entry receives a SHA-256 in `local-release.json`; the archive receives a separate checksum. No `.env`, database, virtualenv, research image, runtime output or developer cache belongs in this package. The installation bootstrap verifies this manifest before copying files.

Installation tests use an isolated directory under the task's scratch workspace. They must not overwrite a user's existing software, data or shortcuts. Acceptance includes an actual pinned-Fiji run, a browser upload/edit/export flow, hostile-origin denial, shutdown, restart and expiry. The release report records commit, archive checksum, platform, passed checks and known limitations. Publishing a ZIP is not evidence that installation succeeded.

## Later hosted execution

Preserve the browser workflow and shared analysis packages. Hosted deployment adds a suitable persistent database, private artifacts, durable dispatch and same-origin/domain routing, with access/retention checks on the actual host. Cloud spend controls must not stop required deletion jobs. See [costs and trade-offs](hosting-costs.ja.md), [deployment](deployment.md) and [remaining gates](roadmap.md).
