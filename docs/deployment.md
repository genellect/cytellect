# Git-driven publication

The normal release path is feature branch → pull request → required CI → merge into main → Vercel automatic production deployment. Never use an uncommitted working directory as the production source. A successful merge, Vercel build, hosted browser check, analysis-server acceptance and scientific validation are distinct states.

Vercel project cytellect is connected to genellect/cytellect with apps/web as root, Node 24, pnpm frozen install and pnpm build. The production branch is main. Preview branches are review deployments. Use Git integration rather than copying a local CLI token into CI secrets. The GitHub App is authorized only for this repository.

The initial bootstrap deployed a clean archive of f172afbf4396a8a4fb6be839435af375fc9f03bf via CLI to establish the account/project connection. Vercel assigned that first deployment to production automatically. Record this one-time bootstrap separately; subsequent production publication must follow main. Public URL: https://cytellect.vercel.app/demo . At bootstrap it serves only cleared published microscopy and recorded results. It does not expose a public analysis API or accept private images.

CI checks Python lint/types/numerical/API/security tests, generated contracts, Web checks/build, real pinned Fiji on Linux, browser workflow and Compose configuration. A Compose configuration check is not a container startup test. No research images or credentials enter CI logs/artifacts. Synthetic inputs are confined to deterministic/internal workflow tests; public viewer uses registered published images.

After merge, verify the deployment commit SHA equals main, build state is READY, then run hosted public Desktop/Mobile tests. When an analysis host exists, repeat the private access/upload/edit/statistics/export/expiry checks on that host before inviting researchers. Roll back by reverting the release commit through the same Git workflow. Emergency alias rollback must be recorded and followed by a matching Git revert.

## Current delivery decision

The first verified implementation was merged through PR #1 as ee81ebfe33f1e99a8f58a8f70fb4b0916acc3810. Its required Python, Web, Linux Fiji/browser and actual isolated worker-container checks passed. Hosted browser acceptance for that deployment is tracked separately.

The next release adds local browser operation because a low-cost hosted backend has not yet passed cost, persistence and retention review. Researchers still use the Web interface; the API and Fiji worker run on the same PC. This is a deployment adapter, not a replacement for shared measurement/statistics contracts. Local setup, browser acceptance and cloud migration remain separate gates. See the [cost/constraint comparison](hosting-costs.ja.md) and [resource measurements](resource-benchmark.md).

No hosting provider, paid plan or new domain has been purchased. The following VM comparison is retained as a baseline, not a selected deployment.

## Always-on host baseline (not purchased)

The existing Compose option uses one Linux x86-64 host, local SSD and one analysis job at a time. Its worker-container limit is 5 GB. Host sizing must account for the API, SQLite and OS as well as the Java heap and native TensorFlow allocations. The 4096² capacity workload failed at both 2 and 4 GiB Java heaps; an 8 GB host is not proof of support. GPU is not required by the current CPU-verified engine.

Options checked 2026-10-02:

| Option | Published configuration | Listed monthly cost | Consideration |
|---|---|---|---|
| Sakura VPS, Ishikari | 6 virtual cores, 8 GB, 400 GB SSD | JPY 7,040 incl. tax, monthly billing | Baseline comparison; outside the desired low-cost starting point |
| AWS Lightsail, Tokyo | 2 vCPU, 8 GB, 160 GB SSD, public IPv4 bundle | USD 44 before applicable taxes/extra usage | Existing AWS familiarity can simplify operations; lower CPU headroom |

Sources: [Sakura specifications](https://vps.sakura.ad.jp/specification/), [Lightsail bundles](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-bundles.html), [Lightsail regions](https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-regions-and-availability-zones-in-amazon-lightsail.html). Prices are not a purchase authorization. Domain, Vercel plan suitability and any excess usage remain separate decisions. No automatic snapshots of research volumes in this PoC.

Use app.<controlled-domain> for Vercel and api.<same-controlled-domain> for the server, HTTPS for both. Do not point at an unrelated existing site without authorization. Strict same-site sessions require this domain arrangement. DNS for the API should resolve directly to the TLS proxy, without a public research-content cache. The owner chooses the domain and creates paid resources; credentials remain outside chat and Git.

## Provisioning and acceptance sequence

1. Select host/region/domain and complete the account/payment steps. Create the x86-64 Linux instance and operator-controlled SSH access. No credentials in this repository.
2. Install Docker Engine/Compose from their official packages. Restrict SSH to operator access; expose only HTTPS/HTTP at the TLS proxy. Keep API port 8000 and SQLite private.
3. Check out the reviewed main commit. Create the dedicated runtime directory outside the checkout, owned by UID 10001 and mode 0700. Use local disk, not NFS.
4. Set CYTELLECT_RUNTIME_DIR, CYTELLECT_API_HOST, CYTELLECT_APP_ORIGIN and secure cookies in a host-private environment. Start the Compose TLS configuration described in security.md. Pin the deployed commit and container digests in the operator record.
5. Point the UI/API hostnames and set NEXT_PUBLIC_API_ORIGIN for the Vercel production build. This change follows a main release. Test the public fixtures first.
6. Verify denied worker egress, memory/time cancellation, restart recovery, cross-session artifact denial, secure cookies/CORS/CSRF, quota, 24-hour expiry and physical deletion. Confirm no raw images in logs/backups/CDN.
7. Issue one-use invitations privately. Only then permit private research uploads. Run M4 scientific and M5 usability acceptance separately.

See security.md for retention and recovery. Server deployment is pending host selection; UI publication is not reported as full hosted-MVP completion.

## Research-workflow publication checkpoints

PR #10 published the revised landing page and no-upload planning guide as main
0a2d6ff1ea263b3980a9288f6e08eba3a185a918. PR #11 published the guided generic
region and descriptive-output source as main dd64f26db0e4ea15970828aaa6dbcae3f9365696.
For PR #11, required CI run 37132236632 passed Python, Web, Linux Fiji/browser
and Windows checks. Vercel Git integration produced READY production deployment
`dpl_ECpWNqM2x2DEUkWSAQWPYCEGjhk9` from that exact merge SHA.

Canonical `https://cytellect.vercel.app/` browser verification covered the public
landing/planning interaction, saved planning JSON, 1440/390 px layout, console
errors and unexpected API/origin requests. This public-page evidence is separate
from the production-build private API/worker workflows: nine cases, followed by
two generic reruns after the scoped mobile control fix. The distributed local.10
package and hosted private-analysis status were unchanged by these releases.
