import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, copyFileSync, mkdirSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { verifyDisabled } from "./verify-disabled.mjs";

test("disabled configuration is account-bound, secret-free and never overwritten", () => {
  const root = mkdtempSync(join(tmpdir(), "cytellect-deploy-"));
  try {
    mkdirSync(join(root, "scripts"));
    const script = join(root, "scripts", "prepare-disabled.mjs");
    copyFileSync(new URL("./prepare-disabled.mjs", import.meta.url), script);
    const args = [script, "a".repeat(32), "11111111-1111-4111-8111-111111111111"];
    assert.equal(spawnSync(process.execPath, args).status, 0);
    const text = readFileSync(join(root, "wrangler.disabled.json"), "utf8");
    const config = JSON.parse(text);
    assert.equal(config.vars.MONTHLY_BUDGET_USD, "0");
    assert.equal(config.vars.DEVICE_MONTHLY_REQUESTS, "0");
    assert.equal(config.observability.enabled, false);
    assert.equal(config.account_id, "a".repeat(32));
    assert.equal("OPENAI_API_KEY" in config.vars, false);
    assert.equal(spawnSync(process.execPath, args).status, 1);
    assert.equal(readFileSync(join(root, "wrangler.disabled.json"), "utf8"), text);
    assert.equal(spawnSync(process.execPath, [script, "invalid", "invalid"]).status, 1);
  } finally { rmSync(root, { recursive: true, force: true }); }
});

test("remote verification sends no research context or valid proposal", async () => {
  const calls = [];
  const result = await verifyDisabled("https://example.workers.dev", "x".repeat(32), async (url, options) => {
    calls.push({ url, options });
    return new Response("{}", { status: calls.length === 1 ? 401 : 503, headers: { "cache-control": "no-store" } });
  });
  assert.equal(result.provider_calls, 0);
  assert.equal(calls.length, 2);
  for (const { options } of calls) {
    assert.equal(options.body, "{}");
    assert.equal(options.redirect, "error");
    assert.equal("idempotency-key" in options.headers, false);
  }
});

test("remote verification fails for an enabled or unavailable service", async () => {
  for (const status of [400, 401, 500, 200]) {
    let count = 0;
    await assert.rejects(verifyDisabled("https://example.workers.dev", "x".repeat(32), async () =>
      new Response("{}", { status: ++count === 1 ? 401 : status, headers: { "cache-control": "no-store" } })));
  }
});

test("remote verification refuses unsafe origins without any request", async () => {
  for (const target of ["http://example.com", "https://user:pass@example.com", "https://example.com/?token=x", "https://example.com/path"]) {
    await assert.rejects(verifyDisabled(target, "x".repeat(32), async () => { assert.fail("must not send"); }));
  }
});
