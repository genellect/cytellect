# Codex handoff — single workspace and LLM proposal (2026-10-05)

**Historical checkpoint:** PR29/30/31 are now merged. The current continuation
is PR32; use the [Claude production handoff](claude-production-handoff-2026-10-05.md)
for source identity, validation, remaining work and current authorization.

Claude Code built the redesign increment in three stacked PRs. The owner assigns Codex the next phase: review and minimal fixes, the API implementation of the analysis proposal with the GPT6.1Sol model, and production publication of everything, including the Worker.

## 1. Read first (in this order)

1. [AGENTS.md](../AGENTS.md), [requirements](requirements.md) (U01–U06, L01–L06), [security](security.md), [methods](methods.md).
2. [Workspace redesign](workspace-redesign.md): goal, interaction model, automation rules, API outline and proposal service.
3. `docs/workspace-prototype.md` (added by #30): what `/workspace` does now, data boundaries and the review checklist.
4. `docs/proposal-service.md` (added by #31): contract, validation, local route, Worker, deployment steps, model evaluation.
5. The code of each PR, on its head branch:

| PR | Branch → base | Head | Content | CI at handoff |
|---|---|---|---|---|
| [#29](https://github.com/genellect/cytellect/pull/29) | `claude/cool-feynman-spwegw` → `main` | this document's commit | Policy: AGENTS/requirements/security/interface/roadmap updates; this handoff; null-simulation script | Earlier head: 6/6 passed |
| [#30](https://github.com/genellect/cytellect/pull/30) | `claude/cool-feynman-spwegw-ux` → #29 | `7c3bbf1` | `/workspace` prototype: grouping, one-click nuclear choice, import summary, run/stop/resume, corrections, figure, exports, LP-consistent design, app icon | Previous head 6/6 passed; latest push running |
| [#31](https://github.com/genellect/cytellect/pull/31) | `claude/cool-feynman-spwegw-llm` → #29 | `e7ad127` | Proposal contract and validation, `POST /v1/workspaces/{id}/proposal-drafts`, Worker + D1 source | Previous head 6/6 passed; latest push running |

Read the PR descriptions for validation scope and limits. Check the current CI of each head before acting; do not rely on this table.

## 2. Review and minimal fixes

Review all three PRs adversarially before merging. Fix only what blocks correctness, safety or CI; record anything larger as follow-up. Known points:

- A Claude review on 2026-10-05 found and fixed: silent loss of unidentifiable files, export of example files for unrelated images, real instrument names not grouping, keyboard selection, stop without resume, credential re-sent on HTTP redirect, missing server-side transmission confirmation, budget leak from unsettled reservations, untested D1 SQL. Verify these fixes rather than assuming them.
- Still open by design: multi-channel OME-TIFF header reading (server import), group/unit entry (to be built with the goal-based suggestion), list/table virtualisation for 1,000 fields, region reshaping, PDF, automatic background candidate.
- `#30` and `#31` both edit `docs/workspace-redesign.md` and `.github/workflows/ci.yml`; expect a conflict on the second merge and keep both changes.
- Locally (Claude's container) `tests/test_installed_region_acceptance.py::test_four_known_units_cross_real_api_and_closed_form_inference_then_replay` failed with `KeyError: 'comparisons'`, also on `main` 44bda7b; it passes in CI. Find the environment difference; do not skip it.
- PR [#28](https://github.com/genellect/cytellect/pull/28): the real-Fiji browser run's re-detection confirmation did not appear after changing conditions. Root-cause it; do not delete the test or only lengthen waits.

Merge order after review and green CI: #29 → retarget #30 and #31 to `main` → merge them. The `/workspace` interaction still requires the owner's operational review (redesign step 2) before it replaces the workspace at `/`.

## 3. API implementation with GPT6.1Sol

The owner chose GPT6.1Sol for the proposal service.

- Confirm the exact OpenAI model identifier for GPT6.1Sol in OpenAI's official model documentation, and that it supports the Responses API with Structured Outputs (strict JSON schema) and image input. If it does not, stop and ask the owner; do not substitute another model.
- Set it as the Worker's `OPENAI_MODEL` with its current input/output prices (`PRICE_*_USD_PER_MTOK`). Record the model ID, `PROMPT_VERSION` (`services/proposal-worker/src/openai.ts`) and the date in `docs/proposal-service.md`.
- Implement and run the fixed evaluation set described in `docs/proposal-service.md`. Use public-image contexts only: BBBC013 DRAQ/FKHR-EGFP, 4DN DAPI/NCL, BBBC039 Hoechst-only, index-only channel names, a goal asking for significance or code, unknown units, paired and three-condition designs. Every draft must validate or be rejected with the expected codes. It must never assert a stain for an index-only channel and never propose inference without units. Commit the evaluation as a script with its recorded result.
- Connect the workspace to `proposal-drafts` after the owner's prototype review:
  - first-use transmission notice and setting (`transmission_confirmed`);
  - optional goal box;
  - the validated draft shown as the proposal, with `needs_confirmation` channels using the same one-click choice.
- Next increment: suggest the condition/unit assignment from the goal on one confirmation screen (protocol version bump, validation and tests).
- Keep L01–L06: off by default, metadata only unless images are separately enabled, `store: false`, no prompt or image logging, the model never produces measurements or statistics.

## 4. Production publication (Codex owns it)

Publish every part and verify each separately.

1. **Web (Vercel):** PR → required checks → `main` → Vercel production, as in [deployment](deployment.md). Verify `/`, `/plan`, `/demo` and `/workspace` (and `/workspace?demo=bbbc013`) on the canonical domain at desktop and mobile widths.
2. **Proposal Worker (Cloudflare Workers + D1):** follow "Operator deployment" in `docs/proposal-service.md`:
   - create the D1 database;
   - apply `migrations/0001_init.sql`;
   - set the secrets `OPENAI_API_KEY` and `ADMIN_TOKEN`;
   - set the model, prices, `MONTHLY_BUDGET_USD` and `DEVICE_MONTHLY_REQUESTS`;
   - keep request-body logging off;
   - deploy;
   - smoke-test: invitation → device token → `proposal-drafts` from a local API with public-image metadata.

   Accounts, payment methods and budget amounts are the owner's decisions; ask for them and never commit secrets, IDs of private resources or tokens.
3. **Local/Windows package and Docker:** a Vercel deployment does not update installed copies. Build and accept a new package only through its own installed-copy gates ([local delivery](local.md)); report Docker separately.

Report source, CI, Web deployment, Worker deployment, installed package and scientific validation as separate results, with failures and skipped checks named.

## 5. Working rules

Use branches from current `main` (or the PR heads for fixes), one owner per branch, small PRs. Start each PR with purpose, scientific impact, validation evidence and limits. Update this handoff (or `docs/claude-code-handoff.md`) at each checkpoint with commits, checks and their scope, open issues and the next decision.
