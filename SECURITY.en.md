# Security Policy

[日本語](SECURITY.md)

Cytellect analyses unpublished microscopy images on the researcher's own PC. Images, masks, measurements and figures are stored on the PC and not in the Cytellect cloud. The relay service and the inference server store no research data and do not hold the update-signing key. As a result, an attacker who obtains a researcher's account, the relay service or write access to the repository cannot reach research data on the PC or installed applications.

The implementation and tests of the measures are public in this repository. The operator is genellect, which is responsible for operating the relay service, managing credentials and keys, and responding to incidents.

Vulnerability reports are accepted through the [private report form](https://github.com/genellect/cytellect/security/advisories/new) ([7. Vulnerability handling](#7-vulnerability-handling)).

- [1. Design principles](#1-design-principles)
- [2. Architecture and trust boundaries](#2-architecture-and-trust-boundaries)
- [3. Countermeasures against attacks](#3-countermeasures-against-attacks)
- [4. Protection of credentials, keys and accounts](#4-protection-of-credentials-keys-and-accounts)
- [5. Protection of research data](#5-protection-of-research-data)
- [6. Monitoring and incident response](#6-monitoring-and-incident-response)
- [7. Vulnerability handling](#7-vulnerability-handling)
- [8. Related documents](#8-related-documents)

## 1. Design principles

| Principle | Description |
|---|---|
| Research data stays on the PC | Images, masks, measurements and figures are stored on the PC and not in the Cytellect cloud. Detection, measurement, statistics and figure rendering also run on the PC. |
| The cloud holds minimal data and authority | The relay service stores no research data and does not hold the update-signing key. It stores only account information and usage records. |
| One compromise does not reach the whole | Data, keys and permissions are separated by component. Obtaining a researcher's account, the relay service or write access to the repository does not give access to research data on the PC or to installed applications. |
| The receiver verifies input crossing a boundary | The server on the PC, the relay service and the inference server each independently verify input that reaches them across a boundary. |
| Credentials are not stored in plaintext and are narrowly scoped | Tokens and sign-in codes are stored only as hashes. API keys and the signing key are held only by the component that uses them. |
| AI output is not executed | AI output is not executed as code. An analysis proposal is a draft of settings validated on the PC and is not used in an analysis until the researcher adopts it. |
| Releases are verified by signature and hash | The PC runs only updates whose signature it has verified. Dependencies and bundled components are pinned by hash. |

## 2. Architecture and trust boundaries

### 2.1 Components

Cytellect is provided as the Windows release (Microsoft Store and EXE) and as the Docker release, which runs on a PC or a lab server. The PC or server running the application is called the PC below.

| Component | Role | Data held | Keys and credentials held |
|---|---|---|---|
| PC (local web interface, the server on the PC, analysis worker) | Runs detection, measurement, statistics and figure rendering. | All research data | One device token (when signed in to the cloud) |
| Relay service (Cytellect Worker, running on Cloudflare Workers) | Handles sign-in, user approval and quotas, and relays requests to the cloud GPU and the AI. | Account information and usage records | API keys of external services; the HMAC key |
| Inference server (running on Modal) | Runs GPU inference for cell detection (Cellpose). | None | None |
| Distribution (Microsoft Store, GitHub) | Distributes and updates the application. | None | None (the update-signing key is kept in signing environments restricted to runs from `main`) |
| Public site (`cytellect.app`) | Serves the landing page, demo and guides. | None (accepts no research images) | None |

### 2.2 Trust boundaries

| Boundary | What crosses it | Verification by the receiver |
|---|---|---|
| Browser → the server on the PC | Requests from the local web interface | Peer address, Host, Origin, Fetch Metadata, the anti-CSRF header, session and ownership |
| PC → relay service | Detection and AI requests | Device token, account state, quota, body size and schema, request identifier |
| Relay service → inference server | Detection requests | Modal proxy authentication; format, size and fields of the input |
| Relay service → PC | Detection results, analysis proposals and discussion drafts | Comparison of the version hashes, schema validation of proposals and the researcher's adoption |
| Distribution host → PC | Updates | Signature, version, SHA-256 and size |

### 2.3 External services

| Service | Purpose | Information received |
|---|---|---|
| Cloudflare | Running the relay service, recording account information and usage, authenticating the admin page | Requests in transit (not stored), account information and usage records |
| Modal | GPU inference for cell detection | The image plane to detect, nuclear labels and detection parameters (only while processed) |
| Anthropic, OpenAI | Generating analysis proposals and discussion drafts | The data transmitted to the AI as listed in [5.1 Information transmitted from the PC](#51-information-transmitted-from-the-pc) |
| Resend | Delivering sign-in codes by e-mail | The e-mail address and the sign-in code |
| GitHub | Source code hosting, CI and distribution of the EXE release | None |
| Microsoft Store | Distribution and updates of the Windows release | None |
| Vercel | Serving the public site | None |
| Google Analytics | Web analytics on the public pages (landing page, demo and guides) | Information about visits to the public pages. Advertising use is disabled, and no measurement takes place when the browser signals a tracking opt-out (Do Not Track, Global Privacy Control). Not used in the analysis screen or the installed application. |

## 3. Countermeasures against attacks

### 3.1 Unauthorised access

| Attack | Countermeasures | Implementation and tests |
|---|---|---|
| Brute-forcing sign-in codes | Five incorrect entries invalidate a sign-in code, and 20 incorrect entries for one e-mail address within a day lock it for 24 hours. Incorrect entries are counted per e-mail address, so changing the source IP address yields no additional attempts. Issuance of sign-in codes is limited to 20 per hour per IP address (per /64 for IPv6) and to 6 per hour and 10 per day per e-mail address; verification is limited to 30 per hour per IP address. The probability of success against a six-digit sign-in code is at most 2×10⁻⁵ per day per e-mail address. | [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |
| Credential stuffing | No passwords are used. Authentication uses a single-use sign-in code received by e-mail (valid for 10 minutes; generated without bias from a cryptographically secure random source) and a 256-bit token issued per device. Sign-in codes are sent only to e-mail addresses the Cytellect maintainer has allowed. | [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`http.ts`](services/proposal-worker/src/http.ts) [`mail.ts`](services/proposal-worker/src/mail.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |
| Token theft | A device token is 256 random bits. The relay service stores only its SHA-256 hash. On the PC it is stored in a settings area separate from research data, and the server on the PC includes it in neither responses nor logs. The device token is sent only to the URL that issued it, and redirects are not followed. It expires after 90 days without use and is deleted from both the PC and the relay service on sign-out. | [`cloud_account.py`](services/api/src/cytellect_api/cloud_account.py) [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`http.ts`](services/proposal-worker/src/http.ts) [`test_cloud_account.py`](tests/test_cloud_account.py) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |
| Session fixation and hijacking | The server issues a new token at every sign-in. A session named by the client is never adopted. Sessions are held in HttpOnly, SameSite=Strict cookies, and the server stores only the SHA-256 of the token. Logging out revokes the session, and the Windows release revokes all sessions when the application exits. | [`app.py`](services/api/src/cytellect_api/app.py) [`local.py`](services/api/src/cytellect_api/local.py) [`db.py`](services/api/src/cytellect_api/db.py) [`test_local.py`](tests/test_local.py) |
| Cross-site request forgery (CSRF) | State-changing requests must carry an exactly matching Origin and a dedicated anti-CSRF header. CORS permits only the application's own origin. The session cookie is not sent with requests from other sites. | [`app.py`](services/api/src/cytellect_api/app.py) [`local.py`](services/api/src/cytellect_api/local.py) [`desktop.py`](services/api/src/cytellect_api/desktop.py) [`test_local.py`](tests/test_local.py) [`test_desktop_owner.py`](tests/test_desktop_owner.py) |
| DNS rebinding | The server on the PC listens only on `127.0.0.1`. The Windows release checks the peer address, an exactly matching Host and Fetch Metadata (Sec-Fetch-Site) on every request, and rejects requests carrying forwarding headers (Forwarded, X-Forwarded-*). | [`local.py`](services/api/src/cytellect_api/local.py) [`test_local.py`](tests/test_local.py) |
| Unauthorised reads and writes (broken access control) | Every route that takes a workspace, field, job or result identifier compares the session's owner with the owner of the target. A request that does not match receives the same response as for a target that does not exist. Identifiers are UUID v4 values generated by the server, and an identifier alone confers no permission. | [`app.py`](services/api/src/cytellect_api/app.py) [`regions.py`](services/api/src/cytellect_api/regions.py) [`db.py`](services/api/src/cytellect_api/db.py) [`test_upload_guard.py`](tests/test_upload_guard.py) |
| Unauthorised access to admin functions | The admin page is placed behind Cloudflare Access (Google sign-in). The relay service also independently verifies the JWT issued by Cloudflare Access: its signature (algorithm fixed to RS256), issuer, audience, expiry and the maintainer's e-mail address. Admin routes respond only on the designated origin; other entry points such as `workers.dev` do not respond even to a valid token. | [`access.ts`](services/proposal-worker/src/access.ts) [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`access.test.ts`](services/proposal-worker/src/access.test.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) [`wrangler.toml.example`](services/proposal-worker/wrangler.toml.example) |
| Forged approval | A new researcher is approved through a single-use link signed with HMAC (valid for 7 days). Opening the link alone approves nothing; approval requires a confirming action on the page. | [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`admin-page.ts`](services/proposal-worker/src/admin-page.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |
| Direct requests to the inference server | Modal proxy authentication is required, and unauthenticated requests are not accepted. | [`modal_cellpose.py`](infra/modal_cellpose.py) [`cloud.ts`](services/proposal-worker/src/cloud.ts) |

### 3.2 Injection

| Attack | Countermeasures | Implementation and tests |
|---|---|---|
| SQL injection | The server on the PC builds queries with SQLAlchemy expressions and binds every value. The relay service executes every statement as a prepared statement with bound values. No request value is concatenated into an SQL string. | [`db.py`](services/api/src/cytellect_api/db.py) [`app.py`](services/api/src/cytellect_api/app.py) [`store.ts`](services/proposal-worker/src/store.ts) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) |
| Command injection | External processes are started with an argument array and never through a shell. Fiji receives only typed parameters, and no macro text is executed. The detection model name is fixed and cannot be specified by a request. | [`supervision.py`](services/worker/src/cytellect_worker/supervision.py) [`engine.py`](packages/analysis/src/cytellect_analysis/engine.py) [`CytellectEngine.java`](engines/fiji/CytellectEngine.java) [`region_contracts.py`](packages/analysis/src/cytellect_analysis/region_contracts.py) |
| Prompt injection | The AI is given no tool calls. AI output is restricted to a JSON schema and is not executed as code. An analysis proposal is validated against the schema on the PC, and one containing an undefined field is rejected. The schema has no field representing a file path, a URL or a command. A proposal is not used in an analysis until the researcher adopts it. Measurements and statistics are computed by the shared implementation irrespective of the proposal's content. A discussion draft is displayed as text and does not modify analysis settings or values. | [`proposal_validation.py`](packages/analysis/src/cytellect_analysis/proposal_validation.py) [`proposal_contracts.py`](packages/analysis/src/cytellect_analysis/proposal_contracts.py) [`proposals.py`](services/api/src/cytellect_api/proposals.py) [`openai.ts`](services/proposal-worker/src/openai.ts) [`anthropic.ts`](services/proposal-worker/src/anthropic.ts) [`test_proposals.py`](tests/test_proposals.py) [`test_proposals_persistence.py`](tests/test_proposals_persistence.py) |
| Cross-site scripting (XSS) | The local web interface renders through React's escaping. Researcher input and AI output are displayed as text and are not interpreted as HTML. The only content inserted as HTML is the SVG figure produced by the analysis, which is sanitised with an allowlist of elements and attributes before insertion. The admin page sets values as text and applies a nonce-based Content Security Policy. | [`EditableFigure.tsx`](apps/web/src/components/workspace/review/EditableFigure.tsx) [`DiscussionPanel.tsx`](apps/web/src/components/workspace/review/DiscussionPanel.tsx) [`admin-page.ts`](services/proposal-worker/src/admin-page.ts) [`http.ts`](services/proposal-worker/src/http.ts) |
| Path traversal | Storage uses server-generated UUIDs and fixed names, and uploaded file names are not used in paths. Paths are verified to lie inside the storage area. Settings files and working areas refuse symbolic links. Archives are not extracted to disk. | [`db.py`](services/api/src/cytellect_api/db.py) [`config.py`](services/api/src/cytellect_api/config.py) [`local.py`](services/api/src/cytellect_api/local.py) [`app.py`](services/api/src/cytellect_api/app.py) |
| Insecure deserialisation | pickle is not used. Every array is loaded with pickle disabled. Model weights are loaded in weights-only mode after their SHA-256 has been checked. JSON arriving from outside is validated against schemas that reject undefined fields. | [`server.py`](engines/cellpose/server.py) [`runner.py`](engines/cellpose/runner.py) [`cellpose_engine.py`](packages/analysis/src/cytellect_analysis/cellpose_engine.py) [`contracts.py`](packages/analysis/src/cytellect_analysis/contracts.py) [`proposal_contracts.py`](packages/analysis/src/cytellect_analysis/proposal_contracts.py) [`schema.ts`](services/proposal-worker/src/schema.ts) |
| Server-side request forgery (SSRF) | Outbound destinations are determined by configuration alone. Neither a request nor AI output can specify a destination. Destination URLs must use HTTPS, and those containing credentials, a query or a fragment are rejected. Outbound requests do not follow redirects. Update downloads are restricted to an allowlist of hosts, and redirect targets are checked as well. An inference request cannot specify a URL, a file path or an arbitrary model. | [`cloud_account.py`](services/api/src/cytellect_api/cloud_account.py) [`cellpose_engine.py`](packages/analysis/src/cytellect_analysis/cellpose_engine.py) [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`openai.ts`](services/proposal-worker/src/openai.ts) [`anthropic.ts`](services/proposal-worker/src/anthropic.ts) [`app_update.py`](services/api/src/cytellect_api/app_update.py) [`server.py`](engines/cellpose/server.py) [`runner.py`](engines/cellpose/runner.py) |

### 3.3 Input and resources

| Attack | Countermeasures | Implementation and tests |
|---|---|---|
| Upload of crafted files | An image must be a two-dimensional 8-bit or 16-bit TIFF with a single series. A side is at most 4096 px, and the pixel count derived from the header is confirmed to be within the limit before decompression. OME files referring to external files are rejected. A table is at most 8 MiB and 100,000 rows, with a fixed set of columns. A workspace holds at most 100 fields and 2 GiB in total. | [`images.py`](packages/analysis/src/cytellect_analysis/images.py) [`numerical_csv.py`](packages/analysis/src/cytellect_analysis/numerical_csv.py) [`app.py`](services/api/src/cytellect_api/app.py) [`upload_guard.py`](services/api/src/cytellect_api/upload_guard.py) [`test_upload_guard.py`](tests/test_upload_guard.py) |
| Denial of service and resource exhaustion | The relay service limits body size per route (authentication 4 KiB, analysis proposals and discussions 6 MiB, detection 256 MiB). The server on the PC allows at most 10 queued and running jobs in total and applies time (3600 s) and memory (4096 MB) limits to each job. The inference server processes one request at a time in a single container. | [`index.ts`](services/proposal-worker/src/index.ts) [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`app.py`](services/api/src/cytellect_api/app.py) [`supervision.py`](services/worker/src/cytellect_worker/supervision.py) [`modal_cellpose.py`](infra/modal_cellpose.py) [`test_supervision.py`](tests/test_supervision.py) |
| Cost exhaustion | GPU seconds and AI cost are subject to per-account monthly limits and an overall monthly budget. The maximum cost of a request is reserved atomically before the model is called, and requests exceeding a limit are rejected without being forwarded to the external service. GPU requests are limited to one in flight per account. If the cost records become inconsistent, requests to the AI are suspended until the inconsistency is resolved. | [`store.ts`](services/proposal-worker/src/store.ts) [`index.ts`](services/proposal-worker/src/index.ts) [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`store.test.ts`](services/proposal-worker/src/store.test.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |
| Replay of requests | A proposal request is accepted once per device for each unique identifier (UUID). Sign-in codes, approval links and invitations are consumed exactly once. | [`index.ts`](services/proposal-worker/src/index.ts) [`store.ts`](services/proposal-worker/src/store.ts) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`index.test.ts`](services/proposal-worker/src/index.test.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |
| Exploitation of race conditions | Single-use consumption, budget reservation and rate-limit increments are each executed atomically in a single statement. The database on the PC serialises writes, and a job's lease is verified by compare-and-swap. | [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`store.ts`](services/proposal-worker/src/store.ts) [`db.py`](services/api/src/cytellect_api/db.py) |
| Escape from the analysis environment | The Docker analysis worker runs in a container with no network, as a non-root user, on a read-only root filesystem. All Linux capabilities are dropped, privilege escalation is disabled, and memory and process count are limited. CI verifies on the real container that outbound connections are denied. No code or model is downloaded while an analysis runs. | [`compose.yaml`](compose.yaml) [`ci.yml`](.github/workflows/ci.yml) [`runner.py`](engines/cellpose/runner.py) |

### 3.4 Transport and presentation

| Attack | Countermeasures | Implementation and tests |
|---|---|---|
| Eavesdropping and tampering (man in the middle) | External communication from the PC and the relay service uses HTTPS only, with server certificates verified against the OS trust store. No path disables certificate verification. Plain HTTP is used only inside the PC (loopback). Updates are verified by signature independently of the network path. | [`cloud_account.py`](services/api/src/cytellect_api/cloud_account.py) [`cellpose_engine.py`](packages/analysis/src/cytellect_analysis/cellpose_engine.py) [`proposals.py`](services/api/src/cytellect_api/proposals.py) [`app_update.py`](services/api/src/cytellect_api/app_update.py) |
| API calls from other origins | The relay service returns no CORS headers permitting other origins. Because the device token is sent in the Authorization header, requests from pages on other sites are blocked by the browser's preflight. | [`http.ts`](services/proposal-worker/src/http.ts) [`cloud.ts`](services/proposal-worker/src/cloud.ts) |
| Clickjacking | Embedding in frames is forbidden on the local web interface, the public site and the admin page alike. | [`app.py`](services/api/src/cytellect_api/app.py) [`local.py`](services/api/src/cytellect_api/local.py) [`next.config.ts`](apps/web/next.config.ts) [`admin-page.ts`](services/proposal-worker/src/admin-page.ts) |
| Information disclosure | Errors return predefined error codes only; internal exceptions, stack traces and analysis program output are not returned. Responses carry headers that forbid caching, MIME type sniffing and sending the referrer. Access logging is disabled, and request bodies, file names and token values are not logged. The relay service disables Cloudflare Workers log collection and replaces errors from external services with predefined error codes and the HTTP status only. | [`app.py`](services/api/src/cytellect_api/app.py) [`local.py`](services/api/src/cytellect_api/local.py) [`index.ts`](services/proposal-worker/src/index.ts) [`wrangler.toml.example`](services/proposal-worker/wrangler.toml.example) [`deployment.test.mjs`](services/proposal-worker/scripts/deployment.test.mjs) |

### 3.5 Distribution and supply chain

| Attack | Countermeasures | Implementation and tests |
|---|---|---|
| Replacement of an update and rollback to an older version | Each EXE release carries a manifest stating the version, installer name, SHA-256, size, source commit and time of issue, with a signature made with the Ed25519 key. The application verifies the manifest's signature with its built-in public key before fetching the installer. The installer runs only when the version is newer than the installed one and its SHA-256 and size match the manifest. The hash reported by the distribution host is not trusted. The Microsoft Store release is signed by Microsoft and updated by the Microsoft Store. | [`update_signature.py`](services/api/src/cytellect_api/update_signature.py) [`app_update.py`](services/api/src/cytellect_api/app_update.py) [`local-release.yml`](.github/workflows/local-release.yml) [`test_update_signature.py`](tests/test_update_signature.py) [`test_app_update.py`](tests/test_app_update.py) |
| Replacement of the first download | The installer for a first installation can also be verified against the same signed manifest ([steps, in Japanese](docs/install-windows.ja.md#2-ダウンロードと確認)). | [`update_signature.py`](services/api/src/cytellect_api/update_signature.py) |
| Replacement of dependencies, bundled components and detection models | Python and JavaScript dependencies are pinned by version and hash in lockfiles. The bundled Fiji, detection models and Python runtime are checked against SHA-256 at build time. Detection models are also checked against SHA-256 before loading. | [`uv.lock`](uv.lock) [`pnpm-lock.yaml`](pnpm-lock.yaml) [`fiji/runtime.lock.json`](engines/fiji/runtime.lock.json) [`cellpose/runtime.lock.json`](engines/cellpose/runtime.lock.json) [`build_windows_installer.py`](scripts/build_windows_installer.py) [`runner.py`](engines/cellpose/runner.py) [`test_windows_installer.py`](tests/test_windows_installer.py) |
| Unauthorised changes to the repository | Merging to `main` is restricted to the maintainer by a ruleset. Changes are made through pull requests and merged once the required CI has passed. A release is built from a single commit, which is re-checked at each stage. A commit that is not in the history of `main` and reuse of a tag are refused. A file whose size or hash does not match the tested file is not published. | [`local-release.yml`](.github/workflows/local-release.yml) [`windows_exe_release.cjs`](scripts/windows_exe_release.cjs) [`windows_exe_release.test.cjs`](scripts/windows_exe_release.test.cjs) |
| Abuse of CI | The workflow token is read-only by default. Runs originating from forks receive neither write permission nor secrets. Releases refuse runs originating from forks. | [`ci.yml`](.github/workflows/ci.yml) [`local-release.yml`](.github/workflows/local-release.yml) [`windows_exe_release.cjs`](scripts/windows_exe_release.cjs) |
| Exploitation of known vulnerabilities | CodeQL (workflows, JavaScript/TypeScript, Python) runs on pull requests, on `main` and weekly. Dependency vulnerability audits (pip-audit, pnpm audit) and generation of a software bill of materials (SBOM) run in CI. | [`codeql.yml`](.github/workflows/codeql.yml) [`ci.yml`](.github/workflows/ci.yml) [`sbom.py`](scripts/sbom.py) [`test_sbom.py`](tests/test_sbom.py) |

### 3.6 Impact of a compromise

The extent of impact when an attacker obtains one of the following.

| What the attacker has obtained | Extent of impact | What cannot be reached |
|---|---|---|
| A researcher's e-mail or device token | That account's quota for the month | Research data (none is stored in the cloud) |
| The relay service | Requests relayed during the compromise, and the API keys and account information the relay service holds. A proposal is not used in an analysis without validation on the PC and the researcher's adoption. | Research data on the PC, installed applications and the update-signing key |
| The relay service's database | E-mail addresses, approval states and usage records | Usable credentials (only hashes are stored) and research data |
| Write access to the repository | Branches and pull requests | `main` and installed PCs (updates require a signature made with the key in the signing environments) |

## 4. Protection of credentials, keys and accounts

### 4.1 Inventory of credentials and keys

| Credential or key | Where it is kept | Scope of authority | Lifetime and revocation |
|---|---|---|---|
| Device token | The settings area on the PC (readable only by the OS user). The relay service holds only the SHA-256 hash. | Detection and AI requests within that account's quota | Invalidated by 90 days without use, sign-out or account revocation. Revocation takes effect from the next request. |
| Session on the PC | A browser cookie (HttpOnly, SameSite=Strict). The server on the PC holds only the SHA-256 hash. | Operations on workspaces on that PC | 7 days. Invalidated immediately by logging out or by exiting the application (Windows release). |
| Sign-in code | The relay service holds only the HMAC-SHA256 hash. | One sign-in | 10 minutes. Invalidated by one use or by five incorrect entries. |
| Approval link | The relay service holds only the SHA-256 hash. The link is signed with HMAC. | Approval of one e-mail address | 7 days. Invalidated by one use. |
| HMAC key | A secret of the relay service (outside the database). With a key shorter than 32 characters, the sign-in and admin functions do not start. | Hashing sign-in codes, signing approval links and computing rate-limit identifiers (with a separate domain per purpose) | At rotation, unused sign-in codes and approval links become invalid. |
| API keys of external services (Anthropic, OpenAI, Resend) | Kept only as secrets of the relay service. Not included on the PC, in a release or in a response from the relay service. | AI calls and e-mail delivery. Cost is bounded by the monthly budget. | Rotated by invalidating the key at the external service and updating the secret. |
| Inference server credential (Modal proxy authentication) | Kept as a secret of the relay service. A PC signed in to the cloud does not hold it. | Detection requests to the inference server | Rotated by reissuing it at Modal and updating the secret. |
| Update-signing key (Ed25519) | Kept only in the maintainer's password manager and in GitHub Actions signing environments restricted to runs from `main`. Not kept as a repository-wide secret. | Signing the update manifest of the EXE release. Used only by the signing job. | Rotation and revocation procedures are defined ([release signing](docs/release-signing.md), in Japanese). |
| Update public key | Built into the application. | Verifying the manifest's signature | Changed only through the key rotation procedure. |
| Microsoft Store submission credentials | Kept in a GitHub Actions environment that requires the maintainer's approval and is restricted to `main`. | Submissions to the Microsoft Store | Used only by the submission job. |
| Cloudflare API token | Kept only in the maintainer's operating environment. | Editing Workers and D1, limited to the Cytellect account and the `cytellect.app` zone | Revoked by invalidating it at Cloudflare. |
| Workflow token (`GITHUB_TOKEN`) | Issued by GitHub Actions for each run. | Read-only by default. Write access is granted only to jobs that need it. | Invalidated when the run ends. |

Implementation and tests: [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`http.ts`](services/proposal-worker/src/http.ts) [`cloud_account.py`](services/api/src/cytellect_api/cloud_account.py) [`local.py`](services/api/src/cytellect_api/local.py) [`update_signature.py`](services/api/src/cytellect_api/update_signature.py) [`wrangler.toml.example`](services/proposal-worker/wrangler.toml.example) [`local-release.yml`](.github/workflows/local-release.yml) [`windows-store-release.yml`](.github/workflows/windows-store-release.yml) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) [`test_cloud_account.py`](tests/test_cloud_account.py) [`deployment.test.mjs`](services/proposal-worker/scripts/deployment.test.mjs)

### 4.2 Leak prevention and detection

| Measure | Mechanism | Implementation and tests |
|---|---|---|
| No plaintext storage | Tokens, sign-in codes, approval links and invitations are stored only as hashes. IP addresses are not stored, and rate-limit identifiers are also stored as values computed with HMAC. Tokens and sign-in codes are compared in constant time. | [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`http.ts`](services/proposal-worker/src/http.ts) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`db.py`](services/api/src/cytellect_api/db.py) |
| Repository scanning | A hash-verified gitleaks scans the full Git history and tracked files of `main` and of every pull request. The scan outputs only counts and rule identifiers. | [`scan_secrets.py`](scripts/scan_secrets.py) [`security-tools.lock.json`](scripts/security-tools.lock.json) [`ci.yml`](.github/workflows/ci.yml) [`test_scan_secrets.py`](tests/test_scan_secrets.py) |
| Release scanning | The installer and the Microsoft Store package are scanned for credentials at build time, and the build fails if any is found. | [`build_windows_installer.py`](scripts/build_windows_installer.py) [`test_windows_installer.py`](tests/test_windows_installer.py) |
| Restricted outbound transmission | The relay service sends API keys only to the fixed HTTPS destination of each external service and does not follow redirects. Only headers describing the content type and length are forwarded to the inference server, and the researcher's device token is not passed on. | [`openai.ts`](services/proposal-worker/src/openai.ts) [`anthropic.ts`](services/proposal-worker/src/anthropic.ts) [`mail.ts`](services/proposal-worker/src/mail.ts) [`cloud.ts`](services/proposal-worker/src/cloud.ts) |
| Separation from development | A development environment holds only a device token issued for that environment. API keys and the signing key are not placed in development environments. The repository and CI contain no private research data. Development environments used by several people reject uploads other than registered public files by checking their SHA-256. | [`public_uploads.py`](services/api/src/cytellect_api/public_uploads.py) [`test_public_uploads.py`](tests/test_public_uploads.py) |

### 4.3 Protection of operational accounts

| Measure | Mechanism | Implementation and tests |
|---|---|---|
| Multi-factor authentication | Every external service account used for operations requires multi-factor authentication with a passkey or an authenticator app. | Operational setting |
| Operational authority | The relay service, the inference server and distribution are operated by genellect alone. No other user is invited to the inference server's account. | Operational setting |
| Release approval | Manual releases and Microsoft Store submissions run in GitHub Actions environments that require the maintainer's approval. An automatic release publishes only versions that have passed CI and the distribution tests on protected `main`. | [`local-release.yml`](.github/workflows/local-release.yml) [`windows-store-release.yml`](.github/workflows/windows-store-release.yml) [`windows_exe_release.cjs`](scripts/windows_exe_release.cjs) [`windows_exe_release.test.cjs`](scripts/windows_exe_release.test.cjs) |
| Spending limits | In addition to the relay service's monthly budget and per-account limits, a spending limit is also set at the inference server's provider. | [`store.ts`](services/proposal-worker/src/store.ts) [`wrangler.toml.example`](services/proposal-worker/wrangler.toml.example) |

### 4.4 Cryptography

| Purpose | Method |
|---|---|
| Protection in transit | TLS. Server certificates are verified against the OS trust store. |
| Token generation | 256 bits from a cryptographically secure random source |
| Token storage | SHA-256 hash |
| Sign-in code storage and approval-link signatures | HMAC-SHA256 (with a separate domain per purpose) |
| Admin page JWT | The RS256 signature is verified with Cloudflare Access's public keys. |
| Update signature | An Ed25519 SSH signature (OpenSSH SSHSIG format, namespace `cytellect-update`, SHA-512 hash) |
| Integrity verification | SHA-256. Applied to the installer, bundled components, detection models, dependencies and imported images. |
| Encryption at rest | The OS's disk encryption (BitLocker and similar) |

Implementation and tests: [`http.ts`](services/proposal-worker/src/http.ts) [`access.ts`](services/proposal-worker/src/access.ts) [`update_signature.py`](services/api/src/cytellect_api/update_signature.py) [`test_update_signature.py`](tests/test_update_signature.py) [`access.test.ts`](services/proposal-worker/src/access.test.ts)

## 5. Protection of research data

### 5.1 Information transmitted from the PC

Research data leaves the PC only when the researcher performs one of the following three operations. Without them, research data does not leave the PC.

| Operation | Data transmitted | Destination | Handling at the destination |
|---|---|---|---|
| Cell detection on the cloud GPU | One image plane to detect (one field, one channel, at original size) and the detection parameters. For nucleolar detection, the adopted nuclear labels (an image marking the nuclear regions) are added. | The inference server, via the relay service | The relay service forwards the body as a stream, without interpreting or retaining it. The inference server processes it in memory only and does not write it to a file. Neither stores or logs it. |
| Consultation with the AI | The research goal, channel and field records, image dimensions, the current analysis settings and downscaled preview images of one representative field (itemised below) | Anthropic or OpenAI, via the relay service | The relay service neither stores nor logs it. The AI providers do not use it for model training. |
| Discussion draft generation by the AI | The saved comparison and the experiment purpose (itemised below) | As above | As above |

A consultation with the AI transmits the following.

- The research goal
- Channel names and recorded stains
- Field names (by default the file name) and records (condition, experimental run, pair, acquisition date)
- Image dimensions and pixel size, and field and group counts
- The current analysis settings and the previous proposal
- Per-channel downscaled preview images of one representative field (at most 512 px per side; can be disabled in settings)

Discussion draft generation transmits the following.

- The experiment purpose (it defaults to the research goal written to the AI in that workspace)
- The summary on screen (heading and points)
- The metric's name and definition, the stain name, and the region, group, experimental run and channel names
- Group values, differences and confidence intervals, per-run values, and n and its breakdown
- Aggregation and test methods, the researcher's experimental-unit definition and pairing basis, and the test and its p-value

Per-nucleus measurements and file paths are not transmitted by any operation. Fields the researcher has excluded are used neither for proposals nor for preview images. Requests to OpenAI set `store: false` so that responses are not stored. The AI providers retain data for abuse monitoring for the period their API terms define.

Three communications carry no research data: cloud sign-in (the e-mail address and the sign-in code), use of the cloud features (the device token) and the EXE release's update check (fetching GitHub's public release list). The installed application and the analysis screen transmit no usage telemetry.

Implementation and tests: [`proposals.py`](services/api/src/cytellect_api/proposals.py) [`discussions.py`](services/api/src/cytellect_api/discussions.py) [`cellpose_engine.py`](packages/analysis/src/cytellect_analysis/cellpose_engine.py) [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`server.py`](engines/cellpose/server.py) [`app_update.py`](services/api/src/cytellect_api/app_update.py) [`test_proposals.py`](tests/test_proposals.py) [`test_result_discussion_api.py`](tests/test_result_discussion_api.py) [`test_cellpose_remote.py`](tests/test_cellpose_remote.py)

### 5.2 Consent and transmission confirmation

| Measure | Mechanism | Implementation and tests |
|---|---|---|
| Consent | The scope transmitted to the AI is displayed, and consent obtained, at cloud sign-in and at the first discussion draft. The AI settings panel also displays the scope at all times. | [`CloudAccount.tsx`](apps/web/src/components/workspace/CloudAccount.tsx) [`ConnectedWorkspace.tsx`](apps/web/src/components/workspace/review/ConnectedWorkspace.tsx) [`AiSettings.tsx`](apps/web/src/components/workspace/AiSettings.tsx) |
| Transmission confirmation | The server on the PC sends to the AI only requests the researcher has confirmed on screen, and rejects requests without that confirmation. | [`proposals.py`](services/api/src/cytellect_api/proposals.py) [`discussions.py`](services/api/src/cytellect_api/discussions.py) [`test_proposals.py`](tests/test_proposals.py) [`test_result_discussion_api.py`](tests/test_result_discussion_api.py) |

### 5.3 Storage and deletion

| Measure | Mechanism | Implementation and tests |
|---|---|---|
| Storage location | Data and credentials on the PC are stored in an area of the OS user's profile that only that user can read (`%LOCALAPPDATA%\Cytellect` in the Windows release). | [`local.py`](services/api/src/cytellect_api/local.py) [`cloud_account.py`](services/api/src/cytellect_api/cloud_account.py) [`local_setup.ps1`](scripts/local_setup.ps1) |
| Integrity of original images | Original pixel values are not modified. An imported image is checked against its SHA-256 before it is used in an analysis, and results are written to a separate area. | [`worker/regions.py`](services/worker/src/cytellect_worker/regions.py) |
| Retention | The Windows release retains work data until the researcher deletes it (the EXE release also offers automatic deletion after 24 hours at installation). The Docker release expires and deletes it 24 hours after the last action. In a configuration that listens only on `127.0.0.1`, retention until deletion can be selected. | [`config.py`](services/api/src/cytellect_api/config.py) [`test_workspace_retention.py`](tests/test_workspace_retention.py) |
| Deletion | Reads are blocked immediately on expiry or deletion. Inputs, arrays, masks, figures and exported files are then removed. | [`app.py`](services/api/src/cytellect_api/app.py) [`worker/main.py`](services/worker/src/cytellect_worker/main.py) [`test_workspace_retention.py`](tests/test_workspace_retention.py) |

### 5.4 Information stored in the cloud

The Cytellect cloud stores only the following four classes of information. Research data is not among them.

| Class | Content | Use |
|---|---|---|
| Account information | E-mail address, approval state, times of request, approval and revocation, and per-account quotas | Approval, revocation and quota management |
| Authentication records | Hashes of device tokens, sign-in codes, approval links and invitations, with their expiry times | Authentication |
| Rate-limit and replay-prevention records | Identifiers computed with HMAC and their counts, and request identifiers (UUID) | Preventing brute force and replay |
| Usage records | Monthly GPU seconds, the start time of a GPU request in flight, and per analysis proposal the cost, AI input and output token counts, model name and prompt version | Quota and cost management |

Implementation and tests: [`migrations/`](services/proposal-worker/migrations) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`store.ts`](services/proposal-worker/src/store.ts) [`store.test.ts`](services/proposal-worker/src/store.test.ts)

## 6. Monitoring and incident response

### 6.1 The operator's responsibilities

Cytellect is operated by genellect. genellect is responsible for the following.

- Operating the relay service and the inference server and managing their configuration
- Keeping, rotating and revoking credentials and keys
- Approving and revoking researchers' access
- Signing releases and distributing fixed versions
- Responding to vulnerability reports and publishing security advisories
- Containing incidents, assessing their impact, notifying affected researchers and recovering

### 6.2 Detection

| Measure | Mechanism | Implementation and tests |
|---|---|---|
| Authentication anomalies | Incorrect entries and rate-limit counts are recorded, and an e-mail address that reaches a limit is locked automatically. A new access request is notified to the maintainer by e-mail. | [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) |
| Usage and cost anomalies | Usage per account is recorded and shown on the admin page. If the cost records become inconsistent, requests to the AI are suspended automatically. | [`store.ts`](services/proposal-worker/src/store.ts) [`admin-page.ts`](services/proposal-worker/src/admin-page.ts) [`index.ts`](services/proposal-worker/src/index.ts) [`store.test.ts`](services/proposal-worker/src/store.test.ts) |
| Credentials in code or releases | CI scans the full Git history and releases ([4.2 Leak prevention and detection](#42-leak-prevention-and-detection)). | [`scan_secrets.py`](scripts/scan_secrets.py) [`build_windows_installer.py`](scripts/build_windows_installer.py) [`ci.yml`](.github/workflows/ci.yml) |
| Vulnerabilities | CodeQL and dependency audits run in CI, and external reports are accepted through the private report form ([7. Vulnerability handling](#7-vulnerability-handling)). | [`codeql.yml`](.github/workflows/codeql.yml) [`ci.yml`](.github/workflows/ci.yml) |
| Tampering with releases | The signature is verified when a release is created, and the published files are verified again afterwards. The application rejects an update whose signature or hash does not match and reports it as an error. | [`local-release.yml`](.github/workflows/local-release.yml) [`windows_exe_release.cjs`](scripts/windows_exe_release.cjs) [`app_update.py`](services/api/src/cytellect_api/app_update.py) [`test_app_update.py`](tests/test_app_update.py) |

### 6.3 Incident response

1. Containment. The affected function is stopped and the credentials and keys involved are revoked ([6.4 Means of stopping and revoking](#64-means-of-stopping-and-revoking)).
2. Impact assessment. The affected accounts, data and versions are identified.
3. Notification. When researchers' account information or data in transit is affected, the registered e-mail addresses are notified as soon as the impact is confirmed.
4. Recovery. Keys are rotated and a fixed version is distributed. The public site and cloud features are deployed to production, and the Windows release is distributed through the Microsoft Store and a signed update.
5. Disclosure. A security advisory is published, stating the cause, the extent of impact and the fixed version.
6. Prevention of recurrence. The cause is identified from evidence and addressed structurally rather than case by case.

### 6.4 Means of stopping and revoking

| Target | Means | Effect |
|---|---|---|
| A researcher's account | The account is revoked on the admin page. | Requests from every device signed in with it are rejected from the next request. |
| AI features | The relay service's budget setting is set to zero. | Requests for analysis proposals and discussions are rejected without being forwarded to the external service. |
| Cloud GPU | The relay service's monthly GPU limit is set to zero. | Detection requests are rejected without being forwarded to the inference server. |
| Sign-in and administration | The relay service's HMAC key is rotated. | Unused sign-in codes and approval links become invalid at rotation. |
| API keys of external services | The key is invalidated at the external service and the relay service's secret is updated. | The old API key becomes unusable at invalidation. |
| Automatic EXE distribution | Automatic distribution is disabled and running workflows are cancelled. | No new release is published. |
| Update-signing key | The key is removed from the signing environments and a version with a new built-in key is distributed ([release signing](docs/release-signing.md), in Japanese). | From the moment of removal, the signing environments can no longer sign with that key. Later versions are signed with the new key, and researchers are directed to install them with the new installer. |
| Version of the relay service | The service is rolled back to a previous version. | The previous version handles requests from the moment of rollback. |

Implementation and tests: [`auth-store.ts`](services/proposal-worker/src/auth-store.ts) [`cloud.ts`](services/proposal-worker/src/cloud.ts) [`index.ts`](services/proposal-worker/src/index.ts) [`wrangler.toml.example`](services/proposal-worker/wrangler.toml.example) [`cloud.test.ts`](services/proposal-worker/src/cloud.test.ts) [`deployment.test.mjs`](services/proposal-worker/scripts/deployment.test.mjs) [`proposal-deployment.md`](docs/proposal-deployment.md) [`release-signing.md`](docs/release-signing.md)

## 7. Vulnerability handling

### 7.1 Versions that receive fixes

| Target | Security fixes |
|---|---|
| The Microsoft Store release | Provided (the Microsoft Store updates it to the latest version) |
| The latest EXE release | Provided |
| `main` (`cytellect.app`, the cloud features and the Docker release) | Provided |
| Earlier EXE releases | Not provided (they move to the latest version through the in-app update) |

### 7.2 Scope

This repository's code, the Windows release (Microsoft Store and EXE), the Docker release, `cytellect.app`, the relay service and the inference server are in scope. Issues arising from how Cytellect configures or uses an external service are also in scope. Vulnerabilities in bundled third-party components (Fiji, Cellpose and others) and in the external services themselves are handled by their upstream projects and providers.

### 7.3 Reporting a vulnerability

Report vulnerabilities through GitHub's private reporting feature. Selecting **Report a vulnerability** under the repository's **Security** tab submits a report visible only to the reporter and the repository maintainers ([report form](https://github.com/genellect/cytellect/security/advisories/new)). Do not describe vulnerabilities in public places such as issues, pull requests or discussions.

Include the following in a report.

- The affected commit, or the version of the Windows release
- Reproduction steps
- The expected impact

### 7.4 Rules for testing

- Test with your own account and with synthetic or public data.
- Do not touch other researchers' data or accounts.
- Do not perform tests that take the service down.
- Do not disclose the vulnerability until the fixed version has been distributed (for at most 90 days).

### 7.5 Response to a report

1. Reasonable reports receive a reply within three days.
2. The affected scope is identified, the severity is assessed with CVSS, and both are shared with the reporter.
3. The issue is fixed in a private security advisory and the fixed version is distributed. The reporter is asked to withhold disclosure until distribution, for at most 90 days.
4. After the release, the security advisory is published and a CVE is requested where appropriate. The reporter is credited by name on request.

Published security advisories are available in the [list](https://github.com/genellect/cytellect/security/advisories).

## 8. Related documents

| Document | Content |
|---|---|
| [Release signing](docs/release-signing.md) | Creating, registering, rotating and revoking the signing key (in Japanese) |
| [Team development rules, section 6](docs/team-development.md#6-research-data) | The handling of research data and credentials in development |
| [Privacy policy](https://cytellect.app/privacy) | Information handled by the Microsoft Store release and the cloud features (in Japanese) |
