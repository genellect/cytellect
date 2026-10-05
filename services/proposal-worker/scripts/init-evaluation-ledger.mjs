/** Explicit, non-billable initialization. Never replace a lost ledger to renew approval. */
import { fileURLToPath } from "node:url";
import { EvaluationLedger } from "../src/evaluation-ledger.ts";

try {
  const ledger = await EvaluationLedger.open(
    process.env.CYTELLECT_PUBLIC_EVAL_LEDGER,
    fileURLToPath(new URL("../../..", import.meta.url)),
    Number(process.env.CYTELLECT_PUBLIC_EVAL_BUDGET_USD), true,
  );
  console.info(JSON.stringify({ status: "evaluation_ledger_ready", cumulative_accounted_upper_usd: ledger.accountedUsd() }));
  ledger.close();
} catch {
  console.error("evaluation_ledger_initialization_failed");
  process.exitCode = 1;
}
