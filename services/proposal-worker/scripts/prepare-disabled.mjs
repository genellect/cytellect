import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

// Generate a separate, reviewable configuration. Never inherit a possibly enabled
// operator configuration or replace one in place.
const [accountId, databaseId] = process.argv.slice(2);
if (!/^[a-f0-9]{32}$/i.test(accountId ?? "")
  || !/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(databaseId ?? "")) {
  console.error("Usage: node scripts/prepare-disabled.mjs ACCOUNT_ID D1_DATABASE_ID");
  process.exit(1);
}
const config = {
  name: "cytellect-proposal", account_id: accountId, main: "src/index.ts",
  compatibility_date: "2026-10-01", workers_dev: true,
  d1_databases: [{ binding: "DB", database_name: "cytellect-proposal", database_id: databaseId, migrations_dir: "migrations" }],
  vars: {
    OPENAI_MODEL: "gpt-6.1-sol", MONTHLY_BUDGET_USD: "0", DEVICE_MONTHLY_REQUESTS: "0",
    PRICE_INPUT_USD_PER_MTOK: "", PRICE_OUTPUT_USD_PER_MTOK: "",
    PRICE_CACHED_INPUT_USD_PER_MTOK: "", PRICE_CACHE_WRITE_USD_PER_MTOK: "",
    REASONING_EFFORT: "medium", LOW_EFFORT_EVALUATED: "false", MAX_OUTPUT_TOKENS: "8000",
  },
  observability: { enabled: false },
};
try {
  writeFileSync(fileURLToPath(new URL("../wrangler.disabled.json", import.meta.url)), `${JSON.stringify(config, null, 2)}\n`, { flag: "wx", mode: 0o600 });
  console.info("Created wrangler.disabled.json; provider budget and device quota are zero. No remote changes made.");
} catch {
  console.error("Configuration not created; check permissions or review the existing file. Existing configuration was not overwritten.");
  process.exitCode = 1;
}
