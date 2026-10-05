/** Paid evaluation is never run by ordinary CI: both explicit flags and a cap are required. */
import { describe, expect, it } from "vitest";
import { draftProposal, inputTokenCeiling, MODEL } from "./openai";
import { expectedBehavior, PUBLIC_CASES } from "./public-cases";
import contract from "./contract.json";
import { matchesSchema } from "./schema";
import { APPROVED_TOTAL_USD, EvaluationLedger } from "./evaluation-ledger";

const processModule = "node:process";
const childModule = "node:child_process";
const pathModule = "node:path";
const urlModule = "node:url";
const { env, platform } = await import(processModule);

describe("public proposal evaluation", () => {
  it("keeps public inputs within the current closed context contract", () => {
    for (const item of PUBLIC_CASES) expect(matchesSchema(item.context, contract.context_schema), item.id).toBe(true);
  });
  it("does not count blanket rejection as a useful proposal", () => {
    const rejected = { recipe: "none", statistics: { kind: "descriptive" }, metrics: [] };
    expect(PUBLIC_CASES.filter((item) => expectedBehavior(item, rejected)).map((item) => item.id)).toEqual(["unsupported-frap"]);
  });

  it.skipIf(env.CYTELLECT_ALLOW_PAID_PUBLIC_EVAL !== "true")("evaluates fixed public method scenarios through Sol and the Python validator", async () => {
    const budget = Number(env.CYTELLECT_PUBLIC_EVAL_BUDGET_USD);
    const repeats = Number(env.CYTELLECT_PUBLIC_EVAL_REPEATS ?? "3");
    const effort = env.CYTELLECT_PUBLIC_EVAL_EFFORT ?? "medium";
    expect(!env.CI || env.CI === "false", "paid evaluation cannot run in CI").toBe(true);
    expect(Number.isFinite(budget) && budget > 0 && budget <= APPROVED_TOTAL_USD, "cumulative approved evaluation cap must be >0 and <=5 USD").toBe(true);
    expect(typeof env.CYTELLECT_PUBLIC_EVAL_LEDGER === "string" && env.CYTELLECT_PUBLIC_EVAL_LEDGER.length > 0,
      "an external durable ledger path is required; reuse it for every run").toBe(true);
    expect(Number.isInteger(repeats) && repeats >= 1 && repeats <= 3).toBe(true);
    expect(["low", "medium"]).toContain(effort);
    expect(Boolean(env.OPENAI_API_KEY), "operator must provide the key privately").toBe(true);
    const { spawnSync } = await import(childModule);
    const { resolve } = await import(pathModule);
    const { fileURLToPath } = await import(urlModule);
    const root = fileURLToPath(new URL("../../..", import.meta.url));
    const python = env.CYTELLECT_EVAL_PYTHON ?? resolve(root, platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python");
    const helper = resolve(root, "scripts/evaluate_sol_proposal.py");
    // The semantic oracle needs no API credentials. Retain only OS/runtime variables.
    const oracleEnv = Object.fromEntries(["PATH", "Path", "SystemRoot", "WINDIR", "TEMP", "TMP", "HOME", "VIRTUAL_ENV"]
      .filter((name) => typeof env[name] === "string").map((name) => [name, env[name]]));
    const oracleOptions = { cwd: root, encoding: "utf8", env: oracleEnv, timeout: 15_000, maxBuffer: 512 * 1024 };
    // Probe the local oracle before any paid request; never print its raw stderr.
    const probe = spawnSync(python, ["-c", "import cytellect_analysis.proposal_validation"], oracleOptions);
    expect(probe.status, "local semantic validator must be installed first").toBe(0);
    const settings = { apiKey: env.OPENAI_API_KEY, model: MODEL, maxOutputTokens: 8000, reasoningEffort: effort as "low" | "medium" };
    const ledger = await EvaluationLedger.open(env.CYTELLECT_PUBLIC_EVAL_LEDGER, root, budget);
    const report: Record<string, unknown>[] = [];
    try {
      for (let repetition = 0; repetition < repeats; repetition += 1) {
        for (const item of PUBLIC_CASES) {
        const reserved = 2 * (inputTokenCeiling(settings, item.context, []) * 2.5 + settings.maxOutputTokens * 10) / 1e6;
        // The committed file-backed hold precedes the first provider call. A crash
        // leaves it in place; another process or later run cannot reset the cap.
        const reservation = ledger.reserve(item.id, reserved);
        if (!reservation) {
          report.push({ id: item.id, repetition, outcome: "budget_stop" });
          console.info(JSON.stringify({ model: MODEL, effort, cumulative_accounted_upper_usd: ledger.accountedUsd(), report }));
          throw new Error("public_evaluation_budget_exhausted");
        }
        const started = Date.now();
        try {
          const result = await draftProposal(settings, item.context, []);
          const cost = result.usageComplete
            ? ((result.inputTokens - result.cachedInputTokens) * 2.5 + result.cachedInputTokens * 0.1 + result.outputTokens * 10) / 1e6 : reserved;
          if (result.usageComplete) ledger.settle(reservation, cost, {
            inputTokens: result.inputTokens, cachedInputTokens: result.cachedInputTokens, outputTokens: result.outputTokens, calls: result.calls,
          });
          const checked = spawnSync(python, [helper], { ...oracleOptions, input: JSON.stringify({ context: item.context, draft: result.draft }) });
          if (checked.status !== 0) throw new Error("semantic_oracle_failed");
          const semantic = JSON.parse(checked.stdout);
          report.push({ id: item.id, repetition, valid: semantic.valid, codes: semantic.codes, useful: expectedBehavior(item, result.draft),
            latency_ms: Date.now() - started, calls: result.calls, input_tokens: result.inputTokens, output_tokens: result.outputTokens,
            accounted_upper_usd: cost });
        } catch {
          // Do not settle or expire unknown billing; its durable hold still counts.
          report.push({ id: item.id, repetition, outcome: "request_failed", latency_ms: Date.now() - started });
        }
        }
      }
      console.info(JSON.stringify({ model: MODEL, effort, cumulative_accounted_upper_usd: ledger.accountedUsd(), report }));
      expect(report.filter((entry) => entry.valid !== true || entry.useful !== true), "inspect fixed case IDs; do not weaken expectations to hide failures").toEqual([]);
    } finally { ledger.close(); }
  }, 12 * 3 * 250_000);
});
