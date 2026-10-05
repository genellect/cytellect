import { afterEach, describe, expect, it } from "vitest";
import { EvaluationLedger } from "./evaluation-ledger";
const fsModule = "node:fs", osModule = "node:os", pathModule = "node:path";
const transferModule = "../scripts/transfer-evaluation-ledger.mjs";
const { mkdtempSync, mkdirSync, rmSync, writeFileSync, readFileSync } = await import(fsModule);
const { tmpdir } = await import(osModule);
const { join } = await import(pathModule);
const { exportLedger, activateLedger } = await import(transferModule);
const cryptoModule = "node:crypto", restoreModule = "../scripts/restore-evaluation-ledger.mjs";
const { createHash } = await import(cryptoModule);
const { restoreLedger } = await import(restoreModule);

const temps: string[] = [];
afterEach(() => { for (const item of temps.splice(0)) rmSync(item, { recursive: true, force: true }); });
async function fixture() {
  const temp = mkdtempSync(join(tmpdir(), "cytellect-transfer-")); temps.push(temp);
  const root = join(temp, "checkout"); mkdirSync(root);
  const source = join(temp, "source.sqlite"), destination = join(temp, "cloud.sqlite");
  const ledger = await EvaluationLedger.open(source, root, 5, true);
  ledger.reserve("unknown-billing", 0.3);
  const known = ledger.reserve("known-billing", 1)!;
  ledger.settle(known, 0.13363);
  ledger.close();
  return { root, source, destination };
}

describe("single-operator evaluation handoff", () => {
  it("preserves held and settled costs, freezes the original and activates the copy explicitly", async () => {
    const p = await fixture();
    expect(await exportLedger(p.source, p.destination, p.root)).toEqual({ accounted_upper_usd: 0.43363, source_frozen: true, destination_blocked: true });
    for (const file of [p.source, p.destination]) {
      const ledger = await EvaluationLedger.open(file, p.root, 5);
      expect(ledger.accountedUsd()).toBe(0.43363);
      expect(() => ledger.reserve("next-case", 0.2)).toThrow("reconciliation_required"); ledger.close();
    }
    await expect(activateLedger(p.destination, false, p.root)).rejects.toThrow("ack_required");
    await activateLedger(p.destination, true, p.root);
    await expect(activateLedger(p.source, true, p.root)).rejects.toThrow("snapshot_required");
    const active = await EvaluationLedger.open(p.destination, p.root, 5);
    expect(active.reserve("next-case", 4.6)).toBeNull();
    expect(active.reserve("next-case", 0.2)).toBeTruthy(); active.close();
    await expect(activateLedger(p.destination, true, p.root)).rejects.toThrow("snapshot_required");
  });
  it("cannot overwrite another ledger or export into Git", async () => {
    const p = await fixture(); writeFileSync(p.destination, "preserved");
    await expect(exportLedger(p.source, p.destination, p.root)).rejects.toThrow("destination_exists");
    await expect(exportLedger(p.source, join(p.root, "secret.sqlite"), p.root)).rejects.toThrow("outside_checkout");
  });
  it("never clears a genuine reconciliation block or initializes a new allowance", async () => {
    const p = await fixture();
    const ledger = await EvaluationLedger.open(p.source, p.root, 5);
    const hold = ledger.reserve("overspend", 0.1)!;
    expect(() => ledger.settle(hold, 0.2)).toThrow("reconciliation_required"); ledger.close();
    await expect(exportLedger(p.source, p.destination, p.root)).rejects.toThrow("source_blocked");
    await expect(activateLedger(p.source, true, p.root)).rejects.toThrow();
    await expect(activateLedger(join(p.root, "missing.sqlite"), true, p.root)).rejects.toThrow();
  });
  it("restores a hash-checked private snapshot without overwriting an existing cloud ledger", async () => {
    const p = await fixture(); await exportLedger(p.source, p.destination, p.root);
    const data = readFileSync(p.destination), cloud = join(p.root, "..", "restored.sqlite");
    const env = { CLAUDE_CODE_REMOTE: "true", CYTELLECT_EVAL_SINGLE_OPERATOR: "true", CYTELLECT_PUBLIC_EVAL_LEDGER: cloud,
      CYTELLECT_EVAL_LEDGER_SNAPSHOT_B64: data.toString("base64"), CYTELLECT_EVAL_LEDGER_SHA256: createHash("sha256").update(data).digest("hex") };
    await expect(restoreLedger({ ...env, CYTELLECT_EVAL_LEDGER_SHA256: "0".repeat(64) }, p.root)).rejects.toThrow("snapshot_invalid");
    expect(await restoreLedger(env, p.root)).toEqual({ accounted_upper_usd: 0.43363, active_destination: true });
    await expect(restoreLedger(env, p.root)).rejects.toThrow();
    const ledger = await EvaluationLedger.open(cloud, p.root, 5);
    expect(ledger.accountedUsd()).toBe(0.43363); ledger.close();
  });
});
